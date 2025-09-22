-- Snowflake User Setup with RSA Key Authentication
-- This script creates a user for Snowpipe Streaming integration

-- Step 1: Create the user (replace with your desired username)
CREATE USER IF NOT EXISTS EINVOICE_STREAM_USER
  DEFAULT_ROLE = 'PUBLIC'
  DEFAULT_WAREHOUSE = 'COMPUTE_WH'
  DEFAULT_NAMESPACE = 'DB_DEV_DATAFABRIC_RAW.CONTROL_DAN'
  COMMENT = 'User for Deltastream Snowpipe Streaming integration';

-- Step 2: Set the RSA public key for the user
-- Replace 'YOUR_RSA_PUBLIC_KEY_HERE' with your actual RSA public key
-- The key should be in the format: RSA PUBLIC KEY (without -----BEGIN/END----- headers)
ALTER USER EINVOICE_STREAM_USER SET RSA_PUBLIC_KEY = 'YOUR_RSA_PUBLIC_KEY_HERE';

-- Step 3: Create a custom role for streaming operations (optional but recommended)
CREATE ROLE IF NOT EXISTS STREAMING_ROLE
  COMMENT = 'Role for Snowpipe Streaming operations';

-- Step 4: Grant necessary privileges to the role
-- Database and schema privileges
GRANT USAGE ON DATABASE DB_DEV_DATAFABRIC_RAW TO ROLE STREAMING_ROLE;
GRANT USAGE ON SCHEMA DB_DEV_DATAFABRIC_RAW.CONTROL_DAN TO ROLE STREAMING_ROLE;

-- Table privileges for SAMPLESINK table
GRANT INSERT, SELECT ON TABLE DB_DEV_DATAFABRIC_RAW.CONTROL_DAN.SAMPLESINK TO ROLE STREAMING_ROLE;

-- Snowpipe Streaming specific privileges
GRANT CREATE PIPE ON SCHEMA DB_DEV_DATAFABRIC_RAW.CONTROL_DAN TO ROLE STREAMING_ROLE;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE STREAMING_ROLE;

-- Warehouse privileges (if using a specific warehouse)
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE STREAMING_ROLE;

-- Step 5: Grant the role to the user
GRANT ROLE STREAMING_ROLE TO USER EINVOICE_STREAM_USER;

-- Step 6: Set the role as default for the user
ALTER USER EINVOICE_STREAM_USER SET DEFAULT_ROLE = 'STREAMING_ROLE';

-- Step 7: Verify the user setup
SHOW USERS LIKE 'EINVOICE_STREAM_USER';
DESC USER EINVOICE_STREAM_USER;

-- Additional verification queries
SELECT 
    name,
    default_role,
    default_warehouse,
    default_namespace,
    rsa_public_key_fp
FROM SNOWFLAKE.ACCOUNT_USAGE.USERS 
WHERE name = 'EINVOICE_STREAM_USER';

-- Test connection (run this after setting up your client)
-- This should be run from your application/client to verify connectivity
-- SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE();
