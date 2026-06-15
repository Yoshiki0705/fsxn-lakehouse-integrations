#!/bin/bash
set -euo pipefail

# FSx for ONTAP S3 Access Points — PoC Quick Deploy
# Usage: ./deploy.sh --region <region>

REGION="ap-northeast-1"
STACK_NAME="fsxn-lakehouse-poc"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  FSx for ONTAP S3 Access Points — PoC Deployment            ║"
echo "║  Region: ${REGION}                                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --help) echo "Usage: ./deploy.sh --region <region> [--stack-name <name>]"; exit 0 ;;
    *) shift ;;
  esac
done

echo "📋 Pre-flight checks..."
echo "  ✓ AWS CLI: $(aws --version 2>&1 | head -1)"
echo "  ✓ Region: ${REGION}"
echo "  ✓ Account: $(aws sts get-caller-identity --query Account --output text)"
echo ""

# Check if FSx for ONTAP file system exists
echo "🔍 Checking for existing FSx for ONTAP file systems..."
FS_COUNT=$(aws fsx describe-file-systems --query 'FileSystems[?FileSystemType==`ONTAP`] | length(@)' --output text --region "${REGION}")

if [ "${FS_COUNT}" -eq "0" ]; then
  echo "  ❌ No FSx for ONTAP file systems found in ${REGION}."
  echo "  Please create an FSx for ONTAP file system first."
  echo "  See: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/getting-started.html"
  exit 1
fi

echo "  ✓ Found ${FS_COUNT} FSx for ONTAP file system(s)"
echo ""

# List file systems for selection
echo "📂 Available file systems:"
aws fsx describe-file-systems \
  --query 'FileSystems[?FileSystemType==`ONTAP`].{Id:FileSystemId,Lifecycle:Lifecycle,Storage:StorageCapacity,Throughput:OntapConfiguration.ThroughputCapacity}' \
  --output table --region "${REGION}"
echo ""

# List SVMs
echo "📂 Available SVMs:"
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[].{Name:Name,Id:StorageVirtualMachineId,FileSystem:FileSystemId,Lifecycle:Lifecycle}' \
  --output table --region "${REGION}"
echo ""

# List existing S3 Access Points
echo "📂 Existing S3 Access Point attachments:"
aws fsx describe-s3-access-point-attachments \
  --query 'S3AccessPointAttachments[].{Name:Name,Lifecycle:Lifecycle,Alias:S3AccessPoint.Alias,Volume:VolumeId}' \
  --output table --region "${REGION}" 2>/dev/null || echo "  (none found)"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "✅ Pre-flight complete. Your environment is ready for PoC."
echo ""
echo "Next steps:"
echo "  1. If you need a new S3 Access Point:"
echo "     aws fsx create-and-attach-s3-access-point \\"
echo "       --name poc-analytics-ap \\"
echo "       --type ONTAP \\"
echo "       --ontap-configuration '{\"VolumeId\":\"<VOL_ID>\",\"FileSystemIdentity\":{\"Type\":\"UNIX\",\"UnixUser\":{\"Name\":\"analytics_reader\"}}}' \\"
echo "       --region ${REGION}"
echo ""
echo "  2. Upload sample data:"
echo "     ./upload-sample-data.sh --ap-alias <your-ap-alias>"
echo ""
echo "  3. Validate connectivity:"
echo "     ./validate.sh --ap-alias <your-ap-alias>"
echo ""
echo "  4. Run first Athena query:"
echo "     ../02-athena-quickstart/run-first-query.sh --ap-alias <your-ap-alias>"
echo "═══════════════════════════════════════════════════════════════"
