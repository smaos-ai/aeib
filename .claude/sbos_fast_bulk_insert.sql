-- SBOS Synthetic Transaction Data Bulk Insert (Direct SQL)
-- Generates 4.8M+ rows with anomalies directly in PostgreSQL
-- Execution: psql -h localhost sbos_financial_pilot -U andriileukhin -f sbos_fast_bulk_insert.sql

TRUNCATE TABLE transactions;
SELECT setseed(0.42);

-- Base transaction generation: 4,750,000 rows (normal)
INSERT INTO transactions (transaction_id, date, amount, vendor, category, description, metadata)
SELECT
    'TX-' || LPAD(ROW_NUMBER() OVER (ORDER BY gen.id)::TEXT, 8, '0'),
    DATE '2019-01-01' + (RANDOM() * 2190)::INT,
    ROUND((CASE
        WHEN RANDOM() < 0.80 THEN 100 + RANDOM() * 4900
        WHEN RANDOM() < 0.95 THEN 5000 + RANDOM() * 45000
        ELSE 50000 + RANDOM() * 450000
    END)::NUMERIC, 2),
    (ARRAY['Acme Corp', 'TechFlow Inc', 'GlobalTrade LLC', 'DataSoft Solutions',
            'CloudNine Services', 'SwiftPay Networks', 'NexGen Logistics',
            'VendorX Industries', 'ProcureHub', 'SupplyChain Pro',
            'BuildRight Materials', 'OfficeWorks', 'TransitGo', 'PaymentGateway',
            'CloudSync', 'DigitalVault', 'MarketPlace', 'API Integration Co'])[FLOOR(RANDOM() * 18 + 1)],
    (ARRAY['Operations', 'Marketing', 'R&D', 'Infrastructure', 'Personnel',
            'Compliance', 'Travel', 'Equipment', 'Software Licenses', 'Consulting',
            'Utilities', 'Insurance', 'Maintenance', 'Advertising', 'Outsourcing'])[FLOOR(RANDOM() * 15 + 1)],
    'Normal transaction',
    JSON_BUILD_OBJECT(
        'department', (ARRAY['Finance', 'Engineering', 'Operations', 'Sales'])[FLOOR(RANDOM() * 4 + 1)],
        'approval_status', 'approved',
        'invoice_id', SUBSTRING(MD5(RANDOM()::TEXT), 1, 8)
    )::JSONB
FROM GENERATE_SERIES(1, 4750000) gen(id);

ANALYZE transactions;

-- Anomaly injection using CTEs to avoid window function restrictions
WITH base_sample AS (
    SELECT * FROM transactions
    WHERE RANDOM() < 0.05
    LIMIT 237500
)
INSERT INTO transactions (transaction_id, date, amount, vendor, category, description, metadata)
SELECT
    'TX-DUP-' || LPAD(ROW_NUMBER() OVER (ORDER BY transaction_id)::TEXT, 7, '0'),
    date + INTERVAL '12 hours',
    amount,
    vendor,
    category,
    'DUPLICATE: ' || description,
    metadata
FROM base_sample;

WITH base_sample AS (
    SELECT * FROM transactions
    WHERE RANDOM() < 0.05
      AND transaction_id NOT LIKE 'TX-DUP-%'
    LIMIT 237500
)
INSERT INTO transactions (transaction_id, date, amount, vendor, category, description, metadata)
SELECT
    'TX-SPIKE-' || LPAD(ROW_NUMBER() OVER (ORDER BY transaction_id)::TEXT, 7, '0'),
    date,
    ROUND((amount * 10)::NUMERIC, 2),
    vendor,
    category || ' SPIKE',
    'SPIKE: ' || description,
    metadata
FROM base_sample;

WITH base_sample AS (
    SELECT * FROM transactions
    WHERE RANDOM() < 0.05
      AND transaction_id NOT LIKE 'TX-DUP-%'
      AND transaction_id NOT LIKE 'TX-SPIKE-%'
    LIMIT 237500
)
INSERT INTO transactions (transaction_id, date, amount, vendor, category, description, metadata)
SELECT
    'TX-POLICY-' || LPAD(ROW_NUMBER() OVER (ORDER BY transaction_id)::TEXT, 7, '0'),
    date,
    amount,
    (ARRAY['BlackMarket Inc', 'UnknownVendor Ltd', 'SuspiciousTrade Co', 'RedFlag Industries'])[FLOOR(RANDOM() * 4 + 1)],
    'POLICY_VIOLATION',
    'POLICY_VIOLATION: ' || description,
    metadata
FROM base_sample;

WITH base_sample AS (
    SELECT * FROM transactions
    WHERE RANDOM() < 0.05
      AND transaction_id NOT LIKE 'TX-DUP-%'
      AND transaction_id NOT LIKE 'TX-SPIKE-%'
      AND transaction_id NOT LIKE 'TX-POLICY-%'
    LIMIT 237500
)
INSERT INTO transactions (transaction_id, date, amount, vendor, category, description, metadata)
SELECT
    'TX-TEMPORAL-' || LPAD(ROW_NUMBER() OVER (ORDER BY transaction_id)::TEXT, 7, '0'),
    date + INTERVAL '3 hours',
    amount,
    vendor,
    'TEMPORAL_ANOMALY',
    'TEMPORAL_ANOMALY: ' || description,
    metadata
FROM base_sample;

-- Final verification
SELECT
    COUNT(*) as total_rows,
    COUNT(DISTINCT CASE WHEN transaction_id LIKE 'TX-DUP-%' THEN 1 END) as duplicates,
    COUNT(DISTINCT CASE WHEN transaction_id LIKE 'TX-SPIKE-%' THEN 1 END) as spikes,
    COUNT(DISTINCT CASE WHEN transaction_id LIKE 'TX-POLICY-%' THEN 1 END) as policy_violations,
    COUNT(DISTINCT CASE WHEN transaction_id LIKE 'TX-TEMPORAL-%' THEN 1 END) as temporal_anomalies
FROM transactions;

ANALYZE transactions;
