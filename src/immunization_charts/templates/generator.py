"""
Template generation for immunization charts.

This module provides functionality to generate Typst templates
from processed JSON data for PDF compilation.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class TemplateGenerator:
    """Handles generation of Typst templates from JSON data."""

    def __init__(self, templates_dir: Path, assets_dir: Path, config_dir: Path):
        """Initialize the template generator.

        Args:
            templates_dir: Directory containing template scripts
            assets_dir: Directory containing assets (logo, signature)
            config_dir: Directory containing configuration files
        """
        self.templates_dir = templates_dir
        self.assets_dir = assets_dir
        self.config_dir = config_dir

    def generate_templates(self, output_dir: Path, language: str) -> List[Path]:
        """Generate Typst templates for all JSON files in the output directory.

        Args:
            output_dir: Directory containing JSON files
            language: Language for template generation ("english" or "french")

        Returns:
            List of generated .typ template files
        """
        json_dir = output_dir / f"json_{language}"
        if not json_dir.exists():
            logger.error(f"JSON directory not found: {json_dir}")
            return []

        json_files = list(json_dir.glob("*.json"))
        if not json_files:
            logger.warning(f"No JSON files found in {json_dir}")
            return []

        generated_templates = []

        for json_file in json_files:
            filename = json_file.stem
            logger.info(f"Generating template for {filename}")

            template_file = self._generate_single_template(json_dir, filename, language)

            if template_file:
                generated_templates.append(template_file)

        logger.info(f"Generated {len(generated_templates)} templates")
        return generated_templates

    def _generate_single_template(
        self, json_dir: Path, filename: str, language: str
    ) -> Optional[Path]:
        """Generate a single Typst template file.

        Args:
            json_dir: Directory containing JSON files
            filename: Base filename (without extension)
            language: Language for template generation

        Returns:
            Path to generated template file, or None if failed
        """
        template_script = self.templates_dir / f"{language}_template.sh"
        if not template_script.exists():
            logger.error(f"Template script not found: {template_script}")
            return None

        # Prepare paths
        logo_path = self.assets_dir / "logo.png"
        signature_path = self.assets_dir / "signature.png"
        parameters_path = self.config_dir / "parameters.yaml"

        # Check if required files exist
        for file_path in [logo_path, signature_path, parameters_path]:
            if not file_path.exists():
                logger.error(f"Required file not found: {file_path}")
                return None

        # Copy required files to output directory for relative paths
        import shutil

        copied_files = []
        try:
            # Copy logo
            logo_dest = json_dir / "logo.png"
            shutil.copy2(logo_path, logo_dest)
            copied_files.append(logo_dest)

            # Copy signature
            signature_dest = json_dir / "signature.png"
            shutil.copy2(signature_path, signature_dest)
            copied_files.append(signature_dest)

            # Copy parameters
            params_dest = json_dir / "parameters.yaml"
            shutil.copy2(parameters_path, params_dest)
            copied_files.append(params_dest)

            # Copy conf.typ
            conf_src = self.templates_dir / "conf.typ"
            conf_dest = json_dir / "conf.typ"
            shutil.copy2(conf_src, conf_dest)
            copied_files.append(conf_dest)

        except Exception as e:
            logger.error(f"Failed to copy required files: {e}")
            return None

        # Make template script executable
        template_script.chmod(0o755)

        # Run template generation script with relative paths
        try:
            cmd = [
                str(template_script),
                str(json_dir.absolute()),
                filename,
                "logo.png",  # Use relative path
                "signature.png",  # Use relative path
                "parameters.yaml",  # Use relative path
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, cwd=self.templates_dir, capture_output=True, text=True, check=True
            )

            # Check if template was generated
            template_file = json_dir / f"{filename}_immunization_notice.typ"
            if template_file.exists():
                logger.info(f"Generated template: {template_file}")
                return template_file
            else:
                logger.error(f"Template file not created: {template_file}")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Template generation failed for {filename}: {e}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating template for {filename}: {e}")
            return None
        finally:
            # Clean up copied files (except files needed for PDF compilation)
            keep_files = ["conf.typ", "parameters.yaml", "logo.png", "signature.png"]
            for file_path in copied_files:
                if file_path.name not in keep_files:  # Keep these for PDF compilation
                    try:
                        if file_path.exists():
                            file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to clean up {file_path}: {e}")


def generate_templates_for_language(
    output_dir: Path,
    language: str,
    templates_dir: Optional[Path] = None,
    assets_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> List[Path]:
    """Convenience function to generate templates for a specific language.

    Args:
        output_dir: Base output directory
        language: Language for template generation
        templates_dir: Directory containing template scripts (defaults to templates/)
        assets_dir: Directory containing assets (defaults to assets/)
        config_dir: Directory containing config files (defaults to config/)

    Returns:
        List of generated template files
    """
    if templates_dir is None:
        templates_dir = Path(__file__).parent.parent.parent.parent / "templates"
    if assets_dir is None:
        assets_dir = Path(__file__).parent.parent.parent.parent / "assets"
    if config_dir is None:
        config_dir = Path(__file__).parent.parent.parent.parent / "config"

    generator = TemplateGenerator(templates_dir, assets_dir, config_dir)
    return generator.generate_templates(output_dir, language)
