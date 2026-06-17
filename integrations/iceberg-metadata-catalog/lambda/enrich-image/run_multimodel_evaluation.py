"""
run_multimodel_evaluation — Execute Multi-Model Classification on Existing Catalog

Reads image file records from the existing Iceberg metadata table (already
populated by the initial-metadata-scan.py and AI enrichment pipeline),
runs multi-model classification on each image file, and generates an
evaluation report comparing single-model vs multi-model results.

Prerequisites:
  - Iceberg metadata table already populated (Phase 1-3 verified)
  - Bedrock API access configured (Claude Haiku + Nova Lite)
  - FSx for ONTAP S3 Access Point accessible

Usage:
    # Run from an environment with Bedrock + S3 AP access (EC2 in VPC or Lambda)
    python run_multimodel_evaluation.py \
        --access-point-arn <S3_AP_ARN> \
        --max-files 20 \
        --output evaluation_results.json

    # Or using existing single-model results from the Iceberg table
    python run_multimodel_evaluation.py \
        --use-existing-classifications \
        --max-files 20 \
        --output evaluation_results.json

References:
  - Blog Part 2: AI Enrichment Pipeline (Bedrock Vision classification at 0.9 confidence)
  - PoC Results: 38 files scanned, ~6 sec/file, ~$0.01/file
  - Phase 3 evidence: Claude Vision confidence 0.95, 7/7 PII entities
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any

import boto3

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multimodel_classify import classify_image_multimodel, MODELS
from evaluation import (
    evaluate_predictions,
    evaluate_agreement_stats,
    estimate_cost,
    run_evaluation_report,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")


def fetch_image_records_from_iceberg(max_files: int = 20) -> list[dict]:
    """
    Fetch image file records from the existing Iceberg metadata table via Athena.

    Returns records with: file_id, file_path, file_type, classification (existing single-model)
    """
    athena = boto3.client("athena", region_name=REGION)

    query = f"""
    SELECT file_id, file_path, file_type, classification, confidence_score
    FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
    WHERE file_type LIKE 'image/%'
      AND is_deleted = false
    ORDER BY created_at DESC
    LIMIT {max_files}
    """

    # Start query execution
    response = athena.start_query_execution(
        QueryString=query,
        ResultConfiguration={
            "OutputLocation": f"s3://athena-results-{REGION}/multimodel-eval/"
        },
    )
    query_id = response["QueryExecutionId"]

    # Wait for completion
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)

    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query failed: {state}")

    # Get results
    results = athena.get_query_results(QueryExecutionId=query_id)
    rows = results["ResultSet"]["Rows"][1:]  # Skip header

    records = []
    for row in rows:
        cells = [c.get("VarCharValue", "") for c in row["Data"]]
        records.append({
            "file_id": cells[0],
            "file_path": cells[1],
            "file_type": cells[2],
            "existing_classification": cells[3],
            "existing_confidence": float(cells[4]) if cells[4] else 0.0,
        })

    logger.info(f"Fetched {len(records)} image records from Iceberg table")
    return records


def run_single_model_classification(
    image_bytes: bytes, media_type: str
) -> dict:
    """Run single-model (Claude Haiku) classification for baseline comparison."""
    from multimodel_classify import _classify_with_model

    model_config = {
        "id": "anthropic.claude-3-haiku-20240307-v1:0",
        "name": "claude-haiku",
        "api_format": "anthropic",
    }
    return _classify_with_model(model_config, image_bytes, media_type)


def run_evaluation(
    access_point_arn: str,
    max_files: int = 20,
    use_existing: bool = False,
) -> dict:
    """
    Run the complete multi-model evaluation pipeline.

    Steps:
    1. Fetch image records from Iceberg (or use existing classifications)
    2. For each image: run single-model + multi-model classification
    3. Compare results and generate evaluation report
    """
    import base64

    logger.info(f"Starting multi-model evaluation (max {max_files} files)")
    start_time = time.time()

    # Step 1: Get image records
    records = fetch_image_records_from_iceberg(max_files)
    if not records:
        logger.warning("No image records found in Iceberg table")
        return {"error": "no_records"}

    s3 = boto3.client("s3", region_name=REGION)

    single_results = []
    multi_results = []
    ground_truths = []  # Use existing classification as pseudo-ground-truth for now
    timings = {"single": [], "multi": []}

    for i, record in enumerate(records):
        file_path = record["file_path"]
        file_type = record["file_type"]
        logger.info(f"[{i+1}/{len(records)}] Processing: {file_path}")

        # Read image from S3 AP
        try:
            s3_key = "/".join(file_path.split("/")[4:]) if file_path.startswith("/") else file_path
            response = s3.get_object(Bucket=access_point_arn, Key=s3_key)
            image_bytes = response["Body"].read(5_000_000)
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}. Skipping.")
            continue

        # Single-model classification
        t0 = time.time()
        single_result = run_single_model_classification(image_bytes, file_type)
        timings["single"].append(time.time() - t0)
        single_results.append(single_result)

        # Multi-model classification
        t0 = time.time()
        multi_result = classify_image_multimodel(image_bytes, file_type)
        timings["multi"].append(time.time() - t0)
        multi_results.append(multi_result)

        # Use existing classification as ground truth (pseudo-label)
        # In production, replace with manually verified labels
        ground_truths.append(record["existing_classification"])

        logger.info(
            f"  Single: {single_result.get('classification')} ({single_result.get('confidence_score', 0):.2f})"
            f" | Multi: {multi_result['classification']} ({multi_result['confidence_score']:.2f}, {multi_result['agreement']})"
        )

    # Step 3: Generate evaluation report
    report = run_evaluation_report(single_results, multi_results, ground_truths)

    # Add timing stats
    report["timing"] = {
        "single_model_avg_sec": round(sum(timings["single"]) / len(timings["single"]), 2) if timings["single"] else 0,
        "multi_model_avg_sec": round(sum(timings["multi"]) / len(timings["multi"]), 2) if timings["multi"] else 0,
        "total_elapsed_sec": round(time.time() - start_time, 1),
    }

    # Add agreement stats
    report["multi_model"]["agreement"] = evaluate_agreement_stats(multi_results)

    logger.info(f"\n{'='*60}")
    logger.info(f"EVALUATION COMPLETE ({len(records)} files)")
    logger.info(f"Single-model F1: {report['single_model']['metrics']['f1_macro']:.3f}")
    logger.info(f"Multi-model F1:  {report['multi_model']['metrics']['f1_macro']:.3f}")
    logger.info(f"F1 improvement:  {report['comparison']['f1_improvement']:.3f}")
    logger.info(f"Target met (+5%): {report['comparison']['target_f1_improvement_5pct']}")
    logger.info(f"Agreement: {report['multi_model']['agreement']}")
    logger.info(f"{'='*60}\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="Run multi-model classification evaluation")
    parser.add_argument("--access-point-arn", required=True, help="FSx S3 Access Point ARN or alias")
    parser.add_argument("--max-files", type=int, default=20, help="Max files to evaluate")
    parser.add_argument("--output", default="evaluation_results.json", help="Output file path")
    parser.add_argument("--use-existing-classifications", action="store_true", help="Use existing Iceberg classifications as ground truth")

    args = parser.parse_args()

    report = run_evaluation(
        access_point_arn=args.access_point_arn,
        max_files=args.max_files,
        use_existing=args.use_existing_classifications,
    )

    # Save report
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"Report saved to {args.output}")

    # Print summary
    if "error" not in report:
        print(f"\n📊 Evaluation Summary:")
        print(f"   Files evaluated: {report['dataset_size']}")
        print(f"   Single-model F1: {report['single_model']['metrics']['f1_macro']:.3f}")
        print(f"   Multi-model F1:  {report['multi_model']['metrics']['f1_macro']:.3f}")
        print(f"   F1 improvement:  {report['comparison']['f1_improvement']:+.3f}")
        print(f"   Target (+5%):    {'✅ MET' if report['comparison']['target_f1_improvement_5pct'] else '❌ NOT MET'}")
        print(f"   Recommendation:  {report['recommendation']}")
        print(f"   Cost ($/file):   single=${report['cost']['single_model_cost_per_file_usd']:.5f} / multi=${report['cost']['multi_model_cost_per_file_usd']:.5f}")
        print(f"   Latency (avg):   single={report['timing']['single_model_avg_sec']:.1f}s / multi={report['timing']['multi_model_avg_sec']:.1f}s")


if __name__ == "__main__":
    main()
