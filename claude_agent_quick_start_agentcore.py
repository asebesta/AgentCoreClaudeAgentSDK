#!/usr/bin/env python3
"""Claude Agent SDK with AgentCore wrapper - maintains conversation context via Memory."""

import os
from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from bedrock_agentcore.memory.client import MemoryClient
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

app = BedrockAgentCoreApp()

# System prompt - guides agent behavior and enables multi-agent delegation
SYSTEM_PROMPT = """You are a helpful assistant that can handle complex tasks.

For complex or multi-step tasks, use the Task tool to delegate to specialized sub-agents:
- Use Task for research, code exploration, or analysis that benefits from focused attention
- Use Task for parallel work when multiple independent subtasks can run concurrently
- Each sub-agent gets its own context and can use all available tools

Keep responses concise and actionable. When delegating, clearly specify what you need from each sub-agent."""

# Memory configuration
MEMORY_ID = (
    os.environ.get("BEDROCK_AGENTCORE_MEMORY_ID") or
    os.environ.get("MEMORY_ID") or
    "claudeagentsdkdemo_mem-ASCTQAHVFO"
)
ACTOR_ID = "claude_agent"

print(f"Memory ID configured: {MEMORY_ID}")


def get_memory_client():
    """Get Memory client for session persistence."""
    return MemoryClient(region_name=os.environ.get("AWS_REGION", "us-west-2"))


def get_stored_session_id(memory_client: MemoryClient, conversation_id: str) -> str | None:
    """Retrieve stored Claude SDK session_id from AgentCore Memory."""
    if not MEMORY_ID:
        return None

    try:
        events = memory_client.list_events(
            memory_id=MEMORY_ID,
            actor_id=ACTOR_ID,
            session_id=conversation_id,
            max_results=10
        )

        print(f"Found {len(events)} events for conversation {conversation_id}")

        for event in events:
            if not isinstance(event, dict):
                continue

            # Payload is a list of message objects
            payload = event.get("payload", [])
            if not isinstance(payload, list):
                continue

            for msg in payload:
                # Message format: {"conversational": {"content": {"text": "..."}, "role": "..."}}
                if isinstance(msg, dict):
                    conversational = msg.get("conversational", {})
                    content = conversational.get("content", {}).get("text", "")

                    if isinstance(content, str) and content.startswith("__SESSION__:"):
                        session_id = content.replace("__SESSION__:", "").strip()
                        print(f"Found stored session: {session_id}")
                        return session_id

        return None
    except Exception as e:
        print(f"Error retrieving session: {e}")
        return None


def save_session_id(memory_client: MemoryClient, conversation_id: str, session_id: str, user_input: str, response: str):
    """Save the Claude SDK session_id to AgentCore Memory."""
    if not MEMORY_ID or not session_id:
        return

    try:
        # Format: (content, role) tuples
        memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=ACTOR_ID,
            session_id=conversation_id,
            messages=[
                (user_input, "USER"),
                (response, "ASSISTANT"),
                (f"__SESSION__:{session_id}", "OTHER")
            ]
        )
        print(f"Saved session {session_id} for conversation {conversation_id}")
    except Exception as e:
        print(f"Error saving session: {e}")


@app.entrypoint
async def main(payload: dict = None, context: RequestContext = None):
    """
    Main entrypoint - handles conversation with context persistence.

    Payload:
    {
        "prompt": "Your question",
        "conversation_id": "unique_id"  # Optional - for multi-turn conversations
    }
    """
    if not payload:
        return {"error": "No payload provided"}

    prompt = payload.get("prompt", "")
    if not prompt:
        return {"error": "No prompt provided"}

    # Get conversation_id from payload or use AgentCore session
    conversation_id = payload.get("conversation_id")
    if not conversation_id and context:
        conversation_id = context.session_id or "default"
    elif not conversation_id:
        conversation_id = "default"

    print(f"Conversation ID: {conversation_id}")

    # Check for existing session to resume
    memory_client = get_memory_client()
    stored_session = get_stored_session_id(memory_client, conversation_id)

    async def execute_query(resume_session: str | None = None) -> tuple[list[str], str | None]:
        """Execute query, optionally resuming a session. Returns (responses, session_id)."""
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            max_turns=10,
        )

        if resume_session:
            options.resume = resume_session

        responses = []
        new_session_id = None

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            responses.append(block.text)
                            print(f"Claude: {block.text}")

                if isinstance(message, ResultMessage):
                    new_session_id = message.session_id
                    print(f"Got session_id: {new_session_id}")

        return responses, new_session_id

    # Execute query with session resume fallback
    full_response = []
    session_id = None

    try:
        if stored_session:
            print(f"Resuming session: {stored_session}")
            try:
                full_response, session_id = await execute_query(resume_session=stored_session)
            except Exception as e:
                # Session expired or not found - start fresh
                # Error could be "No conversation found" or generic "Command failed"
                error_msg = str(e).lower()
                if "no conversation found" in error_msg or "exit code 1" in error_msg:
                    print(f"Session expired or not found, starting fresh")
                    full_response, session_id = await execute_query(resume_session=None)
                else:
                    raise
        else:
            print("Starting new session")
            full_response, session_id = await execute_query(resume_session=None)

    except Exception as e:
        print(f"Error during query: {e}")
        return {"error": str(e)}

    response_text = "\n".join(full_response)

    # Save session for future resumption
    if session_id:
        save_session_id(memory_client, conversation_id, session_id, prompt, response_text)

    return {
        "response": response_text,
        "conversation_id": conversation_id,
        "session_id": session_id
    }


if __name__ == "__main__":
    app.run()
