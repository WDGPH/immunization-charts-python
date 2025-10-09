#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Cleaning up..."

rm -rf "${OUTDIR}/by_school"
rm -rf "${OUTDIR}/artifacts_${LANG}/"*.typ
rm -rf "${OUTDIR}/artifacts_${LANG}/"*.json
rm -rf "${OUTDIR}/artifacts_${LANG}/"*.csv
rm -rf "${OUTDIR}/artifacts_${LANG}/conf.pdf"
rm -rf "${OUTDIR}/batches"

echo "Cleanup complete."