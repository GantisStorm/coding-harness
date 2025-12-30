#!/usr/bin/env python3
"""
Autonomous Coding Agent CLI Runner
===================================

CLI runner for autonomous coding agent with milestone-based MR creation.
This script implements a three-phase workflow:
  Phase 1: Initializer - Create milestone and issues from app_spec.txt
  Phase 2: Coding - Work on issues in the milestone
  Phase 3: MR Creation - Create merge request when all issues are closed

Example Usage:
    cd /path/to/my-gitlab-project
    vim app_spec.txt  # Create your specification
    python -m agent.cli --spec-file app_spec.txt
    python -m agent.cli --spec-file app_spec.txt --target-branch develop --max-iterations 10

Note: This CLI runner requires manual approval for all HITL checkpoints.
      For auto-accept mode, use the TUI: ./start.sh
"""

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

from common import validate_required_env_vars

from .core import run_autonomous_agent
from .prompts import initialize_agent_workspace


def main() -> None:
    """Main entry point."""
    args = _parse_args()

    # Validate required environment variables
    success, error = validate_required_env_vars()
    if not success:
        print(error, file=sys.stderr)
        sys.exit(1)

    # Use specified project directory or current working directory
    project_dir = Path(args.project_dir).resolve() if args.project_dir else Path.cwd()

    # Verify current directory is a git repository (check before creating files)
    git_dir = project_dir / ".git"
    if not git_dir.exists():
        print("Error: Current directory is not a git repository", file=sys.stderr)
        print(f"\nCurrent directory: {project_dir}", file=sys.stderr)
        print("\nPlease run this script from the root of your GitLab project.", file=sys.stderr)
        print("If this is a new project, initialize git first:", file=sys.stderr)
        print("  git init", file=sys.stderr)
        print("  git remote add origin <your-gitlab-project-url>", file=sys.stderr)
        sys.exit(1)

    # Verify spec file exists
    spec_file = Path(args.spec_file).resolve()
    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}", file=sys.stderr)
        sys.exit(1)
    if not spec_file.is_file():
        print(f"Error: Not a file: {spec_file}", file=sys.stderr)
        sys.exit(1)

    # Initialize agent workspace before running
    try:
        agent_dir, spec_slug, spec_hash = initialize_agent_workspace(
            project_dir, spec_file, args.target_branch, file_only_mode=args.file_only, skip_mr_creation=args.skip_mr
        )

        # Validate return values
        if not agent_dir or not spec_slug or not spec_hash:
            print("Error: Failed to initialize agent workspace - invalid return values", file=sys.stderr)
            sys.exit(1)

        print(f"Spec slug: {spec_slug}")
        print(f"Spec hash: {spec_hash}")
        print(f"Agent workspace: {agent_dir}")
    except (ValueError, OSError, shutil.Error) as e:
        print(f"Error: Failed to initialize agent workspace: {e}", file=sys.stderr)
        sys.exit(1)

    # Run the agent
    # When run via TUI daemon, CODING_HARNESS_AUTO_ACCEPT env var controls auto-accept
    # When run directly from CLI, defaults to manual approval (False)
    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101"),
                max_iterations=args.max_iterations,
                target_branch=args.target_branch,
                spec_slug=spec_slug,
                spec_hash=spec_hash,
                auto_accept=os.getenv("CODING_HARNESS_AUTO_ACCEPT", "0") == "1",
                file_only_mode=args.file_only,
                skip_mr_creation=args.skip_mr,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        print("To resume, run the same command again from the same directory", file=sys.stderr)
    except Exception as e:  # Re-raise after logging for debugging
        print(f"\nFatal error: {e}", file=sys.stderr)
        raise


# ============================================================================
# Private Helper Functions
# ============================================================================


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent CLI - Milestone-based MR creation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with spec file:
  python -m agent.cli --spec-file /path/to/spec.txt

  # Run with options:
  python -m agent.cli --spec-file spec.txt --target-branch develop --max-iterations 10

Note: Git operations use GitLab MCP with GITLAB_PERSONAL_ACCESS_TOKEN.
      Commits are attributed to the token owner's GitLab identity.
      No local git user configuration is required.

Environment Variables (Required):
  CLAUDE_CODE_OAUTH_TOKEN          Claude Code OAuth token
  GITLAB_PERSONAL_ACCESS_TOKEN     GitLab personal access token (for MCP git operations)
""",
    )

    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project directory (default: current working directory)",
    )

    parser.add_argument(
        "--target-branch",
        type=str,
        default="main",
        help="Target branch for merge request (default: main)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--spec-file",
        type=str,
        required=True,
        help="Path to the spec file (required)",
    )

    parser.add_argument(
        "--file-only",
        action="store_true",
        help="Use local file tracking instead of GitLab for milestones/issues",
    )

    parser.add_argument(
        "--skip-mr",
        action="store_true",
        help="Skip MR creation after coding completes (keep changes on branch)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
