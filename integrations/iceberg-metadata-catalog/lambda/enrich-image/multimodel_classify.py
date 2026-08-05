"""
multimodel_classify — Multi-Model Image Classification with Majority Vote

Extends the single-model approach (handler.py) to run the same image through
multiple Bedrock models in parallel, compare results, and apply a majority-vote
consensus strategy (Debby pattern).

Target: +5% F1 score improvement over single-model baseline.

Models:
  - Claude 3 Haiku (primary, current baseline)
  - Amazon Titan Image (if Vision-capable, else Nova Lite)
  - Amazon Nova Lite

Decision logic:
  - 3/3 agree → accept with high confidence (avg confidence)
  - 2/3 agree → accept majority with moderate confidence
  - 0 agree (3-way split) → escalate to human review queue

Output: classification + confidence + model_agreement + individual_results

Environment Variables:
    AWS_REGION - AWS region (default: ap-northeast-1)
    ESCALATION_QUEUE_URL - SQS URL for human review (optional)
"""

import base64
import concurrent.futures
import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
ESCALATION_QUEUE_URL = os.environ.get("ESCALATION_QUEUE_URL", "")

# Models to use for multi-model classification
MODELS = [
    {
        "id": "anthropic.claude-3-haiku-20240307-v1:0",
        "name": "claude-haiku",
        "api_format": "anthropic",
    },
    {
        "id": "amazon.nova-lite-v1:0",
        "name": "nova-lite",
        "api_format": "nova",
    },
    {
        "id": "mistral.mistral-large-3-675b-instruct",
        "name": "mistral-large-3",
        "api_format": "mistral",
    },
]

IMAGE_CLASSIFICATION_CATEGORIES = [
    "product_photo",
    "medical_image",
    "blueprint",
    "satellite",
    "screenshot",
    "diagram",
    "photograph",
    "scan",
    "other",
]

CLASSIFICATION_PROMPT = f"""Analyze this image and classify it.
Choose exactly one category from: [{', '.join(IMAGE_CLASSIFICATION_CATEGORIES)}]
Also provide a confidence score from 0.0 to 1.0.

Respond in JSON only: {{"classification": "...", "confidence_score": 0.X}}"""


def _invoke_anthropic(client: Any, model_id: str, image_b64: str, media_type: str) -> dict:
    """Invoke Anthropic-format model (Claude)."""
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 256,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": CLASSIFICATION_PROMPT},
                ],
            }],
        }),
    )
    body = json.loads(response["body"].read())
    return _parse_json_response(body["content"][0]["text"])


def _invoke_nova(client: Any, model_id: str, image_b64: str, media_type: str) -> dict:
    """Invoke Amazon Nova format model."""
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [{
                "role": "user",
                "content": [
                    {"image": {"format": media_type.split("/")[1], "source": {"bytes": image_b64}}},
                    {"text": CLASSIFICATION_PROMPT},
                ],
            }],
            "inferenceConfig": {"maxTokens": 256},
        }),
    )
    body = json.loads(response["body"].read())
    text = body["output"]["message"]["content"][0]["text"]
    return _parse_json_response(text)


def _invoke_mistral(client: Any, model_id: str, image_b64: str, media_type: str) -> dict:
    """Invoke Mistral Vision format model (OpenAI-compatible)."""
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                    {"type": "text", "text": CLASSIFICATION_PROMPT},
                ],
            }],
            "max_tokens": 256,
        }),
    )
    body = json.loads(response["body"].read())
    text = body["choices"][0]["message"]["content"]
    return _parse_json_response(text)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from model response, handling markdown code blocks."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    try:
        result = json.loads(text.strip())
        classification = result.get("classification", "other")
        if classification not in IMAGE_CLASSIFICATION_CATEGORIES:
            classification = "other"
        confidence = min(max(float(result.get("confidence_score", 0.5)), 0.0), 1.0)
        return {"classification": classification, "confidence_score": confidence}
    except (json.JSONDecodeError, ValueError):
        return {"classification": "other", "confidence_score": 0.3}


def _classify_with_model(model_config: dict, image_b64: str, media_type: str) -> dict:
    """Classify an image with a single model. Returns result + model name."""
    client = boto3.client("bedrock-runtime", region_name=REGION)
    model_id = model_config["id"]
    api_format = model_config["api_format"]
    name = model_config["name"]

    try:
        if api_format == "anthropic":
            result = _invoke_anthropic(client, model_id, image_b64, media_type)
        elif api_format == "nova":
            result = _invoke_nova(client, model_id, image_b64, media_type)
        elif api_format == "mistral":
            result = _invoke_mistral(client, model_id, image_b64, media_type)
        else:
            # Skip unsupported formats
            return {"model": name, "classification": "other", "confidence_score": 0.0, "error": "unsupported_format"}

        return {"model": name, **result}
    except Exception as e:
        logger.warning(f"Model {name} failed: {e}")
        return {"model": name, "classification": "other", "confidence_score": 0.0, "error": str(e)}


def majority_vote(results: list[dict]) -> dict:
    """
    Apply majority-vote consensus (Debby pattern).

    Returns:
        classification: str
        confidence_score: float (average of agreeing models)
        agreement: str ("unanimous", "majority", "disagreement")
        vote_count: dict (classification -> count)
        escalate: bool (True if 3-way split)
    """
    classifications = [r["classification"] for r in results if r.get("error") is None]
    if not classifications:
        return {"classification": "other", "confidence_score": 0.0, "agreement": "error", "escalate": True}

    # Count votes
    from collections import Counter
    votes = Counter(classifications)
    winner, winner_count = votes.most_common(1)[0]

    # Calculate agreement
    total_models = len(classifications)
    if winner_count == total_models:
        agreement = "unanimous"
        avg_confidence = sum(r["confidence_score"] for r in results if r["classification"] == winner) / winner_count
        escalate = False
    elif winner_count >= 2:
        agreement = "majority"
        avg_confidence = sum(r["confidence_score"] for r in results if r["classification"] == winner) / winner_count
        # Reduce confidence slightly for non-unanimous
        avg_confidence *= 0.9
        escalate = False
    else:
        agreement = "disagreement"
        avg_confidence = 0.4  # Low confidence for 3-way split
        escalate = True

    return {
        "classification": winner,
        "confidence_score": round(avg_confidence, 3),
        "agreement": agreement,
        "vote_count": dict(votes),
        "escalate": escalate,
        "individual_results": results,
    }


def classify_image_multimodel(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    models: list[dict] | None = None,
    existing_single_result: dict | None = None,
) -> dict:
    """
    Classify an image using multiple models in parallel and apply majority vote.

    Args:
        image_bytes: Raw image bytes
        media_type: MIME type of the image
        models: List of model configs (defaults to MODELS)
        existing_single_result: If provided, reuse this result for the first model
            (avoids redundant API call when single-model classification already exists)

    Returns:
        dict with classification, confidence, agreement, and per-model results
    """
    if models is None:
        models = [m for m in MODELS if not m.get("skip_if_no_vision")]

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Run models in parallel using ThreadPoolExecutor
    results = []

    # If existing single-model result is provided, reuse it (avoid redundant call)
    models_to_run = models
    if existing_single_result and models:
        first_model_name = models[0]["name"]
        if existing_single_result.get("model") == first_model_name:
            results.append(existing_single_result)
            models_to_run = models[1:]  # Skip the first model

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models_to_run)) as executor:
        futures = {
            executor.submit(_classify_with_model, model, image_b64, media_type): model["name"]
            for model in models_to_run
        }
        for future in concurrent.futures.as_completed(futures):
            model_name = futures[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(f"Model {model_name}: {result.get('classification')} ({result.get('confidence_score')})")
            except Exception as e:
                logger.error(f"Model {model_name} exception: {e}")
                results.append({"model": model_name, "classification": "other", "confidence_score": 0.0, "error": str(e)})

    # Apply majority vote
    consensus = majority_vote(results)

    # Escalate if needed
    if consensus["escalate"] and ESCALATION_QUEUE_URL:
        _send_to_escalation_queue(consensus)

    return consensus


def _send_to_escalation_queue(consensus: dict) -> None:
    """Send disagreement case to human review queue."""
    try:
        sqs = boto3.client("sqs", region_name=REGION)
        sqs.send_message(
            QueueUrl=ESCALATION_QUEUE_URL,
            MessageBody=json.dumps({
                "reason": "multimodel_disagreement",
                "consensus": consensus,
            }),
        )
        logger.info("Sent to escalation queue for human review")
    except Exception as e:
        logger.warning(f"Failed to send to escalation queue: {e}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for multi-model classification.

    Input:
        file_id: str
        file_path: str
        file_type: str
        access_point_arn: str

    Output:
        classification: str
        confidence_score: float
        agreement: str ("unanimous"|"majority"|"disagreement")
        escalate: bool
        individual_results: list
    """
    file_path = event["file_path"]
    file_type = event.get("file_type", "image/jpeg")
    access_point_arn = event["access_point_arn"]

    # Read image from FSx for ONTAP S3 AP
    s3_key = "/".join(file_path.split("/")[4:])
    s3_client = boto3.client("s3", region_name=REGION)

    response = s3_client.get_object(Bucket=access_point_arn, Key=s3_key)
    image_bytes = response["Body"].read(5_000_000)

    # Multi-model classification
    result = classify_image_multimodel(image_bytes, file_type)

    return result


# Standalone execution for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python multimodel_classify.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    # Determine media type
    ext = os.path.splitext(image_path)[1].lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    mtype = media_map.get(ext, "image/jpeg")

    result = classify_image_multimodel(img_bytes, mtype)
    print(json.dumps(result, indent=2, ensure_ascii=False))
