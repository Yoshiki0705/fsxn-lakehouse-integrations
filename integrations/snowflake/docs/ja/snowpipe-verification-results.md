🌐 [English](../en/snowpipe-verification-results.md) | **日本語**

# Snowpipe + FSx for ONTAP S3 Access Point — 検証結果

**測定日**: 2026-08-05 | **リージョン**: ap-northeast-1

本ドキュメントは、FSx for ONTAP S3 Access Point から Snowflake へデータを取り込む経路について、**実際に測定できたこと**と、同じく重要な**測定できていないこと**を記録します。本リポジトリでこれまで引用されていた数値のいくつかにエビデンス記録がなく、そのうち 1 つは再現しないことが判明したため作成しました。

生エビデンス:

- [`verification-pack/s3ap-list-latency/evidence/2026-08-05/`](../../../../verification-pack/s3ap-list-latency/evidence/2026-08-05/benchmark-result.yaml)
- [`verification-pack/snowpipe-pattern-a/evidence/2026-08-05/`](../../../../verification-pack/snowpipe-pattern-a/evidence/2026-08-05/aws-side-verification.yaml)

---

## エグゼクティブサマリ

**Snowpipe は定期実行できません。** Snowpipe は設計上イベント駆動であり、「5 分ごとに Snowpipe を実行する」という選択肢は存在しません。FSx for ONTAP S3 Access Point からの定期取り込みは **Snowflake Task で COPY INTO を実行する**方式で行い、これは Snowpipe とは別の機能で、既に検証済みです。

| 取り込み経路 | ステータス | エビデンス |
|---|:---:|---|
| Snowpipe 自動取り込み（`AUTO_INGEST = TRUE`、実 S3 イベント） | ❌ 不可 | FSx for ONTAP S3 AP は S3 イベント通知非対応（[BLK-003](../../../../docs/ja/blocker-tracker.md)） |
| **Task + COPY INTO（定期実行）** | ✅ **検証済み** | AP バックエンドの stage からの COPY INTO: [2026-05-24](../../../../verification-pack/snowflake/evidence/2026-05-24/evidence-record.yaml) |
| Task + `ALTER EXTERNAL TABLE ... REFRESH` | ✅ 検証済み | External Table 読み取りを 2026-05-24 に検証 |
| パターン A: Lambda ポーリング → SNS → Snowpipe | ⚠️ AWS 側は検証済み、Snowflake 側は**未検証** | [本ドキュメント](#パターン-a-lambda-ポーリング--sns) |
| パターン B: FPolicy → Lambda → SNS → Snowpipe | ⚠️ 設計のみ | live 検証なし |
| Snowpipe REST API（`insertFiles`） | ⚠️ 未検証 | 選択肢としての記載のみ |

**現時点で定期取り込みが必要なら Task + COPY INTO を使ってください。** 合成通知が不要で、Snowflake 自身のロード履歴により、ポーリング窓では得られない exactly-once の挙動が得られます。

---

## 訂正: 「ListObjectsV2 が 30-80 倍遅い」という数値について

本リポジトリではこれまで十数箇所で、FSx for ONTAP S3 Access Point に対する ListObjectsV2 がネイティブ S3 より **30-80 倍遅い**と記載していました。この数値を再測定した結果、**再現しませんでした**。

測定値（median、データ点ごとに記録試行 5 回、warm-up 1 回を破棄、計測範囲はページネーションされた ListObjectsV2 ループのみ）:

| オブジェクト数 | FSx for ONTAP S3 AP | ネイティブ S3 | 比率 |
|--------:|--------------------:|----------:|------:|
| 10 | 38 ms | 27 ms | 1.4x |
| 100 | 52 ms | 39 ms | 1.3x |
| 1,000 | 162 ms | 128 ms | 1.3x |
| 5,000 | 665 ms | 704 ms | 0.9x |

ネスト構造（2 階層、leaf ディレクトリあたり 10 オブジェクト、日付パーティション相当）でも 1,000 件で 1.4x、5,000 件で 1.0x となり、フラット構造と実質的な差はありませんでした。

**この結果が意味すること・意味しないこと。** 測定したオブジェクト数の範囲では、Access Point はネイティブ S3 の約 1.4 倍以内で動作し、本ブロッカーに記録されていた性能目標（100 ファイル未満で 1 秒未満、1,000 ファイル未満で 3 秒未満）を十分に満たしています。ただしこれは、リスティングが無制限にスケールすることを意味**しません**。本測定は 5,000 オブジェクトで打ち切っており、単一ディレクトリに数十万〜数百万オブジェクトある場合の挙動は未検証です。小ファイルを統合しキー空間をパーティション分割するという設計指針は、その理由により依然として有効です。

30-80 倍という数値の出自は特定できていません。比較対象となるエビデンス記録が残っていないため、特定の原因に帰属させず「未解明」として記録します。考えられる要因としては、CLI ラッパー経由での測定（短時間の呼び出しではプロセス起動時間が支配的になる）、当時ファイルシステムが劣化状態にあった、当時から現在までのプラットフォーム側の変更などがあります。

> **リクエストコストに関する補足**: `MaxKeys=1000` 指定時、ネイティブ S3 は 1 回の API 呼び出しで 1,000 キーを返しましたが、Access Point では 2 回必要でした（5,000 オブジェクトでは 6 回対 5 回）。実時間は同等なのでボトルネックではありませんが、API コストを見積もる場合や、クライアントがページネーション深度を制限している場合には、リクエスト回数が同一であることを前提にしないでください。

再現方法:

```bash
python3 shared/scripts/benchmark_list_objects.py \
  --ap-arn arn:aws:s3:<region>:<account>:accesspoint/<ap-name> \
  --native-bucket <comparison-bucket> \
  --counts 10,100,1000,5000 --trials 5 --layout flat --teardown
```

---

## パターン A: Lambda ポーリング → SNS

パターン A は、S3 イベント通知が使えない制約を回避するため、スケジュール実行される Lambda が Access Point をリストし、S3 イベント形式の通知を合成して SNS に publish し、それが `AUTO_INGEST = TRUE` の pipe を支える Snowflake 管理の SQS キューに流れ込む、という構成です。

このチェーンの AWS 側は検証しました。Snowflake 側は、本環境に Snowflake の認証情報がなかったため未検証です。

### 合格した項目

| ステップ | 結果 |
|---|---|
| Access Point への PutObject（74 バイトのオブジェクト） | 716-805 ms |
| ポーラー Lambda の ListObjectsV2 検知 | 981 ms（wall time） |
| SNS publish と配信 | SNS を subscribe した SQS キューでメッセージを捕捉して確認 |
| ファイル書き込み → 通知配信 | **2.1 秒** |
| Access Point のアドレッシング | `Bucket` パラメータには ARN でも alias でも動作。AP ARN に付与した IAM で alias 経由のリクエストも認可される |

2.1 秒という数値は EventBridge のスケジュール待ち時間を含みません。実運用での検知遅延は（スケジュール間隔）+ 約 2 秒となるため、`rate(5 minutes)` なら最大約 5 分です。ポーリング方式の設計目標として引用されている「5-7 分」と整合します。

### 発見した欠陥

検証により 6 件の欠陥が明らかになりました。うち 2 件は、公開されているアーティファクトがそのままでは動作しない原因です。

| ID | 深刻度 | 内容 |
|---|---|---|
| DEFECT-1 | High | `snowpipe-lambda/template.yaml` が実 handler ではなくプレースホルダー関数をデプロイする |
| DEFECT-2 | High | ポーリング窓より古いオブジェクトが通知されずに失われる（データ損失） |
| DEFECT-3 | Medium | 合成通知に、実 S3 イベントには存在するフィールドが欠落している |
| DEFECT-4 | Medium | AP ARN を設定すると `s3.bucket.name` に ARN が入る |
| DEFECT-5 | Low | 窓の重複により、既に通知したオブジェクトを再通知する |
| DEFECT-6 | Low | ポーラーに DLQ もエラーアラームもない |

**DEFECT-1** — テンプレートのインライン `Code.ZipFile` の本体は `return {"statusCode": 200, "body": "Deploy handler.py"}` です。公開されているテンプレートをそのままデプロイすると、何もリストしないポーラーができます。`handler.py` はインラインのサイズ上限を超えるため単に貼り付けることはできず、実際のパッケージング手順が必要です。テンプレートは `Transform: AWS::Serverless-2016-10-31` を宣言していますが SAM リソースを定義していないため、この Transform は現状無効です。

**DEFECT-2** — `STATE_TABLE` 未設定時、cutoff は `now - POLLING_INTERVAL_MINUTES` となり、この cutoff は実時間に追従するため、窓より古いオブジェクトは二度と参照されません。再現しました: 05:07:52Z に書き込んだオブジェクトは、cutoff が 05:08:33Z である 05:09:33Z の実行から不可視で、`new_files_found=0` となりました。一方、同じ prefix に対する ListObjectsV2 ではそのオブジェクトの存在が確認できました。さらに悪いことに、`template.yaml` は `STATE_TABLE` パラメータを一切公開していないため、CloudFormation でデプロイしたポーラーは常にこの損失モードで動作し、`handler.py` の DynamoDB チェックポイント経路は公開テンプレート経由では到達不能です。

**DEFECT-3 / DEFECT-4** — 合成されるレコードは `eventVersion`・`eventSource`・`eventName`・`eventTime`・`s3.bucket.name`・`s3.object.key`・`s3.object.size` のみを持ちます。実際の S3 通知はこれに加えて `awsRegion`・`s3.s3SchemaVersion`・`s3.configurationId`・`s3.bucket.ownerIdentity`・`s3.bucket.arn`・`s3.object.eTag`・`s3.object.sequencer` を持ちます。また別途、`handler.py` は `S3_ACCESS_POINT_ALIAS` をそのまま `s3.bucket.name` にコピーするため、AP ARN を渡すとバケット名が入るべき箇所に ARN が出力されます。Snowpipe は受信した通知を pipe の stage location と照合するため、ここに ARN が入ると `s3://<bucket>/<path>` 形式の stage URL と一致する見込みは低いです。

### 未検証のまま残っている点

決定的な問いは、**合成された**通知を Snowflake が pipe の `notification_channel` で受理し COPY を発火させるかどうかです。その上流はすべてエビデンスが揃いましたが、この 1 ステップだけが揃っていません。ここが検証されるまで、パターン A を動作する経路として提示すべきではありません。

検証には、`ACCOUNTADMIN`（storage integration と pipe の作成用）を持つ Snowflake アカウントと、DEFECT-1 〜 DEFECT-4 を修正した上での AWS 側の再デプロイが必要です。`integrations/snowflake/tests/test_snowpipe_e2e.sh` が想定されているハーネスで、これには追加でボリュームの NFS マウントも必要です。

---

## すべての経路に共通する制約

以下は今回の検証で変わっておらず、FSx for ONTAP のデータを Snowflake に取り込む際の実質的な制限として残ります。

| 制約 | 影響 |
|---|---|
| S3 イベント通知非対応 | Snowpipe 自動取り込みと `AUTO_REFRESH` が利用不可（[BLK-003](../../../../docs/ja/blocker-tracker.md)） |
| `AUTO_REFRESH` 非対応 | External Table と Directory Table のメタデータには明示的な `REFRESH` が必要。通常は Task で駆動する |
| 条件付き書き込み非対応 | Iceberg / Delta の書き戻しがブロックされる（[BLK-002](../../../../docs/ja/blocker-tracker.md)） |
| PutObject 5 GB 上限 | それを超えるオブジェクトはこの上限内でマルチパートアップロードが必要 |
| AP stage で `TO_FILE()` 非対応 | Vision AI には `COPY FILES` によるステージング手順が必要 |
| Snowflake 公式サポート対象外 | Snowflake は FSx for ONTAP S3 Access Point を External Stage のバックエンドとして文書化していません。読み取りとガバナンス経路は本リポジトリで検証済みですが、本番利用前に Snowflake サポートへ確認してください |

> **Dynamic Table に関する補足**: External Table をソースとする Dynamic Table には `REFRESH_MODE = FULL` が必要です（増分リフレッシュには change tracking が必要で、External Table はこれを提供しません）。また `TARGET_LAG` の最小値は 60 秒です。さらに `AUTO_REFRESH` が使えないため、事前に External Table のメタデータをリフレッシュする Task に依存する点も変わりません。

---

## 関連ドキュメント

- [Snowflake 統合 README](../../README.md) — 検証ステータスと選定指針
- [Snowpipe 統合ガイド](./snowpipe-integration.md) — 候補となる 3 パターン
- [内部テーブル取り込みガイド](./internal-table-ingestion-guide.md) — Task + COPY INTO と Dynamic Table のパターン
- [Blocker Tracker](../../../../docs/ja/blocker-tracker.md) — BLK-003 と BLK-006
- [イベント駆動アーキテクチャ](../../../../docs/ja/event-driven-architecture.md) — FPolicy 経路の設計目標値
- [互換性マトリクス](../../../../docs/ja/compatibility-matrix.md) — 制約の全一覧
