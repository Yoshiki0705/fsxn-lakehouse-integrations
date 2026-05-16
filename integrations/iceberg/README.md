# Apache Iceberg Integration / Apache Iceberg 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Vendor-neutral Apache Iceberg table management on FSx for NetApp ONTAP.
Uses REST Catalog for metadata management, accessible from any Iceberg-compatible engine.

### Architecture

```
Any Engine (Spark/Trino/Flink/Databricks/Snowflake)
    │
    └── REST Catalog (Lambda/ECS)
            │
            └── S3 Access Point ──→ FSxN Volume (Parquet data + Iceberg metadata)
```

### Status: 🚧 Planned

### Planned Content

- [ ] CloudFormation template (REST Catalog on Lambda/ECS)
- [ ] Iceberg REST Catalog configuration
- [ ] Sample table creation scripts
- [ ] Multi-engine access examples (Spark, Trino, Databricks, Snowflake)
- [ ] Documentation (JA/EN)
- [ ] E2E verification tasks

### ONTAP Value for Iceberg

| Feature | Benefit |
|---------|---------|
| Snapshot | Recover entire Iceberg table state (metadata + data files) |
| FlexClone | Test schema/partition evolution on clone before production |
| Deduplication | Iceberg compaction creates duplicate blocks → dedup saves space |
| FabricPool | Old snapshots/partitions auto-tier to S3 |

---

<a id="日本語"></a>

## 日本語

### 概要

FSx for NetApp ONTAP 上でのベンダー中立な Apache Iceberg テーブル管理です。
REST Catalog でメタデータを管理し、Iceberg 互換の任意のエンジンからアクセスできます。

### アーキテクチャ

```
任意のエンジン (Spark/Trino/Flink/Databricks/Snowflake)
    │
    └── REST Catalog (Lambda/ECS)
            │
            └── S3 Access Point ──→ FSxN Volume (Parquet データ + Iceberg メタデータ)
```

### ステータス: 🚧 計画中

### 計画コンテンツ

- [ ] CloudFormation テンプレート（Lambda/ECS 上の REST Catalog）
- [ ] Iceberg REST Catalog 設定
- [ ] テーブル作成サンプルスクリプト
- [ ] マルチエンジンアクセス例（Spark, Trino, Databricks, Snowflake）
- [ ] ドキュメント（日英）
- [ ] E2E 検証タスク
