"""VIPER Pipeline Orchestrator.

This script orchestrates the end-to-end immunization notice generation pipeline.
It executes each step in sequence, handles errors, and provides detailed timing and
progress information.

**Error Handling Philosophy:**

The pipeline distinguishes between critical and optional steps:

- **Critical Steps** (Notice generation, Compilation, PDF validation) implement fail-fast:
  - Any error halts the pipeline immediately
  - No partial output; users get deterministic results
  - Pipeline exits with code 1; user must investigate and retry

- **Optional Steps** (QR codes, Encryption, Batching) implement per-item recovery:
  - Individual item failures (PDF, client, batch) are logged and skipped
  - Remaining items continue processing
  - Pipeline completes successfully even if some items failed
  - Users are shown summary of successes, skipped, and failed items

- **Infrastructure Errors** (missing files, config errors) always fail-fast:
  - Caught and raised immediately; no recovery attempts
  - Prevents confusing partial output caused by misconfiguration
  - Pipeline exits with code 1

**Exit Codes:**
- 0: Pipeline completed successfully
- 1: Pipeline failed (critical step error or infrastructure error)
- 2: User cancelled (output preparation step)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Import pipeline steps
from . import batch_pdfs, cleanup, compile_notices, count_pdfs
from . import (
    encrypt_notice,
    generate_notices,
    generate_qr_codes,
    prepare_output,
    preprocess,
)
from .config_loader import load_config
from .enums import Language

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_INPUT_DIR = ROOT_DIR / "input"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output"
DEFAULT_TEMPLATES_ASSETS_DIR = ROOT_DIR / "templates" / "assets"
DEFAULT_CONFIG_DIR = ROOT_DIR / "config"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the VIPER immunization notice generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s students.xlsx en
  %(prog)s students.xlsx fr
        """,
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Name of the input file (e.g., students.xlsx)",
    )
    parser.add_argument(
        "language",
        choices=sorted(Language.all_codes()),
        help=f"Language for output ({', '.join(sorted(Language.all_codes()))})",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help=f"Config directory (default: {DEFAULT_CONFIG_DIR})",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and raise errors if invalid."""
    if args.input_file and not (args.input_dir / args.input_file).exists():
        raise FileNotFoundError(
            f"Input file not found: {args.input_dir / args.input_file}"
        )


def print_header(input_file: str) -> None:
    """Print the pipeline header."""
    print()
    print("🚀 Starting VIPER Pipeline")
    print(f"🗂️  Input File: {input_file}")
    print()


def print_step(step_num: int, description: str) -> None:
    """Print a step header."""
    print()
    print(f"{'=' * 60}")
    print(f"Step {step_num}: {description}")
    print(f"{'=' * 60}")


def print_step_complete(step_num: int, description: str, duration: float) -> None:
    """Print step completion message."""
    print(f"✅ Step {step_num}: {description} complete in {duration:.1f} seconds.")


def run_step_1_prepare_output(
    output_dir: Path,
    log_dir: Path,
    auto_remove: bool,
) -> bool:
    """Step 1: Prepare output directory."""
    print_step(1, "Preparing output directory")

    success = prepare_output.prepare_output_directory(
        output_dir=output_dir,
        log_dir=log_dir,
        auto_remove=auto_remove,
    )

    if not success:
        # User cancelled - exit with code 2 to match shell script
        return False

    return True


def run_step_2_preprocess(
    input_dir: Path,
    input_file: str,
    output_dir: Path,
    language: str,
    run_id: str,
) -> int:
    """Step 2: Preprocessing.

    Returns:
        Total number of clients processed.
    """
    print_step(2, "Preprocessing")

    # Configure logging
    log_path = preprocess.configure_logging(output_dir, run_id)

    # Load and process input data
    input_path = input_dir / input_file
    df_raw = preprocess.read_input(input_path)
    df = preprocess.ensure_required_columns(df_raw)

    # Load configuration
    vaccine_reference_path = preprocess.VACCINE_REFERENCE_PATH
    vaccine_reference = json.loads(vaccine_reference_path.read_text(encoding="utf-8"))

    # Build preprocessing result
    result = preprocess.build_preprocess_result(
        df, language, vaccine_reference, preprocess.IGNORE_AGENTS
    )

    # Write artifact
    artifact_path = preprocess.write_artifact(
        output_dir / "artifacts", language, run_id, result
    )

    print(f"📄 Preprocessed artifact: {artifact_path}")
    print(f"Preprocess log written to {log_path}")
    if result.warnings:
        print("Warnings detected during preprocessing:")
        for warning in result.warnings:
            print(f" - {warning}")

    # Summarize the preprocessed clients
    total_clients = len(result.clients)
    print(f"👥 Clients normalized: {total_clients}")
    return total_clients


def run_step_3_generate_qr_codes(
    output_dir: Path,
    run_id: str,
    config_dir: Path,
) -> int:
    """Step 3: Generating QR code PNG files (optional).

    Returns:
        Number of QR codes generated (0 if disabled or no clients).
    """
    print_step(3, "Generating QR codes")

    config = load_config(config_dir / "parameters.yaml")

    qr_config = config.get("qr", {})
    qr_enabled = qr_config.get("enabled", True)

    if not qr_enabled:
        print("QR code generation disabled in configuration")
        return 0

    artifact_path = output_dir / "artifacts" / f"preprocessed_clients_{run_id}.json"
    artifacts_dir = output_dir / "artifacts"
    parameters_path = config_dir / "parameters.yaml"

    # Generate QR codes
    generated = generate_qr_codes.generate_qr_codes(
        artifact_path,
        artifacts_dir,
        parameters_path,
    )
    if generated:
        print(
            f"Generated {len(generated)} QR code PNG file(s) in {artifacts_dir}/qr_codes/"
        )
    return len(generated)


def run_step_4_generate_notices(
    output_dir: Path,
    run_id: str,
    assets_dir: Path,
    config_dir: Path,
) -> None:
    """Step 4: Generating Typst templates."""
    print_step(4, "Generating Typst templates")

    artifact_path = output_dir / "artifacts" / f"preprocessed_clients_{run_id}.json"
    artifacts_dir = output_dir / "artifacts"
    logo_path = assets_dir / "logo.png"
    signature_path = assets_dir / "signature.png"
    parameters_path = config_dir / "parameters.yaml"

    # Generate Typst files using main function
    generated = generate_notices.main(
        artifact_path,
        artifacts_dir,
        logo_path,
        signature_path,
        parameters_path,
    )
    print(f"Generated {len(generated)} Typst files in {artifacts_dir}")


def run_step_5_compile_notices(
    output_dir: Path,
    config_dir: Path,
) -> None:
    """Step 5: Compiling Typst templates to PDFs."""
    print_step(5, "Compiling Typst templates")

    # Load and validate configuration (fail-fast if invalid)
    load_config(config_dir / "parameters.yaml")

    artifacts_dir = output_dir / "artifacts"
    pdf_dir = output_dir / "pdf_individual"
    parameters_path = config_dir / "parameters.yaml"

    # Compile Typst files using config-driven function
    compiled = compile_notices.compile_with_config(
        artifacts_dir,
        pdf_dir,
        parameters_path,
    )
    if compiled:
        print(f"Compiled {compiled} Typst file(s) to PDFs in {pdf_dir}.")


def run_step_6_validate_pdfs(
    output_dir: Path,
    language: str,
    run_id: str,
) -> None:
    """Step 6: Validating compiled PDF lengths."""
    print_step(6, "Validating compiled PDF lengths")

    pdf_dir = output_dir / "pdf_individual"
    metadata_dir = output_dir / "metadata"
    count_json = metadata_dir / f"{language}_page_counts_{run_id}.json"

    # Count and validate PDFs
    count_pdfs.main(
        pdf_dir,
        language=language,
        verbose=False,
        json_output=count_json,
    )


def run_step_7_encrypt_pdfs(
    output_dir: Path,
    language: str,
    run_id: str,
) -> None:
    """Step 7: Encrypting PDF notices (optional)."""
    print_step(7, "Encrypting PDF notices")

    pdf_dir = output_dir / "pdf_individual"
    artifacts_dir = output_dir / "artifacts"
    json_file = artifacts_dir / f"preprocessed_clients_{run_id}.json"

    # Encrypt PDFs using the combined preprocessed clients JSON
    encrypt_notice.encrypt_pdfs_in_directory(
        pdf_directory=pdf_dir,
        json_file=json_file,
        language=language,
    )


def run_step_8_batch_pdfs(
    output_dir: Path,
    language: str,
    run_id: str,
    config_dir: Path,
) -> None:
    """Step 8: Batching PDFs (optional)."""
    print_step(8, "Batching PDFs")

    # Load and validate configuration (fail-fast if invalid)
    load_config(config_dir / "parameters.yaml")

    parameters_path = config_dir / "parameters.yaml"

    # Batch PDFs using config-driven function
    results = batch_pdfs.batch_pdfs_with_config(
        output_dir,
        language,
        run_id,
        parameters_path,
    )
    if results:
        print(f"Created {len(results)} batches in {output_dir / 'pdf_combined'}")


def run_step_9_cleanup(
    output_dir: Path,
    skip_cleanup: bool,
    config_dir: Path,
) -> None:
    """Step 9: Cleanup intermediate files."""
    print_step(9, "Cleanup")

    if skip_cleanup:
        print("Cleanup skipped (keep_intermediate_files enabled).")
    else:
        parameters_path = config_dir / "parameters.yaml"
        cleanup.main(output_dir, parameters_path)
        print("✅ Cleanup completed successfully.")


def print_summary(
    step_times: list[tuple[str, float]],
    total_duration: float,
    batch_size: int,
    group_by: str | None,
    total_clients: int,
    skip_cleanup: bool,
) -> None:
    """Print the pipeline summary."""
    print()
    print("🎉 Pipeline completed successfully!")
    print("🕒 Time Summary:")
    for step_name, duration in step_times:
        print(f"  - {step_name:<25} {duration:.1f}s")
    print(f"  - {'─' * 25} {'─' * 6}")
    print(f"  - {'Total Time':<25} {total_duration:.1f}s")
    print()

    # Only show batch info if batching is actually enabled
    if batch_size > 0:
        print(f"📦 Batch size:             {batch_size}")
        if group_by == "school":
            print("🏫 Batch scope:            School")
        elif group_by == "board":
            print("🏢 Batch scope:            Board")
        else:
            print("🏷️  Batch scope:            Sequential")

    print(f"👥 Clients processed:      {total_clients}")
    if skip_cleanup:
        print("🧹 Cleanup:                Skipped")


def main() -> int:
    """Run the pipeline orchestrator."""
    try:
        args = parse_args()
        validate_args(args)
    except (ValueError, SystemExit) as exc:
        if isinstance(exc, ValueError):
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        raise

    # Setup paths and load configuration
    output_dir = args.output_dir.resolve()
    config_dir = args.config_dir.resolve()
    log_dir = output_dir / "logs"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    # Load configuration
    try:
        config = load_config(config_dir / "parameters.yaml")
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Extract config settings
    pipeline_config = config.get("pipeline", {})
    encryption_enabled = config.get("encryption", {}).get("enabled", False)
    auto_remove_output = pipeline_config.get("auto_remove_output", False)
    keep_intermediate = pipeline_config.get("keep_intermediate_files", False)

    print_header(args.input_file)

    total_start = time.time()
    step_times = []
    total_clients = 0

    try:
        # Step 1: Prepare output directory
        step_start = time.time()
        if not run_step_1_prepare_output(output_dir, log_dir, auto_remove_output):
            return 2  # User cancelled
        step_duration = time.time() - step_start
        step_times.append(("Output Preparation", step_duration))
        print_step_complete(1, "Output directory prepared", step_duration)

        # Step 2: Preprocessing
        step_start = time.time()
        total_clients = run_step_2_preprocess(
            args.input_dir,
            args.input_file,
            output_dir,
            args.language,
            run_id,
        )
        step_duration = time.time() - step_start
        step_times.append(("Preprocessing", step_duration))
        print_step_complete(2, "Preprocessing", step_duration)

        # Step 3: Generating QR Codes (optional)
        step_start = time.time()
        qr_count = run_step_3_generate_qr_codes(
            output_dir,
            run_id,
            config_dir,
        )
        step_duration = time.time() - step_start
        if qr_count > 0:
            step_times.append(("QR Code Generation", step_duration))
            print_step_complete(3, "QR code generation", step_duration)
        else:
            print("QR code generation skipped (disabled or no clients).")

        # Step 4: Generating Notices
        step_start = time.time()
        run_step_4_generate_notices(
            output_dir,
            run_id,
            DEFAULT_TEMPLATES_ASSETS_DIR,
            config_dir,
        )
        step_duration = time.time() - step_start
        step_times.append(("Template Generation", step_duration))
        print_step_complete(4, "Template generation", step_duration)

        # Step 5: Compiling Notices
        step_start = time.time()
        run_step_5_compile_notices(output_dir, config_dir)
        step_duration = time.time() - step_start
        step_times.append(("Template Compilation", step_duration))
        print_step_complete(5, "Compilation", step_duration)

        # Step 6: Validating PDFs
        step_start = time.time()
        run_step_6_validate_pdfs(output_dir, args.language, run_id)
        step_duration = time.time() - step_start
        step_times.append(("PDF Validation", step_duration))
        print_step_complete(6, "Length validation", step_duration)

        # Step 7: Encrypting PDFs (optional)
        if encryption_enabled:
            step_start = time.time()
            run_step_7_encrypt_pdfs(output_dir, args.language, run_id)
            step_duration = time.time() - step_start
            step_times.append(("PDF Encryption", step_duration))
            print_step_complete(7, "Encryption", step_duration)

        # Step 8: Batching PDFs (optional, skipped if encryption enabled)
        batching_was_run = False
        if not encryption_enabled:
            batching_config = config.get("batching", {})
            batch_size = batching_config.get("batch_size", 0)

            if batch_size > 0:
                step_start = time.time()
                run_step_8_batch_pdfs(
                    output_dir,
                    args.language,
                    run_id,
                    config_dir,
                )
                step_duration = time.time() - step_start
                step_times.append(("PDF Batching", step_duration))
                print_step_complete(8, "Batching", step_duration)
                batching_was_run = True
            else:
                print_step(8, "Batching")
                print("Batching skipped (batch_size set to 0).")
        else:
            print_step(8, "Batching")
            print("Batching skipped (encryption enabled).")

        # Step 9: Cleanup
        run_step_9_cleanup(output_dir, keep_intermediate, config_dir)

        # Print summary
        total_duration = time.time() - total_start

        # Only show batching config if batching actually ran
        if batching_was_run:
            batching_config = config.get("batching", {})
            batch_size = batching_config.get("batch_size", 0)
            group_by = batching_config.get("group_by")
        else:
            batch_size = 0
            group_by = None

        print_summary(
            step_times,
            total_duration,
            batch_size,
            group_by,
            total_clients,
            keep_intermediate,
        )

        return 0

    except Exception as exc:
        print(f"\n❌ Pipeline failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
