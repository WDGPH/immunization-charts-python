"""Batch per-client PDFs into combined bundles with manifests.

This module implements Task 5 of the per-client PDF refactor plan. It can be
invoked as a CLI tool or imported for unit testing. Batching supports three
modes:

* Size-based (default): chunk the ordered list of PDFs into groups of
  ``batch_size``.
* School-based: group by ``school_id`` and then chunk each group while
  preserving client order.
* Board-based: group by ``board_id`` and chunk each group.

Each batch produces a merged PDF inside ``output/pdf_combined`` and a manifest JSON
record inside ``output/metadata`` that captures critical metadata for audits.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import islice
from pathlib import Path
from typing import Dict, Iterator, List, Sequence

from pypdf import PdfReader, PdfWriter

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass(frozen=True)
class BatchConfig:
    output_dir: Path
    language: str
    batch_size: int
    batch_by_school: bool
    batch_by_board: bool
    run_id: str


@dataclass(frozen=True)
class ClientArtifact:
    sequence: str
    client_id: str
    language: str
    person: Dict[str, object]
    school: Dict[str, object]
    board: Dict[str, object]
    contact: Dict[str, object]
    vaccines_due: str | None
    vaccines_due_list: Sequence[str] | None
    received: Sequence[dict] | None
    metadata: Dict[str, object]


@dataclass(frozen=True)
class PdfRecord:
    sequence: str
    client_id: str
    pdf_path: Path
    page_count: int
    client: ClientArtifact


@dataclass(frozen=True)
class BatchPlan:
    batch_type: str
    batch_identifier: str | None
    batch_number: int
    total_batches: int
    clients: List[PdfRecord]


@dataclass(frozen=True)
class BatchResult:
    pdf_path: Path
    manifest_path: Path
    batch_plan: BatchPlan


PDF_PATTERN = re.compile(r"^(?P<lang>[a-z]{2})_client_(?P<sequence>\d{5})_(?P<client_id>.+)\.pdf$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch per-client PDFs into combined outputs.")
    parser.add_argument("output_dir", type=Path, help="Root output directory containing pipeline artifacts.")
    parser.add_argument("language", choices=["en", "fr"], help="Language prefix to batch (en or fr).")
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=0,
        help="Maximum number of clients per batch (0 disables batching).",
    )
    parser.add_argument(
        "--batch-by-school",
        dest="batch_by_school",
        action="store_true",
        help="Group batches by school identifier before chunking.",
    )
    parser.add_argument(
        "--batch-by-board",
        dest="batch_by_board",
        action="store_true",
        help="Group batches by board identifier before chunking.",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        required=True,
        help="Pipeline run identifier to locate preprocessing artifacts and logs.",
    )
    return parser.parse_args(argv)


def chunked(iterable: Sequence[PdfRecord], size: int) -> Iterator[List[PdfRecord]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for index in range(0, len(iterable), size):
        yield list(islice(iterable, index, index + size))


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return re.sub(r"_+", "_", cleaned).strip("_").lower() or "unknown"


def load_artifact(output_dir: Path, run_id: str) -> Dict[str, object]:
    artifact_path = output_dir / "artifacts" / f"preprocessed_clients_{run_id}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Preprocessed artifact not found at {artifact_path}")
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    return payload


def build_client_lookup(artifact: Dict[str, object]) -> Dict[tuple[str, str], ClientArtifact]:
    clients = artifact.get("clients", [])
    lookup: Dict[tuple[str, str], ClientArtifact] = {}
    for client in clients:
        record = ClientArtifact(**client)
        lookup[(record.sequence, record.client_id)] = record
    return lookup


def discover_pdfs(output_dir: Path, language: str) -> List[Path]:
    pdf_dir = output_dir / "pdf_individual"
    if not pdf_dir.exists():
        return []
    return sorted(pdf_dir.glob(f"{language}_client_*.pdf"))


def build_pdf_records(output_dir: Path, language: str, clients: Dict[tuple[str, str], ClientArtifact]) -> List[PdfRecord]:
    pdf_paths = discover_pdfs(output_dir, language)
    records: List[PdfRecord] = []
    for pdf_path in pdf_paths:
        match = PDF_PATTERN.match(pdf_path.name)
        if not match:
            LOG.warning("Skipping unexpected PDF filename: %s", pdf_path.name)
            continue
        sequence = match.group("sequence")
        client_id = match.group("client_id")
        key = (sequence, client_id)
        if key not in clients:
            raise KeyError(f"No client metadata found for PDF {pdf_path.name}")
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        records.append(
            PdfRecord(
                sequence=sequence,
                client_id=client_id,
                pdf_path=pdf_path,
                page_count=page_count,
                client=clients[key],
            )
        )
    return sorted(records, key=lambda record: record.sequence)


def ensure_ids(records: Sequence[PdfRecord], *, attr: str, log_path: Path) -> None:
    missing = [
        record
        for record in records
        if not getattr(record.client, attr)["id"]
    ]
    if missing:
        sample = missing[0]
        raise ValueError(
            "Missing {attr} for client {client} (sequence {sequence});\n"
            "Cannot batch without identifiers. See {log_path} for preprocessing warnings.".format(
                attr=attr.replace("_", " "),
                client=sample.client_id,
                sequence=sample.sequence,
                log_path=log_path,
            )
        )


def group_records(records: Sequence[PdfRecord], key: str) -> Dict[str, List[PdfRecord]]:
    grouped: Dict[str, List[PdfRecord]] = {}
    for record in records:
        identifier = getattr(record.client, key)["id"]
        grouped.setdefault(identifier, []).append(record)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def plan_batches(config: BatchConfig, records: List[PdfRecord], log_path: Path) -> List[BatchPlan]:
    if config.batch_size <= 0:
        return []

    if config.batch_by_school and config.batch_by_board:
        raise ValueError("Cannot batch by both school and board simultaneously.")

    plans: List[BatchPlan] = []

    if config.batch_by_school:
        ensure_ids(records, attr="school", log_path=log_path)
        grouped = group_records(records, "school")
        for identifier, items in grouped.items():
            total_batches = (len(items) + config.batch_size - 1) // config.batch_size
            for index, chunk in enumerate(chunked(items, config.batch_size), start=1):
                plans.append(
                    BatchPlan(
                        batch_type="school",
                        batch_identifier=identifier,
                        batch_number=index,
                        total_batches=total_batches,
                        clients=chunk,
                    )
                )
        return plans

    if config.batch_by_board:
        ensure_ids(records, attr="board", log_path=log_path)
        grouped = group_records(records, "board")
        for identifier, items in grouped.items():
            total_batches = (len(items) + config.batch_size - 1) // config.batch_size
            for index, chunk in enumerate(chunked(items, config.batch_size), start=1):
                plans.append(
                    BatchPlan(
                        batch_type="board",
                        batch_identifier=identifier,
                        batch_number=index,
                        total_batches=total_batches,
                        clients=chunk,
                    )
                )
        return plans

    # Size-based batching
    total_batches = (len(records) + config.batch_size - 1) // config.batch_size
    for index, chunk in enumerate(chunked(records, config.batch_size), start=1):
        plans.append(
            BatchPlan(
                batch_type="size",
                batch_identifier=None,
                batch_number=index,
                total_batches=total_batches,
                clients=chunk,
            )
        )
    return plans


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def merge_pdf_files(pdf_paths: Sequence[Path], destination: Path) -> None:
    writer = PdfWriter()
    for pdf_path in pdf_paths:
        with pdf_path.open("rb") as stream:
            reader = PdfReader(stream)
            for page in reader.pages:
                writer.add_page(page)
    with destination.open("wb") as output_stream:
        writer.write(output_stream)


def write_batch(
    config: BatchConfig,
    plan: BatchPlan,
    *,
    combined_dir: Path,
    metadata_dir: Path,
    artifact_path: Path,
) -> BatchResult:
    if plan.batch_identifier:
        identifier_slug = slugify(plan.batch_identifier)
        name = f"{config.language}_{plan.batch_type}_{identifier_slug}_{plan.batch_number:03d}_of_{plan.total_batches:03d}"
    else:
        name = f"{config.language}_batch_{plan.batch_number:03d}_of_{plan.total_batches:03d}"

    output_pdf = combined_dir / f"{name}.pdf"
    manifest_path = metadata_dir / f"{name}_manifest.json"

    merge_pdf_files([record.pdf_path for record in plan.clients], output_pdf)

    checksum = sha256(output_pdf.read_bytes()).hexdigest()
    total_pages = sum(record.page_count for record in plan.clients)

    manifest = {
        "run_id": config.run_id,
        "language": config.language,
        "batch_type": plan.batch_type,
        "batch_identifier": plan.batch_identifier,
        "batch_number": plan.batch_number,
        "total_batches": plan.total_batches,
        "batch_size": config.batch_size,
        "total_clients": len(plan.clients),
        "total_pages": total_pages,
        "sha256": checksum,
        "output_pdf": _relative(output_pdf, config.output_dir),
        "clients": [
            {
                "sequence": record.sequence,
                "client_id": record.client_id,
                "full_name": record.client.person.get("full_name"),
                "school": record.client.school,
                "board": record.client.board,
                "pdf_path": _relative(record.pdf_path, config.output_dir),
                "artifact_path": _relative(artifact_path, config.output_dir),
                "pages": record.page_count,
            }
            for record in plan.clients
        ],
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOG.info("Created %s (%s clients)", output_pdf.name, len(plan.clients))
    return BatchResult(pdf_path=output_pdf, manifest_path=manifest_path, batch_plan=plan)


def batch_pdfs(config: BatchConfig) -> List[BatchResult]:
    if config.batch_size <= 0:
        LOG.info("Batch size <= 0; skipping batching step.")
        return []

    artifact_path = config.output_dir / "artifacts" / f"preprocessed_clients_{config.run_id}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Expected artifact at {artifact_path}")

    artifact = load_artifact(config.output_dir, config.run_id)
    if artifact.get("language") != config.language:
        raise ValueError(
            f"Artifact language {artifact.get('language')!r} does not match requested language {config.language!r}."
        )
    clients = build_client_lookup(artifact)

    records = build_pdf_records(config.output_dir, config.language, clients)
    if not records:
        LOG.info("No PDFs found for language %s; nothing to batch.", config.language)
        return []

    log_path = config.output_dir / "logs" / f"preprocess_{config.run_id}.log"
    plans = plan_batches(config, records, log_path)
    if not plans:
        LOG.info("No batch plans produced; check batch size and filters.")
        return []

    combined_dir = config.output_dir / "pdf_combined"
    combined_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir = config.output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    results: List[BatchResult] = []
    for plan in plans:
        results.append(
            write_batch(
                config,
                plan,
                combined_dir=combined_dir,
                metadata_dir=metadata_dir,
                artifact_path=artifact_path,
            )
        )

    LOG.info("Generated %d batch(es).", len(results))
    return results


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = BatchConfig(
        output_dir=args.output_dir.resolve(),
        language=args.language,
        batch_size=args.batch_size,
        batch_by_school=args.batch_by_school,
        batch_by_board=args.batch_by_board,
        run_id=args.run_id,
    )

    results = batch_pdfs(config)
    if results:
        print(f"Created {len(results)} batches in {config.output_dir / 'pdf_combined'}")
    else:
        print("No batches created.")


if __name__ == "__main__":
    main()
