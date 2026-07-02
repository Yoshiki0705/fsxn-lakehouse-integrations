# Databricks + FSx for ONTAP S3 AP Validation Delivery Plan

> This delivery plan is a template for teams conducting a controlled validation of Databricks integration with FSx for ONTAP S3 Access Points. Adapt phases and timelines to your environment.

## Phase 0: Readiness

**Duration**: 1–2 days  
**Owner**: Platform / Infrastructure team

- [ ] Confirm workspace type (Databricks-managed VPC or Customer-managed VPC)
- [ ] Confirm cluster access mode (Standard / Dedicated / Dedicated + Instance Profile)
- [ ] Confirm FSx for ONTAP S3 AP ARN and alias
- [ ] Confirm FSx SVM and volume configuration
- [ ] Confirm governance requirement (Unity Catalog mandatory? Lineage required?)
- [ ] Confirm IAM role and trust policy
- [ ] Confirm network connectivity (VPC, subnets, security groups, route tables)
- [ ] Confirm DBR version and Spark version
- [ ] Identify data owner, security owner, platform owner
- [ ] Define success criteria and Go / No-Go decision framework

## Phase 1: Baseline

**Duration**: 1–2 days  
**Owner**: Data Engineer / Platform Engineer

- [ ] Regular S3 bucket via Unity Catalog External Location → confirm success
- [ ] FSx for ONTAP S3 AP via Unity Catalog External Location → document result
- [ ] Instance Profile registration (if applicable)
- [ ] IMDS access verification
- [ ] Network connectivity tests (TCP 2049, 111, 635 if NFS path is in scope)
- [ ] Document baseline evidence in `evidence-template.yaml`

## Phase 2: Controlled PoC

**Duration**: 2–3 days  
**Owner**: Data Engineer

- [ ] Driver-only boto3 access to FSx for ONTAP S3 AP
- [ ] ListObjectsV2, GetObject, HeadObject operations
- [ ] Negative tests:
  - [ ] PutObject should fail (if read-only policy)
  - [ ] DeleteObject should fail
  - [ ] Unauthorized prefix access should fail
  - [ ] Cross-account access should fail (if applicable)
- [ ] Evidence capture (screenshots, logs, error messages)
- [ ] CloudTrail data event verification (if enabled)

## Phase 3: Executor-scale Validation

**Duration**: 2–3 days  
**Owner**: Data Engineer / Performance Engineer

- [ ] `mapPartitions` validation with boto3 from executors
- [ ] Per-executor JSONL evidence capture
- [ ] FSx throughput observation during distributed access
- [ ] Credential propagation verification across executors
- [ ] Concurrency and retry behavior documentation
- [ ] Latency and error rate measurement

## Phase 4: Decision

**Duration**: 1 day  
**Owner**: Architecture / Security / Data Owner

- [ ] Architecture recommendation document
- [ ] Governance exception review (if bypassing Unity Catalog)
- [ ] Security owner sign-off
- [ ] Data owner sign-off
- [ ] Platform owner sign-off
- [ ] Next action: proceed / adjust / stop
- [ ] If proceed: define production hardening requirements
- [ ] If stop: document alternative path (Athena, EMR, etc.)

---

## Roles and Responsibilities

| Role | Responsibility |
|------|---------------|
| Platform Engineer | Environment setup, network, IAM |
| Data Engineer | Validation execution, evidence capture |
| Security Owner | Governance exception review, approval |
| Data Owner | Data access approval, scope definition |
| Architecture Lead | Decision recommendation, risk assessment |

## Evidence Artifacts

All evidence should be captured in:
- `verification-pack/databricks/instance-profile-boto3/evidence-template.yaml`
- `verification-pack/databricks/support-case-packet/minimal-repro.md` (if support case needed)
- Per-executor JSONL logs (Phase 3)
- Screenshots and terminal output

## Go / No-Go Criteria

| Criteria | Go | No-Go |
|----------|:--:|:-----:|
| Driver boto3 access works | ✅ | — |
| Negative tests pass (unauthorized access denied) | ✅ | — |
| Governance exception approved | ✅ | ❌ |
| Executor-scale latency acceptable | ✅ | ❌ |
| FSx throughput within limits | ✅ | ❌ |
| Security review completed | ✅ | ❌ |
