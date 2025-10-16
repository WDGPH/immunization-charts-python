from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfWriter

from scripts import count_pdfs


def _make_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)


def test_summary_and_language_filter(tmp_path: Path, capsys) -> None:
    pdf_dir = tmp_path / "pdfs"
    _make_pdf(pdf_dir / "en_client_a.pdf", pages=2)
    _make_pdf(pdf_dir / "en_client_b.pdf", pages=3)
    _make_pdf(pdf_dir / "fr_client_c.pdf", pages=2)

    files = count_pdfs.discover_pdfs(pdf_dir)
    filtered = count_pdfs.filter_by_language(files, "en")
    results, buckets = count_pdfs.summarize_pdfs(filtered)
    count_pdfs.print_summary(results, buckets, language="en", verbose=False)

    output = capsys.readouterr().out
    assert "Analyzed 2 PDF(s)" in output
    assert "2 page(s)" in output
    assert "3 page(s)" in output
    assert "⚠️" in output  # 3-page PDF triggers warning


def test_json_output(tmp_path: Path, capsys) -> None:
    pdf_dir = tmp_path / "pdfs"
    target_pdf = pdf_dir / "en_client_single.pdf"
    _make_pdf(target_pdf, pages=2)

    files = count_pdfs.discover_pdfs(pdf_dir)
    results, buckets = count_pdfs.summarize_pdfs(files)
    json_path = tmp_path / "summary.json"
    count_pdfs.write_json(results, buckets, target=json_path, language="en")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["total_pdfs"] == 1
    assert data["buckets"]["2"] == 1
    assert data["files"][0]["path"].endswith("en_client_single.pdf")

    # Ensure summary printing still works when verbose requested
    count_pdfs.print_summary(results, buckets, language="en", verbose=True)
    output = capsys.readouterr().out
    assert "en_client_single.pdf" in output