#!/bin/bash
#
# Batch VixSrc Downloader
# Download multiple episodes or movies from a list
#
# Usage:
#   ./batch_download.sh episodes.txt [output_directory]
#
# File format (one per line):
#   tv TMDB_ID SEASON EPISODE [OUTPUT_FILE] [LANG] [QUALITY]
#   movie TMDB_ID [OUTPUT_FILE] [LANG] [QUALITY]
#
# Example episodes.txt:
#   tv 60625 4 1 breaking_bad_s04e01.mp4 en 1080
#   tv 60625 4 2 bb_s04e02.mp4 es
#   movie 550 fight_club.mp4 en 720
#   movie 603
#
# If output_directory is specified, all downloads will be saved there.
# If not specified, files will be saved in the current directory.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if input file is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No input file specified${NC}"
    echo "Usage: $0 <file_with_download_list> [output_directory]"
    echo ""
    echo "File format (one per line):"
    echo "  tv TMDB_ID SEASON EPISODE [OUTPUT_FILE] [LANG] [QUALITY]"
    echo "  movie TMDB_ID [OUTPUT_FILE] [LANG] [QUALITY]"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_DIR="${2:-}"

# Create output directory if specified
if [ -n "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR"
    echo -e "${GREEN}Created/using output directory: $OUTPUT_DIR${NC}"
    echo ""
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: File '$INPUT_FILE' not found${NC}"
    exit 1
fi

# Check if downloader script exists
DOWNLOADER="./vixsrc_downloader.py"
if [ ! -f "$DOWNLOADER" ]; then
    echo -e "${RED}Error: vixsrc_downloader.py not found in current directory${NC}"
    exit 1
fi

# Make downloader executable
chmod +x "$DOWNLOADER"

# Statistics
TOTAL=0
SUCCESS=0
FAILED=0

echo -e "${GREEN}=== VixSrc Batch Downloader ===${NC}"
echo ""

# Process each line
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^#.*$ ]] && continue
    
    TOTAL=$((TOTAL + 1))
    
    # Parse the line
    read -ra PARTS <<< "$line"
    TYPE="${PARTS[0]}"
    
    echo -e "${YELLOW}[$TOTAL] Processing: $line${NC}"
    
    if [ "$TYPE" == "tv" ]; then
        TMDB_ID="${PARTS[1]}"
        SEASON="${PARTS[2]}"
        EPISODE="${PARTS[3]}"
        OUTPUT="${PARTS[4]:-}"
        LANG="${PARTS[5]:-}"
        QUALITY="${PARTS[6]:-}"

        # Treat "-" as empty/no value
        [ "$OUTPUT" == "-" ] && OUTPUT=""
        [ "$LANG" == "-" ] && LANG=""
        [ "$QUALITY" == "-" ] && QUALITY=""

        if [ -z "$TMDB_ID" ] || [ -z "$SEASON" ] || [ -z "$EPISODE" ]; then
            echo -e "${RED}  ✗ Invalid TV format: $line${NC}"
            FAILED=$((FAILED + 1))
            continue
        fi

        CMD="python3 $DOWNLOADER --tv $TMDB_ID --season $SEASON --episode $EPISODE"
        if [ -n "$OUTPUT" ]; then
            # If output directory is specified and OUTPUT is not an absolute path, prepend directory
            if [ -n "$OUTPUT_DIR" ] && [[ "$OUTPUT" != /* ]]; then
                CMD="$CMD --output \"$OUTPUT_DIR/$OUTPUT\""
            else
                CMD="$CMD --output \"$OUTPUT\""
            fi
        elif [ -n "$OUTPUT_DIR" ]; then
            # No custom filename, but directory specified - let TMDB auto-generate filename in directory
            CMD="$CMD --output-dir \"$OUTPUT_DIR\""
        fi
        [ -n "$LANG" ] && CMD="$CMD --lang $LANG"
        [ -n "$QUALITY" ] && CMD="$CMD --quality $QUALITY"
        
    elif [ "$TYPE" == "movie" ]; then
        TMDB_ID="${PARTS[1]}"
        OUTPUT="${PARTS[2]:-}"
        LANG="${PARTS[3]:-}"
        QUALITY="${PARTS[4]:-}"

        # Treat "-" as empty/no value
        [ "$OUTPUT" == "-" ] && OUTPUT=""
        [ "$LANG" == "-" ] && LANG=""
        [ "$QUALITY" == "-" ] && QUALITY=""

        if [ -z "$TMDB_ID" ]; then
            echo -e "${RED}  ✗ Invalid movie format: $line${NC}"
            FAILED=$((FAILED + 1))
            continue
        fi

        CMD="python3 $DOWNLOADER --movie $TMDB_ID"
        if [ -n "$OUTPUT" ]; then
            # If output directory is specified and OUTPUT is not an absolute path, prepend directory
            if [ -n "$OUTPUT_DIR" ] && [[ "$OUTPUT" != /* ]]; then
                CMD="$CMD --output \"$OUTPUT_DIR/$OUTPUT\""
            else
                CMD="$CMD --output \"$OUTPUT\""
            fi
        elif [ -n "$OUTPUT_DIR" ]; then
            # No custom filename, but directory specified - let TMDB auto-generate filename in directory
            CMD="$CMD --output-dir \"$OUTPUT_DIR\""
        fi
        [ -n "$LANG" ] && CMD="$CMD --lang $LANG"
        [ -n "$QUALITY" ] && CMD="$CMD --quality $QUALITY"
        
    else
        echo -e "${RED}  ✗ Unknown type: $TYPE${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Execute download
    if eval $CMD; then
        echo -e "${GREEN}  ✓ Download successful${NC}"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${RED}  ✗ Download failed${NC}"
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
done < "$INPUT_FILE"

# Print summary
echo -e "${GREEN}=== Summary ===${NC}"
echo "Total: $TOTAL"
echo -e "${GREEN}Success: $SUCCESS${NC}"
echo -e "${RED}Failed: $FAILED${NC}"

exit 0
