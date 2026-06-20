# Sample Datasets / サンプルデータセット

> 🌐 English / 日本語（本ファイルはバイリンガル）

## Purpose / 目的

This directory contains synthetic manufacturing datasets for PoC Phase 1 validation.
All data is **entirely synthetic** — no real factory, product, or person is represented.

本ディレクトリには PoC Phase 1 検証用の合成製造データを格納しています。
全データは**完全に合成**です。実在の工場、製品、個人を表すものではありません。

## Dataset Structure / データセット構成

```
samples/
├── README.md                          ← This file
└── manufacturing/
    ├── sensor-data.csv                ← IoT sensor time-series (temperature, vibration, pressure)
    ├── quality-inspection.json        ← Quality inspection results with metadata
    ├── file-metadata-acl.json         ← File metadata + ACL hints (for annotation PoC)
    └── generate-samples.py            ← Script to regenerate with different parameters
```

## Usage / 利用方法

### Quick Start: Upload to FSx for ONTAP and query via Athena

```bash
# 1. Copy sample data to FSx for ONTAP volume (via NFS mount)
cp samples/manufacturing/sensor-data.csv /mnt/fsxn/vol1/data/sensor/

# 2. Or use DataSync to sync to S3
aws datasync start-task-execution --task-arn <TASK_ARN>

# 3. Query via Athena (after Glue Crawler)
# SELECT * FROM fsxn_analytics.sensor_data WHERE temperature > 85.0;
```

### Quick Start: S3 Annotations PoC

```bash
# Use file-metadata-acl.json as annotation payload
python3 samples/manufacturing/generate-samples.py --annotate
```

## Data Characteristics / データ特性

| Dataset | Records | Format | Size | Use Case |
|---------|---------|--------|------|----------|
| sensor-data.csv | 1,000 rows | CSV | ~50 KB | DataSync → Athena / Databricks PoC |
| quality-inspection.json | 50 records | JSON | ~15 KB | Bedrock KB / AI classification PoC |
| file-metadata-acl.json | 20 records | JSON | ~8 KB | S3 Annotations ACL-hint PoC |

## Schema Details / スキーマ詳細

### sensor-data.csv

| Column | Type | Description (EN) | 説明 (JA) |
|--------|------|-----------------|-----------|
| timestamp | ISO 8601 | Measurement time | 計測時刻 |
| line_id | string | Production line identifier | 生産ライン ID |
| equipment_id | string | Equipment identifier | 設備 ID |
| sensor_type | string | temperature / vibration / pressure | センサー種別 |
| value | float | Measured value | 計測値 |
| unit | string | °C / mm/s / kPa | 単位 |
| status | string | normal / warning / alarm | ステータス |

### quality-inspection.json

| Field | Type | Description (EN) | 説明 (JA) |
|-------|------|-----------------|-----------|
| inspection_id | string | Unique inspection ID | 検査 ID |
| timestamp | ISO 8601 | Inspection time | 検査時刻 |
| lot_id | string | Production lot | ロット ID |
| part_number | string | Part number | 品番 |
| result | string | pass / fail / conditional | 判定結果 |
| defect_category | string | null / scratch / dimension / contamination | 欠陥分類 |
| image_path | string | Reference path to inspection image | 検査画像パス |
| inspector_shift | string | day / night | 検査シフト |
| equipment_id | string | Inspection equipment | 検査設備 |

### file-metadata-acl.json

| Field | Type | Description (EN) | 説明 (JA) |
|-------|------|-----------------|-----------|
| file_path | string | Source path on FSx for ONTAP | FSx for ONTAP 上のパス |
| svm_name | string | Storage Virtual Machine | SVM 名 |
| volume_name | string | Volume name | ボリューム名 |
| security_style | string | ntfs / unix | セキュリティスタイル |
| owner | string | File owner | 所有者 |
| group | string | Primary group | プライマリグループ |
| acl_hash | string | SHA-256 of normalized ACL | ACL ハッシュ |
| classification | string | public / internal / confidential | データ分類 |
| retention_days | int | Required retention period | 保持日数 |

## Regeneration / 再生成

```bash
# Default: 1000 sensor rows, 50 inspections, 20 file metadata
python3 samples/manufacturing/generate-samples.py

# Custom: 10000 sensor rows for scale testing
python3 samples/manufacturing/generate-samples.py --sensor-rows 10000

# With S3 annotation upload (requires boto3 + S3 bucket)
python3 samples/manufacturing/generate-samples.py --annotate --bucket <BUCKET_NAME>
```

## Related Documents / 関連ドキュメント

- [DataSync → S3 ガイド / Guide](../docs/ja/datasync-to-s3-guide.md) — Phase 1 で使用
- [S3 Annotations 評価 / Evaluation](../docs/ja/s3-annotations-governance-evaluation.md) — ACL-hint annotation PoC
- [互換性マトリクス / Compatibility Matrix](../docs/ja/compatibility-matrix.md) — クイックスタート手順
- [読み順ガイド / Reading Path Guide](../docs/ja/reading-path-guide.md) — PoC 着手前の推奨読書
