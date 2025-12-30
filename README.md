# Coding Harness

> Human-in-the-Loop AI Coding Agent with GitLab Integration (or File-Only Mode)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Type checked: pyright](https://img.shields.io/badge/type%20checked-pyright-blue.svg)](https://github.com/microsoft/pyright)

*Note: The badges above are for the harness codebase itself. Target projects can use any language and tooling - see [Pluggable Code Quality System](#pluggable-code-quality-system-target-projects).*

## Overview

**What is an Agent Harness?** A harness is a coordination layer or scaffolding around AI agents that allows them to work for hours (or days) on complex tasks without overwhelming their context window. Instead of asking an agent to do everything at once, a harness connects multiple agent sessions together—each starting fresh but quickly catching up via structured artifacts, then making incremental progress before handing off to the next session.

Coding Harness is an autonomous coding agent orchestration system that combines Claude AI with a terminal user interface (TUI) for milestone-based development workflows. It takes specification files, breaks them into issues (GitLab or local JSON files), and uses AI agents to implement each issue with human oversight at critical decision points.

```
┌──────────┐    ┌──────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Spec   │───▶│   TUI    │───▶│  Claude Agents   │───▶│ GitLab (default)│
│   File   │    │ (human)  │    │ (Init→Code→MR)   │    │ - OR -          │
└──────────┘    └────┬─────┘    └────────┬─────────┘    │ Local JSON files│
                     │                   │              └─────────────────┘
                     └───── 8 HITL ──────┘
                          checkpoints
```

The harness provides Human-in-the-Loop (HITL) checkpoints at 8 key stages, ensuring humans maintain control over project setup, issue breakdown, implementation approval, and merge request creation.

## Conceptual Foundations

### The Evolution: Prompts → Context → Harnesses

AI engineering has evolved through three stages:

1. **Prompt Engineering** (2020-2023) - Optimizing single interactions with LLMs
2. **Context Engineering** (2023-2024) - Optimizing entire sessions—what context to provide, when, and how to avoid overwhelming the model
3. **Agent Harnesses** (2024+) - Connecting multiple sessions together for long-running tasks

Early examples include Manis (2024) and LangChain's deep agents. The pattern is becoming standardized as "the next unlock for AI capability."

**Why harnesses now?** The raw power of LLMs isn't exploding like it was. Scaling has hit limits. The breakthrough now comes from the layer *around* LLMs—memory systems, handoff protocols, validation loops, and orchestration. Harnesses are this layer.

**2026 prediction:** Cole Medin and others predict 2026 will be "the year of agent harnesses"—shifting from experimental to production-grade, with reliable autonomous coding becoming mainstream.

**Vibe coding becomes viable** when you have an engineered harness with human-in-the-loop at strategic checkpoints. Without the scaffolding, delegating coding to AI fails. With it, you can trust long-running autonomous work—though the system itself requires careful engineering.

### Resources

**Anthropic Research:**
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) - Engineering blog (Nov 2025)
- [Autonomous Coding Quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) - Reference implementation

**Video Explainers:**
- [I Forced Claude to Code for 24 Hours NONSTOP](https://www.youtube.com/watch?v=usQ2HBTTWxs) - Cole Medin's live test (result: 54% of 200 tests passing after 54 sessions)
- [Claude SDK: 24-Hour Coding Agent](https://www.youtube.com/watch?v=BGouphNN5hg) - Live stream with Ray, Linear integration, cloud deployment, mid-run feedback
- [Are Agent Harnesses Bringing Back Vibe Coding?](https://www.youtube.com/watch?v=13HP_bSeNjU) - Evolution from prompts to harnesses, two unsolved problems
- [Unlock DEEP AGENTS with Anthropic's Agent Harness](https://www.youtube.com/watch?v=RQq3aMV7a5g) - n8n implementation with concurrency patterns

**Related Projects (mentioned in live stream):**
- [Archon](https://github.com/coleam00/archon) - Cole Medin's open source "command center for AI coding" with Kanban board, knowledge curation, and MCP server. Similar concepts to Linear integration but AI-optimized.
- [Factory](https://www.factory.ai/) - Ray's preferred coding agent. Uses memory compression (different approach than this harness's fresh-context-per-session pattern).
- Remote Agentic Coding System - Cole's upcoming project for kicking off agents from Slack, Discord, Telegram, GitHub. Combines harness ideas with remote observability.

**Concepts Drawn from Each Source:**

| Source | Key Concepts Incorporated |
|--------|--------------------------|
| Anthropic Blog | Initializer + coding agent pattern, feature list with `passes: false→true`, `claude-progress.txt` equivalent, git commits as checkpoints, one-shotting/premature-completion failures |
| Cole Medin (24hr) | PIV loop mental model, "priming" phase, Claude Agent SDK usage, security hooks pattern, regression testing, test-driven verification, brownfield adaptation |
| Cole Medin (Live) | Linear MCP integration, token efficiency, cloud deployment issues, mid-run feedback injection, meta issue pattern, harness simplicity ("just two prompts"), OAuth subscription token, alternative SDKs comparison, real-time task board observation (no refresh needed), mobile monitoring via Linear app, parallel MCP calls for speed, spec template + brain dump workflow, OpenCode + Ollama confirmed working, temperature variance between providers |
| Vibe Coding Video | Evolution timeline (prompts→context→harnesses), bounded attention/"dumb zone", compounding error math (95%²⁰=36%), vibe coding viability with HITL, predictive context as unsolved problem, autonomy balance |
| n8n Deep Agents | Concurrency patterns, lock mechanisms, research artifact staging, progressive summarization, Retrieval→Synthesize→Write pipeline, task dependency concepts |

**Comprehensive Feature Coverage:**

| Concept | Source | Status | Notes |
|---------|--------|--------|-------|
| **Core Architecture** ||||
| Initializer → Coding → MR agents | Anthropic | ✅ Have | Extended to 3 agents with HITL |
| Feature/task list persistence | Anthropic | ✅ Have (adapted) | GitLab issues instead of JSON |
| Progress file handoffs | Anthropic | ✅ Have (adapted) | GitLab comments + `.gitlab_milestone.json` |
| Git commits as checkpoints | All | ✅ Have | Structured format with metadata |
| **Failure Mode Prevention** ||||
| One-shotting prevention | Anthropic | ✅ Have | ONE issue per coding session |
| Premature completion prevention | Anthropic | ✅ Have | Quality gates + HITL before closure |
| Compounding error mitigation | Vibe Coding | ✅ Have | Circuit breakers, regression tests |
| Context rot prevention | Vibe Coding | ✅ Have | Fresh context per session |
| **Validation & Testing** ||||
| Browser automation (Puppeteer) | Anthropic | ✅ Have | Via Puppeteer MCP |
| Regression testing | All | ✅ Have | Before/after each issue |
| Unit test creation | Cole Medin | ✅ Have | Mandatory for new code |
| Test repair loop | Cole Medin | ✅ Have | Max 3 attempts then skip |
| Quality gates (lint/type/test) | All | ✅ Have | Must pass before issue closure |
| **Human Oversight** ||||
| Human-in-the-loop checkpoints | All | ✅ Have | 8 checkpoint types |
| Autonomy balance | Vibe Coding | ✅ Have | Strategic checkpoints, not constant |
| Auto-accept mode | - | ✅ Have | For trusted runs |
| **Memory & Persistence** ||||
| File system as memory | n8n | ✅ Have | `.claude-agent/` directory |
| Git as external memory | Cole Medin | ✅ Have | Commit log for context |
| Progressive summarization | n8n | ⚠️ Kinda have | Handoff comments, not systematic |
| Research artifact staging | n8n | ⚠️ Kinda have | GitLab comments serve this role |
| Lock mechanisms | n8n | ⚠️ Kinda have | Daemon handles single-agent; no multi-worker locks |
| **Advanced Patterns** ||||
| Static planning | n8n | ✅ Have | Issues created upfront |
| Rolling/adaptive planning | n8n | ❌ Don't have | No replanning based on progress |
| Goal-driven planning | n8n | ❌ Don't have | No dynamic goal reassessment |
| Parallel task execution | n8n | ❌ Don't have | Sequential only |
| Task dependency graphs | n8n | ❌ Don't have | No explicit dependencies |
| Hybrid concurrency | n8n | ❌ Don't have | No parallel retrieval → sequential synthesis |
| WorkTrees for parallel branches | Cole Medin | ❌ Don't have | Single branch per agent |
| **Development Modes** ||||
| Greenfield (new projects) | Anthropic | ✅ Have | Primary mode |
| Brownfield (existing codebases) | Cole Medin | ✅ Have | Supported via spec design |
| Refactoring/migrations | Cole Medin | ⚠️ Possible | Untested, needs custom validation |
| **Multi-Assistant Support** ||||
| Claude Agent SDK | Anthropic | ✅ Have | Only supported assistant |
| Other SDKs (Codex, OpenCode, AMP) | Cole Medin | ❌ Don't have | Architecture is portable, not implemented |
| **Specialized Agents** ||||
| Testing agent | Anthropic (future) | ❌ Don't have | Coding agent does inline |
| QA agent | Anthropic (future) | ⚠️ Partial | Puppeteer in coding agent |
| Code cleanup agent | Anthropic (future) | ❌ Don't have | Coding agent does inline |
| Research agent | n8n | ⚠️ Partial | Issue enrichment phase |
| Input validation agent | n8n | ❌ Don't have | HITL serves this purpose |
| **External Integrations** ||||
| GitLab issues/MRs | - | ✅ Have | Core integration |
| Linear/Jira/Asana | Cole Medin (Live) | ❌ Don't have | GitLab-specific |
| Real-time task observation | Cole Medin (Live) | ⚠️ Kinda have | GitLab updates require refresh; Linear updates live |
| Mobile monitoring | Cole Medin (Live) | ⚠️ Kinda have | GitLab mobile app works; Linear demo'd on phone |
| Meta issue for handoffs | Cole Medin (Live) | ✅ Have | GitLab comments on milestone; Linear uses meta issue |
| Context7 (library docs) | - | ✅ Have | Optional enrichment |
| SearxNG (web search) | - | ✅ Have | Optional enrichment |
| **Spec & Planning** ||||
| Template + brain dump workflow | Cole Medin (Live) | ✅ Have | Give LLM template + rough idea → structured spec |
| Vibe planning (unstructured) | Cole Medin (Live) | ⚠️ Kinda have | Supported via spec writing; not explicit phase |
| PIV loop (Plan-Implement-Verify) | Cole Medin | ✅ Have | Core harness pattern |
| **Authentication & Cost** ||||
| OAuth subscription token | Cole Medin (Live) | ✅ Have | Use Max plan instead of API credits |
| API key fallback | Anthropic | ✅ Have | Per-token billing option |
| **Alternative Providers** ||||
| OpenCode + Ollama (local) | Cole Medin (Live) | ❌ Don't have | Community-confirmed working; not implemented |
| OpenCode + Gemini 3 | Cole Medin (Live) | ❌ Don't have | Supported by OpenCode; not implemented |
| Parallel MCP calls | Cole Medin (Live) | ⚠️ Kinda have | Claude does this automatically when appropriate |

**Legend:** ✅ Have = Fully implemented | ⚠️ Kinda have = Partial/adapted | ❌ Don't have = Not implemented

### The Three Problems Harnesses Solve

Complex projects can't be completed in a single context window. When context fills up, a new session starts with no memory. This creates three core challenges:

**1. Bounded Attention (Context Rot)**

As you add more information to an LLM's context, it enters what's been called the "dumb zone"—overwhelmed and making poor decisions. Harnesses solve this by:
- Clearing context between sessions (fresh start)
- Using external memory (files, databases, git) instead of in-context memory
- Progressive summarization of older work
- Handoff artifacts that capture only what's needed to continue

**2. Compounding Errors (Reliability Decay)**

If an agent has 95% reliability per step, over 20 steps that compounds to only 36% system reliability (0.95²⁰). Harnesses address this through:
- Checkpoints with self-validation after each task
- Human-in-the-loop at critical decision points
- Automatic rollback via git when things go wrong
- Guard rails that stop progress if quality checks fail

**3. Predictive Context (Unsolved)**

The hardest problem: you can't predict which observation becomes critical 10 steps later. Current approaches try to preserve everything potentially relevant, but optimal summarization—knowing exactly what future sessions will need—remains an open challenge. This harness addresses it through:
- Structured handoff templates that capture known-important context
- Git history as lossless memory (always recoverable)
- GitLab comments preserving full context on each issue

Anthropic specifically identified two behavioral failure modes:

1. **One-shotting** - Agent tries to do everything at once, runs out of context mid-implementation, leaves codebase broken. Next session must guess what happened.

2. **Premature completion** - Agent sees progress has been made, declares the job done while major features remain unimplemented.

### The Solution: Initializer + Task Agent Pattern

**The core insight:** Despite appearing complex, harnesses are fundamentally simple. As Cole Medin emphasized during the live stream: "Everything that seems fancy with AI coding assistants is just a bunch of prompts... all this harness is is two prompts—the initializer prompt and the coding prompt. That's it."

The most common harness architecture uses two specialized agents:

| Agent | Purpose |
|-------|---------|
| **Initializer** (session 1) | Create feature list/tasks, setup environment, initialize git |
| **Task Agent** (sessions 2+) | Implement ONE task, verify it works, commit, repeat in loop |

This pattern appears across implementations—Anthropic's coding quickstart, LangChain's deep agents, and custom harnesses. The task agent loops until all work is complete, with each iteration:

1. **Prime** - Read progress files, git log, understand current state ("getting bearings")
2. **Validate** - Regression test previous work before touching anything new
3. **Execute** - Implement one task, write tests, verify
4. **Handoff** - Update progress files, commit, prepare for next session

This maps to what Cole Medin calls the **PIV loop** (Plan-Implement-Verify)—a mental model for structured AI coding where each cycle produces verified, committed work.

The key insight: **agents need structured artifacts to quickly understand project state when starting fresh**. These include:
- A task/feature list that tracks what's done vs remaining (never edit descriptions, only mark complete)
- Progress notes summarizing recent work
- Git commits as atomic checkpoints
- Session handoff comments with specific next steps

### How This Harness Adapts the Pattern

| Aspect | Quickstart | This Harness |
|--------|------------|--------------|
| Work units | 200 tiny test cases | GitLab issues (fewer, larger) |
| Granularity | Each test ≈ one session | Each issue may span multiple sessions |
| Progress tracking | `passes: false → true` in JSON | GitLab comments + "in-progress" label (or local JSON in file-only mode) |
| Completion signal | Edit JSON field | Close issue via GitLab API (or update local JSON) |
| State file | `claude-progress.txt` | `.gitlab_milestone.json` |
| Human oversight | None (fully autonomous) | 8 HITL checkpoints |
| Interface | CLI auto-loop | TUI with log streaming |
| Issue tracking | Local JSON only | GitLab (default) or local JSON (file-only mode) |
| MR creation | N/A | Optional (can skip to keep changes on branch) |

**Key difference in granularity:** The quickstart decomposes specs into ~200 small test cases, each small enough to complete in a single context window. This harness uses GitLab issues—larger work units that may require multiple sessions to complete.

**Multi-session issue support:** When an issue can't be completed in one session:
- The "in-progress" label persists across sessions
- Structured handoff comments include:
  - Last commit SHA and message
  - Progress checklist (completed / in-progress / not started)
  - Files changed with change types
  - Specific next steps for the following session
  - Gotchas and key context
- Next session reviews git log and handoff comments before continuing
- The issue stays assigned until closed

**Commit conventions:** All commits follow a structured format for traceability:
```
<type>(#<issue>): <short description>

<body - what changed and why>

Files: <count> changed
Tests: <added/updated/none>
Issue: #<iid> - <title>
```

Types: `feat`, `fix`, `test`, `refactor`, `style`, `docs`, `chore`

We extend to three agents (Initializer → Coding loop → MR Creation) and add human approval gates at critical decisions—directly addressing the premature completion problem.

### Advanced Patterns (Not Yet Implemented)

Agent harnesses can vary significantly based on the use case. This section documents patterns from the research that we don't yet implement—useful context for understanding the design space and future directions.

**Planning Strategies:**

| Strategy | Description | This Harness |
|----------|-------------|--------------|
| **Static Plan** | Create all tasks upfront, execute sequentially | ✅ Used |
| **Rolling Plan** | Plan → execute → replan based on progress | ❌ Not implemented |
| **Goal-Driven** | Constantly ask "what's the best next action?" | ❌ Not implemented |
| **Test-Driven Loop** | Iterate until criteria/tests pass | ✅ Partial (quality gates) |

**Concurrency Patterns:**

| Pattern | Description | This Harness |
|---------|-------------|--------------|
| **Sequential** | One task at a time | ✅ Used |
| **Parallel Retrieval** | Research multiple sources simultaneously | ❌ Not implemented |
| **Hybrid Concurrent** | Parallel retrieval → sequential synthesis | ❌ Not implemented |
| **Dependency Graph** | Tasks with explicit dependencies | ❌ Not implemented |

**Multi-Assistant Support:**

The harness architecture (prompts + artifacts) is theoretically portable to other coding assistants with SDKs (Codex, OpenCode, AMP). However, this implementation is Claude-specific. Porting would require:
- Replacing Claude Agent SDK calls with equivalent SDK
- Adjusting prompts for model-specific behaviors
- Testing validation and tool use patterns

**Confirmed working alternatives (from live stream):**
- **OpenCode + Ollama** - Tested during the stream by community member Rasmus. OpenCode supports local models via Ollama, enabling fully local harness execution with models like Qwen 3 Coder or Kimi K2.
- **OpenCode + Gemini 3** - Listed as supported model in OpenCode docs.

**Temperature considerations:** Ray noted that different providers may have different default temperatures, and this affects output quality. When using open models through providers like Fireworks or Cerebras, check the model card for recommended temperature settings. Models trained for agentic tool use (like Kimi K2, which handles hundreds of tool calls) may behave differently than general-purpose models.

**WorkTrees:**

Git worktrees enable parallel work on multiple branches. This harness uses a single branch per agent. Implementing worktrees would allow multiple issues to be worked simultaneously—useful for independent features with no code overlap.

### Greenfield vs Brownfield Development

The Anthropic quickstart is optimized for **greenfield** development—building new applications from scratch. This harness supports both modes:

| Mode | Description | This Harness |
|------|-------------|--------------|
| **Greenfield** | Build new project from scratch via spec file | ✅ Primary mode |
| **Brownfield** | Add features to existing codebase | ✅ Supported |
| **Refactoring** | Large-scale code modernization | ⚠️ Possible but untested |

**How brownfield works:**
1. Spec file describes features to ADD to existing codebase (not rebuild from scratch)
2. Issues are created relative to current project state
3. Agent reads existing code patterns before implementing
4. Issue enrichment researches codebase context (grep, file structure)

**Brownfield example** (from Cole Medin's video): Sean used a modified harness for TypeScript refactoring—upgrading a codebase 12 major TypeScript versions behind. The harness handled:
- Breaking changes across versions
- Deprecated code patterns
- Validation that refactored code still compiles

**Community results shared during live stream:**
- WebDevCody: "I tried this last night for 24 [hours]. It's pretty amazing. 128 commits in."
- Multiple community members confirmed successful runs with custom applications
- Rasmus: "Tested the remote agent workflow manager harness today, built a Circle clone in a few hours in Django"

**Refactoring considerations:**
- Change spec to describe the transformation, not features
- Issues become refactoring tasks (e.g., "update all X to Y pattern")
- Quality gates verify no regressions introduced
- May need custom validation beyond test suites

**Not yet supported:**
- **Parallel brownfield** - Multiple agents on different features of same codebase
- **Migration scripts** - Database schema or infrastructure changes
- **Cross-repo refactoring** - Changes spanning multiple repositories

### Multi-Agent Specialization (Future Work)

The Anthropic blog mentions potential specialized agents beyond the current Initializer → Coding → MR pattern:

| Agent Type | Purpose | Status |
|------------|---------|--------|
| **Testing Agent** | Write comprehensive test suites | ❌ Not implemented (coding agent does inline) |
| **QA Agent** | End-to-end quality validation | ⚠️ Partial (via Puppeteer in coding agent) |
| **Code Cleanup Agent** | Dead code removal, style fixes | ❌ Not implemented (coding agent does inline) |
| **Research Agent** | Deep context gathering | ⚠️ Partial (issue enrichment phase) |

Current approach: A single coding agent handles implementation, testing, and cleanup inline. Specialization could improve quality but adds coordination complexity.

### Known Limitations

**Browser Automation:**
- Cannot see browser-native alert/confirm/prompt modals through Puppeteer MCP
- Some dynamic UI elements may not be visible in screenshots
- Timing issues with slow-loading content

**Context Prediction:**
- Cannot predict which information becomes critical later
- Handoff templates are heuristic, not optimal
- Git history as fallback is comprehensive but token-expensive to read

**Rate Limiting:**
- Claude subscription has usage limits (varies by plan)
- Long-running agents may hit rate limits; resume from checkpoint
- OAuth token lasts 1 year; API key has no expiry but costs per-token

**Observations from live stream:** Cole Medin reported running Opus 4.5 for 24 hours (even running two harness instances for 12 of those hours) without hitting rate limits on the $200/month Max plan. However, other community members report hitting limits quickly. Rate limit behavior appears to vary by account and region. Recommendation: use multiple coding assistants (toggle between Claude Code, Codex, OpenCode) to distribute load if you hit limits frequently.

### Core Behaviors (How We Tackle Harness Challenges)

**Incremental progress** *(solves: one-shotting)*: Each session works on ONE issue at a time. Large issues may span multiple sessions—progress is documented in GitLab comments with structured handoffs, and the next session continues where the last left off.

**Clean state** *(solves: broken handoffs)*: Every session ends with code that's mergeable—no half-implementations, no broken tests, no uncommitted changes. If an issue isn't complete, the "in-progress" label stays on and a detailed handoff comment documents progress, last commit SHA, and next steps.

**Test-driven verification** *(solves: compounding errors)*: Agents write unit tests for all new code, fix failing tests before proceeding, and verify features through browser automation. This combines automated test coverage with end-to-end UI verification—catching errors before they compound.

**Quality gates** *(solves: premature completion)*: Before closing issues—linting, type checking, and test suite must pass. Regression checks on previously completed features. The agent cannot declare success without passing external validation.

**Structured commits** *(solves: context rot)*: All commits follow a conventional format (`feat(#42): description`) with metadata (files changed, tests added, issue reference). Git becomes external memory—new sessions can read the commit log to understand what happened without relying on in-context memory.

**File tracking** *(solves: accidental pollution)*: Agents track exactly which files they modify in `session_files.tracked`. Only those files get pushed—never pre-existing user changes or unrelated modifications.

### Operating Modes

The harness supports flexible operating modes to fit different workflows:

**GitLab Mode (Default)**
- Issues and milestones tracked in GitLab
- MR created automatically when coding completes
- Full observability through GitLab's web interface

**File-Only Mode**
- Issues and milestones stored in local JSON files (`.claude-agent/<spec>/`)
- No GitLab account required for issue tracking
- Useful for: offline work, private repos, quick prototyping
- Enable via TUI checkbox or `"file_only_mode": true` in JSON specs

**Skip MR Creation**
- Agent stops after coding completes
- All changes remain on the feature branch
- Useful for: manual review before MR, experimental work, draft features
- Enable via TUI checkbox or `"skip_mr_creation": true` in JSON specs

**Combined Modes**
All modes can be combined. For example, file-only mode + skip MR creation gives you a fully local workflow where the agent codes but you handle all git operations manually afterward.

## Features

*Each feature below addresses a specific harness challenge—context management, reliability, or coordination.*

- **Interactive TUI** - Textual-based terminal interface for intuitive agent management
- **GitLab Integration** - Automatic milestone creation, issue management, and merge request generation
- **File-Only Mode** - Optional local JSON-based tracking instead of GitLab (no GitLab account required)
- **Skip MR Creation** - Option to stop after coding without creating a merge request (keep changes on branch)
- **8 HITL Checkpoints** - Human approval gates for project verification, issue breakdown, implementation review, and more
- **Spec-to-Issues Breakdown** - AI-powered conversion of specifications into actionable GitLab issues
- **Issue Enrichment** - Optional Context7 and SearxNG integration for researching libraries and best practices
- **Multi-Spec Support** - Run multiple specification files in batch mode
- **Real-Time Output** - Log-tailing terminal widget streams agent output live
- **Atomic State Persistence** - Checkpoint state is safely persisted to prevent data loss
- **Unit Test Creation** - Agents write tests for all new code (pytest, Jest, Vitest, Go, Rust)
- **Test Repair Loop** - Failing tests are automatically fixed before proceeding with new work
- **Regression Testing** - Automated verification of existing features before and after implementation
- **Quality Gates** - Mandatory code quality checks (linting, formatting, type checking) before issue closure
- **Structured Commits** - Conventional commit format with issue references and metadata
- **File Tracking** - Agents track files they modify; only pushes agent-created changes (never user's uncommitted work)
- **Multi-Session Handoffs** - Detailed handoff comments with commit SHAs for seamless session continuity
- **Verification Loops** - GitLab API calls with retry logic, issue creation verification, MR existence validation

## Prerequisites

- **Docker** (recommended) - [Install Docker](https://docs.docker.com/get-docker/)
- **OR Python 3.11+** - [Download Python](https://www.python.org/downloads/) (for native mode)
- **Git** - For repository operations
- **GitLab Account** - With API access token ([Create Token](https://gitlab.com/-/user_settings/personal_access_tokens))
  - *Optional if using file-only mode for issue tracking*
- **Claude API Access** - Either:
  - Claude Code OAuth token (recommended) - Generate with `claude setup-token`
  - Anthropic API key - [Get API Key](https://console.anthropic.com/settings/keys)
- **Optional:**
  - [Context7](https://context7.com/) API key for library documentation lookup
  - [SearxNG](https://github.com/searxng/searxng) instance for web search enrichment

## Installation

### Docker Mode (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd coding-harness

# Copy environment template
cp .env.example .env

# Edit .env with your credentials (see Configuration section)
nano .env  # or your preferred editor

# Start (Docker image builds automatically on first run)
./start.sh
```

**Docker mode benefits:**
- Daemon + agents persist when TUI exits
- Reconnect anytime with `./start.sh --connect`
- True SSH-like experience

### Native Mode (Without Docker)

```bash
# Clone the repository
git clone <repository-url>
cd coding-harness

# Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your credentials (see Configuration section)
nano .env  # or your preferred editor

# Start in native mode
./start.sh --native
```

**Native mode differences:**
- Daemon is started automatically but killed when TUI exits
- No persistence - agents stop when you quit
- Good for quick testing, not long-running tasks

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_PERSONAL_ACCESS_TOKEN` | GitLab token with scopes: `api`, `read_api`, `read_repository`, `write_repository` (optional in file-only mode) |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code OAuth token (preferred) |
| `ANTHROPIC_API_KEY` | Alternative: Anthropic API key (if not using OAuth) |

*Note: You need either `CLAUDE_CODE_OAUTH_TOKEN` OR `ANTHROPIC_API_KEY`, not both.*
*Note: `GITLAB_PERSONAL_ACCESS_TOKEN` is optional if using file-only mode for issue tracking.*

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTEXT7_API_KEY` | - | For library documentation lookup during issue enrichment |
| `SEARXNG_URL` | `http://localhost:8888` | SearxNG instance URL for web search |
| `CLAUDE_MODEL` | `claude-opus-4-5-20251101` | Claude model to use |
| `GITLAB_API_URL` | `https://gitlab.com/api/v4` | For self-hosted GitLab instances |

### Git Authentication

The harness needs git access for both read operations (`git fetch`, `git pull`) and write operations (pushing code). Authentication is handled differently for each:

**Write Operations (push/commit):**
- Always use GitLab MCP with `GITLAB_PERSONAL_ACCESS_TOKEN`
- Token-based, works everywhere without additional setup

**Read Operations (fetch/pull):**
- **Docker mode:** Auto-configured using `GITLAB_PERSONAL_ACCESS_TOKEN` as git credential
- **Native mode:** Uses your local git credentials (SSH or keychain)

**Docker Mode (automatic):**

The container automatically configures git credentials from `GITLAB_PERSONAL_ACCESS_TOKEN`. No additional setup required - `git fetch` and `git pull` just work.

If you prefer SSH:
```bash
# SSH agent is forwarded if running
ssh-add ~/.ssh/your_key  # Add key to agent before starting
./start.sh               # SSH_AUTH_SOCK is forwarded to container
```

**Native Mode (manual setup):**

For HTTP(S) remotes, store your GitLab token in the keychain:
```bash
# Erase old credential
git credential-osxkeychain erase <<EOF
protocol=https
host=gitlab.com
EOF

# Store new credential (use your GitLab PAT as password)
git credential-osxkeychain store <<EOF
protocol=https
host=gitlab.com
username=your_username
password=your_gitlab_personal_access_token
EOF
```

For SSH remotes (recommended for native mode):
```bash
# Ensure SSH key is added to GitLab
cat ~/.ssh/id_ed25519.pub  # Add this to GitLab > Settings > SSH Keys

# Update remote to use SSH
git remote set-url origin git@gitlab.com:your/repo.git
```

## Quick Start

### Interactive Mode

The easiest way to start - the TUI guides you through all configuration:

```bash
./start.sh                # Docker mode (default)
./start.sh --native       # Native Python mode
```

### Docker Container Management

```bash
./start.sh                # Start new container
./start.sh --build        # Rebuild Docker image
./start.sh --list         # List running containers
./start.sh --connect      # Connect to running container
./start.sh --connect coding-harness-2  # Connect to specific container
```

**Container Controls:**
- `Enter` - Start/restart TUI
- `Ctrl+C` - Stop container
- `Ctrl+P, Ctrl+Q` - Detach (keep running)
- `Q` - Quit TUI (container stays running)

### Programmatic Mode

For automation or scripting, provide specs as JSON:

```bash
./start.sh --specs '[{
  "spec_file": "/path/to/feature-spec.txt",
  "project_dir": "/path/to/your/project",
  "target_branch": "main"
}]'
```

**With optional flags:**

```bash
# File-only mode (no GitLab required)
./start.sh --specs '[{
  "spec_file": "/path/to/feature-spec.txt",
  "project_dir": "/path/to/your/project",
  "target_branch": "main",
  "file_only_mode": true
}]'

# Skip MR creation (keep changes on branch)
./start.sh --specs '[{
  "spec_file": "/path/to/feature-spec.txt",
  "project_dir": "/path/to/your/project",
  "target_branch": "main",
  "skip_mr_creation": true
}]'

# Both flags together
./start.sh --specs '[{
  "spec_file": "/path/to/feature-spec.txt",
  "project_dir": "/path/to/your/project",
  "target_branch": "main",
  "file_only_mode": true,
  "skip_mr_creation": true
}]'
```

> **Note:** Git operations use GitLab MCP with `GITLAB_PERSONAL_ACCESS_TOKEN`. Commits are attributed to the token owner's GitLab identity. In file-only mode, GitLab is not required for issue tracking but is still used for git operations.

### Auto-Accept Mode

Run without human approval prompts (use with caution):

```bash
./start.sh --auto-accept --specs '[...]'
```

## Usage

### Runtime Architecture

*Level 3 detail: Docker containers, persistence, and process management.*

The harness uses a daemon architecture for robust agent management:

```
  ┌─────────────────────────── Docker Container ───────────────────────────┐
  │                                                                        │
  │  ┌──────────────────────────────────────────────────────────────────┐  │
  │  │               Agent Daemon (python -m agent.daemon)              │  │
  │  │               Always running while container is up               │  │
  │  │                                                                  │  │
  │  │  Responsibilities:                                               │  │
  │  │    • Spawns agent subprocesses (python -m agent.cli)             │  │
  │  │    • Monitors process lifecycle (running/stopped/failed)         │  │
  │  │    • Persists state to .data/daemon_state.json                   │  │
  │  │    • Routes log output to per-agent log files                    │  │
  │  │                                                                  │  │
  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │  │
  │  │  │   Agent CLI     │  │   Agent CLI     │  │   Agent CLI     │   │  │
  │  │  │  (subprocess)   │  │  (subprocess)   │  │  (subprocess)   │   │  │
  │  │  │                 │  │                 │  │                 │   │  │
  │  │  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │   │  │
  │  │  │  │Orchestratr│  │  │  │Orchestratr│  │  │  │Orchestratr│  │   │  │
  │  │  │  │  Session  │  │  │  │  Session  │  │  │  │  Session  │  │   │  │
  │  │  │  │  Phases:  │  │  │  │           │  │  │  │           │  │   │  │
  │  │  │  │ •Init     │  │  │  │ •Coding   │  │  │ (idle/done)  │  │   │  │
  │  │  │  │ •Coding   │  │  │  │           │  │  │  │           │  │   │  │
  │  │  │  │ •MR       │  │  │  └───────────┘  │  │  └───────────┘  │   │  │
  │  │  │  └───────────┘  │  │                 │  │                 │   │  │
  │  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘   │  │
  │  │           │                    │                    │            │  │
  │  │           ▼                    ▼                    ▼            │  │
  │  │  ┌─────────────────────────────────────────────────────────────┐ │  │
  │  │  │     Log Files (in project's .claude-agent/<slug>/logs/)     │ │  │
  │  │  │                    (persisted via $HOME mount)              │ │  │
  │  │  └─────────────────────────────────────────────────────────────┘ │  │
  │  └──────────────────────────────────┬───────────────────────────────┘  │
  │                                     │                                  │
  │                      Unix Socket (/tmp/coding-harness-daemon.sock)     │
  │                                     │                                  │
  │  ┌──────────────────────────────────▼───────────────────────────────┐  │
  │  │                      TUI (python -m tui.main)                    │  │
  │  │                         (ephemeral, can restart)                 │  │
  │  │                                                                  │  │
  │  │  Commands to daemon:           Views:                            │  │
  │  │    • list - get all agents       • Agent list (status)           │  │
  │  │    • start - spawn new agent     • Log viewer (tail log files)   │  │
  │  │    • stop - terminate agent      • HITL checkpoint dialogs       │  │
  │  │    • status - get agent info     • Session phase indicator       │  │
  │  │    • remove - delete agent       • Git branch/status             │  │
  │  │                                                                  │  │
  │  │  ┌────────────────────────────────────────────────────────────┐  │  │
  │  │  │              Can exit freely (Ctrl+C, q, Esc)              │  │  │
  │  │  │           Daemon + agents continue in background           │  │  │
  │  │  └────────────────────────────────────────────────────────────┘  │  │
  │  └──────────────────────────────────────────────────────────────────┘  │
  │                                                                        │
  ├────────────────────────── Persistence Layer ───────────────────────────┤
  │                                                                        │
  │  Named Volume: ${container}-data → /app/.data/                         │
  │    • daemon_state.json (agent registry, status, config)                │
  │                                                                        │
  │  Bind Mount: $HOME:$HOME                                               │
  │    • Project files (.claude-agent/<slug>-<hash>/)                      │
  │    • Log files (logs/*.log)                                            │
  │    • Milestone state (.gitlab_milestone.json)                          │
  │    • HITL checkpoints (.hitl_checkpoint.json)                          │
  │    • Workspace info (.workspace_info.json)                             │
  │                                                                        │
  │  Bind Mount: /tmp:/tmp                                                 │
  │    • Daemon socket (ephemeral, recreated on start)                     │
  │    • Daemon PID file                                                   │
  │                                                                        │
  └────────────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- **TUI can exit/restart** - Agents keep running in daemon
- **Logs persist** - Written to project's `.claude-agent/` directory
- **True SSH-like experience** - Reconnect to see agent output
- **No state file hacks** - Daemon IS the state

**Workflow:**
1. Start agents in TUI
2. Press `Q` to quit TUI (agents keep running in daemon)
3. Press `Enter` to restart TUI
4. TUI syncs with daemon, shows running agents

**Detach vs Quit:**
- `Q` - Quit TUI, agents keep running in daemon
- `Ctrl+P, Ctrl+Q` - Detach from container entirely (container + daemon + agents keep running)
- `Ctrl+C` - Stop container (kills daemon and all agents)

### Persistence Model

The harness uses a two-tier persistence model with Docker volumes:

```
PROJECT DIRECTORY (bind mount via $HOME:$HOME):
project/.claude-agent/{spec-slug}-{hash}/    ← LOCAL ONLY, never pushed to GitLab
├── .workspace_info.json      # Spec config, branch, auto-accept setting
├── .gitlab_milestone.json    # Milestone ID, issue list, progress, session_files tracking
├── .hitl_checkpoint_log.json # All checkpoint history with decisions
├── app_spec.txt              # Copy of original specification
└── logs/                     # Agent execution logs (project-scoped)
    └── agent_1-20241223-120530.log

DAEMON STATE (named Docker volume per container):
/app/.data/                   # Inside container, persisted via volume
└── daemon_state.json         # Daemon's agent registry (for reconnect)
```

> **Important:** The `.claude-agent/` directory is **local working storage** for agents.
> It is never pushed to GitLab and should be in your `.gitignore`. Agents read/write
> these files directly via filesystem tools, not through git.

**What survives container restart:**
| Data | Location | Persists? | Notes |
|------|----------|-----------|-------|
| Checkpoint history | Project `.claude-agent/` | ✅ Yes | Bind mount to host |
| Milestone state | Project `.claude-agent/` | ✅ Yes | Bind mount to host |
| Agent logs | Project `.claude-agent/logs/` | ✅ Yes | Bind mount to host |
| Daemon state | Docker volume | ✅ Yes | Volume `{container}-data` |
| Auto-accept pref | Project `.workspace_info.json` | ✅ Yes | Bind mount to host |

**Docker volumes (per-container):**
```bash
docker volume ls                          # List all volumes
# Volumes are named: coding-harness-data, coding-harness-2-data, etc.
docker volume inspect coding-harness-data # View volume details
docker volume rm coding-harness-data      # Delete volume (reset daemon state)
```

**Atomic saves:** All JSON files use atomic write (temp file + rename) to prevent corruption if the process crashes mid-write.

**Alternative Approaches (from n8n Deep Agents):**

Other harness implementations use different persistence strategies:
- **Research artifacts table** - Intermediate findings stored in DB, later synthesized
- **Lock mechanisms** - Timestamp-based locking prevents multiple workers on same task
- **Progressive summarization** - Older work is compressed more than recent work
- **Staged processing** - Retrieval → Synthesize → Write with separate artifact storage

This harness uses GitLab as its "artifact staging area"—comments on issues preserve research findings, and the issue itself tracks state. This trades some flexibility for simpler infrastructure (no separate database required).

**External Task Tracking (Linear/Jira/Asana):**

Cole Medin's Linear integration pattern shows an alternative: use external task management for remote monitoring. Benefits include:
- Monitor agent progress from mobile or any browser
- Edit task descriptions to inject human feedback mid-run
- Real-time task board updates (no page refresh needed)
- Multiple observers without SSH access

From the live stream, Cole demonstrated watching Linear update in real-time as agents completed tasks—no page refresh required. The agent makes parallel MCP calls to Linear for efficiency (creating multiple issues in batches rather than sequentially). Each issue gets a description that humans can edit mid-run, and agents pick up those edits when they start the next task.

**The meta issue pattern:** A special "project tracker" issue serves as the handoff artifact between sessions. Each agent comments on this issue with a summary of what it completed, which tasks it marked done, and context for the next session. This replaces the local `claude-progress.txt` file from Anthropic's quickstart.

**Why external task management over local files:** Local JSON files work fine for single-machine runs, but can't be easily monitored remotely. Cole's insight: "If we're going to have these agents run for a really long time, we need observability... we can't interrupt it because it's set up as a process to run in the background. So we need some way to communicate to it."

**Token efficiency insight (from Coriolis via Ray):** External task management via MCP is more token-efficient than reading/writing local JSON files. You hand off task management to the MCP server rather than having the agent parse and rewrite JSON. Agents are trained on human workflows—they naturally understand systems like Linear, making the integration feel native rather than forced.

This harness achieves similar observability through GitLab's native issue tracking—the trade-off is GitLab-specific vs. tool-agnostic integration.

### TUI Workflow

1. **Select Repository** - Choose a directory containing a git repository
2. **Select Spec File** - Pick the specification file to implement
3. **Select Target Branch** - Choose which branch to target for the merge request
4. **Agent Options** - Configure behavior:
   - **File-only mode** - Use local JSON files instead of GitLab for tracking
   - **Skip MR creation** - Stop after coding without creating a merge request
5. **Advanced Options** - Configure iterations and other settings
6. **Agent Execution** - Watch the agent work with HITL checkpoints for your approval

### Writing a Specification File

A good specification file clearly describes what you want built. You don't have to write it from scratch—Cole Medin demonstrated a **template + brain dump workflow**:

1. Give an LLM (Claude Opus 4.5 recommended) an existing app spec as a template
2. Provide your own "brain dump"—a rough description of what you want to build
3. Ask it to combine them into a structured spec following the template format
4. Iterate with follow-up questions to fill in missing details

This approach reduces the mental burden of spec writing while ensuring comprehensive coverage. The spec doesn't need to be perfect—the initializer agent will break it into granular tasks regardless of spec detail level.

**Example spec structure:**

```text
# Feature: User Authentication System

## Overview
Add a complete authentication system with login, registration, and session management.

## Requirements
- Email/password login and registration
- Session persistence across browser refreshes
- Password reset via email
- OAuth support for Google and GitHub

## Acceptance Criteria
- Users can register with email and password
- Users can log in and are redirected to dashboard
- Sessions persist for 7 days
- Password reset emails are sent within 30 seconds
- OAuth buttons appear on login page

## Technical Notes
- Use bcrypt for password hashing
- Store sessions in Redis
- Follow existing auth patterns in the codebase
```

### Issue Creation & Enrichment

The harness uses a two-phase approach to issue creation:

**Phase 1: Spec-Faithful Issue Creation**

Initial issues are created by transcribing the specification directly—no embellishment, no research:

```
Spec Detail Level    →    Issue Detail Level
─────────────────────────────────────────────
Detailed spec        →    Detailed issues
Vague spec           →    Vague issues
Spec silent on X     →    Issue omits X
```

The issue template adapts to whatever the spec provides:
- **Summary** - Transcribed requirement (spec's exact language)
- **Requirement Details** - Listed only if spec provides them
- **Technical Notes** - Included only if spec mentions constraints
- **User-Facing Behavior** - Included only if spec describes UX
- **Test Criteria** - From spec, or minimal generic criteria
- **Open Questions** - Flags ambiguities for later enrichment

**Phase 2: Optional Deep Enrichment**

After issues are created, the LLM judges which need enrichment. Human selects which to enrich (can override LLM). Selected issues get comprehensive enhancement:

| Step | Action | GitLab API |
|------|--------|------------|
| A | Deep Research | Context7 (library docs), grep (codebase), web search |
| B | Update Title | `update_issue` - make action-oriented |
| C | Replace Description | `update_issue` - full implementation guide |
| D | Add Research Comment | `create_issue_note` - raw findings |
| E | Add Dependencies Comment | `create_issue_note` - cross-issue links |
| F | Add Labels | `update_issue` - `enriched`, `complexity-X`, `time-estimate-Xh` |

**Enriched description includes:**
- Implementation guide (step-by-step with code patterns)
- API/interface specifications
- Codebase patterns to follow (with `file:line` references)
- Acceptance criteria (checkbox format)
- Test plan (table format)
- Time estimate and risk assessment

**Non-enriched issues** proceed to implementation with original spec-faithful description.

### HITL Checkpoints

The harness pauses at 8 checkpoint types for human review. This reflects the **autonomy balance** principle: agents should be as autonomous as possible, but with easy injection points for human validation at critical decisions. The goal is strategic checkpoints, not constant interruption.

**Checkpoint types:**

| Checkpoint | Description | Quick Approve (Y) | Quick Reject (N) |
|------------|-------------|-------------------|------------------|
| `project_verification` | Validates project setup and configuration | Standard approve | Standard reject |
| `spec_to_issues` | Reviews proposed breakdown of spec into issues | Standard approve | Standard reject |
| `issue_enrichment` | Reviews issues flagged for additional context | Auto-select LLM-recommended issues | Skip all (empty list) |
| `regression_approval` | Handles detected regressions during development | Default to "fix_now" | ⚠️ Blocked - requires explicit action |
| `issue_selection` | Confirms which issue to work on next | Use recommended issue | Standard reject |
| `issue_closure` | Reviews completed implementation before closing | Standard approve | Standard reject |
| `mr_phase_transition` | Gate before entering merge request creation | Standard approve | Standard reject |
| `mr_review` | Reviews final merge request before creation | Standard approve | Standard reject |

**Checkpoint Output Format:**

Each checkpoint displays a consistent structure in the agent logs:

```
================================================================
HITL CHECKPOINT: [CHECKPOINT NAME]
================================================================

WHAT HAPPENED:
  ✓ What LLM already completed
  ✓ What LLM verified
  → What human needs to decide

[CONTEXT-SPECIFIC DETAILS]

┌─────────────────────────────────────────────────────────────┐
│  IF APPROVED:                                               │
│    → What happens next                                      │
│                                                             │
│  IF REJECTED:                                               │
│    → What happens instead                                   │
└─────────────────────────────────────────────────────────────┘

================================================================
  TUI SHORTCUTS:
    [Y] or [1]  →  APPROVE
    [X] or [0]  →  REJECT
================================================================
```

**Keyboard Shortcuts:**
- `Y` or `1` - Quick approve (with checkpoint-specific defaults)
- `N` or `0` - Quick reject (blocked for `regression_approval`)
- `R` - Open full review screen
- `Esc` - Cancel/dismiss

### Auto-Accept Mode

When auto-accept is enabled (`--auto-accept` or toggle with `A` key), checkpoints are automatically approved with intelligent defaults:

| Checkpoint | Auto-Accept Behavior |
|------------|---------------------|
| `issue_enrichment` | Uses LLM judgment to auto-select issues needing enrichment |
| `regression_approval` | Defaults to "fix_now" action |
| `issue_selection` | Uses the recommended issue from context |
| Others | Standard automatic approval |

**Per-Agent Toggle:** Each agent independently tracks its auto-accept preference. Press `A` in the TUI to toggle for the selected agent. The `[AUTO]` indicator shows when enabled.

### Quality Assurance & Guardrails

**Why this matters for harnesses:** With 95% per-step reliability, 20 steps = 36% system reliability. The only way to run agents for hours is aggressive self-validation at every step. These guardrails are what make long-running execution possible:

#### Before Starting Work (Coding Agent)
- **Dead code detection** - Checks for unused imports, variables, and arguments (via project's linter)
- **Test suite execution & repair** - Runs project's test suite; fixes any failing tests before proceeding
- **Git log review** - Checks previous commits for context on multi-session issues
- **Feature regression testing** - Puppeteer-based verification of completed features

#### During Implementation
- **Unit test creation (mandatory)** - Writes tests for all new functions, endpoints, and classes
- **Test framework detection** - Auto-detects pytest, Jest, Vitest, Go testing, or Cargo test
- **Coverage requirements** - 1 happy path + 1 edge case per function, 1 success + 1 error per endpoint

#### Before Issue Closure
- **Post-implementation regression check** - Re-run test suite, spot-check previous features
- **Build & quality gate** - All linting, formatting, and type checks must pass
- **Git status verification** - Ensure clean working tree before checkpoint

#### Before MR Creation
- **Full test suite execution** - All tests must pass
- **Comprehensive regression check** - Test ALL completed features in milestone
- **MR existence verification** - Confirm MR was actually created on GitLab with retries

#### Test Repair Loop
When tests fail, the agent follows a structured repair process:
1. Read the test to understand what it's testing
2. Diagnose: outdated test, implementation bug, or flaky test
3. Fix appropriately (update expectation, fix code, or add deterministic waits)
4. Re-run to verify fix
5. After 3 failed attempts, skip with documented reason and create bug issue

#### GitLab API Reliability
- **Retry wrapper** - Exponential backoff for all GitLab API calls that modify data
- **Issue creation verification** - Confirm all issues were created successfully
- **State file validation** - Atomic writes prevent data corruption

**Guardrails** *(hard stops that prevent compounding errors)*:
- Never implement new features if test suite is failing due to agent changes
- All tests must pass (or be explicitly skipped with reason) before new work
- Do NOT create issue_closure checkpoint if quality checks fail
- Stop MR creation if ANY regression is found
- Do NOT mark checkpoint complete until MR is verified on GitLab

These aren't suggestions—they're circuit breakers. Without them, a harness running for 24 hours would accumulate errors until the codebase is unusable.

**Security Boundaries:**

The Claude Agent SDK enables fine-grained control over what agents can do:
- **Directory isolation** - Agents can only operate within the project directory
- **Command filtering** - Dangerous bash commands (rm -rf, kill self, etc.) are blocked via hooks
- **Tool allowlists** - Only approved tools (read, write, bash, MCP) are available
- **Sandboxed execution** - Agents run in controlled subprocess environments

Anthropic's quickstart repository includes a security hook that validates bash commands before execution—a pattern worth studying for production harnesses.

## Architecture

Three levels of detail: [Overview](#overview) (L1) → Component (L2) → [Runtime](#runtime-architecture) (L3)

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TUI (tui/)                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │  Repo   │→│  Spec   │→│ Branch  │→│ Quality │→│ Options │→│  Running  │  │
│  │ Screen  │ │ Screen  │ │ Screen  │ │ Screen  │ │ Screen  │ │ (logs+ckpt│  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────────┘  │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ daemon socket
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                           Daemon (agent/daemon/)                            │
│                     manages agent subprocesses + state                      │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Initializer  │ ────────▶ │    Coding     │ ────────▶ │  MR Creation  │
│    Agent      │           │    Agent      │           │    Agent      │
│               │           │    (loop)     │           │               │
│ • Verify proj │           │ • Pick issue  │           │ • Sync branch │
│ • Create issue│           │ • Implement   │           │ • Final tests │
│ • Enrich      │           │ • Test+verify │           │ • Create MR   │
│ • Make branch │           │ • Close issue │           │ • Verify MR   │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        └───────────────────────────┴───────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                         MCP Servers (Integration)                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ GitLab  │  │Context7 │  │ SearxNG │  │Puppeteer│  │  Files  │           │
│  │ issues  │  │lib docs │  │ search  │  │ browser │  │ quality │           │
│  │   MRs   │  │         │  │         │  │  tests  │  │  gates  │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Checkpoint Flow

*When each HITL checkpoint occurs. Details in [HITL Checkpoints](#hitl-checkpoints) table.*

```
INITIALIZER                    CODING (per issue)              MR CREATION
───────────                    ──────────────────              ───────────
    │                               │                              │
    ▼                               ▼                              ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ project_verify  │──┐       │ issue_selection │──┐       │ mr_phase_trans  │
└─────────────────┘  │       └─────────────────┘  │       └─────────────────┘
                     │              │              │              │
┌─────────────────┐  │              ▼              │              ▼
│ spec_to_issues  │──┤        (implement)         │       ┌─────────────────┐
└─────────────────┘  │              │              │       │   mr_review     │
                     │              ▼              │       └─────────────────┘
┌─────────────────┐  │       ┌─────────────────┐  │              │
│ issue_enrichment│──┘       │ regression_appr │  │              ▼
└─────────────────┘          └─────────────────┘  │         (create MR)
        │                           │              │
        ▼                           ▼              │
   (create branch)           ┌─────────────────┐  │
                             │ issue_closure   │──┘
                             └─────────────────┘
                                    │
                                    ▼
                              (next issue)
```

### Component Overview

| Directory | Purpose |
|-----------|---------|
| `agent/` | Core agent logic, prompts, HITL system, Claude API client |
| `tui/` | Textual UI screens, terminal widget, event handling |
| `common/` | Shared types, utilities, configuration |
| `.claude/` | Claude Code configuration (settings, skills, agents, commands) |

## Development

### Code Quality

The coding harness uses a **pluggable code quality skill system**. Code quality commands are defined in skill presets rather than hardcoded, allowing any language or tooling to be used.

**For this project:** See `.claude/skills/code-quality.md` for the specific commands used.

### Project Structure

```
coding-harness/
├── agent/
│   ├── __init__.py        # Package exports
│   ├── cli.py             # CLI entry point (python -m agent.cli)
│   ├── core/              # Core agent logic
│   │   ├── __init__.py
│   │   ├── orchestrator.py  # Main agent loop
│   │   ├── client.py        # Claude SDK client
│   │   └── hitl.py          # HITL checkpoints
│   ├── daemon/            # Background daemon
│   │   ├── __init__.py
│   │   ├── __main__.py      # Module entry (python -m agent.daemon)
│   │   ├── server.py        # Daemon process
│   │   └── client.py        # TUI client
│   ├── prompts/           # Prompt templates
│   │   ├── __init__.py      # Loader functions
│   │   └── templates/       # Markdown templates
│   └── skills/            # Agent skills
│       └── code-quality/
│           └── presets/     # Language-specific presets
├── tui/
│   ├── __init__.py
│   ├── app.py             # Main Textual app (connects to daemon)
│   ├── events.py          # Custom event types
│   ├── log_terminal.py    # Log file tailing widget
│   ├── main.py            # Entry point
│   └── screens/           # TUI screen components
├── common/
│   ├── __init__.py
│   ├── types.py         # Shared type definitions
│   └── utils.py         # Utility functions
├── .claude/             # Claude Code configuration
├── .env.example         # Environment template
├── Dockerfile           # Docker image definition
├── docker-entrypoint.sh # Container entrypoint script
├── .dockerignore        # Docker build exclusions
├── CLAUDE.md           # AI assistant instructions
├── requirements.txt    # Python dependencies
├── ruff.toml           # Linting configuration
├── pyrightconfig.json  # Type checking configuration
└── start.sh            # Entry point script (Docker + native)
```

**Runtime directories (created at runtime, not in repo):**
- `.data/` - Daemon state in native mode (`daemon_state.json`). Docker mode uses a named volume instead.
- `project/.claude-agent/` - Agent workspace created in target projects (see [Persistence Model](#persistence-model))

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Docker not found" | Install Docker or use `./start.sh --native` |
| Container exits immediately | Rebuild with `./start.sh --build` |
| Can't see files in container | Your home directory is mounted - use absolute paths |
| "GitLab token invalid" | Verify token has scopes: `api`, `read_api`, `read_repository`, `write_repository` |
| "Claude API error" | Check `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` is set correctly |
| "No .git folder" | Select a directory that is a git repository |
| Agent seems stuck | Check terminal output - likely waiting for HITL checkpoint approval |
| "Permission denied" on start.sh | Run `chmod +x start.sh` |
| Python version error | Ensure Python 3.11+ is active in your virtual environment |
| Agent logs not showing | Logs are in project's `.claude-agent/{spec}/logs/` - check file permissions |
| Daemon not starting | Check if socket exists at `/tmp/coding-harness-daemon.sock` |
| TUI says "Daemon not running" | Stale socket from previous container - rebuild with `./start.sh --build` |
| "could not read Password" git error | **Docker:** Rebuild with `./start.sh --build` to get auto-credentials. **Native:** See [Git Authentication](#git-authentication) section |
| Git fetch/pull fails in container | Ensure `GITLAB_PERSONAL_ACCESS_TOKEN` is set in `.env` - it's used for git credentials in Docker |

## FAQ

**Q: Do I need Docker?**
A: No, you can use `./start.sh --native` to run with a local Python virtual environment. However, native mode doesn't persist agents - they stop when you quit the TUI. For long-running tasks, use Docker.

**Q: Can I run multiple containers?**
A: Yes! Each new `./start.sh` creates a container named `coding-harness`, `coding-harness-2`, etc.

**Q: How do I keep agents running when I disconnect?**
A: In Docker mode: press `Q` to quit TUI - agents continue in daemon. Reconnect with `./start.sh --connect` or press Enter after restarting. Use `Ctrl+P, Ctrl+Q` to detach entirely. In native mode: agents stop when TUI exits (no persistence).

**Q: Can I use this without GitLab?**
A: Yes! Enable **file-only mode** in the TUI's Agent Options screen or use `"file_only_mode": true` in JSON specs. This stores milestones and issues in local JSON files instead of GitLab. Note: Git operations still use GitLab MCP for pushing commits.

**Q: Can I skip merge request creation?**
A: Yes! Enable **skip MR creation** in the TUI's Agent Options screen or use `"skip_mr_creation": true` in JSON specs. The agent will stop after coding completes and keep all changes on the feature branch without creating an MR.

**Q: What's the difference between file-only mode and skip MR creation?**
A: They're independent options:
- **File-only mode** - Changes where issue/milestone tracking happens (GitLab vs local JSON files)
- **Skip MR creation** - Changes whether an MR is created at the end (can be used with or without GitLab tracking)
You can use either or both together.

**Q: What Claude models are supported?**
A: Default is `claude-opus-4-5-20251101`. You can use other models by setting `CLAUDE_MODEL`.

**Q: Can I run multiple specs at once?**
A: Yes! Use JSON mode with multiple spec objects in the array.

**Q: How do I skip human approval?**
A: Use `--auto-accept` flag, but this removes human oversight - use carefully.

**Q: Can I use a different coding assistant (not Claude)?**
A: The architecture is portable but not implemented. During the live stream, community members confirmed OpenCode + Ollama works for local models (Qwen 3, Kimi K2). Porting requires replacing Claude Agent SDK calls with equivalent SDK (Codex SDK, OpenCode SDK, AMP SDK). The prompts and artifacts pattern transfers directly.

**Q: Will I hit rate limits running for 24 hours?**
A: It varies. Cole Medin ran Opus 4.5 for 24 hours on the $200/month Max plan without limits, but others report hitting limits quickly. Behavior seems to vary by account and region. Mitigation: toggle between Claude Code, Codex, and OpenCode to distribute load.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run code quality checks (see `.claude/skills/code-quality.md` for commands)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

[License type to be determined]
