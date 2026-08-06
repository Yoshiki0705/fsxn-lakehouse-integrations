🌐 [English](./apache-iceberg.md) | **日本語**

# フィードバック: Apache Iceberg

対象: メタデータ書き込み時における `S3FileIO` の Amazon FSx for NetApp ONTAP S3
Access Point エイリアスの扱い。2026-08-06 時点。

## サマリー

所見は1件で、最初に記録した時点より対処可能性が高いことが分かっています。

FSx for ONTAP S3 Access Point 上の Iceberg は動作します。Athena + Glue Data Catalog 経由で
エンドツーエンドに検証済みで、UPDATE、DELETE、タイムトラベル、`OPTIMIZE`、`VACUUM`、
同時2コミットを含みます。同じテーブルフォーマットが同じストレージ上で、EMR Serverless
経由ではコミットパスの `NullPointerException` で失敗します。

フォーマットが動作しストレージも動作するため、差分は `S3FileIO` が Access Point エイリアスを
どう解決するかにあります。これはストレージ互換性の問題ではなくクライアントコードの問題で
あり、意味のある再分類です。

---

## 失敗の内容

**計測** 2026-05-24、EMR Serverless 7.1.0 で。
[エビデンス](../../verification-pack/iceberg/evidence/2026-05-24/evidence-record.yaml)

ウェアハウスパスを Access Point エイリアス上に置いた `CREATE TABLE` が、メタデータ
書き込み時に失敗します。

```
java.lang.NullPointerException: Cannot invoke
"org.apache.iceberg.TableMetadata.metadataFileLocation()"
because "metadata" is null
```

| 観測項目 | 内容 |
|---|---|
| 失敗箇所 | メタデータ書き込みとコミット検証 |
| データファイル書き込み | 到達せず |
| Glue Catalog データベース作成 | 成功（`glue:CreateDatabase` は動作） |
| ウェアハウスパスの形式 | Access Point エイリアスをバケット名として使用。例: `s3://<ap-alias>-ext-s3alias/path` |

記録された根本原因分析では3つの可能性を検討していました。

1. `S3FileIO` が S3 Access Point エイリアスをバケット名として正しく扱えない
2. メタデータの `PutObject` は成功するが、その後の `HeadObject` または `GetObject` による
   検証がエイリアス解決のために失敗する
3. コミットプロトコルが Access Point の非対応操作を必要とする

## 可能性3を除外できるようになった理由

失敗を記録した時点では分かりえなかったため、追記する価値がある部分です。

当時、FSx for ONTAP S3 Access Points は条件付き書き込みに `501 NotImplemented` を返すことが
判明しており、Delta Lake 書き込みがその理由で失敗することも判明していました。Iceberg
書き込みも同じ理由で失敗しているという推論は妥当なものでした。

2026-08-06 の Athena での実行がその推論を否定しました。
[エビデンス](../../verification-pack/athena-iceberg/evidence/2026-08-06/evidence-record.yaml)

| Athena + Glue 経由の Access Point 上での操作 | 結果 |
|---|---|
| `CREATE TABLE`（Iceberg） | 成功、1,607 ms |
| `INSERT INTO`（コミット） | 成功、4,766 ms |
| `UPDATE`（行レベル） | 成功、4,733 ms |
| `DELETE`（行レベル） | 成功、6,323 ms |
| タイムトラベル `FOR VERSION AS OF` | 成功 |
| `OPTIMIZE ... REWRITE DATA` | 成功、4,748 ms |
| `VACUUM`（スナップショット期限切れ） | 成功、4,773 ms |
| 同時2件の `INSERT` | 双方成功。件数は正しく、更新の喪失なし |

データとメタデータの双方が Access Point 上に存在しました。書き込まれたオブジェクトは11件、
データファイル3件とメタデータファイル8件です。Glue が現行メタデータのポインタを保持し
コミットが Glue 内の条件付き更新になるため、オブジェクトストアへの条件付き書き込みは
不要です。

したがって Access Point は Iceberg のコミットプロトコルが要求するすべてに対応しています。
EMR での失敗は `S3FileIO` 内の可能性1または2です。

## あると助かること

| 提案 | 根拠 |
|---|---|
| `S3FileIO` が S3 Access Point エイリアスをバケット名としてサポートするかを確認し、いずれの結論でもドキュメント化する | 現状は、エイリアスが構文上は妥当なバケット名であるため動作するように見え、コミット検証で失敗します。対応・非対応が明示されていれば、利用者は即座に経路を選択できます |
| `NullPointerException` ではなく切り分け可能なエラーで失敗する | `metadata is null` はエイリアス解決が関与していることを一切示しません。検証できなかったパスを示すメッセージであれば原因を指し示します |
| エイリアスが非対応であれば、Access Point ARN の受理を検討する | AWS SDK の一部の経路では、エイリアスが同一に解決されない場面で ARN 形式が受理されます。ここで有効かは未テストであり、結論ではなく方向性として記載します |

## 本プロジェクトがテストしていないこと

この所見を実際より網羅的に読まれないよう記載します。

| 未確認事項 | 備考 |
|---|---|
| エイリアスではなく Access Point ARN を設定した `S3FileIO` | エビデンス記録に調査すべき推奨事項として記載しているが、実行していない |
| `S3FileIO` ではなく `S3AFileSystem`（`s3a://`） | 同様。記録に推奨として記載、未実施 |
| AWS Glue ETL からの Iceberg 書き込み | UNV-017 / UNV-018。Glue 4.0 はネイティブの Iceberg サポートを持ちポインタ管理に Glue Catalog を使うため、EMR ではなく Athena に近い挙動になる可能性がある。実行なし |
| 3以上の同時ライター | Athena での実行は同時2コミットをテストした。ここで同時実行が categorical に危険ではないことを示すが、同時実行の上限ではない |
| 現実的なテーブルサイズ | Athena での実行は1桁の行数。規模を伴ったマニフェスト増加、コンパクションコスト、パーティション進化は未計測（UNV-021） |
| position-delete と copy-on-write の挙動の違い | 未確認 |

## ステータス

Apache Iceberg プロジェクトへは未提出です。EMR Serverless がランタイムを提供・構成している
ため修正の置き場所は両方ありえ、[AWS のページ](./aws-ja.md)にも記録しています。

## Iceberg 側から読む方への前提情報

FSx for ONTAP S3 Access Points は NFS/SMB のファイルデータを S3 API 経由で公開します。
Iceberg にとって関係する Amazon S3 との差分は以下です。

| 性質 | 状態 |
|---|---|
| 条件付き書き込み（`If-None-Match`） | `501 NotImplemented` を返す。Athena の結果が示すとおり、カタログがポインタを保持する場合は問題にならない |
| アトミックリネーム | 利用不可。S3 API に存在しない。Iceberg は必要としない |
| 書き込み後の一覧整合性 | 対応 |
| `PutObject`、`GetObject`、`DeleteObject`、マルチパート | 対応 |
| 単一アップロード上限 | 5 GB |
| オブジェクトバージョニング | 非対応 |
| バケットのアドレッシング | Access Point エイリアス。形式は `<name>-<suffix>-ext-s3alias` |
