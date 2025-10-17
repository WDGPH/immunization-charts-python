#!/usr/bin/env python3
"""Utility to prepare the pipeline output directory.

This script ensures the output directory exists, optionally removes any
existing contents (while preserving the logs directory), and creates the log
directory if needed. It mirrors the behaviour previously implemented in the
``run_pipeline.sh`` shell script so that all directory management lives in
Python.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Callable, Optional

CANCELLED_EXIT_CODE = 2


def _is_log_directory(candidate: Path, log_dir: Path) -> bool:
    """Return True when *candidate* is the log directory or one of its ancestors.

    The pipeline stores logs under a dedicated directory (``output/logs``). When
    cleaning the output directory we must preserve the log directory and its
    contents. The check accounts for potential symlinks by resolving both paths.
    """

    try:
        candidate_resolved = candidate.resolve()
    except FileNotFoundError:
        # If the child disappears while scanning, treat it as non-log.
        return False

    try:
        log_resolved = log_dir.resolve()
    except FileNotFoundError:
        # If the log directory does not exist yet we should not attempt to skip
        # siblings – the caller will create it afterwards.
        return False

    return candidate_resolved == log_resolved


def _purge_output_directory(output_dir: Path, log_dir: Path) -> None:
    """Remove everything inside *output_dir* except the logs directory."""

    for child in output_dir.iterdir():
        if _is_log_directory(child, log_dir):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def _default_prompt(output_dir: Path) -> bool:
    print("")
    print(f"⚠️  Output directory already exists: {output_dir}")
    response = input("Delete contents (except logs) and proceed? [y/N] ")
    return response.strip().lower() in {"y", "yes"}


def prepare_output_directory(
    output_dir: Path,
    log_dir: Path,
    auto_remove: bool,
    prompt: Optional[Callable[[Path], bool]] = None,
) -> bool:
    """Prepare the output directory for a new pipeline run.

    Parameters
    ----------
    output_dir:
        Root directory for pipeline outputs.
    log_dir:
        Directory where pipeline logs are stored. Typically a subdirectory of
        ``output_dir``.
    auto_remove:
        When ``True`` the directory is emptied without prompting the user.
    prompt:
        Optional callable used to prompt the user for confirmation. A return
        value of ``True`` proceeds with cleanup, while ``False`` aborts.

    Returns
    -------
    bool
        ``True`` when preparation succeeded, ``False`` when the user aborted the
        operation.
    """

    prompt_callable = prompt or _default_prompt

    if output_dir.exists():
        if not auto_remove and not prompt_callable(output_dir):
            print("❌ Pipeline cancelled. No changes made.")
            return False
        _purge_output_directory(output_dir, log_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    log_dir.mkdir(parents=True, exist_ok=True)
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the pipeline output directory")
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Root directory for pipeline outputs",
    )
    parser.add_argument(
        "--log-dir",
        required=True,
        type=Path,
        help="Directory used to store pipeline logs",
    )
    parser.add_argument(
        "--auto-remove",
        action="store_true",
        help="Remove existing contents without prompting",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    success = prepare_output_directory(
        output_dir=args.output_dir,
        log_dir=args.log_dir,
        auto_remove=args.auto_remove,
    )

    return 0 if success else CANCELLED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
