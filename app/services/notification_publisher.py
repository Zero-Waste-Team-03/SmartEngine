from __future__ import annotations

import json
import logging
import os
from uuid import uuid4

from app.schemas.events import NotificationCommandEvent


logger = logging.getLogger(__name__)


class NotificationPublisher:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.channel = os.getenv("NOTIFY_USER_CHANNEL", "notify_user")

    def publish_many(self, notifications: list[NotificationCommandEvent]) -> int:
        if not notifications:
            logger.info("No notifications to publish channel=%s", self.channel)
            return 0
        logger.info("Publishing notifications batch_size=%s channel=%s", len(notifications), self.channel)
        with self.redis.pipeline(transaction=False) as pipe:
            for item in notifications:
                pipe.publish(self.channel, item.model_dump_json())
            results = pipe.execute()
        published = sum(1 for r in results if isinstance(r, int) and r >= 0)
        logger.info("Published notifications published=%s attempted=%s channel=%s", published, len(notifications), self.channel)
        return published

    def build_notification(
        self,
        user_id: str,
        donation_id: str,
        donation_title: str,
        category: str,
        score: float,
        distance_km: float,
    ) -> NotificationCommandEvent:
        return NotificationCommandEvent(
            eventId=uuid4(),
            userId=user_id,  
            title="New relevant donation found",
            body=f"{donation_title} ({category}) matched your interests.",
            meta={
                "donationId": donation_id,
                "matchScore": round(score, 4),
                "distanceKm": distance_km,
            },
        )

