"""
Claude SDK Client Configuration
================================

Functions for creating and configuring the Claude Agent SDK client.
Updated for claude-agent-sdk 0.1.18 with direct options (no settings file).

Security hooks are defined in agent/core/hooks/ module.
"""

from __future__ import annotations

import os
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .hooks import get_all_hooks

# Puppeteer MCP tools for browser automation
_PUPPETEER_TOOLS = (
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
)

# GitLab MCP tools for project management
# Using @zereight/mcp-gitlab community MCP server (v2.0.11+)
# Docs: https://deepwiki.com/zereight/gitlab-mcp/4-tools-reference
#
# NOTE: We use MCP for ALL git operations to GitLab (no local git push).
# This avoids credential/authentication issues in Docker containers.
# Local git is only used for: status, diff, log, checkout, merge (read-only + local branch ops)
_GITLAB_TOOLS = (
    # Project operations
    "mcp__gitlab__get_project",
    # User operations
    "mcp__gitlab__get_users",
    "mcp__gitlab__my_issues",
    # Branch operations (MCP replaces git push -u origin branch)
    "mcp__gitlab__create_branch",
    # Commit operations (verify pushes)
    "mcp__gitlab__list_commits",
    "mcp__gitlab__get_commit",
    "mcp__gitlab__get_commit_diff",
    # File operations (MCP replaces git add + commit + push)
    "mcp__gitlab__get_file_contents",
    "mcp__gitlab__create_or_update_file",
    "mcp__gitlab__push_files",  # PRIMARY: push multiple files in single commit
    # Issue management
    "mcp__gitlab__create_issue",
    "mcp__gitlab__get_issue",
    "mcp__gitlab__update_issue",
    "mcp__gitlab__list_issues",
    "mcp__gitlab__create_note",
    # Labels
    "mcp__gitlab__create_label",
    "mcp__gitlab__list_labels",
    # Merge requests
    "mcp__gitlab__create_merge_request",
    "mcp__gitlab__get_merge_request",
    "mcp__gitlab__list_merge_requests",
    # Milestones (requires USE_MILESTONE=true)
    "mcp__gitlab__create_milestone",
    "mcp__gitlab__list_milestones",
    "mcp__gitlab__get_milestone",
    "mcp__gitlab__edit_milestone",
    "mcp__gitlab__get_milestone_issue",
    "mcp__gitlab__get_milestone_merge_requests",
)

# Context7 MCP tools for documentation search
# Using Context7 HTTP MCP server for library documentation
_CONTEXT7_TOOLS = (
    "mcp__context7__resolve_library_id",  # Find library by name
    "mcp__context7__get_library_docs",  # Get library documentation
)

# SearXNG MCP tools for web search
# Using local SearXNG instance via mcp-searxng
_SEARXNG_TOOLS = (
    "mcp__searxng__searxng_web_search",  # Web search using local SearXNG
    "mcp__searxng__web_url_read",  # Read content from URLs
)

# Built-in tools
_BUILTIN_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "Task",  # For spawning agents (uses SDK's built-in agent types)
    "WebFetch",  # Fallback for web content if searxng fails
    "Skill",  # For invoking .claude/skills/ in the project
)


def create_client(project_dir: Path, model: str) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use

    Returns:
        Configured ClaudeSDKClient

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. permission_mode - Auto-approve file edits within working directory
    3. Security hooks - Bash commands validated against an allowlist
       (see agent/core/hooks/ module for implementation)

    Uses SDK 0.1.18 direct options instead of settings file.
    """
    # Environment variables are validated in runner.py (entry point)
    # Get them here for MCP server configuration
    gitlab_token = os.environ.get("GITLAB_PERSONAL_ACCESS_TOKEN", "")
    gitlab_api_url = os.environ.get("GITLAB_API_URL", "https://gitlab.com/api/v4")
    context7_api_key = os.environ.get("CONTEXT7_API_KEY", "")
    searxng_url = os.environ.get("SEARXNG_URL", "http://localhost:8888")

    # Ensure project directory exists
    project_dir.mkdir(parents=True, exist_ok=True)

    print("Configuring Claude Agent SDK client:")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Working directory: {project_dir.resolve()}")
    print("   - permission_mode: acceptEdits (auto-approve file operations)")
    print("   - Bash commands restricted to allowlist (see agent/core/hooks/)")
    print(f"   - MCP servers: puppeteer (browser), gitlab (project mgmt), context7 (docs), searxng ({searxng_url})")
    print("   - Web search: SearXNG (primary), WebFetch (fallback)")
    print()

    # Note: Timeout configuration is not exposed in ClaudeAgentOptions (SDK 0.1.18)
    # The SDK handles timeouts internally for:
    # - API requests (uses Anthropic SDK defaults)
    # - MCP server startup (default: ~10s per server)
    # - MCP tool calls (no explicit timeout, relies on HTTP defaults)
    # If you need custom timeouts, they must be configured at the MCP server level
    # or via environment variables for specific MCP servers.

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            system_prompt=(
                "You are an expert full-stack developer building a production-quality web application. "
                "You use GitLab for project management and tracking all your work."
            ),
            # Tools configuration (SDK 0.1.12+)
            allowed_tools=[
                *_BUILTIN_TOOLS,
                *_PUPPETEER_TOOLS,
                *_GITLAB_TOOLS,
                *_CONTEXT7_TOOLS,
                *_SEARXNG_TOOLS,
            ],
            # Permission mode (SDK 0.1.18) - replaces settings file permissions
            # "acceptEdits" auto-approves Read, Write, Edit, Glob, Grep within cwd
            permission_mode="acceptEdits",
            # Sandbox configuration (SDK 0.1.18) - replaces settings file sandbox
            sandbox={
                "enabled": True,
                "autoAllowBashIfSandboxed": True,
            },
            # Load skills from project's .claude/ directory
            setting_sources=["project"],
            # MCP servers for external integrations
            # type: ignore[arg-type] - SDK expects a specific MCP server config type that's not publicly exported
            mcp_servers={  # type: ignore[arg-type]
                "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]},
                # GitLab MCP server using stdio transport
                "gitlab": {
                    "command": "npx",
                    "args": ["-y", "@zereight/mcp-gitlab"],
                    "env": {
                        "GITLAB_PERSONAL_ACCESS_TOKEN": gitlab_token,
                        "GITLAB_API_URL": gitlab_api_url,
                        "USE_MILESTONE": "true",
                    },
                },
                # Context7 HTTP MCP server for library documentation
                "context7": {
                    "type": "http",
                    "url": "https://mcp.context7.com/mcp",
                    "headers": {
                        "CONTEXT7_API_KEY": context7_api_key,
                    },
                },
                # SearXNG MCP server for web search (local instance)
                "searxng": {
                    "command": "npx",
                    "args": ["-y", "mcp-searxng"],
                    "env": {
                        "SEARXNG_URL": searxng_url,
                    },
                },
            },
            # Security hooks - see agent/core/hooks/ for implementation
            hooks=get_all_hooks(),
            # Execution limits
            max_turns=1000,
            # File checkpointing - enables rewinding file changes
            enable_file_checkpointing=True,
            extra_args={"replay-user-messages": None},
            # Working directory - all file operations are relative to this
            cwd=str(project_dir.resolve()),
            # Filter noisy CLI stderr (socket watch errors on macOS)
            stderr=_stderr_filter,
        )
    )


def _stderr_filter(msg: str) -> None:
    """
    Filter and log stderr messages from Claude Code client.

    Suppresses INFO-level messages from MCP servers to reduce noise.
    Logs WARNING and ERROR messages normally.

    Args:
        msg: stderr message string from Claude Code client
    """
    # Skip file watcher errors on socket files (macOS doesn't support watching sockets)
    if "EOPNOTSUPP" in msg:
        return
    # Skip other common noise
    if "watch" in msg.lower() and ".sock" in msg:
        return
    print(f"[CLI] {msg}")
