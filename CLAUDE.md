# Code Quality Workflow

**After making code changes, run code quality checks.**

## Quick Command

```bash
# Run this after every code edit
.venv/bin/ruff check . --fix && .venv/bin/ruff format . && .venv/bin/pyright
```

This auto-fixes linting issues, formats code, and checks types.

## Core Principles

1. **Context-driven analysis** - Gather project standards before analyzing code
2. **Evidence-based findings** - Every issue needs concrete examples with file:line references
3. **Project standards first** - Prioritize project conventions over generic best practices
4. **Security awareness** - Check for OWASP Top 10 vulnerabilities
5. **Actionable recommendations** - Suggestions must be specific with exact locations
6. **Minimum quality target** - Maintain 9.1/10 quality score

## Quality Dimensions (11 Total)

| Dimension | Weight | Key Checks |
|-----------|--------|------------|
| Code Organization | 12% | File structure, module cohesion |
| Naming Quality | 10% | Descriptive names, consistent conventions |
| Scope Correctness | 10% | Public/private visibility, unused elements |
| Type Safety | 12% | Type hints, return types, null safety |
| No Dead Code | 8% | Unused imports, variables, functions |
| No Duplication (DRY) | 8% | No copy-paste, extracted helpers |
| Error Handling | 10% | Specific exceptions, proper cleanup |
| Modern Patterns | 5% | Language idioms, current syntax |
| SOLID Principles | 10% | SRP, OCP, LSP, ISP, DIP |
| Security (OWASP) | 10% | No injection, input validation |
| Cognitive Complexity | 5% | Understandable code, limited nesting |

## Key Quality Checks

### SOLID Principles
- **SRP**: One reason to change per class/function
- **OCP**: Open for extension, closed for modification
- **LSP**: Subclasses must be substitutable
- **ISP**: No unused interface implementations
- **DIP**: Depend on abstractions, not concretions

### DRY/KISS/YAGNI
- **DRY**: No duplicate code blocks (>3 lines similar)
- **KISS**: No over-engineered solutions or unnecessary abstractions
- **YAGNI**: No unused parameters or speculative generality

### Security (OWASP)
- No SQL/command injection (no string concatenation in queries)
- No hardcoded credentials/secrets
- Input validation at entry points
- No eval/exec with untrusted data

### Performance
- No O(n^2) where O(n log n) is possible
- No N+1 query problems
- Resource cleanup (close file handles, connections)

## Skills Reference

For detailed commands, checklists, and metrics:

- **Code Quality Commands & Principles:** See `.claude/skills/code-quality/SKILL.md`
  - Complete analysis checklists
  - All linting, formatting, and type checking commands
  - Advanced metrics (Halstead, ABC, coupling)
  - Troubleshooting and configuration info

## Configuration Files

- `ruff.toml` - Linting and formatting rules (120 char line limit)
- `pyrightconfig.json` - Type checking rules
- `.pylintrc` - IDE warnings configuration

**Don't modify these** unless necessary - they affect the entire team.

## IDE + CLI Integration

Your IDE and CLI use the **same configuration files**:
- **Pyright** (`pyrightconfig.json`) - Type checking in both IDE and CLI
- **Pylint** (`.pylintrc`) - IDE warnings only
- **Ruff** (`ruff.toml`) - CLI only (no IDE extension available)

This means:
- Red squiggles (IDE) = Type errors from Pyright - **Must fix**
- Yellow squiggles (IDE) = Warnings from Pylint - Should fix
- CLI checks = Same errors as IDE

## Before Committing

Always run the quick command above before committing. All checks must pass.

```bash
# If checks pass, commit
git add .
git commit -m "Your message"
```

---

For detailed instructions, troubleshooting, and all available commands, see `.claude/skills/code-quality/SKILL.md`.
