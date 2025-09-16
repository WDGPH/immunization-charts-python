#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Cleaning up..."

rm -rf "${OUTDIR}/by_school"
rm -rf "${OUTDIR}/json_${LANG}/"*.typ
rm -rf "${OUTDIR}/json_${LANG}/"*.json
rm -rf "${OUTDIR}/json_${LANG}/"*.csv
rm -rf "${OUTDIR}/json_${LANG}/conf.pdf"
rm -rf "${OUTDIR}/batches"

echo "Cleanup complete."