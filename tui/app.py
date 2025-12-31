# pylint: disable=too-many-lines
"""
TUI Application - Terminal-based agent runner

Uses daemon architecture: agents run in background daemon process,
TUI connects to display output and control agents.
"""

import contextlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal  # noqa: E402
from textual.css.query import NoMatches  # noqa: E402
from textual.widgets import Footer, Header, OptionList, Static  # noqa: E402
from textual.widgets.option_list import Option  # noqa: E402

from agent.core import (  # noqa: E402
    approve_checkpoint,
    get_pending_checkpoint_type,
    is_checkpoint_pending,
    load_pending_checkpoint,
    reject_checkpoint,
    resolve_checkpoint,
)

# Import agent functionality for orchestration
from agent.daemon import DaemonClient, DaemonError, DaemonNotRunningError  # noqa: E402
from common import (  # noqa: E402
    CheckpointStatus,
    SpecConfig,
    generate_spec_hash,
    spec_filename_to_slug,
)

from .events import (  # noqa: E402
    AddAnotherSpecResponse,
    AdvancedOptionsConfigured,
    AgentConfigured,
    CheckpointResolved,
    FileOnlyModeSelected,
    RepoSelected,
    SpecSelected,
)
from .log_terminal import LogTerminal  # noqa: E402
from .screens import (  # noqa: E402
    AddAnotherSpecDialog,
    AdvancedOptionsScreen,
    AgentOptionsScreen,
    BranchSelectScreen,
    CheckpointReviewScreen,
    LogViewerScreen,
    RepoSelectScreen,
    SpecSelectScreen,
)

# Agent status constants
STATUS_READY = "ready"
STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"


@dataclass
class AgentSession:
    """Tracks an agent and its associated configuration.

    Attributes:
        agent_id: Unique agent identifier
        config: Spec configuration
        terminal: LogTerminal widget displaying agent output (tails log file)
        status: Current agent status ("ready", "running", "stopped")
        log_file: Path to agent's log file (written by daemon)
        agent_dir: Path to agent workspace directory
        spec_slug: Unique spec identifier
        name: Display name
        auto_accept: Whether auto-accept mode is enabled for this agent
    """

    agent_id: str
    config: SpecConfig
    terminal: LogTerminal | None = None
    status: str = STATUS_READY
    log_file: Path | None = None
    # Computed fields (set in __post_init__)
    agent_dir: Path = field(init=False)
    spec_slug: str = field(init=False)
    name: str = field(init=False)
    auto_accept: bool = field(init=False)

    def __post_init__(self) -> None:
        """Initialize workspace and load preferences."""
        # Use pre-computed values from SpecConfig (which already has the hash)
        self.agent_dir = self.config.agent_dir
        self.spec_slug = self.config.spec_slug
        self.name = self.config.name

        # Load auto-accept preference from file
        self.auto_accept = _load_auto_accept_preference(self.config.project_dir, self.spec_slug, self.config.spec_hash)


class CodingHarnessApp(App):
    """Terminal-based TUI for running spec agents.

    Uses daemon architecture:
    - Agents run as subprocesses of the daemon (not TUI)
    - TUI connects to daemon to start/stop/list agents
    - TUI tails log files to display agent output
    - TUI can exit/restart without affecting running agents
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #info-bar {
        height: 1;
        background: $primary-darken-2;
        padding: 0 1;
    }

    #workspace {
        height: 1fr;
        layout: horizontal;
    }

    #agent-list {
        width: 26;
        height: 100%;
        border-right: solid $primary-darken-2;
        padding: 0;
    }

    #agent-list OptionList {
        height: 1fr;
        margin: 0;
    }

    #terminal-area {
        width: 1fr;
        height: 100%;
    }

    #terminal-status {
        height: 100%;
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }

    .agent-terminal {
        height: 100%;
        margin: 0 1;
        background: $surface;
        border: none;
    }

    .agent-terminal:focus {
        border: none;
    }
    """

    BINDINGS = [
        # Global commands (no agent selection needed)
        Binding("q", "quit", "Quit"),
        Binding("?", "show_help", "Help"),
        Binding("n", "new_agent", "New"),
        Binding("f", "toggle_fullscreen", "Full"),
        # Agent commands (require agent selection) - prefixed with ▸
        Binding("s", "start_agent", "▸Start"),
        Binding("k", "stop_agent", "▸Stop"),
        Binding("d", "delete_agent", "▸Del"),
        Binding("a", "toggle_auto_accept", "▸Auto"),
        Binding("b", "change_branch", "▸Branch"),
        # Checkpoint commands (require agent + checkpoint) - prefixed with ◆
        Binding("r", "review_checkpoint", "◆Review"),
        Binding("y", "hitl_approve", "◆Yes"),
        Binding("x", "hitl_reject", "◆No"),
        # Log commands (require agent selection) - prefixed with ▸
        Binding("c", "copy_logs", "▸Copy"),
        Binding("o", "open_logs", "▸View"),
        # Hidden aliases
        Binding("1", "hitl_approve", "Approve", show=False),
        Binding("0", "hitl_reject", "Reject", show=False),
    ]

    def __init__(
        self,
        spec_configs: list[SpecConfig] | None = None,
    ):
        super().__init__()
        self.agents: dict[str, AgentSession] = {}
        self.selected_agent: str | None = None
        self._agent_counter = 0
        self._daemon_client = DaemonClient()

        # Multi-spec state management
        self._preload_specs = spec_configs or []

        # Multi-spec wizard state
        self._batch_specs: list[SpecConfig] = []
        self._in_batch_mode: bool = False
        self._batch_project_dir: Path | None = None
        self._batch_spec: Path | None = None
        self._batch_spec_base: dict | None = None
        self._batch_file_only_mode: bool = False
        self._batch_skip_mr_creation: bool = False
        self._batch_skip_puppeteer: bool = False
        self._batch_skip_test_suite: bool = False
        self._batch_skip_regression: bool = False
        self._changing_branch_agent: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Connecting to daemon... | ? for help", id="info-bar")
        with Horizontal(id="workspace"):
            with Container(id="agent-list"):
                yield OptionList(id="agents")
            with Container(id="terminal-area"):
                yield Static("No agent selected\n\nPress 'n' to add an agent", id="terminal-status")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the app - connect to daemon and load agents."""
        if not await self._connect_to_daemon():
            return
        await self._sync_agents_from_daemon()
        await self._initialize_agents()

    async def _connect_to_daemon(self) -> bool:
        """Connect to the daemon service.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            await self._daemon_client.connect()
            return True
        except DaemonNotRunningError:
            self.notify("Daemon not running! Start with: python -m agent.daemon", severity="error")
            self._update_info_bar()
            return False

    async def _initialize_agents(self) -> None:
        """Initialize agents from preload specs or start batch wizard."""
        if self._preload_specs:
            for spec_config in self._preload_specs:
                await self._add_agent_from_config(spec_config)
            self._preload_specs = []
            self._update_info_bar()
        elif not self.agents:
            # No agents - start the batch wizard
            self._in_batch_mode = True
            self._batch_specs = []
            self._batch_project_dir = None
            self._batch_spec = None
            self.push_screen(RepoSelectScreen())

    async def _sync_agents_from_daemon(self) -> None:
        """Sync agent list from daemon."""
        try:
            daemon_agents = await self._daemon_client.list_agents()
            restored_count = 0
            failed_count = 0

            for agent_info in daemon_agents:
                agent_id = agent_info.get("agent_id")
                if agent_id and agent_id not in self.agents:
                    # Update counter to avoid ID collisions
                    if agent_id.startswith("agent_"):
                        try:
                            num = int(agent_id.split("_")[1])
                            if num >= self._agent_counter:
                                self._agent_counter = num + 1
                        except (IndexError, ValueError):
                            pass
                    # Reconstruct session from daemon info
                    config_dict = agent_info.get("config", {})
                    try:
                        spec_config = SpecConfig.from_dict(config_dict)
                        session = AgentSession(agent_id, spec_config)
                        session.status = agent_info.get("status", STATUS_STOPPED)
                        session.log_file = Path(agent_info["log_file"]) if agent_info.get("log_file") else None
                        self.agents[agent_id] = session
                        restored_count += 1
                    except (KeyError, ValueError) as e:
                        self.log.warning(f"Failed to restore agent {agent_id}: {e}")
                        self.notify(f"Failed to restore agent: {e}", severity="warning")
                        failed_count += 1

            self._update_agent_list()
            if self.agents:
                # Select first agent
                first_id = list(self.agents.keys())[0]
                self.selected_agent = first_id
                self._show_terminal(first_id)
                if failed_count > 0:
                    self.notify(f"Restored {restored_count} agent(s), {failed_count} failed")
                else:
                    self.notify(f"Restored {restored_count} agent(s) from daemon")
            self._update_info_bar()
        except DaemonError as e:
            self.notify(f"Failed to sync with daemon: {e}", severity="error")

    def _get_selected_session(self, require_running: bool = False) -> AgentSession | None:
        """Get the currently selected agent session with validation.

        Args:
            require_running: If True, also checks that agent is running.

        Returns:
            AgentSession if valid selection exists, None otherwise with notification.
        """
        if not self.selected_agent or self.selected_agent not in self.agents:
            self.notify("No agent selected", severity="warning")
            return None

        session = self.agents[self.selected_agent]
        if require_running and session.status != STATUS_RUNNING:
            self.notify("Agent not running", severity="warning")
            return None

        return session

    def _update_info_bar(self) -> None:
        """Update the info bar with current context."""
        if self.selected_agent and self.selected_agent in self.agents:
            session = self.agents[self.selected_agent]
            branch = _get_current_branch(session.config.project_dir)
            spec_name = session.config.spec_file.stem
            # Truncate long spec names for display (max 25 chars, show 22 + ellipsis)
            if len(spec_name) > 25:
                spec_name = spec_name[:22] + "..."
            status = session.status.upper()

            model_short = self._abbreviate_model(session.config.model)

            auto_indicator = " AUTO" if session.auto_accept else " HITL"
            file_only_indicator = " FILE" if session.config.file_only_mode else " GL"
            no_mr_indicator = " NO-MR" if session.config.skip_mr_creation else " MR"

            hitl_indicator = ""
            checkpoint_type = get_pending_checkpoint_type(
                session.config.project_dir, session.spec_slug, session.config.spec_hash
            )
            if checkpoint_type:
                hitl_labels = {
                    "project_verification": "PROJ",
                    "spec_to_issues": "ISSUES",
                    "issue_enrichment": "ENRICH",
                    "regression_approval": "REGRESS",
                    "issue_selection": "SELECT",
                    "issue_closure": "CLOSE",
                    "mr_phase_transition": "MR-GATE",
                    "mr_review": "MR",
                }
                hitl_label = hitl_labels.get(checkpoint_type.value, "HITL")
                hitl_indicator = f" [HITL:{hitl_label}]"

            iters_indicator = "" if session.config.max_iterations is None else f" | max:{session.config.max_iterations}"

            text = (
                f"{spec_name} | {status}{auto_indicator}{file_only_indicator}{no_mr_indicator}{hitl_indicator} | "
                f"{branch} | {model_short}{iters_indicator} | ?"
            )

        elif len(self.agents) > 0:
            unique_models = {session.config.model for session in self.agents.values()}
            if len(unique_models) == 1:
                model_short = list(unique_models)[0].replace("claude-", "").replace("-20251101", "")
                text = f"Multi-Project Harness | {len(self.agents)} specs | {model_short} | ? for help"
            else:
                text = f"Multi-Project Harness | {len(self.agents)} specs | {len(unique_models)} models | ? for help"
        else:
            text = "Multi-Project Harness | ? for help"

        self.query_one("#info-bar", Static).update(text)

    def _abbreviate_model(self, model: str) -> str:
        """Convert model ID to short display name (max 10 chars).

        Examples:
            claude-opus-4-5-20251101 -> opus-4.5
            claude-sonnet-4-20251101 -> sonnet-4
            claude-haiku-3-5-20251101 -> haiku-3.5
        """
        short = model.replace("claude-", "")
        # Remove date suffixes
        for suffix in ["-20251101", "-20250929", "-20250219", "-20241022", "-20240620", "-20240229", "-20240307"]:
            short = short.replace(suffix, "")
        # Convert dashes to dots for version numbers
        # opus-4-5 -> opus-4.5, haiku-3-5 -> haiku-3.5
        short = re.sub(r"-(\d+)-(\d+)$", r"-\1.\2", short)
        short = re.sub(r"^(\w+)-(\d+\.\d+)$", r"\1-\2", short)
        # Shorten to max 10 chars
        if len(short) > 10:
            short = short[:10]
        return short

    def _format_agent_label(self, session: AgentSession) -> str:
        """Format agent session label showing only the spec name.

        All other details (status, branch, model, etc.) are shown in the status bar.

        Returns:
            Agent name string (truncated if needed).
        """
        name = session.name
        if len(name) > 22:
            name = name[:19] + "..."
        return name

    def _update_agent_list(self) -> None:
        """Refresh the agent list display."""
        opt_list = self.query_one("#agents", OptionList)
        opt_list.clear_options()

        for agent_id, session in self.agents.items():
            label = self._format_agent_label(session)
            opt_list.add_option(Option(label, id=agent_id))

    def _show_terminal(self, agent_id: str | None) -> None:
        """Display the terminal for the selected agent."""
        status = self.query_one("#terminal-status", Static)

        # Hide all terminals first
        for term in self.query(".agent-terminal"):
            term.display = False

        if agent_id is None or agent_id not in self.agents:
            status.display = True
            status.update("No agent selected\n\nPress 'n' to add an agent")
            return

        session = self.agents[agent_id]
        status.display = False

        term_id = f"term-{agent_id}"
        try:
            terminal = self.query_one(f"#{term_id}", LogTerminal)
            terminal.display = True
        except NoMatches:
            if session.log_file and session.status in (STATUS_RUNNING, STATUS_STOPPED):
                # Create terminal to tail log file
                terminal = LogTerminal(log_file=session.log_file, id=term_id, classes="agent-terminal")
                terminal_area = self.query_one("#terminal-area", Container)
                terminal_area.mount(terminal)
                session.terminal = terminal
                terminal.start()
            else:
                status.display = True
                status.update(f"Agent: {session.name}\n\nPress 's' to start")

    async def _add_agent_from_config(self, spec_config: SpecConfig) -> str:
        """Add a new agent session from a SpecConfig and return its ID."""
        self._agent_counter += 1
        agent_id = f"agent_{self._agent_counter}"

        session = AgentSession(agent_id, spec_config)
        self.agents[agent_id] = session

        # Register with daemon immediately for persistence
        try:
            config_dict = spec_config.to_dict()
            await self._daemon_client.register_agent(agent_id, config_dict)
        except DaemonError as e:
            self.notify(f"Warning: Failed to register with daemon: {e}", severity="warning")

        self._update_agent_list()

        # Select the new agent
        opt_list = self.query_one("#agents", OptionList)
        opt_list.highlighted = len(self.agents) - 1
        self.selected_agent = agent_id
        self._show_terminal(agent_id)
        self._update_info_bar()

        return agent_id

    async def _start_agent_via_daemon(self, agent_id: str) -> None:
        """Start an agent via the daemon."""
        if agent_id not in self.agents:
            return

        session = self.agents[agent_id]
        config = session.config

        try:
            # Use to_dict() to send complete config (including spec_slug, spec_hash, etc.)
            config_dict = config.to_dict()
            agent_info = await self._daemon_client.start_agent(agent_id, config_dict)

            session.status = agent_info.get("status", STATUS_RUNNING)
            session.log_file = Path(agent_info["log_file"]) if agent_info.get("log_file") else None

            # Create terminal to tail the log file
            await self._create_log_terminal(agent_id)

            self._update_agent_list()
            self._update_info_bar()
            self.notify(f"Started: {session.name}")

        except DaemonError as e:
            self.notify(f"Failed to start agent: {e}", severity="error")

    async def _create_log_terminal(self, agent_id: str) -> None:
        """Create a LogTerminal widget to tail the agent's log file."""
        if agent_id not in self.agents:
            return

        session = self.agents[agent_id]
        if not session.log_file:
            return

        term_id = f"term-{agent_id}"

        # Remove existing terminal if any (must await since remove() is async)
        try:
            old_term = self.query_one(f"#{term_id}", LogTerminal)
            old_term.stop()
            await old_term.remove()
        except NoMatches:
            pass

        # Create new terminal
        terminal = LogTerminal(log_file=session.log_file, id=term_id, classes="agent-terminal")
        terminal_area = self.query_one("#terminal-area", Container)
        terminal_area.mount(terminal)

        self.query_one("#terminal-status", Static).display = False
        terminal.start()
        session.terminal = terminal

    async def _stop_agent_via_daemon(self, agent_id: str) -> None:
        """Stop an agent via the daemon."""
        if agent_id not in self.agents:
            return

        session = self.agents[agent_id]

        try:
            agent_info = await self._daemon_client.stop_agent(agent_id)
            session.status = agent_info.get("status", STATUS_STOPPED)
            self._update_agent_list()
            self._update_info_bar()
            self.notify("Stopped agent")
        except DaemonError as e:
            self.notify(f"Failed to stop agent: {e}", severity="error")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def on_repo_selected(self, event: RepoSelected) -> None:
        """Handle working directory selection in batch wizard."""
        if self._in_batch_mode:
            self._batch_project_dir = event.path
            self.push_screen(SpecSelectScreen(event.path))

    def on_spec_selected(self, event: SpecSelected) -> None:
        """Handle spec selection - show branch selector next."""
        if self._in_batch_mode and self._batch_project_dir:
            self._batch_spec = event.path
            self.push_screen(BranchSelectScreen(self._batch_project_dir, event.path, self._batch_project_dir))

    def on_agent_configured(self, event: AgentConfigured) -> None:
        """Handle agent configuration from branch selection."""
        if hasattr(self, "_changing_branch_agent") and self._changing_branch_agent:
            agent_id = self._changing_branch_agent
            if agent_id in self.agents:
                session = self.agents[agent_id]
                old_branch = session.config.target_branch
                session.config.target_branch = event.target_branch
                self._update_workspace_info(session, event.target_branch)
                self._update_agent_list()
                self._update_info_bar()
                self.notify(f"Branch changed: {old_branch} -> {event.target_branch}")
            self._changing_branch_agent = None
            return

        if self._in_batch_mode and self._batch_spec and self._batch_project_dir:
            self._batch_spec_base = {
                "spec_file": self._batch_spec,
                "project_dir": self._batch_project_dir,
                "target_branch": event.target_branch,
            }
            self._batch_project_dir = None
            self._batch_spec = None
            # Show agent options screen next
            self.push_screen(AgentOptionsScreen())

    def on_file_only_mode_selected(self, event: FileOnlyModeSelected) -> None:
        """Handle file-only mode and skip flag selection."""
        if self._in_batch_mode and self._batch_spec_base:
            self._batch_file_only_mode = event.file_only_mode
            self._batch_skip_mr_creation = event.skip_mr_creation
            self._batch_skip_puppeteer = event.skip_puppeteer
            self._batch_skip_test_suite = event.skip_test_suite
            self._batch_skip_regression = event.skip_regression
            self.push_screen(AdvancedOptionsScreen())

    def on_advanced_options_configured(self, event: AdvancedOptionsConfigured) -> None:
        """Handle advanced options configuration."""
        if self._in_batch_mode and self._batch_spec_base:
            try:
                spec_config = SpecConfig(
                    spec_file=self._batch_spec_base["spec_file"],
                    project_dir=self._batch_spec_base["project_dir"],
                    target_branch=self._batch_spec_base["target_branch"],
                    spec_slug=spec_filename_to_slug(self._batch_spec_base["spec_file"]),
                    spec_hash=generate_spec_hash(self._batch_spec_base["spec_file"]),
                    name=self._batch_spec_base["spec_file"].stem,
                    max_iterations=event.max_iterations,
                    file_only_mode=self._batch_file_only_mode,
                    skip_mr_creation=self._batch_skip_mr_creation,
                    skip_puppeteer=self._batch_skip_puppeteer,
                    skip_test_suite=self._batch_skip_test_suite,
                    skip_regression_testing=self._batch_skip_regression,
                )
            except ValueError as e:
                self.notify(str(e), severity="error")
                return

            self._batch_specs.append(spec_config)
            self._batch_spec_base = None
            self._batch_file_only_mode = False  # Reset for next spec
            self._batch_skip_mr_creation = False  # Reset for next spec
            self._batch_skip_puppeteer = False  # Reset for next spec
            self._batch_skip_test_suite = False  # Reset for next spec
            self._batch_skip_regression = False  # Reset for next spec
            self.push_screen(AddAnotherSpecDialog(len(self._batch_specs)))

    def on_add_another_spec_response(self, event: AddAnotherSpecResponse) -> None:
        """Handle response from 'add another spec' dialog."""
        if event.add_another:
            self.push_screen(RepoSelectScreen())
        else:
            if self._batch_specs:
                # Use run_worker to handle async in sync context
                self.run_worker(self._create_batch_agents())
            else:
                self.notify("No specs collected", severity="warning")

    async def _create_batch_agents(self) -> None:
        """Create all agents from batch collection."""
        for spec_config in self._batch_specs:
            await self._add_agent_from_config(spec_config)

        count = len(self._batch_specs)
        self.notify(f"Created {count} agent(s)")

        self._batch_specs = []
        self._in_batch_mode = False
        self._batch_project_dir = None
        self._batch_spec = None

    def _update_workspace_info(self, session: AgentSession, new_target_branch: str) -> None:
        """Update the workspace_info.json when target branch changes."""
        workspace_info_path = session.agent_dir / ".workspace_info.json"
        if workspace_info_path.exists():
            try:
                info = json.loads(workspace_info_path.read_text(encoding="utf-8"))
                info["target_branch"] = new_target_branch
                workspace_info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
            except (OSError, json.JSONDecodeError) as e:
                self.log.error(f"Failed to update workspace info: {e}")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle agent selection."""
        if event.option.id:
            self.selected_agent = event.option.id
            self._show_terminal(self.selected_agent)
            self._update_info_bar()

    # =========================================================================
    # Actions
    # =========================================================================

    async def action_quit(self) -> None:
        """Quit the TUI. Agents keep running in daemon."""
        # Stop all log terminals (just stop tailing, agents keep running)
        for agent_id in self.agents:
            term_id = f"term-{agent_id}"
            try:
                terminal = self.query_one(f"#{term_id}", LogTerminal)
                terminal.stop()
            except NoMatches:
                pass

        self.exit()

    def action_show_help(self) -> None:
        """Show keyboard shortcuts."""
        help_text = """Keyboard Shortcuts:

  n  New agent      s  Start agent
  k  Stop agent     d  Delete agent
  b  Change branch  a  Toggle auto-accept
  r  Review checkpoint (detailed view)
  y  Approve HITL   x  Reject HITL
  1  Approve HITL   0  Reject HITL
  ?  Show help      q  Quit

Daemon Architecture:
  - Agents run in background daemon
  - Quit TUI, agents keep running
  - Reconnect to see agent output"""
        self.notify(help_text, title="Help", timeout=15)

    def action_new_agent(self) -> None:
        """Start the multi-spec wizard."""
        self._in_batch_mode = True
        self._batch_specs = []
        self._batch_project_dir = None
        self._batch_spec = None
        self.push_screen(RepoSelectScreen())

    def action_start_agent(self) -> None:
        """Start the selected agent."""
        session = self._get_selected_session()
        if not session:
            return

        if session.status == STATUS_RUNNING:
            self.notify("Agent already running", severity="warning")
            return

        # Start via daemon (async)
        self.run_worker(self._start_agent_via_daemon(session.agent_id))

    def action_stop_agent(self) -> None:
        """Stop the selected agent."""
        session = self._get_selected_session()
        if not session:
            return

        self.run_worker(self._stop_agent_via_daemon(session.agent_id))

    def action_delete_agent(self) -> None:
        """Delete the selected agent."""
        session = self._get_selected_session()
        if not session:
            return

        agent_id = session.agent_id

        # Stop terminal
        term_id = f"term-{agent_id}"
        try:
            terminal = self.query_one(f"#{term_id}", LogTerminal)
            terminal.stop()
            terminal.remove()
        except NoMatches:
            pass

        # Remove from daemon
        async def remove_from_daemon() -> None:
            with contextlib.suppress(DaemonError):
                await self._daemon_client.remove_agent(agent_id)

        self.run_worker(remove_from_daemon())

        del self.agents[agent_id]
        self.selected_agent = None
        self._update_agent_list()
        self._show_terminal(None)
        self._update_info_bar()
        self.notify("Removed agent")

    def action_change_branch(self) -> None:
        """Change the target branch of the selected agent."""
        session = self._get_selected_session()
        if not session:
            return

        if session.status == STATUS_RUNNING:
            self.notify("Stop the agent before changing branch", severity="warning")
            return

        self._changing_branch_agent = self.selected_agent
        self.push_screen(
            BranchSelectScreen(session.config.project_dir, session.config.spec_file, session.config.project_dir)
        )

    def action_toggle_auto_accept(self) -> None:
        """Toggle auto-accept mode for the selected agent."""
        session = self._get_selected_session()
        if not session:
            return

        session.auto_accept = not session.auto_accept

        if session.agent_dir:
            try:
                _save_auto_accept_preference(
                    session.config.project_dir, session.spec_slug, session.config.spec_hash, session.auto_accept
                )
                mode_text = "ENABLED" if session.auto_accept else "DISABLED"
                self.notify(f"Auto-Accept: {mode_text}")
                self._update_info_bar()
            except (OSError, json.JSONDecodeError) as e:
                self.notify(f"Failed to save auto-accept preference: {e}", severity="error")

    def action_hitl_approve(self) -> None:
        """Approve HITL checkpoint."""
        session = self._get_selected_session(require_running=True)
        if not session:
            return

        if not is_checkpoint_pending(session.config.project_dir, session.spec_slug, session.config.spec_hash):
            self.notify("No pending checkpoint", severity="warning")
            return

        result = approve_checkpoint(session.config.project_dir, session.spec_slug, session.config.spec_hash)
        if result:
            self.notify("Checkpoint approved!")
            self._update_info_bar()
            self._update_agent_list()
        else:
            self.notify("Failed to approve checkpoint", severity="error")

    def action_copy_logs(self) -> None:
        """Copy the current agent's log file to clipboard."""
        session = self._get_selected_session()
        if not session:
            return

        if not session.log_file or not session.log_file.exists():
            self.notify("No log file available", severity="warning")
            return

        try:
            content = session.log_file.read_text(encoding="utf-8", errors="replace")
            lines = content.count("\n")

            # Use Textual's built-in clipboard support
            self.copy_to_clipboard(content)
            self.notify(f"Copied {lines} lines to clipboard")
        except (OSError, UnicodeDecodeError) as e:
            self.notify(f"Failed to copy: {e}", severity="error")

    def action_toggle_fullscreen(self) -> None:
        """Toggle sidebar visibility to maximize log view."""
        agent_list = self.query_one("#agent-list")
        agent_list.display = not agent_list.display

    def action_open_logs(self) -> None:
        """Open full-screen log viewer with selection and copy support."""
        session = self._get_selected_session()
        if not session:
            return

        if not session.log_file or not session.log_file.exists():
            self.notify("No log file available", severity="warning")
            return

        self.push_screen(LogViewerScreen(session.log_file, session.name))

    def action_hitl_reject(self) -> None:
        """Reject HITL checkpoint."""
        session = self._get_selected_session(require_running=True)
        if not session:
            return

        if not is_checkpoint_pending(session.config.project_dir, session.spec_slug, session.config.spec_hash):
            self.notify("No pending checkpoint", severity="warning")
            return

        result = reject_checkpoint(
            session.config.project_dir, session.spec_slug, session.config.spec_hash, "Rejected via TUI"
        )
        if result:
            self.notify("Checkpoint rejected!")
            self._update_info_bar()
            self._update_agent_list()
        else:
            self.notify("Failed to reject checkpoint", severity="error")

    def action_review_checkpoint(self) -> None:
        """Open the checkpoint review screen."""
        session = self._get_selected_session(require_running=True)
        if not session:
            return

        if not is_checkpoint_pending(session.config.project_dir, session.spec_slug, session.config.spec_hash):
            self.notify("No pending checkpoint to review", severity="warning")
            return

        checkpoint = load_pending_checkpoint(session.config.project_dir, session.spec_slug, session.config.spec_hash)
        if not checkpoint:
            self.notify("Failed to load checkpoint", severity="error")
            return

        self.push_screen(CheckpointReviewScreen(checkpoint.to_dict()))

    def on_checkpoint_resolved(self, event: CheckpointResolved) -> None:
        """Handle checkpoint resolution from the review screen."""
        session = self._get_selected_session()
        if not session:
            return

        status_map = {
            "approved": CheckpointStatus.APPROVED,
            "rejected": CheckpointStatus.REJECTED,
            "modified": CheckpointStatus.MODIFIED,
        }
        status = status_map.get(event.status, CheckpointStatus.APPROVED)

        result = resolve_checkpoint(
            session.config.project_dir,
            status=status,
            spec_slug=session.spec_slug,
            spec_hash=session.config.spec_hash,
            decision=event.decision,
            notes=event.notes,
            modifications=event.modifications,
        )

        if result:
            checkpoint_type = result.checkpoint_type.value.replace("_", " ").title()
            if event.decision:
                self.notify(f"{checkpoint_type}: {event.status} ({event.decision})")
            else:
                self.notify(f"{checkpoint_type}: {event.status}")
            self._update_info_bar()
            self._update_agent_list()
        else:
            self.notify("Failed to resolve checkpoint", severity="error")


# ============================================================================
# Private Helper Functions
# ============================================================================


def _load_auto_accept_preference(project_dir: Path, spec_slug: str, spec_hash: str) -> bool:
    """Load auto-accept preference from .workspace_info.json."""
    agent_dir = project_dir / ".claude-agent" / f"{spec_slug}-{spec_hash}"
    workspace_info_path = agent_dir / ".workspace_info.json"
    if workspace_info_path.exists():
        try:
            with open(workspace_info_path, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("auto_accept", False)
        except (OSError, json.JSONDecodeError):
            return False
    return False


def _save_auto_accept_preference(project_dir: Path, spec_slug: str, spec_hash: str, auto_accept: bool) -> None:
    """Save auto-accept preference to .workspace_info.json."""
    agent_dir = project_dir / ".claude-agent" / f"{spec_slug}-{spec_hash}"
    workspace_info_path = agent_dir / ".workspace_info.json"
    if workspace_info_path.exists():
        try:
            with open(workspace_info_path, encoding="utf-8") as f:
                data = json.load(f)
            data["auto_accept"] = auto_accept
            with open(workspace_info_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except (OSError, json.JSONDecodeError):
            agent_dir.mkdir(parents=True, exist_ok=True)
            with open(workspace_info_path, "w", encoding="utf-8") as f:
                json.dump({"auto_accept": auto_accept}, f, indent=2)
    else:
        # Create file if it doesn't exist
        agent_dir.mkdir(parents=True, exist_ok=True)
        with open(workspace_info_path, "w", encoding="utf-8") as f:
            json.dump({"auto_accept": auto_accept}, f, indent=2)


def _get_current_branch(repo_path: Path) -> str:
    """Get the current git branch for the given repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return ""
