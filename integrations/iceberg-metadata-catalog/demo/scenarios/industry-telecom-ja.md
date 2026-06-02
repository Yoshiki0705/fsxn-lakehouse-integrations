# 通信業向けデモシナリオ: ネットワークログ & 鉄塔点検インテリジェンス

🌐 日本語 | [English](industry-telecom.md)

> ネットワークログ、鉄塔点検写真、顧客契約書、スペクトル分析レポートを通信事業者のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

通信事業者が直面する課題：

- **ネットワークログの過負荷**: RAN、コア、トランスポートネットワークから日々数百万のログファイルが生成され統一検索機能なし
- **鉄塔点検の断片化**: 点検写真、構造レポート、保守記録がフィールドオペレーションシステムに分散
- **契約管理の複雑さ**: 顧客契約書、SLA、サービス修正が法人・個人部門に一貫性なく保管
- **スペクトルデータのサイロ化**: RF測定、干渉レポート、カバレッジマップが計画文書と非連結

### 解決後の姿

- ネットワークログと通信文書がネットワークエレメント、重大度、イベントタイプ別に自動分類
- 「東部リージョンで構造的懸念のある全鉄塔点検を表示」が SQL で即座に回答
- 顧客契約がSLAパフォーマンス指標と修正履歴にリンク
- スペクトル分析がネットワーク性能と相関し最適化計画に活用

---

## デモフロー

### ステップ 1: サンプル通信ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry telecom --target /vol/telecom-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `network-log-RAN-site042-20260601.log` | ネットワークログ | RANサイトイベントログ、42,000イベント |
| `tower-inspection-SITE042-20260601.pdf` | 鉄塔点検 | 年次構造点検 |
| `tower-photo-SITE042-antenna-array.jpg` | 点検写真 | アンテナアレイ状態確認 |
| `customer-contract-ENT-C08842-5G.pdf` | 顧客契約書 | 法人5G SLA契約 |
| `spectrum-analysis-band77-region-east.pdf` | スペクトル分析 | n77バンド利用状況レポート |

**トークポイント**:
- 「ネットワーク管理システムがログを FSx にエクスポート — FPolicy が運用に影響なくトリガー」
- 「フィールド技術者の写真とオフィス文書が同じパイプラインで処理」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: network-log-RAN-site042-20260601.log
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: ネットワークログ/RAN
   - サイト ID: SITE-042
   - リージョン: 東部
   - 日付: 2026-06-01
   - イベント: 42,000
   - クリティカルアラート: 3
   - ネットワークエレメント: gNodeB
   - テクノロジー: 5G NR
   - 異常検出: ハンドオーバー失敗スパイク
✅ Classified in 40.1s | Cost: $0.05
```

---

### ステップ 3〜5: （英語版と同等の構造）

各ステップの詳細は英語版 [industry-telecom.md](./industry-telecom.md) を参照。

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 94% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 40 秒/ファイル | ログファイルは効率的に処理 |
| 1 ファイルあたりコスト | $0.05–$0.07 | ログ: $0.05、レポート: $0.07 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| ネットワーク障害調査 | 1 時間/インシデント × 500 件/年 → 10 分 | **417 時間削減** |
| 鉄塔点検検索 | 15 分/検索 × 500 検索/年 → 2 分 | **108 時間削減** |
| 契約管理 | 20 分/契約 × 1,000 契約/年 → 3 分 | **283 時間削減** |
| スペクトル計画 | 4 時間/分析 × 50 分析/年 → 1 時間 | **150 時間削減** |

**保守的年間生産性効果**: ~958 時間 × ¥5,500/時 = **¥5,269,000**（~$35,100）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,752%

---

## 通信業に関連する制限事項

| 制限事項 | 通信業への影響 |
|---------|--------------|
| S3 AP（パイプラインは読み取りのみ使用） | パイプライン経由でネットワーク構成変更をトリガー不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の NOC アラートトリガー不可 |
| リアルタイム制約 | リアルタイム障害管理には非対応。バッチログカタログ化 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| ログ量 | 大量ログストリームはコスト効率のため FSx 保管前に集約が必要 |
| 規制データ | 通信プライバシー規制に従った顧客データ取り扱い |
| OT/IT 分離 | FPolicy がネットワーク管理システム性能に影響しないことを確認 |

---

## カスタマイズポイント

1. **ネットワークエレメント**: 特定ベンダースタック向け設定（Ericsson、Nokia、Samsung、O-RAN）
2. **リージョンマッピング**: サイトIDを地理リージョンと行政区域にマッピング
3. **SLAカテゴリ**: 契約ティアとパフォーマンス閾値追跡を設定
4. **スペクトルバンド**: オペレーターライセンスごとの周波数割当を追加

---

## Iceberg Time Travel: 履歴比較

Iceberg テーブル形式のユニークな利点の一つがタイムトラベル — 過去の任意の時点でのメタデータをクエリする機能です。

```sql
-- スナップショット履歴の表示
SELECT * FROM s3_tables.metadata_catalog.file_metadata$snapshots
ORDER BY committed_at DESC LIMIT 10;

-- 24 時間前の時点でのメタデータをクエリ
SELECT ai_classification, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
FOR TIMESTAMP AS OF (current_timestamp - interval '24' hour)
GROUP BY ai_classification;

-- 現在 vs. 以前の分類件数を比較
WITH current_state AS (
  SELECT ai_classification, COUNT(*) as current_count
  FROM s3_tables.metadata_catalog.file_metadata
  GROUP BY ai_classification
),
previous_state AS (
  SELECT ai_classification, COUNT(*) as previous_count
  FROM s3_tables.metadata_catalog.file_metadata
  FOR TIMESTAMP AS OF (current_timestamp - interval '7' day)
  GROUP BY ai_classification
)
SELECT COALESCE(c.ai_classification, p.ai_classification) as category,
       COALESCE(c.current_count, 0) as now,
       COALESCE(p.previous_count, 0) as week_ago,
       COALESCE(c.current_count, 0) - COALESCE(p.previous_count, 0) as delta
FROM current_state c
FULL OUTER JOIN previous_state p ON c.ai_classification = p.ai_classification
ORDER BY delta DESC;
```

**この業界でのタイムトラベル活用例**:
- ファイル分類分布の時系列変化を追跡
- コンプライアンス判断時のメタデータ状態を監査
- 意図しない一括再分類や削除からの復旧
- 異なる AI モデルバージョン間のエンリッチメント結果比較


---

*関連: [use-cases/telecom/](../../use-cases/telecom/)*
*ペアドキュメント: [industry-telecom.md](./industry-telecom.md)*
