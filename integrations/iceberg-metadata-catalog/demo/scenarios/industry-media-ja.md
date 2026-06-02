# メディア/VFX 向けデモシナリオ: 制作アセット AI 分類 & クリエイティブ検索

> メディア制作・VFX スタジオのアセット管理、プロジェクト追跡、クリエイティブ再利用を改善するデモシナリオ

---

## ビジネスコンテキスト

### 課題

メディア・VFX スタジオが直面する課題：

- **アセットの拡散**: レンダリング、コンポジット、テクスチャ、プレートスキャンが体系的タグ付けなしにプロジェクト共有に蓄積
- **再レンダリング vs 再利用**: 既存の類似アセットが見つけられないため新規作成してしまう
- **プロジェクト引き継ぎの摩擦**: チーム間のプロジェクト移管時、既存アセットの把握に数日
- **スケールでのストレージコスト**: VFX プロジェクトで制作あたり 10–100TB 生成。完了作業のアーカイブが手動

### 解決後の姿

- 制作アセットが種類別（レンダー、コンポジット、テクスチャ、プレート、リファレンス）に自動分類
- ファイルパスとコンテンツからプロジェクト・ショットメタデータを自動抽出
- ベクトル検索による類似アセット発見（「これに似たテクスチャを探す」）
- プロダクションマネージャー向けプロジェクトインベントリクエリ

---

## デモフロー

### ステップ 1: サンプルメディアアセットを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry media-vfx --target /vol/production/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `shot_010_comp_v003_final.exr` | ファイナルコンポジット | ヒーローショットコンポジット v3 |
| `env_forest_hdri_8k.hdr` | HDRI 環境 | 8K 森林環境マップ |
| `char_dragon_texture_diffuse_4k.png` | キャラクターテクスチャ | ドラゴンキャラ ディフューズマップ |
| `plate_scan_shot010_cam_A.dpx` | プレートスキャン | 撮影素材（カメラ A） |
| `previs_sequence_act2_v05.mov` | プレビズ | 第 2 幕プレビズアニマティック |

**トークポイント**:
- 「アーティストは通常通りプロジェクト共有に保存 — レンダーファーム出力、Nuke コンポジット、Maya レンダーすべてがパイプラインをトリガー」
- 「大容量ファイル（EXR、DPX）は問題なく動作。ただし Bedrock 分類コストは高め（10MB+ で ~$0.15）」
- 「Linux レンダーノードからの NFS アクセスも Windows ワークステーションからの SMB と同様に FPolicy をトリガー」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: shot_010_comp_v003_final.exr
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - アセット種別: ファイナルコンポジット
   - プロジェクト: [制作名]
   - ショット: 010
   - バージョン: v003
   - ステータス: Final
   - 解像度: 4096x2160
   - カラースペース: ACEScg
   - 部門: コンポジット
✅ Classified in 45.1s | Cost: $0.15 (large file)
```

**トークポイント**:
- 「AI がファイル命名規則とコンテンツ分析の両方からプロジェクト/ショット/バージョンを抽出」
- 「大容量メディアファイル（10MB+）は 1 ファイルあたり ~$0.15」
- 「信頼度: テストデータでの PoC 0.94。本番精度は変動 — 非標準命名規則では抽出精度が低下」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       project, shot, version, status, department, resolution
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'media-vfx'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | project | shot | version | status |
|-----------|------------------|:---------:|:-------:|:----:|:-------:|:------:|
| .../shot_010_comp_v003_final.exr | ファイナルコンポジット | 0.95 | PROD-2026 | 010 | v003 | Final |
| .../env_forest_hdri_8k.hdr | HDRI 環境 | 0.93 | ライブラリ | - | - | Approved |
| .../char_dragon_texture_diffuse_4k.png | キャラクターテクスチャ | 0.94 | PROD-2026 | - | - | WIP |
| .../plate_scan_shot010_cam_A.dpx | プレートスキャン | 0.96 | PROD-2026 | 010 | - | Source |
| .../previs_sequence_act2_v05.mov | プレビズ | 0.92 | PROD-2026 | Act2 | v05 | Review |

**注意**: 信頼度は PoC 結果。非標準命名規則やプロプライエタリ形式では精度が低下する場合あり。

---

### ステップ 4: プロダクション管理クエリ

**所要時間**: 5 分

```sql
-- ショット完了状況
SELECT shot, 
       count(case when status = 'Final' then 1 end) as final_count,
       count(case when status = 'WIP' then 1 end) as wip_count,
       max(scan_timestamp) as last_activity
FROM s3_tables.metadata_catalog.file_metadata
WHERE project = 'PROD-2026'
GROUP BY shot
ORDER BY shot;

-- ショットごとの最新バージョン
SELECT file_path, shot, version, status, department, scan_timestamp
FROM s3_tables.metadata_catalog.file_metadata
WHERE project = 'PROD-2026' AND shot = '010'
ORDER BY version DESC;

-- 部門・ステータス別ストレージ使用量
SELECT department, status, 
       count(*) as file_count,
       sum(file_size_bytes) / (1024*1024*1024) as total_gb
FROM s3_tables.metadata_catalog.file_metadata
WHERE project = 'PROD-2026'
GROUP BY department, status
ORDER BY total_gb DESC;
```

**トークポイント**:
- 「プロダクションマネージャーが各部門に確認せずにリアルタイムのショット状況を把握」
- 「ストレージ使用量の可視化で的確なアーカイブ判断が可能に」
- 「注意: アイドル後の最初の Athena クエリ: 3–5 秒コールドスタート」

---

### ステップ 5: セマンティック検索でクリエイティブアセットを再利用

**所要時間**: 5 分

**シナリオ**: 「森林シーンに似た HDRI 環境を検索」

OpenSearch セマンティック検索：
1. **キーワード**: `"forest" "HDRI" "environment"` → 完全一致
2. **類似検索**: `env_forest_hdri_8k.hdr` の埋め込みを使用 → 視覚的/概念的に類似した環境を検索
3. **フィルター**: `ai_classification = 'HDRI 環境' AND resolution >= '4K'`

**トークポイント**:
- 「アーティストがゼロから作り直す代わりに再利用可能なアセットを発見」
- 「ベクトル検索は命名が異なっても概念的に類似したアセットを見つけ出します」
- 「OpenSearch ウォームアップ: 長時間アイドル後 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 90% 以上（5 カテゴリ） | PoC 結果。非標準命名では精度低下 |
| 処理時間 | 42–60 秒/ファイル | 大容量 EXR/DPX はより長い場合あり |
| 1 ファイルあたりコスト | $0.07–$0.15 | ファイルサイズにより変動（10MB+ = ~$0.15） |
| ショットメタデータ抽出 | 85% 以上 | 一貫した命名規則に依存 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| アセット再利用（再レンダリング回避） | 5% レンダー節約 × 年間レンダーコスト $500K | **$25,000 節約** |
| アーティスト検索時間 | 15 分/日 × 30 人 × 50% 利用率 | **~1,370 時間/年** |
| プロダクションマネージャーレポート | 2 時間/週 → 5 分/週 | **100 時間/年** |
| アーカイブ効率化 | 1 週間/プロジェクト → 1 日 | **160 時間/年** |

**保守的年間生産性効果**: ~1,630 時間 × ¥5,000/時 + $25,000 レンダー節約 = **¥8,150,000 + $25,000**（~$79,300）
**年間ソリューションコスト**: ~$2,000（大容量ファイル = Bedrock コスト増）
**保守的 ROI**: ~3,865%

**前提条件**: 50% 利用率、保守的時間見積もり、控えめなレンダー再利用率。

---

## メディア/VFX に関連する制限事項

| 制限事項 | メディアへの影響 |
|---------|---------------|
| 大容量ファイルのコスト | 10MB+ ファイルは Bedrock 分類に ~$0.15。数百万の EXR フレームを持つ VFX プロジェクトではコスト累積 |
| メディアファイルの Bedrock 精度 | バイナリ形式（EXR、DPX）は主にファイル名/パスで分類。実際の画像コンテンツ分析は限定的 |
| FPolicy レイテンシ (~1–5ms) | ファイル保存には影響微小。リアルタイムレンダーパイプラインとボリュームを共有する場合はテスト必要 |
| S3 AP 読み取り専用 | ファイナル済みアセットのアーカイブストレージへの自動移動不可 |
| Lambda メモリ制限 | 超大容量ファイル（>500MB）は Lambda メモリを超過する可能性。チャンク処理が必要 |
| 命名規則への依存 | メタデータ抽出品質はファイル/フォルダの一貫した命名に大きく依存 |

---

## カスタマイズポイント

1. **分類カテゴリ**: スタジオパイプラインステージにマッピング（プレビズ、レイアウト、アニメーション、ライティング、コンプ、ファイナル）
2. **メタデータフィールド**: プロジェクトコード、ショット番号、フレームレンジ、カラースペース
3. **バージョン追跡**: スタジオ命名規則に合わせたバージョン抽出パターンを設定
4. **ステータスワークフロー**: ファイル配置/命名を制作ステータス（WIP/Review/Final/Approved）にマッピング
5. **コスト管理**: FPolicy スコープを特定ディレクトリに限定（temp/cache ファイルの処理を回避）

---

*関連設定: [`media-vfx.yaml`](../sample-data/industry-configs/media-vfx.yaml)*
*ペアドキュメント: [industry-media.md](./industry-media.md)*
