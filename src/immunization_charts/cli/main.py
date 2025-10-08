"""
Command-line interface for immunization charts.

This module provides the main CLI entry point for the immunization charts application.
"""

import argparse
import logging
import sys
from pathlib import Path

from ..core.pipeline import ImmunizationPipeline

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "config"))
from settings import config


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("immunization_charts.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Generate personalized immunization history charts and notice letters"
    )

    parser.add_argument("input_file", help="Path to input data file (Excel or CSV)")

    parser.add_argument(
        "language",
        choices=["english", "french"],
        help="Language for processing (english or french)",
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for generated files (default: output)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument(
        "--preprocess-only", action="store_true", help="Only run preprocessing step"
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    # Create pipeline
    pipeline = ImmunizationPipeline()

    try:
        if args.preprocess_only:
            # Run only preprocessing
            pipeline.run_preprocessing(str(input_path), args.output_dir, args.language)
            logger.info("Preprocessing completed successfully")
        else:
            # Run full pipeline
            result = pipeline.run_full_pipeline(
                str(input_path), args.output_dir, args.language
            )

            if result["success"]:
                logger.info("Pipeline completed successfully")
                print(pipeline.get_timing_summary())
            else:
                logger.error(f"Pipeline failed: {result['error']}")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
