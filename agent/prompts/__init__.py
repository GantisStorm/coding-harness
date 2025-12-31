"""
Prompt Loading & Configuration Utilities
=========================================

Functions for loading prompt templates and multi-spec configuration support.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from common.utils import generate_spec_hash, spec_filename_to_slug

__all__ = [
    "get_initializer_prompt",
    "get_coding_prompt",
    "get_mr_creation_prompt",
    "initialize_agent_workspace",
    "TEMPLATES_DIR",
]

TEMPLATES_DIR = Path(__file__).parent / "templates"

# File-only mode prompt template names
FILE_ONLY_INITIALIZER_PROMPT = "initializer_prompt_file_only"
FILE_ONLY_CODING_PROMPT = "coding_prompt_file_only"
FILE_ONLY_MR_CREATION_PROMPT = "mr_creation_prompt_file_only"


def _process_conditional_blocks(
    prompt: str, skip_puppeteer: bool, skip_test_suite: bool, skip_regression_testing: bool
) -> str:
    """Process conditional blocks in prompt templates.

    Removes content between {{#UNLESS_SKIP_*}} and {{/UNLESS_SKIP_*}} markers
    when the corresponding skip flag is True.

    Args:
        prompt: The prompt template with conditional markers
        skip_puppeteer: If True, remove UNLESS_SKIP_PUPPETEER blocks
        skip_test_suite: If True, remove UNLESS_SKIP_TEST_SUITE blocks
        skip_regression_testing: If True, remove UNLESS_SKIP_REGRESSION blocks

    Returns:
        Processed prompt with conditional blocks resolved
    """
    # Map flags to their marker names
    conditions = [
        (skip_puppeteer, "SKIP_PUPPETEER"),
        (skip_test_suite, "SKIP_TEST_SUITE"),
        (skip_regression_testing, "SKIP_REGRESSION"),
    ]

    for skip_flag, marker_name in conditions:
        pattern = rf"\{{\{{#UNLESS_{marker_name}\}}\}}(.*?)\{{\{{/UNLESS_{marker_name}\}}\}}"
        if skip_flag:
            # Remove the entire block (including content)
            prompt = re.sub(pattern, "", prompt, flags=re.DOTALL)
        else:
            # Keep content, remove only the markers
            prompt = re.sub(pattern, r"\1", prompt, flags=re.DOTALL)

    return prompt


def _validate_non_empty_string(value: str, name: str) -> None:
    """Validate that a string parameter is non-empty.

    Args:
        value: The string value to validate
        name: Parameter name for error messages

    Raises:
        ValueError: If value is empty or whitespace-only
    """
    if not value or not value.strip():
        raise ValueError(f"{name} cannot be empty")


def get_initializer_prompt(
    target_branch: str,
    spec_slug: str,
    spec_hash: str,
    file_only_mode: bool = False,
) -> str:
    """Load the initializer prompt with variables substituted.

    Template substitution approach:
    - Uses simple string replacement for {{TARGET_BRANCH}} and {{SPEC_SLUG}} markers
    - These markers should NOT appear in code examples within the prompt files
    - Limitation: String replacement doesn't distinguish between template markers
      and literal text in examples, so avoid using these patterns in examples

    Args:
        target_branch: The branch to target for merge requests
        spec_slug: The spec slug for the agent state directory
        spec_hash: The spec hash for the agent state directory
        file_only_mode: If True, use local file tracking instead of GitLab

    Raises:
        ValueError: If any parameter is empty or invalid
    """
    _validate_non_empty_string(target_branch, "target_branch")
    _validate_non_empty_string(spec_slug, "spec_slug")
    _validate_non_empty_string(spec_hash, "spec_hash")

    prompt_name = FILE_ONLY_INITIALIZER_PROMPT if file_only_mode else "initializer_prompt"
    prompt = _load_prompt(prompt_name)
    prompt = prompt.replace("{{TARGET_BRANCH}}", target_branch)
    prompt = prompt.replace("{{SPEC_SLUG}}", f"{spec_slug}-{spec_hash}")
    return prompt


def get_coding_prompt(
    spec_slug: str,
    spec_hash: str,
    file_only_mode: bool = False,
    skip_puppeteer: bool = False,
    skip_test_suite: bool = False,
    skip_regression_testing: bool = False,
) -> str:
    """Load the coding agent prompt.

    Template substitution approach:
    - Uses simple string replacement for {{SPEC_SLUG}} markers
    - These markers should NOT appear in code examples within the prompt files
    - See get_initializer_prompt() for details on substitution limitations

    Args:
        spec_slug: The spec slug for finding state files
        spec_hash: The spec hash for finding state files
        file_only_mode: If True, use local file tracking instead of GitLab
        skip_puppeteer: If True, remove UNLESS_SKIP_PUPPETEER blocks from prompt
        skip_test_suite: If True, remove UNLESS_SKIP_TEST_SUITE blocks from prompt
        skip_regression_testing: If True, remove UNLESS_SKIP_REGRESSION blocks from prompt

    Raises:
        ValueError: If any parameter is empty or invalid
    """
    _validate_non_empty_string(spec_slug, "spec_slug")
    _validate_non_empty_string(spec_hash, "spec_hash")

    prompt_name = FILE_ONLY_CODING_PROMPT if file_only_mode else "coding_prompt"
    prompt = _load_prompt(prompt_name)
    prompt = prompt.replace("{{SPEC_SLUG}}", f"{spec_slug}-{spec_hash}")
    prompt = _process_conditional_blocks(prompt, skip_puppeteer, skip_test_suite, skip_regression_testing)
    return prompt


def get_mr_creation_prompt(
    spec_slug: str,
    spec_hash: str,
    target_branch: str = "main",
    file_only_mode: bool = False,
    skip_puppeteer: bool = False,
    skip_test_suite: bool = False,
    skip_regression_testing: bool = False,
) -> str:
    """Load the MR creation prompt.

    Template substitution approach:
    - Uses simple string replacement for {{SPEC_SLUG}} and {{TARGET_BRANCH}} markers
    - These markers should NOT appear in code examples within the prompt files
    - See get_initializer_prompt() for details on substitution limitations

    Args:
        spec_slug: The spec slug for finding state files
        spec_hash: The spec hash for finding state files
        target_branch: The target branch for the merge request
        file_only_mode: If True, use local file tracking instead of GitLab
        skip_puppeteer: If True, remove UNLESS_SKIP_PUPPETEER blocks from prompt
        skip_test_suite: If True, remove UNLESS_SKIP_TEST_SUITE blocks from prompt
        skip_regression_testing: If True, remove UNLESS_SKIP_REGRESSION blocks from prompt

    Raises:
        ValueError: If any parameter is empty or invalid
    """
    _validate_non_empty_string(spec_slug, "spec_slug")
    _validate_non_empty_string(spec_hash, "spec_hash")
    _validate_non_empty_string(target_branch, "target_branch")

    prompt_name = FILE_ONLY_MR_CREATION_PROMPT if file_only_mode else "mr_creation_prompt"
    prompt = _load_prompt(prompt_name)
    prompt = prompt.replace("{{SPEC_SLUG}}", f"{spec_slug}-{spec_hash}")
    prompt = prompt.replace("{{TARGET_BRANCH}}", target_branch)
    prompt = _process_conditional_blocks(prompt, skip_puppeteer, skip_test_suite, skip_regression_testing)
    return prompt


def initialize_agent_workspace(
    project_dir: Path,
    spec_source: Path,
    target_branch: str,
    file_only_mode: bool = False,
    skip_mr_creation: bool = False,
    skip_puppeteer: bool = False,
    skip_test_suite: bool = False,
    skip_regression_testing: bool = False,
    spec_hash: str | None = None,
    spec_slug: str | None = None,
) -> tuple[Path, str, str]:
    """Initialize the agent workspace before Claude Code starts.

    Creates the isolated directory structure and copies the spec file.
    This is called BEFORE the agent runs so Claude doesn't have to create directories.

    Args:
        project_dir: The project root directory
        spec_source: Path to the source spec file
        target_branch: Target branch for merge request
        file_only_mode: If True, use local file tracking instead of GitLab
        skip_mr_creation: If True, skip MR creation after coding completes

    Returns:
        Tuple of (agent_dir, spec_slug, spec_hash) where:
        - agent_dir: Path to .claude-agent/<slug>-<hash>
        - spec_slug: Unique spec identifier (without hash)
        - spec_hash: 8-character base62 hash (content + random)

    Creates:
        - .claude-agent/<slug>-<hash>/ directory
        - .claude-agent/<slug>-<hash>/app_spec.txt (copied from spec_source)
        - .claude-agent/<slug>-<hash>/.workspace_info.json (minimal metadata)
        - .claude-agent/<slug>-<hash>/.hitl_checkpoint_log.json (checkpoint history)
        - .claude-agent/<slug>-<hash>/.file_milestone.json (file-only mode) OR
          .claude-agent/<slug>-<hash>/.gitlab_milestone.json (GitLab mode)
        - .claude-agent/<slug>-<hash>/logs/ directory
    """
    # Use provided values or generate from spec filename
    if spec_slug is None:
        spec_slug = spec_filename_to_slug(spec_source)
    if spec_hash is None:
        spec_hash = generate_spec_hash(spec_source)

    # Create isolated directory structure
    agent_dir = project_dir / ".claude-agent" / f"{spec_slug}-{spec_hash}"
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Copy spec file
    spec_dest = agent_dir / "app_spec.txt"
    shutil.copy(spec_source, spec_dest)

    # Create initial workspace info file (helps agent understand context)
    workspace_info = agent_dir / ".workspace_info.json"

    info = {
        "spec_slug": spec_slug,
        "spec_hash": spec_hash,
        "target_branch": target_branch,
        "feature_branch": f"feature/{spec_slug}-{spec_hash}",
        "spec_file": "app_spec.txt",
        "initialized": True,
        "auto_accept": False,
        "file_only_mode": file_only_mode,
        "skip_mr_creation": skip_mr_creation,
        "skip_puppeteer": skip_puppeteer,
        "skip_test_suite": skip_test_suite,
        "skip_regression_testing": skip_regression_testing,
    }
    workspace_info.write_text(json.dumps(info, indent=2), encoding="utf-8")

    # Create template files for agent state (LLM will append to these)
    checkpoint_log = agent_dir / ".hitl_checkpoint_log.json"
    if not checkpoint_log.exists():
        checkpoint_log.write_text('{"global": []}', encoding="utf-8")

    # Create milestone file based on mode
    milestone_filename = ".file_milestone.json" if file_only_mode else ".gitlab_milestone.json"
    milestone_state = agent_dir / milestone_filename
    if not milestone_state.exists():
        milestone_state.write_text('{"initialized": false}', encoding="utf-8")

    # Create logs directory for agent output logs
    logs_dir = agent_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    return agent_dir, spec_slug, spec_hash


# ============================================================================
# Private Helper Functions
# ============================================================================


def _load_prompt(name: str) -> str:
    """Load a prompt template from the templates directory."""
    prompt_path = TEMPLATES_DIR / f"{name}.md"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}") from e
    except (OSError, UnicodeDecodeError) as e:
        raise OSError(f"Failed to read prompt template {prompt_path}: {e}") from e
