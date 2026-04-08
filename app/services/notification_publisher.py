from __future__ import annotations

import json
from typing import Any

from app.services.redis_connection import create_redis_client


NOTIFICATION_CHANNEL = "smart.notifications.command.v1"


class RedisNotificationPublisher:
    def __init__(self, client: Any | None = None, channel: str = NOTIFICATION_CHANNEL) -> None:
        self._redis = client or create_redis_client()
        self._channel = channel

    def publish(self, payload: dict[str, Any]) -> None:

        self._redis.publish(self._channel, json.dumps(payload, ensure_ascii=False))


FileOutboxNotificationPublisher = RedisNotificationPublisher
