import pytest

from scripts.prepare_output import prepare_output_directory


def test_prepare_output_creates_directories(tmp_path):
    output_dir = tmp_path / "output"
    log_dir = output_dir / "logs"

    succeeded = prepare_output_directory(output_dir, log_dir, auto_remove=True)

    assert succeeded is True
    assert output_dir.exists()
    assert log_dir.exists()


def test_prepare_output_preserves_logs(tmp_path):
    output_dir = tmp_path / "output"
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "previous.log").write_text("log")
    (output_dir / "artifacts").mkdir(parents=True)
    (output_dir / "artifacts" / "data.json").write_text("{}")
    (output_dir / "pdf_individual").mkdir()
    (output_dir / "pdf_individual" / "client.pdf").write_text("pdf")

    succeeded = prepare_output_directory(output_dir, log_dir, auto_remove=True)

    assert succeeded is True
    assert log_dir.exists()
    assert (log_dir / "previous.log").exists()
    assert not (output_dir / "artifacts").exists()
    assert not (output_dir / "pdf_individual").exists()


def test_prepare_output_prompts_and_aborts_on_negative_response(tmp_path):
    output_dir = tmp_path / "output"
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True)
    file_to_keep = output_dir / "should_remain.txt"
    file_to_keep.write_text("keep")

    succeeded = prepare_output_directory(
        output_dir,
        log_dir,
        auto_remove=False,
        prompt=lambda *_: False,
    )

    assert succeeded is False
    assert file_to_keep.exists()
    # log directory should remain untouched
    assert log_dir.exists()


@pytest.mark.parametrize("input_value", ["y", "Y", "yes", "YES", "  y   "])
def test_custom_prompt_allows_cleanup(tmp_path, input_value):
    output_dir = tmp_path / "output"
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True)
    (output_dir / "obsolete.txt").write_text("obsolete")

    responses = iter([input_value])

    def fake_prompt(_):
        return next(responses).strip().lower().startswith("y")

    succeeded = prepare_output_directory(
        output_dir,
        log_dir,
        auto_remove=False,
        prompt=fake_prompt,
    )

    assert succeeded is True
    assert not (output_dir / "obsolete.txt").exists()
