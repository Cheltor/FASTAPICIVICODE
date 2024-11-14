# storage.py
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load the environment variables
load_dotenv()

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
CONTAINER_NAME = os.getenv('AZURE_CONTAINER_NAME')

if not AZURE_STORAGE_CONNECTION_STRING or not CONTAINER_NAME:
    raise ValueError("Azure storage configuration is missing.")

# Initialize the BlobServiceClient
try:
    blob_service_client = BlobServiceClient.from_connection_string(
        AZURE_STORAGE_CONNECTION_STRING
    )
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
except Exception as e:
    raise RuntimeError(f"Failed to initialize Azure Blob Storage client: {e}")
