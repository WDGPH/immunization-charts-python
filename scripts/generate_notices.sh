#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Generating templates..."

for jsonfile in ${OUTDIR}/json_${LANG}/*.json; do
    filename=$(basename "$jsonfile" .json)
    echo "Processing $filename"
    ./2025_mock_generate_template_${LANG}.sh "${OUTDIR}/json_${LANG}" "$filename" \
        "../../assets/logo.png" \
        "../../assets/signature.png" \
        "../../config/parameters.yaml" 
done
