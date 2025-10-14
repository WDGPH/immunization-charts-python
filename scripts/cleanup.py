import sys
import shutil
import argparse
from pathlib import Path

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Cleanup generated files in the specified directory.")
    parser.add_argument("outdir_path", type=str, help="Path to the output directory.")
    parser.add_argument("language", type=str, help="Language (e.g., 'english', 'french').")
    return parser.parse_args()

def safe_delete(path: Path):
    """Safely delete a file or directory if it exists."""
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

def remove_files_with_ext(base_dir: Path, extensions=('typ', 'json', 'csv')):
    """Remove files with specified extensions in the given directory."""
    for ext in extensions:
        for file in base_dir.glob(f'*.{ext}'):
            safe_delete(file)

def cleanup(outdir_path: Path, language: str):
    """Perform cleanup of generated files and directories."""
    json_file_path = outdir_path / f'json_{language}'
    for folder in ['by_school', 'batches']:
        safe_delete(outdir_path / folder)
    remove_files_with_ext(json_file_path)
    safe_delete(json_file_path / 'conf.pdf')
        
def main():
    args = parse_args()
    outdir_path = Path(args.outdir_path)

    if not outdir_path.is_dir():
        print(f"Error: The path {outdir_path} is not a valid directory.")
        sys.exit(1)
    
    cleanup(outdir_path, args.language)
    print("Cleanup completed successfully.")

if __name__ == "__main__":
    main()