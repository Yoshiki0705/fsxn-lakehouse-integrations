#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Cross-Region FlexCache + SnapMirror Validation — Deploy Script
#
# Creates a 2nd FSx for ONTAP cluster in Region B, establishes VPC Peering,
# Cluster/SVM Peering, and prepares for FlexCache + SnapMirror cross-region tests.
#
# Cost: ~$180/month for FSx for ONTAP (SINGLE_AZ_1, 128 MBps, 1TB)
#       + data transfer between regions
# Time: ~50 minutes (FSx creation ~45min + Peering ~5min)
#
# Usage:
#   cp cross-region-params.env.example cross-region-params.env
#   vim cross-region-params.env
#   ./cross-region-deploy.sh deploy
#   ./cross-region-deploy.sh test
#   ./cross-region-deploy.sh teardown
#
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/cross-region-params.env"
PHASE="${1:-help}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

[[ -f "$PARAMS_FILE" ]] && source "$PARAMS_FILE" || fail "cross-region-params.env not found"

: "${REGION_A:?Set REGION_A}"
: "${REGION_B:?Set REGION_B}"
: "${FS_ID_A:?Set FS_ID_A (existing cluster in Region A)}"
: "${VPC_ID_A:?Set VPC_ID_A}"
: "${VPC_CIDR_A:?Set VPC_CIDR_A}"
: "${SECRET_ARN_A:?Set SECRET_ARN_A}"
: "${SVM_NAME_A:?Set SVM_NAME_A}"

# Region B defaults (will be created)
VPC_CIDR_B="${VPC_CIDR_B:-10.1.0.0/16}"
SUBNET_CIDR_B="${SUBNET_CIDR_B:-10.1.0.0/24}"
FSX_PASSWORD_B="${FSX_PASSWORD_B:?Set FSX_PASSWORD_B in cross-region-params.env}"
SVM_NAME_B="${SVM_NAME_B:-svm-region-b}"

# ============================================================================
deploy() {
  header "DEPLOY: Cross-Region Environment (Region B: ${REGION_B})"

  # --- 1. Create VPC in Region B ---
  header "Step 1: Create VPC in Region B"
  local vpc_id_b
  vpc_id_b=$(aws ec2 create-vpc --cidr-block "$VPC_CIDR_B" \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=fsxn-cross-region-b}]" \
    --query 'Vpc.VpcId' --output text --region "$REGION_B")
  info "VPC B: $vpc_id_b"

  # Enable DNS
  aws ec2 modify-vpc-attribute --vpc-id "$vpc_id_b" --enable-dns-support '{"Value":true}' --region "$REGION_B"
  aws ec2 modify-vpc-attribute --vpc-id "$vpc_id_b" --enable-dns-hostnames '{"Value":true}' --region "$REGION_B"

  # Create subnet
  local subnet_id_b
  subnet_id_b=$(aws ec2 create-subnet --vpc-id "$vpc_id_b" --cidr-block "$SUBNET_CIDR_B" \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=fsxn-cross-region-b-subnet}]" \
    --query 'Subnet.SubnetId' --output text --region "$REGION_B")
  info "Subnet B: $subnet_id_b"

  # Security Group
  local sg_id_b
  sg_id_b=$(aws ec2 create-security-group --vpc-id "$vpc_id_b" \
    --group-name fsxn-cross-region-b-sg --description "FSx for ONTAP cross-region" \
    --query 'GroupId' --output text --region "$REGION_B")
  aws ec2 authorize-security-group-ingress --group-id "$sg_id_b" \
    --protocol -1 --cidr "$VPC_CIDR_A" --region "$REGION_B" > /dev/null
  aws ec2 authorize-security-group-ingress --group-id "$sg_id_b" \
    --protocol -1 --cidr "$VPC_CIDR_B" --region "$REGION_B" > /dev/null
  info "Security Group B: $sg_id_b"

  # --- 2. VPC Peering ---
  header "Step 2: VPC Peering (Region A ↔ Region B)"
  local peering_id
  peering_id=$(aws ec2 create-vpc-peering-connection \
    --vpc-id "$VPC_ID_A" --peer-vpc-id "$vpc_id_b" --peer-region "$REGION_B" \
    --query 'VpcPeeringConnection.VpcPeeringConnectionId' --output text --region "$REGION_A")
  info "Peering: $peering_id"

  sleep 5
  aws ec2 accept-vpc-peering-connection --vpc-peering-connection-id "$peering_id" --region "$REGION_B" > /dev/null
  pass "VPC Peering active"

  # Add routes
  local rt_a
  rt_a=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID_A" "Name=association.main,Values=true" \
    --query 'RouteTables[0].RouteTableId' --output text --region "$REGION_A")
  aws ec2 create-route --route-table-id "$rt_a" --destination-cidr-block "$VPC_CIDR_B" \
    --vpc-peering-connection-id "$peering_id" --region "$REGION_A" > /dev/null 2>&1 || true

  local rt_b
  rt_b=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc_id_b" "Name=association.main,Values=true" \
    --query 'RouteTables[0].RouteTableId' --output text --region "$REGION_B")
  aws ec2 create-route --route-table-id "$rt_b" --destination-cidr-block "$VPC_CIDR_A" \
    --vpc-peering-connection-id "$peering_id" --region "$REGION_B" > /dev/null 2>&1 || true
  pass "Routes configured"

  # --- 3. Create FSx for ONTAP in Region B ---
  header "Step 3: Create FSx for ONTAP in Region B (~45 minutes)"
  local fs_id_b
  fs_id_b=$(aws fsx create-file-system --file-system-type ONTAP \
    --storage-capacity 1024 \
    --subnet-ids "$subnet_id_b" \
    --security-group-ids "$sg_id_b" \
    --ontap-configuration "{
      \"DeploymentType\": \"SINGLE_AZ_1\",
      \"ThroughputCapacity\": 128,
      \"FsxAdminPassword\": \"${FSX_PASSWORD_B}\",
      \"PreferredSubnetId\": \"${subnet_id_b}\"
    }" \
    --tags "Key=Name,Value=fsxn-cross-region-b" "Key=Purpose,Value=cross-region-validation" \
    --query 'FileSystem.FileSystemId' --output text --region "$REGION_B")
  info "FSx B: $fs_id_b (CREATING — ~45 min)"

  # Save state
  cat > "${SCRIPT_DIR}/.cross-region-state.env" << STATE
VPC_ID_B=$vpc_id_b
SUBNET_ID_B=$subnet_id_b
SG_ID_B=$sg_id_b
PEERING_ID=$peering_id
FS_ID_B=$fs_id_b
RT_A=$rt_a
RT_B=$rt_b
STATE
  info "State saved to .cross-region-state.env"

  # Wait for FSx
  info "Waiting for FSx for ONTAP to become AVAILABLE..."
  info "This takes approximately 45 minutes. You can check status with:"
  info "  aws fsx describe-file-systems --file-system-ids $fs_id_b --query 'FileSystems[0].Lifecycle' --region $REGION_B"
  
  while true; do
    local status
    status=$(aws fsx describe-file-systems --file-system-ids "$fs_id_b" \
      --query 'FileSystems[0].Lifecycle' --output text --region "$REGION_B" 2>/dev/null)
    echo -ne "\r  Status: $status  "
    [[ "$status" == "AVAILABLE" ]] && break
    [[ "$status" == "FAILED" ]] && fail "FSx creation failed"
    sleep 60
  done
  echo ""
  pass "FSx for ONTAP B is AVAILABLE"

  # --- 4. Create SVM in Region B ---
  header "Step 4: Create SVM in Region B"
  aws fsx create-storage-virtual-machine \
    --file-system-id "$fs_id_b" \
    --name "$SVM_NAME_B" \
    --region "$REGION_B" > /dev/null
  sleep 30
  pass "SVM $SVM_NAME_B created"

  # --- 5. Store credentials for Region B ---
  header "Step 5: Store credentials"
  aws secretsmanager create-secret \
    --name "fsxn-cross-region-b-admin" \
    --secret-string "{\"username\":\"fsxadmin\",\"password\":\"${FSX_PASSWORD_B}\"}" \
    --region "$REGION_B" > /dev/null 2>&1 || \
  aws secretsmanager update-secret \
    --secret-id "fsxn-cross-region-b-admin" \
    --secret-string "{\"username\":\"fsxadmin\",\"password\":\"${FSX_PASSWORD_B}\"}" \
    --region "$REGION_B" > /dev/null
  pass "Credentials stored in Secrets Manager (Region B)"

  echo ""
  header "DEPLOY COMPLETE"
  info "Region A: $FS_ID_A in $REGION_A"
  info "Region B: $fs_id_b in $REGION_B"
  info "VPC Peering: $peering_id"
  info ""
  info "Next: Run './cross-region-deploy.sh test' to execute validation"
}

# ============================================================================
test_cross_region() {
  header "TEST: Cross-Region FlexCache + SnapMirror"
  
  [[ -f "${SCRIPT_DIR}/.cross-region-state.env" ]] || fail ".cross-region-state.env not found. Run 'deploy' first."
  source "${SCRIPT_DIR}/.cross-region-state.env"

  local mgmt_a mgmt_b
  mgmt_a=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")
  mgmt_b=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_B" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_B")
  info "Mgmt A: $mgmt_a | Mgmt B: $mgmt_b"

  # NOTE: ONTAP REST API calls require network connectivity between the caller and the management IPs.
  # For cross-region, use SSM on an EC2 in each VPC, or ensure VPN/DX connectivity.
  info "Cross-region ONTAP operations require EC2 instances in each VPC."
  info "Use the tc09-deploy-validate-teardown.sh pattern with SSM for each region."
  info ""
  info "Manual steps (or adapt tc09 script):"
  info "  1. Cluster Peering: Region A IC LIFs ↔ Region B IC LIFs"
  info "  2. SVM Peering: ${SVM_NAME_A} ↔ ${SVM_NAME_B}"
  info "  3. FlexCache: Origin in Region A → Cache in Region B"
  info "  4. SnapMirror: Source in Region A → Dest in Region B → break → S3 AP re-attach"
  warn "Full automation of cross-region ONTAP REST API calls requires EC2 in Region B VPC."
}

# ============================================================================
teardown() {
  header "TEARDOWN: Cross-Region Resources"
  
  [[ -f "${SCRIPT_DIR}/.cross-region-state.env" ]] || fail ".cross-region-state.env not found"
  source "${SCRIPT_DIR}/.cross-region-state.env"

  # 1. Delete FSx for ONTAP B (must delete SVM first)
  info "Deleting SVM in Region B..."
  local svm_id
  svm_id=$(aws fsx describe-storage-virtual-machines \
    --filters Name=file-system-id,Values="$FS_ID_B" \
    --query 'StorageVirtualMachines[?Name!=`fsx`].StorageVirtualMachineId' \
    --output text --region "$REGION_B" 2>/dev/null)
  if [[ -n "$svm_id" && "$svm_id" != "None" ]]; then
    aws fsx delete-storage-virtual-machine --storage-virtual-machine-id "$svm_id" --region "$REGION_B" > /dev/null 2>&1
    info "Waiting for SVM deletion..."
    sleep 60
  fi

  info "Deleting FSx for ONTAP B ($FS_ID_B)..."
  aws fsx delete-file-system --file-system-id "$FS_ID_B" \
    --region "$REGION_B" > /dev/null 2>&1 || true

  # 2. Wait for FSx deletion (can take 15-30 min)
  info "Waiting for FSx deletion (this takes 15-30 min)..."
  while true; do
    local status
    status=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_B" \
      --query 'FileSystems[0].Lifecycle' --output text --region "$REGION_B" 2>/dev/null || echo "DELETED")
    [[ "$status" == "DELETED" || "$status" == "None" ]] && break
    echo -ne "\r  Status: $status  "
    sleep 30
  done
  echo ""

  # 3. Delete VPC Peering
  info "Deleting VPC Peering..."
  aws ec2 delete-vpc-peering-connection --vpc-peering-connection-id "$PEERING_ID" --region "$REGION_A" > /dev/null 2>&1 || true

  # 4. Delete routes
  aws ec2 delete-route --route-table-id "$RT_A" --destination-cidr-block "$VPC_CIDR_B" --region "$REGION_A" > /dev/null 2>&1 || true
  aws ec2 delete-route --route-table-id "$RT_B" --destination-cidr-block "$VPC_CIDR_A" --region "$REGION_B" > /dev/null 2>&1 || true

  # 5. Delete Security Group, Subnet, VPC in Region B
  info "Deleting VPC B resources..."
  aws ec2 delete-security-group --group-id "$SG_ID_B" --region "$REGION_B" > /dev/null 2>&1 || true
  aws ec2 delete-subnet --subnet-id "$SUBNET_ID_B" --region "$REGION_B" > /dev/null 2>&1 || true
  sleep 5
  aws ec2 delete-vpc --vpc-id "$VPC_ID_B" --region "$REGION_B" > /dev/null 2>&1 || true

  # 6. Delete Secrets Manager secret
  aws secretsmanager delete-secret --secret-id "fsxn-cross-region-b-admin" \
    --force-delete-without-recovery --region "$REGION_B" > /dev/null 2>&1 || true

  rm -f "${SCRIPT_DIR}/.cross-region-state.env"
  pass "Teardown complete"
}

# ============================================================================
case "$PHASE" in
  deploy) deploy ;;
  test) test_cross_region ;;
  teardown) teardown ;;
  *)
    echo "Usage: $0 [deploy|test|teardown]"
    echo ""
    echo "  deploy   — Create VPC, Peering, FSx for ONTAP in Region B (~50 min)"
    echo "  test     — Run cross-region FlexCache + SnapMirror tests"
    echo "  teardown — Delete all Region B resources"
    ;;
esac
