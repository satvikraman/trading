# cloud/redis_store.py
import json
import os
import redis
from cal.config import is_local, get_env_var

if not is_local():
    redis_client = redis.Redis.from_url(get_env_var("UPSTASH_REDIS_URL"))
else:
    JSON_STORE_PATH = "local_redis_mock.json"
    try:
        with open(JSON_STORE_PATH, 'r') as f:
            fake_store = json.load(f)
    except FileNotFoundError:
        fake_store = {}

def set_key(key, value, ex=None):
    if is_local():
        fake_store[key] = value
        with open(JSON_STORE_PATH, 'w') as f:
            json.dump(fake_store, f)
    else:
        redis_client.set(key, json.dumps(value), ex=ex)

def get_key(key):
    if is_local():
        return fake_store.get(key)
    else:
        val = redis_client.get(key)
        return json.loads(val) if val else None

def delete_key(key):
    if is_local():
        fake_store.pop(key, None)
    else:
        redis_client.delete(key)
