"""
Hooks Module for Claude Agent SDK
==================================

Security hooks for the Claude Agent. Currently provides bash command validation.

Usage:
------
    from agent.core.hooks import get_all_hooks

    options = ClaudeAgentOptions(
        ...
        hooks=get_all_hooks(),
    )
"""

from __future__ import annotations

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import HookEvent

from .security import _bash_security_hook

__all__ = [
    "_bash_security_hook",
    "HookMatcher",
    "get_all_hooks",
]


def get_all_hooks() -> dict[HookEvent, list[HookMatcher]]:
    """
    Get the hooks configuration for ClaudeAgentOptions.

    Currently only includes bash security validation.
    Other hooks (logging, triggers, etc.) can be added back as needed.

    Returns:
        dict with hook event keys and HookMatcher lists.
    """
    return {
        "PreToolUse": [
            # Security validation for bash commands
            HookMatcher(matcher="Bash", hooks=[_bash_security_hook], timeout=60),
        ],
    }
