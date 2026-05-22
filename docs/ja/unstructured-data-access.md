# 非構造化データアクセス（画像・動画・音声・ドキュメント）

🌐 [English](../en/unstructured-data-access.md)

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）の S3 Access Points は構造化データ（Parquet, CSV）だけでなく、
画像・動画・音声・ドキュメントなどの非構造化データへのアクセスも提供します。

エンタープライズのファイルサーバーに蓄積された非構造化データを、
データコピーなしで AI/ML サービスや分析プラットフォームから直接利用できます。

## アーキテクチャ

### パターン E: 非構造化データ処理

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  ┌──────────────┐                                                        │
│  │ NFS/SMB      │  ← ユーザーがファイルをアップロード                      │
│  │ クライアント  │    (画像、動画、ドキュメント)                            │
│  └──────┬───────┘                                                        │
│         │                                                                 │
│         ▼                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────────────────┐  │
│  │ FSx for      │     │ S3 Access    │     │ AI/ML サービス           │  │
│  │ ONTAP Volume │────▶│ Point        │────▶│                         │  │
│  │              │     │              │     │ • SageMaker (学習)       │  │
│  │ /images/     │     │              │     │ • Bedrock (RAG)         │  │
│  │ /videos/     │     │              │     │ • Rekognition (画像)    │  │
│  │ /documents/  │     │              │     │ • Transcribe (音声)     │  │
│  │ /audio/      │     │              │     │ • Lambda (処理)         │  │
│  └──────────────┘     └──────────────┘     └─────────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### パターン F: Lambda によるファイル処理パイプライン

```
FSx for ONTAP Volume (NFS/SMB)
    │
    └── S3 Access Point
            │
            ├── Lambda: サムネイル生成 (画像 → リサイズ → FSx for ONTAP に書き戻し)
            ├── Lambda: テキスト抽出 (PDF/DOCX → テキスト → FSx for ONTAP に書き戻し)
            ├── Lambda: 音声文字起こし (WAV/MP3 → Transcribe → テキスト)
            └── Lambda: メタデータ抽出 (EXIF, 動画長, ページ数)
```

参考: [AWS 公式チュートリアル - Lambda でファイルをサーバーレス処理](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html)

## 対応ファイル形式

### 画像

| 形式 | 拡張子 | ユースケース |
|------|--------|-------------|
| JPEG | .jpg, .jpeg | 写真、Web 画像 |
| PNG | .png | スクリーンショット、透過画像 |
| TIFF | .tif, .tiff | 医療画像、スキャン文書 |
| DICOM | .dcm | 医療画像（CT, MRI） |
| RAW | .raw, .cr2, .nef | プロフェッショナル写真 |

### 動画

| 形式 | 拡張子 | ユースケース |
|------|--------|-------------|
| MP4 | .mp4 | 汎用動画 |
| MOV | .mov | Apple 系動画 |
| AVI | .avi | レガシー動画 |
| MKV | .mkv | 高品質動画 |
| MPEG-TS | .ts | 監視カメラ、放送 |

### 音声

| 形式 | 拡張子 | ユースケース |
|------|--------|-------------|
| WAV | .wav | 高品質音声 |
| MP3 | .mp3 | 圧縮音声 |
| FLAC | .flac | ロスレス音声 |
| OGG | .ogg | オープン形式 |

### ドキュメント

| 形式 | 拡張子 | ユースケース |
|------|--------|-------------|
| PDF | .pdf | ビジネス文書 |
| DOCX | .docx | Word 文書 |
| XLSX | .xlsx | スプレッドシート |
| PPTX | .pptx | プレゼンテーション |
| TXT/MD | .txt, .md | テキストファイル |

## ユースケース別アーキテクチャ

### 1. AI/ML 学習データ（SageMaker + Bedrock）

```
研究者 → NFS マウント → FSx for ONTAP Volume → S3 AP → SageMaker Training Job
                         (画像データセット)               (モデル学習)

                                                       → Bedrock Knowledge Base
                                                         (RAG 用ドキュメント)
```

**ONTAP の価値:**
- **FlexClone**: 学習データセットの瞬時コピー（実験ごとに分離）
- **Snapshot**: 学習データのバージョン管理（再現性確保）
- **重複排除**: 類似画像データセットのストレージ効率化
- **階層化**: 古い学習データを自動的に S3 にティアリング

### 2. メディアアセット管理（Rekognition + MediaConvert）

```
カメラマン → SMB 共有 → FSx for ONTAP Volume → S3 AP → Rekognition (タグ付け)
                         (RAW 画像)                    → MediaConvert (変換)
                                                       → Lambda (サムネイル)
```

**ONTAP の価値:**
- **Snapshot**: 編集前のオリジナルを保護
- **SnapMirror**: 拠点間でのメディア同期
- **圧縮**: RAW ファイルのストレージ最適化
- **マルチプロトコル**: NFS (Linux) + SMB (Windows) + S3 (クラウド) 同時アクセス

### 3. ドキュメント処理パイプライン（Textract + Comprehend）

```
スキャナー → NFS → FSx for ONTAP Volume → S3 AP → Textract (OCR)
                    (PDF/TIFF)                    → Comprehend (NLP)
                                                  → OpenSearch (検索インデックス)
```

**ONTAP の価値:**
- **SnapLock**: コンプライアンス要件のある文書の WORM 保護
- **Snapshot**: 処理前後の文書状態を保持
- **重複排除**: 同一文書の複数バージョンを効率的に保存

### 4. 監視カメラ映像分析

```
カメラ → NFS → FSx for ONTAP Volume → S3 AP → Rekognition Video (分析)
               (MPEG-TS)                      → Kinesis Video (ストリーム)
                                              → Lambda (アラート)
```

**ONTAP の価値:**
- **FabricPool**: 古い映像を自動的に S3 Glacier にティアリング
- **Snapshot**: インシデント時点の映像を保護
- **大容量**: 数百 TB の映像データを効率的に管理

## 第三者プラットフォームでの非構造化データ利用

### Databricks + 非構造化データ

> ⚠️ **検証結果 (2026-05-17)**: Unity Catalog の session policy が FSx for ONTAP S3 Access Point の
> ARN 形式 (`arn:aws:s3:<region>:<account>:accesspoint/<name>`) を認識しないため、
> S3 AP 経由の直接アクセスは現時点でブロックされています。以下に回避策を含む全アプローチを記載します。

#### アプローチ 1: S3 AP + Unity Catalog External Location（❌ 現時点で非対応）

```python
# ❌ Unity Catalog session policy により 403 AccessDenied
# Databricks サポートに対応を依頼中
images_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.jpg") \
    .load(f"s3://{S3_AP_ALIAS}/images/")
```

**ブロッカー**: Unity Catalog が AssumeRole 時に適用する session policy に
FSx for ONTAP S3 AP の ARN が含まれていない。IAM Role 自体は `s3:*` on `*` でも、
session policy が制限する。

**追加の制約**:
- boto3 直接アクセスも不可（IMDS がブロックされ credentials 取得不可）
- Databricks managed VPC では VPC Peering 経由の NFS も到達不可
- AWS PrivateLink は FSx for ONTAP NFS には適用不可（サービスとして公開されていない）

#### アプローチ 2: Customer-managed VPC + NFS マウント（✅ 推奨）

FSx for ONTAP と同一 VPC に Databricks を Customer-managed VPC でデプロイし、NFS 直接マウント:

**前提条件:**
- Databricks Workspace を Customer-managed VPC で作成（FSx for ONTAP と同一 VPC）
- クラスタを Dedicated (Single user) モードで作成（sudo 権限が必要）
- Init Script で NFS マウントを自動化

```bash
# Init Script (クラスタ起動時に実行)
#!/bin/bash
sudo apt-get install -y nfs-common
sudo mkdir -p /mnt/fsxn
sudo mount -t nfs -o nfsvers=3 <FSx-DATA-IP>:/vol1 /mnt/fsxn
```

```python
# ノートブックでの非構造化データ処理
import os
from PIL import Image
from io import BytesIO

# ファイル一覧取得
image_files = [f for f in os.listdir("/mnt/fsxn/images/") if f.endswith(".jpg")]
print(f"Found {len(image_files)} images")

# 画像メタデータ抽出
for fname in image_files[:5]:
    img = Image.open(f"/mnt/fsxn/images/{fname}")
    print(f"  {fname}: {img.width}x{img.height}, {img.format}")

# ドキュメントテキスト抽出
import pypdf
reader = pypdf.PdfReader("/mnt/fsxn/documents/report.pdf")
text = "\n".join(page.extract_text() for page in reader.pages)
print(f"Extracted {len(text)} characters from PDF")
```

**前提条件:**
- VPC Peering: Databricks VPC ↔ FSx for ONTAP VPC
- セキュリティグループ: NFS (TCP 2049, 111) を許可
- Init Script: クラスタ起動時に NFS マウント実行

**利点:**
- Unity Catalog session policy の制約を受けない
- 通常のファイルシステムとして読み書き可能
- S3 AP 不要（NFS 直接アクセス）
- 全ファイル形式に対応

**制約:**
- VPC Peering のネットワーク設定が必要
- Spark の分散処理には不向き（ドライバーノードのローカルファイルとして扱う）
- Init Script の管理が必要

#### アプローチ 3: Instance Profile + boto3（🔲 検証予定）

クラスタに Instance Profile を設定し、boto3 で S3 AP に直接アクセス:

```python
import boto3
from PIL import Image
from io import BytesIO

# Instance Profile の credentials を使用
s3 = boto3.client("s3", region_name="ap-northeast-1")
bucket = "<S3_AP_ALIAS>"

# 画像ファイル読み取り
obj = s3.get_object(Bucket=bucket, Key="images/photo001.jpg")
img = Image.open(BytesIO(obj["Body"].read()))
print(f"Image: {img.width}x{img.height}, {img.format}")

# 処理結果の書き戻し
thumbnail = img.copy()
thumbnail.thumbnail((200, 200))
buf = BytesIO()
thumbnail.save(buf, format="JPEG")
s3.put_object(Bucket=bucket, Key="thumbnails/photo001_thumb.jpg", Body=buf.getvalue())
```

**前提条件:**
- Instance Profile を Databricks ワークスペースに登録
- クラスタに Instance Profile を設定
- Instance Profile の IAM Role に S3 AP アクセス権限

**制約:**
- Unity Catalog 有効クラスタでは Instance Profile が制限される場合あり
- Spark DataFrame としての処理には別途設定が必要

### Snowflake + 非構造化データ

```sql
-- Snowflake Directory Table で非構造化ファイルのメタデータ管理
CREATE OR REPLACE STAGE MEDIA_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/media/'
  DIRECTORY = (ENABLE = TRUE AUTO_REFRESH = FALSE);

-- ファイル一覧の取得
SELECT * FROM DIRECTORY(@MEDIA_STAGE);

-- Pre-signed URL の生成（外部アプリケーション用）
-- NOTE: AWS ドキュメントでは Presign は「非サポート」と記載されていますが、
-- テストにより FSx for ONTAP S3 AP で GET_PRESIGNED_URL が動作することを確認しています。
SELECT GET_PRESIGNED_URL(@MEDIA_STAGE, 'images/photo001.jpg', 3600);
```

**制約:**
- Snowflake は非構造化データを直接クエリできない
- Directory Table でメタデータ管理
- **Pre-signed URL は FSx for ONTAP S3 AP で動作する**（AWS ドキュメントでは「非サポート」と記載されているが、実際には動作確認済み）
- Snowpark で Python UDF を使った画像処理は可能

### Dremio + 非構造化データ

- Dremio は主に構造化/半構造化データ向け
- 非構造化データのメタデータ（パス、サイズ、更新日時）をカタログ化可能
- 実際のファイル処理は外部サービスに委譲

## 考慮事項と制約

### S3 API の制約

| 制約 | 影響 | 回避策 |
|------|------|--------|
| S3 Select 非対応 | ファイル内の部分読み取り不可 | 全ファイルダウンロード後に処理 |
| Event Notification 非対応 | 新ファイル検出が即時でない | Lambda ポーリング（1-5分間隔） |
| Object Lock 非対応 | S3 レベルの WORM 不可 | ONTAP SnapLock で代替 |
| 最大オブジェクトサイズ | 5TB（S3 API 制限） | 通常のメディアファイルは問題なし |

### パフォーマンス考慮

| 項目 | 推奨 | 理由 |
|------|------|------|
| 同時アクセス数 | FSx for ONTAP スループットに依存 | 256 MBps〜4096 MBps |
| 大ファイル読み取り | Multipart Download 推奨 | 並列化で高速化 |
| 小ファイル大量アクセス | バッチ処理推奨 | ListObjects のオーバーヘッド |
| 書き戻し | Multipart Upload 使用 | 5MB 以上のファイル |

### セキュリティ考慮

- **UNIX パーミッション**: FSx for ONTAP のファイルパーミッションが S3 AP 経由でも適用
- **AD 統合**: Active Directory ユーザーマッピングによるアクセス制御
- **暗号化**: FSx for ONTAP の保存時暗号化 + S3 AP の転送時暗号化（TLS）
- **監査**: ONTAP FPolicy + CloudTrail で全アクセスを記録

### ONTAP 固有の価値（非構造化データ）

| 機能 | 非構造化データでの価値 |
|------|---------------------|
| 重複排除 | 類似画像、動画の重複フレーム削減 |
| 圧縮 | テキスト文書の高圧縮率 |
| Snapshot | メディア編集前の状態保護 |
| FlexClone | AI 学習用データセットの瞬時コピー |
| FabricPool | アクセス頻度の低いメディアを自動階層化 |
| SnapLock | コンプライアンス文書の改ざん防止 |
| SnapMirror | 拠点間メディア同期・DR |
| マルチプロトコル | NFS + SMB + S3 同時アクセス |

## 次のステップ

- [アーキテクチャ概要](architecture.md) — 全体構成
- [ベンダー比較](vendor-comparison.md) — プラットフォーム選定
- [クイックスタート](getting-started.md) — 最初のデプロイ
