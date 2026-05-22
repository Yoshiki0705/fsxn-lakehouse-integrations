#!/bin/bash
set -euo pipefail

# =============================================================================
# DuckDB Lambda Layer Builder
# =============================================================================
# Builds a Lambda Layer containing DuckDB + httpfs extension for Python 3.12
# on arm64 (Graviton). Uses Docker to ensure correct architecture.
#
# Output: layer.zip (ready to upload to S3 and deploy)
#
# Usage:
#   ./build_layer.sh [--output-dir ./dist] [--duckdb-version 1.1.3]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../dist"
DUCKDB_VERSION="1.1.3"
LAYER_NAME="duckdb-layer"

while [[ $# -gt 0 ]]; do
  case $1 in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --duckdb-version) DUCKDB_VERSION="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

mkdir -p "${OUTPUT_DIR}"

echo "============================================"
echo "DuckDB Lambda Layer Builder"
echo "============================================"
echo "DuckDB version: ${DUCKDB_VERSION}"
echo "Output:         ${OUTPUT_DIR}/${LAYER_NAME}.zip"
echo ""

# Check if Docker is available
if command -v docker &>/dev/null; then
  echo "🐳 Building with Docker (arm64 compatible)..."

  docker run --rm \
    --platform linux/arm64 \
    -v "${OUTPUT_DIR}:/output" \
    public.ecr.aws/lambda/python:3.12-arm64 \
    bash -c "
      pip install duckdb==${DUCKDB_VERSION} --target /tmp/python/lib/python3.12/site-packages/ --quiet
      cd /tmp && zip -r /output/${LAYER_NAME}.zip python/ -x '*.pyc' -x '*/__pycache__/*'
      echo 'Layer size:' \$(du -sh /output/${LAYER_NAME}.zip | cut -f1)
    "

  echo "✅ Layer built: ${OUTPUT_DIR}/${LAYER_NAME}.zip"

else
  echo "⚠️  Docker not found. Building natively (may not be arm64 compatible)..."
  echo "   For production, use Docker to ensure arm64 compatibility."
  echo ""

  BUILD_DIR=$(mktemp -d)
  PYTHON_DIR="${BUILD_DIR}/python/lib/python3.12/site-packages"
  mkdir -p "${PYTHON_DIR}"

  pip3 install "duckdb==${DUCKDB_VERSION}" --target "${PYTHON_DIR}" --quiet

  cd "${BUILD_DIR}"
  zip -r "${OUTPUT_DIR}/${LAYER_NAME}.zip" python/ -x "*.pyc" -x "*/__pycache__/*"
  rm -rf "${BUILD_DIR}"

  echo "✅ Layer built: ${OUTPUT_DIR}/${LAYER_NAME}.zip"
fi

# Show layer size
LAYER_SIZE=$(du -sh "${OUTPUT_DIR}/${LAYER_NAME}.zip" | cut -f1)
echo "   Size: ${LAYER_SIZE}"
echo ""
echo "Next step: Upload to S3"
echo "  aws s3 cp ${OUTPUT_DIR}/${LAYER_NAME}.zip s3://<bucket>/layers/${LAYER_NAME}-dev.zip"
