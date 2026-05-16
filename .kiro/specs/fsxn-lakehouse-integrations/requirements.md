# Requirements Document

## Introduction

Amazon FSx for NetApp ONTAP のエンタープライズストレージを S3 Access Points 経由で各 Data Lake / Lakehouse プラットフォームと統合するパターン集。ONTAP の重複排除・圧縮・Snapshot・FlexClone・階層化を活かしつつ、モダンな分析基盤からシームレスにアクセスする構成を提供する。本プロジェクトは CloudFormation / Terraform テンプレート、セットアップスクリプト、ノートブック、バイリンガルドキュメントを含む。

## Glossary

- **FSxN**: Amazon FSx for NetApp ONTAP。NFS/SMB/iSCSI および S3 API アクセスを提供するマネージドエンタープライズストレージサービス
- **S3_Access_Point**: Amazon S3 Access Point。FSxN ボリュームへの S3 互換アクセスを提供するエンドポイント
- **Lakehouse_Platform**: データレイクとデータウェアハウスを統合した分析プラットフォーム（Databricks, Snowflake, Athena, Redshift Spectrum, EMR Spark, Dremio, Trino 等）
- **ONTAP_Volume**: FSxN 上のデータストレージ単位。重複排除、圧縮、Snapshot、FlexClone、階層化の機能を持つ
- **Unity_Catalog**: Databricks のデータガバナンスレイヤー。External Location と Storage Credential を管理する
- **External_Stage**: Snowflake が外部ストレージにアクセスするためのオブジェクト。Storage Integration と組み合わせて使用する
- **IaC_Template**: Infrastructure as Code テンプレート。CloudFormation (YAML) または Terraform (HCL) 形式のインフラ定義ファイル
- **Integration_Module**: 特定のベンダー向け統合実装。IaC テンプレート、スクリプト、ノートブック、ドキュメントを含むディレクトリ
- **Medallion_Architecture**: Bronze / Silver / Gold の3層でデータを段階的に精製する ETL パイプラインアーキテクチャ
- **Setup_Script**: 環境構築および検証を自動化する Python または Bash スクリプト
- **Validation_Script**: デプロイ後の接続確認およびデータアクセス検証を行うスクリプト

## Requirements

### Requirement 1: 基盤インフラストラクチャテンプレート

**User Story:** As a クラウドエンジニア, I want FSxN と S3 Access Point の基盤インフラを CloudFormation テンプレートで一括デプロイしたい, so that 各 Lakehouse 統合の前提環境を迅速かつ再現可能に構築できる。

#### Acceptance Criteria

1. THE IaC_Template SHALL define a VPC with private subnets, NAT Gateway, and VPC Endpoints required for FSxN and S3_Access_Point connectivity
2. THE IaC_Template SHALL define an FSxN file system with a storage virtual machine (SVM) and at least one ONTAP_Volume configured with deduplication and compression enabled
3. THE IaC_Template SHALL define an S3_Access_Point scoped to the target VPC with a resource policy restricting access to specified IAM principals
4. THE IaC_Template SHALL define IAM roles and policies following least-privilege principles for each Lakehouse_Platform integration pattern
5. WHEN the CloudFormation stack is deployed, THE IaC_Template SHALL complete without errors and output the FSxN file system ID, SVM ID, S3_Access_Point ARN, and VPC Endpoint ID
6. THE IaC_Template SHALL pass cfn-lint validation without errors or warnings

### Requirement 2: Databricks 統合モジュール

**User Story:** As a データエンジニア, I want Databricks Unity Catalog から FSxN ボリュームに S3 Access Point 経由でアクセスしたい, so that ONTAP のストレージ効率機能を活用しながら Delta Lake テーブルを管理できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide a CloudFormation template that creates an S3_Access_Point with VPC restriction and an IAM Role with cross-account AssumeRole for Databricks
2. THE Integration_Module SHALL provide a Terraform configuration that creates a Unity_Catalog External Location, Storage Credential, and Cluster Policy referencing the S3_Access_Point
3. WHEN the Terraform configuration is applied, THE Integration_Module SHALL register the S3_Access_Point ARN as a Unity_Catalog External Location accessible by specified Databricks workspace users
4. THE Integration_Module SHALL provide a notebook that demonstrates creating an External Table on FSxN data in Parquet format via the S3_Access_Point
5. THE Integration_Module SHALL provide a notebook that demonstrates reading and writing Delta Lake tables stored on FSxN via the S3_Access_Point
6. THE Integration_Module SHALL provide a notebook that demonstrates using FlexClone to create isolated development environments from production data without additional storage consumption
7. THE Integration_Module SHALL provide a notebook that demonstrates using ONTAP Snapshot for point-in-time data recovery integrated with Delta Lake time travel

### Requirement 3: Snowflake 統合モジュール

**User Story:** As a データアナリスト, I want Snowflake から FSxN ボリュームに S3 Access Point 経由でアクセスしたい, so that External Table と Iceberg Table を通じて ONTAP 上のデータを直接クエリできる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide a CloudFormation template that creates an S3_Access_Point, an IAM Role for Snowflake Storage Integration, and an SNS Topic for Snowpipe auto-ingest notifications
2. THE Integration_Module SHALL provide SQL scripts that create a Storage Integration with STORAGE_ALLOWED_LOCATIONS referencing the S3_Access_Point ARN
3. THE Integration_Module SHALL provide SQL scripts that create an External_Stage pointing to the S3_Access_Point with appropriate file format definitions for Parquet, CSV, and JSON
4. THE Integration_Module SHALL provide SQL scripts that create an External Table with AUTO_REFRESH enabled via S3 Event Notification through the SNS Topic
5. THE Integration_Module SHALL provide SQL scripts that create an Iceberg Table on FSxN storage with Snowflake-managed catalog
6. THE Integration_Module SHALL provide SQL scripts that configure Snowpipe for continuous data ingestion from FSxN via the S3_Access_Point
7. WHEN new files are written to the ONTAP_Volume, THE Integration_Module SHALL demonstrate automatic metadata refresh in the External Table within 60 seconds via the configured event notification pipeline

### Requirement 4: Apache Iceberg ベンダーニュートラル統合

**User Story:** As a プラットフォームアーキテクト, I want ベンダーニュートラルな Iceberg テーブルフォーマットで FSxN 上のデータを管理したい, so that 複数の Lakehouse_Platform から同一データにアクセスできる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide configuration templates for an Iceberg catalog (AWS Glue Catalog or REST Catalog) that references FSxN storage via S3_Access_Point
2. THE Integration_Module SHALL provide example code demonstrating Iceberg table creation, schema evolution, partition evolution, and time travel queries against FSxN storage
3. THE Integration_Module SHALL provide example code demonstrating concurrent read access from at least two different Lakehouse_Platform instances to the same Iceberg table on FSxN
4. THE Integration_Module SHALL document the mapping between ONTAP Snapshot and Iceberg snapshot for coordinated point-in-time recovery
5. THE Integration_Module SHALL provide example code demonstrating Iceberg table compaction and orphan file cleanup on FSxN storage

### Requirement 5: AWS ネイティブ統合 (Athena + Glue + Lake Formation)

**User Story:** As a AWS データエンジニア, I want Athena と Glue から FSxN ボリュームに S3 Access Point 経由でアクセスしたい, so that AWS ネイティブサービスで FSxN 上のデータレイクを構築・クエリできる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide a CloudFormation template that creates a Glue Database, Glue Crawler, and Lake Formation permissions referencing the S3_Access_Point
2. THE Integration_Module SHALL provide a Glue Crawler configuration that catalogs data stored on FSxN via the S3_Access_Point and registers tables in the Glue Data Catalog
3. WHEN the Glue Crawler completes execution, THE Integration_Module SHALL demonstrate that Athena can query the cataloged tables using standard SQL
4. THE Integration_Module SHALL provide a Glue ETL job script implementing Medallion_Architecture (Bronze → Silver → Gold) with FSxN as the storage layer via S3_Access_Point
5. THE Integration_Module SHALL provide Lake Formation permission configurations that control column-level and row-level access to FSxN-backed tables
6. IF the Glue Crawler encounters an unsupported file format, THEN THE Integration_Module SHALL document the supported formats and provide a conversion script

### Requirement 6: ETL パイプラインパターン (Pattern C)

**User Story:** As a データエンジニア, I want Medallion Architecture に基づく ETL パイプラインを FSxN 上に構築したい, so that データの段階的精製を ONTAP のストレージ効率機能と組み合わせて実現できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide an ETL pipeline template that implements Bronze, Silver, and Gold layers with each layer stored on separate ONTAP_Volume partitions via S3_Access_Point
2. THE Integration_Module SHALL provide a Glue ETL job or EMR Spark job that reads raw data from the Bronze layer, applies transformations, and writes to the Silver layer on FSxN
3. THE Integration_Module SHALL provide a Glue ETL job or EMR Spark job that aggregates Silver layer data and writes business-ready datasets to the Gold layer on FSxN
4. THE Integration_Module SHALL demonstrate ONTAP deduplication savings when similar datasets are stored across Bronze, Silver, and Gold layers
5. THE Integration_Module SHALL provide a scheduling configuration (Step Functions or Glue Workflow) that orchestrates the multi-stage ETL pipeline with error handling and retry logic
6. IF an ETL job fails during execution, THEN THE Integration_Module SHALL demonstrate recovery using ONTAP Snapshot to restore the target layer to its pre-job state

### Requirement 7: データ共有パターン (Pattern D)

**User Story:** As a データプラットフォーム管理者, I want FSxN 上のデータを S3 Access Point のスコープポリシーで安全に共有したい, so that データプロデューサーとコンシューマー間でセキュアなデータ共有を実現できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide a CloudFormation template that creates multiple S3_Access_Point instances with distinct scoped policies for producer and consumer roles
2. THE Integration_Module SHALL demonstrate prefix-level access control where each consumer S3_Access_Point grants read access only to designated prefixes on the ONTAP_Volume
3. THE Integration_Module SHALL provide an example combining S3_Access_Point policies with ONTAP export policies to implement defense-in-depth access control
4. THE Integration_Module SHALL provide a cross-account data sharing configuration where a consumer AWS account accesses producer FSxN data via a dedicated S3_Access_Point
5. WHEN a consumer attempts to access a prefix outside the scoped policy, THE Integration_Module SHALL demonstrate that the request is denied with an appropriate S3 AccessDenied error

### Requirement 8: セットアップおよび検証スクリプト

**User Story:** As a クラウドエンジニア, I want 環境構築と接続検証を自動化するスクリプトを使いたい, so that 各統合パターンのデプロイと動作確認を効率的に実施できる。

#### Acceptance Criteria

1. THE Setup_Script SHALL automate the deployment of shared CloudFormation stacks (VPC, FSxN, S3 Access Point, IAM) with configurable parameters via a YAML configuration file
2. THE Setup_Script SHALL validate prerequisites (AWS CLI version, required IAM permissions, VPC quota) before initiating deployment
3. THE Validation_Script SHALL verify S3 API connectivity from the deployed VPC to the FSxN volume via the S3_Access_Point by performing GetObject, PutObject, and ListObjectsV2 operations
4. THE Validation_Script SHALL verify that ONTAP storage efficiency features (deduplication, compression) are active on the target volume by querying ONTAP system metrics
5. IF a validation check fails, THEN THE Validation_Script SHALL output a diagnostic message identifying the failure point and suggesting remediation steps
6. THE Setup_Script SHALL generate sample data (Parquet, CSV, JSON formats) on the FSxN volume for use in integration testing

### Requirement 9: バイリンガルドキュメント

**User Story:** As a 開発者, I want 日本語と英語の両方でドキュメントを参照したい, so that 言語に関わらずプロジェクトの構成と使い方を理解できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide documentation in both Japanese (docs/ja/) and English (docs/en/) with identical structure and content coverage
2. THE Integration_Module SHALL include a language switcher link at the top of each README.md file linking to the corresponding document in the other language
3. THE Integration_Module SHALL use English for all code comments, variable names, and configuration keys regardless of the documentation language
4. WHEN a documentation file is added or modified in one language directory, THE Integration_Module SHALL maintain a synchronization checklist or CI check that flags missing translations in the other language directory
5. THE Integration_Module SHALL provide an architecture overview document with diagrams illustrating each integration pattern (Pattern A through Pattern D)

### Requirement 10: テストおよび品質保証

**User Story:** As a 開発者, I want IaC テンプレートとスクリプトの品質を自動テストで担保したい, so that デプロイ前に構成エラーや不整合を検出できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide pytest test cases that validate CloudFormation template syntax and parameter constraints using cfn-lint
2. THE Integration_Module SHALL provide pytest test cases that validate Terraform configurations using terraform validate and tflint
3. THE Integration_Module SHALL provide pytest test cases that validate Python scripts for syntax errors, import resolution, and type consistency
4. WHEN a pull request is submitted, THE Integration_Module SHALL define a CI pipeline configuration (GitHub Actions) that executes all lint and test checks and blocks merge on failure
5. THE Integration_Module SHALL provide integration test scripts that deploy a minimal stack, execute validation checks, and tear down the stack in an isolated test account
6. THE Integration_Module SHALL achieve cfn-lint compliance with zero errors and zero warnings for all CloudFormation templates

### Requirement 11: ONTAP ストレージ効率機能の活用ガイド

**User Story:** As a ストレージ管理者, I want 各統合パターンで ONTAP 固有の機能をどう活用するか理解したい, so that ストレージコスト削減とデータ保護を最大化できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL document deduplication and compression savings estimates for typical Lakehouse workloads (similar Parquet files across partitions, repeated schema metadata)
2. THE Integration_Module SHALL provide runbook procedures for creating and restoring ONTAP Snapshots coordinated with Lakehouse table metadata (Iceberg snapshots, Delta log checkpoints)
3. THE Integration_Module SHALL provide runbook procedures for using FlexClone to create zero-copy development or test environments from production Lakehouse data
4. THE Integration_Module SHALL document FabricPool tiering policies for automatically moving cold partitions to lower-cost object storage while maintaining S3_Access_Point accessibility
5. THE Integration_Module SHALL provide runbook procedures for using SnapMirror to replicate Lakehouse data to a secondary FSxN file system for disaster recovery

### Requirement 12: 業界別ユースケース

**User Story:** As a ソリューションアーキテクト, I want 業界別のユースケース実装例を参照したい, so that 顧客の業界に合わせた FSxN Lakehouse 統合を提案できる。

#### Acceptance Criteria

1. THE Integration_Module SHALL provide a financial data mesh use case demonstrating multi-domain data products on FSxN with domain-scoped S3_Access_Point policies
2. THE Integration_Module SHALL provide a manufacturing IoT data lake use case demonstrating time-series data ingestion from IoT sources to FSxN with Medallion_Architecture processing
3. THE Integration_Module SHALL provide a healthcare research use case demonstrating HIPAA-aligned access controls using S3_Access_Point policies combined with ONTAP export policies and Lake Formation permissions
4. THE Integration_Module SHALL provide a media asset analytics use case demonstrating large binary file (video/image) storage on FSxN with metadata cataloging in a Lakehouse_Platform
5. WHEN a use case is implemented, THE Integration_Module SHALL include a cost estimation worksheet comparing FSxN storage costs (with deduplication and tiering) against native S3 storage for the same workload

