🌐 [English](../en/omnigent-multi-agent-evaluation.md) | **日本語**

# Omnigent マルチエージェント統合: FSx for ONTAP レイクハウスワークフロー向け評価

> **ステータス**: Phase 0 評価完了（インストール検証済み、基本動作確認済み）。Alpha ソフトウェア — API 安定性は保証されていません。2026-06-15 更新。

> **レビューノート**: 本評価は複数レンズによるアーキテクチャレビューを経て作成されています。レビュアーレンズは**ロールのみ**で記述（個人名・所属帰属なし）。各主張にはエビデンス階層を付記: **Public**（公開情報から検証可能）、**Archetype**（ロールベースの推論）、**Project-context**（内部検証）。

---

## Omnigent とは

Omnigent は Databricks が 2026 年 6 月中旬にオープンソース公開した（共同創業者 Matei Zaharia が発表）Apache 2.0 ライセンスの**メタハーネス**です。複数のハーネス（Claude Code, Codex, Pi, カスタムエージェント）にわたる AI エージェントセッションの合成・ガバナンス・コラボレーションを統一インターフェースで提供します。

| 機能 | 説明 |
|------|------|
| Composition | コード書き換えなしで複数モデル・ハーネスを組み合わせ |
| Contextual Policies | ステートフルなコスト上限、モデルルーティング、リスクベースエスカレーション — プロンプトではなくランタイムで適用 |
| Secure OS Sandbox (Omnibox) | ファイルシステム/ネットワークアクセス制限、エージェントからクレデンシャルを隠蔽 |
| Collaboration | URL でライブセッションを共有しリアルタイムチーム協働 |
| Built-in Agents | Polly（マルチエージェントコーディングオーケストレータ）と Debby（モデルディベート） |
| Multi-device | Terminal / Web UI / Desktop / Mobile / REST API |
| Custom Agents | MCP ツールサポート付き宣言的 YAML 定義 |

**ソース**: [Databricks Blog](https://www.databricks.com/blog/introducing-omnigent-meta-harness-combine-control-and-share-your-agents) | [omnigent.ai](https://omnigent.ai/) | [GitHub](https://github.com/omnigent-ai/omnigent)

### DAIS 2026 アップデート（2026-06-16）: Managed Omnigent + Unity AI Gateway

Data + AI Summit 2026 で、本評価に直接影響する 2 つの発表がありました（evidence tier: **Public**）。

- **Managed Omnigent on Databricks（Beta）**: OSS の Omnigent をそのまま Databricks にマネージドワークフローとしてデプロイ可能。共有履歴・リモートアクセス・コラボレーション・**Lakebox** での分離されたクラウド実行を提供。既存の setup / harness / workflow / skill を再構築なしで実行。([AI Gateway 発表](https://www.databricks.com/blog/ai-governance-data-ai-summit-2026-whats-new-unity-ai-gateway))
- **Unity AI Gateway**: Unity Catalog ベースのガバナンスレイヤー。モデル・エージェント・MCP サービス・skill をガバナンスし、**Managed Omnigent の全インタラクションをガバナンス**。中央定義のポリシー、コスト制御（ハード spend cap、smart routing）、ランタイム Contextual Service Policies（Beta: allow / deny / require-approval）、組み込みガードレール（PII / prompt injection / jailbreak / unsafe content）、統合エージェントトレーシング（Lakewatch で分析）。([What's new in Unity Catalog](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026))
- **Agent Bricks との関係**: Databricks は Managed Omnigent を **Agent Bricks**（開発者向けの包括的エージェントプラットフォーム）の*一部*として位置づけ。Agent Bricks は Choice（任意のモデル/ハーネス — LangGraph, CrewAI, Claude Code SDK 等 — を Managed Omnigent でオーケストレーション）、Context（Genie Ontology, MCP, Lakebase 上で動作する agent memory — **Lakebase Search**（Beta）がハイブリッド vector + full-text retrieval を agent-native backend として追加 — および Document Intelligence）、Control（Unity AI Gateway）の 3 本柱で構成。つまり Agent Bricks = プラットフォーム、Managed Omnigent = そのハーネスオーケストレーション要素、Unity AI Gateway = そのガバナンスレイヤー。([Agent Bricks DAIS 2026](https://www.databricks.com/blog/agent-bricks-dais-2026))

**本評価への示唆**: 「開発 = Omnigent / 本番 = Databricks」の仮説が具体化した。self-hosted OSS Omnigent は開発・マルチベンダー実験向け、**Unity AI Gateway がガバナンスする Managed Omnigent on Databricks** が同一ワークフローの本番パス。以下の比較・設計セクションに反映済み。

---

## 本リポジトリとの関連性

本リポジトリは FSx for ONTAP と各分析プラットフォームの統合パターンを検証しています。Omnigent は 3 つのレベルで関連します。

### 1. 開発ワークフローの強化

Omnigent はこのリポジトリの PoC テンプレート、統合テスト、ドキュメントに対して複数のコーディングエージェントを並列実行でき、コストポリシーとサンドボックスで制御されます。

### 2. 製造データプラットフォーム — マルチエージェント品質パイプライン

[製造データプラットフォーム PoC](../../integrations/manufacturing-data-platform/) は Kafka、ClickHouse、FSx for ONTAP、Databricks を含みます。Omnigent のスーパーバイザーエージェントパターンにより:
- スキーマ検証、異常検出、ペイロードカタログ登録の専門サブエージェント
- メタハーネス層で ClickHouse 読み取り専用ポリシーを強制
- AI 品質検査のコスト上限とエスカレーション閾値

### 3. Iceberg メタデータカタログ — マルチモデル分類

[Iceberg メタデータカタログ](../../integrations/iceberg-metadata-catalog/) は Bedrock Vision でファイル分類を行います。Omnigent の Debby（モデルディベート）パターンによりマルチモデル比較で分類信頼度を向上できます。

---

## Phase 0 評価結果（2026-06-15）

### インストール

| 環境 | 結果 | 備考 |
|------|------|------|
| macOS (Intel x86_64) | ❌ 非対応 | `cel-expr-python` 依存パッケージが x86_64 macOS wheel を提供していない |
| Ubuntu 24.04 (x86_64 Linux) | ✅ 成功 | Omnigent 0.1.0、全 CLI コマンド動作確認 |
| macOS (Apple Silicon ARM64) | ✅ 動作想定 | wheel あり、本プロジェクトでは未テスト |

### システム要件

- Python 3.12+
- Node.js 22 LTS + npm
- tmux
- uv（Python パッケージマネージャー）

### 検証済み機能（Project-context）

| 機能 | 検証 | 方法 |
|------|:---:|------|
| CLI インストール | ✅ | `curl -fsSL https://omnigent.ai/install.sh \| sh` |
| サーバー起動 | ✅ | `omnigent server start` → http://127.0.0.1:6767 |
| REST API `/v1/agents` | ✅ | ビルトイン 4 エージェント（debby, polly, claude-native-ui, codex-native-ui）を返却 |
| REST API `/v1/policies` | ✅ | 空リスト（ポリシー未設定）— API 動作確認 |
| Web UI | ✅ | サーバールートで SPA 配信 |
| MCP ツール対応 | ✅（文書確認） | stdio / HTTP トランスポート、バンドルサーバー（GitHub, Slack 等） |
| Databricks FMAPI 統合 | ✅（文書確認） | `databricks-` モデルプレフィックス、`~/.databrickscfg` プロファイル認証 |

### 主要アーキテクチャ所見

```
Interfaces (Terminal / Web / Desktop / Mobile / REST API)
    ↓
Server (Policies + Session Store + REST API, port 6767)
    ↓
Runner (サンドボックス付きエージェント実行 — local / Modal / Daytona)
    ↓
Agent (Harness + Model + Tools + Policies, YAML で定義)
```

- **Server はステートフル**: SQLite（または Postgres）でセッション永続化とポリシー状態管理
- **Policies は動的**: セッション全体で累積コスト、ツール呼び出し回数、リスクスコアを追跡
- **3 つのポリシーレベル**: Session（ユーザー）> Agent config（開発者）> Server-wide（管理者）
- **サブエージェントをツールとして定義**: `type: agent` でエージェント間委任が可能

---

## 設計: Kiro AIDLC との統合

### 補完モデル

| レイヤー | ツール | 責務 |
|---------|--------|------|
| 設計・ライフサイクル | Kiro | Spec（requirements → design → tasks）、Steering、Hooks |
| ランタイム合成 | Omnigent | マルチエージェントオーケストレーション、ポリシー、サンドボックス、コラボレーション |
| 本番ガバナンス | Unity AI Gateway | モデル/エージェント/MCP/skill のランタイムポリシー強制、ハード spend cap、ガードレール、エージェントトレーシング |
| 本番パイプライン | Databricks Agent Bricks / Lakeflow | Unity Catalog ガバナンス、マネージドデプロイ |

Kiro と Omnigent は重複しません。Kiro は**何を構築するか**（spec-driven）を管理。Omnigent は**エージェントをどう協調実行するか**（ランタイム合成）を管理。本番データパイプラインのオーケストレーションには Databricks Workflows / DLT を使用 — Omnigent はパイプラインスケジューリングには使用しません。

### ポリシー責務分割

| 制御 | Kiro | Omnigent |
|------|------|----------|
| コード品質（lint, format） | ✅ Hooks (fileEdited) | — |
| セキュリティ（secrets, Actions） | ✅ pre-commit + CI | — |
| LLM コスト制御 | — | ✅ cost_budget policy |
| ファイルアクセス制限 | — | ✅ Omnibox sandbox |
| データアクセス（FSx ACL） | Steering（原則） | Custom policy（強制） |
| マルチエージェントレビュー | — | ✅ Polly cross-review |

### Bedrock 連携パス

Omnigent は Amazon Bedrock をモデルプロバイダーとしてネイティブサポートしていません。3 つのパスが利用可能:

1. **Databricks Foundation Model API**（プライマリ）: Databricks ワークスペース経由で Bedrock モデルをルーティング
2. **OpenAI 互換 Gateway**（フォールバック）: LiteLLM 等のプロキシを利用
3. **MCP ツール**（Bedrock 固有 API 用）: Vision 分類、Embeddings をツール呼び出しとして提供

---

## ユースケース設計

### 製造品質スーパーバイザー（マルチエージェント）

```
Supervisor Agent (Claude Sonnet)
  ├─→ anomaly-detector (ClickHouse 読み取り専用クエリ)
  ├─→ quality-reporter (構造化 JSON レポート)
  └─→ payload-cataloger (FSx for ONTAP → Iceberg)

ポリシー:
  - daily_cost_cap: $10/日
  - rate_limit: 200 ツール呼び出し/セッション
  - clickhouse: SELECT のみ（INSERT/UPDATE/DELETE 拒否）
  - fsxn: deny-by-default、NFS mount 経由の読み取りのみ

設計判断:
  - リアルタイム検出: ClickHouse Materialized Views（非AI、サブ秒）
  - バッチ分析: Omnigent エージェント（AI、秒〜分）
  - エージェントは ClickHouse ルールベースアラートを置き換えない
```

### Iceberg マルチモデル分類器（Debby パターン）

```
分類オーケストレータ
  → 同一画像を 3 モデル（Claude Haiku / Nova Lite / Mistral Large 3）で分類
  → 結果比較（Debby ディベートパターン / majority vote）
  → 3/3 一致（unanimous）→ 高信頼度で採用
  → 2/3 一致（majority）→ 中信頼度で多数派を採用
  → 0 一致（3-way split）→ 人間レビューにエスカレーション
  → 結果を Iceberg テーブルに記録（UC lineage 保持）
```

#### 検証済み結果（2026-06-17, Project-context）

| メトリクス | 結果 |
|-----------|------|
| テスト済みモデル | Claude 3 Haiku, Amazon Nova Lite, Mistral Large 3 |
| 実行方式 | ThreadPoolExecutor（並列、max_workers=3） |
| レイテンシ | 0.6–0.7s/画像（並列） |
| コスト倍率 | 単一モデル比 1.2x |
| Unanimous 信頼度 | 0.94–0.96 |
| 不一致処理 | 人間レビューキューへ正常エスカレーション |
| 合意方式 | True majority vote（3 モデル） |

**実装**: `integrations/iceberg-metadata-catalog/lambda/enrich-image/multimodel_classify.py`
**評価フレームワーク**: `evaluation.py` — accuracy, F1 macro, カテゴリ別 precision/recall, コスト比較
**エビデンス**: `verification-pack/multimodel-classification/multimodel-classification-evidence.yaml`

---

## FSx for ONTAP 統合設計

### マルチプロトコルアクセスパターン

| ユースケース | プロトコル | 理由 |
|-------------|-----------|------|
| 画像/動画ペイロード読み取り | NFS mount (`/mnt/fsxn/`) | 低レイテンシ、POSIX ACL |
| 分析クエリ用 Parquet | S3 Access Point | Athena/EMR/Databricks との一貫性 |
| メタデータカタログ操作 | S3 Access Point | Iceberg テーブル書き込み |
| 品質レポート出力 | NFS mount | ファイルベースの出力 |

### データ保護統合

| ONTAP 機能 | エージェントユースケース |
|-----------|----------------------|
| Snapshot | バッチ分析用の一貫した point-in-time データ |
| FlexClone | 同一データセットでの A/B テスト（ゼロコピー） |
| SnapMirror | エージェント生成メタデータの DR |
| FPolicy audit | エージェントアクセスログと ONTAP 監査イベントの突合 |

### セキュリティ設計

- **Deny-by-default**: 明示的に許可されない限りエージェントはファイルにアクセス不可
- **Omnibox sandbox**: `read_paths` を指定 FSx ボリュームに制限
- **クレデンシャル非公開**: API キーは Omnigent 経由でブローカリング、エージェントからは不可視
- **監査証跡**: エージェントツール呼び出しログ + ONTAP fpolicy イベントで突合
- **プロンプトインジェクション防御**: 取得ファイル内容はデータとして扱い、指示としては扱わない

---

## 可観測性設計

| メトリクス | 目的 | アラート閾値 |
|-----------|------|------------|
| `omnigent.session.cost_usd` | 累積 LLM コスト | > $5/session |
| `omnigent.agent.tool_calls` | ツール呼び出し回数 | > 100/session |
| `omnigent.policy.deny_count` | ポリシー拒否回数 | > 10/hour |
| `omnigent.agent.latency_ms` | 応答時間 | P99 > 30s |

統合: Omnigent OpenTelemetry → AWS Distro for OpenTelemetry (ADOT) → CloudWatch Metrics + X-Ray。

---

## 比較: Omnigent vs Databricks Agent Bricks

| 軸 | Omnigent（OSS, self-hosted） | Managed Omnigent on Databricks | Agent Bricks（開発者エージェントプラットフォーム） |
|----|------------------------------|-------------------------------|-------------------------------|
| 管理形態 | Self-hosted (OSS) | Databricks マネージド（Beta, Lakebox 実行） | Databricks マネージドプラットフォーム |
| ガバナンス | カスタムポリシー (CEL) | Unity AI Gateway（UC ネイティブ runtime policy） | Unity AI Gateway（Control の柱） |
| モデル対応 | マルチベンダー | マルチベンダー + AI Gateway smart routing | 任意のモデル/ハーネス（Choice の柱） |
| コラボレーション | URL セッション共有 | 共有履歴 + リモートアクセス | プラットフォーム統合 |
| デプロイ | EC2 / ECS / Modal | Lakebox（分離クラウド実行） | Databricks Apps |
| サンドボックス | OS レベル (Omnibox) | Lakebox 分離 | Databricks Sandbox（セキュア VM） |
| 最適用途 | 開発、実験、クロスベンダー | UC データと並ぶ本番エージェントワークフロー | Databricks 上のエンドツーエンドエージェントプラットフォーム |

> **注**: これらは厳密には排他的ではない — Managed Omnigent は Agent Bricks の*一部*（ハーネスオーケストレーション選択肢）として提供され、両マネージドパスは Unity AI Gateway がガバナンスする。本表は OSS ハーネス・そのマネージド形態・広義のプラットフォームを明確化のため分離している。

**Unity AI Gateway** はマネージドパス共通のガバナンスレイヤー: モデル・エージェント・MCP サービス（Google Drive, Jira, Confluence, Slack, GitHub, SharePoint のマネージドコネクタ + カスタム）・skill を、ハード spend cap・smart routing・Contextual Service Policies（Beta）・ガードレール・統合トレーシングでガバナンスする。

**選定ガイダンス**（Archetype）:
- **OSS Omnigent**: マルチベンダーモデル実験、開発時オーケストレーション、セッション共有、Databricks 外環境
- **Managed Omnigent on Databricks**: 同一ワークフローを Unity AI Gateway ガバナンス下で本番運用、UC ガバナンスデータと並走
- **Agent Bricks**: Databricks 上のエンドツーエンドエージェントプラットフォーム（Managed Omnigent を含むモデル/ハーネス選択、Genie Ontology コンテキスト、Unity AI Gateway 制御）

---

## ガードレールアーキテクチャ（3 レイヤー）

```
Layer 1: Omnigent Policies — ランタイム制御（コスト、レート、ACL）
Layer 2: Bedrock Guardrails — モデル出力フィルタ（PII、毒性、オフトピック）
Layer 3: Application Validation — スキーマ + ビジネスロジック検証
```

各レイヤーは独立して動作。いずれかが DENY を返せば出力はブロックされます。

---

## 制約事項

| 制約 | 影響 | 緩和策 |
|------|------|--------|
| Alpha ステータス | API が変更される可能性 | バージョン固定、YAML を最小限に保つ |
| macOS Intel 非対応 | 旧 Mac で開発不可 | Linux（EC2/Docker）または Apple Silicon を使用 |
| Bedrock ネイティブ非対応 | Bedrock を直接モデルとして使用不可 | Gateway または Databricks FMAPI ルーティング |
| 単一サーバーアーキテクチャ | 本番で SPOF | systemd/ECS 自動再起動（PoC）。本番は Managed Omnigent on Databricks（Lakebox）を利用 |
| Volumes コネクタ未対応 | OpenSharing で非構造化データ共有不可 | コネクタ開発をトラッキング、NFS/S3 AP を直接利用 |

---

## 次のステップ

| Phase | アクティビティ | タイムライン | ステータス |
|-------|--------------|------------|-----------|
| 0 | ✅ インストール + 評価 | 完了 | ✅ |
| 1 | Kiro Steering 統合ガイド | 2026-06 | ✅ |
| 2 | Iceberg マルチモデルディベート PoC | 2026-06 | ✅ 検証済み (PR #72) |
| 3 | 製造マルチエージェント品質設計 | 2026-07 | 🔲 ブロック中（インフラ依存） |
| 4 | 公開ドキュメント最終化 | 2026-07 | 🔄 進行中 |

---

## 業界事例（Public Evidence、DAIS 2026）

以下は本リポジトリのユースケースに関連する、公開済みの Agent Bricks 導入事例。

### 7-Eleven: メンテナンス技術者向け GenAI アシスタント

| 観点 | 内容 |
|------|------|
| 課題 | 13,000+ 店舗にわたる数千の設備マニュアル（PDF、スプレッドシート）。技術者は現場でスマホのみ |
| 解決策 | RAG + Agent Bricks + ベクトルインデックス。Microsoft Teams 統合 |
| 成果 | 初回修理成功率 +25%、検索時間 -60%、レイテンシ -40% |
| 関連性 | 本リポジトリの iceberg-metadata-catalog と同じパターン（非構造化ドキュメント → AI 分類 → 即時検索） |

ソース: [Databricks Blog](https://www.databricks.com/blog/how-7-eleven-transformed-maintenance-technician-knowledge-access-databricks-agent-bricks)

### AstraZeneca: マルチエージェントシステム（10x スケール）

| 観点 | 内容 |
|------|------|
| 課題 | 商用チームが治療領域横断で医薬品データにアクセス — 構造化（Genie Spaces）+ 非構造化（40万+ 臨床文書） |
| 解決策 | Supervisor Agent が治療領域別サブエージェントを coordination。Knowledge Assistant（非構造化）。Vega-Lite で Teams に可視化 |
| 成果 | エージェント 10x スケール。40万ドキュメントを 60 分未満でコードなし処理 |
| 関連性 | 本リポジトリの Omnigent Phase 3（製造マルチエージェント品質スーパーバイザー + サブエージェント）の参考アーキテクチャ |

ソース: [DAIS Session](https://www.databricks.com/dataaisummit/session/astrazenecas-multi-agent-system-lessons-scaling-agents-10x-agent-bricks), [Databricks Blog](https://www.databricks.com/blog/bringing-visualizations-life-multi-agent-systems-vega-lite)

## 参考リンク

- [Omnigent 公式サイト](https://omnigent.ai/)
- [Omnigent GitHub リポジトリ](https://github.com/omnigent-ai/omnigent)
- [Databricks Blog: Introducing Omnigent](https://www.databricks.com/blog/introducing-omnigent-meta-harness-combine-control-and-share-your-agents)
- [Unity AI Gateway (DAIS 2026)](https://www.databricks.com/blog/ai-governance-data-ai-summit-2026-whats-new-unity-ai-gateway) — Managed Omnigent on Databricks + AI ガバナンス
- [What's new with Unity Catalog (DAIS 2026)](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026)
- [Agent Bricks Supervisor Agent GA](https://www.databricks.com/blog/agent-bricks-supervisor-agent-now-ga-orchestrate-enterprise-agents)
- [Omnigent Docs: Custom Agents](https://omnigent.ai/docs/use/custom-agents)
- [Omnigent Docs: Contextual Policies](https://omnigent.ai/docs/policies/overview)
- [Omnigent Docs: MCP & Tools](https://omnigent.ai/docs/build/tools)
