# 広告・マーケティング — Iceberg メタデータカタログ

🌐 日本語 | [English](README.md)

## ビジネス課題

| 課題 | 影響 | 本ソリューション |
|------|------|-----------------|
| キャンペーン横断のクリエイティブ資産追跡が断片化 | 納期遅延、重複作業 | AI分類 + キャンペーンメタデータ連携 |
| キャンペーンコンプライアンス確認が手動 | ブランドリスク、規制罰金 | 承認ステータス + 権利期限の自動追跡 |
| チャネル横断のブランド一貫性が困難 | ブランドアイデンティティの希薄化 | チャネル横断検索 + ブランドガイドライン連携 |

## 対象ファイル形式

`.ai`, `.psd`, `.png`, `.jpg`（クリエイティブ素材）、`.mp4`（動画広告）、`.pdf`（ブランドガイドライン、クリエイティブブリーフ）

## スキーマ拡張

📄 [schema-extension.yaml](schema-extension.yaml)

追加フィールド:
- `campaign_id` — キャンペーン識別子
- `brand` — ブランドまたはサブブランド名
- `channel` — 配信チャネル（web / social / print / tv）
- `asset_type` — クリエイティブ種別（hero / banner / thumbnail / video）
- `rights_expiry` — ライセンス・権利の有効期限
- `approval_status` — 承認ステータス（draft / pending / approved / rejected）

## クイックスタート

```bash
# サンプルデータ生成
python use-cases/_shared/sample-data/generate.py --industry advertising-marketing --count 200

# 業界デモ実行
./use-cases/_shared/demo/run-demo.sh --industry advertising-marketing
```

## サンプルクエリ

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- 承認待ちのキャンペーンクリエイティブ資産
SELECT file_name, campaign_id, brand, channel, asset_type, approval_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification IN ('hero_image', 'banner', 'video_ad')
  AND approval_status = 'pending'
  AND campaign_id IS NOT NULL
ORDER BY campaign_id, channel;
```

## 制限事項

- 本ソリューションはメタデータカタログのみを提供し、広告プラットフォームのコンプライアンス（GDPR同意、COPPA）は強制しません
- 権利期限追跡は情報提供目的です — 法務/調達ワークフローとの連携が必要です
- 業界固有の広告規制（景品表示法、薬機法等）は別途コンプライアンス検証が必要です

## 関連リンク

- [業界ユースケース — 広告・マーケティング](../../docs/industry-use-cases.md#advertising--marketing)
- [デモシナリオ](../../demo/scenarios/industry-advertising-marketing-ja.md)
- [ベーススキーマ](../_shared/base-schema.yaml)
