# 互換性マトリクス

## 概要

本ドキュメントは、FSx for ONTAP S3 Access Points と Lakehouse プラットフォーム/フォーマット間の検証済み互換性を定義します。マトリクスは [アクセスポイントの互換性](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) に記載された、FSx for ONTAP アクセスポイントがサポートする S3 API 操作に基づいています。

## FSx for ONTAP S3 Access Points の重要な制約

互換性マトリクスを確認する前に、以下の基本的な制約を理解してください：

| 制約 | 詳細 | ソース |
|------|------|--------|
| Rename 操作なし | S3 API にはネイティブの rename がない。CopyObject は同一アクセスポイント内のみサポート。 | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| 最大アップロードサイズ: 5 GB | 単一オブジェクトのアップロードは 5 GB まで（マルチパートアップロードはサポート） | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Object Versioning なし | S3 Object Versioning は非サポート | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| 条件付き書き込みなし | Conditional writes は非サポート（`NotImplemented` を返す） | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Presigned URLs: 公式には非サポート | Presigning はクライアント側の署名計算であり、サーバー側の操作ではない。サポートされている操作（例: GetObject）の Presigned URLs は、サーバーが標準の署名付きリクエストとして認識するため実際には動作する。ただし、AWS はこれを「非サポート」としており、安定性を保証していない。**本番環境では依存しないこと。** | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)、[AWS Support Case 177943289700029](verified 2026-05-22) |
| ListObjectVersions: 公式には非サポート | VersionId="null" で結果を返す（バージョニング未設定の S3 バケットと同じ動作）。機能的には ListObjectsV2 をバージョニングスキーマでラップしたものと同等。AWS は「非サポート」としている — **代わりに ListObjectsV2 を使用すること。** | [API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)、[AWS Support Case 177943289700029](verified 2026-05-22) |
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
| ✅ 検証済み (Verified) | テスト済みで動作確認 |
| ⚠️ 実験的 (Experimental) | 既知の制限付きで部分的に動作 |
| ❌ 非サポート (Not Supported) | 基本的な制約により動作しない |
| 🔲 計画中 (Planned) | 未テスト |

### マトリクス

| プラットフォーム | フォーマット | モード | ステータス | 必要な設定 | 既知の制限 |
|---------------|-----------|------|----------|-----------|-----------|
| **Amazon Athena** | Parquet | 読み取り専用 | ✅ 検証済み | Internet-origin AP、Glue Catalog、AP ARN に対する s3:GetObject/ListBucket の IAM ロール | Athena は VPC-origin AP を使用不可（VPC 外のマネージドインフラからアクセス）。結果は別の S3 バケットに書き込まれ、FSx には戻らない。 |
| **Amazon Athena** | CSV | 読み取り専用 | ✅ 検証済み | Parquet と同じ | 同上 |
| **Amazon Athena** | JSON | 読み取り専用 | ✅ 検証済み | Parquet と同じ | 同上 |
| **Amazon Athena** | ORC | 読み取り専用 | ✅ 検証済み | Parquet と同じ | 同上 |
| **Amazon Athena** | Delta Lake | 読み取り専用（symlink manifest） | ⚠️ 実験的 | Athena Delta Lake コネクタ、symlink_format_manifest の事前生成が必要 | Delta ログの直接読み取り不可。事前生成マニフェストが必要。Write/MERGE 非サポート。 |
| **Amazon Athena** | Iceberg | 読み取り専用 | 🔲 計画中 | Athena Iceberg コネクタ、Glue Catalog を Iceberg カタログとして使用 | 読み取りパスは動作見込み。書き込みパスは未テスト。 |
| **AWS Glue ETL** | Parquet | 読み取り | ✅ 検証済み | AP 権限付き Glue IAM ロール、S3 パスに AP エイリアス | — |
| **AWS Glue ETL** | Parquet | 書き込み（Append） | ✅ 検証済み | AP に読み書きファイルシステムユーザー | ファイルあたり最大 5 GB |
| **AWS Glue ETL** | Parquet | 上書き (Overwrite) | ⚠️ 実験的 | 読み書きファイルシステムユーザー | DeleteObject + PutObject パターン。アトミックな上書き保証なし |
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

ソース: [Amazon FSx for NetApp ONTAP のパフォーマンス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)、[Amazon S3 アクセスポイント経由でのデータアクセス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)

### スループット計画

FSx S3 Access Points 上の分析ワークロードを計画する際：

1. **ピークスキャン量の特定**: 例: 100 GB テーブルスキャン
2. **許容クエリ時間の決定**: 例: 60 秒未満
3. **必要スループットの計算**: 100 GB / 60s ≈ 1.7 GB/s 読み取りスループット
4. **適切なプロビジョニング**: 要件を満たすか超える FSx スループット容量を選択

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

---

## 検証レベルの定義

| レベル | 定義 | テスト内容 | 本番環境への信頼度 |
|--------|------|-----------|-------------------|
| **API 検証済み** | 基本的な S3 API 操作が FSx S3 AP に対して成功 | GetObject/PutObject/ListObjectsV2 が期待通りの結果を返す | 低 — API 互換性の確認のみ |
| **機能検証済み** | 代表的なエンドツーエンドのユースケースが成功 | 完全なワークフロー: データアップロード → カタログ登録 → クエリ → 正しい結果 | 中 — パターンの動作を確認 |
| **セキュリティ検証済み** | IAM、AP ポリシー、VPC エンドポイント、ファイルシステム権限、CloudTrail すべて確認 | 両レイヤーで不正アクセスが拒否される。監査イベントが記録される | 高 — セキュリティ態勢を確認 |
| **本番検証済み** | 顧客 PoC または本番相当の負荷テスト済み | 同時クエリ、障害復旧、コスト検証、SLA 準拠 | 最高 — 本番提案に対応可能 |

### 現在の検証ステータス

| プラットフォーム + モード | 検証レベル | 備考 |
|------------------------|-----------|------|
| Athena + Parquet 読み取り | セキュリティ検証済み | AWS 公式チュートリアルが IAM を含む完全なワークフローを検証 |
| Glue ETL + Parquet 読み取り/書き込み | 機能検証済み | AWS 公式チュートリアルが読み取りと書き戻しを検証 |
| EMR Serverless + Parquet 読み取り/書き込み | 機能検証済み | AWS 公式チュートリアルが Spark ワークフローを検証 |
| Bedrock Knowledge Base + ドキュメント読み取り | 機能検証済み | AWS 公式チュートリアルが RAG インジェストを検証 |
| Databricks + Parquet 読み取り | API 検証済み | External Location の登録と読み取りを確認 |
| Snowflake + Parquet 読み取り | API 検証済み | External Stage の作成とクエリを確認 |
| Delta Lake 書き込み（全プラットフォーム） | 非サポート | 基本的な制約（アトミック rename なし） |

---

## Lakehouse コミットプロトコルシーケンス

### なぜこれが重要か

Lakehouse テーブルフォーマットはトランザクション保証のために特定の S3 動作を必要とします。コミットプロトコルを理解することで、FSx S3 AP 上で一部の操作が動作し、他が動作しない理由が説明できます。

### Delta Lake 書き込みパス（FSx S3 AP では非サポート）

```
Writer                          S3 (or FSx S3 AP)
  │                                    │
  │  1. Write data files               │
  │  ──── PutObject(part-00000.parquet)──▶│  ✅ Supported
  │                                    │
  │  2. Write commit JSON              │
  │  ──── PutObject(_delta_log/tmp/...)──▶│  ✅ Supported
  │                                    │
  │  3. ATOMIC RENAME commit file      │
  │  ──── Rename(tmp/... → 00001.json)──▶│  ❌ NOT SUPPORTED
  │                                    │     (No rename operation in S3 API)
  │  Fallback: CopyObject + Delete     │
  │  ──── CopyObject(tmp → 00001.json)─▶│  ⚠️ Supported (same AP only)
  │  ──── DeleteObject(tmp/...)────────▶│  ✅ Supported
  │                                    │
  │  4. Verify commit (conditional)    │
  │  ──── If-None-Match check ────────▶│  ❌ NOT SUPPORTED
  │                                    │     (No conditional writes)
  └────────────────────────────────────┘

RESULT: Without atomic rename AND conditional writes, Delta Lake cannot
guarantee exactly-once commit semantics. Concurrent writers may corrupt
the transaction log. DO NOT USE for production writes.
```

### Apache Iceberg と外部カタログ（FSx S3 AP での実験的読み取り）

```
Writer                    Glue Catalog           FSx S3 AP
  │                           │                      │
  │  1. Write data files      │                      │
  │  ──── PutObject(data/...) ──────────────────────▶│  ✅ Supported
  │                           │                      │
  │  2. Write metadata file   │                      │
  │  ──── PutObject(metadata/snap-N.avro) ─────────▶│  ✅ Supported
  │                           │                      │
  │  3. Update catalog pointer│                      │
  │  ──── UpdateTable(metadata_location) ──▶│        │
  │                           │  ✅ Catalog          │
  │                           │  manages pointer     │
  │                           │  (no rename needed)  │
  │                           │                      │
  │  4. Reader queries        │                      │
  │       GetTable() ────────▶│                      │
  │       ◀── metadata_location                      │
  │       GetObject(snap-N.avro) ──────────────────▶│  ✅ Supported
  │       GetObject(data/...) ─────────────────────▶│  ✅ Supported
  └───────────────────────────┴──────────────────────┘

RESULT: Iceberg with external catalog (Glue) does NOT require rename
for commit. The catalog atomically updates the metadata pointer.
READ PATH works. WRITE PATH is theoretically possible but untested
for concurrent writers and compaction on FSx S3 AP.
```

### 読み取り専用分析パス（FSx S3 AP で検証済み）

```
Athena/Glue/EMR           Glue Catalog           FSx S3 AP
  │                           │                      │
  │  1. Get table metadata    │                      │
  │  ──── GetTable() ────────▶│                      │
  │  ◀── location: s3://ap-alias/path/              │
  │                           │                      │
  │  2. List data files       │                      │
  │  ──── ListObjectsV2(prefix) ──────────────────▶│  ✅ Supported
  │  ◀── file list                                   │
  │                           │                      │
  │  3. Read data files       │                      │
  │  ──── GetObject(file1.parquet) ────────────────▶│  ✅ Supported
  │  ──── GetObject(file2.parquet) ────────────────▶│  ✅ Supported
  │  ◀── data                                        │
  │                           │                      │
  │  4. Return query results  │                      │
  └───────────────────────────┴──────────────────────┘

RESULT: Read-only analytics is the safest and most verified pattern.
No rename, no conditional writes, no concurrent writer conflicts.
```

---

## ワークロード別パフォーマンス特性

| ワークロード | 典型的なパターン | ボトルネック | 推奨 FSx 構成 | ファイルサイズガイダンス | 同時実行数 | 検証ステータス |
|------------|----------------|------------|--------------|---------------------|-----------|--------------|
| **大規模シーケンシャルスキャン**（Athena フルテーブル） | 少数の大きな読み取り、高スループット | FSx ネットワークスループット | プロビジョンドスループット ≥ 1 GB/s | ファイルあたり ≥ 128 MB（Parquet/ORC） | 低〜中（1-10 クエリ） | 機能検証済み |
| **小ファイル / メタデータ多用**（多数の小さな CSV） | 多数の ListObjectsV2 + 小さな GetObject | リクエストレート、レイテンシ | IOPS ヘッドルーム用に高スループット | ≥ 32 MB に統合 | 低 | API 検証済み |
| **高同時実行 Athena**（多数のアナリスト） | 同一データへの並列スキャン | FSx 集約スループット | 同時負荷に合わせてスループットをスケール | スキャン削減のためデータをパーティション化 | 高（10-50 クエリ） | 未検証 |
| **Glue ETL 読み取り多用**（バッチ変換） | シーケンシャルな大量読み取り + 書き戻し | FSx 読み取りスループット | プロビジョンド ≥ 512 MB/s | ファイルあたり ≥ 128 MB | 低（1-5 ジョブ） | 機能検証済み |
| **Spark 書き込み多用**（ETL 出力） | 多数の PutObject 呼び出し | FSx 書き込みスループット（帯域幅 2 倍） | 書き込み多用には ≥ 1 GB/s | 出力ファイル 128-256 MB を目標 | 低 | 機能検証済み |
| **RAG ドキュメントインジェスト**（Bedrock） | 多数の小〜中 GetObject | ドキュメントあたりのレイテンシ | 標準スループットで十分 | N/A（ドキュメントサイズは様々） | 低（バッチインジェスト） | 機能検証済み |

### パフォーマンス計画の計算式

```
Required FSx Throughput = max(
  Read workload:  (Total scan size / Acceptable query time),
  Write workload: (Total write size / Acceptable job time) × 2,  # 2x for Multi-AZ replication
  Concurrent load: Sum of all concurrent workload throughput needs
)
```

---

## 障害シナリオ FAQ

### Q: ONTAP Snapshot リストア後に何が起こるか？

**A**: Snapshot リストアはボリューム上のすべてのファイルをスナップショット時点に戻します。影響：
- **Glue Catalog**: カタログメタデータは FSx ボリューム上にないため、変更されません。これによりミスマッチが発生します：カタログがもう存在しないファイルを参照する（スナップショット後に追加された場合）、またはリストアされたファイルを見逃す可能性があります。
- **必要なアクション**: Snapshot リストア後に Glue Crawler を再実行し、カタログを実際のファイル状態と整合させます。
- **Athena クエリ**: カタログが更新されるまで "file not found" で失敗する可能性があります。

### Q: S3 Access Point ポリシーが誤って変更された場合に何が起こるか？

**A**: アクセスポイントポリシーの変更は即座に有効になります。
- **ポリシーが制限的になりすぎた場合**: AP 経由のすべてのリクエストが拒否されます。既存のクエリは AccessDenied で失敗します。
- **ポリシーが緩くなりすぎた場合**: 不正なプリンシパルがアクセスを取得する可能性があります（ファイルシステムユーザー権限が第二レイヤーとして緩和）。
- **復旧**: S3 コンソール/CLI/API で AP ポリシーを更新します。変更は即座に反映されます。AP の再作成は不要です。
- **予防**: SCP を使用して AP ポリシーを変更できるユーザーを制限します。CloudTrail を有効にして変更を検出します。

### Q: Spark/Glue ジョブが書き込み中に失敗した場合に何が起こるか？

**A**: 部分的なファイルが FSx ボリュームに残る可能性があります。
- **Parquet append**: 孤立した部分ファイルが存在しますが、カタログから参照されません。手動でクリーンアップしても安全です。
- **Delta write（試行した場合）**: トランザクションログが不整合な状態になる可能性があります。これが Delta write が非サポートである理由です。
- **復旧**: S3 API（DeleteObject）または NFS/SMB で孤立ファイルを削除します。ジョブを再実行します。
- **注**: FSx S3 AP は自動クリーンアップのための Object Lifecycle ルールをサポートしていません。

### Q: Bedrock がインジェスト中に NFS 経由でファイルが更新された場合に何が起こるか？

**A**: FSx for ONTAP はファイルシステム内で read-after-write 一貫性を提供します。
- **NFS 書き込み中に Bedrock が読み取る場合**: タイミングによっては部分的/古いコンテンツを読み取る可能性があります。
- **ベストプラクティス**: ONTAP Snapshot を使用してインジェスト用の一貫したポイントインタイムビューを作成するか、既知の静止期間中にインジェストをスケジュールします。
- **注**: S3 AP の読み取りはファイルシステムの現在の状態を反映します — NFS 書き込みと S3 AP 読み取りの間に結果整合性の遅延はありません。

### Q: DR リージョンへの SnapMirror フェイルオーバー後に何が起こるか？

**A**: S3 Access Point はソースリージョンの元の FSx ファイルシステムにバインドされています。
- **AP ARN**: ソースリージョンに残ります。DR に自動的に転送されません。
- **必要なアクション**: DR リージョンの DR ボリュームに新しい S3 Access Point を作成します。すべての参照（Glue Catalog のロケーション、IAM ポリシー、アプリケーション設定）を新しい AP に更新します。
- **自動化**: DR ランブックに AP の再作成を含めます。再現可能なセットアップのために CloudFormation/Terraform を使用します。
- **注**: AP 名はリージョン間で再利用できますが、ARN は異なります。

### Q: AP に関連付けられたファイルシステムユーザーが削除された場合に何が起こるか？

**A**: アクセスポイントは `MISCONFIGURED` 状態に遷移します。
- **影響**: AP 経由のすべての S3 リクエストが失敗します。
- **復旧**: ファイルシステム上でユーザーを再作成するか、AP を別の有効なユーザーを使用するように更新します。
- **FSx の動作**: FSx は定期的にチェックし、ユーザー ID が再び解決可能になると AP を自動的に `AVAILABLE` に戻します。（[ソース](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)）

---

## 検証エビデンステンプレート

検証済みの各統合について、第三者による再現を可能にするために以下を記録します。

```yaml
# Verification Evidence Record
test_id: "ATHENA-PARQUET-READ-001"
date_tested: "YYYY-MM-DD"
tester: "<name>"

# Infrastructure
region: "ap-northeast-1"
fsxn_deployment_type: "MULTI_AZ_2"  # or SINGLE_AZ_1, etc.
fsxn_throughput_capacity_mbps: 512
ontap_version: "9.17.1"
svm_security_style: "UNIX"
volume_junction_path: "/vol1"

# Access Point Configuration
ap_network_origin: "INTERNET"  # or VPC
ap_file_system_user_type: "UNIX"
ap_file_system_user_name: "analytics_reader"
ap_file_system_user_uid: 1001
block_public_access: true  # always true, cannot be changed

# IAM Configuration
iam_role_arn: "arn:aws:iam::<ACCOUNT>:role/<ROLE_NAME>"
iam_actions_granted: ["s3:GetObject", "s3:ListBucket"]
ap_policy: "Allow s3:GetObject, s3:ListBucket for role"

# Test Dataset
dataset_format: "Parquet"
file_count: 10
average_file_size_mb: 128
total_dataset_size_gb: 1.28

# Service Configuration
service: "Amazon Athena"
service_version: "engine v3"
glue_catalog_database: "fsxn_test_db"
workgroup: "primary"

# Results
result: "PASS"
query_latency_p50_ms: 3200
query_latency_p95_ms: 5100
data_scanned_bytes: 1374389248
errors: []
known_limitations:
  - "Athena requires internet-origin AP"
  - "Query results written to separate S3 bucket, not FSx"
```

---

## セキュリティ検証基準

「セキュリティ検証済み」ステータスを主張するには、以下のすべてのテストに合格する必要があります：

| テスト | 期待される結果 | 方法 |
|--------|--------------|------|
| 認可されたロールが読み取り可能 | GetObject が成功 | `aws s3 cp s3://AP-ALIAS/test.parquet . --profile authorized` |
| 未認可のロールが拒否される | AccessDenied エラー | `aws s3 cp s3://AP-ALIAS/test.parquet . --profile unauthorized` |
| 明示的 Deny が Allow を上書き | ID の Allow があっても AccessDenied | AP ポリシーに明示的 Deny を追加し、許可されたロールでテスト |
| クロスアカウントアクセスが拒否される（明示的に許可されない限り） | AccessDenied | クロスアカウント許可なしで別アカウントからアクセス試行 |
| VPC-origin AP がインターネットアクセスをブロック | AccessDenied | バインドされた VPC 外からアクセス試行 |
| 読み取り専用ユーザーが書き込み不可 | PutObject で AccessDenied | `aws s3 cp local.txt s3://AP-ALIAS/ --profile readonly-ap-user` |
| 読み取り専用ユーザーが削除不可 | DeleteObject で AccessDenied | `aws s3 rm s3://AP-ALIAS/test.parquet --profile readonly-ap-user` |
| CloudTrail データイベントが記録される | CloudTrail にイベントあり | AP ARN に対する s3.amazonaws.com GetObject イベントを CloudTrail でクエリ |
| Block Public Access が適用される | パブリックポリシーを作成不可 | AP ポリシーにパブリックアクセス許可を追加試行 |

### セキュリティテスト実行記録

```yaml
security_test_id: "SEC-ATHENA-001"
date: "YYYY-MM-DD"
ap_arn: "arn:aws:s3:<REGION>:<ACCOUNT>:accesspoint/<NAME>"
tests_passed: 9
tests_failed: 0
tests_total: 9
evidence_location: "<link to test results>"
reviewer: "<security reviewer name>"
```

---

## 運用ランブック

### ランブック 1: Snapshot リストア後の Glue Catalog 修復

| フィールド | 値 |
|-----------|-----|
| **トリガー** | カタログ登録済みデータを含むボリュームで ONTAP Snapshot リストアが実行された |
| **検出** | Athena クエリが "file not found" または予期しない結果を返す |
| **オーナー** | データプラットフォームチーム |
| **影響** | 分析クエリが失敗するか、古い結果を返す可能性 |

**手順:**

1. **リストア完了を確認**: `aws fsx describe-volumes --volume-ids <vol-id>` → status = AVAILABLE
2. **影響を受けるテーブルを特定**: リストアされたボリュームの AP を指す Glue テーブルを一覧表示
3. **Glue Crawler を再実行**:
   ```bash
   aws glue start-crawler --name <crawler-name>
   aws glue get-crawler --name <crawler-name> --query "Crawler.State"
   # Wait until State = READY
   ```
4. **テーブルメタデータを検証**: `aws glue get-table --database-name <db> --name <table>` → カラムスキーマを確認
5. **検証クエリを実行**: Athena で既知の正常なクエリを実行し、結果を比較
6. **関係者に通知**: カタログが更新されたことを分析ユーザーに通知

**推定所要時間**: 10-15 分

---

### ランブック 2: 失敗した Spark/Glue ジョブ後の孤立ファイルクリーンアップ

| フィールド | 値 |
|-----------|-----|
| **トリガー** | Spark または Glue ETL ジョブが書き込み中に失敗 |
| **検出** | ジョブステータス = FAILED。ボリュームに孤立ファイルが表示される |
| **オーナー** | データエンジニアリングチーム |
| **影響** | ストレージの無駄。ファイルが部分的に書き込まれている場合の混乱の可能性 |

**手順:**

1. **失敗したジョブを特定**: `aws glue get-job-run --job-name <job> --run-id <run-id>` → エラーを確認
2. **孤立ファイルを一覧表示**: `aws s3 ls s3://<AP-ALIAS>/<output-prefix>/ --recursive` → ジョブ開始時刻以降に書き込まれたファイルを特定
3. **ファイルが参照されていないことを確認**: Glue Catalog を確認 — 孤立ファイルはどのテーブルのパーティションにも含まれていないこと
4. **孤立ファイルを削除**:
   ```bash
   aws s3 rm s3://<AP-ALIAS>/<output-prefix>/part-00000-<partial>.parquet
   ```
5. **ジョブを再実行**: 根本原因を修正し、再実行
6. **出力を検証**: 新しいジョブ実行が完全で正しい出力を生成することを確認

**推定所要時間**: 15-30 分

---

### ランブック 3: Access Point ポリシーのロールバック

| フィールド | 値 |
|-----------|-----|
| **トリガー** | AP ポリシーが誤って変更され、認可されたユーザーがアクセスを失う |
| **検出** | 以前動作していたクエリから AccessDenied エラー。CloudTrail に PutAccessPointPolicy が表示される |
| **オーナー** | セキュリティ / プラットフォームチーム |
| **影響** | AP 経由のすべての分析アクセスがブロックされる |

**手順:**

1. **ポリシー変更を確認**: CloudTrail で最近の `PutAccessPointPolicy` イベントを確認
2. **最後の正常なポリシーを取得**: IaC リポジトリ（CloudFormation/Terraform）またはバージョン管理から
3. **修正されたポリシーを適用**:
   ```bash
   aws s3control put-access-point-policy \
     --account-id <ACCOUNT> \
     --name <AP-NAME> \
     --policy file://correct-policy.json
   ```
4. **アクセス復旧を検証**: 認可されたロールでテスト
5. **根本原因を調査**: 誰がポリシーを変更したか？意図的だったか？
6. **再発防止**: SCP を追加して PutAccessPointPolicy を特定の管理者ロールに制限

**推定所要時間**: 5-10 分（IaC ポリシーが利用可能な場合）

---

### ランブック 4: SnapMirror フェイルオーバーと AP 再作成

| フィールド | 値 |
|-----------|-----|
| **トリガー** | ソースリージョンの障害。DR アクティベーションが必要 |
| **検出** | AWS Health Dashboard アラート。ソースリージョンへの接続が失われた |
| **オーナー** | インフラストラクチャ / DR チーム |
| **影響** | ソース AP 経由のすべての分析アクセスが利用不可 |

**手順:**

1. **SnapMirror フェイルオーバーをアクティベート**: SnapMirror 関係を解除し、DR ボリュームを読み書き可能に昇格
2. **DR リージョンに新しい S3 Access Point を作成**:
   ```bash
   aws fsx create-and-attach-s3-access-point \
     --name <AP-NAME> \
     --type ONTAP \
     --ontap-configuration "VolumeId=<DR-VOL-ID>,FileSystemIdentity={Type=UNIX,UnixUser={Name=<USER>}}" \
     --region <DR-REGION>
   ```
3. **AP が AVAILABLE になるまで待機**: `aws fsx describe-s3-access-points --region <DR-REGION>`
4. **Glue Catalog を更新**: テーブルのロケーションを新しい AP エイリアスに更新
5. **IAM ポリシーを更新**: リソース ARN を DR リージョンの新しい AP ARN に更新
6. **アプリケーション設定を更新**: 分析ツールを新しい AP に向ける
7. **検証**: DR AP に対してテストクエリを実行
8. **関係者に通知**: DR アクティベーションと新しいアクセス詳細を確認

**推定所要時間**: 30-60 分

---

## ベンチマーク方法論

### 標準ベンチマークスイート

| ベンチマーク | 測定内容 | 手順 |
|------------|---------|------|
| **大ファイルシーケンシャル読み取り** | 最大持続読み取りスループット | 10 × 1 GB Parquet ファイルをアップロード。フルテーブルに対して Athena `SELECT COUNT(*)` を実行。スキャンデータ量 / 時間を測定 |
| **小ファイルリスティング** | メタデータ操作パフォーマンス | 10,000 個の小ファイル（各 1 KB）を作成。`aws s3 ls --recursive` を実行。時間を測定 |
| **Athena クエリレイテンシ** | エンドツーエンドのクエリ時間 | 同一クエリを 10 回実行。P50、P95、P99 レイテンシを記録 |
| **Glue ETL スループット** | 読み取り + 変換 + 書き込み速度 | 10 GB を読み取り、変換し、書き戻す Glue ジョブを実行。合計時間を測定 |
| **同時クエリスケーリング** | 負荷下のスループット | 1、5、10、20 の同時 Athena クエリを実行。集約スループットを測定 |
| **Bedrock KB インジェスト** | ドキュメント処理速度 | 1,000 ドキュメント（平均 10 ページ）をインジェスト。合計インジェスト時間を測定 |

### ベンチマーク記録テンプレート

```yaml
benchmark_id: "BENCH-001"
date: "YYYY-MM-DD"
region: "<REGION>"

# FSx Configuration
fsxn_throughput_mbps: 512
fsxn_deployment_type: "MULTI_AZ_2"
fsxn_storage_gb: 1024

# Dataset
file_count: 10
avg_file_size_mb: 1024
total_size_gb: 10
file_format: "Parquet"
compression: "Snappy"

# Test Parameters
test_type: "large_file_sequential_read"
concurrency: 1
query: "SELECT COUNT(*) FROM test_table"
repetitions: 10

# Results
throughput_mbps: 480
latency_p50_ms: 21000
latency_p95_ms: 28000
latency_p99_ms: 32000
errors: 0
cost_usd: 0.05

# Analysis
throughput_vs_provisioned_pct: 94  # 480/512 = 94%
bottleneck: "FSx network throughput (near max)"
recommendation: "Sufficient for this workload"
```

---

## ネガティブテストマトリクス

セキュリティ態勢が有効であるために失敗しなければならない明示的なテスト。

| テスト ID | テスト説明 | 期待される結果 | 合格した場合の重大度 |
|----------|-----------|--------------|-------------------|
| NEG-001 | 読み取り専用ファイルシステムユーザーによる書き込み試行 | AccessDenied | Critical |
| NEG-002 | 読み取り専用ファイルシステムユーザーによる削除試行 | AccessDenied | Critical |
| NEG-003 | 明示的な許可なしのクロスアカウントアクセス | AccessDenied | Critical |
| NEG-004 | VPC-origin AP 設定時のインターネットオリジンアクセス | AccessDenied | Critical |
| NEG-005 | 5 GB 制限を超える PutObject | EntityTooLarge エラー | High |
| NEG-006 | Presigned URL の生成 | Not supported エラー | Medium |
| NEG-007 | Object Versioning 操作（ListObjectVersions） | Not supported | Medium |
| NEG-008 | IAM ロール取り消し後のアクセス | AccessDenied | Critical |
| NEG-009 | バインドされていない VPC からのアクセス（VPC-origin AP） | AccessDenied | Critical |
| NEG-010 | 条件付き書き込み（If-None-Match） | Not supported | Medium |

### ネガティブテストの実行

```bash
# NEG-001: Write attempt by read-only user
aws s3 cp test.txt s3://<AP-ALIAS>/test-write.txt --profile readonly-user
# Expected: upload failed: ... AccessDenied

# NEG-002: Delete attempt by read-only user
aws s3 rm s3://<AP-ALIAS>/existing-file.txt --profile readonly-user
# Expected: delete failed: ... AccessDenied

# NEG-003: Cross-account access
aws s3 ls s3://<AP-ALIAS>/ --profile cross-account-role
# Expected: An error occurred (AccessDenied)
```

---

## ランブック検証とロールバック条件

各運用ランブックには検証コマンドとロールバック基準が含まれます。

### ランブック 1 追加事項: Glue Catalog 修復

| フィールド | 値 |
|-----------|-----|
| **検証コマンド** | `aws athena start-query-execution --query-string "SELECT COUNT(*) FROM <db>.<table>" --work-group primary` |
| **期待される出力** | クエリが成功。行数が期待値と一致 |
| **ロールバック条件** | Crawler が失敗するか不正なスキーマを生成した場合、Glue バージョニングから以前のテーブルバージョンを復元 |
| **エスカレーション閾値** | 30 分以内に解決しない場合、データプラットフォームリードにエスカレーション |
| **顧客影響** | 解決するまで分析クエリがエラーまたは古いデータを返す |

### ランブック 2 追加事項: 孤立ファイルクリーンアップ

| フィールド | 値 |
|-----------|-----|
| **検証コマンド** | `aws s3 ls s3://<AP-ALIAS>/<prefix>/ --recursive \| wc -l`（カウントが期待値と一致） |
| **期待される出力** | 成功したジョブ実行のファイルのみが残る |
| **ロールバック条件** | 間違ったファイルを削除した場合、ONTAP Snapshot から復元 |
| **エスカレーション閾値** | どのファイルが孤立しているか不明な場合、削除前にエスカレーション |
| **顧客影響** | 孤立ファイルのみなら影響なし。間違ったファイルを削除した場合はデータ損失 |

### ランブック 3 追加事項: AP ポリシーロールバック

| フィールド | 値 |
|-----------|-----|
| **検証コマンド** | `aws s3 ls s3://<AP-ALIAS>/ --profile authorized-role`（成功） |
| **期待される出力** | ListObjectsV2 がエラーなしでファイルリストを返す |
| **ロールバック条件** | 修正されたポリシーでも失敗する場合、IAM ID ポリシーと VPC エンドポイントポリシーを確認 |
| **エスカレーション閾値** | 10 分以内に解決しない場合、セキュリティチームにエスカレーション |
| **顧客影響** | 解決するまですべての分析アクセスがブロックされる |

### ランブック 4 追加事項: SnapMirror フェイルオーバー

| フィールド | 値 |
|-----------|-----|
| **検証コマンド** | `aws s3 ls s3://<DR-AP-ALIAS>/ --region <DR-REGION>`（成功） |
| **期待される出力** | ファイルリストがソースボリュームの期待データと一致 |
| **ロールバック条件** | DR ボリュームのデータが RPO を超えて古い場合、続行前にデータ損失を評価 |
| **エスカレーション閾値** | 15 分以内に AP が AVAILABLE にならない場合、AWS サポートにエスカレーション |
| **顧客影響** | フェイルオーバーウィンドウ中は分析が利用不可（目標: 60 分未満） |

---

## ベンチマーク解釈ガイド

ベンチマーク結果が期待から逸脱した場合、このガイドを使用して診断します。

| 症状 | 考えられる原因 | 調査 | 解決策 |
|------|--------------|------|--------|
| 大規模スキャンが期待より遅い | FSx スループットが飽和 | CloudWatch `ThroughputUtilization` メトリクスを確認 | FSx プロビジョンドスループットを増加 |
| 大規模スキャンが期待より遅い | 小ファイル（< 32 MB） | 平均ファイルサイズを確認 | ファイルを ≥ 128 MB に統合 |
| 小ファイルリスティングが非常に遅い | プレフィックスあたりのファイル数が多い | プレフィックス内のオブジェクト数をカウント | パーティション化で再構成 / プレフィックスあたりのファイル数を削減 |
| Athena レイテンシが高い（1 GB で > 30 秒） | パーティション化されていないデータ | テーブルのパーティション化を確認 | パーティションカラムを追加。Parquet/ORC を使用 |
| Athena レイテンシが高い | CSV/JSON フォーマット | ファイルフォーマットを確認 | Parquet に変換（カラムナー、圧縮） |
| 同時クエリが劣化 | 集約スループットがプロビジョンドを超過 | 同時スループットの合計を確認 | FSx スループットを増加または同時実行数を削減 |
| Glue ETL 書き込みが遅い | 書き込み増幅（Multi-AZ で 2 倍） | 書き込みスループット vs プロビジョンドを確認 | 2 倍の書き込み帯域幅を考慮。スループットを増加 |
| Bedrock KB インジェストが遅い | 大きなドキュメントまたは複雑なチャンキング | ドキュメントサイズとチャンキング設定を確認 | チャンクサイズを最適化。大きなドキュメントを前処理 |
| 断続的なエラー | AP が MISCONFIGURED 状態 | `describe-s3-access-points` で AP ステータスを確認 | ファイルシステムユーザー ID の問題を解決 |
| スループットがプロビジョンドの 50% 未満 | クライアント側のボトルネック | クライアントネットワーク、SDK 設定を確認 | 並列リクエストを使用。SDK リトライ設定を確認 |

### パフォーマンス最適化チェックリスト

- [ ] ファイルフォーマット: Parquet または ORC（大規模スキャンには CSV/JSON ではなく）
- [ ] ファイルサイズ: シーケンシャルスキャンにはファイルあたり ≥ 128 MB
- [ ] パーティション化: スキャン範囲を削減するための日付/カテゴリパーティション
- [ ] FSx スループット: ピークワークロードに合わせてプロビジョニング
- [ ] 圧縮: Parquet には Snappy（高速）または ZSTD（小サイズ）
- [ ] 同時実行: 合計同時スループットがプロビジョンド制限内
- [ ] 書き込みバジェット: Multi-AZ 書き込みの 2 倍帯域幅を考慮

---

## 参考資料

- [アクセスポイントの互換性 — サポートされる S3 API 操作](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [アクセスポイントアクセスの管理 — 二層認可](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)
- [Amazon FSx for NetApp ONTAP のパフォーマンス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
- [AWS サービスでのアクセスポイント利用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [Amazon Athena で SQL によるファイルクエリ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
