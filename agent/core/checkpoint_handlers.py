"""
Checkpoint Handler Strategy Pattern
===================================

Each checkpoint type has a dedicated handler class.
Adding new checkpoint types = adding new handler class (OCP compliant).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from common.exceptions import CheckpointError
from common.types import CheckpointData, CheckpointType

if TYPE_CHECKING:
    from common.state import AgentState
    from common.types import SpecConfig


@dataclass
class HandlerContext:
    """Context passed to checkpoint handlers."""

    state: AgentState
    spec_config: SpecConfig
    project_dir: str


@dataclass
class HandlerResult:
    """Result from checkpoint handling."""

    resolved: bool
    output: str
    decision: str | None = None
    notes: str | None = None
    modifications: dict[str, Any] | None = None


class CheckpointHandler(Protocol):
    """Strategy interface for checkpoint types."""

    def can_handle(self, checkpoint_type: CheckpointType) -> bool:
        """Return True if this handler can process the checkpoint type."""
        ...

    def auto_approve(self, checkpoint: CheckpointData, ctx: HandlerContext) -> HandlerResult:
        """Auto-approve the checkpoint (for auto-accept mode)."""
        ...


class IssueEnrichmentHandler:
    """Handler for ISSUE_ENRICHMENT checkpoints."""

    def can_handle(self, checkpoint_type: CheckpointType) -> bool:
        return checkpoint_type == CheckpointType.ISSUE_ENRICHMENT

    def auto_approve(self, checkpoint: CheckpointData, ctx: HandlerContext) -> HandlerResult:
        """Auto-approve with LLM-recommended issues for enrichment."""
        all_issues = checkpoint.context.get("all_issues_with_judgments", [])
        selected_iids = [
            issue_data.get("issue_iid")
            for issue_data in all_issues
            if issue_data.get("llm_judgment", {}).get("decision") == "needs_enrichment"
            and issue_data.get("issue_iid") is not None
        ]

        if selected_iids:
            notes = f"Auto-approved with {len(selected_iids)} LLM-recommended issues for enrichment"
        else:
            notes = "Auto-approved - no issues flagged for enrichment"

        return HandlerResult(
            resolved=True,
            output=f"[HITL] Checkpoint auto-approved: Issue Enrichment\n[HITL] Modifications: {{'selected_issue_iids': {selected_iids}}}",
            notes=notes,
            modifications={"selected_issue_iids": selected_iids},
        )


class RegressionApprovalHandler:
    """Handler for REGRESSION_APPROVAL checkpoints."""

    def can_handle(self, checkpoint_type: CheckpointType) -> bool:
        return checkpoint_type == CheckpointType.REGRESSION_APPROVAL

    def auto_approve(self, checkpoint: CheckpointData, ctx: HandlerContext) -> HandlerResult:
        """Auto-approve with fix_now action."""
        return HandlerResult(
            resolved=True,
            output="[HITL] Checkpoint auto-approved: Regression Approval\n[HITL] Decision: fix_now",
            decision="fix_now",
            notes="Auto-approved with fix_now action",
        )


class IssueSelectionHandler:
    """Handler for ISSUE_SELECTION checkpoints."""

    def can_handle(self, checkpoint_type: CheckpointType) -> bool:
        return checkpoint_type == CheckpointType.ISSUE_SELECTION

    def auto_approve(self, checkpoint: CheckpointData, ctx: HandlerContext) -> HandlerResult:
        """Auto-approve with recommended issue."""
        rec_iid = checkpoint.context.get("recommended_issue_iid")
        if rec_iid:
            return HandlerResult(
                resolved=True,
                output=f"[HITL] Checkpoint auto-approved: Issue Selection\n[HITL] Selected issue #{rec_iid}",
                notes=f"Auto-approved recommended issue #{rec_iid}",
                modifications={"selected_issue_iid": rec_iid},
            )
        return HandlerResult(
            resolved=True,
            output="[HITL] Checkpoint auto-approved: Issue Selection",
            notes="Auto-approved (no specific recommendation)",
        )


class DefaultCheckpointHandler:
    """Default handler for checkpoint types without specific logic."""

    def __init__(self, handled_types: list[CheckpointType] | None = None) -> None:
        """Initialize with optional list of types to handle.

        If handled_types is None, handles all types not handled by other handlers.
        """
        self._handled_types = handled_types

    def can_handle(self, checkpoint_type: CheckpointType) -> bool:
        if self._handled_types is None:
            return True  # Catch-all
        return checkpoint_type in self._handled_types

    def auto_approve(self, checkpoint: CheckpointData, ctx: HandlerContext) -> HandlerResult:
        """Auto-approve with default behavior."""
        checkpoint_type_display = checkpoint.checkpoint_type.value.replace("_", " ").title()
        return HandlerResult(
            resolved=True,
            output=f"[HITL] Checkpoint auto-approved: {checkpoint_type_display}",
            notes="Auto-approved",
        )


class CheckpointDispatcher:
    """Coordinates checkpoint handling using registered handlers."""

    def __init__(self, handlers: list[CheckpointHandler] | None = None) -> None:
        """Initialize with optional list of handlers.

        If handlers is None, uses default handler set.
        """
        if handlers is None:
            self.handlers: list[CheckpointHandler] = [
                IssueEnrichmentHandler(),
                RegressionApprovalHandler(),
                IssueSelectionHandler(),
                DefaultCheckpointHandler(),  # Catch-all last
            ]
        else:
            self.handlers = handlers

    def get_handler(self, checkpoint_type: CheckpointType) -> CheckpointHandler:
        """Get the handler for a checkpoint type."""
        for handler in self.handlers:
            if handler.can_handle(checkpoint_type):
                return handler
        raise CheckpointError(f"No handler registered for checkpoint type: {checkpoint_type}")

    def auto_approve(self, checkpoint: CheckpointData, ctx: HandlerContext) -> HandlerResult:
        """Auto-approve a checkpoint using the appropriate handler."""
        handler = self.get_handler(checkpoint.checkpoint_type)
        return handler.auto_approve(checkpoint, ctx)
