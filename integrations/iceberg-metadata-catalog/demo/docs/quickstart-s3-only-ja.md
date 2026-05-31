# クイックスタート: S3 のみモード (FSx 不要)

🌐 日本語 | [English](quickstart-s3-only.md)

## 概要

本ガイドにより、**FSx for ONTAP なし**で Iceberg メタデータカタログを試すことができます。FSx の S3 Access Point の代わりに、通常の S3 バケットとサンプルファイルを使用します。

**体験できること**: 同じメタデータカタログ、AI 分類、ベクトル検索、ガバナンス — ファイルソースが FSx ではなく S3 になるだけです。

**所要時間**: ~10 分 | **コスト**: < $0.10 | **前提条件**: AWS CLI + Python 3.12+

## Step 1: サンプルファイル付き S3 バケット作成

```bash
# 変数設定
export BUCKET_NAME="iceberg-metadata-demo-$(aws sts get-caller-identity --query Account --output text)"
export REGION="ap-northeast-1"  # お好みのリージョン

# バケット作成
aws s3 mb s3://${BUCKET_NAME} --region ${REGION}

# サンプルファイルアップロード（本リポジトリから）
aws s3 cp integrations/iceberg-metadata-catalog/demo/sample-data/ \
  s3://${BUCKET_NAME}/demo-files/ --recursive

# または独自のサンプルファイルを作成:
echo "機密 - 従業員記録
氏名: 山田太郎
メール: taro.yamada@example.co.jp
電話: 090-1234-5678
マイナンバー: 1234 5678 9012" > /tmp/pii-sample-ja.txt

aws s3 cp /tmp/pii-sample-ja.txt s3://${BUCKET_NAME}/demo-files/documents/
```

## Step 2: S3 Tables メタデータカタログ作成

```bash
# 依存パッケージインストール
pip install -r requirements.txt

# Iceberg テーブル作成 + スキャン
python3 scripts/initial-metadata-scan.py \
  --access-point-arn ${BUCKET_NAME} \
  --table-bucket-arn arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/fsxn-metadata-catalog \
  --max-files 100 \
  --region ${REGION}
```

> **注**: `--access-point-arn` パラメータは S3 AP エイリアスと通常のバケット名の両方を受け付けます。スクリプトは `s3.list_objects_v2(Bucket=...)` を使用しており、どちらでも動作します。

## Step 3: AI エンリッチメント実行

```bash
python3 demo/scripts/demo-enrich.py \
  --table-bucket-arn arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/fsxn-metadata-catalog \
  --ap-alias ${BUCKET_NAME} \
  --region ${REGION} \
  --max-files 10
```

## Step 4: Athena クエリ

```sql
-- Glue カタログ登録（初回のみ）:
-- demo-guide-ja.md の Step 2 を参照

SELECT file_name, classification, confidence_score
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE enrichment_status = 'completed'
ORDER BY confidence_score DESC;
```

## Step 5: ベクトル検索

```bash
python3 demo/scripts/demo-search.py \
  --query "個人情報を含むドキュメントを検索" \
  --region ${REGION}
```

## Step 6: PII 検出

```bash
python3 demo/scripts/demo-anonymize.py \
  --ap-alias ${BUCKET_NAME} \
  --region ${REGION} \
  --file-key demo-files/documents/pii-sample-ja.txt
```

## クリーンアップ

```bash
# S3 バケット削除
aws s3 rb s3://${BUCKET_NAME} --force

# S3 Tables 削除（作成した場合）
aws s3tables delete-table \
  --table-bucket-arn arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/fsxn-metadata-catalog \
  --namespace metadata --name unstructured_files --region ${REGION}
```

## フルデモとの違い

| 機能 | S3 のみモード | フルモード (FSx for ONTAP) |
|------|:---:|:---:|
| メタデータスキャン | ✅ | ✅ |
| AI 分類 | ✅ | ✅ |
| ベクトル検索 | ✅ | ✅ |
| PII 検出 | ✅ | ✅ |
| Athena クエリ | ✅ | ✅ |
| Lake Formation ガバナンス | ✅ | ✅ |
| **ゼロコピー (データ移動なし)** | ❌ (データは S3 に存在) | ✅ |
| **NFS/SMB アクセス** | ❌ | ✅ |
| **重複排除** | ❌ | ✅ (50-70% 削減) |
| **FPolicy リアルタイム同期** | ❌ | ✅ |
| **Snapshot/FlexClone** | ❌ | ✅ |

FSx for ONTAP の核心的価値は**ゼロコピー**: 既存の NFS/SMB ファイルがデータ移動なしで AI 検索可能になること。S3 のみモードでは、まずファイルを S3 にアップロードする必要があります。

## 次のステップ

- **フル体験したい場合**: FSx for ONTAP + S3 Access Points をデプロイ → [PoC ガイド](../../docs/poc-guide-ja.md)
- **独自ファイルを追加したい場合**: S3 バケットにアップロードしてスキャンを再実行
- **リアルタイム同期が必要な場合**: FSx for ONTAP FPolicy がファイル変更を自動検出
