# Customer Demo Guide

🌐 [日本語](demo-guide-ja.md) | English

## Overview

This guide enables you to run the complete Iceberg Metadata Catalog demo in ~15 minutes. All resources scale-to-zero when idle ($0 cost).

**Demo flow**: Metadata Scan → AI Classification → Athena Query → Vector Search → PII Anonymization

## Prerequisites

| Requirement | Details |
|------------|---------|
| AWS CLI v2 | Configured with appropriate permissions |
| Python 3.12+ | With packages: `boto3 pyarrow 'pyiceberg[s3tables]' opensearch-py requests-aws4auth` |
| FSx for ONTAP | With S3 Access Point configured (alias ending in `-ext-s3alias`) |
| **Bedrock access** | **Claude 3 Haiku + Titan Embeddings V2 must be enabled in target region** ([Enable model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)) |

## Quick Start (One Command)

```bash
cd integrations/iceberg-metadata-catalog/demo/scripts
chmod +x run-demo.sh
./run-demo.sh --ap-alias <your-ap-alias-ext-s3alias>
```

## Step-by-Step

### 1. Deploy Infrastructure (~5 min)

```bash
aws cloudformation deploy \
  --template-file cloudformation/demo-stack.yaml \
  --stack-name fsxn-metadata-catalog-demo \
  --parameter-overrides S3AccessPointAlias=<your-ap-alias> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1
```

**What gets created**:
- S3 Tables table bucket (metadata storage)
- OpenSearch Serverless NextGen collection (vector search, scale-to-zero)
- Athena workgroup (SQL queries)

### 2. Register Glue Catalog + Create Iceberg Table (~2 min)

```bash
# Register S3 Tables federated catalog (one-time)
aws glue create-catalog --name "s3tablescatalog" --catalog-input '{
  "FederatedCatalog": {
    "Identifier": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/*",
    "ConnectionName": "aws:s3tables"
  },
  "CreateDatabaseDefaultPermissions": [],
  "CreateTableDefaultPermissions": []
}' --region ap-northeast-1

# Create Iceberg table with schema (PyIceberg)
python3 ../../scripts/initial-metadata-scan.py \
  --access-point-arn <your-ap-alias-ext-s3alias> \
  --table-bucket-arn arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog \
  --max-files 100
```

### 3. Run AI Enrichment (~3 min)

```bash
python3 scripts/demo-enrich.py \
  --table-bucket-arn arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog \
  --ap-alias <your-ap-alias-ext-s3alias> \
  --max-files 5
```

### 4. Query with Athena (~1 min)

```sql
-- In Athena console or CLI:
SELECT file_name, classification, confidence_score, summary
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE enrichment_status = 'completed'
ORDER BY confidence_score DESC;

-- Production query with deduplication (handles append-only Iceberg writes):
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY modified_at DESC) as rn
  FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
)
SELECT file_name, classification, confidence_score, summary
FROM ranked
WHERE rn = 1 AND is_deleted = false
ORDER BY confidence_score DESC;
```

### 5. Vector Similarity Search (~1 min)

```bash
python3 scripts/demo-search.py --query "find invoice or payment documents"
```

### 6. PII Anonymization (~1 min)

```bash
python3 scripts/demo-anonymize.py --ap-alias <your-ap-alias-ext-s3alias>
```

## Demo Talking Points

| Time | Demo Step | Key Message |
|------|-----------|-------------|
| 0:00 | Show FSx S3 AP files | "Unstructured data stays on ONTAP — no S3 copy needed" |
| 2:00 | Run metadata scan | "38 files cataloged in 30 seconds" |
| 4:00 | Show Athena query | "Any file findable in < 2 seconds via SQL" |
| 6:00 | Show AI classification | "Bedrock automatically classifies images at $0.01/file" |
| 8:00 | Run similarity search | "Find similar files using natural language" |
| 10:00 | Show PII detection | "7 PII types detected, all redacted automatically" |
| 12:00 | Show cost summary | "All this for less than the S3 copy it eliminates" |

## Cleanup

```bash
# Delete demo stack (all resources)
aws cloudformation delete-stack --stack-name fsxn-metadata-catalog-demo --region ap-northeast-1

# Delete S3 Tables data (if needed)
aws s3tables delete-table --table-bucket-arn <ARN> --namespace metadata --name unstructured_files --region ap-northeast-1
aws s3tables delete-namespace --table-bucket-arn <ARN> --namespace metadata --region ap-northeast-1
aws s3tables delete-table-bucket --table-bucket-arn <ARN> --region ap-northeast-1

# Remove Glue catalog (shared — only if no longer needed)
aws glue delete-catalog --name s3tablescatalog --region ap-northeast-1
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `CATALOG_NOT_FOUND` in Athena | Run Step 2 (register Glue catalog) |
| `COLUMN_NOT_FOUND` in Athena | Grant Lake Formation SELECT permission |
| OpenSearch search returns 0 hits | Wait 30s (scale-to-zero cold start) then retry |
| Bedrock `ThrottlingException` | Reduce --max-files or wait 30s |
| Bedrock `AccessDeniedException` | Enable model access: [Bedrock Console](https://console.aws.amazon.com/bedrock/home#/modelaccess) → Request access for Claude 3 Haiku + Titan Embeddings V2 |
| `ModuleNotFoundError: pyiceberg` | `pip install 'pyiceberg[s3tables]'` |

## Post-Demo Follow-Up Checklist

After the demo, complete these actions within 1 week:

- [ ] Share demo recording with customer stakeholders (asciinema link or GIF)
- [ ] Send post-demo feedback survey (`docs/post-demo-survey.md`)
- [ ] Send "Next Steps" template with PoC process (`docs/next-steps-template.md`)
- [ ] Schedule 1-week follow-up meeting to discuss PoC scope
- [ ] Log demo outcome in CRM (interest level, priority use case, timeline)
- [ ] If interest level ≥ 4: initiate PoC planning with SA team
