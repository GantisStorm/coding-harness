"""
Claude SDK Client Configuration & Security
===========================================

Functions for creating and configuring the Claude Agent SDK client.
Includes security hooks for bash command validation.
Updated for claude-agent-sdk 0.1.18 with direct options (no settings file).

TODO: Add unit tests for security validation functions. This is a security-critical
module that validates bash commands before execution. Test coverage should include:
- _bash_security_hook with allowed and blocked commands
- _validate_pkill_command with various process names
- _validate_chmod_command with various modes
- _validate_script_path with path traversal attempts
- _validate_script_arguments with injection attempts
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookContext, HookInput, HookJSONOutput, HookMatcher

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
    "WebFetch",  # Fallback for web content if searxng fails
    "Skill",  # For invoking .claude/skills/ in the project
)

# ============================================================================
# Security: Bash Command Validation
# ============================================================================
# Pre-tool-use hooks that validate bash commands for security.
# Uses an allowlist approach - only explicitly permitted commands can run.

# Allowed commands for development tasks
# Minimal set needed for the autonomous coding demo
_ALLOWED_COMMANDS = frozenset(
    {
        # File inspection
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        # File operations (agent uses SDK tools for most file ops, but cp/mkdir needed occasionally)
        "cp",
        "mkdir",
        "chmod",  # For making scripts executable; validated separately
        # Directory
        "pwd",
        # Node.js development
        "npm",
        "node",
        # Version control
        "git",
        # Process management
        "ps",
        "lsof",
        "sleep",
        "pkill",  # For killing dev servers; validated separately
        # Script execution
        "init.sh",  # Init scripts; validated separately
        "start.sh",  # Project start scripts; validated separately
        "cd",
        "gh",
        "echo",
    }
)

# Commands that need additional validation even when in the allowlist
_COMMANDS_NEEDING_EXTRA_VALIDATION = frozenset({"pkill", "chmod", "init.sh", "start.sh"})

# Security limits for command validation
_MAX_COMMAND_LENGTH = 10000  # Maximum length for bash commands
_MAX_SCRIPT_ARGS = 50  # Maximum number of script arguments
_MAX_ARG_LENGTH = 1000  # Maximum length for individual arguments

# Regex pattern for splitting on semicolons outside quotes
_SEMICOLON_SPLIT_PATTERN = re.compile(r'(?<!["\'])\s*;\s*(?!["\'])')

# Shell operators that indicate a new command follows
_SHELL_OPERATORS = frozenset({"|", "||", "&&", "&"})

# Shell keywords that should be skipped when extracting commands
_SHELL_KEYWORDS = frozenset(
    {
        "if",
        "then",
        "else",
        "elif",
        "fi",
        "for",
        "while",
        "until",
        "do",
        "done",
        "case",
        "esac",
        "in",
        "!",
        "{",
        "}",
    }
)


async def _bash_security_hook(
    input_data: HookInput,
    _tool_use_id: str | None,
    _context: HookContext,
) -> HookJSONOutput:
    """
    Pre-tool-use hook that validates bash commands using an allowlist.

    Only commands in ALLOWED_COMMANDS are permitted.

    This is an internal function used by the SDK hook system.

    Args:
        input_data: Typed dict containing tool_name and tool_input
        _tool_use_id: Optional tool use ID for tracking (unused but required by hook interface)
        _context: Hook context with session info (unused but required by hook interface)

    Returns:
        Empty dict to allow, or hookSpecificOutput with permissionDecision="deny" to block
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    # Validate command doesn't contain null bytes or exceed length limit
    if "\0" in command or len(command) > _MAX_COMMAND_LENGTH:
        return _deny_command("Command contains invalid characters or exceeds length limit")

    # Detect command substitutions and subshells
    if "$(" in command or "`" in command or "<(" in command:
        return _deny_command("Command substitutions and subshells are not allowed")

    # Extract all commands from the command string
    commands = _extract_commands(command)

    if not commands:
        # Could not parse - fail safe by blocking
        return _deny_command(f"Could not parse command for security validation: {command}")

    # Split into segments for per-command validation
    segments = _split_command_segments(command)

    # Check each command against the allowlist
    for cmd in commands:
        if cmd not in _ALLOWED_COMMANDS:
            return _deny_command(f"Command '{cmd}' is not in the allowed commands list")

        # Additional validation for sensitive commands
        if cmd in _COMMANDS_NEEDING_EXTRA_VALIDATION:
            # Find the specific segment containing this command
            cmd_segment = _get_command_for_validation(cmd, segments)
            if not cmd_segment:
                return _deny_command(f"Failed to locate command segment for validation: {cmd}")

            if cmd == "pkill":
                allowed, reason = _validate_pkill_command(cmd_segment)
                if not allowed:
                    return _deny_command(reason)
            elif cmd == "chmod":
                allowed, reason = _validate_chmod_command(cmd_segment)
                if not allowed:
                    return _deny_command(reason)
            elif cmd == "init.sh":
                allowed, reason = _validate_init_script(cmd_segment)
                if not allowed:
                    return _deny_command(reason)
            elif cmd == "start.sh":
                allowed, reason = _validate_start_script(cmd_segment)
                if not allowed:
                    return _deny_command(reason)

    return {}


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
       (see _ALLOWED_COMMANDS in this module)

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
    print("   - Bash commands restricted to allowlist (see _ALLOWED_COMMANDS)")
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
            # Security hooks (SDK 0.1.3+ typed)
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[_bash_security_hook]),
                ],
            },
            # Execution limits
            max_turns=1000,
            # Working directory - all file operations are relative to this
            cwd=str(project_dir.resolve()),
            # Filter noisy CLI stderr (socket watch errors on macOS)
            stderr=_stderr_filter,
        )
    )


# ============================================================================
# Private Helper Functions
# ============================================================================


def _is_path_safe(base_dir: Path, target_path: Path) -> bool:
    """
    Check if target_path is within base_dir (handles symlinks correctly).

    Uses Path.resolve() to resolve symlinks and relative paths to absolute paths,
    then verifies the target is within the base directory. This prevents path
    traversal attacks via symlinks or relative paths like ../../../../etc/passwd.

    Args:
        base_dir: The base directory that should contain the target
        target_path: The path to validate

    Returns:
        True if target_path resolves to a location within base_dir, False otherwise
    """
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return resolved_target.is_relative_to(resolved_base)
    except (ValueError, OSError):
        return False


def _split_command_segments(command_string: str) -> list[str]:
    """
    Split a compound command into individual command segments.

    Handles command chaining (&&, ||, ;) but not pipes (those are single commands).

    Args:
        command_string: The full shell command

    Returns:
        List of individual command segments
    """

    # Split on && and || while preserving the ability to handle each segment
    # This regex splits on && or || that aren't inside quotes
    segments = re.split(r"\s*(?:&&|\|\|)\s*", command_string)

    # Further split on semicolons
    # Note: This regex-based approach has limitations with escaped quotes and complex quoting.
    # For robust parsing of shell metacharacters within quoted strings, a full shell parser
    # would be needed. This simple regex works for common cases but may miss edge cases like:
    # echo "foo;bar" (semicolon inside quotes - should not split)
    # echo 'it\'s;done' (escaped quote - may cause incorrect split)
    result = []
    for segment in segments:
        sub_segments = _SEMICOLON_SPLIT_PATTERN.split(segment)
        for sub in sub_segments:
            sub = sub.strip()
            if sub:
                result.append(sub)

    return result


def _extract_commands(command_string: str) -> list[str]:
    """
    Extract command names from a shell command string.

    Handles pipes, command chaining (&&, ||, ;), and subshells.
    Returns the base command names (without paths).

    Args:
        command_string: The full shell command

    Returns:
        List of command names found in the string
    """
    commands = []

    # shlex doesn't treat ; as a separator, so we need to pre-process

    # Split on semicolons that aren't inside quotes (simple heuristic)
    # This handles common cases like "echo hello; ls"
    segments = _SEMICOLON_SPLIT_PATTERN.split(command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        tokens, _error = _safe_shlex_split(segment)
        if tokens is None:
            # Malformed command (unclosed quotes, etc.)
            # Return empty to trigger block (fail-safe)
            return []

        if not tokens:
            continue

        # Track when we expect a command vs arguments
        expect_command = True

        for token in tokens:
            # Shell operators indicate a new command follows
            if token in _SHELL_OPERATORS:
                expect_command = True
                continue

            # Skip shell keywords that precede commands
            if token in _SHELL_KEYWORDS:
                continue

            # Skip flags/options
            if token.startswith("-"):
                continue

            # Skip variable assignments (VAR=value)
            if "=" in token and not token.startswith("="):
                continue

            if expect_command:
                # Extract the base command name (handle paths like /usr/bin/python)
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


def _validate_pkill_command(command_string: str) -> tuple[bool, str]:
    """
    Validate pkill commands - only allow killing dev-related processes.

    Uses shlex to parse the command, avoiding regex bypass vulnerabilities.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    # Allowed process names for pkill
    allowed_process_names = {
        "node",
        "npm",
        "npx",
        "vite",
        "next",
    }

    tokens, error = _safe_shlex_split(command_string)
    if tokens is None:
        return False, f"Could not parse pkill command: {error}"

    if not tokens:
        return False, "Empty pkill command"

    # Separate flags from arguments
    args = []
    for token in tokens[1:]:
        if not token.startswith("-"):
            args.append(token)

    if not args:
        return False, "pkill requires a process name"

    # The target is typically the last non-flag argument
    target = args[-1]

    # For -f flag (full command line match), extract the first word as process name
    # e.g., "pkill -f 'node server.js'" -> target is "node server.js", process is "node"
    if " " in target:
        target = target.split()[0]

    if target in allowed_process_names:
        return True, ""
    return False, f"pkill only allowed for dev processes: {allowed_process_names}"


def _validate_chmod_command(command_string: str) -> tuple[bool, str]:
    """
    Validate chmod commands - only allow making files executable with +x.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    # pylint: disable=too-many-return-statements
    # Early returns improve readability for validation logic - each return handles a specific failure case
    tokens, error = _safe_shlex_split(command_string)
    if tokens is None:
        return False, f"Could not parse chmod command: {error}"

    if not tokens or tokens[0] != "chmod":
        return False, "Not a chmod command"

    # Look for the mode argument
    # Valid modes: +x, u+x, a+x, etc. (anything ending with +x for execute permission)
    mode = None
    files = []

    for token in tokens[1:]:
        if token.startswith("-"):
            # Skip flags like -R (we don't allow recursive chmod anyway)
            return False, "chmod flags are not allowed"
        elif mode is None:
            mode = token
        else:
            files.append(token)

    if mode is None:
        return False, "chmod requires a mode"

    if not files:
        return False, "chmod requires at least one file"

    # Only allow +x variants (making files executable)
    # This matches: +x, u+x, g+x, o+x, a+x, ug+x, etc.

    if not re.match(r"^[ugoa]*\+x$", mode):
        return False, f"chmod only allowed with +x mode, got: {mode}"

    return True, ""


def _validate_script_path(
    command_string: str,
    script_name: str,
    allowed_scripts: tuple[str, ...],
) -> tuple[bool, str]:
    """
    Common validation logic for script execution commands.

    Args:
        command_string: The full command string to validate
        script_name: Name of the script being validated (for error messages)
        allowed_scripts: Tuple of allowed script names/patterns

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    tokens, error = _safe_shlex_split(command_string)
    if tokens is None:
        return False, f"Invalid {script_name} command syntax: {error}"

    if not tokens:
        return False, f"Empty {script_name} command"

    # Get the script path (first token)
    script_token = tokens[0]

    # Handle ./ prefix
    script_base = script_token
    if script_token.startswith("./"):
        script_base = script_token[2:]

    # Verify it's an allowed script
    if not any(script_base == allowed for allowed in allowed_scripts):
        return False, f"Script must be one of: {', '.join(allowed_scripts)}"

    # Only allow exact ./ prefix to prevent path traversal
    if script_token != f"./{script_base}":
        return False, f"Only ./{script_base} is allowed, got: {script_token}"

    # Additional check: verify the resolved path is in the current directory
    # This prevents symlink attacks where ./script.sh is a symlink to /evil/script.sh
    try:
        current_dir = Path.cwd()
        script_path = Path(script_token)
        if not _is_path_safe(current_dir, script_path):
            return False, f"Script path resolves outside current directory: {script_token}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Broad catch is intentional: handle any path resolution error (OSError, ValueError, RuntimeError)
        return False, f"Failed to validate script path: {e}"

    # Validate arguments
    return _validate_script_arguments(tokens)


def _validate_script_arguments(tokens: list[str]) -> tuple[bool, str]:
    """
    Validate script arguments for dangerous characters that could enable command injection.

    Args:
        tokens: List of command tokens (including script name)

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    # Shell metacharacters that could enable command injection
    dangerous_chars = {";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r", "\\"}

    # Limit total number of arguments to prevent resource exhaustion
    if len(tokens) - 1 > _MAX_SCRIPT_ARGS:
        return False, f"Script has too many arguments (max {_MAX_SCRIPT_ARGS}, got {len(tokens) - 1})"

    # Limit argument length to prevent buffer overflow-style attacks

    # Check all arguments (skip the script name itself)
    for arg in tokens[1:]:
        # Check argument length
        if len(arg) > _MAX_ARG_LENGTH:
            return False, f"Script argument exceeds maximum length ({_MAX_ARG_LENGTH} chars): {arg[:50]}..."

        # Check for dangerous shell metacharacters
        for char in dangerous_chars:
            if char in arg:
                return False, f"Script argument contains dangerous character '{char}': {arg}"

        # Check for path traversal attempts
        if "../" in arg or "/.." in arg:
            return False, f"Script argument contains path traversal: {arg}"

        # Check for attempts to break out of quotes
        if arg.count("'") % 2 != 0 or arg.count('"') % 2 != 0:
            return False, f"Script argument contains unbalanced quotes: {arg}"

    return True, ""


def _validate_init_script(command_string: str) -> tuple[bool, str]:
    """Validate init.sh script execution."""
    return _validate_script_path(command_string, "init.sh", ("init.sh",))


def _validate_start_script(command_string: str) -> tuple[bool, str]:
    """Validate start.sh script execution."""
    # Allowed subcommands for start.sh
    allowed_subcommands = {
        "dev",
        "prod",
        "restart-dev",
        "stop",
        "check",
        "typecheck",
        "lint",
        "lint-fix",
        "build",
        "clean",
        "install",
        "setup",
        "test",
    }

    # First, validate the script path and arguments using the common helper
    is_valid, error_msg = _validate_script_path(command_string, "start.sh", ("start.sh",))
    if not is_valid:
        return False, error_msg

    # Additional validation: check subcommand if present
    tokens, error = _safe_shlex_split(command_string)
    if tokens is None:
        return False, f"Could not parse start script command: {error}"

    if len(tokens) > 1:
        subcommand = tokens[1]
        if subcommand not in allowed_subcommands:
            return False, f"start.sh subcommand '{subcommand}' not allowed. Allowed: {allowed_subcommands}"

    return True, ""


def _get_command_for_validation(cmd: str, segments: list[str]) -> str:
    """
    Find the specific command segment that contains the given command.

    Args:
        cmd: The command name to find
        segments: List of command segments

    Returns:
        The segment containing the command, or empty string if not found
    """
    for segment in segments:
        segment_commands = _extract_commands(segment)
        if cmd in segment_commands:
            return segment
    return ""


def _deny_command(reason: str) -> HookJSONOutput:
    """Helper to create a deny response in SDK 0.1.18 format."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _safe_shlex_split(command_string: str) -> tuple[list[str] | None, str]:
    """
    Safely parse a command string using shlex.

    Args:
        command_string: The shell command to parse

    Returns:
        Tuple of (tokens, error_message). tokens is None if parsing failed.
    """
    try:
        tokens = shlex.split(command_string)
        return tokens, ""
    except ValueError as e:
        return None, str(e)


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
