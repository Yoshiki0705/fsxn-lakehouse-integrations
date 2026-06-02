# Customer FAQ: FSx for ONTAP AI Metadata Catalog

---

## Q: Do I need to copy my files?

**A:** No. The solution uses FSx for ONTAP's S3 Access Point to read file content in-place. Your files never leave the FSx volume. Only extracted metadata (classification labels, embeddings, timestamps) is stored in S3 Tables. This is the **zero-copy principle**.

**Q: ファイルをコピーする必要がありますか？**

**A:** いいえ。FSx for ONTAP の S3 Access Point を使い、ファイルをその場で読み取ります。ファイルが FSx ボリュームから移動することはありません。S3 Tables に格納されるのは抽出されたメタデータ（分類ラベル、埋め込み、タイムスタンプ）のみです。これが**ゼロコピー原則**です。

---

## Q: What about security and compliance?

**A:** Files remain on FSx for ONTAP with your existing access controls (NFS/SMB permissions). Only metadata flows through the AI pipeline. Governance is enforced through:
- **AWS Lake Formation**: Fine-grained access control on metadata tables
- **AWS CloudTrail**: Full audit trail of all API calls
- **IAM Policies**: Least-privilege access to S3 Access Points and Bedrock
- **VPC Private Endpoints**: All traffic stays within your VPC (no internet transit)

**Q: セキュリティとコンプライアンスはどうなっていますか？**

**A:** ファイルは既存のアクセス制御（NFS/SMB 権限）を維持したまま FSx for ONTAP 上に残ります。AI パイプラインを通るのはメタデータのみです。ガバナンスは以下で実現します：
- **AWS Lake Formation**: メタデータテーブルへのきめ細かいアクセス制御
- **AWS CloudTrail**: 全 API コールの完全な監査証跡
- **IAM ポリシー**: S3 Access Point と Bedrock への最小権限アクセス
- **VPC プライベートエンドポイント**: 全トラフィックは VPC 内で完結（インターネット経由なし）

---

## Q: Can I use Snowflake or Databricks?

**A:**
- **Snowflake**: Cortex File AI integration is verified (✅). Direct Iceberg table query via S3 Tables catalog is pending Snowflake feature support.
- **Databricks**: Integration via DataSync or Foreign Catalog is under evaluation (pending).
- **Amazon Athena**: Fully supported (✅). Direct SQL query against S3 Tables Iceberg.
- **Amazon EMR (Spark)**: Fully supported (✅). Read/write Iceberg tables natively.

**Q: Snowflake や Databricks は使えますか？**

**A:**
- **Snowflake**: Cortex File AI 連携は検証済み（✅）。S3 Tables カタログ経由の直接 Iceberg クエリは Snowflake 側の機能対応待ちです。
- **Databricks**: DataSync または Foreign Catalog 経由の統合を評価中（保留）。
- **Amazon Athena**: 完全対応（✅）。S3 Tables Iceberg テーブルへの直接 SQL クエリ。
- **Amazon EMR (Spark)**: 完全対応（✅）。Iceberg テーブルのネイティブ読み書き。

---

## Q: What's the cost?

**A:** Approximately **$114/month** for 100,000 files with 1,000 daily changes. Key components:
- Lambda invocations: ~$0.20/1M requests
- Bedrock (Claude): ~$0.07/file for classification
- S3 Tables (Iceberg metadata): ~$0.01/GB/month
- OpenSearch Serverless: scales to near-zero when idle

**No upfront commitment.** Costs scale linearly with file activity.

**Q: コストはどのくらいですか？**

**A:** 10 万ファイル、1 日 1,000 件変更の環境で月額約 **$114** です。主なコスト構成：
- Lambda 実行: ~$0.20/100 万リクエスト
- Bedrock (Claude): ~$0.07/ファイル（分類処理）
- S3 Tables (Iceberg メタデータ): ~$0.01/GB/月
- OpenSearch Serverless: アイドル時はほぼゼロまでスケールダウン

**事前のコミットメントは不要です。** コストはファイルの更新頻度に比例します。

---

## Q: How long does a PoC take?

**A:** **1–2 weeks** for full validation:
- Week 1: Infrastructure deploy + AI pipeline configuration + initial classification
- Week 2: Accuracy tuning + dashboard setup + user acceptance testing

A minimal "Quick Win" demo can run in **30 minutes** using CloudFormation and sample data.

**Q: PoC にはどのくらいの期間がかかりますか？**

**A:** フル検証で **1〜2 週間** です：
- 1 週目: インフラデプロイ + AI パイプライン設定 + 初期分類実行
- 2 週目: 精度チューニング + ダッシュボード構築 + ユーザー受入テスト

CloudFormation とサンプルデータを使った「クイックウィン」デモなら **30 分** で実行可能です。

---

## Q: What industries are supported?

**A:** **20 industry templates** are available out of the box:
Manufacturing, Financial Services, Healthcare, Construction, Legal, Media, Public Sector, Education, Logistics, Retail, Real Estate, Energy, Telecommunications, Pharmaceutical, Insurance, Agriculture, Automotive, Aerospace, Government, Research/Academia.

Each template includes pre-configured AI classification categories, sample queries, and ROI narratives.

**Q: どの業種に対応していますか？**

**A:** **20 業種テンプレート** がすぐに利用可能です：
製造業、金融、医療、建設、法務、メディア、公共、教育、物流、小売、不動産、エネルギー、通信、製薬、保険、農業、自動車、航空宇宙、政府機関、研究/学術。

各テンプレートには事前設定された AI 分類カテゴリ、サンプルクエリ、ROI ストーリーが含まれます。

---

## Q: What AI models are used?

**A:**
- **Amazon Bedrock Claude** (Anthropic): File classification, content extraction, and vision (image/PDF analysis)
- **Amazon Titan Embeddings**: Vector embeddings for semantic similarity search
- **Amazon Comprehend**: PII detection (names, addresses, phone numbers, etc.)

All models run within your AWS account. No data leaves your account or region.

**Q: どの AI モデルが使われていますか？**

**A:**
- **Amazon Bedrock Claude** (Anthropic): ファイル分類、コンテンツ抽出、ビジョン（画像/PDF 解析）
- **Amazon Titan Embeddings**: セマンティック類似検索用のベクトル埋め込み
- **Amazon Comprehend**: PII 検出（氏名、住所、電話番号など）

すべてのモデルはお客様の AWS アカウント内で実行されます。データがアカウントやリージョンの外に出ることはありません。

---

## Q: What about PII (Personally Identifiable Information)?

**A:** PII is automatically detected in both English and Japanese content using Amazon Comprehend. Detected PII is:
1. Flagged in metadata with PII type and confidence score
2. Redacted before indexing in OpenSearch (optional, configurable)
3. Available for compliance reporting via Athena queries

Types detected: names, addresses, phone numbers, email addresses, national IDs, credit card numbers, bank account numbers, and more.

**Q: PII（個人情報）の扱いはどうなっていますか？**

**A:** PII は Amazon Comprehend を使い、英語・日本語の両方で自動検出されます。検出された PII は：
1. メタデータに PII タイプと信頼度スコアをフラグ付け
2. OpenSearch へのインデックス前にマスキング（任意、設定可能）
3. Athena クエリによるコンプライアンスレポートに利用可能

検出される種類: 氏名、住所、電話番号、メールアドレス、マイナンバー、クレジットカード番号、口座番号など。

---

## Q: Can my on-premises ONTAP work too?

**A:** Yes. Two integration paths:
1. **SnapMirror to FSx for ONTAP**: Mirror on-prem volumes to FSx, then use the AI pipeline against the FSx copy. Near real-time sync with minimal network overhead.
2. **AWS DataSync**: Direct transfer of specific files/directories from on-prem ONTAP to S3 for processing.

The SnapMirror approach maintains the zero-copy advantage since files on FSx are accessed via S3 Access Point.

**Q: オンプレミスの ONTAP でも使えますか？**

**A:** はい。2 つの統合パスがあります：
1. **SnapMirror → FSx for ONTAP**: オンプレミスのボリュームを FSx にミラーリングし、FSx 上のコピーに対して AI パイプラインを実行。最小限のネットワーク負荷でほぼリアルタイム同期。
2. **AWS DataSync**: オンプレミス ONTAP から S3 へ特定ファイル/ディレクトリを直接転送。

SnapMirror 方式では FSx 上のファイルが S3 Access Point 経由でアクセスされるため、ゼロコピーの利点を維持できます。

---

## Q: What about multi-region deployment?

**A:** Multi-region architecture is supported through:
- **SnapMirror**: Cross-region volume replication (FSx for ONTAP built-in)
- **Catalog rebinding**: Metadata tables can be replicated or re-pointed across regions
- **Design documented**: Full multi-region DR architecture is documented in `integrations/iceberg-metadata-catalog/dr/`

This enables both disaster recovery and geo-distributed search scenarios.

**Q: マルチリージョン展開はどうなっていますか？**

**A:** マルチリージョンアーキテクチャは以下でサポートされています：
- **SnapMirror**: クロスリージョンボリュームレプリケーション（FSx for ONTAP 標準機能）
- **カタログリバインディング**: メタデータテーブルのリージョン間レプリケーションまたは再ポインティング
- **設計文書化済み**: マルチリージョン DR アーキテクチャの全体像は `integrations/iceberg-metadata-catalog/dr/` に文書化

これにより災害復旧と地理分散検索の両シナリオに対応できます。

---

*Last updated: 2026-06*
