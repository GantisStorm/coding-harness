"""
Dialog Screens
==============

Various dialog screens for user interaction.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..events import AddAnotherSpecResponse, AdvancedOptionsConfigured

# Constants
MAX_ITERATIONS_LIMIT = 1000


class AddAnotherSpecDialog(Screen):
    """Dialog asking if user wants to add another spec file.

    Shown after each spec is configured during batch creation mode.
    """

    DEFAULT_CSS = """
    AddAnotherSpecDialog {
        align: center middle;
    }

    AddAnotherSpecDialog > Vertical {
        width: 50%;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 2 4;
    }

    AddAnotherSpecDialog .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    AddAnotherSpecDialog .message {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    AddAnotherSpecDialog .count {
        text-align: center;
        color: $success;
        text-style: bold;
        margin-bottom: 2;
    }

    AddAnotherSpecDialog Horizontal {
        height: auto;
        align: center middle;
    }

    AddAnotherSpecDialog Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    BINDINGS = [
        ("y", "add_another", "Yes"),
        ("n", "done", "No"),
        ("escape", "done", "Done"),
    ]

    def __init__(
        self,
        spec_count: int,
        name: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        classes: str | None = None,
    ) -> None:
        """Initialize the add another spec dialog.

        Args:
            spec_count: Number of specs configured so far
            name: Optional widget name
            id: Optional widget ID
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.spec_count = spec_count

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical():
            yield Static("Add Another Spec?", classes="title")
            yield Static(f"You have configured {self.spec_count} spec(s) so far.", classes="count")
            yield Static(
                "Would you like to add another specification file?",
                classes="message",
            )
            with Horizontal():
                yield Button("Yes (y)", id="btn-yes", variant="success")
                yield Button("No, Create Agents (n)", id="btn-no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id: str | None = event.button.id

        if button_id == "btn-yes":
            self._respond_and_dismiss(add_another=True)
        elif button_id == "btn-no":
            self._respond_and_dismiss(add_another=False)

    def _respond_and_dismiss(self, add_another: bool) -> None:
        """Post response message and dismiss dialog."""
        self.post_message(AddAnotherSpecResponse(add_another=add_another))
        self.dismiss()

    def action_add_another(self) -> None:
        """Quick action to add another spec."""
        self._respond_and_dismiss(add_another=True)

    def action_done(self) -> None:
        """Quick action to finish adding specs."""
        self._respond_and_dismiss(add_another=False)


class AdvancedOptionsScreen(Screen):
    """Screen for configuring advanced options for a spec.

    Allows the user to configure max_iterations and model,
    or use defaults. Displayed after branch selection for each spec.
    """

    DEFAULT_CSS = """
    AdvancedOptionsScreen {
        align: center middle;
    }

    AdvancedOptionsScreen > Vertical {
        width: 60%;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 2 4;
    }

    AdvancedOptionsScreen .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    AdvancedOptionsScreen .instructions {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    AdvancedOptionsScreen .field-label {
        color: $text;
        margin-top: 1;
        margin-bottom: 0;
    }

    AdvancedOptionsScreen Input {
        margin-bottom: 1;
    }

    AdvancedOptionsScreen Horizontal {
        height: auto;
        align: center middle;
        margin-top: 2;
    }

    AdvancedOptionsScreen Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    BINDINGS = [
        ("enter", "apply", "Apply Settings"),
        ("escape", "use_defaults", "Use Defaults"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the advanced options screen."""
        with Vertical():
            yield Static("Advanced Options (Optional)", classes="title")
            yield Static(
                "Configure advanced options or use defaults",
                classes="instructions",
            )

            yield Static("Max Iterations:", classes="field-label")
            yield Input(
                placeholder="unlimited",
                id="max-iterations-input",
            )

            with Horizontal():
                yield Button("Use Defaults", id="btn-defaults", variant="default")
                yield Button("Apply Settings", id="btn-apply", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id: str | None = event.button.id

        if button_id == "btn-defaults":
            self._use_defaults()
        elif button_id == "btn-apply":
            self._apply_settings()

    def _use_defaults(self) -> None:
        """Use default settings (unlimited iterations)."""
        self.post_message(AdvancedOptionsConfigured(max_iterations=None))
        self.dismiss()

    def _apply_settings(self) -> None:
        """Validate user input and post message with settings.

        Validates max_iterations is a positive integer not exceeding 1000.
        Shows notification on validation failure and returns without posting.
        """
        # Get input values
        max_iterations_input = self.query_one("#max-iterations-input", Input)

        # Validate and parse max_iterations
        max_iterations_str = max_iterations_input.value.strip()
        if max_iterations_str:
            try:
                max_iterations = int(max_iterations_str)
                if max_iterations <= 0:
                    self.notify("Max iterations must be a positive integer", severity="error")
                    return
                if max_iterations > MAX_ITERATIONS_LIMIT:
                    self.notify(f"Max iterations cannot exceed {MAX_ITERATIONS_LIMIT}", severity="error")
                    return
            except ValueError:
                self.notify("Max iterations must be a valid integer", severity="error")
                return
        else:
            max_iterations = None

        # Post message with validated values
        self.post_message(AdvancedOptionsConfigured(max_iterations=max_iterations))
        self.dismiss()

    def action_use_defaults(self) -> None:
        """Quick action to use defaults (ESC key)."""
        self._use_defaults()

    def action_apply(self) -> None:
        """Quick action to apply settings (Enter key)."""
        self._apply_settings()
