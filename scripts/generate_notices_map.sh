#!/bin/bash

OUTDIR="../output"
LANG=$1
MAP_SCHOOL=$2

if [ "$MAP_SCHOOL" != "false" ]; then
  MAP_SCHOOL="../../config/map_school.json"
  echo "Using school mapping file: $MAP_SCHOOL"
fi

echo "Generating templates..."

for jsonfile in ${OUTDIR}/json_${LANG}/*.json; do
    filename=$(basename "$jsonfile" .json)
    echo "Processing $filename"
    ./2025_mock_generate_template_${LANG}.sh "${OUTDIR}/json_${LANG}" "$filename" \
        "../../assets/logo.png" \
        "../../assets/signature.png" \
        "../../config/parameters.yaml" \
        $MAP_SCHOOL
done
