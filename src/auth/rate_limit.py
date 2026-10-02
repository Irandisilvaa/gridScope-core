from __future__ import annotations

import hashlib

import redis

try:
    from src.cache_redis import redis_client
except ModuleNotFoundError:
    from cache_redis import redis_client


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("Limite de requisições excedido")


class RateLimitUnavailable(RuntimeError):
    """Indica que não é seguro liberar uma operação sem o Redis de controle."""


def _rate_key(scope: str, identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"gridscope:rate:{scope}:{digest}"


def enforce_rate_limit(scope: str, identity: str, limit: int, window_seconds: int) -> None:
    if redis_client is None:
        raise RateLimitUnavailable()

    key = _rate_key(scope, identity)
    try:
        if not redis_client.ping():
            raise RateLimitUnavailable()
        pipeline = redis_client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, window_seconds)
        count, _ = pipeline.execute()
        if int(count) > limit:
            ttl = redis_client.ttl(key)
            raise RateLimitExceeded(ttl if ttl > 0 else window_seconds)
    except RateLimitExceeded:
        raise
    except (redis.RedisError, OSError) as error:
        raise RateLimitUnavailable() from error
