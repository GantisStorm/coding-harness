"""
TUI Events Module
==================

Custom event types for TUI communication between widgets and agent runner.
"""

from pathlib import Path
from typing import Any

from textual.message import Message

__all__ = [
    "RepoSelected",
    "CheckpointResolved",
    "SpecSelected",
    "FileOnlyModeSelected",
    "AgentConfigured",
    "AddAnotherSpecResponse",
    "AdvancedOptionsConfigured",
]

# =============================================================================
# TUI Events
# =============================================================================


class RepoSelected(Message):
    """Message sent when a repository directory is selected."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__()


class CheckpointResolved(Message):
    """Message sent when a checkpoint is resolved via the review screen."""

    def __init__(
        self,
        status: str,  # "approved", "rejected", "modified"
        decision: str | None = None,  # For regression: fix_now, defer, rollback, false_positive
        notes: str | None = None,  # User guidance/notes
        modifications: dict[str, Any] | None = None,  # For modified checkpoints
    ) -> None:
        self.status = status
        self.decision = decision
        self.notes = notes
        self.modifications = modifications
        super().__init__()


class SpecSelected(Message):
    """Message sent when a spec file is selected."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__()


class FileOnlyModeSelected(Message):
    """Message sent when agent options are selected (file-only mode, skip flags)."""

    def __init__(
        self,
        file_only_mode: bool,
        skip_mr_creation: bool,
        skip_puppeteer: bool = False,
        skip_test_suite: bool = False,
        skip_regression: bool = False,
    ) -> None:
        self.file_only_mode = file_only_mode
        self.skip_mr_creation = skip_mr_creation
        self.skip_puppeteer = skip_puppeteer
        self.skip_test_suite = skip_test_suite
        self.skip_regression = skip_regression
        super().__init__()


class AgentConfigured(Message):
    """Message sent when agent is fully configured (spec + branch + project_dir)."""

    def __init__(self, spec_path: Path, project_dir: Path, target_branch: str) -> None:
        self.spec_path = spec_path
        self.project_dir = project_dir
        self.target_branch = target_branch
        super().__init__()


class AddAnotherSpecResponse(Message):
    """Message sent when user responds to 'add another spec' prompt."""

    def __init__(self, add_another: bool) -> None:
        self.add_another = add_another
        super().__init__()


class AdvancedOptionsConfigured(Message):
    """Message sent when user configures advanced options."""

    def __init__(
        self,
        max_iterations: int | None,
    ) -> None:
        self.max_iterations = max_iterations
        super().__init__()
