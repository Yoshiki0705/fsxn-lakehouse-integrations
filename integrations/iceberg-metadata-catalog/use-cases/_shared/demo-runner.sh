#!/bin/bash
# =============================================================================
# Shared Demo Runner — Industry Use Case Framework
# =============================================================================
# Runs a metadata catalog demo for a specific industry.
# Delegates to the main run-demo.sh with industry-specific configuration.
#
# Usage:
#   ./demo-runner.sh --industry <name> --ap-alias <alias> [--count 50]
#
# This script:
#   1. Generates industry-specific sample data
#   2. Runs the metadata scan
#   3. Runs AI enrichment
#   4. Executes industry-specific Athena queries
#   5. Shows results
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASES_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$USE_CASES_DIR")"
INDUSTRY=""
AP_ALIAS=""
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
COUNT=50

while [[ $# -gt 0 ]]; do
  case $1 in
    --industry) INDUSTRY="$2"; shift 2 ;;
    --ap-alias) AP_ALIAS="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --count) COUNT="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

if [[ -z "$INDUSTRY" || -z "$AP_ALIAS" ]]; then
  echo "Usage: $0 --industry <name> --ap-alias <alias> [--count 50]"
  echo ""
  echo "Available industries:"
  ls -d "$USE_CASES_DIR"/*/  | grep -v _shared | xargs -I{} basename {} | sort
  exit 1
fi

INDUSTRY_DIR="$USE_CASES_DIR/$INDUSTRY"
if [[ ! -d "$INDUSTRY_DIR" ]]; then
  echo "Error: Industry '$INDUSTRY' not found in $USE_CASES_DIR"
  exit 1
fi

echo "═══════════════════════════════════════════════════════════"
echo " Iceberg Metadata Catalog — $INDUSTRY Demo"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Industry:  $INDUSTRY"
echo "  AP Alias:  $AP_ALIAS"
echo "  Region:    $REGION"
echo "  Count:     $COUNT"
echo ""

# Step 1: Generate sample data
echo "── Step 1: Generate sample data ──"
if [[ -f "$INDUSTRY_DIR/sample-data/generate.py" ]]; then
  python3 "$INDUSTRY_DIR/sample-data/generate.py" --count "$COUNT"
else
  python3 "$PROJECT_DIR/demo/sample-data/generate-sample-data.py" \
    --industry "$INDUSTRY" --count "$COUNT"
fi
echo ""

# Step 2: Run main demo with industry context
echo "── Step 2: Run metadata scan + AI enrichment ──"
"$PROJECT_DIR/demo/scripts/run-demo.sh" \
  --ap-alias "$AP_ALIAS" \
  --region "$REGION" \
  --skip-deploy
echo ""

# Step 3: Run industry-specific queries
echo "── Step 3: Industry-specific queries ──"
if [[ -f "$INDUSTRY_DIR/queries/named-queries.sql" ]]; then
  echo "  Available queries in $INDUSTRY/queries/named-queries.sql:"
  grep "^-- Name:" "$INDUSTRY_DIR/queries/named-queries.sql" | sed 's/-- Name: /    • /'
  echo ""
  echo "  Run in Athena console or:"
  echo "    aws athena start-query-execution --query-string \"\$(cat $INDUSTRY_DIR/queries/named-queries.sql | head -20)\""
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Demo Complete"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "    • Review queries: $INDUSTRY_DIR/queries/named-queries.sql"
echo "    • Schema details: $INDUSTRY_DIR/schema-extension.yaml"
echo "    • Talking points: $INDUSTRY_DIR/demo/talking-points.md"
echo "    • Full docs: $PROJECT_DIR/docs/industry-use-cases.md"
