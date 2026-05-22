# Security Verified Candidate Review

## Meeting Details

- **Date**: YYYY-MM-DD
- **Integration**: [e.g., Athena + Parquet Read]
- **Participants**:
  - Storage SA: 
  - Security reviewer: 
  - Data/Analytics reviewer: 

## Scope

- Platform: 
- Format: 
- Mode: 
- Access Point origin: 
- File system user: 

## Evidence Reviewed

| Evidence | Location | Status |
|----------|----------|--------|
| Functional test result | `evidence/YYYY-MM-DD/evidence-record.yaml` | |
| Negative test result | `evidence/YYYY-MM-DD/negative-test-result.yaml` | |
| CloudTrail events | `evidence/YYYY-MM-DD/cloudtrail-events.json` | |
| IAM policy | `evidence/YYYY-MM-DD/iam-policy.json` | |
| AP policy | `evidence/YYYY-MM-DD/ap-policy.json` | |
| Benchmark result | `evidence/YYYY-MM-DD/benchmark-result.yaml` | |

## Decision

- [ ] **Pass** — All criteria met; promote to Security Verified
- [ ] **Pass with conditions** — Promote with documented conditions
- [ ] **Fail** — Criteria not met; remediation required

## Critical Negative Test Results

| Test | Expected | Actual | Denial Layer | Pass? |
|------|----------|--------|:---:|:---:|
| NEG-001 Write by read-only user | AccessDenied | | | |
| NEG-002 Delete by read-only user | AccessDenied | | | |
| NEG-003 Cross-account access | AccessDenied | | | |
| NEG-004 Internet access to VPC-origin AP | AccessDenied | | | |

## Open Issues

| # | Issue | Severity | Resolution Required? |
|---|-------|----------|:---:|
| 1 | | | |

## Conditions (if Pass with conditions)

- 

## Known Limitations (accepted)

- 

## Reviewer Sign-off

| Reviewer | Role | Decision | Date |
|----------|------|----------|------|
| | Storage SA | | |
| | Security reviewer | | |
| | Data/Analytics reviewer | | |
