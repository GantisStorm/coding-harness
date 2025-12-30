"""
Shared Types and Data Classes
==============================

Common type definitions used across agent and TUI packages.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Default target branch for merge requests
DEFAULT_TARGET_BRANCH: str = "main"


# ============================================================================
# HITL Checkpoint Types
# ============================================================================


class CheckpointType(str, Enum):
    """Types of HITL checkpoints."""

    PROJECT_VERIFICATION = "project_verification"
    SPEC_TO_ISSUES = "spec_to_issues"
    ISSUE_ENRICHMENT = "issue_enrichment"
    REGRESSION_APPROVAL = "regression_approval"
    ISSUE_SELECTION = "issue_selection"
    ISSUE_CLOSURE = "issue_closure"
    MR_PHASE_TRANSITION = "mr_phase_transition"  # Gate for transitioning to MR creation phase
    MR_REVIEW = "mr_review"


class CheckpointStatus(str, Enum):
    """Status of a HITL checkpoint."""

    PENDING = "pending"  # Awaiting human review
    APPROVED = "approved"  # Human approved
    REJECTED = "rejected"  # Human rejected
    MODIFIED = "modified"  # Human approved with modifications
    SKIPPED = "skipped"  # Checkpoint was auto-approved (auto-accept mode)


class SessionType(str, Enum):
    """Types of agent sessions."""

    INITIALIZER = "initializer"
    CODING = "coding"
    MR_CREATION = "mr_creation"


@dataclass
class CheckpointData:
    """Data for a HITL checkpoint."""

    checkpoint_type: CheckpointType
    status: CheckpointStatus = CheckpointStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_at: str | None = None

    # Context provided by agent
    context: dict[str, Any] = field(default_factory=dict)

    # Human response
    human_decision: str | None = None
    human_notes: str | None = None
    modifications: dict[str, Any] | None = None

    # Persistent log fields
    completed: bool = False
    completed_at: str | None = None
    issue_iid: str | None = None  # String to match JSON keys ("123" not 123, or "global")
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:13])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all checkpoint fields, enum values as strings.
        """
        return {
            "checkpoint_type": self.checkpoint_type.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "context": self.context,
            "human_decision": self.human_decision,
            "human_notes": self.human_notes,
            "modifications": self.modifications,
            "completed": self.completed,
            "completed_at": self.completed_at,
            "issue_iid": self.issue_iid,
            "checkpoint_id": self.checkpoint_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointData:
        """Create CheckpointData from dictionary.

        Args:
            data: Dictionary containing checkpoint data, typically from JSON.

        Returns:
            New CheckpointData instance with fields populated from dict.

        Raises:
            KeyError: If required 'checkpoint_type' key is missing from data.
            ValueError: If checkpoint_type value is not a valid CheckpointType.
        """
        if "checkpoint_type" not in data:
            raise KeyError("Required key 'checkpoint_type' missing from checkpoint data dict")
        return cls(
            checkpoint_type=CheckpointType(data["checkpoint_type"]),
            status=CheckpointStatus(data.get("status", "pending")),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            resolved_at=data.get("resolved_at"),
            context=data.get("context", {}),
            human_decision=data.get("human_decision"),
            human_notes=data.get("human_notes"),
            modifications=data.get("modifications"),
            completed=data.get("completed", False),
            completed_at=data.get("completed_at"),
            issue_iid=data.get("issue_iid"),
            checkpoint_id=data.get("checkpoint_id", str(uuid.uuid4())[:13]),
        )


# ============================================================================
# Spec Configuration
# ============================================================================


@dataclass
class SpecConfig:  # pylint: disable=too-many-instance-attributes
    """
    Configuration for a single specification file in a multi-spec environment.

    Each SpecConfig represents an independent workspace for processing a specification.
    This enables the agent to handle multiple specs simultaneously, each with its own
    project directory, target branch, and state tracking.

    Attributes:
        spec_file: Path to the specification file to be processed
        project_dir: Root project directory for this spec (must exist)
        target_branch: Git branch name to target for this spec's changes
        spec_slug: URL-safe identifier derived from the spec filename
        spec_hash: 5-character unique hash for this spec (enforces uniqueness)
        name: Human-readable display name for this spec
        max_iterations: Optional[int] = None - Maximum iterations allowed (None = unlimited)
        model: str - Claude model ID to use (default from CLAUDE_MODEL env var or claude-opus-4-5-20251101)

    Properties:
        agent_dir: Path to the agent's state directory for this spec
                  (computed as project_dir/.claude-agent/spec_slug)

    Example:
        >>> config = SpecConfig(
        ...     spec_file=Path("specs/feature-auth.txt"),
        ...     project_dir=Path("/projects/myapp"),
        ...     target_branch="feature/auth",
        ...     spec_slug="feature-auth",
        ...     name="Authentication Feature"
        ... )
        >>> print(config.agent_dir)
        /projects/myapp/.claude-agent/feature-auth
    """

    spec_file: Path
    project_dir: Path
    target_branch: str
    spec_slug: str
    spec_hash: str = ""
    name: str = ""
    max_iterations: int | None = None
    model: str = ""  # Will be set from env or default in __post_init__
    file_only_mode: bool = False  # If True, use local files instead of GitLab for tracking
    skip_mr_creation: bool = False  # If True, skip MR creation after coding completes

    def __post_init__(self) -> None:
        """
        Validate the configuration after initialization.

        Ensures that:
        1. The project directory exists and is accessible
        2. The spec file exists and is readable
        3. Auto-generates spec_hash if not provided
        4. Auto-generates name if not provided

        Raises:
            ValueError: If project_dir doesn't exist or spec_file isn't readable
        """
        # Import here to avoid circular dependency
        from common.utils import generate_spec_hash

        # Ensure project_dir exists
        if not self.project_dir.exists():
            raise ValueError(f"Project directory does not exist: {self.project_dir}")

        if not self.project_dir.is_dir():
            raise ValueError(f"Project directory path is not a directory: {self.project_dir}")

        # Ensure spec_file is readable
        if not self.spec_file.exists():
            raise ValueError(f"Spec file does not exist: {self.spec_file}")

        if not self.spec_file.is_file():
            raise ValueError(f"Spec file path is not a file: {self.spec_file}")

        # Attempt to read the spec file to ensure it's readable
        try:
            self.spec_file.read_text(encoding="utf-8")
        except (PermissionError, OSError) as e:
            raise ValueError(f"Spec file is not readable: {self.spec_file}. Error: {e}") from e

        # Auto-generate spec_hash if not provided (using object.__setattr__ for frozen-like behavior)
        if not self.spec_hash:
            object.__setattr__(self, "spec_hash", generate_spec_hash(self.spec_file))

        # Auto-generate name if not provided
        if not self.name:
            object.__setattr__(self, "name", self.spec_file.stem)

        # Set model from environment if not provided
        if not self.model:
            object.__setattr__(self, "model", os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101"))

        # Validate max_iterations
        if self.max_iterations is not None and self.max_iterations <= 0:
            raise ValueError(f"max_iterations must be a positive integer or None, got: {self.max_iterations}")

        # Validate model
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError(f"model must be a non-empty string, got: {self.model}")

        # Validate spec_hash format (must be exactly 5 hex characters)
        if not re.match(r"^[a-f0-9]{5}$", self.spec_hash):
            raise ValueError(f"spec_hash must be exactly 5 lowercase hex characters, got: {self.spec_hash}")

        # Validate spec_slug format (alphanumeric, hyphens, no leading/trailing hyphens)
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", self.spec_slug):
            raise ValueError(
                f"spec_slug must contain only lowercase letters, numbers, and hyphens "
                f"(no leading/trailing hyphens), got: {self.spec_slug}"
            )

    @property
    def agent_dir(self) -> Path:
        """Get the agent's state directory for this spec.

        The agent directory stores all spec-specific state including progress
        tracking, generated artifacts, and temporary files.

        Returns:
            Path: project_dir/.claude-agent/{spec_slug}-{spec_hash}
        """
        return self.project_dir / ".claude-agent" / f"{self.spec_slug}-{self.spec_hash}"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the SpecConfig to a dictionary for serialization.

        Path objects are converted to strings for JSON compatibility.

        Returns:
            Dictionary representation with string paths

        Example:
            >>> config.to_dict()
            {
                'spec_file': '/path/to/spec.txt',
                'project_dir': '/path/to/project',
                'target_branch': 'feature/auth',
                'spec_slug': 'feature-auth',
                'name': 'Authentication Feature'
            }
        """
        return {
            "spec_file": str(self.spec_file),
            "project_dir": str(self.project_dir),
            "target_branch": self.target_branch,
            "spec_slug": self.spec_slug,
            "spec_hash": self.spec_hash,
            "name": self.name,
            "max_iterations": self.max_iterations,
            "model": self.model,
            "file_only_mode": self.file_only_mode,
            "skip_mr_creation": self.skip_mr_creation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecConfig:
        """
        Create a SpecConfig from a dictionary.

        String paths are converted back to Path objects.
        If spec_slug, spec_hash, or name are not provided, they are auto-generated from spec_file.

        Args:
            data: Dictionary containing spec configuration (typically from JSON)

        Returns:
            New SpecConfig instance

        Raises:
            KeyError: If required keys (spec_file, project_dir, target_branch) are missing.
            ValueError: If paths don't exist or validation fails in __post_init__.

        Example:
            >>> # Minimal - spec_slug, spec_hash, and name auto-generated
            >>> data = {
            ...     'spec_file': '/path/to/spec.txt',
            ...     'project_dir': '/path/to/project',
            ...     'target_branch': 'feature/auth'
            ... }
            >>> config = SpecConfig.from_dict(data)
            >>> # Full - with all fields
            >>> data = {
            ...     'spec_file': '/path/to/spec.txt',
            ...     'project_dir': '/path/to/project',
            ...     'target_branch': 'feature/auth',
            ...     'spec_slug': 'feature-auth',
            ...     'spec_hash': 'a1b2c',
            ...     'name': 'Authentication Feature'
            ... }
            >>> config = SpecConfig.from_dict(data)
        """
        # Import here to avoid circular dependency
        from common.utils import generate_spec_hash, spec_filename_to_slug

        spec_file = Path(data["spec_file"])

        # Auto-generate spec_slug if not provided
        spec_slug = data["spec_slug"] if "spec_slug" in data else spec_filename_to_slug(spec_file)

        # Auto-generate spec_hash if not provided
        spec_hash = data["spec_hash"] if "spec_hash" in data else generate_spec_hash(spec_file)

        # Auto-generate name if not provided (use filename stem as fallback)
        name = data.get("name", spec_file.stem)

        return cls(
            spec_file=spec_file,
            project_dir=Path(data["project_dir"]),
            target_branch=data["target_branch"],
            spec_slug=spec_slug,
            spec_hash=spec_hash,
            name=name,
            max_iterations=data.get("max_iterations"),
            model=data.get("model", os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101")),
            file_only_mode=data.get("file_only_mode", False),
            skip_mr_creation=data.get("skip_mr_creation", False),
        )
