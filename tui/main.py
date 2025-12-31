#!/usr/bin/env python3
"""
TUI Entry Point for Coding Harness
===================================

A Text User Interface (TUI) for the autonomous coding agent.

Example Usage:
    # Run the TUI (interactive mode - will prompt for specs)
    ./start.sh

    # Pre-load specs using JSON array
    ./start.sh --specs '[{
        "spec_file":"/abs/path/spec.txt",
        "project_dir":"/abs/path/project",
        "target_branch":"main"
    }]'

Note: Git operations use GitLab MCP with GITLAB_PERSONAL_ACCESS_TOKEN.
      Commits are attributed to the token owner's GitLab identity.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from dotenv import load_dotenv

from common import SpecConfig, validate_required_env_vars

# Load .env before importing modules that read env vars at import time
load_dotenv(Path(__file__).parent.parent / ".env")

# pylint: disable=wrong-import-position
from .app import CodingHarnessApp  # noqa: E402 - Must load .env first


def main() -> None:
    """Main entry point."""
    args = _parse_args()

    success, error = validate_required_env_vars()
    if not success:
        _exit_with_error(error)

    # Parse spec configurations
    spec_configs = _parse_spec_configs(args)

    app = CodingHarnessApp(
        spec_configs=spec_configs,
        # Note: model and max_iterations are now per-spec in SpecConfig
        # Auto-accept is managed per-agent via 'a' key toggle (saved to workspace file)
    )
    app.run()


# ============================================================================
# Private Helper Functions
# ============================================================================


def _exit_with_error(*messages: str) -> NoReturn:
    """Print error messages and exit with code 1.

    Args:
        *messages: One or more error message strings to print.

    Returns:
        Never returns - always exits the program.
    """
    for msg in messages:
        print(msg)
    sys.exit(1)


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="TUI for Autonomous Coding Agent - Milestone-based MR creation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive TUI mode (will prompt for all required fields):
  ./start.sh

  # Pre-load specs via JSON:
  ./start.sh --specs '[
    {
      "spec_file": "/path/to/spec.txt",
      "project_dir": "/path/to/project",
      "target_branch": "main"
    }
  ]'

  # Multiple specs:
  ./start.sh --specs '[
    {
      "spec_file": "/home/user/specs/feature1.txt",
      "project_dir": "/home/user/project",
      "target_branch": "main"
    },
    {
      "spec_file": "/home/user/specs/feature2.txt",
      "project_dir": "/home/user/project",
      "target_branch": "develop"
    }
  ]'

Required Spec JSON Fields:
  spec_file        Path to the specification file (absolute path)
  project_dir      Root project directory (absolute path)
  target_branch    Git branch to target for changes

Optional Spec JSON Fields:
  max_iterations   Maximum agent iterations (default: unlimited)

Note: Git operations use GitLab MCP with GITLAB_PERSONAL_ACCESS_TOKEN.
      Commits are attributed to the token owner's GitLab identity.

Environment Variables (Required):
  CLAUDE_CODE_OAUTH_TOKEN          Claude Code OAuth token
  GITLAB_PERSONAL_ACCESS_TOKEN     GitLab personal access token (for MCP git operations)

Environment Variables (Optional):
  ANTHROPIC_API_KEY                Alternative to CLAUDE_CODE_OAUTH_TOKEN
  GITLAB_API_URL                   For self-hosted GitLab
        """,
    )

    parser.add_argument(
        "--specs",
        type=str,
        default=None,
        help=(
            'JSON array of spec configs: [{"spec_file": "spec1.txt", "project_dir": "/path", "target_branch": "main"}]'
        ),
    )

    return parser.parse_args()


def _validate_absolute_paths(specs: list[SpecConfig]) -> tuple[bool, str]:
    """Validate that all paths in specs are absolute.

    Args:
        specs: List of SpecConfig objects to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    for i, spec in enumerate(specs):
        if not spec.spec_file.is_absolute():
            return (False, f"Spec {i + 1}: spec_file must be an absolute path, got: {spec.spec_file}")

        if not spec.project_dir.is_absolute():
            return (False, f"Spec {i + 1}: project_dir must be an absolute path, got: {spec.project_dir}")

    return (True, "")


def _parse_and_validate_json(specs_json: str) -> list[dict]:
    """Parse JSON specs string and validate basic structure.

    Args:
        specs_json: JSON string containing spec configurations.

    Returns:
        List of spec dictionaries.

    Raises:
        SystemExit: If JSON is invalid or not a non-empty list.
    """
    try:
        specs_data = json.loads(specs_json)
    except json.JSONDecodeError as e:
        _exit_with_error(f"Error: Invalid JSON in --specs argument: {e}")

    if not isinstance(specs_data, list):
        _exit_with_error(
            "Error: --specs must be a JSON array of spec configurations",
            'Example: --specs \'[{"spec_file":"/path/to/spec.txt",'
            '"project_dir":"/path/to/project","target_branch":"main"}]\'',
        )

    if not specs_data:
        _exit_with_error("Error: --specs array cannot be empty")

    return specs_data  # type: ignore[return-value]


def _validate_spec_objects(specs_data: list[dict]) -> None:
    """Validate that each spec object has required fields.

    Args:
        specs_data: List of spec dictionaries to validate.

    Raises:
        SystemExit: If any spec is invalid.
    """
    required_fields = ["spec_file", "project_dir", "target_branch"]

    for i, spec in enumerate(specs_data):
        if not isinstance(spec, dict):
            _exit_with_error(f"Error: Spec {i + 1} must be a JSON object, got {type(spec).__name__}")

        missing_fields = [f for f in required_fields if f not in spec]
        if missing_fields:
            _exit_with_error(
                f"Error: Spec {i + 1} is missing required fields: {', '.join(missing_fields)}",
                "\nRequired fields for each spec:",
                "  spec_file        Path to the specification file (absolute path)",
                "  project_dir      Root project directory (absolute path)",
                "  target_branch    Git branch to target for changes",
            )


def _parse_spec_configs(args: argparse.Namespace) -> list[SpecConfig]:
    """Parse spec configurations from arguments.

    Only supports --specs JSON format.

    Args:
        args: Parsed command line arguments

    Returns:
        List of SpecConfig objects, or empty list if no specs provided.
    """
    if args.specs:
        specs_data = _parse_and_validate_json(args.specs)
        _validate_spec_objects(specs_data)

        try:
            specs = [SpecConfig.from_dict(s) for s in specs_data]
        except (KeyError, ValueError, TypeError) as e:
            _exit_with_error(f"Error: Failed to create spec configuration: {e}")

        # Validate that all paths are absolute
        is_valid, error_msg = _validate_absolute_paths(specs)
        if not is_valid:
            _exit_with_error(
                f"Error: {error_msg}",
                "\nAll paths in --specs must be absolute paths.",
                "Example: /home/user/specs/myspec.txt (not ./specs/myspec.txt)",
            )

        return specs

    # No specs provided - TUI will prompt interactively
    return []


if __name__ == "__main__":
    main()
