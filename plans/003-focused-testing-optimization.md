# Focused testing optimization plan (pre-1.0, Round 2)

## Goals
- Further reduce low-signal tests while safeguarding pipeline contracts.
- Prioritize failures that impact users (pipeline stops, incorrect PDFs, invalid configs).
- Minimize IO-heavy checks by shifting them to integration/contract tests where possible.
- Keep the test suite fast and deterministic for pre-1.0 development.

## Current baseline (post-round-1)
- 443 total tests, 100% passing.
- E2E: single file covering EN + FR smoke paths.
- Integration: consolidated contract tests plus error propagation and translation flow.
- Unit: consolidated config/orchestrator tests and trimmed data models.

## Round-2 focus areas

### 1) Contract-driven test inventory (line-level)
**Objective:** identify tests that do not assert unique contracts.
- Build a contract map for the pipeline steps (1–9), mapping each to:
  - Input file format
  - Output file format
  - Critical invariants (e.g., PDF count equals client count, QR payloads match IDs)
- For each test file, label which invariant(s) it protects.
- Remove tests that only repeat a previously-validated invariant unless they are cheaper or more targeted.

**Deliverable:** `tests/contract_map.md` (short, single table). Avoid creating new standalone docs; integrate into [docs/TESTING_STANDARDS.md](docs/TESTING_STANDARDS.md) as a new appendix if preferred.

---

### 2) Replace formatting tests with snapshot-free invariants
**Objective:** remove tests that only validate formatting details and replace them with resilient, minimal assertions.
- For tests in [tests/unit/test_generate_notices.py](tests/unit/test_generate_notices.py) and [tests/unit/test_preprocess.py](tests/unit/test_preprocess.py):
  - Replace string equality checks with structural assertions (presence of keys, stable ordering rules, required text fragments).
  - Avoid exact formatted output if not contract-critical.

**Example heuristic:**
- Replace: “Exact rendered field equals …”
- With: “Rendered field includes required tokens and preserves stable ordering.”

---

### 3) Shrink the orchestration surface
**Objective:** focus [tests/unit/test_orchestrator.py](tests/unit/test_orchestrator.py) on the CLI contract and minimal step sequencing.
- Keep tests validating:
  - CLI arguments
  - Run ID generation
  - Step order (one happy-path)
  - Failure propagation rules
- Remove tests that mock internal step behavior already validated in integration (e.g., per-step warnings and debug log patterns).

---

### 4) Split “feature toggles” into 1–2 representative contracts
**Objective:** avoid exhaustive toggle combinations.
- Keep only one integration test per toggle cluster:
  - QR enabled/disabled
  - Encryption enabled/disabled
  - Bundling enabled/disabled
- Ensure each test confirms:
  - Step is skipped or executed
  - Output artifact set matches expectation
- Remove tests that validate every combination.

---

### 5) Trim data model coverage to unique serialization logic
**Objective:** ensure model tests only cover custom logic.
- Verify only:
  - schema serialization/deserialization
  - any custom validation logic
- Remove any remaining generic dataclass checks.

---

### 6) Reduce integration test volume with “contract pack” fixtures
**Objective:** standardize inputs across integration tests to reduce duplication.
- Create a shared fixture (in [tests/conftest.py](tests/conftest.py)) that produces:
  - a minimal preprocess artifact
  - a minimal QR artifact
  - a minimal notice artifact
- Replace repeated fixtures in [tests/integration/test_pipeline_contracts.py](tests/integration/test_pipeline_contracts.py).

---

### 7) Introduce a “fast-smoke” pipeline mode (if feasible)
**Objective:** reduce E2E runtime while preserving end-to-end confidence.
- In the E2E run config, ensure:
  - encryption disabled
  - bundling disabled
  - minimal client count (already 3)
  - optional steps disabled where possible
- Verify that this is captured in [tests/e2e/test_full_pipeline.py](tests/e2e/test_full_pipeline.py).

---

## Execution checklist
1. Build contract map and tag each test file.
2. Identify and remove low-signal formatting checks.
3. Trim `test_orchestrator.py` to core CLI/sequence behaviors.
4. Collapse feature toggle permutations into single representative tests.
5. Consolidate fixtures in `tests/conftest.py`.
6. Ensure E2E remains minimal (EN + FR only).
7. Run `uv run pytest` and `uv run pytest -m integration`.

## Success criteria
- Tests remain under ~425 total, still 100% passing.
- No reduction in contract coverage (step input/output boundaries still asserted).
- E2E runtime stays within 10–15 seconds for full run.
- Documentation reflects all remaining tests in [docs/TESTING_STANDARDS.md](docs/TESTING_STANDARDS.md).

## Notes
- No new standalone docs unless required; prefer updates in [docs/TESTING_STANDARDS.md](docs/TESTING_STANDARDS.md).
- Focus on maintainability and clarity over raw coverage numbers.
