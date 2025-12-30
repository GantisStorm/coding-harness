"""
Checkpoint Review Screen
=========================

Screen for reviewing and resolving HITL checkpoints.
"""

from collections.abc import Callable
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option  # Option not available from textual.widgets directly

from ..events import CheckpointResolved

# Constants for preview/summary text truncation
_MAX_SUMMARY_PREVIEW_LENGTH = 200
_MAX_DESCRIPTION_PREVIEW_LENGTH = 300

# Constants for title display truncation in ranking inputs
_MAX_TITLE_DISPLAY_LENGTH = 40
_MAX_TITLE_DISPLAY_LENGTH_COMPACT = 35


class CheckpointReviewScreen(Screen):
    """Screen for reviewing and resolving HITL checkpoints.

    Displays checkpoint details and provides appropriate actions based on
    the checkpoint type:
    - project_verification: Approve/Reject with notes
    - spec_to_issues: Approve/Reject with notes
    - regression_approval: Choose action (fix_now/defer/rollback/false_positive)
    - issue_selection: Approve recommended or select different issue
    - issue_closure: Approve/Reject with notes
    - mr_phase_transition: Approve/Reject transition to MR creation phase
    - mr_review: Approve/Modify/Reject
    """

    DEFAULT_CSS = """
    CheckpointReviewScreen {
        align: center middle;
    }

    CheckpointReviewScreen > Vertical {
        width: 90%;
        height: 90%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    CheckpointReviewScreen .title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    CheckpointReviewScreen .checkpoint-type {
        text-align: center;
        color: $primary;
        margin-bottom: 1;
    }

    CheckpointReviewScreen .details {
        height: 1fr;
        min-height: 10;
        border: round $primary;
        padding: 1;
        overflow-y: auto;
        overflow-x: auto;
        margin-bottom: 1;
        scrollbar-gutter: stable;
    }

    CheckpointReviewScreen .scroll-hint {
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }

    CheckpointReviewScreen .section-title {
        text-style: bold;
        color: $secondary;
        margin-top: 1;
    }

    CheckpointReviewScreen .notes-label {
        margin-top: 1;
        color: $text-muted;
    }

    CheckpointReviewScreen Input {
        margin-bottom: 1;
    }

    CheckpointReviewScreen TextArea {
        height: 4;
        margin-bottom: 1;
    }

    CheckpointReviewScreen OptionList {
        height: auto;
        max-height: 8;
        margin-bottom: 1;
        border: round $primary;
    }

    CheckpointReviewScreen .actions {
        height: auto;
        align: center middle;
    }

    CheckpointReviewScreen .actions Button {
        margin: 0 1;
    }

    CheckpointReviewScreen SelectionList {
        height: 100%;
        border: solid $primary;
    }

    CheckpointReviewScreen #enrichment-ranking,
    CheckpointReviewScreen #issue-ranking {
        height: auto;
        max-height: 15;
        overflow-y: auto;
        border: solid $primary;
        padding: 1;
    }

    CheckpointReviewScreen .ranking-row {
        height: 3;
        align: left middle;
    }

    CheckpointReviewScreen .rank-input {
        width: 8;
        min-width: 8;
        max-width: 8;
        margin-right: 1;
    }

    CheckpointReviewScreen .rank-label {
        width: 1fr;
    }

    CheckpointReviewScreen .issue-judgment-header {
        text-style: bold;
        padding: 1 0 0 0;
    }

    CheckpointReviewScreen .llm-reasoning {
        padding: 0 0 0 4;
        color: $accent;
    }

    CheckpointReviewScreen .recommended {
        color: $warning;
    }

    CheckpointReviewScreen .sufficient {
        color: $success;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("y", "quick_approve", "Quick Approve"),
        ("n", "quick_reject", "Quick Reject"),
        ("pageup", "scroll_up", "Scroll Up"),
        ("pagedown", "scroll_down", "Scroll Down"),
    ]

    def __init__(
        self,
        checkpoint_data: dict[str, Any],
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the checkpoint review screen.

        Args:
            checkpoint_data: The checkpoint data dict from hitl.py
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.checkpoint = checkpoint_data
        self.checkpoint_type = checkpoint_data.get("checkpoint_type", "unknown")
        self.context = checkpoint_data.get("context", {})

    def _handle_regression_action(self) -> None:
        """Handle regression approval action selection."""
        notes = self._get_notes()
        try:
            option_list = self.query_one("#regression-action", OptionList)
            if option_list.highlighted is not None:
                action = option_list.get_option_at_index(option_list.highlighted).id
                if action is None:
                    self.notify("Selected action has no ID", severity="error")
                    return
                self._resolve_and_dismiss(status="approved", notes=notes, decision=action)
            else:
                self.notify("Please select an action", severity="warning")
        except NoMatches as e:
            # Widget not found
            self.notify(f"Error: {e}", severity="error")

    def compose(self) -> ComposeResult:
        """Compose the checkpoint review screen."""

        type_display = self.checkpoint_type.upper().replace("_", " ")

        with Vertical():
            yield Static("HITL CHECKPOINT REVIEW", classes="title")
            yield Static(f"Type: {type_display}", classes="checkpoint-type")
            yield Static("↑↓ Scroll: PageUp/PageDown, Arrow keys, Mouse wheel", classes="scroll-hint")

            # Details section - scrollable
            with Vertical(classes="details"):
                yield from self._compose_details()

            # Notes input for user guidance with checkpoint-specific help
            notes_label, notes_placeholder, notes_examples = self._get_notes_guidance()
            yield Static(notes_label, classes="notes-label")
            yield Static(notes_examples, classes="notes-label")
            yield Input(
                placeholder=notes_placeholder,
                id="notes-input",
            )

            # Action-specific inputs
            yield from self._compose_action_inputs()

            # Action buttons
            with Horizontal(classes="actions"):
                yield from self._compose_action_buttons()

    def _compose_details(self) -> ComposeResult:
        """Compose the details section based on checkpoint type."""
        # Dispatch to type-specific composer
        composers = {
            "project_verification": self._compose_project_verification_details,
            "spec_to_issues": self._compose_spec_to_issues_details,
            "regression_approval": self._compose_regression_approval_details,
            "issue_selection": self._compose_issue_selection_details,
            "issue_closure": self._compose_issue_closure_details,
            "issue_enrichment": self._compose_issue_enrichment_details,
            "mr_phase_transition": self._compose_mr_phase_transition_details,
            "mr_review": self._compose_mr_review_details,
        }

        composer = composers.get(self.checkpoint_type)
        if composer:
            yield from composer()
        else:
            yield Static(f"Unknown checkpoint type: {self.checkpoint_type}")

    def _compose_project_verification_details(self) -> ComposeResult:
        """Compose details for project_verification checkpoint."""
        ctx = self.context
        yield Static("PROJECT DETAILS", classes="section-title")
        yield Static(f"  Project ID: {ctx.get('project_id', 'N/A')}")
        yield Static(f"  Project Path: {ctx.get('project_path', 'N/A')}")
        yield Static(f"  Milestone: {ctx.get('proposed_milestone_title', 'N/A')}")
        yield Static(f"  Feature Branch: {ctx.get('proposed_feature_branch', 'N/A')}")
        yield Static(f"  Target Branch: {ctx.get('proposed_target_branch', 'N/A')}")

        milestones = ctx.get("existing_milestones", [])
        if milestones:
            yield Static(f"\nEXISTING MILESTONES ({len(milestones)})", classes="section-title")
            for m in milestones[:5]:
                yield Static(f"  - {m.get('title', 'N/A')} (ID: {m.get('id', 'N/A')})")

    def _compose_spec_to_issues_details(self) -> ComposeResult:
        """Compose details for spec_to_issues checkpoint."""
        ctx = self.context
        yield Static(f"Spec: {ctx.get('spec_name', 'N/A')}", classes="section-title")
        total_count = ctx.get("total_count", len(ctx.get("proposed_issues", [])))
        yield Static(f"Total Issues: {total_count}")

        # Show summary counts if available
        by_priority = ctx.get("by_priority", {})
        by_category = ctx.get("by_category", {})

        if by_priority:
            priority_summary = " | ".join(f"{k}: {v}" for k, v in by_priority.items() if v > 0)
            if priority_summary:
                yield Static(f"By Priority: {priority_summary}")

        if by_category:
            category_summary = " | ".join(f"{k}: {v}" for k, v in by_category.items() if v > 0)
            if category_summary:
                yield Static(f"By Category: {category_summary}")

        yield Static("")  # Spacer

        # Show full details for each issue
        yield Static("-" * 60)
        yield Static("PROPOSED ISSUES (scroll to review all)", classes="section-title")
        yield Static("-" * 60)

        for i, issue in enumerate(ctx.get("proposed_issues", []), 1):
            title = issue.get("title", "Untitled")
            priority = issue.get("priority", "")
            category = issue.get("category", "")
            labels = issue.get("labels", [])

            # Issue header
            yield Static("")
            priority_badge = f"[{priority}]" if priority else ""
            category_badge = f"({category})" if category else ""
            yield Static(f"#{i} {priority_badge} {title} {category_badge}", classes="section-title")

            # Labels
            if labels:
                label_str = ", ".join(labels) if isinstance(labels, list) else str(labels)
                yield Static(f"   Labels: {label_str}")

            # Description - show full_description or description_preview
            description = (
                issue.get("full_description") or issue.get("description_preview") or issue.get("description", "")
            )
            if description:
                yield Static("   +-- Description ---------------------------------------------")
                # Split description into lines and indent each
                for line in description.split("\n"):
                    # Truncate very long lines
                    if len(line) > 100:
                        line = line[:97] + "..."
                    yield Static(f"   | {line}")
                yield Static("   +------------------------------------------------------------")
            else:
                yield Static("   (No description)")

        yield Static("")
        yield Static("-" * 60)
        yield Static(f"Total: {total_count} issues to be created")

    def _compose_regression_approval_details(self) -> ComposeResult:
        """Compose details for regression_approval checkpoint."""
        ctx = self.context
        yield Static("REGRESSION DETECTED", classes="section-title")
        yield Static(f"  Issue: #{ctx.get('regressed_issue_iid', 'N/A')} - {ctx.get('regressed_issue_title', 'N/A')}")
        yield Static("\nWhat Broke:")
        yield Static(f"  {ctx.get('what_broke', 'N/A')}")
        yield Static("\nCurrent Work:")
        yield Static(f"  {ctx.get('current_work_in_progress', 'N/A')}")

        yield Static("\nOPTIONS", classes="section-title")
        for opt in ctx.get("options", []):
            yield Static(f"  [{opt.get('action', 'N/A')}] {opt.get('description', 'N/A')}")

    def _compose_issue_selection_details(self) -> ComposeResult:
        """Compose details for issue_selection checkpoint."""
        ctx = self.context
        yield Static("ISSUE SELECTION - RANKED ORDER", classes="section-title")

        # Show LLM's recommended order
        rec_order = ctx.get("recommended_issue_order", [])
        available_issues = ctx.get("available_issues", [])

        if rec_order:
            yield Static("LLM RECOMMENDED ORDER:", classes="section-title")
            for i, iid in enumerate(rec_order[:5], 1):  # Show top 5
                # Find issue title
                issue_title = "Untitled"
                priority = ""
                for issue in available_issues:
                    if issue.get("iid") == iid:
                        issue_title = issue.get("title", "Untitled")
                        priority = issue.get("priority", "")
                        break
                priority_str = f" [{priority}]" if priority else ""
                yield Static(f"  {i}. #{iid}: {issue_title}{priority_str}")
            if len(rec_order) > 5:
                yield Static(f"  ... and {len(rec_order) - 5} more")
            yield Static("")

        yield Static(f"Reason: {ctx.get('recommendation_reason', 'N/A')}")

        yield Static(f"\nALL AVAILABLE ISSUES ({len(available_issues)})", classes="section-title")
        yield Static("-" * 50)
        for issue in available_issues[:10]:
            iid = issue.get("iid", "?")
            title = issue.get("title", "Untitled")
            rec_ord = issue.get("recommended_order")
            labels = ", ".join(issue.get("labels", [])[:3])  # Limit labels

            # Status indicator with recommended order
            status = f"LLM #{rec_ord}" if rec_ord else ""
            labels_str = f" [{labels}]" if labels else ""
            yield Static(f"  #{iid} {status}: {title}{labels_str}")
        if len(available_issues) > 10:
            yield Static(f"  ... and {len(available_issues) - 10} more")
        yield Static("-" * 50)

        yield Static("Enter rank (1,2,3...) to set order. Blank = LLM decides:", classes="section-title")

    def _compose_issue_closure_details(self) -> ComposeResult:
        """Compose details for issue_closure checkpoint."""
        ctx = self.context
        yield Static("ISSUE COMPLETED", classes="section-title")
        yield Static(f"  #{ctx.get('issue_iid', 'N/A')} - {ctx.get('issue_title', 'N/A')}")
        yield Static(f"  Commit: {ctx.get('commit_hash', 'N/A')}")

        yield Static("\nIMPLEMENTATION SUMMARY", classes="section-title")
        yield Static(f"  {ctx.get('implementation_summary', 'N/A')[:_MAX_SUMMARY_PREVIEW_LENGTH]}")

        yield Static("\nTEST CHECKLIST", classes="section-title")
        for item in ctx.get("test_checklist", []):
            status = "[x]" if item.get("passed") else "[ ]"
            yield Static(f"  {status} {item.get('description', 'N/A')}")

        yield Static(f"\nScreenshots: {len(ctx.get('screenshots', []))}")

    def _compose_issue_enrichment_details(self) -> ComposeResult:
        """Compose details for issue_enrichment checkpoint."""
        ctx = self.context
        yield Static("ISSUE ENRICHMENT - RANKED ORDER", classes="section-title")

        # Summary stats
        summary = ctx.get("judgment_summary", {})
        total = summary.get("total_issues", 0)
        sufficient = summary.get("sufficient_as_is", 0)
        recommended = summary.get("flagged_for_enrichment", 0)

        yield Static(f"Total: {total} | Sufficient: {sufficient} | Recommended: {recommended}")
        yield Static("")

        # Show LLM's recommended order
        rec_order = ctx.get("recommended_enrichment_order", [])
        if rec_order:
            yield Static("LLM RECOMMENDED ORDER:", classes="section-title")
            for i, iid in enumerate(rec_order, 1):
                # Find issue title
                all_issues = ctx.get("all_issues_with_judgments", [])
                issue_title = "Untitled"
                for issue in all_issues:
                    if issue.get("issue_iid") == iid:
                        issue_title = issue.get("title", "Untitled")
                        break
                yield Static(f"  {i}. #{iid}: {issue_title}")
            yield Static("")

        # Show all issues with LLM judgments
        all_issues = ctx.get("all_issues_with_judgments", [])
        if all_issues:
            yield Static("-" * 50)
            for issue in all_issues:
                iid = issue.get("issue_iid", "?")
                title = issue.get("title", "Untitled")
                judgment = issue.get("llm_judgment", {})
                decision = judgment.get("decision", "unknown")
                rec_ord = judgment.get("recommended_order")
                confidence = judgment.get("confidence", "?")
                complexity = judgment.get("estimated_complexity", "?")
                reasoning = judgment.get("reasoning", "")

                # Status indicator with recommended order
                status = self._get_enrichment_status_indicator(decision, rec_ord)
                yield Static(f"#{iid} {status} {title}")
                yield Static(f"    Confidence: {confidence} | Complexity: {complexity}")
                if reasoning:
                    short_reason = reasoning[:80] + "..." if len(reasoning) > 80 else reasoning
                    yield Static(f"    -> {short_reason}")
                yield Static("")
            yield Static("-" * 50)
        else:
            yield Static("  No issues with judgments available")

        yield Static("Enter rank (1,2,3...) to set order. Blank = LLM decides:", classes="section-title")

    def _compose_mr_phase_transition_details(self) -> ComposeResult:
        """Compose details for mr_phase_transition checkpoint."""
        ctx = self.context
        # NOTE: Depends on CheckpointType.MR_PHASE_TRANSITION in common/types.py (parallel change)
        yield Static("MR PHASE TRANSITION GATE", classes="section-title")
        yield Static(f"  Milestone: {ctx.get('milestone_title', 'N/A')}")
        yield Static(f"  Repository: {ctx.get('repository', 'N/A')}")
        yield Static(f"  Feature Branch: {ctx.get('feature_branch', 'N/A')}")
        yield Static(f"  Closed Issues: {ctx.get('closed_issue_count', 0)}")

        commit_hash = ctx.get("commit_hash")
        if commit_hash:
            yield Static(f"  Latest Commit: {commit_hash[:8]}")

        yield Static("\nPHASE TRANSITION", classes="section-title")
        yield Static("  All issues have been closed. The agent is ready to")
        yield Static("  transition to the MR creation phase.")
        yield Static("\n  Approve to allow MR creation, or reject to continue coding.")

    def _compose_mr_review_details(self) -> ComposeResult:
        """Compose details for mr_review checkpoint."""
        ctx = self.context
        yield Static("MERGE REQUEST", classes="section-title")
        yield Static(f"  Title: {ctx.get('mr_title', 'N/A')}")
        yield Static(f"  Source: {ctx.get('source_branch', 'N/A')}")
        yield Static(f"  Target: {ctx.get('target_branch', 'N/A')}")
        yield Static(f"  Issues to close: {ctx.get('issues_count', 0)}")

        yield Static("\nISSUES", classes="section-title")
        for issue in ctx.get("issues_to_close", [])[:10]:
            # Handle both dict format (with iid/title) and string format (e.g., "#88")
            if isinstance(issue, dict):
                yield Static(f"  #{issue.get('iid', 'N/A')}: {issue.get('title', 'N/A')}")
            else:
                yield Static(f"  {issue}")

        yield Static("\nDESCRIPTION PREVIEW", classes="section-title")
        desc = ctx.get("mr_description", "")[:_MAX_DESCRIPTION_PREVIEW_LENGTH]
        yield Static(f"  {desc}...")

    def _get_notes_guidance(self) -> tuple[str, str, str]:
        """Get checkpoint-specific guidance for human_notes.

        Returns:
            Tuple of (label, placeholder, examples_text)
        """
        guidance = {
            "project_verification": (
                "Notes / Guidance (optional) - Adjust project setup:",
                'e.g., "Use develop branch" or "Project ID should be 54321"',
                "Tip: Branch preferences, milestone title, project ID corrections, label requirements",
            ),
            "spec_to_issues": (
                "Notes / Guidance (optional) - Adjust issue breakdown:",
                'e.g., "Split auth into login + registration" or "Add priority labels"',
                "Tip: Split/merge issues, add estimates, skip features, priority labels, acceptance criteria",
            ),
            "issue_enrichment": (
                "Notes / Guidance (optional) - Guide enrichment decisions:",
                'e.g., "Research library X for issue #5" or "Issue #3 needs more codebase context"',
                "Tip: Request external research (Context7/web search), suggest codebase "
                "patterns to explore, flag spec gaps, identify missing dependencies",
            ),
            "regression_approval": (
                "Notes / Guidance (optional) - Provide regression context:",
                'e.g., "Happens on mobile only" or "Check event handlers"',
                "Tip: Where it happens, what to check, priority level, test requirements",
            ),
            "issue_selection": (
                "Notes / Guidance (optional) - Guide implementation approach:",
                'e.g., "Use library X" or "Focus on security" or "This is urgent"',
                "Tip: Implementation approach, library preferences, security focus, urgency, stakeholder checks",
            ),
            "issue_closure": (
                "Notes / Guidance (optional) - Feedback on implementation:",
                'e.g., "Great work" or "Fix: save function called twice" or "Add edge case tests"',
                "Tip: Praise, bugs found, missing features, edge cases, follow-up items",
            ),
            "mr_phase_transition": (
                "Notes / Guidance (optional) - Guide MR phase transition:",
                'e.g., "Wait for stakeholder review" or "Include cleanup commits"',
                "Tip: Final review requirements, stakeholder sign-off, cleanup tasks, "
                "defer if more testing needed, additional documentation",
            ),
            "mr_review": (
                "Notes / Guidance (optional) - Enhance MR description:",
                'e.g., "Add deployment notes" or "Mention breaking API changes"',
                "Tip: Breaking changes, deployment steps, security fixes, performance improvements, docs links",
            ),
        }

        return guidance.get(
            self.checkpoint_type,
            (
                "Notes / Guidance (optional):",
                "Add notes or guidance for the agent...",
                "Tip: Add any helpful context or instructions",
            ),
        )

    def _get_enrichment_status_indicator(self, decision: str, recommended_order: int | None) -> str:
        """Get status indicator string for enrichment decision.

        Args:
            decision: The LLM decision (e.g., "needs_enrichment", "sufficient")
            recommended_order: The LLM's recommended order number, if any

        Returns:
            Status indicator string like "[!] LLM #1", "[!] LLM", or "[ok]"
        """
        if decision == "needs_enrichment" and recommended_order:
            return f"[!] LLM #{recommended_order}"
        elif decision == "needs_enrichment":
            return "[!] LLM"
        return "[ok]"

    def _resolve_and_dismiss(
        self,
        status: str,
        notes: str | None = None,
        decision: str | None = None,
        modifications: dict[str, Any] | None = None,
    ) -> None:
        """Post checkpoint resolution and dismiss screen.

        Args:
            status: Resolution status (e.g., "approved", "rejected", "modified")
            notes: Optional user notes
            decision: Optional decision string (for regression_approval)
            modifications: Optional modifications dict
        """
        self.post_message(
            CheckpointResolved(
                status=status,
                decision=decision,
                notes=notes if notes else None,
                modifications=modifications,
            )
        )
        self.dismiss()

    def _compose_action_inputs(self) -> ComposeResult:
        """Compose action-specific input widgets."""
        if self.checkpoint_type == "regression_approval":
            yield Static("Select action:", classes="notes-label")
            option_list = OptionList(id="regression-action")
            option_list.add_option(Option("Fix Now - Fix the regression before continuing", id="fix_now"))
            option_list.add_option(Option("Defer - Mark as known issue, continue", id="defer"))
            option_list.add_option(Option("Rollback - Revert problematic commits", id="rollback"))
            option_list.add_option(Option("False Positive - Not a real regression", id="false_positive"))
            yield option_list

        elif self.checkpoint_type == "issue_enrichment":
            all_issues = self.context.get("all_issues_with_judgments", [])

            if all_issues:
                # Build ranked input fields for each issue
                yield Static("Issue Ranking (enter 1, 2, 3... or leave blank):", classes="notes-label")
                with Vertical(id="enrichment-ranking"):
                    for issue_data in all_issues:
                        iid = issue_data.get("issue_iid")
                        title = issue_data.get("title", "Untitled")
                        judgment = issue_data.get("llm_judgment", {})
                        decision = judgment.get("decision", "unknown")
                        rec_ord = judgment.get("recommended_order")

                        # Status indicator
                        status = self._get_enrichment_status_indicator(decision, rec_ord)

                        # Truncate title for display
                        short_title = (
                            title[:_MAX_TITLE_DISPLAY_LENGTH] + "..."
                            if len(title) > _MAX_TITLE_DISPLAY_LENGTH
                            else title
                        )

                        with Horizontal(classes="ranking-row"):
                            yield Input(
                                placeholder="#",
                                id=f"rank-{iid}",
                                classes="rank-input",
                                restrict=r"[0-9]*",
                                max_length=2,
                            )
                            yield Static(f"#{iid} {status} {short_title}", classes="rank-label")

                yield Static(
                    "LLM recommends [!] | Enter rank to override | Blank = use default",
                    classes="notes-label",
                )

        elif self.checkpoint_type == "issue_selection":
            available_issues = self.context.get("available_issues", [])

            if available_issues:
                # Build ranked input fields for each issue
                yield Static("Issue Ranking (enter 1, 2, 3... or leave blank):", classes="notes-label")
                with Vertical(id="issue-ranking"):
                    for issue in available_issues[:10]:  # Limit to 10
                        iid = issue.get("iid")
                        title = issue.get("title", "Untitled")
                        rec_ord = issue.get("recommended_order")
                        priority = issue.get("priority", "")

                        # Status indicator with LLM order
                        status = f"LLM #{rec_ord}" if rec_ord else ""
                        priority_str = f" [{priority}]" if priority else ""

                        # Truncate title for display
                        short_title = (
                            title[:_MAX_TITLE_DISPLAY_LENGTH_COMPACT] + "..."
                            if len(title) > _MAX_TITLE_DISPLAY_LENGTH_COMPACT
                            else title
                        )

                        with Horizontal(classes="ranking-row"):
                            yield Input(
                                placeholder="#",
                                id=f"issue-rank-{iid}",
                                classes="rank-input",
                                restrict=r"[0-9]*",
                                max_length=2,
                            )
                            yield Static(f"#{iid} {status}: {short_title}{priority_str}", classes="rank-label")

                yield Static("Enter rank to set order (1 = work first) | Blank = use LLM order", classes="notes-label")

        elif self.checkpoint_type == "mr_review":
            yield Static("Edit MR title (optional):", classes="notes-label")
            yield Input(
                value=self.context.get("mr_title", ""),
                id="mr-title-input",
            )

    def _compose_action_buttons(self) -> ComposeResult:
        """Compose action buttons based on checkpoint type."""
        if self.checkpoint_type == "regression_approval":
            yield Button("Apply Action", id="btn-apply-action", variant="success")
            yield Button("Cancel", id="btn-cancel", variant="default")

        elif self.checkpoint_type == "issue_selection":
            yield Button("Approve", id="btn-approve", variant="success", classes="action-btn-approve")
            yield Button("Skip", id="btn-reject", variant="warning")
            yield Button("Cancel", id="btn-cancel", variant="default")

        elif self.checkpoint_type == "mr_review":
            yield Button("Approve", id="btn-approve", variant="success", classes="action-btn-approve")
            yield Button("Approve with Edits", id="btn-modify", variant="primary")
            yield Button("Reject", id="btn-reject", variant="error", classes="action-btn-reject")
            yield Button("Cancel", id="btn-cancel", variant="default")

        else:
            # Default: approve/reject
            yield Button("Approve", id="btn-approve", variant="success", classes="action-btn-approve")
            yield Button("Reject", id="btn-reject", variant="error", classes="action-btn-reject")
            yield Button("Cancel", id="btn-cancel", variant="default")

    def _get_notes(self) -> str:
        """Get the notes from the input field."""
        try:
            notes_input = self.query_one("#notes-input", Input)
            return notes_input.value.strip()
        except NoMatches:
            # Widget not found in this checkpoint type
            return ""

    def _collect_rankings(
        self,
        items: list[dict[str, Any]],
        iid_key: str,
        input_id_prefix: str,
    ) -> list[int]:
        """Collect ranked item IIDs from input fields.

        Generic method for collecting user-specified rankings from input fields.
        Used by both enrichment and issue selection checkpoints.

        Args:
            items: List of item dictionaries containing IIDs
            iid_key: Key to extract IID from each item (e.g., "issue_iid" or "iid")
            input_id_prefix: Prefix for input field IDs (e.g., "rank-" or "issue-rank-")

        Returns:
            List of IIDs in the order specified by user rankings.
            Empty list means use defaults.
        """
        rankings: list[tuple[int, int]] = []  # (rank, iid)

        for item in items:
            iid = item.get(iid_key)
            if iid is None:
                continue

            try:
                rank_input = self.query_one(f"#{input_id_prefix}{iid}", Input)
                rank_value = rank_input.value.strip()
                if rank_value:
                    try:
                        rank = int(rank_value)
                        if rank > 0:
                            rankings.append((rank, iid))
                    except ValueError:
                        pass  # Invalid rank, skip
            except NoMatches:
                pass  # No input field for this issue

        rankings.sort(key=lambda x: x[0])
        return [iid for _, iid in rankings]

    def _collect_enrichment_rankings(self) -> list[int]:
        """Collect ranked issue IIDs from enrichment input fields.

        Returns a list of issue IIDs in the order specified by user rankings.
        Empty list means use LLM defaults.
        """
        return self._collect_rankings(
            items=self.context.get("all_issues_with_judgments", []),
            iid_key="issue_iid",
            input_id_prefix="rank-",
        )

    def _collect_issue_rankings(self) -> list[int]:
        """Collect ranked issue IIDs from issue selection input fields.

        Returns a list of issue IIDs in the order specified by user rankings.
        Empty list means use LLM defaults.
        """
        return self._collect_rankings(
            items=self.context.get("available_issues", []),
            iid_key="iid",
            input_id_prefix="issue-rank-",
        )

    def on_option_list_option_selected(self, _event: OptionList.OptionSelected) -> None:
        """Handle OptionList selection (Enter key or double-click)."""
        # Automatically trigger the appropriate action based on checkpoint type
        if self.checkpoint_type == "regression_approval":
            # Call the helper method directly
            self._handle_regression_action()

        # For issue_selection, issue_enrichment: use ranked inputs, not OptionList
        # For other checkpoint types: use Approve/Reject buttons

    def _handle_cancel(self) -> None:
        """Handle cancel button press."""
        self.dismiss()

    def _handle_approve(self) -> None:
        """Handle approve button press."""
        notes = self._get_notes()

        if self.checkpoint_type == "issue_enrichment":
            enrichment_order = self._collect_enrichment_rankings()
            # If user provided rankings, use them (modified status)
            # If empty, use LLM defaults (approved status)
            status = "modified" if enrichment_order else "approved"
            self._resolve_and_dismiss(status=status, notes=notes, modifications={"enrichment_order": enrichment_order})

        elif self.checkpoint_type == "issue_selection":
            issue_order = self._collect_issue_rankings()
            # If user provided rankings, use them (modified status)
            # If empty, use LLM defaults (approved status)
            status = "modified" if issue_order else "approved"
            self._resolve_and_dismiss(status=status, notes=notes, modifications={"issue_order": issue_order})

        else:
            # Other checkpoint types
            self._resolve_and_dismiss(status="approved", notes=notes)

    def _handle_reject(self) -> None:
        """Handle reject button press."""
        notes = self._get_notes()
        self._resolve_and_dismiss(status="rejected", notes=notes if notes else "Rejected via TUI")

    def _handle_modify(self) -> None:
        """Handle modify button press (MR review)."""
        notes = self._get_notes()
        try:
            title_input = self.query_one("#mr-title-input", Input)
            new_title = title_input.value.strip()
            original_title = self.context.get("mr_title", "")

            modifications: dict[str, Any] = {}
            if new_title and new_title != original_title:
                modifications["mr_title"] = new_title

            if modifications:
                self._resolve_and_dismiss(status="modified", notes=notes, modifications=modifications)
            else:
                # No actual modifications, just approve
                self._resolve_and_dismiss(status="approved", notes=notes)
        except NoMatches as e:
            # Widget not found
            self.notify(f"Error: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        handlers: dict[str | None, Callable[[], None]] = {
            "btn-cancel": self._handle_cancel,
            "btn-approve": self._handle_approve,
            "btn-reject": self._handle_reject,
            "btn-apply-action": self._handle_regression_action,
            "btn-modify": self._handle_modify,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    def action_cancel(self) -> None:
        """Cancel and dismiss the screen."""
        self.dismiss()

    def action_quick_approve(self) -> None:
        """Quick approve with appropriate defaults for each checkpoint type."""
        if self.checkpoint_type == "issue_enrichment":
            # Quick approve with LLM-recommended order (empty = use context.recommended_enrichment_order)
            self._resolve_and_dismiss(
                status="approved",
                notes="Quick approved with LLM-recommended order",
                modifications={"enrichment_order": []},  # Empty = use LLM defaults
            )
        elif self.checkpoint_type == "regression_approval":
            # Default to fix_now for regression
            self._resolve_and_dismiss(
                status="approved",
                decision="fix_now",
                notes="Quick approved with fix_now action",
            )
        elif self.checkpoint_type == "issue_selection":
            # Quick approve with LLM-recommended order (empty = use context.recommended_issue_order)
            self._resolve_and_dismiss(
                status="approved",
                notes="Quick approved with LLM-recommended order",
                modifications={"issue_order": []},  # Empty = use LLM defaults
            )
        else:
            # Default approve for other checkpoint types
            self._resolve_and_dismiss(status="approved")

    def action_quick_reject(self) -> None:
        """Quick reject (or skip) for checkpoint types that support it."""
        if self.checkpoint_type == "regression_approval":
            # Cannot quick reject regression - user must select an action
            self.notify(
                "Regression requires action selection. Use Fix Now, Defer, Rollback, or False Positive.",
                severity="warning",
                timeout=5,
            )
            return
        if self.checkpoint_type == "issue_enrichment":
            # Quick skip enrichment - reject to skip entirely
            self._resolve_and_dismiss(status="rejected", notes="Quick skipped - no enrichment")
        else:
            self._resolve_and_dismiss(status="rejected", notes="Quick rejected via TUI")

    def action_scroll_up(self) -> None:
        """Scroll the details section up."""
        try:
            details = self.query_one(".details")
            details.scroll_page_up()
        except NoMatches:
            pass

    def action_scroll_down(self) -> None:
        """Scroll the details section down."""
        try:
            details = self.query_one(".details")
            details.scroll_page_down()
        except NoMatches:
            pass
