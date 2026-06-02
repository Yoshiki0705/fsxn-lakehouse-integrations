# 金融業向けデモシナリオ: KYC 文書 AI 分類 & コンプライアンス検索

> 金融機関のドキュメントガバナンスと検索を改善するデモシナリオ

---

## ビジネスコンテキスト

### 課題

金融機関が直面する課題：

- **規制文書の拡散**: KYC 書類、契約書、リスクレポート、規制当局提出書類がファイル共有に散在し体系的に分類されていない
- **コンプライアンス監査の負荷**: 規制監査のための特定文書検索に数日を要する
- **PII 露出リスク**: 未分類ファイルに機密顧客データが存在し、何に PII が含まれるか可視化されていない
- **保存期限ポリシーの欠落**: 保存期限を過ぎた文書が残り続ける（何のファイルか分からないため）

### 解決後の姿

- ファイル作成・変更時に自動で AI 分類
- 「90 日以内に期限切れの KYC 文書をすべて表示」が SQL で即座に回答
- PII を含む文書が即座にフラグ付けされコンプライアンスレビューへ
- 保存期限ポリシーの適用がデータドリブンに（手動判断から脱却）

---

## デモフロー

### ステップ 1: サンプル金融文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry financial --target /vol/compliance/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `kyc-customer-C789012-2024.pdf` | KYC 書類 | 顧客本人確認、リスク評価 |
| `loan-agreement-FIN-2026-0042.pdf` | 契約書 | 5,000 万円融資契約 |
| `portfolio-var-report-Q1-2026.xlsx` | リスクレポート | 四半期 VaR・ストレステスト結果 |
| `basel3-filing-2026Q1.pdf` | 規制当局提出書類 | バーゼル III 四半期提出 |
| `client-review-corpABC.msg` | 顧客コミュニケーション | 口座レビューのやり取り |

**トークポイント**:
- 「コンプライアンス担当者はファイルの保存方法を変える必要がありません。パイプラインは自動トリガーされます」
- 「NFS でも SMB でも FPolicy がトリガー — 既存の Windows ファイル共有でそのまま動作します」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: kyc-customer-C789012-2024.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: KYC/本人確認書類
   - 顧客 ID: C-789012
   - リスクレベル: Low
   - 確認ステータス: 完了
   - PII 検出: あり（氏名、住所、マイナンバー）
   - 保存期限: 最終取引から 10 年
✅ Classified in 41.8s | Cost: $0.07
```

**トークポイント**:
- 「FPolicy はファイルシステムレベルのイベント検知。ポーリングもクロールも不要です」
- 「Bedrock Claude が文書内容を読み取り、構造化メタデータを抽出します」
- 「PII 検出は自動実行 — 別ツール不要」
- 「分類信頼度: テストデータセットでの PoC 平均 0.94。本番精度は文書品質と言語構成により変動します」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
-- Athena で分類結果を確認
SELECT file_path, ai_classification, confidence_score,
       customer_id, risk_level, pii_detected, retention_years
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'financial'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | customer_id | risk_level | pii_detected |
|-----------|------------------|:---------:|:-----------:|:----------:|:------------:|
| /vol/compliance/kyc-customer-C789012-2024.pdf | KYC/本人確認書類 | 0.94 | C-789012 | Low | Yes |
| /vol/compliance/loan-agreement-FIN-2026-0042.pdf | 契約書/融資 | 0.96 | - | - | Yes |
| /vol/compliance/portfolio-var-report-Q1-2026.xlsx | リスクレポート | 0.92 | - | - | No |
| /vol/compliance/basel3-filing-2026Q1.pdf | 規制当局提出書類 | 0.95 | - | - | No |
| /vol/compliance/client-review-corpABC.msg | 顧客コミュニケーション | 0.91 | - | Normal | Yes |

**注意**: 信頼度スコアはテストデータセットでの PoC 結果。本番精度はファイルタイプ、言語構成、ドメイン用語により変動。

**トークポイント**:
- 「5 種類の文書が高信頼度で正確に分類されました」
- 「5 文書中 3 文書で PII が自動フラグ付けされています」
- 「このデータはコンプライアンスレポートとしてクエリ可能です」

---

### ステップ 4: コンプライアンスクエリ

**所要時間**: 5 分

**シナリオ**: 「90 日以内に保存期限が切れる KYC 文書をすべて表示」

```sql
-- 保存期限が近づいている KYC 文書
SELECT file_path, customer_id, risk_level, retention_expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'KYC/本人確認書類'
  AND retention_expiry_date < current_date + interval '90' day
ORDER BY retention_expiry_date ASC;

-- PII を含むがマスキングされていない文書
SELECT file_path, ai_classification, pii_types, pii_redacted
FROM s3_tables.metadata_catalog.file_metadata
WHERE pii_detected = true AND pii_redacted = false
ORDER BY scan_timestamp DESC;

-- 高リスク顧客の文書一覧
SELECT file_path, ai_classification, customer_id, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE risk_level = 'High'
ORDER BY last_modified DESC;
```

**トークポイント**:
- 「以前はフォルダ構造を手動で探し、数日かかっていた作業です」
- 「SQL なので自動化・監査・反復が可能」
- 「注意: アイドル後の最初の Athena クエリは 3–5 秒（コールドスタート）。後続クエリはより高速です」

---

### ステップ 5: セマンティック検索で関連文書を発見

**所要時間**: 5 分

**シナリオ**: 「顧客 C-789012 に関連するすべての文書を検索」

OpenSearch を使用：
1. **キーワード検索**: `"C-789012"` → この顧客に言及する全文書
2. **セマンティック検索**: 「融資契約 担保書類」→ ベクトル類似度で関連ファイルを発見
3. **組み合わせ**: 顧客フィルター + セマンティック関連度

**トークポイント**:
- 「ベクトル検索はキーワードが異なっていても関連文書を見つけ出します」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」
- 「ウォーム後はキーワード検索もセマンティック検索もサブ秒レスポンス」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 90% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 42 秒/ファイル | 単一ファイル。バッチは並行度に依存 |
| 1 ファイルあたりコスト | $0.07 | 100KB–1MB 文書前提 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 監査準備時間 | 5 日/監査 → 2 時間/監査 × 年 4 回 | **80 時間削減** |
| 文書検索（コンプライアンスチーム） | 10 分/日 × 20 人 × 50% 利用率 | **~370 時間/年** |
| PII 露出リスク削減 | リスク軽減（直接定量化せず） | **リスク低減** |
| 保存期限ポリシー自動化 | 手動レビュー: 2 週間/年 → 自動化 | **80 時間削減** |

**保守的年間生産性効果**: ~530 時間 × ¥5,000/時 = **¥2,650,000**（~$17,700）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~1,194%

**前提条件**: 50% ユーザー利用率、10 分/日の実検索削減、コンプライアンスリスク削減の追加価値は含まず。

---

## 金融業に関連する制限事項

| 制限事項 | 金融業への影響 |
|---------|-------------|
| S3 AP（パイプラインは読み取りのみ使用） | 分析パイプラインで期限切れ文書を自動アーカイブ不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の下流コンプライアンスワークフロートリガー不可 |
| Bedrock 精度の変動 | 法務/規制文書の分類には専門用語のプロンプトチューニングが必要な場合あり |
| FPolicy レイテンシ (~1–5ms) | 文書管理には影響微小。トレーディングシステムがボリュームを共有する場合はテスト必要 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — メタデータ抽出には許容範囲だが InfoSec と確認 |
| S3 Tables 成熟度 | クロスプラットフォーム Iceberg アクセス（Snowflake、Databricks）は発展途上 |

---

## カスタマイズポイント

1. **分類カテゴリ**: 機関固有の文書タイプ追加（社内メモ、取締役会議事録等）
2. **PII タイプ**: 管轄地域固有の識別子を検出設定（マイナンバー、SSN 等）
3. **保存ルール**: 文書タイプごとに規制要件に基づく保存期限をマッピング
4. **アクセス制御**: Lake Formation ポリシーを部門レベルのデータガバナンスに整合

---

## Iceberg Time Travel: 履歴比較

Iceberg テーブル形式のユニークな利点の一つがタイムトラベル — 過去の任意の時点でのメタデータをクエリする機能です。

```sql
-- スナップショット履歴の表示
SELECT * FROM s3_tables.metadata_catalog.file_metadata$snapshots
ORDER BY committed_at DESC LIMIT 10;

-- 24 時間前の時点でのメタデータをクエリ
SELECT ai_classification, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
FOR TIMESTAMP AS OF (current_timestamp - interval '24' hour)
GROUP BY ai_classification;

-- 現在 vs. 以前の分類件数を比較
WITH current_state AS (
  SELECT ai_classification, COUNT(*) as current_count
  FROM s3_tables.metadata_catalog.file_metadata
  GROUP BY ai_classification
),
previous_state AS (
  SELECT ai_classification, COUNT(*) as previous_count
  FROM s3_tables.metadata_catalog.file_metadata
  FOR TIMESTAMP AS OF (current_timestamp - interval '7' day)
  GROUP BY ai_classification
)
SELECT COALESCE(c.ai_classification, p.ai_classification) as category,
       COALESCE(c.current_count, 0) as now,
       COALESCE(p.previous_count, 0) as week_ago,
       COALESCE(c.current_count, 0) - COALESCE(p.previous_count, 0) as delta
FROM current_state c
FULL OUTER JOIN previous_state p ON c.ai_classification = p.ai_classification
ORDER BY delta DESC;
```

**この業界でのタイムトラベル活用例**:
- ファイル分類分布の時系列変化を追跡
- コンプライアンス判断時のメタデータ状態を監査
- 意図しない一括再分類や削除からの復旧
- 異なる AI モデルバージョン間のエンリッチメント結果比較


---

*関連設定: [`financial.yaml`](../sample-data/industry-configs/financial.yaml)*
*ペアドキュメント: [industry-financial.md](./industry-financial.md)*
