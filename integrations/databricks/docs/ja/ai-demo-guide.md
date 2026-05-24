🌐 [English](../en/ai-demo-guide.md) | **日本語**

# Databricks AI/ML デモガイド — FSx for ONTAP S3 AP

本ガイドでは、Databricks から S3 Access Point 経由で FSx for ONTAP データにアクセスする際の AI/ML 機能とその現在のステータスを文書化します。

> **重要**: Unity Catalog のセッションポリシーにより、FSx for ONTAP S3 Access Point 上でのテーブル作成およびサブディレクトリ一覧取得が現在ブロックされています。以下のシナリオでは、現時点で動作するもの（ドライバーノードのみの PoC）、ブロックされているもの、プラットフォーム境界が解消された場合に可能になるものを文書化しています。

## 前提条件

- AWS 上の Databricks ワークスペース（Customer-managed VPC 推奨）
- FSx for ONTAP S3 Access Point の設定完了
- S3 AP アクセス権限を持つ Instance Profile（PoC パス用）
- `access_point` フィールドが設定された Unity Catalog External Location
- DBR 17.3 LTS 以降

## 現在のステータスサマリー

| 機能 | ステータス | パス | ブロッカー |
|---|:---:|---|---|
| Spark ファイル読み取り（明示パス） | ✅ 動作 | UC External Location + `access_point` | — |
| サブディレクトリ一覧 | ❌ ブロック | UC External Location | セッションポリシーのプレフィックスレベルアクセス |
| S3 AP 上の CREATE TABLE | ❌ ブロック | UC External Location | UC_CLOUD_STORAGE_ACCESS_FAILURE |
| boto3 ファイル読み取り（ドライバー） | ✅ 動作 | Instance Profile (Customer VPC) | UC ガバナンスをバイパス |
| Feature Store テーブル | ❌ ブロック | CREATE TABLE が必要 | セッションポリシー |
| MLflow トラッキング | ✅ 動作 | ストレージパスに依存しない | — |
| Model Serving | ⚠️ 未検証 | 異なるクレデンシャルパス | — |

---

## デモ 1: FSx for ONTAP からの Spark 読み取り（動作確認済み）

**ユースケース**: ML 特徴量エンジニアリングのために FSx for ONTAP から構造化データ（CSV、Parquet）を読み取り。

```python
# FSx for ONTAP S3 AP からセンサーデータを読み取り（明示的ファイルパス）
df = spark.read.format("csv") \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .load("s3://<s3ap-alias>/bronze/sensor_data/sensor_readings.csv")

df.show(5)
print(f"✅ FSx for ONTAP S3 AP から {df.count()} 行を読み取り")
```

**結果**: FSx for ONTAP 上のセンサー CSV から 1000 行を正常に読み取り（External Location に `access_point` フィールドを設定した明示的ファイルパス）。

![Spark が FSx S3 AP 上の明示的ファイルパスの読み取りに成功](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/databricks-ai-spark-read-success.png)

*Spark が Unity Catalog ガバナンス下で、明示的ファイルパスを使用して FSx for ONTAP S3 Access Point からセンサー CSV データを正常に読み取り。*

**制限事項**: 明示的ファイルパスのみ動作。ディレクトリレベルの読み取り（例: `spark.read.parquet("s3://<alias>/bronze/")`）はセッションポリシーによりサブディレクトリ一覧がブロックされるため失敗。

---

## デモ 2: CREATE TABLE — ブロック（エラー証跡）

**ユースケース**: ML パイプライン用に FSx for ONTAP データをガバナンス付き Unity Catalog テーブルとして登録。

```sql
-- FSx for ONTAP S3 AP 上に External Table を作成試行
CREATE TABLE fsxn_lakehouse.bronze.sensor_data
USING CSV
OPTIONS (header = 'true', inferSchema = 'true')
LOCATION 's3://<s3ap-alias>/bronze/sensor_data/';
```

**結果**: ❌ `UC_CLOUD_STORAGE_ACCESS_FAILURE` — Unity Catalog の内部検証が S3 AP パスにアクセスできず、テーブル登録が失敗。

![UC セッションポリシーにより FSx S3 AP 上の CREATE TABLE がブロック](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/databricks-ai-create-table-blocked.png)

*Unity Catalog が FSx for ONTAP S3 Access Point 上のテーブル作成を拒否。AssumeRole 時に生成されるセッションポリシーが、内部検証操作に対して S3 AP ARN パターンを含まない。*

**AI/ML への影響**: テーブル作成ができないため、以下がブロック:
- Feature Store テーブル登録
- ML 学習データ用 Delta Lake マネージドテーブル
- モデル学習の Unity Catalog リネージ追跡
- 学習データへのカラムレベルガバナンスタグ

---

## デモ 3: サブディレクトリ一覧 — ブロック（エラー証跡）

**ユースケース**: バッチ処理（画像分類、ドキュメント抽出）のためにサブディレクトリ内のファイルを一覧取得。

```python
# サブディレクトリ内容の一覧取得を試行
files = dbutils.fs.ls("s3://<s3ap-alias>/media/images/")
```

**結果**: ❌ `getFileStatus` で `AccessDenied` — プレフィックスベースの ListObjectsV2 がサブディレクトリに対してブロック。

![セッションポリシーによりサブディレクトリ一覧がブロック](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/databricks-ai-subdir-listing-blocked.png)

*サブディレクトリ一覧が AccessDenied で失敗。UC セッションポリシーはトップレベルの一覧を許可するが、サブディレクトリに対するプレフィックススコープの ListObjectsV2 をブロック。*

**AI/ML への影響**: サブディレクトリ一覧がないため、`spark.read.format("binaryFile").load("s3://<alias>/media/images/")` のようなバッチ処理パターンがファイルを自動検出できない。

---

## デモ 4: Instance Profile + boto3（PoC パス — 動作確認済み）

**ユースケース**: AI 処理のために FSx for ONTAP から非構造化データ（画像、ドキュメント）を読み取り。

```python
import boto3
from PIL import Image
from io import BytesIO

# Instance Profile 経由で FSx for ONTAP から画像を読み取り（UC をバイパス）
s3 = boto3.client('s3', region_name='ap-northeast-1')
response = s3.get_object(
    Bucket='<s3ap-alias>',
    Key='media/images/inspection_photo.jpg'
)
img = Image.open(BytesIO(response['Body'].read()))
print(f"✅ 画像読み込み完了: {img.size}, {img.mode}")
```

**結果**: ✅ Customer-managed VPC の Dedicated クラスター上で Instance Profile 経由により FSx for ONTAP S3 AP から画像ファイルを正常に読み取り。

**⚠️ ガバナンス警告**: このパスは Unity Catalog を完全にバイパスします。Databricks 内でのリネージ、アクセス制御、監査証跡はありません。データオーナー、セキュリティオーナー、プラットフォームオーナーの明示的な承認を得た管理された PoC にのみ使用してください。

---

## デモ 5: MLflow 実験トラッキング（動作確認済み）

**ユースケース**: FSx for ONTAP データを学習ソースとして使用する ML 実験を追跡。

```python
import mlflow

# MLflow トラッキングはストレージパスに依存せず動作
with mlflow.start_run(run_name="fsxn_sensor_model"):
    mlflow.log_param("data_source", "fsxn_s3ap")
    mlflow.log_param("data_path", "s3://<s3ap-alias>/bronze/sensor_data/")
    mlflow.log_param("access_method", "instance_profile_boto3")

    # boto3 経由で読み取ったデータでモデルを学習...
    # mlflow.log_metric("accuracy", 0.95)
    # mlflow.sklearn.log_model(model, "model")

    print("✅ MLflow 実験トラッキング完了")
```

**結果**: ✅ MLflow 実験トラッキングはデータアクセス方法に関係なく動作。ただし、boto3 経由でデータを読み取った場合、Unity Catalog リネージ（どのテーブル → どのモデル）は記録されない。

**ベストプラクティス**: boto3 PoC パスを使用する場合でも、学習済みモデルは Unity Catalog Model Registry に登録してガバナンスを確保。

---

## 将来の機能（UC セッションポリシー解消後）

Databricks が S3 Access Point に対する Unity Catalog セッションポリシーの境界を解消した場合、以下の AI/ML ワークフローが利用可能になります:

### FSx for ONTAP 上の Feature Store

```python
# 将来: FSx for ONTAP 上の Feature テーブル（CREATE TABLE が必要）
from databricks.feature_engineering import FeatureEngineeringClient

fe = FeatureEngineeringClient()
fe.create_table(
    name="fsxn_lakehouse.features.customer_features",
    primary_keys=["customer_id"],
    df=feature_df,
    description="FSx for ONTAP に保存された顧客 ML 特徴量"
)
```

### CLIP による画像エンベディング

```python
# 将来: バッチ画像処理（サブディレクトリ一覧が必要）
images_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.{jpg,png}") \
    .load("s3://<s3ap-alias>/media/images/")

# CLIP エンベディングを生成
embeddings_df = images_df.withColumn(
    "embedding", generate_clip_embedding(col("content"))
)
```

### RAG 用ドキュメント処理

```python
# 将来: ドキュメントテキスト抽出（binaryFile ディレクトリ読み取りが必要）
docs_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.{pdf,docx}") \
    .load("s3://<s3ap-alias>/media/documents/")

# テキスト抽出、チャンク分割、エンベディング生成（RAG パイプライン）
```

### Mosaic AI モデル学習

```python
# 将来: UC リネージ付きガバナンスモデル学習
# 必要: S3 AP 上の UC テーブル → 学習データ → モデル → UC Model Registry
# 完全リネージ: データソース → 特徴量 → モデル → サービングエンドポイント
```

---

## 検証結果サマリー

| 機能 | ステータス | アクセスパス | ユースケース |
|---|:---:|---|---|
| Spark CSV 読み取り（明示パス） | ✅ 検証済み | UC External Location | ML 用構造化データ |
| トップレベルファイル一覧 | ✅ 検証済み | UC External Location | ファイル検出 |
| boto3 ファイル読み取り（ドライバー） | ✅ 検証済み | Instance Profile | 非構造化データ PoC |
| MLflow トラッキング | ✅ 検証済み | 独立 | 実験管理 |
| CREATE TABLE | ❌ ブロック | UC External Location | Feature Store、ガバナンステーブル |
| サブディレクトリ一覧 | ❌ ブロック | UC External Location | バッチファイル処理 |
| Delta 書き戻し | ❌ ブロック | UC External Location | 特徴量エンジニアリング出力 |
| Feature Store 登録 | ❌ ブロック | CREATE TABLE が必要 | ML 特徴量管理 |
| エグゼキュータースケール処理 | ⚠️ 未検証 | — | 分散 ML ワークロード |

---

## 業界別ユースケース（将来の状態）

### 製造業 / 品質検査

| ユースケース | Databricks 機能 | FSx 上のデータ | ステータス |
|---|---|---|---|
| センサー異常検知 | MLflow + Spark ML | IoT センサー Parquet/CSV | ⚠️ 明示パス読み取りのみ |
| 画像欠陥分類 | CLIP / カスタム CNN | 製品画像 | ❌ バッチ読み取りブロック |
| 予知保全 | Feature Store + AutoML | 設備テレメトリ | ❌ Feature テーブルブロック |
| 品質レポート生成 | LLM (Foundation Model API) | 検査ドキュメント | ⚠️ boto3 PoC のみ |

### 金融 / 保険

| ユースケース | Databricks 機能 | FSx 上のデータ | ステータス |
|---|---|---|---|
| ドキュメント分類 | Spark NLP / binaryFile | 契約書 PDF | ❌ バッチ読み取りブロック |
| 不正検知特徴量 | Feature Store | 取引データ | ❌ Feature テーブルブロック |
| リスクモデル学習 | MLflow + XGBoost | 過去データ | ⚠️ 明示パス読み取りのみ |
| 規制文書テキスト抽出 | UDF + pypdf | コンプライアンス文書 | ⚠️ boto3 PoC のみ |

### 医療 / ライフサイエンス

| ユースケース | Databricks 機能 | FSx 上のデータ | ステータス |
|---|---|---|---|
| 医療画像分析 | torchvision / CLIP | DICOM/PNG 画像 | ❌ バッチ読み取りブロック |
| 臨床試験データ準備 | Spark ETL | 試験ドキュメント | ⚠️ 明示パス読み取りのみ |
| 研究論文エンベディング | Sentence Transformers | PDF 論文 | ❌ バッチ読み取りブロック |
| 患者記録抽出 | pypdf + NLP | スキャン記録 | ⚠️ boto3 PoC のみ |

### メディア / コンテンツ管理

| ユースケース | Databricks 機能 | FSx 上のデータ | ステータス |
|---|---|---|---|
| 画像類似検索 | CLIP エンベディング | メディアアセット | ❌ バッチ読み取りブロック |
| 動画フレーム抽出 | OpenCV + Spark | 動画ファイル | ❌ バッチ読み取りブロック |
| コンテンツタグ付け | Foundation Model API | 全メディア | ⚠️ boto3 PoC のみ |
| アセットメタデータカタログ | Delta テーブル | ファイルメタデータ | ❌ CREATE TABLE ブロック |

---

## 現時点での推奨代替手段

UC セッションポリシーの解消を待つ間、FSx for ONTAP データに対する AI/ML には以下の検証済みパスを使用:

| AI/ML ニーズ | 推奨サービス | ステータス | リファレンス |
|---|---|---|---|
| ドキュメント RAG | Amazon Bedrock Knowledge Bases | AWS ドキュメント済み | [チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html) |
| OCR / Document AI | Snowflake PARSE_DOCUMENT | ✅ 検証済み | [デモガイド](../../../snowflake/docs/ja/ai-demo-guide.md) |
| テキスト要約 | Snowflake Cortex SUMMARIZE | ✅ 検証済み | [デモガイド](../../../snowflake/docs/ja/ai-demo-guide.md) |
| ファイル処理 (Lambda) | AWS Lambda | AWS ドキュメント済み | [チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html) |
| SQL 分析 | Amazon Athena | ✅ 検証済み (Part 1) | [ブログ](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh) |
| Spark ETL | EMR Serverless | シリーズ内で検証済み | [チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-run-spark-with-emr-serverless.html) |

---

## はじめに

1. **インフラデプロイ** — [セットアップガイド](setup-guide.md) に従う
2. **External Location 設定** — `access_point` フィールドを設定（[UC 統合](unity-catalog-integration.md)）
3. **明示的ファイル読み取りテスト** — 既知のファイルパスで Spark 読み取りを検証
4. **PoC 用**: Dedicated クラスターに Instance Profile を設定
5. **実験トラッキング** — アクセスパスに関係なく MLflow を使用
6. **モニタリング**: S3 AP サポートに関する Databricks プラットフォームアップデートを監視

## Databricks AI/ML ドキュメント

- [Mosaic AI 概要](https://docs.databricks.com/en/machine-learning/index.html)
- [Feature Engineering](https://docs.databricks.com/en/machine-learning/feature-store/index.html)
- [MLflow on Databricks](https://docs.databricks.com/en/mlflow/index.html)
- [Foundation Model APIs](https://docs.databricks.com/en/machine-learning/foundation-models/index.html)
- [Unity Catalog Models](https://docs.databricks.com/aws/en/catalog-explorer/explore-models)
- [External Locations](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials)
- [Instance Profiles (レガシー)](https://docs.databricks.com/en/admin/sql/data-access-configuration.html)
- [Binary File Data Source](https://docs.databricks.com/en/query/formats/binary-file.html)
