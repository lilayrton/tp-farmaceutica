import os
import redis

_client = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
        if redis_url:
            _client = redis.Redis.from_url(redis_url, decode_responses=True)
        else:
            password = os.getenv("REDIS_PASSWORD", None)
            _client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                password=password,
                decode_responses=True,
            )
    return _client


def close_redis():
    global _client
    if _client is not None:
        _client.close()
        _client = None
