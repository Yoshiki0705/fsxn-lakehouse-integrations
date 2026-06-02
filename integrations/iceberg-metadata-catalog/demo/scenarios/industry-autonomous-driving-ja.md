# 自動運転・モビリティ向けデモシナリオ: センサーデータ & 走行ログインテリジェンス

🌐 日本語 | [English](industry-autonomous-driving.md)

> センサーデータ、走行ログ、アノテーションファイル、キャリブレーションデータを自動運転開発のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

自動運転開発チームが直面する課題：

- **膨大なデータ量**: 各テスト車両がLiDAR、カメラ、レーダー、IMUデータを日々テラバイト単位で生成し、整理が不統一
- **アノテーション追跡の欠落**: 数百万のラベル済みフレームがアノテーションチームの出力先に散在し、統一検索なし
- **キャリブレーションファイルの混乱**: センサーキャリブレーションや車両コンフィグのバージョンが体系的に管理されていない
- **シナリオ発見の困難**: 特定の走行シナリオ（雨天、高速合流、歩行者横断）を見つけるために手動でログをレビューする必要がある

### 解決後の姿

- センサーデータと走行ログがシナリオタイプ、天候、道路種別、イベントカテゴリ別に自動分類
- 「雨天の高速合流で歩行者ニアミスのシナリオをすべて表示」が SQL で即座に回答
- シナリオ別・センサーモダリティ別のアノテーション完了率を追跡
- キャリブレーションファイルのバージョンがテストセッションに紐づき再現性を確保

---

## デモフロー

### ステップ 1: サンプル自動運転ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry autonomous-driving --target /vol/av-data/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `drive-log-VH042-20260601-route7.json` | 走行ログ | 車両042、ルート7、847イベント |
| `lidar-pointcloud-VH042-frame08421.pcd` | センサーデータ | LiDAR点群、交差点シーン |
| `annotation-VH042-frame08421-3dbox.json` | アノテーション | 3Dバウンディングボックス、23オブジェクト |
| `calibration-VH042-20260601-sensors.yaml` | キャリブレーション | マルチセンサーキャリブレーションパラメータ |
| `scenario-report-nearmiss-PED-20260601.pdf` | シナリオレポート | 歩行者ニアミスイベント分析 |

**トークポイント**:
- 「FSx の高性能 NFS が AV データパイプラインに必要なスループットを提供」
- 「FPolicy はデータ記録パイプラインにレイテンシを追加せずにトリガー」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: drive-log-VH042-20260601-route7.json
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 走行ログ
   - 車両 ID: VH042
   - ルート: Route 7（都市幹線道路）
   - 日付: 2026-06-01
   - 走行時間: 2時間14分
   - 天候: 雨（小雨）
   - イベント: 847件（安全クリティカル 12件）
   - シナリオ: 高速合流、歩行者横断、工事区間
✅ Classified in 44.3s | Cost: $0.07
```

**トークポイント**:
- 「AI がログメタデータからシナリオタイプ、天候条件、安全クリティカルイベントを抽出」
- 「点群ファイルはファイル名パターンと関連メタデータでシーンタイプを分類」
- 「分類信頼度: PoC 精度。本番精度はログ形式とセンサー構成により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       vehicle_id, scenario_type, weather, safety_events
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'autonomous-driving'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | vehicle_id | scenario_type | weather |
|-----------|------------------|:---------:|:----------:|:-------------:|:-------:|
| /vol/av-data/drive-log-VH042-20260601-route7.json | 走行ログ/都市 | 0.95 | VH042 | 複合シナリオ | 雨 |
| /vol/av-data/lidar-pointcloud-VH042-frame08421.pcd | センサー/LiDAR | 0.97 | VH042 | 交差点 | 雨 |
| /vol/av-data/annotation-VH042-frame08421-3dbox.json | アノテーション/3Dボックス | 0.98 | VH042 | 交差点 | - |
| /vol/av-data/calibration-VH042-20260601-sensors.yaml | キャリブレーション/マルチセンサー | 0.99 | VH042 | - | - |
| /vol/av-data/scenario-report-nearmiss-PED-20260601.pdf | シナリオレポート/安全 | 0.94 | VH042 | 歩行者 | 雨 |

**トークポイント**:
- 「走行シナリオが抽出・分類され、学習データ選定に活用可能」
- 「天候条件がタグ付けされ、シナリオ多様性分析に利用」
- 「安全クリティカルイベントが優先レビューのためにフラグ付け」

---

### ステップ 4: 自動運転向けクエリ

**所要時間**: 5 分

```sql
-- モデル学習用の雨天歩行者シナリオを検索
SELECT file_path, vehicle_id, scenario_type, safety_events, duration_min
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '走行ログ%'
  AND weather = '雨'
  AND scenario_type LIKE '%歩行者%'
ORDER BY safety_events DESC;

-- シナリオタイプ別アノテーション完了率
SELECT scenario_type, 
       COUNT(CASE WHEN ai_classification LIKE 'アノテーション%' THEN 1 END) as annotated,
       COUNT(CASE WHEN ai_classification LIKE 'センサー%' THEN 1 END) as total_frames
FROM s3_tables.metadata_catalog.file_metadata
WHERE vehicle_id = 'VH042'
GROUP BY scenario_type;

-- 再現性のための車両別・日付別キャリブレーションファイル
SELECT file_path, vehicle_id, sensor_config_version, calibration_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'キャリブレーション/マルチセンサー'
ORDER BY vehicle_id, calibration_date DESC;
```

**トークポイント**:
- 「ML エンジニアが特定シナリオを数時間ではなく数秒で発見」
- 「アノテーションチームがデータセット全体の完了率を追跡」
- 「キャリブレーションバージョン追跡でテスト再現性を確保」

---

### ステップ 5: シナリオマイニングのためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「安全分析のために類似ニアミスイベントを検索」

OpenSearch を使用：
1. **キーワード検索**: `"near-miss" AND "pedestrian"` → 正確なイベント一致
2. **セマンティック検索**: 「雨天で遮蔽された歩行者のいる横断歩道に車両が接近」→ 類似シナリオを発見
3. **組み合わせ**: 天候 + シナリオタイプ + セマンティック類似度フィルター

**トークポイント**:
- 「数百万マイルの走行記録からのシナリオマイニングが検索可能に」
- 「異なるロギング形式でもセマンティック検索が類似安全イベントを発見」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 94% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 44 秒/ファイル | メタデータ抽出。完全な点群処理ではない |
| 1 ファイルあたりコスト | $0.05–$0.07 | ログ/メタデータファイル。大容量バイナリはファイル名パターン |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 学習用シナリオ検索 | 2 時間/検索 × 200 検索/年 → 5 分 | **393 時間削減** |
| キャリブレーション追跡 | 30 分/セッション × 500 セッション/年 → 自動化 | **240 時間削減** |
| 安全イベント調査 | 1 時間/イベント × 100 イベント/年 → 10 分 | **83 時間削減** |
| アノテーション追跡 | 2 時間/週 手動 → 自動化 | **96 時間削減** |

**保守的年間生産性効果**: ~812 時間 × ¥7,000/時 = **¥5,684,000**（~$37,900）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,671%

**前提条件**: 50% 利用率、単一 AV 開発チーム、モデル反復高速化や安全レビューサイクル短縮の追加価値は含まず。

---

## 自動運転に関連する制限事項

| 制限事項 | 自動運転への影響 |
|---------|----------------|
| S3 AP 読み取り専用 | パイプライン経由で再処理・再アノテーションをトリガー不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の ML 学習パイプライントリガー不可 |
| 大容量バイナリファイル | 点群（100MB以上）はメタデータ/ファイル名で処理。完全なコンテンツ分析ではない |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| リアルタイム制約 | リアルタイム車両データには非対応。バッチ/ニアリアルタイムのメタデータカタログ化 |
| データ主権 | 走行データに地理的制約がある場合あり。クロスリージョンレプリケーションポリシーを確認 |

- **センサーデータ形式**: LiDAR 点群（.pcd, .las）、レーダーデータ、生カメラフィードは Bedrock Claude で直接処理できません。分類前にフォーマット固有パーサーでメタデータ（タイムスタンプ、センサーID、GPS 座標）を抽出してください。動画から抽出した画像フレーム（JPEG/PNG）は分類可能です。[AI プロンプトガイド](ai-prompt-customization-guide-ja.md)のマルチモーダルマトリクスを参照。

---

## カスタマイズポイント

1. **シナリオ分類**: 内部 ODD（運行設計領域）定義に合わせたシナリオタイプを設定
2. **センサーモダリティ**: 自社固有のセンサータイプ追加（サーマル、超音波、V2X メッセージ）
3. **安全分類**: イベント重要度を内部安全評価フレームワークにマッピング
4. **アノテーション標準**: アノテーション形式バージョンとラベリングガイドライン準拠を追跡

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

*関連: [use-cases/autonomous-driving/](../../use-cases/autonomous-driving/)*
*ペアドキュメント: [industry-autonomous-driving.md](./industry-autonomous-driving.md)*
