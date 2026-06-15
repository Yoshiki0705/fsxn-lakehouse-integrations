#!/bin/bash
set -euo pipefail

# FSxN DuckDB Integration — Resource Cleanup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/../params.json"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="dev"
STACK_NAME="fsxn-duckdb-integration"

echo "🗑️  FSxN DuckDB Cleanup"
read -p "Delete all DuckDB verification resources? [y/N] " -n 1 -r; echo
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 0

# Delete CloudFormation stack
echo "  Deleting stack: ${STACK_NAME}-${ENVIRONMENT}..."
aws cloudformation delete-stack --stack-name "${STACK_NAME}-${ENVIRONMENT}" --region "${REGION}" 2>/dev/null || true
aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}-${ENVIRONMENT}" --region "${REGION}" 2>/dev/null || true

# Clean local artifacts
rm -rf "${SCRIPT_DIR}/../tests/results/" "${SCRIPT_DIR}/../dist/"
echo "✅ Cleanup complete"
