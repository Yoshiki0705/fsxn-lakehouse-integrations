-- =============================================================================
-- FSxN Athena Integration — Partition Pruning Verification
-- =============================================================================
-- Compares data scanned between filtered (partition-pruned) and unfiltered queries.
-- Partition pruning should significantly reduce DataScannedInBytes.
--
-- Expected: Filtered query scans ~1/12 of full table (1 month out of 12)
-- =============================================================================

-- ============================================================
-- Query A: Full table scan (NO partition filter)
-- Record: DataScannedInBytes from query execution stats
-- ============================================================
SELECT
    COUNT(*) AS total_rows,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
FROM fsxn_athena_db.transactions;

-- ============================================================
-- Query B: Partition-pruned query (WITH partition filter)
-- Record: DataScannedInBytes — should be much less than Query A
-- ============================================================
SELECT
    COUNT(*) AS total_rows,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
FROM fsxn_athena_db.transactions
WHERE year = 2024 AND month = 1;

-- ============================================================
-- Query C: Multi-partition filter (2 months)
-- ============================================================
SELECT
    year,
    month,
    COUNT(*) AS row_count,
    SUM(amount) AS total_amount
FROM fsxn_athena_db.transactions
WHERE year = 2024 AND month IN (1, 2)
GROUP BY year, month;

-- ============================================================
-- Query D: Range filter on partition column
-- ============================================================
SELECT
    year,
    month,
    category,
    COUNT(*) AS txn_count,
    SUM(amount) AS category_total
FROM fsxn_athena_db.transactions
WHERE year = 2024 AND month BETWEEN 1 AND 3
GROUP BY year, month, category
ORDER BY year, month, category_total DESC;

-- ============================================================
-- Verification: Compare data scanned
-- Run these queries and compare DataScannedInBytes:
--   Query A (full scan):     __________ bytes
--   Query B (1 partition):   __________ bytes
--   Pruning effectiveness:   __________ % reduction
-- ============================================================
