🌐 [English](./snowflake.md) | **日本語**

# フィードバック: Snowflake

対象: Amazon FSx for NetApp ONTAP S3 Access Points に対する Snowflake の挙動。特記なき
場合 2026-08-06 の計測。
[エビデンス](../../verification-pack/snowflake/evidence/2026-08-06/evidence-record.yaml)

## サマリー

読み取りパスは、本リポジトリが扱うサードパーティプラットフォームの中で最も網羅的に
検証できています。1セッションで、Parquet、CSV、JSON、Avro、ORC のすべてを Access Point
バックエンドの外部ステージから読み取り、Snowpark UDF の `SnowflakeFile.open` がファイル
内容を返し、`BUILD_SCOPED_FILE_URL`、`PARSE_DOCUMENT`、`TO_FILE` がいずれも動作し、
ステージに対する `COPY INTO` から Managed Iceberg Table をエンドツーエンドで構築して
宛先バケット上に実際の Iceberg レイアウトを確認しました。

所見は3件です。1件目は失敗パスにおける実際の不具合。2件目はドキュメント化する価値のある
制約。3件目は本リポジトリが誤って公開した内容の訂正で、誤った説明は Snowflake ではなく
当方のものであるため含めています。

| # | 所見 | 重大度 |
|:---:|---|---|
| 1 | [アンロードがオブジェクト着地後にチェックサム検証で失敗する](#1-アンロードがオブジェクト着地後にチェックサム検証で失敗する) | **高** — 静かな孤児オブジェクト |
| 2 | [Dynamic Table が External Table を参照できない](#2-dynamic-table-が-external-table-を参照できない) | 低 — 明快なエラー、単純な回避策 |
| 3 | [訂正: 外部ステージは設計上読み取り専用ではない](#3-訂正-外部ステージは設計上読み取り専用ではない) | ドキュメント — Snowflake ではなく当方の誤り |

---

## 1. アンロードがオブジェクト着地後にチェックサム検証で失敗する

**計測** 2026-08-06。[BLK-009](../ja/blocker-tracker.md)

Access Point バックエンドの外部ステージに対する `COPY INTO @stage` は 479 ms で以下により
失敗します。

```
Remote upload failed checksum validation. Ensure the destination stage or COPY
command was configured with the storage bucket's default encryption type, such
as AWS_SSE_KMS.
```

**それにもかかわらずオブジェクトは書き込まれます。** 失敗後に Access Point 上で確認した
内容:

| 項目 | 値 |
|---|---|
| キー | `sfverify/formats/unload_probe_1/data_0_0_0.csv.gz` |
| サイズ | 25 バイト |
| gzip の整合性 | 妥当 |
| 内容 | SELECT した内容と一致 |
| `ServerSideEncryption` | `aws:fsx` |
| `StorageClass` | `FSX_ONTAP` |

### 根本原因

FSx for ONTAP はサーバーサイド暗号化を `aws:fsx` として報告し、これは `AWS_SSE_S3` でも
`AWS_SSE_KMS` でもありません。Snowflake のアップロード後チェックサム検証がこれを認識できず
ステートメントを失敗させます。その時点でファイルシステムへの書き込みは既に成功しています。

認識されない暗号化タイプを報告することが上流の原因であるため、AWS 側にも提起しています
（[AWS のページ](./aws-ja.md)）。ここに記載するのは、認識されない暗号化タイプを部分書き込みに
変えているのはクライアント側の処理だからです。

### 重大度を高とした理由

失敗したステートメントは通常、何も起きなかったことを意味します。ここでは書き込みが完了し
確認応答が失敗したことを意味します。リトライロジックを持つ呼び出し側は重複を蓄積します。
このページを読む前に試したことがある人は、認識していない孤児オブジェクトを抱えています。

提案する変更は `aws:fsx` を無条件に受け入れることではありません。**書き込む前に失敗するか、
失敗した後に片付けること**です。どちらでも「失敗した `COPY INTO` は出力を残さない」という
不変条件が保たれます。ステージの暗号化タイプはステートメント開始時点で既知であるため、
その時点で検証するほうが安価です。

### 暗号化タイプを明示すると悪化する

| 試行 | 結果 |
|---|---|
| 暗号化の明示なし | 479 ms で失敗。オブジェクトは書き込まれた |
| ステージに `ENCRYPTION=(TYPE='AWS_SSE_S3')` | **ハング。** 2分54秒でキャンセル。何も書かれなかった |

2行目のほうがより懸念すべき挙動と言えます。ハングは運用者に対処のとりかかりを与えません。
`AWS_SSE_KMS` で挙動が変わるかは未テストです。

**検証済みの回避策**: Access Point へアンロードしない。代わりに Snowflake 管理のストレージ
へ書き込む。内部テーブル、または External Volume 上の Managed Iceberg Table です。後者は
同一セッションでエンドツーエンドに検証しました。同じボリュームへの NFS または SMB
アクセスがあれば、そちらへ書くことで S3 層を完全に回避できます。

---

## 2. Dynamic Table が External Table を参照できない

**計測** 2026-08-06。

```
CREATE DYNAMIC TABLE ... AS SELECT ... FROM <AP ステージ上の外部テーブル>

→ Object ref EXT_FMT_JSON of type EXTERNAL_TABLE not supported in
  Dynamic Table definition
```

明快な拒否、明確なメッセージ、素直な回避策。不具合ではなく制約として記録しています。

**動作する経路**（同一セッションで検証）:

| ステップ | 結果 |
|---|---|
| Access Point バックエンドのステージから標準テーブルへ `COPY INTO` | PASS、2,114 ms、3行 |
| `CREATE DYNAMIC TABLE (TARGET_LAG='60 seconds', REFRESH_MODE=FULL)` | PASS、1,872 ms |
| Dynamic Table から `SELECT` | PASS、541 ms |

リフレッシュの挙動は仕様どおりでした。2つ目のファイルを追加してロードした後、集計は
正しく更新され、リフレッシュ履歴は約 48 秒ごとの実行を示し、`refresh_action` はデータが
変わったときは `FULL`、変わっていないときは `NO_DATA`、すべて `SUCCEEDED`、ラグは 1〜3 秒
でした。

**あると助かること**: Dynamic Table のドキュメントに External Table の制約を記載すること。
外部データに対する増分パイプラインを設計する人は、まさにこの組み合わせを最初に試します。
着地ステップを挟むことは、分かってしまえば容易に追加できます。

---

## 3. 訂正: 外部ステージは設計上読み取り専用ではない

**これは本リポジトリに対する訂正であり、Snowflake へのフィードバックではありません。**
誤った記述がここで公開され他者に読まれたため、含めています。

旧版では次のように記述していました。

> Snowflake の外部ステージは設計上読み取り専用である。

これは誤りです。書き込みは拒否されません。書き込みはファイルシステムに到達しオブジェクトは
無傷で、その後ステートメントが項目1の理由でチェックサム検証に失敗します。

誤った説明は単に不正確であるより悪いものでした。部分書き込みハザードを隠していました。
ステージが設計上読み取り専用であれば、アンロードの失敗は何も書かれなかったことを含意します。
そうではないため、アンロードの失敗は完全なオブジェクトを残しえます。誤った説明は読者に
確認を省かせていたはずです。

[互換性マトリクス](../ja/compatibility-matrix.md)、[ブロッカートラッカー](../ja/blocker-tracker.md)、
[未検証項目インベントリ](../ja/unverified-inventory.md)はいずれも訂正後の理由を記載しています。

---

## 同一セッションで検証できたこと（網羅性のため記録）

これらについて Snowflake 側に必要なことはありません。問題のみを列挙したフィードバックは
統合の実態を誤って伝えるため掲載しています。

| 機能 | 結果 |
|---|---|
| Access Point バックエンドのステージからの JSON、Avro、ORC 読み取り | 同一内容に対して3形式すべてが同一の行を返した。名前付き `FILE FORMAT` オブジェクトが必要で、ステージのテーブル関数形式ではインラインの `FILE_FORMAT` は受け付けられない。Access Point の制約ではなく Snowflake の構文 |
| Snowpark `SnowflakeFile.open` | ファイル内容を返した。SQL で表現できない非構造化処理に有用 |
| ステージからの `COPY INTO` による Managed Iceberg Table | エンドツーエンド: External Volume 作成、`SYSTEM$VERIFY_EXTERNAL_VOLUME` が write/read/list/delete を通過、テーブル作成、行のロードと読み戻し、宛先バケット上に実際の Iceberg レイアウト（メタデータ JSON、マニフェスト Avro、データ Parquet） |
| `VENDED_CREDENTIALS` を用いた Glue Iceberg REST | 2026-06-05 に検証。`CREATE TABLE`、`SELECT`、`COUNT`、`DESCRIBE`、`AUTO_REFRESH` がいずれも動作。`ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` の明示と、既定 External Volume を持たないスキーマが必要 |
| 合成した S3 通知からの Snowpipe | publish から約 0.5 秒後に取り込まれた。FSx for ONTAP S3 Access Points は S3 イベントを発行しないため、通知は Lambda ポーラーで合成した。[エビデンス](../../verification-pack/snowpipe-pattern-a/evidence/2026-08-06/snowflake-side-verification.yaml) |

### セットアップに関する所見1点

Snowflake の External Volume は、Storage Integration と同じ2段階の IAM 信頼設定を必要と
します。プレースホルダの信頼ポリシーで作成し、生成された IAM ユーザー ARN と external ID を
読み戻し、信頼ポリシーを更新します。ドキュメント化されていますが、初回で最も見落とされ
やすいステップであり、結果として発生する失敗は信頼ポリシーを指し示しません。

---

## 未解決事項

| 項目 | 阻害要因 |
|---|---|
| External Catalog ソースとしての S3 Tables Iceberg REST エンドポイント | サポートされたカタログタイプではない。2026-05 に機能要望を提出。代替として Glue Iceberg REST が動作し検証済み |
| `COPY INTO` の64日間ロード履歴による重複排除 | 64日間の経過時間（UNV-003）。短縮不可 |
| Iceberg テーブルを読む外部エンジンに対する Horizon Catalog ガバナンスの適用 | カタログに対して構成した2つ目のエンジン（UNV-004） |
| Access Point バックエンドのステージへの PrivateLink | Business Critical エディション以上（UNV-007） |
| 宛先ステージの `AWS_SSE_KMS` がアンロードの結果を変えるか | 未テスト |

> 上記すべてに対する規模の注意点: 2026-08-06 セッションの全テストは1桁の行数で実施して
> います。これらの経路が動作することは示していますが、規模を伴った際の挙動は示していません。
