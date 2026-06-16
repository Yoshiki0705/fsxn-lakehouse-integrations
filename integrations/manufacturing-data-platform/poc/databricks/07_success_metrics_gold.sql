-- Manufacturing Data Platform PoC — Success Metrics (Databricks Gold Dashboard)
-- Mirror of Edge cloud/clickhouse/queries/success_metrics.sql (M1-M6)
-- Sync Date: 2026-06-16
--
-- These queries power a Databricks SQL dashboard for PoC Go/No-Go evaluation.
-- The Edge ClickHouse queries compute the same metrics on the real-time side;
-- these compute them on the governed Gold/Bronze layers for cross-validation.
--
-- Run against catalog: manufacturing_poc

-- ============================================================
-- M1: E2E Pipeline Health (event arrival + ingestion lag)
-- ============================================================
-- Counts events landed in Bronze and the ingestion lag distribution.
SELECT
    'M1_e2e_pipeline' AS metric,
    count(*) AS total_events,
    count(DISTINCT site_id) AS sites,
    count(DISTINCT equipment_id) AS equipment,
    avg(unix_timestamp(_ingested_at) - unix_timestamp(event_timestamp)) AS avg_lag_seconds,
    max(unix_timestamp(_ingested_at) - unix_timestamp(event_timestamp)) AS max_lag_seconds
FROM manufacturing_poc.bronze.kafka_events
WHERE event_timestamp > current_timestamp() - INTERVAL 24 HOURS;

-- ============================================================
-- M2: AI Accuracy / Precision / Recall (from feedback_events)
-- ============================================================
-- Joins AI predictions (quality_events) with human ground truth
-- (feedback_events) on the target event ID. Binary framing: defect = positive.
WITH labeled AS (
    SELECT
        q.event_id,
        q.classification_result AS ai_label,
        f.human_label,
        -- Binary: 'defect' is the positive class
        CASE WHEN q.classification_result = 'defect' THEN 1 ELSE 0 END AS ai_positive,
        CASE WHEN f.human_label = 'defect' THEN 1 ELSE 0 END AS truth_positive
    FROM manufacturing_poc.bronze.quality_events q
    INNER JOIN manufacturing_poc.bronze.feedback_events f
        ON q.event_id = f.target_event_id
    WHERE f.human_label IS NOT NULL
)
SELECT
    'M2_ai_accuracy' AS metric,
    count(*) AS labeled_samples,
    -- Accuracy = correct predictions / total
    round(sum(CASE WHEN ai_positive = truth_positive THEN 1 ELSE 0 END) / count(*), 4) AS accuracy,
    -- Precision = TP / (TP + FP)
    round(
        sum(CASE WHEN ai_positive = 1 AND truth_positive = 1 THEN 1 ELSE 0 END)
        / nullif(sum(CASE WHEN ai_positive = 1 THEN 1 ELSE 0 END), 0),
        4
    ) AS precision,
    -- Recall = TP / (TP + FN)
    round(
        sum(CASE WHEN ai_positive = 1 AND truth_positive = 1 THEN 1 ELSE 0 END)
        / nullif(sum(CASE WHEN truth_positive = 1 THEN 1 ELSE 0 END), 0),
        4
    ) AS recall
FROM labeled;

-- ============================================================
-- M3: Dashboard Latency (ingest lag percentiles, target p95 < 500ms)
-- ============================================================
SELECT
    'M3_dashboard_latency' AS metric,
    percentile(unix_millis(_ingested_at) - unix_millis(event_timestamp), 0.50) AS p50_ms,
    percentile(unix_millis(_ingested_at) - unix_millis(event_timestamp), 0.95) AS p95_ms,
    percentile(unix_millis(_ingested_at) - unix_millis(event_timestamp), 0.99) AS p99_ms,
    CASE
        WHEN percentile(unix_millis(_ingested_at) - unix_millis(event_timestamp), 0.95) < 500
        THEN 'PASS' ELSE 'FAIL'
    END AS p95_target_500ms
FROM manufacturing_poc.bronze.kafka_events
WHERE event_timestamp > current_timestamp() - INTERVAL 1 HOUR;

-- ============================================================
-- M4: AI Analysis Latency (Bedrock response time, target < 5000ms)
-- ============================================================
-- Reads processing latency recorded in quality_events metadata.
SELECT
    'M4_ai_latency' AS metric,
    count(*) AS analyzed_events,
    avg(CAST(get_json_object(metadata, '$.processing_latency_ms') AS DOUBLE)) AS avg_latency_ms,
    percentile(CAST(get_json_object(metadata, '$.processing_latency_ms') AS DOUBLE), 0.95) AS p95_latency_ms,
    CASE
        WHEN percentile(CAST(get_json_object(metadata, '$.processing_latency_ms') AS DOUBLE), 0.95) < 5000
        THEN 'PASS' ELSE 'FAIL'
    END AS p95_target_5000ms
FROM manufacturing_poc.bronze.quality_events
WHERE event_timestamp > current_timestamp() - INTERVAL 24 HOURS
  AND get_json_object(metadata, '$.processing_latency_ms') IS NOT NULL;

-- ============================================================
-- M5: Payload Reference Coverage (quality_event ↔ payload_manifest)
-- ============================================================
SELECT
    'M5_payload_coverage' AS metric,
    count(*) AS quality_events_with_payload,
    sum(CASE WHEN pm.payload_uri IS NOT NULL THEN 1 ELSE 0 END) AS matched_in_manifest,
    round(
        sum(CASE WHEN pm.payload_uri IS NOT NULL THEN 1 ELSE 0 END) / count(*),
        4
    ) AS coverage_rate
FROM manufacturing_poc.bronze.quality_events q
LEFT JOIN manufacturing_poc.bronze.payload_manifest pm
    ON q.payload_uri = pm.payload_uri
WHERE q.payload_uri IS NOT NULL
  AND q.event_timestamp > current_timestamp() - INTERVAL 24 HOURS;

-- ============================================================
-- M6: Dead Letter Rate (target < 1%)
-- ============================================================
-- Compares successfully ingested events vs. parse failures.
-- Note: Bronze DLT drops invalid rows via expectations; for an accurate
-- DLQ rate, read the DLT event log or the ClickHouse dead_letter_events table.
WITH counts AS (
    SELECT
        (SELECT count(*) FROM manufacturing_poc.bronze.kafka_events
         WHERE event_timestamp > current_timestamp() - INTERVAL 24 HOURS) AS good_events,
        -- Placeholder: replace with DLT expectation drop count or ClickHouse DLQ count
        0 AS dead_letter_events
)
SELECT
    'M6_dead_letter_rate' AS metric,
    good_events,
    dead_letter_events,
    round(dead_letter_events / nullif(good_events + dead_letter_events, 0), 4) AS dlq_rate,
    CASE
        WHEN dead_letter_events / nullif(good_events + dead_letter_events, 0) < 0.01
        THEN 'PASS' ELSE 'FAIL'
    END AS target_under_1pct
FROM counts;
