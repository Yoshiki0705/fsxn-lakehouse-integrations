# ハイブリッド製造アーキテクチャにおけるリアルタイム分析: ポジショニングガイド

🌐 [English](../en/14_realtime_analytics_landscape.md) | 日本語

> 最終更新: 2026-06-16
> 背景: Databricks Data + AI Summit 2026 — Lakehouse//RT 発表

---

## 背景

Databricks Data + AI Summit (2026年6月) にて、Databricks は「**Reyden**」エンジンをベースとした新リアルタイム分析機能 **Lakehouse//RT** を発表した。Delta Lake / Apache Iceberg テーブル上でミリ秒レベルのクエリを直接実行可能にし、「別のリアルタイムサービングシステムが不要になる」ことを目指すと明示。

本ドキュメントでは、オンプレミスのリアルタイム分析（ClickHouse）とクラウドのガバナンス付き分析（Databricks）を含むハイブリッド製造データプラットフォームのアーキテクチャに Lakehouse//RT がどう影響するかを評価する。

---

## アーキテクチャコンテキスト: 3層ハイブリッドプラットフォーム

```
Layer 1: エッジ/工場（オンプレミス）
  Kafka → ClickHouse → ローカルダッシュボード、異常検知

Layer 2: クラウドリアルタイム分析
  Kafka（レプリケーション） → ClickHouse Cloud or Lakehouse//RT → 運用ダッシュボード

Layer 3: ガバナンス付き AI/分析
  Databricks → Unity Catalog → Delta/Iceberg → AI, BI, コンプライアンス
```

Lakehouse//RT が提起する問い: **Layer 2 に専用 RT データベースが必要か、それとも Databricks が Layer 2 と 3 の両方を担えるか？**

---

## 比較: 専用 RT DB vs Lakehouse//RT

| 軸 | 専用 RT DB (例: ClickHouse) | Lakehouse//RT (Databricks) |
|---|---|---|
| デプロイオプション | オンプレ、クラウド、ハイブリッド | クラウドのみ（現時点） |
| クエリレイテンシ | 1-50ms (MergeTree 最適化) | 10-100ms (Reyden, Preview) |
| データフォーマット | 独自カラムナ | オープン (Delta, Iceberg) |
| ガバナンス統合 | 外部（ビルトインカタログなし） | ネイティブ (Unity Catalog) |
| インジェスト遅延 | サブ秒 (Kafka Engine) | 秒〜分 (Structured Streaming) |
| ネットワーク回復力 | 障害時もローカル動作 | クラウド接続必須 |
| コンカレンシー | 数百〜千同時クエリ | 高 (Reyden で改善) |
| コストモデル | インフラベース（クエリ課金なし） | DBU ベース（コンピュート時間課金） |
| AI/ML 統合 | 別パイプライン必要 | ネイティブ (MLflow, Feature Store) |

---

## Lakehouse//RT が専用 RT エンジンを代替できるケース

1. **全データが既に Databricks にある** — 別のインジェストパス不要
2. **クラウドのみのアーキテクチャ** — オンプレ/エッジ要件なし
3. **ガバナンスが最優先** — UC lineage / ACL が必須
4. **10-100ms レイテンシで十分** — BI ダッシュボード（サブ 10ms アラートでない）
5. **統一プラットフォーム志向** — 管理システム数を最小化したい

## 専用 RT エンジンが引き続き必要なケース

1. **オンプレ/エッジ展開** — 工場フロア、製造ライン、断続接続環境
2. **サブ 10ms レイテンシ必須** — リアルタイムアラート、異常検知、制御フィードバック
3. **超高頻度インジェスト** — 毎秒数百万イベント、サブ秒可視化
4. **ネットワーク断続時の動作** — クラウド接続喪失時も継続必須
5. **コスト重視の大量クエリ** — クエリ課金なし、固定インフラコスト
6. **軽量デプロイ** — 1つの分析ユースケースに Databricks フルプラットフォーム不要

---

## ハイブリッドアーキテクチャ: 共存パターン

製造・産業 IoT ユースケースでは、最適アーキテクチャは**両方を使う**ことが多い:

```
オンプレミス                          クラウド (AWS)
┌──────────────────────┐      ┌──────────────────────────┐
│ センサー/PLC/カメラ    │      │                          │
│        │             │      │   Kafka (レプリケーション) │
│        ▼             │      │        │                 │
│ Kafka (ローカル)      │─────▶│        ▼                 │
│        │             │      │ Databricks Lakehouse//RT │
│        ▼             │      │ (ガバナンス付き、AI対応、    │
│ ClickHouse (ローカル) │      │  ミリ秒クエリ)             │
│ - 異常検知            │      │                          │
│ - 品質ダッシュボード    │      │ Unity Catalog ガバナンス   │
│ - サブ5msアラート      │      │ AI/ML モデル訓練           │
│                      │      │ 工場横断比較分析            │
│ ペイロードストレージ    │      │                          │
│ (ONTAP オンプレ)      │─ ─ ─ │ FSx for ONTAP (キャッシュ) │
└──────────────────────┘      └──────────────────────────┘
```

**役割分担:**
- **ローカル ClickHouse**: 即時運用分析（ライン停止判断、品質アラート、OEE）
- **Lakehouse//RT / Databricks**: 工場横断分析、AI サービング、ガバナンス付き BI、コンプライアンス

---

## この PoC への影響

| PoC コンポーネント | Lakehouse//RT の影響 | アクション |
|---|---|---|
| オンプレ ClickHouse (Phase B) | **影響なし** — クラウドのみ | 設計通り継続 |
| ClickHouse Cloud (Phase A) | **代替可能性** — Databricks が既にあれば | GA 後に再評価 |
| Kafka → ClickHouse パイプライン | **補完関係** — CH=ローカル RT、DB=ガバナンス分析 | 両パス維持 |
| Databricks Structured Streaming | **強化** — Streaming table のレイテンシ改善の可能性 | GA 性能を監視 |

### 推奨

- **Phase A (AWS)**: ClickHouse Cloud でリアルタイム検証を継続。Lakehouse//RT GA + 価格確定後に再評価。
- **Phase B (オンプレ)**: Instaclustr 経由 ClickHouse オンプレは影響なし。Lakehouse//RT にオンプレオプションなし。
- **長期**: 「両方使う」アーキテクチャは Lakehouse//RT のクラウド限定スコープにより検証済み。

---

## 主要ポイント

1. Lakehouse//RT は Databricks 内クラウドリアルタイム分析の大きな進歩
2. 「別のサービングレイヤー」パターン（クラウド上の ClickHouse, Druid, Pinot）を直接ターゲット
3. オンプレ、エッジ、ネットワーク断続環境のリアルタイム分析には対応**しない**
4. ハイブリッド製造アーキテクチャでは両レイヤーが引き続き必要
5. ストレージレイヤー（ONTAP / FSx for ONTAP）は両パターンにペイロードソースとして機能し影響なし

---

## 参考

- [Databricks: Introducing Lakehouse//RT](https://www.databricks.com/blog/introducing-lakehousert-real-time-performance-unified-lakehouse) (2026-06-16)
- [Databricks: プレスリリース](https://www.databricks.com/company/newsroom/press-releases/databricks-launches-lakehousert-bring-real-time-analytics-directly) (2026-06-16)
- [ClickHouse vs Databricks: Join Performance](https://clickhouse.com/blog/join-me-if-you-can-clickhouse-vs-databricks-snowflake-join-performance) (2025)
- [ClickHouse: Real-Time Analytics Platforms Comparison](https://clickhouse.com/resources/engineering/real-time-analytics-platforms-a-practical-comparison) (2025)
