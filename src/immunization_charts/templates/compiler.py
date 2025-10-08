"""
PDF compilation for immunization charts.

This module provides functionality to compile Typst templates
into PDF files using the Typst compiler.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class PDFCompiler:
    """Handles compilation of Typst templates to PDF files."""

    def __init__(
        self, font_path: Optional[str] = None, root_dir: Optional[Path] = None
    ):
        """Initialize the PDF compiler.

        Args:
            font_path: Path to fonts directory for Typst
            root_dir: Root directory for Typst compilation
        """
        self.font_path = font_path or "/usr/share/fonts/truetype/freefont/"
        self.root_dir = root_dir

    def compile_templates(self, output_dir: Path, language: str) -> List[Path]:
        """Compile all Typst templates in the output directory to PDFs.

        Args:
            output_dir: Directory containing .typ template files
            language: Language for compilation ("english" or "french")

        Returns:
            List of generated PDF files
        """
        json_dir = output_dir / f"json_{language}"
        if not json_dir.exists():
            logger.error(f"JSON directory not found: {json_dir}")
            return []

        typ_files = list(json_dir.glob("*.typ"))
        if not typ_files:
            logger.warning(f"No Typst template files found in {json_dir}")
            return []

        generated_pdfs = []

        for typ_file in typ_files:
            logger.info(f"Compiling template: {typ_file}")

            pdf_file = self._compile_single_template(typ_file)
            if pdf_file:
                generated_pdfs.append(pdf_file)

        logger.info(f"Compiled {len(generated_pdfs)} PDF files")
        return generated_pdfs

    def _compile_single_template(self, typ_file: Path) -> Optional[Path]:
        """Compile a single Typst template to PDF.

        Args:
            typ_file: Path to .typ template file

        Returns:
            Path to generated PDF file, or None if failed
        """
        try:
            # Prepare command
            cmd = ["typst", "compile"]

            if self.font_path and Path(self.font_path).exists():
                cmd.extend(["--font-path", self.font_path])

            if self.root_dir:
                cmd.extend(["--root", str(self.root_dir)])

            cmd.append(str(typ_file))

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Run Typst compilation
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Check if PDF was generated
            pdf_file = typ_file.with_suffix(".pdf")
            if pdf_file.exists():
                logger.info(f"Generated PDF: {pdf_file}")
                return pdf_file
            else:
                logger.error(f"PDF file not created: {pdf_file}")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"PDF compilation failed for {typ_file}: {e}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("Typst compiler not found. Please install Typst.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error compiling {typ_file}: {e}")
            return None

    def validate_pdfs(self, pdf_files: List[Path]) -> List[Path]:
        """Validate that generated PDF files are readable.

        Args:
            pdf_files: List of PDF files to validate

        Returns:
            List of valid PDF files
        """
        valid_pdfs = []

        for pdf_file in pdf_files:
            if self._validate_single_pdf(pdf_file):
                valid_pdfs.append(pdf_file)

        logger.info(f"Validated {len(valid_pdfs)} out of {len(pdf_files)} PDF files")
        return valid_pdfs

    def _validate_single_pdf(self, pdf_file: Path) -> bool:
        """Validate a single PDF file.

        Args:
            pdf_file: Path to PDF file to validate

        Returns:
            True if PDF is valid, False otherwise
        """
        try:
            from ..utils.pdf_utils import validate_pdf_file

            return validate_pdf_file(pdf_file)
        except Exception as e:
            logger.error(f"Error validating PDF {pdf_file}: {e}")
            return False


def compile_templates_to_pdf(
    output_dir: Path,
    language: str,
    font_path: Optional[str] = None,
    root_dir: Optional[Path] = None,
) -> List[Path]:
    """Convenience function to compile templates to PDFs.

    Args:
        output_dir: Base output directory
        language: Language for compilation
        font_path: Path to fonts directory
        root_dir: Root directory for Typst compilation

    Returns:
        List of generated PDF files
    """
    compiler = PDFCompiler(font_path, root_dir)
    return compiler.compile_templates(output_dir, language)
