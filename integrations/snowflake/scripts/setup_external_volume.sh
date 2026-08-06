#!/bin/bash
# =============================================================================
# Snowflake External Volume setup - guided three-phase deploy
# =============================================================================
# An External Volume is where Snowflake writes Managed Iceberg Tables. Setting one
# up is awkward because the IAM trust policy and the Snowflake object each need a
# value the other produces:
#
#   Phase 1  create the IAM role with a placeholder trust        (this script)
#   Phase 2  CREATE EXTERNAL VOLUME in Snowflake using RoleArn   (you, in a worksheet)
#   Phase 3  re-deploy the role trusting Snowflake's principal   (this script)
#
# The script cannot run Phase 2 for you - it has no Snowflake credentials, and
# putting them in this repository would be worse than the manual step. It prints
# the exact SQL, waits, and then takes the two values DESC EXTERNAL VOLUME returns.
#
# Usage:
#   ./scripts/setup_external_volume.sh --bucket <name> [OPTIONS]        # phase 1
#   ./scripts/setup_external_volume.sh --phase3 \                        # phase 3
#       --snowflake-arn <arn> --external-id <id>
#
# Required for phase 1:
#   --bucket <name>          S3 bucket for the Iceberg tables. Globally unique.
#
# Required for phase 3:
#   --snowflake-arn <arn>    STORAGE_AWS_IAM_USER_ARN from DESC EXTERNAL VOLUME
#   --external-id <id>       STORAGE_AWS_EXTERNAL_ID from DESC EXTERNAL VOLUME
#
# Optional:
#   --env-name <name>        Resource name prefix        (default: fsxn-lakehouse)
#   --prefix <prefix>        Prefix inside the bucket    (default: iceberg/)
#   --existing-bucket        Do not create the bucket; it already exists
#   --stack-name <name>      CloudFormation stack name
#                            (default: <env-name>-sf-external-volume)
#   --region <region>        AWS region  (default: AWS CLI configured region)
#   --profile <profile>      AWS CLI profile
#   --dry-run                Print what would happen, change nothing
#   --help                   Show this message
#
# Example:
#   ./scripts/setup_external_volume.sh --bucket acme-lakehouse-iceberg-apne1
#   # ... paste the printed SQL into Snowflake, run DESC EXTERNAL VOLUME ...
#   ./scripts/setup_external_volume.sh --phase3 \
#     --snowflake-arn "arn:aws:iam::123456789012:user/abc1-b-self1234" \
#     --external-id "ACCOUNT_SFCRole=2_base64string="
#
# Prerequisites:
#   - AWS CLI v2, permission to create IAM roles and S3 buckets
#   - A Snowflake account where you can run CREATE EXTERNAL VOLUME (ACCOUNTADMIN,
#     or a role granted CREATE EXTERNAL VOLUME)
#
# Verified end to end on 2026-08-06. See docs/en/snowflake-iceberg-setup.md
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEGRATION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE="${INTEGRATION_DIR}/template-external-volume.yaml"
STATE_FILE="${INTEGRATION_DIR}/.external-volume-state"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; BOLD=$'\033[1m'; NC=$'\033[0m'

info()  { printf '%s\n' "${BLUE}==>${NC} $*"; }
ok()    { printf '%s\n' "${GREEN}OK${NC}  $*"; }
warn()  { printf '%s\n' "${YELLOW}!!${NC}  $*"; }
error() { printf '%s\n' "${RED}ERROR${NC} $*" >&2; exit 1; }

ENV_NAME="fsxn-lakehouse"
BUCKET=""
PREFIX="iceberg/"
CREATE_BUCKET="true"
STACK_NAME=""
REGION=""
PROFILE=""
PHASE3="false"
SNOWFLAKE_ARN=""
EXTERNAL_ID=""
DRY_RUN="false"

show_help() { sed -n '2,52p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bucket)          BUCKET="$2"; shift 2 ;;
        --env-name)        ENV_NAME="$2"; shift 2 ;;
        --prefix)          PREFIX="$2"; shift 2 ;;
        --existing-bucket) CREATE_BUCKET="false"; shift ;;
        --stack-name)      STACK_NAME="$2"; shift 2 ;;
        --region)          REGION="$2"; shift 2 ;;
        --profile)         PROFILE="$2"; shift 2 ;;
        --phase3)          PHASE3="true"; shift ;;
        --snowflake-arn)   SNOWFLAKE_ARN="$2"; shift 2 ;;
        --external-id)     EXTERNAL_ID="$2"; shift 2 ;;
        --dry-run)         DRY_RUN="true"; shift ;;
        --help|-h)         show_help ;;
        *) error "Unknown option: $1. Use --help." ;;
    esac
done

command -v aws >/dev/null 2>&1 || error "AWS CLI not found. Install AWS CLI v2."

AWS_ARGS=()
[[ -n "${REGION}"  ]] && AWS_ARGS+=(--region "${REGION}")
[[ -n "${PROFILE}" ]] && AWS_ARGS+=(--profile "${PROFILE}")

# Reload settings saved by phase 1 so phase 3 needs only the two Snowflake values.
if [[ -f "${STATE_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${STATE_FILE}"
    [[ -z "${BUCKET}" ]] && BUCKET="${SAVED_BUCKET:-}"
    [[ "${ENV_NAME}" == "fsxn-lakehouse" && -n "${SAVED_ENV_NAME:-}" ]] && ENV_NAME="${SAVED_ENV_NAME}"
    [[ "${PREFIX}" == "iceberg/" && -n "${SAVED_PREFIX:-}" ]] && PREFIX="${SAVED_PREFIX}"
    [[ -z "${STACK_NAME}" && -n "${SAVED_STACK_NAME:-}" ]] && STACK_NAME="${SAVED_STACK_NAME}"
fi

[[ -z "${STACK_NAME}" ]] && STACK_NAME="${ENV_NAME}-sf-external-volume"

deploy() {
    local phase_desc="$1"; shift
    local params=("$@")

    if [[ "${DRY_RUN}" == "true" ]]; then
        warn "dry run - would deploy stack ${STACK_NAME} (${phase_desc})"
        printf '    %s\n' "${params[@]}"
        return 0
    fi

    info "Deploying ${STACK_NAME} (${phase_desc})"
    aws cloudformation deploy \
        --template-file "${TEMPLATE}" \
        --stack-name "${STACK_NAME}" \
        --parameter-overrides "${params[@]}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --no-fail-on-empty-changeset \
        "${AWS_ARGS[@]}" >/dev/null
    ok "Stack deployed"
}

stack_output() {
    aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" \
        --output text "${AWS_ARGS[@]}"
}

# ---------------------------------------------------------------------------
# Phase 3
# ---------------------------------------------------------------------------
if [[ "${PHASE3}" == "true" ]]; then
    [[ -n "${SNOWFLAKE_ARN}" ]] || error "--phase3 needs --snowflake-arn"
    [[ -n "${EXTERNAL_ID}"   ]] || error "--phase3 needs --external-id"
    [[ -n "${BUCKET}"        ]] || error "No bucket known. Run phase 1 first, or pass --bucket."

    # A common mistake is pasting the role ARN instead of the IAM user ARN.
    if [[ "${SNOWFLAKE_ARN}" != *":user/"* ]]; then
        error "--snowflake-arn should be an IAM *user* ARN (contains :user/).
  You passed: ${SNOWFLAKE_ARN}
  Use STORAGE_AWS_IAM_USER_ARN from DESC EXTERNAL VOLUME, not STORAGE_AWS_ROLE_ARN."
    fi
    if [[ "${EXTERNAL_ID}" != *"SFCRole="* ]]; then
        warn "--external-id does not contain SFCRole=. Double-check you copied
      STORAGE_AWS_EXTERNAL_ID and not something else."
    fi

    deploy "phase 3 - trust Snowflake" \
        "EnvironmentName=${ENV_NAME}" \
        "BucketName=${BUCKET}" \
        "BucketPrefix=${PREFIX}" \
        "CreateBucket=${CREATE_BUCKET}" \
        "SnowflakeIamUserArn=${SNOWFLAKE_ARN}" \
        "SnowflakeExternalId=${EXTERNAL_ID}"

    if [[ "${DRY_RUN}" == "true" ]]; then exit 0; fi

    echo
    ok "Trust policy now targets the Snowflake principal."
    printf '%s\n' "${BOLD}Confirm it from Snowflake:${NC}"
    echo
    printf '  %s\n' "$(stack_output VerifySql)"
    echo
    cat <<'EOF'
  A healthy result has "success": true with writeResult, readResult, listResult
  and deleteResult all PASSED. If it fails:

    "Access Denied"        the external id or principal does not match. Re-run
                           DESC EXTERNAL VOLUME and check for a truncated paste -
                           the external id ends with '=' and is easy to clip.
    "not authorized"       IAM changes can take a few seconds to take effect.
                           Wait, then retry.
    listResult FAILED      the prefix in STORAGE_BASE_URL does not match the
                           prefix the IAM policy allows.
EOF
    echo
    printf '%s\n' "Then create a table and load it. See docs/en/snowflake-iceberg-setup.md"
    exit 0
fi

# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------
[[ -n "${BUCKET}" ]] || error "--bucket is required for phase 1.
  Bucket names are globally unique, so pick something specific, for example
  <org>-lakehouse-iceberg-<region-short>."

if [[ ! "${PREFIX}" =~ /$ ]]; then
    warn "--prefix '${PREFIX}' has no trailing slash. Adding one."
    PREFIX="${PREFIX}/"
fi

if [[ "${CREATE_BUCKET}" == "true" ]] && [[ "${DRY_RUN}" != "true" ]]; then
    if aws s3api head-bucket --bucket "${BUCKET}" "${AWS_ARGS[@]}" 2>/dev/null; then
        error "Bucket ${BUCKET} already exists.
  Pass --existing-bucket to use it instead of creating it."
    fi
fi

deploy "phase 1 - placeholder trust" \
    "EnvironmentName=${ENV_NAME}" \
    "BucketName=${BUCKET}" \
    "BucketPrefix=${PREFIX}" \
    "CreateBucket=${CREATE_BUCKET}" \
    "SnowflakeIamUserArn=" \
    "SnowflakeExternalId="

if [[ "${DRY_RUN}" == "true" ]]; then exit 0; fi

cat > "${STATE_FILE}" <<EOF
# Written by setup_external_volume.sh phase 1 so phase 3 needs fewer arguments.
# Contains no secrets. Safe to delete.
SAVED_ENV_NAME="${ENV_NAME}"
SAVED_BUCKET="${BUCKET}"
SAVED_PREFIX="${PREFIX}"
SAVED_STACK_NAME="${STACK_NAME}"
EOF

ROLE_ARN="$(stack_output RoleArn)"
BASE_URL="$(stack_output StorageBaseUrl)"
CREATE_SQL="$(stack_output CreateExternalVolumeSql)"

echo
ok "IAM role created with a placeholder trust. Snowflake cannot assume it yet - that is expected."
echo
printf '%s\n' "  Role ARN : ${ROLE_ARN}"
printf '%s\n' "  Base URL : ${BASE_URL}"
echo
printf '%s\n' "${BOLD}Phase 2 - run this in a Snowflake worksheet:${NC}"
echo
printf '%s\n' "${CREATE_SQL}"
echo
printf '%s\n' "DESC EXTERNAL VOLUME ${ENV_NAME}_iceberg_vol;"
echo
cat <<'EOF'
Expand STORAGE_LOCATION_1 in the result and copy two values out of the JSON:

  STORAGE_AWS_IAM_USER_ARN   an IAM *user* ARN in a Snowflake-owned account
  STORAGE_AWS_EXTERNAL_ID    looks like ACCOUNT_SFCRole=2_base64string=

Both are specific to this external volume. Recreating the external volume issues
a new external id, so redo phase 3 if you ever recreate it.
EOF
echo
printf '%s\n' "${BOLD}Phase 3 - come back and run:${NC}"
echo
printf '%s\n' "  ${0} --phase3 \\"
printf '%s\n' "    --snowflake-arn \"<STORAGE_AWS_IAM_USER_ARN>\" \\"
printf '%s\n' "    --external-id \"<STORAGE_AWS_EXTERNAL_ID>\""
echo
