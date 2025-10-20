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

    base_name="$filename"
    if [[ "$filename" == *_immunization_notice ]]; then
        base_name="${filename%_immunization_notice}"
    fi

    PDF_PATH="${OUTDIR}/json_${LANG}/$filename.pdf"
    JSON_PATH="${OUTDIR}/json_${LANG}/${base_name}.json"

    if [ -f "${PDF_PATH}" ] && [ -f "${JSON_PATH}" ]; then
        "${PYTHON:-python3}" encrypt_notice.py "${JSON_PATH}" "${PDF_PATH}" "${LANG}"
    else
        echo "WARNING: Skipping encryption for ${filename}: missing PDF or JSON."
    fi
done
