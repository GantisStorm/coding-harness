"""Agent daemon - background process management for agents."""

from .client import DaemonClient, DaemonError, DaemonNotRunningError
from .server import SOCKET_PATH, AgentDaemon

__all__ = [
    "AgentDaemon",
    "DaemonClient",
    "DaemonError",
    "DaemonNotRunningError",
    "SOCKET_PATH",
]
