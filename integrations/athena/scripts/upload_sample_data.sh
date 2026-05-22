#!/bin/bash
set -euo pipefail

# =============================================================================
# FSxN Athena Integration — Upload Sample Data to FSxN via NFS
# =============================================================================
# Mounts FSxN volume via NFS and copies generated sample data.
# Data is organized in Hive-style partition structure for Glue Crawler.
#
# Prerequisites:
#   - FSxN NFS endpoint accessible from this machine
#   - Sample data generated via generate_sample_data.py
#   - NFS client installed (nfs-common / nfs-utils)
#
# Usage:
#   ./upload_sample_data.sh [--mount-point /mnt/fsxn] [--data-dir ./sample_data]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/../params.json"

# Defaults
MOUNT_POINT="/mnt/fsxn"
DATA_DIR="${SCRIPT_DIR}/../sample_data"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --mount-point) MOUNT_POINT="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Load NFS endpoint from params
if [[ -f "${PARAMS_FILE}" ]]; then
  SVM_NFS_ENDPOINT=$(jq -r '.SvmNfsEndpoint // empty' "${PARAMS_FILE}")
  NFS_MOUNT_POINT=$(jq -r '.NfsMountPoint // empty' "${PARAMS_FILE}")
  if [[ -n "${NFS_MOUNT_POINT}" ]]; then
    MOUNT_POINT="${NFS_MOUNT_POINT}"
  fi
fi

echo "============================================"
echo "FSxN Sample Data Upload"
echo "============================================"
echo "Data source:  ${DATA_DIR}"
echo "Mount point:  ${MOUNT_POINT}"
echo ""

# Check data directory exists
if [[ ! -d "${DATA_DIR}" ]]; then
  echo "❌ Data directory not found: ${DATA_DIR}"
  echo "   Run: python scripts/generate_sample_data.py first"
  exit 1
fi

# Check mount point
if ! mountpoint -q "${MOUNT_POINT}" 2>/dev/null; then
  echo "⚠️  ${MOUNT_POINT} is not mounted."
  echo ""
  if [[ -n "${SVM_NFS_ENDPOINT:-}" ]]; then
    echo "Mount command:"
    echo "  sudo mkdir -p ${MOUNT_POINT}"
    echo "  sudo mount -t nfs -o vers=4.1 ${SVM_NFS_ENDPOINT}:/ ${MOUNT_POINT}"
  else
    echo "Please mount FSxN volume first:"
    echo "  sudo mount -t nfs -o vers=4.1 <SVM_NFS_ENDPOINT>:/<volume_junction> ${MOUNT_POINT}"
  fi
  echo ""
  read -p "Continue anyway (data dir may already be accessible)? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Upload data
echo "📤 Uploading sample data to FSxN..."
echo ""

# Transactions (partitioned Parquet)
echo "  📁 transactions/ (partitioned Parquet)..."
rsync -av --progress "${DATA_DIR}/transactions/" "${MOUNT_POINT}/transactions/"
echo ""

# Customers (CSV)
echo "  📁 customers/ (CSV)..."
rsync -av --progress "${DATA_DIR}/customers/" "${MOUNT_POINT}/customers/"
echo ""

# Events (JSON)
echo "  📁 events/ (JSON)..."
rsync -av --progress "${DATA_DIR}/events/" "${MOUNT_POINT}/events/"
echo ""

# Create gold output directory
echo "  📁 Creating gold/ output directory..."
mkdir -p "${MOUNT_POINT}/gold"
echo ""

# Summary
TOTAL_FILES=$(find "${MOUNT_POINT}/transactions" "${MOUNT_POINT}/customers" "${MOUNT_POINT}/events" -type f 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "${MOUNT_POINT}/transactions" "${MOUNT_POINT}/customers" "${MOUNT_POINT}/events" 2>/dev/null | awk '{sum += $1} END {print sum}')

echo "============================================"
echo "✅ Upload complete!"
echo "============================================"
echo "  Files uploaded: ~${TOTAL_FILES} files"
echo ""
echo "Directory structure on FSxN:"
echo "  ${MOUNT_POINT}/"
echo "  ├── transactions/year=2024/month=01/*.parquet"
echo "  ├── transactions/year=2024/month=02/*.parquet"
echo "  ├── ..."
echo "  ├── customers/customers.csv"
echo "  ├── events/events_*.json"
echo "  └── gold/ (empty — CTAS output target)"
echo ""
echo "Next step: Run Glue Crawler to discover tables"
echo "  aws glue start-crawler --name fsxn-athena-crawler-dev"
