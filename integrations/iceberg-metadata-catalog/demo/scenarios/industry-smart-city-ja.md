# スマートシティ・通信向けデモシナリオ: IoT センサー & 都市データインテリジェンス

🌐 日本語 | [English](industry-smart-city.md)

> IoTセンサーログ、交通カメラ画像、市民苦情申請、都市計画文書をスマートシティのファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

スマートシティ運用者が直面する課題：

- **IoTデータの断片化**: 交通、環境、インフラモニターからの数百万のセンサー読み取りが統一分類なく保管
- **インシデント文書のギャップ**: 交通カメラキャプチャ、市民報告、保守記録が相互に非連結
- **都市計画のサイロ化**: ゾーニング文書、環境評価、インフラ計画が部門間に分散
- **部門間調整**: 交通、環境、公共事業の関連データ検索に部門間のデータ要求が必要

### 解決後の姿

- IoTデータと都市文書がセンサータイプ、位置、イベントカテゴリ別に自動分類
- 「朝のラッシュ時にD7地区で発生した交通異常イベントをすべて表示」が SQL で即座に回答
- 市民苦情が地理エリアとインフラ保守記録に紐づけ
- セマンティック検索による部門横断の文書発見が実現

---

## デモフロー

### ステップ 1: サンプルスマートシティファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry smart-city --target /vol/smart-city/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `iot-traffic-sensor-D7-INT042-20260601.json` | IoTセンサーログ | 交通フローデータ、交差点042 |
| `camera-capture-D7-INT042-anomaly-0842.jpg` | 交通カメラ | 異常検知キャプチャ、車両停止 |
| `citizen-complaint-CC-2026-08842.pdf` | 市民苦情 | 路面損傷報告、D7地区 |
| `infrastructure-plan-water-D7-2026.pdf` | インフラ計画 | 上水道本管更新計画 |
| `env-sensor-air-quality-D7-20260601.csv` | 環境データ | 大気質測定、1,440測定値 |

**トークポイント**:
- 「IoTゲートウェイがセンサーデータを FSx に書き込み — FPolicy がデータ収集に影響なく分類をトリガー」
- 「市民提出文書とセンサーデータが同じパイプラインで処理」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: iot-traffic-sensor-D7-INT042-20260601.json
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: IoTセンサー/交通
   - 地区: 7
   - 交差点: INT-042
   - 日付: 2026-06-01
   - 異常: 3件（車両数スパイク）
   - ピーク時間: 08:15-08:45
   - センサー健全性: 正常
   - データ完全性: 99.8%
✅ Classified in 38.5s | Cost: $0.05
```

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       district, location, event_type, data_quality
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'smart-city'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | district | location | event_type |
|-----------|------------------|:---------:|:--------:|:--------:|:----------:|
| /vol/smart-city/iot-traffic-sensor-D7-INT042-20260601.json | IoT/交通 | 0.97 | D7 | INT-042 | 異常 |
| /vol/smart-city/camera-capture-D7-INT042-anomaly-0842.jpg | カメラ/交通異常 | 0.93 | D7 | INT-042 | 車両停止 |
| /vol/smart-city/citizen-complaint-CC-2026-08842.pdf | 市民苦情 | 0.95 | D7 | Road-7A | 損傷 |
| /vol/smart-city/infrastructure-plan-water-D7-2026.pdf | インフラ計画 | 0.96 | D7 | - | 計画 |
| /vol/smart-city/env-sensor-air-quality-D7-20260601.csv | IoT/環境 | 0.98 | D7 | Station-A7 | 正常 |

---

### ステップ 4: スマートシティ向けクエリ

**所要時間**: 5 分

```sql
-- 地区・時間帯別交通異常
SELECT district, location, event_type, event_time, anomaly_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'IoT/交通'
  AND anomaly_count > 0
  AND scan_timestamp > current_date - interval '7' day
ORDER BY anomaly_count DESC;

-- インフラ問題と相関する市民苦情
SELECT cc.district, cc.complaint_type, ip.plan_type, ip.status
FROM s3_tables.metadata_catalog.file_metadata cc
JOIN s3_tables.metadata_catalog.file_metadata ip
  ON cc.district = ip.district
WHERE cc.ai_classification = '市民苦情'
  AND ip.ai_classification = 'インフラ計画';

-- 環境センサーアラート
SELECT location, measurement_type, max_value, alert_threshold, alert_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'IoT/環境'
  AND alert_triggered = true
ORDER BY alert_time DESC;
```

---

### ステップ 5: 都市課題調査のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「D7地区の交通渋滞に関連するすべてのデータを検索」

OpenSearch を使用：
1. **キーワード検索**: `"D7地区" AND "交通" AND "渋滞"` → 完全一致
2. **セマンティック検索**: 「スクールゾーン近くの道路工事による車両滞留」→ 関連する苦情、カメラキャプチャ、計画を発見
3. **組み合わせ**: 地区 + 日付範囲 + セマンティック関連度フィルター

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 94% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 38 秒/ファイル | 構造化IoTデータはより高速に処理 |
| 1 ファイルあたりコスト | $0.05 | 構造化センサーデータ |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 部門横断データ検索 | 30 分/要求 × 500 要求/年 → 3 分 | **225 時間削減** |
| 市民苦情ルーティング | 15 分/件 × 2,000 件/年 → 自動化 | **475 時間削減** |
| インフラ計画策定 | 2 日/計画 × 12 計画/年 → 4 時間 | **176 時間削減** |
| センサー異常調査 | 20 分/イベント × 500 イベント/年 → 5 分 | **125 時間削減** |

**保守的年間生産性効果**: ~1,001 時間 × ¥4,500/時 = **¥4,505,000**（~$30,000）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,193%

---

## スマートシティに関連する制限事項

| 制限事項 | スマートシティへの影響 |
|---------|---------------------|
| S3 AP（パイプラインは読み取りのみ使用） | パイプライン経由でセンサーアラートへの自動応答をトリガー不可 |
| リアルタイムストリーミング | リアルタイムIoTストリーミングには非対応。バッチメタデータカタログ化 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| データプライバシー | 市民苦情のPIIは自治体個人情報規制に従った取り扱いが必要 |
| カメラ映像 | フル動画は非処理。スチルキャプチャとメタデータのみ |
| 複数機関ガバナンス | 機関間のデータ共有ポリシーは地域規制に従い設定が必要 |

---

## カスタマイズポイント

1. **センサータイプ**: 都市固有のIoTインフラ設定（交通、環境、水道、エネルギー）
2. **地理ゾーン**: 地区とゾーンを自治体の行政区域にマッピング
3. **苦情カテゴリ**: 市民サービスリクエスト分類に整合
4. **アラート閾値**: センサータイプと規制要件に応じて設定

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

*関連: [use-cases/smart-city/](../../use-cases/smart-city/)*
*ペアドキュメント: [industry-smart-city.md](./industry-smart-city.md)*
