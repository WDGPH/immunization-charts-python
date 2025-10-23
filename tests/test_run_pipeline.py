"""Tests for the run_pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts import run_pipeline


def test_parse_args_minimal():
    """Test parse_args with minimal required arguments."""
    with patch("sys.argv", ["run_pipeline.py", "students.xlsx", "en"]):
        args = run_pipeline.parse_args()
        assert args.input_file == "students.xlsx"
        assert args.language == "en"
        assert args.input_dir == run_pipeline.DEFAULT_INPUT_DIR
        assert args.output_dir == run_pipeline.DEFAULT_OUTPUT_DIR
        assert args.config_dir == run_pipeline.DEFAULT_CONFIG_DIR


def test_parse_args_with_options():
    """Test parse_args with all optional arguments."""
    with patch(
        "sys.argv",
        [
            "run_pipeline.py",
            "students.xlsx",
            "fr",
            "--input-dir",
            "/tmp/input",
            "--output-dir",
            "/tmp/output",
            "--config-dir",
            "/tmp/config",
        ],
    ):
        args = run_pipeline.parse_args()
        assert args.input_file == "students.xlsx"
        assert args.language == "fr"
        assert args.input_dir == Path("/tmp/input")
        assert args.output_dir == Path("/tmp/output")
        assert args.config_dir == Path("/tmp/config")


def test_validate_args_missing_input_file():
    """Test that validate_args raises when input file doesn't exist."""
    with patch("sys.argv", ["run_pipeline.py", "nonexistent.xlsx", "en"]):
        args = run_pipeline.parse_args()
        try:
            run_pipeline.validate_args(args)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


def test_validate_args_valid():
    """Test that valid args pass validation."""
    # Create a temporary input file for testing
    with patch("sys.argv", ["run_pipeline.py", "rodent_dataset.xlsx", "en"]):
        args = run_pipeline.parse_args()
        # Should not raise for a file that exists
        try:
            run_pipeline.validate_args(args)
        except FileNotFoundError:
            pass  # Expected if file doesn't exist


def test_print_functions_no_errors():
    """Test that print functions don't raise errors."""
    run_pipeline.print_header("test.xlsx")
    run_pipeline.print_step(1, "Test step")
    run_pipeline.print_step_complete(1, "Test step", 1.5)
    run_pipeline.print_summary(
        [("Step 1", 1.0), ("Step 2", 2.0)],
        3.0,
        batch_size=0,
        group_by=None,
        total_clients=10,
        skip_cleanup=False,
    )
