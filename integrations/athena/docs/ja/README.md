# AWS Athena 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ セキュリティ検証済み (2026-05-23)**
>
> ベンチマーク: ピークスループット 54.8 MB/s、5M 行を 2.2 秒でクエリ（103 MB Parquet、128 MB/s プロビジョニング）。
> 9/9 ネガティブセキュリティテスト PASS。CloudTrail 監査確認済み。

## 概要

Amazon Athena から Amazon FSx for NetApp ONTAP（FSx for ONTAP）のデータを直接クエリします。
Glue Data Catalog と S3 Access Points を使用したサーバーレス・従量課金制の分析基盤です。

## アーキテクチャ

```
Athena (サーバーレス SQL)
    │
    └── Glue Data Catalog
            │
            ├── Glue Crawler (スキーマ検出)
            │
            └── S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
                                                        ├── transactions/ (Parquet, パーティション)
                                                        ├── customers/ (CSV)
                                                        ├── events/ (JSON)
                                                        └── gold/ (CTAS 出力)
```

## 重要: ネットワークオリジン

Athena は **internet ネットワークオリジン** の S3 Access Point が必要です。
VPC 限定のアクセスポイントは Athena では動作しません。

## データフォーマット対応

| フォーマット | 読み取り | 書き込み (CTAS) | 備考 |
|------------|---------|----------------|------|
| Parquet | ✅ | ✅ | パーティションプルーニング対応 |
| CSV | ✅ | ✅ | |
| JSON | ✅ | ✅ | |
| ORC | ✅ | ✅ | |
| Avro | ✅ | ❌ | |

## 非構造化データ対応

Athena は構造化データ（Parquet, CSV, JSON）のクエリに最適化されています。非構造化データ（画像、動画）の直接クエリはサポートされていませんが、メタデータテーブルを作成してファイルパスを管理し、他のサービス（Lambda, Bedrock）と連携することで処理できます。

**パターン:**
1. **メタデータテーブル** — Glue Crawler でファイルパス・サイズ・更新日時をカタログ化
2. **Athena + Lambda UDF** — クエリ結果のファイルパスを Lambda に渡して処理
3. **S3 AP Pre-signed URL** — Athena クエリ結果からファイルパスを取得し、アプリケーションでダウンロード

```sql
-- ファイルメタデータをクエリ（Glue Crawler で登録済みの場合）
SELECT key, size, last_modified
FROM fsxn_file_catalog
WHERE key LIKE '%.pdf'
ORDER BY last_modified DESC;
```

## クイックスタート

```bash
# 1. パラメータをコピーして値を設定
cp params.example.json params.json

# 2. サンプルデータを生成
pip install pandas pyarrow
python scripts/generate_sample_data.py

# 3. FSx for ONTAP に NFS 経由でアップロード
./scripts/upload_sample_data.sh

# 4. インフラをデプロイ
./deploy.sh

# 5. 接続を検証
python scripts/validate_connectivity.py
```
