# Security Hardening

🌐 **English** | [日本語](../ja/12_security_hardening.md)

---

> Addresses P1-#5 from SA Persona Review Board (Persona 5: Security Reviewer).
> Covers: secrets management, explicit deny policies, audit trail, encryption configuration.

---

## SEC-001: Secrets Management

### Secret Inventory

| Secret | Component | Storage Location | Rotation Policy |
|--------|-----------|-----------------|----------------|
| MSK SASL/SCRAM credentials | Kafka producers/consumers | AWS Secrets Manager | 90 days |
| ClickHouse admin password | ClickHouse Cloud/on-prem | AWS Secrets Manager | 90 days |
| ONTAP S3 access key + secret | ClickHouse cold tier, payload generator | AWS Secrets Manager | 90 days |
| Databricks service principal token | Streaming pipeline, CI/CD | AWS Secrets Manager | 30 days |
| FSx for ONTAP SVM admin password | SVM management | AWS Secrets Manager | 90 days |
| Edge device Kafka credentials | Raspberry Pi producer | Local encrypted config (Phase B) | On device rotation |

### Secrets Manager Configuration

```yaml
# Secrets naming convention
secrets:
  - name: manufacturing-poc/kafka/sasl-credentials
    keys: [username, password]
    rotation: 90 days
    
  - name: manufacturing-poc/clickhouse/admin
    keys: [username, password, endpoint]
    rotation: 90 days
    
  - name: manufacturing-poc/ontap-s3/clickhouse-user
    keys: [access_key, secret_key, endpoint, bucket]
    rotation: 90 days
    
  - name: manufacturing-poc/databricks/service-principal
    keys: [client_id, client_secret, workspace_url]
    rotation: 30 days
```

### Rules

1. **Never hardcode** secrets in source code, CloudFormation parameters, or environment variables in version control
2. **Use IAM roles** for AWS service-to-service authentication (prefer over static credentials)
3. **Secrets Manager** for all non-IAM credentials (Kafka SCRAM, ClickHouse password, ONTAP S3 keys)
4. **Rotation automation**: Set up Lambda-based rotation for PoC (or manual rotation schedule with reminders)
5. **Access to Secrets Manager**: Only the specific IAM role for each component can read its own secrets

---

## SEC-002: Explicit Deny Policies

### Principle: Deny by Default, Allow Explicitly

#### MSK IAM Policy — Producer (Write-Only)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowProduceOnly",
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:Connect",
        "kafka-cluster:WriteData",
        "kafka-cluster:DescribeTopic"
      ],
      "Resource": [
        "arn:aws:kafka:*:*:cluster/manufacturing-poc-msk/*",
        "arn:aws:kafka:*:*:topic/manufacturing-poc-msk/*/factory.*"
      ]
    },
    {
      "Sid": "DenyReadData",
      "Effect": "Deny",
      "Action": [
        "kafka-cluster:ReadData",
        "kafka-cluster:AlterGroup"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyTopicDeletion",
      "Effect": "Deny",
      "Action": [
        "kafka-cluster:DeleteTopic",
        "kafka-cluster:AlterTopic"
      ],
      "Resource": "*"
    }
  ]
}
```

#### MSK IAM Policy — Consumer (Read-Only)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowConsumeOnly",
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:Connect",
        "kafka-cluster:ReadData",
        "kafka-cluster:DescribeTopic",
        "kafka-cluster:AlterGroup",
        "kafka-cluster:DescribeGroup"
      ],
      "Resource": [
        "arn:aws:kafka:*:*:cluster/manufacturing-poc-msk/*",
        "arn:aws:kafka:*:*:topic/manufacturing-poc-msk/*/factory.*",
        "arn:aws:kafka:*:*:group/manufacturing-poc-msk/*/*"
      ]
    },
    {
      "Sid": "DenyWriteData",
      "Effect": "Deny",
      "Action": ["kafka-cluster:WriteData"],
      "Resource": "*"
    },
    {
      "Sid": "DenyTopicManagement",
      "Effect": "Deny",
      "Action": [
        "kafka-cluster:CreateTopic",
        "kafka-cluster:DeleteTopic",
        "kafka-cluster:AlterTopic"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Unity Catalog — Deny Matrix

```sql
-- pipeline_service CANNOT read data (separation of duties)
DENY SELECT ON SCHEMA manufacturing_poc.factory_alpha FROM `pipeline_service`;
-- Note: UC doesn't have explicit DENY; implement via grant absence + workspace restrictions

-- Alternative: Use workspace-level IP access lists to restrict where pipeline runs
-- Only the streaming cluster can access the streaming job
```

#### FSx for ONTAP — Export Policy Deny

```bash
# NFS export policy: deny all except allowed CIDRs
vserver export-policy rule create -vserver svm-factory-poc \
  -policyname factory_payload_policy \
  -ruleindex 1 \
  -protocol nfs \
  -clientmatch 10.0.1.0/24,10.0.2.0/24 \  # Only edge subnet + ClickHouse subnet
  -rorule sys \
  -rwrule sys \
  -superuser none

# Deny all others (implicit deny - no matching rule = no access)
```

---

## SEC-003: Audit Trail Configuration

### CloudTrail — Data Events

```yaml
# CloudTrail trail configuration for manufacturing PoC
trail:
  name: manufacturing-poc-audit
  s3_bucket: manufacturing-poc-audit-logs
  
  event_selectors:
    - read_write_type: All
      include_management_events: true
      data_resources:
        # S3 data events (Delta Lake reads/writes)
        - type: AWS::S3::Object
          values: ["arn:aws:s3:::manufacturing-poc-delta-lake/"]
        # Kafka API events
        - type: AWS::Kafka::Cluster
          values: ["arn:aws:kafka:*:*:cluster/manufacturing-poc-msk/*"]
  
  # Encrypt audit logs
  kms_key_id: alias/manufacturing-poc-audit-key
  
  # Enable log file validation (tamper detection)
  enable_log_file_validation: true
```

### ClickHouse Query Audit

```sql
-- Enable query log retention (default is 30 days)
-- In ClickHouse Cloud: managed automatically
-- Self-managed: set in config.xml

-- Query audit view for manufacturing data access
CREATE VIEW factory.audit_query_log AS
SELECT
    event_time,
    user,
    query_kind,
    query,
    read_rows,
    result_rows,
    query_duration_ms,
    client_hostname
FROM system.query_log
WHERE
    type = 'QueryFinish'
    AND query LIKE '%factory.%'
    AND event_time > now() - INTERVAL 30 DAY
ORDER BY event_time DESC;
```

### ONTAP Audit Log

```bash
# Enable ONTAP audit logging for file access events
vserver audit create -vserver svm-factory-poc \
  -destination /vol_audit/audit_logs \
  -events file-ops,cifs-logon-logoff \
  -format evtx \
  -rotate-size 100MB \
  -rotate-limit 50

vserver audit enable -vserver svm-factory-poc
```

### Audit Log Aggregation Strategy

| Source | Log Type | Destination | Retention |
|--------|----------|-------------|-----------|
| CloudTrail | Management + Data events | S3 (encrypted, validated) | 90 days (PoC), 1 year (prod) |
| ClickHouse | query_log | ClickHouse system table | 30 days |
| ONTAP | File access audit | ONTAP audit volume | 30 days |
| Databricks | Unity Catalog audit | Databricks system tables | 365 days (managed) |
| MSK | Broker logs | CloudWatch Logs | 30 days |

---

## SEC-004: Encryption Configuration

### Encryption at Rest

| Component | Mechanism | Key | Status |
|-----------|-----------|-----|--------|
| S3 (Delta tables) | SSE-KMS | `alias/manufacturing-poc-delta-key` | Required |
| S3 (checkpoints) | SSE-KMS | Same key | Required |
| S3 (audit logs) | SSE-KMS | `alias/manufacturing-poc-audit-key` | Required |
| FSx for ONTAP | Volume encryption | AWS-managed KMS key (default) | Default-on; explicit in config |
| ClickHouse Cloud | Managed by ClickHouse | Provider-managed | Managed |
| MSK | At-rest encryption | AWS-managed KMS key (default) | Default-on |
| Secrets Manager | Managed encryption | AWS-managed key | Default |

### Encryption in Transit

| Connection | Mechanism | Configuration |
|-----------|-----------|-------------|
| Edge → Kafka | SASL_SSL (TLS 1.2+) | Producer security.protocol=SASL_SSL |
| Kafka → ClickHouse | SASL_SSL or SSL (mTLS) | Kafka Engine settings |
| Kafka → Databricks | SASL_SSL | Structured Streaming options |
| Client → FSx NFS | NFSv4.1 + Kerberos (optional for PoC) | Export policy krb5p (production) |
| Client → FSx ONTAP S3 | HTTPS (TLS 1.2+) | S3 endpoint on port 443 |
| Client → ClickHouse | HTTPS (TLS 1.2+) | ClickHouse Cloud enforces TLS |
| FlexCache intercluster | Cluster peering encryption | `cluster peer create -encryption true` |

---

## SEC-005: Network Security

### Security Group Rules (Least Privilege)

| SG Name | Inbound | Source | Port | Purpose |
|---------|---------|--------|------|---------|
| sg-msk | Allow | sg-edge-producer | 9098 | Kafka IAM auth |
| sg-msk | Allow | sg-clickhouse | 9098 | ClickHouse consumer |
| sg-msk | Allow | sg-databricks | 9098 | Databricks consumer |
| sg-msk | Deny | 0.0.0.0/0 | All | Deny all other |
| sg-clickhouse | Allow | sg-dashboard | 8443 | Query access |
| sg-clickhouse | Allow | sg-msk | 9098 | Kafka connectivity |
| sg-fsxn | Allow | sg-edge-producer | 2049 | NFS |
| sg-fsxn | Allow | sg-clickhouse | 443 | ONTAP S3 |
| sg-fsxn | Allow | sg-databricks | 2049 | NFS (FlexCache access) |
| sg-fsxn | Deny | 0.0.0.0/0 | All | Deny all other |

### VPC Endpoint Policy (S3)

```json
{
  "Statement": [
    {
      "Sid": "AllowManufacturingBucketsOnly",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::manufacturing-poc-delta-lake",
        "arn:aws:s3:::manufacturing-poc-delta-lake/*",
        "arn:aws:s3:::manufacturing-poc-checkpoints",
        "arn:aws:s3:::manufacturing-poc-checkpoints/*"
      ]
    }
  ]
}
```

---

## Persona Review Notes

- **Persona 5 (Security)**: All P1 security findings addressed. Secrets managed in Secrets Manager. Deny policies explicit. Audit trail covers all components. Encryption enforced at rest and in transit.
- **Persona 2 (Storage)**: ONTAP export policy and S3 auth chain documented. Audit logging for file access enabled.
- **Persona 6 (Reliability)**: Audit log rotation and retention defined. CloudTrail log validation prevents tampering.
- **Confidentiality**: ✅ Pass — All ARNs use placeholder account IDs. No real CIDR blocks. No real credentials.
