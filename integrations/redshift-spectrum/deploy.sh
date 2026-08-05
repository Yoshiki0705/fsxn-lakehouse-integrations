#!/bin/bash
set -euo pipefail

# =============================================================================
# FSx for ONTAP Redshift Spectrum Integration — Deploy & Verify & Cleanup
# =============================================================================
# Creates Redshift Serverless, runs Spectrum queries on FSx for ONTAP S3 AP data,
# records results, then DELETES Redshift to avoid ongoing costs.
#
# Cost: ~$2.88/hr (8 RPU minimum). Script targets <30 min total.
#
# Prerequisites:
#   - AWS CLI configured
#   - Glue Catalog database 'fsxn_athena_verification' with tables
#   - S3 AP (internet-origin) with data
#
# Usage:
#   ./deploy.sh [--region ap-northeast-1] [--skip-cleanup]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
NAMESPACE="fsxn-spectrum-ns"
WORKGROUP="fsxn-spectrum-wg"
DB_NAME="dev"
ADMIN_USER="admin"
SKIP_CLEANUP=false
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# S3 AP details (reuse from Athena verification)
S3_AP_NAME="verification-test-ap"
S3_AP_ARN="arn:aws:s3:${REGION}:${ACCOUNT_ID}:accesspoint/${S3_AP_NAME}"
GLUE_DB="fsxn_athena_verification"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --skip-cleanup) SKIP_CLEANUP=true; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

echo "============================================"
echo "FSx for ONTAP Redshift Spectrum Verification"
echo "============================================"
echo "Region:     ${REGION}"
echo "Namespace:  ${NAMESPACE}"
echo "Workgroup:  ${WORKGROUP}"
echo "Glue DB:    ${GLUE_DB}"
echo "S3 AP:      ${S3_AP_NAME}"
echo "Cleanup:    $([ "${SKIP_CLEANUP}" = true ] && echo 'SKIP' || echo 'YES (after verification)')"
echo ""

# --- Step 1: Create IAM Role for Redshift Spectrum ---
echo "🔐 Step 1: Creating IAM Role for Redshift Spectrum..."

ROLE_NAME="fsxn-redshift-spectrum-role"
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "redshift.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text 2>/dev/null || true)

if [[ -z "${ROLE_ARN}" || "${ROLE_ARN}" == "None" ]]; then
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document "${TRUST_POLICY}" \
    --region "${REGION}" > /dev/null

  # Attach S3 AP access policy
  POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3APAccess",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": [
        "${S3_AP_ARN}",
        "${S3_AP_ARN}/object/*"
      ]
    },
    {
      "Sid": "GlueCatalogAccess",
      "Effect": "Allow",
      "Action": ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables", "glue:GetPartitions"],
      "Resource": ["*"]
    }
  ]
}
EOF
)
  aws iam put-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-name "S3APSpectrumPolicy" \
    --policy-document "${POLICY_DOC}"

  ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text)
  echo "  ✅ Role created: ${ROLE_ARN}"
  echo "  ⏳ Waiting 10s for IAM propagation..."
  sleep 10
else
  echo "  ✅ Role exists: ${ROLE_ARN}"
fi

# --- Step 2: Create Redshift Serverless Namespace ---
echo ""
echo "🗄️  Step 2: Creating Redshift Serverless Namespace..."

NS_STATUS=$(aws redshift-serverless get-namespace --namespace-name "${NAMESPACE}" --region "${REGION}" --query 'namespace.status' --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "${NS_STATUS}" == "NOT_FOUND" ]]; then
  aws redshift-serverless create-namespace \
    --namespace-name "${NAMESPACE}" \
    --admin-username "${ADMIN_USER}" \
    --admin-user-password "TempPass123!" \
    --db-name "${DB_NAME}" \
    --iam-roles "${ROLE_ARN}" \
    --region "${REGION}" > /dev/null
  echo "  ✅ Namespace created"
else
  echo "  ✅ Namespace exists (${NS_STATUS})"
fi

# --- Step 3: Create Redshift Serverless Workgroup ---
echo ""
echo "⚡ Step 3: Creating Redshift Serverless Workgroup (8 RPU)..."

WG_STATUS=$(aws redshift-serverless get-workgroup --workgroup-name "${WORKGROUP}" --region "${REGION}" --query 'workgroup.status' --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "${WG_STATUS}" == "NOT_FOUND" ]]; then
  aws redshift-serverless create-workgroup \
    --workgroup-name "${WORKGROUP}" \
    --namespace-name "${NAMESPACE}" \
    --base-capacity 8 \
    --region "${REGION}" > /dev/null
  echo "  ⏳ Waiting for workgroup to become AVAILABLE..."

  for i in $(seq 1 30); do
    WG_STATUS=$(aws redshift-serverless get-workgroup --workgroup-name "${WORKGROUP}" --region "${REGION}" --query 'workgroup.status' --output text 2>/dev/null)
    if [[ "${WG_STATUS}" == "AVAILABLE" ]]; then
      break
    fi
    echo "    Status: ${WG_STATUS} (${i}/30)..."
    sleep 10
  done

  if [[ "${WG_STATUS}" != "AVAILABLE" ]]; then
    echo "  ❌ Workgroup not available after 5 minutes. Status: ${WG_STATUS}"
    exit 1
  fi
  echo "  ✅ Workgroup AVAILABLE"
else
  echo "  ✅ Workgroup exists (${WG_STATUS})"
fi

# --- Step 4: Run Spectrum Queries ---
echo ""
echo "🔍 Step 4: Running Spectrum queries..."

# Create external schema
echo "  Creating external schema..."
STMT_ID=$(aws redshift-data execute-statement \
  --workgroup-name "${WORKGROUP}" \
  --database "${DB_NAME}" \
  --sql "CREATE EXTERNAL SCHEMA IF NOT EXISTS fsxn_spectrum FROM DATA CATALOG DATABASE '${GLUE_DB}' IAM_ROLE '${ROLE_ARN}' REGION '${REGION}';" \
  --region "${REGION}" \
  --query 'Id' --output text)

# Wait for completion
for i in $(seq 1 20); do
  STATUS=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Status' --output text)
  if [[ "${STATUS}" == "FINISHED" || "${STATUS}" == "FAILED" || "${STATUS}" == "ABORTED" ]]; then
    break
  fi
  sleep 3
done
echo "  External schema: ${STATUS}"

if [[ "${STATUS}" == "FAILED" ]]; then
  aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Error' --output text
fi

# Query 1: Simple SELECT
echo ""
echo "  ▶ Query 1: SELECT COUNT(*) FROM sensor_readings"
STMT_ID=$(aws redshift-data execute-statement \
  --workgroup-name "${WORKGROUP}" \
  --database "${DB_NAME}" \
  --sql "SELECT COUNT(*) AS total_rows FROM fsxn_spectrum.sensor_readings;" \
  --region "${REGION}" \
  --query 'Id' --output text)

for i in $(seq 1 30); do
  STATUS=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Status' --output text)
  if [[ "${STATUS}" == "FINISHED" || "${STATUS}" == "FAILED" || "${STATUS}" == "ABORTED" ]]; then
    break
  fi
  sleep 2
done

if [[ "${STATUS}" == "FINISHED" ]]; then
  DURATION=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Duration' --output text)
  RESULT=$(aws redshift-data get-statement-result --id "${STMT_ID}" --region "${REGION}" --query 'Records[0][0].longValue' --output text 2>/dev/null || echo "N/A")
  echo "    ✅ Result: ${RESULT} rows | Duration: ${DURATION}ns"
else
  echo "    ❌ ${STATUS}"
  aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Error' --output text
fi

# Query 2: GROUP BY aggregation
echo ""
echo "  ▶ Query 2: GROUP BY status with AVG"
STMT_ID=$(aws redshift-data execute-statement \
  --workgroup-name "${WORKGROUP}" \
  --database "${DB_NAME}" \
  --sql "SELECT status, COUNT(*) AS cnt, AVG(temperature) AS avg_temp, AVG(humidity) AS avg_hum FROM fsxn_spectrum.sensor_readings GROUP BY status ORDER BY cnt DESC;" \
  --region "${REGION}" \
  --query 'Id' --output text)

for i in $(seq 1 30); do
  STATUS=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Status' --output text)
  if [[ "${STATUS}" == "FINISHED" || "${STATUS}" == "FAILED" || "${STATUS}" == "ABORTED" ]]; then
    break
  fi
  sleep 2
done

if [[ "${STATUS}" == "FINISHED" ]]; then
  DURATION=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Duration' --output text)
  echo "    ✅ Duration: ${DURATION}ns"
  aws redshift-data get-statement-result --id "${STMT_ID}" --region "${REGION}" --query 'Records[]' --output json 2>/dev/null | python3 -c "
import sys, json
records = json.load(sys.stdin)
for r in records:
    status = r[0].get('stringValue','?')
    cnt = r[1].get('longValue','?')
    temp = r[2].get('stringValue','?')
    hum = r[3].get('stringValue','?')
    print(f'    {status:10s}: {cnt:>6} rows, temp={temp}, hum={hum}')
" 2>/dev/null || echo "    (result parsing skipped)"
else
  echo "    ❌ ${STATUS}"
  aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Error' --output text
fi

# Query 3: Large table scan (5M rows)
echo ""
echo "  ▶ Query 3: COUNT(*) on sensor_benchmark (5M rows)"
STMT_ID=$(aws redshift-data execute-statement \
  --workgroup-name "${WORKGROUP}" \
  --database "${DB_NAME}" \
  --sql "SELECT COUNT(*) AS total FROM fsxn_spectrum.sensor_benchmark;" \
  --region "${REGION}" \
  --query 'Id' --output text)

for i in $(seq 1 60); do
  STATUS=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Status' --output text)
  if [[ "${STATUS}" == "FINISHED" || "${STATUS}" == "FAILED" || "${STATUS}" == "ABORTED" ]]; then
    break
  fi
  sleep 3
done

if [[ "${STATUS}" == "FINISHED" ]]; then
  DURATION=$(aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Duration' --output text)
  RESULT=$(aws redshift-data get-statement-result --id "${STMT_ID}" --region "${REGION}" --query 'Records[0][0].longValue' --output text 2>/dev/null || echo "N/A")
  echo "    ✅ Result: ${RESULT} rows | Duration: ${DURATION}ns"
else
  echo "    ❌ ${STATUS}"
  aws redshift-data describe-statement --id "${STMT_ID}" --region "${REGION}" --query 'Error' --output text
fi

echo ""
echo "============================================"
echo "✅ Spectrum verification complete"
echo "============================================"

# --- Step 5: Cleanup ---
if [[ "${SKIP_CLEANUP}" == "false" ]]; then
  echo ""
  echo "🧹 Step 5: Cleaning up Redshift Serverless (cost control)..."

  aws redshift-serverless delete-workgroup \
    --workgroup-name "${WORKGROUP}" \
    --region "${REGION}" 2>/dev/null || true
  echo "  Workgroup deletion initiated"

  # Wait for workgroup deletion before deleting namespace
  for i in $(seq 1 20); do
    WG_EXISTS=$(aws redshift-serverless get-workgroup --workgroup-name "${WORKGROUP}" --region "${REGION}" 2>/dev/null && echo "yes" || echo "no")
    if [[ "${WG_EXISTS}" == "no" ]]; then
      break
    fi
    sleep 5
  done

  aws redshift-serverless delete-namespace \
    --namespace-name "${NAMESPACE}" \
    --region "${REGION}" 2>/dev/null || true
  echo "  Namespace deletion initiated"

  echo "  ✅ Cleanup complete (resources being deleted)"
else
  echo ""
  echo "⚠️  Cleanup SKIPPED (--skip-cleanup). Remember to delete manually!"
  echo "    aws redshift-serverless delete-workgroup --workgroup-name ${WORKGROUP} --region ${REGION}"
  echo "    aws redshift-serverless delete-namespace --namespace-name ${NAMESPACE} --region ${REGION}"
fi
