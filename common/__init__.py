"""Common package - Shared types and utilities for agent and TUI.

Note: DaemonError and DaemonNotRunningError are defined in agent/daemon/client.py
since they are tightly coupled with the daemon communication implementation.
"""

# Explicit re-exports for proper package API
# pylint: disable=useless-import-alias
from .exceptions import CheckpointError as CheckpointError
from .exceptions import CodingHarnessError as CodingHarnessError
from .exceptions import StateError as StateError
from .state import AgentState as AgentState
from .state import FileStateRepository as FileStateRepository
from .state import MilestoneState as MilestoneState
from .state import StateRepository as StateRepository
from .state import WorkspaceInfo as WorkspaceInfo
from .types import CheckpointData as CheckpointData
from .types import CheckpointStatus as CheckpointStatus
from .types import CheckpointType as CheckpointType
from .types import SessionType as SessionType
from .types import SpecConfig as SpecConfig
from .utils import generate_spec_hash as generate_spec_hash
from .utils import spec_filename_to_slug as spec_filename_to_slug
from .utils import validate_required_env_vars as validate_required_env_vars

# pylint: enable=useless-import-alias

__all__ = [
    # Exceptions
    "CheckpointError",
    "CodingHarnessError",
    "StateError",
    # State
    "AgentState",
    "FileStateRepository",
    "MilestoneState",
    "StateRepository",
    "WorkspaceInfo",
    # Types
    "CheckpointData",
    "CheckpointStatus",
    "CheckpointType",
    "SessionType",
    "SpecConfig",
    # Utils
    "generate_spec_hash",
    "spec_filename_to_slug",
    "validate_required_env_vars",
]
