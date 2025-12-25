"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
Includes Human-in-the-Loop (HITL) checkpoint handling (always enabled).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage

from agent.prompts import get_coding_prompt, get_initializer_prompt, get_mr_creation_prompt
from common import CheckpointData, CheckpointStatus, CheckpointType, SessionType

from .client import create_client
from .hitl import (
    get_milestone_state_path,
    is_checkpoint_type_approved,
    load_pending_checkpoint,
    resolve_checkpoint,
)

# Callback types for TUI integration
OutputCallback = Callable[[str], None]
ToolCallback = Callable[[str, str, bool], None]  # (tool_name, content, is_error)


class _MilestoneState(TypedDict, total=False):
    """Type definition for milestone state dictionary."""

    initialized: bool
    repository: str
    milestone_id: int
    feature_branch: str
    all_issues_closed: bool
    milestone_name: str
    total_issues: int
    enrichments: dict
    progress_comments: dict


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3
_HITL_CHECK_INTERVAL_SECONDS = 5

# Separator constants for consistent output formatting
_SEPARATOR_HEAVY = "=" * 70
_SEPARATOR_LIGHT = "-" * 70
_SEPARATOR_MEDIUM = "-" * 50


@dataclass
class AgentConfig:
    """Configuration for the autonomous agent.

    Groups related parameters to reduce function signature complexity.
    """

    project_dir: Path
    model: str
    spec_slug: str
    spec_hash: str
    max_iterations: int | None = None
    target_branch: str = "main"
    auto_accept: bool = False


@dataclass
class AgentCallbacks:
    """Callbacks for TUI integration.

    Groups callback functions for output, tool usage, and phase changes.
    """

    on_output: OutputCallback | None = None
    on_tool: ToolCallback | None = None
    on_phase: Callable[[SessionType, int], None] | None = None


@dataclass
class AgentEvents:
    """Async events for agent control.

    Groups events for stopping and pausing the agent.
    """

    stop_event: asyncio.Event | None = None
    pause_event: asyncio.Event | None = None


def _emit_output(on_output: OutputCallback | None, message: str) -> None:
    """Emit output to callback or print."""
    if on_output:
        on_output(message)
    else:
        print(message, end="" if not message.endswith("\n") else "")


def _handle_auto_accept_checkpoint(
    checkpoint: CheckpointData,
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
) -> None:
    """Handle auto-accept logic for a pending checkpoint.

    Processes checkpoint-type-specific auto-approval logic and resolves
    the checkpoint with appropriate decisions, notes, and modifications.

    Args:
        checkpoint: The pending checkpoint to auto-approve
        project_dir: Project directory
        spec_slug: Spec slug identifier
        spec_hash: 5-character hex hash
    """
    checkpoint_type_display = checkpoint.checkpoint_type.value.replace("_", " ").title()

    # Default values
    decision = None
    notes = "Auto-approved"
    modifications = None

    # Checkpoint-type-specific auto-accept logic
    match checkpoint.checkpoint_type:
        case CheckpointType.ISSUE_ENRICHMENT:
            all_issues = checkpoint.context.get("all_issues_with_judgments", [])
            selected_iids = [
                issue_data.get("issue_iid")
                for issue_data in all_issues
                if issue_data.get("llm_judgment", {}).get("decision") == "needs_enrichment"
                and issue_data.get("issue_iid") is not None
            ]
            modifications = {"selected_issue_iids": selected_iids}
            notes = (
                f"Auto-approved with {len(selected_iids)} LLM-recommended issues for enrichment"
                if selected_iids
                else "Auto-approved - no issues flagged for enrichment"
            )
        case CheckpointType.REGRESSION_APPROVAL:
            decision = "fix_now"
            notes = "Auto-approved with fix_now action"
        case CheckpointType.ISSUE_SELECTION:
            rec_iid = checkpoint.context.get("recommended_issue_iid")
            if rec_iid:
                modifications = {"selected_issue_iid": rec_iid}
                notes = f"Auto-approved recommended issue #{rec_iid}"
        case _:
            pass  # Use defaults

    resolve_checkpoint(
        project_dir=project_dir,
        spec_slug=spec_slug,
        spec_hash=spec_hash,
        status=CheckpointStatus.APPROVED,
        decision=decision,
        notes=notes,
        modifications=modifications,
    )
    print(f"\n[HITL] Checkpoint auto-approved: {checkpoint_type_display}")
    if modifications:
        print(f"[HITL] Modifications: {modifications}")


def _validate_milestone_state(state: _MilestoneState | dict[str, object]) -> tuple[bool, str]:
    """Validate required milestone keys and types.

    Validates that the milestone state dict contains all required keys with correct types.
    This prevents MR creation when the state file is malformed or partial.

    Args:
        state: Milestone state dictionary to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty string.
    """
    required_fields: dict[str, type] = {
        "initialized": bool,
        "repository": str,
        "milestone_id": int,
        "feature_branch": str,
        "all_issues_closed": bool,
    }

    for field_name, expected_type in required_fields.items():
        if field_name not in state:
            return False, f"Missing required field: {field_name}"
        if not isinstance(state[field_name], expected_type):
            actual_type = type(state[field_name]).__name__
            return False, f"Invalid type for '{field_name}': expected {expected_type.__name__}, got {actual_type}"

    return True, ""


def _print_agent_header(config: AgentConfig) -> None:
    """Print the initial agent header with configuration info."""
    print("\n" + _SEPARATOR_HEAVY)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print(_SEPARATOR_HEAVY)
    print(f"\nProject directory: {config.project_dir}")
    print(f"Model: {config.model}")
    print(f"Spec slug: {config.spec_slug}")
    print(f"Agent files: .claude-agent/{config.spec_slug}/")
    if config.max_iterations:
        print(f"Max iterations: {config.max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()


def _load_workspace_config(config: AgentConfig) -> AgentConfig:
    """Load workspace configuration and return updated config.

    Loads spec_hash and auto_accept preferences from workspace_info.json if present.

    Args:
        config: Current agent configuration

    Returns:
        Updated AgentConfig with values from workspace file
    """
    workspace_info_file = (
        config.project_dir / ".claude-agent" / f"{config.spec_slug}-{config.spec_hash}" / ".workspace_info.json"
    )

    if not workspace_info_file.exists():
        return config

    # Load workspace data once
    try:
        with open(workspace_info_file, encoding="utf-8") as f:
            workspace_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return config  # Keep defaults on read/parse errors

    return AgentConfig(
        project_dir=config.project_dir,
        model=config.model,
        spec_slug=config.spec_slug,
        spec_hash=workspace_data.get("spec_hash", config.spec_hash),
        max_iterations=config.max_iterations,
        target_branch=config.target_branch,
        auto_accept=config.auto_accept or workspace_data.get("auto_accept", False),
    )


def _print_phase_info(session_type: SessionType, config: AgentConfig) -> None:
    """Print phase-specific information based on session type."""
    if session_type == SessionType.INITIALIZER:
        print("Phase 1: Initializer - Creating milestone and issues")
        print()
        print(_SEPARATOR_HEAVY)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is creating a milestone and issues.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print(_SEPARATOR_HEAVY)
        print()
    elif session_type == SessionType.MR_CREATION:
        print("Phase 3: MR Creation - All issues complete, creating merge request")
        _print_progress_summary(config.project_dir, config.spec_slug, config.spec_hash)
    else:
        print("Phase 2: Coding - Working on milestone issues")
        _print_progress_summary(config.project_dir, config.spec_slug, config.spec_hash)


def _get_session_prompt(session_type: SessionType, config: AgentConfig) -> str:
    """Get the appropriate prompt based on session type.

    Args:
        session_type: Current session type
        config: Agent configuration

    Returns:
        The prompt string for the session
    """
    if session_type == SessionType.INITIALIZER:
        return get_initializer_prompt(
            target_branch=config.target_branch,
            spec_slug=config.spec_slug,
            spec_hash=config.spec_hash,
        )
    if session_type == SessionType.MR_CREATION:
        return get_mr_creation_prompt(
            spec_slug=config.spec_slug,
            spec_hash=config.spec_hash,
            target_branch=config.target_branch,
        )
    return get_coding_prompt(spec_slug=config.spec_slug, spec_hash=config.spec_hash)


async def _handle_pending_checkpoint(config: AgentConfig) -> bool:
    """Handle a pending HITL checkpoint.

    Args:
        config: Agent configuration

    Returns:
        True if agent should continue, False if it should stop
    """
    checkpoint = load_pending_checkpoint(config.project_dir, config.spec_slug, config.spec_hash)

    if not checkpoint or checkpoint.status != CheckpointStatus.PENDING:
        return True  # No pending checkpoint, continue

    if config.auto_accept:
        _handle_auto_accept_checkpoint(checkpoint, config.project_dir, config.spec_slug, config.spec_hash)
        return True

    # Wait for manual approval
    print("\n" + _SEPARATOR_MEDIUM)
    print("  AWAITING APPROVAL:  [Y]/[1] Approve  [X]/[0] Reject")
    print(_SEPARATOR_MEDIUM)

    approved = await _wait_for_hitl_approval(config.project_dir, config.spec_slug, config.spec_hash)
    if not approved:
        print("\nHITL checkpoint rejected. Stopping.")
        return False

    print("\n[HITL] Checkpoint approved, agent will continue from saved state...")
    return True


async def _check_stop_pause_signals(events: AgentEvents, callbacks: AgentCallbacks) -> bool:
    """Check for stop/pause signals and handle them.

    Args:
        events: Agent events (stop, pause)
        callbacks: Agent callbacks

    Returns:
        True if agent should stop, False to continue
    """
    # Check for stop signal
    if events.stop_event and events.stop_event.is_set():
        _emit_output(callbacks.on_output, "\n[Agent stopped by user]\n")
        return True

    # Check for pause signal
    if events.pause_event and not events.pause_event.is_set():
        _emit_output(callbacks.on_output, "\n[Agent paused - waiting to resume...]\n")
        await events.pause_event.wait()
        _emit_output(callbacks.on_output, "[Agent resumed]\n")

    return False


async def _handle_session_result(
    status: str,
    config: AgentConfig,
    events: AgentEvents,
    callbacks: AgentCallbacks,
) -> bool:
    """Handle the result of an agent session.

    Args:
        status: Session status ("continue", "error", or other)
        config: Agent configuration
        events: Agent events
        callbacks: Agent callbacks

    Returns:
        True if agent should stop, False to continue
    """
    if status == "continue":
        print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
        _print_progress_summary(config.project_dir, config.spec_slug, config.spec_hash)
        if await _wait_with_stop_check(events.stop_event, AUTO_CONTINUE_DELAY_SECONDS, callbacks.on_output):
            return True

    if status == "error":
        print("\nSession encountered an error")
        print("Will retry with a fresh session...")
        if await _wait_with_stop_check(events.stop_event, AUTO_CONTINUE_DELAY_SECONDS, callbacks.on_output):
            return True

    # Small delay between sessions
    print("\nPreparing next session...\n")
    if events.stop_event and events.stop_event.is_set():
        _emit_output(callbacks.on_output, "\n[Agent stopped by user]\n")
        return True
    await asyncio.sleep(1)

    return False


def _print_final_summary(config: AgentConfig) -> None:
    """Print the final session summary."""
    print("\n" + _SEPARATOR_HEAVY)
    print("  SESSION COMPLETE")
    print(_SEPARATOR_HEAVY)
    print(f"\nProject directory: {config.project_dir}")
    _print_progress_summary(config.project_dir, config.spec_slug, config.spec_hash)
    print("\nDone!")


def determine_session_type(project_dir: Path, spec_slug: str, spec_hash: str) -> SessionType:
    """Determine which type of session to run based on milestone state.

    Args:
        project_dir: Project directory
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)

    Returns:
        Session type: SessionType.INITIALIZER, SessionType.CODING, or SessionType.MR_CREATION
    """
    if not _is_milestone_initialized(project_dir, spec_slug, spec_hash):
        return SessionType.INITIALIZER

    state = _load_milestone_state(project_dir, spec_slug, spec_hash)
    if state and state.get("all_issues_closed", False):
        # Validate milestone state before allowing MR creation
        is_valid, error_msg = _validate_milestone_state(state)
        if not is_valid:
            print(f"\n[Warning] Milestone state invalid: {error_msg}")
            print("  Cannot proceed to MR creation phase. Continuing with coding session.")
            return SessionType.CODING

        # Check if MR_PHASE_TRANSITION checkpoint is approved
        # NOTE: Depends on is_checkpoint_type_approved in agent/hitl.py (parallel change)
        # NOTE: Depends on CheckpointType.MR_PHASE_TRANSITION in common/types.py (parallel change)
        if not is_checkpoint_type_approved(project_dir, spec_slug, spec_hash, CheckpointType.MR_PHASE_TRANSITION):
            print("\n[HITL] Waiting for MR phase approval before creating merge request.")
            print("  All issues are closed. Approve the MR_PHASE_TRANSITION checkpoint to proceed.")
            return SessionType.CODING

        return SessionType.MR_CREATION

    return SessionType.CODING


async def run_autonomous_agent(  # pylint: disable=too-many-locals
    project_dir: Path,
    model: str,
    spec_slug: str,
    spec_hash: str,
    *,
    max_iterations: int | None = None,
    target_branch: str = "main",
    auto_accept: bool = False,
    on_output: OutputCallback | None = None,
    on_tool: ToolCallback | None = None,
    on_phase: Callable[[SessionType, int], None] | None = None,
    stop_event: asyncio.Event | None = None,
    pause_event: asyncio.Event | None = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)
        max_iterations: Maximum number of iterations (None for unlimited)
        target_branch: Target branch for merge request (default: main)
        auto_accept: Automatically approve HITL checkpoints (default: False)
        on_output: Optional callback for text output (TUI integration)
        on_tool: Optional callback for tool usage (TUI integration)
        on_phase: Optional callback for phase changes (session_type, iteration)
        stop_event: Optional asyncio.Event to signal agent should stop
        pause_event: Optional asyncio.Event to control pause/resume (set=running, clear=paused)
    """
    # Create structured configuration objects
    config = AgentConfig(
        project_dir=project_dir,
        model=model,
        spec_slug=spec_slug,
        spec_hash=spec_hash,
        max_iterations=max_iterations,
        target_branch=target_branch,
        auto_accept=auto_accept,
    )
    callbacks = AgentCallbacks(on_output=on_output, on_tool=on_tool, on_phase=on_phase)
    events = AgentEvents(stop_event=stop_event, pause_event=pause_event)

    # Print header and setup
    _print_agent_header(config)
    config.project_dir.mkdir(parents=True, exist_ok=True)
    config = _load_workspace_config(config)

    # Determine initial session type and print phase info
    session_type = determine_session_type(config.project_dir, config.spec_slug, config.spec_hash)
    _print_phase_info(session_type, config)

    # Run main agent loop
    await _run_agent_loop(config, callbacks, events)


async def _run_agent_loop(
    config: AgentConfig,
    callbacks: AgentCallbacks,
    events: AgentEvents,
) -> None:
    """Run the main agent iteration loop.

    Args:
        config: Agent configuration
        callbacks: Agent callbacks for TUI integration
        events: Async events for agent control
    """
    iteration = 0

    while True:
        iteration += 1

        # Check for stop/pause signals
        if await _check_stop_pause_signals(events, callbacks):
            break

        # Check max iterations
        if config.max_iterations and iteration > config.max_iterations:
            print(f"\nReached max iterations ({config.max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Handle pending HITL checkpoint
        if not await _handle_pending_checkpoint(config):
            break

        # Re-determine session type (in case it changed)
        session_type = determine_session_type(config.project_dir, config.spec_slug, config.spec_hash)

        # Check if milestone is already completed (MR created and milestone closed)
        state = _load_milestone_state(config.project_dir, config.spec_slug, config.spec_hash)
        if state and state.get("milestone_closed", False):
            print("\n" + _SEPARATOR_HEAVY)
            print("  MILESTONE COMPLETED")
            print(_SEPARATOR_HEAVY)
            print("\nMilestone is already closed.")
            if state.get("merge_request_url"):
                print(f"Merge Request: {state.get('merge_request_url')}")
            print("\nNo further action needed. Exiting agent loop.")
            break

        # Invoke phase callback if provided
        if callbacks.on_phase:
            callbacks.on_phase(session_type, iteration)

        # Print session header and run session
        _print_session_header(iteration, session_type == SessionType.INITIALIZER)
        client = create_client(config.project_dir, config.model)
        prompt = _get_session_prompt(session_type, config)

        async with client:
            status, _ = await _run_agent_session(
                client, prompt, on_output=callbacks.on_output, on_tool=callbacks.on_tool
            )

        # Handle session result
        if await _handle_session_result(status, config, events, callbacks):
            break

    # Final summary
    _print_final_summary(config)


# ============================================================================
# Private Helper Functions
# ============================================================================


def _load_milestone_state(project_dir: Path, spec_slug: str, spec_hash: str) -> _MilestoneState | None:
    """
    Load the GitLab milestone state from the marker file.

    Args:
        project_dir: Project directory
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)

    Returns:
        Milestone state dict or None if not initialized

        The state dict contains:
        - initialized: bool - Whether milestone has been set up
        - repository: str - GitLab project path (e.g., "group/project")
        - milestone_name: str - Milestone title
        - milestone_id: int - GitLab milestone ID
        - total_issues: int - Number of issues created
        - feature_branch: str - Feature branch name
        - all_issues_closed: bool - Whether all issues are closed
        - enrichments: dict - Issue enrichment data (future field, currently not populated)
        - progress_comments: dict - Progress comment history (future field, currently not populated)

        Note: The enrichments and progress_comments fields are reserved for future use.
        They may appear in the JSON file but are not currently written by any code.
    """
    state_path = get_milestone_state_path(project_dir, spec_slug, spec_hash)
    if state_path.exists():
        try:
            with open(state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Silently return None on read/parse errors (matches hitl.py pattern)
            return None

    return None


def _is_milestone_initialized(project_dir: Path, spec_slug: str, spec_hash: str) -> bool:
    """
    Check if GitLab milestone has been initialized.

    Args:
        project_dir: Directory to check
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)

    Returns:
        True if .gitlab_milestone.json exists and is valid
    """
    state = _load_milestone_state(project_dir, spec_slug, spec_hash)
    return state is not None and state.get("initialized", False)


def _print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"

    print("\n" + _SEPARATOR_HEAVY)
    print(f"  SESSION {session_num}: {session_type}")
    print(_SEPARATOR_HEAVY)
    print()


def _print_progress_summary(project_dir: Path, spec_slug: str, spec_hash: str) -> None:
    """
    Print a summary of current progress.

    Since actual progress is tracked in GitLab, this reads the local
    state file for cached information. The agent updates GitLab directly
    and reports progress in milestone and issue comments.

    Args:
        project_dir: Project directory
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)
    """
    state = _load_milestone_state(project_dir, spec_slug, spec_hash)

    if state is None:
        print("\nProgress: GitLab milestone not yet initialized")
        return

    # Validate milestone state and warn if invalid
    is_valid, error_msg = _validate_milestone_state(state)
    if not is_valid:
        print("\nProgress: Milestone state invalid, skipping MR phase")
        print(f"  Validation error: {error_msg}")
        print("  The agent will continue in coding mode until state is corrected.")
        return

    total = state.get("total_issues", 0)
    milestone = state.get("milestone_name", "unknown")
    repo = state.get("repository", "unknown")

    print("\nGitLab Milestone Status:")
    print(f"  Project: {repo}")
    print(f"  Milestone: {milestone}")
    print(f"  Total issues created: {total}")
    print("  (Check GitLab for current opened/closed counts)")


async def _wait_for_hitl_approval(
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
) -> bool:
    """Wait for human to resolve a pending HITL checkpoint.

    Args:
        project_dir: Project directory
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)

    Returns:
        True if checkpoint was approved/modified, False if rejected
    """
    while True:
        checkpoint = load_pending_checkpoint(project_dir, spec_slug, spec_hash)

        if checkpoint is None:
            # No pending checkpoint - treat as approved
            return True

        match checkpoint.status:
            case CheckpointStatus.APPROVED:
                print("\n[HITL] Checkpoint APPROVED by human")
                if checkpoint.human_notes:
                    print(f"[HITL] Notes: {checkpoint.human_notes}")
                return True
            case CheckpointStatus.MODIFIED:
                print("\n[HITL] Checkpoint APPROVED with modifications")
                if checkpoint.human_notes:
                    print(f"[HITL] Notes: {checkpoint.human_notes}")
                return True
            case CheckpointStatus.REJECTED:
                print("\n[HITL] Checkpoint REJECTED by human")
                if checkpoint.human_notes:
                    print(f"[HITL] Reason: {checkpoint.human_notes}")
                return False
            case CheckpointStatus.SKIPPED:
                print("\n[HITL] Checkpoint SKIPPED")
                return True
            case _:
                pass  # Still pending

        # Still pending - wait and check again
        await asyncio.sleep(_HITL_CHECK_INTERVAL_SECONDS)


async def _wait_with_stop_check(
    stop_event: asyncio.Event | None,
    timeout: float,
    on_output: OutputCallback | None,
) -> bool:
    """Wait for timeout while checking for stop signal.

    Args:
        stop_event: Optional event to signal stop
        timeout: Seconds to wait
        on_output: Optional callback for output

    Returns:
        True if should stop, False if timeout elapsed normally
    """
    try:
        if stop_event:
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
            if on_output:
                on_output("\n[Agent stopped by user]\n")
            return True
        await asyncio.sleep(timeout)
    except TimeoutError:
        pass  # Normal timeout
    return False


async def _run_agent_session(  # pylint: disable=too-many-branches
    client: ClaudeSDKClient,
    message: str,
    on_output: OutputCallback | None = None,
    on_tool: ToolCallback | None = None,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Agent SDK.

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
    _emit_output(on_output, status_msg)

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
                        _emit_output(on_output, block.text)
                    elif isinstance(block, ToolUseBlock):
                        input_str = str(block.input)
                        if len(input_str) > 200:
                            input_str = input_str[:200] + "..."
                        if on_tool:
                            on_tool(block.name, input_str, False)
                        else:
                            print(f"\n[Tool: {block.name}]", flush=True)
                            if input_str:
                                print(f"   Input: {input_str}", flush=True)

            # Handle UserMessage (tool results)
            elif isinstance(response, UserMessage) and isinstance(response.content, list):
                # UserMessage.content can be str or list[ContentBlock]
                for block in response.content:
                    if isinstance(block, ToolResultBlock):
                        result_content = block.content or ""
                        is_error = block.is_error or False

                        # Check if command was blocked by security hook
                        if "blocked" in str(result_content).lower():
                            if on_tool:
                                on_tool("ToolResult", f"[BLOCKED] {result_content}", True)
                            else:
                                print(f"   [BLOCKED] {result_content}", flush=True)
                        elif is_error:
                            # Show errors (truncated)
                            error_str = str(result_content)[:500]
                            if on_tool:
                                on_tool("ToolResult", f"[Error] {error_str}", True)
                            else:
                                print(f"   [Error] {error_str}", flush=True)
                        else:
                            # Tool succeeded - just show brief confirmation
                            if on_tool:
                                on_tool("ToolResult", "[Done]", False)
                            else:
                                print("   [Done]", flush=True)

        separator = "\n" + _SEPARATOR_LIGHT + "\n"
        _emit_output(on_output, separator)
        return "continue", response_text

    except Exception as e:  # pylint: disable=broad-exception-caught
        # Broad catch is intentional: handle SDK errors, network issues, and runtime errors gracefully
        error_msg = f"Error during agent session: {e}\n"
        _emit_output(on_output, error_msg)
        return "error", str(e)
