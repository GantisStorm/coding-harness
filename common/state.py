"""
Unified State Management
========================

Provides a single interface for all state operations.
Replaces scattered JSON file access with a clean repository pattern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from common.types import CheckpointData, CheckpointStatus

if TYPE_CHECKING:
    from common.types import CheckpointType


@dataclass
class MilestoneState:
    """Milestone tracking state."""

    initialized: bool = False
    repository: str = ""
    milestone_id: int = 0
    milestone_name: str = ""
    feature_branch: str = ""
    total_issues: int = 0
    all_issues_closed: bool = False
    milestone_closed: bool = False
    merge_request_url: str | None = None
    enrichments: dict[str, Any] = field(default_factory=dict)
    progress_comments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "initialized": self.initialized,
            "repository": self.repository,
            "milestone_id": self.milestone_id,
            "milestone_name": self.milestone_name,
            "feature_branch": self.feature_branch,
            "total_issues": self.total_issues,
            "all_issues_closed": self.all_issues_closed,
            "milestone_closed": self.milestone_closed,
            "merge_request_url": self.merge_request_url,
            "enrichments": self.enrichments,
            "progress_comments": self.progress_comments,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MilestoneState:
        """Create from dictionary."""
        return cls(
            initialized=data.get("initialized", False),
            repository=data.get("repository", ""),
            milestone_id=data.get("milestone_id", 0),
            milestone_name=data.get("milestone_name", data.get("title", "")),
            feature_branch=data.get("feature_branch", ""),
            total_issues=data.get("total_issues", 0),
            all_issues_closed=data.get("all_issues_closed", False),
            milestone_closed=data.get("milestone_closed", False),
            merge_request_url=data.get("merge_request_url"),
            enrichments=data.get("enrichments", {}),
            progress_comments=data.get("progress_comments", {}),
        )


@dataclass
class WorkspaceInfo:
    """Workspace configuration state."""

    spec_slug: str = ""
    spec_hash: str = ""
    spec_file: str = ""
    target_branch: str = "main"
    file_only_mode: bool = False
    skip_mr_creation: bool = False
    auto_accept: bool = False
    skip_puppeteer: bool = False
    skip_test_suite: bool = False
    skip_regression_testing: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "spec_slug": self.spec_slug,
            "spec_hash": self.spec_hash,
            "spec_file": self.spec_file,
            "target_branch": self.target_branch,
            "file_only_mode": self.file_only_mode,
            "skip_mr_creation": self.skip_mr_creation,
            "auto_accept": self.auto_accept,
            "skip_puppeteer": self.skip_puppeteer,
            "skip_test_suite": self.skip_test_suite,
            "skip_regression_testing": self.skip_regression_testing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceInfo:
        """Create from dictionary."""
        return cls(
            spec_slug=data.get("spec_slug", ""),
            spec_hash=data.get("spec_hash", ""),
            spec_file=data.get("spec_file", ""),
            target_branch=data.get("target_branch", "main"),
            file_only_mode=data.get("file_only_mode", False),
            skip_mr_creation=data.get("skip_mr_creation", False),
            auto_accept=data.get("auto_accept", False),
            skip_puppeteer=data.get("skip_puppeteer", False),
            skip_test_suite=data.get("skip_test_suite", False),
            skip_regression_testing=data.get("skip_regression_testing", False),
        )


@dataclass
class AgentState:
    """Unified agent state container.

    Aggregates all state needed by the agent into a single object.
    """

    milestone: MilestoneState | None = None
    workspace: WorkspaceInfo | None = None
    checkpoint_log: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def is_initialized(self) -> bool:
        """Check if milestone is initialized."""
        return self.milestone is not None and self.milestone.initialized

    @property
    def all_issues_closed(self) -> bool:
        """Check if all issues are closed."""
        return self.milestone is not None and self.milestone.all_issues_closed

    @property
    def auto_accept(self) -> bool:
        """Check if auto-accept is enabled."""
        return self.workspace is not None and self.workspace.auto_accept

    @property
    def file_only_mode(self) -> bool:
        """Check if running in file-only mode."""
        return self.workspace is not None and self.workspace.file_only_mode


class StateRepository(Protocol):
    """Abstract state storage interface.

    Implementations provide persistence for agent state.
    This protocol enables testing with mock implementations.
    """

    def load(self, project_dir: Path, spec_slug: str, spec_hash: str) -> AgentState:
        """Load complete agent state."""
        ...

    def load_pending_checkpoint(self, project_dir: Path, spec_slug: str, spec_hash: str) -> CheckpointData | None:
        """Load the most recent pending checkpoint."""
        ...

    def is_checkpoint_type_approved(
        self,
        project_dir: Path,
        spec_slug: str,
        spec_hash: str,
        checkpoint_type: CheckpointType,
    ) -> bool:
        """Check if a checkpoint type has been approved."""
        ...


class FileStateRepository:
    """JSON file-based state repository.

    Maintains backward compatibility with existing file structure:
    - .workspace_info.json
    - .gitlab_milestone.json / .file_milestone.json
    - .hitl_checkpoint_log.json
    """

    WORKSPACE_FILE = ".workspace_info.json"
    GITLAB_MILESTONE_FILE = ".gitlab_milestone.json"
    FILE_MILESTONE_FILE = ".file_milestone.json"
    CHECKPOINT_LOG_FILE = ".hitl_checkpoint_log.json"

    def _get_agent_dir(self, project_dir: Path, spec_slug: str, spec_hash: str) -> Path:
        """Get the agent state directory."""
        return project_dir / ".claude-agent" / f"{spec_slug}-{spec_hash}"

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        """Read JSON file, return None on error."""
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def load(self, project_dir: Path, spec_slug: str, spec_hash: str) -> AgentState:
        """Load complete agent state from files."""
        agent_dir = self._get_agent_dir(project_dir, spec_slug, spec_hash)

        # Load workspace info
        workspace_data = self._read_json(agent_dir / self.WORKSPACE_FILE)
        workspace = WorkspaceInfo.from_dict(workspace_data) if workspace_data else None

        # Determine milestone file based on mode
        file_only_mode = workspace.file_only_mode if workspace else False
        milestone_file = self.FILE_MILESTONE_FILE if file_only_mode else self.GITLAB_MILESTONE_FILE
        milestone_data = self._read_json(agent_dir / milestone_file)
        milestone = MilestoneState.from_dict(milestone_data) if milestone_data else None

        # Load checkpoint log
        checkpoint_data = self._read_json(agent_dir / self.CHECKPOINT_LOG_FILE)
        checkpoint_log = checkpoint_data if isinstance(checkpoint_data, dict) else {}

        return AgentState(
            milestone=milestone,
            workspace=workspace,
            checkpoint_log=checkpoint_log,
        )

    def load_pending_checkpoint(self, project_dir: Path, spec_slug: str, spec_hash: str) -> CheckpointData | None:
        """Load the most recent pending checkpoint."""
        agent_dir = self._get_agent_dir(project_dir, spec_slug, spec_hash)
        checkpoint_data = self._read_json(agent_dir / self.CHECKPOINT_LOG_FILE)

        if not checkpoint_data or not isinstance(checkpoint_data, dict):
            return None

        # Find all pending checkpoints across all issues
        all_pending: list[dict[str, Any]] = []
        for checkpoints in checkpoint_data.values():
            if isinstance(checkpoints, list):
                for ckpt in checkpoints:
                    if not ckpt.get("completed", False):
                        all_pending.append(ckpt)

        if not all_pending:
            return None

        # Return most recent by created_at
        latest = max(all_pending, key=lambda x: x.get("created_at", ""))
        return CheckpointData.from_dict(latest)

    def is_checkpoint_type_approved(
        self,
        project_dir: Path,
        spec_slug: str,
        spec_hash: str,
        checkpoint_type: CheckpointType,
    ) -> bool:
        """Check if a checkpoint type has been approved."""
        agent_dir = self._get_agent_dir(project_dir, spec_slug, spec_hash)
        checkpoint_data = self._read_json(agent_dir / self.CHECKPOINT_LOG_FILE)

        if not checkpoint_data or not isinstance(checkpoint_data, dict):
            return False

        # Find all checkpoints of this type
        matching: list[dict[str, Any]] = []
        for checkpoints in checkpoint_data.values():
            if isinstance(checkpoints, list):
                for ckpt in checkpoints:
                    if ckpt.get("checkpoint_type") == checkpoint_type.value:
                        matching.append(ckpt)

        if not matching:
            return False

        # Check if latest is approved
        latest = max(matching, key=lambda x: x.get("created_at", ""))
        return latest.get("status") == CheckpointStatus.APPROVED.value
