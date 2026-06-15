#!/bin/bash
set -euo pipefail

# Manufacturing Data Platform PoC — Deployment Orchestrator
# Deploys all CloudFormation stacks in dependency order.
#
# Usage:
#   ./deploy.sh deploy              — Deploy all stacks (new FSx for ONTAP)
#   ./deploy.sh deploy --use-existing-fsx  — Deploy without FSx (use existing)
#   ./deploy.sh status              — Check stack statuses
#   ./deploy.sh destroy             — Delete all stacks (reverse order)
#   ./deploy.sh volumes             — Create volumes on existing FSx for ONTAP
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - Region set (defaults to ap-northeast-1)
#
# Architecture Reference: ADR-007 (Phase A: AWS-only deployment)

REGION="${AWS_REGION:-ap-northeast-1}"
ENV="${ENVIRONMENT:-poc}"
STACK_PREFIX="manufacturing-${ENV}"

# Existing infrastructure (from iceberg-metadata-catalog / verification project)
EXISTING_VPC_ID="${EXISTING_VPC_ID:-vpc-0ae01826f906191af}"
EXISTING_SUBNET_1="${EXISTING_SUBNET_1:-subnet-0307ebbd55b35c842}"  # ap-northeast-1a private
EXISTING_SUBNET_2="${EXISTING_SUBNET_2:-subnet-0af86ebd3c65481b8}"  # ap-northeast-1c private
EXISTING_FSX_ID="${EXISTING_FSX_ID:-fs-09ffe72a3b2b7dbbd}"
EXISTING_SVM_ID="${EXISTING_SVM_ID:-svm-0e5ef72d9b4470f19}"
USE_EXISTING_INFRA=true  # Default: use existing VPC + FSx

# Stack names (deployment order)
STACKS_CORE=(
  "${STACK_PREFIX}-vpc"
  "${STACK_PREFIX}-s3"
  "${STACK_PREFIX}-msk"
)
STACKS_FSX=(
  "${STACK_PREFIX}-fsxn"
)

# Template mapping (function-based to avoid associative array on macOS bash 3.x)
get_template() {
  case "$1" in
    "${STACK_PREFIX}-vpc") echo "01-vpc-network.yaml" ;;
    "${STACK_PREFIX}-s3") echo "02-s3-buckets.yaml" ;;
    "${STACK_PREFIX}-msk") echo "msk-serverless.yaml" ;;
    "${STACK_PREFIX}-fsxn") echo "03-fsx-ontap.yaml" ;;
    *) echo "" ;;
  esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Helper Functions ---

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

wait_for_stack() {
  local stack_name="$1"
  local operation="$2"  # create or delete
  
  log "Waiting for ${stack_name} (${operation})..."
  
  if [ "$operation" = "create" ]; then
    aws cloudformation wait stack-create-complete \
      --stack-name "$stack_name" \
      --region "$REGION" 2>/dev/null || \
    aws cloudformation wait stack-update-complete \
      --stack-name "$stack_name" \
      --region "$REGION" 2>/dev/null || true
  elif [ "$operation" = "delete" ]; then
    aws cloudformation wait stack-delete-complete \
      --stack-name "$stack_name" \
      --region "$REGION" 2>/dev/null || true
  fi
}

get_stack_output() {
  local stack_name="$1"
  local output_key="$2"
  
  aws cloudformation describe-stacks \
    --stack-name "$stack_name" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
    --output text 2>/dev/null
}

stack_exists() {
  local stack_name="$1"
  aws cloudformation describe-stacks \
    --stack-name "$stack_name" \
    --region "$REGION" &>/dev/null
}

# --- Deploy Functions ---

deploy_vpc() {
  if [ "$USE_EXISTING_INFRA" = true ]; then
    log "⏭️  Using existing VPC: ${EXISTING_VPC_ID}"
    log "   Subnet 1: ${EXISTING_SUBNET_1} (ap-northeast-1a)"
    log "   Subnet 2: ${EXISTING_SUBNET_2} (ap-northeast-1c)"
    return 0
  fi
  
  local stack_name="${STACK_PREFIX}-vpc"
  log "Deploying VPC stack: ${stack_name}"
  
  # Get AZs for the region
  local az1 az2
  az1=$(aws ec2 describe-availability-zones --region "$REGION" \
    --query 'AvailabilityZones[0].ZoneName' --output text)
  az2=$(aws ec2 describe-availability-zones --region "$REGION" \
    --query 'AvailabilityZones[1].ZoneName' --output text)
  
  aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/01-vpc-network.yaml" \
    --stack-name "$stack_name" \
    --parameter-overrides \
      Environment="$ENV" \
      AvailabilityZone1="$az1" \
      AvailabilityZone2="$az2" \
    --region "$REGION" \
    --no-fail-on-empty-changeset \
    --tags Project=manufacturing-data-platform-poc Environment="$ENV"
  
  log "VPC stack deployed ✅"
}

deploy_s3() {
  local stack_name="${STACK_PREFIX}-s3"
  log "Deploying S3 stack: ${stack_name}"
  
  aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/02-s3-buckets.yaml" \
    --stack-name "$stack_name" \
    --parameter-overrides \
      Environment="$ENV" \
    --region "$REGION" \
    --no-fail-on-empty-changeset \
    --tags Project=manufacturing-data-platform-poc Environment="$ENV"
  
  log "S3 stack deployed ✅"
}

deploy_msk() {
  local stack_name="${STACK_PREFIX}-msk"
  log "Deploying MSK stack: ${stack_name}"
  
  local vpc_id subnet1 subnet2
  
  if [ "$USE_EXISTING_INFRA" = true ]; then
    vpc_id="$EXISTING_VPC_ID"
    subnet1="$EXISTING_SUBNET_1"
    subnet2="$EXISTING_SUBNET_2"
  else
    vpc_id=$(get_stack_output "${STACK_PREFIX}-vpc" "VpcId")
    subnet1=$(get_stack_output "${STACK_PREFIX}-vpc" "PrivateSubnet1Id")
    subnet2=$(get_stack_output "${STACK_PREFIX}-vpc" "PrivateSubnet2Id")
  fi
  
  aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/msk-serverless.yaml" \
    --stack-name "$stack_name" \
    --parameter-overrides \
      VpcId="$vpc_id" \
      SubnetIds="${subnet1},${subnet2}" \
      ClusterName="${STACK_PREFIX}-msk" \
      Environment="$ENV" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset \
    --tags Project=manufacturing-data-platform-poc Environment="$ENV"
  
  log "MSK stack deployed ✅"
}

deploy_fsxn() {
  local stack_name="${STACK_PREFIX}-fsxn"
  log "Deploying FSx for ONTAP stack: ${stack_name}"
  
  local vpc_id subnet1 fsx_sg
  vpc_id=$(get_stack_output "${STACK_PREFIX}-vpc" "VpcId")
  subnet1=$(get_stack_output "${STACK_PREFIX}-vpc" "PrivateSubnet1Id")
  fsx_sg=$(get_stack_output "${STACK_PREFIX}-vpc" "FSxSecurityGroupId")
  
  # Prompt for SVM password if not set
  if [ -z "${FSX_SVM_PASSWORD:-}" ]; then
    echo "Enter FSx SVM admin password (min 8 chars):"
    read -rs FSX_SVM_PASSWORD
    echo ""
  fi
  
  aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/03-fsx-ontap.yaml" \
    --stack-name "$stack_name" \
    --parameter-overrides \
      Environment="$ENV" \
      VpcId="$vpc_id" \
      SubnetId="$subnet1" \
      SecurityGroupId="$fsx_sg" \
      SvmAdminPassword="$FSX_SVM_PASSWORD" \
    --region "$REGION" \
    --no-fail-on-empty-changeset \
    --tags Project=manufacturing-data-platform-poc Environment="$ENV"
  
  log "FSx for ONTAP stack deployed ✅"
  log "⚠️  FSx for ONTAP creation takes 20-40 minutes. Run './deploy.sh status' to check."
}

# --- Main Commands ---

deploy_all() {
  log "🚀 Starting Manufacturing Data Platform PoC deployment"
  log "   Region: ${REGION}"
  log "   Environment: ${ENV}"
  log "   Use existing infra: ${USE_EXISTING_INFRA}"
  if [ "$USE_EXISTING_INFRA" = true ]; then
    log "   Existing VPC: ${EXISTING_VPC_ID}"
    log "   Existing FSx: ${EXISTING_FSX_ID}"
    log "   Existing SVM: ${EXISTING_SVM_ID}"
  fi
  echo ""
  
  deploy_vpc
  deploy_s3
  deploy_msk
  
  if [ "$USE_EXISTING_INFRA" = true ]; then
    log "⏭️  Skipping FSx for ONTAP deployment (using existing: ${EXISTING_FSX_ID})"
    log "   Run './deploy.sh volumes' to create PoC volumes on the existing file system."
  else
    deploy_fsxn
  fi
  
  echo ""
  log "🎉 Deployment complete."
  log ""
  log "Next steps:"
  if [ "$USE_EXISTING_INFRA" = true ]; then
    log "  1. Create PoC volumes: ./deploy.sh volumes"
  fi
  log "  2. Get MSK bootstrap: aws kafka list-clusters-v2 --region ${REGION} --query 'ClusterInfoList[?ClusterName==\`${STACK_PREFIX}-msk\`].ClusterArn' --output text"
  log "  3. Configure ClickHouse Cloud (clickhouse.cloud — free trial)"
  log "  4. Configure Databricks (databricks/01_setup_catalog.sql)"
  log "  5. Test: python generate_events.py --dry-run"
}

create_volumes_on_existing_fsx() {
  log "📦 Creating PoC volumes on existing FSx for ONTAP"
  log "   File System: ${EXISTING_FSX_ID}"
  log "   SVM: ${EXISTING_SVM_ID}"
  echo ""
  
  # Check if FSx exists and is available
  local status
  status=$(aws fsx describe-file-systems \
    --file-system-ids "$EXISTING_FSX_ID" \
    --region "$REGION" \
    --query 'FileSystems[0].Lifecycle' \
    --output text 2>/dev/null || echo "NOT_FOUND")
  
  if [ "$status" != "AVAILABLE" ]; then
    log "❌ ERROR: FSx file system ${EXISTING_FSX_ID} is not AVAILABLE (status: ${status})"
    exit 1
  fi
  log "   Status: ${status} ✅"
  
  # Create volumes using AWS CLI (not CloudFormation — avoids lifecycle management conflicts)
  local volumes=(
    "vol_mfg_images:/vol_images:307200:UNIX:AUTO:31"
    "vol_mfg_videos:/vol_videos:409600:UNIX:AUTO:7"
    "vol_mfg_documents:/vol_documents:102400:MIXED:AUTO:90"
    "vol_mfg_clickhouse_cold:/vol_clickhouse_cold:204800:UNIX:NONE:0"
  )
  
  for vol_spec in "${volumes[@]}"; do
    IFS=':' read -r name junction size security tiering cooling <<< "$vol_spec"
    
    # Check if volume already exists
    local existing
    existing=$(aws fsx describe-volumes \
      --region "$REGION" \
      --filters "Name=file-system-id,Values=${EXISTING_FSX_ID}" \
      --query "Volumes[?Name=='${name}'].VolumeId" \
      --output text 2>/dev/null || echo "")
    
    if [ -n "$existing" ] && [ "$existing" != "None" ]; then
      log "   ⏭️  Volume ${name} already exists (${existing})"
      continue
    fi
    
    log "   Creating volume: ${name} (${junction}, $(( size / 1024 )) GB, ${security})"
    
    local tiering_json="{\"Name\":\"${tiering}\"}"
    if [ "$tiering" = "AUTO" ] && [ "$cooling" -gt 0 ]; then
      tiering_json="{\"Name\":\"AUTO\",\"CoolingPeriod\":${cooling}}"
    fi
    
    aws fsx create-volume \
      --region "$REGION" \
      --name "$name" \
      --volume-type ONTAP \
      --ontap-configuration "{
        \"JunctionPath\": \"${junction}\",
        \"StorageVirtualMachineId\": \"${EXISTING_SVM_ID}\",
        \"SizeInMegabytes\": ${size},
        \"StorageEfficiencyEnabled\": true,
        \"SecurityStyle\": \"${security}\",
        \"TieringPolicy\": ${tiering_json},
        \"SnapshotPolicy\": \"default\",
        \"CopyTagsToBackups\": true
      }" \
      --tags "Key=Project,Value=manufacturing-data-platform-poc" \
             "Key=Environment,Value=${ENV}" \
             "Key=ManagedBy,Value=deploy-script" \
      --output text --query 'Volume.VolumeId' && \
    log "   ✅ Volume ${name} creation initiated" || \
    log "   ❌ Failed to create ${name}"
  done
  
  echo ""
  log "📦 Volume creation complete. Volumes take 1-2 minutes to become AVAILABLE."
  log "   Check status: aws fsx describe-volumes --region ${REGION} --filters Name=file-system-id,Values=${EXISTING_FSX_ID} --query 'Volumes[*].[Name,Lifecycle]' --output table"
}

show_status() {
  log "Stack Status:"
  echo ""
  printf "%-35s %-20s\n" "STACK" "STATUS"
  printf "%-35s %-20s\n" "-----" "------"
  
  for stack in "${STACKS_CORE[@]}"; do
    local status
    status=$(aws cloudformation describe-stacks \
      --stack-name "$stack" \
      --region "$REGION" \
      --query 'Stacks[0].StackStatus' \
      --output text 2>/dev/null || echo "NOT_FOUND")
    printf "%-35s %-20s\n" "$stack" "$status"
  done
  
  if [ "$USE_EXISTING_INFRA" = false ]; then
    for stack in "${STACKS_FSX[@]}"; do
      local status
      status=$(aws cloudformation describe-stacks \
        --stack-name "$stack" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
      printf "%-35s %-20s\n" "$stack" "$status"
    done
  else
    printf "%-35s %-20s\n" "FSx for ONTAP (existing)" "${EXISTING_FSX_ID}"
  fi
  
  # Show existing FSx volumes if using existing
  if [ "$USE_EXISTING_INFRA" = true ]; then
    echo ""
    log "PoC Volumes on existing FSx:"
    aws fsx describe-volumes \
      --region "$REGION" \
      --filters "Name=file-system-id,Values=${EXISTING_FSX_ID}" \
      --query 'Volumes[?Tags[?Key==`Project` && Value==`manufacturing-data-platform-poc`]].[Name,Lifecycle,OntapConfiguration.JunctionPath,OntapConfiguration.SizeInMegabytes]' \
      --output table 2>/dev/null || echo "  (no PoC volumes found)"
  fi
}

destroy_all() {
  log "⚠️  DESTROYING all PoC stacks. This is irreversible."
  echo "Press Ctrl+C to cancel, or Enter to continue..."
  read -r
  
  # Delete FSx stack if it exists (only if we created it)
  if [ "$USE_EXISTING_INFRA" = false ]; then
    for stack in "${STACKS_FSX[@]}"; do
      if stack_exists "$stack"; then
        log "Deleting: ${stack}"
        aws cloudformation delete-stack --stack-name "$stack" --region "$REGION"
        wait_for_stack "$stack" "delete"
        log "Deleted: ${stack} ✅"
      fi
    done
  else
    log "⚠️  Existing FSx for ONTAP volumes (vol-mfg-*) are NOT deleted automatically."
    log "   Delete manually if needed:"
    log "   aws fsx describe-volumes --filters Name=file-system-id,Values=${EXISTING_FSX_ID} --query 'Volumes[?Tags[?Key==\`Project\` && Value==\`manufacturing-data-platform-poc\`]].VolumeId' --output text"
  fi
  
  # Reverse order for core stacks
  for ((i=${#STACKS_CORE[@]}-1; i>=0; i--)); do
    local stack="${STACKS_CORE[$i]}"
    if stack_exists "$stack"; then
      log "Deleting: ${stack}"
      aws cloudformation delete-stack --stack-name "$stack" --region "$REGION"
      wait_for_stack "$stack" "delete"
      log "Deleted: ${stack} ✅"
    else
      log "Skip (not found): ${stack}"
    fi
  done
  
  log "🗑️  All stacks deleted."
  log "Note: S3 buckets with data are retained (delete manually if needed)."
}

# --- Entry Point ---

case "${1:-help}" in
  deploy)
    if [ "${2:-}" = "--new-infra" ]; then
      USE_EXISTING_INFRA=false
    fi
    deploy_all
    ;;
  volumes)
    create_volumes_on_existing_fsx
    ;;
  status)
    show_status
    ;;
  destroy)
    if [ "${2:-}" = "--new-infra" ]; then
      USE_EXISTING_INFRA=false
    fi
    destroy_all
    ;;
  *)
    echo "Usage: $0 {deploy|volumes|status|destroy} [--new-infra]"
    echo ""
    echo "Commands:"
    echo "  deploy              — Deploy MSK + S3 into existing VPC (default: reuse existing infra)"
    echo "  deploy --new-infra  — Deploy ALL new infrastructure (VPC + S3 + MSK + FSx)"
    echo "  volumes             — Create PoC volumes on existing FSx for ONTAP"
    echo "  status              — Show current stack and volume statuses"
    echo "  destroy             — Delete all PoC stacks (with confirmation)"
    echo ""
    echo "Default behavior (existing infra reuse):"
    echo "  VPC:  ${EXISTING_VPC_ID}"
    echo "  FSx:  ${EXISTING_FSX_ID}"
    echo "  SVM:  ${EXISTING_SVM_ID}"
    echo "  Sub1: ${EXISTING_SUBNET_1}"
    echo "  Sub2: ${EXISTING_SUBNET_2}"
    echo ""
    echo "Environment variables:"
    echo "  AWS_REGION          — AWS region (default: ap-northeast-1)"
    echo "  ENVIRONMENT         — Environment name (default: poc)"
    echo "  EXISTING_VPC_ID     — Existing VPC ID"
    echo "  EXISTING_SUBNET_1   — Existing private subnet (AZ-a)"
    echo "  EXISTING_SUBNET_2   — Existing private subnet (AZ-c)"
    echo "  EXISTING_FSX_ID     — Existing FSx file system ID"
    echo "  EXISTING_SVM_ID     — Existing SVM ID"
    exit 1
    ;;
esac
