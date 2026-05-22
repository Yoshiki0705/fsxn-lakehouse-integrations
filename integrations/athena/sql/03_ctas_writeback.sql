-- =============================================================================
-- FSxN Athena Integration — CTAS Write-Back to FSxN
-- =============================================================================
-- Creates curated (gold) tables on FSxN via S3 Access Point using CTAS.
-- Verifies Athena can write Parquet files back to FSxN.
--
-- Prerequisites:
--   - IAM role has s3:PutObject on S3 AP /gold/* path
--   - FSxN volume has sufficient space
-- =============================================================================

-- ============================================================
-- CTAS 1: Daily transaction summary (Parquet output)
-- ============================================================
CREATE TABLE fsxn_athena_db.gold_daily_summary
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    external_location = 's3://${AP_ALIAS}/gold/daily_summary/'
) AS
SELECT
    year,
    month,
    CAST(transaction_date AS DATE) AS txn_date,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount,
    COUNT(DISTINCT customer_id) AS unique_customers
FROM fsxn_athena_db.transactions
WHERE status = 'completed'
GROUP BY year, month, CAST(transaction_date AS DATE);

-- ============================================================
-- CTAS 2: Customer summary (Parquet output)
-- ============================================================
CREATE TABLE fsxn_athena_db.gold_customer_summary
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    external_location = 's3://${AP_ALIAS}/gold/customer_summary/'
) AS
SELECT
    t.customer_id,
    c.name AS customer_name,
    c.country,
    c.segment,
    COUNT(*) AS total_transactions,
    SUM(t.amount) AS lifetime_value,
    AVG(t.amount) AS avg_transaction,
    MIN(t.transaction_date) AS first_transaction,
    MAX(t.transaction_date) AS last_transaction
FROM fsxn_athena_db.transactions t
JOIN fsxn_athena_db.customers c
    ON t.customer_id = c.customer_id
WHERE t.status = 'completed'
GROUP BY t.customer_id, c.name, c.country, c.segment;

-- ============================================================
-- CTAS 3: Category analytics (JSON output for comparison)
-- ============================================================
CREATE TABLE fsxn_athena_db.gold_category_analytics
WITH (
    format = 'JSON',
    external_location = 's3://${AP_ALIAS}/gold/category_analytics/'
) AS
SELECT
    category,
    year,
    month,
    COUNT(*) AS txn_count,
    SUM(amount) AS total_amount,
    APPROX_PERCENTILE(amount, 0.5) AS median_amount,
    APPROX_PERCENTILE(amount, 0.95) AS p95_amount
FROM fsxn_athena_db.transactions
GROUP BY category, year, month;

-- ============================================================
-- Verify CTAS output: Query the new gold tables
-- ============================================================
SELECT COUNT(*) AS row_count FROM fsxn_athena_db.gold_daily_summary;
SELECT COUNT(*) AS row_count FROM fsxn_athena_db.gold_customer_summary;
SELECT COUNT(*) AS row_count FROM fsxn_athena_db.gold_category_analytics;

-- ============================================================
-- Cleanup (run after verification)
-- ============================================================
-- DROP TABLE IF EXISTS fsxn_athena_db.gold_daily_summary;
-- DROP TABLE IF EXISTS fsxn_athena_db.gold_customer_summary;
-- DROP TABLE IF EXISTS fsxn_athena_db.gold_category_analytics;
