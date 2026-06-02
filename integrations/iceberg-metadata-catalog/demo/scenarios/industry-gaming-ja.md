# ゲーム業界向けデモシナリオ: ゲームアセットパイプライン & QA レポートインテリジェンス

🌐 日本語 | [English](industry-gaming.md)

> ゲームアセット（テクスチャ、3Dモデル、オーディオ）、ビルドログ、QAレポート、プレイヤーフィードバックをスタジオのファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

ゲームスタジオが直面する課題：

- **大規模アセット管理**: 数百万のテクスチャ、3Dモデル、オーディオファイル、アニメーションクリップが命名規則なくプロジェクトドライブに散在
- **ビルド成果物の蓄積**: ナイトリービルドが生成する数百のログ、クラッシュダンプ、パフォーマンスレポートが体系的な整理なく蓄積
- **QA レポートの断片化**: バグレポート、テスト結果、プレイヤーフィードバックがツールやファイル共有に分散
- **バージョン混乱**: 同一アセットの複数バージョンが明確な系譜や承認ステータスなく存在

### 解決後の姿

- ゲームアセットがタイプ、プロジェクト、マイルストーン、品質ティア別に自動分類
- 「現行マイルストーンで4K以上の未圧縮テクスチャをすべて表示」が即座に回答
- QA レポートやクラッシュログがビルドバージョン、重要度、コンポーネント別に検索可能
- セマンティック検索によるプロジェクト間のアセット再利用が実現

---

## デモフロー

### ステップ 1: サンプルゲームスタジオファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry gaming --target /vol/game-studio/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `tex_env_forest_ground_01_4k.png` | テクスチャアセット | 4K地面テクスチャ、森林バイオーム |
| `mdl_character_hero_v12.fbx` | 3D モデル | ヒーローキャラクターモデル、v12 |
| `build-log-v2.4.1-nightly-20260601.log` | ビルドログ | ナイトリービルド出力、342 warnings |
| `qa-report-sprint42-combat-system.pdf` | QA レポート | Sprint 42 戦闘システムテスト結果 |
| `audio_sfx_explosion_large_01.wav` | オーディオアセット | 効果音、爆発カテゴリ |

**トークポイント**:
- 「アーティストや開発者は既存のファイル保存ワークフローを維持 — ツール移行不要」
- 「FSx の高性能 NFS がゲームスタジオに必要なスループットを提供」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: tex_env_forest_ground_01_4k.png
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - アセットタイプ: テクスチャ/環境
   - 解像度: 4096x4096
   - バイオーム: 森林
   - エレメント: 地面
   - 圧縮: なし（RAW）
   - LOD ティア: High
   - プロジェクト: 現行（推定）
✅ Classified in 38.7s | Cost: $0.05
```

**トークポイント**:
- 「AI がアセットタイプ、解像度、プロジェクトコンテキスト、品質ティアを識別」
- 「ビルドログはエラー件数、警告カテゴリ、障害モードが解析されます」
- 「分類信頼度: PoC 精度。本番精度はアセット命名規則により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
-- Athena で分類結果を確認
SELECT file_path, ai_classification, confidence_score,
       asset_type, resolution, project, milestone
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'gaming'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | asset_type | resolution | project |
|-----------|------------------|:---------:|:----------:|:----------:|:-------:|
| /vol/game-studio/tex_env_forest_ground_01_4k.png | テクスチャ/環境 | 0.96 | Texture | 4096x4096 | ProjectX |
| /vol/game-studio/mdl_character_hero_v12.fbx | 3Dモデル/キャラクター | 0.94 | Model | - | ProjectX |
| /vol/game-studio/build-log-v2.4.1-nightly-20260601.log | ビルドログ/ナイトリー | 0.98 | Log | - | ProjectX |
| /vol/game-studio/qa-report-sprint42-combat-system.pdf | QA レポート | 0.95 | Report | - | ProjectX |
| /vol/game-studio/audio_sfx_explosion_large_01.wav | オーディオ/SFX | 0.93 | Audio | - | ProjectX |

**トークポイント**:
- 「5種類のアセットタイプが高信頼度で分類」
- 「解像度と品質ティアが抽出され、パイプライン最適化に活用可能」
- 「ビルドバージョンとスプリントの紐づけが自動維持」

---

### ステップ 4: ゲームスタジオ向けクエリ

**所要時間**: 5 分

```sql
-- 最適化が必要な4K以上の未圧縮テクスチャ
SELECT file_path, resolution, file_size_mb, compression_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'テクスチャ/環境'
  AND resolution_x >= 4096
  AND compression_status = 'None'
ORDER BY file_size_mb DESC;

-- 過去7日間のコンポーネント別ビルド失敗
SELECT build_version, error_category, error_count, build_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'ビルドログ/ナイトリー'
  AND error_count > 0
  AND scan_timestamp > current_date - interval '7' day
ORDER BY error_count DESC;

-- クリティカルバグを含む QA レポート
SELECT file_path, sprint, component, critical_bug_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'QA レポート'
  AND critical_bug_count > 0
ORDER BY critical_bug_count DESC;
```

**トークポイント**:
- 「テクニカルアーティストがターゲットプラットフォーム向けに圧縮が必要なテクスチャを即座に特定」
- 「ビルドエンジニアがナイトリービルドの繰り返し障害パターンを識別」
- 「QA リードがコンポーネント別・スプリント別のクリティカルバグ密度を追跡」

---

### ステップ 5: アセット再利用のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「全プロジェクトから爆発関連アセットを再利用のために検索」

OpenSearch を使用：
1. **キーワード検索**: `"explosion" AND "sfx"` → オーディオの完全一致
2. **セマンティック検索**: 「大規模爆発のパーティクルエフェクト」→ 関連する VFX、テクスチャ、オーディオを発見
3. **組み合わせ**: アセットタイプ + セマンティック類似度スコアフィルター

**トークポイント**:
- 「プロジェクト間のアセット再利用でマイルストーンごとに数週間のアーティスト工数を削減」
- 「チーム間の命名規則が異なっても、セマンティック検索が関連アセットを発見」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 92% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 40 秒/ファイル | メタデータ抽出のみ。レンダリングなし |
| 1 ファイルあたりコスト | $0.05–$0.07 | ファイルタイプと内容により変動 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| アセット検索時間 | 20 分/日 × 40 アーティスト × 50% 利用率 | **~730 時間/年** |
| ビルドログ分析 | 30 分/日 × 5 ビルドエンジニア → 自動化 | **~45 時間/年** |
| アセット再利用発見 | 2 日/マイルストーン × 6 マイルストーン → 2 時間 | **84 時間削減** |
| QA レポート集約 | 1 時間/スプリント × 26 スプリント → 自動化 | **26 時間削減** |

**保守的年間生産性効果**: ~885 時間 × ¥6,000/時 = **¥5,310,000**（~$35,400）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,488%

**前提条件**: 50% 利用率、中規模スタジオ（40 アーティスト、5 ビルドエンジニア）、市場投入期間短縮の追加価値は含まず。

---

## ゲーム業界に関連する制限事項

| 制限事項 | ゲーム業界への影響 |
|---------|-----------------|
| S3 AP 読み取り専用 | パイプライン経由でのアセット自動変換・圧縮不可 |
| S3 Event Notifications 非対応 | S3 イベント経由のビルドパイプラインステップトリガー不可 |
| Bedrock 精度の変動 | カスタムアセット命名規則にはプロンプトチューニングが必要な場合あり |
| 大容量ファイル | ゲームアセット（100MB 以上のモデル）は Lambda 処理時間が増加 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| バイナリファイル分析 | バイナリ形式はメタデータ/ファイル名パターンでの AI 分類 |

---

## カスタマイズポイント

1. **アセットカテゴリ**: スタジオ固有のタイプ追加（コンセプトアート、ストーリーボード、カットシーンスクリプト）
2. **パイプライン連携**: 分類をアセットパイプラインステータスに接続（WIP、レビュー、承認、公開）
3. **プラットフォームタグ**: ターゲットプラットフォーム別タグ付け（PC、コンソール、モバイル）
4. **LOD ティア**: ターゲットハードウェアごとの LOD 要件マッピング

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

*関連: [use-cases/gaming/](../../use-cases/gaming/)*
*ペアドキュメント: [industry-gaming.md](./industry-gaming.md)*
