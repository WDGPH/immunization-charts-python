"""Integration tests for artifact schema consistency across pipeline steps.

Tests cover multi-step artifact contracts:
- Preprocess output → QR generation input validation
- QR generation output file structure validation
- Notice generation input validation from preprocessed artifact
- Typst template structure validation
- QR payload generation and validation

Real-world significance:
- Pipeline steps communicate via JSON artifacts with defined schemas
- Schema consistency is required for multi-step data flow
- Missing or malformed data causes silent pipeline failure
- Artifacts must preserve all critical fields through processing
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from scripts import data_models
from tests.fixtures import sample_input


@pytest.mark.integration
class TestPreprocessToQrArtifactContract:
    """Integration tests for preprocess output → QR generation contract."""

    def test_preprocess_artifact_readable_by_qr_generation(
        self, tmp_test_dir: Path, config_file: Path
    ) -> None:
        """Verify preprocessed artifact has all fields required by QR generation.

        Real-world significance:
        - QR generation Step 3 depends on artifact schema from Step 2
        - Missing fields cause QR generation to crash silently or produce invalid data
        - Must preserve client_id, person data, contact, school info
        """
        # Create preprocessed artifact
        artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="en", run_id="test_qr_001"
        )
        artifact_dir = tmp_test_dir / "artifacts"
        artifact_dir.mkdir(exist_ok=True)

        artifact_path = sample_input.write_test_artifact(artifact, artifact_dir)

        # Load artifact as QR generation would
        with open(artifact_path) as f:
            loaded = json.load(f)

        # Verify all required fields for QR payload template
        for client in loaded["clients"]:
            assert "client_id" in client
            assert "person" in client
            assert "school" in client
            assert "contact" in client
            assert client["person"]["date_of_birth_iso"]  # Required for QR templates

    def test_qr_payload_template_placeholders_in_artifact(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify artifact data supports all QR payload template placeholders.

        Real-world significance:
        - QR template may use any of: client_id, name, date_of_birth_iso, school, city, etc.
        - Artifact must provide all fields that template references
        - Missing field causes QR payload generation to fail
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=1, language="en", run_id="test_qr_payload_001"
        )

        client = artifact.clients[0]

        # These come from person dict
        assert client.person["date_of_birth_iso"]
        assert client.person["first_name"]
        assert client.person["last_name"]

        # These come from school/board/contact
        assert client.school["name"]
        assert client.contact["city"]
        assert client.contact["postal_code"]
        assert client.contact["province"]
        assert client.contact["street"]  # street_address

    def test_artifact_client_sequence_preserved(self, tmp_test_dir: Path) -> None:
        """Verify client sequence numbers are deterministic and preserved.

        Real-world significance:
        - Sequence numbers (00001, 00002, ...) determine PDF filename
        - Must be consistent for reproducible batching
        - QR generation uses sequence in filenames
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=5, language="en", run_id="test_seq_001"
        )
        artifact_dir = tmp_test_dir / "artifacts"
        artifact_dir.mkdir()

        artifact_path = sample_input.write_test_artifact(artifact, artifact_dir)

        with open(artifact_path) as f:
            loaded = json.load(f)

        # Sequences should be ordered 00001, 00002, etc.
        sequences = [c["sequence"] for c in loaded["clients"]]
        assert sequences == ["00001", "00002", "00003", "00004", "00005"]

    def test_multilingual_artifact_preserves_language_in_clients(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify language is preserved in both artifact and individual clients.

        Real-world significance:
        - QR generation and notice generation need language to format dates
        - Downstream steps must know language to select proper templates
        - Mixed-language artifacts not supported; all clients same language
        """
        en_artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="en", run_id="test_lang_en"
        )
        fr_artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="fr", run_id="test_lang_fr"
        )

        artifact_dir = tmp_test_dir / "artifacts"
        artifact_dir.mkdir()

        en_path = sample_input.write_test_artifact(en_artifact, artifact_dir)
        fr_path = sample_input.write_test_artifact(fr_artifact, artifact_dir)

        with open(en_path) as f:
            en_data = json.load(f)
        with open(fr_path) as f:
            fr_data = json.load(f)

        # Artifact top-level language
        assert en_data["language"] == "en"
        assert fr_data["language"] == "fr"

        # Per-client language
        for client in en_data["clients"]:
            assert client["language"] == "en"
        for client in fr_data["clients"]:
            assert client["language"] == "fr"


@pytest.mark.integration
class TestNoticeToCompileArtifactContract:
    """Integration tests for notice generation → compilation contract."""

    def test_notice_generation_input_schema_from_artifact(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify artifact schema supports notice generation requirements.

        Real-world significance:
        - Notice generation Step 4 reads preprocessed artifact
        - Templates need: client name, DOB, vaccines_due, school, contact info
        - Missing fields cause template rendering to fail
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=1, language="en", run_id="test_notice_001"
        )

        client = artifact.clients[0]

        # Notice generation needs these fields for template rendering
        assert client.person["first_name"]
        assert client.person["last_name"]
        assert client.person["full_name"]
        assert client.person["date_of_birth_display"]
        assert client.vaccines_due  # List of diseases needing immunization
        assert client.vaccines_due_list  # Expanded list
        assert client.school["name"]
        assert client.contact["city"]

    def test_typst_file_generation_metadata_from_artifact(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify all metadata needed for Typst file generation is in artifact.

        Real-world significance:
        - Typst templates (.typ files) reference QR image files by name
        - Names are derived from sequence number and client_id
        - Typst compilation fails if QR file not found with expected name
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="en", run_id="test_typst_001"
        )

        for i, client in enumerate(artifact.clients, 1):
            # These fields determine QR filename: {sequence}_{client_id}.png
            assert client.sequence == f"{i:05d}"
            assert client.client_id
            # QR dict (if present) should have filename
            # In real pipeline, set during QR generation step
            if client.qr:
                assert "filename" in client.qr

    def test_vaccines_due_list_for_notice_rendering(self, tmp_test_dir: Path) -> None:
        """Verify vaccines_due_list is populated for notice template iteration.

        Real-world significance:
        - Notices display a chart showing which vaccines are due
        - Template iterates over vaccines_due_list to build chart rows
        - Missing vaccines_due_list causes chart to be empty/broken
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=1, language="en", run_id="test_vax_001"
        )

        client = artifact.clients[0]

        # Should have both string and list representation
        assert client.vaccines_due  # e.g., "Measles/Mumps/Rubella"
        assert client.vaccines_due_list  # e.g., ["Measles", "Mumps", "Rubella"]
        assert isinstance(client.vaccines_due_list, list)
        assert len(client.vaccines_due_list) > 0


@pytest.mark.integration
class TestQrPayloadGeneration:
    """Integration tests for QR payload template variable substitution."""

    def test_qr_payload_template_variable_substitution(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify QR payload templates correctly substitute artifact variables.

        Real-world significance:
        - QR template (from config) may use placeholders like {client_id}, {name}
        - Variables must be correctly extracted from artifact and substituted
        - Typos or missing variables cause invalid QR payloads
        """
        config_qr_template = "https://example.com/v?id={client_id}&name={first_name}"

        client = sample_input.create_test_client_record(
            sequence="00001",
            client_id="C12345",
            first_name="Alice",
            language="en",
        )

        # Simulate variable extraction
        template_vars = {
            "client_id": client.client_id,
            "first_name": client.person["first_name"],
            "name": f"{client.person['first_name']} {client.person['last_name']}",
            "language_code": client.language,
        }

        payload = config_qr_template.format(**template_vars)

        assert "id=C12345" in payload
        assert "name=Alice" in payload

    def test_qr_payload_iso_date_format(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify QR payloads use ISO date format (YYYY-MM-DD).

        Real-world significance:
        - QR payloads should be URL-safe and parseable by receiving system
        - ISO date format (2015-06-15) is unambiguous vs regional formats
        - Used in many backend systems for DOB verification
        """
        config_qr_template = (
            "https://example.com/update?client_id={client_id}&dob={date_of_birth_iso}"
        )

        client = sample_input.create_test_client_record(
            client_id="C99999",
            date_of_birth="2015-06-15",
            language="en",
        )

        template_vars = {
            "client_id": client.client_id,
            "date_of_birth_iso": client.person["date_of_birth_iso"],
        }

        payload = config_qr_template.format(**template_vars)

        assert "dob=2015-06-15" in payload
        assert "dob=" + "2015-06-15" in payload  # Verify exact format


@pytest.mark.integration
class TestArtifactMetadataPreservation:
    """Integration tests for artifact metadata flow through steps."""

    def test_artifact_metadata_preserved_through_json_serialization(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify artifact metadata (run_id, warnings, created_at) survives JSON round-trip.

        Real-world significance:
        - Metadata enables linking pipeline runs for debugging
        - Warnings track data quality issues
        - created_at timestamp enables audit trail
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="en", run_id="test_meta_20250101_120000"
        )
        artifact_dir = tmp_test_dir / "artifacts"
        artifact_dir.mkdir()

        artifact_path = sample_input.write_test_artifact(artifact, artifact_dir)

        with open(artifact_path) as f:
            loaded = json.load(f)

        assert loaded["run_id"] == "test_meta_20250101_120000"
        assert "created_at" in loaded
        assert loaded["total_clients"] == 2

    def test_artifact_warnings_accumulated(self, tmp_test_dir: Path) -> None:
        """Verify warnings are preserved in artifact for user visibility.

        Real-world significance:
        - Preprocessing may encounter data quality issues (missing board, invalid postal)
        - Warnings should be logged to artifact for user review
        - Allows diagnosing why certain clients have incomplete data
        """
        artifact = data_models.ArtifactPayload(
            run_id="test_warn_001",
            language="en",
            clients=[
                sample_input.create_test_client_record(
                    sequence="00001", client_id="C00001", language="en"
                ),
            ],
            warnings=[
                "Missing board name for client C00001",
                "Invalid postal code format for client C00002",
            ],
            created_at="2025-01-01T12:00:00Z",
            input_file="test_input.xlsx",
            total_clients=1,
        )

        artifact_dir = tmp_test_dir / "artifacts"
        artifact_dir.mkdir()

        artifact_path = sample_input.write_test_artifact(artifact, artifact_dir)

        with open(artifact_path) as f:
            loaded = json.load(f)

        assert len(loaded["warnings"]) == 2
        assert "Missing board name" in loaded["warnings"][0]
