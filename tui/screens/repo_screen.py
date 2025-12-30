"""
Repository Selection Screen
============================

Screen for selecting a repository working directory.
"""

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Input, Static

from ..events import RepoSelected


class RepoSelectScreen(Screen):
    """Screen for selecting a repository working directory.

    Displayed on startup to prompt the user for the repository path.
    Validates that the selected directory contains a .git folder.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("enter", "select", "Select"),
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS: ClassVar[str] = """
    RepoSelectScreen {
        align: center middle;
    }

    RepoSelectScreen > Vertical {
        width: 80%;
        height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    RepoSelectScreen .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    RepoSelectScreen .instructions {
        color: $text-muted;
        margin-bottom: 1;
    }

    RepoSelectScreen Input {
        margin-bottom: 1;
    }

    RepoSelectScreen DirectoryTree {
        height: 1fr;
        margin-bottom: 1;
        border: round $primary;
    }

    RepoSelectScreen Horizontal {
        height: auto;
        align: center middle;
    }

    RepoSelectScreen Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the repository selection screen.

        Args:
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        """Compose the repository selection screen."""
        with Vertical():
            yield Static("Select Repository Directory", classes="title")
            yield Static(
                "Choose a directory containing a Git repository. You can type a path or browse using the tree below.",
                classes="instructions",
            )
            yield Input(
                placeholder="Enter path or browse below",
                id="repo-path-input",
            )
            yield DirectoryTree(Path.home(), id="repo-tree")
            with Horizontal():
                yield Button("Select", id="repo-select", variant="success")
                yield Button("Cancel", id="repo-cancel", variant="default")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Update the input field when a directory is selected in the tree."""
        path_input = self.query_one("#repo-path-input", Input)
        path_input.value = str(event.path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "repo-select":
            path_input = self.query_one("#repo-path-input", Input)
            path_str = path_input.value.strip()

            if not path_str:
                self.notify("Please enter or select a directory path", severity="error")
                return

            path = Path(path_str).expanduser().resolve()
            is_valid, error_msg = self._validate_repo(path)

            if not is_valid:
                self.notify(error_msg, severity="error")
                return

            self.post_message(RepoSelected(path))
            self.dismiss()

        elif button_id == "repo-cancel":
            self.app.exit()

    def action_select(self) -> None:
        """Quick action to select the current path (Enter key)."""
        select_button = self.query_one("#repo-select", Button)
        select_button.press()

    def action_cancel(self) -> None:
        """Quick action to cancel selection (Escape key)."""
        self.app.exit()

    def _validate_repo(self, path: Path) -> tuple[bool, str]:
        """Validate that the path is a valid Git repository.

        Performs validation checks without raising exceptions. All validation
        failures are returned as (False, error_message) tuples.

        Args:
            path: The path to validate

        Returns:
            A tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if not path.exists():
            return False, f"Directory does not exist: {path}"

        if not path.is_dir():
            return False, f"Path is not a directory: {path}"

        git_dir = path / ".git"
        if not git_dir.exists():
            return False, f"Directory is not a Git repository (no .git folder): {path}"

        return True, ""
