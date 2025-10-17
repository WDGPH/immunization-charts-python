#!/bin/bash
set -e

usage() {
    echo "Usage: $0 <input_file> <language> [options]"
    echo "       <language>: en | fr"
    echo "Options:"
    echo "  --keep-intermediate-files    Preserve .typ, .json, and per-client .pdf files"
    echo "  --remove-existing-output     Automatically remove existing output directory without prompt"
    echo "  --batch-size <N>             Enable batching with at most N clients per batch"
    echo "  --batch-by-school            Group batches by school identifier"
    echo "  --batch-by-board             Group batches by board identifier"
}

if [ $# -lt 2 ]; then
    usage
    exit 1
fi

INFILE=$1
LANG=$2
shift 2

SKIP_CLEANUP=false
BATCH_SIZE=0
BATCH_BY_SCHOOL=false
BATCH_BY_BOARD=false
REMOVE_EXISTING_OUTPUT=false

while [ $# -gt 0 ]; do
    case "$1" in
        --keep-intermediate-files)
            SKIP_CLEANUP=true
            ;;
        --remove-existing-output)
            REMOVE_EXISTING_OUTPUT=true
            ;;
        --batch-size)
            shift
            if [ -z "$1" ]; then
                echo "Error: --batch-size requires a value"
                usage
                exit 1
            fi
            BATCH_SIZE=$1
            ;;
        --batch-by-school)
            BATCH_BY_SCHOOL=true
            ;;
        --batch-by-board)
            BATCH_BY_BOARD=true
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

if [ "$BATCH_BY_SCHOOL" = true ] && [ "$BATCH_BY_BOARD" = true ]; then
    echo "Error: --batch-by-school and --batch-by-board cannot be used together."
    exit 1
fi

if ! [[ $BATCH_SIZE =~ ^[0-9]+$ ]]; then
    echo "Error: --batch-size must be a non-negative integer"
    exit 1
fi

INDIR="../input"
OUTDIR="../output"
LOG_DIR="${OUTDIR}/logs"
RUN_ID=$(date +%Y%m%dT%H%M%S)

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
# Step 1: Prepare Output Directory
##########################################
STEP1_START=$(date +%s)
echo "🧽 Step 1: Preparing output directory..."
PREPARE_ARGS=("--output-dir" "${OUTDIR}" "--log-dir" "${LOG_DIR}")
if [ "$REMOVE_EXISTING_OUTPUT" = true ]; then
    PREPARE_ARGS+=("--auto-remove")
fi

if ! python prepare_output.py "${PREPARE_ARGS[@]}"; then
    status=$?
    if [ "$status" -eq 2 ]; then
        exit 0
    fi
    exit "$status"
fi
STEP1_END=$(date +%s)
STEP1_DURATION=$((STEP1_END - STEP1_START))
echo "✅ Step 1: Output directory prepared in ${STEP1_DURATION} seconds."


##########################################
# Step 2: Preprocessing
##########################################
STEP2_START=$(date +%s)
echo ""
echo "🔍 Step 2: Preprocessing started..."
python preprocess.py ${INDIR} ${INFILE} ${OUTDIR} ${LANG} --run-id ${RUN_ID}
STEP2_END=$(date +%s)
STEP2_DURATION=$((STEP2_END - STEP2_START))
echo "✅ Step 2: Preprocessing complete in ${STEP2_DURATION} seconds."

ARTIFACT_PATH="${OUTDIR}/artifacts/preprocessed_clients_${RUN_ID}.json"
if [ -f "$ARTIFACT_PATH" ]; then
    TOTAL_CLIENTS=$(python summarize_preprocessed_clients.py "$ARTIFACT_PATH")
    echo "📄 Preprocessed artifact: ${ARTIFACT_PATH}"
    echo "👥 Clients normalized: ${TOTAL_CLIENTS}"
else
    echo "⚠️ Preprocessed artifact not found at ${ARTIFACT_PATH}"
    TOTAL_CLIENTS=0
fi

##########################################
# Step 3: Generating Notices
##########################################
STEP3_START=$(date +%s)
echo ""
echo "📝 Step 3: Generating Typst templates..."
python generate_notices.py \
    "${OUTDIR}/artifacts/preprocessed_clients_${RUN_ID}.json" \
    "${OUTDIR}/artifacts" \
    "../assets/logo.png" \
    "../assets/signature.png" \
    "../config/parameters.yaml"
STEP3_END=$(date +%s)
STEP3_DURATION=$((STEP3_END - STEP3_START))
echo "✅ Step 3: Template generation complete in ${STEP3_DURATION} seconds."

##########################################
# Step 4: Compiling Notices
##########################################
STEP4_START=$(date +%s)

echo ""
echo "📄 Step 4: Compiling Typst templates..."
python compile_notices.py \
    "${OUTDIR}/artifacts" \
    "${OUTDIR}/pdf_individual" \
    --quiet
STEP4_END=$(date +%s)
STEP4_DURATION=$((STEP4_END - STEP4_START))
echo "✅ Step 4: Compilation complete in ${STEP4_DURATION} seconds."

##########################################
# Step 5: Checking length of compiled files against expected length
##########################################

STEP5_START=$(date +%s)
echo ""
echo "📏 Step 5: Validating compiled PDF lengths..."
COUNT_JSON="${OUTDIR}/metadata/${LANG}_page_counts_${RUN_ID}.json"
python count_pdfs.py "${OUTDIR}/pdf_individual" --language "${LANG}" --json "${COUNT_JSON}"
STEP5_END=$(date +%s)
STEP5_DURATION=$((STEP5_END - STEP5_START))
echo "✅ Step 5: Length validation complete in ${STEP5_DURATION} seconds."

##########################################
# Step 6: Batching PDFs (optional)
########################################

STEP6_START=$(date +%s)
echo ""
if [ "$BATCH_SIZE" -gt 0 ]; then
    echo "📦 Step 6: Batching PDFs..."
    BATCH_ARGS=("${OUTDIR}" "${LANG}" "--run-id" "${RUN_ID}" "--batch-size" "${BATCH_SIZE}")
    if [ "$BATCH_BY_SCHOOL" = true ]; then
        BATCH_ARGS+=("--batch-by-school")
    fi
    if [ "$BATCH_BY_BOARD" = true ]; then
        BATCH_ARGS+=("--batch-by-board")
    fi
    python batch_pdfs.py "${BATCH_ARGS[@]}"
else
    echo "📦 Step 6: Batching skipped (batch size <= 0)."
fi
STEP6_END=$(date +%s)
STEP6_DURATION=$((STEP6_END - STEP6_START))
if [ "$BATCH_SIZE" -gt 0 ]; then
    echo "✅ Step 6: Batching complete in ${STEP6_DURATION} seconds."
fi

##########################################
# Step 7: Cleanup
##########################################

echo ""
if [ "$SKIP_CLEANUP" = true ]; then
    echo "🧹 Step 7: Cleanup skipped (--keep-intermediate-files flag)."
else
    echo "🧹 Step 7: Cleanup started..."
    python cleanup.py ${OUTDIR}
fi

##########################################
# Summary
##########################################
TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

echo ""
echo "🎉 Pipeline completed successfully!"
echo "🕒 Time Summary:"
echo "  - Output Preparation:    ${STEP1_DURATION}s"
echo "  - Preprocessing:         ${STEP2_DURATION}s"
echo "  - Template Generation:   ${STEP3_DURATION}s"
echo "  - Template Compilation:  ${STEP4_DURATION}s"
echo "  - PDF Validation:        ${STEP5_DURATION}s"
if [ "$BATCH_SIZE" -gt 0 ]; then
    echo "  - PDF Batching:          ${STEP6_DURATION}s"
fi
echo "  - -----------------------------"
echo "  - Total Time:            ${TOTAL_DURATION}s"
echo ""
echo "📦 Batch size:             ${BATCH_SIZE}"
if [ "$BATCH_BY_SCHOOL" = true ]; then
    echo "🏫 Batch scope:            School"
elif [ "$BATCH_BY_BOARD" = true ]; then
    echo "🏢 Batch scope:            Board"
else
    echo "🏷️  Batch scope:            Sequential"
fi
echo "👋 Clients processed:      ${TOTAL_CLIENTS}"
if [ "$SKIP_CLEANUP" = true ]; then
    echo "🧹 Cleanup:                Skipped"
fi