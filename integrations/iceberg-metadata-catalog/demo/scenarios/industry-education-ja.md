# 教育・研究向けデモシナリオ: 研究論文 & 研究費申請インテリジェンス

🌐 日本語 | [English](industry-education.md)

> 研究論文、学位論文、講義録画メタデータ、研究費申請書を学術機関のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

学術機関が直面する課題：

- **研究成果の断片化**: 論文、データセット、補足資料が学科共有に散在し統一的な発見手段がない
- **研究費申請の混乱**: 申請書、予算書、審査フィードバック、採択通知が研究グループ間で一貫性なく保管
- **学位論文管理のギャップ**: ドラフト版、委員会フィードバック、最終提出版のバージョン追跡が不十分
- **組織知の喪失**: 教員の異動で未整理の研究ファイルがコンテキストなく残される

### 解決後の姿

- 研究文書が学科、トピック、資金源、出版ステータス別に自動分類
- 「2026年のML分野でJST助成の本学科論文をすべて表示」が SQL で即座に回答
- 研究費申請が期限、審査ステータス、関連出版物で追跡
- セマンティック検索による学科横断の研究発見が実現

---

## デモフロー

### ステップ 1: サンプル教育ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry education --target /vol/research/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `paper-ML-transformer-efficiency-2026.pdf` | 研究論文 | Transformer最適化に関する発表論文 |
| `thesis-draft-PhD-tanaka-ch4-v3.pdf` | 学位論文 | 博士論文第4章、第3版 |
| `grant-proposal-JST-CREST-2026.pdf` | 研究費申請 | JST CREST 助成申請 |
| `lecture-metadata-CS401-week12.json` | 講義メタデータ | 上級ML講義録画情報 |
| `dataset-readme-sentiment-analysis-v2.md` | データセット文書 | 研究データセットの説明 |

**トークポイント**:
- 「研究者は自分のやり方でファイルを保存し続けられます — 分類は自動で実行」
- 「学科NFS共有も個別研究グループ共有も両方サポート」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: paper-ML-transformer-efficiency-2026.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 研究論文
   - 学科: 計算機科学
   - トピック: 機械学習 / Transformer アーキテクチャ
   - 著者: 3名
   - 助成: JST CREST
   - 出版ステータス: 発表済
   - 発表先: ICML 2026
   - キーワード: 効率性、アテンション機構、スパース
✅ Classified in 44.1s | Cost: $0.07
```

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       department, topic, funding_source, status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'education'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | department | topic | status |
|-----------|------------------|:---------:|:----------:|:-----:|:------:|
| /vol/research/paper-ML-transformer-efficiency-2026.pdf | 研究論文 | 0.95 | CS | ML/Transformer | 発表済 |
| /vol/research/thesis-draft-PhD-tanaka-ch4-v3.pdf | 学位論文/ドラフト | 0.94 | CS | ML | 進行中 |
| /vol/research/grant-proposal-JST-CREST-2026.pdf | 研究費申請 | 0.96 | CS | ML | 提出済 |
| /vol/research/lecture-metadata-CS401-week12.json | 講義メタデータ | 0.98 | CS | ML | アクティブ |
| /vol/research/dataset-readme-sentiment-analysis-v2.md | データセット文書 | 0.93 | CS | NLP | 公開済 |

---

### ステップ 4: 学術機関向けクエリ

**所要時間**: 5 分

```sql
-- 学科・資金源別研究成果
SELECT department, funding_source, COUNT(*) as papers, publication_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '研究論文'
GROUP BY department, funding_source, publication_status;

-- 期限が迫る研究費申請
SELECT file_path, funding_agency, proposal_title, deadline, days_remaining
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '研究費申請'
  AND status = '準備中'
  AND deadline < current_date + interval '60' day
ORDER BY deadline ASC;

-- 学位論文進捗追跡
SELECT student_name, chapter, version, last_modified, committee_feedback
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '学位論文%'
ORDER BY student_name, chapter;
```

---

### ステップ 5: 研究発見のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「効率的なアテンション機構に関連する研究を検索」

OpenSearch を使用：
1. **キーワード検索**: `"アテンション機構" AND "効率性"` → 完全一致
2. **セマンティック検索**: 「大規模言語モデルにおけるセルフアテンションの計算コスト削減」→ 関連論文とデータセットを発見
3. **組み合わせ**: 学科 + 年度 + セマンティック関連度フィルター

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 44 秒/ファイル | 学術論文は長めの傾向 |
| 1 ファイルあたりコスト | $0.07 | 研究論文 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 研究論文発見 | 30 分/検索 × 200 検索/年 → 3 分 | **90 時間削減** |
| 研究費申請準備 | 申請ごと 2 日短縮 × 10 申請/年 | **160 時間削減** |
| 学位論文管理 | 2 時間/週 × 20 学生 → 自動化 | **80 時間削減** |
| 組織知保全 | 定性的 — 知識喪失防止 | **リスク軽減** |

**保守的年間生産性効果**: ~330 時間 × ¥6,000/時 = **¥1,980,000**（~$13,200）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~867%

---

## 教育・研究に関連する制限事項

| 制限事項 | 教育への影響 |
|---------|------------|
| S3 AP（パイプラインは読み取りのみ使用） | パイプライン経由で出版ワークフローをトリガー不可 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| 著作権コンテンツ | 研究論文に著作権素材を含む可能性。メタデータのみ抽出 |
| 学生プライバシー | 学位論文に関してFERPA同等の学生データ取り扱いが必要 |
| 多言語 | 複数言語の研究は分類精度が低下する可能性 |
| オープンアクセス | 機関リポジトリシステムの代替ではない |

---

## カスタマイズポイント

1. **学科分類**: 機関固有の学科・研究室構造を設定
2. **助成機関**: 関連機関を追加（JST、JSPS、科研費、NSF、NIH、EU Horizon）
3. **発表先**: 研究グループ別のターゲット学会・ジャーナルを追跡
4. **論文ステージ**: 大学院プログラム要件に従ったマイルストーン追跡を設定

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

*関連: [use-cases/education/](../../use-cases/education/)*
*ペアドキュメント: [industry-education.md](./industry-education.md)*
