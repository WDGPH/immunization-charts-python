import sys
import os
import glob
import shutil

# Check system arguments
if len(sys.argv) != 3:
    print("Usage: python cleanup.py <directory_path>")
    sys.exit(1)

outdir_path = sys.argv[1]
language = sys.argv[2]

# Validate directory path
if not os.path.isdir(outdir_path):
    print(f"Error: The path '{outdir_path}' is not a valid directory.")
    sys.exit(1)

# Remove by_school directory
school_dir = os.path.join(outdir_path, 'by_school')
batch_dirs = os.path.join(outdir_path, 'batches')

if os.path.exists(school_dir):
    shutil.rmtree(school_dir)

if os.path.exists(batch_dirs):
    shutil.rmtree(batch_dirs)

json_file_path = outdir_path + '/json_' + language + '/'

typst_files = glob.glob(os.path.join(json_file_path, '*.typ'))
json_files = glob.glob(os.path.join(json_file_path, '*.json'))
csv_files = glob.glob(os.path.join(json_file_path, '*.csv'))

for file in typst_files + json_files + csv_files:
    os.remove(file)

# if conf.pdf exists, remove it
if os.path.exists(json_file_path + 'conf.pdf'):
    os.remove(json_file_path + 'conf.pdf')