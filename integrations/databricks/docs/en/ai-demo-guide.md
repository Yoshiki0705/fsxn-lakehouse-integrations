🌐 **English** | [日本語](../ja/ai-demo-guide.md)

# Databricks AI/ML Demo Guide — FSx for ONTAP S3 AP

This guide documents AI/ML capabilities and their current status when accessing FSx for ONTAP data from Databricks via S3 Access Points.

> **Important**: Unity Catalog session policy currently blocks table creation and subdirectory listing on FSx for ONTAP S3 Access Points. The scenarios below document what works today (driver-only PoC), what's blocked, and what would be possible once the platform boundary is resolved.

## Prerequisites

- Databricks workspace on AWS (Customer-managed VPC recommended)
- FSx for ONTAP S3 Access Point configured
- Instance Profile with S3 AP access (for PoC path)
- Unity Catalog External Location with `access_point` field set
- DBR 17.3 LTS or later

## Current Status Summary

| Capability | Status | Path | Blocker |
|---|:---:|---|---|
| Spark file read (explicit path) | ✅ Works | UC External Location + `access_point` | — |
| Subdirectory listing | ❌ Blocked | UC External Location | Session policy prefix-level access |
| CREATE TABLE on S3 AP | ❌ Blocked | UC External Location | UC_CLOUD_STORAGE_ACCESS_FAILURE |
| boto3 file read (driver) | ✅ Works | Instance Profile (Customer VPC) | Bypasses UC governance |
| Feature Store table | ❌ Blocked | Requires CREATE TABLE | Session policy |
| MLflow tracking | ✅ Works | Independent of storage path | — |
| Model Serving | ⚠️ Not validated | Different credential path | — |

---

## Demo 1: Spark Read from FSx for ONTAP (Working)

**Use case**: Read structured data (CSV, Parquet) from FSx for ONTAP for ML feature engineering.

```python
# Read sensor data from FSx for ONTAP via S3 AP (explicit file path)
df = spark.read.format("csv") \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .load("s3://<s3ap-alias>/bronze/sensor_data/sensor_readings.csv")

df.show(5)
print(f"✅ Read {df.count()} rows from FSx for ONTAP S3 AP")
```

**Result**: 1000 rows read successfully from sensor CSV on FSx for ONTAP (explicit file path with `access_point` field set on External Location).

![Spark read succeeds for explicit file path on FSx S3 AP](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/databricks-ai-spark-read-success.png)

*Spark successfully reads sensor CSV data from FSx for ONTAP S3 Access Point using an explicit file path under Unity Catalog governance.*

**Limitation**: Only explicit file paths work. Directory-level reads (e.g., `spark.read.parquet("s3://<alias>/bronze/")`) fail because subdirectory listing is blocked by the session policy.

---

## Demo 2: CREATE TABLE — Blocked (Error Evidence)

**Use case**: Register FSx for ONTAP data as a governed Unity Catalog table for ML pipelines.

```sql
-- Attempt to create External Table on FSx for ONTAP S3 AP
CREATE TABLE fsxn_lakehouse.bronze.sensor_data
USING CSV
OPTIONS (header = 'true', inferSchema = 'true')
LOCATION 's3://<s3ap-alias>/bronze/sensor_data/';
```

**Result**: ❌ `UC_CLOUD_STORAGE_ACCESS_FAILURE` — Unity Catalog's internal validation cannot access the S3 AP path for table registration.

![CREATE TABLE blocked by UC session policy on FSx S3 AP](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/databricks-ai-create-table-blocked.png)

*Unity Catalog rejects table creation on FSx for ONTAP S3 Access Point. The session policy generated during AssumeRole does not include the S3 AP ARN pattern for internal validation operations.*

**Impact on AI/ML**: Without table creation, the following are blocked:
- Feature Store table registration
- Delta Lake managed tables for ML training data
- Unity Catalog lineage tracking for model training
- Column-level governance tags on training data

---

## Demo 3: Subdirectory Listing — Blocked (Error Evidence)

**Use case**: List files in a subdirectory for batch processing (image classification, document extraction).

```python
# Attempt to list subdirectory contents
files = dbutils.fs.ls("s3://<s3ap-alias>/media/images/")
```

**Result**: ❌ `AccessDenied` on `getFileStatus` — prefix-based ListObjectsV2 is blocked for subdirectories.

![Subdirectory listing blocked by session policy](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/databricks-ai-subdir-listing-blocked.png)

*Subdirectory listing fails with AccessDenied. The UC session policy allows top-level listing but blocks prefix-scoped ListObjectsV2 for subdirectories.*

**Impact on AI/ML**: Without subdirectory listing, batch processing patterns like `spark.read.format("binaryFile").load("s3://<alias>/media/images/")` cannot discover files automatically.

---

## Demo 4: Instance Profile + boto3 (PoC Path — Works)

**Use case**: Read unstructured data (images, documents) from FSx for ONTAP for AI processing.

```python
import boto3
from PIL import Image
from io import BytesIO

# Read image from FSx for ONTAP via Instance Profile (bypasses UC)
s3 = boto3.client('s3', region_name='ap-northeast-1')
response = s3.get_object(
    Bucket='<s3ap-alias>',
    Key='media/images/inspection_photo.jpg'
)
img = Image.open(BytesIO(response['Body'].read()))
print(f"✅ Image loaded: {img.size}, {img.mode}")
```

**Result**: ✅ Image file read successfully from FSx for ONTAP S3 AP via Instance Profile on Customer-managed VPC (Dedicated cluster).

**⚠️ Governance warning**: This path bypasses Unity Catalog entirely. No lineage, no access control, no audit trail within Databricks. Use only for controlled PoC with explicit approval from data owner, security owner, and platform owner.

---

## Demo 5: MLflow Experiment Tracking (Works)

**Use case**: Track ML experiments that use FSx for ONTAP data as training source.

```python
import mlflow

# MLflow tracking works independently of storage path
with mlflow.start_run(run_name="fsxn_sensor_model"):
    mlflow.log_param("data_source", "fsxn_s3ap")
    mlflow.log_param("data_path", "s3://<s3ap-alias>/bronze/sensor_data/")
    mlflow.log_param("access_method", "instance_profile_boto3")

    # Train model using data read via boto3...
    # mlflow.log_metric("accuracy", 0.95)
    # mlflow.sklearn.log_model(model, "model")

    print("✅ MLflow experiment tracked")
```

**Result**: ✅ MLflow experiment tracking works regardless of how data is accessed. However, Unity Catalog lineage (which table → which model) is NOT captured when data is read via boto3.

**Best practice**: Even when using the boto3 PoC path, register trained models in Unity Catalog Model Registry for governance.

---

## Future Capabilities (When UC Session Policy Is Resolved)

Once Databricks resolves the Unity Catalog session policy boundary for S3 Access Points, the following AI/ML workflows would become available:

### Feature Store on FSx for ONTAP

```python
# FUTURE: Feature table on FSx for ONTAP (requires CREATE TABLE)
from databricks.feature_engineering import FeatureEngineeringClient

fe = FeatureEngineeringClient()
fe.create_table(
    name="fsxn_lakehouse.features.customer_features",
    primary_keys=["customer_id"],
    df=feature_df,
    description="Customer ML features stored on FSx for ONTAP"
)
```

### Image Embeddings with CLIP

```python
# FUTURE: Batch image processing (requires subdirectory listing)
images_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.{jpg,png}") \
    .load("s3://<s3ap-alias>/media/images/")

# Generate CLIP embeddings
embeddings_df = images_df.withColumn(
    "embedding", generate_clip_embedding(col("content"))
)
```

### Document Processing for RAG

```python
# FUTURE: Document text extraction (requires binaryFile directory read)
docs_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.{pdf,docx}") \
    .load("s3://<s3ap-alias>/media/documents/")

# Extract text, chunk, embed for RAG pipeline
```

### Mosaic AI Model Training

```python
# FUTURE: Governed model training with UC lineage
# Requires: UC table on S3 AP → training data → model → UC Model Registry
# Full lineage: data source → features → model → serving endpoint
```

---

## Verified Results Summary

| Capability | Status | Access Path | Use Case |
|---|:---:|---|---|
| Spark CSV read (explicit path) | ✅ Verified | UC External Location | Structured data for ML |
| Top-level file listing | ✅ Verified | UC External Location | File discovery |
| boto3 file read (driver) | ✅ Verified | Instance Profile | Unstructured data PoC |
| MLflow tracking | ✅ Verified | Independent | Experiment management |
| CREATE TABLE | ❌ Blocked | UC External Location | Feature Store, governed tables |
| Subdirectory listing | ❌ Blocked | UC External Location | Batch file processing |
| Delta write-back | ❌ Blocked | UC External Location | Feature engineering output |
| Feature Store registration | ❌ Blocked | Requires CREATE TABLE | ML feature management |
| Executor-scale processing | ⚠️ Not validated | — | Distributed ML workloads |

---

## Industry Use Cases (Future State)

### Manufacturing / Quality Inspection

| Use Case | Databricks Feature | Data on FSx | Status |
|---|---|---|---|
| Sensor anomaly detection | MLflow + Spark ML | IoT sensor Parquet/CSV | ⚠️ Explicit path read only |
| Image defect classification | CLIP / Custom CNN | Product images | ❌ Batch read blocked |
| Predictive maintenance | Feature Store + AutoML | Equipment telemetry | ❌ Feature table blocked |
| Quality report generation | LLM (Foundation Model API) | Inspection documents | ⚠️ boto3 PoC only |

### Financial Services / Insurance

| Use Case | Databricks Feature | Data on FSx | Status |
|---|---|---|---|
| Document classification | Spark NLP / binaryFile | Contract PDFs | ❌ Batch read blocked |
| Fraud detection features | Feature Store | Transaction data | ❌ Feature table blocked |
| Risk model training | MLflow + XGBoost | Historical data | ⚠️ Explicit path read only |
| Regulatory text extraction | UDF + pypdf | Compliance docs | ⚠️ boto3 PoC only |

### Healthcare / Life Sciences

| Use Case | Databricks Feature | Data on FSx | Status |
|---|---|---|---|
| Medical image analysis | torchvision / CLIP | DICOM/PNG images | ❌ Batch read blocked |
| Clinical trial data prep | Spark ETL | Trial documents | ⚠️ Explicit path read only |
| Research paper embeddings | Sentence Transformers | PDF papers | ❌ Batch read blocked |
| Patient record extraction | pypdf + NLP | Scanned records | ⚠️ boto3 PoC only |

### Media / Content Management

| Use Case | Databricks Feature | Data on FSx | Status |
|---|---|---|---|
| Image similarity search | CLIP embeddings | Media assets | ❌ Batch read blocked |
| Video frame extraction | OpenCV + Spark | Video files | ❌ Batch read blocked |
| Content tagging | Foundation Model API | All media | ⚠️ boto3 PoC only |
| Asset metadata catalog | Delta table | File metadata | ❌ CREATE TABLE blocked |

---

## Recommended Alternatives Today

While waiting for UC session policy resolution, use these validated paths for AI/ML on FSx for ONTAP data:

| AI/ML Need | Recommended Service | Status | Reference |
|---|---|---|---|
| RAG over documents | Amazon Bedrock Knowledge Bases | AWS-documented | [Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html) |
| OCR / Document AI | Snowflake PARSE_DOCUMENT | ✅ Verified | [Demo Guide](../../../snowflake/docs/en/ai-demo-guide.md) |
| Text summarization | Snowflake Cortex SUMMARIZE | ✅ Verified | [Demo Guide](../../../snowflake/docs/en/ai-demo-guide.md) |
| File processing (Lambda) | AWS Lambda | AWS-documented | [Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html) |
| SQL analytics | Amazon Athena | ✅ Verified (Part 1) | [Blog](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh) |
| Spark ETL | EMR Serverless | Validated in series | [Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-run-spark-with-emr-serverless.html) |

---

## Getting Started

1. **Deploy infrastructure** — Follow the [Setup Guide](setup-guide.md)
2. **Configure External Location** — Set `access_point` field ([UC Integration](unity-catalog-integration.md))
3. **Test explicit file read** — Verify Spark read with known file path
4. **For PoC**: Configure Instance Profile on Dedicated cluster
5. **Track experiments** — Use MLflow regardless of access path
6. **Monitor**: Watch for Databricks platform updates on S3 AP support

## Databricks AI/ML Documentation

- [Mosaic AI Overview](https://docs.databricks.com/en/machine-learning/index.html)
- [Feature Engineering](https://docs.databricks.com/en/machine-learning/feature-store/index.html)
- [MLflow on Databricks](https://docs.databricks.com/en/mlflow/index.html)
- [Foundation Model APIs](https://docs.databricks.com/en/machine-learning/foundation-models/index.html)
- [Unity Catalog Models](https://docs.databricks.com/aws/en/catalog-explorer/explore-models)
- [External Locations](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials)
- [Instance Profiles (Legacy)](https://docs.databricks.com/en/admin/sql/data-access-configuration.html)
- [Binary File Data Source](https://docs.databricks.com/en/query/formats/binary-file.html)
