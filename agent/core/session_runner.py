"""
Session Runner
==============

Executes individual agent sessions using Claude SDK.
Extracted from orchestrator for single responsibility.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from claude_agent_sdk import AssistantMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage

from .output import SEPARATOR_LIGHT, emit_output

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient

# Callback types
OutputCallback = Callable[[str], None]
ToolCallback = Callable[[str, str, bool], None]  # (tool_name, content, is_error)


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    on_output: OutputCallback | None = None,
    on_tool: ToolCallback | None = None,
) -> tuple[str, str]:
    """Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        on_output: Optional callback for text output (TUI integration)
        on_tool: Optional callback for tool usage (TUI integration)

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    status_msg = "Sending prompt to Claude Agent SDK...\n"
    emit_output(on_output, status_msg)

    try:
        # Send the query
        await client.query(message)

        # Collect response text and show tool use
        response_text = ""
        async for response in client.receive_response():
            # Handle AssistantMessage (text and tool use)
            if isinstance(response, AssistantMessage):
                for block in response.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                        emit_output(on_output, block.text)
                    elif isinstance(block, ToolUseBlock):
                        _handle_tool_use(block, on_tool)

            # Handle UserMessage (tool results)
            elif isinstance(response, UserMessage) and isinstance(response.content, list):
                for block in response.content:
                    if isinstance(block, ToolResultBlock):
                        _handle_tool_result(block, on_tool)

        separator = "\n" + SEPARATOR_LIGHT + "\n"
        emit_output(on_output, separator)
        return "continue", response_text

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Error during agent session: {e}\n"
        emit_output(on_output, error_msg)
        return "error", str(e)


def _handle_tool_use(block: ToolUseBlock, on_tool: ToolCallback | None) -> None:
    """Handle a tool use block."""
    input_str = str(block.input)
    if len(input_str) > 200:
        input_str = input_str[:200] + "..."

    if on_tool:
        on_tool(block.name, input_str, False)
    else:
        print(f"\n[Tool: {block.name}]", flush=True)
        if input_str:
            print(f"   Input: {input_str}", flush=True)


def _handle_tool_result(block: ToolResultBlock, on_tool: ToolCallback | None) -> None:
    """Handle a tool result block."""
    result_content = block.content or ""
    is_error = block.is_error or False

    # Check if command was blocked
    if "blocked" in str(result_content).lower():
        if on_tool:
            on_tool("ToolResult", f"[BLOCKED] {result_content}", True)
        else:
            print(f"   [BLOCKED] {result_content}", flush=True)
    elif is_error:
        error_str = str(result_content)[:500]
        if on_tool:
            on_tool("ToolResult", f"[Error] {error_str}", True)
        else:
            print(f"   [Error] {error_str}", flush=True)
    else:
        if on_tool:
            on_tool("ToolResult", "[Done]", False)
        else:
            print("   [Done]", flush=True)
