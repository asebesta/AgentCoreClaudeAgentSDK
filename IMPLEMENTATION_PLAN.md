# Claude Agent SDK on Amazon Bedrock AgentCore Runtime - Implementation Plan

## Current State Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| Python | 3.9.6 | Tutorial recommends 3.10+, may need upgrade |
| AWS CLI | Configured | Account: 170076963924, User: agentcore-dev |
| Claude Code CLI | v2.0.76 | Meets requirement (2.0.0+) |
| claude-agent-sdk | Not installed | Required: v0.1.3+ |
| bedrock-agentcore | Not installed | Required: v1.0.4+ |
| bedrock-agentcore-starter-toolkit | Not installed | Required for deployment |
| Bedrock env vars | Not configured | Need CLAUDE_CODE_USE_BEDROCK, AWS_BEARER_TOKEN_BEDROCK, etc. |

---

## Phase 1: Environment Setup

### Step 1.1: Python Version Check
- Current: Python 3.9.6
- Required: Python 3.10+
- **Action**: Check if Python 3.10+ is available, or proceed with 3.9.6 (may work)

### Step 1.2: Install Required Packages
```bash
pip install claude-agent-sdk==0.1.3
pip install bedrock-agentcore==1.0.4
pip install bedrock-agentcore-starter-toolkit
```

### Step 1.3: Configure Environment Variables
Required environment variables for Bedrock integration:
```bash
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_BEARER_TOKEN_BEDROCK=<your-bedrock-api-key>
export AWS_REGION=us-west-2
export ANTHROPIC_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0
export ANTHROPIC_SMALL_FAST_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
```

---

## Phase 2: Local Development & Testing

### Step 2.1: Create Basic Agent Script
Create `claude_agent_quick_start.py` with:
- Basic example (simple math query)
- Options example (custom system prompt)
- Tools example (file operations)

### Step 2.2: Verify Claude Code Configuration
```bash
claude /model  # Verify model settings
```

### Step 2.3: Test Basic Agent Locally
```bash
python claude_agent_quick_start.py
```

---

## Phase 3: AgentCore Integration

### Step 3.1: Create AgentCore-Wrapped Version
Create `claude_agent_quick_start_agentcore.py` with:
1. Import: `from bedrock_agentcore import BedrockAgentCoreApp`
2. Initialize: `app = BedrockAgentCoreApp()`
3. Decorate entrypoint: `@app.entrypoint`
4. Run with: `app.run()`

### Step 3.2: Create requirements.txt
```
bedrock-agentcore==1.0.4
claude-agent-sdk==0.1.3
```

### Step 3.3: Test AgentCore Wrapper Locally
```bash
# Terminal 1: Start server
python claude_agent_quick_start_agentcore.py

# Terminal 2: Invoke
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "what is the largest language model?"}'
```

---

## Phase 4: Deployment to AgentCore Runtime

### Step 4.1: Configure AgentCore Deployment
```bash
agentcore configure -e claude_agent_quick_start_agentcore.py
```
This creates `.bedrock_agentcore.yaml` configuration file.

### Step 4.2: Customize Dockerfile
Modify `.bedrock_agentcore/Dockerfile` to include Claude Code installation:
```dockerfile
# Install Node.js and npm (for Claude Code)
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code
```

### Step 4.3: Deploy to AgentCore Runtime
```bash
agentcore launch -a claude_agent_quick_start_agentcore \
  --env CLAUDE_CODE_USE_BEDROCK=1 \
  --env AWS_BEARER_TOKEN_BEDROCK=<your-key> \
  --env DEBUG=true \
  --env ANTHROPIC_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --env ANTHROPIC_SMALL_FAST_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
```

### Step 4.4: Invoke Deployed Agent
```bash
agentcore invoke '{"prompt": "what is the largest language model?"}'
```

---

## Phase 5: Verification & Cleanup

### Step 5.1: Verify Deployment
- Check CloudWatch logs for invocation details
- Verify session isolation is working
- Test multiple concurrent invocations

### Step 5.2: Cleanup (when needed)
```bash
agentcore destroy
```

---

## Key Architecture Points

1. **Session Isolation**: Each invocation gets its own MicroVM environment
2. **8-Hour Execution Window**: Long-running agent tasks supported
3. **Framework Agnostic**: Same pattern works for LangGraph, CrewAI, etc.
4. **Minimal Code Changes**: Only 3 lines to wrap existing agent

---

## Files to Create

1. `claude_agent_quick_start.py` - Basic agent (local testing)
2. `claude_agent_quick_start_agentcore.py` - AgentCore-wrapped agent
3. `requirements.txt` - Python dependencies
4. `.bedrock_agentcore/Dockerfile` - Custom Dockerfile (auto-generated, then modified)

---

## Prerequisites Checklist

- [ ] AWS credentials configured with AgentCore permissions
- [ ] Bedrock API access/bearer token available
- [ ] Python 3.10+ (recommended) or 3.9.6 (may work)
- [ ] Claude Code CLI installed (v2.0.0+)

---

## Deployment Complete!

### Deployed Agent Details

| Property | Value |
|----------|-------|
| Agent Name | `claudeagentsdkdemo` |
| Agent ARN | `arn:aws:bedrock-agentcore:us-west-2:170076963924:runtime/claudeagentsdkdemo-M49JvLFDPh` |
| ECR Repository | `170076963924.dkr.ecr.us-west-2.amazonaws.com/bedrock-agentcore-claudeagentsdkdemo:latest` |
| Memory ID | `claudeagentsdkdemo_mem-ASCTQAHVFO` |
| Region | `us-west-2` |

### Quick Commands

```bash
# Activate environment
source venv/bin/activate

# Invoke the agent
agentcore invoke '{"prompt": "Your question here"}'

# Check agent status
agentcore status

# View logs
aws logs tail /aws/bedrock-agentcore/runtimes/claudeagentsdkdemo-M49JvLFDPh-DEFAULT --log-stream-name-prefix "2025/12/28/[runtime-logs]" --follow

# Destroy resources (when done)
agentcore destroy
```

### Key Learnings

1. **Model ID Format**: Use `us.anthropic.claude-*` prefix for cross-region inference profiles
2. **IAM Auth**: Can use IAM credentials instead of bearer tokens for Bedrock
3. **AgentCore Wrapper**: Only 3 lines of code to make existing agents deployable
4. **Session Isolation**: Each invocation gets its own MicroVM environment
