"""
Agent Options Screen
====================

Screen for selecting agent behavior options:
- File-only mode for milestone/issue tracking
- Skip MR creation after coding completes
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Static

from ..events import FileOnlyModeSelected


class AgentOptionsScreen(Screen):
    """Screen for selecting agent behavior options.

    Allows the user to configure:
    - File-only mode: Use local JSON files instead of GitLab for tracking
    - Skip MR creation: Stop after coding without creating a merge request
    """

    DEFAULT_CSS = """
    AgentOptionsScreen {
        align: center middle;
    }

    AgentOptionsScreen > Vertical {
        width: 65%;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 2 4;
    }

    AgentOptionsScreen .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 2;
    }

    AgentOptionsScreen .section-title {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    AgentOptionsScreen .description {
        color: $text-muted;
        margin-bottom: 1;
    }

    AgentOptionsScreen Checkbox {
        margin: 1 0;
    }

    AgentOptionsScreen Horizontal {
        height: auto;
        align: center middle;
        margin-top: 2;
    }

    AgentOptionsScreen Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    BINDINGS = [
        ("enter", "continue", "Continue"),
        ("escape", "continue", "Continue"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the agent options screen."""
        with Vertical():
            yield Static("Agent Options", classes="title")

            yield Static("Issue Tracking", classes="section-title")
            yield Static(
                "Use local files instead of GitLab for milestone/issue tracking",
                classes="description",
            )
            yield Checkbox("Enable file-only mode", id="file-only-checkbox")

            yield Static("MR Creation", classes="section-title")
            yield Static(
                "Skip merge request creation after coding completes",
                classes="description",
            )
            yield Checkbox("Skip MR creation (keep changes on branch)", id="skip-mr-checkbox")

            yield Static("Testing Options", classes="section-title")
            yield Static(
                "Skip specific testing phases during development",
                classes="description",
            )
            yield Checkbox("Skip Puppeteer/browser automation", id="skip-puppeteer-checkbox")
            yield Checkbox("Skip test suite execution", id="skip-test-suite-checkbox")
            yield Checkbox("Skip regression spot-checks", id="skip-regression-checkbox")

            with Horizontal():
                yield Button("Continue", id="btn-continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "btn-continue":
            self._post_selection()

    def action_continue(self) -> None:
        """Quick action to continue with current selections."""
        self._post_selection()

    def _post_selection(self) -> None:
        """Post the selection message with current checkbox values."""
        try:
            file_only = self.query_one("#file-only-checkbox", Checkbox).value
            skip_mr = self.query_one("#skip-mr-checkbox", Checkbox).value
            skip_puppeteer = self.query_one("#skip-puppeteer-checkbox", Checkbox).value
            skip_test_suite = self.query_one("#skip-test-suite-checkbox", Checkbox).value
            skip_regression = self.query_one("#skip-regression-checkbox", Checkbox).value
            self.post_message(
                FileOnlyModeSelected(
                    file_only_mode=file_only,
                    skip_mr_creation=skip_mr,
                    skip_puppeteer=skip_puppeteer,
                    skip_test_suite=skip_test_suite,
                    skip_regression=skip_regression,
                )
            )
            self.dismiss()
        except NoMatches:
            # Should not happen in normal operation, but handle gracefully
            self.notify("Error: Required checkbox not found", severity="error")
