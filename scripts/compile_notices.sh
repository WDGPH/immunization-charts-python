#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Compiling Typst templates..."

for typfile in ${OUTDIR}/artifacts_${LANG}/*.typ; do
    filename=$(basename "$typfile" .typ)
    typst compile --font-path /usr/share/fonts/truetype/freefont/ --root ../ \
    "${OUTDIR}/artifacts_${LANG}/$filename.typ"
done