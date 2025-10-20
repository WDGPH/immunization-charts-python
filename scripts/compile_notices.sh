#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Compiling Typst templates..."

for typfile in ${OUTDIR}/json_${LANG}/*.typ; do
    filename=$(basename "$typfile" .typ)

    # Skip shared configuration templates
    if [ "$filename" = "conf" ]; then
        continue
    fi

    typst compile --font-path /usr/share/fonts/truetype/freefont/ --root ../ \
        "${OUTDIR}/json_${LANG}/$filename.typ"
done

echo "Encrypting compiled notices..."
ENCRYPT_ARGS=(--directory "${OUTDIR}/json_${LANG}" --language "${LANG}")
if [ -n "${ENCRYPTION_WORKERS:-}" ]; then
    ENCRYPT_ARGS+=(--workers "${ENCRYPTION_WORKERS}")
fi
if [ -n "${ENCRYPTION_CHUNK_SIZE:-}" ]; then
    ENCRYPT_ARGS+=(--chunk-size "${ENCRYPTION_CHUNK_SIZE}")
fi

"${PYTHON:-python3}" encrypt_notice.py "${ENCRYPT_ARGS[@]}"
