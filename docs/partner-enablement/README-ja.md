# SI パートナーイネーブルメント: FSx for ONTAP AI メタデータカタログ

> SI パートナー様がお客様へ提案・構築・運用するために必要なすべてを網羅したパッケージです。

---

## 同梱内容

| アセット | 説明 | 格納場所 |
|---------|------|----------|
| CloudFormation テンプレート | ワンクリックインフラデプロイ | `integrations/iceberg-metadata-catalog/cloudformation/` |
| デモスクリプト | 自動化されたエンドツーエンドデモ | `integrations/iceberg-metadata-catalog/demo/scripts/` |
| 20 業種テンプレート | 業種別 AI 分類設定 | `integrations/iceberg-metadata-catalog/use-cases/` |
| インフラ依頼テンプレート | お客様環境サイジングシート | `docs/partner-enablement/infra-request-template.md` |
| サンプルデータ生成ツール | 業種別テストファイル自動生成 | `integrations/iceberg-metadata-catalog/demo/sample-data/` |
| ROI 計算シート | 提案用コスト/効果分析 | `docs/sales-enablement/roi-calculator.md` |
| お客様 FAQ | よくある質問と回答（日英対応） | `docs/sales-enablement/customer-faq.md` |

---

## 構築タイムライン

### Phase 1: インフラストラクチャ（1〜2 日）

- FSx for ONTAP デプロイ（または既存環境の検証）
- S3 Access Point 設定
- S3 Tables (Iceberg) ネームスペース作成
- Lambda 関数と IAM ロールのデプロイ
- ネットワーク接続性の検証（VPC、セキュリティグループ）

### Phase 2: AI パイプライン（2〜3 日）

- FSx for ONTAP に FPolicy を設定
- Bedrock 連携の分類パイプラインをデプロイ
- 業種別分類テンプレートの設定
- OpenSearch Serverless コレクション構築
- 既存ファイルの初期バッチ処理実行
- お客様と AI 分類精度を検証

### Phase 3: BI/検索インターフェース（1〜2 日）

- Athena ワークグループと保存クエリの設定
- OpenSearch Dashboards（検索 UI）のデプロイ
- Lake Formation ガバナンスポリシーの設定
- お客様固有のダッシュボード作成
- ユーザー受入テストの実施

**合計: 5〜7 営業日**（キックオフから本番稼働まで）

---

## SI 収益モデル

### 初期構築収益

| コンポーネント | 標準工数 | 備考 |
|--------------|---------|------|
| インフラ構築 | 2 日 | CloudFormation + ネットワーク |
| AI パイプライン設定 | 3 日 | テンプレートカスタマイズ + 精度チューニング |
| BI/検索 UI | 2 日 | ダッシュボード + 保存クエリ |
| トレーニング・引き渡し | 1 日 | 管理者トレーニング + ドキュメント |
| **合計** | **8 日** | 固定価格またはタイムアンドマテリアルで請求 |

### 月次運用収益

| サービス | 内容 | 頻度 |
|---------|------|------|
| FPolicy 監視 | パイプライン障害・スループット異常のアラート | 日次 |
| Bedrock チューニング | フィードバックに基づく分類精度改善 | 月次 |
| ダッシュボード保守 | 新規クエリ、ビュー、レポートの追加 | 随時 |
| テンプレート更新 | ビジネス変化に応じた新規ファイルカテゴリ追加 | 四半期 |
| コスト最適化 | Lambda/Bedrock 利用量レビュー、ライトサイジング | 月次 |

### 拡張機会

- 追加部門/ファイル共有の接続
- 追加業種テンプレートの導入
- マルチリージョン DR 構成
- Snowflake/Databricks 連携（対応後）
- カスタム AI モデルトレーニング（ファインチューニング）

---

## PoC 実行チェックリスト

### PoC 前（Day 0）

- [ ] お客様が PoC スコープと成功基準を承認
- [ ] AWS アカウント ID とリージョンを確認
- [ ] FSx for ONTAP 環境が利用可能（または新規プロビジョニング）
- [ ] サンプルファイルを特定（代表的なファイル 100〜1000 件）
- [ ] ネットワーク接続性を検証（VPC ピアリング/エンドポイント）
- [ ] 対象リージョンで Bedrock モデルアクセスを有効化

### Phase 1: デプロイ（Day 1–2）

- [ ] CloudFormation スタックのデプロイ成功
- [ ] S3 Access Point の検証（FSx からファイル読み取り可能）
- [ ] Lambda 関数をサンプルファイルでテスト
- [ ] S3 Tables ネームスペースを作成し Athena からアクセス確認

### Phase 2: パイプライン（Day 3–5）

- [ ] FPolicy 設定完了、イベントが流れていることを確認
- [ ] サンプルファイルで AI 分類が実行されている
- [ ] お客様と分類精度をレビュー（目標 85% 以上）
- [ ] OpenSearch インデックスにデータが投入されている
- [ ] ベクトル埋め込みが生成されている

### Phase 3: 検証（Day 6–10）

- [ ] お客様が Athena SQL でファイル検索可能
- [ ] お客様が OpenSearch UI でファイル検索可能
- [ ] PII 検出の検証（該当する場合）
- [ ] パフォーマンス検証（単一ファイルで 42 秒目標）
- [ ] コスト予測をお客様に提示
- [ ] Go/No-Go 判定を文書化

### PoC 後

- [ ] PoC 結果をお客様向けレポートにまとめる
- [ ] 本番構築提案書（タイムライン・見積もり付き）
- [ ] 継続運用契約書のドラフト作成

---

## 関連リンク

| リソース | リンク |
|---------|--------|
| ソリューション概要（JA） | [`docs/sales-enablement/solution-overview-ja.md`](../sales-enablement/solution-overview-ja.md) |
| お客様 FAQ | [`docs/sales-enablement/customer-faq.md`](../sales-enablement/customer-faq.md) |
| ROI 計算シート | [`docs/sales-enablement/roi-calculator.md`](../sales-enablement/roi-calculator.md) |
| 競合差別化ガイド | [`docs/sales-enablement/competitive-differentiation.md`](../sales-enablement/competitive-differentiation.md) |
| クイックウィンデモ（30 分） | [`integrations/iceberg-metadata-catalog/demo/scenarios/quick-win-30min.md`](../../integrations/iceberg-metadata-catalog/demo/scenarios/quick-win-30min.md) |
| 製造業デモ（JA） | [`integrations/iceberg-metadata-catalog/demo/scenarios/industry-manufacturing-ja.md`](../../integrations/iceberg-metadata-catalog/demo/scenarios/industry-manufacturing-ja.md) |
| GitHub リポジトリ | [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) |

---

## サポート

パートナーイネーブルメントに関するご質問、デモのスケジュール調整、技術的な深掘りについては、藤原良樹（Yoshiki Fujiwara）までお問い合わせください。
