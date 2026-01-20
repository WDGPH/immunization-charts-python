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

## Status: Completed (January 20, 2026)

The strategic testing refinement is complete. The test suite has been streamlined as follows:
- **Unit suite reduced:** Merged redundant config, template loading, and language validation tests. Removed `test_enums.py`. Trimmed `test_data_models.py`.
- **Integration suite consolidated:** Created `test_pipeline_contracts.py` as the canonical handoff check. Removed redundant config-behavior checks.
- **Translation logic moved:** Pure unit-level translation/normalization tests relocated to the unit suite.
- **E2E preserved:** High-level smoke tests for English and French are retained.

**Suite Metrics:**
- Total tests: 443 (previously 513)
- Passing: 100%

## Decision criteria matrix
Here is the assessment of the refined test suite:

| Test file | Category | Contract(s) | Source link(s) | Cost | Duplicates? | Keep/Trim/Refine | Rationale |
|---|---|---|---|---|---|---|---|
| `tests/unit/test_config_loader.py` | Unit | Config loading & validation | [pipeline/config_loader.py](pipeline/config_loader.py) | Fast | No | Keep | Consolidated config lifecycle (from `test_config_validation.py`). |
| `tests/unit/test_data_models.py` | Unit | Dataclass integrity | [pipeline/data_models.py](pipeline/data_models.py) | Fast | Yes | Trimmed | Removed generic property checks. |
| `tests/unit/test_preprocess.py` | Unit | Normalization/Sorting | [pipeline/preprocess.py](pipeline/preprocess.py) | Mod | No | Keep | Core business logic with high complexity. |
| `tests/unit/test_generate_notices.py` | Unit | Notice Generation | [pipeline/generate_notices.py](pipeline/generate_notices.py) | Fast | No | Keep | Consolidated with template discovery. |
| `tests/unit/test_orchestrator.py` | Unit | Pipeline Orchestration | [pipeline/orchestrator.py](pipeline/orchestrator.py) | Fast | Yes | Keep | Unified orchestration testing (from `test_run_pipeline.py`). |
| `tests/integration/test_pipeline_contracts.py` | Integration | Step IO schema & flow | [pipeline/orchestrator.py](pipeline/orchestrator.py) | Mod | No | Keep | Canonical handoff check. |
| `tests/integration/test_error_propagation.py` | Integration | Philosophy | [pipeline/orchestrator.py](pipeline/orchestrator.py) | Mod | No | Keep | Fail-fast vs recovery contract. |
| `tests/integration/test_custom_templates.py` | Integration | Dynamic loading | [pipeline/generate_notices.py](pipeline/generate_notices.py) | Mod | No | Keep | PHU customization contract. |
| `tests/integration/test_translation_integration.py` | Integration | Translation flow | [pipeline/translation_helpers.py](pipeline/translation_helpers.py) | Mod | No | Keep | Core localized data flow. |
| `tests/e2e/test_full_pipeline.py` | E2E | Full pipeline (EN/FR) | [pipeline/orchestrator.py](pipeline/orchestrator.py) | Slow | No | Keep | Essential smoke tests for both languages. |

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

## Audit Findings

### Subagent B — Integration tests audit (Findings)
The audit of [tests/integration](tests/integration) is complete.

#### 1. Covered Contracts & Modules
Integration tests cover the following multi-step handoffs:
- **Preprocess -> QR Gen -> Notice Gen:** Covered by [tests/integration/test_pipeline_stages.py](tests/integration/test_pipeline_stages.py) and [tests/integration/test_artifact_schema_flow.py](tests/integration/test_artifact_schema_flow.py). Verifies field availability in the intermediate JSON artifact used across steps 2, 3, and 4.
- **Notice Gen -> Compilation:** Covered by [tests/integration/test_custom_templates.py](tests/integration/test_custom_templates.py). Verifies dynamic module loading and asset resolution during steps 4 and 5.
- **Compilation -> Validation -> Encryption -> Bundling:** Covered by [tests/integration/test_pipeline_stages.py](tests/integration/test_pipeline_stages.py). Verifies metadata preservation and file presence for steps 6, 7, and 8.
- **Fail-Fast vs Recovery Philosophy:** Covered by [tests/integration/test_error_propagation.py](tests/integration/test_error_propagation.py). Verifies orchestrator contracts for critical vs optional steps.
- **Translation-Normalization Chain:** Covered by [tests/integration/test_translation_integration.py](tests/integration/test_translation_integration.py). Verifies the flow from raw data to translated template context.

#### 2. Overlap & Redundancy
- **Brittle Data Assertions:** [tests/integration/test_artifact_schema.py](tests/integration/test_artifact_schema.py) and [tests/integration/test_artifact_schema_flow.py](tests/integration/test_artifact_schema_flow.py) are largely redundant with each other and with unit tests for [pipeline/data_models.py](pipeline/data_models.py).
- **Low-Value Config Checks:** [tests/integration/test_config_driven_behavior.py](tests/integration/test_config_driven_behavior.py) asserts key presence in dictionaries, which is a unit-level concern for [pipeline/config_loader.py](pipeline/config_loader.py) and provides little integration signal.
- **Pure Unit Logic:** [tests/integration/test_translation_integration.py](tests/integration/test_translation_integration.py) contains several tests for disease normalization that should be pure unit tests for [pipeline/translation_helpers.py](pipeline/translation_helpers.py).

#### 3. Recommended Minimal Set
To maintain confidence while reducing maintenance, the following changes are proposed:
- **Keep** [tests/integration/test_error_propagation.py](tests/integration/test_error_propagation.py) (Philosophy/Orchestration contract).
- **Keep** [tests/integration/test_custom_templates.py](tests/integration/test_custom_templates.py) (Dynamic loading/PHU customization contract).
- **Consolidate** [tests/integration/test_pipeline_stages.py](tests/integration/test_pipeline_stages.py), [tests/integration/test_artifact_schema.py](tests/integration/test_artifact_schema.py), and [tests/integration/test_artifact_schema_flow.py](tests/integration/test_artifact_schema_flow.py) into a single `test_pipeline_contracts.py` that focuses on disk-based handoffs.
- **Simplify** [tests/integration/test_translation_integration.py](tests/integration/test_translation_integration.py) to focus on the `preprocess` -> `context` boundary, moving pure string logic to unit tests.
- **Delete** [tests/integration/test_config_driven_behavior.py](tests/integration/test_config_driven_behavior.py).

## Notes and decisions
- Keep one E2E pipeline run per language as requested (English + French).
- Prioritize deterministic, step-isolated tests aligned with pre-1.0 simplification.
- Any removed tests must have their contract covered elsewhere or deemed low-risk.
