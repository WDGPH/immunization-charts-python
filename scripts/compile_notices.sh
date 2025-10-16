#!/bin/bash

OUTDIR="../output"
LANG=$1
ARTIFACT_DIR="${OUTDIR}/artifacts"
PDF_DIR="${OUTDIR}/pdf"

mkdir -p "${PDF_DIR}"

echo "Compiling Typst templates from ${ARTIFACT_DIR}..."

shopt -s nullglob
for typfile in "${ARTIFACT_DIR}"/${LANG}_client_*.typ; do
    filename=$(basename "$typfile" .typ)
    output_pdf="${PDF_DIR}/${filename}.pdf"
    typst compile --font-path /usr/share/fonts/truetype/freefont/ --root ../ "$typfile" "$output_pdf"
done
shopt -u nullglob