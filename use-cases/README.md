# Industry Use Cases

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

Industry-specific reference architectures for FSx for ONTAP Lakehouse integrations.

Nothing has been built under this directory yet. The table below records which
industry patterns are intended to live here, and where the closest usable
material sits today.

| Use Case | Industry | Pattern | Status | Closest existing material |
|----------|----------|---------|--------|---------------------------|
| Financial Data Mesh | Financial Services | Pattern D (Data Sharing) | 🔲 Planned | [Implementation steps](../docs/adoption-guide/adoption-assessment.md#financial-data-mesh-with-fsx-for-ontap-and-s3-access-points) |
| Manufacturing IoT Lake | Manufacturing | Pattern C (ETL Pipeline) | 🔲 Planned | [Manufacturing data platform templates](../integrations/manufacturing-data-platform/README.md) (deployable today) |
| Healthcare Research | Healthcare | Pattern B (Managed Tables) | 🔲 Planned | [Implementation steps](../docs/adoption-guide/adoption-assessment.md#regulated-data-lakehouse-for-healthcare-research) |
| Media Asset Analytics | Media & Entertainment | Pattern A (Read-Only) | 🔲 Planned | [Zero-copy media governance](../docs/en/zero-copy-media-governance.md) |

> A full use case here means an architecture diagram, CloudFormation templates,
> sample data, and a verification record. None of the four have all four yet, so
> they are listed as planned rather than linked to empty directories.
> For fit criteria and the per-pattern implementation outline, see the
> [Adoption Assessment Guide](../docs/adoption-guide/adoption-assessment.md).

---

<a id="日本語"></a>

## 日本語

FSx for ONTAP Lakehouse 統合の業界別リファレンスアーキテクチャ。

このディレクトリ配下にはまだ何も実装していません。下表は、ここに配置予定の業界別
パターンと、現時点で最も近い既存の資料を記録したものです。

| ユースケース | 業界 | パターン | ステータス | 現時点で最も近い資料 |
|------------|------|---------|----------|-------------------|
| Financial Data Mesh | 金融サービス | パターン D（データ共有） | 🔲 計画中 | [導入ステップ](../docs/adoption-guide/adoption-assessment-ja.md#financial-data-mesh-with-fsx-for-ontap-and-s3-access-points) |
| Manufacturing IoT Lake | 製造 | パターン C（ETL パイプライン） | 🔲 計画中 | [製造データプラットフォームのテンプレート](../integrations/manufacturing-data-platform/README-ja.md)（デプロイ可能） |
| Healthcare Research | 医療 | パターン B（マネージドテーブル） | 🔲 計画中 | [導入ステップ](../docs/adoption-guide/adoption-assessment-ja.md#regulated-data-lakehouse-for-healthcare-research) |
| Media Asset Analytics | メディア | パターン A（読み取り専用） | 🔲 計画中 | [ゼロコピー非構造化データガバナンス](../docs/ja/zero-copy-media-governance.md) |

> ここでのユースケース完成とは、アーキテクチャ図・CloudFormation テンプレート・
> サンプルデータ・検証記録の4点が揃った状態を指します。4件いずれも未達のため、
> 空のディレクトリへリンクせず計画中として記載しています。
> 適用条件とパターン別の導入手順の概要は[導入評価ガイド](../docs/adoption-guide/adoption-assessment-ja.md)を参照してください。
