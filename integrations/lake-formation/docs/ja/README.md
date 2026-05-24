# Lake Formation 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 機能検証済み (2026-05-24)**
>
> - Lake Formation 管理者設定完了
> - テーブルレベル SELECT 専用権限検証済み
> - Lake Formation ガバナンス下での Athena クエリ: PASS
> - 4 層認可確認済み

## 概要

AWS Lake Formation を使用して FSx for ONTAP S3 Access Point データに細粒度ガバナンス（テーブル/カラムレベルのアクセス制御）を追加します。規制産業向けデプロイメントを実現。

## アーキテクチャ

```
ユーザー/ロール
    │
    ▼
Lake Formation (テーブル/カラム権限)
    │
    ▼
Glue Data Catalog (テーブルメタデータ)
    │
    ▼
S3 Access Point (IAM + AP ポリシー)
    │
    ▼
FSx for ONTAP (ファイルシステムユーザー権限)
```

**4 層認可**:
1. Lake Formation: どのテーブル/カラムに誰がアクセスできるか
2. IAM: どの API を誰が呼び出せるか
3. S3 AP ポリシー: どのプリンシパルがこのアクセスポイントにアクセスできるか
4. ファイルシステム: 基盤ファイルの UNIX パーミッション

## 非構造化データ対応

Lake Formation は Glue Data Catalog に登録されたテーブルに対するガバナンスを提供します。非構造化データに対しても、メタデータテーブルを通じてアクセス制御を適用できます。

**パターン:**
1. **メタデータテーブルのガバナンス** — ファイルパスを含むテーブルにカラムレベルセキュリティを適用
2. **タグベースアクセス制御** — ファイルタイプや機密度に基づくタグで自動的にアクセス権を付与
3. **監査** — 誰がどのファイルメタデータにアクセスしたかを一元的に記録
4. **クロスアカウント共有** — S3 AP ポリシーを変更せずにテーブル（ファイルカタログ）を共有

```sql
-- Lake Formation で保護されたファイルカタログをクエリ
-- （カラムレベルセキュリティにより、機密ファイルパスはマスクされる）
SELECT file_path, file_type, file_size
FROM fsxn_db.file_catalog
WHERE classification = 'public';
```

## ガバナンスの価値

| 機能 | メリット |
|------|---------|
| テーブルレベルアクセス | S3 AP ポリシーを変更せずに特定テーブルへの SELECT を付与 |
| カラムレベルセキュリティ | ロールごとに機密カラム（PHI, PII）をマスク |
| タグベースアクセス制御 | データを分類し、タグで自動的にアクセス権を付与 |
| 一元監査 | 誰がどのテーブルにいつアクセスしたかを記録 |
| クロスアカウント共有 | S3 AP を共有せずにテーブルを共有 |

## クイックスタート

```bash
# 1. Lake Formation 管理者を設定
aws lakeformation put-data-lake-settings \
  --data-lake-settings '{"DataLakeAdmins":[{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT>:user/<ADMIN>"}]}'

# 2. テーブル権限を付与
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier":"<ROLE_ARN>"}' \
  --resource '{"Table":{"DatabaseName":"<DB>","Name":"<TABLE>"}}' \
  --permissions "SELECT" "DESCRIBE"

# 3. Athena 経由でクエリ（権限が適用される）
aws athena start-query-execution \
  --query-string "SELECT * FROM <DB>.<TABLE> LIMIT 10"
```
