-- pii_coverage.sql — PII detection coverage report
SELECT
  COUNT(*) AS total_files,
  COUNT(CASE WHEN has_pii IS NOT NULL THEN 1 END) AS pii_scanned,
  COUNT(CASE WHEN has_pii = true THEN 1 END) AS pii_detected,
  COUNT(CASE WHEN anonymization_status = 'completed' THEN 1 END) AS anonymized,
  ROUND(100.0 * COUNT(CASE WHEN has_pii IS NOT NULL THEN 1 END) / COUNT(*), 1) AS coverage_pct
FROM metadata.latest_unstructured_files;
