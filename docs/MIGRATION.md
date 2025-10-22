# Migration from run_pipeline.sh to run_pipeline.py

## Summary

The pipeline orchestrator has been migrated from a Bash shell script (`run_pipeline.sh`) to a Python script (`run_pipeline.py`). This provides better maintainability, testability, and integration with the existing Python codebase.

## Feature Parity

The Python orchestrator (`run_pipeline.py`) provides full feature parity with the shell script:

### All Features Supported:
- ✅ Input file and language specification
- ✅ Output directory preparation with optional auto-removal
- ✅ All 7 pipeline steps (preparation, preprocessing, notice generation, compilation, validation, batching, cleanup)
- ✅ Timing information for each step
- ✅ Batch size configuration
- ✅ Batch grouping by school or board
- ✅ Option to keep intermediate files
- ✅ Summary output with total time and client count
- ✅ Error handling and exit codes

### Command-Line Compatibility:

**Old (Shell Script):**
```bash
./run_pipeline.sh students.xlsx en --keep-intermediate-files --batch-size 50 --batch-by-school
```

**New (Python Script):**
```bash
python3 run_pipeline.py students.xlsx en --keep-intermediate-files --batch-size 50 --batch-by-school
```

The only difference is using `python3 run_pipeline.py` instead of `./run_pipeline.sh`.

### Argument Mapping:

| Shell Script Flag | Python Script Flag | Notes |
|------------------|-------------------|-------|
| `--keep-intermediate-files` | `--keep-intermediate-files` | Same |
| `--remove-existing-output` | `--remove-existing-output` | Same |
| `--batch-size N` | `--batch-size N` | Same |
| `--batch-by-school` | `--batch-by-school` | Same |
| `--batch-by-board` | `--batch-by-board` | Same |

## Benefits of Python Version

1. **Better Error Handling**: More detailed error messages and proper exception handling
2. **Testability**: Unit tests for argument parsing, validation, and individual steps
3. **Maintainability**: Pure Python code is easier to maintain than shell scripts
4. **Type Safety**: Type hints throughout the code
5. **Consistency**: Uses the same patterns as other Python scripts in the project
6. **Modularity**: Each script can be imported and called programmatically

## Testing

All existing tests continue to pass, and new tests have been added for the orchestrator:
- Argument parsing validation
- Error condition handling
- Print functions

Run tests with:
```bash
python3 -m pytest tests/test_run_pipeline.py -v
```

## Rollback Plan

If needed, the shell script (`run_pipeline.sh`) can be restored from git history. However, the Python version is recommended going forward as it provides better integration with the codebase and testing infrastructure.
