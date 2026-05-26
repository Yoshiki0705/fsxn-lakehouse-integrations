🌐 [English](../en/datasync-to-s3-guide.md) | **日本語**

# AWS DataSync: FSx for ONTAP → S3 同期ガイド

> **ステータス**: リファレンスアーキテクチャ — DataSync は FSx for ONTAP から標準 S3 バケットへの唯一の検証済み同期メカニズムです（SnapMirror S3 は [FSx for ONTAP で利用不可](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml)）。

## このガイドが必要な場面

- Databricks Unity Catalog が標準 S3 バケットのデータを要求する場合（FSx for ONTAP S3 AP は UC 非サポート）
- Delta Lake / Iceberg / Hudi テーブルフォーマット書き込みに標準 S3 が必要な場合（FSx for ONTAP S3 AP は conditional writes 非サポート）
- FSx for ONTAP データのガバナンス付きコピーを S3 に配置して下流で消費する場合

## アーキテクチャ

```
FSx for ONTAP (NFS)
  ↓ DataSync タスク（スケジュール）
Amazon S3 バケット（標準）
  ↓
分析エンジン（Databricks UC, Delta Lake, Iceberg 等）
```

## 前提条件

- NFS アクセス可能なボリュームを持つ FSx for ONTAP ファイルシステム
- 同一リージョンのターゲット S3 バケット
- FSx for ONTAP NFS からの読み取りと S3 への書き込み権限を持つ DataSync 用 IAM ロール
- FSx for ONTAP 管理/データ LIF への接続性を持つ VPC

## セットアップ手順

### ステップ 1: DataSync ソースロケーション作成（FSx for ONTAP NFS）

```bash
aws datasync create-location-fsx-ontap \
  --storage-virtual-machine-arn arn:aws:fsx:ap-northeast-1:<ACCOUNT>:storage-virtual-machine/<SVM_ID> \
  --protocol NFS={} \
  --subdirectory /vol1/data/ \
  --security-group-arns arn:aws:ec2:ap-northeast-1:<ACCOUNT>:security-group/<SG_ID>
```

参照: [FSx for ONTAP での転送設定](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)

### ステップ 2: DataSync 宛先ロケーション作成（S3）

```bash
aws datasync create-location-s3 \
  --s3-bucket-arn arn:aws:s3:::<BUCKET_NAME> \
  --s3-config BucketAccessRoleArn=arn:aws:iam::<ACCOUNT>:role/DataSyncS3Role \
  --subdirectory /fsxn-sync/
```

### ステップ 3: DataSync タスク作成

```bash
aws datasync create-task \
  --source-location-arn <SOURCE_LOCATION_ARN> \
  --destination-location-arn <DESTINATION_LOCATION_ARN> \
  --name fsxn-to-s3-sync \
  --options '{
    "VerifyMode": "ONLY_FILES_TRANSFERRED",
    "OverwriteMode": "ALWAYS",
    "Atime": "BEST_EFFORT",
    "Mtime": "PRESERVE",
    "PreserveDeletedFiles": "REMOVE",
    "TransferMode": "CHANGED"
  }'
```

主要オプション:
- `TransferMode: CHANGED` — 変更されたファイルのみ転送（増分）
- `PreserveDeletedFiles: REMOVE` — FSx for ONTAP で削除されたファイルを S3 からも削除
- `Mtime: PRESERVE` — 変更検知のために更新タイムスタンプを保持

### ステップ 4: タスクのスケジュール設定

```bash
aws datasync update-task \
  --task-arn <TASK_ARN> \
  --schedule ScheduleExpression="rate(5 minutes)"
```

スケジュールオプション:
- `rate(5 minutes)` — 5分ごと（準リアルタイム）
- `rate(1 hour)` — 1時間ごと（バッチ）
- `cron(0 */6 * * ? *)` — 6時間ごと

### ステップ 5: 実行と監視

```bash
# 手動実行
aws datasync start-task-execution --task-arn <TASK_ARN>

# ステータス確認
aws datasync describe-task-execution --task-execution-arn <EXECUTION_ARN>
```

## コストモデル

| コンポーネント | コスト | 備考 |
|------------|------|------|
| DataSync 転送 | $0.0125/GB（同一リージョン） | 初回同期後は変更バイトのみ転送 |
| S3 ストレージ | $0.023/GB/月（Standard） | 宛先ストレージ |
| S3 リクエスト | $0.005/1000 PUT | 同期中 |

**例**: 1 TB 初回同期 + 10 GB/日の増分変更
- 初回: 1000 GB × $0.0125 = $12.50（一回限り）
- 日次増分: 10 GB × $0.0125 = $0.125/日
- 月次増分: 約$3.75/月
- S3 ストレージ: 1 TB × $0.023 = $23/月
- **月額合計（初回同期後）: 1 TB で約$27/月**

## エンドツーエンドレイテンシモデル

| DataSync スケジュール | 転送時間 (10 GB) | Auto Loader 検出 | 合計ラグ |
|---|---|---|---|
| 5分ごと | 約1-2分 | 5分ポーリング | **約7-12分** |
| 1時間ごと | 約1-2分 | 5分ポーリング | **約65分** |
| 6時間ごと | 約1-2分 | 5分ポーリング | **約6時間** |

> 準リアルタイム要件（<1分）には、DataSync の代わりに FPolicy → Lambda → S3 を使用してください。

## ベストプラクティス

1. **`TransferMode: CHANGED` を使用** — 未変更ファイルの再転送を回避
2. **`PreserveDeletedFiles: REMOVE` を設定** — FSx for ONTAP での削除を S3 に反映
3. **Snapshot で整合性を確保** — Snapshot 取得後に DataSync を実行し、ポイントインタイム整合性のある転送を実現
4. **includes/excludes でフィルタ** — 関連プレフィックスのみ同期（例: `/bronze/sensor-data/`）
5. **CloudWatch で監視** — `BytesTransferred`、`FilesTransferred`、`TaskExecutionStatus` にアラーム設定
6. **S3 ライフサイクルルールを使用** — N日後に古い同期データを S3-IA や Glacier に階層化

## Databricks UC との統合

DataSync がデータを S3 に同期した後:

```sql
-- S3 バケットを UC External Location として登録
CREATE EXTERNAL LOCATION fsxn_synced
  URL 's3://<BUCKET>/fsxn-sync/'
  WITH (STORAGE CREDENTIAL <credential_name>);

-- 同期データから UC Managed Table を作成
CREATE TABLE catalog.schema.sensor_data
USING DELTA
AS SELECT * FROM parquet.`s3://<BUCKET>/fsxn-sync/sensor-data/`;
```

## Delta Lake / Iceberg との統合

DataSync がデータを S3 に同期した後、テーブルフォーマット書き込みが正常に動作:

```python
# EMR Spark — 同期済み S3 データに Delta テーブルを書き込み
df = spark.read.parquet("s3://<BUCKET>/fsxn-sync/sensor-data/")
df.write.format("delta").mode("overwrite").save("s3://<BUCKET>/delta-tables/sensors/")
```

## なぜ SnapMirror S3 ではないのか？

SnapMirror S3（ONTAP S3 バケット → AWS S3 レプリケーション）は NetApp ONTAP 9.10.1+ のドキュメントに記載されていますが、**FSx for ONTAP では利用不可**です（2026年5月検証）:
- `snapmirror object-store` CLI コマンド: "not a recognized command"
- `/api/cloud/targets` REST API: "not authorized for that command"
- AWS に機能要望を提出済み

参照: [SnapMirror S3 検証エビデンス](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml)

## 参考資料

- [AWS DataSync + FSx for ONTAP](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)
- [DataSync 料金](https://aws.amazon.com/datasync/pricing/)
- [DataSync タスクオプション](https://docs.aws.amazon.com/datasync/latest/userguide/API_Options.html)
- [FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html)
