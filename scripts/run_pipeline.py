#!/usr/bin/env python3
"""VIPER Pipeline Orchestrator.

This script orchestrates the end-to-end immunization notice generation pipeline,
replacing the previous run_pipeline.sh shell script. It executes each step in
sequence, handles errors, and provides detailed timing and progress information.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Import pipeline steps
try:
    from . import batch_pdfs, cleanup, compile_notices, count_pdfs
    from . import generate_notices, prepare_output, preprocess
except ImportError:  # pragma: no cover - fallback for CLI execution
    import batch_pdfs
    import cleanup
    import compile_notices
    import count_pdfs
    import generate_notices
    import prepare_output
    import preprocess

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_INPUT_DIR = ROOT_DIR / "input"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output"
DEFAULT_ASSETS_DIR = ROOT_DIR / "assets"
DEFAULT_CONFIG_DIR = ROOT_DIR / "config"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the VIPER immunization notice generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s students.xlsx en
  %(prog)s students.xlsx fr --keep-intermediate-files
  %(prog)s students.xlsx en --batch-size 50 --batch-by-school
        """,
    )
    
    parser.add_argument(
        "input_file",
        type=str,
        help="Name of the input file (e.g., students.xlsx)",
    )
    parser.add_argument(
        "language",
        choices=["en", "fr"],
        help="Language for output (en or fr)",
    )
    parser.add_argument(
        "--keep-intermediate-files",
        action="store_true",
        help="Preserve .typ, .json, and per-client .pdf files",
    )
    parser.add_argument(
        "--remove-existing-output",
        action="store_true",
        help="Automatically remove existing output directory without prompt",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Enable batching with at most N clients per batch (0 disables batching)",
    )
    parser.add_argument(
        "--batch-by-school",
        action="store_true",
        help="Group batches by school identifier",
    )
    parser.add_argument(
        "--batch-by-board",
        action="store_true",
        help="Group batches by board identifier",
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
    
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and raise errors if invalid."""
    if args.batch_by_school and args.batch_by_board:
        raise ValueError("--batch-by-school and --batch-by-board cannot be used together")
    
    if args.batch_size < 0:
        raise ValueError("--batch-size must be a non-negative integer")


def print_header(input_file: str) -> None:
    """Print the pipeline header."""
    print()
    print("🚀 Starting VIPER Pipeline")
    print(f"🗂️  Input File: {input_file}")
    print()


def print_step(step_num: int, description: str) -> None:
    """Print a step header."""
    print()
    print(f"{'='*60}")
    print(f"Step {step_num}: {description}")
    print(f"{'='*60}")


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
    import json
    disease_map_path = preprocess.DISEASE_MAP_PATH
    vaccine_reference_path = preprocess.VACCINE_REFERENCE_PATH
    disease_map = json.loads(disease_map_path.read_text(encoding="utf-8"))
    vaccine_reference = json.loads(vaccine_reference_path.read_text(encoding="utf-8"))
    
    # Build preprocessing result
    result = preprocess.build_preprocess_result(
        df, language, disease_map, vaccine_reference, preprocess.IGNORE_AGENTS
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


def run_step_3_generate_notices(
    output_dir: Path,
    run_id: str,
    assets_dir: Path,
    config_dir: Path,
) -> None:
    """Step 3: Generating Typst templates."""
    print_step(3, "Generating Typst templates")
    
    artifact_path = output_dir / "artifacts" / f"preprocessed_clients_{run_id}.json"
    artifacts_dir = output_dir / "artifacts"
    logo_path = assets_dir / "logo.png"
    signature_path = assets_dir / "signature.png"
    parameters_path = config_dir / "parameters.yaml"
    
    # Read artifact and generate Typst files
    payload = generate_notices.read_artifact(artifact_path)
    generated = generate_notices.generate_typst_files(
        payload,
        artifacts_dir,
        logo_path,
        signature_path,
        parameters_path,
    )
    print(f"Generated {len(generated)} Typst files in {artifacts_dir} for language {payload.language}")


def run_step_4_compile_notices(
    output_dir: Path,
) -> None:
    """Step 4: Compiling Typst templates to PDFs."""
    print_step(4, "Compiling Typst templates")
    
    artifacts_dir = output_dir / "artifacts"
    pdf_dir = output_dir / "pdf_individual"
    
    # Compile Typst files
    compiled = compile_notices.compile_typst_files(
        artifacts_dir,
        pdf_dir,
        typst_bin=compile_notices.DEFAULT_TYPST_BIN,
        font_path=compile_notices.DEFAULT_FONT_PATH,
        root_dir=compile_notices.ROOT_DIR,
        verbose=False,  # quiet mode
    )
    if compiled:
        print(f"Compiled {compiled} Typst file(s) to PDFs in {pdf_dir}.")


def run_step_5_validate_pdfs(
    output_dir: Path,
    language: str,
    run_id: str,
) -> None:
    """Step 5: Validating compiled PDF lengths."""
    print_step(5, "Validating compiled PDF lengths")
    
    pdf_dir = output_dir / "pdf_individual"
    metadata_dir = output_dir / "metadata"
    count_json = metadata_dir / f"{language}_page_counts_{run_id}.json"
    
    # Discover and count PDFs
    files = count_pdfs.discover_pdfs(pdf_dir)
    filtered = count_pdfs.filter_by_language(files, language)
    results, buckets = count_pdfs.summarize_pdfs(filtered)
    count_pdfs.print_summary(results, buckets, language=language, verbose=False)
    count_pdfs.write_json(results, buckets, target=count_json, language=language)


def run_step_6_batch_pdfs(
    output_dir: Path,
    language: str,
    run_id: str,
    batch_size: int,
    batch_by_school: bool,
    batch_by_board: bool,
) -> None:
    """Step 6: Batching PDFs (optional)."""
    print_step(6, "Batching PDFs")
    
    if batch_size <= 0:
        print("📦 Step 6: Batching skipped (batch size <= 0).")
        return
    
    # Create batch configuration
    config = batch_pdfs.BatchConfig(
        output_dir=output_dir.resolve(),
        language=language,
        batch_size=batch_size,
        batch_by_school=batch_by_school,
        batch_by_board=batch_by_board,
        run_id=run_id,
    )
    
    # Execute batching
    results = batch_pdfs.batch_pdfs(config)
    if results:
        print(f"Created {len(results)} batches in {config.output_dir / 'pdf_combined'}")
    else:
        print("No batches created.")


def run_step_7_cleanup(
    output_dir: Path,
    skip_cleanup: bool,
) -> None:
    """Step 7: Cleanup intermediate files."""
    print()
    
    if skip_cleanup:
        print("🧹 Step 7: Cleanup skipped (--keep-intermediate-files flag).")
    else:
        print("🧹 Step 7: Cleanup started...")
        cleanup.cleanup(output_dir)
        print("✅ Cleanup completed successfully.")


def print_summary(
    step_times: list[tuple[str, float]],
    total_duration: float,
    batch_size: int,
    batch_by_school: bool,
    batch_by_board: bool,
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
    print(f"📦 Batch size:             {batch_size}")
    if batch_by_school:
        print("🏫 Batch scope:            School")
    elif batch_by_board:
        print("🏢 Batch scope:            Board")
    else:
        print("🏷️  Batch scope:            Sequential")
    print(f"👥 Clients processed:      {total_clients}")
    if skip_cleanup:
        print("🧹 Cleanup:                Skipped")


def main(argv: Optional[list[str]] = None) -> int:
    """Run the pipeline orchestrator."""
    try:
        args = parse_args() if argv is None else argparse.Namespace(**dict(
            parse_args().__dict__, **vars(parse_args().__dict__)
        ))
        if argv is not None:
            # For testing: re-parse with provided argv
            parser = argparse.ArgumentParser()
            args = parse_args()
        
        validate_args(args)
    except (ValueError, SystemExit) as exc:
        if isinstance(exc, ValueError):
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        raise
    
    # Setup paths
    output_dir = args.output_dir.resolve()
    log_dir = output_dir / "logs"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    
    print_header(args.input_file)
    
    total_start = time.time()
    step_times = []
    total_clients = 0
    
    try:
        # Step 1: Prepare output directory
        step_start = time.time()
        if not run_step_1_prepare_output(output_dir, log_dir, args.remove_existing_output):
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
        
        # Step 3: Generating Notices
        step_start = time.time()
        run_step_3_generate_notices(
            output_dir,
            run_id,
            DEFAULT_ASSETS_DIR,
            DEFAULT_CONFIG_DIR,
        )
        step_duration = time.time() - step_start
        step_times.append(("Template Generation", step_duration))
        print_step_complete(3, "Template generation", step_duration)
        
        # Step 4: Compiling Notices
        step_start = time.time()
        run_step_4_compile_notices(output_dir)
        step_duration = time.time() - step_start
        step_times.append(("Template Compilation", step_duration))
        print_step_complete(4, "Compilation", step_duration)
        
        # Step 5: Validating PDFs
        step_start = time.time()
        run_step_5_validate_pdfs(output_dir, args.language, run_id)
        step_duration = time.time() - step_start
        step_times.append(("PDF Validation", step_duration))
        print_step_complete(5, "Length validation", step_duration)
        
        # Step 6: Batching PDFs
        step_start = time.time()
        run_step_6_batch_pdfs(
            output_dir,
            args.language,
            run_id,
            args.batch_size,
            args.batch_by_school,
            args.batch_by_board,
        )
        step_duration = time.time() - step_start
        if args.batch_size > 0:
            step_times.append(("PDF Batching", step_duration))
            print_step_complete(6, "Batching", step_duration)
        
        # Step 7: Cleanup
        run_step_7_cleanup(output_dir, args.keep_intermediate_files)
        
        # Print summary
        total_duration = time.time() - total_start
        print_summary(
            step_times,
            total_duration,
            args.batch_size,
            args.batch_by_school,
            args.batch_by_board,
            total_clients,
            args.keep_intermediate_files,
        )
        
        return 0
        
    except Exception as exc:
        print(f"\n❌ Pipeline failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
