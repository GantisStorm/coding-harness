"""
Branch Selection Screen
========================

Screen for selecting the target branch for merge requests.
"""

import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option  # Option not available from textual.widgets directly

from ..events import AgentConfigured

# Priority branch names for sorting (common default branches first)
_PRIORITY_BRANCHES = ["main", "master", "develop", "development"]
_GIT_COMMAND_TIMEOUT = 5  # seconds


class BranchSelectScreen(Screen):
    """Screen for selecting the target branch for merge requests.

    Displayed after spec selection to choose which branch the agent
    should target for its merge request.
    """

    DEFAULT_CSS = """
    BranchSelectScreen {
        align: center middle;
    }

    BranchSelectScreen > Vertical {
        width: 60%;
        height: 70%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    BranchSelectScreen .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    BranchSelectScreen .instructions {
        color: $text-muted;
        margin-bottom: 1;
    }

    BranchSelectScreen .spec-info {
        color: $primary;
        margin-bottom: 1;
    }

    BranchSelectScreen Input {
        margin-bottom: 1;
    }

    BranchSelectScreen OptionList {
        height: 1fr;
        margin-bottom: 1;
        border: round $primary;
    }

    BranchSelectScreen Horizontal {
        height: auto;
        align: center middle;
    }

    BranchSelectScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("enter", "select", "Select"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        repo_dir: Path,
        spec_path: Path,
        project_dir: Path,
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the branch selection screen.

        Args:
            repo_dir: The repository directory
            spec_path: The selected spec file path
            project_dir: The working directory for the agent
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.repo_dir = repo_dir
        self.spec_path = spec_path
        self.project_dir = project_dir

    def compose(self) -> ComposeResult:
        """Compose the branch selection screen."""
        branches = self._get_git_branches()

        with Vertical():
            yield Static("Select Target Branch", classes="title")
            yield Static(f"Spec: {self.spec_path.name}", classes="spec-info")
            yield Static(
                "Choose the branch that the merge request should target. "
                "Select from existing branches or enter a custom branch name.",
                classes="instructions",
            )
            yield Input(
                placeholder="Enter branch name or select below",
                id="branch-input",
                value=self._get_default_branch(branches),
            )
            option_list = OptionList(id="branch-list")
            for branch in branches:
                option_list.add_option(Option(branch, id=branch))
            yield option_list
            with Horizontal():
                yield Button("Select", id="branch-select", variant="success")
                yield Button("Cancel", id="branch-cancel", variant="default")

    def _get_git_branches(self) -> list[str]:
        """Get list of git branches from the repository."""
        return _get_branches(self.repo_dir)

    def _get_default_branch(self, branches: list[str]) -> str:
        """Get the default branch to pre-select."""
        # Try to detect the default branch
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=_GIT_COMMAND_TIMEOUT,
                check=False,  # We check returncode manually
            )
            if result.returncode == 0:
                # refs/remotes/origin/main -> main
                ref = result.stdout.strip()
                if "/" in ref:
                    return ref.split("/")[-1]
        except (subprocess.SubprocessError, OSError):
            pass

        # Fall back to first branch in list
        return branches[0] if branches else "main"

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Update the input field when a branch is selected."""
        branch_input = self.query_one("#branch-input", Input)
        if event.option.id:
            branch_input.value = str(event.option.id)

    def _validate_branch_name(self, branch: str) -> tuple[bool, str]:
        """Validate that the branch name follows git rules.

        Args:
            branch: The branch name to validate

        Returns:
            A tuple of (is_valid, error_message)
        """
        # Git branch name rules: https://git-scm.com/docs/git-check-ref-format
        invalid_chars = [" ", "~", "^", ":", "\\", "*", "?", "[", "@{"]
        if any(char in branch for char in invalid_chars):
            return False, "Invalid branch name: contains forbidden characters"
        if ".." in branch or branch.startswith(".") or branch.endswith(".") or branch.endswith(".lock"):
            return False, "Invalid branch name: invalid path component"
        if branch.endswith("/") or "//" in branch:
            return False, "Invalid branch name: invalid slash usage"
        return True, ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "branch-select":
            branch_input = self.query_one("#branch-input", Input)
            branch = branch_input.value.strip()

            if not branch:
                self.notify("Please enter or select a branch name", severity="error")
                return

            is_valid, error_msg = self._validate_branch_name(branch)
            if not is_valid:
                self.notify(error_msg, severity="error")
                return

            self.post_message(AgentConfigured(self.spec_path, self.project_dir, branch))
            self.dismiss()

        elif button_id == "branch-cancel":
            self.dismiss()

    def action_select(self) -> None:
        """Quick action to select the current branch (Enter key)."""
        select_button = self.query_one("#branch-select", Button)
        select_button.press()

    def action_cancel(self) -> None:
        """Quick action to cancel selection (Escape key)."""
        self.dismiss()


# ============================================================================
# Private Helper Functions
# ============================================================================


def _get_branches(repo_path: Path) -> list[str]:
    """
    Get list of git branches from the repository.

    Args:
        repo_path: Path to the git repository

    Returns:
        List of branch names, sorted with common branches (main, master, etc.) first
    """
    try:
        # Get all branches (local and remote)
        result = subprocess.run(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_GIT_COMMAND_TIMEOUT,
            check=False,  # We check returncode manually
        )
        if result.returncode != 0:
            return _PRIORITY_BRANCHES.copy()

        branches = []
        seen = set()
        for line in result.stdout.strip().split("\n"):
            branch = line.strip()
            # Skip empty lines and HEAD references
            if not branch or "HEAD" in branch:
                continue
            # Clean up remote branch names (origin/main -> main)
            if branch.startswith("origin/"):
                branch = branch[7:]
            # Skip duplicates
            if branch not in seen:
                seen.add(branch)
                branches.append(branch)

        # Ensure common branches are at the top
        priority = _PRIORITY_BRANCHES.copy()
        sorted_branches = []
        for p in priority:
            if p in branches:
                sorted_branches.append(p)
                branches.remove(p)
        sorted_branches.extend(sorted(branches))

        return sorted_branches if sorted_branches else ["main"]

    except (subprocess.SubprocessError, OSError):
        return _PRIORITY_BRANCHES.copy()
