# Customer FAQ: FSx for ONTAP AI Metadata Catalog

> Honest answers including limitations and constraints.

---

## General

### Q: Do I need to copy my files?

**A:** No. The solution uses FSx for ONTAP's S3 Access Point to read file content in-place (zero-copy storage). Files never leave the FSx for ONTAP volume. Only extracted metadata is stored externally in S3 Tables.

**Clarification on "zero-copy storage":** File bytes are not duplicated to another storage location. However, during AI processing, file content is temporarily accessed in Lambda memory (ephemeral — not persisted outside the source FSx for ONTAP volume).

---

### Q: What about security and compliance?

**A:** Files remain on FSx for ONTAP with existing access controls (NFS/SMB permissions). Only metadata flows through the AI pipeline. Governance is enforced through:
- **AWS Lake Formation**: Fine-grained access control on metadata tables
- **AWS CloudTrail**: Full audit trail of all API calls
- **IAM Policies**: Least-privilege access to S3 Access Points and Bedrock
- **VPC Private Endpoints**: All traffic stays within your VPC

---

### Q: What's the cost?

**A:** Approximately **$114/month** for 100,000 files with 1,000 daily changes (assuming 100KB–1MB average file size).

File-size-dependent Bedrock costs:
| File Size | Cost per File |
|-----------|:------------:|
| 1 KB text | ~$0.01 |
| 100 KB document | ~$0.05 |
| 1 MB PDF | ~$0.07 |
| 10 MB image | ~$0.15 |

Actual cost depends on prompt complexity and output tokens. No upfront commitment — costs scale with file activity. Idle cost: ~$5/month.

---

### Q: How accurate is the AI classification?

**A:** PoC testing achieved **0.94 average confidence** on a test dataset of mixed business documents.

**Important caveat:** This is PoC accuracy on a specific test dataset. Production accuracy varies by:
- File type (text documents classify better than scanned images)
- Language mix (single-language content is more accurate than mixed)
- Domain terminology (specialized vocabulary may need prompt tuning)
- File quality (poor scans, handwritten notes reduce accuracy)

We recommend a 1–2 week PoC with your actual files to validate accuracy for your environment.

---

## Limitations & Constraints

### Q: What DOESN'T work with this solution?

**A:** Key constraints to be aware of:

| Limitation | Impact |
|-----------|--------|
| S3 AP is used read-only in this pipeline (writes are supported) | Analytics tools cannot write results back to FSx for ONTAP volumes |
| No S3 Event Notifications via S3 AP | Cannot auto-trigger Snowpipe, EventBridge rules, or bucket notifications |
| FPolicy adds latency | ~1–5ms per file operation on NAS clients |
| Lambda ephemeral processing | File content passes through Lambda memory (not truly "zero data movement" at the processing layer) |
| Athena cold start | First query after idle: 3–5s additional latency |
| OpenSearch warm-up | Serverless OCU allocation may take 10–30s after extended idle |
| S3 Tables is relatively new | GA Dec 2024; some cross-platform integrations still evolving |

---

### Q: Can analytics tools write back to FSx for ONTAP through S3 Access Point?

**A:** No. S3 Access Point on FSx for ONTAP is **read-only**. If your analytics workflow requires writing results back to storage, those results must be written to a separate S3 bucket or other storage. The source FSx for ONTAP volume is not writable via S3 AP.

---

### Q: Does FPolicy affect NAS performance?

**A:** Yes, modestly. FPolicy adds approximately **1–5ms latency per file operation** (create, modify, delete, rename) on NAS clients. For most workloads this is imperceptible, but latency-sensitive applications (e.g., high-frequency trading data feeds, real-time video editing) should be tested.

FPolicy can be scoped to specific volumes/shares and event types to minimize impact.

---

### Q: Can I trigger Snowpipe or EventBridge from S3 Access Point?

**A:** No. S3 Access Point on FSx for ONTAP does **not support S3 Event Notifications**. This means:
- Snowpipe cannot be auto-triggered by file changes via S3 AP
- EventBridge rules cannot be triggered by S3 AP events
- S3 bucket notification configurations do not apply to S3 AP

The workaround is FPolicy → Lambda → direct API call (to Snowpipe REST API, EventBridge PutEvents, etc.), which is how this solution operates.

---

## Platform Integration

### Q: Can I use Snowflake?

**A:**
- **Cortex File AI**: Verified ✅ — can process files via presigned URLs
- **Iceberg table query via S3 Tables catalog**: Pending Snowflake feature support. Snowflake's S3 Tables integration as an Iceberg catalog is not yet available.
- **Workaround**: Export metadata to S3 in Parquet format for Snowflake external table access

---

### Q: Can I use Databricks?

**A:**
- **Direct S3 Tables access via Foreign Catalog**: Under evaluation. Databricks Foreign Catalog support for S3 Tables is still evolving (as of 2026-06).
- **Workaround**: DataSync to copy metadata to S3 bucket accessible by Databricks, or export Iceberg metadata to a Databricks-managed location.

---

### Q: What about Amazon Athena performance?

**A:** Athena queries against S3 Tables Iceberg work well for analytics workloads. Note:
- **Cold start**: First query after idle period takes 3–5 seconds additional latency
- **Subsequent queries**: Sub-second to a few seconds depending on data volume
- **Partition pruning**: Effective when queries filter on partitioned columns (e.g., scan_date)

---

### Q: What about OpenSearch Serverless performance?

**A:** OpenSearch Serverless provides vector + keyword search. Note:
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

All models run within your AWS account. No data leaves your account or region.

**Accuracy note:** Bedrock classification accuracy varies by file type and language. PoC accuracy on test dataset; production accuracy depends on your specific file mix.

---

### Q: What about PII detection?

**A:** PII is automatically detected in both English and Japanese content using Amazon Comprehend. Detected PII is:
1. Flagged in metadata with PII type and confidence score
2. Optionally redacted before indexing in OpenSearch (configurable)
3. Available for compliance reporting via Athena queries

---

### Q: Can on-premises ONTAP work too?

**A:** Yes. Two paths:
1. **SnapMirror → FSx for ONTAP**: Mirror on-prem volumes to FSx, then apply AI pipeline to the FSx for ONTAP copy. Maintains zero-copy storage advantage.
2. **AWS DataSync**: Direct file transfer from on-prem to S3 for processing.

---

## ROI & Business Case

### Q: What's the ROI?

**A:** Using conservative estimates (50% adoption, 10 min/day search reduction, ¥4,000/hr rate):
- **Monthly net benefit**: ~$3,500 (100K files, 50 users)
- **Payback period**: ~10 days
- **Annual ROI**: ~3,000%

These are conservative figures. See [ROI Calculator](./roi-calculator.md) for moderate and optimistic scenarios, plus all assumptions listed.

**Key assumptions:**
- Users actually adopt the search interface (change management required)
- Freed search time is productively reused
- Classification accuracy is sufficient for the use case

---

### Q: How long does a PoC take?

**A:** 1–2 weeks for full validation:
- Week 1: Infrastructure deploy + AI pipeline configuration + initial classification
- Week 2: Accuracy tuning + dashboard setup + user acceptance testing

A minimal "Quick Win" demo runs in **30 minutes** using CloudFormation and sample data.

---

*Last updated: 2026-06*
