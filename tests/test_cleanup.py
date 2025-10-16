from scripts.cleanup import safe_delete, remove_files_with_ext, cleanup

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
    remove_files_with_ext(tmp_path)

    # Check that the correct files were deleted
    assert not (tmp_path / "file1.typ").exists()
    assert not (tmp_path / "file2.json").exists()
    assert not (tmp_path / "file3.csv").exists()
    assert (tmp_path / "file4.txt").exists()  

def test_cleanup(tmp_path):
    # Setup the directory structure
    outdir_path = tmp_path
    json_en = outdir_path / 'json_en'
    json_en.mkdir()
    (json_en / "file1.typ").touch()
    (json_en / "file2.json").touch()
    (json_en / "conf.pdf").touch()
    json_fr = outdir_path / 'json_fr'
    json_fr.mkdir()
    artifacts_path = outdir_path / "artifacts"
    artifacts_path.mkdir()
    (artifacts_path / "sample.typ").touch()
    (outdir_path / "by_school").mkdir()
    (outdir_path / "batches").mkdir()
    logs_path = outdir_path / "logs"
    logs_path.mkdir()

    # Ensure everything exists before cleanup
    assert (json_en / "file1.typ").exists()
    assert (json_en / "file2.json").exists()
    assert (json_en / "conf.pdf").exists()
    assert json_fr.exists()
    assert artifacts_path.exists()
    assert (outdir_path / "by_school").exists()
    assert (outdir_path / "batches").exists()
    assert logs_path.exists()

    # Perform cleanup
    cleanup(outdir_path)

    # Check that the correct files and directories were deleted
    assert not json_en.exists()
    assert not json_fr.exists()
    assert not artifacts_path.exists()
    assert not (outdir_path / "by_school").exists()
    assert not (outdir_path / "batches").exists()
    assert logs_path.exists()