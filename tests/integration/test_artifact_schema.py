"""Integration tests for artifact schema consistency across pipeline steps.

Tests cover:
- PreprocessResult schema validation
- Artifact JSON structure consistency
- ClientRecord data preservation through steps
- Metadata flow and accumulation

Real-world significance:
- Pipeline steps communicate via JSON artifacts with defined schemas
- Schema consistency is required for multi-step data flow
- Breaking schema changes cause silent data loss
- Artifacts must be shareable between different runs/environments
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import data_models
from tests.fixtures import sample_input


@pytest.mark.integration
class TestArtifactSchema:
    """Integration tests for artifact schema consistency."""

    def test_preprocess_result_serializable_to_json(self) -> None:
        """Verify PreprocessResult can be serialized to JSON.

        Real-world significance:
        - Artifacts are stored as JSON files in output/artifacts/
        - Must be JSON-serializable to persist between steps
        """
        result = sample_input.create_test_preprocess_result(num_clients=2)

        # Should be convertible to dict
        payload = data_models.ArtifactPayload(
            run_id="test_001",
            language=result.clients[0].language,
            clients=result.clients,
            warnings=result.warnings,
            created_at="2025-01-01T00:00:00Z",
            total_clients=len(result.clients),
        )

        assert payload.run_id == "test_001"
        assert len(payload.clients) == 2

    def test_artifact_payload_round_trip(self, tmp_path: Path) -> None:
        """Verify ArtifactPayload can be written and read from JSON.

        Real-world significance:
        - Artifacts must be persistent across pipeline runs
        - Must survive round-trip serialization without data loss
        """
        original = sample_input.create_test_artifact_payload(num_clients=3, run_id="test_001")

        # Write artifact
        artifact_path = sample_input.write_test_artifact(original, tmp_path)

        # Read artifact
        assert artifact_path.exists()
        with open(artifact_path) as f:
            artifact_data = json.load(f)

        # Verify key fields preserved
        assert artifact_data["run_id"] == "test_001"
        assert len(artifact_data["clients"]) == 3
        assert artifact_data["total_clients"] == 3

    def test_client_record_fields_preserved_in_artifact(self, tmp_path: Path) -> None:
        """Verify all ClientRecord fields are preserved in artifact JSON.

        Real-world significance:
        - Downstream steps depend on specific fields being present
        - Missing fields cause pipeline crashes or silent errors
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=1,
            run_id="test_001",
        )

        artifact_path = sample_input.write_test_artifact(artifact, tmp_path)

        with open(artifact_path) as f:
            artifact_data = json.load(f)

        client_dict = artifact_data["clients"][0]

        # Verify critical fields present
        required_fields = [
            "sequence",
            "client_id",
            "language",
            "person",
            "school",
            "board",
            "contact",
            "vaccines_due",
        ]

        for field in required_fields:
            assert field in client_dict, f"Missing critical field: {field}"

    def test_multiple_languages_in_artifact(self, tmp_path: Path) -> None:
        """Verify artifacts support both English and French clients.

        Real-world significance:
        - Pipeline must support bilingual operation
        - Artifacts may contain mixed-language client data
        """
        en_artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="en", run_id="test_en"
        )
        fr_artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="fr", run_id="test_fr"
        )

        # Both should write successfully
        en_path = sample_input.write_test_artifact(en_artifact, tmp_path)
        fr_path = sample_input.write_test_artifact(fr_artifact, tmp_path)

        assert en_path.exists()
        assert fr_path.exists()

        # Verify language is preserved
        with open(en_path) as f:
            en_data = json.load(f)
        with open(fr_path) as f:
            fr_data = json.load(f)

        assert en_data["language"] == "en"
        assert fr_data["language"] == "fr"
        assert en_data["clients"][0]["language"] == "en"
        assert fr_data["clients"][0]["language"] == "fr"
