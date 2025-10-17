#!/usr/bin/env python3
"""Helpers to summarise the preprocessed clients artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def extract_total_clients(path: Path) -> int:
    """Return the total number of clients encoded in *path*.

    The function first looks for the ``total_clients`` key. When that is missing
    it falls back to counting the number of entries under the ``clients`` key.
    """

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    total: Optional[int] = payload.get("total_clients")
    if total is None:
        clients = payload.get("clients", [])
        total = len(clients)

    try:
        return int(total)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError("Unable to determine the total number of clients") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarise the preprocessed clients artifact")
    parser.add_argument("artifact_path", type=Path, help="Path to the preprocessed clients JSON file")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    artifact_path: Path = args.artifact_path
    if not artifact_path.exists():
        print(f"⚠️ Preprocessed artifact not found at {artifact_path}", file=sys.stderr, flush=True)
        print("0")
        return 0

    total_clients = extract_total_clients(artifact_path)
    print(total_clients)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
