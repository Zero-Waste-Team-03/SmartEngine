from __future__ import annotations

import json
import logging
import os
import time
from urllib import error, request


logger = logging.getLogger(__name__)


class EmbeddingRequestError(RuntimeError):
    pass


class EmbeddingsService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        self.ollama_url = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")
        self.request_timeout_seconds = float(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SECONDS", "8.0"))
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "2"))
        self.retry_backoff_seconds = float(os.getenv("EMBEDDING_RETRY_BACKOFF_SECONDS", "0.4"))

    def embed_text(self, text: str) -> list[float]:
        normalized = " ".join(text.strip().split())
        if not normalized:
            logger.info("Skipped embedding generation: empty normalized text")
            return []

        logger.info(
            "Generating embedding model=%s url=%s text_len=%s",
            self.model,
            self.ollama_url,
            len(normalized),
        )
        payload = json.dumps({"model": self.model, "prompt": normalized}).encode("utf-8")
        raw = self._request_embedding(payload)

        embedding = raw.get("embedding") or []
        if not embedding:
            raise RuntimeError("Embedding model returned empty vector")
        logger.info("Generated embedding successfully dim=%s", len(embedding))
        return embedding

    def _request_embedding(self, payload: bytes) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            req = request.Request(self.ollama_url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            try:
                with request.urlopen(req, timeout=self.request_timeout_seconds) as resp:
                    logger.info(
                        "Embedding HTTP request succeeded attempt=%s timeout=%.1fs",
                        attempt + 1,
                        self.request_timeout_seconds,
                    )
                    return json.loads(resp.read().decode("utf-8"))
            except (error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                sleep_seconds = self.retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "Embedding request failed (attempt %s/%s). Retrying in %.2fs: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    sleep_seconds,
                    exc,
                )
                time.sleep(sleep_seconds)

        raise EmbeddingRequestError(f"Embedding request failed after retries: {last_error}")

