"""
Coding Harness Exception Hierarchy
==================================

Structured exceptions for the coding harness.
All harness-specific exceptions inherit from CodingHarnessError.

Note: DaemonError and DaemonNotRunningError are defined in agent/daemon/client.py
since they are tightly coupled with the daemon communication implementation.
"""

from __future__ import annotations


class CodingHarnessError(Exception):
    """Base exception for all harness errors.

    All harness-specific exceptions should inherit from this class.
    This allows callers to catch all harness errors with a single except clause.
    """


class StateError(CodingHarnessError):
    """State load/save failed.

    Raised when:
    - State file is corrupted
    - State file cannot be written
    - State validation fails
    """


class CheckpointError(CodingHarnessError):
    """Checkpoint handling failed.

    Raised when:
    - Checkpoint file is corrupted
    - No handler for checkpoint type
    - Checkpoint resolution fails
    """
