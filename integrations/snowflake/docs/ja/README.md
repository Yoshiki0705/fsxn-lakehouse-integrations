# Snowflake 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 検証済み（`AWS_ACCESS_POINT_ARN` 使用）**
>
> Snowflake は `AWS_ACCESS_POINT_ARN` ステージパラメータを使用して FSx for ONTAP S3 Access Point のデータをクエリできます。
> このパラメータを設定すると、SELECT、External Table 作成、LIST が全て動作します。
> 設定しない場合、LIST は動作しますが SELECT は "access denied" で失敗します。

## 検証結果

| 操作 | `AWS_ACCESS_POINT_ARN` なし | `AWS_ACCESS_POINT_ARN` あり |
|---|:---:|:---:|
| Storage Integration | ✅ | ✅ |
| ステージ作成 | ✅ | ✅ |
| LIST @stage | ✅ | ✅ |
| SELECT @stage (Parquet) | ❌ Access Denied | ✅ |
| SELECT @stage (CSV) | ❌ | ✅ |
| External Table | ❌ | ✅ |
| COPY INTO (ロード) | ❌ | ✅ |
| ガバナンスタグ | N/A | ✅ |
| Snowpipe (自動取り込み) | ❌ | ❌ (S3 Event Notifications 非サポート) |
| Iceberg Table 書き込み | ❌ | ❌ (conditional writes 非サポート) |
| GET_PRESIGNED_URL | ✅ (動作確認済み) | ✅ |

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）の S3 Access Point を Snowflake の External Stage として統合し、External Table / Iceberg Table のストレージレイヤーとして使用するパターンです。

## アーキテクチャ

```
┌───────────────────────────────────────────────────────────────────────┐
│                              AWS アカウント                             │
│                                                                       │
│  ┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐  │
│  │ FSx for ONTAP   │     │ FSx for ONTAP    │     │ IAM ロール     │  │
│  │ (NFS ボリューム)  │◀───▶│ S3 Access Point  │◀────│ (Snowflake    │  │
│  │                 │     │ (Internet origin) │     │  AssumeRole)  │  │
│  └─────────────────┘     └────────┬─────────┘     └───────┬───────┘  │
│                                    │                        │         │
└────────────────────────────────────┼────────────────────────┼─────────┘
                                     │ S3 API                 │ STS
                                     ▼                        ▼
                          ┌────────────────────────────────────────────┐
                          │  Snowflake (SaaS — ap-northeast-1)         │
                          │                                            │
                          │  Storage Integration → External Stage      │
                          │       → External Table / Iceberg Table     │
                          │       → Snowpipe (FPolicy + SNS 経由)       │
                          └────────────────────────────────────────────┘
```

## データフォーマット対応

| フォーマット | 読み取り | 書き込み | テーブルタイプ |
|------------|---------|---------|-------------|
| Parquet | ✅ | ✅ | External Table / Iceberg |
| CSV | ✅ | ✅ | External Table |
| JSON | ✅ | ✅ | External Table |
| ORC | ✅ | ❌ | External Table |
| Avro | ✅ | ❌ | External Table |

## 非構造化データ対応

| フォーマット | アクセス方法 | ユースケース |
|------------|------------|------------|
| 画像 (JPEG, PNG, TIFF) | GET_PRESIGNED_URL / BUILD_SCOPED_FILE_URL | サムネイル生成、ML 推論、品質検査 |
| 動画 (MP4, MOV) | GET_PRESIGNED_URL | ストリーミング、フレーム抽出 |
| ドキュメント (PDF, DOCX) | GET_PRESIGNED_URL / Snowpark File Access | テキスト抽出、RAG、文書処理 |
| 音声 (WAV, MP3) | GET_PRESIGNED_URL | 文字起こし、音声分析 |
| バイナリ / アーカイブ | GET_PRESIGNED_URL | ダウンロード、転送 |

**非構造化データへのアクセス方法:**
1. **Directory Table** — ファイルのメタデータ（パス、サイズ、更新日時）をカタログとして管理
2. **GET_PRESIGNED_URL()** — アプリケーション向けの期限付きダウンロード URL を生成
3. **BUILD_SCOPED_FILE_URL()** — Snowflake 経由のセキュアな URL を生成
4. **Snowpark File Access** — UDF/UDTF 内でファイルを直接処理（要検証）

```sql
-- Directory Table を有効化してファイルカタログとして使用
ALTER STAGE fsxn_stage SET DIRECTORY = (ENABLE = TRUE);
ALTER STAGE fsxn_stage REFRESH;

-- ファイルカタログをクエリ
SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED FROM DIRECTORY(@fsxn_stage);

-- ダウンロード URL を生成（1時間有効）
SELECT GET_PRESIGNED_URL(@fsxn_stage, 'images/photo001.jpg', 3600);
```

> **注意**: FSx S3 AP は S3 Event Notifications をサポートしていないため、AUTO_REFRESH は使用できません。`ALTER STAGE REFRESH` を手動または Snowflake Task でスケジュール実行してください。

## ONTAP の価値

| ONTAP 機能 | Snowflake へのメリット | リファレンス |
|---|---|---|
| **FlexCache** | リージョン/拠点間でデータをキャッシュし低遅延の Snowflake アクセスを実現。WAN 帯域を削減 | [FlexCache ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) |
| **SnapLock / Tamperproof Snapshot** | コンプライアンス向け不変データ保護 — 管理者権限でも保持期間中は削除不可 | [SnapLock on FSx](https://netapp.com/blog/snaplock-on-amazon-fsx-ontap/) |
| **ARP/AI** | AI によるランサムウェア検知。分析データへの被害拡大前に自動スナップショット | [ARP on FSx](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/ARP.html) |
| **FlexClone** | 本番データを使った即時ステージング環境（ゼロコピー） | [FlexClone ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| **Snapshot** | Snowflake Time Travel 保持期間を超えたデータ復旧。データパイプラインのバージョン管理 | [Snapshot ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| **FabricPool** | 過去パーティションの S3 自動階層化（Snowflake クエリに透過的） | [FabricPool ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fabricpool.html) |
| **ストレージ効率化** | 重複排除 + 圧縮 + コンパクションでファイルデータを最大 65% 削減 | [ストレージ効率](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-efficiency.html) |
| **SnapMirror** | Snowflake レプリケーションと DR 向けクロスリージョンデータ可用性 | [SnapMirror ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html) |
| **マルチプロトコル** | NFS（取り込み）+ SMB（Windows ユーザー）+ S3 AP（Snowflake）— 同一データ、コピー不要 | [マルチプロトコル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| **FPolicy** | Lambda 経由のイベント駆動 Snowpipe 取り込み（<30秒レイテンシ） | [FPolicy ドキュメント](https://docs.netapp.com/us-en/ontap/nas-audit/fpolicy-config-types-concept.html) |

## ガバナンス & AI/ML ガイド

| ガイド | 説明 |
|---|---|
| [AI/ML デモガイド](ai-demo-guide.md) | Cortex AI デモ（OCR、SUMMARIZE、Vision）、業界別ユースケース、AI 向け ONTAP 価値 |
| [ガバナンス: タグとデータ保護](ai-demo-guide.md#ガバナンスタグとデータ保護) | Tag-based masking、Row Access Policy、エディション要件 |
| [ガバナンス: ファイルレベルアクセス制御](ai-demo-guide.md#ファイルレベルのアクセス制御-ontap-ネイティブレイヤー) | ONTAP デュアルレイヤー認可、FPolicy、コンシューマーごとの S3 AP 分離 |
| [統合: ONTAP × Snowflake タグ](ai-demo-guide.md#統合-ontap-ファイルレベル制御--snowflake-タグガバナンス) | 組み合わせガバナンスマトリクス、設計パターン、フロー図 |

## クイックスタート

```bash
# 1. FSx for ONTAP S3 Access Point を作成（前提条件）
aws fsx create-and-attach-s3-access-point \
  --name snowflake-ap --type ONTAP \
  --ontap-configuration 'VolumeId=fsvol-xxx,FileSystemIdentity={Type=UNIX,UnixUser={Name=root}}'

# 2. CloudFormation で IAM ロールをデプロイ
cp params.example.json params.json  # 編集: S3AccessPointArn を設定
./deploy.sh

# 3. Snowflake で SQL スクリプトを実行 (01 → 09)
```

## 既知の制限事項

1. **FSx for ONTAP S3 AP レイテンシ**: ListObjects に数十秒〜数分かかる場合がある
2. **Pre-signed URL**: AWS ドキュメントでは「非サポート」だが、実際には `GET_PRESIGNED_URL()` で動作確認済み
3. **S3 Event Notifications 非サポート**: Snowpipe の直接トリガー不可（FPolicy で代替）
4. **最大アップロードサイズ**: 5GB（Multipart Upload 対応）
5. **AUTO_REFRESH 不可**: 手動 REFRESH または Snowflake Task でスケジュール実行が必要
