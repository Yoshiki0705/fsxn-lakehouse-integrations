# 広告・マーケティング向けデモシナリオ: クリエイティブアセット & キャンペーンインテリジェンス

🌐 日本語 | [English](industry-advertising-marketing.md)

> クリエイティブアセット、キャンペーンブリーフ、メディアプラン、ブランドガイドラインを広告代理店のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

広告・マーケティング組織が直面する課題：

- **クリエイティブアセットの混乱**: 数千の画像、動画、コピー文書、デザインファイルがキャンペーンフォルダに命名規則なく散在
- **キャンペーンブリーフの断片化**: ブリーフ、修正版、クライアントフィードバック、承認文書がプロジェクトドライブに分離
- **ブランドガイドラインのドリフト**: ブランドガイドラインとアセットテンプレートの複数バージョンが現行ステータス不明確のまま存在
- **アセット再利用の失敗**: 過去キャンペーンの承認済みクリエイティブ検索に数年分のアーカイブの手動検索が必要

### 解決後の姿

- クリエイティブアセットがキャンペーン、フォーマット、承認ステータス、利用権別に自動分類
- 「Q1キャンペーンのBrand X承認済みヒーロー画像をすべて表示」が SQL で即座に回答
- キャンペーン文書がプロジェクト別にリビジョン履歴と承認チェーン追跡付きでリンク
- セマンティック検索によるキャンペーン横断のクリエイティブ発見が実現

---

## デモフロー

### ステップ 1: サンプル広告ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry advertising-marketing --target /vol/creative-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `creative-hero-brandX-summer2026-v3-approved.psd` | クリエイティブアセット | ヒーロー画像、承認済み最終版 |
| `campaign-brief-brandX-summer2026.pdf` | キャンペーンブリーフ | 夏季キャンペーン戦略と要件 |
| `media-plan-brandX-Q3-digital.xlsx` | メディアプラン | Q3デジタルメディア配分 |
| `brand-guidelines-brandX-v4.2.pdf` | ブランドガイドライン | 現行ブランド基準文書 |
| `performance-report-brandX-summer-week4.pdf` | パフォーマンスレポート | 4週目キャンペーン指標 |

**トークポイント**:
- 「クリエイティブチームは Dropbox/Drive を FSx に同期して使い続けられます — ワークフロー変更なし」
- 「ラスター/ベクターのクリエイティブと文書が同じパイプラインで処理」

---

### ステップ 2〜5: （英語版と同等の構造）

各ステップの詳細は英語版 [industry-advertising-marketing.md](./industry-advertising-marketing.md) を参照。

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 41 秒/ファイル | クリエイティブファイルはメタデータ/ファイル名で処理 |
| 1 ファイルあたりコスト | $0.05–$0.07 | 文書: $0.07、画像: $0.05 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| アセット検索時間 | 20 分/検索 × 1,000 検索/年 → 2 分 | **300 時間削減** |
| クリエイティブ再利用 | 5 アセット/月の再利用 × ¥20 万の制作費削減 | **¥1,200 万削減** |
| キャンペーンレポーティング | 2 時間/週 × 50 週 → 自動化 | **100 時間削減** |
| ブランドガイドラインコンプライアンス | 4 時間/月の追跡 → 自動化 | **44 時間削減** |

**保守的年間生産性効果**: ~444 時間 × ¥5,500/時 = **¥2,442,000**（~$16,300）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~1,091%

---

## 広告・マーケティングに関連する制限事項

| 制限事項 | 広告業への影響 |
|---------|--------------|
| S3 AP 読み取り専用 | パイプライン経由でクリエイティブ承認ワークフローをトリガー不可 |
| 大容量クリエイティブファイル | PSD/AI ファイル（100MB以上）はメタデータ/ファイル名レベルで処理 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| 利用権 | AI による権利メタデータ抽出は補助的。法務確認が必要 |
| クリエイティブ判断 | AI はクリエイティブ品質やブランド適合性を評価できない — 人間レビュー必要 |
| クライアント機密性 | クライアントのクリエイティブがアカウント境界を超えて漏洩しないことを確認 |

---

## カスタマイズポイント

1. **ブランド階層**: クライアント → ブランド → サブブランド → キャンペーンの構造を設定
2. **アセットフォーマット**: ファイルタイプをクリエイティブ制作ステージにマッピング（ブリーフ、カンプ、最終版）
3. **利用権**: ライセンスタイプカテゴリと有効期限追跡を設定
4. **承認ワークフロー**: ステータス値を企業承認プロセスのステージにマッピング

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

*関連: [use-cases/advertising-marketing/](../../use-cases/advertising-marketing/)*
*ペアドキュメント: [industry-advertising-marketing.md](./industry-advertising-marketing.md)*
