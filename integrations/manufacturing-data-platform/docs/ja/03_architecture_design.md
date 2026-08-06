# アーキテクチャ設計

🌐 [English](../en/03_architecture_design.md) | **日本語**

---

## アーキテクチャ決定記録

本設計は以下の ADR に基づく（詳細は [docs/adr/](../adr/README.md) を参照）：

| ADR | 決定 |
|-----|------|
| [ADR-001](../adr/ADR-001.md) | Kafka を工場イベントバックボーンとして使用 |
| [ADR-002](../adr/ADR-002.md) | ClickHouse をリアルタイム運用分析に使用 |
| [ADR-003](../adr/ADR-003.md) | FSx for ONTAP を大容量非構造化データのペイロードストレージとして使用 |
| [ADR-004](../adr/ADR-004.md) | Databricks 統合で S3 アクセスポイントへの直接依存を回避 |
| [ADR-005](../adr/ADR-005.md) | 大容量ファイルにメタデータ/ペイロード分離を使用 |

## 未設計項目（設計分析より）

以下の項目は[初回設計分析](07_initial_design_analysis.md)で **Must Fix** として
特定され、PoC 設計フェーズで対処する。なお同レビューは役割ベースのアーキタイプ
チェックリストに対する構造化されたセルフレビューであり、外部専門家によるレビューでは
ない：

| 項目 | ステータス | タスク |
|------|----------|--------|
| ClickHouse デプロイモデル（Cloud / BYOC / セルフマネージド） | 未設計 | TSK-001 |
| エッジバッファリングと障害復旧の設計 | 未設計 | TSK-002 |
| Kafka → ClickHouse コネクタの指定 | 未設計 | TSK-003 |

---

## DES-001: システムアーキテクチャ概要

### コンポーネント責務

| コンポーネント | 責務 | 管理対象 |
|--------------|------|---------|
| Amazon MSK (Kafka) | イベントバックボーン | メッセージ配信、順序保証、リプレイ |
| ClickHouse | リアルタイム運用分析 | サブ秒クエリ、時系列集計 |
| FSx for ONTAP | ペイロードストレージ | ドキュメント、画像、動画、コールドデータ |
| Databricks | ガバナンス付き分析・AI | キュレーション済み Delta テーブル、ML/AI ワークフロー |
| Unity Catalog | データガバナンス | メタデータ、権限、リネージ、監査 |
| ネイティブ Amazon S3 | Delta Lake 物理ストレージ | Parquet ファイル、トランザクションログ |

### DES-002: データフローアーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────┐
│                      エッジ / 工場レイヤー                             │
├─────────────────────────────────────────────────────────────────────┤
│  センサー  品質システム  カメラ   PLC   SCADA   MES                     │
│     │           │         │      │      │      │                    │
│     └───────────┴─────────┴──────┴──────┴──────┘                    │
│                              │                                      │
│              ┌───────────────┼───────────────┐                      │
│              ↓                               ↓                      │
│     MQTT/Kafka プロデューサー          ファイル転送エージェント           │
│     (構造化イベント)                   (大容量ペイロード)                │
└──────────────┬───────────────────────────────┬──────────────────────┘
               │                               │
               ↓                               ↓
┌──────────────────────────┐    ┌──────────────────────────┐
│      Amazon MSK          │    │     FSx for ONTAP        │
│      (Kafka)             │    │     (ペイロードストア)      │
│                          │    │                          │
│  トピック：                │    │  プロトコル：              │
│  - sensor-data           │    │  - NFS (PLC/SCADA)       │
│  - quality-events        │    │  - SMB (Windows)         │
│  - document-metadata     │    │  - ONTAP S3 (アプリ)      │
│  - image-metadata        │    │                          │
│  - system-alerts         │    │  ストレージ:               │
│                          │    │  - /images/              │
│                          │    │  - /videos/              │
│                          │    │  - /documents/           │
│                          │    │  - /clickhouse-cold/     │
└──────────┬───────────────┘    └──────────────────────────┘
           │                               ↑
           ├──────────────────┐            │ (S3互換階層化)
           ↓                  ↓            │
┌─────────────────────┐  ┌────────────────────────────────┐
│    ClickHouse       │  │       Databricks               │
│    (リアルタイム)     │──┘       (ガバナンス付き分析)        │
│                     │  │                                │
│  Kafka Engine:      │  │  Structured Streaming:         │
│  - イベント取り込み    │  │  - Kafka トピック読み取り        │
│  - MergeTree テーブル │  │  - Delta テーブル書き込み        │
│  - マテリアライズド    │  │  - 正確に1回の処理              │
│    ビュー            │  │                               │
│  - S3 コールド階層    │  │  Unity Catalog:               │
│    (→ ONTAP S3)     │  │  - Delta テーブル管理           │
│                     │  │  - リネージ追跡                 │
│  ダッシュボード:      │  │  - アクセス制御                  │
│  - OEE メトリクス    │  │                                │
│  - 品質トレンド       │  │  Delta Tables (ネイティブ S3):  │
│  - アラート          │  │  - manufacturing.sensor_data   │
│                     │  │  - manufacturing.quality_events│
└─────────────────────┘  │  - manufacturing.payload_refs  │
                         └────────────────────────────────┘
```

### DES-003: Kafka トピック設計

| トピック | 内容 | キー | パーティション | 保持期間 |
|---------|------|------|------------|---------|
| `factory.sensor-data` | センサー読み取り（温度、圧力、振動） | device_id | 12 | 7日 |
| `factory.quality-events` | 品質検査結果 | line_id | 6 | 30日 |
| `factory.document-metadata` | ドキュメントアップロード通知（メタデータのみ） | document_id | 3 | 30日 |
| `factory.image-metadata` | 画像キャプチャ通知（メタデータのみ） | device_id | 6 | 30日 |
| `factory.system-alerts` | システムヘルスとアラート | source_system | 3 | 90日 |

### DES-004: メッセージスキーマ (Avro/JSON Schema)

```json
{
  "type": "record",
  "name": "QualityEvent",
  "namespace": "factory.quality",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "device_id", "type": "string"},
    {"name": "line_id", "type": "string"},
    {"name": "event_type", "type": {"type": "enum", "name": "EventType", "symbols": ["INSPECTION", "MEASUREMENT", "DEFECT", "PASS"]}},
    {"name": "measurement_value", "type": ["null", "double"]},
    {"name": "measurement_unit", "type": ["null", "string"]},
    {"name": "pass_fail", "type": ["null", "boolean"]},
    {"name": "payload_uri", "type": ["null", "string"]},
    {"name": "payload_type", "type": ["null", "string"]},
    {"name": "payload_size_bytes", "type": ["null", "long"]},
    {"name": "payload_checksum", "type": ["null", "string"]}
  ]
}
```

### DES-005: ClickHouse テーブル設計

```sql
-- リアルタイムセンサーデータ（ホットストレージ）
CREATE TABLE factory.sensor_data (
    event_id String,
    timestamp DateTime64(3),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    sensor_type LowCardinality(String),
    value Float64,
    unit LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (line_id, device_id, timestamp)
TTL timestamp + INTERVAL 90 DAY TO VOLUME 's3_cold';

-- 品質イベント
CREATE TABLE factory.quality_events (
    event_id String,
    timestamp DateTime64(3),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    event_type LowCardinality(String),
    measurement_value Nullable(Float64),
    pass_fail Nullable(UInt8),
    payload_uri Nullable(String),
    payload_type Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (line_id, event_type, timestamp);
```

### DES-006: Databricks Delta テーブル設計

```sql
-- ガバナンス付きセンサーデータ（Unity Catalog マネージドテーブル）
CREATE TABLE manufacturing_catalog.factory_data.sensor_readings (
    event_id STRING,
    event_timestamp TIMESTAMP,
    device_id STRING,
    line_id STRING,
    sensor_type STRING,
    value DOUBLE,
    unit STRING,
    ingestion_timestamp TIMESTAMP,
    kafka_topic STRING,
    kafka_partition INT,
    kafka_offset BIGINT
)
USING DELTA
PARTITIONED BY (sensor_type, date(event_timestamp))
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');

-- ペイロード参照付き品質イベント
CREATE TABLE manufacturing_catalog.factory_data.quality_events (
    event_id STRING,
    event_timestamp TIMESTAMP,
    device_id STRING,
    line_id STRING,
    event_type STRING,
    measurement_value DOUBLE,
    measurement_unit STRING,
    pass_fail BOOLEAN,
    payload_uri STRING,
    payload_type STRING,
    payload_size_bytes BIGINT,
    payload_checksum STRING,
    ingestion_timestamp TIMESTAMP
)
USING DELTA
PARTITIONED BY (event_type, date(event_timestamp));
```

### DES-007: FSx for ONTAP ストレージ設計

| ボリューム | プロトコル | 用途 | 容量 |
|----------|----------|------|------|
| `/vol_images` | NFS + ONTAP S3 | 品質検査画像 | 500 GB |
| `/vol_videos` | NFS + SMB | プロセスモニタリング動画 | 2 TB |
| `/vol_documents` | SMB + NFS | 品質証明書、レポート | 200 GB |
| `/vol_clickhouse_cold` | ONTAP S3 | ClickHouse コールド階層データ | 1 TB |

**Snapshot ポリシー:** 毎時（24保持）、毎日（7保持）、毎週（4保持）

### DES-008: ネットワークアーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│                    VPC (10.0.0.0/16)                │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Private Sub  │  │ Private Sub  │                 │
│  │ (MSK)        │  │ (ClickHouse) │                 │
│  │ 10.0.1.0/24  │  │ 10.0.2.0/24  │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Private Sub  │  │ Private Sub  │                 │
│  │ (FSx for ONTAP)  │  │ (Databricks) │                 │
│  │ 10.0.3.0/24  │  │ 10.0.4.0/24  │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                     │
│  VPC Endpoints: S3, STS, Glue Catalog               │
│  VPC Peering: Databricks ワークスペース VPC            │
└─────────────────────────────────────────────────────┘
```

### DES-009: セキュリティアーキテクチャ

| レイヤー | 制御 |
|---------|------|
| ネットワーク | プライベートサブネット、セキュリティグループ、VPC エンドポイント |
| Kafka | SASL/SCRAM + TLS、IAM 認証（MSK） |
| ClickHouse | パスワード認証、TLS、IP 許可リスト |
| FSx for ONTAP | セキュリティグループ、エクスポートポリシー、CIFS 認証 |
| Databricks | Unity Catalog RBAC、ワークスペース分離 |
| S3 | バケットポリシー、暗号化（SSE-S3/SSE-KMS）、パブリックアクセス禁止 |
| シークレット | AWS Secrets Manager で認証情報管理 |

### DES-010: ストリーミングパイプライン設計 (Databricks)

```python
# Structured Streaming: Kafka → Delta Lake (Unity Catalog ガバナンス付き)
from pyspark.sql.functions import from_json, col, current_timestamp

# Kafka から読み取り
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "<msk-bootstrap-servers>")
    .option("subscribe", "factory.sensor-data")
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "AWS_MSK_IAM")
    .option("startingOffsets", "latest")
    .load()
)

# パースと変換
parsed_df = (
    kafka_df
    .select(
        from_json(col("value").cast("string"), sensor_schema).alias("data"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp").alias("kafka_timestamp")
    )
    .select("data.*", "topic", "partition", "offset")
    .withColumn("ingestion_timestamp", current_timestamp())
)

# Unity Catalog マネージドテーブルに書き込み
(
    parsed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "s3://poc-checkpoints/sensor-data/")
    .toTable("manufacturing_catalog.factory_data.sensor_readings")
)
```
