from __future__ import annotations

import json
import logging
import os
import time

from pydantic import ValidationError
from redis.exceptions import RedisError

from app.schemas.events import BeneficiarySearchPerformedEvent, DonationPublishedEvent, DonationLikedEvent
from app.services.embeddings_service import EmbeddingRequestError
from app.services.event_processing_service import get_event_processing_service
from app.services.redis_connection import create_redis_client


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

EVENT_CHANNEL = os.getenv("DONATION_EVENTS_CHANNEL", "publish_donation")


def run() -> None:
    event_processing_service = get_event_processing_service()
    client = create_redis_client()
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(EVENT_CHANNEL)
    logger.info("Subscribed to %s", EVENT_CHANNEL)

    while True:
        try:
            message = pubsub.get_message(timeout=1.0)
            if not message:
                time.sleep(0.1)
                continue

            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if not data:
                continue

            payload = json.loads(data)
            event_name = payload.get("eventName")
            event_id = payload.get("eventId")
            logger.info("Received event eventName=%s eventId=%s", event_name, event_id)

            if event_name == "BeneficiarySearchPerformed":
                logger.info("Dispatching BeneficiarySearchPerformed eventId=%s", event_id)
                event_processing_service.process_beneficiary_search(
                    BeneficiarySearchPerformedEvent.model_validate(payload)
                )
                continue

            if event_name in {"DonationPublished", "publish_donation"}:
                logger.info("Dispatching DonationPublished/publish_donation eventId=%s", event_id)
                event_processing_service.process_donation_published(DonationPublishedEvent.model_validate(payload))
                continue

            if event_name in {"DonationLiked", "LikedDonation"}:
                logger.info("Dispatching DonationLiked eventId=%s", event_id)
                event_processing_service.process_donation_liked(DonationLikedEvent.model_validate(payload))
                continue

            logger.info("Ignored event: %s", event_name)
        except KeyboardInterrupt:
            logger.info("Worker stopped")
            break
        except ValidationError as exc:
            logger.warning("Invalid event payload ignored: %s", exc)
            continue
        except EmbeddingRequestError as exc:
            logger.warning("Embedding service unavailable; skipped event: %s", exc)
            continue
        except RedisError as exc:
            logger.exception("Redis connection error, reconnecting: %s", exc)
            time.sleep(2)
            client = create_redis_client()
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(EVENT_CHANNEL)
        except Exception as exc:
            logger.exception("Event processing failed; event skipped: %s", exc)
            continue


if __name__ == "__main__":
    run()
