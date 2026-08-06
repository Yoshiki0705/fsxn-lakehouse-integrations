#!/bin/bash
# =============================================================================
# Deploy Customer-managed VPC Network for Databricks × FSx for ONTAP
# =============================================================================
# Creates the network infrastructure needed for Databricks to access FSx for
# ONTAP via NFS in a Customer-managed VPC configuration.
#
# Usage:
#   ./deploy-customer-vpc.sh [deploy|delete|status]
#
# Prerequisites:
#   - AWS CLI v2 configured with appropriate permissions
#   - FSx for ONTAP already deployed in the target VPC
#
# After deployment:
#   1. Register Network Configuration in Databricks Account Console
#   2. Create a new Workspace using the Network Configuration
#   3. Create a Dedicated (Single user) cluster for NFS testing
#
# Cost: ~$45/month (NAT Gateway) — delete when not in use
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
STACK_NAME="databricks-fsxn-customer-vpc"
ACTION="${1:-status}"

# Default parameters (override via environment variables)
VPC_ID="${DATABRICKS_VPC_ID:-vpc-0EXAMPLE7777aaaaa}"
PUBLIC_SUBNET="${DATABRICKS_PUBLIC_SUBNET:-subnet-0EXAMPLEccccdddd}"
SUBNET1_CIDR="${DATABRICKS_SUBNET1_CIDR:-10.0.32.0/19}"
SUBNET2_CIDR="${DATABRICKS_SUBNET2_CIDR:-10.0.64.0/19}"
AZ1="${DATABRICKS_AZ1:-ap-northeast-1a}"
AZ2="${DATABRICKS_AZ2:-ap-northeast-1c}"
FSX_NFS_IP="${FSX_NFS_IP:-198.51.100.30}"
FSX_MGMT_IP="${FSX_MGMT_IP:-198.51.100.31}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }

case "${ACTION}" in
  deploy)
    log "Deploying Customer-managed VPC network stack..."
    log "  VPC: ${VPC_ID}"
    log "  Subnets: ${SUBNET1_CIDR}, ${SUBNET2_CIDR}"
    log "  Region: ${REGION}"
    echo ""

    aws cloudformation deploy \
      --template-file "${SCRIPT_DIR}/customer-vpc-network.yaml" \
      --stack-name "${STACK_NAME}" \
      --region "${REGION}" \
      --parameter-overrides \
        VpcId="${VPC_ID}" \
        PublicSubnetId="${PUBLIC_SUBNET}" \
        DatabricksSubnet1Cidr="${SUBNET1_CIDR}" \
        DatabricksSubnet2Cidr="${SUBNET2_CIDR}" \
        AvailabilityZone1="${AZ1}" \
        AvailabilityZone2="${AZ2}" \
        FsxNfsIp="${FSX_NFS_IP}" \
        FsxMgmtIp="${FSX_MGMT_IP}" \
      --tags \
        Project=fsxn-lakehouse-integrations \
        Integration=databricks \
        Purpose=customer-vpc-verification

    echo ""
    log "Stack deployed successfully!"
    log ""
    log "=== Outputs ==="
    aws cloudformation describe-stacks \
      --stack-name "${STACK_NAME}" \
      --region "${REGION}" \
      --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
      --output table

    echo ""
    info "Next steps:"
    info "  1. Go to Databricks Account Console > Cloud Resources > Networks"
    info "  2. Create Network Configuration with the above Subnet IDs and Security Group"
    info "  3. Create a new Workspace using this Network Configuration"
    info "  4. Create a Dedicated (Single user) cluster for NFS testing"
    echo ""
    warn "Cost: NAT Gateway runs ~\$45/month. Delete stack when not in use:"
    warn "  ./deploy-customer-vpc.sh delete"
    ;;

  delete)
    log "Deleting Customer-managed VPC network stack..."
    warn "This will remove: NAT Gateway, EIP, Subnets, Route Table, Security Group"
    warn "Databricks workspace using these resources must be deleted first!"
    echo ""
    read -p "Are you sure? (y/N): " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
      aws cloudformation delete-stack \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}"
      log "Delete initiated. Waiting for completion..."
      aws cloudformation wait stack-delete-complete \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" 2>/dev/null || true
      log "Stack deleted."
    else
      log "Cancelled."
    fi
    ;;

  status)
    log "Stack status: ${STACK_NAME}"
    echo ""
    STATUS=$(aws cloudformation describe-stacks \
      --stack-name "${STACK_NAME}" \
      --region "${REGION}" \
      --query 'Stacks[0].StackStatus' \
      --output text 2>/dev/null || echo "DOES_NOT_EXIST")

    if [ "${STATUS}" = "DOES_NOT_EXIST" ]; then
      info "Stack does not exist. Deploy with:"
      info "  ./deploy-customer-vpc.sh deploy"
    else
      log "Status: ${STATUS}"
      echo ""
      aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table 2>/dev/null || true
    fi
    ;;

  *)
    echo "Usage: $0 [deploy|delete|status]"
    echo ""
    echo "Actions:"
    echo "  deploy  - Create Customer-managed VPC network infrastructure"
    echo "  delete  - Remove all resources (saves ~\$45/month NAT Gateway cost)"
    echo "  status  - Show current stack status and outputs"
    echo ""
    echo "Environment variables:"
    echo "  DATABRICKS_VPC_ID        - Target VPC (default: ${VPC_ID})"
    echo "  DATABRICKS_PUBLIC_SUBNET - Public subnet for NAT GW (default: ${PUBLIC_SUBNET})"
    echo "  FSX_NFS_IP               - FSx NFS LIF IP (default: ${FSX_NFS_IP})"
    echo "  FSX_MGMT_IP              - FSx management IP (default: ${FSX_MGMT_IP})"
    ;;
esac
