# エネルギー・ユーティリティ向けデモシナリオ: 点検レポート & SCADA ログインテリジェンス

🌐 日本語 | [English](industry-energy.md)

> 点検レポート、SCADA ログ、設備写真、コンプライアンス申告書をエネルギー企業のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

エネルギー・ユーティリティ企業が直面する課題：

- **点検文書の散在**: 数千のフィールド点検レポート、メンテナンスログ、安全評価書が地域運用センターに分散
- **SCADA データサイロ**: 分散制御システムの運用ログがメンテナンスイベントとの相関なく保管
- **設備写真の混乱**: ドローンやフィールド点検画像が設備 ID、状態、欠陥タイプの体系的タグ付けなく保管
- **コンプライアンス報告の負荷**: 規制当局への提出（NERC、FERC、国内同等規制）に複数ソースからの手動組み立てが必要

### 解決後の姿

- 点検レポートが設備タイプ、状態重大度、必要アクション別に自動分類
- 「直近四半期のクリティカル欠陥を含むタービン点検をすべて表示」が SQL で即座に回答
- 設備写真がアセット ID に紐づき自動欠陥検知と重大度評価付き
- コンプライアンス提出が期限と完了ステータスで追跡

---

## デモフロー

### ステップ 1: サンプルエネルギー文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry energy --target /vol/energy-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `inspection-WTG042-blade-20260601.pdf` | 点検レポート | 風力タービンブレード点検、軽微なクラック |
| `scada-log-substation-A7-20260601.csv` | SCADA ログ | 変電所運用データ、86,400 レコード |
| `drone-photo-WTG042-blade3-defect.jpg` | 設備写真 | ドローン点検画像、ブレード欠陥 |
| `compliance-filing-NERC-CIP-Q2-2026.pdf` | コンプライアンス申告 | NERC CIP 四半期提出 |
| `maintenance-wo-WTG042-20260605.pdf` | 作業指示書 | 是正保全、ブレード修理 |

**トークポイント**:
- 「フィールド技術者がタブレットから点検レポートをアップロード — パイプラインが自動トリガー」
- 「SCADA エクスポートとドローン画像も同じパイプラインで処理」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: inspection-WTG042-blade-20260601.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 点検レポート/風力タービン
   - 設備 ID: WTG-042
   - コンポーネント: ブレード
   - 状態: 欠陥検出（軽微なクラック）
   - 重大度: 中
   - 必要アクション: 予定保全
   - 次回点検: 90日後
   - コンプライアンスタグ: IEC 61400
✅ Classified in 42.8s | Cost: $0.07
```

**トークポイント**:
- 「AI が設備、コンポーネント、欠陥タイプ、必要アクションを自動識別」
- 「ドローン写真が欠陥指標と状態評価で分析」
- 「分類信頼度: PoC 精度。本番精度はレポート形式と画像品質により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       equipment_id, component, severity, action_required
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'energy'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | equipment_id | component | severity |
|-----------|------------------|:---------:|:------------:|:---------:|:--------:|
| /vol/energy-ops/inspection-WTG042-blade-20260601.pdf | 点検/風力タービン | 0.95 | WTG-042 | ブレード | 中 |
| /vol/energy-ops/scada-log-substation-A7-20260601.csv | SCADAログ/変電所 | 0.98 | SUB-A7 | - | - |
| /vol/energy-ops/drone-photo-WTG042-blade3-defect.jpg | 設備写真/欠陥 | 0.92 | WTG-042 | ブレード3 | 中 |
| /vol/energy-ops/compliance-filing-NERC-CIP-Q2-2026.pdf | コンプライアンス申告/NERC | 0.96 | - | - | - |
| /vol/energy-ops/maintenance-wo-WTG042-20260605.pdf | 作業指示書/是正 | 0.94 | WTG-042 | ブレード | - |

**トークポイント**:
- 「設備レベルの文書リンケージが点検、写真、作業指示書間で維持」
- 「点検レポートの欠陥重大度がドローン写真分析で裏付け」
- 「コンプライアンス提出が期限認識で追跡」

---

### ステップ 4: エネルギー業務クエリ

**所要時間**: 5 分

```sql
-- 即時対応が必要なクリティカル設備欠陥
SELECT equipment_id, component, severity, action_required, inspection_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '点検%'
  AND severity IN ('高', 'クリティカル')
  AND action_required != '完了'
ORDER BY severity DESC, inspection_date ASC;

-- 点検所見と相関するSCADA異常イベント
SELECT s.equipment_id, s.anomaly_type, s.event_time, i.severity
FROM s3_tables.metadata_catalog.file_metadata s
JOIN s3_tables.metadata_catalog.file_metadata i
  ON s.equipment_id = i.equipment_id
WHERE s.ai_classification LIKE 'SCADA%' AND i.ai_classification LIKE '点検%';

-- 規制別コンプライアンス提出状況
SELECT regulation, filing_period, status, deadline, days_until_deadline
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'コンプライアンス申告%'
ORDER BY deadline ASC;
```

**トークポイント**:
- 「運用チームが欠陥重大度に基づきメンテナンスを優先」
- 「SCADA データと物理点検の相関で予測保全を実現」
- 「コンプライアンスチームが規制フレームワーク全体で提出期限を追跡」

---

### ステップ 5: 設備履歴のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「WTG-042 のブレード劣化に関するすべての過去問題を検索」

OpenSearch を使用：
1. **キーワード検索**: `"WTG-042" AND "blade"` → 正確な設備一致
2. **セマンティック検索**: 「風力タービン前縁侵食の進行性劣化」→ 類似欠陥パターンを発見
3. **組み合わせ**: 設備タイプ + 重大度 + セマンティック類似度フィルター

**トークポイント**:
- 「メンテナンス計画のための完全な設備履歴が数秒で組み立て」
- 「セマンティック検索がフリート全体から類似欠陥パターンを発見」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 42 秒/ファイル | 単一ファイル。バッチは並行度に依存 |
| 1 ファイルあたりコスト | $0.05–$0.07 | ドローン写真: ~$0.05 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 点検レポート検索 | 20 分/検索 × 500 検索/年 → 2 分 | **150 時間削減** |
| コンプライアンス提出組み立て | 5 日/四半期 → 1 日 × 4 回/年 | **128 時間削減** |
| 設備履歴検索 | 30 分/検索 × 300 検索/年 → 3 分 | **135 時間削減** |
| 予測保全による故障防止 | 2 件/年の故障防止 × 平均 ¥500 万 | **¥1,000 万のコスト回避** |

**保守的年間生産性効果**: ~413 時間 × ¥5,000/時 = **¥2,065,000**（~$13,800）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~909%（故障防止価値を除く）

**前提条件**: 50% 利用率、単一風力発電所または変電所エリア、故障防止価値は別途記載。

---

## エネルギー業に関連する制限事項

| 制限事項 | エネルギー業への影響 |
|---------|-------------------|
| S3 AP（パイプラインは読み取りのみ使用） | パイプライン経由で作業指示書作成をトリガー不可 |
| S3 Event Notifications 非対応 | S3 イベント経由のメンテナンスワークフロートリガー不可 |
| Bedrock 精度の変動 | 技術点検用語にドメイン固有のプロンプトチューニングが必要な場合あり |
| SCADA データ量 | 大容量 SCADA エクスポートはサマリレベルで処理。リアルタイムストリーミングではない |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| 安全重要判断 | AI 分類は情報提供目的。有資格点検者の判断の代替ではない |
| OT/IT 分離 | FPolicy が OT ネットワークパフォーマンスに影響しないことを確認 |

---

## カスタマイズポイント

1. **設備分類**: CMMS（設備保全管理システム）に合わせたアセット階層を設定
2. **欠陥コード**: AI 分類を標準欠陥コーディングシステムにマッピング
3. **コンプライアンスフレームワーク**: NERC CIP、FERC、国内規制に応じて設定
4. **重大度閾値**: 欠陥重大度を企業のリスクマトリクスに整合

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

*関連: [use-cases/energy/](../../use-cases/energy/)*
*ペアドキュメント: [industry-energy.md](./industry-energy.md)*
