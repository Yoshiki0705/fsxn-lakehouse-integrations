# EMR Serverless Spark Integration / EMR Serverless Spark 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Run Spark SQL on FSx for ONTAP data via S3 Access Points using EMR Serverless.
Read, transform, and write-back Parquet — no cluster management required.

### Status: ✅ Functional Verified (2026-05-23)

- Read 10K rows: 6.78s
- GROUP BY aggregation: 2.52s
- Window function: 1.19s
- Write-back to FSxN: 3.61s
- Total Spark execution: 16.35s (job total: 37s including cold start)

### Architecture

```
EMR Serverless (Spark 3.5)
    │
    └── EMRFS (s3:// — natively supports S3 AP aliases)
            │
            └── S3 Access Point (internet-origin) ──→ FSx for ONTAP Volume
```

### Key Finding: EMRFS vs S3A

- **EMRFS (`s3://`)**: Natively supports S3 AP aliases. Use this.
- **S3A (`s3a://`)**: Does NOT work with AP aliases (URL parsing error). Do not use.

### Quick Start

```bash
# 1. Create EMR Serverless application
aws emr-serverless create-application \
  --name "fsxn-spark" --release-label "emr-7.1.0" --type "SPARK"

# 2. Upload PySpark script
aws s3 cp scripts/spark_verification.py s3://<your-bucket>/emr-scripts/

# 3. Run job
aws emr-serverless start-job-run \
  --application-id <app-id> \
  --execution-role-arn <role-arn> \
  --job-driver '{"sparkSubmit":{"entryPoint":"s3://<bucket>/emr-scripts/spark_verification.py"}}'

# 4. Stop application (cost control)
aws emr-serverless stop-application --application-id <app-id>
```

### Important: Parquet Timestamp

Parquet files must use **microsecond** timestamps (not nanosecond). pandas default is nanosecond — Spark cannot read these.

```python
# Generate Spark-compatible Parquet
import pyarrow as pa
ts_array = pa.array(df['timestamp'].values.astype('datetime64[us]'), type=pa.timestamp('us'))
```

### Cost

EMR Serverless charges per vCPU-hour and GB-hour. A 37-second job costs approximately $0.05.
Application has zero cost when stopped.

---

<a id="日本語"></a>

## 日本語

### 概要

EMR Serverless を使用して FSx for ONTAP のデータに Spark SQL を実行。
Parquet の読み取り、変換、書き戻し — クラスタ管理不要。

### ステータス: ✅ 機能検証済み (2026-05-23)

### 重要: EMRFS vs S3A

- **EMRFS (`s3://`)**: S3 AP alias をネイティブサポート。こちらを使用。
- **S3A (`s3a://`)**: AP alias で動作しない（URL パースエラー）。使用不可。

### 重要: Parquet タイムスタンプ

Parquet ファイルは**マイクロ秒**タイムスタンプを使用すること（ナノ秒ではない）。
pandas デフォルトはナノ秒 — Spark では読み取り不可。
