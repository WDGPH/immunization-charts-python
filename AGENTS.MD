# Agent Development Guidelines

## Philosophy: Simplification First

**Pre-v1.0:** No backward compatibility constraints. Question every class, module, and abstraction: "Is this worth its weight?" Favor simple code over extensibility. Use dicts and native Python structures freely. Colocate utilities in the step that uses them; only truly reused functions belong in `utils.py`. No argument parsers per file—interaction patterns are fixed (see Workflow).

## Configuration (parameters.yaml)

Organize by pipeline step under headers like `# Step 3: Generating QR Codes`. Add parameters to the appropriate step section (never create new top-level sections). Use dot notation (`qr.enabled`, `qr.payload_template`) and snake_case. Document in YAML comments, not README.

Validate: `uv run python -c "import yaml; yaml.safe_load(open('config/parameters.yaml'))"`

## Testing Requirements

- **Required**: Adding/modifying functionality, configuration options, error handling
- **Optional**: Docs-only changes, non-behavior-preserving refactors

Create `test_<module_name>.py` in `tests/`. Use test classes and test happy path + edge cases + error cases. Run with: `uv run pytest`

## Code Style

**All imports at top**, organized: future → stdlib → third-party → local. Example:
```python
from __future__ import annotations
import json
import yaml
from .config_loader import load_config
```

Use type hints, f-strings, docstrings, dataclasses. Avoid wildcard imports.

## Documentation (README)

Update when **wrapping up features** only. Put parameter docs in `parameters.yaml` comments. Update README for: new steps, behavior changes, architecture decisions.

## Using `uv`

Setup: `uv sync` (or `uv sync --group dev` for tests)

**Run pipeline:** `uv run viper <input.xlsx> <en|fr>`

**Run tests:**
```bash
uv run pytest                              # all tests
uv run pytest tests/test_file.py -v        # specific file
uv run pytest -k "pattern" --tb=short       # matching pattern
uv run pytest --cov=scripts tests/ -x       # coverage, stop on fail
```

## Workflow

1. **Plan** code/architecture
2. **Implement** with imports at top, type hints, docstrings
3. **Test** in `tests/` directory (`uv run pytest`)
4. **Configure** in `parameters.yaml` step sections with comments
5. **Document** README only when feature complete
