# 業界デモシナリオ

🌐 日本語 | [English](README.md)

> AIメタデータカタログのデモシナリオ索引。AWSインダストリーチーム別に整理。

---

## チーム別クイックナビゲーション

| AWSインダストリーチーム | 対象業界 | シナリオ数 |
|---|---|---|
| [金融サービス](#金融サービス) | 金融、保険 | 2 |
| [HCLS](#hcls) | ヘルスケア、ライフサイエンス、ゲノミクス | 3 |
| [製造](#製造) | 製造、半導体 | 2 |
| [自動車](#自動車) | 自動運転、物流 | 2 |
| [エネルギー](#エネルギー) | エネルギー | 1 |
| [メディア＆エンターテインメント](#メディアエンターテインメント) | メディア/VFX、ゲーミング | 2 |
| [公共セクター](#公共セクター) | 公共、防衛/衛星、教育 | 3 |
| [リテール＆CPG](#リテールcpg) | リテール | 1 |
| [通信](#通信) | 通信、スマートシティ | 2 |
| [旅行＆ホスピタリティ](#旅行ホスピタリティ) | 旅行・ホスピタリティ | 1 |
| [広告＆マーケティング](#広告マーケティング) | 広告・マーケティング | 1 |
| [AEC](#aec) | 建設/BIM | 1 |
| [クロスインダストリー](#クロスインダストリー) | SAP/ERP、法務 | 2 |

**合計**: 23業界シナリオ

---

## 全シナリオ一覧

### 金融サービス

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 金融 | [KYC Document AI Classification & Compliance Search](industry-financial.md) | [KYC書類AI分類・コンプライアンス検索](industry-financial-ja.md) | [`financial.yaml`](../sample-data/industry-configs/financial.yaml) | [use-cases/financial/](../../use-cases/financial/) |
| 保険 | [Claims Document Intelligence & Fraud Detection](industry-insurance.md) | [保険金請求書類インテリジェンス・不正検知](industry-insurance-ja.md) | [`insurance.yaml`](../sample-data/industry-configs/insurance.yaml) | [use-cases/insurance/](../../use-cases/insurance/) |

### HCLS

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| ヘルスケア | [Medical Record Classification & PHI Detection](industry-healthcare.md) | [医療記録分類・PHI検出](industry-healthcare-ja.md) | [`healthcare.yaml`](../sample-data/industry-configs/healthcare.yaml) | [use-cases/healthcare/](../../use-cases/healthcare/) |
| ライフサイエンス | [Research Data Management & Regulatory Submission](industry-life-sciences.md) | [研究データ管理・規制申請](industry-life-sciences-ja.md) | [`life-sciences.yaml`](../sample-data/industry-configs/life-sciences.yaml) | [use-cases/life-sciences/](../../use-cases/life-sciences/) |
| ゲノミクス | [Sequencing Data Classification & Cross-Study Discovery](industry-genomics.md) | [シーケンシングデータ分類・横断研究探索](industry-genomics-ja.md) | [`genomics.yaml`](../sample-data/industry-configs/genomics.yaml) | [use-cases/genomics/](../../use-cases/genomics/) |

### 製造

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 製造 | [Design Document Search & Quality Traceability](industry-manufacturing.md) | [設計文書検索・品質トレーサビリティ](industry-manufacturing-ja.md) | [`manufacturing.yaml`](../sample-data/industry-configs/manufacturing.yaml) | [use-cases/manufacturing/](../../use-cases/manufacturing/) |
| 半導体 | [EDA Design Validation & IP Reuse](industry-semiconductor.md) | [EDA設計検証・IP再利用](industry-semiconductor-ja.md) | [`semiconductor.yaml`](../sample-data/industry-configs/semiconductor.yaml) | [use-cases/semiconductor/](../../use-cases/semiconductor/) |

### 自動車

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 自動運転 | [Scene Classification & Annotation Tracking](industry-autonomous-driving.md) | [シーン分類・アノテーション追跡](industry-autonomous-driving-ja.md) | [`autonomous-driving.yaml`](../sample-data/industry-configs/autonomous-driving.yaml) | [use-cases/autonomous-driving/](../../use-cases/autonomous-driving/) |
| 物流 | [Shipping Document OCR & Delivery Proof](industry-logistics.md) | [配送書類OCR・配達証明](industry-logistics-ja.md) | [`logistics.yaml`](../sample-data/industry-configs/logistics.yaml) | [use-cases/logistics/](../../use-cases/logistics/) |

### エネルギー

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| エネルギー | [Seismic Survey Classification & Well Log Search](industry-energy.md) | [地震探査分類・坑井ログ検索](industry-energy-ja.md) | [`energy.yaml`](../sample-data/industry-configs/energy.yaml) | [use-cases/energy/](../../use-cases/energy/) |

### メディア＆エンターテインメント

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| メディア/VFX | [Asset Tracking & Similarity Search](industry-media-vfx.md) | [アセット追跡・類似検索](industry-media-vfx-ja.md) | [`media-vfx.yaml`](../sample-data/industry-configs/media-vfx.yaml) | [use-cases/media-vfx/](../../use-cases/media-vfx/) |
| ゲーミング | [Game Asset Classification & Build Tracking](industry-gaming.md) | [ゲームアセット分類・ビルド追跡](industry-gaming-ja.md) | [`gaming.yaml`](../sample-data/industry-configs/gaming.yaml) | [use-cases/gaming/](../../use-cases/gaming/) |

### 公共セクター

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 公共 | [FOIA Response & PII Detection](industry-public-sector.md) | [情報公開請求対応・PII検出](industry-public-sector-ja.md) | [`public-sector.yaml`](../sample-data/industry-configs/public-sector.yaml) | [use-cases/public-sector/](../../use-cases/public-sector/) |
| 防衛/衛星 | [Imagery Classification & Change Detection](industry-defense-satellite.md) | [画像分類・変化検出](industry-defense-satellite-ja.md) | [`defense-satellite.yaml`](../sample-data/industry-configs/defense-satellite.yaml) | [use-cases/defense-satellite/](../../use-cases/defense-satellite/) |
| 教育 | [Research Paper Classification & Dataset Discovery](industry-education.md) | [研究論文分類・データセット探索](industry-education-ja.md) | [`education.yaml`](../sample-data/industry-configs/education.yaml) | [use-cases/education/](../../use-cases/education/) |

### リテール＆CPG

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| リテール | [Product Catalog & Supply Chain Document Intelligence](industry-retail.md) | [商品カタログ・サプライチェーン文書インテリジェンス](industry-retail-ja.md) | [`retail.yaml`](../sample-data/industry-configs/retail.yaml) | [use-cases/retail/](../../use-cases/retail/) |

### 通信

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 通信 | [Network Configuration & Technical Document Management](industry-telecom.md) | [ネットワーク構成・技術文書管理](industry-telecom-ja.md) | [`telecom.yaml`](../sample-data/industry-configs/telecom.yaml) | [use-cases/telecom/](../../use-cases/telecom/) |
| スマートシティ | [GIS Classification & Disaster Risk Assessment](industry-smart-city.md) | [GIS分類・災害リスク評価](industry-smart-city-ja.md) | [`smart-city.yaml`](../sample-data/industry-configs/smart-city.yaml) | [use-cases/smart-city/](../../use-cases/smart-city/) |

### 旅行＆ホスピタリティ

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 旅行・ホスピタリティ | [Guest Document & Property Asset Management](industry-travel-hospitality.md) | [宿泊客書類・施設資産管理](industry-travel-hospitality-ja.md) | [`travel-hospitality.yaml`](../sample-data/industry-configs/travel-hospitality.yaml) | [use-cases/travel-hospitality/](../../use-cases/travel-hospitality/) |

### 広告＆マーケティング

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 広告・マーケティング | [Creative Asset Intelligence & Campaign Tracking](industry-advertising-marketing.md) | [クリエイティブアセットインテリジェンス・キャンペーン追跡](industry-advertising-marketing-ja.md) | [`advertising-marketing.yaml`](../sample-data/industry-configs/advertising-marketing.yaml) | [use-cases/advertising-marketing/](../../use-cases/advertising-marketing/) |

### AEC

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| 建設/BIM | [BIM Version Tracking & Safety Compliance](industry-construction-bim.md) | [BIMバージョン管理・安全コンプライアンス](industry-construction-bim-ja.md) | [`construction-bim.yaml`](../sample-data/industry-configs/construction-bim.yaml) | [use-cases/construction-bim/](../../use-cases/construction-bim/) |

### クロスインダストリー

| 業界 | シナリオ (EN) | シナリオ (JA) | 設定 | ユースケース |
|------|--------------|---------------|------|-------------|
| SAP/ERP | [Spool Classification & Archive Search](industry-sap-erp.md) | [スプール分類・アーカイブ検索](industry-sap-erp-ja.md) | [`sap-erp.yaml`](../sample-data/industry-configs/sap-erp.yaml) | [use-cases/sap-erp/](../../use-cases/sap-erp/) |
| 法務 | [Contract Classification & Obligation Tracking](industry-legal.md) | [契約書分類・義務追跡](industry-legal-ja.md) | [`legal.yaml`](../sample-data/industry-configs/legal.yaml) | [use-cases/legal/](../../use-cases/legal/) |

---

## 全シナリオ共通の制約事項

以下の制約はすべてのシナリオに適用されます：

| 制約 | 説明 |
|------|------|
| S3 Access Point 読み取り専用 | パイプラインはS3 AP経由でファイルを読み取れるが、書き戻しやアーカイブは不可 |
| S3 Event Notifications非対応 | S3 Tablesはイベント通知をサポートしない。FPolicyがイベントソース |
| Bedrock精度のばらつき | 分類精度はドキュメントの品質、言語構成、専門用語に依存 |
| FPolicyレイテンシ | ファイル操作あたり約1〜5msのオーバーヘッド（多くのワークフローで無視可能） |
| Lambda一時的処理 | ファイルコンテンツはLambdaメモリを通過 — ゼロコピーストレージ + 一時的処理 |
| S3 Tablesクロスプラットフォーム | Snowflake/Databricksからのフェデレーテッドカタログアクセスはまだ進化中 |
| Lake Formationカラムレベル | S3 Tablesフェデレーテッドカタログでのカラムレベルフィルタリングは未対応（テーブルレベル権限は動作） |
| EMR Spark タイムトラベル構文 | EMR Spark は Spark SQL で `VERSION AS OF <snapshot_id>` または `TIMESTAMP AS OF` を使用; Athena は `FOR TIMESTAMP AS OF` を使用。エンジンごとに構文を確認してください。 |

---

## 横断ガイド

| ガイド | 説明 |
|--------|------|
| [ガバナンス詳細](governance-deep-dive-ja.md) | Lake Formation行/列フィルタリング、CloudTrail監査、PIIマスキング |
| [AIプロンプトカスタマイズガイド](ai-prompt-customization-guide-ja.md) | 業界別Bedrock Claudeプロンプトチューニング |
| [Snowflakeアクティベーションパターン](snowflake-activation-pattern-ja.md) | メタデータ同期 + Cortex Search連携 |

## プラットフォーム別リソース

| プラットフォーム | リソース | 説明 |
|---------------|---------|------|
| Databricks | [`demo/notebooks/databricks-metadata-catalog-demo.py`](../notebooks/databricks-metadata-catalog-demo.py) | Databricksでのメタデータ探索用インタラクティブノートブック |
| Snowflake | [`snowflake-activation-pattern-ja.md`](snowflake-activation-pattern-ja.md) | Cortex Search連携のフルアクティベーションガイド |
| EMR Spark | [`cross-platform/athena-emr/emr-spark-access.py`](../../cross-platform/athena-emr/emr-spark-access.py) | EMR Sparkアクセススクリプト |

---

*参照: [use-cases/README.md](../../use-cases/README.md) — ユースケース詳細ドキュメント*
