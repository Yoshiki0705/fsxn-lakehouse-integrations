# Databricks Verification Evidence

## Structure

```
verification-pack/databricks/
├── uc-external-location/       # Unity Catalog External Location test evidence
├── instance-profile-boto3/     # Instance Profile + boto3 PoC evidence
├── nfs-mount/                  # NFS mount investigation evidence
└── support-case-packet/        # Support case documentation
```

## Evidence Recording

Each test should produce a YAML evidence record:

```yaml
test_id: "DBX-S3AP-UC-001"
runtime: "DBR 17.3 LTS"
workspace_type: "customer-managed-vpc"
cluster_mode: "dedicated"
result: "fail"
error_signature: "no session policy allows s3:ListBucket"
evidence_file: "..."
```

## Current Status

| Test Path | Result | Date |
|-----------|--------|------|
| UC External Location | ❌ Blocked (session policy) | 2026-05-17 |
| Instance Profile + boto3 (driver) | ✅ Pass | 2026-05-17 |
| Kernel NFS mount | ❌ Blocked (runtime seccomp) | 2026-05-17 |
| User-space NFS RPC | ✅ Pass (experimental) | 2026-05-17 |
| Executor-scale boto3 | 🔲 Not yet validated | — |
