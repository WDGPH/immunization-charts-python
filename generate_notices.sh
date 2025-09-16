#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Generating templates..."

for jsonfile in ${OUTDIR}/${LANG}_json/*.json; do
    filename=$(basename "$jsonfile" .json)
    ./2025_row_generate_template_${LANG}.sh "${OUTDIR}/${LANG}_json" "$filename" \
        "../../assets/logo.png" \
        "../../assets/signature.png" \
        "../../config/parameters.yaml" 
done
