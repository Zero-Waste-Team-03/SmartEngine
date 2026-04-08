from __future__ import annotations

import importlib
import os
from typing import Any


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def create_redis_client() -> Any:
    redis = importlib.import_module("redis")
    return redis.Redis.from_url(get_redis_url(), decode_responses=True)
