import os
import json
from cal.config import is_local
from google.cloud import secretmanager_v1

SECRETS_CACHE = {}

# Load local secrets once if in local env
if is_local():
    with open("secrets.local.json") as f:
        SECRETS_CACHE = json.load(f)

def get_secret(key):
    if is_local():
        return SECRETS_CACHE.get(key)
    else:
        if key in SECRETS_CACHE:
            return SECRETS_CACHE[key]

        client = secretmanager_v1.SecretManagerServiceClient()
        project_id = os.getenv("GCP_PROJECT_ID")
        secret_name = f"projects/{project_id}/secrets/{key}/versions/latest"

        response = client.access_secret_version(request={"name": secret_name})
        secret_value = response.payload.data.decode("UTF-8")
        SECRETS_CACHE[key] = secret_value
        return secret_value
