# 通信 — Iceberg メタデータカタログ

🌐 日本語 | [English](README.md)

## ビジネス課題

| 課題 | 影響 | 本ソリューション |
|------|------|-----------------|
| ネットワーク構成文書がチーム間で散在 | 障害復旧の遅延、知識のサイロ化 | ゼロコピーストレージによる集中管理 + SQL検索 |
| 基地局点検写真がタグ付けされず検索不可 | メンテナンス漏れ、コンプライアンス違反 | AI分類 + 点検メタデータ |
| 顧客契約アーカイブの検索に数時間 | SLA違反、規制リスク | 契約メタデータによる即時検索 |

## 対象ファイル形式

`.pdf`（契約書、コンプライアンス報告）、`.docx`, `.xlsx`（キャパシティプラン）、`.png`, `.jpg`（基地局点検写真）、設定ファイル（`.cfg`, `.xml`）

## スキーマ拡張

📄 [schema-extension.yaml](schema-extension.yaml)

追加フィールド:
- `tower_id` — 基地局・サイト識別子
- `region_code` — ネットワークリージョンコード
- `document_type` — 文書種別（config / contract / inspection / compliance）
- `equipment_vendor` — 機器ベンダー（Ericsson、Nokia等）
- `frequency_band` — 周波数帯（700MHz、3.5GHz、mmWave等）
- `inspection_result` — 点検結果（pass / fail / requires_followup）

## クイックスタート

```bash
# サンプルデータ生成
python use-cases/_shared/sample-data/generate.py --industry telecom --count 200

# 業界デモ実行
./use-cases/_shared/demo/run-demo.sh --industry telecom
```

## サンプルクエリ

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- 不合格の基地局点検写真
SELECT file_name, tower_id, region_code, inspection_result, equipment_vendor, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'tower_inspection'
  AND inspection_result = 'fail'
ORDER BY modified_at DESC;
```

## 制限事項

- 本ソリューションはゼロコピーストレージのメタデータカタログであり、ネットワーク管理システム（NMS）の代替ではありません
- 点検結果のAI分類は補助的なものであり、最終判定には有資格エンジニアによるレビューが必要です
- 通信業界固有の規制遵守（電波法、総務省基準）は別途監査証跡システムが必要です

## 関連リンク

- [業界ユースケース — 通信](../../docs/industry-use-cases.md)
- [デモシナリオ](../../demo/scenarios/industry-telecom-ja.md)
- [ベーススキーマ](../_shared/base-schema.yaml)
