#!/bin/bash
# Script to run the AgentCore wrapper locally with Bedrock configuration

# Activate virtual environment
source /Users/aaron/playground/LitReview/ResearchAgent/AgentCoreClaudeAgentSDK/venv/bin/activate

# Configure Claude Code to use Bedrock
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=us-west-2
# Use us. prefix for cross-region inference profile
export ANTHROPIC_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
export ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0

# Run the agent
python /Users/aaron/playground/LitReview/ResearchAgent/AgentCoreClaudeAgentSDK/claude_agent_quick_start_agentcore.py
