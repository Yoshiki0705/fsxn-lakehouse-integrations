# 医療業向けデモシナリオ: 医療文書 AI 分類 & 患者データガバナンス

> 医療機関の臨床文書管理と規制コンプライアンスを改善するデモシナリオ

---

## ビジネスコンテキスト

### 課題

医療機関が直面する課題：

- **臨床文書の過負荷**: 放射線画像、病理レポート、臨床ノート、同意書が体系的な分類なく蓄積
- **患者データガバナンスの欠落**: PHI（保護対象医療情報）を含む文書がファイル共有に散在し可視化されていない
- **規制コンプライアンスの負荷**: 医療記録保存要件（管轄地域により 5–30 年）への対応が手動でエラーを起こしやすい
- **研究データの発見困難**: 研究者が関連する臨床データセットを見つけられない

### 解決後の姿

- 医療文書が種類別（放射線、病理、管理、同意書）に自動分類
- PHI が自動検出されガバナンス適用のためにフラグ付け
- 文書分類に基づく保存期限ポリシーの適用
- 研究チームが SQL/セマンティッククエリで臨床データを検索

---

## デモフロー

### ステップ 1: サンプル医療文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry healthcare --target /vol/medical-records/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `radiology-mri-brain-20260115.dcm` | DICOM 画像 | 脳 MRI スキャン |
| `pathology-report-PAT-2026-0089.pdf` | 病理レポート | 組織生検結果 |
| `clinical-note-dr-tanaka-20260120.docx` | 臨床ノート | 患者診察記録 |
| `consent-form-surgery-PT-4567.pdf` | 同意書 | 手術同意書 |
| `pharmacy-order-RX-2026-1234.pdf` | 処方箋 | 投薬オーダー |

**トークポイント**:
- 「医療スタッフは通常通り文書を保存するだけ — ワークフロー変更不要」
- 「DICOM、PDF、Word — すべて同一パイプラインで処理」
- 「重要: 処理中にファイルコンテンツが Lambda メモリを通過（一時的、永続化されない）。PHI 取り扱い要件についてコンプライアンスチームと確認してください」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: pathology-report-PAT-2026-0089.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 病理レポート
   - 部門: 病理
   - 患者 ID 検出: あり（PHI）
   - 検査種類: 組織生検
   - 保存要件: 10 年（医療記録）
   - PHI 要素: 患者名、生年月日、診察券番号
✅ Classified in 43.2s | Cost: $0.07
```

**トークポイント**:
- 「AI が文書種類を識別し、医療コンテンツから構造化メタデータを抽出します」
- 「PHI 検出は自動 — データをクエリする前にガバナンス対象としてフラグ付け」
- 「分類信頼度: テストデータでの PoC 平均 0.94。本番精度は変動 — 医療用語と画像品質が結果に影響します」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       department, phi_detected, retention_years
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'healthcare'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | department | phi_detected | retention_years |
|-----------|------------------|:---------:|:----------:|:------------:|:--------------:|
| .../radiology-mri-brain-20260115.dcm | 放射線/MRI | 0.93 | 放射線科 | Yes | 10 |
| .../pathology-report-PAT-2026-0089.pdf | 病理レポート | 0.95 | 病理 | Yes | 10 |
| .../clinical-note-dr-tanaka-20260120.docx | 臨床ノート | 0.94 | 内科 | Yes | 5 |
| .../consent-form-surgery-PT-4567.pdf | 同意書 | 0.96 | 外科 | Yes | 30 |
| .../pharmacy-order-RX-2026-1234.pdf | 処方箋 | 0.92 | 薬剤部 | Yes | 3 |

**注意**: 信頼度スコアは PoC 結果。本番精度はファイルタイプ、スキャン品質、言語構成により変動。

---

### ステップ 4: コンプライアンス & ガバナンスクエリ

**所要時間**: 5 分

```sql
-- PHI を含みアクセス制限が未設定の文書
SELECT file_path, ai_classification, phi_elements, access_restricted
FROM s3_tables.metadata_catalog.file_metadata
WHERE phi_detected = true AND access_restricted = false
ORDER BY scan_timestamp DESC;

-- 保存期限コンプライアンス: 期限超過文書
SELECT file_path, ai_classification, creation_date,
       retention_years,
       date_add('year', retention_years, creation_date) as expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE date_add('year', retention_years, creation_date) < current_date;

-- 部門別文書インベントリ
SELECT department, ai_classification, count(*) as doc_count,
       sum(case when phi_detected then 1 else 0 end) as phi_count
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY department, ai_classification
ORDER BY department, doc_count DESC;
```

**トークポイント**:
- 「コンプライアンスチームがオンデマンドでクエリ実行可能 — IT チケット不要」
- 「PHI の可視化により事後対応型から予防型ガバナンスへ転換」
- 「注意: アイドル後の最初の Athena クエリは 3–5 秒（コールドスタート）」

---

### ステップ 5: 研究データの発見

**所要時間**: 5 分

**シナリオ**: 「2025–2026 年の肝生検に関する病理レポートをすべて検索」

```sql
-- 構造化検索
SELECT file_path, study_type, creation_date, department
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '病理レポート'
  AND study_type LIKE '%肝%'
  AND creation_date >= date '2025-01-01';
```

OpenSearch セマンティック検索：
- 「肝生検 線維化 ステージング」→ 異なる用語でも関連レポートを発見

**トークポイント**:
- 「研究者が PHI に直接アクセスせずに関連データセットを発見可能」
- 「セマンティック検索は正確なキーワードではなく臨床概念で文書を見つけます」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 90% 以上（5 カテゴリ） | PoC 結果。医療画像は精度が低い場合あり |
| 処理時間 | 42 秒/ファイル | DICOM ファイルは大きいため長くなる場合あり |
| 1 ファイルあたりコスト | $0.07–$0.15 | ファイルサイズにより変動（DICOM 画像: ~$0.15） |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| PHI 検出率 | 95% 以上 | 英語 PHI は高精度。日本語 PHI は精度変動あり |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| コンプライアンス監査準備 | 3 日 → 4 時間 × 年 2 回 | **44 時間削減** |
| 文書検索（臨床スタッフ） | 10 分/日 × 30 人 × 50% 利用率 | **550 時間/年** |
| PHI 漏洩リスク削減 | リスク軽減（直接定量化せず） | **リスク低減** |
| 研究データ発見 | 2 日/研究 → 1 時間/研究 × 年 20 研究 | **300 時間削減** |

**保守的年間生産性効果**: ~894 時間 × ¥5,000/時 = **¥4,470,000**（~$29,800）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,079%

---

## 医療業に関連する制限事項

| 制限事項 | 医療業への影響 |
|---------|-------------|
| Lambda 一時的処理 | PHI が Lambda メモリを通過 — HIPAA/医療記録法の要件についてコンプライアンスチームと確認 |
| Bedrock 精度の変動 | 医療用語、手書きメモ、低品質スキャンで精度低下 |
| S3 AP 読み取り専用 | フラグ付き PHI 文書の自動隔離・移動は分析パイプラインで不可 |
| DICOM 画像処理 | 大容量 DICOM（10MB+）は ~$0.15/ファイルで分類信頼度が低い場合あり |
| 書き戻し不可 | ガバナンスタグを FSx 上のオリジナルファイルメタデータに書き戻せない |
| 規制スコープ | 本ソリューションは補助的分類を提供 — 臨床データガバナンスシステムの代替ではない |

---

## カスタマイズポイント

1. **分類カテゴリ**: 施設固有の文書タイプにマッピング（退院サマリー、看護記録等）
2. **PHI タイプ**: 管轄地域に合わせた設定（HIPAA、日本の医療記録法）
3. **保存ルール**: 文書カテゴリ別の病院固有保存ポリシー
4. **アクセス制御**: Lake Formation による部門レベルのアクセス

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

*関連設定: [`healthcare.yaml`](../sample-data/industry-configs/healthcare.yaml)*
*ペアドキュメント: [industry-healthcare.md](./industry-healthcare.md)*
