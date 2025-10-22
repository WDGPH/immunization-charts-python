"""Tests for the run_pipeline orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts import run_pipeline


def test_parse_args_minimal():
    """Test parse_args with minimal required arguments."""
    with patch("sys.argv", ["run_pipeline.py", "students.xlsx", "en"]):
        args = run_pipeline.parse_args()
        assert args.input_file == "students.xlsx"
        assert args.language == "en"
        assert args.keep_intermediate_files is False
        assert args.remove_existing_output is False
        assert args.batch_size == 0
        assert args.batch_by_school is False
        assert args.batch_by_board is False


def test_parse_args_with_options():
    """Test parse_args with all optional arguments."""
    with patch(
        "sys.argv",
        [
            "run_pipeline.py",
            "students.xlsx",
            "fr",
            "--keep-intermediate-files",
            "--remove-existing-output",
            "--batch-size",
            "50",
            "--batch-by-school",
        ],
    ):
        args = run_pipeline.parse_args()
        assert args.input_file == "students.xlsx"
        assert args.language == "fr"
        assert args.keep_intermediate_files is True
        assert args.remove_existing_output is True
        assert args.batch_size == 50
        assert args.batch_by_school is True
        assert args.batch_by_board is False


def test_validate_args_batch_by_both_raises():
    """Test that using both --batch-by-school and --batch-by-board raises an error."""
    with patch("sys.argv", ["run_pipeline.py", "students.xlsx", "en", "--batch-by-school", "--batch-by-board"]):
        args = run_pipeline.parse_args()
        with pytest.raises(ValueError, match="cannot be used together"):
            run_pipeline.validate_args(args)


def test_validate_args_negative_batch_size_raises():
    """Test that negative batch size raises an error."""
    with patch("sys.argv", ["run_pipeline.py", "students.xlsx", "en", "--batch-size", "-1"]):
        args = run_pipeline.parse_args()
        with pytest.raises(ValueError, match="non-negative integer"):
            run_pipeline.validate_args(args)


def test_validate_args_valid():
    """Test that valid args pass validation."""
    with patch("sys.argv", ["run_pipeline.py", "students.xlsx", "en"]):
        args = run_pipeline.parse_args()
        # Should not raise
        run_pipeline.validate_args(args)


def test_print_functions_no_errors():
    """Test that print functions don't raise errors."""
    run_pipeline.print_header("test.xlsx")
    run_pipeline.print_step(1, "Test step")
    run_pipeline.print_step_complete(1, "Test step", 1.5)
    run_pipeline.print_summary(
        [("Step 1", 1.0), ("Step 2", 2.0)],
        3.0,
        batch_size=0,
        batch_by_school=False,
        batch_by_board=False,
        total_clients=10,
        skip_cleanup=False,
    )
