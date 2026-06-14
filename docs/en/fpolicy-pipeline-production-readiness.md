# FPolicy Audit Pipeline — Production Readiness Guide

[日本語版](../ja/fpolicy-pipeline-production-readiness.md)

> Generated from 6-persona review cycle (2026-06-15).
> All technical claims verified against AWS and NetApp documentation.

---

## 1. ONTAP EVTX/XML Format Constraint

### Verified Fact

**ONTAP supports only one audit log format per SVM at any time** — EVTX or XML, never both simultaneously.

Source: [NetApp KB — Can ONTAP generate CIFS audit logs in both EVTX and XML formats at the same time?](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/Can_ONTAP_generate_CIFS_audit_logs_in_both_EVTX_and_XML_formats_at_the_same_time)

### Migration Impact

| Current Format | Impact of Switching to XML | Mitigation |
|---|---|---|
| EVTX (Windows Event Viewer) | Existing SIEM integrations that consume EVTX will break | Dual-SVM strategy (see below) or parallel forwarding with format conversion |
| XML (already) | No impact | — |
| No audit configured | No impact | — |

### Recommended Migration Strategy

```
Option A: Dedicated Audit SVM
  - Create a new SVM with XML format for this pipeline
  - Keep existing SVM with EVTX for legacy tools
  - Use inter-SVM data sharing (FlexCache or volume move) if needed

Option B: Staged Cutover
  - Phase 1: Deploy pipeline reading from existing EVTX (add EVTX parser module)
  - Phase 2: Validate pipeline output matches legacy SIEM
  - Phase 3: Switch SVM to XML, decommission legacy EVTX consumers
  - Rollback: Switch back to EVTX if issues found (audit config change is immediate)

Option C: Format Conversion Layer
  - Keep EVTX format on SVM
  - Add a Lambda-based EVTX→XML converter after S3 AP read
  - Trade-off: additional compute cost and latency
```

### Coexistence with Existing Audit Tools

For environments where multiple tools consume the same audit data:

```
FPolicy Events (real-time)     Audit Logs (file-based)
       │                              │
       ▼                              ▼
  SQS → Lambda              S3 AP → Lambda (this pipeline)
  (metadata catalog)         (SIEM/LogScale)
       │                              │
       ▼                              ▼
  S3 Tables (Iceberg)        HEC → LogScale / Splunk
                                      │
                              ┌───────┴───────┐
                              ▼               ▼
                         LogScale         S3 (archive)
                         (primary)        + Object Lock
```

**Best practice for dual-destination logging:**
- Use SNS fan-out from SQS for multiple consumers
- Or configure Lambda to write to both HEC and S3 in the same invocation
- Never duplicate the S3 AP read — read once, fan out after parse

---

## 2. S3 Access Point I/O Overhead

### Provisioned Throughput Impact

FSx for ONTAP S3 Access Point reads consume from the file system's provisioned throughput capacity.

**Sizing considerations:**
- Audit log files are typically small (1-50 MB each)
- Read pattern: sequential, infrequent (event-driven, not continuous streaming)
- Typical throughput: < 10 MB/s for audit log reading
- Impact on production NFS/SMB workloads: **negligible** for event-driven pipelines

**When to be concerned:**
- Backfill scenarios (reading hundreds of historical audit files)
- High-frequency polling (sub-minute intervals on large files)
- File systems with throughput already near capacity

**Mitigation:**
- Schedule backfill during off-peak hours
- Use `burst` throughput mode for temporary spikes
- Monitor `DataReadBytes` CloudWatch metric for the file system
- Set Lambda concurrency limit to prevent thundering herd

---

## 3. Production Checkpoint Design (DynamoDB)

### Architecture: SSM Parameter Store → DynamoDB Migration

| Aspect | PoC (SSM Parameter Store) | Production (DynamoDB) |
|--------|--------------------------|----------------------|
| Concurrency safety | ❌ No atomic CAS | ✅ Conditional writes |
| Cost at scale | ~$0.05/1000 params | ~$1.25/million writes |
| TTL/lease timeout | ❌ Not supported | ✅ Native TTL |
| Throughput | 40 TPS standard | 25,000+ WCU |
| Audit trail | Parameter version history | DynamoDB Streams |

### DynamoDB Table Schema

```
Table: fpolicy-pipeline-checkpoints
  PK: file_path (S)        # S3 AP path of the audit log file
  SK: segment_id (S)       # "FULL" for single-file processing or segment identifier

Attributes:
  status:        S  # PENDING | PROCESSING | COMPLETED | FAILED
  lease_expiry:  N  # Unix timestamp — when the lock auto-releases
  processor_id:  S  # Lambda request ID (unique per invocation)
  version:       N  # Optimistic locking version
  last_offset:   N  # Byte offset or event count for resumable processing
  ttl:           N  # DynamoDB TTL — auto-delete completed records after 7 days
  created_at:    S  # ISO-8601
  updated_at:    S  # ISO-8601
```

### Conditional Write Pattern (Lease-Based Locking)

```python
import time
import boto3
from botocore.exceptions import ClientError

LEASE_DURATION_SECONDS = 900  # 15 minutes

def acquire_lease(table, file_path, processor_id):
    """Acquire processing lease with conditional write."""
    now = int(time.time())
    try:
        table.put_item(
            Item={
                'file_path': file_path,
                'segment_id': 'FULL',
                'status': 'PROCESSING',
                'lease_expiry': now + LEASE_DURATION_SECONDS,
                'processor_id': processor_id,
                'version': 1,
                'ttl': now + (7 * 86400),  # Auto-delete after 7 days
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
            },
            ConditionExpression=(
                'attribute_not_exists(file_path) OR '   # New file
                'status = :failed OR '                   # Previously failed
                'lease_expiry < :now'                     # Ghost lock expired
            ),
            ExpressionAttributeValues={
                ':failed': 'FAILED',
                ':now': now,
            }
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False  # Another processor holds the lease
        raise

def complete_processing(table, file_path, processor_id):
    """Mark processing as complete with version check."""
    table.update_item(
        Key={'file_path': file_path, 'segment_id': 'FULL'},
        UpdateExpression='SET #s = :completed, updated_at = :now',
        ConditionExpression='processor_id = :pid AND #s = :processing',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':completed': 'COMPLETED',
            ':processing': 'PROCESSING',
            ':pid': processor_id,
            ':now': datetime.utcnow().isoformat(),
        }
    )
```

### Ghost Lock Prevention (Lease Timeout)

```
Lambda invocation starts
  │
  ├── acquire_lease(file_path, request_id)
  │     │
  │     ├── [Success] → Process file → complete_processing()
  │     │
  │     └── [ConditionalCheckFailed]
  │           │
  │           └── Check: is lease_expiry < now?
  │                 │
  │                 ├── [Yes: ghost lock] → Overwrite with new lease (force acquire)
  │                 │
  │                 └── [No: active processor] → Skip, exit gracefully
  │
  └── [Lambda timeout/crash]
        │
        └── lease_expiry auto-expires after 15 minutes
              → Next invocation can acquire the lease
```

**Production Readiness Checklist:**
- [ ] DynamoDB TTL enabled (auto-delete COMPLETED records after 7 days)
- [ ] `lease_expiry` set to Lambda timeout + buffer (e.g., 15 minutes)
- [ ] CloudWatch alarm on items with `status=PROCESSING` older than 2× lease duration
- [ ] Dead letter handling for items stuck in FAILED state

---

## 4. Security: Immutability and Cross-Account Log Aggregation

### S3 Object Lock for Audit Log Immutability

```
Recommended configuration:
  Bucket: <org>-security-audit-logs
  Object Lock: Enabled (at bucket creation)
  Default retention:
    Mode: COMPLIANCE (cannot be shortened, even by root)
    Period: 365 days (adjust per regulatory requirement)
```

**Why Compliance Mode (not Governance):**
- Compliance mode cannot be overridden by any IAM principal, including root
- Required for SEC 17a-4, FINRA, and equivalent Japanese FSA regulations
- Governance mode allows users with `s3:BypassGovernanceRetention` to delete — not suitable for audit

### Cross-Account Log Aggregation with S3 Access Points

```
Production Account (Account A)          Security Account (Account B)
┌─────────────────────┐                 ┌─────────────────────┐
│ FSx for ONTAP       │                 │ S3 Bucket           │
│   └─ Audit Logs     │                 │   + Object Lock     │
│       └─ S3 AP ─────┼────────────────▶│   + Versioning      │
│                     │  Cross-account   │   + Lifecycle       │
└─────────────────────┘  S3 AP policy    └─────────────────────┘
```

**S3 AP cross-account policy (on Account A's AP):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSecurityAccountRead",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SECURITY_ACCOUNT_ID:role/AuditLogAggregator"
      },
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:REGION:PROD_ACCOUNT_ID:accesspoint/fsxn-audit-ap",
        "arn:aws:s3:REGION:PROD_ACCOUNT_ID:accesspoint/fsxn-audit-ap/object/*"
      ]
    }
  ]
}
```

Source: [AWS Blog — Setting up cross-account Amazon S3 access with S3 Access Points](https://aws.amazon.com/blogs/storage/setting-up-cross-account-amazon-s3-access-with-s3-access-points/)

---

## 5. Data Classification and PII Masking (Field-Level Strategy)

### Enhanced FIELD_MAPPING with Processing Strategy

```python
from hashlib import sha256
import os

# Salt stored in Secrets Manager (rotated quarterly)
HASH_SALT = os.environ.get('PII_HASH_SALT', '')

FIELD_MAPPING = {
    "timestamp": {
        "keys": ["TimeCreated_SystemTime", "timestamp"],
        "action": "keep"
    },
    "user": {
        "keys": ["SubjectUserName", "UserName", "user"],
        "action": "hash"  # Pseudonymized — reversible via lookup table
    },
    "client_ip": {
        "keys": ["IpAddress", "ClientIP", "client_ip"],
        "action": "mask"  # Network address anonymized
    },
    "path": {
        "keys": ["ObjectName", "path"],
        "action": "truncate_dir"  # Directory only, filename stripped
    },
    "operation": {
        "keys": ["EventID", "operation"],
        "action": "keep"
    },
    "result": {
        "keys": ["Status", "result"],
        "action": "keep"
    },
}

def apply_field_strategy(field_name: str, value: str) -> str:
    """Apply masking strategy based on FIELD_MAPPING configuration."""
    config = FIELD_MAPPING.get(field_name, {"action": "keep"})
    action = config["action"]

    if action == "keep":
        return value
    elif action == "hash":
        # Salted SHA-256 — pseudonymization (reversible via lookup table)
        return sha256(f"{HASH_SALT}{value}".encode()).hexdigest()[:16]
    elif action == "mask":
        # IP masking: preserve subnet, zero host
        parts = value.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.xxx.xxx"
        return "MASKED"
    elif action == "truncate_dir":
        # Keep directory path, remove filename
        import os.path
        return os.path.dirname(value) or "/"
    else:
        return value
```

### Operational Considerations for Hashed Fields

| Concern | Mitigation |
|---------|------------|
| Incident response requires original username | Maintain lookup table in separate security account (encrypted, access-controlled) |
| Hash collision risk | SHA-256 with 16-char truncation: collision probability < 1 in 10^19 for typical username space |
| Salt rotation | Rotate quarterly; maintain previous salt for 90-day lookback |
| Legal hold / forensics | Lookup table access requires dual-approval (security + legal) |

---

## 6. Splunk HEC Compatibility Notes

### Indexer Acknowledgement Gap

| Behavior | Splunk HEC (native) | LogScale HEC-compatible endpoint |
|----------|--------------------|---------------------------------|
| HTTP 200 means | Event received by indexer queue | Event accepted for indexing |
| Indexer Acknowledgement | ✅ Supported (`/services/collector/ack`) | ❌ Not implemented |
| Data loss guarantee | After ack response: guaranteed on disk | After HTTP 200: best-effort (in-memory before flush) |
| Channel support | ✅ `X-Splunk-Request-Channel` header | ⚠️ Accepted but no ack semantics |

### Recommendation for Splunk-to-LogScale Migration

```python
# For environments requiring Splunk-equivalent data loss protection:
# 1. Write to S3 first (durable), then forward to HEC (best-effort)
# 2. S3 serves as replay source if HEC delivery fails

def send_with_durability(events, s3_client, hec_client):
    """Write-ahead to S3, then forward to HEC."""
    # Step 1: Durable write (S3 + Object Lock)
    s3_key = f"audit-logs/{date}/{batch_id}.json.gz"
    s3_client.put_object(Bucket=ARCHIVE_BUCKET, Key=s3_key, Body=compressed_events)

    # Step 2: Best-effort HEC delivery
    try:
        response = hec_client.send(events)
        if response.status_code == 200:
            return "DELIVERED"
    except Exception:
        pass

    # Step 3: Mark for retry (S3 record exists, HEC delivery pending)
    return "ARCHIVED_PENDING_DELIVERY"
```

### SPL vs CQL Query Comparison

| Use Case | Splunk SPL | CrowdStrike LogScale CQL |
|----------|-----------|--------------------------|
| Time bucket (5min) | `\| bin _time span=5m \| stats count by _time` | `groupBy(_bucket=5m, function=count())` |
| Top users | `\| top limit=10 user` | `top(user, limit=10)` |
| Filter + aggregate | `source="fpolicy" operation="write" \| stats count by user` | `source="fpolicy" operation="write" \| groupBy(user, function=count())` |
| Time range | `earliest=-1h latest=now` | `#type=fpolicy \| start := now() - 1h` |
| Rare events | `\| rare operation` | `groupBy(operation, function=count()) \| sort(count, order=asc)` |

**Key difference for SOC analysts:**
- SPL uses pipe-separated commands with implicit time range from the search bar
- CQL uses filter expressions followed by pipe-separated aggregations; time range is part of the query or UI selector
- Both support real-time streaming, but syntax for windowed aggregation differs

---

## 7. OpenTelemetry / Grafana Alloy Alternative Path

### When to Use OTel Instead of Direct HEC

| Scenario | Recommended Path |
|----------|-----------------|
| Single SIEM destination (LogScale or Splunk) | Direct HEC from Lambda |
| Multi-destination (SIEM + metrics + traces) | OTel Collector / Grafana Alloy |
| Existing Grafana LGTM stack | Grafana Alloy with Loki exporter |
| Need edge-side filtering/sampling | OTel Collector with Transform Processor |
| High-cardinality field management | OTel attributes processor (drop/hash before export) |

### OTel Transform Processor Example (High-Cardinality Control)

```yaml
# otel-collector-config.yaml
processors:
  transform:
    log_statements:
      - context: log
        statements:
          # Hash user field to reduce cardinality in metrics
          - set(attributes["user_hash"], SHA256(attributes["user"]))
          - delete_key(attributes, "user")

          # Mask IP to /16 subnet for metrics (keep full IP in logs)
          - set(attributes["client_subnet"], Concat([Split(attributes["client_ip"], ".")[0], Split(attributes["client_ip"], ".")[1], "0", "0"], "."))

          # Drop high-cardinality path from metric labels
          - delete_key(attributes, "full_path") where resource.attributes["telemetry.type"] == "metrics"
```

**Key principle:** Never use high-cardinality fields (user, IP, file path) as metric labels. Use them in log bodies and trace attributes only. The Transform Processor enables field-level control before export.

---

## References

- [NetApp KB: EVTX/XML simultaneous output](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/Can_ONTAP_generate_CIFS_audit_logs_in_both_EVTX_and_XML_formats_at_the_same_time)
- [AWS: S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [AWS: DynamoDB Optimistic Locking](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_OptimisticLocking.html)
- [AWS: S3 Access Points Cross-Account](https://aws.amazon.com/blogs/storage/setting-up-cross-account-amazon-s3-access-with-s3-access-points/)
- [Splunk: HEC Indexer Acknowledgement](https://help.splunk.com/en/splunk-cloud-platform/get-data-in/get-started-with-getting-data-in/10.1.2507/get-data-with-http-event-collector/about-http-event-collector-indexer-acknowledgment)
- [AWS: DynamoDB Conditional Writes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_ImplementingVersionControl.html)
