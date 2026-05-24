# Lake Formation Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Add fine-grained governance (table/column-level access control) on top of FSx for ONTAP
S3 Access Point data using AWS Lake Formation. Enables regulated industry deployments.

## Status: ✅ Functional Verified (2026-05-24)

- Lake Formation admin configured
- Table-level SELECT-only permission verified
- Athena query under LF governance: PASS
- 4-layer authorization confirmed

## Architecture

```
User/Role
    │
    ▼
Lake Formation (table/column permissions)
    │
    ▼
Glue Data Catalog (table metadata)
    │
    ▼
S3 Access Point (IAM + AP policy)
    │
    ▼
FSx for ONTAP (file system user permissions)
```

**4-layer authorization**:
1. Lake Formation: Who can access which tables/columns
2. IAM: Who can call which APIs
3. S3 AP Policy: Which principals can access this access point
4. File System: UNIX permissions on underlying files

## Governance Value

| Capability | Benefit |
|-----------|---------|
| Table-level access | Grant SELECT on specific tables without modifying S3 AP policy |
| Column-level security | Mask sensitive columns (PHI, PII) per role |
| Tag-based access control | Classify data, auto-grant by tag |
| Centralized audit | Who accessed what table, when |
| Cross-account sharing | Share tables without sharing S3 AP |

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ❌ | N/A (governance layer for structured tables) | — |
| Video (MP4, MOV) | ❌ | N/A | — |
| Documents (PDF, DOCX) | ❌ | N/A | — |
| Audio (WAV, MP3) | ❌ | N/A | — |
| Binary / Archives | ❌ | N/A | — |

Lake Formation provides governance over Glue Data Catalog tables. It cannot directly govern unstructured data files, but can apply access control to metadata tables that reference unstructured files.

**Governance pattern for unstructured file metadata:**
1. **Metadata table governance** — Apply column-level security to tables containing file paths
2. **Tag-based access control** — Auto-grant access based on file type or sensitivity tags
3. **Audit** — Centralized logging of who accessed which file metadata
4. **Cross-account sharing** — Share file catalog tables without modifying S3 AP policy

```sql
-- Query file catalog protected by Lake Formation
-- (column-level security masks sensitive file paths by role)
SELECT file_path, file_type, file_size
FROM fsxn_db.file_catalog
WHERE classification = 'public';
```

## Quick Start

```bash
# 1. Set Lake Formation admin
aws lakeformation put-data-lake-settings \
  --data-lake-settings '{"DataLakeAdmins":[{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT>:user/<ADMIN>"}]}'

# 2. Grant table permissions
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier":"<ROLE_ARN>"}' \
  --resource '{"Table":{"DatabaseName":"<DB>","Name":"<TABLE>"}}' \
  --permissions "SELECT" "DESCRIBE"

# 3. Query via Athena (permissions enforced)
aws athena start-query-execution \
  --query-string "SELECT * FROM <DB>.<TABLE> LIMIT 10"
```

## Use Cases (Regulated Industries)

| Industry | Pattern |
|----------|---------|
| Healthcare | Column-level masking of PHI fields |
| Finance | Table-level segregation per business domain |
| Public sector | Tag-based classification enforcement |
