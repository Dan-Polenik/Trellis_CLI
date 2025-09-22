-- Deltastream Flink Configuration for Snowpipe Integration
-- Write JSON files to S3/Stage, let Snowpipe handle serverless ingestion

-- Set Snowflake context
USE DATABASE DB_DEV_DATAFABRIC_RAW;
USE SCHEMA CONTROL_DAN;
USE WAREHOUSE COMPUTE_WH;

-- Option 1: Write to S3 bucket that triggers Snowpipe auto_ingest
CREATE SINK s3_samplesink_staging WITH (
    'connector' = 's3',
    'bucket' = 'your-samplesink-bucket',
    'path' = 'samplesink-events/',
    'format' = 'json',
    'file.size.mb' = '10',  -- Trigger new file every 10MB
    'file.time.seconds' = '60'  -- Or every 60 seconds
);

-- Option 2: If Deltastream has direct Snowpipe Streaming support
CREATE SINK snowpipe_streaming_sink WITH (
    'connector' = 'snowpipe-streaming',
    'snowflake.url' = 'your-account.snowflakecomputing.com',
    'snowflake.user' = 'EINVOICE_STREAM_USER',
    'snowflake.private.key' = 'path/to/your/rsa_key.p8',
    'snowflake.database' = 'DB_DEV_DATAFABRIC_RAW',
    'snowflake.schema' = 'CONTROL_DAN',
    'snowflake.table' = 'SAMPLESINK',
    'snowflake.warehouse' = 'COMPUTE_WH'  -- Added warehouse
);

-- Transform your stream data to match SAMPLESINK table
INSERT INTO s3_samplesink_staging  -- or snowpipe_streaming_sink
SELECT 
    tenantId,
    documentId,
    status,
    eventInstant,
    eventHash
FROM your_flink_source_stream
WHERE eventHash IS NOT NULL;  -- Ensure PK constraint compliance
