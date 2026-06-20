🌐 **English** | [日本語](../ja/verification-plan-clickhouse-uc-connectivity.md)

# Live Verification Phase Plan: ClickHouse `DataLakeCatalog` → Unity Catalog (Beta) + Network (NCC / SG / endpoints)

> **Status**: Plan (2026-06-18). Phase A0/B0 gate check **executed read-only** (2026-06-18) → mostly **BLOCKED** (no ClickHouse Cloud / Databricks credentials). A1+ and B1+ start once credentials are available.
> **Scope**: phases the unverified items from the [connectivity document](./kafka-clickhouse-unity-catalog-connectivity.md).
> **Approach**: each phase has Objective / Prerequisites / Gate / Steps / Expected result / Evidence / Cost / Cleanup. Follows the reproducible-evidence convention.
> **Note**: no individual or company names. Account ID / workspace URL / SG ID, etc., are **placeholders** (`<...>`). CLI/SQL are **templates**; for Beta features, confirm syntax against current official docs.
> **Safety**: throwaway, least-privilege, always clean up after verification. Do not modify existing production resources.

---

## 0. Overview and common prerequisites

| Track | Objective | Main prerequisites |
|-------|-----------|--------------------|
| **Track A** | Verify on real systems that ClickHouse `DataLakeCatalog` (Beta) can read UC tables | Databricks UC + external data access enabled, ClickHouse Cloud, a test UC table |
| **Track B** | Verify the Kafka→Databricks path (NCC/SG/ports) and ClickHouse→S3 path (VPC endpoint) | Databricks serverless, existing MSK, VPC/SG/endpoint permissions |

**Environment note (grounding, read-only check on 2026-06-18)**: the verification account has an **existing provisioned MSK cluster** (no new Kafka source needed for Track B) and **S3 Gateway VPC endpoints across multiple VPCs**. Specific IDs are placeholdered here.

**Cost/safety principles**:
- Track A: keep the test UC table small. Use a minimal, short-lived ClickHouse Cloud warehouse.
- Track B: use the existing MSK (do not create a new one). NCC is largely free, but PrivateLink endpoints are billed. Revoke SG rules after verification.
- Record all evidence as YAML under `verification-evidence/<date>/` (existing convention).

---

## Track A: ClickHouse `DataLakeCatalog` → Unity Catalog (Beta)

### Phase A0: Prerequisites / gate
- **Gate (BLOCKED if unmet)**:
  - A ClickHouse Cloud version/region that supports `DataLakeCatalog` (`catalog_type='unity'`) Beta
  - **External data access enabled** on the Databricks metastore
  - An auth principal (service principal or PAT) and UC privileges (`SELECT` + external-use grant)
- **Evidence**: a gate-satisfaction checklist

### Phase A1: UC-side setup
- **Steps (template)**:
  ```sql
  -- Databricks SQL (UC side)
  CREATE CATALOG IF NOT EXISTS ext_demo;
  CREATE SCHEMA IF NOT EXISTS ext_demo.s;
  CREATE TABLE ext_demo.s.t (id INT, v STRING) USING DELTA;
  INSERT INTO ext_demo.s.t VALUES (1,'a'),(2,'b');
  -- Grants for external engines (credential vending)
  GRANT SELECT ON TABLE ext_demo.s.t TO `<principal>`;
  GRANT EXTERNAL USE SCHEMA ON SCHEMA ext_demo.s TO `<principal>`;
  ```
  - Enable external data access as a metastore setting (account console / API).
- **Expected result**: table creation + grants succeed.
- **Evidence**: `DESCRIBE EXTENDED`, grant listing.

### Phase A2: Configure ClickHouse `DataLakeCatalog` (type: unity)
- **Steps (template; confirm against current ClickHouse docs)**:
  ```sql
  -- ClickHouse Cloud
  CREATE DATABASE uc_demo
  ENGINE = DataLakeCatalog
  SETTINGS
    catalog_type = 'unity',
    warehouse = '<catalog>',
    catalog_credential = '<oauth-token-or-sp>',
    storage_endpoint = '<workspace-url>/api/2.1/unity-catalog/iceberg-rest';
  ```
- **Expected result**: `uc_demo` appears in `SHOW DATABASES`.
- **Evidence**: connection success/failure, ClickHouse server log (DataLakeCatalog connection line).
- **Gate**: syntax/settings keys are Beta — align with the [ClickHouse Unity Catalog docs](https://clickhouse.com/docs/use-cases/data-lake/unity-catalog).

### Phase A3: Read verification
- **Steps**:
  ```sql
  SHOW TABLES FROM uc_demo;
  SELECT count() FROM uc_demo.`ext_demo.s.t`;
  SELECT * FROM uc_demo.`ext_demo.s.t` LIMIT 10;
  ```
- **Expected result**: row count = the rows inserted in Phase A1.
- **Evidence**: row count, query latency, `EXPLAIN`.

### Phase A4: Iceberg path (type: rest)
- **Objective**: verify the path that reads UC as an Iceberg REST catalog (`catalog_type='rest'`).
- **Expected result**: the same table is readable as Iceberg.
- **Evidence**: results match the Delta path (A3).

### Phase A5: Governance verification
- **Steps**:
  - Query a non-granted table → confirm **AccessDenied** (least-privilege effectiveness).
  - Observe credential-vending **TTL/scope** (credential expiry).
  - Confirm external-engine reads appear in UC audit logs (`system.access.audit`, etc.).
- **Expected result**: non-granted denied, granted succeeds, audit records present.
- **Evidence**: denial response, audit log line, observed TTL.

### Phase A6: Cleanup
- ClickHouse: `DROP DATABASE uc_demo;`
- UC: `DROP TABLE/SCHEMA/CATALOG ext_demo...;` revoke grants.
- Stop the ClickHouse Cloud warehouse.

---

## Track B: Network (NCC / SG / endpoints)

### Phase B0: Prerequisites / gate
- **Gate**: Databricks **serverless** workspace, NCC region availability, SG/endpoint change permissions, existing MSK bootstrap info.

### Phase B1: Kafka→Databricks private path (NCC + MSK SG)
- **Steps (template)**:
  ```bash
  # Databricks account CLI: create NCC → attach to workspace (stable egress / PrivateLink)
  databricks account network-connectivity-configs create \
    --json '{"name":"<ncc-name>","region":"ap-northeast-1"}'
  # Allow Databricks egress on the MSK broker SG (example: IAM auth = 9098)
  aws ec2 authorize-security-group-ingress --region ap-northeast-1 \
    --group-id <msk-broker-sg> --protocol tcp --port 9098 --cidr <databricks-egress-cidr>
  ```
  ```python
  # Databricks notebook: Structured Streaming read from the existing MSK (IAM auth)
  df = (spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", "<bootstrap-brokers:9098>")
        .option("kafka.security.protocol", "SASL_SSL")
        .option("subscribe", "<topic>").load())
  ```
- **Expected result**: messages received over the private path → written to a UC-managed Delta table.
- **Evidence**: record count, path (via NCC/PrivateLink), SG rules.
- **Ports**: private TLS 9094 / SCRAM 9096 / IAM 9098.

### Phase B2: ClickHouse→S3 VPC endpoint path
- **Objective**: whether ClickHouse → S3 data reads can go via a VPC endpoint (self-managed case). Distinguish ClickHouse Cloud (SaaS egress, different path).
- **Steps**: confirm the route of the existing S3 Gateway endpoint (for self-managed ClickHouse).
  ```bash
  aws ec2 describe-vpc-endpoints --region ap-northeast-1 \
    --filters Name=service-name,Values=com.amazonaws.ap-northeast-1.s3 \
    --query 'VpcEndpoints[].{id:VpcEndpointId,vpc:VpcId}'
  ```
- **Expected result**: self-managed ClickHouse reads via the S3 endpoint. ClickHouse Cloud uses the SaaS path (verify PrivateLink options).
- **Evidence**: route table, S3 access logs.

### Phase B3: Connectivity / port verification
- **Steps**:
  ```bash
  nc -zv <bootstrap-broker> 9098    # MSK IAM (private)
  nc -zv <workspace-host> 443        # Databricks UC REST
  ```
- **Expected result**: only allowed ports reachable, others blocked.
- **Evidence**: nc results, SG rule table.

### Phase B4: Cleanup
- Revoke SG rules; delete the verification NCC if not needed; delete test topics/tables.

---

## Gate summary (BLOCKED conditions)

| Gate | Affected track | How to satisfy |
|------|----------------|----------------|
| ClickHouse Cloud `DataLakeCatalog` (unity, Beta) support | A | Confirm supported version/region |
| UC external data access enabled | A | Metastore setting |
| Serverless workspace | B | Confirm workspace type |
| NCC region availability | B | Confirm region |
| SG/endpoint change permission | B | IAM permission |

---

## Evidence recording

Record each phase's results as YAML under `integrations/manufacturing-data-platform/verification-evidence/<YYYY-MM-DD>/` (per existing convention). Fields: timestamp, environment (region/version), steps, expected result, actual result (pass/fail/limitation), log excerpts, cleanup confirmation.

### Reproducible gate check (read-only)

Phase A0/B0 gate satisfaction can be checked with a reproducible script (read-only, no credentials required, no billable resources created):

```bash
# Default region ap-northeast-1. Connection hints can be passed via env vars.
bash integrations/manufacturing-data-platform/poc/infrastructure/gate-check-uc-connectivity.sh
```

- Prints each gate as `MET` / `NOT MET / BLOCKED` and counts the blocked ones.
- Outputs only "tool presence / connection-hint presence / MSK & endpoint counts" (no account-specific IDs are hardcoded in the script).

**Recorded run (2026-06-18)**: `verification-evidence/2026-06-18/gate-check-clickhouse-uc-connectivity.yaml`
- Track A = **BLOCKED** (no ClickHouse Cloud + no Databricks auth).
- Track B = **PARTIAL** (existing MSK cluster ACTIVE, SASL/IAM+SCRAM, private-only, TLS in transit; 5 S3 Gateway endpoints confirmed read-only — but NCC/connectivity tests not run because no Databricks serverless workspace).

---

## References
- [Connectivity document (Kafka/ClickHouse → UC)](./kafka-clickhouse-unity-catalog-connectivity.md)
- [ClickHouse: Unity Catalog integration](https://clickhouse.com/docs/use-cases/data-lake/unity-catalog)
- [Databricks: External data access for pipelines](https://docs.databricks.com/aws/en/external-access/external-for-pipelines)
- [Databricks: Kafka authentication (UC service credentials)](https://docs.databricks.com/aws/en/connect/streaming/kafka/authentication)
- [Amazon MSK: Port information](https://docs.aws.amazon.com/msk/latest/developerguide/port-info.html)

> Source descriptions are paraphrased/summarized for licensing compliance.
