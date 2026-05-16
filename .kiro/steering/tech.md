# Technology Stack

## Infrastructure as Code

- **CloudFormation (YAML)**: AWS ネイティブリソース（FSxN, S3 AP, IAM, VPC, Lambda, Glue）
- **Terraform**: ベンダー固有リソース（Databricks Unity Catalog, Snowflake Storage Integration）
- **cfn-lint**: CloudFormation テンプレートの静的解析

## Languages & Runtimes

- **Python 3.12**: スクリプト、Lambda、データ生成、テスト
- **Bash**: セットアップスクリプト、自動化
- **SQL**: Snowflake SQL, Athena SQL, Trino SQL, Spark SQL

## Data Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| Apache Parquet | .parquet | 列指向分析クエリ（推奨デフォルト） |
| Apache Iceberg | metadata + .parquet | ACID テーブル（ベンダー中立） |
| Delta Lake | _delta_log/ + .parquet | ACID テーブル（Databricks エコシステム） |
| Apache Hudi | .hoodie/ + .parquet | CDC + Upsert ワークロード |
| CSV | .csv | レガシーデータ取り込み |
| JSON / NDJSON | .json / .jsonl | セミ構造化データ |
| ORC | .orc | Hive 互換ワークロード |
| Avro | .avro | スキーマ進化が必要なストリーミング |

## S3 API Compatibility Notes

FSxN の S3 プロトコルは以下の API をサポート:

### Fully Supported
- `GetObject` / `HeadObject`
- `PutObject` (single + multipart)
- `DeleteObject`
- `ListObjectsV2`
- `CreateMultipartUpload` / `UploadPart` / `CompleteMultipartUpload`
- `CopyObject`

### Partially Supported / Limitations
- `GetBucketLocation`: 常に SVM のリージョンを返す
- `ListBuckets`: SVM 内のバケットのみ
- Object Tagging: ONTAP 9.11.1+ で対応
- Versioning: ONTAP Snapshot で代替（S3 versioning とは異なる）

### Not Supported
- S3 Select
- S3 Inventory
- S3 Batch Operations
- Requester Pays
- Object Lock (WORM は SnapLock で代替)

## Testing

- **pytest**: Python スクリプト・Lambda のユニットテスト
- **cfn-lint**: CloudFormation テンプレート検証
- **terraform validate**: Terraform 構文検証
- **boto3 integration tests**: S3 AP アクセス検証

## Key Dependencies

```
boto3>=1.34.0
pandas>=2.2.0
pyarrow>=15.0.0
pytest>=8.0.0
cfn-lint>=0.87.0
```
