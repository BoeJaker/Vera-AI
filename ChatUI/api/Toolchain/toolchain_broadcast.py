"""
toolchain_broadcast.py — SINGLE SOURCE OF TRUTH for loop capture + broadcasting
================================================================================
Both toolchain.py and enhanced_monitored_toolchain_planner.py import from here.
This fixes the "two separate _main_loop variables" problem.

Usage:
  from Vera.ChatUI.api.toolchain_broadcast import schedule_broadcast, init_broadcast_loop

In your FastAPI startup:
  @app.on_event("startup")
  async def startup():
      from Vera.ChatUI.api.toolchain_broadcast import init_broadcast_loop
      init_broadcast_loop()

In toolchain.py websocket handler (keep existing call too for safety):
  from Vera.ChatUI.api.toolchain_broadcast import init_broadcast_loop
  init_broadcast_loop()
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Single shared reference — never reset once set
_main_loop: asyncio.AbstractEventLoop | None = None


def init_broadcast_loop() -> None:
    """
    Capture the running event loop for use by worker threads.
    Safe to call multiple times — only captures once.
    Should be called from an async context (FastAPI startup, WS handler, etc.)
    """
    global _main_loop
    if _main_loop is not None and not _main_loop.is_closed():
        return  # already captured
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            _main_loop = loop
            logger.info(f"[broadcast] Captured main event loop: {loop}")
        else:
            logger.warning("[broadcast] Event loop exists but is not running — will retry on first WS connect")
    except RuntimeError as e:
        logger.warning(f"[broadcast] Could not capture event loop: {e}")


def schedule_broadcast(session_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Schedule a WebSocket broadcast on the main event loop.
    Thread-safe: works from ANY thread including orchestrator workers.
    Silently drops if no loop is available (never raises).
    """
    global _main_loop

    # Lazy capture: if called from an async context and we have no loop yet, grab it now
    if _main_loop is None or _main_loop.is_closed():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                _main_loop = loop
        except RuntimeError:
            pass

    if _main_loop is None or _main_loop.is_closed():
        logger.debug(f"[broadcast] No loop available, dropping {event_type} for {session_id}")
        return

    # Import here to avoid circular imports at module load time
    from Vera.ChatUI.api.session import websocket_connections

    async def _send():
        conns = websocket_connections.get(session_id, [])
        if not conns:
            return
        payload = {
            "type":      event_type,
            "data":      data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        dead = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.debug(f"[broadcast] WS send failed ({event_type}): {e}")
                dead.append(ws)
        for ws in dead:
            try:
                conns.remove(ws)
            except ValueError:
                pass

    try:
        asyncio.run_coroutine_threadsafe(_send(), _main_loop)
    except Exception as e:
        logger.error(f"[broadcast] run_coroutine_threadsafe failed: {e}")


# Backward-compat aliases used by existing code
set_main_loop = init_broadcast_loop