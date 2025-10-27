"""Utility to prepare the pipeline output directory.

This script ensures the output directory exists, optionally removes any
existing contents (while preserving the logs directory), and creates the log
directory if needed.

Note: This module is called exclusively from orchestrator.py. The internal
functions handle all logic; CLI support has been removed in favor of explicit
function calls from the orchestrator.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional


def is_log_directory(candidate: Path, log_dir: Path) -> bool:
    """Check if a path is the log directory or one of its ancestors.

    Module-internal helper for purge_output_directory(). The pipeline stores logs
    under a dedicated directory (``output/logs``). When cleaning the output directory
    we must preserve the log directory and its contents. This check accounts for
    potential symlinks by resolving both paths.

    Parameters
    ----------
    candidate : Path
        Path to check.
    log_dir : Path
        Reference log directory path.

    Returns
    -------
    bool
        True if candidate is the log directory or an ancestor, False otherwise.
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


def purge_output_directory(output_dir: Path, log_dir: Path) -> None:
    """Remove everything inside output_dir except the logs directory.

    Module-internal helper for prepare_output_directory(). Recursively deletes
    all files and subdirectories except the log directory, which is preserved
    for audit trails.

    Parameters
    ----------
    output_dir : Path
        Output directory to clean.
    log_dir : Path
        Log directory to preserve.
    """

    for child in output_dir.iterdir():
        if is_log_directory(child, log_dir):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def default_prompt(output_dir: Path) -> bool:
    """Prompt user for confirmation to delete output directory contents.

    Module-internal helper for prepare_output_directory(). Interactive prompt
    to prevent accidental data loss when auto_remove is False.

    Parameters
    ----------
    output_dir : Path
        Directory path being queried.

    Returns
    -------
    bool
        True if user confirms (y/yes), False otherwise.
    """
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

    prompt_callable = prompt or default_prompt

    if output_dir.exists():
        if not auto_remove and not prompt_callable(output_dir):
            print("❌ Pipeline cancelled. No changes made.")
            return False
        purge_output_directory(output_dir, log_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    log_dir.mkdir(parents=True, exist_ok=True)
    return True


if __name__ == "__main__":
    raise RuntimeError(
        "prepare_output.py should not be invoked directly. Use orchestrator.py instead."
    )
