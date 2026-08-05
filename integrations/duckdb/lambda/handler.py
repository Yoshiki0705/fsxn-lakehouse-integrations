"""
FSx for ONTAP DuckDB Integration — Lambda Handler

Executes DuckDB SQL queries on FSx for ONTAP data via S3 Access Point (VPC-scoped).
DuckDB runs in-process within Lambda — no external database server required.

Features:
  - httpfs extension for S3 Access Point connectivity
  - Automatic credential configuration from execution role
  - Cold start vs warm invocation tracking
  - Execution metrics (time, rows, data scanned)
  - Support for Parquet, CSV, and JSON formats

Event payload:
  {
    "query": "SELECT * FROM read_parquet('s3://<ap-alias>/path/*.parquet') LIMIT 10",
    "format": "json" | "csv",       # Output format (default: json)
    "max_rows": 1000                 # Max rows to return (default: 1000)
  }
"""

import json
import logging
import os
import time
import traceback
from typing import Any

import duckdb

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Cold start tracking ---
_is_cold_start = True
_db_connection = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    """Get or create DuckDB connection with httpfs configured."""
    global _db_connection

    if _db_connection is not None:
        return _db_connection

    logger.info("Initializing DuckDB connection with httpfs extension")

    conn = duckdb.connect(database=":memory:")

    # Set home directory for Lambda environment
    conn.execute("SET home_directory = '/tmp';")

    # Install and load httpfs extension
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")

    # Configure S3 credentials from Lambda execution role (automatic via IAM)
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "ap-northeast-1"))
    conn.execute(f"SET s3_region = '{region}';")

    # Use credential chain (Lambda execution role provides credentials via env vars)
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    aws_session_token = os.environ.get("AWS_SESSION_TOKEN", "")

    if aws_access_key and aws_secret_key:
        conn.execute(f"SET s3_access_key_id = '{aws_access_key}';")
        conn.execute(f"SET s3_secret_access_key = '{aws_secret_key}';")
        if aws_session_token:
            conn.execute(f"SET s3_session_token = '{aws_session_token}';")

    # Performance settings
    conn.execute("SET threads TO 4;")
    conn.execute("SET memory_limit = '512MB';")
    # S3 AP aliases require path-style access
    conn.execute("SET s3_url_style = 'path';")
    conn.execute("SET s3_endpoint = 's3.ap-northeast-1.amazonaws.com';")
    conn.execute("SET s3_use_ssl = true;")

    _db_connection = conn
    logger.info("DuckDB connection initialized successfully")
    return conn


def _format_results(result, columns: list[str], output_format: str, max_rows: int) -> dict:
    """Format DuckDB query results."""
    rows = result.fetchmany(max_rows)
    row_count = len(rows)

    if output_format == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(rows)
        return {
            "format": "csv",
            "data": output.getvalue(),
            "row_count": row_count,
            "columns": columns,
        }
    else:
        # JSON format (default)
        data = [dict(zip(columns, [_serialize_value(v) for v in row])) for row in rows]
        return {
            "format": "json",
            "data": data,
            "row_count": row_count,
            "columns": columns,
        }


def _serialize_value(value: Any) -> Any:
    """Serialize DuckDB values to JSON-compatible types."""
    if value is None:
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    # datetime, date, etc.
    return str(value)


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda entry point for DuckDB query execution.

    Args:
        event: {"query": str, "format": str, "max_rows": int}
        context: Lambda context object

    Returns:
        Query results with execution metrics
    """
    global _is_cold_start

    start_time = time.time()
    cold_start = _is_cold_start
    _is_cold_start = False

    logger.info(f"Invocation start — cold_start={cold_start}, "
                f"memory_limit={context.memory_limit_in_mb}MB")

    # Parse input
    query = event.get("query")
    if not query:
        return {
            "statusCode": 400,
            "error": "Missing required field: 'query'",
        }

    output_format = event.get("format", "json").lower()
    max_rows = min(event.get("max_rows", 1000), 10000)  # Cap at 10k rows

    # Substitute S3 AP alias placeholder if present
    s3_ap_alias = os.environ.get("S3_ACCESS_POINT_ALIAS", "")
    if "{S3_AP}" in query and s3_ap_alias:
        query = query.replace("{S3_AP}", s3_ap_alias)

    logger.info(f"Executing query (format={output_format}, max_rows={max_rows}): "
                f"{query[:200]}...")

    try:
        conn = _get_connection()
        init_time = time.time()

        # Execute query
        result = conn.execute(query)
        columns = [desc[0] for desc in result.description] if result.description else []

        exec_time = time.time()

        # Format results
        formatted = _format_results(result, columns, output_format, max_rows)

        end_time = time.time()

        # Build response with metrics
        response = {
            "statusCode": 200,
            "results": formatted,
            "metrics": {
                "total_time_ms": round((end_time - start_time) * 1000, 2),
                "init_time_ms": round((init_time - start_time) * 1000, 2),
                "query_time_ms": round((exec_time - init_time) * 1000, 2),
                "format_time_ms": round((end_time - exec_time) * 1000, 2),
                "cold_start": cold_start,
                "memory_limit_mb": context.memory_limit_in_mb,
                "rows_returned": formatted["row_count"],
            },
        }

        logger.info(f"Query completed — rows={formatted['row_count']}, "
                    f"total_time={response['metrics']['total_time_ms']}ms")

        return response

    except duckdb.Error as e:
        error_time = time.time()
        logger.error(f"DuckDB error: {e}")
        return {
            "statusCode": 500,
            "error": f"DuckDB error: {str(e)}",
            "metrics": {
                "total_time_ms": round((error_time - start_time) * 1000, 2),
                "cold_start": cold_start,
            },
        }
    except Exception as e:
        error_time = time.time()
        logger.error(f"Unexpected error: {traceback.format_exc()}")
        return {
            "statusCode": 500,
            "error": f"Unexpected error: {str(e)}",
            "metrics": {
                "total_time_ms": round((error_time - start_time) * 1000, 2),
                "cold_start": cold_start,
            },
        }
