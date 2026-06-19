#!/bin/bash
set -uo pipefail

# =============================================================================
# Reproducible Gate Check — ClickHouse DataLakeCatalog -> Unity Catalog (Beta)
#                           + Network (NCC / SG / VPC Endpoint)
# =============================================================================
# Plan: docs/{ja,en}/verification-plan-clickhouse-uc-connectivity.md (Phases A0/B0)
#
# Purpose : READ-ONLY check of whether the prerequisites ("gates") for the live
#           verification are met in the current environment. Run this BEFORE
#           attempting Track A / Track B so you know what is blocked and why.
#
# Safety  : Read-only ONLY. Calls: command -v, aws sts/kafka/ec2 describe|list.
#           No resources created, no SG/IAM/UC changes, no billable provisioning.
#
# Config  : Parameterized via environment variables (no hardcoded account values):
#             REGION              (default: ap-northeast-1)
#             MSK_CLUSTER_NAME    (optional: filter MSK list to this name)
#             DATABRICKS_HOST     (optional: presence-only check)
#             CLICKHOUSE_HOST     (optional: presence-only check)
#
# Exit    : Always 0 (diagnostic). Prints a gate matrix + BLOCKED count.
# =============================================================================

REGION="${REGION:-ap-northeast-1}"

PASS="MET"
FAIL="NOT MET / BLOCKED"
blocked=0

ok()    { echo "  [ ${PASS} ] $1"; }
no()    { echo "  [ ${FAIL} ] $1"; blocked=$((blocked+1)); }
info()  { echo "          - $1"; }

echo "============================================================"
echo " Gate Check: ClickHouse DataLakeCatalog -> UC (Beta) + Net"
echo " Region: ${REGION}   Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"

# ---------------------------------------------------------------------------
echo ""
echo "## AWS identity (read-only)"
if aws sts get-caller-identity >/dev/null 2>&1; then
  ACCT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)"
  ok "AWS credentials usable (account: ${ACCT})"
else
  no "AWS credentials NOT usable (aws sts get-caller-identity failed)"
fi

# ---------------------------------------------------------------------------
echo ""
echo "## Track A gates — ClickHouse DataLakeCatalog -> Unity Catalog"

# A-gate 1: ClickHouse client / Cloud access
if command -v clickhouse-client >/dev/null 2>&1; then
  ok "clickhouse-client installed"
else
  no "clickhouse-client NOT installed"
fi
if [ -n "${CLICKHOUSE_HOST:-}" ] || env | grep -qiE '^(CLICKHOUSE|CH)_'; then
  ok "ClickHouse connection hint present (env/CLICKHOUSE_HOST)"
else
  no "No ClickHouse Cloud credentials/host in environment"
  info "Need: ClickHouse Cloud with DataLakeCatalog (catalog_type='unity', Beta) enabled"
fi

# A-gate 2/3: Databricks CLI + auth
if command -v databricks >/dev/null 2>&1; then
  ok "databricks CLI installed"
else
  no "databricks CLI NOT installed"
fi
if [ -n "${DATABRICKS_HOST:-}" ] || env | grep -qiE '^DATABRICKS_'; then
  ok "Databricks connection hint present (env/DATABRICKS_HOST)"
else
  no "No Databricks workspace auth in environment (host/token)"
  info "Need: workspace URL + token (or SP); UC external data access enabled (CN-B3)"
fi

# ---------------------------------------------------------------------------
echo ""
echo "## Track B gates — Network (NCC / SG / VPC endpoint)"

# B-grounding: MSK cluster existence (read-only)
MSK_JSON="$(aws kafka list-clusters-v2 --region "${REGION}" \
  --query 'ClusterInfoList[].{name:ClusterName,state:State,type:ClusterType}' \
  --output json 2>/dev/null || echo '[]')"
MSK_COUNT="$(echo "${MSK_JSON}" | grep -c '"name"' || true)"
if [ "${MSK_COUNT}" -gt 0 ]; then
  ok "MSK cluster(s) present: ${MSK_COUNT} (Kafka source does not need to be built)"
  if [ -n "${MSK_CLUSTER_NAME:-}" ]; then
    echo "${MSK_JSON}" | grep -q "\"${MSK_CLUSTER_NAME}\"" \
      && info "Named cluster '${MSK_CLUSTER_NAME}' found" \
      || info "Named cluster '${MSK_CLUSTER_NAME}' NOT found"
  fi
else
  no "No MSK cluster found in ${REGION}"
fi

# B-grounding: S3 Gateway VPC endpoints (read-only)
EP_COUNT="$(aws ec2 describe-vpc-endpoints --region "${REGION}" \
  --filters "Name=service-name,Values=com.amazonaws.${REGION}.s3" \
  --query 'length(VpcEndpoints[?VpcEndpointType==`Gateway`])' \
  --output text 2>/dev/null || echo 0)"
if [ "${EP_COUNT}" != "0" ] && [ -n "${EP_COUNT}" ]; then
  ok "S3 Gateway VPC endpoint(s) available: ${EP_COUNT}"
else
  no "No S3 Gateway VPC endpoint found (ClickHouse->S3 private path B2)"
fi

# B-gate: Databricks serverless workspace (needed for NCC create/assign + streaming)
if command -v databricks >/dev/null 2>&1 && { [ -n "${DATABRICKS_HOST:-}" ] || env | grep -qiE '^DATABRICKS_'; }; then
  ok "Databricks access present (NCC create/assign + Structured Streaming possible)"
else
  no "Databricks serverless workspace access absent (NCC/streaming path B1 blocked)"
fi

# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
if [ "${blocked}" -eq 0 ]; then
  echo " RESULT: ALL GATES MET — Track A (A1..A6) and Track B (B1..B4) can run."
else
  echo " RESULT: ${blocked} gate(s) BLOCKED — see [ ${FAIL} ] lines above."
  echo " Next  : provide the missing credentials/access, then re-run this check."
fi
echo "============================================================"
echo ""
echo "Reminder: Beta features (DataLakeCatalog, UC external data access)"
echo "          -> treat as evaluation; defer production decision until GA."

exit 0
