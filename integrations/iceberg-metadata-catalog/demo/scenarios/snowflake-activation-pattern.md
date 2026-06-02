# Snowflake Activation Pattern: Metadata Sync + Cortex Search

🌐 [日本語](snowflake-activation-pattern-ja.md) | English

> How Snowflake users can leverage the AI Metadata Catalog today, including Cortex Search for natural language queries and AI_COMPLETE for file analysis.

---

## Purpose

While direct Iceberg catalog access from Snowflake to S3 Tables is not yet available (credential vending / federated catalog integration pending), Snowflake users can activate the metadata catalog today via a PyIceberg export → External Stage → COPY INTO pattern.

This provides:
- Full metadata search via Cortex Search (natural language)
- AI file analysis via AI_COMPLETE + TO_FILE on FSx External Stage
- No storage duplication for the source files (zero-copy storage on FSx)
- Metadata sync on schedule or event-driven

---

## Architecture

```
FSx for ONTAP → FPolicy → Lambda → S3 Tables (Iceberg)
                                          │
                                    PyIceberg Export
                                          │
                                          ▼
                               S3 (Parquet Export)
                                          │
                              Snowflake External Stage
                                          │
                                    COPY INTO / MERGE INTO
                                          │
                                          ▼
                              Snowflake Managed Table
                                     │          │
                                     ▼          ▼
                            Cortex Search    AI_COMPLETE
                          (natural language)  (file AI via TO_FILE)
```

**Key point**: Source files remain on FSx for ONTAP (zero-copy storage). Only metadata records (small, ~1KB per file) are synced to Snowflake.

---

## Step-by-Step

### Step 1: Export Metadata from S3 Tables to S3 Parquet

Use PyIceberg to export the latest-record metadata from S3 Tables to S3 as Parquet files:

```python
# export_metadata.py
from pyiceberg.catalog import load_catalog
import pyarrow.parquet as pq

# Load S3 Tables catalog
catalog = load_catalog(
    "s3_tables",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-1",
    }
)

# Read metadata table
table = catalog.load_table("metadata_catalog.file_metadata")
scan = table.scan()
df = scan.to_arrow()

# Export to S3 as Parquet
pq.write_table(
    df,
    "s3://my-export-bucket/metadata-export/file_metadata.parquet"
)
print(f"Exported {len(df)} records")
```

**Scheduling**: Run via EventBridge + Lambda on schedule (e.g., hourly) or trigger after FPolicy batch processing completes.

---

### Step 2: Create Snowflake External Stage

Point a Snowflake External Stage to the export bucket:

```sql
-- Create storage integration (one-time setup)
CREATE OR REPLACE STORAGE INTEGRATION s3_metadata_export_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/SnowflakeMetadataExportRole'
  STORAGE_ALLOWED_LOCATIONS = ('s3://my-export-bucket/metadata-export/');

-- Create external stage
CREATE OR REPLACE STAGE metadata_export_stage
  STORAGE_INTEGRATION = s3_metadata_export_int
  URL = 's3://my-export-bucket/metadata-export/'
  FILE_FORMAT = (TYPE = PARQUET);
```

---

### Step 3: COPY INTO Managed Table

Load the exported metadata into a Snowflake managed table:

```sql
-- Create target table
CREATE OR REPLACE TABLE file_metadata (
  file_path VARCHAR,
  file_name VARCHAR,
  file_size_bytes NUMBER,
  last_modified TIMESTAMP_NTZ,
  ai_classification VARCHAR,
  confidence_score FLOAT,
  sensitivity_level VARCHAR,
  industry VARCHAR,
  department VARCHAR,
  pii_detected BOOLEAN,
  pii_types ARRAY,
  scan_timestamp TIMESTAMP_NTZ,
  -- Industry-specific fields as VARIANT for flexibility
  extended_metadata VARIANT
);

-- Full refresh (simple approach)
TRUNCATE TABLE file_metadata;
COPY INTO file_metadata
FROM @metadata_export_stage/file_metadata.parquet
FILE_FORMAT = (TYPE = PARQUET)
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
```

**Incremental approach** (for large datasets):

```sql
-- MERGE for incremental updates
MERGE INTO file_metadata AS target
USING (
  SELECT $1:file_path::VARCHAR AS file_path,
         $1:file_name::VARCHAR AS file_name,
         $1:file_size_bytes::NUMBER AS file_size_bytes,
         $1:last_modified::TIMESTAMP_NTZ AS last_modified,
         $1:ai_classification::VARCHAR AS ai_classification,
         $1:confidence_score::FLOAT AS confidence_score,
         $1:sensitivity_level::VARCHAR AS sensitivity_level,
         $1:industry::VARCHAR AS industry,
         $1:department::VARCHAR AS department,
         $1:pii_detected::BOOLEAN AS pii_detected,
         $1:pii_types::ARRAY AS pii_types,
         $1:scan_timestamp::TIMESTAMP_NTZ AS scan_timestamp,
         $1:extended_metadata::VARIANT AS extended_metadata
  FROM @metadata_export_stage/file_metadata.parquet
) AS source
ON target.file_path = source.file_path
WHEN MATCHED AND target.scan_timestamp < source.scan_timestamp THEN
  UPDATE SET
    ai_classification = source.ai_classification,
    confidence_score = source.confidence_score,
    sensitivity_level = source.sensitivity_level,
    pii_detected = source.pii_detected,
    scan_timestamp = source.scan_timestamp,
    extended_metadata = source.extended_metadata
WHEN NOT MATCHED THEN
  INSERT (file_path, file_name, file_size_bytes, last_modified,
          ai_classification, confidence_score, sensitivity_level,
          industry, department, pii_detected, pii_types,
          scan_timestamp, extended_metadata)
  VALUES (source.file_path, source.file_name, source.file_size_bytes,
          source.last_modified, source.ai_classification,
          source.confidence_score, source.sensitivity_level,
          source.industry, source.department, source.pii_detected,
          source.pii_types, source.scan_timestamp, source.extended_metadata);
```

---

### Step 4: Create Cortex Search Service

Enable natural language search over the metadata:

```sql
-- Create Cortex Search service on the managed table
CREATE OR REPLACE CORTEX SEARCH SERVICE file_metadata_search
  ON file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_path, ai_classification, industry, department, sensitivity_level'
  COLUMNS = (
    file_path,
    file_name,
    ai_classification,
    industry,
    department,
    sensitivity_level,
    confidence_score
  )
  SEARCH_COLUMN = 'file_name';
```

**Note**: Cortex Search requires a `SEARCH_COLUMN` — the column used for text-based search. For richer search, concatenate metadata fields into a dedicated search text column:

```sql
-- Enhanced: create a search-optimized column
ALTER TABLE file_metadata ADD COLUMN search_text VARCHAR;
UPDATE file_metadata SET search_text = 
  CONCAT(file_name, ' | ', ai_classification, ' | ', 
         COALESCE(industry, ''), ' | ', COALESCE(department, ''));

-- Recreate search service with enhanced search column
CREATE OR REPLACE CORTEX SEARCH SERVICE file_metadata_search
  ON file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_path, ai_classification, industry, department, sensitivity_level'
  COLUMNS = (file_path, file_name, ai_classification, industry, 
             department, sensitivity_level, confidence_score, search_text)
  SEARCH_COLUMN = 'search_text';
```

---

### Step 5: Query via Cortex Search (Natural Language)

```sql
-- Natural language search
SELECT *
FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH(
    'file_metadata_search',
    'quality inspection report for semiconductor wafer',
    5  -- top 5 results
  )
);

-- Search with filter
SELECT *
FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH(
    'file_metadata_search',
    'KYC document expiring soon',
    10,
    OBJECT_CONSTRUCT('industry', 'financial')
  )
);
```

---

### Step 6: AI_COMPLETE for File Analysis via TO_FILE

For direct file AI analysis using Snowflake's AI_COMPLETE with FSx files via External Stage:

```sql
-- Create External Stage pointing to FSx S3 Access Point
CREATE OR REPLACE STAGE fsxn_files_stage
  STORAGE_INTEGRATION = s3_fsxn_int
  URL = 's3://<fsxn-s3-access-point-alias>/vol/data/'
  FILE_FORMAT = (TYPE = AUTO);

-- Use AI_COMPLETE with TO_FILE for file analysis (confirmed working)
SELECT
  file_path,
  ai_classification,
  SNOWFLAKE.CORTEX.AI_COMPLETE(
    'claude-3-5-sonnet',
    CONCAT(
      'Summarize this document in 2 sentences: ',
      TO_FILE('@fsxn_files_stage', file_name)
    )
  ) AS ai_summary
FROM file_metadata
WHERE ai_classification = 'quality_report'
  AND industry = 'manufacturing'
LIMIT 5;
```

**Note**: TO_FILE on FSx External Stage has been confirmed working in testing. This enables Snowflake users to run AI analysis on files stored on FSx without copying file content.

---

## Current Blockers

| Blocker | Status | Impact |
|---------|--------|--------|
| S3 Tables Iceberg direct query from Snowflake | ❌ Not available | Cannot query S3 Tables directly as Iceberg catalog |
| Credential vending for S3 Tables | ❌ Not available | Snowflake cannot authenticate to S3 Tables federated catalog |
| Snowflake Iceberg catalog integration with S3 Tables | ❌ Pending | Feature request submitted; no ETA |

**Workaround**: The PyIceberg export pattern described above provides functional equivalence at the cost of a sync step.

---

## Future Path

When Snowflake adds S3 Tables / federated catalog support:

```
Current:  S3 Tables → PyIceberg Export → S3 Parquet → Snowflake Stage → Managed Table
Future:   S3 Tables → Snowflake Iceberg Catalog (direct read) → Virtual Table
```

The future state eliminates:
- Export step (no PyIceberg job needed)
- Storage duplication (metadata only in S3 Tables)
- Sync lag (real-time access to latest metadata)

Until then, the export pattern provides a working solution with acceptable lag (configurable: minutes to hours).

---

## Cost Model

### Snowflake Costs

| Component | Estimated Cost | Notes |
|-----------|---------------|-------|
| Warehouse compute (COPY INTO) | ~$2–5/run | X-Small warehouse, <1 min for 100K records |
| Warehouse compute (Cortex Search indexing) | ~$3–8/day | Depends on data volume and TARGET_LAG |
| Cortex Search service | ~$0.08/1K queries | Pay per search query |
| AI_COMPLETE (Claude via Snowflake) | ~$0.03–0.10/call | Depends on input size and model |
| Managed table storage | ~$23/TB/month | Metadata only — typically <1GB |

### AWS Costs (Export Side)

| Component | Estimated Cost | Notes |
|-----------|---------------|-------|
| Lambda (PyIceberg export) | ~$0.50/run | 256MB, <60s for 100K records |
| S3 storage (Parquet export) | ~$0.02/month | Metadata Parquet files are small |
| S3 GET/PUT requests | ~$0.005/export | Minimal request costs |

**Total estimated cost**: ~$5–15/day for hourly sync with 100K files, moderate Cortex Search usage.

---

## Limitations

| Limitation | Description |
|-----------|-------------|
| Sync lag | Metadata in Snowflake is delayed by export frequency (not real-time) |
| No direct Iceberg query | Cannot query S3 Tables Iceberg format directly from Snowflake |
| Export maintenance | PyIceberg export job requires monitoring and error handling |
| Schema evolution | Schema changes in S3 Tables require manual update to Snowflake table DDL |
| Cortex Search availability | Cortex Search is available in select Snowflake regions |
| TO_FILE size limits | Large files may timeout; best for documents <50MB |
| AI_COMPLETE model availability | Not all models available in all Snowflake regions |

---

## Complete Setup Script

```sql
-- ==============================================
-- Snowflake Activation: Full Setup
-- ==============================================

-- 1. Storage Integration
CREATE OR REPLACE STORAGE INTEGRATION s3_metadata_export_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/SnowflakeMetadataExportRole'
  STORAGE_ALLOWED_LOCATIONS = (
    's3://my-export-bucket/metadata-export/',
    's3://<fsxn-s3-access-point-alias>/'
  );

-- 2. External Stage (metadata)
CREATE OR REPLACE STAGE metadata_export_stage
  STORAGE_INTEGRATION = s3_metadata_export_int
  URL = 's3://my-export-bucket/metadata-export/'
  FILE_FORMAT = (TYPE = PARQUET);

-- 3. Target Table
CREATE OR REPLACE TABLE file_metadata (
  file_path VARCHAR,
  file_name VARCHAR,
  file_size_bytes NUMBER,
  last_modified TIMESTAMP_NTZ,
  ai_classification VARCHAR,
  confidence_score FLOAT,
  sensitivity_level VARCHAR,
  industry VARCHAR,
  department VARCHAR,
  pii_detected BOOLEAN,
  pii_types ARRAY,
  scan_timestamp TIMESTAMP_NTZ,
  extended_metadata VARIANT,
  search_text VARCHAR
);

-- 4. Load Data
COPY INTO file_metadata (file_path, file_name, file_size_bytes, last_modified,
  ai_classification, confidence_score, sensitivity_level, industry, department,
  pii_detected, pii_types, scan_timestamp, extended_metadata)
FROM @metadata_export_stage/file_metadata.parquet
FILE_FORMAT = (TYPE = PARQUET)
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

-- 5. Populate search text
UPDATE file_metadata SET search_text =
  CONCAT(file_name, ' | ', ai_classification, ' | ',
         COALESCE(industry, ''), ' | ', COALESCE(department, ''));

-- 6. Cortex Search Service
CREATE OR REPLACE CORTEX SEARCH SERVICE file_metadata_search
  ON file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_path, ai_classification, industry, department, sensitivity_level'
  COLUMNS = (file_path, file_name, ai_classification, industry,
             department, sensitivity_level, confidence_score, search_text)
  SEARCH_COLUMN = 'search_text';

-- 7. Verify
SELECT COUNT(*) FROM file_metadata;
SELECT * FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH('file_metadata_search', 'test query', 3)
);
```

---

*Related: [Governance Deep Dive](governance-deep-dive.md) — access control considerations for cross-platform sync*
*Related: [AI Prompt Customization Guide](ai-prompt-customization-guide.md) — classification that produces the metadata being synced*
*Pair document: [snowflake-activation-pattern-ja.md](snowflake-activation-pattern-ja.md)*
