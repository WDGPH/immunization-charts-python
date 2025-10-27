"""Batch per-client PDFs into combined bundles with manifests.

This module batches individual per-client PDFs into combined bundles with
accompanying manifest records. It can be invoked as a CLI tool or imported for
unit testing. Batching supports three modes:

* Size-based (default): chunk the ordered list of PDFs into groups of
  ``batch_size``.
* School-based: group by ``school_code`` and then chunk each group while
  preserving client order.
* Board-based: group by ``board_code`` and chunk each group.

Each batch produces a merged PDF inside ``output/pdf_combined`` and a manifest JSON
record inside ``output/metadata`` that captures critical metadata for audits.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import islice
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, TypeVar

from pypdf import PdfReader, PdfWriter

from .config_loader import load_config
from .data_models import PdfRecord
from .enums import BatchStrategy, BatchType

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass(frozen=True)
class BatchConfig:
    """Configuration for PDF batching operation.

    Attributes
    ----------
    output_dir : Path
        Root output directory containing pipeline artifacts
    language : str
        Language code ('en' or 'fr')
    batch_size : int
        Maximum number of clients per batch (0 disables batching)
    batch_strategy : BatchStrategy
        Strategy for grouping PDFs into batches
    run_id : str
        Pipeline run identifier
    """

    output_dir: Path
    language: str
    batch_size: int
    batch_strategy: BatchStrategy
    run_id: str


@dataclass(frozen=True)
class BatchPlan:
    """Plan for a single batch of PDFs.

    Attributes
    ----------
    batch_type : BatchType
        Type/strategy used for this batch
    batch_identifier : str | None
        School or board code if batch was grouped, None for size-based
    batch_number : int
        Sequential batch number
    total_batches : int
        Total number of batches in this operation
    clients : List[PdfRecord]
        List of PDFs and metadata in this batch
    """

    batch_type: BatchType
    batch_identifier: str | None
    batch_number: int
    total_batches: int
    clients: List[PdfRecord]


@dataclass(frozen=True)
class BatchResult:
    """Result of a completed batch operation.

    Attributes
    ----------
    pdf_path : Path
        Path to the merged PDF file
    manifest_path : Path
        Path to the JSON manifest file
    batch_plan : BatchPlan
        The plan used to create this batch
    """

    pdf_path: Path
    manifest_path: Path
    batch_plan: BatchPlan


PDF_PATTERN = re.compile(
    r"^(?P<lang>[a-z]{2})_notice_(?P<sequence>\d{5})_(?P<client_id>.+)\.pdf$"
)


def batch_pdfs_with_config(
    output_dir: Path,
    language: str,
    run_id: str,
    config_path: Path | None = None,
) -> List[BatchResult]:
    """Batch PDFs using configuration from parameters.yaml.

    Parameters
    ----------
    output_dir : Path
        Root output directory containing pipeline artifacts.
    language : str
        Language prefix to batch ('en' or 'fr').
    run_id : str
        Pipeline run identifier to locate preprocessing artifacts.
    config_path : Path, optional
        Path to parameters.yaml. If not provided, uses default location.

    Returns
    -------
    List[BatchResult]
        List of batch results created.
    """
    config = load_config(config_path)

    batching_config = config.get("batching", {})
    batch_size = batching_config.get("batch_size", 0)
    group_by = batching_config.get("group_by", None)

    batch_strategy = BatchStrategy.from_string(group_by)

    config_obj = BatchConfig(
        output_dir=output_dir.resolve(),
        language=language,
        batch_size=batch_size,
        batch_strategy=batch_strategy,
        run_id=run_id,
    )

    return batch_pdfs(config_obj)


def main(
    output_dir: Path, language: str, run_id: str, config_path: Path | None = None
) -> List[BatchResult]:
    """Main entry point for PDF batching.

    Parameters
    ----------
    output_dir : Path
        Root output directory containing pipeline artifacts.
    language : str
        Language prefix to batch ('en' or 'fr').
    run_id : str
        Pipeline run identifier.
    config_path : Path, optional
        Path to parameters.yaml configuration file.

    Returns
    -------
    List[BatchResult]
        List of batches created.
    """
    results = batch_pdfs_with_config(output_dir, language, run_id, config_path)
    if results:
        print(f"Created {len(results)} batches in {output_dir / 'pdf_combined'}")
    else:
        print("No batches created.")
    return results


T = TypeVar("T")


def chunked(iterable: Sequence[T], size: int) -> Iterator[List[T]]:
    """Split an iterable into fixed-size chunks.

    Parameters
    ----------
    iterable : Sequence[T]
        Sequence to chunk.
    size : int
        Maximum number of items per chunk (must be positive).

    Returns
    -------
    Iterator[List[T]]
        Iterator yielding lists of up to `size` items.

    Raises
    ------
    ValueError
        If size is not positive.

    Examples
    --------
    >>> list(chunked([1, 2, 3, 4, 5], 2))
    [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for index in range(0, len(iterable), size):
        yield list(islice(iterable, index, index + size))


def slugify(value: str) -> str:
    """Convert a string to a URL-safe slug format.

    Converts spaces and special characters to underscores, removes consecutive
    underscores, and lowercases the result. Used for generating batch filenames
    from school/board names.

    Parameters
    ----------
    value : str
        String to slugify (e.g., school or board name).

    Returns
    -------
    str
        Slugified string, or 'unknown' if value is empty/whitespace.

    Examples
    --------
    >>> slugify("Lincoln High School")
    'lincoln_high_school'
    >>> slugify("Bd. Métropolitain")
    'bd_m_tropolitain'
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return re.sub(r"_+", "_", cleaned).strip("_").lower() or "unknown"


def load_artifact(output_dir: Path, run_id: str) -> Dict[str, object]:
    """Load the preprocessed artifact JSON from the output directory.

    Parameters
    ----------
    output_dir : Path
        Root output directory containing artifacts.
    run_id : str
        Pipeline run identifier matching the artifact filename.

    Returns
    -------
    Dict[str, object]
        Parsed preprocessed artifact with clients and metadata.

    Raises
    ------
    FileNotFoundError
        If the preprocessed artifact file does not exist.
    """
    artifact_path = output_dir / "artifacts" / f"preprocessed_clients_{run_id}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Preprocessed artifact not found at {artifact_path}")
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    return payload


def build_client_lookup(
    artifact: Dict[str, object],
) -> Dict[tuple[str, str], dict]:
    """Build a lookup table from artifact clients dict.

    Parameters
    ----------
    artifact : Dict[str, object]
        Preprocessed artifact dictionary

    Returns
    -------
    Dict[tuple[str, str], dict]
        Lookup table keyed by (sequence, client_id)
    """
    clients_obj = artifact.get("clients", [])
    clients = clients_obj if isinstance(clients_obj, list) else []
    lookup: Dict[tuple[str, str], dict] = {}
    for client in clients:  # type: ignore[var-annotated]
        sequence = client.get("sequence")  # type: ignore[attr-defined]
        client_id = client.get("client_id")  # type: ignore[attr-defined]
        lookup[(sequence, client_id)] = client  # type: ignore[typeddict-item]
    return lookup


def discover_pdfs(output_dir: Path, language: str) -> List[Path]:
    """Discover all individual PDF files for a given language.

    Parameters
    ----------
    output_dir : Path
        Root output directory.
    language : str
        Language prefix to match (e.g., 'en' or 'fr').

    Returns
    -------
    List[Path]
        Sorted list of PDF file paths matching the language, or empty list
        if pdf_individual directory doesn't exist.
    """
    pdf_dir = output_dir / "pdf_individual"
    if not pdf_dir.exists():
        return []
    return sorted(pdf_dir.glob(f"{language}_notice_*.pdf"))


def build_pdf_records(
    output_dir: Path, language: str, clients: Dict[tuple[str, str], dict]
) -> List[PdfRecord]:
    """Build a list of PdfRecord objects from discovered PDF files.

    Discovers PDFs, extracts metadata from filenames, looks up client data,
    and constructs PdfRecord objects with page counts and client metadata.

    Parameters
    ----------
    output_dir : Path
        Root output directory.
    language : str
        Language prefix to filter PDFs.
    clients : Dict[tuple[str, str], dict]
        Lookup table of client data keyed by (sequence, client_id).

    Returns
    -------
    List[PdfRecord]
        Sorted list of PdfRecord objects by sequence.

    Raises
    ------
    KeyError
        If a PDF filename has no matching client in the lookup table.
    """
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
    missing = [record for record in records if not record.client[attr].get("id")]
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
        identifier = record.client[key]["id"]
        grouped.setdefault(identifier, []).append(record)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def plan_batches(
    config: BatchConfig, records: List[PdfRecord], log_path: Path
) -> List[BatchPlan]:
    """Plan how to group PDFs into batches based on configuration.

    Parameters
    ----------
    config : BatchConfig
        Batching configuration including strategy and batch size
    records : List[PdfRecord]
        List of PDF records to batch
    log_path : Path
        Path to logging file

    Returns
    -------
    List[BatchPlan]
        List of batch plans
    """
    if config.batch_size <= 0:
        return []

    plans: List[BatchPlan] = []

    if config.batch_strategy == BatchStrategy.SCHOOL:
        ensure_ids(records, attr="school", log_path=log_path)
        grouped = group_records(records, "school")
        for identifier, items in grouped.items():
            total_batches = (len(items) + config.batch_size - 1) // config.batch_size
            for index, chunk in enumerate(chunked(items, config.batch_size), start=1):
                plans.append(
                    BatchPlan(
                        batch_type=BatchType.SCHOOL_GROUPED,
                        batch_identifier=identifier,
                        batch_number=index,
                        total_batches=total_batches,
                        clients=chunk,
                    )
                )
        return plans

    if config.batch_strategy == BatchStrategy.BOARD:
        ensure_ids(records, attr="board", log_path=log_path)
        grouped = group_records(records, "board")
        for identifier, items in grouped.items():
            total_batches = (len(items) + config.batch_size - 1) // config.batch_size
            for index, chunk in enumerate(chunked(items, config.batch_size), start=1):
                plans.append(
                    BatchPlan(
                        batch_type=BatchType.BOARD_GROUPED,
                        batch_identifier=identifier,
                        batch_number=index,
                        total_batches=total_batches,
                        clients=chunk,
                    )
                )
        return plans

    # Size-based batching (default)
    total_batches = (len(records) + config.batch_size - 1) // config.batch_size
    for index, chunk in enumerate(chunked(records, config.batch_size), start=1):
        plans.append(
            BatchPlan(
                batch_type=BatchType.SIZE_BASED,
                batch_identifier=None,
                batch_number=index,
                total_batches=total_batches,
                clients=chunk,
            )
        )
    return plans


def relative(path: Path, root: Path) -> str:
    """Convert path to string relative to root directory.

    Module-internal helper for manifest generation. Creates relative path strings
    for storing in JSON manifests, making paths portable across different base directories.

    Parameters
    ----------
    path : Path
        Absolute path to convert.
    root : Path
        Root directory to compute relative path from.

    Returns
    -------
    str
        Relative path as POSIX string.
    """
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
    # Generate filename based on batch type and identifiers
    if plan.batch_type == BatchType.SCHOOL_GROUPED:
        identifier_slug = slugify(plan.batch_identifier or "unknown")
        name = f"{config.language}_school_{identifier_slug}_{plan.batch_number:03d}_of_{plan.total_batches:03d}"
    elif plan.batch_type == BatchType.BOARD_GROUPED:
        identifier_slug = slugify(plan.batch_identifier or "unknown")
        name = f"{config.language}_board_{identifier_slug}_{plan.batch_number:03d}_of_{plan.total_batches:03d}"
    else:  # SIZE_BASED
        name = f"{config.language}_batch_{plan.batch_number:03d}_of_{plan.total_batches:03d}"

    output_pdf = combined_dir / f"{name}.pdf"
    manifest_path = metadata_dir / f"{name}_manifest.json"

    merge_pdf_files([record.pdf_path for record in plan.clients], output_pdf)

    checksum = sha256(output_pdf.read_bytes()).hexdigest()
    total_pages = sum(record.page_count for record in plan.clients)

    manifest = {
        "run_id": config.run_id,
        "language": config.language,
        "batch_type": plan.batch_type.value,
        "batch_identifier": plan.batch_identifier,
        "batch_number": plan.batch_number,
        "total_batches": plan.total_batches,
        "batch_size": config.batch_size,
        "total_clients": len(plan.clients),
        "total_pages": total_pages,
        "sha256": checksum,
        "output_pdf": relative(output_pdf, config.output_dir),
        "clients": [
            {
                "sequence": record.sequence,
                "client_id": record.client_id,
                "full_name": record.client["person"]["full_name"],
                "school": record.client["school"]["name"],
                "board": record.client["board"]["name"],
                "pdf_path": relative(record.pdf_path, config.output_dir),
                "artifact_path": relative(artifact_path, config.output_dir),
                "pages": record.page_count,
            }
            for record in plan.clients
        ],
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOG.info("Created %s (%s clients)", output_pdf.name, len(plan.clients))
    return BatchResult(
        pdf_path=output_pdf, manifest_path=manifest_path, batch_plan=plan
    )


def batch_pdfs(config: BatchConfig) -> List[BatchResult]:
    if config.batch_size <= 0:
        LOG.info("Batch size <= 0; skipping batching step.")
        return []

    artifact_path = (
        config.output_dir / "artifacts" / f"preprocessed_clients_{config.run_id}.json"
    )
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


if __name__ == "__main__":
    # This script is now called only from orchestrator.py
    # and should not be invoked directly
    raise RuntimeError(
        "batch_pdfs.py should not be invoked directly. Use orchestrator.py instead."
    )
