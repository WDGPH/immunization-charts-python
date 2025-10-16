#!/bin/bash
set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <input_file> <language> [--no-cleanup]"
    echo "       <language>: en | fr"
    exit 1
fi

INFILE=$1
LANG=$2
SKIP_CLEANUP=false

if [ $# -ge 3 ]; then
    case "$3" in
        --no-cleanup)
            SKIP_CLEANUP=true
            ;;
        *)
            echo "Unknown option: $3"
            echo "Usage: $0 <input_file> <language> [--no-cleanup]"
            echo "       <language>: en | fr"
            exit 1
            ;;
    esac
fi

INDIR="../input"
OUTDIR="../output"
LOG_DIR="${OUTDIR}/logs"
BATCH_SIZE=100
RUN_ID=$(date +%Y%m%dT%H%M%S)
mkdir -p "${OUTDIR}" "${LOG_DIR}"

if [ "$LANG" != "en" ] && [ "$LANG" != "fr" ]; then
    echo "Error: Language must be 'en' or 'fr'"
    exit 1
fi

echo ""
echo "🚀 Starting VIPER Pipeline"
echo "🗂️  Input File: ${INFILE}"
echo ""

TOTAL_START=$(date +%s)


##########################################
# Step 1: Preprocessing
##########################################
STEP1_START=$(date +%s)
echo ""
echo "🔍 Step 1: Preprocessing started..."
python preprocess.py ${INDIR} ${INFILE} ${OUTDIR} ${LANG} --run-id ${RUN_ID}
STEP1_END=$(date +%s)
STEP1_DURATION=$((STEP1_END - STEP1_START))
echo "✅ Step 1: Preprocessing complete in ${STEP1_DURATION} seconds."

##########################################
# Record count
##########################################
CSV_PATH="${INDIR}/${CSVFILE}"
if [ -f "$CSV_PATH" ]; then
    TOTAL_RECORDS=$(tail -n +2 "$CSV_PATH" | wc -l)
    echo "📊 Total records (excluding header): $TOTAL_RECORDS"
else
    echo "⚠️ CSV not found for record count: $CSV_PATH"
fi

##########################################
# Step 2: Generating Notices
##########################################
STEP2_START=$(date +%s)
echo ""
echo "📝 Step 2: Generating Typst templates..."
python generate_notices.py \
    "${OUTDIR}/artifacts/preprocessed_clients_${RUN_ID}.json" \
    "${OUTDIR}/artifacts" \
    ${LANG} \
    "../assets/logo.png" \
    "../assets/signature.png" \
    "../config/parameters.yaml"
STEP2_END=$(date +%s)
STEP2_DURATION=$((STEP2_END - STEP2_START))
echo "✅ Step 2: Template generation complete in ${STEP2_DURATION} seconds."

##########################################
# Step 3: Compiling Notices
##########################################
STEP3_START=$(date +%s)

echo ""
echo "📄 Step 3: Compiling Typst templates..."
bash ./compile_notices.sh ${LANG}
STEP3_END=$(date +%s)
STEP3_DURATION=$((STEP3_END - STEP3_START))
echo "✅ Step 3: Compilation complete in ${STEP3_DURATION} seconds."

##########################################
# Step 4: Checking length of compiled files against expected length
##########################################

echo ""
echo "📏 Step 4: Checking length of compiled files..."

shopt -s nullglob
for file in "${OUTDIR}/pdf/${LANG}_client_"*.pdf; do
    python count_pdfs.py ${file}
done
shopt -u nullglob

##########################################
# Step 5: Cleanup
##########################################

echo ""
if [ "$SKIP_CLEANUP" = true ]; then
    echo "🧹 Step 5: Cleanup skipped (--no-cleanup flag)."
else
    echo "🧹 Step 5: Cleanup started..."
    python cleanup.py ${OUTDIR} ${LANG}
fi

##########################################
# Summary
##########################################
TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

echo ""
echo "🎉 Pipeline completed successfully!"
echo "🕒 Time Summary:"
echo "  - Preprocessing:         ${STEP1_DURATION}s"
echo "  - Template Generation:   ${STEP2_DURATION}s"
echo "  - Template Compilation:  ${STEP3_DURATION}s"
echo "  - -----------------------------"
echo "  - Total Time:            ${TOTAL_DURATION}s"
echo ""
echo "📦 Batch size:             ${BATCH_SIZE}"
echo "📊 Total records:          ${TOTAL_RECORDS}"
if [ "$SKIP_CLEANUP" = true ]; then
    echo "🧹 Cleanup:                Skipped"
fi