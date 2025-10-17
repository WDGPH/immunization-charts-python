from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import generate_notices


@pytest.fixture()
def sample_artifact(tmp_path: Path) -> Path:
    artifact = {
        "run_id": "20251015T210000",
        "language": "en",
        "clients": [
            {
                "sequence": "00001",
                "client_id": "12345",
                "language": "en",
                "person": {
                    "first_name": "Alice",
                    "last_name": "Mouse",
                    "full_name": "Alice Mouse",
                    "date_of_birth_iso": "2015-01-01",
                    "date_of_birth_display": "January 1, 2015",
                    "age": 10,
                    "over_16": False,
                },
                "school": {
                    "id": "sch_abc",
                    "name": "Burrow Public School",
                    "type": "Elementary",
                },
                "board": {
                    "id": "brd_foo",
                    "name": "Whisker Board",
                },
                "contact": {
                    "street": "1 Carrot Lane",
                    "city": "Burrow",
                    "province": "Ontario",
                    "postal_code": "N0N0N0",
                },
                "vaccines_due": "MMR",
                "vaccines_due_list": ["MMR"],
                "received": [
                    {
                        "date_given": "2020-01-01",
                        "vaccine": ["MMR"],
                        "diseases": ["Measles"],
                    }
                ],
                "metadata": {
                    "unique_id": "abc123",
                },
            }
        ],
    }
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    return artifact_path


def test_generate_typst_files_creates_expected_output(tmp_path: Path, sample_artifact: Path) -> None:
    output_dir = tmp_path / "output"
    project_root = Path(__file__).resolve().parents[1]
    logo = project_root / "assets" / "logo.png"
    signature = project_root / "assets" / "signature.png"
    parameters = project_root / "config" / "parameters.yaml"

    payload = generate_notices.read_artifact(sample_artifact)
    generated = generate_notices.generate_typst_files(
        payload,
        output_dir,
        logo,
        signature,
        parameters,
    )

    assert len(generated) == 1
    typst_file = generated[0]
    assert typst_file.name == "en_client_00001_12345.typ"
    content = typst_file.read_text(encoding="utf-8")
    assert "Alice Mouse" in content
    assert "Burrow Public School" in content
    assert "MMR" in content
    assert '#let vaccines_due_array = ("MMR",)' in content


def test_read_artifact_mismatched_language(tmp_path: Path, sample_artifact: Path) -> None:
    output_dir = tmp_path / "out"
    logo = tmp_path / "logo.png"
    signature = tmp_path / "signature.png"
    parameters = tmp_path / "parameters.yaml"
    for path in (logo, signature, parameters):
        path.write_text("stub", encoding="utf-8")

    payload = generate_notices.read_artifact(sample_artifact)
    payload = generate_notices.read_artifact(sample_artifact)
    payload = generate_notices.ArtifactPayload(
        run_id=payload.run_id,
        language="fr",
        clients=payload.clients,
    )

    with pytest.raises(ValueError):
        generate_notices.generate_typst_files(
            payload,
            output_dir,
            logo,
            signature,
            parameters,
        )
