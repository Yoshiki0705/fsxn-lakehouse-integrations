# Architecture Decision Records (ADR)

🌐 **English** | [日本語](#adr-ルール--運用方針)

## ADR Rules / ADR ルール

### Rules

- Each major architecture decision must be recorded as an ADR.
- Use sequential IDs: ADR-001, ADR-002, etc.
- Each ADR contains bilingual sections (English primary, Japanese summary).
- Each ADR must include: Status, Context, Decision, Options Considered, Consequences, Risks, Evidence and References, Persona Review Notes, Confidentiality Review Status.
- ADRs are immutable once accepted. To change a decision, create a new ADR that supersedes the previous one.

### ADR ルール / 運用方針

- 主要なアーキテクチャ決定は ADR として記録すること。
- 連番 ID を使用: ADR-001、ADR-002 等。
- 各 ADR はバイリンガルセクションを含む（英語が主、日本語サマリー付き）。
- 各 ADR は以下を含むこと: ステータス、コンテキスト、決定、検討オプション、結果、リスク、エビデンスと参照、ペルソナレビューノート、機密性レビューステータス。
- ADR は承認後は不変。決定を変更するには、前の ADR を置き換える新しい ADR を作成する。

---

## ADR Index / インデックス

| ID | Title / タイトル | Status |
|----|-----------------|--------|
| [ADR-001](ADR-001.md) | Use Kafka as the factory event backbone / Kafka を工場イベントバックボーンとして使用 | Accepted |
| [ADR-002](ADR-002.md) | Use ClickHouse for real-time operational analytics / ClickHouse をリアルタイム運用分析に使用 | Accepted |
| [ADR-003](ADR-003.md) | Use FSx for ONTAP as payload storage for large unstructured data / FSx for ONTAP を大容量非構造化データのペイロードストレージとして使用 | Accepted |
| [ADR-004](ADR-004.md) | Avoid direct dependency on S3 Access Points for Databricks integration / Databricks 統合で S3 アクセスポイントへの直接依存を回避 | Accepted |
| [ADR-005](ADR-005.md) | Use metadata/payload separation for large files / 大容量ファイルにメタデータ/ペイロード分離を使用 | Accepted |
| [ADR-006](ADR-006.md) | Use ClickHouse Cloud as PoC deployment model / ClickHouse Cloud を PoC デプロイモデルとして使用 | Accepted (Phase A) |
| [ADR-007](ADR-007.md) | Phased deployment: AWS-first then hybrid with Instaclustr on-premises / フェーズ別デプロイ: AWS 先行後 Instaclustr オンプレミスとのハイブリッド | Accepted |
| [ADR-008](ADR-008.md) | Edge buffering and failure recovery design / エッジバッファリングと障害復旧の設計 | Accepted |
| [ADR-009](ADR-009.md) | Kafka → ClickHouse connector specification / Kafka → ClickHouse コネクタの指定 | Accepted |
| [ADR-010](ADR-010.md) | End-to-end deduplication strategy / エンドツーエンド重複排除戦略 | Accepted |
| [ADR-011](ADR-011.md) | Unity Catalog permissions model / Unity Catalog 権限モデル | Accepted |
| [ADR-012](ADR-012.md) | Schema evolution strategy / スキーマ進化戦略 | Accepted |
| [ADR-013](ADR-013.md) | FSx for ONTAP sizing, Snapshot policy, and storage design / FSx for ONTAP サイジング、Snapshot ポリシー、ストレージ設計 | Accepted |
| [ADR-014](ADR-014.md) | MSK Serverless → Provisioned migration for ClickHouse Cloud connectivity / ClickHouse Cloud 接続のための MSK Serverless → Provisioned 移行 | Accepted |
| [ADR-015](ADR-015.md) | Kafka deployment strategy: MSK vs Instaclustr on AWS / Kafka デプロイ戦略: MSK vs AWS 上の Instaclustr | Proposed |
