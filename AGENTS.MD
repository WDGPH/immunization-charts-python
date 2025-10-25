# Agent Development Guidelines

## Philosophy: Simplification First

**Pre-v1.0:** No backward compatibility constraints. Question every class, module, and abstraction: "Is this worth its weight?" Favor simple code over extensibility. Use dicts and native Python structures freely. Colocate utilities in the step that uses them; only truly reused functions belong in `utils.py`. No argument parsers per file—interaction patterns are fixed (see Workflow).

## Package Structure

The main package is `scripts/`, containing the 9-step pipeline orchestrator and supporting modules. This is a deliberate architectural choice—**do not refactor into a different package structure** without explicit guidance. All entry points (`viper` CLI) and imports (`from scripts import ...`) depend on this naming. The module organization follows pipeline steps 1–9, not functional categories.

## Dependency Management

**Tight control via `uv` lockfile, not runtime fallbacks.** Dependencies are pinned in `uv.lock`. Write code for the specific, tested versions in that lockfile—not for theoretical version compatibility. Document version requirements in `pyproject.toml` only when necessary. **Do not add runtime fallbacks** (e.g., try PyPDF method A, fallback to method B) to support multiple versions. If a dependency needs a version bump, update `pyproject.toml`, run `uv sync`, test, and commit the new lockfile. The lockfile is the single source of truth.

## Core Standards (Reference These)

This project maintains authoritative standards in focused documents. Before coding, review:

- **Testing strategy & organization:** `docs/TESTING_STANDARDS.md` (unit/integration/e2e layers, markers, patterns)
- **Code analysis procedures:** `docs/CODE_ANALYSIS_STANDARDS.md` (dead code detection, duplication, real-world significance)
- **Configuration management:** Comments in `config/parameters.yaml` (parameters organized by pipeline step)

## Configuration (parameters.yaml)

Organize by pipeline step under headers like `# Step 3: Generating QR Codes`. Add parameters to the appropriate step section (never create new top-level sections). Use dot notation (`qr.enabled`, `qr.payload_template`) and snake_case. Document inline in YAML.

Validate: `uv run python -c "import yaml; yaml.safe_load(open('config/parameters.yaml'))"`

## Code Style

**All imports at top**, organized: future → stdlib → third-party → local. Example:
```python
from __future__ import annotations
import json
import yaml
from .config_loader import load_config
```

Use type hints, f-strings, docstrings, dataclasses. Avoid wildcard imports. See `docs/CODE_ANALYSIS_STANDARDS.md` for docstring depth and real-world significance guidance.

## Code Quality & Pre-commit Hooks

**Setup:** One-time initialization to enable automatic code checks on every commit:
```bash
uv sync --group dev                 # Install pre-commit (includes pytest, pytest-cov)
uv run pre-commit install           # Initialize git hooks
```

**Manual checks anytime:**
```bash
uv run pre-commit run --all-files   # Run ruff linting and formatting on all files
```

The pre-commit hook (configured in `.pre-commit-config.yaml`) runs automatically on each `git commit`:
- **`ruff check --fix`**: Lint issues (auto-fixes when possible)
- **`ruff format`**: Code formatting (black-like style)

If either check fails, your commit is blocked until issues are resolved. This ensures consistent code quality across all contributions.

## Running Tests (Quick Reference for AI Agents)

**Setup:** `uv sync --group dev` (one-time, installs pytest and testing dependencies)

**Run pipeline:** `uv run viper <input.xlsx> <en|fr>`

**Run tests:**
```bash
uv run pytest                                      # all tests
uv run pytest -m unit                              # unit only (fast, ~2s)
uv run pytest -m "not e2e"                         # skip E2E (fast feedback)
uv run pytest tests/e2e/ -v                        # only E2E tests
uv run pytest tests/test_file.py::TestClass::test_name -v  # specific test
```

**Coverage report:**
```bash
uv run pytest --cov=scripts --cov-report=html     # generates htmlcov/index.html
```

See `docs/TESTING_STANDARDS.md` for test organization, markers, and patterns.

## E2E Test Pitfalls

When writing E2E tests for this project:

**Path Constraint (Critical):**
- E2E tests MUST run in **project context**, not pytest `tmp_path`
- Reason: Typst subprocess requires absolute paths relative to project root (`generate_notices.py` uses `_to_root_relative()`)
- Solution: Use `project_root` fixture, place test files in `project_root / "input"`, use `yield` for cleanup
- Incorrect: `subprocess.run(..., cwd=str(tmp_path), ...)` ❌
- Correct: `subprocess.run(..., cwd=str(project_root), ...)` ✅

**Configuration Override Pattern:**
- Feature flags (QR, encryption, batching) are tested by modifying `config/parameters.yaml`
- Pattern: load YAML → modify key → write → run test → try-finally restore original
- Example: See `tests/e2e/test_full_pipeline.py::test_pipeline_with_qr_disabled()`
- This tests real config parsing, not mocked behavior

**Test Fixtures:**
- Use project-aware fixtures for input/output (not tmp dirs)
- See `docs/TESTING_STANDARDS.md` → "E2E Test Patterns for Immunization Pipeline" for examples
- Input fixture creates test Excel in `project_root / "input"`, yields path, cleans up after test

## Key Realizations for Efficient Development

**Unit test coverage doesn't tell the full story.** The orchestration layer (`run_pipeline.py`) has low unit coverage because tests mock internal steps (fast feedback). E2E tests provide integration verification. Don't panic at low unit coverage numbers—trace call sites and check E2E tests first.

**Defensive code and error handling are features, not bloat.** Edge case handling in date parsing, error paths for malformed data, and validation exist because real-world data is messy. When you see broad try/except or defensive checks, verify they serve a real purpose before removing them.

**Optional features (Steps 7-9) have different testing expectations.** Encryption, batching, and cleanup are conditional based on configuration. They'll have lighter test coverage than core steps 1-6, and that's acceptable. Focus testing effort on the critical path first.

**The test architecture trades unit speed for E2E confidence.** Fast unit tests (2s) catch logic bugs in isolation. E2E tests (50s) verify orchestration and integration. This is a deliberate design, not a gap to fix.

## Workflow

1. **Understand** project deeply (code patterns, data flow, existing duplication)—use docs + functional analysis (`grep`, trace usages)
2. **Plan** code/architecture around this understanding
3. **Implement** with imports at top, type hints, significant docstrings
4. **Test** in `tests/` directory (`uv run pytest`)
5. **Configure** in `parameters.yaml` step sections with comments
6. **Document** README only when feature complete. For standards & procedures, update the appropriate reference doc (TESTING_STANDARDS.md, CODE_ANALYSIS_STANDARDS.md). Archive detailed analysis into standards or docstrings rather than creating standalone reports.

## Communication with AI Agents

- **Summarize findings directly in conversation**, don't output to temporary files
- **Integrate learnings into documentation** rather than creating standalone analysis documents
- **Final step of work:** Archive insights into standards docs, function docstrings, or module comments for efficient future collaboration 
