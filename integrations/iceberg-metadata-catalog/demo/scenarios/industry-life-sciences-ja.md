# ライフサイエンス・製薬向けデモシナリオ: 治験文書 & 規制当局申請インテリジェンス

🌐 日本語 | [English](industry-life-sciences.md)

> 治験文書、FDA/PMDA申請書類、ラボレポート、SOP文書を製薬企業のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

製薬企業が直面する課題：

- **規制文書の複雑さ**: 治験プロトコル、有害事象報告書、規制当局申請書類が治療領域別に数千件、整理が不統一
- **申請準備のギャップ**: FDA/PMDA申請のための特定文書検索に数週間の手動組み立てが必要
- **SOPバージョンの混乱**: 標準作業手順書が複数バージョンで承認ステータスが不明確
- **クロススタディの可視性不足**: 治験間の関連所見の特定に深い専門知識と手動検索が必要

### 解決後の姿

- 治験文書が試験フェーズ、治療領域、文書タイプ（ICH/eCTD）別に自動分類
- 「2026年のオンコロジーPhase 3有害事象報告書をすべて表示」が SQL で即座に回答
- SOPバージョンが承認ステータスと有効日付で追跡
- セマンティック検索によるクロススタディのシグナル検出が実現

---

## デモフロー

### ステップ 1: サンプルライフサイエンス文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry life-sciences --target /vol/clinical-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `protocol-ONCO-2026-P3-042.pdf` | 治験プロトコル | Phase 3 オンコロジー試験プロトコル |
| `ae-report-ONCO042-SAE-0087.pdf` | 有害事象報告書 | 重篤有害事象、Grade 3 |
| `lab-report-ONCO042-biomarker-wk24.pdf` | ラボレポート | 24週バイオマーカー分析 |
| `sop-GCP-monitoring-v4.2.pdf` | SOP文書 | GCPモニタリング手順、v4.2 |
| `ectd-module5-clinical-overview.pdf` | 規制当局申請 | eCTD Module 5 臨床概要 |

**トークポイント**:
- 「治験運営チームはバリデート済みファイルシステムを継続使用 — 再バリデーション不要」
- 「GxP と非GxP の両方のファイル共有が FPolicy 経由でサポート」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: protocol-ONCO-2026-P3-042.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 治験プロトコル
   - 試験 ID: ONCO-2026-042
   - フェーズ: 3
   - 治療領域: オンコロジー
   - 適応症: 非小細胞肺がん
   - ICH 分類: E6（GCP）
   - eCTD モジュール: Module 5.3.5.1
   - バージョン: 2.0、承認済
✅ Classified in 45.2s | Cost: $0.07
```

**トークポイント**:
- 「AI が試験フェーズ、治療領域、ICH分類、eCTDモジュールを識別」
- 「文書バージョンと承認ステータスが自動抽出」
- 「分類信頼度: PoC 精度。本番精度は文書フォーマットにより変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       study_id, phase, therapeutic_area, ectd_module
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'life-sciences'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | study_id | phase | therapeutic_area |
|-----------|------------------|:---------:|:--------:|:-----:|:---------------:|
| /vol/clinical-ops/protocol-ONCO-2026-P3-042.pdf | 治験プロトコル | 0.96 | ONCO-042 | 3 | オンコロジー |
| /vol/clinical-ops/ae-report-ONCO042-SAE-0087.pdf | 有害事象/SAE | 0.94 | ONCO-042 | 3 | オンコロジー |
| /vol/clinical-ops/lab-report-ONCO042-biomarker-wk24.pdf | ラボレポート/バイオマーカー | 0.93 | ONCO-042 | 3 | オンコロジー |
| /vol/clinical-ops/sop-GCP-monitoring-v4.2.pdf | SOP/GCP | 0.97 | - | - | - |
| /vol/clinical-ops/ectd-module5-clinical-overview.pdf | 規制当局/eCTD M5 | 0.95 | ONCO-042 | 3 | オンコロジー |

**トークポイント**:
- 「ICH/eCTD分類に基づき規制要件に整合した文書分類」
- 「プロトコル、レポート、申請書類間で試験リンケージを維持」
- 「SOPバージョンが承認ステータスとともに追跡」

---

### ステップ 4: ライフサイエンス向けクエリ

**所要時間**: 5 分

```sql
-- 治療領域別Phase 3有害事象報告
SELECT file_path, study_id, ae_grade, ae_type, report_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '有害事象/SAE'
  AND phase = 3
  AND therapeutic_area = 'オンコロジー'
ORDER BY report_date DESC;

-- eCTD申請準備状況チェック
SELECT ectd_module, COUNT(*) as documents,
       COUNT(CASE WHEN status = '承認済' THEN 1 END) as approved
FROM s3_tables.metadata_catalog.file_metadata
WHERE study_id = 'ONCO-042'
  AND ai_classification LIKE '規制当局%'
GROUP BY ectd_module
ORDER BY ectd_module;

-- レビュー期限が近づいているSOP文書
SELECT file_path, sop_id, current_version, effective_date, next_review_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'SOP%'
  AND next_review_date < current_date + interval '90' day
ORDER BY next_review_date ASC;
```

**トークポイント**:
- 「薬事部門がリアルタイムで申請準備状況を追跡」
- 「安全性チームがポートフォリオ全体の有害事象をモニタリング」
- 「品質部門がSOP期限切れ前のレビューを確保」

---

### ステップ 5: クロススタディシグナルのためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「試験間で類似の有害事象パターンを検索」

OpenSearch を使用：
1. **キーワード検索**: `"肝毒性" AND "Grade 3"` → 正確な有害事象一致
2. **セマンティック検索**: 「併用療法患者での肝酵素上昇」→ 関連シグナルを発見
3. **組み合わせ**: 治療領域 + フェーズ + セマンティック類似度フィルター

**トークポイント**:
- 「クロススタディのシグナル検出が数週間から数分に加速」
- 「異なるMedDRAコーディングでもセマンティック検索が関連安全シグナルを発見」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 45 秒/ファイル | 単一ファイル。バッチは並行度に依存 |
| 1 ファイルあたりコスト | $0.07 | 治験文書は長めの傾向 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 申請文書組み立て | 3 週間 → 3 日/申請 × 4 回/年 | **480 時間削減** |
| 有害事象検索 | 1 時間/検索 × 200 検索/年 → 5 分 | **183 時間削減** |
| SOP 管理 | 2 時間/週の手動追跡 → 自動化 | **96 時間削減** |
| クロススタディシグナル検出 | 2 週間/レビュー → 2 日 × 4 レビュー/年 | **320 時間削減** |

**保守的年間生産性効果**: ~1,079 時間 × ¥8,000/時 = **¥8,632,000**（~$57,500）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~4,105%

**前提条件**: 50% 利用率、中規模製薬企業、規制承認の迅速化や早期シグナル検出の追加価値は含まず。

---

## ライフサイエンスに関連する制限事項

| 制限事項 | ライフサイエンスへの影響 |
|---------|----------------------|
| S3 AP 読み取り専用 | パイプライン経由で文書ワークフロー遷移をトリガー不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の申請コンパイルトリガー不可 |
| Bedrock 精度の変動 | 専門的な医学/科学用語にドメイン固有のプロンプトチューニングが必要な場合あり |
| GxP バリデーション | AI 分類は補助的。バリデート済み文書管理システムの代替ではない |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| 21 CFR Part 11 | メタデータカタログは補完的。電子署名と監査証跡はバリデート済み DMS で管理 |
| データインテグリティ | AI メタデータは情報提供目的。正本はバリデート済みファイルシステム |

---

## カスタマイズポイント

1. **eCTD 分類**: 自社固有の eCTD 構造と命名にマッピング
2. **治療領域**: ドメイン固有の語彙を設定（MedDRA、WHO Drug）
3. **試験フェーズ**: 前臨床と市販後調査の文書タイプを追加
4. **規制当局**: FDA、EMA、PMDA、マルチリージョン申請向けに設定

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

*関連: [use-cases/life-sciences/](../../use-cases/life-sciences/)*
*ペアドキュメント: [industry-life-sciences.md](./industry-life-sciences.md)*
