from __future__ import annotations

import logging
import os

from app.schemas.events import DonationPublishedEvent
from app.services.embeddings_service import EmbeddingsService
from app.services.notification_publisher import NotificationPublisher
from app.services.vector_store import VectorStore


logger = logging.getLogger(__name__)


class MatchingService:
    def __init__(self, embeddings: EmbeddingsService, vector_store: VectorStore, notifications: NotificationPublisher):
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.notifications = notifications
        self.top_k = int(os.getenv("MATCHING_TOP_K", "20"))
        self.max_distance_km = float(os.getenv("MATCHING_MAX_DISTANCE_KM", "25"))

    def process_donation(self, event: DonationPublishedEvent) -> int:
        logger.info(
            "Start donation matching donationId=%s donorId=%s category=%s top_k=%s",
            event.donationId,
            event.donorId,
            event.category,
            self.top_k,
        )
        donation_text = self._build_donation_text(event)
        logger.info("Built donation text donationId=%s text_len=%s", event.donationId, len(donation_text))
        donation_embedding = self.embeddings.embed_text(donation_text)
        self.vector_store.save_donation_vector(event, donation_embedding)

        candidates = self.vector_store.fetch_top_users_by_vector(
            donation_embedding, top_k=self.top_k, category=event.category
        )
        logger.info("Fetched vector candidates donationId=%s count=%s", event.donationId, len(candidates))
        filtered = self.vector_store.filter_candidates(
            candidates,
            donation_lat=event.location.latitude,
            donation_lon=event.location.longitude,
            max_distance_km=self.max_distance_km,
            top_k=self.top_k,
        )
        logger.info("Filtered candidates donationId=%s count=%s", event.donationId, len(filtered))

        notifications = [
            self.notifications.build_notification(
                user_id=item["user_id"],
                donation_id=str(event.donationId),
                donation_title=event.donationTitle,
                category=event.category,
                score=item["score"],
                distance_km=item["distance_km"],
            )
            for item in filtered
            if item.get("user_id")
        ]
        published_count = self.notifications.publish_many(notifications)
        logger.info(
            "Finished donation matching donationId=%s notifications_built=%s notifications_published=%s",
            event.donationId,
            len(notifications),
            published_count,
        )
        return len(notifications)

    @staticmethod
    def _build_donation_text(event: DonationPublishedEvent) -> str:
        tags = ", ".join(event.tags) if event.tags else ""
        description = event.donationDescription or ""
        location = f"{event.location.city or ''} {event.location.neighborhood or ''} {event.location.country or ''}"
        return f"{event.donationTitle}. {description}. category:{event.category}. urgency:{event.urgency}. tags:{tags}. {location}".strip()

