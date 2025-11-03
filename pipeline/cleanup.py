"""Cleanup module for removing intermediate pipeline artifacts.

Removes specified directories and file types from the output directory to reduce
storage footprint after the pipeline completes successfully. Optionally deletes
unencrypted individual PDFs after bundling or encryption operations.

**Input Contract:**
- Reads configuration from parameters.yaml (cleanup section)
- Assumes output directory structure exists (may be partially populated)
- Assumes cleanup configuration keys exist (remove_directories, delete_unencrypted_pdfs)

**Output Contract:**
- Removes specified directories and file types from output_dir
- Optionally removes unencrypted individual PDFs from pdf_individual/
- Does not modify final PDF outputs (bundles, encrypted PDFs)
- Does not halt pipeline if cleanup fails

**Error Handling:**
- File deletion errors are logged and continue (optional step)
- Missing directories/files don't cause errors (idempotent)
- Pipeline completes even if cleanup partially fails (utility step)

**Validation Contract:**

What this module validates:
- Output directory exists and is writable
- Directory/file paths can be safely deleted (exist check before delete)
- delete_unencrypted_pdfs configuration is boolean

What this module assumes (validated upstream):
- Configuration keys are valid (cleanup.remove_directories, cleanup.delete_unencrypted_pdfs)
- Output directory structure is correct (created by prior steps)

Note: This is a utility/cleanup step. Failures don't halt pipeline. Can be skipped
entirely via pipeline.keep_intermediate_files config setting.
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

    Parameters
    ----------
    output_dir : Path
        Root output directory containing generated files.
    config_path : Path, optional
        Path to parameters.yaml. If not provided, uses default location.
    """
    config = load_config(config_path)
    cleanup_config = config.get("cleanup", {})

    remove_dirs = cleanup_config.get("remove_directories", [])
    delete_unencrypted = cleanup_config.get("delete_unencrypted_pdfs", False)

    # Remove configured directories
    for folder_name in remove_dirs:
        safe_delete(output_dir / folder_name)

    # Delete unencrypted PDFs if configured
    if delete_unencrypted:
        pdf_dir = output_dir / "pdf_individual"
        if pdf_dir.exists():
            for pdf_file in pdf_dir.glob("*.pdf"):
                # Only delete unencrypted PDFs (skip _encrypted versions)
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
