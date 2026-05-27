🌐 [English](README.md) | **日本語**

# モジュール 06: DuckDB Lambda（最安パス — $0.00001/クエリ）

## 概要

DuckDB が Lambda 内（arm64, 1024 MB）で動作し、S3 AP 経由で FSx for ONTAP 上の Parquet をクエリ。ゼロインフラ、サブ秒ウォームクエリ。

## クイックスタート

```bash
# 1. Lambda レイヤー生成
docker run --rm --platform linux/arm64 --entrypoint bash \
  -v "$(pwd)/dist:/output" \
  public.ecr.aws/lambda/python:3.12-arm64 \
  -c "pip install duckdb==1.1.3 --target /tmp/python/lib/python3.12/site-packages/ --quiet && \
      cd /tmp && zip -qr /output/duckdb-layer.zip python/"

# 2. デプロイ (CloudFormation)
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name fsxn-duckdb-lambda \
  --parameter-overrides S3ApAlias=<AP_ALIAS> \
  --capabilities CAPABILITY_IAM

# 3. テスト
aws lambda invoke --function-name fsxn-duckdb-query \
  --payload '{"query":"SELECT COUNT(*) FROM read_parquet('"'"'s3://{S3_AP}/sensor-data/sensor_data.parquet'"'"')"}' \
  response.json && cat response.json | jq .
```

## 重要な設定 (handler.py)

```python
conn.execute("SET home_directory = '/tmp';")        # Lambda にはホームディレクトリがない
conn.execute("SET s3_url_style = 'path';")          # AP エイリアスに必須
conn.execute("SET s3_endpoint = 's3.<REGION>.amazonaws.com';")  # 明示的エンドポイント
```

## ベンチマーク

| テスト | レイテンシ |
|--------|---------|
| コールドスタート | 1,854 ms |
| ウォーム COUNT(*) 10K 行 | **452 ms** |
| ウォーム GROUP BY | 1,411 ms |
| 書き戻し (COPY TO) | 304 ms |

## コスト

- ~$0.00001/クエリ
- 1000クエリ/日 = **$1.10/月**
- ゼロアイドルコスト

## 使用すべき場面

✅ 最安のアドホック分析、API 駆動クエリ、IoT クイック分析
❌ 10 GB 超のデータセット、ガバナンス/カタログが必要、DWH JOIN が必要
