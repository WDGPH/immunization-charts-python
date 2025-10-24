"""Unit tests for data_models module - core pipeline data structures.

Tests cover:
- ClientRecord dataclass structure and serialization
- PreprocessResult aggregation
- ArtifactPayload metadata and schema
- PdfRecord for compiled notice tracking

Real-world significance:
- These immutable dataclasses enforce consistent data structure across pipeline
- Type hints and frozen dataclasses prevent bugs from data corruption
- Schema must remain stable for artifacts to be shareable between pipeline runs
"""

from __future__ import annotations

import pytest

from scripts import data_models


@pytest.mark.unit
class TestClientRecord:
    """Unit tests for ClientRecord dataclass."""

    def test_client_record_creation(self) -> None:
        """Verify ClientRecord can be created with all required fields.

        Real-world significance:
        - ClientRecord is the core data structure for each student notice
        """
        client = data_models.ClientRecord(
            sequence="00001",
            client_id="C00001",
            language="en",
            person={"first_name": "Alice", "full_name": "Alice Zephyr"},
            school={"name": "Tunnel Academy"},
            board={"name": "Guelph Board"},
            contact={"street": "123 Main St"},
            vaccines_due="Measles/Mumps/Rubella",
            vaccines_due_list=["Measles", "Mumps", "Rubella"],
            received=[],
            metadata={},
        )

        assert client.sequence == "00001"
        assert client.client_id == "C00001"
        assert client.language == "en"

    def test_client_record_is_frozen(self) -> None:
        """Verify ClientRecord is immutable (frozen).

        Real-world significance:
        - Prevents accidental modification of client data after preprocessing
        - Ensures data integrity through pipeline
        """
        client = data_models.ClientRecord(
            sequence="00001",
            client_id="C00001",
            language="en",
            person={},
            school={},
            board={},
            contact={},
            vaccines_due=None,
            vaccines_due_list=None,
            received=None,
            metadata={},
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            client.sequence = "00002"

    def test_client_record_optional_qr_field(self) -> None:
        """Verify ClientRecord has optional qr field.

        Real-world significance:
        - QR code added in Step 2, may be None before then
        """
        client = data_models.ClientRecord(
            sequence="00001",
            client_id="C00001",
            language="en",
            person={},
            school={},
            board={},
            contact={},
            vaccines_due=None,
            vaccines_due_list=None,
            received=None,
            metadata={},
            qr=None,
        )

        assert client.qr is None

        client_with_qr = data_models.ClientRecord(
            sequence="00001",
            client_id="C00001",
            language="en",
            person={},
            school={},
            board={},
            contact={},
            vaccines_due=None,
            vaccines_due_list=None,
            received=None,
            metadata={},
            qr={"payload": "test_payload", "filename": "test.png"},
        )

        assert client_with_qr.qr is not None
        assert client_with_qr.qr["payload"] == "test_payload"


@pytest.mark.unit
class TestPreprocessResult:
    """Unit tests for PreprocessResult dataclass."""

    def test_preprocess_result_creation(self) -> None:
        """Verify PreprocessResult aggregates clients and warnings.

        Real-world significance:
        - Output of Step 1 (Preprocess), input to Steps 2-3
        """
        clients = [
            data_models.ClientRecord(
                sequence="00001",
                client_id="C00001",
                language="en",
                person={},
                school={},
                board={},
                contact={},
                vaccines_due=None,
                vaccines_due_list=None,
                received=None,
                metadata={},
            )
        ]

        result = data_models.PreprocessResult(
            clients=clients,
            warnings=["Warning 1"],
        )

        assert len(result.clients) == 1
        assert len(result.warnings) == 1

    def test_preprocess_result_empty_warnings(self) -> None:
        """Verify PreprocessResult works with no warnings.

        Real-world significance:
        - Clean input should have empty warnings list
        """
        result = data_models.PreprocessResult(
            clients=[],
            warnings=[],
        )

        assert result.warnings == []


@pytest.mark.unit
class TestArtifactPayload:
    """Unit tests for ArtifactPayload dataclass."""

    def test_artifact_payload_creation(self) -> None:
        """Verify ArtifactPayload stores metadata and clients.

        Real-world significance:
        - Artifacts are JSON files with client data and metadata
        - Must include run_id for comparing pipeline runs
        """
        clients = []
        payload = data_models.ArtifactPayload(
            run_id="test_run_001",
            language="en",
            clients=clients,
            warnings=[],
            created_at="2025-01-01T12:00:00Z",
            input_file="test.xlsx",
            total_clients=0,
        )

        assert payload.run_id == "test_run_001"
        assert payload.language == "en"
        assert payload.total_clients == 0

    def test_artifact_payload_optional_input_file(self) -> None:
        """Verify ArtifactPayload has optional input_file field.

        Real-world significance:
        - Not all artifacts know their source file
        """
        payload_with_file = data_models.ArtifactPayload(
            run_id="test_run_001",
            language="en",
            clients=[],
            warnings=[],
            created_at="2025-01-01T12:00:00Z",
            input_file="input.xlsx",
        )

        assert payload_with_file.input_file == "input.xlsx"


@pytest.mark.unit
class TestPdfRecord:
    """Unit tests for PdfRecord dataclass."""

    def test_pdf_record_creation(self, tmp_path) -> None:
        """Verify PdfRecord tracks compiled PDF metadata.

        Real-world significance:
        - Used in Step 6 (Count PDFs) to verify all notices compiled
        """
        pdf_path = tmp_path / "00001_C00001.pdf"

        record = data_models.PdfRecord(
            sequence="00001",
            client_id="C00001",
            pdf_path=pdf_path,
            page_count=1,
            client={"first_name": "Alice"},
        )

        assert record.sequence == "00001"
        assert record.client_id == "C00001"
        assert record.page_count == 1
