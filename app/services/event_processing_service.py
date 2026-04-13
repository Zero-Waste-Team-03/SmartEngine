from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.schemas.events import (
    BeneficiarySearchPerformedEvent,
    DonationPublishedEvent,
    NotificationCommandEvent,
)
from app.services.contracts_service import contract_service
from app.services.notification_publisher import RedisNotificationPublisher
from app.services.vector_store import RedisVectorStore


class EventProcessingService:
    def __init__(
        self,
        store: RedisVectorStore | None = None,
        publisher: RedisNotificationPublisher | None = None,
    ) -> None:
        self._store = store or RedisVectorStore()
        self._publisher = publisher or RedisNotificationPublisher()

    def process_notification_command(self, payload: NotificationCommandEvent) -> dict[str, Any]:
        command = {
            "eventId": str(payload.event_id),
            "userId": str(payload.user_id),
            "title": payload.title,
            "body": payload.body,
            "type": payload.type,
            "save": payload.save,
            "meta": payload.meta,
        }
        self._publisher.publish(command)
        self._store.record_notification(command)
        return {"accepted": True, "channels": contract_service.channels()}

    def process_beneficiary_search(self, payload: BeneficiarySearchPerformedEvent) -> dict[str, Any]:
        text = " ".join(
            part
            for part in [
                payload.event_name,
                str(payload.category_id) if payload.category_id else "",
                payload.urgency or "",
                payload.distance_bucket or "",
                payload.origin or "",
            ]
            if part
        )
        stored = self._store.upsert_interest(
            {
                "user_id": str(payload.user_id),
                "text": text,
                "keywords": [item for item in [payload.urgency, payload.distance_bucket, payload.origin] if item],
                "category_id": str(payload.category_id) if payload.category_id else None,
                "urgency": payload.urgency,
                "metadata": {"eventName": payload.event_name, "timestamp": payload.timestamp.isoformat()},
            }
        )
        return {
            "userId": stored["user_id"],
            "text": stored["text"],
            "keywordCount": len(stored["keywords"]),
            "channels": contract_service.channels(),
        }

    def process_donation_published(self, payload: DonationPublishedEvent) -> dict[str, Any]:
        donation_title = self._build_donation_title(payload)
        donation_body = self._build_donation_body(payload)
        donation_tags = self._build_donation_tags(payload)
        donation_text = self._build_donation_search_text(payload, donation_title, donation_body, donation_tags)

        stored = self._store.add_donation(
            {
                "donation_id": str(payload.donation_id),
                "donor_id": str(payload.donor_id),
                "title": donation_title,
                "body": donation_body,
                "category_id": str(payload.category_id) if payload.category_id else None,
                "urgency": payload.urgency,
                "safety_checklist_completed": payload.safety_checklist_completed,
                "tags": donation_tags,
                "metadata": {"eventName": payload.event_name, "timestamp": payload.timestamp.isoformat(), **payload.metadata},
                "search_text": donation_text,
            }
        )

        matches = self._store.find_matching_interests(stored["search_text"], threshold=0.25, limit=5)
        notifications: list[dict[str, Any]] = []

        for match in matches:
            interest = match["interest"]
            command = {
                "eventId": str(uuid4()),
                "userId": interest["user_id"],
                "title": stored["title"],
                "body": stored["body"],
                "type": "New_post",
                "save": True,
                "meta": {
                    "donationId": stored["donation_id"],
                    "categoryId": stored.get("category_id"),
                    "urgency": stored.get("urgency"),
                    "score": match["score"],
                },
            }
            self._publisher.publish(command)
            self._store.record_notification(command)
            notifications.append(command)

        return {
            "donationId": stored["donation_id"],
            "matchedUsers": [
                {"userId": match["interest"]["user_id"], "score": match["score"]} for match in matches
            ],
            "notifications": notifications,
        }

    @staticmethod
    def _build_donation_title(payload: DonationPublishedEvent) -> str:
        metadata_title = payload.metadata.get("title")
        if isinstance(metadata_title, str) and metadata_title.strip():
            return metadata_title.strip()
        return "New donation available"

    @staticmethod
    def _build_donation_body(payload: DonationPublishedEvent) -> str:
        metadata_body = payload.metadata.get("body")
        if isinstance(metadata_body, str) and metadata_body.strip():
            return metadata_body.strip()

        parts = [
            f"Category: {payload.category_id}" if payload.category_id else "",
            f"Urgency: {payload.urgency}" if payload.urgency else "",
            f"Safety checklist completed: {payload.safety_checklist_completed}",
        ]
        return " | ".join(part for part in parts if part)

    @staticmethod
    def _build_donation_tags(payload: DonationPublishedEvent) -> list[str]:
        tags: list[str] = []
        if payload.urgency:
            tags.append(payload.urgency)
        if payload.category_id:
            tags.append(str(payload.category_id))

        metadata_tags = payload.metadata.get("tags")
        if isinstance(metadata_tags, list):
            for item in metadata_tags:
                if isinstance(item, str) and item.strip():
                    tags.append(item.strip())

        return tags

    @staticmethod
    def _build_donation_search_text(
        payload: DonationPublishedEvent,
        title: str,
        body: str,
        tags: list[str],
    ) -> str:
        parts = [
            title,
            body,
            payload.event_name,
            str(payload.category_id) if payload.category_id else "",
            payload.urgency or "",
            " ".join(tags),
        ]
        return " ".join(part for part in parts if part).strip()


_event_processing_service: EventProcessingService | None = None


def get_event_processing_service() -> EventProcessingService:
    global _event_processing_service
    if _event_processing_service is None:
        _event_processing_service = EventProcessingService()
    return _event_processing_service
