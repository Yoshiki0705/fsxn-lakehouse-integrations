# 半導体向けデモシナリオ: ウェーハマップ & プロセスログインテリジェンス

🌐 日本語 | [English](industry-semiconductor.md)

> ウェーハマップ、プロセスログ、欠陥画像、デザインルールチェックレポートを半導体ファブのファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

半導体メーカーが直面する課題：

- **ウェーハデータの爆発**: 各ロットが数百のウェーハマップ、計測レポート、プロセスログを複雑な命名階層で生成
- **欠陥追跡の断片化**: SEM/光学欠陥画像が検査装置間に散在し、統一的な分類なし
- **プロセスレシピ管理**: レシピバージョン、スプリット条件、エクスカーションログが体系的な相関なく保管
- **歩留まり分析の遅延**: 複数プロセスステップ横断の根本原因データ検索に深い専門知識と手動検索が必要

### 解決後の姿

- ウェーハデータがプロセスステップ、ロット、装置、品質ステータス別に自動分類
- 「先週のリソグラフィ工程で歩留まり85%未満のウェーハマップをすべて表示」が SQL で即座に回答
- 欠陥画像がタイプ、サイズ、プロセスレイヤー別に分類され自動キル確率推定付き
- プロセスエクスカーションが影響ロットと下流影響評価に紐づけ

---

## デモフロー

### ステップ 1: サンプル半導体ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry semiconductor --target /vol/fab-data/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `wafermap-LOT2026A042-W08-litho.klarf` | ウェーハマップ | リソグラフィ欠陥マップ、ウェーハ08 |
| `process-log-LOT2026A042-etch-step7.csv` | プロセスログ | エッチングチャンバーログ、1,247パラメータ |
| `defect-image-W08-D0042-sem50k.tiff` | 欠陥画像 | SEM 画像 50,000倍、パーティクル欠陥 |
| `drc-report-CHIP-A42-rev3.pdf` | DRC レポート | デザインルールチェック、3件の違反 |
| `excursion-log-TOOL-ETCH04-20260601.pdf` | エクスカーションログ | プロセス逸脱、温度ドリフト |

**トークポイント**:
- 「FSx の高性能 NFS がファブデータのスループット要件に対応」
- 「FPolicy が装置-ホスト間通信のレイテンシに影響なく統合」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: wafermap-LOT2026A042-W08-litho.klarf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: ウェーハマップ/欠陥
   - ロット ID: LOT2026A042
   - ウェーハ: 08
   - プロセスステップ: リソグラフィ
   - 欠陥数: 142
   - 歩留まり推定: 82.3%
   - キル率: 0.31
   - 装置: LITHO-ASML04
✅ Classified in 41.5s | Cost: $0.07
```

**トークポイント**:
- 「AI がウェーハマップメタデータからロット、プロセスステップ、装置、欠陥数、歩留まりを識別」
- 「欠陥画像がタイプ（パーティクル、スクラッチ、パターン）とレイヤーで分類」
- 「分類信頼度: PoC 精度。本番精度は KLARF フォーマットバージョンにより変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       lot_id, wafer, process_step, yield_estimate
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'semiconductor'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | lot_id | process_step | yield_estimate |
|-----------|------------------|:---------:|:------:|:------------:|:--------------:|
| /vol/fab-data/wafermap-LOT2026A042-W08-litho.klarf | ウェーハマップ/欠陥 | 0.96 | LOT2026A042 | リソグラフィ | 82.3% |
| /vol/fab-data/process-log-LOT2026A042-etch-step7.csv | プロセスログ/エッチ | 0.98 | LOT2026A042 | エッチング | - |
| /vol/fab-data/defect-image-W08-D0042-sem50k.tiff | 欠陥画像/パーティクル | 0.91 | LOT2026A042 | リソグラフィ | - |
| /vol/fab-data/drc-report-CHIP-A42-rev3.pdf | DRC レポート | 0.97 | - | 設計 | - |
| /vol/fab-data/excursion-log-TOOL-ETCH04-20260601.pdf | エクスカーションログ | 0.95 | LOT2026A042 | エッチング | - |

**トークポイント**:
- 「ロットレベルのトレーサビリティがウェーハマップ、プロセスログ、欠陥画像間で維持」
- 「歩留まり推定が抽出されリアルタイムモニタリングに活用」
- 「エクスカーションイベントが影響ロットに紐づけ」

---

### ステップ 4: 半導体ファブ向けクエリ

**所要時間**: 5 分

```sql
-- プロセスステップ別の低歩留まりウェーハ
SELECT lot_id, wafer, process_step, yield_estimate, defect_count, tool_id
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'ウェーハマップ/欠陥'
  AND yield_estimate < 85.0
  AND scan_timestamp > current_date - interval '7' day
ORDER BY yield_estimate ASC;

-- 装置別欠陥密度トレンド
SELECT tool_id, process_step, AVG(defect_count) as avg_defects,
       COUNT(*) as wafer_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'ウェーハマップ/欠陥'
  AND scan_timestamp > current_date - interval '30' day
GROUP BY tool_id, process_step
ORDER BY avg_defects DESC;

-- エクスカーションイベントと影響ロット
SELECT file_path, tool_id, excursion_type, affected_lots, event_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'エクスカーションログ'
  AND scan_timestamp > current_date - interval '7' day
ORDER BY event_time DESC;
```

**トークポイント**:
- 「歩留まりエンジニアが問題のある装置とプロセスステップを即座に特定」
- 「欠陥トレンドがフルロットに影響する前に系統的問題を発見」
- 「エクスカーション影響評価が自動化され迅速な封じ込め判断を支援」

---

### ステップ 5: 根本原因分析のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「歩留まりエクスカーションの根本原因のために類似欠陥パターンを検索」

OpenSearch を使用：
1. **キーワード検索**: `"particle" AND "lithography" AND "ASML04"` → 正確な装置/欠陥一致
2. **セマンティック検索**: 「リソ装置のチャンバーメンテナンス後のランダムパーティクル汚染」→ 類似過去イベントを発見
3. **組み合わせ**: 装置 + 欠陥タイプ + 時間範囲 + セマンティック類似度フィルター

**トークポイント**:
- 「類似の過去エクスカーションの発見で根本原因調査を加速」
- 「セマンティック検索が異なる装置タイプやノード間で関連パターンを識別」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 94% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 41 秒/ファイル | マップファイルからのメタデータ抽出 |
| 1 ファイルあたりコスト | $0.05–$0.07 | KLARF/マップファイル。SEM 画像はメタデータのみ |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 歩留まりエクスカーション調査 | 4 時間/件 × 50 件/年 → 1 時間 | **150 時間削減** |
| 欠陥分類 | 10 分/ウェーハ × 10,000 ウェーハ/年 → 自動化 | **1,633 時間削減** |
| プロセス相関分析 | 2 日/分析 × 24 分析/年 → 4 時間 | **368 時間削減** |
| 歩留まり改善 | 0.5% 歩留まり向上 × 年間 ¥1 億の収益影響 | **¥5,000 万の増収** |

**保守的年間生産性効果**: ~2,151 時間 × ¥8,000/時 = **¥17,208,000**（~$114,700）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~8,384%

**前提条件**: 50% 利用率、単一ファブライン、歩留まり改善価値は別途記載。

---

## 半導体に関連する制限事項

| 制限事項 | 半導体への影響 |
|---------|--------------|
| S3 AP 読み取り専用 | パイプライン経由でレシピ調整やロットホールドをトリガー不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の MES アクショントリガー不可 |
| プロプライエタリフォーマット | KLARF、SINF フォーマットはメタデータレベルで処理。完全な空間分析ではない |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| ファブセキュリティ | パイプラインがプロセス IP を管理環境外に送信しないことを確認 |
| リアルタイム要件 | リアルタイム SPC には非対応。バッチメタデータカタログ化向け設計 |
| 装置連携 | FSx 上の FPolicy は装置ネイティブデータシステムの補完であり代替ではない |

---

## カスタマイズポイント

1. **プロセスフロー**: 特定テクノロジーノード（7nm、5nm、3nm）に合わせたステップ設定
2. **欠陥分類**: 自社固有の欠陥分類システムにマッピング
3. **装置グループ**: タイプとベイ別に装置をグルーピングし集約分析
4. **歩留まり目標**: 製品仕様に合わせたステップ別歩留まり閾値を設定

---

*関連: [use-cases/semiconductor/](../../use-cases/semiconductor/)*
*ペアドキュメント: [industry-semiconductor.md](./industry-semiconductor.md)*
