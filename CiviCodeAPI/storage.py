# storage.py
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Do not force loading env or initializing clients at import time.
# dotenv is loaded by main.py before imports; however, to be defensive we lazily
# initialize the BlobServiceClient and container client when first needed.

_blob_service_client = None
_container_client = None


def _parse_conn_str(conn_str: str):
    params = {}
    for part in conn_str.split(';'):
        if not part:
            continue
        if '=' in part:
            k, v = part.split('=', 1)
            params[k] = v
    return params


def _init_clients():
    """Initialize Azure Blob clients. Raises descriptive errors if configuration is missing."""
    global _blob_service_client, _container_client, account_name, account_key
    if _blob_service_client and _container_client:
        return

    # Load env here as a fallback in case main didn't load it
    load_dotenv()

    conn_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    container = os.getenv('AZURE_CONTAINER_NAME')

    # strip surrounding quotes that may be present in .env values
    if conn_str:
        conn_str = conn_str.strip('"').strip("'")
    if container:
        container = container.strip('"').strip("'")

    if not conn_str or not container:
        raise ValueError("Azure storage configuration is missing. Set AZURE_STORAGE_CONNECTION_STRING and AZURE_CONTAINER_NAME.")

    try:
        _blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        _container_client = _blob_service_client.get_container_client(container)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Azure Blob Storage client: {e}")

    # parse account name/key for compatibility with code that references them
    params = _parse_conn_str(conn_str)
    account_name = params.get('AccountName')
    account_key = params.get('AccountKey')

def ensure_initialized():
    """Public helper to guarantee blob clients and account metadata are ready."""
    _init_clients()


class _LazyBlobServiceClient:
    def __getattr__(self, name):
        _init_clients()
        return getattr(_blob_service_client, name)


class _LazyContainerClient:
    def __getattr__(self, name):
        _init_clients()
        return getattr(_container_client, name)


# Expose module-level names for backward compatibility. These will be lazy proxies
# that initialize the real clients on first access. Existing code that does
# `from storage import blob_service_client, container_client, CONTAINER_NAME,
# account_name, account_key` will import these names and work as before.
blob_service_client = _LazyBlobServiceClient()
container_client = _LazyContainerClient()

# Expose container name and account info (may be empty strings until init)
CONTAINER_NAME = (os.getenv('AZURE_CONTAINER_NAME') or '').strip('"').strip("'")
account_name = None
account_key = None
