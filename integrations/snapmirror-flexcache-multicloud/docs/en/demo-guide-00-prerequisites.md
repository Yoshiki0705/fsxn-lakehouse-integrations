> 🌐 Language: [日本語](../ja/demo-guide-00-prerequisites.md) | **English**

# Demo Guide: Common Prerequisites

> Each demo guide references this document for shared prerequisites, tools, and variable configuration.

> 📐 **Design Guides**: Review these before running demos:
> - [S3 AP Design Considerations](../../../../docs/en/s3ap-design-considerations.md) — Directory layout, performance characteristics, PoC checklist
> - [FlexCache / SnapMirror Considerations](../../../../docs/en/s3ap-flexcache-snapmirror-considerations.md) — Write mode selection, cache propagation, teardown ordering

---

## Required Tools

| Tool | Version | Check Command |
|------|---------|---------------|
| AWS CLI | v2.15+ | `aws --version` |
| jq | 1.6+ | `jq --version` |
| curl | 7.x+ | `curl --version` |
| Python | 3.12+ | `python3 --version` |

## ONTAP Version Requirements

| Feature | Minimum ONTAP |
|---------|:-------------:|
| S3 Access Point | 9.14.1 |
| S3 NAS bucket on FlexCache Origin | 9.12.1 |
| S3 NAS bucket on FlexCache Cache | **9.18.1** |
| FlexCache write-back | 9.15.1 |
| FlexCache (read-only) | 9.5 |
| SnapMirror Async | 9.11.1 |
| Cluster Peering Encryption (TLS 1.2) | 9.6 |

## Common Environment Variables

```bash
export AWS_REGION="ap-northeast-1"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

## ONTAP REST API Helper

All guides use this pattern for ONTAP REST API calls:

```bash
# Get management IP
MGMT_IP=$(aws fsx describe-file-systems \
  --file-system-ids "$FS_ID" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$AWS_REGION")

# Get credentials from Secrets Manager
CREDS=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" --query SecretString --output text --region "$AWS_REGION")
ONTAP_USER=$(echo "$CREDS" | jq -r '.username')
ONTAP_PASS=$(echo "$CREDS" | jq -r '.password')

# ONTAP REST API call template
ontap_api() {
  curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
    -X "$1" "https://${MGMT_IP}/api$2" \
    -H "Content-Type: application/json" ${3:+-d "$3"}
}
```

## Network Ports Required

| Port | Protocol | Purpose |
|------|----------|---------|
| 443 | TCP | ONTAP REST API (management) |
| 2049 | TCP | NFS |
| 445 | TCP | SMB/CIFS |
| 11104 | TCP | SnapMirror / FlexCache intercluster |
| 11105 | TCP | SnapMirror / FlexCache intercluster |

## Related Documentation

- [AWS Docs: FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/)
- [NetApp Docs: ONTAP REST API](https://docs.netapp.com/us-en/ontap-automation/)
- [Research Document (EN)](./research.md)
- [Research Document (JA)](../ja/research.md)


---

## FSx for ONTAP-Specific Notes (Validated)

The following behaviors were confirmed during hands-on validation and are not always explicitly documented. All demo guides incorporate these findings.

### FlexCache Creation

| Item | Details |
|------|---------|
| **API endpoint** | Use `/api/storage/flexcache/flexcaches`. The `/api/storage/volumes` endpoint does not accept FlexCache parameters. |
| **`use_tiered_aggregate: true`** | Required on FSx for ONTAP (FabricPool aggregate). Omitting this causes "No suitable storage" error. |
| **Minimum size** | 60GB+ (FlexGroup type) |
| **Deletion procedure** | ① Clear junction path (PATCH `nas.path: ""`) → ② Disable write-back if enabled → ③ DELETE |

### fsxadmin Password

| Item | Details |
|------|---------|
| **Propagation delay** | After FSx API password reset, ONTAP REST API reflects the change in 30-60 seconds |
| **Recommended pattern** | Store in Secrets Manager, retrieve dynamically in scripts (never hardcode) |

### S3 Access Point

| Item | Details |
|------|---------|
| **FileSystemIdentity** | For UNIX type, specify a user that exists on the SVM. `root` always exists. |
| **Creation time** | 30-60 seconds. Poll until AVAILABLE. |
| **Deletion** | `aws fsx detach-and-delete-s3-access-point --name <name>` |

### VPC Peering (Cross-Region)

| Item | Details |
|------|---------|
| **Routing** | If EC2 subnet uses an explicit Route Table (not main), add route to that specific RT. Main RT route alone is insufficient. |
| **Security Group** | Allow inbound from peer VPC CIDR (all traffic or 443+11104-11105) on FSx SG. |
| **Accept** | Cross-region peering requires explicit `accept-vpc-peering-connection` even for same-account. |

### FlexCache Write-Back

| Item | Details |
|------|---------|
| **Origin propagation** | Cache writes become visible at Origin (S3 AP) in 30-90 seconds |
| **Concurrent S3 AP writes** | Same-file writes from S3 AP and Cache cause XLD revoke (Cache data lost). Use separate file sets. |
| **Pre-deletion** | PATCH `writeback.enabled: false` before deleting FlexCache volume |
