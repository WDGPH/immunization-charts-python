"""Compile per-client Typst notices into PDFs sequentially.

This lightweight helper keeps the compilation step in Python so future
enhancements (parallel workers, structured logging) can be layered on in a
follow-up. For now it mirrors the behaviour of the original shell script.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

# Defaults mirror the prior shell implementation while leaving room for future
# configurability.
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FONT_PATH = Path("/usr/share/fonts/truetype/freefont/")
DEFAULT_TYPST_BIN = os.environ.get("TYPST_BIN", "typst")


def discover_typst_files(artifact_dir: Path) -> list[Path]:
    return sorted(artifact_dir.glob("*.typ"))


def compile_file(
    typ_path: Path,
    pdf_dir: Path,
    *,
    typst_bin: str,
    font_path: Path | None,
    root_dir: Path,
) -> None:
    pdf_path = pdf_dir / f"{typ_path.stem}.pdf"
    command = [typst_bin, "compile"]
    if font_path:
        command.extend(["--font-path", str(font_path)])
    command.extend(["--root", str(root_dir), str(typ_path), str(pdf_path)])
    subprocess.run(command, check=True)
    print(f"Compiled {typ_path.name} -> {pdf_path.name}")


def compile_typst_files(
    artifact_dir: Path,
    pdf_dir: Path,
    *,
    typst_bin: str,
    font_path: Path | None,
    root_dir: Path,
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
        )
    return len(typ_files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile Typst notices into PDFs.")
    parser.add_argument("artifact_dir", type=Path, help="Directory containing Typst artifacts.")
    parser.add_argument("output_dir", type=Path, help="Directory to write compiled PDFs.")
    parser.add_argument(
        "--font-path",
        type=Path,
        default=DEFAULT_FONT_PATH,
        help="Optional font search path to pass to typst.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR,
        help="Typst root directory for resolving absolute imports.",
    )
    parser.add_argument(
        "--typst-bin",
        default=DEFAULT_TYPST_BIN,
        help="Typst executable to invoke (defaults to $TYPST_BIN or 'typst').",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    compiled = compile_typst_files(
        args.artifact_dir,
        args.output_dir,
        typst_bin=args.typst_bin,
        font_path=args.font_path,
        root_dir=args.root,
    )
    if compiled:
        print(f"Compiled {compiled} Typst files to PDFs.")


if __name__ == "__main__":
    main()
