"""
evaluation — Multi-Model Classification Evaluation Framework

Compares single-model (Claude Haiku baseline) vs multi-model (majority vote)
on a labeled evaluation dataset.

Metrics:
  - Accuracy (overall)
  - F1 score (macro-averaged across categories)
  - Per-category precision/recall/F1
  - Model agreement rate
  - Cost comparison ($/file)

Usage:
    python evaluation.py --dataset eval_dataset.json [--output results.json]

Evaluation dataset format (eval_dataset.json):
[
  {"file_path": "...", "ground_truth": "blueprint", "media_type": "image/jpeg"},
  ...
]
"""

import json
import logging
import os
import sys
import time
from collections import Counter, defaultdict
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Cost per 1K input tokens (approximate, ap-northeast-1 pricing)
MODEL_COSTS = {
    "claude-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    "nova-lite": {"input_per_1k": 0.00006, "output_per_1k": 0.00024},
    "titan-image": {"input_per_1k": 0.0002, "output_per_1k": 0.0002},
}

# Approximate tokens per image classification request
ESTIMATED_INPUT_TOKENS_PER_IMAGE = 1500  # ~1.5K for image + prompt
ESTIMATED_OUTPUT_TOKENS_PER_IMAGE = 50


def calculate_f1(precision: float, recall: float) -> float:
    """Calculate F1 from precision and recall."""
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def evaluate_predictions(
    predictions: list[dict], ground_truths: list[str]
) -> dict[str, Any]:
    """
    Evaluate classification predictions against ground truth.

    Args:
        predictions: list of {"classification": str, "confidence_score": float, ...}
        ground_truths: list of ground truth labels

    Returns:
        metrics dict with accuracy, f1_macro, per_category, agreement stats
    """
    assert len(predictions) == len(ground_truths)

    correct = 0
    total = len(predictions)
    per_category: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for pred, gt in zip(predictions, ground_truths):
        pred_label = pred["classification"]
        if pred_label == gt:
            correct += 1
            per_category[gt]["tp"] += 1
        else:
            per_category[pred_label]["fp"] += 1
            per_category[gt]["fn"] += 1

    accuracy = correct / total if total > 0 else 0.0

    # Per-category precision/recall/F1
    category_metrics = {}
    f1_scores = []
    for category, counts in per_category.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = calculate_f1(precision, recall)
        category_metrics[category] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }
        f1_scores.append(f1)

    f1_macro = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "f1_macro": round(f1_macro, 4),
        "total_samples": total,
        "correct": correct,
        "per_category": category_metrics,
    }


def evaluate_agreement_stats(multimodel_results: list[dict]) -> dict:
    """Calculate agreement statistics from multi-model results."""
    agreements = Counter(r.get("agreement", "unknown") for r in multimodel_results)
    total = len(multimodel_results)
    return {
        "unanimous_rate": round(agreements.get("unanimous", 0) / total, 3) if total else 0,
        "majority_rate": round(agreements.get("majority", 0) / total, 3) if total else 0,
        "disagreement_rate": round(agreements.get("disagreement", 0) / total, 3) if total else 0,
        "escalation_count": sum(1 for r in multimodel_results if r.get("escalate")),
        "counts": dict(agreements),
    }


def estimate_cost(num_files: int, num_models: int = 2) -> dict:
    """Estimate cost comparison: single-model vs multi-model."""
    single_cost_per_file = (
        MODEL_COSTS["claude-haiku"]["input_per_1k"] * ESTIMATED_INPUT_TOKENS_PER_IMAGE / 1000
        + MODEL_COSTS["claude-haiku"]["output_per_1k"] * ESTIMATED_OUTPUT_TOKENS_PER_IMAGE / 1000
    )

    multi_cost_per_file = sum(
        MODEL_COSTS[model]["input_per_1k"] * ESTIMATED_INPUT_TOKENS_PER_IMAGE / 1000
        + MODEL_COSTS[model]["output_per_1k"] * ESTIMATED_OUTPUT_TOKENS_PER_IMAGE / 1000
        for model in ["claude-haiku", "nova-lite"]
    )

    return {
        "single_model_cost_per_file_usd": round(single_cost_per_file, 6),
        "multi_model_cost_per_file_usd": round(multi_cost_per_file, 6),
        "cost_multiplier": round(multi_cost_per_file / single_cost_per_file, 2),
        "total_single_usd": round(single_cost_per_file * num_files, 4),
        "total_multi_usd": round(multi_cost_per_file * num_files, 4),
    }


def generate_evaluation_dataset(num_samples: int = 50) -> list[dict]:
    """
    Generate a synthetic evaluation dataset with ground-truth labels.
    In production, replace with manually labeled images from FSx for ONTAP.
    """
    import random

    categories = [
        "product_photo", "product_photo", "product_photo",  # weighted
        "blueprint", "blueprint",
        "medical_image", "medical_image",
        "screenshot", "screenshot",
        "diagram",
        "photograph", "photograph",
        "satellite",
        "scan",
    ]

    dataset = []
    for i in range(num_samples):
        gt = random.choice(categories)
        dataset.append({
            "file_id": f"eval-{i:04d}",
            "file_path": f"/mnt/fsxn/vol_eval/{gt}/sample_{i:04d}.jpg",
            "ground_truth": gt,
            "media_type": "image/jpeg",
        })

    return dataset


def run_evaluation_report(
    single_results: list[dict],
    multi_results: list[dict],
    ground_truths: list[str],
) -> dict:
    """
    Generate a complete evaluation report comparing single vs multi-model.
    """
    single_metrics = evaluate_predictions(single_results, ground_truths)
    multi_metrics = evaluate_predictions(multi_results, ground_truths)
    agreement_stats = evaluate_agreement_stats(multi_results)
    cost = estimate_cost(len(ground_truths))

    f1_improvement = multi_metrics["f1_macro"] - single_metrics["f1_macro"]
    target_met = f1_improvement >= 0.05

    report = {
        "evaluation_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_size": len(ground_truths),
        "single_model": {
            "model": "claude-haiku",
            "metrics": single_metrics,
        },
        "multi_model": {
            "models": ["claude-haiku", "nova-lite"],
            "metrics": multi_metrics,
            "agreement": agreement_stats,
        },
        "comparison": {
            "f1_improvement": round(f1_improvement, 4),
            "accuracy_improvement": round(
                multi_metrics["accuracy"] - single_metrics["accuracy"], 4
            ),
            "target_f1_improvement_5pct": target_met,
        },
        "cost": cost,
        "recommendation": (
            "ADOPT: Multi-model improves F1 by ≥5%"
            if target_met
            else f"EVALUATE: F1 improvement is {f1_improvement:.1%}, below 5% target. Consider expanding model set or adjusting vote logic."
        ),
    }

    return report


if __name__ == "__main__":
    # Demo: generate synthetic dataset and show report structure
    dataset = generate_evaluation_dataset(50)

    print(f"Generated {len(dataset)} evaluation samples")
    print(f"Category distribution: {Counter(d['ground_truth'] for d in dataset)}")
    print()
    print("Cost estimate (50 files):")
    print(json.dumps(estimate_cost(50), indent=2))
    print()
    print("To run actual evaluation:")
    print("  1. Prepare labeled images on FSx for ONTAP")
    print("  2. Run single-model: handler.py on each image")
    print("  3. Run multi-model: multimodel_classify.py on each image")
    print("  4. Call run_evaluation_report(single_results, multi_results, ground_truths)")
    print()

    # Save synthetic dataset
    output_path = "eval_dataset_synthetic.json"
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"Saved synthetic dataset to {output_path}")
