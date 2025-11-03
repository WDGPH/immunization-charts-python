"""End-to-end tests for full pipeline execution.

Tests cover:
- Complete pipeline runs for English input
- Complete pipeline runs for French input
- Optional feature integration (encryption, batching, QR codes)
- Edge cases and minimal data

Real-world significance:
- E2E tests verify entire pipeline works together
- First indication that pipeline can successfully process user input
- Must verify output files are created and contain expected data
- Tests run against production config (not mocked)

Each test:
1. Prepares a temporary input Excel file
2. Runs the full viper pipeline
3. Validates exit code and output structure
4. Checks that expected artifacts were created
5. Verifies PDF count matches client count
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

from tests.fixtures.sample_input import create_test_input_dataframe


@pytest.mark.e2e
class TestFullPipelineExecution:
    """End-to-end tests for complete pipeline execution."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get the project root directory."""
        return Path(__file__).resolve().parent.parent.parent

    @pytest.fixture
    def pipeline_input_file(self, project_root: Path) -> Generator[Path, None, None]:
        """Create a test input Excel file in the project input directory."""
        input_file = project_root / "input" / "e2e_test_clients.xlsx"
        df = create_test_input_dataframe(num_clients=3)
        df.to_excel(input_file, index=False, engine="openpyxl")

        yield input_file

        # Cleanup
        if input_file.exists():
            input_file.unlink()

    def run_pipeline(
        self,
        input_file: Path,
        language: str,
        project_root: Path,
        config_overrides: dict | None = None,
    ) -> subprocess.CompletedProcess:
        """Run the viper pipeline via subprocess.

        Parameters
        ----------
        input_file : Path
            Path to input Excel file
        language : str
            Language code ('en' or 'fr')
        project_root : Path
            Project root (used for output directory within project tree)
        config_overrides : dict, optional
            Config parameters to override before running pipeline

        Returns
        -------
        subprocess.CompletedProcess
            Result of pipeline execution
        """
        if config_overrides:
            config_path = project_root / "config" / "parameters.yaml"
            with open(config_path) as f:
                config = yaml.safe_load(f)

            # Merge overrides
            for key, value in config_overrides.items():
                if (
                    isinstance(value, dict)
                    and key in config
                    and isinstance(config[key], dict)
                ):
                    config[key].update(value)
                else:
                    config[key] = value

            with open(config_path, "w") as f:
                yaml.dump(config, f)

        cmd = [
            "uv",
            "run",
            "viper",
            str(input_file.name),
            language,
            "--input-dir",
            str(input_file.parent),
        ]

        result = subprocess.run(
            cmd, cwd=str(project_root), capture_output=True, text=True
        )
        return result

    def test_full_pipeline_english(
        self, tmp_path: Path, pipeline_input_file: Path, project_root: Path
    ) -> None:
        """Test complete pipeline execution with English language.

        Real-world significance:
        - Core pipeline functionality must work for English input
        - Verifies all 9 steps execute successfully
        - Checks that per-client PDFs are created
        """
        result = self.run_pipeline(pipeline_input_file, "en", project_root)

        assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
        assert "Pipeline completed successfully" in result.stdout

        # Verify output structure (in project output directory)
        output_dir = project_root / "output"
        assert (output_dir / "artifacts").exists()
        assert (output_dir / "pdf_individual").exists()

        # Verify PDFs exist
        pdfs = list((output_dir / "pdf_individual").glob("en_notice_*.pdf"))
        assert len(pdfs) == 3, f"Expected 3 PDFs but found {len(pdfs)}"

    def test_full_pipeline_french(
        self, tmp_path: Path, pipeline_input_file: Path, project_root: Path
    ) -> None:
        """Test complete pipeline execution with French language.

        Real-world significance:
        - Multilingual support must work for French input
        - Templates, notices, and metadata must be in French
        - Verifies language parameter is respected throughout pipeline
        """
        result = self.run_pipeline(pipeline_input_file, "fr", project_root)

        assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
        assert "Pipeline completed successfully" in result.stdout

        # Verify output structure (in project output directory)
        output_dir = project_root / "output"
        assert (output_dir / "artifacts").exists()
        assert (output_dir / "pdf_individual").exists()

        # Verify PDFs exist with French prefix
        pdfs = list((output_dir / "pdf_individual").glob("fr_notice_*.pdf"))
        assert len(pdfs) == 3, f"Expected 3 French PDFs but found {len(pdfs)}"

    def test_pipeline_with_qr_disabled(
        self, tmp_path: Path, pipeline_input_file: Path, project_root: Path
    ) -> None:
        """Test pipeline with QR code generation disabled.

        Real-world significance:
        - QR codes are optional (controlled by config)
        - Pipeline must skip QR generation when disabled
        - Should complete faster without QR generation
        """
        # Temporarily disable QR in config
        config_path = project_root / "config" / "parameters.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        original_qr_enabled = config.get("qr", {}).get("enabled")

        try:
            config["qr"]["enabled"] = False
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            result = self.run_pipeline(pipeline_input_file, "en", project_root)

            assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
            assert "Step 3: Generating QR codes" in result.stdout
            assert (
                "disabled" in result.stdout.lower()
                or "skipped" in result.stdout.lower()
            )

            # Verify PDFs still exist
            output_dir = project_root / "output"
            pdfs = list((output_dir / "pdf_individual").glob("en_notice_*.pdf"))
            assert len(pdfs) == 3
        finally:
            # Restore original config
            config["qr"]["enabled"] = original_qr_enabled
            with open(config_path, "w") as f:
                yaml.dump(config, f)

    def test_pipeline_with_encryption(
        self, tmp_path: Path, pipeline_input_file: Path, project_root: Path
    ) -> None:
        """Test pipeline with PDF encryption enabled.

        Real-world significance:
        - Encryption protects sensitive student data in PDFs
        - Each PDF is encrypted with a unique password based on client data
        - Both encrypted and unencrypted versions are available
        """
        # Temporarily enable encryption and disable bundling in config
        config_path = project_root / "config" / "parameters.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        original_encryption = config.get("encryption", {}).get("enabled")
        original_bundle_size = config.get("bundling", {}).get("bundle_size")

        try:
            config["encryption"]["enabled"] = True
            config["bundling"]["bundle_size"] = 0  # Disable bundling
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            result = self.run_pipeline(pipeline_input_file, "en", project_root)

            assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
            assert "Encryption" in result.stdout
            assert "success: 3" in result.stdout

            # Verify PDFs exist (encrypted)
            output_dir = project_root / "output"
            pdfs = list(
                (output_dir / "pdf_individual").glob("en_notice_*_encrypted.pdf")
            )
            assert len(pdfs) == 3, f"Expected 3 encrypted PDFs but found {len(pdfs)}"
        finally:
            # Restore original config
            config["encryption"]["enabled"] = original_encryption
            config["bundling"]["bundle_size"] = original_bundle_size
            with open(config_path, "w") as f:
                yaml.dump(config, f)

    def test_pipeline_with_batching(
        self, tmp_path: Path, pipeline_input_file: Path, project_root: Path
    ) -> None:
        """Test pipeline with PDF bundling enabled.

        Real-world significance:
        - Bundling groups individual PDFs into combined files
        - Useful for organizing output by school or size
        - Creates manifests for audit trails
        """
        # Temporarily enable bundling in config
        config_path = project_root / "config" / "parameters.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        original_bundle_size = config.get("bundling", {}).get("bundle_size")
        original_encryption = config.get("encryption", {}).get("enabled")

        try:
            # Disable encryption and enable bundling
            config["encryption"]["enabled"] = False
            config["bundling"]["bundle_size"] = 2
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            result = self.run_pipeline(pipeline_input_file, "en", project_root)

            assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
            assert "Bundling" in result.stdout
            assert (
                "created" in result.stdout.lower() or "bundle" in result.stdout.lower()
            )

            # Verify bundled PDFs exist
            output_dir = project_root / "output"
            assert (output_dir / "pdf_combined").exists()
            bundles = list((output_dir / "pdf_combined").glob("en_bundle_*.pdf"))
            assert len(bundles) > 0, "Expected bundled PDFs to be created"

            # Verify manifests exist
            assert (output_dir / "metadata").exists()
            manifests = list((output_dir / "metadata").glob("*_manifest.json"))
            assert len(manifests) == len(bundles)
        finally:
            # Restore original config
            config["bundling"]["bundle_size"] = original_bundle_size
            config["encryption"]["enabled"] = original_encryption
            with open(config_path, "w") as f:
                yaml.dump(config, f)

    def test_pipeline_minimal_input(self, tmp_path: Path, project_root: Path) -> None:
        """Test pipeline with minimal input (1 client).

        Real-world significance:
        - Pipeline must handle edge case of single client
        - Single-client PDFs must work correctly
        - Minimal input helps debug issues
        """
        # Create minimal input file with 1 client in project input dir
        input_file = project_root / "input" / "e2e_minimal_input.xlsx"
        df = create_test_input_dataframe(num_clients=1)
        df.to_excel(input_file, index=False, engine="openpyxl")

        try:
            result = self.run_pipeline(input_file, "en", project_root)

            assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
            assert "Pipeline completed successfully" in result.stdout

            # Verify single PDF was created
            output_dir = project_root / "output"
            pdfs = list((output_dir / "pdf_individual").glob("en_notice_*.pdf"))
            assert len(pdfs) == 1
        finally:
            # Cleanup input file
            if input_file.exists():
                input_file.unlink()

    def test_pipeline_validates_output_artifacts(
        self, tmp_path: Path, pipeline_input_file: Path, project_root: Path
    ) -> None:
        """Test that pipeline creates valid output artifacts.

        Real-world significance:
        - Pipeline produces JSON artifacts that are read by other steps
        - Artifacts must have correct schema (format, required fields)
        - JSON corruption would cause silent failures in downstream steps
        """
        result = self.run_pipeline(pipeline_input_file, "en", project_root)

        assert result.returncode == 0

        # Find and validate the preprocessed artifact
        output_dir = project_root / "output"
        artifacts = list((output_dir / "artifacts").glob("preprocessed_clients_*.json"))
        assert len(artifacts) >= 1, "Expected at least 1 preprocessed artifact"

        artifact = artifacts[0]
        with open(artifact) as f:
            data = json.load(f)

        # Validate artifact structure
        assert "run_id" in data
        assert "language" in data
        assert data["language"] == "en"
        assert "clients" in data
        assert len(data["clients"]) == 3
        assert "warnings" in data

        # Validate each client record
        for client in data["clients"]:
            assert "sequence" in client
            assert "client_id" in client
            assert "person" in client
            assert "school" in client
            assert "board" in client
            assert "contact" in client
            assert "vaccines_due" in client

    def test_placeholder_e2e_marker_applied(self) -> None:
        """Placeholder test ensuring e2e marker is recognized by pytest.

        Real-world significance:
        - E2E tests are marked so they can be run separately
        - Can run only E2E tests with: uv run pytest -m e2e
        """
        assert True
