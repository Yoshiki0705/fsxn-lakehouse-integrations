# Snowflake Cortex AI Demo Guide — FSx for ONTAP S3 AP

This guide demonstrates AI/ML capabilities on FSx for ONTAP data accessed via Snowflake External Stage with `AWS_ACCESS_POINT_ARN`.

## Prerequisites

- Snowflake account with Cortex AI enabled
- FSx for ONTAP S3 Access Point configured
- External Stage with `AWS_ACCESS_POINT_ARN` (see [README](../../README.md))

## Demo 1: OCR Text Extraction (PARSE_DOCUMENT)

**Use case**: Extract text from scanned inspection reports, invoices, or quality documents stored on NAS.

```sql
-- OCR: Extract text from image on FSx for ONTAP
SELECT SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
  @fsxn_stage,
  'media/documents/invoice_sample.png',
  {'mode': 'OCR'}
) AS ocr_result;
```

**Result**: Structured text extracted from the image (6.0s).

**Manufacturing use case**: Digitize paper-based inspection reports stored on NFS, making them searchable and analyzable without manual data entry.

## Demo 2: AI Text Summarization (CORTEX.SUMMARIZE)

**Use case**: Summarize sensor data, log files, or document content for quick insights.

```sql
-- Summarize sensor data from External Table
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(VALUE::VARCHAR) AS ai_summary
FROM fsxn_sensor_ext_table
LIMIT 1;
```

**Result**: "The text is a JSON object containing data on humidity, pressure, temperature, sensor ID, status, and timestamp." (3.3s)

**Manufacturing use case**: Auto-generate shift summaries from IoT sensor data stored on FSx for ONTAP.

## Demo 3: File Catalog + Download URLs

**Use case**: Manage unstructured data (images, videos, documents) as a searchable library.

```sql
-- Enable file catalog
ALTER STAGE fsxn_stage SET DIRECTORY = (ENABLE = TRUE);
ALTER STAGE fsxn_stage REFRESH;

-- Search for inspection images
SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED,
  GET_PRESIGNED_URL(@fsxn_stage, RELATIVE_PATH, 3600) AS DOWNLOAD_URL
FROM DIRECTORY(@fsxn_stage)
WHERE RELATIVE_PATH LIKE 'media/images/%'
ORDER BY LAST_MODIFIED DESC;
```

**Result**: File catalog with downloadable URLs for each image.

**Manufacturing use case**: Quality engineers search for inspection photos by date/location, download for review.

## Demo 4: Vision AI for Defect Detection (TBD)

**Use case**: Natural language instructions for product quality inspection.

```sql
-- Vision AI: Analyze product inspection image (syntax requires validation)
SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
  'claude-3-5-sonnet',
  'Analyze this product inspection image and identify any defects or quality issues.',
  {'image': BUILD_SCOPED_FILE_URL(@fsxn_stage, 'media/images/product_inspection.png')}
) AS defect_analysis;
```

**Status**: ⚠️ The multimodal AI_COMPLETE syntax for External Stage files requires additional validation. The function is supported in Snowflake but the correct SQL syntax for passing stage file URLs to vision models needs confirmation.

**Manufacturing use case**: Automated visual quality inspection — natural language instructions like "identify scratches on this component" or "check alignment of this assembly."

## Verified Results Summary

| Capability | Status | Duration | Use Case |
|---|:---:|---|---|
| PARSE_DOCUMENT (OCR) | ✅ Verified | 6.0s | Invoice/report text extraction |
| CORTEX.SUMMARIZE | ✅ Verified | 3.3s | Sensor data / document summarization |
| Directory Table + URLs | ✅ Verified | 1.3s | Unstructured data catalog |
| AI_COMPLETE (Vision) | ⚠️ TBD | — | Image defect detection, yield analysis |

## Screenshots

- OCR + Query History: `docs/images/snowflake-08-parse-document-ocr.png`
- Cortex SUMMARIZE: `docs/images/snowflake-07-cortex-llm-summary.png`
- Directory Table: `docs/images/snowflake-06-directory-table-presigned-url.png`
