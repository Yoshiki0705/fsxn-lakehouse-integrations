# Verification Pack

## Purpose

Executable test suites and evidence records for FSx for ONTAP S3 Access Point integrations. Results stored here serve as the basis for Verification Level promotion decisions.

## Current Status

| Integration | Current Level | Target Level | Blocker |
|-------------|:---:|:---:|---------|
| Athena + Parquet Read | Functional Verified | Security Verified | Negative tests pending |

**Note**: No integration should be labeled "Production Validated" until tested with customer-representative data under production-equivalent load with operational monitoring in place.

## Directory Structure

```
verification-pack/
├── README.md                          # This file
├── athena-parquet-read/               # First verification target
│   ├── 01-functional-tests/           # Basic API and workflow tests
│   ├── 02-negative-tests/             # Must-fail security tests
│   ├── 03-benchmark/                  # Performance measurements
│   └── evidence/                      # Completed evidence records
└── templates/                         # Reusable templates
    ├── evidence-record.yaml
    ├── negative-test-result.yaml
    └── benchmark-record.yaml
```

## First Verification Target: Athena + Parquet Read

### Scope

| Item | Value |
|------|-------|
| Platform | Amazon Athena (engine v3) |
| Format | Apache Parquet (Snappy compression) |
| Mode | Read-only |
| Access Point | Internet-origin (required for Athena) |
| File System User | Read-only UNIX user |
| Catalog | AWS Glue Data Catalog |

### Tests Required for Security Verified

| Category | Tests | Pass Criteria |
|----------|-------|---------------|
| Functional | Glue Crawler registers table; Athena query returns correct results | All pass |
| Negative (Critical) | NEG-001 through NEG-004 | All denied as expected |
| Negative (High/Medium) | NEG-005 through NEG-010 | All denied/rejected as expected |
| Security evidence | CloudTrail data event captured for GetObject | Event present in trail |
| Benchmark | Large file sequential read | Throughput ≥ 70% of provisioned |

### Security Verified Promotion Decision

To promote from Functional Verified → Security Verified, ALL must be true:

- [ ] Functional tests passed
- [ ] All Critical negative tests passed (NEG-001 to NEG-004)
- [ ] All High/Medium negative tests passed (NEG-005 to NEG-010)
- [ ] No unexpected write/delete succeeded
- [ ] CloudTrail data event evidence captured
- [ ] AP policy and IAM policy documented in evidence record
- [ ] Benchmark completed with no blocking performance issue
- [ ] Known limitations documented
- [ ] Reviewer sign-off recorded

### What This Is NOT

- This is NOT "Production Validated" — that requires customer-representative data, production monitoring, and operational runbook execution under load.
- This is NOT a guarantee of compatibility with all Athena features — only the tested workflow is verified.

### Production Validated Promotion Criteria (Future)

To promote from Security Verified → Production Validated, ALL of the following additional conditions must be met:

- [ ] Tested with customer-representative data (size, format, file count)
- [ ] Production-equivalent monitoring and alerting configured
- [ ] Operational runbooks rehearsed under production-like conditions
- [ ] Operational owner formally assigned
- [ ] Customer or partner acceptance confirmation documented
- [ ] Known limitations reviewed and accepted by customer
- [ ] DR/recovery procedure tested (if applicable)

## How to Run

See individual test directories for execution instructions. Each test produces a YAML evidence record that should be committed to `evidence/`.

## Benchmark-to-Business KPI Mapping

| Benchmark Metric | Business KPI | Why It Matters |
|-----------------|-------------|----------------|
| Athena query latency | Time from analysis request to decision | Directly impacts analyst productivity |
| Data freshness (NFS write → S3 AP visible) | Operational data reflection delay | Determines if decisions are based on current data |
| Bedrock KB ingestion time | Knowledge update lead time | How quickly new documents become searchable |
| Query cost ($/TB scanned) | Cost per analytical insight | Budget planning for analytics operations |
| Access failure rate | Business continuity risk | Unplanned downtime impact |
| Throughput (MB/s) | Concurrent analyst capacity | Whether the team can run all needed analyses |
