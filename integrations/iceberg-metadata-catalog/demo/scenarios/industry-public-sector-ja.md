# 公共機関向けデモシナリオ: 行政文書 AI 分類 & 情報ガバナンス

> 行政機関の文書管理、情報公開対応、保存期限管理を改善するデモシナリオ

---

## ビジネスコンテキスト

### 課題

行政機関が直面する課題：

- **大量文書の蓄積**: 政策文書、住民対応文書、内部メモ、規制関連文書が体系的分類なく増加し続ける
- **情報公開請求への対応**: ファイル共有に散在する該当文書の検索に数週間を要する
- **保存期限管理の複雑さ**: 文書タイプごとに異なる保存期限（1 年〜永久保存）— 手動管理はエラーを誘発
- **部門横断の情報共有**: 各部門の関連文書が相互に見えない状態

### 解決後の姿

- 行政文書が種類と機密レベル別に自動分類
- 情報公開請求に数時間で対応（従来は数週間）
- 文書分類に基づく保存期限の自動適用
- アクセス制御を維持した部門横断文書検索

---

## デモフロー

### ステップ 1: サンプル行政文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry public-sector --target /vol/government/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `policy-draft-digital-transformation-2026.docx` | 政策文書 | デジタル・トランスフォーメーション戦略ドラフト |
| `citizen-inquiry-INQ-2026-4521.pdf` | 住民対応文書 | サービスに関する住民照会 |
| `budget-report-FY2026-Q1.xlsx` | 予算報告 | 四半期予算執行報告 |
| `internal-memo-security-review-20260115.docx` | 内部メモ | セキュリティプロトコル見直し |
| `procurement-contract-PROC-2026-0089.pdf` | 調達契約 | IT サービスのベンダー契約 |

**トークポイント**:
- 「職員は通常通り共有ドライブに保存するだけ — プロセス変更不要」
- 「分類はバックグラウンドで自動実行」
- 「機密レベルは AI が付与 — 情報公開前に人間がレビュー確認」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: policy-draft-digital-transformation-2026.docx
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 政策文書/ドラフト
   - 部門: デジタル庁
   - 機密区分: 内部（ドラフト — 公開対象外）
   - 保存期限: 10 年（政策記録）
   - PII 検出: なし
   - 情報公開関連: あり（確定後）
✅ Classified in 40.5s | Cost: $0.07
```

**トークポイント**:
- 「AI はドラフトと確定版を区別 — 情報公開判断に重要」
- 「機密分類は補助的 — 最終的な公開判断は情報公開担当者が行う」
- 「信頼度: テストデータでの PoC 平均 0.94。本番精度は文書タイプと言語により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       department, sensitivity_level, retention_years, foia_relevant
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'public-sector'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | sensitivity | retention | foia_relevant |
|-----------|------------------|:---------:|:----------:|:---------:|:-------------:|
| .../policy-draft-digital-transformation-2026.docx | 政策文書/ドラフト | 0.94 | 内部 | 10 | あり（確定後） |
| .../citizen-inquiry-INQ-2026-4521.pdf | 住民対応文書 | 0.96 | 制限（PII） | 5 | あり |
| .../budget-report-FY2026-Q1.xlsx | 予算報告 | 0.95 | 公開 | 10 | あり |
| .../internal-memo-security-review-20260115.docx | 内部メモ | 0.93 | 秘 | 3 | なし |
| .../procurement-contract-PROC-2026-0089.pdf | 調達契約 | 0.94 | 公開（墨消し） | 10 | あり |

**注意**: 機密分類は AI 補助。情報公開担当者が最終判断を行います。

---

### ステップ 4: 情報公開対応クエリ

**所要時間**: 5 分

**シナリオ**: 「情報公開請求に対応: デジタル・トランスフォーメーション政策に関する全文書」

```sql
-- トピックに該当する情報公開対象文書を検索
SELECT file_path, ai_classification, department, sensitivity_level,
       scan_timestamp, confidence_score
FROM s3_tables.metadata_catalog.file_metadata
WHERE foia_relevant = true
  AND (content_summary LIKE '%digital transformation%'
       OR content_summary LIKE '%デジタル・トランスフォーメーション%')
ORDER BY scan_timestamp DESC;

-- 保存期限コンプライアンス: 期限超過で処分未実施の文書
SELECT file_path, ai_classification, creation_date, retention_years,
       date_add('year', retention_years, creation_date) as disposal_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE date_add('year', retention_years, creation_date) < current_date
  AND disposition_status IS NULL;

-- 部門別・機密区分別文書インベントリ
SELECT department, sensitivity_level, count(*) as doc_count
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY department, sensitivity_level
ORDER BY department, sensitivity_level;
```

**トークポイント**:
- 「数週間かかっていた情報公開対応のスコーピングが数時間に短縮」
- 「注意: AI 分類はプロセスの補助 — 情報公開担当者が最終判断」
- 「アイドル後の最初の Athena クエリ: 3–5 秒のコールドスタート」

---

### ステップ 5: 部門横断検索

**所要時間**: 5 分

**シナリオ**: 「サイバーセキュリティ政策に関する全省庁の文書を検索」

OpenSearch セマンティック検索：
- キーワード: `"サイバーセキュリティ" OR "cybersecurity"` → 完全一致
- セマンティック: 「情報セキュリティ 政策 行政 ガイドライン」→ 概念的に関連する文書

**トークポイント**:
- 「アクセス制御を変更せずに部門横断の可視性を実現」
- 「Lake Formation で各部門は許可されたメタデータのみ閲覧可能」
- 「OpenSearch ウォームアップ: 長時間アイドル後 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 90% 以上（5 カテゴリ） | PoC 結果。法務/規制文書はプロンプトチューニングが必要な場合あり |
| 処理時間 | 42 秒/ファイル | 標準文書 |
| 1 ファイルあたりコスト | $0.07 | 100KB–1MB 文書 |
| 情報公開スコーピング | 数時間（従来: 数週間） | 関連ファイルのメタデータカバレッジが十分な前提 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 情報公開対応時間 | 5 日 → 4 時間 × 年 50 件 | **2,350 時間削減** |
| 記録管理 | 手動レビュー: 1 ヶ月/年 → 1 週間 | **120 時間削減** |
| 部門横断検索 | 2 時間/検索 → 5 分 × 年 200 回 | **390 時間削減** |
| 監査準備 | 1 週間 → 1 日 × 年 2 回 | **64 時間削減** |

**保守的年間生産性効果**: ~2,924 時間 × ¥5,000/時 = **¥14,620,000**（~$97,500）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~7,027%

**前提条件**: 50% 利用率、保守的時間見積もり、年間情報公開請求 50 件。

---

## 公共機関に関連する制限事項

| 制限事項 | 行政への影響 |
|---------|------------|
| AI 分類は補助的 | 情報公開判断の根拠にはならない — 人的レビュー必須 |
| Lambda 一時的処理 | 秘密指定コンテンツが Lambda メモリを通過 — セキュリティ要件と照合して評価 |
| Bedrock 精度の変動 | 法務/規制用語やバイリンガル文書で精度低下の可能性 |
| S3 AP 読み取り専用 | 分析パイプラインでの保存期限処分（削除/アーカイブ）自動実行不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の下流記録管理ワークフロートリガー不可 |
| 部門横断アクセス | マルチ部門可視性には Lake Formation ポリシーの慎重な設計が必要 |

---

## カスタマイズポイント

1. **分類カテゴリ**: 機関固有の文書分類体系にマッピング
2. **機密レベル**: 政府の文書管理区分に整合（公開/内部/秘/極秘）
3. **保存期限**: 文書タイプを法定保存要件にマッピング
4. **情報公開ワークフロー**: 情報公開レビュープロセスをサポートするメタデータフィールドを設定
5. **アクセス制御**: Lake Formation でロールベースポリシーによるマルチ部門アクセス

---

*関連設定: [`public-sector.yaml`](../sample-data/industry-configs/public-sector.yaml)*
*ペアドキュメント: [industry-public-sector.md](./industry-public-sector.md)*
