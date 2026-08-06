🌐 [English](./databricks.md) | **日本語**

# フィードバック: Databricks

対象: Amazon FSx for NetApp ONTAP S3 Access Points に対する Unity Catalog および
Databricks Runtime の挙動。2026-08-06 時点。

## サマリー

アーキテクチャ上の帰結が最も大きい統合です。読み取りが不可能だからではなく（読み取りは
実現可能です）、動作する経路がいずれも Unity Catalog を迂回し、そして Unity Catalog こそが
このプラットフォームを使う理由だからです。

結果として、FSx for ONTAP のデータについては、ゼロコピー分析と Unity Catalog ガバナンスが
現時点で両立しません。どの回避策も一方を他方と引き換えにします。

| # | 所見 | ステータス | 帰結 |
|:---:|---|---|---|
| 1 | [Access Point を Unity Catalog の External Location にできない](#1-access-point-を-unity-catalog-の-external-location-にできない) | Databricks サポートが 2026-05-26 に確認 | ゼロコピー経路でガバナンスが使えない |
| 2 | [`iceberg_rest` が Connection Type として受け付けられない](#2-iceberg_rest-が-connection-type-として受け付けられない) | `CONNECTION_TYPE_NOT_SUPPORTED`、2026-05-31 | S3 Tables を Foreign Catalog として参照できない |
| 3 | [Runtime の seccomp が NFS/SMB マウントを禁止する](#3-runtime-の-seccomp-が-nfssmb-マウントを禁止する) | 設計どおり | 直接のファイルシステム経路がない。要望ではなく想定どおりとして記載 |

## 提起の経緯について

サポートケース2件は、技術的な判断ではなくサポートティアの理由で not entitled として
クローズされました。元の問いは評価されておらず、未解決のままです。公開コミュニティ
フォーラムへ移しています。

- [Unity Catalog External Location with S3 Access Points](https://community.databricks.com/t5/data-engineering/unity-catalog-external-location-with-amazon-s3-access-points/m-p/160296#M54880)（2026-06）
- [OpenSharing vended STS credentials on S3 Access Points](https://community.databricks.com/t5/data-engineering/opensharing-vended-sts-credentials-on-s3-access-points-verified/m-p/160298#M54881)（2026-06）

これは製品ではなくプロセスへのフィードバックですが、述べておく価値があります。
プラットフォーム機能に関する問いがサポート経路でエンジニアに届かない場合、注目を
競い合うフォーラム投稿として残ります。統合互換性に関する問いについて、より適した経路が
あるなら知りたいところです。

---

## 1. Access Point を Unity Catalog の External Location にできない

**Databricks サポートが確認** 2026-05-26。[BLK-001](../ja/blocker-tracker.md) ·
[統合ノート](../../integrations/databricks/README.md#support-confirmation-2026-05-26)

Access Point のパスに対する `CREATE TABLE` は以下で失敗します。

```
UC_CLOUD_STORAGE_ACCESS_FAILURE
```

サポートは、S3 Access Point は External Location の対象としてサポートされておらず、
`access_point` フィールドは GA ではないと確認しました。記録されている根本原因は、
`AssumeRole` 時に生成されるセッションポリシーが Access Point ARN を正しく解釈しないこと
です。

### 部分的な成功は誤解を招くため、正確に記述する価値がある

2026-05-24 のテストでは、バケットルートの一覧取得と明示的なファイルパスの読み取りが
成功しました。部分的にサポートされているように見えました。サポートはこれを
**「不完全な内部処理の副作用であり、サポートされたコードパスではない」**と説明しました。
サブディレクトリの一覧取得と `CREATE TABLE` はいずれも失敗しています。

評価する立場にとってこれは重要です。初期のテストが有望に見えるだけの成功を返し、
その後テーブルを定義する段階で失敗しえます。サポート対象の経路ではないと知ることで、
その上に構築せずに済みます。

### 動作するもの、および各選択肢のコスト

| 経路 | ガバナンス | コピーコスト | トレードオフ |
|---|:---:|---|---|
| DataSync → 標準 S3 → External Location | ✅ Unity Catalog 全機能 | 約 $27/月/TB | 推奨経路。ゼロコピーを失う。それが元々このアーキテクチャを選ぶ理由だった |
| Kafka → Structured Streaming → Unity Catalog Delta | ✅ 全機能 | ストリーミング基盤 | リアルタイム要件に適合。運用は重い |
| Glue または EMR ETL → 標準 S3 → Unity Catalog | ✅ 全機能 | 変換 + ストレージ | 既存のバッチパイプラインに適合 |
| Instance Profile + boto3 での直接読み取り | ❌ なし | ゼロ | 動作するが Unity Catalog を完全に迂回する。PoC 限定 — リネージ、タグ、マスク、行フィルターなし |

最後の行が現状の正直な要約です。Databricks から FSx for ONTAP のデータを読むことは
可能で、ガバナンス下で読むことはできません。

### これがゲートである理由

他のいくつかのブロッカーは、これが解消して初めて価値を生みます。FSx for ONTAP S3
Access Points に条件付き書き込みが実装されれば Athena と EMR は即座に恩恵を受けますが、
Databricks Unity Catalog は受けません。Unity Catalog がそもそもそのストレージを
アドレスできないためです。依存は一方向です。

**解消に必要なこと**: S3 Access Point を External Location の対象として GA サポート
すること。生成されるセッションポリシーが Access Point ARN を扱えることが前提になります。

---

## 2. `iceberg_rest` が Connection Type として受け付けられない

**計測** 2026-05-31。[BLK-005](../ja/blocker-tracker.md)

```sql
CREATE CONNECTION ... TYPE iceberg_rest ...
→ CONNECTION_TYPE_NOT_SUPPORTED
```

S3 Tables はマネージドな Iceberg REST Catalog エンドポイントを提供します。Databricks SQL
Warehouse はこれを利用できません。`iceberg_rest` がサポートされる接続タイプに含まれない
ためです。`TYPE GLUE` は代替になりません。host、httpPath、PAT を要求するため、
Databricks 間の接続用です。

同じエンドポイントに対する比較として、Athena は Glue フェデレーテッドカタログ経由で設定
不要に読み取り、PyIceberg と DuckDB は直接読み取ります。エンドポイント自体は素直に
利用できるものです。

### 回避策（成立度の高い順）

| 選択肢 | ガバナンス | 備考 |
|---|:---:|---|
| Glue HMS Federation（`CREATE CONNECTION TYPE glue`） | ✅ Unity Catalog が適用される | **現時点の実務上の答え。** Glue フェデレーテッドカタログ経由で S3 Tables の Iceberg テーブルを Foreign Catalog として参照する。[実行ガイド](../../integrations/iceberg-metadata-catalog/databricks/foreign-iceberg-execution-guide.md) |
| 標準 S3 上の Iceberg → Glue Catalog → Foreign Catalog | ✅ 適用される | 最も確実だが、S3 Tables のマネージドメンテナンスを手放す |
| `spark.sql.catalog.s3tables` を手動設定した Databricks Spark クラスタ | ❌ Unity Catalog の外 | 技術的には EMR の機構と等価。**本プロジェクトでは未テスト**（UNV-009）— EMR の結果からの推論で、実行記録はない |
| 代わりに Athena または EMR でクエリする | 該当なし | AWS ネイティブのエンジンは正常に動作する |

Glue HMS Federation が存在し GA であるため、項目1より重大度は低いです。機能の欠落では
なく直接経路の欠落です。

---

## 3. Runtime の seccomp が NFS/SMB マウントを禁止する

**確認** 2026-05、設計レベルの制約として。[BLK-007](../ja/blocker-tracker.md)

Databricks Runtime の seccomp プロファイルが `mount` と `umount` を禁止しているため、
クラスタから NFS や SMB をマウントして FSx for ONTAP に直接到達できません。

**要望ではなく想定どおりの挙動として記録しています。** これは意図的なセキュリティ設計で、
マルチテナントのランタイムとしては正しい既定です。ここに記載するのは、この失敗に
遭遇して追求すべきか迷う人に理由が見えるようにするためだけです。答えは追求すべきでは
なく、項目1のネットワーク経路を使うことです。

---

## テストしていない事項

2026年5月に使用した Databricks ワークスペースは撤去済みで、いくつかのケースは実行記録が
ありません。このフィードバックを実際より徹底したものと読まれないよう記載します。

| 項目 | 備考 |
|---|---|
| Databricks Spark クラスタからの Iceberg REST Catalog | UNV-009。EMR の機構からの推論で、実行なし |
| 顧客管理 VPC からのエグゼキュータ規模の boto3 アクセス | UNV-010。Databricks 管理 VPC のケースは FSx へのエグレスで失敗したと記録。顧客管理 VPC のケースは未テスト |
| `verification-pack/databricks/test-cases.yaml` の11ケースのうち9件 | UNV-011。実行記録なし |
| 統合の自動テスト | UNV-012。`integrations/databricks/tests/` には `.gitkeep` のみ。Snowflake には8つのテストファイルがあるが Databricks にはない |

なお、これらが何を示すかにかかわらず、項目1が Unity Catalog 経路を阻害します。
