# ADR-003: Staged-to-S3 パターンを Databricks UC 接続の標準アーキテクチャとして採用

| 属性 | 値 |
|------|---|
| **Status** | Accepted |
| **Date** | 2026-06-01 |
| **Decision makers** | プロジェクトアーキテクチャチーム |
| **Related blockers** | [BLK-001](../ja/blocker-tracker.md), [BLK-002](../ja/blocker-tracker.md) |
| **Depends on** | [ADR-001](./ADR-001-datasync-as-primary-sync.md) |

---

## Context

Databricks Unity Catalog（UC）は FSx for ONTAP S3 Access Points を External Location として直接サポートしない（BLK-001: セッションポリシーが S3 AP ARN を処理できない）。また、FSx for ONTAP S3 AP は conditional writes をサポートしないため（BLK-002）、Delta Lake / Iceberg の書き込みも不可。

この二重制約により、FSx for ONTAP データを UC ガバナンス下で利用するには、何らかの「中間層」を経由する必要がある。

設計上の選択肢:
1. **Staged-to-S3**: FSx for ONTAP → 標準 S3 にデータを同期し、S3 を UC に登録
2. **ゼロコピーの将来対応を待つ**: BLK-001 解消まで実装を保留
3. **UC バイパス**: Instance Profile + boto3 で直接読み取り（ガバナンスなし）

## Decision

**Staged-to-S3 パターン（FSx for ONTAP → DataSync → 標準 S3 → UC）を Databricks UC 接続の標準アーキテクチャとして採用する。**

このパターンは「回避策」ではなく「NAS ファイルデータを AI-ready データプロダクトに変換するキュレーションパターン」として位置づける。

### アーキテクチャ

```
FSx for ONTAP (NFS/SMB/S3 AP)
  │
  │  [既存の業務ユーザー]
  │  ├── NFS → Linux ワークステーション
  │  ├── SMB → Windows 共有
  │  └── S3 AP → Athena / Glue / Snowflake（読み取り分析）
  │
  │  [Databricks UC パス — staged-to-S3]
  ↓
DataSync (rate(5 min) ~ daily, CHANGED mode)
  ↓
Amazon S3 (標準バケット, curated subset)
  ↓
UC External Location → UC Tables / Volumes
  ↓
UC ガバナンス (lineage, tags, masks, row filters)
```

### 設計原則

1. **全データを同期しない** — 下流プラットフォームが必要とする curated subset のみを同期
2. **DataSync が主要同期メカニズム** — ADR-001 に準拠
3. **Snapshot/FlexClone ステージング** — 本番ワークロードへの影響ゼロ
4. **UC ガバナンスはコピー側に適用** — ソース（FSx for ONTAP）のガバナンスは ONTAP ACL + S3 AP ポリシーが継続担当

## Consequences

### 良い影響
- **UC フルガバナンス適用可能**: lineage, tags, masks, row filters, audit が標準 S3 上で機能
- **即座に実装可能**: BLK-001/002 の解消を待たずに本番パイプラインを構築
- **Medallion アーキテクチャ適合**: Bronze（raw sync）→ Silver（cleansed）→ Gold（aggregated）が自然に設計可能
- **FSx for ONTAP の価値維持**: ソース側はマルチプロトコル + Snapshot + FlexClone + SnapMirror の恩恵を引き続き享受
- **ハイブリッド設計**: 読み取り専用分析（Athena/Snowflake）は S3 AP 直接、ガバナンス付き分析（UC）は staged S3

### 悪い影響・制約
- **データコピーの二重化**: FSx for ONTAP + S3 のストレージコスト（~$27/月/TB）
- **同期レイテンシ**: 最短 5 分。リアルタイム要件は別パス（Kafka → Structured Streaming）で対応
- **ゼロコピーではない**: Snowflake（S3 AP 直接対応）と比較してコスト面で不利
- **同期範囲の設計が必要**: 何を同期し何を同期しないかの判断が運用チームに委ねられる

### リスク
- BLK-001 が解消された場合、本パターンは「必須」から「オプション」に変わる。ただし、curated subset の概念自体は有効であり続ける（全データを UC に登録するのではなく、必要なサブセットのみ）
- 同期範囲のドリフト: 初期設計では限定的だった同期範囲が、要求の増加により「全データ同期」に近づくリスク。定期的な同期範囲レビューを推奨

## Alternatives Considered

### ゼロコピー対応を待つ（却下）

- **理由**: BLK-001 の解消タイムラインが未定。ビジネス要件は待てない
- 2026-05 に Feature Request 提出済みだが、Databricks からのコミットなし
- 解消まで「UC ガバナンスなしの PoC」に留まるのはリスク

### UC バイパス — Instance Profile + boto3（却下、PoC のみ許容）

- **理由**: UC ガバナンスを完全にバイパスするため、データ流出リスクが存在
- lineage 追跡不可、tag/mask 適用不可、audit 不完全
- PoC 段階での概念検証にのみ許容し、本番利用は禁止

### Lakehouse Federation 経由（部分的に採用）

- **理由**: EC2 上の PostgreSQL/MySQL（FSx for ONTAP をデータストア）を UC Lakehouse Federation で読み取る
- 読み取り専用 + プッシュダウンクエリに限定
- UC 接続ガイドの「パス — EC2 セルフマネージド DB」として記載
- Staged-to-S3 パターンの**補完**として採用（代替ではない）

### Foreign Iceberg × Glue REST（検証中、将来候補）

- **理由**: FSx for ONTAP データを Iceberg テーブル化し、Glue REST endpoint 経由で UC Foreign Catalog に公開
- データコピー最小化の可能性あり（メタデータポインタのみ）
- BLK-005（`iceberg_rest` 未サポート）のため現時点ではブロック
- 検証計画策定済み、解除後に再評価

## References

- [UC 接続総合ガイド](../ja/fsx-ontap-to-databricks-unity-catalog-guide.md) — 全パスの俯瞰
- [DataSync → S3 ガイド](../ja/datasync-to-s3-guide.md) — 実装詳細
- [ブロッカー追跡: BLK-001](../ja/blocker-tracker.md) — UC × S3 AP
- [ブロッカー追跡: BLK-002](../ja/blocker-tracker.md) — Conditional writes
- [ADR-001](./ADR-001-datasync-as-primary-sync.md) — DataSync 採用決定
