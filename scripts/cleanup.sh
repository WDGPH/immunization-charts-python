#!/bin/bash

OUTDIR="../output"
LANG=$1

echo "Cleaning up..."



rm -rf "${OUTDIR}/by_school"
rm -rf "${OUTDIR}/${LANG}_json/"*.typ
rm -rf "${OUTDIR}/${LANG}_json/"*.json
rm -rf "${OUTDIR}/${LANG}_json/"*.csv
rm -rf "${OUTDIR}/${LANG}_json/conf.pdf"
rm -rf "${OUTDIR}/batched"

# tar a;;
# zip -r "${OUTDIR}/phsd_immunization_charts_$(date +%Y-%m-%d).zip" "${OUTDIR}/by_childcare_centre" "${OUTDIR}/english_json"
echo "Cleanup complete."