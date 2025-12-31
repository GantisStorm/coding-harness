"""
Output Formatting Utilities
===========================

Centralized output formatting for consistent display.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.state import AgentState, MilestoneState
    from common.types import SessionType

# Callback type for TUI integration
OutputCallback = Callable[[str], None]

# Separator constants
SEPARATOR_HEAVY = "=" * 70
SEPARATOR_LIGHT = "-" * 70
SEPARATOR_MEDIUM = "-" * 50


def emit_output(on_output: OutputCallback | None, message: str) -> None:
    """Emit output to callback or print."""
    if on_output:
        on_output(message)
    else:
        print(message, end="" if not message.endswith("\n") else "")


def format_agent_header(
    project_dir: Path,
    model: str,
    spec_slug: str,
    spec_hash: str,
    max_iterations: int | None,
) -> str:
    """Format the initial agent header."""
    lines = [
        "",
        SEPARATOR_HEAVY,
        "  AUTONOMOUS CODING AGENT DEMO",
        SEPARATOR_HEAVY,
        f"\nProject directory: {project_dir}",
        f"Model: {model}",
        f"Spec slug: {spec_slug}",
        f"Agent files: .claude-agent/{spec_slug}-{spec_hash}/",
    ]
    if max_iterations:
        lines.append(f"Max iterations: {max_iterations}")
    else:
        lines.append("Max iterations: Unlimited (will run until completion)")
    lines.append("")
    return "\n".join(lines)


def format_session_header(session_num: int, is_initializer: bool) -> str:
    """Format a session header."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"
    return f"\n{SEPARATOR_HEAVY}\n  SESSION {session_num}: {session_type}\n{SEPARATOR_HEAVY}\n"


def format_phase_info(session_type: SessionType, state: AgentState | None) -> str:
    """Format phase-specific information."""
    # Import locally to avoid circular dependency
    from common.types import SessionType as SessionTypeEnum

    lines: list[str] = []

    if session_type == SessionTypeEnum.INITIALIZER:
        lines.extend(
            [
                "Phase 1: Initializer - Creating milestone and issues",
                "",
                SEPARATOR_HEAVY,
                "  NOTE: First session takes 10-20+ minutes!",
                "  The agent is creating a milestone and issues.",
                "  This may appear to hang - it's working. Watch for [Tool: ...] output.",
                SEPARATOR_HEAVY,
                "",
            ]
        )
    elif session_type == SessionTypeEnum.MR_CREATION:
        lines.append("Phase 3: MR Creation - All issues complete, creating merge request")
        if state and state.milestone:
            lines.append(format_progress_summary(state.milestone, state.file_only_mode))
    else:
        lines.append("Phase 2: Coding - Working on milestone issues")
        if state and state.milestone:
            lines.append(format_progress_summary(state.milestone, state.file_only_mode))

    return "\n".join(lines)


def format_progress_summary(milestone: MilestoneState | None, file_only_mode: bool) -> str:
    """Format current progress summary."""
    if milestone is None:
        mode_name = "File" if file_only_mode else "GitLab"
        return f"\nProgress: {mode_name} milestone not yet initialized"

    # Validate required fields
    required_fields = ["initialized", "repository", "milestone_id", "feature_branch", "all_issues_closed"]
    for field_name in required_fields:
        if not hasattr(milestone, field_name):
            return f"\nProgress: Milestone state invalid, missing {field_name}"

    total = milestone.total_issues
    milestone_name = milestone.milestone_name
    repo = milestone.repository

    mode_label = "File-Only" if file_only_mode else "GitLab"
    lines = [
        f"\n{mode_label} Milestone Status:",
        f"  Project: {repo}",
        f"  Milestone: {milestone_name}",
        f"  Total issues: {total}",
    ]

    if milestone.all_issues_closed:
        lines.append("  Status: All issues closed")
    elif not file_only_mode:
        lines.append("  (Check GitLab for current opened/closed counts)")

    return "\n".join(lines)


def format_final_summary(project_dir: Path, milestone: MilestoneState | None, file_only_mode: bool) -> str:
    """Format the final session summary."""
    lines = [
        f"\n{SEPARATOR_HEAVY}",
        "  SESSION COMPLETE",
        SEPARATOR_HEAVY,
        f"\nProject directory: {project_dir}",
        format_progress_summary(milestone, file_only_mode),
        "\nDone!",
    ]
    return "\n".join(lines)


def format_checkpoint_awaiting() -> str:
    """Format checkpoint awaiting message."""
    return f"\n{SEPARATOR_MEDIUM}\n  AWAITING APPROVAL:  [Y]/[1] Approve  [X]/[0] Reject\n{SEPARATOR_MEDIUM}"


def format_milestone_complete(feature_branch: str, target_branch: str) -> str:
    """Format message when coding is complete but MR creation skipped."""
    return f"""
{SEPARATOR_HEAVY}
  CODING COMPLETE - MR CREATION SKIPPED
{SEPARATOR_HEAVY}

All issues are closed. MR creation was skipped as requested.
Changes are available on branch: {feature_branch}

To create an MR manually:
  git push origin {feature_branch}
  # Then create MR via GitLab UI targeting {target_branch}
"""


def format_milestone_closed(merge_request_url: str | None) -> str:
    """Format message when milestone is already closed."""
    lines = [
        f"\n{SEPARATOR_HEAVY}",
        "  MILESTONE COMPLETED",
        SEPARATOR_HEAVY,
        "\nMilestone is already closed.",
    ]
    if merge_request_url:
        lines.append(f"Merge Request: {merge_request_url}")
    lines.append("\nNo further action needed. Exiting agent loop.")
    return "\n".join(lines)
