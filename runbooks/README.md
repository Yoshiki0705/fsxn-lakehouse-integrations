# Operational Runbooks / 運用 Runbook

> 🌐 Bilingual (JA/EN)

## Purpose / 目的

Checklist-based operational procedures for Day-2 operations of the FSx for ONTAP × Lakehouse integration pipeline.
FSx for ONTAP × Lakehouse 統合パイプラインの Day-2 運用手順書（チェックリスト形式）。

## Runbook List / 一覧

| # | Runbook | Trigger / トリガー |
|:---:|---|---|
| 1 | [DataSync Task Failure Triage](./01-datasync-failure-triage.md) | DataSync タスク実行失敗時 |
| 2 | [FPolicy Lambda Failure & DLQ Reprocessing](./02-fpolicy-lambda-failure.md) | Lambda タイムアウト/エラー、DLQ 蓄積時 |
| 3 | [Pipeline Health Check](./03-pipeline-health-check.md) | 定期（週次）または異常検知時 |

## When to Use / 使用タイミング

- **アラート発報時**: CloudWatch アラームが発報したら該当 Runbook を開く
- **定期点検**: 週次で Runbook #3 を実行し、パイプライン全体の健全性を確認
- **インシデント対応**: 障害発生時に Runbook を上から順に実行し、原因を特定

## Related Documents / 関連ドキュメント

- [DataSync → S3 ガイド / Guide](../docs/ja/datasync-to-s3-guide.md) — 設計背景
- [ブロッカー追跡 / Blocker Tracker](../docs/ja/blocker-tracker.md) — 既知制約
- [読み順ガイド / Reading Path Guide](../docs/ja/reading-path-guide.md) — ドキュメントナビゲーション
