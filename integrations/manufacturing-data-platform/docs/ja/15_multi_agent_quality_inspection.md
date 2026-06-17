🌐 [English](../en/15_multi_agent_quality_inspection.md) | **日本語**

# Omnigent によるマルチエージェント品質検査

> **ステータス**: 設計フェーズ。Manufacturing PoC Phase A インフラ完了に依存。
> **最終更新**: 2026-06-15
> **関連**: [アーキテクチャ設計](03_architecture_design.md) | [リアルタイム分析ランドスケープ](14_realtime_analytics_landscape.md)

---

## 概要

本ドキュメントは、製造データプラットフォーム（Kafka + ClickHouse + FSx for ONTAP + Databricks）と統合された、Omnigent ベースの AI マルチエージェント品質検査システムの設計を記述する。

**主要設計判断**: リアルタイム検出は ClickHouse Materialized Views（ルールベース、サブ秒）が担当。Omnigent エージェントは**バッチ品質分析**、**傾向検出**、**レポート生成**、**AI 異常分類**（秒〜分）を担当。

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│  エッジ / 工場                                                    │
│  センサー → MQTT → Kafka (MSK) → トピック:                        │
│    • mfg.sensors.temperature                                     │
│    • mfg.sensors.vibration                                       │
│    • mfg.quality.inspection-logs                                 │
│    • mfg.payloads.new-file-events                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  リアルタイム層 (ClickHouse)                                      │
│  • Kafka Engine (サブ秒インジェスト)                               │
│  • Materialized Views (ルールベース異常検知)                       │
│  • アラート (閾値ベース、即時)                                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ (アラートトリガー or スケジュール)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  AI 品質検査層 (Omnigent)                                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Supervisor Agent                                         │    │
│  │  ├─→ anomaly-detector (ClickHouse MCP、読み取り専用)      │    │
│  │  ├─→ quality-reporter (構造化 JSON 出力)                  │    │
│  │  └─→ payload-cataloger (FSx for ONTAP → Iceberg)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ポリシー: cost_cap=$10/日、ClickHouse=SELECT のみ、             │
│           FSx=deny-by-default、escalation=score>0.8              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  ガバナンス層 (Databricks)                                        │
│  • Unity Catalog (lineage, ACL, 監査)                            │
│  • Delta Lake (品質結果テーブル)                                   │
│  • MLflow (モデル評価トラッキング)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## エージェント設計

### Supervisor Agent

品質検査ワークフローをオーケストレーション。専門タスクをサブエージェントに委任。

**責務**:
- トリガー受信（スケジュール or アラート）
- ClickHouse で直近の異常パターンをクエリ
- サブエージェントに分析を委任
- 結果の集約
- 重大問題のエスカレーション（anomaly_score > 0.8）
- 結果を Databricks UC マネージドテーブルに書き込み

### サブエージェント: Anomaly Detector

**目的**: ClickHouse 時系列データをクエリしてパターンを特定

**制約**:
- 読み取り専用 SQL（SELECT, SHOW, DESCRIBE, EXPLAIN）
- クエリタイムアウト: 10 秒
- 最大結果行数: 10,000
- パラメータ化クエリ（SQL インジェクション防止）
- `data_as_of` タイムスタンプの報告必須

### サブエージェント: Quality Reporter

**目的**: 検査結果から構造化品質レポートを生成

**出力フォーマット**:
```json
{
  "report_id": "uuid",
  "data_as_of": "2026-06-15T12:00:00Z",
  "data_staleness_seconds": 45,
  "findings": [
    {
      "finding_id": "uuid",
      "category": "temperature_anomaly",
      "severity": "high",
      "confidence": 0.92,
      "evidence": "センサー S-101 が 5 連続読み取りで 85°C を超過",
      "recommendation": "24 時間以内のメンテナンス点検をスケジュール",
      "source_query": "SELECT ... FROM sensor_readings WHERE ..."
    }
  ],
  "summary": {
    "total_findings": 3,
    "critical": 1,
    "high": 1,
    "medium": 1,
    "escalated": true
  }
}
```

### サブエージェント: Payload Cataloger

**目的**: FSx for ONTAP 上の品質検査画像/動画を Iceberg メタデータカタログに登録

**制約**:
- FSx for ONTAP は NFS mount 経由で読み取り専用
- メタデータは Iceberg テーブルに書き込み（S3 Access Point）
- ペイロード URI を ClickHouse の品質イベントにリンク

---

## データ分離（工場/ライン単位）

各工場ラインは独自のデータ境界内で動作:

```yaml
# ライン A エージェントインスタンス
os_env:
  sandbox:
    read_paths: [/mnt/fsxn/factory-tokyo/line-a/]
    write_paths: [./output/line-a/]

# ライン B エージェントインスタンス
os_env:
  sandbox:
    read_paths: [/mnt/fsxn/factory-tokyo/line-b/]
    write_paths: [./output/line-b/]
```

ライン A のエージェントはライン B のデータにアクセスできない。これは OS サンドボックスレベル（Omnibox）で強制され、プロンプトによる制御ではない。

---

## 耐障害設計

| 障害モード | エージェント動作 | 復旧 |
|-----------|----------------|------|
| Kafka メッセージなし > 5 分 | WARNING ログ、data_staleness 報告 | 監視継続 |
| ClickHouse クエリタイムアウト > 10s | 1 回リトライ、その後 ERROR でスキップ | DLQ 相当にログ |
| FSx for ONTAP mount 到達不可 | 即座に STOP、エスカレーション | 人間による再起動が必要 |
| Omnigent サーバークラッシュ | セッションは DB に永続化 | systemd 自動再起動 |
| コスト予算超過 | セッション一時停止（ASK ポリシー） | 人間承認で継続 |

---

## 既存 PoC インフラとの統合

| コンポーネント | ステータス | マルチエージェントとの接続 |
|-------------|---------|--------------------------|
| MSK (Kafka) | Phase A ✅ | トピックイベントでエージェントトリガー |
| ClickHouse Cloud | Phase A ✅ | サブエージェントが MCP 経由でクエリ |
| FSx for ONTAP volumes | Phase A ✅ | ペイロード保管、NFS mount |
| Databricks workspace | Phase A 🔄 | 結果の UC テーブル、モデルの FMAPI |

---

## 可観測性

| メトリクス | ソース | アラート |
|-----------|--------|---------|
| `quality.findings.critical` | エージェント出力 | > 0 → PagerDuty |
| `quality.data_staleness_seconds` | エージェント出力 | > 300 → WARNING |
| `omnigent.session.cost_usd` | Omnigent テレメトリ | > $5/session |
| `clickhouse.query_duration_ms` | ClickHouse MCP | P99 > 5000ms |

---

## コスト見積もり

| コンポーネント | 単価 | 月額（10 検査/日） |
|-------------|------|-------------------|
| Supervisor Agent (Claude Sonnet) | ~$0.05/検査 | ~$15 |
| Anomaly Detector クエリ | ~$0.01/検査 | ~$3 |
| Quality Reporter (Haiku) | ~$0.005/検査 | ~$1.5 |
| Payload Cataloger (embeddings) | ~$0.01/ファイル | 可変 |
| **合計** | | **~$20-50/月** |

`daily_cost_cap: $10` ポリシーで統制。

---

## 前提条件

- [ ] Manufacturing PoC Phase A インフラ完了
- [ ] Omnigent が EC2 にインストール済み（Ubuntu 24.04、検証済み）
- [ ] Anthropic API key 設定済み（`omnigent setup`）
- [ ] ClickHouse MCP サーバー実装済み
- [ ] FSx for ONTAP NFS mount がエージェントホストからアクセス可能
- [ ] Databricks workspace で FMAPI アクセス可能

---

## 参考

- [Omnigent マルチエージェント評価](../../../../docs/ja/omnigent-multi-agent-evaluation.md)
- [アーキテクチャ設計](03_architecture_design.md)
- [リアルタイム分析ランドスケープ](14_realtime_analytics_landscape.md)
- [SLO & 運用レディネス](10_slo_operational_readiness.md)
