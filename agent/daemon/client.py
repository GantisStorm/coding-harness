"""
Agent Daemon Client
====================

Client for TUI to communicate with the agent daemon via Unix socket.
Provides async methods for starting, stopping, and monitoring agents.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

# Must match daemon.py
SOCKET_PATH = Path("/tmp/coding-harness-daemon.sock")


class DaemonError(Exception):
    """Error from daemon communication."""


class DaemonNotRunningError(DaemonError):
    """Daemon is not running."""


class DaemonClient:
    """Async client for communicating with the agent daemon."""

    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> DaemonClient:
        """Enter async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Exit async context manager."""
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the daemon."""
        if not SOCKET_PATH.exists():
            raise DaemonNotRunningError(f"Daemon socket not found: {SOCKET_PATH}")

        try:
            self._reader, self._writer = await asyncio.open_unix_connection(str(SOCKET_PATH))
        except (ConnectionRefusedError, FileNotFoundError) as e:
            raise DaemonNotRunningError(f"Cannot connect to daemon: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from the daemon."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def _send_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send a command to the daemon and return the response."""
        async with self._lock:
            if not self._reader or not self._writer:
                await self.connect()

            if not self._reader or not self._writer:
                raise DaemonNotRunningError("Not connected to daemon")

            try:
                # Send command
                self._writer.write(json.dumps(command).encode() + b"\n")
                await self._writer.drain()

                # Read response with timeout to prevent indefinite blocking
                try:
                    data = await asyncio.wait_for(self._reader.readline(), timeout=30.0)
                except TimeoutError:
                    await self.disconnect()
                    raise DaemonError("Daemon response timeout") from None
                if not data:
                    raise DaemonError("Daemon closed connection")

                response = json.loads(data.decode())
                return response

            except (ConnectionResetError, BrokenPipeError) as e:
                # Connection lost, try to reconnect
                await self.disconnect()
                raise DaemonError(f"Connection lost: {e}") from e

    def _validate_response(
        self, response: dict[str, Any], error_msg: str, return_key: str | None = None
    ) -> dict[str, Any]:
        """Validate daemon response and extract result.

        Args:
            response: The response dict from _send_command
            error_msg: Default error message if status is not ok
            return_key: Optional key to extract from response (e.g., "agent", "agents")

        Returns:
            dict[str, Any]: If return_key is None, returns the full response dict.
                If return_key is provided, returns the value at that key (as dict),
                or an empty dict if the key is missing or value is not a dict.

        Raises:
            DaemonError: If response status is not "ok"
        """
        if response.get("status") != "ok":
            raise DaemonError(response.get("message", error_msg))
        if return_key:
            result = response.get(return_key, {})
            return result if isinstance(result, dict) else {}
        return response

    async def ping(self) -> bool:
        """Check if daemon is running.

        Note: This method is available for external use but currently has no
        consumers in the codebase. Consider using is_daemon_running() for sync
        checks or calling list_agents() which implicitly verifies connectivity.
        """
        try:
            response = await self._send_command({"cmd": "ping"})
            return response.get("status") == "ok"
        except DaemonError:
            return False

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all agents."""
        response = await self._send_command({"cmd": "list"})
        self._validate_response(response, "Failed to list agents")
        return response.get("agents", [])

    async def register_agent(self, agent_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Register an agent without starting it (for persistence).

        Args:
            agent_id: Unique identifier for the agent
            config: Agent configuration

        Returns:
            Agent info dict
        """
        response = await self._send_command(
            {
                "cmd": "register",
                "agent_id": agent_id,
                "config": config,
            }
        )
        return self._validate_response(response, "Failed to register agent", "agent")

    async def start_agent(self, agent_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Start a new agent.

        Args:
            agent_id: Unique identifier for the agent
            config: Agent configuration with keys:
                - spec_file: Path to spec file
                - project_dir: Project directory
                - target_branch: Target branch for MR
                - max_iterations: Optional max iterations
                - auto_accept: Optional auto-accept mode

        Returns:
            Agent info dict
        """
        response = await self._send_command(
            {
                "cmd": "start",
                "agent_id": agent_id,
                "config": config,
            }
        )
        return self._validate_response(response, "Failed to start agent", "agent")

    async def stop_agent(self, agent_id: str) -> dict[str, Any]:
        """Stop an agent."""
        response = await self._send_command(
            {
                "cmd": "stop",
                "agent_id": agent_id,
            }
        )
        return self._validate_response(response, "Failed to stop agent", "agent")

    async def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        """Get status of a specific agent.

        Note: This method is available for external use but currently has no
        consumers in the codebase. The TUI uses list_agents() and tracks status
        via AgentSession objects instead.
        """
        response = await self._send_command(
            {
                "cmd": "status",
                "agent_id": agent_id,
            }
        )
        return self._validate_response(response, "Failed to get status", "agent")

    async def remove_agent(self, agent_id: str) -> None:
        """Remove an agent (stops it if running)."""
        response = await self._send_command(
            {
                "cmd": "remove",
                "agent_id": agent_id,
            }
        )
        self._validate_response(response, "Failed to remove agent")

    async def shutdown_daemon(self) -> None:
        """Shutdown the daemon.

        Note: This method is available for external use but currently has no
        consumers in the codebase. The daemon is typically stopped via CLI
        or by sending SIGTERM directly.
        """
        with contextlib.suppress(DaemonError):
            await self._send_command({"cmd": "shutdown"})


# Convenience functions for sync code
def is_daemon_running() -> bool:
    """Check if daemon is running (sync version)."""
    return SOCKET_PATH.exists()


def get_daemon_pid() -> int | None:
    """Get daemon PID from pid file.

    Returns None if file doesn't exist, is unreadable, or contains invalid data.
    """
    pid_file = Path("/tmp/coding-harness-daemon.pid")
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        # File exists but is unreadable or contains invalid PID
        return None
