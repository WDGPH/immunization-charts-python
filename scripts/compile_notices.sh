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
        python3 - "${JSON_PATH}" "${PDF_PATH}" "${LANG}" <<'PY'
import json
import sys
from pathlib import Path

json_path = Path(sys.argv[1])
pdf_path = Path(sys.argv[2])
language = sys.argv[3]

if not json_path.exists() or not pdf_path.exists():
    sys.exit(0)

sys.path.insert(0, str(Path.cwd()))

from utils import encrypt_pdf, convert_date_iso  # noqa: E402
try:
    from utils import convert_date_french_to_iso  # noqa: E402
except ImportError:
    convert_date_french_to_iso = None

data = json.loads(json_path.read_text())
if not data:
    sys.exit(0)

first_key = next(iter(data))
record = data[first_key]
client_id = record.get("client_id", first_key)

dob_iso = record.get("date_of_birth_iso")
if not dob_iso:
    dob_display = record.get("date_of_birth")
    if not dob_display:
        sys.exit(0)
    if language == "english":
        dob_iso = convert_date_iso(dob_display)
    elif convert_date_french_to_iso:
        dob_iso = convert_date_french_to_iso(dob_display)
    else:
        sys.exit(0)
try:
    encrypt_pdf(str(pdf_path), str(client_id), dob_iso)
except Exception as exc:
    print(f"WARNING: Encryption failed for {pdf_path.name}: {exc}")
PY
    else
        echo "WARNING: Skipping encryption for ${filename}: missing PDF or JSON."
    fi
done
