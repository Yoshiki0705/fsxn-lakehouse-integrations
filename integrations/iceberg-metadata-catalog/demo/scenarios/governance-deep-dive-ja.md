# ガバナンス詳細: Lake Formation + CloudTrail + PII

🌐 日本語 | [English](governance-deep-dive.md)

> AIメタデータカタログに適用されるLake Formationの行/列フィルタリング、CloudTrail監査証跡、PIIマスキングを示すクロスインダストリーガバナンスデモ。

---

## 目的

本ガイドは、23業界シナリオすべてに適用されるガバナンスコントロールを実演します。業界を問わず、同一の`sensitivity_level`フィールドとLake Formationポリシーにより、一貫したデータアクセス制御、監査証跡、PII保護を実現します。

**重要コンセプト**: メタデータカタログは全業界共通の`sensitivity_level`フィールド（値: `public`、`internal`、`confidential`、`restricted`）を使用します。この単一フィールドにより、基盤となる業界データに関係なく統一的なガバナンスポリシーが適用可能です。

---

## 前提条件

- AIメタデータカタログがサンプルデータでデプロイ済み（任意の業界）
- Lake Formationが`s3_tables.metadata_catalog`データベースで構成済み
- IAMロール: `CatalogAdmin`、`CatalogAnalyst`、`CatalogRestricted`
- CloudTrailがS3 Tablesのデータイベントで有効化済み

---

## デモ手順

### ステップ1: 全アクセス表示（管理者ビュー）

**所要時間**: 2分

全カラムが見える管理者ロールでクエリ実行：

```sql
-- CatalogAdminとして: 全カラムが表示される
SELECT file_path, ai_classification, confidence_score,
       customer_id, pii_detected, pii_types,
       sensitivity_level, retention_years
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'financial'
LIMIT 10;
```

**期待結果**: PII含有フィールド（`customer_id`、`pii_types`）を含むすべてのカラムが返される。

**トークポイント**:
- 「管理者にはすべて見えます — これが比較のベースラインです」
- 「`sensitivity_level`フィールドに注目 — これがすべてのアクセス判断を駆動します」

---

### ステップ2: カラムフィルタリング付き制限ロールの作成

**所要時間**: 3分

Lake Formationで`CatalogAnalyst`ロールに非機密カラムのみへのアクセスを付与：

```sql
-- Lake Formationカラムレベル付与（コンソールまたはCLI経由）
-- 付与先: CatalogAnalyst
-- データベース: s3_tables.metadata_catalog
-- テーブル: file_metadata
-- 含まれるカラム:
--   file_path, ai_classification, confidence_score,
--   industry, department, file_size_bytes, last_modified,
--   sensitivity_level
-- 除外されるカラム:
--   customer_id, pii_types, pii_detected, risk_level,
--   retention_years
```

**AWS CLI相当**（Lake Formation付与）：

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal":{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT_ID>:role/CatalogAnalyst"}}' \
  --resource '{"TableWithColumns":{"DatabaseName":"metadata_catalog","Name":"file_metadata","ColumnNames":["file_path","ai_classification","confidence_score","industry","department","file_size_bytes","last_modified","sensitivity_level"],"CatalogId":"<ACCOUNT_ID>"}}' \
  --permissions '["SELECT"]' \
  --region ap-northeast-1
```

**重要な制約**: フェデレーテッドカタログ（Glue Data Catalog連携）経由でのS3 Tablesに対するカラムレベル付与は、テスト時点では動作していません。以下のワークアラウンドとしてAthena Viewsを使用します。

---

### ステップ3: 制限ロールでクエリ — ブロックされたカラムが非表示

**所要時間**: 3分

```sql
-- CatalogAnalystとして: 付与されたカラムのみ表示
SELECT file_path, ai_classification, confidence_score,
       sensitivity_level, department
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'financial'
LIMIT 10;
```

**期待結果**: 付与されたカラムのみでクエリが成功。

```sql
-- ブロックされたカラムへのアクセス試行
SELECT customer_id
FROM s3_tables.metadata_catalog.file_metadata
LIMIT 1;
```

**期待結果**: アクセス拒否 — このロールにはカラムが非表示。

**トークポイント**:
- 「アナリストはPIIを見ずに分類・検索ができます」
- 「同一メタデータカタログ、ロールに基づく異なるビュー」
- 「データ複製なし — ゼロコピーストレージ、アクセスレベルフィルタリング」

---

### ステップ4: PII編集済みビュー（感度レベルフィルタリング）

**所要時間**: 5分

`sensitivity_level`に基づきアクセスを許可する行フィルタ付きビューを作成：

```sql
-- 感度に基づく行レベルフィルタリングのビューを作成
CREATE OR REPLACE VIEW metadata_catalog.public_metadata AS
SELECT file_path, ai_classification, confidence_score,
       industry, department, file_size_bytes, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE sensitivity_level IN ('public', 'internal');
```

Lake Formation行フィルタを適用（直接テーブルアクセス用）：

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal":{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT_ID>:role/CatalogRestricted"}}' \
  --resource '{"Table":{"DatabaseName":"metadata_catalog","Name":"file_metadata","CatalogId":"<ACCOUNT_ID>"}}' \
  --permissions '["SELECT"]' \
  --permissions-with-grant-option '[]' \
  --region ap-northeast-1
```

行フィルタ式（Lake Formationコンソール → データフィルタ経由）：

```json
{
  "RowFilter": {
    "FilterExpression": "sensitivity_level IN ('public', 'internal')"
  }
}
```

```sql
-- CatalogRestrictedとして: 非機密行のみ表示
SELECT file_path, ai_classification, sensitivity_level
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'healthcare';
-- sensitivity_level = 'public' または 'internal' の行のみ返される
-- PHIフラグ付き行（sensitivity_level = 'restricted'）は非表示
```

**トークポイント**:
- 「ヘルスケアのPHIレコードは、権限のないロールには表示されません」
- 「金融のPII文書は、クエリ結果が返される前に行レベルでフィルタリングされます」
- 「全23業界で同一に機能 — 同じフィールド、同じポリシー」

---

### ステップ5: CloudTrail監査証跡

**所要時間**: 5分

アクセス試行と拒否を示すCloudTrailログをクエリ：

```sql
-- Athena経由のCloudTrailクエリ（CloudTrail LakeまたはS3ベースログ）
SELECT eventTime, userIdentity.arn AS user_arn,
       eventName, requestParameters,
       errorCode, errorMessage
FROM cloudtrail_logs
WHERE eventSource = 'lakeformation.amazonaws.com'
  AND eventTime > current_timestamp - interval '1' hour
ORDER BY eventTime DESC
LIMIT 20;
```

**監査証跡の例**:

| eventTime | user_arn | eventName | errorCode |
|-----------|----------|-----------|-----------|
| 2026-06-01T10:15:32Z | .../CatalogAnalyst | GetTableData | - |
| 2026-06-01T10:15:45Z | .../CatalogAnalyst | GetTableData | AccessDeniedException |
| 2026-06-01T10:14:12Z | .../CatalogAdmin | GetTableData | - |

```sql
-- S3データアクセスイベント（S3データイベントが有効な場合）
SELECT eventTime, userIdentity.arn AS user_arn,
       eventName,
       requestParameters.bucketName,
       requestParameters.key
FROM cloudtrail_logs
WHERE eventSource = 's3.amazonaws.com'
  AND requestParameters.bucketName LIKE '%metadata-catalog%'
  AND eventTime > current_timestamp - interval '1' hour
ORDER BY eventTime DESC;
```

**トークポイント**:
- 「すべてのアクセス試行が記録されます — 成功も拒否も」
- 「監査人は、誰がいつ何にアクセスし、権限があったかを証明できます」
- 「金融、ヘルスケア、公共セクターの規制要件を満たします」
- 「CloudTrailログは不変です — データユーザーによる改ざんは不可能」

---

## 感度レベルリファレンス

`sensitivity_level`フィールドはAI分類時に設定され、一貫して適用されます：

| レベル | 説明 | 典型的なコンテンツ | アクセス |
|--------|------|-------------------|----------|
| `public` | 非機密メタデータ | ファイルタイプ、サイズ、作成日 | 全ロール |
| `internal` | 社内用 | 部門情報、プロジェクト名 | アナリスト以上 |
| `confidential` | ビジネス機密 | 財務数値、契約書 | マネージャー以上 |
| `restricted` | 規制対象/PII | 顧客PII、PHI、機密区分 | 管理者のみ |

**業界別マッピング例**:

| 業界 | `restricted`コンテンツ |
|------|----------------------|
| 金融 | 顧客ID、口座番号、KYC書類 |
| ヘルスケア | PHI（患者記録、患者データ付きDICOM） |
| 公共セクター | 機密文書、情報公開請求のPII |
| 法務 | 秘匿特権通信、和解内容 |
| リテール | 顧客決済データ、ロイヤルティプログラムPII |

---

### PII 検出の言語カバレッジ

| 言語 | 状態 | 方法 |
|------|------|------|
| 英語 | ✅ 検証済み | Amazon Comprehend（ネイティブ） |
| 日本語 | ✅ 検証済み | Bedrock Claude（プロンプトベース） |
| その他の言語 | ⚠️ 未検証 | Comprehend 対応言語で動作見込み; 言語ごとに検証が必要 |

**注**: PII 検出精度は言語により異なります。多言語環境では、PoC で言語ごとの検出精度を検証してください。Amazon Comprehend は複数言語をネイティブサポート; Bedrock Claude はほとんどの言語で PII パターンを検出できますが、すべてのエンティティタイプで精度が保証されるわけではありません。

---

## 動作確認済み vs. 未対応

### 動作確認済み

| 機能 | 状態 | 備考 |
|------|------|------|
| テーブルレベルLake Formation付与 | ✅ 動作 | S3 Tablesに対する完全なテーブル付与/取消 |
| Athena Viewsによるカラムフィルタリング | ✅ 動作 | カラムサブセットのCREATE VIEW |
| Athena Viewsによる行フィルタリング | ✅ 動作 | ビュー定義内のWHERE句 |
| CloudTrail監査ログ | ✅ 動作 | 全アクセスイベントがキャプチャされる |
| IAMロールベースアクセス | ✅ 動作 | 異なるアクセスレベル用のAssumeRole |
| Lake Formationタグ | ✅ 動作 | データベースに対するタグベースアクセス制御 |

### 既知の制約（観測済み）

| 機能 | 状態 | ワークアラウンド |
|------|------|-----------------|
| S3 Tables（フェデレーテッドカタログ）に対するLake Formationカラムレベルフィルタリング | ⚠️ 未対応 | カラムサブセットのAthena Viewsを使用 |
| S3 Tablesに対するLake Formation行レベルフィルタリング（データフィルタ） | ⚠️ 未対応 | WHERE句付きAthena Viewsを使用 |
| S3 TablesのクロスアカウントLake Formation共有 | ⚠️ 未テスト | S3クロスアカウントレプリケーションを使用 |
| CloudTrailでのカラムアクセスの詳細監査 | ⚠️ 限定的 | テーブルレベルイベントは利用可能、カラムレベル詳細は粒度不足 |

---

## SQLリファレンス: 共通ガバナンスクエリ

```sql
-- コンプライアンスダッシュボード: 感度分布
SELECT industry, sensitivity_level, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY industry, sensitivity_level
ORDER BY industry, sensitivity_level;

-- 全業界横断PIIインベントリ
SELECT industry, ai_classification, COUNT(*) as pii_files
FROM s3_tables.metadata_catalog.file_metadata
WHERE pii_detected = true
GROUP BY industry, ai_classification
ORDER BY pii_files DESC;

-- リテンションコンプライアンス: 保持期限超過ファイル
SELECT file_path, industry, ai_classification,
       retention_expiry_date, sensitivity_level
FROM s3_tables.metadata_catalog.file_metadata
WHERE retention_expiry_date < current_date
  AND sensitivity_level IN ('confidential', 'restricted')
ORDER BY retention_expiry_date ASC;

-- アクセスパターン監査: 誰が何をクエリしたか
SELECT DATE(eventTime) as access_date,
       userIdentity.arn as user_role,
       COUNT(*) as query_count
FROM cloudtrail_logs
WHERE eventSource = 'athena.amazonaws.com'
  AND eventTime > current_timestamp - interval '30' day
GROUP BY DATE(eventTime), userIdentity.arn
ORDER BY access_date DESC;
```

---

## 業界シナリオとの統合

各業界シナリオはこれらのガバナンスコントロールを継承します：

1. **AI分類**が処理中に`sensitivity_level`を自動設定
2. **Lake Formation**（またはAthena Views）がそのレベルに基づきアクセスを強制
3. **CloudTrail**が監査証跡として全アクセスを記録
4. **コード変更不要** — ガバナンスはインフラストラクチャレベル

特定の業界デモにガバナンスを適用するには、IAMロールが構成されていることを確認し、適切なロールでデモを実行するだけです。

---

*関連: [AIプロンプトカスタマイズガイド](ai-prompt-customization-guide-ja.md) — 分類がsensitivity_levelをどう設定するか*
*関連: [Snowflakeアクティベーションパターン](snowflake-activation-pattern-ja.md) — クロスプラットフォームアクセスのガバナンス考慮事項*
*ペアドキュメント: [governance-deep-dive.md](governance-deep-dive.md)*
