import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import json
import boto3
from datetime import datetime

class SnowflakeStreamer:
    def __init__(self, account, user, private_key_path, warehouse, database, schema):
        self.account = account
        self.user = user
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        
        # Load private key
        with open(private_key_path, 'rb') as key_file:
            private_key = load_pem_private_key(
                key_file.read(),
                password=None  # Add password if your key is encrypted
            )
        
        # Convert to PEM format for Snowflake
        self.private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        self.connection = None
    
    def connect(self):
        """Establish connection to Snowflake using key pair authentication"""
        self.connection = snowflake.connector.connect(
            user=self.user,
            account=self.account,
            private_key=self.private_key_bytes,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema
        )
        print("Connected to Snowflake successfully!")
    
    def stream_json_to_s3_then_snowflake(self, json_data, s3_bucket, s3_key):
        """Stream JSON object to S3, which triggers Snowpipe"""
        # Upload JSON to S3
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=json.dumps(json_data),
            ContentType='application/json'
        )
        print(f"JSON data uploaded to s3://{s3_bucket}/{s3_key}")
    
    def direct_insert_json(self, json_data):
        """Directly insert JSON data into Snowflake table"""
        cursor = self.connection.cursor()
        
        # Extract data from JSON
        tenant_id = json_data.get('tenantId')
        document_id = json_data.get('documentId')
        filename = json_data.get('filename')
        filepath = json_data.get('filepath')
        document_type = json_data.get('documentTypeName')
        payload = json.dumps(json_data.get('payload'))
        
        insert_query = """
        INSERT INTO EINVOICE (Tenantid, DocumentId, Filename, filepath, DocumentTypeName, Payload, ingestdate, lastUpdateDate)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """
        
        cursor.execute(insert_query, (tenant_id, document_id, filename, filepath, document_type, payload))
        cursor.close()
        print("JSON data inserted directly into Snowflake")
    
    def close(self):
        if self.connection:
            self.connection.close()

# Example usage
if __name__ == "__main__":
    # Initialize streamer
    streamer = SnowflakeStreamer(
        account='your-account.snowflakecomputing.com',
        user='EINVOICE_STREAM_USER',
        private_key_path='/Users/daniel.polenik/Documents/_projects/snowpipe/rsa_key.p8',
        warehouse='COMPUTE_WH',
        database='DB_QA_EINVOICE_RAW',
        schema='EINVOICE'
    )
    
    # Connect
    streamer.connect()
    
    # Sample JSON data
    sample_json = {
        "tenantId": "tenant123",
        "documentId": "doc456",
        "filename": "invoice_001.json",
        "filepath": "s3://bucket/tenant123/invoices/doc456/invoice_001.json",
        "documentTypeName": "INVOICE",
        "payload": {
            "invoiceNumber": "INV-001",
            "amount": 1500.00,
            "customer": "ACME Corp",
            "date": "2025-09-10"
        }
    }
    
    # Option 1: Stream via S3 (triggers Snowpipe automatically)
    streamer.stream_json_to_s3_then_snowflake(
        sample_json, 
        'your-einvoice-stream-bucket', 
        f'einvoices/{datetime.now().isoformat()}.json'
    )
    
    # Option 2: Direct insert
    # streamer.direct_insert_json(sample_json)
    
    # Close connection
    streamer.close()
