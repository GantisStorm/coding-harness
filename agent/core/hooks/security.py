"""
Bash Command Security Hook
==========================

Pre-tool-use hook that validates bash commands using an allowlist approach.
Only commands in ALLOWED_COMMANDS are permitted to execute.

This module was extracted from agent/core/client.py to consolidate
security validation logic for the SDK hook system.

Security Features:
- Command allowlist validation
- Sensitive command extra validation (pkill, chmod, scripts)
- Command substitution/subshell detection
- Path traversal prevention
- Script argument sanitization
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from claude_agent_sdk import HookContext, HookInput, HookJSONOutput

__all__ = ["_bash_security_hook"]

# ============================================================================
# Constants: Allowed Commands
# ============================================================================

# Allowed commands for development tasks
# Minimal set needed for the autonomous coding demo
ALLOWED_COMMANDS = frozenset(
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
COMMANDS_NEEDING_EXTRA_VALIDATION = frozenset({"pkill", "chmod", "init.sh", "start.sh"})

# ============================================================================
# Constants: Security Limits
# ============================================================================

# Maximum length for bash commands
MAX_COMMAND_LENGTH = 10000

# Maximum number of script arguments
MAX_SCRIPT_ARGS = 50

# Maximum length for individual arguments
MAX_ARG_LENGTH = 1000

# ============================================================================
# Constants: Parsing Patterns
# ============================================================================

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


# ============================================================================
# Main Hook: Bash Security Validation
# ============================================================================


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
    if "\0" in command or len(command) > MAX_COMMAND_LENGTH:
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
        if cmd not in ALLOWED_COMMANDS:
            return _deny_command(f"Command '{cmd}' is not in the allowed commands list")

        # Additional validation for sensitive commands
        if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
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


# ============================================================================
# Helper Functions: Command Parsing
# ============================================================================


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


# ============================================================================
# Helper Functions: Response Builders
# ============================================================================


def _deny_command(reason: str) -> HookJSONOutput:
    """Helper to create a deny response in SDK 0.1.18 format."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


# ============================================================================
# Helper Functions: Command Validators
# ============================================================================


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


# ============================================================================
# Helper Functions: Script Validators
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
    if len(tokens) - 1 > MAX_SCRIPT_ARGS:
        return False, f"Script has too many arguments (max {MAX_SCRIPT_ARGS}, got {len(tokens) - 1})"

    # Limit argument length to prevent buffer overflow-style attacks

    # Check all arguments (skip the script name itself)
    for arg in tokens[1:]:
        # Check argument length
        if len(arg) > MAX_ARG_LENGTH:
            return False, f"Script argument exceeds maximum length ({MAX_ARG_LENGTH} chars): {arg[:50]}..."

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
