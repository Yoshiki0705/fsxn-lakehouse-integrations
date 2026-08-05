-- =============================================================================
-- FSx for ONTAP Athena Integration — Basic Queries
-- =============================================================================
-- Executes SELECT, WHERE, GROUP BY, COUNT, SUM, AVG, JOIN queries
-- on Parquet, CSV, and JSON tables discovered by Glue Crawler.
--
-- Prerequisites:
--   - Glue Crawler has run and discovered tables
--   - Athena workgroup 'fsxn-verification' is configured
--   - S3 AP has internet network origin
-- =============================================================================

-- ============================================================
-- Query 1: Simple SELECT on Parquet (transactions)
-- ============================================================
SELECT *
FROM fsxn_athena_db.transactions
LIMIT 100;

-- ============================================================
-- Query 2: Aggregation — Daily transaction summary
-- ============================================================
SELECT
    year,
    month,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount,
    MIN(amount) AS min_amount,
    MAX(amount) AS max_amount
FROM fsxn_athena_db.transactions
GROUP BY year, month
ORDER BY year, month;

-- ============================================================
-- Query 3: Filtered query with WHERE clause
-- ============================================================
SELECT
    customer_id,
    COUNT(*) AS txn_count,
    SUM(amount) AS total_spent
FROM fsxn_athena_db.transactions
WHERE status = 'completed'
  AND amount > 100
GROUP BY customer_id
ORDER BY total_spent DESC
LIMIT 20;

-- ============================================================
-- Query 4: CSV table query (customers)
-- ============================================================
SELECT *
FROM fsxn_athena_db.customers
LIMIT 50;

-- ============================================================
-- Query 5: JSON table query (events)
-- ============================================================
SELECT
    event_type,
    COUNT(*) AS event_count
FROM fsxn_athena_db.events
GROUP BY event_type
ORDER BY event_count DESC;

-- ============================================================
-- Query 6: JOIN — Transactions with Customer details
-- ============================================================
SELECT
    t.customer_id,
    c.name AS customer_name,
    c.country,
    COUNT(*) AS txn_count,
    SUM(t.amount) AS total_amount
FROM fsxn_athena_db.transactions t
JOIN fsxn_athena_db.customers c
    ON t.customer_id = c.customer_id
WHERE t.status = 'completed'
GROUP BY t.customer_id, c.name, c.country
ORDER BY total_amount DESC
LIMIT 20;

-- ============================================================
-- Query 7: Window function — Running total per customer
-- ============================================================
SELECT
    customer_id,
    transaction_date,
    amount,
    SUM(amount) OVER (
        PARTITION BY customer_id
        ORDER BY transaction_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM fsxn_athena_db.transactions
WHERE customer_id = 'CUST-00001'
ORDER BY transaction_date
LIMIT 50;
