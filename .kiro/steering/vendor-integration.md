---
inclusion: auto
---

# Vendor Integration Checklist

## Adding a New Vendor Integration

Every new vendor integration MUST complete these steps:

### 1. S3 AP Compatibility Check

| API | Required | Notes |
|-----|----------|-------|
| GetObject | ✅ | All platforms need read |
| PutObject | For Pattern B/C | Write-back capability |
| ListObjectsV2 | ✅ | Table/file discovery |
| DeleteObject | For Pattern B/C | Table maintenance |
| Multipart Upload | For large files | Delta/Iceberg writes |
| GetBucketLocation | Check | Some platforms require this |

### 2. Network Origin Requirement

- **Internet origin**: Athena, Glue, Redshift Spectrum, Snowflake
- **VPC origin**: Databricks (customer VPC), EMR, Lambda

### 3. Authentication Pattern

- Databricks: Cross-account IAM Role + External ID
- Snowflake: Storage Integration → DESCRIBE → update trust policy
- AWS services: Service-linked roles or execution roles
- Third-party: IAM Role with trust policy for vendor's AWS account

### 4. Required Deliverables

- [ ] `template.yaml` — CloudFormation (S3 AP + IAM Role + policies)
- [ ] `README.md` — Bilingual with language switcher
- [ ] `docs/ja/setup-guide.md` — Japanese setup guide
- [ ] `docs/en/setup-guide.md` — English setup guide
- [ ] Sample queries/notebooks
- [ ] E2E verification tasks in tasks.md
- [ ] Per-vendor spec prompt in `.kiro/specs/`

### 5. E2E Verification (5 Phases)

Every vendor MUST have tasks for:
- **A**: Account preparation & credentials
- **B**: AWS infrastructure deploy & validation
- **C**: Vendor UI configuration & screenshots
- **D**: Demo scenario execution
- **E**: Results recording & final check

### 6. ONTAP Value Documentation

Document how these ONTAP features benefit the specific platform:
- Snapshot → Recovery strategy
- FlexClone → Dev/test workflow
- FabricPool → Cold data management
- Deduplication → Storage efficiency
- SnapMirror → DR strategy
