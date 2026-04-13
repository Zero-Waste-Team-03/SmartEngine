from __future__ import annotations

import json
import logging
import time

from pydantic import ValidationError

from app.schemas.events import BeneficiarySearchPerformedEvent, DonationPublishedEvent
from app.services.event_processing_service import get_event_processing_service
from app.services.redis_connection import create_redis_client


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

EVENT_CHANNEL = "smart.behavior.events.v1"


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

            if event_name == "BeneficiarySearchPerformed":
                event_processing_service.process_beneficiary_search(
                    BeneficiarySearchPerformedEvent.model_validate(payload)
                )
                continue

            if event_name == "DonationPublished":
                event_processing_service.process_donation_published(DonationPublishedEvent.model_validate(payload))
                continue

            logger.info("Ignored event: %s", event_name)
        except KeyboardInterrupt:
            logger.info("Worker stopped")
            break
        except ValidationError as exc:
            logger.warning("Invalid event payload ignored: %s", exc)
            continue
        except Exception as exc:
            logger.exception("Redis error, reconnecting: %s", exc)
            time.sleep(2)
            client = create_redis_client()
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(EVENT_CHANNEL)


if __name__ == "__main__":
    run()
