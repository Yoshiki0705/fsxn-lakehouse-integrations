"""
FSx for ONTAP S3 AP — DuckDB Lambda Handler (PoC Template)

Simplified handler for PoC validation. For production, see:
  integrations/duckdb/lambda/handler.py

Critical settings for S3 AP:
  1. SET home_directory = '/tmp'     — Lambda has no home
  2. SET s3_url_style = 'path'       — Required for AP alias
  3. SET s3_endpoint = 's3.<REGION>.amazonaws.com'  — Explicit endpoint
"""

import json
import os
import time
import duckdb

_connection = None
_is_cold_start = True


def get_connection():
    """Initialize DuckDB with httpfs configured for S3 AP."""
    global _connection
    if _connection:
        return _connection

    conn = duckdb.connect(":memory:")
    conn.execute("SET home_directory = '/tmp';")
    conn.execute("INSTALL httpfs; LOAD httpfs;")

    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    conn.execute(f"SET s3_region = '{region}';")
    conn.execute(f"SET s3_access_key_id = '{os.environ.get('AWS_ACCESS_KEY_ID', '')}';")
    conn.execute(f"SET s3_secret_access_key = '{os.environ.get('AWS_SECRET_ACCESS_KEY', '')}';")
    token = os.environ.get("AWS_SESSION_TOKEN", "")
    if token:
        conn.execute(f"SET s3_session_token = '{token}';")

    # Critical for S3 AP alias resolution
    conn.execute("SET s3_url_style = 'path';")
    conn.execute(f"SET s3_endpoint = 's3.{region}.amazonaws.com';")

    _connection = conn
    return conn


def lambda_handler(event, context):
    """Execute DuckDB query on FSx for ONTAP data via S3 AP."""
    global _is_cold_start
    start = time.time()
    cold = _is_cold_start
    _is_cold_start = False

    query = event.get("query", "SELECT 1 AS test")

    # Replace {S3_AP} placeholder with actual alias
    ap_alias = os.environ.get("S3_ACCESS_POINT_ALIAS", "")
    if "{S3_AP}" in query and ap_alias:
        query = query.replace("{S3_AP}", ap_alias)

    try:
        conn = get_connection()
        result = conn.execute(query)
        columns = [d[0] for d in result.description] if result.description else []
        rows = result.fetchmany(1000)
        data = [dict(zip(columns, row)) for row in rows]

        elapsed = round((time.time() - start) * 1000, 1)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "data": data,
                "row_count": len(data),
                "query_time_ms": elapsed,
                "cold_start": cold,
            }, default=str),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "cold_start": cold}),
        }
