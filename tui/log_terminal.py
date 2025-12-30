"""
Log Terminal Widget
====================

Widget for displaying agent log output by tailing log files.
Agents run in the daemon process; this widget just displays their output.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.text import Text
from textual.widgets import RichLog


class LogTerminal(RichLog):
    """A terminal-like widget that tails a log file.

    This widget displays agent output by watching a log file written by the daemon.
    It uses async file tailing to show real-time updates.
    """

    _FILE_WAIT_INTERVAL: float = 0.5  # Seconds to wait when file doesn't exist
    _POLL_INTERVAL: float = 0.2  # Seconds between file reads for new content

    def __init__(
        self,
        log_file: Path | str | None = None,
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the log terminal.

        Args:
            log_file: Path to the log file to tail
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True,
        )
        self._log_file: Path | None = Path(log_file) if log_file else None
        self._tail_task: asyncio.Task[None] | None = None
        self._file_position: int = 0
        self._active: bool = False

    def start(self) -> None:
        """Start tailing the log file."""
        if not self._log_file:
            self.write(Text("[No log file set]", style="yellow"))
            return

        self._active = True
        self._start_tailing()

    def stop(self) -> None:
        """Stop tailing the log file."""
        self._active = False
        self._stop_tailing()

    def _start_tailing(self) -> None:
        """Start the tail task."""
        if self._tail_task and not self._tail_task.done():
            return

        self._tail_task = asyncio.create_task(self._tail_file())

    def _stop_tailing(self) -> None:
        """Stop the tail task."""
        if self._tail_task and not self._tail_task.done():
            self._tail_task.cancel()
            self._tail_task = None

    async def _tail_file(self) -> None:
        """Tail the log file and write new content to the widget."""
        if not self._log_file:
            return

        try:
            # Wait for file to exist
            while not self._log_file.exists():
                if not self._active:
                    return
                await asyncio.sleep(self._FILE_WAIT_INTERVAL)

            # Read existing content first
            with open(self._log_file, encoding="utf-8", errors="replace") as f:
                content = f.read()
                if content:
                    self._write_content(content)
                self._file_position = f.tell()

            # Then tail for new content
            while self._active:
                try:
                    with open(self._log_file, encoding="utf-8", errors="replace") as f:
                        f.seek(self._file_position)
                        new_content = f.read()
                        if new_content:
                            self._write_content(new_content)
                            self._file_position = f.tell()
                except FileNotFoundError:
                    # File was deleted, wait for it to reappear
                    pass

                await asyncio.sleep(self._POLL_INTERVAL)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.write(Text(f"[Error tailing log: {e}]", style="red"))

    def _write_content(self, content: str) -> None:
        """Write content to the widget, handling ANSI codes."""
        # Split into lines and write each
        for line in content.splitlines(keepends=True):
            # Strip trailing newline for cleaner display
            stripped_line = line.rstrip("\n\r")
            if stripped_line:
                self.write(Text.from_ansi(stripped_line))

    def on_mount(self) -> None:
        """Start tailing when mounted if a log file is set."""
        if self._log_file and self._active:
            self._start_tailing()

    def on_unmount(self) -> None:
        """Stop tailing when unmounted."""
        self._stop_tailing()
