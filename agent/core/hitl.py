"""
Human-in-the-Loop (HITL) Module
================================

Provides checkpoint functionality for requiring human approval at key decision points
in the autonomous agent workflow.

HITL Checkpoints:
1. Project Verification - Confirm correct GitLab project before creating anything
2. Spec-to-Issues Breakdown - Review proposed issues before creation
3. Issue Enrichment - Add metadata (time estimates, dependencies) after creation
4. Regression Approval - Human decides if regression is real & how to proceed
5. Issue Selection - Approve which issue to work on next
6. Issue Closure - Require human test before closing issue
7. MR Review - Approve MR title/description before creation
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from common.types import CheckpointData, CheckpointStatus, CheckpointType

# State file names
HITL_LOG_FILE = ".hitl_checkpoint_log.json"
MILESTONE_STATE_FILE = ".gitlab_milestone.json"
AGENT_STATE_DIR = ".claude-agent"


def get_milestone_state_path(project_dir: Path, spec_slug: str, spec_hash: str) -> Path:
    """Get the path to the milestone state file."""
    state_dir = _get_agent_state_dir(project_dir, spec_slug, spec_hash)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / MILESTONE_STATE_FILE


def load_pending_checkpoint(project_dir: Path, spec_slug: str, spec_hash: str) -> CheckpointData | None:
    """Load the most recent pending checkpoint from the log.

    Returns:
        The most recent checkpoint where completed=False, or None
    """
    log_data = _load_checkpoint_log(project_dir, spec_slug, spec_hash)

    # Search all issues for pending checkpoints
    all_checkpoints = _collect_checkpoints(
        log_data,
        lambda ckpt: not ckpt.get("completed", False),
    )

    if not all_checkpoints:
        return None

    # Return most recent (by created_at)
    latest = max(all_checkpoints, key=lambda x: x.get("created_at", ""))
    return CheckpointData.from_dict(latest)


def is_checkpoint_pending(project_dir: Path, spec_slug: str, spec_hash: str) -> bool:
    """Check if there's a pending HITL checkpoint."""
    checkpoint = load_pending_checkpoint(project_dir, spec_slug, spec_hash)
    return checkpoint is not None and checkpoint.status == CheckpointStatus.PENDING


def get_pending_checkpoint_type(project_dir: Path, spec_slug: str, spec_hash: str) -> CheckpointType | None:
    """Get the type of pending checkpoint, if any."""
    checkpoint = load_pending_checkpoint(project_dir, spec_slug, spec_hash)
    if checkpoint and checkpoint.status == CheckpointStatus.PENDING:
        return checkpoint.checkpoint_type
    return None


def get_latest_checkpoint_by_type(
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
    checkpoint_type: CheckpointType,
) -> CheckpointData | None:
    """Return the most recent checkpoint of a given type, any status.

    Searches all checkpoints in the log and returns the most recent one
    matching the specified type, regardless of its status (pending, approved,
    rejected, etc.).

    Args:
        project_dir: Project root directory
        spec_slug: Spec slug identifier
        spec_hash: 5-character hex hash
        checkpoint_type: The type of checkpoint to search for

    Returns:
        The most recent CheckpointData of the given type, or None if not found
    """
    log_data = _load_checkpoint_log(project_dir, spec_slug, spec_hash)

    # Collect all checkpoints of the specified type
    matching_checkpoints = _collect_checkpoints(
        log_data,
        lambda ckpt: ckpt.get("checkpoint_type") == checkpoint_type.value,
    )

    if not matching_checkpoints:
        return None

    # Return most recent (by created_at)
    latest = max(matching_checkpoints, key=lambda x: x.get("created_at", ""))
    return CheckpointData.from_dict(latest)


def is_checkpoint_type_approved(
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
    checkpoint_type: CheckpointType,
) -> bool:
    """Return True if the latest checkpoint of the given type is approved.

    This is a convenience function used to gate phase transitions. It checks
    if the most recent checkpoint of the specified type has been approved.

    Args:
        project_dir: Project root directory
        spec_slug: Spec slug identifier
        spec_hash: 5-character hex hash
        checkpoint_type: The type of checkpoint to check

    Returns:
        True if the latest checkpoint of the type exists and is approved,
        False otherwise (including if no checkpoint of that type exists)
    """
    checkpoint = get_latest_checkpoint_by_type(project_dir, spec_slug, spec_hash, checkpoint_type)
    if checkpoint is None:
        return False
    return checkpoint.status == CheckpointStatus.APPROVED


def resolve_checkpoint(
    project_dir: Path,
    status: CheckpointStatus,
    spec_slug: str,
    spec_hash: str,
    decision: str | None = None,
    notes: str | None = None,
    modifications: dict | None = None,
) -> CheckpointData | None:
    """Resolve a pending checkpoint with human decision.

    This function now properly persists ALL resolution data to disk atomically,
    fixing the critical data loss bug where human decisions, notes, and modifications
    were lost after checkpoint resolution.

    Args:
        project_dir: Project directory
        status: Resolution status
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)
        decision: Optional decision string
        notes: Optional notes from human
        modifications: Optional modifications dict

    Returns the updated checkpoint data, or None if no checkpoint was pending.
    """
    checkpoint = load_pending_checkpoint(project_dir, spec_slug, spec_hash)
    if checkpoint is None or checkpoint.status != CheckpointStatus.PENDING:
        return None

    # Prepare timestamp for both in-memory and persisted updates
    resolved_at = datetime.now(UTC).isoformat()

    # Update in-memory checkpoint (for return value)
    checkpoint.status = status
    checkpoint.resolved_at = resolved_at
    checkpoint.human_decision = decision
    checkpoint.human_notes = notes
    checkpoint.modifications = modifications
    # NOTE: Do NOT set completed=True here. The agent will mark as completed
    # after acting on the decision (claiming issue, closing issue, etc.)

    # Define atomic update function that saves ALL resolution data
    def update_resolution(ckpt_dict: dict) -> None:
        """Update ALL resolution fields atomically."""
        ckpt_dict["status"] = status.value
        ckpt_dict["resolved_at"] = resolved_at
        ckpt_dict["human_decision"] = decision
        ckpt_dict["human_notes"] = notes
        ckpt_dict["modifications"] = modifications
        # NOTE: Do NOT set completed=True here. The agent will mark as completed
        # after acting on the decision (claiming issue, closing issue, etc.)

    # Save ALL fields atomically to disk
    _atomic_checkpoint_update(project_dir, spec_slug, spec_hash, checkpoint.checkpoint_id, update_resolution)

    return checkpoint


def approve_checkpoint(
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
    notes: str | None = None,
) -> CheckpointData | None:
    """Approve a pending checkpoint."""
    return resolve_checkpoint(
        project_dir,
        status=CheckpointStatus.APPROVED,
        spec_slug=spec_slug,
        spec_hash=spec_hash,
        decision="approved",
        notes=notes,
    )


def reject_checkpoint(
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
    reason: str,
) -> CheckpointData | None:
    """Reject a pending checkpoint."""
    return resolve_checkpoint(
        project_dir,
        status=CheckpointStatus.REJECTED,
        spec_slug=spec_slug,
        spec_hash=spec_hash,
        decision="rejected",
        notes=reason,
    )


# ============================================================================
# Private Helper Functions
# ============================================================================


def _get_agent_state_dir(project_dir: Path, spec_slug: str, spec_hash: str) -> Path:
    """Get the agent state directory for a spec.

    Args:
        project_dir: Project root directory
        spec_slug: Spec slug identifier (required)
        spec_hash: 5-character hex hash (required)

    Returns:
        Path to agent state directory in format .claude-agent/spec-slug-hash/

    Raises:
        ValueError: If spec_slug or spec_hash are not provided
    """
    if not spec_slug or not spec_hash:
        raise ValueError("Both spec_slug and spec_hash are required")

    base_dir = project_dir / AGENT_STATE_DIR
    return base_dir / f"{spec_slug}-{spec_hash}"


def _get_hitl_log_path(project_dir: Path, spec_slug: str, spec_hash: str) -> Path:
    """Get the path to the HITL checkpoint log file."""
    state_dir = _get_agent_state_dir(project_dir, spec_slug, spec_hash)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / HITL_LOG_FILE


def _collect_checkpoints(
    log_data: dict[str, list[dict]],
    predicate: Callable[[dict], bool],
) -> list[dict]:
    """Collect checkpoints matching a predicate.

    Args:
        log_data: Checkpoint log dictionary
        predicate: Function that returns True for checkpoints to include

    Returns:
        List of matching checkpoint dicts
    """
    return [ckpt_dict for checkpoints in log_data.values() for ckpt_dict in checkpoints if predicate(ckpt_dict)]


def _load_checkpoint_log(project_dir: Path, spec_slug: str, spec_hash: str) -> dict[str, list[dict]]:
    """Load the entire checkpoint log.

    Returns:
        Dictionary mapping issue_iid (or "global") to list of checkpoint dicts
    """
    log_path = _get_hitl_log_path(project_dir, spec_slug, spec_hash)
    if not log_path.exists():
        return {}

    try:
        with open(log_path, encoding="utf-8") as f:
            data = json.load(f)
            # Expect dict format: {issue_iid: [checkpoints]}
            if not isinstance(data, dict):
                return {}
            return data
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Silently return empty dict to handle corrupted/malformed files gracefully
        # Uncomment for debugging: import logging; logging.debug(f"Failed to load checkpoint log: {e}")
        _ = e  # Acknowledge exception variable to satisfy linters
        return {}


def _save_checkpoint_log(project_dir: Path, log_data: dict[str, list[dict]], spec_slug: str, spec_hash: str) -> None:
    """Save the checkpoint log atomically using temp file + rename pattern.

    This prevents file corruption if the process crashes during write.
    Uses atomic rename operation to ensure consistency.
    """
    log_path = _get_hitl_log_path(project_dir, spec_slug, spec_hash)

    # Write to temporary file in the same directory (required for atomic rename)
    fd, temp_path = tempfile.mkstemp(dir=log_path.parent, prefix=".hitl_tmp_", suffix=".json", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
            # Ensure all data is written to disk before rename
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename - this is the key operation for atomicity
        # On POSIX systems, rename is atomic even if target exists
        os.replace(temp_path, log_path)
    except Exception:
        # Clean up temp file if anything goes wrong
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_path)
        raise


def _atomic_checkpoint_update(
    project_dir: Path,
    spec_slug: str,
    spec_hash: str,
    checkpoint_id: str,
    update_fn: Callable[[dict], None],
) -> dict | None:
    """Atomically update a checkpoint in the log.

    This function implements the load-modify-save pattern with proper atomicity
    by using the atomic save_checkpoint_log function.

    Args:
        project_dir: Project directory
        spec_slug: Spec slug identifier
        spec_hash: 5-character hex hash
        checkpoint_id: Unique checkpoint ID to update
        update_fn: Function that modifies the checkpoint dict in-place

    Returns:
        The updated checkpoint dict, or None if not found
    """
    log_data = _load_checkpoint_log(project_dir, spec_slug, spec_hash)

    # Find and update checkpoint
    for _issue_key, checkpoints in log_data.items():
        for ckpt_dict in checkpoints:
            if ckpt_dict.get("checkpoint_id") == checkpoint_id:
                # Apply update function
                update_fn(ckpt_dict)

                # Save atomically (this is the critical operation)
                _save_checkpoint_log(project_dir, log_data, spec_slug, spec_hash)

                return ckpt_dict

    return None
