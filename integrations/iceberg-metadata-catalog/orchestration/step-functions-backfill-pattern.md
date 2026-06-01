# Step Functions Distributed Map — Backfill Pattern

🌐 [日本語](step-functions-backfill-pattern-ja.md) | English

## Purpose

For large initial backfills (100K+ files), use Step Functions Distributed Map to orchestrate parallel processing with concurrency control, failure thresholds, and progress tracking.

## When to Use

| Scenario | Recommended Orchestration |
|----------|--------------------------|
| Daily incremental (< 1000 files) | SQS → Lambda (existing pipeline) |
| Initial backfill (10K-1M files) | **Step Functions Distributed Map** |
| Re-enrichment after model change | Step Functions Distributed Map |
| OpenSearch reindex | Step Functions Distributed Map |

## Architecture

```
Step Functions (Distributed Map)
  │
  ├── Input: S3 manifest of files to process
  │
  ├── Map state (max 10,000 parallel child executions)
  │   ├── Child 1: Enrich file → write to S3 Tables
  │   ├── Child 2: Enrich file → write to S3 Tables
  │   └── ...
  │
  ├── Failure threshold: tolerate up to 10% failures
  │
  └── Output: Summary (processed, failed, skipped)
```

## Key Configuration

- `MaxConcurrency`: Start at 10, increase after validating FSx throughput impact
- `ToleratedFailurePercentage`: 10% (investigate failures after completion)
- `ItemReader`: S3 manifest JSON (list of file paths to process)
- Child workflow: Lambda function (same enrichment logic as incremental)

## Benefits over SQS-only

- **Progress visibility**: Know exactly how many files processed / remaining
- **Failure threshold**: Stop early if too many failures (bad model, permission issue)
- **Pause/resume**: Can stop and restart without losing progress
- **Concurrency control**: Explicit max parallelism (protect FSx throughput)
- **Cost**: Pay per state transition, not per idle Lambda

## References

- [Step Functions Distributed Map](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-asl-use-map-state-distributed.html)
