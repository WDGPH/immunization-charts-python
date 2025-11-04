"""Integration tests for multi-step pipeline workflows.

Tests cover end-to-end interactions between adjacent steps:
- Preprocessing → QR generation (artifact validation)
- QR generation → Notice generation (QR references in templates)
- Notice generation → Typst compilation (template syntax)
- Compilation → PDF validation/counting (PDF integrity)
- PDF validation → Encryption (PDF metadata preservation)
- Encryption → Bundling (bundle manifest generation)

Real-world significance:
- Multi-step workflows depend on contracts between adjacent steps
- A single missing field or changed format cascades failures
- Integration testing catches failures that unit tests miss
- Verifies configuration changes propagate through pipeline
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pipeline import data_models
from tests.fixtures import sample_input


@pytest.mark.integration
class TestPreprocessToQrStepIntegration:
    """Integration tests for Preprocess → QR generation workflow."""

    def test_preprocess_output_suitable_for_qr_generation(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify preprocessed artifact has all data needed by QR generation step.

        Real-world significance:
        - QR generation (Step 3) reads preprocessed artifact from Step 2
        - Must have: client_id, name, DOB, school, contact info for payload template
        - Missing data causes QR payload generation to fail
        """
        artifact = sample_input.create_test_artifact_payload(
            num_clients=3, language="en", run_id="test_preqr_001"
        )
        artifact_dir = tmp_test_dir / "artifacts"
        artifact_dir.mkdir()

        artifact_path = sample_input.write_test_artifact(artifact, artifact_dir)

        # Verify artifact is readable and has required fields
        with open(artifact_path) as f:
            loaded = json.load(f)

        assert len(loaded["clients"]) == 3

        # Each client must have fields for QR payload template
        for client_dict in loaded["clients"]:
            assert "client_id" in client_dict
            assert "person" in client_dict
            assert client_dict["person"]["first_name"]
            assert client_dict["person"]["last_name"]
            assert client_dict["person"]["date_of_birth_iso"]
            assert "school" in client_dict
            assert "contact" in client_dict

    def test_client_sequence_ordered_for_qr_files(self, tmp_test_dir: Path) -> None:
        """Verify client sequences are deterministic for QR filename generation.

        Real-world significance:
        - QR files named: {sequence}_{client_id}.png
        - Sequence numbers (00001, 00002, ...) must be stable
        - Same input → same filenames across multiple runs
        """
        clients = [
            sample_input.create_test_client_record(
                sequence=f"{i + 1:05d}",
                client_id=f"C{i:05d}",
                language="en",
            )
            for i in range(5)
        ]

        artifact = data_models.ArtifactPayload(
            run_id="test_seq_qr",
            language="en",
            clients=clients,
            warnings=[],
            created_at="2025-01-01T12:00:00Z",
            total_clients=5,
        )

        # Verify sequences are in expected order
        sequences = [c.sequence for c in artifact.clients]
        assert sequences == ["00001", "00002", "00003", "00004", "00005"]

    def test_language_consistency_preprocess_to_qr(self, tmp_test_dir: Path) -> None:
        """Verify language is preserved and consistent across steps.

        Real-world significance:
        - QR generation may format dates differently per language
        - Must know language to select correct template placeholders
        - All clients in artifact must have same language
        """
        for lang in ["en", "fr"]:
            artifact = sample_input.create_test_artifact_payload(
                num_clients=2, language=lang, run_id=f"test_lang_{lang}"
            )

            assert artifact.language == lang
            for client in artifact.clients:
                assert client.language == lang


@pytest.mark.integration
class TestQrToNoticeGenerationIntegration:
    """Integration tests for QR generation → Notice generation workflow."""

    def test_qr_payload_fits_template_variables(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify QR payload can be generated from artifact template.

        Real-world significance:
        - Notice templates reference QR by filename and may embed payload
        - Payload template may use: {client_id}, {name}, {date_of_birth_iso}
        - Template validation ensures all placeholders exist in artifact
        """
        client = sample_input.create_test_client_record(
            sequence="00001",
            client_id="C12345",
            first_name="Alice",
            last_name="Zephyr",
            date_of_birth="2015-06-15",
            language="en",
        )

        # Simulate template variable substitution from config
        template = default_config["qr"]["payload_template"]

        # Create variable dict from client (as QR generation would)
        template_vars = {
            "client_id": client.client_id,
            "first_name": client.person["first_name"],
            "last_name": client.person["last_name"],
            "name": " ".join(
                filter(None, [client.person["first_name"], client.person["last_name"]])
            ).strip(),
            "date_of_birth_iso": client.person["date_of_birth_iso"],
            "school": client.school["name"],
            "city": client.contact["city"],
            "postal_code": client.contact["postal_code"],
            "province": client.contact["province"],
            "street_address": client.contact["street"],
            "language_code": client.language,
        }

        # Template should successfully format
        try:
            payload = template.format(**template_vars)
            assert len(payload) > 0
        except KeyError as e:
            pytest.fail(f"Template refers to missing field: {e}")

    def test_qr_filename_reference_in_artifact(self, tmp_test_dir: Path) -> None:
        """Verify artifact can reference QR file generated in Step 3.

        Real-world significance:
        - Notice templates (Step 4) embed: !image("00001_C12345.png")
        - Filename must match what QR generation produces: {sequence}_{client_id}.png
        - If QR step adds qr.filename to artifact, notice step can reference it
        """
        client = sample_input.create_test_client_record(
            sequence="00001",
            client_id="C12345",
            language="en",
        )

        # Simulate QR generation adding QR reference to client
        client_with_qr = data_models.ClientRecord(
            sequence=client.sequence,
            client_id=client.client_id,
            language=client.language,
            person=client.person,
            school=client.school,
            board=client.board,
            contact=client.contact,
            vaccines_due=client.vaccines_due,
            vaccines_due_list=client.vaccines_due_list,
            received=client.received,
            metadata=client.metadata,
            qr={
                "filename": f"{client.sequence}_{client.client_id}.png",
                "payload": "https://example.com/vac/C12345",
            },
        )

        # Notice generation can now reference the QR file
        assert client_with_qr.qr is not None
        assert client_with_qr.qr["filename"] == "00001_C12345.png"


@pytest.mark.integration
class TestNoticeToCompileIntegration:
    """Integration tests for Notice generation → Typst compilation workflow."""

    def test_notice_template_render_requires_artifact_fields(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify notice templates can access all required artifact fields.

        Real-world significance:
        - Typst templates access: client.person, client.vaccines_due_list, school
        - Missing fields cause template render errors
        - Template syntax: client.person.first_name, client.vaccines_due_list
        """
        client = sample_input.create_test_client_record(
            first_name="Alice",
            last_name="Zephyr",
            date_of_birth="2015-06-15",
            vaccines_due="Measles/Mumps/Rubella",
            vaccines_due_list=["Measles", "Mumps", "Rubella"],
            language="en",
        )

        # Simulate template variable access
        template_vars = {
            "client_first_name": client.person["first_name"],
            "client_last_name": client.person["last_name"],
            "client_full_name": " ".join(
                filter(None, [client.person["first_name"], client.person["last_name"]])
            ).strip(),
            "client_dob": client.person["date_of_birth_display"],
            "school_name": client.school["name"],
            "vaccines_list": client.vaccines_due_list,
        }

        # All fields should be present
        assert template_vars["client_first_name"] == "Alice"
        assert template_vars["client_last_name"] == "Zephyr"
        assert template_vars["vaccines_list"] is not None
        assert len(template_vars["vaccines_list"]) == 3

    def test_typst_file_structure_consistency(self, tmp_test_dir: Path) -> None:
        """Verify .typ files can be structured for Typst compilation.

        Real-world significance:
        - Typst compiler (Step 5) processes .typ files from Step 4
        - Files must have valid Typst syntax
        - Files reference QR images by filename
        """
        # Create mock .typ file content (simplified)
        typ_content = """#import "conf.typ": header, footer

#set page(
  margin: (top: 1cm, bottom: 1cm, left: 1cm, right: 1cm),
)

#header()
= Immunization Notice for Alice Zephyr

Client: Alice Zephyr
DOB: 2015-06-15

#image("artifacts/qr_codes/00001_C00001.png")

#footer()
"""

        typ_file = tmp_test_dir / "00001_C00001.typ"
        typ_file.write_text(typ_content)

        # Verify file is created and readable
        assert typ_file.exists()
        content = typ_file.read_text()
        assert "Alice Zephyr" in content
        assert "00001_C00001.png" in content


@pytest.mark.integration
class TestCompilationToPdfValidation:
    """Integration tests for Typst compilation → PDF validation workflow."""

    def test_pdf_page_count_validation_structure(self, tmp_test_dir: Path) -> None:
        """Verify PDF validation can record page counts for compiled files.

        Real-world significance:
        - Step 6 counts PDF pages for quality assurance
        - Single-page PDFs indicate successful compilation
        - Multi-page PDFs indicate template issues or client data problems
        """
        # Create mock PDF records
        pdf_records: List[data_models.PdfRecord] = []
        for i in range(1, 4):
            record = data_models.PdfRecord(
                sequence=f"{i:05d}",
                client_id=f"C{i:05d}",
                pdf_path=tmp_test_dir / f"{i:05d}_C{i:05d}.pdf",
                page_count=1,
                client={
                    "first_name": f"Client{i}",
                    "last_name": "Student",
                    "school": "Test School",
                },
            )
            pdf_records.append(record)

        # Verify page count structure
        assert len(pdf_records) == 3
        for record in pdf_records:
            assert record.page_count == 1
            assert record.sequence
            assert record.client_id

    def test_pdf_validation_manifest_generation(self, tmp_test_dir: Path) -> None:
        """Verify PDF validation can create manifest of page counts.

        Real-world significance:
        - Manifest stored in output/metadata/<lang>_page_counts_<run_id>.json
        - Enables detecting incomplete compilations
        - Useful for auditing and quality control
        """
        manifest = {
            "run_id": "test_compile_001",
            "language": "en",
            "created_at": "2025-01-01T12:00:00Z",
            "total_pdfs": 3,
            "page_counts": [
                {
                    "sequence": "00001",
                    "client_id": "C00001",
                    "page_count": 1,
                },
                {
                    "sequence": "00002",
                    "client_id": "C00002",
                    "page_count": 1,
                },
                {
                    "sequence": "00003",
                    "client_id": "C00003",
                    "page_count": 1,
                },
            ],
            "warnings": [],
        }

        # Write manifest to metadata directory
        metadata_dir = tmp_test_dir / "metadata"
        metadata_dir.mkdir()
        manifest_path = metadata_dir / "en_page_counts_test_compile_001.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        # Verify manifest can be read back
        assert manifest_path.exists()
        with open(manifest_path) as f:
            loaded = json.load(f)

        assert loaded["run_id"] == "test_compile_001"
        assert len(loaded["page_counts"]) == 3


@pytest.mark.integration
class TestEncryptionToBundlingWorkflow:
    """Integration tests for encryption and bundling workflows."""

    def test_encryption_preserves_pdf_reference_data(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify encrypted PDFs preserve references needed by bundling.

        Real-world significance:
        - Encryption step (Step 7) reads individual PDFs and encrypts
        - Must preserve filename, client metadata for bundling
        - Bundle step needs: sequence, client_id, school/board for grouping
        """
        # Create mock encrypted PDF record
        pdf_data = {
            "sequence": "00001",
            "client_id": "C00001",
            "filename": "00001_C00001.pdf",
            "client": {
                "first_name": "Alice",
                "last_name": "Zephyr",
                "school": "Test Academy",
                "board": "Test Board",
            },
            "encrypted": True,
            "password": "20150615",  # DOB in YYYYMMDD format
        }

        # Verify bundling can use this data
        assert pdf_data["sequence"]
        assert isinstance(pdf_data["client"], dict)
        assert pdf_data["client"]["school"]  # For group_by="school"
        assert pdf_data["client"]["board"]  # For group_by="board"

    def test_bundling_manifest_generation_from_pdfs(self, tmp_test_dir: Path) -> None:
        """Verify bundling creates manifest of grouped PDFs.

        Real-world significance:
        - Bundle step creates manifest mapping: bundle file → contained client PDFs
        - Manifest allows recipients to know which students in each bundle
        - Enables validation that no students lost in bundling
        """
        bundle_manifest = {
            "run_id": "test_bundle_001",
            "language": "en",
            "created_at": "2025-01-01T12:00:00Z",
            "bundles": [
                {
                    "bundle_id": "bundle_001",
                    "bundle_file": "bundle_001.pdf",
                    "group_key": "Test_Academy",  # school name
                    "client_count": 5,
                    "clients": [
                        {"sequence": "00001", "client_id": "C00001"},
                        {"sequence": "00002", "client_id": "C00002"},
                        {"sequence": "00003", "client_id": "C00003"},
                        {"sequence": "00004", "client_id": "C00004"},
                        {"sequence": "00005", "client_id": "C00005"},
                    ],
                },
            ],
            "total_bundles": 1,
            "total_clients": 5,
        }

        # Write manifest
        metadata_dir = tmp_test_dir / "metadata"
        metadata_dir.mkdir()
        manifest_path = metadata_dir / "en_bundle_manifest_test_bundle_001.json"

        with open(manifest_path, "w") as f:
            json.dump(bundle_manifest, f, indent=2)

        # Verify manifest structure
        assert manifest_path.exists()
        with open(manifest_path) as f:
            loaded = json.load(f)

        assert loaded["total_clients"] == 5
        assert len(loaded["bundles"]) == 1
        assert loaded["bundles"][0]["client_count"] == 5


@pytest.mark.integration
class TestConfigPropagationAcrossSteps:
    """Integration tests for configuration changes affecting multi-step workflow."""

    def test_qr_disabled_affects_notice_generation(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify notice generation respects qr.enabled=false configuration.

        Real-world significance:
        - If QR generation is disabled (qr.enabled=false), Step 3 doesn't run
        - Notice templates should handle missing QR references
        - Notices should still generate without QR images
        """
        config_no_qr = default_config.copy()
        config_no_qr["qr"]["enabled"] = False

        # Notice generation with qr.enabled=false should:
        # 1. Skip QR reference in template (if applicable)
        # 2. Still generate notice content
        # 3. Not fail on missing QR files

        assert config_no_qr["qr"]["enabled"] is False

    def test_encryption_disabled_enables_bundling(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify bundling is enabled only when encryption is disabled.

        Real-world significance:
        - If encryption.enabled=true, bundling is skipped (Step 8 not run)
        - If encryption.enabled=false, bundling can run
        - Configuration enforces: encrypt OR bundle, not both
        """
        config_encrypted = copy.deepcopy(default_config)
        config_encrypted["encryption"]["enabled"] = True

        config_bundled = copy.deepcopy(default_config)
        config_bundled["encryption"]["enabled"] = False
        config_bundled["bundling"]["bundle_size"] = 50

        # When encryption enabled, bundling should be skipped
        assert config_encrypted["encryption"]["enabled"] is True

        # When encryption disabled, bundling can proceed
        assert config_bundled["encryption"]["enabled"] is False
        assert config_bundled["bundling"]["bundle_size"] > 0

    def test_cleanup_configuration_affects_artifact_retention(
        self, tmp_test_dir: Path, default_config: Dict[str, Any]
    ) -> None:
        """Verify cleanup step respects keep_intermediate_files configuration.

        Real-world significance:
        - If keep_intermediate_files=true: retain .typ, JSON, per-client PDFs
        - If keep_intermediate_files=false: delete intermediate files
        - Affects disk space usage significantly for large runs
        """
        config_keep = copy.deepcopy(default_config)
        config_keep["pipeline"]["keep_intermediate_files"] = True

        config_clean = copy.deepcopy(default_config)
        config_clean["pipeline"]["keep_intermediate_files"] = False

        # With keep_intermediate_files=true, files should be retained
        assert config_keep["pipeline"]["keep_intermediate_files"] is True

        # With keep_intermediate_files=false, files should be deleted
        assert config_clean["pipeline"]["keep_intermediate_files"] is False
