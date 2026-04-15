# Project Guide for AI Assistants

This document guides AI assistants on how to navigate and work with this project.

## Project Overview

**What this project does:** A toolkit for declarative GitHub Organization governance. It manages Org-level Teams (create/update/delete), syncs Team membership (add Users to Teams), and assigns Teams to Repositories with specific permission roles (admin/maintain/push/pull). The workflow is: define desired state in TSV files or Python code -> compute delta against current GitHub state -> preview (plan mode) or apply changes.

**Key modules:**
- `gh_org_gov/client.py` - Authenticated GitHub client (PyGithub REST + GraphQL)
- `gh_org_gov/team_def.py` - Pure data types: `TeamDef`, `ExistingTeamDef`, TSV loader
- `gh_org_gov/team.py` - Team sync engine: `plan_sync()` (pure logic) + `sync_teams()` (API calls)
- `gh_org_gov/constants/` - Enums for repository roles, TSV column names

**Project type:** Python package

## Core Configuration Files

### Tool & Dependency Management
- `mise.toml` - Task runner and tool version management (Python 3.12, uv, claude)
- `pyproject.toml` - Python dependencies and package metadata
- `.venv/` - Virtual environment directory (created by uv)

Use `mise ls python --current` to see the exact Python version in use.

### CI/CD & Testing
- `.github/workflows/main.yml` - GitHub Actions CI workflow
- `codecov.yml` + `.coveragerc` - Code coverage reporting (codecov.io)
- `.readthedocs.yml` - Documentation hosting (readthedocs.org)

### Documentation
- `docs/source/` - Sphinx documentation source files
- `docs/source/conf.py` - Sphinx configuration

## Development Workflow

### Task Management
List all available tasks:
```bash
mise tasks ls
```

Run a specific task:
```bash
mise run ${task_name}
```

**Key tasks:**
- `inst` - Install all dependencies using uv (fast package manager)
- `cov` - Run unit tests with coverage report
- `build-doc` - Build Sphinx documentation

For complete task reference, run `mise run list-tasks` to generate `.claude/mise-tasks.md`.

### Testing Philosophy
This project uses **pytest** with a special pattern that allows running individual test files as standalone scripts.

**Example:** See `tests/test_api.py` - the `if __name__ == "__main__":` block demonstrates this pattern. It runs pytest as a subprocess with coverage tracking for the specific module, enabling quick isolated testing during development.

## Working with This Project

**Approach:**
1. Don't load entire files unnecessarily - read specific files only when needed
2. Use task commands (`mise run`) instead of direct tool invocation
3. Follow the testing pattern when creating new test files
4. Reference configuration files for specific settings rather than assuming defaults

**Tools in use:**
- **mise-en-place** - Development tool management
- **uv** - Fast Python package management
- **pytest** - Unit testing framework
- **sphinx** - Documentation generation
