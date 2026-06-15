#!/bin/bash
set -euo pipefail

# FSx for ONTAP S3 AP — Lake Formation Governance Setup (PoC)
# Usage: ./lakeformation-setup.sh --account <ACCOUNT_ID> --admin <ADMIN_USER> --database <DB_NAME> --table <TABLE_NAME>

ACCOUNT_ID=""
ADMIN_USER=""
DATABASE="fsxn_poc"
TABLE="sensor_data"
ANALYST_ROLE=""
REGION="${AWS_REGION:-ap-northeast-1}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --account) ACCOUNT_ID="$2"; shift 2 ;;
    --admin) ADMIN_USER="$2"; shift 2 ;;
    --database) DATABASE="$2"; shift 2 ;;
    --table) TABLE="$2"; shift 2 ;;
    --analyst-role) ANALYST_ROLE="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --help)
      echo "Usage: ./lakeformation-setup.sh --account <ID> --admin <USER> [--database <DB>] [--table <TABLE>] [--analyst-role <ROLE>]"
      exit 0 ;;
    *) shift ;;
  esac
done

if [ -z "$ACCOUNT_ID" ] || [ -z "$ADMIN_USER" ]; then
  echo "Error: --account and --admin are required"
  exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Lake Formation Governance Setup                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Account:  ${ACCOUNT_ID}"
echo "Admin:    ${ADMIN_USER}"
echo "Database: ${DATABASE}"
echo "Table:    ${TABLE}"
echo "Region:   ${REGION}"
echo ""

# ============================================================
# Step 1: Set Lake Formation Admin
# ============================================================
echo "━━━ Step 1: Set Lake Formation Admin ━━━"
aws lakeformation put-data-lake-settings \
  --data-lake-settings "{
    \"DataLakeAdmins\": [{
      \"DataLakePrincipalIdentifier\": \"arn:aws:iam::${ACCOUNT_ID}:user/${ADMIN_USER}\"
    }]
  }" \
  --region "${REGION}"
echo "  ✅ Lake Formation admin set: ${ADMIN_USER}"
echo ""

# ============================================================
# Step 2: Create LF-Tag (sensitivity classification)
# ============================================================
echo "━━━ Step 2: Create LF-Tag ━━━"
aws lakeformation create-lf-tag \
  --tag-key "sensitivity" \
  --tag-values '["public","internal","confidential"]' \
  --region "${REGION}" 2>/dev/null || echo "  (Tag already exists)"
echo "  ✅ LF-Tag 'sensitivity' created with values: public, internal, confidential"
echo ""

# ============================================================
# Step 3: Assign tag to table
# ============================================================
echo "━━━ Step 3: Assign tag to table ━━━"
aws lakeformation add-lf-tags-to-resource \
  --resource "{\"Table\": {\"DatabaseName\": \"${DATABASE}\", \"Name\": \"${TABLE}\"}}" \
  --lf-tags "[{\"TagKey\": \"sensitivity\", \"TagValues\": [\"internal\"]}]" \
  --region "${REGION}" 2>/dev/null || echo "  (Tag already assigned)"
echo "  ✅ Tag 'sensitivity=internal' assigned to ${DATABASE}.${TABLE}"
echo ""

# ============================================================
# Step 4: Grant table-level SELECT (if analyst role specified)
# ============================================================
if [ -n "$ANALYST_ROLE" ]; then
  echo "━━━ Step 4: Grant table-level SELECT to analyst role ━━━"
  aws lakeformation grant-permissions \
    --principal "{\"DataLakePrincipalIdentifier\": \"arn:aws:iam::${ACCOUNT_ID}:role/${ANALYST_ROLE}\"}" \
    --resource "{\"Table\": {\"DatabaseName\": \"${DATABASE}\", \"Name\": \"${TABLE}\"}}" \
    --permissions '["SELECT", "DESCRIBE"]' \
    --region "${REGION}"
  echo "  ✅ SELECT + DESCRIBE granted to role: ${ANALYST_ROLE}"
  echo ""
fi

# ============================================================
# Step 5: Create column-level permission example
# ============================================================
echo "━━━ Step 5: Column-level permission example ━━━"
echo "  To grant access to specific columns only:"
echo ""
echo "  aws lakeformation grant-permissions \\"
echo "    --principal '{\"DataLakePrincipalIdentifier\": \"arn:aws:iam::${ACCOUNT_ID}:role/<RESTRICTED_ROLE>\"}' \\"
echo "    --resource '{\"TableWithColumns\": {\"DatabaseName\": \"${DATABASE}\", \"Name\": \"${TABLE}\", \"ColumnNames\": [\"device_id\", \"temperature\", \"status\"]}}' \\"
echo "    --permissions '[\"SELECT\"]' \\"
echo "    --region ${REGION}"
echo ""

# ============================================================
# Step 6: Create row filter example
# ============================================================
echo "━━━ Step 6: Row filter (Data Cells Filter) example ━━━"
echo "  To create a row filter (status = 'normal' only):"
echo ""
echo "  aws lakeformation create-data-cells-filter \\"
echo "    --table-data '{\"TableCatalogId\": \"${ACCOUNT_ID}\", \"DatabaseName\": \"${DATABASE}\", \"TableName\": \"${TABLE}\", \"Name\": \"normal_only\", \"RowFilter\": {\"FilterExpression\": \"status = '\\''normal'\\''\"}, \"ColumnNames\": [\"device_id\", \"timestamp\", \"temperature\", \"status\"]}' \\"
echo "    --region ${REGION}"
echo ""

# ============================================================
# Summary
# ============================================================
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Lake Formation governance setup complete"
echo ""
echo "Verify with Athena:"
echo "  SELECT * FROM ${DATABASE}.${TABLE} LIMIT 10;"
echo ""
echo "Verify column restriction (as restricted role):"
echo "  SELECT humidity FROM ${DATABASE}.${TABLE};  -- Should fail"
echo ""
echo "Documentation:"
echo "  - Lake Formation: https://docs.aws.amazon.com/lake-formation/"
echo "  - Blog Part 6: Redshift Spectrum + Lake Formation"
echo "═══════════════════════════════════════════════════════════════"
