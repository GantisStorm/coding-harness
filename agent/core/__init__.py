"""Core agent logic - orchestration, client, and HITL checkpoints.

Exports:
    Client:
        create_client: Create configured Claude SDK client

    Orchestrator:
        determine_session_type: Determine which session phase to run
        run_autonomous_agent: Main agent execution loop

    HITL Checkpoints:
        approve_checkpoint: Approve a pending checkpoint
        reject_checkpoint: Reject a pending checkpoint
        resolve_checkpoint: Resolve checkpoint with custom data
        load_pending_checkpoint: Load most recent pending checkpoint
        is_checkpoint_pending: Check if checkpoint is pending
        get_pending_checkpoint_type: Get type of pending checkpoint

    New modules (added by refactor):
        CheckpointDispatcher: Strategy-based checkpoint handling
        emit_output: Output utility
        run_agent_session: Session execution
"""

from .checkpoint_handlers import CheckpointDispatcher
from .client import create_client
from .hitl import (
    approve_checkpoint,
    get_pending_checkpoint_type,
    is_checkpoint_pending,
    load_pending_checkpoint,
    reject_checkpoint,
    resolve_checkpoint,
)
from .orchestrator import determine_session_type, run_autonomous_agent
from .output import emit_output
from .session_runner import run_agent_session

__all__ = [
    # Client
    "create_client",
    # Orchestrator
    "determine_session_type",
    "run_autonomous_agent",
    # HITL
    "approve_checkpoint",
    "reject_checkpoint",
    "resolve_checkpoint",
    "load_pending_checkpoint",
    "is_checkpoint_pending",
    "get_pending_checkpoint_type",
    # New modules
    "CheckpointDispatcher",
    "emit_output",
    "run_agent_session",
]
