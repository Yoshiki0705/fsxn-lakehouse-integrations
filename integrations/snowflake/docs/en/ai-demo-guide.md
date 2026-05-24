🌐 **English** | [日本語](../ja/ai-demo-guide.md)

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

**Result**: Structured text extracted from the image (~8s).

![PARSE_DOCUMENT OCR extracts text from image on FSx S3 AP](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/snowflake-08-parse-document-ocr.png)

*PARSE_DOCUMENT successfully extracts text from an invoice image stored on FSx for ONTAP via S3 Access Point. The result includes structured fields such as invoice number, customer name, and amount.*

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

![Cortex SUMMARIZE generates AI summary from External Table on FSx S3 AP](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/snowflake-07-cortex-llm-summary.png)

*Cortex SUMMARIZE generates an AI summary of sensor data stored on FSx for ONTAP, accessed via External Table (3.3s).*

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

![Directory Table with presigned URLs for unstructured data on FSx S3 AP](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/snowflake-06-directory-table-presigned-url.png)

*Directory Table catalogs image files on FSx for ONTAP with metadata and generates download URLs for each file.*

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
| PARSE_DOCUMENT (OCR) | ✅ Verified | ~8s | Invoice/report text extraction |
| CORTEX.SUMMARIZE | ✅ Verified | 3.3s | Sensor data / document summarization |
| Directory Table + URLs | ✅ Verified | 1.3s | Unstructured data catalog |
| AI_COMPLETE (Vision) | ⚠️ TBD | — | Image defect detection, yield analysis |

## Screenshots

- OCR + Query History: `docs/images/snowflake-08-parse-document-ocr.png`
- Cortex SUMMARIZE: `docs/images/snowflake-07-cortex-llm-summary.png`
- Directory Table: `docs/images/snowflake-06-directory-table-presigned-url.png`

---

## Industry Use Cases with Snowflake Cortex AI + FSx for ONTAP

### Manufacturing / Quality Inspection

| Use Case | Cortex Function | Data on FSx | Reference |
|---|---|---|---|
| Inspection report OCR | PARSE_DOCUMENT (OCR mode) | Scanned reports (PNG/PDF) | [Snowflake PARSE_DOCUMENT docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| Sensor anomaly summarization | CORTEX.SUMMARIZE | IoT sensor Parquet/CSV | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| Visual defect detection | AI_COMPLETE (vision) | Product images | [AI_COMPLETE multimodal](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal) |
| Yield analysis from dashboards | AI_COMPLETE (vision) | Dashboard screenshots | [Image Analysis Quickstart](https://www.snowflake.com/en/developers/guides/build-image-analysis-app-with-streamlit-and-snowflake-cortex/) |

### Financial Services / Insurance

| Use Case | Cortex Function | Data on FSx | Reference |
|---|---|---|---|
| Invoice data extraction | PARSE_DOCUMENT (LAYOUT mode) | Invoice PDFs/images | [Document AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| Contract clause summarization | CORTEX.SUMMARIZE | Contract documents | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| Claims document processing | PARSE_DOCUMENT + SUMMARIZE | Claims forms | [OCR + RAG Quickstart](https://quickstarts.snowflake.com/guide/getting_started_with_ocr_and_rag_with_snowflake_notebooks/) |
| Regulatory document search | Cortex Search (via COPY INTO) | Compliance docs | [Cortex Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) |

### Healthcare / Life Sciences

| Use Case | Cortex Function | Data on FSx | Reference |
|---|---|---|---|
| Medical record digitization | PARSE_DOCUMENT (OCR) | Scanned records | [PARSE_DOCUMENT](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| Research paper summarization | CORTEX.SUMMARIZE | PDF papers | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| Lab report text extraction | PARSE_DOCUMENT | Lab images/PDFs | [Document AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| Clinical trial data catalog | Directory Table | Trial documents | [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables) |

### Media / Content Management

| Use Case | Cortex Function | Data on FSx | Reference |
|---|---|---|---|
| Image metadata extraction | AI_COMPLETE (vision) | Media assets | [AI_COMPLETE](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal) |
| Video frame description | AI_COMPLETE (vision) | Extracted frames | [Image Analysis](https://www.snowflake.com/en/developers/guides/build-image-analysis-app-with-streamlit-and-snowflake-cortex/) |
| Asset catalog management | Directory Table + Tags | All media files | [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables) |
| Content translation | CORTEX.TRANSLATE | Text documents | [Cortex TRANSLATE](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#label-cortex-llm-translate) |

### Cross-Industry: Data Engineering

| Use Case | Cortex Function | Data on FSx | Reference |
|---|---|---|---|
| Schema inference from files | PARSE_DOCUMENT + LLM | Mixed format files | [Cortex LLM](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| Data quality assessment | CORTEX.SUMMARIZE | Data samples | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| File classification/tagging | AI_COMPLETE + Tags | Unstructured files | [Governance Tags](https://docs.snowflake.com/en/user-guide/object-tagging/introduction) |
| Automated documentation | CORTEX.SUMMARIZE | Code/config files | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |

---

## Getting Started

1. **Set up FSx S3 AP stage** — Follow the [Configuration Guide](../../README.md)
2. **Upload sample data** — Place images/documents on FSx for ONTAP via NFS
3. **Refresh Directory Table** — `ALTER STAGE REFRESH` to detect new files
4. **Run Cortex functions** — Use the SQL examples above
5. **Build Streamlit app** — For interactive dashboards with image thumbnails

## Snowflake Cortex AI Documentation

- [Cortex AI Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex)
- [LLM Functions (SUMMARIZE, COMPLETE, TRANSLATE)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions)
- [PARSE_DOCUMENT (OCR / Document AI)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document)
- [AI_COMPLETE (Multimodal/Vision)](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal)
- [Cortex Search (RAG)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables)
- [OCR + RAG Quickstart](https://quickstarts.snowflake.com/guide/getting_started_with_ocr_and_rag_with_snowflake_notebooks/)
- [Image Analysis with Streamlit](https://www.snowflake.com/en/developers/guides/build-image-analysis-app-with-streamlit-and-snowflake-cortex/)
