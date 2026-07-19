from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any
from loguru import logger as runtime_logger

logger = logging.getLogger("app.rag.trace")
logger.setLevel(logging.INFO)

_BLOCKED_KEYS = {
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "prompt",
    "context",
    "content",
    "answer",
}
_DOCUMENT_SAFE_KEYS = {
    "doc_id",
    "document_id",
    "canonical_context_id",
    "citation_id",
    "rank",
    "score",
    "rrf_score",
    "rerank_score",
    "family",
    "variant_id",
    "weight",
    "contribution",
}


def _sanitize_value(key: str, value: Any) -> Any:
    if key.lower() in _BLOCKED_KEYS:
        return None
    if key == "documents" and isinstance(value, list):
        return [
            {k: v for k, v in item.items() if k in _DOCUMENT_SAFE_KEYS}
            for item in value
            if isinstance(item, dict)
        ]
    if isinstance(value, dict):
        return {
            nested_key: sanitized
            for nested_key, nested_value in value.items()
            if (sanitized := _sanitize_value(nested_key, nested_value)) is not None
        }
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value]
    return value


@dataclass(frozen=True)
class RagTrace:
    request_id: str
    session_id: str | None
    user_id: int | None
    query_hash: str
    _stages: list[dict[str, Any]] = field(default_factory=list, compare=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        session_id: str | None,
        user_id: int | None,
        query: str,
        request_id: str | None = None,
    ) -> "RagTrace":
        normalized_query = " ".join(str(query or "").split())
        return cls(
            request_id=request_id or str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            query_hash=hashlib.sha256(normalized_query.encode("utf-8")).hexdigest(),
        )

    def stage(self, stage: str, **fields: Any) -> None:
        record: dict[str, Any] = {
            "request_id": self.request_id,
            "stage": stage,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "query_hash": self.query_hash,
        }
        for key, value in fields.items():
            sanitized = _sanitize_value(key, value)
            if sanitized is not None:
                record[key] = sanitized
        self._stages.append(record.copy())
        payload = json.dumps(record, ensure_ascii=False, default=str)
        logger.info(payload)
        runtime_logger.info("[RAG_TRACE] {}", payload)

    def snapshot(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "query_hash": self.query_hash,
            "stages": [record.copy() for record in self._stages],
        }
