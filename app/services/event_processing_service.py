from __future__ import annotations

import logging
from functools import lru_cache
from time import time

from app.schemas.events import BeneficiarySearchPerformedEvent, DonationLikedEvent, DonationPublishedEvent
from app.services.embeddings_service import EmbeddingsService
from app.services.matching_service import MatchingService
from app.services.notification_publisher import NotificationPublisher
from app.services.redis_connection import create_redis_client
from app.services.vector_store import VectorStore


logger = logging.getLogger(__name__)


class EventProcessingService:
    def __init__(self, matching_service: MatchingService, vector_store: VectorStore, embeddings: EmbeddingsService):
        self.matching_service = matching_service
        self.vector_store = vector_store
        self.embeddings = embeddings

    def process_donation_published(self, event: DonationPublishedEvent) -> None:
        logger.info(
            "Processing donation published eventId=%s donationId=%s",
            event.eventId,
            event.donationId,
        )
        self.matching_service.process_donation(event)
        logger.info("Processed donation published donationId=%s", event.donationId)

    def process_beneficiary_search(self, event: BeneficiarySearchPerformedEvent) -> None:
        if not event.category:
            logger.info("Skipped beneficiary search embedding eventId=%s reason=missing_category", event.eventId)
            return

        logger.info(
            "Processing beneficiary search eventId=%s beneficiaryId=%s category=%s",
            event.eventId,
            event.beneficiaryId,
            event.category,
        )
        profile_text = f"Interested in {event.category} donations"
        if event.location:
            profile_text = (
                f"{profile_text} near {event.location.city or ''} {event.location.neighborhood or ''} "
                f"{event.location.country or ''}"
            )

        embedding = self.embeddings.embed_text(profile_text)
        self.vector_store.upsert_user_profile_embedding(
            user_id=str(event.beneficiaryId),
            embedding=embedding,
            categories=[event.category],
            latitude=event.location.latitude if event.location else 0.0,
            longitude=event.location.longitude if event.location else 0.0,
            activity_score=0.8,
            updated_at_ts=int(time()),
        )
        self.vector_store.set_user_profile_text(str(event.beneficiaryId), profile_text)
        logger.info("Updated beneficiary profile embedding beneficiaryId=%s", event.beneficiaryId)

    def process_donation_liked(self, event: DonationLikedEvent) -> None:
        logger.info(
            "Processing donation liked eventId=%s likerUserId=%s donationId=%s",
            event.eventId,
            event.likerUserId,
            event.donationId,
        )
        existing = self.vector_store.get_user_profile_text(str(event.likerUserId)) or ""
        behavior_text = f"{existing}. Liked donation: {event.donationTitle} in {event.category}".strip()
        embedding = self.embeddings.embed_text(behavior_text)
        self.vector_store.upsert_user_profile_embedding(
            user_id=str(event.likerUserId),
            embedding=embedding,
            categories=[event.category],
            latitude=event.location.latitude,
            longitude=event.location.longitude,
            activity_score=0.95,
            updated_at_ts=int(time()),
        )
        self.vector_store.set_user_profile_text(str(event.likerUserId), behavior_text)
        logger.info("Updated liker profile embedding likerUserId=%s", event.likerUserId)


@lru_cache(maxsize=1)
def get_event_processing_service() -> EventProcessingService:
    redis_client = create_redis_client()
    embeddings = EmbeddingsService(redis_client)
    vector_store = VectorStore(redis_client)
    notifications = NotificationPublisher(redis_client)
    matching = MatchingService(embeddings, vector_store, notifications)
    logger.info("Initialized event processing service with matching pipeline")
    return EventProcessingService(matching, vector_store, embeddings)

