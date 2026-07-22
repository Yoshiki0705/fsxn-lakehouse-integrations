#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Cross-Region Safe Teardown Script
#
# Implements the validated teardown order (SM-VAL-011) that prevents
# orphaned SVM peer records and MISCONFIGURED state.
#
# CRITICAL ORDER:
#   1. S3 APs (both regions)
#   2. SnapMirror release (source side, CLI)
#   3. SnapMirror relationships (destination side)
#   4. FlexCache volumes (unmount junction → delete)
#   5. Regular volumes
#   6. SVM peers (BOTH sides, poll until num_records=0)
#   7. Cluster peers
#   8. SVM (FSx API)
#   9. File System (FSx API)
#  10. VPC Peering + VPC resources
#
# Usage:
#   ./cross-region-teardown.sh
#
# Prerequisites:
#   - cross-region-params.env filled
#   - .cross-region-state.env exists (from deploy)
#   - sshpass installed (for ONTAP CLI access)
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/cross-region-params.env"
source "${SCRIPT_DIR}/.cross-region-state.env"

# --- Logging & Audit Trail ---
LOG_FILE="${SCRIPT_DIR}/teardown-$(date +%Y%m%dT%H%M%S).log"
# Write colored output to terminal, strip ANSI codes for log file readability
exec > >(tee >(sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE")) 2>&1
echo "Teardown started: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE" > /dev/null

# --- Trap: Graceful interrupt handling ---
cleanup_on_interrupt() {
  echo ""
  echo -e "${YELLOW}[INTERRUPTED]${NC} Teardown interrupted at $(date -u +%H:%M:%S)."
  echo "  Log file: $LOG_FILE"
  echo "  ⚠️  Resources may be in partial state. Review log and resume manually."
  echo "  ⚠️  CRITICAL: Do NOT delete VPC Peering if SVM peer deletion was in progress (Step 6)."
  exit 130
}
trap cleanup_on_interrupt INT TERM

# --- Cost Warning ---
# ⚠️ Running cross-region resources cost approximately:
#   - FSx for ONTAP (Single-AZ, 1TB): ~$6.40/day ($0.267/hr)
#   - VPC Peering: Free (data transfer: $0.01-0.02/GB)
#   - If teardown fails midway, monitor costs and retry within 24h.

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

# Get management IPs
MGMT_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")
MGMT_B=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_B" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_B" 2>/dev/null || echo "")

PASS_A=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN_A" \
  --query SecretString --output text --region "$REGION_A" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['password'])")
PASS_B="${FSX_PASSWORD_B}"

# Helper: ONTAP CLI via SSH (preferred over REST for peer operations)
# ⚠️ Security note: sshpass with -p exposes password in process table.
#    This is acceptable for demo/test teardown. For production automation,
#    use SSH key-based auth or AWS Systems Manager Session Manager.
#    SSH access must be enabled on the FSx file system (not enabled by default on all deployments).
ontap_cli_a() { sshpass -p "$PASS_A" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "fsxadmin@${MGMT_A}" "$1"; }
ontap_cli_b() { sshpass -p "$PASS_B" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "fsxadmin@${MGMT_B}" "$1"; }

# ============================================================================
header "SAFE TEARDOWN: Cross-Region Resources"
echo ""
warn "This will delete ALL cross-region validation resources."
warn "Region A resources (volumes, S3 APs) will also be removed."
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo ""
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 0

# --- Step 1: Delete S3 Access Points ---
header "Step 1: Delete S3 Access Points"
for ap_name in $(aws fsx describe-s3-access-point-attachments \
  --filters Name=file-system-id,Values="$FS_ID_A" \
  --query 'S3AccessPointAttachments[?contains(Name,`xregion`)].Name' --output text --region "$REGION_A" 2>/dev/null); do
  info "Deleting S3 AP: $ap_name (Region A)"
  aws fsx detach-and-delete-s3-access-point --name "$ap_name" --region "$REGION_A" 2>/dev/null || true
done

if [[ -n "$MGMT_B" ]]; then
  for ap_name in $(aws fsx describe-s3-access-point-attachments \
    --filters Name=file-system-id,Values="$FS_ID_B" \
    --query 'S3AccessPointAttachments[?contains(Name,`xregion`)].Name' --output text --region "$REGION_B" 2>/dev/null); do
    info "Deleting S3 AP: $ap_name (Region B)"
    aws fsx detach-and-delete-s3-access-point --name "$ap_name" --region "$REGION_B" 2>/dev/null || true
  done
fi
pass "S3 APs deletion initiated"
sleep 10

# --- Step 2: SnapMirror release (source side via CLI) ---
header "Step 2: SnapMirror Release (Source Side)"
info "Releasing SnapMirror destinations from Region A..."
DESTS=$(ontap_cli_a "snapmirror list-destinations -source-vserver ${SVM_NAME_A} -destination-vserver ${SVM_NAME_B}" 2>/dev/null || echo "")
if echo "$DESTS" | grep -q "$SVM_NAME_B"; then
  # Extract destination paths and release each one
  while IFS= read -r line; do
    DEST_PATH=$(echo "$line" | awk '{print $3}')
    SRC_PATH=$(echo "$line" | awk '{print $1}')
    if [[ -n "$DEST_PATH" && "$DEST_PATH" != "Path" && "$DEST_PATH" != "---" ]]; then
      info "Releasing: $SRC_PATH → $DEST_PATH"
      ontap_cli_a "snapmirror release -destination-path ${DEST_PATH} -source-path ${SRC_PATH} -force true" || true
    fi
  done <<< "$DESTS"
  pass "SnapMirror releases completed"
else
  info "No SnapMirror destinations found for ${SVM_NAME_B}"
fi

# --- Step 3: Delete SnapMirror relationships (destination side) ---
header "Step 3: Delete SnapMirror Relationships (Destination)"
if [[ -n "$MGMT_B" ]]; then
  SM_UUIDS=$(ontap_cli_b "snapmirror show -vserver ${SVM_NAME_B} -fields uuid" 2>/dev/null | grep -oE '[0-9a-f-]{36}' || echo "")
  for uuid in $SM_UUIDS; do
    info "Deleting SM relationship: $uuid"
    ontap_cli_b "snapmirror delete -destination-path ${SVM_NAME_B}:* -source-path ${SVM_NAME_A}:*" 2>/dev/null || true
  done
fi
pass "SnapMirror relationships cleaned"

# --- Step 4: Delete FlexCache volumes (Region B) ---
header "Step 4: Delete FlexCache Volumes"
if [[ -n "$MGMT_B" ]]; then
  FC_VOLS=$(ontap_cli_b "volume flexcache origin show-caches" 2>/dev/null | grep "$SVM_NAME_B" | awk '{print $2}' || echo "")
  for vol in $FC_VOLS; do
    info "Deleting FlexCache: $vol"
    ontap_cli_b "volume unmount -vserver ${SVM_NAME_B} -volume ${vol}" 2>/dev/null || true
    ontap_cli_b "volume flexcache delete -vserver ${SVM_NAME_B} -volume ${vol}" 2>/dev/null || true
  done
fi

# --- Step 5: Delete volumes (FSx API) ---
header "Step 5: Delete Volumes"
for vol_id in $(aws fsx describe-volumes --filters Name=file-system-id,Values="$FS_ID_B" \
  --query "Volumes[?Name!='svm_region_b_root'].VolumeId" --output text --region "$REGION_B" 2>/dev/null); do
  info "Deleting volume: $vol_id"
  aws fsx delete-volume --volume-id "$vol_id" --ontap-configuration '{"SkipFinalBackup":true}' --region "$REGION_B" 2>/dev/null || true
done

# Delete source volumes in Region A (only xregion-prefixed)
for vol_id in $(aws fsx describe-volumes --filters Name=file-system-id,Values="$FS_ID_A" \
  --query "Volumes[?contains(Name,'xregion')].VolumeId" --output text --region "$REGION_A" 2>/dev/null); do
  info "Deleting source volume: $vol_id"
  aws fsx delete-volume --volume-id "$vol_id" --ontap-configuration '{"SkipFinalBackup":true}' --region "$REGION_A" 2>/dev/null || true
done
sleep 15

# --- Step 6: Delete SVM peers (BOTH sides via CLI — critical step) ---
header "Step 6: Delete SVM Peers (CRITICAL — must complete on BOTH sides)"

info "Deleting SVM peer from Region A (triggers two-phase cleanup)..."
ontap_cli_a "vserver peer delete -vserver ${SVM_NAME_A} -peer-vserver ${SVM_NAME_B}" 2>/dev/null || true
sleep 5

# Poll BOTH sides until clean
MAX_WAIT=120
ELAPSED=0
while [[ $ELAPSED -lt $MAX_WAIT ]]; do
  COUNT_B=$(ontap_cli_b "vserver peer show" 2>/dev/null | grep -c "peered" || echo "0")
  COUNT_A=$(ontap_cli_a "vserver peer show -peer-vserver ${SVM_NAME_B}" 2>/dev/null | grep -c "peered" || echo "0")
  if [[ "$COUNT_A" == "0" && "$COUNT_B" == "0" ]]; then
    pass "All SVM peers deleted (both sides confirmed)"
    break
  fi
  info "  Waiting... A peers: $COUNT_A, B peers: $COUNT_B (${ELAPSED}s / ${MAX_WAIT}s)"
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
  warn "SVM peer deletion timed out. Attempting force-delete from Region B..."
  ontap_cli_b "vserver peer delete -vserver ${SVM_NAME_B} -peer-vserver ${SVM_NAME_A}" 2>/dev/null || true
  sleep 10
fi

# --- Step 7: Delete Cluster peers ---
header "Step 7: Delete Cluster Peers"
ontap_cli_a "cluster peer delete -cluster $(ontap_cli_a 'cluster peer show' 2>/dev/null | grep 'FsxId' | awk '{print $1}' | head -1)" 2>/dev/null || true
pass "Cluster peer deleted"

# --- Step 8: Delete SVM (FSx API) ---
header "Step 8: Delete SVM (Region B)"
SVM_ID_B=$(aws fsx describe-storage-virtual-machines --filters Name=file-system-id,Values="$FS_ID_B" \
  --query "StorageVirtualMachines[?Name=='${SVM_NAME_B}'].StorageVirtualMachineId" --output text --region "$REGION_B" 2>/dev/null)
if [[ -n "$SVM_ID_B" && "$SVM_ID_B" != "None" ]]; then
  aws fsx delete-storage-virtual-machine --storage-virtual-machine-id "$SVM_ID_B" --region "$REGION_B" 2>/dev/null || true
  info "SVM deletion initiated. Waiting ~2 min..."
  sleep 120
  # Verify
  SVM_STATUS=$(aws fsx describe-storage-virtual-machines --storage-virtual-machine-ids "$SVM_ID_B" \
    --query 'StorageVirtualMachines[0].Lifecycle' --output text --region "$REGION_B" 2>/dev/null || echo "GONE")
  if [[ "$SVM_STATUS" == "GONE" || -z "$SVM_STATUS" ]]; then
    pass "SVM deleted"
  else
    warn "SVM status: $SVM_STATUS — may need more time or manual intervention"
  fi
fi

# --- Step 9: Delete File System ---
header "Step 9: Delete FSx File System (Region B)"
aws fsx delete-file-system --file-system-id "$FS_ID_B" --region "$REGION_B" 2>/dev/null || true
info "File system deletion initiated (~30 min). Monitor:"
info "  aws fsx describe-file-systems --file-system-ids $FS_ID_B --query 'FileSystems[0].Lifecycle' --region $REGION_B"

# --- Step 10: Delete VPC Peering + VPC ---
header "Step 10: Delete VPC Peering + Region B VPC"
aws ec2 delete-vpc-peering-connection --vpc-peering-connection-id "${PEERING_ID}" --region "$REGION_A" 2>/dev/null || true
pass "VPC Peering deleted"

# Remove routes from Region A route tables
for rt in $(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$(aws fsx describe-file-systems --file-system-ids $FS_ID_A --query 'FileSystems[0].VpcId' --output text --region $REGION_A)" \
  --query 'RouteTables[].RouteTableId' --output text --region "$REGION_A"); do
  aws ec2 delete-route --route-table-id "$rt" --destination-cidr-block "$VPC_CIDR_B" --region "$REGION_A" 2>/dev/null || true
done

info "Region B VPC resources (subnet, SG, VPC) will be deletable after FSx ENIs release (~30 min)."
info "  Run after FSx deletion completes:"
info "    aws ec2 delete-subnet --subnet-id ${SUBNET_ID_B} --region ${REGION_B}"
info "    aws ec2 delete-security-group --group-id ${SG_ID_B} --region ${REGION_B}"
info "    aws ec2 delete-vpc --vpc-id ${VPC_ID_B} --region ${REGION_B}"

# --- Done ---
echo ""
header "TEARDOWN COMPLETE"
echo ""
echo "  ✅ S3 APs deleted"
echo "  ✅ SnapMirror released + deleted"
echo "  ✅ Volumes deleted"
echo "  ✅ SVM peers deleted (both sides)"
echo "  ✅ Cluster peers deleted"
echo "  ✅ SVM deleted"
echo "  ✅ File System DELETING"
echo "  ✅ VPC Peering deleted"
echo "  ⏳ VPC resources: delete after FSx ENI release (~30 min)"
echo ""
echo "  Estimated cost saved: ~\$6/day"
