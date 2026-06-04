#!/bin/bash

# Usage: ./scripts/compile_wasm.sh <source_file> <function1,function2>
# Example: ./scripts/compile_wasm.sh src/modules/core_logic/math.cpp standalone_sum,reset_timer

SRC_FILE=$1
FUNCTIONS=$2

if [ -z "$SRC_FILE" ]; then
    echo "Error: Please provide a source file."
    echo "Usage: $0 <source_file> <function1,function2>"
    exit 1
fi

# 1. Extract the filename for the output (e.g., some_module.cpp -> some_module)
BASE_NAME=$(basename -- "$SRC_FILE")
NAME="${BASE_NAME%.*}"
OUTPUT_DIR=$(dirname "$SRC_FILE")
OUTPUT_PATH="${OUTPUT_DIR}/${NAME}.wasm"

# 2. Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# 3. Format the exports string
# Converts "func1,func2" into "['_func1','_func2']"
if [ -n "$FUNCTIONS" ]; then
    # Replace commas with ','_ and wrap the whole thing
    FORMATTED=$(echo "$FUNCTIONS" | sed "s/,/','_/g" | sed "s/^/['_/g" | sed "s/$/']/g")
    EXPORT_FLAG="-s EXPORTED_FUNCTIONS=$FORMATTED"
else
    EXPORT_FLAG=""
fi

# 4. Set debug and optimization flags (always debug for research)
DEBUG_FLAG="-g"

# 4. Execute emcc
echo "Compiling $SRC_FILE..."
emcc "$SRC_FILE" \
    -o "$OUTPUT_PATH" \
    --no-entry \
    $EXPORT_FLAG \
    $DEBUG_FLAG \
    -s ERROR_ON_UNDEFINED_SYMBOLS=0

if [ $? -eq 0 ]; then
    echo "Successfully created: $OUTPUT_PATH"
else
    echo "Compilation failed."
fi