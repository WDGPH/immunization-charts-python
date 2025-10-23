"""Cleanup module for removing intermediate pipeline artifacts.

Removes specified directories and file types from the output directory to reduce
storage footprint after the pipeline completes successfully."""

import shutil
from pathlib import Path

try:
    from .config_loader import load_config
except ImportError:  # pragma: no cover - fallback for CLI execution
    from config_loader import load_config


def safe_delete(path: Path):
    """Safely delete a file or directory if it exists."""
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def remove_files_with_ext(base_dir: Path, extensions):
    """Remove files with specified extensions in the given directory."""
    if not base_dir.exists():
        return
    for ext in extensions:
        for file in base_dir.glob(f"*.{ext}"):
            safe_delete(file)


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

    # Remove configured directories
    for folder_name in remove_dirs:
        safe_delete(output_dir / folder_name)


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
    raise RuntimeError(
        "cleanup.py should not be invoked directly. Use run_pipeline.py instead."
    )
