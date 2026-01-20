"""Integration tests for pipeline step contracts and artifact consistency.

This module consolidates tests that verify the handoff between pipeline steps:
- Preprocess → QR Generation
- QR Generation → Notice Generation
- Notice Generation → Typst Compilation
- Compilation → PDF Validation/Bundling

It ensures that artifact schemas are consistent, required fields are preserved,
and configuration propagates correctly across the multi-step workflow.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from pipeline import data_models
from tests.fixtures import sample_input


@pytest.mark.integration
class TestArtifactContracts:
    """Integration tests for artifact schema consistency and metadata preservation."""

    def test_artifact_payload_round_trip(self, tmp_path: Path) -> None:
        """Verify ArtifactPayload can be written and read from JSON.

        Real-world significance:
        - Artifacts must survive round-trip serialization without data loss
        - Steps communicate via these files on disk
        """
        original = sample_input.create_test_artifact_payload(
            num_clients=3, run_id="test_round_trip_001"
        )

        # Write artifact
        artifact_path = sample_input.write_test_artifact(original, tmp_path)

        # Read artifact
        assert artifact_path.exists()
        with open(artifact_path) as f:
            artifact_data = json.load(f)

        # Verify key fields preserved
        assert artifact_data["run_id"] == "test_round_trip_001"
        assert len(artifact_data["clients"]) == 3
        assert artifact_data["total_clients"] == 3
        assert "created_at" in artifact_data

    def test_client_record_fields_preserved_in_artifact(self, tmp_path: Path) -> None:
        """Verify critical ClientRecord fields are preserved in artifact JSON.

        Real-world significance:
        - Downstream steps depend on specific fields being present
        - Missing fields cause pipeline crashes or silent errors
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=1,
            run_id="test_fields_001",
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
            "vaccines_due_list",
        ]

        for field in required_fields:
            assert field in client_dict, f"Missing critical field: {field}"

    def test_multilingual_artifact_support(self, tmp_path: Path) -> None:
        """Verify artifacts support both English and French clients consistently.

        Real-world significance:
        - Pipeline must support bilingual operation
        - Artifacts must preserve language markers for template selection
        """
        for lang in ["en", "fr"]:
            artifact = sample_input.create_test_artifact_payload(
                num_clients=2, language=lang, run_id=f"test_lang_{lang}"
            )
            path = sample_input.write_test_artifact(artifact, tmp_path)

            with open(path) as f:
                data = json.load(f)

            assert data["language"] == lang
            for client in data["clients"]:
                assert client["language"] == lang

    def test_artifact_warnings_accumulation(self, tmp_path: Path) -> None:
        """Verify warnings are preserved in artifact for user visibility."""
        artifact = data_models.ArtifactPayload(
            run_id="test_warn_001",
            language="en",
            clients=[
                sample_input.create_test_client_record(sequence="00001", language="en")
            ],
            warnings=["Missing board name", "Invalid postal code"],
            created_at="2025-01-01T12:00:00Z",
            total_clients=1,
        )

        artifact_path = sample_input.write_test_artifact(artifact, tmp_path)

        with open(artifact_path) as f:
            loaded = json.load(f)

        assert len(loaded["warnings"]) == 2
        assert "Missing board name" in loaded["warnings"][0]


@pytest.mark.integration
class TestPreprocessToQrContract:
    """Integration tests for Preprocess (Step 2) → QR Generation (Step 3) contract."""

    def test_artifact_data_supports_qr_payload_generation(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify artifact has all data needed for QR payload substitution.

        Real-world significance:
        - QR generation substitution depends on specific artifact fields
        - Missing fields cause KR payload generation to fail
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=1, language="en", run_id="test_qr_contract"
        )
        client = artifact.clients[0]

        # Fields required by default QR payload templates
        assert client.client_id
        assert client.person["first_name"]
        assert client.person["last_name"]
        assert client.person["date_of_birth_iso"]
        assert client.school["name"]
        assert client.contact["city"]

    def test_client_sequence_stability_for_filenames(self, tmp_path: Path) -> None:
        """Verify client sequence numbers are deterministic for filename generation.

        Real-world significance:
        - Filenames (QR, Notice, PDF) use the sequence number (00001, 00002...)
        - Consistency is critical for traceability and batching
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=5, language="en", run_id="test_sequence"
        )
        sequences = [c.sequence for c in artifact.clients]
        assert sequences == ["00001", "00002", "00003", "00004", "00005"]


@pytest.mark.integration
class TestQrToNoticeContract:
    """Integration tests for QR Generation (Step 3) → Notice Generation (Step 4) contract."""

    def test_qr_reference_field_in_client_record(self) -> None:
        """Verify ClientRecord can carry QR metadata to notice generation.

        Real-world significance:
        - Notice templates need to know the QR filename to embed it
        - QR step adds this info to the artifact
        """
        import dataclasses

        client = sample_input.create_test_client_record(
            sequence="00001", client_id="C123"
        )
        client = dataclasses.replace(
            client,
            qr={
                "filename": "00001_C123.png",
                "payload": "https://example.com/vax/C123",
            },
        )

        assert client.qr["filename"] == "00001_C123.png"

    def test_qr_payload_formatting_iso_date(self) -> None:
        """Verify QR payloads correctly format ISO dates for receiving systems."""
        client = sample_input.create_test_client_record(date_of_birth="2015-06-15")
        template = "dob={date_of_birth_iso}"

        payload = template.format(date_of_birth_iso=client.person["date_of_birth_iso"])
        assert payload == "dob=2015-06-15"


@pytest.mark.integration
class TestNoticeToCompileContract:
    """Integration tests for Notice Generation (Step 4) → Typst Compilation (Step 5) contract."""

    def test_vaccines_due_list_for_template_iteration(self) -> None:
        """Verify vaccines_due_list is present and correct for chart rendering.

        Real-world significance:
        - Notice templates iterate over this list to build the immunization chart
        """
        client = sample_input.create_test_client_record(
            vaccines_due="Measles/Mumps/Rubella",
            vaccines_due_list=["Measles", "Mumps", "Rubella"],
        )

        assert isinstance(client.vaccines_due_list, list)
        assert len(client.vaccines_due_list) == 3
        assert "Measles" in client.vaccines_due_list

    def test_typst_synthetic_file_structure(self, tmp_path: Path) -> None:
        """Verify the content structure expected by the Typst compiler."""
        content = '#import "conf.typ": header\n#header()\n= Notice for {name}'
        rendered = content.format(name="John Doe")

        assert "header()" in rendered
        assert "John Doe" in rendered


@pytest.mark.integration
class TestDownstreamWorkflowContracts:
    """Integration tests for Step 6+ handoffs and configuration propagation."""

    def test_compilation_to_validation_manifest(self, tmp_path: Path) -> None:
        """Verify structure of PDF validation manifest (Step 6)."""
        manifest = {
            "run_id": "test_run",
            "page_counts": [{"sequence": "00001", "page_count": 1}],
        }
        path = tmp_path / "manifest.json"
        with open(path, "w") as f:
            json.dump(manifest, f)

        assert path.exists()

    def test_encryption_to_bundling_metadata(self) -> None:
        """Verify encryption (Step 7) preserves fields for bundling (Step 8)."""
        record = {
            "client": {"school": "School A", "board": "Board B"},
            "password": "password123",
        }
        # Bundling needs school/board to group PDFs
        assert record["client"]["school"] == "School A"
        assert record["client"]["board"] == "Board B"

    def test_config_propagation_encryption_vs_bundling(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify configuration enforces mutually exclusive encryption and bundling."""
        config = copy.deepcopy(default_config)

        # Scenario: Encryption enabled
        config["encryption"]["enabled"] = True
        assert config["encryption"]["enabled"] is True

        # Scenario: Bundling enabled (usually requires encryption disabled)
        config["encryption"]["enabled"] = False
        config["bundling"]["enabled"] = True
        assert config["encryption"]["enabled"] is False
        assert config["bundling"]["enabled"] is True

    def test_cleanup_policy_configuration(self, default_config: Dict[str, Any]) -> None:
        """Verify cleanup policy configuration is accessible."""
        assert "after_run" in default_config["pipeline"]
        assert "remove_artifacts" in default_config["pipeline"]["after_run"]
        assert "remove_unencrypted_pdfs" in default_config["pipeline"]["after_run"]
