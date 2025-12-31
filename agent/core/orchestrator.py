"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
Includes Human-in-the-Loop (HITL) checkpoint handling (always enabled).

This is the SLIM orchestrator - delegates to specialized modules:
- output.py: All formatting and display
- session_runner.py: SDK session execution
- checkpoint_handlers.py: Checkpoint-specific logic
- StateRepository: All state I/O
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent.prompts import get_coding_prompt, get_initializer_prompt, get_mr_creation_prompt
from common.state import AgentState, FileStateRepository, StateRepository
from common.types import CheckpointStatus, CheckpointType, SessionType

from .checkpoint_handlers import CheckpointDispatcher, HandlerContext
from .client import create_client
from .hitl import resolve_checkpoint
from .output import (
    emit_output,
    format_agent_header,
    format_checkpoint_awaiting,
    format_final_summary,
    format_milestone_closed,
    format_milestone_complete,
    format_phase_info,
    format_session_header,
)
from .session_runner import run_agent_session

# Callback types for TUI integration
OutputCallback = Callable[[str], None]
ToolCallback = Callable[[str, str, bool], None]

# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3
_HITL_CHECK_INTERVAL_SECONDS = 5


@dataclass
class AgentConfig:
    """Configuration for the autonomous agent."""

    project_dir: Path
    model: str
    spec_slug: str
    spec_hash: str
    max_iterations: int | None = None
    target_branch: str = "main"
    file_only_mode: bool = False
    skip_mr_creation: bool = False
    skip_puppeteer: bool = False
    skip_test_suite: bool = False
    skip_regression_testing: bool = False


@dataclass
class AgentCallbacks:
    """Callbacks for TUI integration."""

    on_output: OutputCallback | None = None
    on_tool: ToolCallback | None = None
    on_phase: Callable[[SessionType, int], None] | None = None


@dataclass
class AgentEvents:
    """Async events for agent control."""

    stop_event: asyncio.Event | None = None
    pause_event: asyncio.Event | None = None


def determine_session_type(
    state: AgentState,
    skip_mr_creation: bool = False,
    state_repo: StateRepository | None = None,
    project_dir: Path | None = None,
    spec_slug: str = "",
    spec_hash: str = "",
) -> SessionType:
    """Determine which type of session to run based on state.

    Args:
        state: Current agent state
        skip_mr_creation: If True, never return MR_CREATION session type
        state_repo: State repository for checkpoint checks
        project_dir: Project directory (needed for checkpoint checks)
        spec_slug: Spec slug identifier
        spec_hash: 8-character base62 hash

    Returns:
        SessionType: INITIALIZER, CODING, or MR_CREATION
    """
    if not state.is_initialized:
        return SessionType.INITIALIZER

    if not state.all_issues_closed:
        return SessionType.CODING

    # All issues closed - check if we should create MR
    if skip_mr_creation:
        return SessionType.CODING

    # Check if MR phase transition is approved
    if (
        state_repo
        and project_dir
        and not state_repo.is_checkpoint_type_approved(
            project_dir, spec_slug, spec_hash, CheckpointType.MR_PHASE_TRANSITION
        )
    ):
        return SessionType.CODING

    return SessionType.MR_CREATION


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    spec_slug: str,
    spec_hash: str,
    *,
    max_iterations: int | None = None,
    target_branch: str = "main",
    file_only_mode: bool = False,
    skip_mr_creation: bool = False,
    skip_puppeteer: bool = False,
    skip_test_suite: bool = False,
    skip_regression_testing: bool = False,
    on_output: OutputCallback | None = None,
    on_tool: ToolCallback | None = None,
    on_phase: Callable[[SessionType, int], None] | None = None,
    stop_event: asyncio.Event | None = None,
    pause_event: asyncio.Event | None = None,
    state_repo: StateRepository | None = None,
    checkpoint_dispatcher: CheckpointDispatcher | None = None,
) -> None:
    """Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        spec_slug: Spec slug identifier
        spec_hash: 8-character base62 hash
        max_iterations: Maximum iterations (None for unlimited)
        target_branch: Target branch for merge request
        file_only_mode: Use local file tracking instead of GitLab
        skip_mr_creation: Skip MR creation after coding completes
        on_output: Optional callback for text output
        on_tool: Optional callback for tool usage
        on_phase: Optional callback for phase changes
        stop_event: Optional event to signal agent should stop
        pause_event: Optional event to control pause/resume
        state_repo: Optional state repository (defaults to FileStateRepository)
        checkpoint_dispatcher: Optional checkpoint dispatcher (defaults to standard)
    """
    # Create config and callback containers
    config = AgentConfig(
        project_dir=project_dir,
        model=model,
        spec_slug=spec_slug,
        spec_hash=spec_hash,
        max_iterations=max_iterations,
        target_branch=target_branch,
        file_only_mode=file_only_mode,
        skip_mr_creation=skip_mr_creation,
        skip_puppeteer=skip_puppeteer,
        skip_test_suite=skip_test_suite,
        skip_regression_testing=skip_regression_testing,
    )
    callbacks = AgentCallbacks(on_output=on_output, on_tool=on_tool, on_phase=on_phase)
    events = AgentEvents(stop_event=stop_event, pause_event=pause_event)

    # Default dependencies
    if state_repo is None:
        state_repo = FileStateRepository()
    if checkpoint_dispatcher is None:
        checkpoint_dispatcher = CheckpointDispatcher()

    # Print header
    header = format_agent_header(
        config.project_dir, config.model, config.spec_slug, config.spec_hash, config.max_iterations
    )
    print(header)

    # Ensure project dir exists
    config.project_dir.mkdir(parents=True, exist_ok=True)

    # Load initial state and determine session type
    state = state_repo.load(config.project_dir, config.spec_slug, config.spec_hash)
    session_type = determine_session_type(
        state, config.skip_mr_creation, state_repo, config.project_dir, config.spec_slug, config.spec_hash
    )
    print(format_phase_info(session_type, state))

    # Run main loop
    await _run_agent_loop(config, callbacks, events, state_repo, checkpoint_dispatcher)


async def _run_agent_loop(
    config: AgentConfig,
    callbacks: AgentCallbacks,
    events: AgentEvents,
    state_repo: StateRepository,
    checkpoint_dispatcher: CheckpointDispatcher,
) -> None:
    """Run the main agent iteration loop."""
    iteration = 0

    while True:
        iteration += 1

        # Check stop/pause
        if await _check_stop_pause(events, callbacks):
            break

        # Check max iterations
        if config.max_iterations and iteration > config.max_iterations:
            print(f"\nReached max iterations ({config.max_iterations})")
            break

        # Reload state (may have changed)
        state = state_repo.load(config.project_dir, config.spec_slug, config.spec_hash)

        # Handle pending checkpoint
        if not await _handle_pending_checkpoint(config, state, state_repo, checkpoint_dispatcher):
            break

        # Check completion conditions
        if state.milestone and state.milestone.milestone_closed:
            print(format_milestone_closed(state.milestone.merge_request_url))
            break

        if config.skip_mr_creation and state.all_issues_closed:
            feature_branch = state.milestone.feature_branch if state.milestone else f"feature/{config.spec_slug}"
            print(format_milestone_complete(feature_branch, config.target_branch))
            break

        # Determine session type
        session_type = determine_session_type(
            state, config.skip_mr_creation, state_repo, config.project_dir, config.spec_slug, config.spec_hash
        )

        # Invoke phase callback
        if callbacks.on_phase:
            callbacks.on_phase(session_type, iteration)

        # Print session header and run
        print(format_session_header(iteration, session_type == SessionType.INITIALIZER))

        client = create_client(config.project_dir, config.model)
        prompt = _get_session_prompt(session_type, config)

        status = "error"  # Default, will be overwritten
        async with client:
            status, _ = await run_agent_session(client, prompt, callbacks.on_output, callbacks.on_tool)

        # Handle result
        if await _handle_session_result(status, config, events, callbacks):
            break

    # Final summary
    state = state_repo.load(config.project_dir, config.spec_slug, config.spec_hash)
    print(format_final_summary(config.project_dir, state.milestone, state.file_only_mode))


async def _check_stop_pause(events: AgentEvents, callbacks: AgentCallbacks) -> bool:
    """Check for stop/pause signals. Returns True if should stop."""
    if events.stop_event and events.stop_event.is_set():
        emit_output(callbacks.on_output, "\n[Agent stopped by user]\n")
        return True

    if events.pause_event and not events.pause_event.is_set():
        emit_output(callbacks.on_output, "\n[Agent paused - waiting to resume...]\n")
        await events.pause_event.wait()
        emit_output(callbacks.on_output, "[Agent resumed]\n")

    return False


async def _handle_pending_checkpoint(
    config: AgentConfig,
    state: AgentState,
    state_repo: StateRepository,
    checkpoint_dispatcher: CheckpointDispatcher,
) -> bool:
    """Handle pending checkpoint. Returns True to continue, False to stop."""
    checkpoint = state_repo.load_pending_checkpoint(config.project_dir, config.spec_slug, config.spec_hash)

    if not checkpoint or checkpoint.status != CheckpointStatus.PENDING:
        return True

    # Check auto-accept (reload state to get current setting)
    fresh_state = state_repo.load(config.project_dir, config.spec_slug, config.spec_hash)
    if fresh_state.auto_accept:
        # Use checkpoint dispatcher for auto-approval
        ctx = HandlerContext(state=fresh_state, spec_config=None, project_dir=str(config.project_dir))  # type: ignore[arg-type]
        result = checkpoint_dispatcher.auto_approve(checkpoint, ctx)
        print(result.output)

        # Resolve the checkpoint
        resolve_checkpoint(
            config.project_dir,
            status=CheckpointStatus.APPROVED,
            spec_slug=config.spec_slug,
            spec_hash=config.spec_hash,
            decision=result.decision,
            notes=result.notes,
            modifications=result.modifications,
        )
        return True

    # Wait for manual approval
    print(format_checkpoint_awaiting())
    return await _wait_for_approval(config, state_repo)


async def _wait_for_approval(config: AgentConfig, state_repo: StateRepository) -> bool:
    """Wait for checkpoint approval. Returns True if approved, False if rejected."""
    while True:
        checkpoint = state_repo.load_pending_checkpoint(config.project_dir, config.spec_slug, config.spec_hash)

        if checkpoint is None:
            return True

        match checkpoint.status:
            case CheckpointStatus.APPROVED | CheckpointStatus.MODIFIED | CheckpointStatus.SKIPPED:
                print(f"\n[HITL] Checkpoint {checkpoint.status.value}")
                return True
            case CheckpointStatus.REJECTED:
                print("\n[HITL] Checkpoint REJECTED")
                return False
            case _:
                await asyncio.sleep(_HITL_CHECK_INTERVAL_SECONDS)


async def _handle_session_result(
    status: str,
    config: AgentConfig,
    events: AgentEvents,
    callbacks: AgentCallbacks,
) -> bool:
    """Handle session result. Returns True if should stop."""
    if status == "continue":
        print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
        if await _wait_with_stop_check(events.stop_event, AUTO_CONTINUE_DELAY_SECONDS, callbacks.on_output):
            return True

    if status == "error":
        print("\nSession error, retrying...")
        if await _wait_with_stop_check(events.stop_event, AUTO_CONTINUE_DELAY_SECONDS, callbacks.on_output):
            return True

    print("\nPreparing next session...\n")
    if events.stop_event and events.stop_event.is_set():
        emit_output(callbacks.on_output, "\n[Agent stopped by user]\n")
        return True

    await asyncio.sleep(1)
    return False


async def _wait_with_stop_check(
    stop_event: asyncio.Event | None,
    timeout: float,
    on_output: OutputCallback | None,
) -> bool:
    """Wait with stop check. Returns True if stopped."""
    try:
        if stop_event:
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
            emit_output(on_output, "\n[Agent stopped by user]\n")
            return True
        await asyncio.sleep(timeout)
    except TimeoutError:
        pass
    return False


def _get_session_prompt(session_type: SessionType, config: AgentConfig) -> str:
    """Get the appropriate prompt for session type."""
    if session_type == SessionType.INITIALIZER:
        return get_initializer_prompt(
            target_branch=config.target_branch,
            spec_slug=config.spec_slug,
            spec_hash=config.spec_hash,
            file_only_mode=config.file_only_mode,
        )
    if session_type == SessionType.MR_CREATION:
        return get_mr_creation_prompt(
            spec_slug=config.spec_slug,
            spec_hash=config.spec_hash,
            target_branch=config.target_branch,
            file_only_mode=config.file_only_mode,
        )
    return get_coding_prompt(
        spec_slug=config.spec_slug,
        spec_hash=config.spec_hash,
        file_only_mode=config.file_only_mode,
        skip_puppeteer=config.skip_puppeteer,
        skip_test_suite=config.skip_test_suite,
        skip_regression_testing=config.skip_regression_testing,
    )
