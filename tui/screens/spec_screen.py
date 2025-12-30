"""
Spec File Selection Screen
===========================

Screen for selecting a specification file.
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Input, Static

from ..events import SpecSelected


class SpecSelectScreen(Screen):
    """Screen for selecting a specification file.

    Displayed when starting a new agent to select the spec file to process.
    """

    BINDINGS = [
        ("enter", "select", "Select"),
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    SpecSelectScreen {
        align: center middle;
    }

    SpecSelectScreen > Vertical {
        width: 80%;
        height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    SpecSelectScreen .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    SpecSelectScreen .instructions {
        color: $text-muted;
        margin-bottom: 1;
    }

    SpecSelectScreen Input {
        margin-bottom: 1;
    }

    SpecSelectScreen DirectoryTree {
        height: 1fr;
        margin-bottom: 1;
        border: round $primary;
    }

    SpecSelectScreen Horizontal {
        height: auto;
        align: center middle;
    }

    SpecSelectScreen Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        repo_dir: Path,
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the spec selection screen.

        Args:
            repo_dir: The repository directory to start browsing from
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.repo_dir = repo_dir

    def compose(self) -> ComposeResult:
        """Compose the spec file selection screen."""
        with Vertical():
            yield Static(f"Select Specification File for {self.repo_dir.name}", classes="title")

            yield Static(
                "Choose a specification file to process. You can type a path or browse using the tree below.",
                classes="instructions",
            )
            yield Input(
                placeholder="Enter path or browse below",
                id="spec-path-input",
            )
            yield DirectoryTree(self.repo_dir, id="spec-tree")
            with Horizontal():
                yield Button("Select", id="spec-select", variant="success")
                yield Button("Cancel", id="spec-cancel", variant="default")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Update the input field when a file is selected in the tree."""
        path_input = self.query_one("#spec-path-input", Input)
        path_input.value = str(event.path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "spec-select":
            path_input = self.query_one("#spec-path-input", Input)
            path_str = path_input.value.strip()

            if not path_str:
                self.notify("Please enter or select a file path", severity="error")
                return

            path = Path(path_str).expanduser().resolve()
            is_valid, error_msg = self._validate_spec(path)

            if not is_valid:
                self.notify(error_msg, severity="error")
                return

            self.post_message(SpecSelected(path))
            self.dismiss()

        elif button_id == "spec-cancel":
            self.dismiss()

    def _validate_spec(self, path: Path) -> tuple[bool, str]:
        """Validate that the path is a valid, readable spec file.

        Args:
            path: The path to validate

        Returns:
            A tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if not path.exists():
            return False, f"File does not exist: {path}"

        if not path.is_file():
            return False, f"Path is not a file: {path}"

        # Check if the file is readable
        try:
            path.read_bytes()[:1]
        except OSError as e:
            return False, f"Cannot read file: {e}"

        return True, ""

    def action_select(self) -> None:
        """Quick action to select the current path (Enter key)."""
        select_button = self.query_one("#spec-select", Button)
        select_button.press()

    def action_cancel(self) -> None:
        """Quick action to cancel selection (Escape key)."""
        self.dismiss()
