# Redshift Spectrum 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 機能検証済み (2026-05-23)**
>
> Redshift Serverless (8 RPU) + Spectrum で FSx for ONTAP S3 AP（internet-origin）上の検証完了。
> - COUNT(*) 10K 行: 3.2s
> - GROUP BY + AVG: 2.6s
> - COUNT(*) 5M 行: 4.3s

## 概要

Amazon Redshift Spectrum を使用して FSx for ONTAP のデータを直接クエリします。
Glue Data Catalog と S3 Access Points を使用。DWH ローカルテーブルと外部 FSxN データのフェデレーテッドクエリが可能。

## アーキテクチャ

```
Redshift Serverless (DWH)
    │
    ├── ローカルテーブル (Redshift マネージドストレージ)
    │
    └── External Schema (Glue Data Catalog)
            │
            └── S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
```

## 主なポイント

- **Athena と同じパターン**: Internet-origin S3 AP + Glue Catalog
- **フェデレーテッドクエリ**: ローカル Redshift テーブルと外部 FSxN データを JOIN
- **述語プッシュダウン**: Spectrum がフィルターを S3 レイヤーにプッシュ（スキャンデータ削減）
- **セッションポリシー問題なし**: AWS ネイティブサービス、直接 IAM ロール

## 非構造化データ対応

Redshift Spectrum は構造化データ（Parquet, CSV, JSON, ORC）のクエリに特化しています。非構造化データの直接クエリはサポートされていませんが、メタデータテーブルを活用したパターンが可能です。

**パターン:**
1. **メタデータテーブル** — ファイルパス・サイズ・タイプを External Table として登録
2. **フェデレーテッド JOIN** — ローカル DWH テーブル（顧客情報）と外部ファイルカタログを JOIN
3. **UNLOAD** — クエリ結果を FSx for ONTAP に書き戻し、他のサービスで処理

```sql
-- External Table としてファイルカタログをクエリ
SELECT file_path, file_type, file_size
FROM spectrum_schema.file_catalog
WHERE file_type = 'application/pdf'
  AND last_modified > CURRENT_DATE - INTERVAL '7 days';

-- ローカルテーブルとファイルカタログを JOIN
SELECT c.customer_name, f.file_path
FROM local_schema.customers c
JOIN spectrum_schema.file_catalog f ON c.customer_id = f.owner_id;
```

## クイックスタート

```bash
# 1. Redshift Serverless + IAM ロールをデプロイ
./deploy.sh

# 2. External Schema を作成してクエリを実行
python scripts/run_spectrum_queries.py

# 3. クリーンアップ（重要 — Redshift Serverless は 8 RPU で約 $2.88/時間）
./scripts/cleanup.sh
```

## コスト

Redshift Serverless は最小 8 RPU（約 $2.88/時間）。検証後は速やかに削除してください。
