from __future__ import annotations

import array
import logging
import os
from math import asin, cos, radians, sin, sqrt
from typing import Any

from redis.exceptions import ResponseError


logger = logging.getLogger(__name__)


class VectorStore:
    DONATION_INDEX = "idx:donation"
    USER_INDEX = "idx:user_profile"
    DONATION_PREFIX = "smart:donation:"
    USER_PREFIX = "smart:user_profile:"

    def __init__(self, redis_client):
        self.redis = redis_client
        self.embedding_dim = int(os.getenv("EMBEDDING_DIM", "768"))
        self.knn_candidates = int(os.getenv("MATCHING_KNN_CANDIDATES", "150"))
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._create_donation_index()
        self._create_user_index()

    def _create_donation_index(self) -> None:
        try:
            self.redis.execute_command(
                "FT.CREATE",
                self.DONATION_INDEX,
                "ON",
                "HASH",
                "PREFIX",
                "1",
                self.DONATION_PREFIX,
                "SCHEMA",
                "donation_id",
                "TAG",
                "category",
                "TAG",
                "donor_id",
                "TAG",
                "timestamp",
                "NUMERIC",
                "vector",
                "VECTOR",
                "FLAT",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                self.embedding_dim,
                "DISTANCE_METRIC",
                "COSINE",
            )
            logger.info("Created donation vector index index=%s dim=%s", self.DONATION_INDEX, self.embedding_dim)
        except ResponseError as exc:
            if "Index already exists" not in str(exc):
                raise
            logger.info("Donation vector index already exists index=%s", self.DONATION_INDEX)

    def _create_user_index(self) -> None:
        try:
            self.redis.execute_command(
                "FT.CREATE",
                self.USER_INDEX,
                "ON",
                "HASH",
                "PREFIX",
                "1",
                self.USER_PREFIX,
                "SCHEMA",
                "user_id",
                "TAG",
                "categories",
                "TAG",
                "activity_score",
                "NUMERIC",
                "location",
                "GEO",
                "updated_at",
                "NUMERIC",
                "embedding",
                "VECTOR",
                "FLAT",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                self.embedding_dim,
                "DISTANCE_METRIC",
                "COSINE",
            )
            logger.info("Created user profile vector index index=%s dim=%s", self.USER_INDEX, self.embedding_dim)
        except ResponseError as exc:
            if "Index already exists" not in str(exc):
                raise
            logger.info("User profile vector index already exists index=%s", self.USER_INDEX)

    @staticmethod
    def to_vector_bytes(embedding: list[float]) -> bytes:
        return array.array("f", embedding).tobytes()

    def save_donation_vector(self, event, embedding: list[float]) -> None:
        key = f"{self.DONATION_PREFIX}{event.donationId}"
        payload = {
            "donation_id": str(event.donationId),
            "donor_id": str(event.donorId),
            "category": event.category,
            "timestamp": int(event.timestamp.timestamp()),
            "location": f"{event.location.longitude},{event.location.latitude}",
            "vector": self.to_vector_bytes(embedding),
        }
        self.redis.hset(key, mapping=payload)
        logger.info(
            "Stored donation vector key=%s donationId=%s category=%s dim=%s",
            key,
            event.donationId,
            event.category,
            len(embedding),
        )

    def fetch_top_users_by_vector(self, embedding: list[float], top_k: int, category: str) -> list[dict[str, Any]]:
        query = (
            f"(@categories:{{{self._escape_tag(category)}}} @activity_score:[0.3 +inf])=>"
            f"[KNN {max(top_k, self.knn_candidates)} @embedding $vec AS score]"
        )
        response = self.redis.execute_command(
            "FT.SEARCH",
            self.USER_INDEX,
            query,
            "PARAMS",
            "2",
            "vec",
            self.to_vector_bytes(embedding),
            "SORTBY",
            "score",
            "ASC",
            "DIALECT",
            "2",
            "RETURN",
            "6",
            "user_id",
            "activity_score",
            "categories",
            "location",
            "updated_at",
            "score",
        )
        parsed = self._parse_search_response(response)
        logger.info(
            "Vector search completed index=%s category=%s requested_top_k=%s candidates=%s",
            self.USER_INDEX,
            category,
            top_k,
            len(parsed),
        )
        return parsed

    @staticmethod
    def _escape_tag(value: str) -> str:
        return value.replace("-", "\\-").replace(" ", "\\ ")

    @staticmethod
    def _parse_search_response(response) -> list[dict[str, Any]]:
        if not response or len(response) < 2:
            return []
        parsed: list[dict[str, Any]] = []
        for i in range(1, len(response), 2):
            fields = response[i + 1]
            item = {"_key": response[i]}
            for j in range(0, len(fields), 2):
                key = fields[j]
                val = fields[j + 1]
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                if isinstance(val, bytes):
                    val = val.decode("utf-8")
                item[key] = val
            parsed.append(item)
        return parsed

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        c = 2 * asin(min(1, sqrt(a)))
        return radius * c

    def filter_candidates(
        self,
        candidates: list[dict[str, Any]],
        donation_lat: float,
        donation_lon: float,
        max_distance_km: float,
        top_k: int,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        skipped_no_location = 0
        skipped_distance = 0
        for candidate in candidates:
            loc = candidate.get("location")
            if not loc or "," not in loc:
                skipped_no_location += 1
                continue
            lon_str, lat_str = loc.split(",", 1)
            distance = self.haversine_km(donation_lat, donation_lon, float(lat_str), float(lon_str))
            if distance > max_distance_km:
                skipped_distance += 1
                continue

            score = float(candidate.get("score", 1.0))
            cosine_similarity = 1.0 - score
            filtered.append(
                {
                    "user_id": candidate.get("user_id"),
                    "score": cosine_similarity,
                    "distance_km": round(distance, 3),
                    "activity_score": float(candidate.get("activity_score", 0.0)),
                }
            )
            if len(filtered) >= top_k:
                break
        logger.info(
            "Candidate filtering completed input=%s matched=%s skipped_no_location=%s skipped_distance=%s max_distance_km=%.2f",
            len(candidates),
            len(filtered),
            skipped_no_location,
            skipped_distance,
            max_distance_km,
        )
        return filtered

    def upsert_user_profile_embedding(
        self,
        user_id: str,
        embedding: list[float],
        categories: list[str],
        latitude: float,
        longitude: float,
        activity_score: float,
        updated_at_ts: int,
    ) -> None:
        key = f"{self.USER_PREFIX}{user_id}"
        self.redis.hset(
            key,
            mapping={
                "user_id": user_id,
                "categories": "|".join(categories),
                "activity_score": activity_score,
                "location": f"{longitude},{latitude}",
                "updated_at": updated_at_ts,
                "embedding": self.to_vector_bytes(embedding),
            },
        )
        logger.info(
            "Upserted user profile embedding userId=%s categories=%s activity=%.2f dim=%s",
            user_id,
            ",".join(categories),
            activity_score,
            len(embedding),
        )

    def get_user_profile_text(self, user_id: str) -> str | None:
        key = f"{self.USER_PREFIX}{user_id}"
        value = self.redis.hget(key, "profile_text")
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    def set_user_profile_text(self, user_id: str, profile_text: str) -> None:
        key = f"{self.USER_PREFIX}{user_id}"
        self.redis.hset(key, "profile_text", profile_text)

