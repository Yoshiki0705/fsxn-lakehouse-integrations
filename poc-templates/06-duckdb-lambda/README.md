🌐 **English** | [日本語](README-ja.md)

# Module 06: DuckDB Lambda (Cheapest Path — $0.00001/query)

## Overview

DuckDB runs inside Lambda (arm64, 1024 MB) and queries Parquet on FSx for ONTAP via S3 AP. Zero infrastructure, sub-second warm queries.

## Quick Start

```bash
# 1. Generate Lambda layer
docker run --rm --platform linux/arm64 --entrypoint bash \
  -v "$(pwd)/dist:/output" \
  public.ecr.aws/lambda/python:3.12-arm64 \
  -c "pip install duckdb==1.1.3 --target /tmp/python/lib/python3.12/site-packages/ --quiet && \
      cd /tmp && zip -qr /output/duckdb-layer.zip python/"

# 2. Deploy (CloudFormation)
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name fsxn-duckdb-lambda \
  --parameter-overrides S3ApAlias=<AP_ALIAS> \
  --capabilities CAPABILITY_IAM

# 3. Test
aws lambda invoke --function-name fsxn-duckdb-query \
  --payload '{"query":"SELECT COUNT(*) FROM read_parquet('"'"'s3://{S3_AP}/sensor-data/sensor_data.parquet'"'"')"}' \
  response.json && cat response.json | jq .
```

## Critical Configuration (handler.py)

```python
conn.execute("SET home_directory = '/tmp';")        # Lambda has no home
conn.execute("SET s3_url_style = 'path';")          # Required for AP alias
conn.execute("SET s3_endpoint = 's3.<REGION>.amazonaws.com';")  # Explicit endpoint
```

## Benchmark

| Test | Latency |
|------|---------|
| Cold start | 1,854 ms |
| Warm COUNT(*) 10K rows | **452 ms** |
| Warm GROUP BY | 1,411 ms |
| Write-back (COPY TO) | 304 ms |

## Cost

- ~$0.00001/query
- 1000 queries/day = **$1.10/month**
- Zero idle cost

## When to Use

✅ Cheapest ad-hoc analytics, API-driven queries, IoT quick analysis
❌ Datasets > 10 GB, need governance/catalog, need DWH JOINs
