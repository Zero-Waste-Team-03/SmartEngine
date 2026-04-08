from __future__ import annotations

import hashlib
import math
import re

VECTOR_DIMENSION = 256


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def vectorize_text(text: str, dimension: int = VECTOR_DIMENSION) -> list[float]:
    vector = [0.0] * dimension
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest, 16) % dimension
        vector[index] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector

    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(l * r for l, r in zip(left, right))
