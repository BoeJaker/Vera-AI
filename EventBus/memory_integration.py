"""
Vera EventBus — HybridMemory Integration Mixin
================================================

Patches ``HybridMemory`` so that every memory operation publishes an event
to the bus.  This satisfies the requirement:

    "All memories should flow through the event bus."

Usage
-----
Call ``wire_memory_to_bus(mem, bus, session_id_fn)`` once after both
``HybridMemory`` and ``EnhancedRedisEventBus`` are initialised:

    from Vera.EventBus.memory_integration import wire_memory_to_bus
    wire_memory_to_bus(vera.mem, vera.bus, lambda: vera.sess.id)

The patching is additive — original behaviour is fully preserved.
All patches are synchronous wrappers that schedule async bus publishes
on the running event loop via ``asyncio.run_coroutine_threadsafe``.

Events emitted
--------------
memory.session.start     — start_session called
memory.session.end       — end_session called
memory.item.added        — add_session_memory called
memory.entity.upsert     — upsert_entity called
memory.link              — link / upsert_edge called
memory.document.attached — attach_document called
memory.semantic.query    — semantic_retrieve called
memory.promoted          — promote_session_memory_to_long_term called
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

log = logging.getLogger("vera.eventbus.memory_integration")


def wire_memory_to_bus(
    mem,
    bus,
    session_id_fn: Optional[Callable[[], Optional[str]]] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
):
    """
    Patch a live ``HybridMemory`` instance so every operation emits a bus event.

    Parameters
    ----------
    mem            : HybridMemory instance
    bus            : EnhancedRedisEventBus instance
    session_id_fn  : callable returning the current session_id string or None
    loop           : running event loop (auto-detected if None)
    """
    _loop = loop or asyncio.get_event_loop()

    def _publish(event_type: str, payload: Dict[str, Any], session_id: Optional[str] = None):
        from Vera.EventBus.event_model import Event
        meta: Dict[str, Any] = {}
        if session_id:
            meta["session_id"] = session_id
        elif session_id_fn:
            sid = session_id_fn()
            if sid:
                meta["session_id"] = sid

        evt = Event(type=event_type, source="hybrid_memory", payload=payload, meta=meta)
        asyncio.run_coroutine_threadsafe(bus.publish(evt), _loop)

    # ------------------------------------------------------------------
    # start_session
    # ------------------------------------------------------------------
    _orig_start_session = mem.start_session

    def _start_session(session_id=None, metadata=None):
        result = _orig_start_session(session_id=session_id, metadata=metadata)
        _publish("memory.session.start", {
            "session_id": result.id,
            "metadata": metadata or {},
        }, session_id=result.id)
        return result

    mem.start_session = _start_session

    # ------------------------------------------------------------------
    # end_session
    # ------------------------------------------------------------------
    _orig_end_session = mem.end_session

    def _end_session(session_id: str):
        _orig_end_session(session_id)
        _publish("memory.session.end", {"session_id": session_id}, session_id=session_id)

    mem.end_session = _end_session

    # ------------------------------------------------------------------
    # add_session_memory
    # ------------------------------------------------------------------
    _orig_add = mem.add_session_memory

    def _add_session_memory(session_id, text, node_type, metadata=None, **kwargs):
        result = _orig_add(session_id, text, node_type, metadata, **kwargs)
        _publish("memory.item.added", {
            "memory_id": result.id,
            "session_id": session_id,
            "node_type": node_type,
            "text_length": len(text),
            "text_preview": text[:200],
        }, session_id=session_id)
        return result

    mem.add_session_memory = _add_session_memory

    # ------------------------------------------------------------------
    # upsert_entity
    # ------------------------------------------------------------------
    _orig_upsert = mem.upsert_entity

    def _upsert_entity(entity_id, etype, labels=None, properties=None):
        result = _orig_upsert(entity_id, etype, labels, properties)
        sid = (session_id_fn() if session_id_fn else None) or (
            (properties or {}).get("session_id")
        )
        _publish("memory.entity.upsert", {
            "entity_id": entity_id,
            "type": etype,
            "labels": labels or [],
        }, session_id=sid)
        return result

    mem.upsert_entity = _upsert_entity

    # ------------------------------------------------------------------
    # link
    # ------------------------------------------------------------------
    _orig_link = mem.link

    def _link(src, dst, rel, properties=None):
        result = _orig_link(src, dst, rel, properties)
        sid = session_id_fn() if session_id_fn else None
        _publish("memory.link", {
            "src": src, "dst": dst, "rel": rel,
        }, session_id=sid)
        return result

    mem.link = _link

    # ------------------------------------------------------------------
    # attach_document
    # ------------------------------------------------------------------
    _orig_attach = mem.attach_document

    def _attach_document(entity_id, doc_id, text, metadata=None):
        result = _orig_attach(entity_id, doc_id, text, metadata)
        sid = session_id_fn() if session_id_fn else None
        _publish("memory.document.attached", {
            "entity_id": entity_id,
            "doc_id": doc_id,
            "text_length": len(text),
        }, session_id=sid)
        return result

    mem.attach_document = _attach_document

    # ------------------------------------------------------------------
    # semantic_retrieve
    # ------------------------------------------------------------------
    _orig_retrieve = mem.semantic_retrieve

    def _semantic_retrieve(query, k=8, where=None):
        results = _orig_retrieve(query, k=k, where=where)
        sid = session_id_fn() if session_id_fn else None
        _publish("memory.semantic.query", {
            "query": query[:200],
            "k": k,
            "hits": len(results),
        }, session_id=sid)
        return results

    mem.semantic_retrieve = _semantic_retrieve

    # ------------------------------------------------------------------
    # promote_session_memory_to_long_term
    # ------------------------------------------------------------------
    _orig_promote = mem.promote_session_memory_to_long_term

    def _promote(item, entity_anchor=None):
        result = _orig_promote(item, entity_anchor)
        _publish("memory.promoted", {
            "memory_id": item.id,
            "node_type": item.metadata.get("type", "unknown"),
            "entity_anchor": entity_anchor,
        }, session_id=item.metadata.get("session_id"))
        return result

    mem.promote_session_memory_to_long_term = _promote

    log.info("[MemoryIntegration] HybridMemory wired to EventBus — all operations will emit events.")