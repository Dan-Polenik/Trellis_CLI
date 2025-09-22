-- Snowflake Cost Analysis for Direct Streaming

-- 1. WAREHOUSE COMPUTE COSTS
-- Each INSERT operation consumes minimal warehouse time
-- Example: 1000 INSERTs/second ≈ 0.1-0.5 seconds of warehouse time per hour
-- Cost: ~$2-10/hour for SMALL warehouse (depending on complexity)

-- 2. STORAGE COSTS  
-- ~$23/TB/month for your actual data
-- JSON compression typically 70-90%

-- 3. OPTIMIZATION TIPS
-- Use AUTO_SUSPEND on warehouse for cost savings
ALTER WAREHOUSE COMPUTE_WH SET AUTO_SUSPEND = 60; -- seconds

-- Use smaller warehouse for simple INSERTs
CREATE WAREHOUSE STREAMING_WH WITH 
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 30
    AUTO_RESUME = true
    INITIALLY_SUSPENDED = true;

-- 4. MONITORING QUERIES
-- Check your streaming costs
SELECT 
    WAREHOUSE_NAME,
    SUM(CREDITS_USED) as TOTAL_CREDITS,
    SUM(CREDITS_USED) * 3 as ESTIMATED_COST_USD  -- ~$3/credit for Standard
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY 
WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY WAREHOUSE_NAME;

-- Check insert volume and performance
SELECT 
    DATE_TRUNC('hour', INGEST_DATE) as HOUR,
    COUNT(*) as RECORDS_INSERTED,
    COUNT(*) / 3600 as RECORDS_PER_SECOND
FROM CONTROL_DAN.EINVOICE.EINVOICE_STREAM
WHERE INGEST_DATE >= DATEADD(day, -1, CURRENT_TIMESTAMP())
GROUP BY HOUR
ORDER BY HOUR;
