from __future__ import annotations

import base64
import json
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.services.mini_llm import VECTOR_DIMENSION, cosine_similarity, vectorize_text


def _encode_vector(vector: list[float]) -> str:
    return base64.b64encode(json.dumps(vector).encode("utf-8")).decode("utf-8")


def _decode_vector(value: str | bytes | None) -> list[float]:
    if not value:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(base64.b64decode(value.encode("utf-8")).decode("utf-8"))


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for key, value in list(normalized.items()):
        if isinstance(value, UUID):
            normalized[key] = str(value)
        elif isinstance(value, datetime):
            normalized[key] = value.replace(tzinfo=timezone.utc).isoformat()
    return normalized


class RedisVectorStore:
    def __init__(self, client: Any | None = None) -> None:
        from app.services.redis_connection import create_redis_client

        self._redis = client or create_redis_client()
        self._lock = threading.Lock()

    def upsert_interest(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("text", "")
        embedding = vectorize_text(text)
        record = _normalize_payload(payload)
        record["embedding"] = _encode_vector(embedding)
        record["embeddingDim"] = VECTOR_DIMENSION
        record["recordType"] = "interest"
        key = f"interest:{record['user_id']}"
        with self._lock:
            self._redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in record.items()})
        return record

    def add_donation(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("search_text") or " ".join(
            str(part) for part in [payload.get("title", ""), payload.get("body", ""), payload.get("urgency", "")] if part
        )
        embedding = vectorize_text(text)
        record = _normalize_payload(payload)
        record["search_text"] = text
        record["embedding"] = _encode_vector(embedding)
        record["embeddingDim"] = VECTOR_DIMENSION
        record["recordType"] = "donation"
        key = f"donation:{record['donation_id']}"
        with self._lock:
            self._redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in record.items()})
        return record

    def record_notification(self, payload: dict[str, Any]) -> None:
        key = f"notification:{payload['eventId']}"
        record = _normalize_payload(payload)
        record["recordType"] = "notification"
        self._redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in record.items()})

    def _scan_records(self, prefix: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for key in self._redis.scan_iter(match=f"{prefix}*"):
            raw = self._redis.hgetall(key)
            if not raw:
                continue
            records.append(dict(raw))
        return records

    def search_donations(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        query_vector = vectorize_text(query)
        results: list[dict[str, Any]] = []
        for record in self._scan_records("donation:"):
            stored_vector = _decode_vector(record.get("embedding"))
            score = cosine_similarity(query_vector, stored_vector) if stored_vector else 0.0
            results.append({"score": score, "donation": self._hydrate_donation(record)})
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def find_matching_interests(self, query: str, *, threshold: float = 0.25, limit: int = 5) -> list[dict[str, Any]]:
        query_vector = vectorize_text(query)
        results: list[dict[str, Any]] = []
        for record in self._scan_records("interest:"):
            stored_vector = _decode_vector(record.get("embedding"))
            score = cosine_similarity(query_vector, stored_vector) if stored_vector else 0.0
            if score < threshold:
                continue
            results.append({"score": score, "interest": self._hydrate_interest(record)})
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    @staticmethod
    def _hydrate_interest(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": record.get("user_id"),
            "text": record.get("text", ""),
            "keywords": json.loads(record.get("keywords", "[]")),
            "category_id": record.get("category_id") or None,
            "urgency": record.get("urgency") or None,
            "metadata": json.loads(record.get("metadata", "{}")),
        }

    @staticmethod
    def _hydrate_donation(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "donation_id": record.get("donation_id"),
            "donor_id": record.get("donor_id"),
            "title": record.get("title", ""),
            "body": record.get("body", ""),
            "category_id": record.get("category_id") or None,
            "urgency": record.get("urgency") or None,
            "tags": json.loads(record.get("tags", "[]")),
            "metadata": json.loads(record.get("metadata", "{}")),
        }


LocalVectorStore = RedisVectorStore
