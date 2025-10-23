from scripts.cleanup import safe_delete, remove_files_with_ext, cleanup_with_config


def test_safe_delete(tmp_path):
    # Create a temporary file and directory
    temp_file = tmp_path / "temp_file.txt"
    temp_file.touch()
    temp_dir = tmp_path / "temp_dir"
    temp_dir.mkdir()

    # Ensure they exist
    assert temp_file.exists()
    assert temp_dir.exists()

    # Delete the file and directory
    safe_delete(temp_file)
    safe_delete(temp_dir)

    # Ensure they are deleted
    assert not temp_file.exists()
    assert not temp_dir.exists()


def test_remove_files_with_ext(tmp_path):
    # Create temporary files with different extensions
    (tmp_path / "file1.typ").touch()
    (tmp_path / "file2.json").touch()
    (tmp_path / "file3.csv").touch()
    (tmp_path / "file4.txt").touch()

    # Remove files with specified extensions
    remove_files_with_ext(tmp_path, ["typ", "json", "csv"])

    # Check that the correct files were deleted
    assert not (tmp_path / "file1.typ").exists()
    assert not (tmp_path / "file2.json").exists()
    assert not (tmp_path / "file3.csv").exists()
    assert (tmp_path / "file4.txt").exists()


def test_cleanup_with_config(tmp_path, tmp_path_factory):
    # Create a temporary config file
    config_dir = tmp_path_factory.mktemp("config")
    config_file = config_dir / "parameters.yaml"
    config_file.write_text(
        """
cleanup:
  remove_directories:
    - "artifacts"
    - "by_school"
    - "batches"
  remove_extensions:
    - "typ"
    - "json"
    - "csv"
"""
    )

    # Setup the directory structure
    outdir_path = tmp_path
    artifacts_path = outdir_path / "artifacts"
    artifacts_path.mkdir()
    (artifacts_path / "sample.typ").touch()
    (outdir_path / "by_school").mkdir()
    (outdir_path / "batches").mkdir()
    logs_path = outdir_path / "logs"
    logs_path.mkdir()

    # Ensure everything exists before cleanup
    assert artifacts_path.exists()
    assert (outdir_path / "by_school").exists()
    assert (outdir_path / "batches").exists()
    assert logs_path.exists()

    # Perform cleanup
    cleanup_with_config(outdir_path, config_file)

    # Check that the correct directories were deleted
    assert not artifacts_path.exists()
    assert not (outdir_path / "by_school").exists()
    assert not (outdir_path / "batches").exists()
    assert logs_path.exists()
