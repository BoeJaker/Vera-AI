from pydantic import BaseModel, Field
from typing import Dict, Any
from uuid import uuid4
from datetime import datetime

class Event(BaseModel):
    type: str
    source: str
    payload: Dict[str, Any]
    meta: Dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    retries: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        self.meta.setdefault("correlation_id", self.id)
