"""
Vera EventBus — Event Model
============================

Canonical Pydantic model for all bus events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class Event(BaseModel):
    type: str
    source: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    retries: int = 0

    @model_validator(mode="after")
    def _ensure_correlation_id(self):
        self.meta.setdefault("correlation_id", self.id)
        return self

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls.model_validate(d)

    def session_id(self) -> str | None:
        return self.meta.get("session_id") or self.payload.get("session_id")

    def correlation_id(self) -> str:
        return self.meta.get("correlation_id", self.id)