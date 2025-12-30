"""
Shared Utility Functions
========================

Common utility functions used across agent and TUI packages.

Public API:
    spec_filename_to_slug: Convert spec filename to URL-safe slug
    generate_spec_hash: Generate deterministic hash from spec file content
    validate_required_env_vars: Validate required environment variables
    ValidationResult: Type alias for validation function return type
"""

import hashlib
import os
import re
from pathlib import Path

# Type alias for validation result: (success: bool, error_message: str)
# On success: (True, ""), on failure: (False, "error description")
type ValidationResult = tuple[bool, str]


def spec_filename_to_slug(spec_file: Path) -> str:
    """Convert a spec filename to a slug for the agent state directory.

    Args:
        spec_file: Path to the spec file

    Returns:
        A kebab-case slug derived from the filename (without extension)
    """
    # Get filename without extension
    name = spec_file.stem
    # Convert to lowercase, replace spaces/underscores with hyphens
    slug = name.lower().replace(" ", "-").replace("_", "-")
    # Remove any non-alphanumeric characters except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug or "default"


def generate_spec_hash(spec_file: Path) -> str:
    """Generate a deterministic 5-character hash for a spec file.

    Uses spec file content to generate a consistent hash.
    Same spec file always produces the same hash.

    Args:
        spec_file: Path to the spec file

    Returns:
        5-character hexadecimal hash (e.g., "a3f9c")

    Raises:
        FileNotFoundError: If spec file does not exist
        OSError: If spec file cannot be read
        ValueError: If generated hash is not valid 5-char hex format
    """
    # Read spec file content for deterministic hashing
    try:
        spec_content = spec_file.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Spec file not found: {spec_file}") from e
    except (OSError, UnicodeDecodeError) as e:
        raise OSError(f"Failed to read spec file {spec_file}: {e}") from e

    # Generate SHA256 hash from content and take first 5 characters
    hash_obj = hashlib.sha256(spec_content.encode())
    spec_hash = hash_obj.hexdigest()[:5]

    # Validate hash format (5 lowercase hex characters)
    if len(spec_hash) != 5 or not all(c in "0123456789abcdef" for c in spec_hash):
        raise ValueError(f"Generated invalid spec_hash: {spec_hash} (expected 5-char hex)")

    return spec_hash


def validate_required_env_vars() -> ValidationResult:
    """
    Validate that all required environment variables are set.

    Returns:
        tuple[bool, str]: (success, error_message)
    """
    # Check for Claude API token
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") and not os.environ.get("ANTHROPIC_API_KEY"):
        return (
            False,
            "Error: Neither CLAUDE_CODE_OAUTH_TOKEN nor ANTHROPIC_API_KEY environment variable is set\n\n"
            "Option 1: Run 'claude setup-token' after installing the Claude Code CLI.\n"
            "  export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'\n\n"
            "Option 2: Use Anthropic API key directly:\n"
            "  export ANTHROPIC_API_KEY='sk-ant-xxxxxxxxxxxxx'",
        )

    # Check for GitLab token
    if not os.environ.get("GITLAB_PERSONAL_ACCESS_TOKEN"):
        return (
            False,
            "Error: GITLAB_PERSONAL_ACCESS_TOKEN environment variable not set\n\n"
            "Get your personal access token from: https://gitlab.com/-/user_settings/personal_access_tokens\n"
            "Required scopes: api, read_api, read_repository, write_repository\n\n"
            "Then set it:\n"
            "  export GITLAB_PERSONAL_ACCESS_TOKEN='glpat-xxxxxxxxxxxxx'",
        )

    # Note: CONTEXT7_API_KEY and SEARXNG_URL are optional per README.md
    # They enhance functionality but are not required for basic operation.

    return (True, "")
