# Bilingual Glossary / 用語集（日英対照）

> Technical terms used throughout this project. Maintained for consistency between Japanese and English documents.
> Last updated: 2026-06-07

| English | Japanese | Definition |
|---------|----------|------------|
| Unity Catalog | Unity Catalog | Databricks unified governance platform for data and AI assets |
| Delta Lake | Delta Lake | Open-source storage layer providing ACID transactions on data lakes |
| Delta table | Delta テーブル | Table stored in Delta Lake format with transaction log |
| External location | 外部ロケーション | Unity Catalog object mapping a storage credential to a cloud storage path |
| Managed table | マネージドテーブル | Table whose data lifecycle is fully managed by Unity Catalog |
| External table | 外部テーブル | Table whose data files are managed outside Unity Catalog lifecycle |
| Storage credential | ストレージ資格情報 | Unity Catalog credential for accessing cloud object storage |
| Kafka topic | Kafka トピック | Named channel in Apache Kafka for publishing/subscribing messages |
| Kafka producer | Kafka プロデューサー | Client that publishes records to a Kafka topic |
| Kafka consumer | Kafka コンシューマー | Client that subscribes to and processes records from Kafka topics |
| ClickHouse MergeTree | ClickHouse MergeTree | Primary table engine in ClickHouse optimized for analytical workloads |
| S3BackedMergeTree | S3BackedMergeTree | ClickHouse MergeTree engine variant using S3 as backend storage |
| ONTAP S3 | ONTAP S3 | Native S3 protocol support in NetApp ONTAP storage |
| FSx for ONTAP | FSx for ONTAP | Amazon FSx for NetApp ONTAP - fully managed ONTAP file system |
| S3 Access Point | S3 アクセスポイント | AWS S3 endpoint attached to S3 buckets or FSx volumes |
| Metadata/payload separation | メタデータ/ペイロード分離 | Pattern where lightweight metadata flows through streaming while large payloads are stored separately |
| Replay | リプレイ | Re-processing historical messages from a specific offset or timestamp |
| Checkpointing | チェックポイント | Saving processing state to enable recovery from failures |
| Exactly-once semantics | 正確に1回のセマンティクス | Processing guarantee ensuring each message is processed exactly once |
| At-least-once semantics | 少なくとも1回のセマンティクス | Processing guarantee ensuring each message is processed at least once |
| Structured Streaming | Structured Streaming | Spark API for incremental/streaming data processing |
| Streaming table | ストリーミングテーブル | Unity Catalog table with extra support for streaming ingestion |
| Schema evolution | スキーマ進化 | Ability to change table schema while maintaining backward compatibility |
| Amazon MSK | Amazon MSK | Amazon Managed Streaming for Apache Kafka |
| MQTT | MQTT | Lightweight messaging protocol for IoT/edge devices |
| Edge device | エッジデバイス | Computing device deployed at or near the data source (factory floor) |
| Factory data platform | 工場データプラットフォーム | Integrated platform for collecting, processing, and analyzing factory data |
| Quality log | 品質ログ | Records from quality inspection/measurement systems |
| Sensor data | センサーデータ | Time-series data from industrial sensors |
| OEE | 設備総合効率 | Overall Equipment Effectiveness - manufacturing KPI |
| Data historian | データヒストリアン | System for recording and retrieving time-series industrial data |
| FlexClone | FlexClone | ONTAP instant space-efficient clone technology |
| Snapshot | Snapshot | ONTAP point-in-time read-only copy of data |
| SnapMirror | SnapMirror | ONTAP asynchronous data replication technology |
| FlexCache | FlexCache | ONTAP distributed caching technology for remote data |
| Tiered storage | 階層化ストレージ | Strategy of placing data on different storage tiers based on access frequency |
| Tableflow | Tableflow | Confluent product that materializes Kafka topics into open table formats |
| ClickPipes | ClickPipes | ClickHouse Cloud managed ingestion service |
| BYOC | BYOC | Bring Your Own Cloud - managed service deployed in customer's VPC |
| SVM | SVM (Storage Virtual Machine) | Logical storage abstraction in ONTAP for multitenancy |
| NFS | NFS | Network File System protocol |
| SMB | SMB | Server Message Block protocol (Windows file sharing) |
| Multiprotocol access | マルチプロトコルアクセス | Accessing same data via multiple protocols (NFS, SMB, S3) |
| Data lineage | データリネージ | Tracking the origin, movement, and transformation of data |
| Governance | ガバナンス | Policies, processes, and controls for managing data assets |
| PoC | PoC (概念実証) | Proof of Concept |
