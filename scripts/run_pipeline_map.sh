#!/bin/bash
set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <input_file> <language> [--no-cleanup]"
    exit 1
fi

INFILE=$1
LANG=$2
SKIP_CLEANUP=false
MAP_SCHOOL=false


# Shift past the first two arguments
shift 2

# Define allowed flags
allowed_flags=("--no-cleanup" "--map-school")

# Loop through remaining arguments
while [[ $# -gt 0 ]]; do
    flag="$1"
    shift

    # Check if flag is allowed
    if [[ " ${allowed_flags[@]} " =~ " ${flag} " ]]; then
        case $flag in
            --no-cleanup)
                SKIP_CLEANUP=true
                ;;
            --map-school)
                MAP_SCHOOL=true
                ;;
            *)
                echo "Unknown option: $flag"
                echo "Usage: $0 <input_file> <language> [--no-cleanup] [--map-school]"
                exit 1
                ;;
        esac
    
    else
        echo "Error: Unknown flag $flag"
        exit 1
    fi
done

INDIR="../input"
OUTDIR="../output"
BATCH_SIZE=100

if [ "$LANG" != "english" ] && [ "$LANG" != "french" ]; then
    echo "Error: Language must be 'english' or 'french'"
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
python preprocess.py ${INDIR} ${INFILE} ${OUTDIR} ${LANG} ${BATCH_SIZE}
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
bash ./generate_notices.sh ${LANG} ${MAP_SCHOOL}
STEP2_END=$(date +%s)
STEP2_DURATION=$((STEP2_END - STEP2_START))
echo "✅ Step 2: Template generation complete in ${STEP2_DURATION} seconds."

##########################################
# Step 3: Compiling Notices
##########################################
STEP3_START=$(date +%s)

# Check to see if the conf.typ file is in the json_ directory
if [ -e "${OUTDIR}/json_${LANG}/conf.typ" ]; then
    echo "Found conf.typ in ${OUTDIR}/json_${LANG}/"
else
    # Move conf.typ to the json_ directory
    echo "Moving conf.typ to ${OUTDIR}/json_${LANG}/"
    cp ./conf.typ "${OUTDIR}/json_${LANG}/conf.typ"
fi

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

# Remove conf.pdf if it exists
if [ -e "${OUTDIR}/json_${LANG}/conf.pdf" ]; then
    echo "Removing existing conf.pdf..."
    rm "${OUTDIR}/json_${LANG}/conf.pdf"
fi

for file in "${OUTDIR}/json_${LANG}/"*.pdf; do
    python count_pdfs.py ${file}
done

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