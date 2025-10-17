#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Generating templates..."

for jsonfile in ${OUTDIR}/json_${LANG}/*.json; do
    filename=$(basename "$jsonfile" .json)
    echo "Processing $filename"
    python generate_mock_template_${LANG}.py "${OUTDIR}/json_${LANG}" "$filename" \
        "../../assets/logo.png" \
        "../../assets/signature.png" \
        "../../config/parameters.yaml" 
done
