"""
Log Viewer Screen
==================

Full-screen log viewer with scroll, selection, and copy support.
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static, TextArea

_ERROR_PREFIX = "Error loading log:"


class LogViewerScreen(Screen):
    """Full-screen log viewer with text selection and copy support.

    Features:
    - Scrollable log content
    - Text selection (click and drag)
    - Copy selection (Ctrl+C) or copy all (Ctrl+Shift+C)
    - Auto-scroll to bottom on open
    """

    DEFAULT_CSS = """
    LogViewerScreen {
        align: center middle;
    }

    LogViewerScreen > Vertical {
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 0;
    }

    LogViewerScreen .header {
        height: 1;
        background: $primary;
        padding: 0 1;
        text-style: bold;
    }

    LogViewerScreen .log-content {
        height: 1fr;
        margin: 0;
        padding: 0;
    }

    LogViewerScreen TextArea {
        height: 100%;
        border: none;
    }

    LogViewerScreen .footer {
        height: 3;
        background: $primary-darken-2;
        padding: 0 1;
        align: center middle;
    }

    LogViewerScreen .footer Button {
        margin: 0 1;
    }

    LogViewerScreen .hint {
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("ctrl+shift+c", "copy_all", "Copy All"),
        Binding("g", "scroll_top", "Top"),
        Binding("shift+g", "scroll_bottom", "Bottom"),
    ]

    def __init__(
        self,
        log_file: Path,
        agent_name: str,
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the log viewer screen.

        Args:
            log_file: Path to the log file to display
            agent_name: Name of the agent whose log is being viewed
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.log_file = log_file
        self.agent_name = agent_name
        self._content = ""

    @property
    def _text_area(self) -> TextArea:
        """Get the log text area widget."""
        return self.query_one("#log-text", TextArea)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f" Log: {self.agent_name} - {self.log_file.name}", classes="header")
            yield Static(
                " Ctrl+C: copy selection | Ctrl+Shift+C: copy all | g/G: top/bottom | q/Esc: close",
                classes="hint",
            )
            with Vertical(classes="log-content"):
                yield TextArea(id="log-text", read_only=True, show_line_numbers=True)
            with Horizontal(classes="footer"):
                yield Button("Copy All", id="btn-copy-all", variant="primary")
                yield Button("Copy Path", id="btn-copy-path", variant="default")
                yield Button("Close", id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Load log content on mount."""
        self._load_content()

    def _load_content(self) -> None:
        """Load the log file content."""
        try:
            self._content = self.log_file.read_text(encoding="utf-8", errors="replace")
            if not self._content:
                self._content = "(Log file is empty)"
        except OSError as e:
            self._content = f"{_ERROR_PREFIX} {e}"
        self._text_area.load_text(self._content)
        if not self._content.startswith(_ERROR_PREFIX) and self._content != "(Log file is empty)":
            self._text_area.scroll_end(animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-close":
            self.dismiss()
        elif event.button.id == "btn-copy-all":
            self.action_copy_all()
        elif event.button.id == "btn-copy-path":
            self.app.copy_to_clipboard(str(self.log_file))
            self.notify("Path copied to clipboard")

    def action_close(self) -> None:
        """Close the log viewer."""
        self.dismiss()

    def action_copy_all(self) -> None:
        """Copy full log content to clipboard."""
        self.app.copy_to_clipboard(self._content)
        lines = self._content.count("\n")
        self.notify(f"Copied {lines} lines to clipboard")

    def action_scroll_top(self) -> None:
        """Scroll to top of log."""
        self._text_area.scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        """Scroll to bottom of log."""
        self._text_area.scroll_end(animate=False)
