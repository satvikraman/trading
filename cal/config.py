import os
from dotenv import load_dotenv

load_dotenv(override=True)

def is_local():
    ENV = os.getenv("ENVIRONMENT", "LOCAL")
    return ENV.upper() == "LOCAL"

def get_env_var(key, default=None):
    return os.getenv(key, default)
