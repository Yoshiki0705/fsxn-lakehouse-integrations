🌐 [English](./netapp.md) | **日本語**

# フィードバック: NetApp

対象: Amazon FSx for NetApp ONTAP 経由で観測された ONTAP の挙動のうち、AWS サービス層
ではなく ONTAP 自体に起因するもの。2026-08-06 時点。

## 位置づけ

本プロジェクトが見つけた制約の多くは AWS のマネージドサービス層か分析エンジンの実装に
あり、それらは[AWS のページ](./aws-ja.md)およびエンジン別のページに記録しています。
本ページは、ONTAP 自体が該当レイヤーとなる3件を扱います。

うち1件は、目につく場所に一切ドキュメント化されていない実際の設計上の考慮事項で、
本プロジェクトは方向を誤った切り分けに1セッションを費やしました。残る2件は ONTAP の
機能と FSx の公開範囲が乖離しているケースで、公開範囲の判断は NetApp のものではない
にせよ、NetApp が知っておく価値があります。

| # | 所見 | レイヤー | 重大度 |
|:---:|---|---|---|
| 1 | [ネームサービススタックが S3 データパス上にある](#1-ネームサービススタックが-s3-データパス上にある) | ONTAP | 高 — AD 障害がストレージ障害として現れる |
| 2 | [SVM あたり object-store サーバー1つの制約が併存を妨げる](#2-svm-あたり-object-store-サーバー1つの制約が-access-points-との併存を妨げる) | ONTAP | 中 — 構造的であり設計で回避する必要がある |
| 3 | [SnapMirror S3 は ONTAP に存在するが FSx 経由では到達できない](#3-snapmirror-s3-は-ontap-に存在するが-fsx-for-ontap-経由では到達できない) | ONTAP の機能、FSx の公開範囲 | 中 — 移行計画に影響する |

---

## 1. ネームサービススタックが S3 データパス上にある

**本ページで最も有用な所見であり、最もドキュメント化されていないもの。**

SVM に Active Directory 参加用の DNS サーバーが設定されており、その DNS サーバーが
到達不能になると、**その SVM 上の全 S3 Access Point がタイムアウトします。** これは
以下の条件下でも発生します。

- Access Point のボリュームが UNIX セキュリティスタイルである
- NFS エクスポートポリシーが全アクセスを許可している
- ユーザー設定の FPolicy が無効である
- Access Point のライフサイクル状態が `AVAILABLE` である

### 理解している機構

S3 リクエストパスは SVM のネームサービススタックを経由します。CIFS または AD が設定されて
いる場合、ONTAP は UNIX ↔ Windows のユーザーマッピング解決を試み、その解決には
ドメインコントローラーとの DNS 通信が必要です。Windows のアイデンティティに一切
触れない S3 リクエストであっても、SVM が AD 参加していることの代償を払います。

```
S3 API リクエスト
  → Access Point バックエンド
    → SVM ファイルシステムアクセス
      → ONTAP ネームサービススタック (ns-switch: files, dns)
        → 到達不能なドメインコントローラーへの DNS クエリ
          → タイムアウト
```

### 目立つ形でドキュメント化する価値がある理由

失敗の症状が原因から遠い場所を指します。`HeadBucket` はファイルシステムを経由しないため
200 を返します。Access Point は `AVAILABLE` を報告します。IAM ポリシーは妥当です。
ボリュームの権限は緩いままです。エンジニアが最初に確認するすべての項目が正常を返し、
実際の原因は S3 のドキュメントが一切触れていないコードパス上の AD 依存です。

本プロジェクトはこれに、IAM と Access Point ポリシーの層から始まってしばらくそこに
留まる切り分けセッションを費やしました。

**ドキュメント化の提案**: AD 参加した SVM が S3 データパスに DNS 依存を持ち込むこと、
そしてこの依存がボリュームのセキュリティスタイルにかかわらず SVM 上の全 Access Point に
及ぶことを記載すること。1段落の注記で、この誤誘導は完全に防げます。

**機能する切り分け**: `HeadBucket` ではなく `ListObjectsV2 --max-keys 1` で確認し、
発見済みドメインコントローラーを見ること。

```
GET /api/protocols/cifs/domains?svm.name=<svm>&fields=discovered_servers
```

AD 参加した SVM で `discovered_servers` が空であることがシグナルです。

**述べておく価値のある設計上の含意**: あるボリュームが S3 と NFS からのみアクセスされる
なら、その SVM を AD に参加させないことでこの依存を除去できます。これは実際の
トレードオフを伴う実際のアーキテクチャ選択であり、障害対応中に発見されるものではなく
ドキュメント化された選択であるべきです。

---

## 2. SVM あたり object-store サーバー1つの制約が Access Points との併存を妨げる

**計測** 2026-05-26。
[エビデンス](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml)

S3 Access Points が既にある SVM 上でネイティブ ONTAP S3 object-store サーバーを作成すると
失敗します。

```
vserver object-store-server create -vserver verification-svm \
  -object-store-server snapmirror-s3-test -is-http-enabled true

→ Only one object store server is supported per Vserver
```

Access Points は `vserver object-store-server show` に表示されない内部 object-store
サーバーを設置します。したがって運用者の視点では SVM に object-store サーバーは存在せず、
それでも create は失敗します。

逆方向も失敗し、AWS 側からは次のように報告されます。

> Amazon FSx is unable to create an S3 access point because of an existing ONTAP
> object storage server on SVM...

### これが重要な理由

これはタイミングや順序の問題ではなく構造的な競合です。リトライは効きません。設計上の
帰結として、SVM は Access Point 用か ネイティブ ONTAP S3 用のいずれかになり、誤って
選ぶと新しい SVM を作ってボリュームを移動することになります。

**変更の提案**: Access Points が設置する内部サーバーを `vserver object-store-server show`
に表示すること。読み取り専用でもよく、システム管理であることを明示すれば十分です。
現在の挙動は、運用者が競合するリソースを確認し、存在しないことを確認した上で、create で
競合に当たるというものです。リソースを可視化すれば、分かりにくい失敗が明白な失敗に
変わります。

---

## 3. SnapMirror S3 は ONTAP に存在するが FSx for ONTAP 経由では到達できない

**計測** 2026-05-26、ONTAP 9.17.1P6 で。
[エビデンス](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml) ·
[ADR-002](../adr/ADR-002-snapmirror-s3-unavailability.md)

公開範囲の判断は AWS 側に属するため、[AWS のページ](./aws-ja.md)にもその旨で記録して
います。ここに掲載するのは、ONTAP のドキュメントと FSx の実際との乖離が、NetApp
ドキュメントの読まれ方に影響するためです。

| 試行 | 結果 |
|---|---|
| `snapmirror object-store show` | `"object-store" is not a recognized command`。admin / advanced / diagnostic のいずれの権限でも同じ |
| `GET /api/cloud/targets` | `not authorized for that command` |
| `snapmirror policy show -type continuous` | `Continuous` ポリシーが "Policy for S3 bucket mirroring" というコメント付きで存在。存在するが使用不能 |
| `storage aggregate object-store config show` | 空。FabricPool のクラウド階層は未設定 |

S3 プロトコル層は動作します。新規 SVM 上で `vserver object-store-server create` と
`bucket create` はいずれも成功しました（最小バケットサイズは約 100 GB、ボリューム側の
制約）。したがって制限は SnapMirror S3 のコントロールプレーンに限定されています。

### ドキュメントの乖離

NetApp のドキュメントは、ONTAP について正確に次のように記述しています。

> Beginning with ONTAP 9.10.1, you can protect buckets in ONTAP S3 object stores
> using SnapMirror mirroring and backup functionality. Unlike standard SnapMirror,
> SnapMirror S3 enables mirroring and backups to non-NetApp destinations like AWS S3.

FSx for ONTAP の導入を計画しながら読むと、この文は到達できない機能を示唆します。読者は
NetApp のドキュメントから FSx 版がコントロールプレーンを遮断していることを知る術がなく、
AWS のドキュメントからも知る術がありません。FSx の SnapMirror S3 のドキュメント URL は
製品トップページへリダイレクトされます。

**変更の提案**: SnapMirror S3 のページに、FSx for ONTAP はこの機能を公開していないことを
示すプラットフォーム可用性の注記を追加すること。NetApp は ONTAP ドキュメントの他の箇所で
既にプラットフォーム別のサポート状況を区別しているため、新しい慣習ではなく既存の慣習に
沿った変更になります。

**実務上の影響**: オンプレミス ONTAP の機能を前提に書かれた移行計画は、FSx for ONTAP へ
移った後も SnapMirror S3 が使えると想定します。使えません。検証済みの同期手段は AWS
DataSync（NFS → S3）のみで、ONTAP ネイティブのレプリケーション効率は得られません。
ブロックレベルの増分転送も、重複排除の考慮もありません。

---

## 良好に動作している点（バランスのため記録）

これらは要望ではありません。差分と並べて可視化すべき結果です。

| 領域 | 結果 |
|---|---|
| ListObjectsV2 レイテンシ | 2026-08-05 に再測定し、10〜5,000 オブジェクトでネイティブ S3 の **0.9〜1.4 倍**。フラット構成もネスト構成も同様。本リポジトリは以前 30〜80 倍と公開していたが、再現せず取り下げた。元の主張が公開され読まれたため、訂正を記録している。単一ディレクトリで 5,000 を超える範囲は未測定（UNV-025）。[エビデンス](../../verification-pack/s3ap-list-latency/evidence/2026-08-05/benchmark-result.yaml) |
| 読み取り整合性 | 書き込み後の一覧整合性は全体を通して保たれた。失敗したテーブルフォーマットはいずれも欠落した書き込みプリミティブによるもので、整合性の異常によるものは一件もない |
| 同時負荷下の ONTAP キャッシング | 25 並列の Athena クエリが 128 MBps でプロビジョニングされたファイルシステムに対して集計約 389 MB/s を流し、25/25 が成功した。キャッシングが相当な仕事をしている。スループットの読み方に対する注意点として記載しているが、これ自体も実際の結果である。[エビデンス](../../verification-pack/athena-concurrency/evidence/2026-08-06/evidence-record.yaml) |
| マルチプロトコルアクセス | 同一ボリュームに対する NFS と S3 は、双方を行使したすべてのテストで干渉なく動作した |

## 本プロジェクトで ONTAP 側の知見が薄い領域

このフィードバックを実際より網羅的に読まれないよう記載します。

| 未確認事項 | 備考 |
|---|---|
| FlexCache と Access Points の組み合わせ | 考慮事項として文書化しているが未計測。[FlexCache/SnapMirror 考慮事項](../ja/s3ap-flexcache-snapmirror-considerations.md)を参照 |
| ONTAP 9.18.1 以降の挙動 | 現時点では検証不能（UNV-024） |
| 1ディレクトリあたり 5,000 を超えるオブジェクトの一覧 | 未計測（UNV-025）。ONTAP はディレクトリエントリをメモリ上でソートするため、実際のペナルティが現れる可能性が最も高いケース |
| Multi-AZ 構成 | 全計測が `SINGLE_AZ_1` の 128 MBps |
