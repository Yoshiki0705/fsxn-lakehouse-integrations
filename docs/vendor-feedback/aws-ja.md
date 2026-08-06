🌐 [English](./aws.md) | **日本語**

# フィードバック: AWS

対象: Amazon FSx for NetApp ONTAP S3 Access Points と、それを経由して読み取る AWS
分析サービス。2026-08-06 時点。

## サマリー

読み取りパスは良好に動作し、Athena、Glue、EMR Serverless、Redshift Spectrum、DuckDB、
Bedrock で検証済みです。Athena + Glue Data Catalog 経由の Iceberg 読み取り**および
書き込み**はエンドツーエンドで検証できており、これは本リポジトリの想定より良い結果でした。
カタログがコミットのポインタを保持することで、オブジェクトストア側に欠けている
プリミティブを完全に回避しています。

2つの差分が他より際立っていますが、それは機能が欠けていること自体が理由ではありません。
**状態を残す形で失敗する**ためです。設計で回避すべき制約と、事後に検出しなければならない
ハザードの違いがここにあります。

| 優先度 | 項目 | この順位の理由 |
|:---:|---|---|
| 1 | [暗号化タイプが `aws:fsx` として報告される](#1-暗号化タイプ-awsfsx-が書き込み着地後にクライアントのチェックサム検証を壊す) | 静かな部分書き込み。クライアントは失敗を報告するが、オブジェクトは Access Point 上に無傷で残る |
| 2 | [条件付き書き込みが 501 を返す](#2-条件付き書き込みが-http-501-を返す) | Delta と Hudi を阻害し、失敗した試行がデータファイルを取り残す |
| 3 | [S3 Event Notifications が発行されない](#3-s3-event-notifications-が発行されない) | イベント駆動の取り込みが成立しない。回避策は運用負荷が重い |
| 4 | [SnapMirror S3 が無効](#4-fsx-for-ontap-では-snapmirror-s3-が無効化されている) | ONTAP には機能が存在するが FSx 経由では到達できない |
| 5 | [EMR Serverless の Iceberg 書き込みが失敗](#5-emr-serverless-は-access-point-へ-iceberg-を書き込めない) | 同一ストレージ上で Athena は成功するため、対処可能な問題 |
| 6 | [S3 Tables での Lake Formation 列レベル権限](#6-s3-tables-フェデレーテッドカタログで-lake-formation-の列レベル権限が使えない) | それ以外は綺麗な経路における唯一の上限 |
| 7 | [`HeadBucket` はヘルスシグナルにならない](#7-データ操作が失敗する状況でも-headbucket-は成功する) | 切り分けを誤ったレイヤーへ誘導するドキュメントの欠落 |

---

## 1. 暗号化タイプ `aws:fsx` が書き込み着地後にクライアントのチェックサム検証を壊す

**計測** 2026-08-06。
[エビデンス](../../verification-pack/snowflake/evidence/2026-08-06/evidence-record.yaml) ·
[BLK-009](../ja/blocker-tracker.md)

FSx for ONTAP はサーバーサイド暗号化を `aws:fsx` として報告します。アップロード後の
チェックサムを返却された暗号化タイプに対して検証するクライアントは、これが
`AWS_SSE_S3` でも `AWS_SSE_KMS` でもないため認識できず、操作を失敗させます。

書き込み自体は成功します。Snowflake `COPY INTO @stage` は 479 ms で以下により失敗しました。

```
Remote upload failed checksum validation. Ensure the destination stage or COPY
command was configured with the storage bucket's default encryption type, such
as AWS_SSE_KMS.
```

それにもかかわらずオブジェクトは Access Point 上に存在していました。25 バイト、
gzip として妥当、内容も正しく、`ServerSideEncryption: aws:fsx`、`StorageClass: FSX_ONTAP`。

ステージに `ENCRYPTION=(TYPE='AWS_SSE_S3')` を設定しても解決しません。即時失敗が
ハングに変わるだけです。2分54秒でキャンセル、何も書かれませんでした。

**これを1位とした理由。** 失敗したステートメントを見た呼び出し側は、何も書かれなかったと
考えるのが自然です。しかし実際には完全なオブジェクトが残ります。Access Point を
バックエンドとするステージへアンロードを試したことがある人は、認識していない孤児
オブジェクトを抱えています。これは機能の欠落ではなく、失敗パスにおける正しさの問題です。

**解消に必要なこと**: S3 クライアントが既に受け付ける暗号化タイプを報告するか、
クライアントベンダーが受理集合に追加できるよう `aws:fsx` を十分に目立つ形で
ドキュメント化すること。後者は全クライアントとの調整が必要ですが、前者は不要です。

---

## 2. 条件付き書き込みが HTTP 501 を返す

**確認** 2026-05-22、製品レベルの制約として。
[BLK-002](../ja/blocker-tracker.md)

`If-None-Match` が `501 NotImplemented` を返します。Amazon S3 は 2024年8月から条件付き
書き込みに対応しているため、これは新規の要望ではなくパリティの差分です。

### 実際に阻害される範囲（実測）

範囲は本リポジトリが以前記述していたより狭く、この訂正は旧版を読んだ人にとって重要です。

| フォーマット / エンジン | 書き込み | 理由 |
|---|:---:|---|
| Athena + Glue Data Catalog 経由の Iceberg | ✅ 動作 | Glue が現行メタデータのポインタを保持するため、コミットはオブジェクトストアではなく Glue 内の条件付き更新になる。CREATE、INSERT、UPDATE、DELETE、タイムトラベル、`OPTIMIZE`、`VACUUM`、同時2コミットがすべて成功（[エビデンス](../../verification-pack/athena-iceberg/evidence/2026-08-06/evidence-record.yaml)） |
| Delta Lake（エンジン問わず） | ❌ 失敗 | コミットログがオブジェクトストア上の `_delta_log/` にあるため、コミットが欠落プリミティブを必要とする |
| Hudi | ❓ 未テスト | タイムラインが同じアトミックリネームを要求する。これは実測ではなく推論（UNV-023） |

Delta の失敗、delta-rs 1.2.1 での原文（2026-05-23）:

```
Generic S3 error: Error performing PUT
.../delta-lake/write_test/_delta_log/00000000000000000000.json
- Server returned non-2xx status code: 501 Not Implemented
```

### 副作用が主作用と同程度に重要

Delta は Parquet データファイルを先に書き、コミットを後に行います。コミットが 501 に
当たると、**データファイルは残ります。** 検証用 Access Point で 2026-08-06 に観測:
`_delta_log` のない Delta データファイルを持つプレフィックスが4つ、うち1つには1分間隔で
書かれた3ファイル。リトライがそれぞれ残留物を作っています。

これは項目1と同じ残留物の形で、原因は無関係です。同じ運用上の問題に至る独立した経路が
2つあることは、機能差分と並んで失敗パスにも注意を払う価値があることを示しています。

**解消に必要なこと**: S3 ネイティブとのパリティとして `If-None-Match` を実装すること。

---

## 3. S3 Event Notifications が発行されない

**確認** 2026-05-22。[BLK-003](../ja/blocker-tracker.md)

`s3:ObjectCreated` および関連イベントが発行されません。これにより Snowpipe 自動取り込み、
Databricks Auto Loader 通知モード、Access Point から直接読み取る EventBridge 起動の
パイプラインが成立しません。

回避策は存在し、部分的に検証済みです。Lambda ポーリング → SNS → Snowpipe は両側で
検証しました。AWS 側（実装中に6件の不具合を発見・修正）と Snowflake 側で、publish から
約 0.5 秒後に取り込まれています
（[エビデンス](../../verification-pack/snowpipe-pattern-a/evidence/2026-08-06/snowflake-side-verification.yaml)）。

**トレードオフを公平に述べると**: FPolicy → Lambda は技術的には妥当ですが、実際の運用
負荷を伴います。Lambda の同時実行上限、DLQ の扱い、バックプレッシャーです。DataSync の
`rate(5 minutes)` スケジュールで要件を満たせるなら、そちらが単純な選択です。これは
作業を止めるブロッカーではなく、単純なアーキテクチャを選べなくするブロッカーです。

---

## 4. FSx for ONTAP では SnapMirror S3 が無効化されている

**確認** 2026-05-26、ONTAP 9.17.1P6 で CLI と REST API の双方から。
[エビデンス](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml) ·
[BLK-004](../ja/blocker-tracker.md) · [ADR-002](../adr/ADR-002-snapmirror-s3-unavailability.md)

| 試行 | 結果 |
|---|---|
| `snapmirror object-store show` | `"object-store" is not a recognized command` — admin / advanced / diagnostic のいずれの権限レベルでも同じ |
| `GET /api/cloud/targets` | `{"error":{"message":"not authorized for that command","code":"6"}}` |
| `snapmirror policy show -type continuous` | `Continuous` ポリシーは "Policy for S3 bucket mirroring" というコメント付きで存在するが、参照できない |

ONTAP の S3 プロトコル層自体は機能しています。新規 SVM 上で
`vserver object-store-server create` と `bucket create` はいずれも成功しました。
したがってこれは ONTAP のバージョン制約ではなく、マネージドサービスの制限です。

**移行計画にとっての意味**: オンプレミス ONTAP は 9.10.1+ で SnapMirror S3 に対応して
います。オンプレミスの機能を前提に書かれた移行計画は、これが動作すると想定します。
FSx for ONTAP で検証済みの同期手段は AWS DataSync（NFS → S3）のみで、ONTAP ネイティブの
レプリケーション効率は失われます。

**ドキュメントに関する所見**: `docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-snapmirror.html`
は FSx for ONTAP のトップページへリダイレクトされ、scheduled-replication のページは
ボリュームレベルの SnapMirror のみを扱っています。「無い」ことが「無い」と記載されて
いないため、試して初めて分かります。

---

## 5. EMR Serverless は Access Point へ Iceberg を書き込めない

**計測** 2026-05-24。
[エビデンス](../../verification-pack/iceberg/evidence/2026-05-24/evidence-record.yaml)

```
java.lang.NullPointerException: Cannot invoke
"org.apache.iceberg.TableMetadata.metadataFileLocation()"
because "metadata" is null
```

失敗は Iceberg のメタデータ書き込みとコミット検証で発生しており、データファイルの
書き込みではありません。Glue Catalog のデータベース作成は成功しています。

**これは対処可能であることが明確になり、それが新しい情報です。** これを記録した時点では、
Iceberg 書き込みは Delta と同じ欠落プリミティブによって阻害されていると想定していました。
2026-08-06 の Athena Iceberg 実行がそれを否定しました。同じテーブルフォーマットが、同じ
Access Point 上で、フルライフサイクルを完了しています。Athena の Iceberg 実装は、ここで
失敗する S3FileIO のコードパスを通りません。

つまり制約はストレージではなく、S3FileIO が Access Point エイリアスをどう解決するかに
あります。Apache Iceberg 側にも記載していますが（[Iceberg のページ](./apache-iceberg-ja.md)）、
そのランタイムを提供・構成しているのは EMR Serverless であるため、修正の置き場所は
2つありえます。

---

## 6. S3 Tables フェデレーテッドカタログで Lake Formation の列レベル権限が使えない

**確認** 2026-05。[BLK-008](../ja/blocker-tracker.md)

テーブルレベルの許可は機能します。列レベルのマスキングは機能しません。

回避策は、列レベル制御が必要なテーブルを汎用 S3 バケット上の通常の Glue Catalog テーブルに
配置することです。そこでは Lake Formation の列マスクが通常どおり適用されます。これは
動作しますが、テーブルの所在によってガバナンスモデルが変わることを意味し、カタログ
レイアウト全体を通して持ち回る設計上の制約になります。

Glue フェデレーテッドカタログ経由の Athena は S3 Tables への唯一の設定不要な SQL 経路で、
2秒未満のクエリでテーブルレベルの Lake Formation ガバナンスを適用します。列レベルの
差分は、それ以外は綺麗な経路における唯一の上限です。

---

## 7. データ操作が失敗する状況でも `HeadBucket` は成功する

複数の切り分けセッションで観測。
[ネットワーキング考慮事項](../ja/fsx-ontap-s3ap-networking.md)を参照。

`HeadBucket` はファイルシステムを経由せずに S3 層で Access Point の存在を検証するため、
`ListObjectsV2`、`GetObject`、`PutObject` がすべて `AccessDenied` を返すかタイムアウトする
状況でも 200 を返します。

これが起きる状況は2つあります。

| 状況 | 実際の原因 |
|---|---|
| SVM に AD 参加用の DNS サーバーが設定されており、それが到達不能 | その SVM 上の全 Access Point がタイムアウトする。S3 リクエストパスは SVM のネームサービススタックを経由し、これがドメインコントローラーへ到達するために DNS を必要とする。ボリュームのセキュリティスタイル、エクスポートポリシー、Access Point のライフサイクル状態はいずれも無関係 |
| VPC 内のコンピュートが S3 Gateway Endpoint 経由で Internet Origin の Access Point に到達しようとする | エイリアスは `s3-r-w.<region>.amazonaws.com` に解決されるが、これは Gateway Endpoint が使うプレフィックスリストに含まれない場合がある。トラフィックが捕捉され、ルーティングされない |

どちらの場合も、`HeadBucket` が正常で IAM も正しいという状況が、調査を IAM と Access Point
ポリシーの層へ誘導します。そこに問題はありません。

**あると助かること**: `HeadBucket` がファイルシステムパスを行使しないことを明記し、
接続確認には `ListObjectsV2 --max-keys 1` を推奨すること。ドキュメントの変更で済み、
方向を誤ったデバッグを大幅に減らせます。

---

## 本リポジトリ自身の記録に対する訂正

うち2件は問題として AWS に提起したものであり、未訂正のまま残すべきではないため
ここに記載します。

| 以前の主張 | 現在の状態 |
|---|---|
| ListObjectsV2 はネイティブ S3 の 30〜80 倍遅い | **取り下げ。** 2026-08-05 に再測定し、10〜5,000 オブジェクトで 0.9〜1.4 倍、フラット構成もネスト構成も同様で、いずれも当初の性能目標の内側だった。30〜80 倍は再現せず、出所も特定できなかった。単一ディレクトリで 5,000 を超える場合は未測定（UNV-025）であり、ONTAP はディレクトリエントリをメモリ上でソートするため、ファイル集約は妥当な実践として残る。ただし以前示した理由によるものではない。[エビデンス](../../verification-pack/s3ap-list-latency/evidence/2026-08-05/benchmark-result.yaml) |
| Iceberg の同時書き込みはテーブル破損のリスクがある | **推論として取り下げ。** Athena の同時2コミットは正しい行数を返し、更新の喪失もなかった。2ライターは同時実行の上限を示すものではないが、以前示唆したような categorical なリスクではない |
| Delta 書き込みが阻害されるため、全テーブルフォーマットの書き込みが阻害される | **訂正。** Athena + Glue 経由の Iceberg は動作する。決め手はストレージではなく、コミットのポインタがどこにあるか |

## 検証済みの結果がカバーしていない範囲

肯定的な結果を過大に読まないために記載します。

| 未確認事項 | 解釈への影響 |
|---|---|
| Athena Iceberg の実行は1桁の行数だった | 現実的な規模でのマニフェスト増加、コンパクションコスト、パーティション進化が未測定（UNV-021） |
| Athena 同時実行の実行はキャッシュに収まる規模だった | 25/25 のクエリが成功しフルスキャンは約2倍に劣化したが、128 MBps でプロビジョニングされたファイルシステムに対して集計約 389 MB/s が流れている。キャッシュが大きく効いている。同時実行が25までは失敗要因にならないという証拠として読み、スループットモデルとしては読まないこと（UNV-022） |
| `SINGLE_AZ_1` の 128 MBps のみでテストした | Multi-AZ の挙動と上位スループット階層は未測定。Multi-AZ では書き込みがネットワーク帯域を2倍消費する点に注意 |
