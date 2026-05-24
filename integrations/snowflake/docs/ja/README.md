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

| ONTAP 機能 | Snowflake へのメリット |
|-----------|---------------------|
| FlexClone | 本番データを使った即時ステージング環境 |
| Snapshot | Snowflake Time Travel 保持期間を超えたデータ復旧 |
| FabricPool | 過去パーティションの自動階層化（Snowflake に透過的） |
| 重複排除 | 類似ファイルバージョンのストレージ削減 |
| SnapMirror | Snowflake レプリケーション向けクロスリージョンデータ可用性 |
| FPolicy | イベント駆動 Snowpipe 取り込み（<30秒レイテンシ） |
| マルチプロトコル | NFS（取り込み）+ S3 AP（Snowflake）— 同一データ、コピー不要 |

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
