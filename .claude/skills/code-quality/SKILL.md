# Code Quality - Principles & Commands

This document covers code quality principles, analysis dimensions, and CLI commands for maintaining code quality in this Python project.

## Quick Command (Run After Every Edit)

```bash
# Auto-fix linting + format + type check
.venv/bin/ruff check . --fix && .venv/bin/ruff format . && .venv/bin/pyright
```

---

# Code Quality Principles

## Core Principles

1. **Context-driven analysis** - Always gather project standards before analyzing code
2. **Comprehensive element mapping** - Outline ALL code elements (functions, classes, variables, imports)
3. **Multi-dimensional quality assessment** - Evaluate across 11 quality dimensions
4. **Evidence-based findings** - Every quality issue must have concrete code examples with file:line references
5. **Project standards first** - Prioritize project conventions over generic best practices
6. **Security awareness** - Always check for OWASP Top 10 vulnerabilities
7. **Actionable recommendations** - Every suggestion must be specific with exact locations
8. **Minimum quality target** - Maintain 9.1/10 quality score across all dimensions

## Quality Dimensions (11 Total)

Score each dimension 1-10:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Code Organization | 12% | File structure, module cohesion, function/class placement |
| Naming Quality | 10% | Descriptive names, consistent conventions, no single-letter names |
| Scope Correctness | 10% | Public/private visibility, unused elements, proper encapsulation |
| Type Safety | 12% | Type hints, return types, generic usage, null safety |
| No Dead Code | 8% | Unused imports, variables, functions, unreachable code |
| No Duplication (DRY) | 8% | No copy-paste code, extracted helpers, parameterized functions |
| Error Handling | 10% | Specific exceptions, proper cleanup, no empty catch blocks |
| Modern Patterns | 5% | Language idioms, current syntax, efficient constructs |
| SOLID Principles | 10% | Single responsibility, open/closed, Liskov, interface segregation, DI |
| Security (OWASP) | 10% | No injection, proper auth, input validation, secure defaults |
| Cognitive Complexity | 5% | Understandable code, limited nesting, clear control flow |

**Target: 9.1/10 weighted average**

---

# Code Quality Analysis Checklist

## Phase 1: Context Gathering

Before analyzing code, gather project context:

- [ ] Read `CLAUDE.md` and `.claude/CLAUDE.md` for project-specific instructions
- [ ] Read `README.md` for project overview
- [ ] Check `.claude/skills/*.md` for project patterns
- [ ] Find files that import the target (consumers of its API)
- [ ] Find sibling files in same directory (for pattern consistency)
- [ ] Find test files for the target

## Phase 2: Code Element Extraction

Catalog ALL code elements:

### Imports
- Standard library, third-party, local imports
- Mark used/unused status with line numbers

### Globals/Constants
- Naming convention (SCREAMING_CASE for constants)
- Mutable global warnings

### Classes
- Base classes, decorators
- Class variables with visibility
- Instance variables from constructor
- Methods with visibility and call relationships

### Functions
- Visibility (public/private via underscore prefix)
- Parameters with types and defaults
- Return types and paths
- Local variables

### Type Definitions
- Type aliases, generics, protocols
- Data classes, enums

## Phase 3: Scope & Visibility Analysis

### Private Elements
For every element marked private (underscore prefix):
- Verify only used within its class/module
- Flag external access as violations

### Public Elements
For every public element:
- Track internal and external usage
- Recommend making private if not used externally

### Unused Elements
- Imports never referenced
- Variables assigned but not read
- Functions/methods never called
- Parameters never used
- Types only in their own definition

## Phase 4: Call Hierarchy Mapping

- Build call graph within file
- Identify entry points (not called by anything in file)
- Identify internal-only functions (called but not entry points)
- Flag orphaned code (defined but never called)
- Detect recursive and circular calls

---

# Code Smell Detection

## Complexity Issues

- [ ] Functions > 50 lines
- [ ] Cyclomatic complexity > 10
- [ ] Cognitive complexity > 15
- [ ] Nesting depth > 4
- [ ] Too many parameters (> 5)
- [ ] Too many return statements

### Cognitive Complexity Thresholds

| Score | Threshold | Interpretation |
|-------|-----------|----------------|
| 10 | 0-5 | Excellent - very easy to understand |
| 8-9 | 6-10 | Good - straightforward logic |
| 6-7 | 11-15 | Acceptable - consider simplifying |
| 4-5 | 16-25 | Poor - needs refactoring |
| 1-3 | 25+ | Critical - immediate attention required |

## Design Issues

- [ ] God class (too many responsibilities)
- [ ] Feature envy (method uses other class more than its own)
- [ ] Data class (only getters/setters, no behavior)
- [ ] Inappropriate intimacy (excessive coupling)
- [ ] Primitive obsession (overuse of primitives instead of objects)
- [ ] Long parameter list (> 3-4 params without object grouping)

## Naming Issues

- [ ] Single-letter names (except i,j,k in loops)
- [ ] Misleading names (name doesn't match behavior)
- [ ] Inconsistent naming style
- [ ] Names too similar

## Duplication

- [ ] Duplicate code blocks (>5 lines similar)
- [ ] Copy-paste patterns
- [ ] Logic that should be extracted

## Redundant Logic

- [ ] Redundant conditionals (identical branches)
- [ ] Unnecessary conditional expressions
- [ ] Magic numbers that should be constants

---

# SOLID Principles Violations

## Single Responsibility (SRP)
- [ ] Classes with multiple reasons to change
- [ ] Functions doing more than one thing
- [ ] Mixed abstraction levels in same function

## Open/Closed (OCP)
- [ ] Classes requiring modification for extension
- [ ] Switch/if-else chains that grow with new types
- [ ] Missing strategy/plugin patterns

## Liskov Substitution (LSP)
- [ ] Subclasses that change parent behavior unexpectedly
- [ ] Overridden methods with different contracts
- [ ] Type checks for specific subclasses

## Interface Segregation (ISP)
- [ ] Large interfaces forcing unused implementations
- [ ] Classes implementing methods they don't need

## Dependency Inversion (DIP)
- [ ] High-level modules depending on low-level details
- [ ] Missing abstractions/interfaces
- [ ] Concrete class instantiation in business logic

---

# DRY/KISS/YAGNI Violations

## DRY (Don't Repeat Yourself)
- [ ] Duplicate code blocks (>3 lines similar)
- [ ] Copy-paste logic that should be extracted
- [ ] Repeated magic numbers/strings
- [ ] Similar functions that could be parameterized

## KISS (Keep It Simple, Stupid)
- [ ] Over-engineered solutions
- [ ] Unnecessary abstractions
- [ ] Premature optimization
- [ ] Complex one-liners that should be expanded

## YAGNI (You Aren't Gonna Need It)
- [ ] Unused parameters kept "for future use"
- [ ] Dead feature flags
- [ ] Speculative generality
- [ ] Commented-out code blocks

---

# Best Practices

## Python Language Idioms

- [ ] Using concrete type checks instead of duck typing
- [ ] Mutable default arguments
- [ ] Catching all exceptions without specificity
- [ ] Not using context managers (with statements)
- [ ] Inefficient string building in loops

## Modern Python Features

- [ ] Could use pattern matching (Python 3.10+)
- [ ] Could use union types (X | Y instead of Union[X, Y])
- [ ] Old-style formatting instead of f-strings
- [ ] Not using dataclasses where appropriate

## Error Handling

- [ ] Catching too broad exceptions (bare except, Exception)
- [ ] Empty except blocks
- [ ] Not re-raising when appropriate
- [ ] Missing exception chaining (`from` clause)

## Resource Management

- [ ] File handles not closed properly (missing `with`)
- [ ] Database connections not closed
- [ ] Missing cleanup in finally blocks

---

# Security Patterns (OWASP-Aligned)

## Injection Vulnerabilities
- [ ] SQL injection risks (string concatenation in queries)
- [ ] Command injection (shell execution with unsanitized input)
- [ ] Path traversal (unsanitized file paths)

## Authentication & Session
- [ ] Hardcoded credentials/secrets
- [ ] Weak password handling
- [ ] Missing authentication checks

## Data Exposure
- [ ] Sensitive data in logs
- [ ] Secrets in source code
- [ ] Unencrypted sensitive data

## Input Validation
- [ ] Missing input validation at entry points
- [ ] Insufficient output encoding
- [ ] Regex DoS (ReDoS) patterns

## Dangerous Functions
- [ ] Dynamic code evaluation (eval, exec)
- [ ] Unsafe deserialization (pickle with untrusted data)

---

# Performance & Efficiency

## Memory Management
- [ ] Memory leaks from objects not released
- [ ] Excessive allocation in loops
- [ ] Large objects copied instead of referenced
- [ ] Unbounded caches without eviction

## Algorithm Efficiency
- [ ] O(n^2) or worse where O(n log n) possible
- [ ] Redundant computations that could be cached
- [ ] Nested loops that could be optimized

## Database & I/O
- [ ] N+1 query problems (queries in loops)
- [ ] Excessive database roundtrips
- [ ] Large file operations without streaming
- [ ] Synchronous I/O blocking main thread

---

# Concurrency & Thread Safety

- [ ] Shared mutable state without synchronization
- [ ] Race conditions on shared variables
- [ ] Non-atomic operations on shared data
- [ ] Promises/async not handled properly
- [ ] Missing error handling in async code

---

# Advanced Metrics

## Halstead Complexity

| Metric | Formula | Thresholds |
|--------|---------|------------|
| Volume (V) | N * log2(n) | <1000 good, 1000-8000 moderate, >8000 high |
| Difficulty (D) | (n1/2) * (N2/n2) | <10 easy, 10-20 moderate, >20 difficult |
| Effort (E) | D * V | <10000 low, 10000-100000 moderate, >100000 high |
| Bugs (B) | V / 3000 | <0.5 good, 0.5-2 moderate, >2 high risk |

## ABC Metrics (Assignment, Branch, Condition)

- **A** (Assignment Count): Variable assignments, mutations
- **B** (Branch Count): Function calls, method invocations
- **C** (Condition Count): if/else, switch, ternary, boolean logic
- **Magnitude**: sqrt(A^2 + B^2 + C^2) - Thresholds: <20 simple, 20-50 moderate, >50 complex

## Coupling Metrics

- **CBO** (Coupling Between Objects): 0-5 low, 6-10 moderate, >10 high
- **Ce** (Efferent coupling): Classes this class depends on
- **Ca** (Afferent coupling): Classes that depend on this class
- **LCOM** (Lack of Cohesion): 0-20% cohesive, 20-50% moderate, >50% should split

## Maintainability Index

| Score Range | Rating | Action |
|-------------|--------|--------|
| 85-100 | Highly Maintainable | No action needed |
| 65-84 | Moderately Maintainable | Monitor and improve |
| 40-64 | Difficult to Maintain | Plan refactoring |
| 0-39 | Unmaintainable | Urgent refactoring |

---

# Technical Debt Categories

- **Code debt**: Poor quality code (estimated hours to fix)
- **Design debt**: Architectural issues
- **Test debt**: Missing/inadequate tests
- **Documentation debt**: Missing/outdated docs

**Priority Matrix**: Impact (High/Med/Low) x Effort (High/Med/Low) = Priority (P1-P4)

---

# Project Standards Compliance

## Check Against Project Docs

- [ ] Required documentation format followed
- [ ] All public functions documented
- [ ] Type hints complete per project requirements
- [ ] Function naming matches project style
- [ ] Error handling follows project pattern
- [ ] Logging follows project pattern

## Cross-File Consistency

- [ ] Uses same patterns as imported modules
- [ ] API matches consumer usage patterns
- [ ] Structure matches similar sibling files
- [ ] Test patterns match project conventions

---

# CLI Commands

## Individual Commands

### Linting

```bash
# Check for issues
.venv/bin/ruff check .
.venv/bin/ruff check agent/
.venv/bin/ruff check tui/

# Auto-fix issues
.venv/bin/ruff check . --fix
.venv/bin/ruff check agent/ --fix

# Verify clean (no fixes)
.venv/bin/ruff check .
```

### Formatting

```bash
# Format all files
.venv/bin/ruff format .

# Format specific directory
.venv/bin/ruff format agent/
.venv/bin/ruff format tui/
```

**What ruff format does:**
- Breaks long lines (120 char limit)
- Fixes indentation/spacing
- Enforces double quotes
- Adds/removes trailing commas

### Type Checking

```bash
# Check all files
.venv/bin/pyright

# Check specific file
.venv/bin/pyright agent/agent.py
.venv/bin/pyright tui/app.py
```

## Targeted Rule Checking

```bash
# Find unused imports (F401), variables (F841), arguments (ARG)
.venv/bin/ruff check . --select F401,F841,ARG

# Auto-fix unused imports
.venv/bin/ruff check . --select F401 --fix

# Check import sorting only
.venv/bin/ruff check . --select I --fix

# Check for common bugs (flake8-bugbear)
.venv/bin/ruff check . --select B

# Check naming conventions
.venv/bin/ruff check . --select N
```

## Dead Code Detection

### Quick Dead Code Scan

```bash
# Find all dead code (unused imports, variables, arguments)
.venv/bin/ruff check . --select F401,F841,ARG

# Auto-fix safely removable dead code (unused imports only)
.venv/bin/ruff check . --select F401 --fix
```

### Ruff Dead Code Rules

| Rule | Description | Safe to Auto-Fix? |
|------|-------------|-------------------|
| F401 | Unused imports | Yes |
| F841 | Unused local variables | Review first |
| ARG001 | Unused function arguments | Review first |
| ARG002 | Unused method arguments | Review first |
| ARG003 | Unused class method arguments | Review first |
| ARG004 | Unused static method arguments | Review first |
| ARG005 | Unused lambda arguments | Review first |

### When to Use --fix

**Safe to auto-fix:**
- `F401` (unused imports): Always safe, removes clutter

**Review before fixing:**
- `F841` (unused variables): May indicate incomplete implementation
- `ARG*` (unused arguments): May be required for API compatibility

```bash
# Preview what --fix would change
.venv/bin/ruff check . --select F841,ARG --fix --diff

# Fix only after reviewing the diff
.venv/bin/ruff check . --select F841 --fix
```

### Optional: Vulture for Deeper Analysis

```bash
# Install vulture (if not already installed)
pip install vulture

# Run vulture on the codebase
vulture agent/ tui/ common/

# With confidence threshold (higher = fewer false positives)
vulture agent/ tui/ common/ --min-confidence 80
```

## Preview Changes (Diff Mode)

```bash
# Show diff of all auto-fixes
.venv/bin/ruff check . --fix --diff

# Preview formatting changes
.venv/bin/ruff format . --diff

# Check specific file changes
.venv/bin/ruff check agent/hitl.py --fix --diff
```

## Before Committing

```bash
# Complete pre-commit workflow
.venv/bin/ruff check . --fix && \
.venv/bin/ruff format . && \
.venv/bin/ruff check . && \
.venv/bin/pyright
```

If all checks pass, then commit:
```bash
git add .
git commit -m "Your message"
```

## Understanding Output

### Ruff Output

**Clean:**
```
All checks passed!
```

**Issues found:**
```
agent/agent.py:136:5: SIM108 Use ternary operator instead of if-else-block
Found 4 errors (3 fixable).
```
- Line format: `file:line:col: CODE Description`
- `3 fixable` = can auto-fix with `--fix`

### Pyright Output

Shows type errors that must be fixed:
- Missing type annotations
- None type errors
- Import errors
- Type mismatches

## Configuration Files

**Ruff:** `ruff.toml`
- Line length: 120
- Linting rules enabled
- CLI only (no IDE extension)

**Pyright:** `pyrightconfig.json`
- Type checking rules
- Used by both IDE and CLI

**Pylint:** `.pylintrc`
- IDE warnings only
- Configured to match Ruff (120 char)
- Not required for commits

### Enabled Rule Categories

Based on `ruff.toml`, these rule sets are active:

- **E/W** - pycodestyle (PEP 8 style violations)
- **F** - Pyflakes (unused imports, variables, undefined names)
- **I** - isort (import sorting/organization)
- **N** - pep8-naming (naming conventions)
- **UP** - pyupgrade (modernize Python syntax)
- **B** - flake8-bugbear (likely bugs and design problems)
- **C4** - flake8-comprehensions (better list/dict comprehensions)
- **SIM** - flake8-simplify (code simplification suggestions)

## Troubleshooting

### "Command not found: ruff"
```bash
# Use full path to venv
.venv/bin/ruff check .
```

### "Import could not be resolved"
Reload IDE (Cmd+Shift+P -> "Reload Window")

### Type errors
Fix by:
- Adding type annotations
- Checking for None before accessing
- Using `hasattr()` for attribute checks
- Adding type guards

### Long line warnings from Pylint
```bash
# Auto-fix with ruff format
.venv/bin/ruff format .
```

## Quick Status Check

```bash
# Check if tools are available
which .venv/bin/ruff
which .venv/bin/pyright

# Verify versions
.venv/bin/ruff --version
.venv/bin/pyright --version
```

## Reference

- **Ruff docs:** https://docs.astral.sh/ruff/
- **Ruff rules:** https://docs.astral.sh/ruff/rules/
- **Pyright docs:** https://github.com/microsoft/pyright
