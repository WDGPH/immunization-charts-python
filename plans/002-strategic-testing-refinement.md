# Strategic testing refinement plan (pre-1.0)

## Goals
- Reduce test suite size and maintenance cost while preserving confidence in the 9-step pipeline.
- Keep one full E2E path per language (English + French) as smoke coverage.
- Trim duplicate or low-signal tests by tracing each test to a specific contract or behavior.
- Preserve step boundary contracts and critical failure modes.

## Constraints and standards
- Follow markers and layering rules in [pytest.ini](pytest.ini) and [docs/TESTING_STANDARDS.md](docs/TESTING_STANDARDS.md).
- Keep tests aligned with step isolation and deterministic IO per [AGENTS.MD](AGENTS.MD).
- Avoid introducing new standalone docs; this plan is the canonical working doc for this initiative.

## Inventory and mapping workflow
### 1) Build the test inventory
- Enumerate all tests under [tests](tests) and tag each file with:
  - Category: unit / integration / e2e
  - Primary pipeline step(s): 1–9
  - Primary module(s): [pipeline](pipeline), [templates](templates)
  - Cost profile: fast / moderate / slow / flaky
  - Main contract(s): e.g., schema validation, QR payload formatting, Typst compile, PDF validation

### 2) Map tests to source contracts
- For each test file, link to the code it covers and the contract it asserts.
- Use step structure (Steps 1–9) and cross-cutting modules:
  - Orchestrator entry point: [pipeline/orchestrator.py](pipeline/orchestrator.py)
  - Steps: [pipeline](pipeline) modules (preprocess, generate_qr_codes, generate_notices, compile_notices, validate_pdfs, encrypt_notice, bundle_pdfs, cleanup)
  - Config, data models, enums, translation helpers, templates
- Produce a trace table: `test file → contract → source link`.

### 3) Classify each test
Use the rubric below to tag each test file for keep/trim/merge/replace.

**Keep**
- Unique contract coverage with high impact (schema validation, deterministic IO, config parsing errors, step boundary validation).
- Only path covering a failure mode that is expensive to discover later.

**Trim/Merge**
- Repeats the same contract in multiple files.
- Verifies formatting details already asserted in helper tests.
- Duplicates coverage via both integration and unit tests for identical logic.

**Replace**
- Slow tests that can be replaced by a targeted unit contract test.
- Tests that depend on full Typst/PDF pipeline when a mocked or stubbed smoke check suffices.

## Subagent analysis plan
Run subagents with explicit scope, producing structured findings for each test file and code path. Use four subagents total.

### Subagent A — Unit tests audit
- Scope: [tests/unit](tests/unit)
- Output:
  - List of unit files with covered contracts and source links.
  - Candidate duplicates or low-signal tests.
  - Suggested merges or removals.

### Subagent B — Integration tests audit
- Scope: [tests/integration](tests/integration)
- Output:
  - Contract tests that represent step boundaries.
  - Overlap with unit tests or E2E tests.
  - Candidates for replacement with lighter unit tests.

### Subagent C — E2E tests audit
- Scope: [tests/e2e](tests/e2e)
- Output:
  - Keep only one full end-to-end path per language (English + French).
  - Identify expensive fixtures and brittle outputs.
  - Propose a minimal “smoke” variant for each language if full compile is too costly.

### Subagent D — Coverage and trace analysis
- Scope: coverage reports and step/module tracing
- Output:
  - Coverage hotspots: high coverage redundancy.
  - Coverage gaps in critical modules (e.g., config loader, validation boundaries).
  - Recommendations for coverage-based trimming.

## Coverage and trace workflow
1. Run targeted coverage for each category:
   - Unit: `uv run pytest -m unit --cov=pipeline --cov-report=term-missing`
   - Integration: `uv run pytest -m integration --cov=pipeline --cov-report=term-missing`
   - E2E: `uv run pytest -m e2e --cov=pipeline --cov-report=term-missing`
2. Generate HTML coverage once for a full view:
   - `uv run pytest --cov=pipeline --cov-report=html`
   - Review [htmlcov/index.html](htmlcov/index.html)
3. For each test file, note which source lines are exclusively covered by that test. Keep tests that uniquely cover important contracts.

## Decision criteria matrix
Use this matrix for each test file:

| Test file | Category | Contract(s) | Source link(s) | Cost | Duplicates? | Keep/Trim/Replace | Rationale |
|---|---|---|---|---|---|---|---|

### Contract priority (high → low)
1. Orchestrator step ordering & CLI validation.
2. Step boundary validation (inputs/outputs on disk).
3. Schema validation and normalization.
4. QR payload formatting and URL encoding.
5. Template rendering correctness (language-specific).
6. PDF compilation & validation (smoke only in E2E).
7. Encryption and bundling (smoke only in E2E).
8. Cleanup and output preparation.

## Output actions
- Maintain one E2E test per language (English, French) as smoke tests.
- Reduce integration tests to a minimal set of step-boundary contract checks.
- Trim unit tests that validate formatting already covered by higher-level contracts.
- Consolidate duplicated fixtures across [tests/conftest.py](tests/conftest.py) and [tests/fixtures](tests/fixtures).

## Deliverables
1. Completed test inventory table with links to source contracts.
2. Marked keep/trim/replace list per file.
3. Coverage summary (unit/integration/e2e).
4. Final trimmed test plan with the minimal E2E (EN + FR) and reduced integration suite.

## Notes and decisions
- Keep one E2E pipeline run per language as requested (English + French).
- Prioritize deterministic, step-isolated tests aligned with pre-1.0 simplification.
- Any removed tests must have their contract covered elsewhere or deemed low-risk.
