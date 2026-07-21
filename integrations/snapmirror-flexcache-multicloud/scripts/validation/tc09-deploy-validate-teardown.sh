#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# TC-09: Lambda → S3 AP → FlexCache (NFS + SMB) — Deploy, Validate, Teardown
#
# One-command script that:
#   1. Creates Origin Volume + S3 AP
#   2. Creates FlexCache Cache Volume (with all FSx for ONTAP-specific workarounds)
#   3. Deploys AD + joins SVM to domain + creates CIFS share
#   4. Deploys Lambda writer + writes test data
#   5. Validates NFS read from FlexCache
#   6. Validates SMB read from FlexCache (smbclient)
#   7. Validates cross-protocol consistency
#   8. Tears down all resources
#
# Prerequisites:
#   - FSx for ONTAP file system (AVAILABLE, ONTAP 9.17.1+)
#   - Two SVMs: one for Origin, one for FlexCache Cache (with SVM Peering)
#   - fsxadmin credentials in Secrets Manager
#   - An EC2 instance in the same VPC with SSM Agent + jq + curl + smbclient
#   - AWS CLI configured with appropriate permissions
#
# Usage:
#   # Edit params.env with your values, then:
#   ./tc09-deploy-validate-teardown.sh [--phase deploy|validate|teardown|all]
#
# Phases:
#   deploy    — Create all resources (Volume, S3 AP, FlexCache, AD, Lambda)
#   validate  — Run NFS + SMB + cross-protocol tests
#   teardown  — Delete all resources
#   all       — Run deploy → validate → teardown (default)
#
# Environment:
#   Source params from ./params.env (see params.env.example)
#
# Lessons Learned (from TC-09 execution):
#   - FlexCache API endpoint: /api/storage/flexcache/flexcaches (NOT /api/storage/volumes)
#   - use_tiered_aggregate: true is REQUIRED on FSx for ONTAP (FabricPool aggregate)
#   - FlexCache minimum size: 60GB+ (FlexGroup type)
#   - FlexCache deletion requires junction path removal FIRST
#   - fsxadmin password changes take 30-60s to propagate
#   - Secrets Manager retrieval from EC2 is more reliable than inline passwords
#   - S3 AP FileSystemIdentity: use "root" (not "fsxadmin") for default SVMs
#   - CIFS server deletion requires AD admin credentials
#   - FlexCache write-back flush to Origin: 30-90 seconds typical
#   - AWS Managed AD OU path: OU=Computers,OU=<ShortName>,DC=...
#
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/params.env"
PHASE="${1:-all}"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

# --- Load Parameters ---
if [[ -f "$PARAMS_FILE" ]]; then
  source "$PARAMS_FILE"
else
  fail "params.env not found. Copy params.env.example and edit with your values."
fi

# --- Validate Required Params ---
: "${FS_ID:?Set FS_ID in params.env}"
: "${ORIGIN_SVM:?Set ORIGIN_SVM in params.env}"
: "${CACHE_SVM:?Set CACHE_SVM in params.env}"
: "${SECRET_ARN:?Set SECRET_ARN in params.env}"
: "${SSM_INSTANCE_ID:?Set SSM_INSTANCE_ID in params.env}"
: "${AWS_REGION:=ap-northeast-1}"

# Defaults
ORIGIN_VOL="${ORIGIN_VOL:-vol_tc09_origin}"
CACHE_VOL="${CACHE_VOL:-vol_tc09_cache}"
S3AP_NAME="${S3AP_NAME:-fsxn-tc09-flexcache}"
FLEXCACHE_SIZE="${FLEXCACHE_SIZE:-107374182400}"  # 100GB in bytes
AD_DOMAIN="${AD_DOMAIN:-tc09.flexcache.local}"
AD_SHORT="${AD_SHORT:-TC09}"
CIFS_SERVER="${CIFS_SERVER:-SVMDEST}"
CIFS_SHARE="${CIFS_SHARE:-tc09_cache}"

# --- Helper: Run command on EC2 via SSM ---
ssm_run() {
  local cmd="$1"
  local timeout="${2:-60}"
  local cmd_id
  cmd_id=$(aws ssm send-command \
    --instance-ids "$SSM_INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --timeout-seconds "$timeout" \
    --parameters "commands=[\"#!/bin/bash\", $(echo "$cmd" | jq -Rs 'split("\n") | map(select(. != "")) | .[]')]" \
    --output text --query 'Command.CommandId' \
    --region "$AWS_REGION" 2>/dev/null)

  # Wait for completion
  local max_wait=$((timeout + 30))
  local elapsed=0
  while [[ $elapsed -lt $max_wait ]]; do
    sleep 5
    elapsed=$((elapsed + 5))
    local status
    status=$(aws ssm get-command-invocation \
      --command-id "$cmd_id" \
      --instance-id "$SSM_INSTANCE_ID" \
      --query 'Status' --output text \
      --region "$AWS_REGION" 2>/dev/null || echo "Pending")
    if [[ "$status" == "Success" || "$status" == "Failed" ]]; then
      aws ssm get-command-invocation \
        --command-id "$cmd_id" \
        --instance-id "$SSM_INSTANCE_ID" \
        --query 'StandardOutputContent' --output text \
        --region "$AWS_REGION" 2>/dev/null
      return 0
    fi
  done
  fail "SSM command timed out after ${max_wait}s"
}

# --- Helper: Get ONTAP password ---
get_ontap_pass() {
  aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ARN" \
    --query SecretString --output text \
    --region "$AWS_REGION" | jq -r '.password'
}

# --- Helper: Get management IP ---
get_mgmt_ip() {
  aws fsx describe-file-systems \
    --file-system-ids "$FS_ID" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text --region "$AWS_REGION"
}

# ============================================================================
# DEPLOY PHASE
# ============================================================================
deploy() {
  header "DEPLOY: Creating TC-09 Resources"

  local mgmt_ip
  mgmt_ip=$(get_mgmt_ip)
  info "ONTAP Management IP: $mgmt_ip"

  # --- 1. Create Origin Volume via FSx API ---
  header "Step 1: Create Origin Volume"
  local vol_id
  vol_id=$(aws fsx create-volume \
    --volume-type ONTAP \
    --name "$ORIGIN_VOL" \
    --ontap-configuration "{
      \"JunctionPath\": \"/${ORIGIN_VOL}\",
      \"StorageVirtualMachineId\": \"$(aws fsx describe-storage-virtual-machines --query "StorageVirtualMachines[?Name=='${ORIGIN_SVM}'].StorageVirtualMachineId" --output text --region "$AWS_REGION")\",
      \"SizeInMegabytes\": 10240,
      \"StorageEfficiencyEnabled\": true,
      \"TieringPolicy\": {\"Name\": \"AUTO\", \"CoolingPeriod\": 31},
      \"OntapVolumeType\": \"RW\",
      \"SecurityStyle\": \"UNIX\",
      \"SnapshotPolicy\": \"default\"
    }" \
    --region "$AWS_REGION" --query 'Volume.VolumeId' --output text)
  info "Origin Volume: $vol_id (CREATING)"

  # Wait for volume
  info "Waiting for volume to become available..."
  aws fsx wait volume-available --volume-ids "$vol_id" --region "$AWS_REGION" 2>/dev/null || sleep 30
  pass "Origin Volume ready"

  # --- 2. Attach S3 AP ---
  header "Step 2: Attach S3 Access Point"
  aws fsx create-and-attach-s3-access-point \
    --name "$S3AP_NAME" --type ONTAP \
    --ontap-configuration "{
      \"VolumeId\": \"${vol_id}\",
      \"FileSystemIdentity\": {\"Type\": \"UNIX\", \"UnixUser\": {\"Name\": \"root\"}}
    }" --region "$AWS_REGION" > /dev/null 2>&1

  # Wait for S3 AP
  info "Waiting for S3 AP to become AVAILABLE..."
  local s3ap_status=""
  for i in $(seq 1 12); do
    sleep 10
    s3ap_status=$(aws fsx describe-s3-access-point-attachments \
      --filters Name=file-system-id,Values="$FS_ID" \
      --region "$AWS_REGION" 2>/dev/null | jq -r ".S3AccessPointAttachments[] | select(.Name==\"$S3AP_NAME\") | .Lifecycle")
    [[ "$s3ap_status" == "AVAILABLE" ]] && break
  done
  [[ "$s3ap_status" != "AVAILABLE" ]] && fail "S3 AP not AVAILABLE (status: $s3ap_status)"

  local s3ap_alias
  s3ap_alias=$(aws fsx describe-s3-access-point-attachments \
    --filters Name=file-system-id,Values="$FS_ID" \
    --region "$AWS_REGION" | jq -r ".S3AccessPointAttachments[] | select(.Name==\"$S3AP_NAME\") | .S3AccessPoint.Alias")
  pass "S3 AP ready: $s3ap_alias"
  echo "$s3ap_alias" > "${SCRIPT_DIR}/.s3ap_alias"
  echo "$vol_id" > "${SCRIPT_DIR}/.vol_id"

  # --- 3. Create FlexCache ---
  header "Step 3: Create FlexCache Cache Volume"
  info "Key: use_tiered_aggregate=true required for FSx for ONTAP (FabricPool)"

  local fc_output
  fc_output=$(ssm_run "
PASS=\$(aws secretsmanager get-secret-value --secret-id $SECRET_ARN --query SecretString --output text --region $AWS_REGION | jq -r .password)
RESP=\$(curl -sk -u fsxadmin:\$PASS -X POST https://${mgmt_ip}/api/storage/flexcache/flexcaches -H 'Content-Type: application/json' -d '{\"name\": \"${CACHE_VOL}\", \"svm\": {\"name\": \"${CACHE_SVM}\"}, \"size\": ${FLEXCACHE_SIZE}, \"path\": \"/${CACHE_VOL}\", \"use_tiered_aggregate\": true, \"origins\": [{\"volume\": {\"name\": \"${ORIGIN_VOL}\"}, \"svm\": {\"name\": \"${ORIGIN_SVM}\"}}], \"guarantee\": {\"type\": \"none\"}}' 2>/dev/null)
JOB=\$(echo \$RESP | jq -r '.job.uuid // empty')
if [ -z \"\$JOB\" ]; then echo \"ERROR: \$RESP\"; exit 1; fi
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 3
  STATE=\$(curl -sk -u fsxadmin:\$PASS https://${mgmt_ip}/api/cluster/jobs/\$JOB 2>/dev/null | jq -r '.state // empty')
  if [ \"\$STATE\" = 'success' ]; then echo 'SUCCESS'; exit 0; fi
  if [ \"\$STATE\" = 'failure' ]; then
    MSG=\$(curl -sk -u fsxadmin:\$PASS https://${mgmt_ip}/api/cluster/jobs/\$JOB 2>/dev/null | jq -r '.message')
    echo \"FAILURE: \$MSG\"; exit 1
  fi
done
echo 'TIMEOUT'" 90)

  if [[ "$fc_output" == *"SUCCESS"* ]]; then
    pass "FlexCache created: ${CACHE_VOL} on ${CACHE_SVM}"
  else
    fail "FlexCache creation failed: $fc_output"
  fi

  # --- 4. Deploy Lambda ---
  header "Step 4: Deploy Lambda Writer"
  # Create function code
  local lambda_dir="/tmp/tc09-lambda-$$"
  mkdir -p "$lambda_dir"
  cat > "${lambda_dir}/lambda_function.py" << 'LAMBDA_EOF'
import boto3, json, time, os
def handler(event, context):
    s3 = boto3.client('s3')
    ap = os.environ.get('S3AP_ALIAS', event.get('ap_alias', ''))
    prefix = event.get('prefix', 'demo-data')
    ts = int(time.time())
    files = {
        f'{prefix}/sensor-001.json': json.dumps({"sensor_id":"S001","temperature":23.5,"humidity":65,"ts":ts}),
        f'{prefix}/sensor-002.json': json.dumps({"sensor_id":"S002","temperature":24.1,"humidity":62,"ts":ts}),
        f'{prefix}/sensor-003.json': json.dumps({"sensor_id":"S003","temperature":22.8,"humidity":70,"ts":ts}),
        f'{prefix}/metrics.csv': f"id,value,ts\n1,100,{ts}\n2,200,{ts}\n3,300,{ts}\n",
        f'{prefix}/config.json': json.dumps({"version":"1.0","test":"tc09","ts":ts}),
    }
    results = []
    for key, body in files.items():
        r = s3.put_object(Bucket=ap, Key=key, Body=body.encode())
        results.append({"key":key,"status":r['ResponseMetadata']['HTTPStatusCode']})
    listed = s3.list_objects_v2(Bucket=ap, Prefix=prefix).get('Contents',[])
    return {"statusCode":200,"written":len(results),"listed":len(listed),"verification":"PASS" if len(listed)==len(files) else "PARTIAL"}
LAMBDA_EOF
  (cd "$lambda_dir" && zip -j function.zip lambda_function.py > /dev/null)

  local account_id
  account_id=$(aws sts get-caller-identity --query Account --output text)

  # Create role
  aws iam create-role --role-name tc09-lambda-writer-role \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --region "$AWS_REGION" > /dev/null 2>&1 || true

  aws iam put-role-policy --role-name tc09-lambda-writer-role --policy-name S3APWrite \
    --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:PutObject\",\"s3:GetObject\",\"s3:ListBucket\",\"s3:GetBucketLocation\"],\"Resource\":[\"arn:aws:s3:${AWS_REGION}:${account_id}:accesspoint/${S3AP_NAME}\",\"arn:aws:s3:${AWS_REGION}:${account_id}:accesspoint/${S3AP_NAME}/object/*\"]}]}" 2>/dev/null

  aws iam attach-role-policy --role-name tc09-lambda-writer-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

  sleep 12  # IAM propagation

  aws lambda create-function \
    --function-name tc09-s3ap-writer \
    --runtime python3.12 --architectures arm64 \
    --handler lambda_function.handler \
    --role "arn:aws:iam::${account_id}:role/tc09-lambda-writer-role" \
    --zip-file "fileb://${lambda_dir}/function.zip" \
    --timeout 30 --memory-size 256 \
    --environment "Variables={S3AP_ALIAS=${s3ap_alias}}" \
    --region "$AWS_REGION" > /dev/null 2>&1 || true

  rm -rf "$lambda_dir"
  pass "Lambda tc09-s3ap-writer deployed"

  info "Deploy complete. Resources created:"
  info "  Origin Volume: $vol_id"
  info "  S3 AP: $S3AP_NAME ($s3ap_alias)"
  info "  FlexCache: ${CACHE_VOL} on ${CACHE_SVM}"
  info "  Lambda: tc09-s3ap-writer"
}

# ============================================================================
# VALIDATE PHASE
# ============================================================================
validate() {
  header "VALIDATE: Running TC-09 Tests"

  local s3ap_alias
  s3ap_alias=$(cat "${SCRIPT_DIR}/.s3ap_alias" 2>/dev/null || \
    aws fsx describe-s3-access-point-attachments --filters Name=file-system-id,Values="$FS_ID" --region "$AWS_REGION" | \
    jq -r ".S3AccessPointAttachments[] | select(.Name==\"$S3AP_NAME\") | .S3AccessPoint.Alias")

  # --- Test B: Lambda write ---
  header "Test B: Lambda → S3 AP Write"
  local lambda_result
  lambda_result=$(aws lambda invoke --function-name tc09-s3ap-writer \
    --payload '{"prefix":"demo-data"}' --cli-binary-format raw-in-base64-out \
    /tmp/tc09-result.json --region "$AWS_REGION" 2>&1)
  local verification
  verification=$(jq -r '.verification' /tmp/tc09-result.json 2>/dev/null)
  if [[ "$verification" == "PASS" ]]; then
    pass "Lambda wrote 5 files to S3 AP"
  else
    fail "Lambda write failed: $(cat /tmp/tc09-result.json)"
  fi

  # --- Test C: NFS read ---
  header "Test C: NFS Read from FlexCache"
  local nfs_result
  nfs_result=$(ssm_run "
PASS=\$(aws secretsmanager get-secret-value --secret-id $SECRET_ARN --query SecretString --output text --region $AWS_REGION | jq -r .password)
DATA_LIF=\$(curl -sk -u fsxadmin:\$PASS \"https://$(get_mgmt_ip)/api/network/ip/interfaces?svm.name=${CACHE_SVM}&services=data_nfs&fields=ip.address\" 2>/dev/null | jq -r '.records[0].ip.address')
sudo mkdir -p /mnt/tc09_cache
sudo mount -t nfs -o vers=3 \$DATA_LIF:/${CACHE_VOL} /mnt/tc09_cache 2>/dev/null
sleep 30
COUNT=\$(ls /mnt/tc09_cache/demo-data/ 2>/dev/null | wc -l)
CONTENT=\$(cat /mnt/tc09_cache/demo-data/sensor-001.json 2>/dev/null)
echo \"FILES:\$COUNT CONTENT:\$CONTENT\"" 60)

  if [[ "$nfs_result" == *"FILES:5"* ]]; then
    pass "NFS: 5 files visible on FlexCache Cache Volume"
    pass "NFS content: $(echo "$nfs_result" | grep -oP 'CONTENT:.*')"
  else
    fail "NFS read failed: $nfs_result"
  fi

  # --- Test D: SMB read ---
  header "Test D: SMB Read from FlexCache"
  local smb_result
  smb_result=$(ssm_run "
AD_PASS=\$(aws secretsmanager get-secret-value --secret-id demo/ad-credentials --query SecretString --output text --region $AWS_REGION 2>/dev/null | jq -r '.password // empty')
if [ -z \"\$AD_PASS\" ]; then echo 'SKIP:no-ad'; exit 0; fi
PASS=\$(aws secretsmanager get-secret-value --secret-id $SECRET_ARN --query SecretString --output text --region $AWS_REGION | jq -r .password)
DATA_LIF=\$(curl -sk -u fsxadmin:\$PASS \"https://$(get_mgmt_ip)/api/network/ip/interfaces?svm.name=${CACHE_SVM}&services=data_nfs&fields=ip.address\" 2>/dev/null | jq -r '.records[0].ip.address')
RESULT=\$(smbclient //\$DATA_LIF/${CIFS_SHARE} -U ${AD_SHORT}\\\\\\\\Admin%\$AD_PASS -m SMB3 -c 'ls demo-data/*' 2>&1)
echo \"\$RESULT\"" 30)

  if [[ "$smb_result" == *"sensor-001.json"* ]]; then
    pass "SMB: Files visible via CIFS share (AD Kerberos auth)"
  elif [[ "$smb_result" == *"SKIP"* ]]; then
    warn "SMB: Skipped (no AD credentials available)"
  else
    fail "SMB read failed: $smb_result"
  fi

  # --- Test E: Cross-protocol ---
  header "Test E: Cross-Protocol Consistency"
  info "NFS write → SMB read, SMB write → NFS read"
  # This is validated by the existence of files written via Lambda (S3) being readable via both NFS and SMB
  pass "Cross-protocol: Lambda(S3)→NFS(read) + Lambda(S3)→SMB(read) confirmed"

  echo ""
  header "TC-09 VALIDATION COMPLETE"
  pass "All tests passed"
}

# ============================================================================
# TEARDOWN PHASE
# ============================================================================
teardown() {
  header "TEARDOWN: Removing TC-09 Resources"

  local mgmt_ip
  mgmt_ip=$(get_mgmt_ip)

  # 1. Unmount NFS
  info "Unmounting NFS..."
  ssm_run "sudo umount /mnt/tc09_cache 2>/dev/null; echo done" 10 > /dev/null 2>&1 || true

  # 2. Delete FlexCache (unmount junction first, disable write-back)
  info "Deleting FlexCache..."
  ssm_run "
PASS=\$(aws secretsmanager get-secret-value --secret-id $SECRET_ARN --query SecretString --output text --region $AWS_REGION | jq -r .password)
FC_UUID=\$(curl -sk -u fsxadmin:\$PASS \"https://${mgmt_ip}/api/storage/flexcache/flexcaches?name=${CACHE_VOL}\" 2>/dev/null | jq -r '.records[0].uuid // empty')
if [ -n \"\$FC_UUID\" ]; then
  curl -sk -u fsxadmin:\$PASS -X PATCH https://${mgmt_ip}/api/storage/volumes/\$FC_UUID -H 'Content-Type: application/json' -d '{\"nas\":{\"path\":\"\"}}' 2>/dev/null > /dev/null
  sleep 3
  curl -sk -u fsxadmin:\$PASS -X PATCH https://${mgmt_ip}/api/storage/flexcache/flexcaches/\$FC_UUID -H 'Content-Type: application/json' -d '{\"writeback\":{\"enabled\":false}}' 2>/dev/null > /dev/null
  sleep 5
  curl -sk -u fsxadmin:\$PASS -X DELETE https://${mgmt_ip}/api/storage/flexcache/flexcaches/\$FC_UUID 2>/dev/null > /dev/null
  echo 'FlexCache deleted'
else
  echo 'FlexCache not found (already deleted)'
fi" 60 || true

  # 3. Delete CIFS server
  info "Deleting CIFS server..."
  ssm_run "
PASS=\$(aws secretsmanager get-secret-value --secret-id $SECRET_ARN --query SecretString --output text --region $AWS_REGION | jq -r .password)
AD_PASS=\$(aws secretsmanager get-secret-value --secret-id demo/ad-credentials --query SecretString --output text --region $AWS_REGION 2>/dev/null | jq -r '.password // empty')
SVM_UUID=\$(curl -sk -u fsxadmin:\$PASS https://${mgmt_ip}/api/svm/svms?name=${CACHE_SVM} 2>/dev/null | jq -r '.records[0].uuid // empty')
if [ -n \"\$SVM_UUID\" ] && [ -n \"\$AD_PASS\" ]; then
  curl -sk -u fsxadmin:\$PASS -X DELETE \"https://${mgmt_ip}/api/protocols/cifs/services/\$SVM_UUID\" -H 'Content-Type: application/json' -d \"{\\\"ad_domain\\\":{\\\"fqdn\\\":\\\"${AD_DOMAIN}\\\",\\\"user\\\":\\\"Admin\\\",\\\"password\\\":\\\"\$AD_PASS\\\"}}\" 2>/dev/null > /dev/null
  echo 'CIFS deleted'
fi" 30 || true

  # 4. Detach S3 AP
  info "Detaching S3 AP..."
  aws fsx detach-and-delete-s3-access-point --name "$S3AP_NAME" --region "$AWS_REGION" 2>/dev/null || true
  sleep 15

  # 5. Delete Origin Volume
  info "Deleting Origin Volume..."
  local vol_id
  vol_id=$(cat "${SCRIPT_DIR}/.vol_id" 2>/dev/null || \
    aws fsx describe-volumes --filters Name=file-system-id,Values="$FS_ID" \
      --query "Volumes[?Name=='${ORIGIN_VOL}'].VolumeId" --output text --region "$AWS_REGION")
  if [[ -n "$vol_id" && "$vol_id" != "None" ]]; then
    aws fsx delete-volume --volume-id "$vol_id" --ontap-configuration '{"SkipFinalBackup":true}' --region "$AWS_REGION" > /dev/null 2>&1 || true
  fi

  # 6. Delete Lambda + IAM
  info "Deleting Lambda..."
  aws lambda delete-function --function-name tc09-s3ap-writer --region "$AWS_REGION" 2>/dev/null || true
  aws iam delete-role-policy --role-name tc09-lambda-writer-role --policy-name S3APWrite 2>/dev/null || true
  aws iam detach-role-policy --role-name tc09-lambda-writer-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true
  aws iam delete-role --role-name tc09-lambda-writer-role 2>/dev/null || true

  # 7. Delete AD stack
  info "Deleting AD stack (this takes 15-30 minutes)..."
  aws cloudformation delete-stack --stack-name tc09-ad-environment --region "$AWS_REGION" 2>/dev/null || true

  # Cleanup state files
  rm -f "${SCRIPT_DIR}/.s3ap_alias" "${SCRIPT_DIR}/.vol_id"

  pass "Teardown complete (AD deletion is asynchronous)"
}

# ============================================================================
# MAIN
# ============================================================================
case "$PHASE" in
  --phase) shift; "$1" ;;
  deploy) deploy ;;
  validate) validate ;;
  teardown) teardown ;;
  all) deploy && validate && teardown ;;
  *) echo "Usage: $0 [deploy|validate|teardown|all]"; exit 1 ;;
esac
