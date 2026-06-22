# Architecture Decision Records (ADR)

> 本ディレクトリには、FSx for ONTAP × Lakehouse 統合プロジェクトの主要な技術的意思決定を記録しています。

## ADR 一覧

| ID | タイトル | ステータス | 日付 |
|:---:|---|:---:|---|
| [ADR-001](./ADR-001-datasync-as-primary-sync.md) | DataSync を FSx for ONTAP → S3 の主要同期メカニズムとして採用 | Accepted | 2026-05-26 |
| [ADR-002](./ADR-002-snapmirror-s3-unavailability.md) | SnapMirror S3 が FSx for ONTAP で利用不可であることの確認と対応方針 | Accepted | 2026-05-26 |
| [ADR-003](./ADR-003-staged-to-s3-pattern.md) | Staged-to-S3 パターンを Databricks UC 接続の標準アーキテクチャとして採用 | Accepted | 2026-06-01 |

## ADR フォーマット

各 ADR は以下の構造に従います:

1. **Title** — 決定内容を一文で
2. **Status** — Proposed / Accepted / Deprecated / Superseded
3. **Context** — なぜこの決定が必要になったか
4. **Decision** — 何を決定したか
5. **Consequences** — 決定の結果（良い影響・悪い影響・リスク）
6. **Alternatives Considered** — 検討した他の選択肢
7. **References** — 根拠となるエビデンス

## 関連ドキュメント

- [ブロッカー追跡ダッシュボード](../ja/blocker-tracker.md)
- [UC 接続総合ガイド](../ja/fsx-ontap-to-databricks-unity-catalog-guide.md)
- [読み順ガイド](../ja/reading-path-guide.md)
