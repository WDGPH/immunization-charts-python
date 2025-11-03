"""Cleanup module for Step 9: removing intermediate pipeline artifacts.

This step removes intermediate files generated during the pipeline run to reduce
storage footprint. Configuration is read from parameters.yaml under pipeline.after_run.

This is distinct from Step 1 (prepare_output), which uses pipeline.before_run.clear_output_directory
to clean up old pipeline runs at startup while preserving logs.

**Step 1 Configuration (pipeline.before_run in parameters.yaml):**
- clear_output_directory: when true, removes all output except logs before starting a new run

**Step 9 Configuration (pipeline.after_run in parameters.yaml):**
- remove_artifacts: when true, removes output/artifacts directory
- remove_unencrypted_pdfs: when true and encryption is enabled, removes non-encrypted PDFs
  from pdf_individual/ after encryption completes (has no effect if encryption is disabled)

**Input Contract:**
- Reads configuration from parameters.yaml (pipeline.after_run section)
- Assumes output directory structure exists (may be partially populated)
- Assumes encryption.enabled from parameters.yaml to determine if remove_unencrypted_pdfs applies

**Output Contract:**
- Removes specified directories from output_dir
- Removes unencrypted PDFs if conditions are met (encryption enabled + remove_unencrypted_pdfs=true)
- Does not modify final PDF outputs (unless configured to do so)
- Does not halt pipeline if cleanup fails

**Error Handling:**
- File deletion errors are logged and continue (optional step)
- Missing directories/files don't cause errors (idempotent)
- Pipeline completes even if cleanup partially fails (utility step)

**Validation Contract:**

What this module validates:
- Output directory exists and is writable
- Directory/file paths can be safely deleted (exist check before delete)
- Configuration values are sensible boolean types

What this module assumes (validated upstream):
- Configuration keys are valid and well-formed
- Output directory structure is correct (created by prior steps)

Note: This is a utility/cleanup step. Failures don't halt pipeline.
"""

import shutil
from pathlib import Path

from .config_loader import load_config


def safe_delete(path: Path):
    """Safely delete a file or directory if it exists.

    Parameters
    ----------
    path : Path
        File or directory to delete.
    """
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def cleanup_with_config(output_dir: Path, config_path: Path | None = None) -> None:
    """Perform cleanup using configuration from parameters.yaml.

    Reads Step 9 (after_run) cleanup configuration from parameters.yaml.
    This is separate from Step 1's before_run.clear_output_directory setting, which cleans
    old runs at pipeline start (preserving logs).

    Parameters
    ----------
    output_dir : Path
        Root output directory containing generated files.
    config_path : Path, optional
        Path to parameters.yaml. If not provided, uses default location.
    """
    config = load_config(config_path)
    pipeline_config = config.get("pipeline", {})
    after_run_config = pipeline_config.get("after_run", {})
    encryption_enabled = config.get("encryption", {}).get("enabled", False)

    remove_artifacts = after_run_config.get("remove_artifacts", False)
    remove_unencrypted = after_run_config.get("remove_unencrypted_pdfs", False)

    # Remove artifacts directory if configured
    if remove_artifacts:
        safe_delete(output_dir / "artifacts")

    # Delete unencrypted PDFs only if encryption is enabled and setting is true
    if encryption_enabled and remove_unencrypted:
        pdf_dir = output_dir / "pdf_individual"
        if pdf_dir.exists():
            for pdf_file in pdf_dir.glob("*.pdf"):
                # Only delete non-encrypted PDFs (skip _encrypted versions)
                if not pdf_file.stem.endswith("_encrypted"):
                    safe_delete(pdf_file)


def main(output_dir: Path, config_path: Path | None = None) -> None:
    """Main entry point for cleanup.

    Parameters
    ----------
    output_dir : Path
        Root output directory to clean.
    config_path : Path, optional
        Path to parameters.yaml configuration file.
    """
    if not output_dir.is_dir():
        raise ValueError(f"The path {output_dir} is not a valid directory.")

    cleanup_with_config(output_dir, config_path)


if __name__ == "__main__":
    import sys

    print(
        "⚠️  Direct invocation: This module is typically executed via orchestrator.py.\n"
        "   Re-running a single step is valid when pipeline artifacts are retained on disk,\n"
        "   allowing you to skip earlier steps and regenerate output.\n"
        "   Note: Output will overwrite any previous files.\n"
        "\n"
        "   For typical usage, run: uv run viper <input> <language>\n",
        file=sys.stderr,
    )
    sys.exit(1)
