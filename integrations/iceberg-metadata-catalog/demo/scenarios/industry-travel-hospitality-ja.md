# 旅行・ホスピタリティ向けデモシナリオ: ゲスト文書 & 施設管理インテリジェンス

🌐 日本語 | [English](industry-travel-hospitality.md)

> ゲスト文書、施設写真、メンテナンスログ、予約確認書をホスピタリティグループのファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

ホスピタリティ企業が直面する課題：

- **ゲスト文書の散在**: パスポートコピー、予約確認書、特別リクエストが施設間で統一検索なく分散
- **施設アセット管理**: 数千の施設写真、客室レイアウト、リノベーション文書が施設間で一貫性なく保管
- **メンテナンス追跡のギャップ**: 作業指示書、点検報告書、設備ログが客室/施設レコードと非連結
- **ブランドコンプライアンス**: 数百施設のマーケティング写真とブランドガイドライン準拠が手動追跡

### 解決後の姿

- ゲスト・施設文書がタイプ、施設、ステータス別に自動分類
- 「Tokyo-01施設で保留中のメンテナンスリクエストがある客室をすべて表示」が SQL で即座に回答
- 施設写真が客室タイプ、アメニティ、リノベーションステータスでタグ付け
- ポートフォリオ全体でブランドコンプライアンスとアセット鮮度を追跡

---

## デモフロー

### ステップ 1: サンプルホスピタリティファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry travel-hospitality --target /vol/hospitality/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `booking-confirm-RES2026-088421.pdf` | 予約確認書 | スイート予約、3泊 |
| `property-photo-TKY01-suite-801-main.jpg` | 施設写真 | スイート801メインビュー、リノベーション後 |
| `maintenance-log-TKY01-HVAC-20260601.pdf` | メンテナンスログ | HVAC点検、8階 |
| `guest-request-RES088421-dietary.pdf` | ゲストリクエスト | 食事制限、アレルゲン情報 |
| `brand-audit-TKY01-Q2-2026.pdf` | ブランド監査 | 四半期ブランド基準コンプライアンス |

**トークポイント**:
- 「施設スタッフは既存ワークフローで写真と文書をアップロード — プロセス変更なし」
- 「複数施設が中央FSxファイルシステムを共有しポートフォリオ全体のインテリジェンスを実現」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: property-photo-TKY01-suite-801-main.jpg
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 施設写真/客室
   - 施設: Tokyo-01
   - 客室: スイート801
   - ビュー: メイン（広角）
   - リノベーション状況: 完了
   - ブランドコンプライアンス: 基準適合
   - 品質: 掲載可能
   - 確認アメニティ: デスク、ソファ、ミニバー
✅ Classified in 40.5s | Cost: $0.05
```

---

### ステップ 3〜5: （省略 — 英語版と同等の構造）

各ステップの詳細は英語版 [industry-travel-hospitality.md](./industry-travel-hospitality.md) を参照。

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 40 秒/ファイル | 写真はやや高速 |
| 1 ファイルあたりコスト | $0.05–$0.07 | 写真: ~$0.05、文書: ~$0.07 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 施設写真管理 | 10 分/検索 × 500 検索/年 → 1 分 | **75 時間削減** |
| メンテナンス調整 | 15 分/依頼 × 1,000 件/年 → 3 分 | **200 時間削減** |
| ゲストリクエスト検索 | 5 分/予約 × 5,000 予約/年 → 30 秒 | **375 時間削減** |
| ブランド監査準備 | 2 日/四半期 → 4 時間 × 4 監査/年 | **48 時間削減** |

**保守的年間生産性効果**: ~698 時間 × ¥4,000/時 = **¥2,792,000**（~$18,600）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~941%

---

## 旅行・ホスピタリティに関連する制限事項

| 制限事項 | ホスピタリティへの影響 |
|---------|---------------------|
| S3 AP（パイプラインは読み取りのみ使用） | PMSワークフローや客室ステータス更新をトリガー不可 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| ゲストPII | ゲスト文書に広範なPIIを含む。プライバシー規制に従ったデータ取り扱い確認 |
| マルチ施設スケール | ポートフォリオ規模（100施設以上）ではキャパシティプランニングが必要 |
| 写真品質評価 | AI品質レーティングは補助シグナル — 専門レビューの代替ではない |
| リアルタイム運用 | リアルタイムチェックイン/アウトには非対応。バッチ文書処理 |

- **最小規模**: この業界は製造業や金融業と比較してファイル量が少ない場合があります。AI パイプラインのオーバーヘッドを正当化するために、日次ファイル変更が 100 件/日を超えることを確認してください。

---

## カスタマイズポイント

1. **施設階層**: ブランド → 施設 → 棟 → フロア → 客室の構造を設定
2. **客室カテゴリ**: 自社固有の客室タイプ分類にマッピング
3. **メンテナンスタイプ**: PMS カテゴリに整合
4. **ブランド基準**: ブランドティア別のコンプライアンスチェックリスト項目を設定

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

*関連: [use-cases/travel-hospitality/](../../use-cases/travel-hospitality/)*
*ペアドキュメント: [industry-travel-hospitality.md](./industry-travel-hospitality.md)*
