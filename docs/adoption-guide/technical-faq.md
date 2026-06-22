🌐 **English** | [日本語](./technical-faq-ja.md)

# Technical FAQ: FSx for ONTAP AI Metadata Catalog

> Factual answers including limitations and constraints.

---

## General

### Q: Do files need to be copied?

**A:** No. The solution uses FSx for ONTAP's S3 Access Point to read file content in-place (zero-copy storage). Files never leave the FSx for ONTAP volume. Only extracted metadata is stored externally in S3 Tables.

**Clarification on "zero-copy storage":** File bytes are not duplicated to another storage location. However, during AI processing, file content is temporarily accessed in Lambda memory (ephemeral — not persisted outside the source FSx for ONTAP volume).

---

### Q: What security controls are in place?

**A:** Files remain on FSx for ONTAP with existing access controls (NFS/SMB permissions). Only metadata flows through the AI pipeline. Governance is enforced through:
- **AWS Lake Formation**: Fine-grained access control on metadata tables
- **AWS CloudTrail**: Full audit trail of all API calls
- **IAM Policies**: Least-privilege access to S3 Access Points and Bedrock
- **VPC Private Endpoints**: All traffic stays within the VPC

---

### Q: What is the approximate cost?

**A:** Approximately **$114/month** for 100,000 files with 1,000 daily changes (assuming 100KB–1MB average file size).

File-size-dependent Bedrock costs:
| File Size | Approx. Cost per File |
|-----------|:--------------------:|
| 1 KB text | ~$0.01 |
| 100 KB document | ~$0.05 |
| 1 MB PDF | ~$0.07 |
| 10 MB image | ~$0.15 |

Actual cost depends on prompt complexity and output tokens. Costs scale with file activity. Idle cost: ~$5/month.

See [Cost Estimation](./cost-estimation.md) for full breakdown and formulas.

---

### Q: How accurate is the AI classification?

**A:** PoC testing achieved **0.94 average confidence** on a test dataset of mixed business documents.

**Important caveat:** This is PoC accuracy on a specific test dataset. Production accuracy varies by:
- File type (text documents classify better than scanned images)
- Language mix (single-language content is more accurate than mixed)
- Domain terminology (specialized vocabulary may need prompt tuning)
- File quality (poor scans, handwritten notes reduce accuracy)

A PoC with actual target files is recommended to validate accuracy for a specific environment.

---

## Limitations & Constraints

### Q: What does NOT work with this solution?

**A:** Key constraints:

| Limitation | Impact |
|-----------|--------|
| S3 AP is read-only in this pipeline (writes supported at API level) | Analytics tools cannot write results back to FSx for ONTAP volumes |
| No S3 Event Notifications via S3 AP | Cannot auto-trigger Snowpipe, EventBridge rules, or bucket notifications |
| FPolicy adds latency | ~1–5ms per file operation on NAS clients |
| Lambda ephemeral processing | File content passes through Lambda memory (not truly "zero data movement" at the processing layer) |
| Athena cold start | First query after idle: 3–5s additional latency |
| OpenSearch warm-up | Serverless OCU allocation may take 10–30s after extended idle |
| S3 Tables is relatively new | GA Dec 2024; some cross-platform integrations still evolving |

---

### Q: Can analytics tools write back to FSx for ONTAP through S3 Access Point?

**A:** No. S3 Access Point on FSx for ONTAP is used **read-only in this pipeline**. If an analytics workflow requires writing results back, those results must be written to a separate S3 bucket or other storage.

---

### Q: Does FPolicy affect NAS performance?

**A:** Yes, modestly. FPolicy adds approximately **1–5ms latency per file operation** (create, modify, delete, rename) on NAS clients. For most workloads this is imperceptible, but latency-sensitive applications (e.g., high-frequency trading data feeds, real-time video editing) should be tested.

FPolicy can be scoped to specific volumes/shares and event types to minimize impact.

---

### Q: Can Snowpipe or EventBridge be triggered from S3 Access Point?

**A:** No. S3 Access Point on FSx for ONTAP does **not support S3 Event Notifications**. This means:
- Snowpipe cannot be auto-triggered by file changes via S3 AP
- EventBridge rules cannot be triggered by S3 AP events
- S3 bucket notification configurations do not apply to S3 AP

The workaround is FPolicy → Lambda → direct API call (to Snowpipe REST API, EventBridge PutEvents, etc.), which is how this solution operates.

---

## Platform Integration

### Q: Can Snowflake be used?

**A:**
- **Cortex File AI**: Verified ✅ — can process files via presigned URLs
- **Iceberg table query via S3 Tables catalog**: Pending Snowflake feature support. Snowflake's S3 Tables integration as an Iceberg catalog is not yet available.
- **Workaround**: Export metadata to S3 in Parquet format for Snowflake external table access

---

### Q: Can Databricks be used?

**A:**
- **Direct S3 Tables access via Foreign Catalog**: Under evaluation. Databricks Foreign Catalog support for S3 Tables is still evolving (as of 2026-06).
- **Workaround**: DataSync to copy metadata to S3 bucket accessible by Databricks, or export Iceberg metadata to a Databricks-managed location.

---

### Q: What about Amazon Athena performance?

**A:** Athena queries against S3 Tables Iceberg work well for analytics workloads:
- **Cold start**: First query after idle period takes 3–5 seconds additional latency
- **Subsequent queries**: Sub-second to a few seconds depending on data volume
- **Partition pruning**: Effective when queries filter on partitioned columns (e.g., scan_date)

---

### Q: What about OpenSearch Serverless performance?

**A:** OpenSearch Serverless provides vector + keyword search:
- **Warm-up time**: After extended idle, OCU allocation may take 10–30 seconds
- **Once warm**: Sub-second response for both vector similarity and keyword searches
- **Scale-to-zero**: Minimizes cost during idle periods but introduces warm-up latency

---

## Technical Details

### Q: What AI models are used?

**A:**
- **Amazon Bedrock Claude** (Anthropic): File classification, content extraction, vision (image/PDF analysis)
- **Amazon Titan Embeddings**: Vector embeddings for semantic similarity search
- **Amazon Comprehend**: PII detection (names, addresses, phone numbers, etc.)

All models run within the AWS account. No data leaves the account or region.

---

### Q: What about PII detection?

**A:** PII is automatically detected in both English and Japanese content using Amazon Comprehend. Detected PII is:
1. Flagged in metadata with PII type and confidence score
2. Optionally redacted before indexing in OpenSearch (configurable)
3. Available for compliance reporting via Athena queries

---

### Q: Can on-premises ONTAP work too?

**A:** Yes. Two paths:
1. **SnapMirror → FSx for ONTAP**: Mirror on-prem volumes to FSx for ONTAP, then apply AI pipeline to the FSx for ONTAP copy. Maintains zero-copy storage advantage.
2. **AWS DataSync**: Direct file transfer from on-prem to S3 for processing.

---

## PoC Validation

### Q: What does a PoC involve?

**A:** Typically 1–2 weeks for full validation:
- Week 1: Infrastructure deploy + AI pipeline configuration + initial classification
- Week 2: Accuracy tuning + dashboard setup + acceptance testing

A minimal demonstration runs in **30 minutes** using CloudFormation and sample data.

See [PoC Execution Guide](../implementation-guide/poc-execution-guide.md) for the full checklist.

---

## Related Documents

| Document | Content |
|----------|---------|
| [Technical Overview](./technical-overview.md) | Architecture and verified metrics |
| [Architecture Comparison](./architecture-comparison.md) | Decision framework for choosing the right approach |
| [Cost Estimation](./cost-estimation.md) | Component-level cost breakdown and scaling formulas |
| [PoC Execution Guide](../implementation-guide/poc-execution-guide.md) | Step-by-step implementation checklist |

---

*Last updated: 2026-06*
