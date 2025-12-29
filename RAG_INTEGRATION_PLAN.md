# RAG / Document Retrieval Integration Plan

## Problem Statement
Need semantic search across 100s of documents. Simple file tools (S3 read/list) can't adequately search, index, or process documents at scale.

---

## Architecture

```
┌─────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  S3 Bucket  │────▶│ Bedrock Knowledge   │────▶│  Vector Store   │
│  (docs)     │     │ Base (auto-chunks,  │     │  (OpenSearch or │
│             │     │  embeds, indexes)   │     │   Aurora)       │
└─────────────┘     └─────────────────────┘     └────────┬────────┘
                                                         │
                    ┌────────────────────────────────────┘
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│  Claude Agent (ClaudeAgentOptions)                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  MCP Tool: search_documents(query) → Knowledge Base API    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Recommended Approach: Bedrock Knowledge Bases + Custom MCP Tool

### Why This Approach
1. **Fully Managed**: No infrastructure for chunking, embeddings, vector storage
2. **AWS-Native**: Tight integration with Bedrock, IAM, S3
3. **Production-Ready**: Built-in monitoring, security, compliance
4. **Scalable**: Handles hundreds to thousands of documents
5. **Multimodal**: Supports images, tables, charts in documents

### What Knowledge Bases Handles Automatically
- Document parsing (PDF, Word, Excel, HTML, Markdown, images)
- Chunking strategies:
  - Fixed-size (~300 tokens recommended)
  - Hierarchical (parent/child structure)
  - Semantic (analyzes text relationships)
- Embeddings (Amazon Titan Text Embeddings V2 default)
- Vector storage & indexing
- Retrieval API with relevance scoring

---

## Options Comparison

| Option | Monthly Cost | Setup | Best For |
|--------|-------------|-------|----------|
| **KB + OpenSearch Serverless** | ~$350+ | Low | Production, fully managed |
| **KB + Aurora pgvector** | ~$50-150 | Low | Cost-conscious, smaller scale |
| **Custom OpenSearch** | ~$350+ | Medium | Full control over retrieval |
| **Custom Aurora pgvector** | ~$50-150 | Medium | SQL + vectors combined |

### Cost Breakdown

**OpenSearch Serverless:**
- Minimum 4 half-OCUs = ~$350/month (redundant)
- Or 2 half-OCUs = ~$175/month (non-redundant, dev only)
- Storage: ~$0.02/GB-month

**Aurora Serverless v2 with pgvector:**
- ACU-based pricing, scales to zero
- Estimated $50-150/month for 100s of documents
- More cost-effective for smaller workloads

---

## Limitations

| Limit | Value |
|-------|-------|
| Max file size | 50 MB per document |
| Image files | 3.75 MB max |
| Knowledge Bases per account/region | 50 |
| Data sources per KB | 5 |

**Supported Formats:**
- Text: PDF, Word, Excel, HTML, Markdown, TXT, CSV
- Images: JPEG, PNG (within documents or standalone)

---

## Integration Code

### Custom MCP Tool for Knowledge Base

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
import boto3

bedrock = boto3.client('bedrock-agent-runtime', region_name='us-west-2')
KB_ID = "your-knowledge-base-id"

@tool
async def search_documents(
    query: str,
    num_results: int = 5
) -> dict:
    """
    Search the document library for relevant information.
    Returns document excerpts with citations and relevance scores.

    Args:
        query: The search query
        num_results: Number of results to return (default 5)

    Returns:
        Relevant document chunks with sources
    """
    response = bedrock.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={'text': query},
        retrievalConfiguration={
            'vectorSearchConfiguration': {
                'numberOfResults': num_results
            }
        }
    )

    results = []
    for item in response.get('retrievalResults', []):
        results.append({
            'content': item['content']['text'],
            'score': item.get('score', 0),
            'source': item.get('location', {}).get('s3Location', {}).get('uri', 'Unknown')
        })

    return {'results': results, 'count': len(results)}


# Alternative: Retrieve and Generate (includes LLM synthesis)
@tool
async def search_and_summarize(
    query: str,
    num_results: int = 5
) -> dict:
    """
    Search documents and generate a synthesized answer.
    Uses Claude to combine retrieved information into a coherent response.
    """
    response = bedrock.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KB_ID,
                'modelArn': 'arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0',
                'retrievalConfiguration': {
                    'vectorSearchConfiguration': {
                        'numberOfResults': num_results
                    }
                }
            }
        }
    )

    return {
        'answer': response['output']['text'],
        'citations': response.get('citations', [])
    }
```

### Integration with Agent

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server

# Create MCP server with document search tools
doc_search_server = create_sdk_mcp_server(
    name="document-search",
    tools=[search_documents, search_and_summarize]
)

SYSTEM_PROMPT = """You are a research assistant with access to a document library.

Use the search_documents tool to find relevant information from the knowledge base.
Use search_and_summarize when you need a synthesized answer from multiple sources.

Always cite your sources when providing information from documents."""

options = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    mcp_servers=[doc_search_server],
    max_turns=10,
)

async with ClaudeSDKClient(options) as client:
    await client.query("What does the research say about X?")
    # Agent will use search tools as needed
```

---

## Setup Steps

### 1. Create S3 Bucket for Documents
```bash
aws s3 mb s3://your-research-documents-bucket
aws s3 sync ./documents s3://your-research-documents-bucket/
```

### 2. Create Knowledge Base (Console or CLI)
- Go to Amazon Bedrock → Knowledge Bases → Create
- Select S3 as data source
- Choose chunking strategy (recommend: semantic or hierarchical)
- Select vector store:
  - OpenSearch Serverless (auto-provisioned) for production
  - Aurora PostgreSQL for cost-conscious dev

### 3. Note the Knowledge Base ID
```bash
# Will look like: XXXXXXXXXX
```

### 4. Update Agent Code
- Add MCP tool with KB_ID
- Update system prompt to mention document search capability
- Deploy to AgentCore

### 5. Test
```bash
agentcore invoke '{"prompt": "Search for information about X in our documents"}'
```

---

## What NOT to Use

### AgentCore Memory (LTM)
- Designed for conversation-derived memories, not document storage
- Extracts facts from conversations, doesn't ingest documents
- Use it for: session context, user preferences, conversation history
- Don't use for: document corpus, bulk ingestion, semantic search

### Raw S3 + File Tools
- Can't search or index
- Would need to read every document for each query
- Not scalable

---

## Phased Rollout

| Phase | Approach | Cost | Timeline |
|-------|----------|------|----------|
| **Dev/Test** | KB + Aurora pgvector | ~$50-100/mo | Start here |
| **Production** | KB + OpenSearch Serverless | ~$350+/mo | When validated |

---

---

## Multi-Tenant Considerations

### The 50 Knowledge Base Limit

| Knowledge Bases per account/region | 50 (not adjustable) |

**This becomes a problem if:** 1 KB per tenant in a SaaS environment.

### Multi-Tenant Patterns

| Scale | Approach |
|-------|----------|
| < 50 tenants | 1 KB per tenant (simple, true isolation) |
| 50-1000s tenants | Single KB + metadata filtering |
| Enterprise isolation | Separate AWS accounts or custom vector store |

### Recommended: Single KB + Metadata Filtering

**S3 Structure:**
```
documents-bucket/
├── tenant-a/
│   ├── doc1.pdf
│   └── doc2.pdf
├── tenant-b/
│   └── doc1.pdf
```

**Query with tenant filter:**
```python
response = bedrock.retrieve(
    knowledgeBaseId=KB_ID,
    retrievalQuery={'text': query},
    retrievalConfiguration={
        'vectorSearchConfiguration': {
            'numberOfResults': 5,
            'filter': {
                'equals': {
                    'key': 'x-amz-bedrock-kb-source-uri',
                    'value': f's3://bucket/tenant-{tenant_id}/'
                }
            }
        }
    }
)
```

### IAM and Access Control

**Important:** IAM cannot enforce metadata filtering at query time.

| Method | IAM Enforced? | Notes |
|--------|---------------|-------|
| Application-layer filtering | No | Your code injects tenant filter - must trust app |
| Separate KBs + IAM | Yes | IAM controls which KB you can query |
| S3 bucket policies | Yes | Controls source docs, not query results |
| API Gateway + Lambda | Yes | Inject tenant context server-side |

**The Gap:**
```python
# IAM CANNOT enforce this filter - attacker could change tenant_id
response = bedrock.retrieve(
    knowledgeBaseId=KB_ID,
    filter={'tenant_id': 'tenant-a'}  # ← Not IAM-protected
)
```

### Recommended Multi-Tenant Architecture

```
┌─────────────┐     ┌─────────────────────────────┐     ┌─────────────────┐
│  Client     │────▶│  AgentCore Runtime          │────▶│  Knowledge Base │
│  (JWT with  │     │  (server-side, trusted)     │     │  (single, shared│
│  tenant_id) │     │  Agent injects tenant filter│     │   with metadata)│
└─────────────┘     └─────────────────────────────┘     └─────────────────┘
```

**Key insight:** The agent IS the trusted boundary. No need for extra Lambda layer.

**Agent code injects tenant filter:**
```python
@app.entrypoint
async def main(payload: dict, context: RequestContext):
    # Tenant from authenticated context (server-side, trusted)
    tenant_id = context.identity.get('tenant_id')  # or from JWT claims

    # Tool uses tenant - client never touches this code
    @tool
    async def search_documents(query: str) -> dict:
        return bedrock.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'filter': {
                        'equals': {
                            'key': 'tenant_id',
                            'value': tenant_id  # Injected server-side
                        }
                    }
                }
            }
        )
```

**Why this works:**
- AgentCore runs server-side (not client-controlled)
- Our agent code extracts tenant from authenticated context
- Client can't tamper with agent code or filter injection
- Agent has direct KB access - no extra Lambda hop needed

**Benefits:**
- Simple architecture (agent → KB directly)
- Tenant filter enforced in trusted server-side code
- Scales to 1000s of tenants
- Single KB to manage

### Alternative: Row-Level Security (Aurora pgvector)

If using Aurora PostgreSQL as vector store:
```sql
-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their tenant's docs
CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_setting('app.tenant_id'));
```

Set tenant context per connection - enforced at database level.

---

## Open Questions

- [ ] What document formats will be used? (PDF, Word, etc.)
- [ ] Estimated document count and total size?
- [ ] Query volume expectations?
- [ ] Need for multimodal (images in documents)?
- [ ] Access control requirements (per-user document access)?

---

## References

- [Amazon Bedrock Knowledge Bases](https://aws.amazon.com/bedrock/knowledge-bases/)
- [Bedrock KB Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Claude Agent SDK Custom Tools](https://platform.claude.com/docs/en/agent-sdk/custom-tools)
- [AgentCore Memory vs RAG](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-ltm-rag.html)
