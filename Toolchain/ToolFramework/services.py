"""
Vera Tool Framework - Services
================================
Manages tools that run as long-lived background services.

Services are tools with ToolCapability.SERVICE that can:
    - Start/stop/restart independently
    - Run in background threads or async tasks
    - Stream updates to UI via the event bus
    - Be queried by other tool calls while running
    - Optionally register with the orchestrator

Lifecycle: STOPPED → STARTING → RUNNING → STOPPING → STOPPED
                                  ↓
                                FAILED

Example use cases:
    - Network scanner running continuously, queryable for live results
    - Log tailer streaming entries to a UI console
    - HTTP endpoint serving data from a tool's output
    - System monitor emitting periodic health checks
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterator, List, Optional

from Vera.Toolchain.tool_framework.core import (
    ToolCapability,
    ToolContext,
    ToolDescriptor,
)

logger = logging.getLogger("vera.tools.services")


class ServiceState(str, Enum):
    STOPPED  = "stopped"
    STARTING = "starting"
    RUNNING  = "running"
    STOPPING = "stopping"
    FAILED   = "failed"


@dataclass
class ServiceHandle:
    """
    Handle to a running service instance.
    Consumers use this to interact with the service.
    """
    service_id: str
    tool_name: str
    state: ServiceState = ServiceState.STOPPED
    started_at: Optional[float] = None
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Internal
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _output_buffer: List[Any] = field(default_factory=list, repr=False)
    _error: Optional[str] = field(default=None, repr=False)
    _ctx: Optional[ToolContext] = field(default=None, repr=False)
    
    @property
    def is_running(self) -> bool:
        return self.state == ServiceState.RUNNING
    
    @property
    def uptime(self) -> Optional[float]:
        if self.started_at and self.is_running:
            return time.time() - self.started_at
        return None
    
    def get_recent_output(self, n: int = 50) -> List[Any]:
        """Get last N output items."""
        return self._output_buffer[-n:]
    
    def query(self, query: str = "") -> Dict[str, Any]:
        """
        Query the service for its current state/data.
        Services can override this by providing a query handler.
        """
        return {
            "service_id": self.service_id,
            "tool_name": self.tool_name,
            "state": self.state.value,
            "uptime": self.uptime,
            "output_count": len(self._output_buffer),
            "recent_output": self.get_recent_output(10),
            "error": self._error,
            "config": self.config,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "tool_name": self.tool_name,
            "state": self.state.value,
            "started_at": self.started_at,
            "uptime": self.uptime,
            "config": self.config,
            "error": self._error,
            "output_count": len(self._output_buffer),
        }


class ServiceManager:
    """
    Manages the lifecycle of background tool services.
    
    Usage:
        manager = ServiceManager(event_bus=my_event_bus)
        
        # Start a service
        handle = manager.start_service(
            descriptor=port_scanner_descriptor,
            ctx=tool_context,
            config={"target": "192.168.1.0/24", "interval": 60}
        )
        
        # Query it
        status = manager.query_service(handle.service_id)
        
        # Stop it
        manager.stop_service(handle.service_id)
    """

    def __init__(self, event_bus=None, max_services: int = 20,
                 output_buffer_size: int = 1000):
        self._services: OrderedDict[str, ServiceHandle] = OrderedDict()
        self._event_bus = event_bus
        self._max_services = max_services
        self._output_buffer_size = output_buffer_size
        self._lock = threading.Lock()
        
        logger.info(f"ServiceManager initialized (max={max_services})")

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def start_service(
        self,
        descriptor: ToolDescriptor,
        ctx: ToolContext,
        config: Optional[Dict[str, Any]] = None,
        service_id: Optional[str] = None,
    ) -> ServiceHandle:
        """
        Start a tool as a background service.
        
        The tool's handler function will be called in a background thread.
        If it's a generator, each yielded value is captured and optionally
        broadcast via the event bus.
        """
        if not descriptor.can_run_as_service:
            raise ValueError(f"Tool '{descriptor.name}' is not configured as a service")
        
        if len(self._services) >= self._max_services:
            raise RuntimeError(f"Maximum services ({self._max_services}) reached")
        
        sid = service_id or f"svc_{descriptor.name}_{uuid.uuid4().hex[:8]}"
        
        handle = ServiceHandle(
            service_id=sid,
            tool_name=descriptor.name,
            config=config or {},
            _ctx=ctx,
        )
        
        with self._lock:
            self._services[sid] = handle
        
        # Start in background thread
        handle.state = ServiceState.STARTING
        handle._thread = threading.Thread(
            target=self._service_runner,
            args=(handle, descriptor),
            name=f"svc-{descriptor.name}-{sid[:8]}",
            daemon=True,
        )
        handle._thread.start()
        
        self._emit("service.started", {
            "service_id": sid,
            "tool_name": descriptor.name,
            "config": config or {},
        })
        
        logger.info(f"Service started: {descriptor.name} ({sid})")
        return handle

    def stop_service(self, service_id: str, timeout: float = 10.0) -> bool:
        """Stop a running service."""
        handle = self._services.get(service_id)
        if not handle:
            logger.warning(f"Service not found: {service_id}")
            return False
        
        if handle.state not in (ServiceState.RUNNING, ServiceState.STARTING):
            logger.warning(f"Service {service_id} is not running (state={handle.state})")
            return False
        
        handle.state = ServiceState.STOPPING
        handle._stop_event.set()
        
        if handle._thread and handle._thread.is_alive():
            handle._thread.join(timeout=timeout)
        
        handle.state = ServiceState.STOPPED
        
        self._emit("service.stopped", {
            "service_id": service_id,
            "tool_name": handle.tool_name,
        })
        
        logger.info(f"Service stopped: {handle.tool_name} ({service_id})")
        return True

    def restart_service(self, service_id: str, config: Optional[Dict[str, Any]] = None) -> Optional[ServiceHandle]:
        """Restart a service, optionally with new config."""
        handle = self._services.get(service_id)
        if not handle:
            return None
        
        descriptor_name = handle.tool_name
        ctx = handle._ctx
        new_config = config or handle.config
        
        self.stop_service(service_id)
        
        # Need to look up descriptor - caller should provide or we cache it
        # For now, return None if we can't find it (the service was stopped)
        logger.info(f"Service restart requested for {descriptor_name}")
        return None  # Caller should call start_service with the descriptor

    def stop_all(self, timeout: float = 10.0):
        """Stop all running services."""
        for sid in list(self._services.keys()):
            self.stop_service(sid, timeout=timeout)

    # ================================================================
    # QUERYING
    # ================================================================

    def query_service(self, service_id: str, query: str = "") -> Optional[Dict[str, Any]]:
        """Query a service for its current state and data."""
        handle = self._services.get(service_id)
        if not handle:
            return None
        return handle.query(query)

    def get_service(self, service_id: str) -> Optional[ServiceHandle]:
        """Get a service handle."""
        return self._services.get(service_id)

    def list_services(self, tool_name: Optional[str] = None,
                      state: Optional[ServiceState] = None) -> List[Dict[str, Any]]:
        """List all services, optionally filtered."""
        results = []
        for handle in self._services.values():
            if tool_name and handle.tool_name != tool_name:
                continue
            if state and handle.state != state:
                continue
            results.append(handle.to_dict())
        return results

    def get_service_output(self, service_id: str, n: int = 50) -> List[Any]:
        """Get recent output from a service."""
        handle = self._services.get(service_id)
        if not handle:
            return []
        return handle.get_recent_output(n)

    # ================================================================
    # INTERNAL
    # ================================================================

    def _service_runner(self, handle: ServiceHandle, descriptor: ToolDescriptor):
        """Background thread runner for a service."""
        try:
            handle.state = ServiceState.RUNNING
            handle.started_at = time.time()
            
            handler = descriptor._handler
            if not handler:
                raise RuntimeError(f"No handler for service tool: {descriptor.name}")
            
            # Call the handler with context and config
            # The handler should check handle._stop_event periodically
            result = handler(handle._ctx, **handle.config, _stop_event=handle._stop_event)
            
            # If it's a generator, consume it
            if hasattr(result, "__iter__") and hasattr(result, "__next__"):
                for item in result:
                    if handle._stop_event.is_set():
                        break
                    
                    # Buffer output
                    handle._output_buffer.append(item)
                    if len(handle._output_buffer) > self._output_buffer_size:
                        handle._output_buffer = handle._output_buffer[-self._output_buffer_size:]
                    
                    # Broadcast to UI
                    self._emit(f"tool.{descriptor.name}.output", {
                        "service_id": handle.service_id,
                        "data": item,
                    })
            else:
                # Non-generator service (probably has its own loop)
                handle._output_buffer.append(result)
            
            if not handle._stop_event.is_set():
                handle.state = ServiceState.STOPPED
                logger.info(f"Service completed naturally: {descriptor.name}")
        
        except Exception as e:
            handle.state = ServiceState.FAILED
            handle._error = str(e)
            logger.error(f"Service failed: {descriptor.name} - {e}", exc_info=True)
            
            self._emit("service.error", {
                "service_id": handle.service_id,
                "tool_name": descriptor.name,
                "error": str(e),
            })

    def _emit(self, event_type: str, data: Dict[str, Any]):
        """Emit event if bus is available."""
        if self._event_bus:
            try:
                self._event_bus.publish(event_type, data)
            except Exception as e:
                logger.warning(f"Failed to emit event {event_type}: {e}")