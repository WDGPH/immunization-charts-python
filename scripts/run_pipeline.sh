#!/bin/bash
# Simplified pipeline runner that uses the new Python package structure

set -e

INFILE=$1
LANG=$2
INDIR="../input"
OUTDIR="../output"

if [ "$LANG" != "english" ] && [ "$LANG" != "french" ]; then
    echo "Error: Language must be 'english' or 'french'"
    exit 1
fi

echo ""
echo "🚀 Starting Immunization Charts Pipeline"
echo "🗂️  Input File: ${INFILE}"
echo "🌐 Language: ${LANG}"
echo ""

# Activate virtual environment if it exists
if [ -d "../.venv" ]; then
    source ../.venv/bin/activate
    echo "✅ Activated virtual environment"
fi

# Run the Python pipeline
echo "🔍 Running preprocessing pipeline..."
python -m immunization_charts.cli.main "${INDIR}/${INFILE}" "${LANG}" --output-dir "${OUTDIR}"

echo ""
echo "🎉 Pipeline completed successfully!"
echo ""