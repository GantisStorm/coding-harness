#!/usr/bin/env bash
# shellcheck disable=SC1091  # Don't follow sourced files
#
# Coding Harness TUI Launcher
# ===========================
#
# Usage:
#   ./start.sh                    # Build and run with Docker (default)
#   ./start.sh --native           # Run natively with local venv
#   ./start.sh --build            # Build image only (don't run)
#   ./start.sh --connect [name]   # Connect to running container
#   ./start.sh --list             # List running containers
#   ./start.sh --specs '...'      # Pre-load specs from JSON
#
# Examples:
#
#   # Interactive mode - TUI will prompt for all required fields:
#   ./start.sh
#
#   # Interactive mode with native Python (no Docker):
#   ./start.sh --native
#
#   # Single spec:
#   ./start.sh --specs '[{
#     "spec_file": "/home/user/specs/feature.txt",
#     "project_dir": "/home/user/project",
#     "target_branch": "main"
#   }]'
#
#   # Multiple specs:
#   ./start.sh --specs '[
#     {
#       "spec_file": "/home/user/specs/feature1.txt",
#       "project_dir": "/home/user/project",
#       "target_branch": "main"
#     },
#     {
#       "spec_file": "/home/user/specs/feature2.txt",
#       "project_dir": "/home/user/project",
#       "target_branch": "develop"
#     }
#   ]'
#
#   # List running containers:
#   ./start.sh --list
#
#   # Connect to a running container:
#   ./start.sh --connect
#   ./start.sh --connect coding-harness-a1b2c3d4
#
# Required Spec JSON Fields:
#   spec_file        - Path to the specification file (absolute path)
#   project_dir      - Root project directory (absolute path)
#   target_branch    - Git branch to target for changes
#
# Optional Spec JSON Fields:
#   max_iterations   - Maximum agent iterations (default: unlimited)
#
# Note: Git operations use GitLab MCP with GITLAB_PERSONAL_ACCESS_TOKEN.
#       Commits are attributed to the token owner's GitLab identity.
#
# Environment Variables (from .env):
#   Required:
#     CLAUDE_CODE_OAUTH_TOKEN        - Claude Code OAuth token
#     GITLAB_PERSONAL_ACCESS_TOKEN   - GitLab personal access token (for MCP git operations)
#   Optional:
#     ANTHROPIC_API_KEY              - Alternative to CLAUDE_CODE_OAUTH_TOKEN
#     GITLAB_API_URL                 - For self-hosted GitLab instances
#     CLAUDE_MODEL                   - Model to use (default: claude-opus-4-5-20251101)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly IMAGE_NAME="coding-harness"
readonly SOCKET_PATH="/tmp/coding-harness-daemon.sock"
NATIVE_MODE=false
FORCE_BUILD=false
CONNECT_MODE=false
LIST_MODE=false
CONNECT_TARGET=""
PASSTHROUGH_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --native)
            NATIVE_MODE=true
            shift
            ;;
        --build)
            FORCE_BUILD=true
            shift
            ;;
        --connect)
            CONNECT_MODE=true
            shift
            # Check if next arg is a container name (not another flag)
            if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then
                CONNECT_TARGET="$1"
                # Validate container name (alphanumeric, dash, underscore only)
                if [[ ! "$CONNECT_TARGET" =~ ^[a-zA-Z0-9_-]+$ ]]; then
                    echo "Error: Invalid container name format" >&2
                    exit 1
                fi
                shift
            fi
            ;;
        --list)
            LIST_MODE=true
            shift
            ;;
        *)
            PASSTHROUGH_ARGS+=("$1")
            shift
            ;;
    esac
done

# Load .env file
if [ -f ".env" ]; then
    set -a
    # shellcheck source=/dev/null
    source ".env"
    set +a
fi

# ==============================================================================
# List Mode
# ==============================================================================
if [ "$LIST_MODE" = true ]; then
    echo "Running coding-harness containers:"
    docker ps --filter "name=coding-harness" --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}"
    exit 0
fi

# ==============================================================================
# Connect Mode
# ==============================================================================
if [ "$CONNECT_MODE" = true ]; then
    # Find container to connect to
    if [ -n "$CONNECT_TARGET" ]; then
        CONTAINER="$CONNECT_TARGET"
    else
        # Find first running coding-harness container
        CONTAINER=$(docker ps -f "name=coding-harness" --format "{{.Names}}" | head -1)
        if [ -z "$CONTAINER" ]; then
            echo "No running coding-harness containers found."
            echo "Start one with: ./start.sh"
            exit 1
        fi
    fi

    # Check if container exists and is running
    if ! docker ps -q -f "name=^${CONTAINER}$" | grep -q .; then
        echo "Container '$CONTAINER' is not running."
        echo "Running containers:"
        docker ps --filter "name=coding-harness" --format "  {{.Names}}"
        exit 1
    fi

    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║     Attaching to: $CONTAINER"
    echo "╠═══════════════════════════════════════╣"
    echo "║  [Enter]     Start/Restart TUI        ║"
    echo "║  [Ctrl+C]    Stop container           ║"
    echo "║  [Ctrl+P,Q]  Detach (keep running)    ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""
    exec docker attach "$CONTAINER"
fi

# ==============================================================================
# Native Mode
# ==============================================================================
if [ "$NATIVE_MODE" = true ]; then
    if [ -d ".venv" ]; then
        PYTHON=".venv/bin/python"
    elif [ -d "venv" ]; then
        PYTHON="venv/bin/python"
    else
        echo "Error: No venv found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
        exit 1
    fi

    DAEMON_PID=""
    # SOCKET_PATH is defined at top of script as readonly constant

    cleanup_native() {
        echo ""
        echo "Stopping daemon..."
        if [ -n "$DAEMON_PID" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
            kill "$DAEMON_PID" 2>/dev/null || true
            wait "$DAEMON_PID" 2>/dev/null || true
        fi
        [ -S "$SOCKET_PATH" ] && rm -f "$SOCKET_PATH"
        echo "Done."
        exit 0
    }

    trap cleanup_native INT TERM EXIT

    # Start daemon if not already running
    if [ ! -S "$SOCKET_PATH" ]; then
        echo "Starting agent daemon..."
        "$PYTHON" -m agent.daemon &
        DAEMON_PID=$!

        # Wait for socket
        for _ in {1..10}; do
            [ -S "$SOCKET_PATH" ] && break
            sleep 0.5
        done

        if [ ! -S "$SOCKET_PATH" ]; then
            echo "Error: Daemon failed to start" >&2
            exit 1
        fi
        echo "Daemon started (PID: $DAEMON_PID)"
    else
        echo "Daemon already running."
    fi

    # Run TUI
    "$PYTHON" -m tui.main "${PASSTHROUGH_ARGS[@]}" || true

    # Cleanup handled by trap
    exit 0
fi

# ==============================================================================
# Docker Mode
# ==============================================================================

if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found. Install Docker or use --native flag." >&2
    exit 1
fi

# Always build image
echo "Building Docker image..."
if ! docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"; then
    echo "Error: Docker build failed" >&2
    exit 1
fi
if [ "$FORCE_BUILD" = true ]; then
    echo "Build complete."
    exit 0
fi

# Generate unique container name with random hash
CONTAINER_HASH=$(head -c 4 /dev/urandom | xxd -p)
CONTAINER_NAME="${IMAGE_NAME}-${CONTAINER_HASH}"

echo "Starting: $CONTAINER_NAME"

# Named volume for daemon state (agent registry, not logs)
# - Daemon state persists across container restarts
# - Agent logs persist in project's .claude-agent/ via $HOME mount
# - Clear with: docker volume rm ${CONTAINER_NAME}-data
VOLUME_NAME="${CONTAINER_NAME}-data"

# Build SSH agent socket arguments if available (for git SSH auth)
SSH_AGENT_ARGS=()
if [ -n "$SSH_AUTH_SOCK" ] && [ -S "$SSH_AUTH_SOCK" ]; then
    SSH_AGENT_ARGS+=(-e "SSH_AUTH_SOCK=$SSH_AUTH_SOCK")
    SSH_AGENT_ARGS+=(-v "$SSH_AUTH_SOCK:$SSH_AUTH_SOCK")
fi

# Run container
# Git authentication:
#   - HTTP(S): Uses GITLAB_PERSONAL_ACCESS_TOKEN via credential helper (configured in entrypoint)
#   - SSH: Uses forwarded SSH agent socket if available
exec docker run -it --rm \
    --name "$CONTAINER_NAME" \
    -e "HOME=$HOME" \
    -e "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN:-}" \
    -e "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}" \
    -e "GITLAB_PERSONAL_ACCESS_TOKEN=${GITLAB_PERSONAL_ACCESS_TOKEN:-}" \
    -e "GITLAB_API_URL=${GITLAB_API_URL:-}" \
    -e "CLAUDE_MODEL=${CLAUDE_MODEL:-}" \
    -e "CONTEXT7_API_KEY=${CONTEXT7_API_KEY:-}" \
    -e "SEARXNG_URL=${SEARXNG_URL:-}" \
    "${SSH_AGENT_ARGS[@]}" \
    -v "$HOME:$HOME" \
    -v "/tmp:/tmp" \
    -v "${VOLUME_NAME}:/app/.data" \
    -w "$PWD" \
    "$IMAGE_NAME" \
    "${PASSTHROUGH_ARGS[@]}"
