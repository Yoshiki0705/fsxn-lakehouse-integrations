# パートナーオファリングガイド

## 対象顧客

| セグメント | プロファイル | 課題 |
|-----------|------------|------|
| エンタープライズ NAS ユーザー | オンプレミス NetApp ONTAP / NAS で 10TB+ のファイルデータを保有 | 分析にデータコピーが必要、S3 ネイティブサービスから NAS にアクセス不可 |
| FSx for ONTAP 利用企業 | NFS/SMB ワークロードで FSx for ONTAP を既に利用中 | Lakehouse/分析プラットフォームが S3 を要求し、データサイロが発生 |
| ハイブリッドクラウド | オンプレミス ONTAP + AWS、SnapMirror で DR/移行中 | ストレージ再設計なしでクラウド分析を活用したい |

## ビジネス課題

NAS/ONTAP 上にファイルベースのデータを持つ組織は、根本的な断絶に直面しています：

1. **データ重複**: 分析プラットフォーム（Databricks、Snowflake、Athena）が S3 上のデータを要求し、NAS から S3 へのコピーパイプラインが必要
2. **ガバナンス分断**: NAS（UNIX/NTFS 権限）と S3（IAM ポリシー）で別々のアクセス制御が存在し、コンプライアンスギャップが発生
3. **運用オーバーヘッド**: 同期パイプラインがレイテンシ、コスト、障害点を追加
4. **投資の無駄**: データを S3 にコピーすると、既存の ONTAP 機能（重複排除、スナップショット、階層化）が活用できない

## ソリューション: FSx for ONTAP + S3 Access Points + Lakehouse 統合

Amazon FSx for ONTAP S3 Access Points により、FSx for ONTAP ボリューム上のファイルデータにデータ移動なしで S3 API アクセスが可能になります。S3 と連携するアプリケーションや AWS サービスが、アクセスポイント経由でファイルデータを直接読み書きできます。

**主要な技術仕様**（[AWS ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)より）：
- サポートされる S3 操作: GetObject, PutObject, DeleteObject, ListObjectsV2, HeadObject, マルチパートアップロード, CopyObject（同一アクセスポイント内のみ）
- 二層認可: IAM ポリシー評価 + ファイルシステムユーザー権限（UNIX または Windows）
- レイテンシ: 数十ミリ秒（S3 バケットアクセスと同等）
- スループット: FSx ファイルシステムのプロビジョンドスループット容量に依存
- Block Public Access がデフォルトで強制（無効化不可）
- ONTAP バージョン 9.17.1 以降が必要

## ビジネス成果

| 成果 | 指標 |
|------|------|
| データコピーの排除 | N 個のコピー → 1 つの正規ソース |
| 同期パイプラインの廃止 | NAS → S3 ETL ジョブの排除 |
| インサイトまでの時間短縮 | パイプライン構築に数日 → 直接クエリで数時間 |
| NFS/SMB アクセスの維持 | 既存ワークロードは変更不要 |
| ガバナンスの統一 | 単一データ所在地、二層アクセス制御 |
| ファイルデータでの AI/ML 活用 | Bedrock、SageMaker、EMR が S3 AP 経由でアクセス |

## Good / Better / Best 構成

### Good: 単一アカウント・読み取り専用分析

**スコープ**: 単一 AWS アカウント、単一 SVM、読み取り専用分析

| コンポーネント | 構成 |
|--------------|------|
| FSx for ONTAP | Single-AZ、1 SVM、1 ボリューム |
| S3 Access Point | Internet origin、読み取り専用ファイルシステムユーザー |
| 分析 | Athena + Glue Data Catalog |
| セキュリティ | 分析チームごとの IAM ロール、読み取り専用 UNIX ユーザー |
| モニタリング | CloudTrail による API コール記録 |

**ユースケース**: データ移動なしでファイルデータ（CSV、Parquet、JSON）に対するアドホック SQL クエリ

**検証済み AWS 統合**: [Amazon Athena で SQL によるファイルクエリ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

---

### Better: VPC 制限付きアクセスとカタログ統合

**スコープ**: VPC 制限付きアクセス、Glue Catalog / Unity Catalog 統合、ETL 用読み書き

| コンポーネント | 構成 |
|--------------|------|
| FSx for ONTAP | Single-AZ または Multi-AZ、複数ボリューム |
| S3 Access Point | VPC origin（特定 VPC にバインド）、読み書きファイルシステムユーザー |
| 分析 | Databricks Unity Catalog / Snowflake External Stage / Glue ETL |
| セキュリティ | VPC エンドポイントポリシー + アクセスポイントポリシー + ファイルシステム権限 |
| ネットワーク | Gateway エンドポイント（VPC 内）+ Interface エンドポイント（Direct Connect 経由オンプレミス） |
| モニタリング | CloudTrail + CloudWatch メトリクス |

**ユースケース**: FSx for ONTAP からソースデータを読み取り、Glue/EMR で変換し、加工済み結果を書き戻す ETL パイプライン

**検証済み AWS 統合**:
- [AWS Glue を使用した ETL パイプライン構築](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)
- [Amazon EMR Serverless での Spark ジョブ実行](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-run-spark-with-emr-serverless.html)

---

### Best: マルチアカウントガバナンス + DR + AI

**スコープ**: マルチアカウント、Lake Formation / IAM / S3 AP ポリシー、SnapMirror DR、監査ログ、AI/RAG

| コンポーネント | 構成 |
|--------------|------|
| FSx for ONTAP | Multi-AZ、複数 SVM、DR リージョンへの SnapMirror |
| S3 Access Points | コンシューマーごとのアクセスポイント（スコープ付き IAM ポリシー） |
| 分析 | Databricks + Snowflake + Athena（マルチプラットフォーム） |
| AI/ML | Amazon Bedrock Knowledge Bases による RAG |
| セキュリティ | Lake Formation + S3 AP ポリシー + VPC origin + ファイルシステム ACL |
| ガバナンス | CloudTrail、ONTAP 監査ログ、データ分類タグ |
| DR | SnapMirror クロスリージョンレプリケーション、ONTAP スナップショット |

**ユースケース**: ドメイン固有のアクセスポイントによるエンタープライズデータメッシュ、AI ドキュメント検索、規制データガバナンス

**検証済み AWS 統合**:
- [Amazon Bedrock Knowledge Bases を使用した RAG アプリケーション構築](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)
- Good / Better ティアの全統合

---

## 販売可能なユースケース名

| ユースケース名 | 業界 | パターン | ティア |
|--------------|------|---------|-------|
| Zero-Copy NAS Analytics for Manufacturing | 製造 | 読み取り専用分析 | Good |
| Regulated Data Lakehouse for Healthcare Research | 医療 | マネージドテーブル（読み取り） | Better |
| Financial Data Mesh with FSxN and S3 Access Points | 金融 | データ共有 | Best |
| AI-Powered Document Intelligence on Enterprise Files | 全業界 | Bedrock RAG | Best |
| Hybrid Cloud Analytics Bridge | 全業界 | ETL パイプライン | Better |
| Media Asset Analytics without Data Migration | メディア | 読み取り専用分析 | Good |

## ユースケース別導入ステップ

### Zero-Copy NAS Analytics for Manufacturing

| ステップ | アクション | タイムライン |
|---------|----------|------------|
| 1 | FSx for ONTAP + S3 Access Point のデプロイ | Day 1-2 |
| 2 | Glue Crawler の設定 | Day 2 |
| 3 | サンプルデータでの Athena クエリ検証 | Day 3 |
| 4 | BI ツール（QuickSight）接続 | Day 4-5 |
| **成功基準** | 1GB データセットに対するクエリレイテンシ < 10 秒、データコピーゼロ | |

### Regulated Data Lakehouse for Healthcare Research

| ステップ | アクション | タイムライン |
|---------|----------|------------|
| 1 | Multi-AZ FSx for ONTAP + VPC-origin S3 AP のデプロイ | Week 1 |
| 2 | Lake Formation 権限の設定 | Week 1 |
| 3 | 匿名化パイプライン用 Glue ETL のセットアップ | Week 2 |
| 4 | 分析プラットフォームへの外部テーブル登録 | Week 2 |
| 5 | 監査証跡とアクセス制御の検証 | Week 3 |
| **成功基準** | PHI が VPC 外に出ない、監査証跡が完全、クエリ < 30 秒 | |

### Financial Data Mesh with FSxN and S3 Access Points

| ステップ | アクション | タイムライン |
|---------|----------|------------|
| 1 | ドメインごとの SVM によるマルチアカウントセットアップ | Week 1-2 |
| 2 | コンシューマーごとの S3 Access Points（スコープ付きポリシー） | Week 2-3 |
| 3 | クロスアカウント IAM ロールと VPC エンドポイント | Week 3 |
| 4 | SnapMirror DR 設定 | Week 4 |
| 5 | Databricks Unity Catalog + Snowflake External Stage | Week 4-5 |
| **成功基準** | ドメイン分離の検証、DR RTO < 1 時間、マルチプラットフォームクエリ | |

---

## 参考資料

- [S3 アクセスポイント経由でのデータアクセス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [アクセスポイントの互換性](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [AWS サービスでのアクセスポイント利用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [Amazon FSx for NetApp ONTAP のパフォーマンス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
