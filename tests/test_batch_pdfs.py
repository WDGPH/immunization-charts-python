from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from scripts import batch_pdfs

RUN_ID = "20240101T000000"


def _write_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)


def _client_template(sequence: int, *, school_id: str, board_id: str, pages: int = 1) -> tuple[dict, int]:
    seq = f"{sequence:05d}"
    client_id = f"client{sequence:03d}"
    client = {
        "sequence": seq,
        "client_id": client_id,
        "language": "en",
        "person": {
            "first_name": f"Client{sequence}",
            "last_name": "Test",
            "full_name": f"Client{sequence} Test",
        },
        "school": {
            "id": school_id,
            "name": f"School {school_id}",
            "type": "Elementary",
        },
        "board": {
            "id": board_id,
            "name": f"Board {board_id}" if board_id else None,
        },
        "contact": {
            "street": "123 Test St",
            "city": "Guelph",
            "province": "ON",
            "postal_code": "N0N 0N0",
        },
        "vaccines_due": "MMR",
        "vaccines_due_list": ["MMR"],
        "received": [],
        "metadata": {},
    }
    return client, pages


def _write_artifact(output_dir: Path, clients: list[dict]) -> Path:
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"preprocessed_clients_{RUN_ID}.json"
    payload = {
        "run_id": RUN_ID,
        "language": "en",
        "clients": clients,
        "warnings": [],
    }
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")
    return artifact_path


def _build_output_dir(tmp_path: Path) -> Path:
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    return output_dir


def test_size_based_batching_with_remainder(tmp_path: Path) -> None:
    output_dir = _build_output_dir(tmp_path)
    clients = []
    pdf_dir = output_dir / "pdf_individual"
    for idx in range(1, 6):
        client, pages = _client_template(idx, school_id="sch_a", board_id="brd_a")
        clients.append(client)
        pdf_path = pdf_dir / f"en_client_{client['sequence']}_{client['client_id']}.pdf"
        _write_pdf(pdf_path, pages=pages)

    _write_artifact(output_dir, clients)

    config = batch_pdfs.BatchConfig(
        output_dir=output_dir,
        language="en",
        batch_size=2,
        batch_by_school=False,
        batch_by_board=False,
        run_id=RUN_ID,
    )

    results = batch_pdfs.batch_pdfs(config)
    assert len(results) == 3
    assert [result.pdf_path.name for result in results] == [
        "en_batch_001_of_003.pdf",
        "en_batch_002_of_003.pdf",
        "en_batch_003_of_003.pdf",
    ]

    manifest = json.loads(results[0].manifest_path.read_text(encoding="utf-8"))
    assert manifest["batch_type"] == "size"
    assert manifest["total_batches"] == 3
    assert len(manifest["clients"]) == 2
    assert manifest["clients"][0]["sequence"] == "00001"


def test_school_batching_splits_large_group(tmp_path: Path) -> None:
    output_dir = _build_output_dir(tmp_path)
    pdf_dir = output_dir / "pdf_individual"
    clients: list[dict] = []
    for idx in range(1, 5):
        client, pages = _client_template(idx, school_id="sch_shared", board_id="brd_a", pages=idx % 2 + 1)
        clients.append(client)
        pdf_path = pdf_dir / f"en_client_{client['sequence']}_{client['client_id']}.pdf"
        _write_pdf(pdf_path, pages=pages)

    _write_artifact(output_dir, clients)

    config = batch_pdfs.BatchConfig(
        output_dir=output_dir,
        language="en",
        batch_size=2,
        batch_by_school=True,
        batch_by_board=False,
        run_id=RUN_ID,
    )

    results = batch_pdfs.batch_pdfs(config)
    assert len(results) == 2
    assert [result.pdf_path.name for result in results] == [
        "en_school_sch_shared_001_of_002.pdf",
        "en_school_sch_shared_002_of_002.pdf",
    ]

    manifest_one = json.loads(results[0].manifest_path.read_text(encoding="utf-8"))
    assert manifest_one["batch_type"] == "school"
    assert manifest_one["batch_identifier"] == "sch_shared"
    assert manifest_one["total_clients"] == 2
    assert manifest_one["total_pages"] == sum(item["pages"] for item in manifest_one["clients"])


def test_batch_by_board_missing_identifier_raises(tmp_path: Path) -> None:
    output_dir = _build_output_dir(tmp_path)
    pdf_dir = output_dir / "pdf_individual"
    clients = []
    client, pages = _client_template(1, school_id="sch_a", board_id="")
    clients.append(client)
    pdf_path = pdf_dir / f"en_client_{client['sequence']}_{client['client_id']}.pdf"
    _write_pdf(pdf_path, pages=pages)

    _write_artifact(output_dir, clients)

    config = batch_pdfs.BatchConfig(
        output_dir=output_dir,
        language="en",
        batch_size=2,
        batch_by_school=False,
        batch_by_board=True,
        run_id=RUN_ID,
    )

    with pytest.raises(ValueError) as excinfo:
        batch_pdfs.batch_pdfs(config)
    assert "preprocess" in str(excinfo.value)


def test_zero_batch_size_no_output(tmp_path: Path) -> None:
    output_dir = _build_output_dir(tmp_path)
    pdf_dir = output_dir / "pdf_individual"
    clients: list[dict] = []
    for idx in range(1, 3):
        client, _ = _client_template(idx, school_id="sch_a", board_id="brd_a")
        clients.append(client)
        pdf_path = pdf_dir / f"en_client_{client['sequence']}_{client['client_id']}.pdf"
        _write_pdf(pdf_path)

    _write_artifact(output_dir, clients)

    config = batch_pdfs.BatchConfig(
        output_dir=output_dir,
        language="en",
        batch_size=0,
        batch_by_school=False,
        batch_by_board=False,
        run_id=RUN_ID,
    )

    results = batch_pdfs.batch_pdfs(config)
    assert results == []
    assert not (output_dir / "pdf_combined").exists()
    assert not (output_dir / "metadata").exists()
