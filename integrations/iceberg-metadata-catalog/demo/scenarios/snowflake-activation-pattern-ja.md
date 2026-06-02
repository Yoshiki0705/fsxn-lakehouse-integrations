# Snowflakeアクティベーションパターン: メタデータ同期 + Cortex Search

🌐 日本語 | [English](snowflake-activation-pattern.md)

> Snowflakeユーザーが現時点でAIメタデータカタログを活用する方法。自然言語クエリのためのCortex Searchとファイル分析のためのAI_COMPLETEを含む。

---

## 目的

SnowflakeからS3 Tablesへの直接Icebergカタログアクセスはまだ利用できません（credential vending / フェデレーテッドカタログ統合が保留中）。しかし、SnowflakeユーザーはPyIceberg export → External Stage → COPY INTOパターンにより、今すぐメタデータカタログを活用できます。

これにより以下が実現されます：
- Cortex Search経由の完全なメタデータ検索（自然言語）
- AI_COMPLETE + TO_FILEによるFSx External Stage上のファイルAI分析
- ソースファイルのストレージ重複なし（FSxでのゼロコピーストレージ）
- スケジュールまたはイベント駆動のメタデータ同期

---

## アーキテクチャ

```
FSx for ONTAP → FPolicy → Lambda → S3 Tables (Iceberg)
                                          │
                                    PyIceberg Export
                                          │
                                          ▼
                               S3 (Parquet エクスポート)
                                          │
                              Snowflake External Stage
                                          │
                                    COPY INTO / MERGE INTO
                                          │
                                          ▼
                              Snowflake マネージドテーブル
                                     │          │
                                     ▼          ▼
                            Cortex Search    AI_COMPLETE
                          (自然言語)        (TO_FILE経由ファイルAI)
```

**重要ポイント**: ソースファイルはFSx for ONTAP上に残ります（ゼロコピーストレージ）。メタデータレコード（小さい、ファイルあたり約1KB）のみがSnowflakeに同期されます。

---

## 手順詳細

### ステップ1: S3 TablesからS3 Parquetへメタデータをエクスポート

PyIcebergを使用してS3 Tablesから最新レコードのメタデータをParquetとしてS3にエクスポート：

```python
# export_metadata.py
from pyiceberg.catalog import load_catalog
import pyarrow.parquet as pq

# S3 Tablesカタログをロード
catalog = load_catalog(
    "s3_tables",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-1",
    }
)

# メタデータテーブルを読み込み
table = catalog.load_table("metadata_catalog.file_metadata")
scan = table.scan()
df = scan.to_arrow()

# ParquetとしてS3にエクスポート
pq.write_table(
    df,
    "s3://my-export-bucket/metadata-export/file_metadata.parquet"
)
print(f"Exported {len(df)} records")
```

**スケジューリング**: EventBridge + Lambdaでスケジュール実行（例: 1時間ごと）、またはFPolicyバッチ処理完了後にトリガー。

---

### ステップ2: Snowflake External Stageの作成

エクスポートバケットを指すSnowflake External Stageを作成：

```sql
-- ストレージ統合の作成（初回セットアップのみ）
CREATE OR REPLACE STORAGE INTEGRATION s3_metadata_export_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/SnowflakeMetadataExportRole'
  STORAGE_ALLOWED_LOCATIONS = ('s3://my-export-bucket/metadata-export/');

-- External Stageの作成
CREATE OR REPLACE STAGE metadata_export_stage
  STORAGE_INTEGRATION = s3_metadata_export_int
  URL = 's3://my-export-bucket/metadata-export/'
  FILE_FORMAT = (TYPE = PARQUET);
```

---

### ステップ3: マネージドテーブルへCOPY INTO

エクスポートされたメタデータをSnowflakeマネージドテーブルにロード：

```sql
-- ターゲットテーブルの作成
CREATE OR REPLACE TABLE file_metadata (
  file_path VARCHAR,
  file_name VARCHAR,
  file_size_bytes NUMBER,
  last_modified TIMESTAMP_NTZ,
  ai_classification VARCHAR,
  confidence_score FLOAT,
  sensitivity_level VARCHAR,
  industry VARCHAR,
  department VARCHAR,
  pii_detected BOOLEAN,
  pii_types ARRAY,
  scan_timestamp TIMESTAMP_NTZ,
  -- 業界固有フィールドは柔軟性のためVARIANTとして
  extended_metadata VARIANT
);

-- 完全リフレッシュ（シンプルなアプローチ）
TRUNCATE TABLE file_metadata;
COPY INTO file_metadata
FROM @metadata_export_stage/file_metadata.parquet
FILE_FORMAT = (TYPE = PARQUET)
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
```

**インクリメンタルアプローチ**（大規模データセット用）：

```sql
-- インクリメンタル更新のためのMERGE
MERGE INTO file_metadata AS target
USING (
  SELECT $1:file_path::VARCHAR AS file_path,
         $1:file_name::VARCHAR AS file_name,
         $1:file_size_bytes::NUMBER AS file_size_bytes,
         $1:last_modified::TIMESTAMP_NTZ AS last_modified,
         $1:ai_classification::VARCHAR AS ai_classification,
         $1:confidence_score::FLOAT AS confidence_score,
         $1:sensitivity_level::VARCHAR AS sensitivity_level,
         $1:industry::VARCHAR AS industry,
         $1:department::VARCHAR AS department,
         $1:pii_detected::BOOLEAN AS pii_detected,
         $1:pii_types::ARRAY AS pii_types,
         $1:scan_timestamp::TIMESTAMP_NTZ AS scan_timestamp,
         $1:extended_metadata::VARIANT AS extended_metadata
  FROM @metadata_export_stage/file_metadata.parquet
) AS source
ON target.file_path = source.file_path
WHEN MATCHED AND target.scan_timestamp < source.scan_timestamp THEN
  UPDATE SET
    ai_classification = source.ai_classification,
    confidence_score = source.confidence_score,
    sensitivity_level = source.sensitivity_level,
    pii_detected = source.pii_detected,
    scan_timestamp = source.scan_timestamp,
    extended_metadata = source.extended_metadata
WHEN NOT MATCHED THEN
  INSERT (file_path, file_name, file_size_bytes, last_modified,
          ai_classification, confidence_score, sensitivity_level,
          industry, department, pii_detected, pii_types,
          scan_timestamp, extended_metadata)
  VALUES (source.file_path, source.file_name, source.file_size_bytes,
          source.last_modified, source.ai_classification,
          source.confidence_score, source.sensitivity_level,
          source.industry, source.department, source.pii_detected,
          source.pii_types, source.scan_timestamp, source.extended_metadata);
```

---

### ステップ4: Cortex Searchサービスの作成

メタデータ上で自然言語検索を有効化：

```sql
-- マネージドテーブル上にCortex Searchサービスを作成
CREATE OR REPLACE CORTEX SEARCH SERVICE file_metadata_search
  ON file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_path, ai_classification, industry, department, sensitivity_level'
  COLUMNS = (
    file_path,
    file_name,
    ai_classification,
    industry,
    department,
    sensitivity_level,
    confidence_score
  )
  SEARCH_COLUMN = 'file_name';
```

**注**: Cortex Searchにはテキストベース検索に使用する`SEARCH_COLUMN`が必要です。より豊富な検索のために、メタデータフィールドを検索専用テキストカラムに結合します：

```sql
-- 拡張: 検索最適化カラムを作成
ALTER TABLE file_metadata ADD COLUMN search_text VARCHAR;
UPDATE file_metadata SET search_text = 
  CONCAT(file_name, ' | ', ai_classification, ' | ', 
         COALESCE(industry, ''), ' | ', COALESCE(department, ''));

-- 拡張検索カラムでサービスを再作成
CREATE OR REPLACE CORTEX SEARCH SERVICE file_metadata_search
  ON file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_path, ai_classification, industry, department, sensitivity_level'
  COLUMNS = (file_path, file_name, ai_classification, industry, 
             department, sensitivity_level, confidence_score, search_text)
  SEARCH_COLUMN = 'search_text';
```

---

### ステップ5: Cortex Search経由のクエリ（自然言語）

```sql
-- 自然言語検索
SELECT *
FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH(
    'file_metadata_search',
    '半導体ウェーハの品質検査レポート',
    5  -- 上位5件
  )
);

-- フィルター付き検索
SELECT *
FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH(
    'file_metadata_search',
    '期限が近いKYC書類',
    10,
    OBJECT_CONSTRUCT('industry', 'financial')
  )
);
```

---

### ステップ6: TO_FILE経由のAI_COMPLETEによるファイル分析

Snowflake AI_COMPLETEでFSxファイルを直接AI分析：

```sql
-- FSx S3 Access Pointを指すExternal Stageの作成
CREATE OR REPLACE STAGE fsxn_files_stage
  STORAGE_INTEGRATION = s3_fsxn_int
  URL = 's3://<fsxn-s3-access-point-alias>/vol/data/'
  FILE_FORMAT = (TYPE = AUTO);

-- AI_COMPLETE + TO_FILEでファイル分析（動作確認済み）
SELECT
  file_path,
  ai_classification,
  SNOWFLAKE.CORTEX.AI_COMPLETE(
    'claude-3-5-sonnet',
    CONCAT(
      'このドキュメントを2文で要約してください: ',
      TO_FILE('@fsxn_files_stage', file_name)
    )
  ) AS ai_summary
FROM file_metadata
WHERE ai_classification = 'quality_report'
  AND industry = 'manufacturing'
LIMIT 5;
```

**注**: FSx External Stage上のTO_FILEはテストで動作確認済みです。これにより、SnowflakeユーザーはファイルコンテンツをコピーせずにFSx上のファイルに対してAI分析を実行できます。

---

## 現在のブロッカー

| ブロッカー | 状態 | 影響 |
|-----------|------|------|
| SnowflakeからのS3 Tables Iceberg直接クエリ | ❌ 未提供 | S3 TablesをIcebergカタログとして直接クエリ不可 |
| S3 Tablesのcredential vending | ❌ 未提供 | SnowflakeがS3 Tablesフェデレーテッドカタログに認証不可 |
| Snowflake Icebergカタログ統合（S3 Tables対応） | ❌ 保留中 | 機能リクエスト提出済み、ETAなし |

**ワークアラウンド**: 上記のPyIcebergエクスポートパターンが、同期ステップのコストで機能的等価性を提供します。

---

## 将来の姿

SnowflakeがS3 Tables / フェデレーテッドカタログをサポートした際：

```
現在:    S3 Tables → PyIceberg Export → S3 Parquet → Snowflake Stage → マネージドテーブル
将来:    S3 Tables → Snowflake Icebergカタログ（直接読み取り）→ バーチャルテーブル
```

将来の状態で不要になるもの：
- エクスポートステップ（PyIcebergジョブ不要）
- ストレージ重複（メタデータはS3 Tablesのみ）
- 同期ラグ（最新メタデータへのリアルタイムアクセス）

それまでは、エクスポートパターンが許容可能なラグ（構成可能：分〜時間単位）で動作するソリューションを提供します。

---

## コストモデル

### Snowflakeコスト

| コンポーネント | 推定コスト | 備考 |
|---------------|-----------|------|
| ウェアハウスコンピュート（COPY INTO） | 約$2–5/回 | X-Smallウェアハウス、100Kレコードで1分未満 |
| ウェアハウスコンピュート（Cortex Searchインデックス） | 約$3–8/日 | データ量とTARGET_LAGに依存 |
| Cortex Searchサービス | 約$0.08/1Kクエリ | 検索クエリごとの課金 |
| AI_COMPLETE（Snowflake経由Claude） | 約$0.03–0.10/回 | 入力サイズとモデルに依存 |
| マネージドテーブルストレージ | 約$23/TB/月 | メタデータのみ — 通常1GB未満 |

### AWSコスト（エクスポート側）

| コンポーネント | 推定コスト | 備考 |
|---------------|-----------|------|
| Lambda（PyIcebergエクスポート） | 約$0.50/回 | 256MB、100Kレコードで60秒未満 |
| S3ストレージ（Parquetエクスポート） | 約$0.02/月 | メタデータParquetファイルは小さい |
| S3 GET/PUTリクエスト | 約$0.005/エクスポート | 最小限のリクエストコスト |

**推定総コスト**: 100Kファイルの時間単位同期、適度なCortex Search利用で約$5–15/日。

---

## 制約事項

| 制約 | 説明 |
|------|------|
| 同期ラグ | Snowflake内のメタデータはエクスポート頻度分遅延する（リアルタイムではない） |
| 直接Icebergクエリ不可 | S3 Tables Iceberg形式をSnowflakeから直接クエリできない |
| エクスポートメンテナンス | PyIcebergエクスポートジョブにはモニタリングとエラーハンドリングが必要 |
| スキーマ進化 | S3 Tablesのスキーマ変更にはSnowflakeテーブルDDLの手動更新が必要 |
| Cortex Search提供リージョン | Cortex Searchは一部のSnowflakeリージョンでのみ利用可能 |
| TO_FILEサイズ制限 | 大きなファイルはタイムアウトの可能性あり、50MB未満のドキュメントに最適 |
| AI_COMPLETEモデル提供状況 | すべてのモデルがすべてのSnowflakeリージョンで利用可能ではない |

---

## 完全セットアップスクリプト

```sql
-- ==============================================
-- Snowflakeアクティベーション: フルセットアップ
-- ==============================================

-- 1. ストレージ統合
CREATE OR REPLACE STORAGE INTEGRATION s3_metadata_export_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/SnowflakeMetadataExportRole'
  STORAGE_ALLOWED_LOCATIONS = (
    's3://my-export-bucket/metadata-export/',
    's3://<fsxn-s3-access-point-alias>/'
  );

-- 2. External Stage（メタデータ）
CREATE OR REPLACE STAGE metadata_export_stage
  STORAGE_INTEGRATION = s3_metadata_export_int
  URL = 's3://my-export-bucket/metadata-export/'
  FILE_FORMAT = (TYPE = PARQUET);

-- 3. ターゲットテーブル
CREATE OR REPLACE TABLE file_metadata (
  file_path VARCHAR,
  file_name VARCHAR,
  file_size_bytes NUMBER,
  last_modified TIMESTAMP_NTZ,
  ai_classification VARCHAR,
  confidence_score FLOAT,
  sensitivity_level VARCHAR,
  industry VARCHAR,
  department VARCHAR,
  pii_detected BOOLEAN,
  pii_types ARRAY,
  scan_timestamp TIMESTAMP_NTZ,
  extended_metadata VARIANT,
  search_text VARCHAR
);

-- 4. データロード
COPY INTO file_metadata (file_path, file_name, file_size_bytes, last_modified,
  ai_classification, confidence_score, sensitivity_level, industry, department,
  pii_detected, pii_types, scan_timestamp, extended_metadata)
FROM @metadata_export_stage/file_metadata.parquet
FILE_FORMAT = (TYPE = PARQUET)
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

-- 5. 検索テキストの生成
UPDATE file_metadata SET search_text =
  CONCAT(file_name, ' | ', ai_classification, ' | ',
         COALESCE(industry, ''), ' | ', COALESCE(department, ''));

-- 6. Cortex Searchサービス
CREATE OR REPLACE CORTEX SEARCH SERVICE file_metadata_search
  ON file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_path, ai_classification, industry, department, sensitivity_level'
  COLUMNS = (file_path, file_name, ai_classification, industry,
             department, sensitivity_level, confidence_score, search_text)
  SEARCH_COLUMN = 'search_text';

-- 7. 確認
SELECT COUNT(*) FROM file_metadata;
SELECT * FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH('file_metadata_search', 'テストクエリ', 3)
);
```

---

*関連: [ガバナンス詳細](governance-deep-dive-ja.md) — クロスプラットフォーム同期のアクセス制御考慮事項*
*関連: [AIプロンプトカスタマイズガイド](ai-prompt-customization-guide-ja.md) — 同期されるメタデータを生成する分類*
*ペアドキュメント: [snowflake-activation-pattern.md](snowflake-activation-pattern.md)*
