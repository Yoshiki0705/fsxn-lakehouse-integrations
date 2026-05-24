# FSx S3 AP Networking Considerations

## Overview

FSx for ONTAP S3 Access Points have specific networking requirements that differ from regular S3 bucket access. This document consolidates findings from multiple verification rounds.

## Key Findings

### 1. S3 Gateway Endpoint and FSx S3 AP

**Known issue** (documented in [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)):

> VPC 内 Lambda からタイムアウト | Internet Origin AP に S3 Gateway EP 経由でアクセス | Lambda を VPC 外に配置、または NAT Gateway 経由に変更

**Explanation**: When a VPC-attached Lambda or EC2 instance accesses an internet-origin FSx S3 AP, the S3 Gateway VPC Endpoint may intercept the traffic but fail to route it correctly to the FSx S3 AP backend. This is because FSx S3 AP aliases resolve to `s3-r-w.<region>.amazonaws.com` which may not be handled the same way as standard S3 bucket traffic by the Gateway endpoint.

**Workarounds**:
1. Place Lambda outside VPC (no VPC attachment) — simplest for internet-origin APs
2. Use NAT Gateway for outbound S3 AP traffic
3. Remove S3 Gateway endpoint from the specific route table (not recommended for production — breaks regular S3 access optimization)

### 2. Internet-Origin vs VPC-Origin

| AP Type | Access from VPC Lambda | Access from non-VPC Lambda | Access from EC2 (public subnet) |
|---------|----------------------|---------------------------|-------------------------------|
| Internet-origin | ⚠️ May timeout via Gateway EP | ✅ Works | ✅ Works (via IGW) |
| VPC-origin | ✅ Works (via Interface EP) | ❌ Blocked by design | ✅ Works (same VPC) |

### 3. AWS Service Access Patterns

| Service | Network Path | FSx S3 AP Compatibility |
|---------|-------------|------------------------|
| Athena | AWS-managed (no customer VPC) | ✅ Internet-origin required |
| Glue ETL | AWS-managed or VPC-attached | ✅ Internet-origin (non-VPC) or NAT Gateway (VPC) |
| EMR Serverless | AWS-managed | ✅ Internet-origin required |
| Lambda (no VPC) | Internet | ✅ Internet-origin works directly |
| Lambda (VPC-attached) | VPC routing | ⚠️ Requires NAT Gateway or no S3 Gateway EP |
| Redshift Spectrum | AWS-managed | ✅ Internet-origin required |
| Databricks | Customer-managed VPC | ⚠️ Session policy blocks (separate issue) |

### 4. DNS Resolution

FSx S3 AP aliases resolve differently from regular S3 buckets:

```
Regular S3 bucket:
  my-bucket.s3.ap-northeast-1.amazonaws.com → S3 service IPs (in prefix list)

FSx S3 AP alias:
  my-ap-alias-ext-s3alias.s3.ap-northeast-1.amazonaws.com → s3-r-w.ap-northeast-1.amazonaws.com
```

The `s3-r-w` hostname is the FSx S3 AP backend. Its IP addresses may or may not be included in the S3 prefix list (`pl-61a54008` for ap-northeast-1) used by S3 Gateway endpoints.

### 5. Troubleshooting Checklist

When FSx S3 AP access times out:

1. **Verify DNS resolution**: `nslookup <alias>.s3.<region>.amazonaws.com`
2. **Verify TCP connectivity**: `curl -s -o /dev/null -w '%{http_code}' --max-time 5 https://<alias>.s3.<region>.amazonaws.com/`
3. **Test regular S3**: `aws s3 ls s3://<regular-bucket>/` — if this works, the issue is S3 AP-specific
4. **Check S3 Gateway endpoint**: Is the route table associated with a Gateway endpoint? If yes, try removing it temporarily
5. **Check AP lifecycle**: `aws fsx describe-s3-access-point-attachments` — should be AVAILABLE
6. **Check volume status**: `aws fsx describe-volumes --volume-ids <vol-id>` — should be CREATED/AVAILABLE
7. **Check SVM S3 protocol**: Ensure the SVM has S3 protocol enabled and the volume is mounted

### 6. Recommended Architecture for VPC-Internal Access

```
┌─────────────────────────────────────────────────────────────────┐
│  VPC                                                             │
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │ Private Subnet    │     │ Public Subnet     │                  │
│  │ (Lambda/EC2)      │────▶│ NAT Gateway       │────▶ IGW ──▶ FSx S3 AP
│  │                   │     │                   │                  │
│  └──────────────────┘     └──────────────────┘                  │
│         │                                                        │
│         │ S3 Gateway EP (for regular S3 bucket access)           │
│         └──────────────────────────────────────▶ S3 Service      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

For VPC-internal workloads that need both regular S3 and FSx S3 AP:
- Keep S3 Gateway endpoint for regular S3 bucket access (free, low latency)
- Route FSx S3 AP traffic through NAT Gateway (or place compute outside VPC)

## References

- [FSx for ONTAP S3 Access Points documentation](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [Configuring network access for S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [S3 Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns — s3ap-authorization-model.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-authorization-model.md)
