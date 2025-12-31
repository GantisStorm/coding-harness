"""
Shared Utility Functions
========================

Common utility functions used across agent and TUI packages.

Public API:
    spec_filename_to_slug: Convert spec filename to URL-safe slug
    generate_spec_hash: Generate unique 8-char base62 hash from spec file content + randomness
    validate_required_env_vars: Validate required environment variables
    ValidationResult: Type alias for validation function return type
"""

import hashlib
import os
import re
import secrets
from pathlib import Path
from typing import TypeAlias

# Base62 alphabet for compact, URL-safe identifiers
BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# Type alias for validation result: (success: bool, error_message: str)
# On success: (True, ""), on failure: (False, "error description")
ValidationResult: TypeAlias = tuple[bool, str]  # noqa: UP040


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


def _int_to_base62(num: int, length: int) -> str:
    """Convert an integer to a base62 string of fixed length.

    Args:
        num: Non-negative integer to convert
        length: Desired output length (will be zero-padded)

    Returns:
        Base62 string of exactly `length` characters
    """
    if num == 0:
        return BASE62_ALPHABET[0] * length

    result = []
    while num > 0:
        result.append(BASE62_ALPHABET[num % 62])
        num //= 62

    # Pad to desired length
    while len(result) < length:
        result.append(BASE62_ALPHABET[0])

    return "".join(reversed(result[-length:]))


def generate_spec_hash(spec_file: Path) -> str:
    """Generate an 8-character base62 hash for a spec file.

    Combines spec file content hash with random bytes to create a unique
    identifier for each run. Uses base62 encoding (0-9, A-Z, a-z) for
    compact representation with ~218 trillion combinations.

    Args:
        spec_file: Path to the spec file

    Returns:
        8-character base62 hash (e.g., "K7xMp2Qw")

    Raises:
        FileNotFoundError: If spec file does not exist
        OSError: If spec file cannot be read
        ValueError: If generated hash is not valid 8-char base62 format
    """
    # Read spec file content
    try:
        spec_content = spec_file.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Spec file not found: {spec_file}") from e
    except (OSError, UnicodeDecodeError) as e:
        raise OSError(f"Failed to read spec file {spec_file}: {e}") from e

    # Combine content hash with random bytes for uniqueness
    content_hash = hashlib.sha256(spec_content.encode()).digest()[:4]  # 4 bytes from content
    random_bytes = secrets.token_bytes(4)  # 4 random bytes

    # Combine and convert to integer
    combined = int.from_bytes(content_hash + random_bytes, "big")

    # Convert to 8-character base62
    spec_hash = _int_to_base62(combined, 8)

    # Validate hash format (8 base62 characters)
    if len(spec_hash) != 8 or not all(c in BASE62_ALPHABET for c in spec_hash):
        raise ValueError(f"Generated invalid spec_hash: {spec_hash} (expected 8-char base62)")

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
