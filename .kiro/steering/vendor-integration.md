# Vendor Integration Checklist

## New Vendor Integration Requirements

When adding a new lakehouse platform integration, complete the following checklist.

## 1. S3 API Compatibility Assessment

| Check Item | Status | Notes |
|-----------|--------|-------|
| GetObject support | | |
| PutObject support | | |
| DeleteObject support | | |
| ListObjectsV2 support | | |
| Multipart Upload support | | |
| GetBucketLocation handling | | Some platforms require this |
| Path-style vs Virtual-hosted | | FSxN S3 AP uses path-style |
| Custom endpoint URL support | | Required for S3 AP alias |
| Region configuration | | Must match FSxN region |

## 2. Authentication Method

| Method | Supported | Notes |
|--------|-----------|-------|
| IAM Role (AssumeRole) | Preferred | Cross-account role for SaaS platforms |
| IAM Access Key | Fallback | For platforms without IAM integration |
| OAuth / OIDC | If available | Databricks, some SaaS |
| Instance Profile | For EC2-based | EMR, self-hosted platforms |

## 3. Network Access Pattern

| Pattern | Description | When to Use |
|---------|-------------|-------------|
| VPC-internal | Platform in same VPC as FSxN | EMR, Glue, Lambda |
| VPC Peering | Platform in different VPC | Databricks (customer VPC) |
| PrivateLink | Cross-account private | Snowflake, Databricks |
| Internet | Public endpoint | SaaS platforms (with IAM auth) |

## 4. Required CloudFormation Resources

Every integration template MUST include:
- S3 Access Point (VPC-scoped when possible)
- IAM Role with least-privilege S3 AP access
- S3 AP Policy (restrict to platform's principal)
- Security Group rules (if VPC-internal)

## 5. Required Documentation

- `README.md` — Integration overview
- `docs/ja/setup-guide.md` — Step-by-step setup (Japanese)
- `docs/en/setup-guide.md` — Step-by-step setup (English)
- Architecture diagram in `docs/images/`

## 6. Data Format Support Matrix

Document which formats the platform supports with FSxN:

| Format | Read | Write | Table Type |
|--------|------|-------|------------|
| Parquet | | | External Table |
| Iceberg | | | Managed/External |
| Delta Lake | | | Managed/External |
| Hudi | | | External |
| CSV | | | External |
| JSON | | | External |
| ORC | | | External |

## 7. ONTAP Value Integration

Document how ONTAP features benefit this platform:

- **Snapshot**: How to leverage for recovery/testing
- **FlexClone**: Dev/test data provisioning workflow
- **Tiering**: Cold partition management
- **Deduplication**: Storage efficiency for this workload
- **SnapMirror**: DR strategy

## 8. Testing Requirements

- [ ] S3 AP connectivity test (read/write/list)
- [ ] IAM role assumption test
- [ ] Data format read test (at least Parquet + CSV)
- [ ] Data format write test (if read-write pattern)
- [ ] VPC endpoint routing verification
- [ ] Error handling (permission denied, not found)

## 9. Template Parameters (Standard)

All integration templates MUST accept these parameters:

```yaml
Parameters:
  EnvironmentName:
    Type: String
    Default: fsxn-lakehouse
  S3BucketName:
    Type: String
    Description: FSxN SVM S3 bucket name
  VpcId:
    Type: AWS::EC2::VPC::Id
  SubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
  # Platform-specific parameters below...
```
