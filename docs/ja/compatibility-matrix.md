# 互換性マトリクス

## 概要

本ドキュメントは、FSx for ONTAP S3 Access Points と Lakehouse プラットフォーム/フォーマット間の検証済み互換性を定義します。マトリクスは [アクセスポイントの互換性](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) に記載された S3 API 操作サポートに基づいています。

## FSx for ONTAP S3 Access Points の重要な制約

互換性マトリクスを確認する前に、以下の基本的な制約を理解してください：

| 制約 | 詳細 | ソース |
|------|------|--------|
| Rename 操作なし | S3 API にはネイティブの rename がない。CopyObject は同一アクセスポイント内のみサポート | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| 最大アップロードサイズ: 5 GB | 単一オブジェクトのアップロードは 5 GB まで（マルチパートアップロードはサポート） | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Object Versioning なし | S3 Object Versioning は非サポート | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| 条件付き書き込みなし | Conditional writes は非サポート | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Presigned URLs なし | 署名付き URL の生成は非サポート | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| ストレージクラス: FSX_ONTAP のみ | 他のストレージクラスは指定不可 | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| 暗号化: SSE-FSX のみ | AWS KMS マネージド、透過的な保存時暗号化 | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| 同一リージョン必須 | アクセスポイントは FSx for ONTAP ボリュームと同じリージョンに作成必須 | [制限事項](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |
| 同一アカウント必須 | アクセスポイントとファイルシステムは同じ AWS アカウント内に必要 | [制限事項](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |
| ONTAP 9.17.1 以降必須 | S3 Access Points の最小 ONTAP バージョン | [制限事項](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |

## Lakehouse テーブルフォーマットへの影響

Lakehouse テーブルフォーマット（Delta Lake、Apache Iceberg、Apache Hudi）はトランザクション保証のために特定の S3 動作に依存します：

| 要件 | Delta Lake | Apache Iceberg | Apache Hudi | FSx S3 AP サポート |
|------|-----------|----------------|-------------|-------------------|
| コミット用アトミック rename | 必須（\_delta\_log/） | 不要（メタデータポインタ使用） | 必須（タイムライン） | **利用不可** — 同一 AP 内での CopyObject + DeleteObject が回避策 |
| 書き込み後の一貫したリスト | 必須 | 必須 | 必須 | サポート（ONTAP が一貫性を提供） |
| PutObject | 必須 | 必須 | 必須 | サポート |
| DeleteObject | vacuum/クリーンアップに必須 | 有効期限切れに必須 | 必須 | サポート |
| マルチパートアップロード | 大きなファイル用 | 大きなファイル用 | 大きなファイル用 | サポート（アップロード最大 5 GB） |
| 条件付き書き込み（If-None-Match） | 一部実装で使用 | 一部実装で使用 | 一部実装で使用 | **非サポート** |

## プラットフォーム × フォーマット × モード 互換性マトリクス

### 凡例

| ステータス | 意味 |
|----------|------|
| ✅ 検証済み | テスト済みで動作確認 |
| ⚠️ 実験的 | 既知の制限付きで部分的に動作 |
| ❌ 非サポート | 基本的な制約により動作しない |
| 🔲 計画中 | 未テスト |

### マトリクス

| プラットフォーム | フォーマット | モード | ステータス | 必要な設定 | 既知の制限 |
|---------------|-----------|------|----------|-----------|-----------|
| **Amazon Athena** | Parquet | 読み取り専用 | ✅ 検証済み | Internet-origin AP、Glue Catalog、AP ARN に対する s3:GetObject/ListBucket の IAM ロール | Athena は VPC-origin AP を使用不可（VPC 外のマネージドインフラからアクセス）。結果は別の S3 バケットに書き込み。 |
| **Amazon Athena** | CSV | 読み取り専用 | ✅ 検証済み | Parquet と同じ | 同上 |
| **Amazon Athena** | JSON | 読み取り専用 | ✅ 検証済み | Parquet と同じ | 同上 |
| **Amazon Athena** | ORC | 読み取り専用 | ✅ 検証済み | Parquet と同じ | 同上 |
| **Amazon Athena** | Delta Lake | 読み取り専用（symlink manifest） | ⚠️ 実験的 | Athena Delta Lake コネクタ、symlink_format_manifest の事前生成が必要 | Delta ログの直接読み取り不可。事前生成マニフェストが必要。Write/MERGE 非サポート。 |
| **Amazon Athena** | Iceberg | 読み取り専用 | 🔲 計画中 | Athena Iceberg コネクタ、Glue Catalog を Iceberg カタログとして使用 | 読み取りパスは動作見込み。書き込みパスは未テスト。 |
| **AWS Glue ETL** | Parquet | 読み取り | ✅ 検証済み | AP 権限付き Glue IAM ロール、S3 パスに AP エイリアス | — |
| **AWS Glue ETL** | Parquet | 書き込み（Append） | ✅ 検証済み | AP に読み書きファイルシステムユーザー | ファイルあたり最大 5 GB |
| **AWS Glue ETL** | Parquet | 上書き | ⚠️ 実験的 | 読み書きファイルシステムユーザー | DeleteObject + PutObject パターン。アトミックな上書き保証なし |
| **AWS Glue ETL** | Delta Lake | 読み取り | ⚠️ 実験的 | Glue 4.0+ と Delta Lake ライブラリ | Delta ログの読み取りは動作。書き込みのコミットプロトコルは未テスト |
| **AWS Glue ETL** | Delta Lake | 書き込み | ❌ 非サポート | — | Delta コミットプロトコルは _delta_log JSON ファイルのアトミック rename が必要。ネイティブ非サポート |
| **Amazon EMR Serverless** | Parquet | 読み取り | ✅ 検証済み | S3A コネクタ付き Spark、AP エイリアス | — |
| **Amazon EMR Serverless** | Parquet | 書き込み（Append） | ✅ 検証済み | 読み書きファイルシステムユーザー | ファイルあたり最大 5 GB |
| **Amazon EMR Serverless** | Iceberg | 読み取り | ⚠️ 実験的 | Iceberg Spark ランタイム、Glue Catalog | メタデータ読み取りは動作。書き込みコミットは未テスト |
| **Amazon EMR Serverless** | Delta Lake | 読み取り | ⚠️ 実験的 | Delta Lake Spark ライブラリ | ログ読み取りは動作 |
| **Amazon EMR Serverless** | Delta Lake | Write/MERGE | ❌ 非サポート | — | コミットプロトコルにアトミック rename が必要 |
| **Databricks** | Parquet/CSV | 読み取り（External Location） | ✅ 検証済み | Unity Catalog External Location、AP 権限付きインスタンスプロファイル/ストレージクレデンシャル | — |
| **Databricks** | Delta Lake | 読み取り（External Table） | ⚠️ 実験的 | Unity Catalog、FSx ボリューム上の Delta ログ | 既存の Delta ログがあれば読み取り可能 |
| **Databricks** | Delta Lake | Write/MERGE/Compaction | ❌ 非サポート | — | Delta コミットプロトコルに rename が必要。S3A rename エミュレーション（copy+delete）は条件付き書き込みなしで失敗する可能性 |
| **Snowflake** | Parquet/CSV | 読み取り（External Stage） | ✅ 検証済み | AP エイリアス付き External Stage、ストレージ統合 IAM ロール | — |
| **Snowflake** | Iceberg | 読み取り（External Catalog） | ⚠️ 実験的 | 外部カタログ付き Snowflake Iceberg Tables | メタデータポインタの読み取りは動作 |
| **Snowflake** | 全て | 書き込み | ❌ 非サポート | — | Snowflake External Stage は設計上読み取り専用 |
| **Redshift Spectrum** | Parquet/CSV | 読み取り専用 | 🔲 計画中 | Glue Catalog 経由の External Schema、AP 権限付き IAM ロール | 動作見込み（Athena と同じパターン） |
| **Amazon Bedrock** | ドキュメント（PDF、TXT 等） | 読み取り（Knowledge Base） | ✅ 検証済み | AP を指す S3 データソース付き Bedrock Knowledge Base | RAG アプリケーション用。ドキュメントが検索用にインデックス化 |

## パフォーマンス特性

**重要**: FSx for ONTAP S3 Access Points 経由の S3 API アクセスは、**ネイティブ S3 のパフォーマンスと同等ではありません**。パフォーマンスは FSx ファイルシステムのプロビジョンドスループット容量に依存します。

| 特性 | FSx S3 Access Point | ネイティブ S3 |
|------|--------------------:|-------------:|
| レイテンシ | 数十ミリ秒 | 一桁ミリ秒 |
| スループット | FSx プロビジョンドスループットに制限 | 事実上無制限（プレフィックスでスケール） |
| リクエスト/秒 | FSx プロビジョンドスループットに制限 | プレフィックスあたり GET 5,500/s、PUT 3,500/s |
| 最大オブジェクトサイズ（アップロード） | 5 GB | 5 TB |
| 同時リーダー | FSx スループット容量に制限 | 高度に並列化可能 |

ソース: [Amazon FSx for NetApp ONTAP のパフォーマンス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)、[S3 アクセスポイント経由でのデータアクセス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)

### スループット計画

FSx S3 Access Points 上の分析ワークロードを計画する際：

1. **ピークスキャン量の特定**: 例: 100 GB テーブルスキャン
2. **許容クエリ時間の決定**: 例: 60 秒未満
3. **必要スループットの計算**: 100 GB / 60s ≈ 1.7 GB/s 読み取りスループット
4. **適切なプロビジョニング**: 要件を満たす FSx スループット容量を選択

注: 書き込み操作はネットワーク帯域幅を 2 倍消費します（Multi-AZ でセカンダリファイルサーバーにレプリケーション）。

## プラットフォーム別必要 IAM 権限

| プラットフォーム | アクセスポイント ARN に対する必要 IAM アクション |
|---------------|----------------------------------------------|
| Athena（Glue 経由） | `s3:GetObject`、`s3:ListBucket`（AP ARN および AP ARN/object/*） |
| Glue Crawler | `s3:GetObject`、`s3:ListBucket`（AP ARN） |
| Glue ETL（読み書き） | `s3:GetObject`、`s3:PutObject`、`s3:DeleteObject`、`s3:ListBucket` |
| EMR Serverless | `s3:GetObject`、`s3:PutObject`、`s3:ListBucket`、`s3:DeleteObject` |
| Databricks | `s3:GetObject`、`s3:PutObject`、`s3:ListBucket`、`s3:DeleteObject`、`s3:GetBucketLocation` |
| Snowflake | `s3:GetObject`、`s3:ListBucket`、`s3:GetBucketLocation` |
| Bedrock Knowledge Base | `s3:GetObject`、`s3:ListBucket` |

加えて、アクセスポイントに関連付けられた**ファイルシステムユーザー**が、ボリューム上のファイルとディレクトリに対する適切な UNIX/NTFS 権限を持つ必要があります。

## Snapshot vs. Lakehouse Time Travel

詳細な比較は [リカバリセマンティクス](recovery-semantics.md) を参照してください。

## 参考資料

- [アクセスポイントの互換性 — サポートされる S3 API 操作](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [アクセスポイントアクセスの管理 — 二層認可](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)
- [Amazon FSx for NetApp ONTAP のパフォーマンス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
- [AWS サービスでのアクセスポイント利用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [Amazon Athena で SQL によるファイルクエリ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
