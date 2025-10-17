import json

import pytest

from scripts.summarize_preprocessed_clients import extract_total_clients, main


def test_extract_total_clients_prefers_total_key(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"total_clients": 42, "clients": [1, 2, 3]}), encoding="utf-8")

    assert extract_total_clients(artifact_path) == 42


def test_extract_total_clients_falls_back_to_clients_list(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"clients": [1, 2, 3]}), encoding="utf-8")

    assert extract_total_clients(artifact_path) == 3


def test_extract_total_clients_defaults_to_zero_when_keys_missing(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({}), encoding="utf-8")

    assert extract_total_clients(artifact_path) == 0


def test_extract_total_clients_rejects_non_numeric_values(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"total_clients": "not-a-number"}), encoding="utf-8")

    with pytest.raises(ValueError):
        extract_total_clients(artifact_path)


def test_main_returns_zero_when_artifact_missing(tmp_path, capfd):
    artifact_path = tmp_path / "missing.json"

    exit_code = main([str(artifact_path)])
    captured = capfd.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "0"
    assert "Preprocessed artifact not found" in captured.err
