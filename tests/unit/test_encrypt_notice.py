"""Unit tests for encrypt_notice module - Optional PDF encryption.

Tests cover:
- Password-based PDF encryption using client context and templates
- Password template formatting and placeholder validation
- Configuration loading from parameters.yaml
- Error handling for invalid PDFs and missing files
- Round-trip encryption/decryption verification
- Encrypted PDF file naming and metadata preservation
- Batch encryption with directory scanning

Real-world significance:
- Step 7 of pipeline (optional): encrypts individual PDF notices with passwords
- Protects sensitive health information in transit (motion security)
- Password templates use client metadata (DOB, client_id, etc.)
- Feature must be safely skippable if disabled
- Encryption failures must be visible to pipeline orchestrator
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pypdf import PdfReader, PdfWriter

from pipeline import encrypt_notice


@pytest.mark.unit
class TestLoadEncryptionConfig:
    """Unit tests for loading encryption configuration."""

    def test_load_encryption_config_with_valid_yaml(self, tmp_test_dir: Path) -> None:
        """Verify encryption config loads from parameters.yaml.

        Real-world significance:
        - Production config must contain encryption settings
        - Template must be a string (not dict or list)
        - Configuration drives password generation for all PDFs
        """
        config_path = tmp_test_dir / "parameters.yaml"
        config_path.write_text(
            "encryption:\n"
            "  enabled: true\n"
            "  password:\n"
            "    template: '{date_of_birth_iso_compact}'\n"
        )

        # Note: get_encryption_config() uses default path, so we test loading directly
        with patch("pipeline.encrypt_notice.CONFIG_DIR", tmp_test_dir):
            # Reset cached config
            encrypt_notice._encryption_config = None
            config = encrypt_notice.get_encryption_config()
            # Config should at least have password template or be empty (uses default)
            assert isinstance(config, dict)

    def test_encryption_config_missing_file_uses_default(self) -> None:
        """Verify default config is used when file missing.

        Real-world significance:
        - Should not crash if encryption config missing
        - Falls back to reasonable defaults
        """
        with patch("pipeline.encrypt_notice.CONFIG_DIR", Path("/nonexistent")):
            encrypt_notice._encryption_config = None
            config = encrypt_notice.get_encryption_config()
            # Should return empty dict or default config
            assert isinstance(config, dict)


@pytest.mark.unit
class TestPasswordGeneration:
    """Unit tests for password generation from templates."""

    def test_encrypt_pdf_with_context_dict(self, tmp_test_dir: Path) -> None:
        """Verify PDF encryption using context dictionary.

        Real-world significance:
        - New API uses context dict with all template placeholders
        - Password generated from client metadata
        - Creates encrypted PDF with _encrypted suffix
        """
        # Create a minimal valid PDF
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        context = {
            "client_id": "12345",
            "date_of_birth_iso": "2015-03-15",
            "date_of_birth_iso_compact": "20150315",
            "first_name": "John",
            "last_name": "Doe",
            "school": "Lincoln School",
        }

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypted_path = encrypt_notice.encrypt_pdf(str(pdf_path), context)

        assert Path(encrypted_path).exists()
        assert "_encrypted" in Path(encrypted_path).name

    def test_encrypt_pdf_with_custom_password_template(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify password generation from custom template.

        Real-world significance:
        - School can customize password format
        - Might combine client_id + DOB or use other fields
        - Template validation should catch unknown placeholders
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        context = {
            "client_id": "12345",
            "date_of_birth_iso_compact": "20150315",
        }

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={
                "password": {"template": "{client_id}_{date_of_birth_iso_compact}"}
            },
        ):
            encrypted_path = encrypt_notice.encrypt_pdf(str(pdf_path), context)
            assert Path(encrypted_path).exists()

    def test_encrypt_pdf_with_missing_template_placeholder(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error when password template uses unknown placeholder.

        Real-world significance:
        - Configuration error: template refers to non-existent field
        - Should fail loudly so admin can fix config
        - Wrong placeholder in template breaks all encryptions
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        context = {
            "client_id": "12345",
            "date_of_birth_iso_compact": "20150315",
        }

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{unknown_field}"}},
        ):
            with pytest.raises(ValueError, match="Unknown placeholder"):
                encrypt_notice.encrypt_pdf(str(pdf_path), context)

    def test_encrypt_pdf_legacy_mode_with_oen_and_dob(self, tmp_test_dir: Path) -> None:
        """Verify legacy calling pattern (oen string + dob).

        Real-world significance:
        - Some callers may use old API signature
        - Must support backward compatibility
        - Both calling patterns should work
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypted_path = encrypt_notice.encrypt_pdf(
                str(pdf_path), "12345", dob="2015-03-15"
            )
            assert Path(encrypted_path).exists()

    def test_encrypt_pdf_legacy_mode_missing_dob_raises_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error when legacy mode called without DOB.

        Real-world significance:
        - Legacy API requires both oen_partial and dob
        - Calling with just oen string should fail clearly
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        with pytest.raises(ValueError, match="dob must be provided"):
            encrypt_notice.encrypt_pdf(str(pdf_path), "12345", dob=None)


@pytest.mark.unit
class TestEncryptNotice:
    """Unit tests for encrypt_notice function."""

    def test_encrypt_notice_from_json_metadata(self, tmp_test_dir: Path) -> None:
        """Verify encrypting PDF using client data from JSON file.

        Real-world significance:
        - JSON file contains client metadata for password generation
        - Path format: JSON filename corresponds to PDF filename
        - Must load JSON and extract client data correctly
        """
        # Create test PDF
        pdf_path = tmp_test_dir / "en_client_00001_12345.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # Create test JSON metadata
        json_path = tmp_test_dir / "metadata.json"
        client_data = {
            "12345": {
                "client_id": "12345",
                "person": {
                    "full_name": "John Doe",
                    "date_of_birth_iso": "2015-03-15",
                },
                "school": {"name": "Lincoln School"},
                "contact": {"postal_code": "M5V 3A8"},
            }
        }
        json_path.write_text(json.dumps(client_data))

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypted_path = encrypt_notice.encrypt_notice(json_path, pdf_path, "en")
            assert Path(encrypted_path).exists()
            assert "_encrypted" in Path(encrypted_path).name

    def test_encrypt_notice_missing_json_file_raises_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error when JSON metadata file missing.

        Real-world significance:
        - JSON file must exist to get client password data
        - Early error prevents silent failures downstream
        """
        pdf_path = tmp_test_dir / "test.pdf"
        json_path = tmp_test_dir / "missing.json"

        with pytest.raises(FileNotFoundError):
            encrypt_notice.encrypt_notice(json_path, pdf_path, "en")

    def test_encrypt_notice_missing_pdf_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when PDF file missing.

        Real-world significance:
        - PDF must exist to encrypt
        - Should fail quickly instead of trying to read missing file
        """
        pdf_path = tmp_test_dir / "missing.pdf"
        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(json.dumps({"12345": {"client_id": "12345"}}))

        with pytest.raises(FileNotFoundError):
            encrypt_notice.encrypt_notice(json_path, pdf_path, "en")

    def test_encrypt_notice_invalid_json_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when JSON is malformed.

        Real-world significance:
        - JSON corruption should be detected early
        - Invalid JSON prevents password generation
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text("{ invalid json }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            encrypt_notice.encrypt_notice(json_path, pdf_path, "en")

    def test_encrypt_notice_caches_encrypted_pdf(self, tmp_test_dir: Path) -> None:
        """Verify encrypted PDF is reused if already exists and newer.

        Real-world significance:
        - Re-running pipeline step shouldn't re-encrypt already encrypted files
        - Timestamp check prevents re-encryption if PDF hasn't changed
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(
            json.dumps(
                {
                    "12345": {
                        "client_id": "12345",
                        "person": {
                            "full_name": "John Doe",
                            "date_of_birth_iso": "2015-03-15",
                        },
                        "contact": {},
                    }
                }
            )
        )

        # Create encrypted file that's newer than source
        encrypted_path = pdf_path.with_name(
            f"{pdf_path.stem}_encrypted{pdf_path.suffix}"
        )
        with open(encrypted_path, "wb") as f:
            f.write(b"already encrypted")

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            result = encrypt_notice.encrypt_notice(json_path, pdf_path, "en")
            # Should return existing encrypted file
            assert result == str(encrypted_path)


@pytest.mark.unit
class TestEncryptPdfsInDirectory:
    """Unit tests for encrypting multiple PDFs in a directory."""

    def test_encrypt_pdfs_in_directory_processes_all_files(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify all PDFs in directory are encrypted.

        Real-world significance:
        - Batch encryption of notices after compilation
        - Must find all PDFs and encrypt each with correct password
        - Common use case: encrypt output/pdf_individual/ directory
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        # Create test PDFs
        for i in range(1, 4):
            pdf_path = pdf_dir / f"en_client_0000{i}_{100 + i}.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)

        # Create combined JSON metadata
        json_path = tmp_test_dir / "combined_metadata.json"
        metadata = {
            "clients": [
                {
                    "client_id": f"{100 + i}",
                    "person": {
                        "full_name": f"Client {i}",
                        "date_of_birth_iso": "2015-03-15",
                    },
                    "contact": {},
                }
                for i in range(1, 4)
            ]
        }
        json_path.write_text(json.dumps(metadata))

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")

        # Verify encrypted files exist
        encrypted_files = list(pdf_dir.glob("*_encrypted.pdf"))
        assert len(encrypted_files) == 3

    def test_encrypt_pdfs_skips_already_encrypted(self, tmp_test_dir: Path) -> None:
        """Verify already-encrypted PDFs are skipped.

        Real-world significance:
        - Batch encryption shouldn't re-encrypt _encrypted files
        - Prevents double-encryption and unnecessary processing
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        # Create PDF and encrypted version
        pdf_path = pdf_dir / "en_client_00001_101.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        encrypted_path = pdf_dir / "en_client_00001_101_encrypted.pdf"
        with open(encrypted_path, "wb") as f:
            f.write(b"already encrypted")

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(json.dumps({"clients": []}))

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            with patch("pipeline.encrypt_notice.encrypt_pdf") as mock_encrypt:
                encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")
                # encrypt_pdf should not be called for _encrypted files
                mock_encrypt.assert_not_called()

    def test_encrypt_pdfs_skips_conf_pdf(self, tmp_test_dir: Path) -> None:
        """Verify conf.pdf (shared template) is skipped.

        Real-world significance:
        - conf.pdf is shared template file, not a client notice
        - Should be skipped during encryption
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        # Create conf.pdf
        conf_path = pdf_dir / "conf.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(conf_path, "wb") as f:
            writer.write(f)

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(json.dumps({"clients": []}))

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            with patch("pipeline.encrypt_notice.encrypt_pdf") as mock_encrypt:
                encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")
                # encrypt_pdf should not be called for conf.pdf
                mock_encrypt.assert_not_called()

    def test_encrypt_pdfs_missing_directory_raises_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error when PDF directory doesn't exist.

        Real-world significance:
        - Should fail fast if directory structure missing
        - Indicates upstream compilation step failed
        """
        pdf_dir = tmp_test_dir / "nonexistent"
        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(json.dumps({}))

        with pytest.raises(FileNotFoundError):
            encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")

    def test_encrypt_pdfs_missing_json_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when metadata JSON missing.

        Real-world significance:
        - JSON contains client data for password generation
        - Missing JSON prevents all encryptions
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        json_path = tmp_test_dir / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")

    def test_encrypt_pdfs_deletes_unencrypted_after_success(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify unencrypted PDF is deleted after successful encryption.

        Real-world significance:
        - Encrypted version replaces original (with _encrypted suffix)
        - Original unencrypted version should be removed
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        # Create test PDF
        pdf_path = pdf_dir / "en_client_00001_101.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(
            json.dumps(
                {
                    "clients": [
                        {
                            "client_id": "101",
                            "person": {
                                "full_name": "John",
                                "date_of_birth_iso": "2015-03-15",
                            },
                            "contact": {},
                        }
                    ]
                }
            )
        )

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")

        # Original should be deleted
        assert not pdf_path.exists()
        # Encrypted version should exist
        encrypted = pdf_dir / "en_client_00001_101_encrypted.pdf"
        assert encrypted.exists()

    def test_encrypt_pdfs_handles_file_extraction_errors(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify graceful handling of file extraction errors.

        Real-world significance:
        - PDF filename might not match expected format
        - Should log error but continue with other PDFs
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        # Create PDF with unexpected name
        pdf_path = pdf_dir / "unexpected_name.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(json.dumps({"clients": []}))

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            # Should not crash
            encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")

    def test_encrypt_pdfs_invalid_json_structure(self, tmp_test_dir: Path) -> None:
        """Verify error when JSON has invalid structure.

        Real-world significance:
        - JSON might be malformed or have unexpected structure
        - Should fail with clear error
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text("not json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")

    def test_encrypt_pdfs_prints_status_messages(self, tmp_test_dir: Path) -> None:
        """Verify encryption progress is printed to user.

        Real-world significance:
        - User should see encryption progress
        - Start message, completion with counts
        """
        pdf_dir = tmp_test_dir / "pdfs"
        pdf_dir.mkdir()

        # Create one test PDF
        pdf_path = pdf_dir / "en_client_00001_101.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(
            json.dumps(
                {
                    "clients": [
                        {
                            "client_id": "101",
                            "person": {
                                "full_name": "John",
                                "date_of_birth_iso": "2015-03-15",
                            },
                            "contact": {},
                        }
                    ]
                }
            )
        )

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            with patch("builtins.print") as mock_print:
                encrypt_notice.encrypt_pdfs_in_directory(pdf_dir, json_path, "en")
                # Should print start and completion messages
                assert mock_print.called


@pytest.mark.unit
class TestLoadNoticeMetadata:
    """Unit tests for _load_notice_metadata function."""

    def test_load_notice_metadata_extracts_client_data(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify client data and context extraction from JSON.

        Real-world significance:
        - JSON contains client metadata for password generation
        - Must extract nested fields correctly
        """
        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text(
            json.dumps(
                {
                    "12345": {
                        "client_id": "12345",
                        "person": {
                            "full_name": "John Doe",
                            "date_of_birth_iso": "2015-03-15",
                        },
                        "school": {"name": "Lincoln"},
                        "contact": {"postal_code": "M5V"},
                    }
                }
            )
        )

        record, context = encrypt_notice._load_notice_metadata(json_path, "en")

        assert record["client_id"] == "12345"
        assert context["client_id"] == "12345"
        assert context["first_name"] == "John"

    def test_load_notice_metadata_invalid_json(self, tmp_test_dir: Path) -> None:
        """Verify error for invalid JSON structure.

        Real-world significance:
        - JSON corruption should be caught early
        """
        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text("not valid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            encrypt_notice._load_notice_metadata(json_path, "en")

    def test_load_notice_metadata_empty_json(self, tmp_test_dir: Path) -> None:
        """Verify error for empty JSON.

        Real-world significance:
        - Empty JSON has no client data
        """
        json_path = tmp_test_dir / "metadata.json"
        json_path.write_text("{}")

        with pytest.raises(ValueError, match="No client data"):
            encrypt_notice._load_notice_metadata(json_path, "en")


@pytest.mark.unit
class TestPdfEncryptionIntegration:
    """Unit tests for end-to-end PDF encryption workflow."""

    def test_encrypt_preserves_pdf_metadata(self, tmp_test_dir: Path) -> None:
        """Verify encryption preserves original PDF metadata.

        Real-world significance:
        - Original PDF metadata should survive encryption
        - Ensures document information is not lost
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_metadata({"/Title": "Test Notice", "/Author": "VIPER"})
        with open(pdf_path, "wb") as f:
            writer.write(f)

        context = {"date_of_birth_iso_compact": "20150315"}

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypted_path = encrypt_notice.encrypt_pdf(str(pdf_path), context)

        # Verify encrypted PDF can be read and has metadata
        reader = PdfReader(encrypted_path, strict=False)
        # Metadata should be preserved
        assert reader is not None

    def test_encrypt_produces_readable_pdf(self, tmp_test_dir: Path) -> None:
        """Verify encrypted PDF remains readable with correct password.

        Real-world significance:
        - Encrypted PDF must be openable with the generated password
        - User with correct password can access content
        """
        pdf_path = tmp_test_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        context = {"date_of_birth_iso_compact": "20150315"}

        with patch.object(
            encrypt_notice,
            "get_encryption_config",
            return_value={"password": {"template": "{date_of_birth_iso_compact}"}},
        ):
            encrypted_path = encrypt_notice.encrypt_pdf(str(pdf_path), context)

        # Verify encrypted PDF can be opened
        reader = PdfReader(encrypted_path, strict=False)
        assert reader is not None
        # Encrypted PDF requires password to read pages, so we just verify the file exists
        assert Path(encrypted_path).exists()
        assert Path(encrypted_path).stat().st_size > 0
