#!/usr/bin/env python3
"""
Snowflake Verification Script — SYSTEM$VERIFY_CATALOG_INTEGRATION + TO_FILE retest
====================================================================================
Run from local environment with snowflake-connector-python installed.

Prerequisites:
  pip install snowflake-connector-python

Usage:
  # Interactive (prompts for password):
  python run-snowflake-verifications.py

  # With environment variables:
  export SNOWFLAKE_USER=your_user
  export SNOWFLAKE_PASSWORD=your_password
  python run-snowflake-verifications.py

Snowflake Account: MH89262 (CVDRQJT, ap-northeast-1)
"""

import os
import sys
import json
from datetime import datetime

try:
    import snowflake.connector
except ImportError:
    print("ERROR: snowflake-connector-python not installed")
    print("  pip install snowflake-connector-python")
    sys.exit(1)


# Connection parameters
ACCOUNT = "vp28055.ap-northeast-1.aws"
WAREHOUSE = "COMPUTE_WH"
DATABASE = "FSXN_LAKEHOUSE"
SCHEMA = "PUBLIC"
ROLE = "ACCOUNTADMIN"


def get_connection():
    """Establish Snowflake connection."""
    user = os.environ.get("SNOWFLAKE_USER")
    password = os.environ.get("SNOWFLAKE_PASSWORD")

    if not user:
        user = input("Snowflake username: ")
    if not password:
        import getpass
        password = getpass.getpass("Snowflake password: ")

    conn = snowflake.connector.connect(
        account=ACCOUNT,
        user=user,
        password=password,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
        role=ROLE,
    )
    return conn


def test_verify_catalog_integration(cursor):
    """Test 1: SYSTEM$VERIFY_CATALOG_INTEGRATION for credential vending case."""
    print("\n" + "=" * 70)
    print("TEST 1: SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT')")
    print("=" * 70)

    try:
        cursor.execute(
            "SELECT SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT');"
        )
        result = cursor.fetchone()
        print(f"\nResult: {result[0]}")
        return {"test": "SYSTEM$VERIFY_CATALOG_INTEGRATION", "status": "success", "result": result[0]}
    except Exception as e:
        print(f"\nError: {e}")
        return {"test": "SYSTEM$VERIFY_CATALOG_INTEGRATION", "status": "error", "error": str(e)}


def test_to_file_string_literal(cursor):
    """Test 2: TO_FILE with string literal stage name (support-recommended syntax)."""
    print("\n" + "=" * 70)
    print("TEST 2: TO_FILE with string literal syntax")
    print("  Recommended by Snowflake Support (Snowflake support guidance)")
    print("=" * 70)

    query = """
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'Describe this image briefly.',
  TO_FILE('@FSXN_LAKEHOUSE_DB.PUBLIC.FSXN_AP_ARN_TEST_STAGE', '_sample.png')
) AS vision_result;
"""
    print(f"\nQuery:\n{query.strip()}")

    try:
        cursor.execute(query)
        result = cursor.fetchone()
        print(f"\nResult: {result[0][:200]}...")
        return {"test": "TO_FILE_string_literal", "status": "success", "result": result[0][:500]}
    except Exception as e:
        print(f"\nError: {e}")
        return {"test": "TO_FILE_string_literal", "status": "error", "error": str(e)}


def test_to_file_alternative_formats(cursor):
    """Test 2b: Try alternative TO_FILE syntax formats if Test 2 fails."""
    print("\n" + "=" * 70)
    print("TEST 2b: TO_FILE alternative syntax formats")
    print("=" * 70)

    queries = [
        # Format from support: fully qualified with quotes
        (
            "Fully qualified with single quotes",
            """SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'Describe this image briefly.',
  TO_FILE('@FSXN_LAKEHOUSE_DB.PUBLIC.FSXN_AP_ARN_TEST_STAGE', '_sample.png')
) AS vision_result;""",
        ),
        # Simple stage name
        (
            "Simple stage name with quotes",
            """SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'Describe this image briefly.',
  TO_FILE('@FSXN_AP_ARN_TEST_STAGE', '_sample.png')
) AS vision_result;""",
        ),
    ]

    results = []
    for desc, query in queries:
        print(f"\n--- {desc} ---")
        print(f"Query: {query.strip()[:120]}...")
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            print(f"Result: SUCCESS - {result[0][:100]}...")
            results.append({"format": desc, "status": "success", "result": result[0][:500]})
        except Exception as e:
            print(f"Error: {e}")
            results.append({"format": desc, "status": "error", "error": str(e)})

    return results


def test_list_namespaces(cursor):
    """Test 3: SYSTEM$LIST_NAMESPACES_FROM_CATALOG."""
    print("\n" + "=" * 70)
    print("TEST 3: SYSTEM$LIST_NAMESPACES_FROM_CATALOG('S3TABLES_GLUE_REST_INT')")
    print("=" * 70)

    try:
        cursor.execute(
            "SELECT SYSTEM$LIST_NAMESPACES_FROM_CATALOG('S3TABLES_GLUE_REST_INT');"
        )
        result = cursor.fetchone()
        print(f"\nResult: {result[0]}")
        return {"test": "LIST_NAMESPACES", "status": "success", "result": result[0]}
    except Exception as e:
        print(f"\nError: {e}")
        return {"test": "LIST_NAMESPACES", "status": "error", "error": str(e)}


def test_list_tables(cursor):
    """Test 4: SYSTEM$LIST_ICEBERG_TABLES_FROM_CATALOG."""
    print("\n" + "=" * 70)
    print("TEST 4: SYSTEM$LIST_ICEBERG_TABLES_FROM_CATALOG")
    print("=" * 70)

    try:
        cursor.execute(
            "SELECT SYSTEM$LIST_ICEBERG_TABLES_FROM_CATALOG('S3TABLES_GLUE_REST_INT', 'metadata');"
        )
        result = cursor.fetchone()
        print(f"\nResult: {result[0]}")
        return {"test": "LIST_TABLES", "status": "success", "result": result[0]}
    except Exception as e:
        print(f"\nError: {e}")
        return {"test": "LIST_TABLES", "status": "error", "error": str(e)}


def main():
    print("=" * 70)
    print("Snowflake Verification Script")
    print(f"Date: {datetime.utcnow().isoformat()}Z")
    print(f"Account: {ACCOUNT}")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()

    all_results = []

    # Test 1: Verify catalog integration health
    all_results.append(test_verify_catalog_integration(cursor))

    # Test 2: TO_FILE with string literal
    result2 = test_to_file_string_literal(cursor)
    all_results.append(result2)

    # Test 2b: If TO_FILE failed, try alternatives
    if result2["status"] == "error":
        alt_results = test_to_file_alternative_formats(cursor)
        all_results.extend([{"test": f"TO_FILE_alt_{i}", **r} for i, r in enumerate(alt_results)])

    # Test 3: List namespaces
    all_results.append(test_list_namespaces(cursor))

    # Test 4: List tables
    all_results.append(test_list_tables(cursor))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in all_results:
        status_icon = "✅" if r.get("status") == "success" else "❌"
        print(f"  {status_icon} {r.get('test', 'unknown')}: {r.get('status')}")

    # Save results
    output_file = f"snowflake-verification-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "account": ACCOUNT,
                "results": all_results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nResults saved to: {output_file}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
