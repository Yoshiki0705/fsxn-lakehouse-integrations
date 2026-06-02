# Infrastructure Request Template: FSx for ONTAP + S3 Access Point

🌐 [日本語](infrastructure-request-template-ja.md) | English

## Purpose

This template helps data engineers request the infrastructure needed to run the Iceberg Metadata Catalog with real FSx for ONTAP data. Send this to your infrastructure/platform team.

---

## Request Summary

**What I need**: An FSx for ONTAP S3 Access Point that allows read access to unstructured files for AI metadata cataloging.

**Why**: To make existing NAS files (PDF, images, CAD, logs) instantly searchable via SQL and AI — without copying data to S3.

**Impact**: Zero changes to existing NFS/SMB workflows. Read-only S3 API access to the same files.

---

## Required Resources

### 1. FSx for ONTAP S3 Access Point

| Setting | Recommended Value | Notes |
|---------|-------------------|-------|
| Target volume | Volume containing files to catalog | Read-only access is sufficient |
| S3 AP name | `metadata-catalog-ap` | Will get alias ending in `-ext-s3alias` |
| File system identity | Dedicated service account (e.g., `metadata-reader`) | Minimum privilege: read-only on target paths |
| Security style | UNIX or Mixed | Must match volume security style |
| Network access | Same VPC as Lambda/EMR | Or internet-accessible for development |

### 2. IAM Policy for the S3 Access Point

The data engineering team needs an IAM role/user with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>",
        "arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>/*"
      ]
    }
  ]
}
```

### 3. S3 Access Point Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<ACCOUNT_ID>:role/<DATA_ENGINEERING_ROLE>"
      },
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>",
        "arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>/object/*"
      ]
    }
  ]
}
```

### 4. Network Requirements

| Requirement | Details |
|-------------|---------|
| VPC | Same VPC as FSx file system |
| Subnet | Private subnet with NAT gateway (for AWS API calls) |
| Security Group | Allow outbound HTTPS (443) to AWS services |
| DNS | VPC DNS resolution enabled |

---

## What the Data Engineering Team Will Do

Once the S3 Access Point is ready, we will:

1. Run `./check-prerequisites.sh --ap-alias <alias>` to verify access
2. Scan file metadata (read-only, no file modification)
3. Write metadata to S3 Tables (separate from FSx)
4. Query metadata via Athena SQL
5. Optionally: AI classification via Bedrock (reads file content, writes to S3 Tables only)

**No changes to existing files or permissions on FSx.**

---

## Information Needed Back

After setup, please provide:

| Item | Example |
|------|---------|
| S3 AP alias | `metadata-catal-abc123def456-ext-s3alias` |
| Region | `ap-northeast-1` |
| Target volume path(s) | `/vol1/documents/`, `/vol1/images/` |
| File system identity used | `metadata-reader` (UID 1001) |
| Any path restrictions | Only `/vol1/public/` is accessible |

---

## Timeline

| Phase | Duration | Dependency |
|-------|----------|------------|
| S3 AP creation | ~30 minutes | FSx admin access |
| IAM policy setup | ~15 minutes | IAM admin access |
| Verification | ~5 minutes | Data engineering team |
| First metadata scan | ~30 seconds | After verification |

---

## FAQ for Infrastructure Team

**Q: Does this modify any files on FSx?**
A: No. The AI classification pipeline reads files via S3 Access Point but does not modify, move, or delete them. S3 Access Point supports write operations (PutObject, DeleteObject), but this solution's pipeline is designed for read-only access to source files.

**Q: Does this affect NFS/SMB performance?**
A: Minimal impact. S3 AP reads use the same backend as NFS/SMB but through a separate protocol path. For large-scale scans (100K+ files), schedule during off-peak hours.

**Q: What security style should the volume use?**
A: The S3 AP works with UNIX, NTFS, or Mixed security styles. The file system identity determines what files are accessible.

**Q: Can we restrict which paths are accessible?**
A: Yes. The S3 AP is attached to a specific volume. Within that volume, the file system identity's permissions determine accessible paths.

**Q: What happens if we revoke the S3 AP?**
A: The metadata catalog continues to work (metadata is in S3 Tables). New file scans will fail until access is restored. No data loss.

---

## S3 Access Point Setup Steps (for Infrastructure Team)

### Prerequisites Check

Before creating the S3 AP, verify:
- [ ] FSx for ONTAP file system exists and is `AVAILABLE`
- [ ] Target volume exists, is mounted (has a junction path), and contains files to catalog
- [ ] VPC has DNS resolution enabled
- [ ] IAM user/role has `fsx:CreateAndAttachS3AccessPoint`, `s3:CreateAccessPoint`, `s3:GetAccessPoint` permissions

### Option A: AWS Console

1. Open the **Amazon FSx** console at https://console.aws.amazon.com/fsx/
2. In the left navigation pane, choose **Volumes**
3. Select the FSx for ONTAP volume you want to attach the access point to
4. From the **Actions** menu, choose **Create S3 access point**
5. Configure:
   - **Access point name**: `metadata-catalog-ap` (lowercase, 3-50 chars)
   - **File system user identity type**: UNIX or Windows
   - **Username**: e.g., `metadata-reader` (must exist on the file system with appropriate read permissions)
   - **Network origin**: Choose **Internet** (for development) or **Virtual private cloud (VPC)** (for production)
6. (Optional) Add an access point policy to restrict which IAM principals can use the AP
7. Choose **Create access point**
8. Note the generated **Alias** (ending in `-ext-s3alias`) — this is what the data engineering team needs

### Option B: AWS CLI

```bash
# First, find your volume ID:
aws fsx describe-volumes \
  --filters Name=file-system-id,Values=<FSX_FILE_SYSTEM_ID> \
  --query "Volumes[*].{VolumeId:VolumeId,Name:Name,JunctionPath:OntapConfiguration.JunctionPath}" \
  --output table --region <REGION>

# Then create the S3 Access Point:
aws fsx create-and-attach-s3-access-point \
  --name metadata-catalog-ap \
  --type ONTAP \
  --ontap-configuration '{
    "VolumeId": "<VOLUME_ID>",
    "FileSystemIdentity": {
      "Type": "UNIX",
      "UnixUser": {
        "Name": "metadata-reader"
      }
    }
  }' \
  --s3-access-point '{
    "VpcConfiguration": {
      "VpcId": "<VPC_ID>"
    }
  }' \
  --region <REGION>
```

**Required parameters**:
- `--name`: Access point name (lowercase, 3-50 characters)
- `--type`: `ONTAP`
- `--ontap-configuration`: Volume ID + file system identity (UNIX user or Windows user)
- `--s3-access-point` (optional): VPC restriction. Omit for internet-accessible.

**Response** includes the S3 AP alias:
```json
{
  "S3AccessPointAttachment": {
    "Name": "metadata-catalog-ap",
    "S3AccessPoint": {
      "Alias": "metadata-catal-abc123def456-ext-s3alias"
    },
    "Lifecycle": "CREATING"
  }
}
```

Wait for `Lifecycle` to become `AVAILABLE` before use:
```bash
aws fsx describe-s3-access-point-attachments \
  --filters Name=name,Values=metadata-catalog-ap \
  --region <REGION>
```

### Required IAM Permissions (for the person creating the S3 AP)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "fsx:CreateAndAttachS3AccessPoint",
        "fsx:DescribeS3AccessPointAttachments",
        "s3:CreateAccessPoint",
        "s3:GetAccessPoint",
        "s3:PutAccessPointPolicy",
        "s3:DeleteAccessPoint"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Reference**: [AWS Documentation — Creating access points for FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-access-points.html)

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  VPC (same as FSx for ONTAP)                                │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────┐    │
│  │  Private Subnet      │    │  FSx for ONTAP          │    │
│  │                      │    │                         │    │
│  │  Lambda / EMR        │───▶│  S3 Access Point        │    │
│  │  (metadata scan)     │    │  (read-only)            │    │
│  │                      │    │                         │    │
│  └──────────┬───────────┘    │  NFS/SMB (unchanged)    │    │
│             │                │  ↕ existing apps        │    │
│             │ NAT GW         └─────────────────────────┘    │
│             ▼                                               │
│  ┌──────────────────────┐                                   │
│  │  AWS Services         │                                   │
│  │  • S3 Tables          │                                   │
│  │  • Athena             │                                   │
│  │  • Bedrock            │                                   │
│  │  • OpenSearch         │                                   │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

**Key points**:
- Lambda/EMR accesses FSx via S3 AP within the same VPC
- Outbound to AWS services via NAT Gateway or VPC Endpoints
- Existing NFS/SMB traffic is unaffected
- No inbound internet access required

---

## Security & Audit

| Control | Implementation |
|---------|---------------|
| Access scope | Read-only S3 AP with dedicated file system identity |
| Least privilege | IAM policy restricts to specific AP ARN only |
| Audit trail | CloudTrail logs all S3 AP API calls |
| Data classification | Metadata only leaves FSx; raw files stay in place |
| Network isolation | Same VPC, private subnet, no public access |
| Revocation | Delete S3 AP or IAM policy to immediately revoke |

### Recommended Monitoring (Infrastructure Side)

| Metric | Source | Alert condition |
|--------|--------|-----------------|
| FSx throughput | CloudWatch `FSx` namespace | Unusual spike during scan hours |
| S3 AP request count | CloudTrail | Unexpected volume of requests |
| IAM access denied | CloudTrail | Failed access attempts |
