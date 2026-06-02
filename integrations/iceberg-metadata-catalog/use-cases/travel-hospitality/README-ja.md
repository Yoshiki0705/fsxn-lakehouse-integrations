# 旅行・ホスピタリティ — Iceberg メタデータカタログ

🌐 日本語 | [English](README.md)

## ビジネス課題

| 課題 | 影響 | 本ソリューション |
|------|------|-----------------|
| 施設写真がシーズン・客室ごとに未整理 | OTA掲載品質の低下、予約損失 | AI分類 + 施設/シーズンメタデータ |
| ゲスト関連書類に保持ポリシーが未適用 | プライバシー違反、GDPRリスク | 文書種別タグ付け + 保持期間追跡 |
| メンテナンスログの検索に手作業が必要 | 修繕遅延、ゲストクレーム | 施設・ステータス・優先度による即時検索 |

## 対象ファイル形式

`.jpg`, `.png`（施設写真、客室画像）、`.pdf`（契約書、ゲスト同意書）、`.docx`（メンテナンスログ、点検報告書）

## スキーマ拡張

📄 [schema-extension.yaml](schema-extension.yaml)

追加フィールド:
- `property_id` — 施設・ホテル識別子
- `room_category` — 客室タイプ（standard / deluxe / suite / penthouse）
- `document_type` — 文書種別（booking / contract / inspection / marketing）
- `season` — 旅行シーズン（peak / off / shoulder）
- `compliance_status` — 規制準拠ステータス（compliant / review_needed / expired）

## クイックスタート

```bash
# サンプルデータ生成
python use-cases/_shared/sample-data/generate.py --industry travel-hospitality --count 200

# 業界デモ実行
./use-cases/_shared/demo/run-demo.sh --industry travel-hospitality
```

## サンプルクエリ

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- シーズン別マーケティング用施設写真
SELECT file_name, property_id, room_category, season, compliance_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'property_photo'
  AND document_type = 'marketing'
  AND season = 'peak'
ORDER BY property_id, room_category;
```

## 制限事項

- 本ソリューションはゼロコピーストレージのメタデータカタログであり、PMS（施設管理システム）の代替ではありません
- ゲスト文書の取り扱いはメタデータのみです — データ所在地およびGDPR/APPI削除リクエストにはプライバシーワークフローとの連携が必要です
- ホスピタリティ業界固有の規制遵守（旅館業法、消防法）は別途検査システムが必要です

## 関連リンク

- [業界ユースケース — 旅行・ホスピタリティ](../../docs/industry-use-cases.md#travel--hospitality)
- [デモシナリオ](../../demo/scenarios/industry-travel-hospitality-ja.md)
- [ベーススキーマ](../_shared/base-schema.yaml)
