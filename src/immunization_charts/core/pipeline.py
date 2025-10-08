"""
Main pipeline orchestration for immunization charts.

This module provides the main pipeline class that orchestrates the entire
immunization chart generation process from data loading to PDF compilation.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

from ..core.processor import ClientDataProcessor
from ..data.loader import load_and_validate_data
from ..data.splitter import process_batch_files, separate_by_school, split_batches
from ..templates.compiler import compile_templates_to_pdf
from ..templates.generator import generate_templates_for_language

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "config"))
from settings import config

logger = logging.getLogger(__name__)


class ImmunizationPipeline:
    """Main pipeline class for processing immunization data and generating charts."""

    def __init__(self, config_instance=None):
        """Initialize the pipeline.

        Args:
            config_instance: Configuration instance to use (defaults to global config)
        """
        self.config = config_instance or config
        self.start_time = None
        self.step_times = {}

    def run_preprocessing(
        self, input_file: str, output_dir: str, language: str = "english"
    ) -> None:
        """Run the preprocessing step of the pipeline.

        Args:
            input_file: Path to input data file
            output_dir: Base output directory
            language: Language for processing ("english" or "french")
        """
        step_start = time.time()
        logger.info(f"Starting preprocessing for {input_file} in {language}")

        # Load and validate data
        df = load_and_validate_data(input_file, self.config.expected_columns)

        # Create output directories
        output_path = Path(output_dir)
        output_dir_school = output_path / "by_school"
        output_dir_batch = output_path / "batches"
        output_dir_final = output_path / f"json_{language}"

        # Separate by school
        separate_by_school(df, str(output_dir_school), "SCHOOL_NAME")

        # Split into batches
        split_batches(output_dir_school, output_dir_batch, self.config.batch_size)
        logger.info("Completed splitting into batches.")

        # Process each batch
        all_batch_files = sorted(output_dir_batch.glob("*.csv"))

        for batch_file in all_batch_files:
            logger.info(f"Processing batch file: {batch_file}")
            df_batch = self._load_batch_file(batch_file)

            # Create processor and build notices
            processor = ClientDataProcessor(
                df=df_batch,
                disease_map=self.config.disease_map,
                vaccine_ref=self.config.vaccine_reference,
                ignore_agents=self.config.ignore_agents,
                delivery_date=self.config.delivery_date,
                language=language,
            )

            processor.build_notices()
            processor.save_output(output_dir_final, batch_file.stem)

        step_end = time.time()
        self.step_times["preprocessing"] = step_end - step_start
        logger.info(
            f"Preprocessing completed in {self.step_times['preprocessing']:.2f} seconds"
        )

    def _load_batch_file(self, batch_file: Path):
        """Load a batch CSV file with proper encoding.

        Args:
            batch_file: Path to batch file

        Returns:
            Loaded DataFrame
        """
        import pandas as pd

        df_batch = pd.read_csv(
            batch_file, sep=";", engine="python", encoding="latin-1", quotechar='"'
        )

        # Combine address fields if they exist
        if "STREET_ADDRESS_LINE_2" in df_batch.columns:
            df_batch["STREET_ADDRESS"] = (
                df_batch["STREET_ADDRESS_LINE_1"].fillna("")
                + " "
                + df_batch["STREET_ADDRESS_LINE_2"].fillna("")
            )
            df_batch.drop(
                columns=["STREET_ADDRESS_LINE_1", "STREET_ADDRESS_LINE_2"], inplace=True
            )

        return df_batch

    def _run_quality_checks(self, output_dir: Path, language: str) -> None:
        """Run quality checks on generated files.

        Args:
            output_dir: Base output directory
            language: Language for quality checks
        """
        json_dir = output_dir / f"json_{language}"

        # Check PDF files
        pdf_files = list(json_dir.glob("*.pdf"))
        if pdf_files:
            from ..utils.pdf_utils import count_pdf_pages

            for pdf_file in pdf_files:
                page_count = count_pdf_pages(pdf_file)
                if page_count:
                    logger.info(f"PDF {pdf_file.name}: {page_count} pages")
        else:
            logger.warning("No PDF files found for quality checks")

    def run_full_pipeline(
        self, input_file: str, output_dir: str, language: str = "english"
    ) -> dict:
        """Run the complete immunization chart generation pipeline.

        Args:
            input_file: Path to input data file
            output_dir: Base output directory
            language: Language for processing ("english" or "french")

        Returns:
            Dictionary containing timing information and results
        """
        self.start_time = time.time()
        logger.info(f"Starting full pipeline for {input_file} in {language}")

        try:
            # Step 1: Preprocessing
            self.run_preprocessing(input_file, output_dir, language)

            # Step 2: Template Generation
            step_start = time.time()
            logger.info("Starting template generation...")
            templates = generate_templates_for_language(Path(output_dir), language)
            step_end = time.time()
            self.step_times["template_generation"] = step_end - step_start
            logger.info(
                f"Template generation completed in {self.step_times['template_generation']:.2f} seconds"
            )

            # Step 3: PDF Compilation
            step_start = time.time()
            logger.info("Starting PDF compilation...")
            pdfs = compile_templates_to_pdf(Path(output_dir), language)
            step_end = time.time()
            self.step_times["pdf_compilation"] = step_end - step_start
            logger.info(
                f"PDF compilation completed in {self.step_times['pdf_compilation']:.2f} seconds"
            )

            # Step 4: Quality Checks
            step_start = time.time()
            logger.info("Starting quality checks...")
            self._run_quality_checks(Path(output_dir), language)
            step_end = time.time()
            self.step_times["quality_checks"] = step_end - step_start
            logger.info(
                f"Quality checks completed in {self.step_times['quality_checks']:.2f} seconds"
            )

            total_time = time.time() - self.start_time
            self.step_times["total"] = total_time

            logger.info(f"Pipeline completed successfully in {total_time:.2f} seconds")
            logger.info(f"Generated {len(templates)} templates and {len(pdfs)} PDFs")

            return {
                "success": True,
                "timing": self.step_times,
                "output_dir": output_dir,
                "language": language,
                "templates_generated": len(templates),
                "pdfs_generated": len(pdfs),
            }

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return {"success": False, "error": str(e), "timing": self.step_times}

    def get_timing_summary(self) -> str:
        """Get a formatted timing summary.

        Returns:
            Formatted string with timing information
        """
        if not self.step_times:
            return "No timing data available"

        summary = "Pipeline Timing Summary:\n"
        for step, duration in self.step_times.items():
            if step != "total":
                summary += f"  - {step.capitalize()}: {duration:.2f}s\n"

        if "total" in self.step_times:
            summary += f"  - Total Time: {self.step_times['total']:.2f}s"

        return summary
