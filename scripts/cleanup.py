import sys
import shutil
import argparse
from pathlib import Path

def parse_args(argv: list[str] | None = None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Cleanup generated files in the specified directory.")
    parser.add_argument("outdir_path", type=str, help="Path to the output directory.")
    return parser.parse_args(argv)

def safe_delete(path: Path):
    """Safely delete a file or directory if it exists."""
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

def remove_files_with_ext(base_dir: Path, extensions=('typ', 'json', 'csv')):
    """Remove files with specified extensions in the given directory."""
    if not base_dir.exists():
        return
    for ext in extensions:
        for file in base_dir.glob(f'*.{ext}'):
            safe_delete(file)

def cleanup(outdir_path: Path):
    """Perform cleanup of generated files and directories."""
    for legacy_dir in outdir_path.glob('json_*'):
        remove_files_with_ext(legacy_dir)
        safe_delete(legacy_dir)

    for folder in ['artifacts', 'by_school', 'batches']:
        safe_delete(outdir_path / folder)
        
def main(argv: list[str] | None = None):
    args = parse_args(argv)
    outdir_path = Path(args.outdir_path)

    if not outdir_path.is_dir():
        print(f"Error: The path {outdir_path} is not a valid directory.")
        sys.exit(1)
    
    cleanup(outdir_path)
    print("✅ Cleanup completed successfully.")

if __name__ == "__main__":
    main()