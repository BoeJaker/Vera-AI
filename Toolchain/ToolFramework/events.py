"""
Vera Tool Framework - Events
===============================
Tool-specific event bus with stubs for full integration
with the Vera Orchestrator EventBus and WebSocket layer.

This provides a lightweight event system that tools use to:
    - Emit progress/status/data events
    - Push UI updates to the frontend
    - Communicate between tools
    - Integrate with the orchestrator's pub/sub

When the full Vera EventBus (Redis-backed) is available, events
are forwarded there. Otherwise they work locally.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("vera.tools.events")


class EventType(str, Enum):
    """Standard event types for tool communication."""
    # Tool lifecycle
    TOOL_STARTED     = "tool.started"
    TOOL_COMPLETED   = "tool.completed"
    TOOL_FAILED      = "tool.failed"
    TOOL_PROGRESS    = "tool.progress"
    
    # Service lifecycle
    SERVICE_STARTED  = "service.started"
    SERVICE_STOPPED  = "service.stopped"
    SERVICE_ERROR    = "service.error"
    SERVICE_OUTPUT   = "service.output"
    
    # UI events
    UI_UPDATE        = "ui.update"
    UI_CLEAR         = "ui.clear"
    UI_ACTION        = "ui.action"       # User clicked a UI action button
    
    # Data events
    DATA_NEW         = "data.new"
    DATA_UPDATED     = "data.updated"
    DATA_DELETED     = "data.deleted"
    
    # Memory events
    MEMORY_SAVED     = "memory.saved"
    MEMORY_QUERIED   = "memory.queried"
    GRAPH_UPDATED    = "graph.updated"
    
    # Inter-tool
    TOOL_REQUEST     = "tool.request"     # One tool requesting another
    TOOL_RESPONSE    = "tool.response"


@dataclass
class ToolEvent:
    """
    Structured event emitted by tools.
    
    Serialisable to JSON for WebSocket transmission and Redis pub/sub.
    """
    event_type: str
    source: str                              # Tool name or service ID
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToolEvent":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ToolEventBus:
    """
    Tool-level event bus.
    
    Provides local pub/sub with optional forwarding to:
        - Vera Orchestrator EventBus (Redis-backed)
        - WebSocket connections (for UI updates)
    
    Usage:
        bus = ToolEventBus()
        
        # Subscribe
        bus.subscribe("tool.port_scanner.ui", my_handler)
        
        # Publish
        bus.publish("tool.port_scanner.ui", {
            "type": "log",
            "text": "Scanning port 80...",
        })
        
        # With forwarding to orchestrator
        bus = ToolEventBus(orchestrator_event_bus=vera.event_bus)
    """
    
    def __init__(
        self,
        orchestrator_event_bus=None,
        websocket_manager=None,
    ):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._wildcard_subscribers: List[Callable] = []
        self._orchestrator_bus = orchestrator_event_bus
        self._websocket_manager = websocket_manager
        self._event_history: List[ToolEvent] = []
        self._max_history = 1000
        
        logger.info("ToolEventBus initialized")
        if orchestrator_event_bus:
            logger.info("  → Forwarding to orchestrator EventBus")
        if websocket_manager:
            logger.info("  → Forwarding to WebSocket manager")
    
    # ================================================================
    # PUB/SUB
    # ================================================================
    
    def publish(self, channel: str, data: Dict[str, Any],
                source: str = "", session_id: Optional[str] = None):
        """
        Publish an event to a channel.
        
        Args:
            channel: Event channel (e.g. "tool.scanner.ui", "service.started")
            data: Event payload
            source: Source tool/service name
            session_id: Optional session context
        """
        event = ToolEvent(
            event_type=channel,
            source=source,
            data=data,
            session_id=session_id,
        )
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # Notify local subscribers
        for callback in self._subscribers.get(channel, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Subscriber error on {channel}: {e}")
        
        # Notify wildcard subscribers
        for callback in self._wildcard_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Wildcard subscriber error: {e}")
        
        # Forward to orchestrator EventBus
        if self._orchestrator_bus:
            try:
                self._orchestrator_bus.publish(channel, event.to_dict())
            except Exception as e:
                logger.warning(f"Failed to forward to orchestrator bus: {e}")
        
        # Forward to WebSocket
        self._forward_to_websocket(event)
    
    def subscribe(self, channel: str, callback: Callable[[ToolEvent], None]):
        """Subscribe to a specific channel."""
        self._subscribers[channel].append(callback)
        logger.debug(f"Subscribed to {channel} ({len(self._subscribers[channel])} listeners)")
    
    def subscribe_all(self, callback: Callable[[ToolEvent], None]):
        """Subscribe to ALL events (wildcard)."""
        self._wildcard_subscribers.append(callback)
    
    def unsubscribe(self, channel: str, callback: Callable):
        """Unsubscribe from a channel."""
        try:
            self._subscribers[channel].remove(callback)
        except ValueError:
            pass
    
    def unsubscribe_all(self, callback: Callable):
        """Remove a wildcard subscriber."""
        try:
            self._wildcard_subscribers.remove(callback)
        except ValueError:
            pass
    
    # ================================================================
    # QUERYING
    # ================================================================
    
    def get_recent_events(self, n: int = 50,
                          channel: Optional[str] = None,
                          source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered."""
        events = self._event_history
        if channel:
            events = [e for e in events if e.event_type == channel]
        if source:
            events = [e for e in events if e.source == source]
        return [e.to_dict() for e in events[-n:]]
    
    def get_channels(self) -> List[str]:
        """List all channels that have subscribers."""
        return list(self._subscribers.keys())
    
    # ================================================================
    # WEBSOCKET INTEGRATION (STUB)
    # ================================================================
    
    def _forward_to_websocket(self, event: ToolEvent):
        """
        Forward event to WebSocket connections.
        
        STUB: Replace with actual WebSocket manager integration.
        The WebSocket manager should:
            1. Match event channels to connected clients
            2. Serialise the event to JSON
            3. Send to appropriate WebSocket connections
        
        Expected WebSocket message format:
        {
            "type": "tool_event",
            "event": { ... event.to_dict() ... }
        }
        """
        if self._websocket_manager is None:
            return
        
        try:
            # STUB: Actual implementation depends on your WebSocket manager
            # Example with a hypothetical manager:
            #
            # ws_message = {
            #     "type": "tool_event",
            #     "event": event.to_dict(),
            # }
            # self._websocket_manager.broadcast(
            #     session_id=event.session_id,
            #     message=ws_message,
            # )
            pass
        except Exception as e:
            logger.warning(f"WebSocket forward failed: {e}")
    
    def set_websocket_manager(self, manager):
        """
        Set the WebSocket manager for UI event forwarding.
        Call this when the WebSocket layer is initialized.
        """
        self._websocket_manager = manager
        logger.info("WebSocket manager connected to ToolEventBus")
    
    def set_orchestrator_bus(self, bus):
        """
        Set the orchestrator event bus for cross-system forwarding.
        Call this when the orchestrator is initialized.
        """
        self._orchestrator_bus = bus
        logger.info("Orchestrator EventBus connected to ToolEventBus")