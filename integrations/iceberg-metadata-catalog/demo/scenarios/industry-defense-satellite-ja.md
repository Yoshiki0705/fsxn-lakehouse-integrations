# 防衛・衛星向けデモシナリオ: 衛星画像メタデータ & ミッションログインテリジェンス

🌐 日本語 | [English](industry-defense-satellite.md)

> 衛星画像メタデータ、ミッションログ、機密文書インデックスを防衛・宇宙組織のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

防衛・衛星組織が直面する課題：

- **画像メタデータの過負荷**: 日々数千の衛星撮影がメタデータファイルを生成するが、地域、解像度、目的別の体系的分類なし
- **ミッションログの断片化**: テレメトリダウンロード、コマンドログ、異常報告がミッション固有のディレクトリに散在
- **文書インデックスの複雑さ**: 多段階セキュリティレベルの文書にアクセスレベルと配布制限の慎重な追跡が必要
- **クロスミッション相関**: 異なる衛星パスと時間帯の関連観測を見つけるには手動の専門知識が必要

### 解決後の姿

- 衛星画像メタデータが地域、スペクトルバンド、解像度ティア、観測目的別に自動分類
- 「過去72時間の沿岸地域のサブメートル解像度撮影をすべて表示」が SQL で即座に回答
- ミッションログが衛星健全性メトリクスと異常イベントに相関
- セマンティック検索によるクロステンポラルの観測パターン発見が実現

---

## デモフロー

### ステップ 1: サンプル防衛/衛星ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry defense-satellite --target /vol/satellite-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `img-meta-SAT04-PASS2026060142-COASTAL.json` | 画像メタデータ | 沿岸観測メタデータ、0.5m解像度 |
| `mission-log-SAT04-20260601-telemetry.csv` | ミッションログ | 衛星テレメトリ、86,400データ点 |
| `anomaly-report-SAT04-thermal-20260601.pdf` | 異常報告 | 熱制御サブシステム警告 |
| `doc-index-classified-REGION-A-2026Q2.json` | 文書インデックス | 地域Aの機密文書レジストリ |
| `orbit-plan-SAT04-20260602-maneuver.pdf` | 軌道計画 | 軌道維持マヌーバスケジュール |

**トークポイント**:
- 「衛星地上局がダウンリンクデータを FSx に書き込み — FPolicy が自動分類をトリガー」
- 「メタデータのみ処理 — 画像コンテンツはセキュアストレージに留まり、メタデータのみカタログ化」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: img-meta-SAT04-PASS2026060142-COASTAL.json
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 画像メタデータ
   - 衛星: SAT-04
   - パス ID: PASS2026060142
   - 地域: Coastal-A
   - 解像度: 0.5m（サブメートル）
   - スペクトル: マルチスペクトル（8バンド）
   - 雲被覆: 12%
   - 観測タイプ: 海上監視
   - セキュリティレベル: 制限付き
✅ Classified in 39.2s | Cost: $0.05
```

**トークポイント**:
- 「メタデータのみ処理 — 実際の画像はオリジナルのセキュアストレージに留まる」
- 「AI が地域、解像度、スペクトル特性、観測目的を識別」
- 「分類信頼度: PoC 精度。本番精度はメタデータ形式により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       satellite_id, region, resolution, observation_type
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'defense-satellite'
ORDER BY scan_timestamp DESC;
```

---

### ステップ 4: 衛星運用クエリ

**所要時間**: 5 分

```sql
-- 地域別の最近のサブメートル画像
SELECT satellite_id, pass_id, region, resolution, cloud_cover, capture_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '画像メタ%'
  AND resolution_m <= 1.0
  AND capture_time > current_timestamp - interval '72' hour
ORDER BY capture_time DESC;

-- 衛星健全性異常
SELECT satellite_id, anomaly_type, severity, subsystem, event_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '異常報告'
  AND scan_timestamp > current_date - interval '30' day
ORDER BY severity DESC, event_time DESC;

-- 地域・時間別の観測カバレッジ
SELECT region, COUNT(*) as passes, MIN(cloud_cover) as best_cloud_cover,
       MAX(capture_time) as latest_capture
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '画像メタ%'
GROUP BY region
ORDER BY latest_capture DESC;
```

---

### ステップ 5: クロステンポラル分析のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「変化検出のために同じ沿岸エリアの過去の観測を検索」

OpenSearch を使用：
1. **キーワード検索**: `"Coastal-A" AND "maritime"` → 正確な地域一致
2. **セマンティック検索**: 「制限海域における夜間の船舶移動パターン」→ 関連観測を発見
3. **組み合わせ**: 地域 + 時間範囲 + 解像度 + セマンティック類似度フィルター

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 95% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 39 秒/ファイル | メタデータのみ処理 |
| 1 ファイルあたりコスト | $0.05 | JSONメタデータファイル |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 画像検索 | 30 分/検索 × 500 検索/年 → 3 分 | **225 時間削減** |
| ミッション異常相関 | 2 時間/イベント × 50 イベント/年 → 15 分 | **88 時間削減** |
| クロステンポラル分析 | 4 時間/分析 × 100 分析/年 → 30 分 | **350 時間削減** |
| カバレッジ報告 | 4 時間/週 手動 → 自動化 | **192 時間削減** |

**保守的年間生産性効果**: ~855 時間 × ¥7,000/時 = **¥5,985,000**（~$39,900）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~3,274%

---

## 防衛・衛星に関連する制限事項

| 制限事項 | 防衛への影響 |
|---------|------------|
| S3 AP（パイプラインは読み取りのみ使用） | パイプライン経由でタスキングリクエストをトリガー不可 |
| セキュリティレベル | メタデータカタログは適切なセキュリティ境界内にデプロイ必須 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — セキュリティ要件との確認必要 |
| ITAR/EAR 考慮 | 規制対象技術データが認可環境外に流れないことを確認 |
| 画像コンテンツ | メタデータのみ処理 — 実際の画像分析には専用ツールが必要 |
| エアギャップ環境 | ソリューションにネットワークアクセスが必要。接続要件の確認 |
| 監査要件 | すべてのアクセスはセキュリティコンプライアンス要件に従いログ記録必須 |

- **GovCloud 要件**: ITAR/EAR 管理対象ワークロードは AWS GovCloud (US) リージョンが必要な場合があります。本ソリューションは商用リージョン（ap-northeast-1）のみで検証済みです。GovCloud での検証は別途必要 — デプロイ前に Bedrock モデル利用可能性、S3 Tables サポート、FedRAMP 認証ステータスを確認してください。

---

## カスタマイズポイント

1. **地域分類**: 運用要件に基づく観測地域の設定
2. **セキュリティレベル**: アクセス制限を Lake Formation ポリシーにマッピング
3. **衛星コンステレーション**: 衛星プラットフォームごとのセンサーとスペクトルバンドを追加
4. **ミッションタイプ**: 運用ドクトリンに基づく観測目的カテゴリの設定

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

*関連: [use-cases/defense-satellite/](../../use-cases/defense-satellite/)*
*ペアドキュメント: [industry-defense-satellite.md](./industry-defense-satellite.md)*
