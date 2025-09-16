#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Compiling Typst templates..."

for typfile in ${OUTDIR}/${LANG}_json/*.typ; do
    filename=$(basename "$typfile" .typ)
    typst compile --font-path /usr/share/fonts/truetype/freefont/ --root ../ \
        "${OUTDIR}/${LANG}_json/$filename.typ"
done