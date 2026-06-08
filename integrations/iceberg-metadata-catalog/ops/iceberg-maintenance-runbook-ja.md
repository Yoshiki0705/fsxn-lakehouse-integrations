# Iceberg テーブルメンテナンス Runbook

🌐 [English](iceberg-maintenance-runbook.md) | 日本語

## 目的

S3 Tables 上の `metadata.unstructured_files` Iceberg テーブルを最適なクエリパフォーマンスとストレージ効率で維持する。

## 推奨メンテナンス順序

1. **Latest-record ビューの検証** — `latest_unstructured_files` ビューが正しい重複排除結果を返すことを確認
2. **スナップショット有効期限** — 保持ポリシーより古いスナップショットを削除（S3 Tables が自動管理する可能性あり; 確認すること）
3. **孤立ファイルの削除** — いずれのスナップショットからも参照されていないデータファイルをクリーンアップ（エンジンがサポートする場合）
4. **マニフェスト書き換え** — マニフェスト数が ~100 を超えた場合、スキャンプランニング高速化のため書き換え
5. **ベンチマーククエリの再実行** — Athena クエリレイテンシが劣化していないことを確認
6. **エビデンス記録** — メンテナンスアクションを `verification-evidence/` にログ

## S3 Tables マネージドメンテナンス

S3 Tables はサービスマネージドのコンパクションを提供。以下を確認：
- 自動コンパクションの頻度と動作
- スナップショット有効期限が自動か、明示的な設定が必要か
- 孤立ファイルクリーンアップの責任（サービス vs ユーザー）

## 手動メンテナンス（必要な場合）

```python
# PyIceberg 経由（S3 Tables がメンテナンス API を公開している場合）
from pyiceberg.catalog import load_catalog

catalog = load_catalog('glue_s3tables', **{...})
table = catalog.load_table('metadata.unstructured_files')

# 現在のスナップショットを確認
for snapshot in table.metadata.snapshots:
    print(f"{snapshot.snapshot_id} | {snapshot.timestamp_ms}")
```

## モニタリング

| メトリック | 確認方法 | アラート閾値 |
|----------|---------|------------|
| スナップショット数 | `SELECT COUNT(*) FROM ...unstructured_files$history` | > 100 |
| レコード数 vs ユニーク file_id 数 | ベーステーブル vs latest ビューを比較 | 比率 > 2x |
| Athena クエリレイテンシ (p95) | CloudWatch | > 5 秒 |
| マニフェストファイル数 | Iceberg メタデータ検査 | > 100 |

## スケジュール

| アクション | 頻度 | オーナー |
|----------|------|---------|
| Latest-record ビュー検証 | 毎日（自動化） | プラットフォームチーム |
| スナップショット数確認 | 週次 | プラットフォームチーム |
| フルメンテナンスサイクル | 月次 | プラットフォームチーム |
| メンテナンス後の再ベンチマーク | メンテナンスごと | プラットフォームチーム |
