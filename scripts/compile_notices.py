"""Compile per-client Typst notices into PDFs sequentially.

This lightweight helper keeps the compilation step in Python so future
enhancements (parallel workers, structured logging) can be layered on in a
follow-up. For now it mirrors the behaviour of the original shell script.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .config_loader import load_config

ROOT_DIR = Path(__file__).resolve().parent.parent


def discover_typst_files(artifact_dir: Path) -> list[Path]:
    return sorted(artifact_dir.glob("*.typ"))


def compile_file(
    typ_path: Path,
    pdf_dir: Path,
    *,
    typst_bin: str,
    font_path: Path | None,
    root_dir: Path,
    verbose: bool,
) -> None:
    pdf_path = pdf_dir / f"{typ_path.stem}.pdf"
    command = [typst_bin, "compile"]
    if font_path:
        command.extend(["--font-path", str(font_path)])
    command.extend(["--root", str(root_dir), str(typ_path), str(pdf_path)])
    subprocess.run(command, check=True)
    if verbose:
        print(f"Compiled {typ_path.name} -> {pdf_path.name}")


def compile_typst_files(
    artifact_dir: Path,
    pdf_dir: Path,
    *,
    typst_bin: str,
    font_path: Path | None,
    root_dir: Path,
    verbose: bool,
) -> int:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    typ_files = discover_typst_files(artifact_dir)
    if not typ_files:
        print(f"No Typst artifacts found in {artifact_dir}.")
        return 0

    for typ_path in typ_files:
        compile_file(
            typ_path,
            pdf_dir,
            typst_bin=typst_bin,
            font_path=font_path,
            root_dir=root_dir,
            verbose=verbose,
        )
    return len(typ_files)


def compile_with_config(
    artifact_dir: Path,
    output_dir: Path,
    config_path: Path | None = None,
) -> int:
    """Compile Typst files using configuration from parameters.yaml.

    Parameters
    ----------
    artifact_dir : Path
        Directory containing Typst artifacts (.typ files).
    output_dir : Path
        Directory where compiled PDFs will be written.
    config_path : Path, optional
        Path to parameters.yaml. If not provided, uses default location.

    Returns
    -------
    int
        Number of files compiled.
    """
    config = load_config(config_path)

    typst_config = config.get("typst", {})
    font_path_str = typst_config.get("font_path", "/usr/share/fonts/truetype/freefont/")
    typst_bin = typst_config.get("bin", "typst")

    # Allow TYPST_BIN environment variable to override config
    typst_bin = os.environ.get("TYPST_BIN", typst_bin)

    font_path = Path(font_path_str) if font_path_str else None

    return compile_typst_files(
        artifact_dir,
        output_dir,
        typst_bin=typst_bin,
        font_path=font_path,
        root_dir=ROOT_DIR,
        verbose=False,
    )


def main(artifact_dir: Path, output_dir: Path, config_path: Path | None = None) -> int:
    """Main entry point for Typst compilation.

    Parameters
    ----------
    artifact_dir : Path
        Directory containing Typst artifacts.
    output_dir : Path
        Directory for output PDFs.
    config_path : Path, optional
        Path to parameters.yaml configuration file.

    Returns
    -------
    int
        Number of files compiled.
    """
    compiled = compile_with_config(artifact_dir, output_dir, config_path)
    if compiled:
        print(f"Compiled {compiled} Typst file(s) to PDFs in {output_dir}.")
    return compiled


if __name__ == "__main__":
    main()
