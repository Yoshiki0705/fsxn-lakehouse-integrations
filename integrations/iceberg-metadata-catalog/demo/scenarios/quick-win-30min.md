# Quick Win Demo: 30-Minute Hands-On

> Deploy, run, and showcase the AI Metadata Catalog in 30 minutes flat.

---

## Overview

| Item | Detail |
|------|--------|
| Duration | 30 minutes |
| Target audience | Customer executives, SI partner SEs |
| Difficulty | Beginner (guided walkthrough) |
| Outcome | Working AI metadata catalog with searchable results |

---

## Prerequisites

- [ ] AWS account with admin access (or pre-provisioned demo account)
- [ ] FSx for ONTAP volume with sample files (or deploy with sample data — see below)
- [ ] AWS CLI configured with appropriate credentials
- [ ] Bedrock model access enabled (Claude 3 Sonnet, Titan Embeddings)
- [ ] Region: `ap-northeast-1` (recommended) or `us-east-1`

> **No existing FSx for ONTAP?** The CloudFormation template can deploy a demo FSx environment with sample files included.

> **Minimum scale guidance**: This solution provides the most value in environments with 10,000+ files and regular daily changes. For smaller file sets (<5,000 files with infrequent changes), simpler approaches like DataSync + S3 may be more cost-effective. See [Architecture Comparison](../../../docs/sales-enablement/architecture-comparison.md) for decision guidance.

---

## Demo Flow

### Step 1: Deploy CloudFormation (5 minutes)

**What you're doing**: One-click deployment of the entire solution stack.

```bash
# Deploy the demo stack
aws cloudformation deploy \
  --template-file integrations/iceberg-metadata-catalog/cloudformation/demo-stack.yaml \
  --stack-name ai-metadata-catalog-demo \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    FsxVolumeArn=arn:aws:fsx:ap-northeast-1:<ACCOUNT_ID>:volume/fsvol-xxxxxxxx \
    EnableSampleData=true
```

**Talking points**:
- "This single template deploys Lambda functions, S3 Tables, OpenSearch, and all IAM roles"
- "In production, customers use this same template — it's not a separate demo environment"
- "No changes to the existing FSx for ONTAP configuration required at this point"

**Expected output**: Stack creation initiated. Wait for `CREATE_COMPLETE` (~3–4 minutes).

---

### Step 2: Run Prerequisites Check (2 minutes)

**What you're doing**: Validating that all dependencies are correctly configured.

```bash
cd integrations/iceberg-metadata-catalog/scripts
./check-prerequisites.sh
```

**Talking points**:
- "This script validates S3 Access Point connectivity, Bedrock access, and network paths"
- "In a customer PoC, this is the first thing we run to catch configuration issues early"
- "Green checks across the board mean we're ready to process files"

**Expected output**:
```
✅ FSx for ONTAP S3 Access Point: accessible
✅ S3 Tables namespace: created
✅ Bedrock Claude: accessible
✅ Bedrock Titan Embeddings: accessible
✅ OpenSearch Serverless: ready
✅ Lambda functions: deployed
All prerequisites met. Ready for demo.
```

---

### Step 3: Execute Demo (42 seconds)

**What you're doing**: Processing a file through the entire AI pipeline — from detection to searchable metadata.

```bash
# Trigger the pipeline with a sample file
./run-demo.sh --file sample-data/manufacturing/design-drawing-001.pdf
```

**Talking points**:
- "Watch the timer — this entire process completes in about 42 seconds"
- "The pipeline: file detected → S3 AP read → Bedrock classification → Iceberg write → OpenSearch index"
- "In production, FPolicy triggers this automatically on every file create/modify"
- "Cost per execution: $0.07 — Lambda + Bedrock + storage combined"

**Expected output**:
```
📄 Processing: design-drawing-001.pdf
⏱️  Start: 2026-06-15T10:00:00Z
🔍 Reading via S3 Access Point...
🤖 Bedrock classification: CAD/設計図面 (confidence: 0.94)
🏷️  Metadata extracted: part_number=ABC-1234, revision=R3
📊 Writing to Iceberg table...
🔎 Indexing to OpenSearch...
✅ Complete: 42.3s | Cost: $0.068
```

---

### Step 4: Show Athena Query Results (5 minutes)

**What you're doing**: Demonstrating SQL-based metadata search using standard Athena.

Open the Athena console or run via CLI:

```sql
-- Find all design drawings
SELECT file_path, ai_classification, confidence_score, part_number, scan_timestamp
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'CAD/設計図面'
ORDER BY scan_timestamp DESC;

-- Search by part number
SELECT file_path, ai_classification, part_number, revision
FROM s3_tables.metadata_catalog.file_metadata
WHERE part_number LIKE 'ABC%';

-- Summary statistics
SELECT ai_classification, COUNT(*) as file_count, AVG(confidence_score) as avg_confidence
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY ai_classification
ORDER BY file_count DESC;
```

**Talking points**:
- "Standard SQL — any analyst who knows SQL can query this immediately"
- "The Iceberg table format means you get time-travel, schema evolution, and partition pruning"
- "This integrates with any BI tool that connects to Athena (QuickSight, Tableau, etc.)"
- "Notice the AI classification confidence scores — you can filter by confidence threshold"

---

### Step 5: Show OpenSearch Search UI (5 minutes)

**What you're doing**: Demonstrating full-text and semantic (vector) search capabilities.

Open OpenSearch Dashboards URL (output from CloudFormation):

**Demo searches**:
1. **Keyword search**: `"part number ABC-1234"` → shows exact matches
2. **Natural language search**: `"設計図面で材質がSUS304のもの"` → shows semantic matches
3. **Similar file search**: Click "Find similar" on any result → vector similarity search

**Talking points**:
- "Users don't need to know SQL — they can search like Google"
- "Vector search finds semantically similar files, not just keyword matches"
- "A designer looking for 'similar past designs' gets results even with different naming conventions"
- "This is powered by Titan Embeddings — each file gets a 1536-dimensional vector"

---

### Step 6: Discuss Results and Next Steps (10 minutes)

**What you're covering**: Business value, customization, and path to production.

**Discussion guide**:

1. **Validate understanding**
   - "Did you see how the entire pipeline — from file to searchable result — completed in 42 seconds?"
   - "At $0.07 per file, how many files per day would your environment need to process?"

2. **Relate to their environment**
   - "What types of files would benefit most from automatic classification?"
   - "Which departments spend the most time searching for files?"
   - "Do you have compliance requirements around PII detection?"

3. **Customization options**
   - "The 20 industry templates let us match your specific file types and classifications"
   - "We can tune the AI prompts to your terminology and categories"
   - "Additional metadata fields can be extracted based on your business needs"

4. **Path to production**
   - "PoC: 1–2 weeks with your actual files for accuracy validation"
   - "Production: 5–7 business days with an SI partner"
   - "Ongoing: Monthly operations (monitoring, tuning, reporting)"

5. **Cost conversation**
   - "100K files with 1000 daily changes: ~$114/month"
   - "vs copying all data to S3: ~$2,280/month for 100TB"
   - "Time savings: if 50 users save 30 min/day searching, that's 25 hours/day recovered"

---

## Expected Outcomes

By the end of this 30-minute demo, the audience will have:

- [x] Seen a working deployment from CloudFormation → operational pipeline
- [x] Witnessed the 42-second end-to-end pipeline execution
- [x] Queried metadata using standard SQL (Athena)
- [x] Experienced natural language and semantic search (OpenSearch)
- [x] Understood the cost model ($0.07/file, $114/month at scale)
- [x] Identified next steps for their environment (PoC or pilot)

---

## Cleanup

```bash
# Remove demo stack (no persistent costs)
aws cloudformation delete-stack --stack-name ai-metadata-catalog-demo
```

---

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| CloudFormation timeout | Check Bedrock model access is enabled in the target region |
| S3 Access Point error | Verify FSx volume has S3 data repository association configured |
| Bedrock throttling | Wait 30s and retry; demo uses minimal capacity |
| OpenSearch not accessible | Check VPC endpoint and security group allow your IP |

---

*For the full list of demo scenarios, see the [demo scenarios directory](./)*
