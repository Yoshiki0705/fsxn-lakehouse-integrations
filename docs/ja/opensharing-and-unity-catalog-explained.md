🌐 [English](../en/opensharing-and-unity-catalog-explained.md) | **日本語**

# OpenSharing と Unity Catalog: 概念と検証メモ

オブジェクトストレージ（例: Amazon FSx for NetApp ONTAP の S3 Access Points）と
Databricks Unity Catalog の間で、オープンなデータ共有がどう動くのかを中立に整理します。
今できること、まだ発展途上のこと、そしてその理由を扱います。

> 本ドキュメントは概念の解説と一次情報の引用を目的とし、特定ベンダーを持ち上げたり
> 他と対立させたりするものではありません。可用性や提供時期は各プラットフォーム提供元が
> 管理します。最新状況は必ずリンク先ドキュメントで確認してください。

## 概要

NAS/オブジェクトストレージにファイルを置き、Databricks のような分析基盤で
**ガバナンス（リネージ・タグ・アクセス制御）付き**にそのデータを使いたい場合、
いくつかの経路があります。各経路は、データを**コピーするか**、**Unity Catalog の
ガバナンスが自動適用されるか**、そして**成熟度**の点で異なります。

本稿は、混同されやすい2つの仕組みに焦点を当てます。

- **ネイティブな Unity Catalog recipient** — Unity Catalog 自身が共有を取り込み、
  第一級のオブジェクトとしてガバナンスする方式。
- **notebook での「自作」recipient** — 自分のコードで共有データを読む方式（「任意の
  ツールで読む」モデル）。

## 背景: Delta Sharing と OpenSharing

**Delta Sharing** は組織・ツール間でデータを共有するためのオープンプロトコルです。
**OpenSharing** はその後継で、2026 年に Databricks が発表し Linux Foundation が
ホストします。非構造化の **Volumes**（短命の credential vending 経由）、**Tables**、
ML モデル、エージェントスキルへと共有対象を拡張しています。

- OpenSharing の発表: <https://www.databricks.com/blog/introducing-opensharing-next-evolution-delta-sharing-agentic-era>
- プロトコル仕様: <https://github.com/OpenSharing-IO/OpenSharing>
- Linux Foundation プレスリリース: <https://www.linuxfoundation.org/press/linux-foundation-announces-opensharing-project-to-standardize-ai-asset-and-data-exchange>

「credential vending」とは、共有サーバーが**短命でスコープ限定のクラウド認証情報**
（例: AWS STS）を発行し、消費側が**オブジェクトストレージから直接**データを読む
仕組みです。大量コピーは不要です。

## 主要な役割と共有モデル

混乱の大半は次の2用語に由来します。

- **Provider（共有元）** — データを保有し、**共有サーバー**を運用（または内蔵利用）
  する側。プロトコルはオープンなので、誰でも provider サーバーを実装できます。
- **Recipient** — 2つの意味があります。(1) provider が作る「誰に共有するか」を表す
  *recipient オブジェクト*（bearer token を伴う）、(2) 共有データを読む*消費側*。

Databricks は2つの共有モデルを文書化しています。

- **Databricks-to-Databricks** — 両側が Unity Catalog を使用。recipient のメタストアに
  provider オブジェクトが自動生成され、両側にガバナンスが適用されます。
  [recipient 向け provider 管理](https://docs.databricks.com/aws/en/delta-sharing/manage-provider)を参照。
- **Databricks-to-Open** — provider は Databricks/UC で、recipient は**任意のツール**
  （非 Databricks を含む）。credential file や activation URL を使います。
  [共有データへのアクセス（recipient 向け）](https://docs.databricks.com/gcp/en/delta-sharing/recipient)
  と[共有データの読み取り（open sharing）](https://docs.databricks.com/en/data-sharing/read-data-open.html)を参照。

中核の流れ（credential vending）は次のとおりです。

```mermaid
flowchart LR
  R["Recipient (consumer)"] -->|"1. authenticate (bearer token)"| SV["Sharing server (provider side)"]
  SV -->|"2. metadata + short-lived scoped credentials"| R
  R -->|"3. read data directly"| OS["Object storage (e.g., FSx for ONTAP S3 AP)"]
```

> 注: Unity Catalog には、**外部エンジンへ**認証情報を vend する別機能もあります（逆方向）。
> これは OpenSharing とは別物です。
> [UC credential vending](https://docs.databricks.com/gcp/en/external-access/credential-vending)を参照。

## Unity Catalog と FSx for ONTAP S3 Access Points

自然な疑問として、「Unity Catalog は FSx for ONTAP S3 Access Point を直接
**External Location** として登録し、その上にガバナンス付きテーブルを作れるか
（ゼロコピー）？」があります。

本検証時点では、**この直接経路は動作しません**。Unity Catalog がストレージ認証用の
IAM ロールを引き受ける際に生成する**セッションポリシー**が、標準の S3 バケット ARN は
認識する一方で、**S3 Access Point ARN**を認識しないためです。トップレベルの一覧取得や
明示パスの読み取りは動くように見えても、サブディレクトリ一覧・`CREATE TABLE`・書き込みは
失敗します。Databricks サポートは、S3 Access Points が UC External Location の
サポート対象ストレージではないことを確認しています。観測挙動の詳細は本リポジトリの
[integrations/databricks](../../integrations/databricks/)を参照してください。

OpenSharing はこの制約を回避します。**External Location を使わず**、サーバーがスコープ
限定の認証情報を vend し、消費側がオブジェクトストレージを直接読むためです。残る論点は、
Unity Catalog がそのような共有を*どう取り込む*かです。

## データ取り込みの2方式（ネイティブ recipient vs 自作 recipient）

```mermaid
flowchart TB
  OS["FSx for ONTAP S3 AP"]
  OS --> UC["Native Unity Catalog recipient: Foreign Volume/Table"]
  OS --> NB["DIY recipient in a notebook: requests + boto3/Spark"]
  UC --> G1["Governance applied automatically (lineage, tags, ACL)"]
  NB --> G2["Governance not automatic — land in a UC table to regain it"]
```

**1. ネイティブな Unity Catalog recipient（マネージド・ガバナンス付き）。** Unity Catalog
が recipient として振る舞い、共有された Volumes/Tables をガバナンス付きオブジェクト
（リネージ・タグ・アクセス制御）として提供します。Databricks-to-Databricks、および
open-provider の **Tables** については recipient 機能が既に存在します。**非 Databricks
provider の非構造化 Volumes**（FSx for ONTAP S3 Access Point のケース）をネイティブな
ガバナンス付きオブジェクトとして取り込むのは新しい領域です。Databricks は
ハイブリッド/オンプレストレージを OpenSharing で接続する **Storage Ecosystem** を発表して
います（[Storage Ecosystem の発表](https://www.databricks.com/blog/announcing-databricks-storage-ecosystem-governing-enterprise-data-estate-wherever-it-lives)）。
対応スコープと可用性は Databricks に確認してください。

**2. notebook での「自作」recipient（任意のツール）。** Databricks-to-Open モデルでは
recipient は任意のツールで構いません。**Databricks notebook**（Jupyter notebook に似た、
セル単位で対話実行する Databricks ホストのコード環境。
[Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/)参照）から共有
サーバーを呼び、認証情報を受け取り、`boto3`/Spark でデータを読めます。**特別な
「OpenSharing notebook」は存在しません**。単に自分で書く recipient コードです。
トレードオフとして、自作読み取りには Unity Catalog のガバナンスが**自動適用されません**。
ガバナンスを効かせたい場合は、読んだデータを UC マネージドテーブルへ格納します。

## 補足パターン: ファイルプロトコル（NFS/SMB）ストレージ向けの自己管理 provider ブリッジ（設計例）

ストレージをオブジェクトインターフェースではなく**ファイルプロトコル（NFS/SMB）**で
アクセスする場合、オブジェクトストレージ認証情報を vend する代わりに、**自分で運用する
provider** がファイルを NFS/SMB で読み、その実体を HTTPS で配信する構成も考えられます。
これは**設計例（illustrative）であり、検証済みでも製品化された経路でもありません**。
とくに、ネイティブな Unity Catalog recipient が自己ホストの URL を受理するかは
**未検証・仕様外**です（自作 recipient なら成立し得ます）。可用性やネイティブ対応可否は
Databricks に確認してください。

この構成は役割の異なる2層に分かれます。

- **制御面** — OpenSharing API（認証・メタデータ・ルーティング）。軽量でイベント駆動。
- **データ面ブリッジ** — ストレージを NFS/SMB でマウントし、ファイル実体を HTTPS で
  ストリーム配信する常駐コンポーネント。

```mermaid
flowchart LR
  C["Consumer (notebook / any tool)"]
  CP["Control plane: sharing API - auth, metadata (e.g., Lambda + Function URL)"]
  DP["Data-plane bridge: mounts NFS/SMB, streams over HTTPS (e.g., ECS/EC2 behind ALB/NLB)"]
  FS["FSx for ONTAP (NFS / SMB)"]
  C -->|"1. HTTPS 443 + bearer token"| CP
  CP -->|"2. metadata + time-limited download URL"| C
  C -->|"3. HTTPS 443 byte stream"| DP
  DP -->|"4. NFS 2049 / SMB 445"| FS
```

データの流れ:
1. 消費側が制御面に認証（HTTPS 443・bearer token）。
2. 制御面がメタデータと、データ面ブリッジを指す時間制限付きダウンロード URL を返す。
3. 消費側がデータ面ブリッジからファイル実体を HTTPS(443) で取得。
4. データ面ブリッジがストレージを NFS(2049)/SMB(445) で読み、ストリーム返却。

コンピュートの選択（役割別）:

| 役割 | AWS の選択肢 | 理由 |
|---|---|---|
| 制御面（認証・メタデータ・ルーティング） | Lambda + Function URL | 軽量・イベント駆動。本リポジトリのリファレンスサーバーが該当 |
| データ面ブリッジ（マネージド） | ECS on Fargate | サーバー運用が軽い。特権 kernel マウント不可のため userspace の NFS/SMB クライアント実装が前提 |
| データ面ブリッジ（高スループット・大容量） | EC2 / ECS on EC2 | host で `mount -t nfs`/`cifs` 可・高帯域・実行時間無制限 |
| データ面には不向き | Lambda | 15 分上限・応答サイズ上限・任意 NFS マウント不可 |

開けるポート:

| 方向 | ポート | 用途 |
|---|---|---|
| 消費側 → provider エンドポイント | TCP 443（HTTPS/TLS） | 共有 API とバイトストリーム |
| データ面ブリッジ → ストレージ | TCP 2049（+ NFSv3 は portmapper 111） | NFS |
| データ面ブリッジ → ストレージ | TCP 445 | SMB |

考慮事項:
- **自己運用**: パッチ・スケール・HA（マルチ AZ + ALB/NLB）・常駐コストは運用側の責任。
- **データ面がバイト経路上に入る**（帯域・コスト・レイテンシ・単一障害点）。credential
  vending（消費側がストレージを直読み）とは性質が異なる。ブリッジはステートレスにして
  水平スケール・マルチ AZ で冗長化する。
- **SMB + Active Directory**: ブリッジはサービスアカウントで認証（Kerberos/NTLM）。ストレージ側の
  export policy（NFS）/ share ACL（SMB）でブリッジを許可する。ファイル ACL を recipient の
  ID に対応づける（permission-aware）のは追加設計であり、権限不明時は既定で拒否する。
- **認証**: 公開する場合も TLS + bearer token（必要に応じて mTLS）で保護し、非認証の
  エンドポイントは公開しない。私設接続なら PrivateLink / NCC を優先。

## 本リポジトリの独立検証

オープンソースのリファレンスサーバー（本リポジトリ）と決定論的な実行により、
FSx for ONTAP S3 Access Points で以下を観測しました。

- credential vending がスコープ限定・短命の STS 認証情報を発行。**11 のファイル形式**を
  読み取り成功。**prefix 分離**が機能（あるボリューム用の認証情報では別ボリュームを読めない）。
  presigned URL は HTTP 200。
- Databricks **serverless** コンピュートから: 独自の公開エンドポイント（共有サーバーの
  URL）へは既定で**到達できません**（serverless の egress は制限され、egress ポリシーが
  「Full」でも Network Connectivity Configuration が必要）。一方 AWS S3 / S3 Access Point
  へは managed VPC endpoint 経由で**到達可能**で、vend された認証情報を使って notebook が
  S3 Access Point 上のオブジェクトを読み取れました（約 250 KB の parquet）。

本リポジトリで未検証（プラットフォーム機能に依存）: 非 Databricks の Volumes provider に対する
**ネイティブな Unity Catalog recipient**。再現可能なサーバーと手順は
[integrations/opensharing-server](../../integrations/opensharing-server/)にあります。

## 現時点の選び方

- **今すぐガバナンス付き分析が必要** → 標準の S3 バケットへデータをステージング（例:
  AWS DataSync、または FPolicy → Lambda パイプライン）し、そのバケットを Unity Catalog に
  登録。コピーは発生しますが完全なガバナンスが適用されます。
- **完全な UC ガバナンス無しでゼロコピー読み取りが必要** → S3 Access Point を直接読む
  （Athena、または vend された認証情報で notebook の自作 recipient）。
- **ゼロコピー*かつ*ネイティブな UC ガバナンスが欲しい** → ネイティブ recipient /
  Storage Ecosystem の動向を追い、可用性を Databricks に確認。
- **ストレージをファイルプロトコル（NFS/SMB）でしか出せない** → 上記の自己管理 provider
  ブリッジ（設計例）を検討。ただし運用責任と、ネイティブ UC 取り込みが未検証である点に留意。

各選択肢は異なる文脈に適します。ガバナンス・鮮度・コストの要件に基づいて選んでください。

## FAQ

- **ストレージ側が provider を自分で実装できますか？** はい — プロトコルはオープンで、
  本リポジトリには動作するリファレンス provider サーバーが含まれます。ストレージ側だけで
  実装できないのは、Unity Catalog の*recipient 側*の挙動（サードパーティ共有をネイティブ
  オブジェクトとしてガバナンスする部分）で、これは Databricks プラットフォームの機能です。
- **「OpenSharing notebook」は特別な製品ですか？** いいえ。Databricks notebook（Jupyter に
  似た環境）の中に recipient コードを書くことを指します。任意のツールで可能です。
- **credential vending は Unity Catalog の credential vending と同じ？** いいえ。OpenSharing の
  vending は*他者へ*データを共有するもの、
  [UC credential vending](https://docs.databricks.com/gcp/en/external-access/credential-vending)は
  外部エンジンが*UC マネージド*データを読むためのものです。
- **Tables と Volumes は同じ扱い？** open-provider の Table 取り込みは確立済み、非構造化の
  **Volumes** のネイティブ取り込みが新しい領域です。

## 参考資料

- OpenSharing の発表（Databricks）: <https://www.databricks.com/blog/introducing-opensharing-next-evolution-delta-sharing-agentic-era>
- Storage Ecosystem の発表（Databricks）: <https://www.databricks.com/blog/announcing-databricks-storage-ecosystem-governing-enterprise-data-estate-wherever-it-lives>
- OpenSharing 仕様: <https://github.com/OpenSharing-IO/OpenSharing>
- Linux Foundation プレスリリース: <https://www.linuxfoundation.org/press/linux-foundation-announces-opensharing-project-to-standardize-ai-asset-and-data-exchange>
- 共有データへのアクセス（recipient 向け）: <https://docs.databricks.com/gcp/en/delta-sharing/recipient>
- recipient 向け provider 管理: <https://docs.databricks.com/aws/en/delta-sharing/manage-provider>
- 共有データの読み取り（open sharing）: <https://docs.databricks.com/en/data-sharing/read-data-open.html>
- Unity Catalog credential vending: <https://docs.databricks.com/gcp/en/external-access/credential-vending>
- Databricks notebooks: <https://docs.databricks.com/aws/en/notebooks/>
- 本リポジトリ — リファレンスサーバー: [integrations/opensharing-server](../../integrations/opensharing-server/)
- 本リポジトリ — Databricks 統合メモ: [integrations/databricks](../../integrations/databricks/)
