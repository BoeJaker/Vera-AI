#!/usr/bin/env python3
# Vera/ChatUI/api/routes/models.py
"""
GET /api/models/cluster

Returns a flat list of all models available across the Ollama cluster,
annotated with which instance they live on and basic metadata (size,
quantisation, context length).  The frontend routing control uses this to
populate the 'Specific model' picker.

Caching: results are cached for MODEL_CACHE_TTL seconds so rapid UI
refreshes don't hammer every Ollama instance.
"""

import time
import requests
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])

# ── Simple in-process cache ───────────────────────────────────────────────────
_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
MODEL_CACHE_TTL = 60.0  # seconds


def _parse_size(details: dict) -> str:
    """Extract a human-friendly parameter size string from Ollama model details."""
    param_size = details.get("parameter_size", "")
    if param_size:
        return param_size
    # Fall back to byte size if present
    size_bytes = details.get("size", 0)
    if size_bytes:
        gb = size_bytes / 1e9
        return f"{gb:.1f}GB"
    return ""


def _parse_quant(details: dict) -> str:
    return details.get("quantization_level", "")


def _parse_ctx(model_info: dict) -> str:
    ctx = model_info.get("context_length") or model_info.get("n_ctx")
    if not ctx:
        return ""
    if ctx >= 1_000_000:
        return f"{ctx // 1_000_000}M"
    if ctx >= 1_000:
        return f"{ctx // 1_000}k"
    return str(ctx)


def _fetch_models_from_instance(name: str, api_url: str, timeout: float = 6.0) -> List[Dict]:
    """Query a single Ollama instance and return annotated model dicts."""
    models_out = []
    try:
        tags_resp = requests.get(f"{api_url}/api/tags", timeout=timeout)
        if tags_resp.status_code != 200:
            return []
        for m in tags_resp.json().get("models", []):
            model_name = m.get("name") or m.get("model", "")
            if not model_name:
                continue

            details    = m.get("details", {})
            model_info: dict = {}

            # Try to get richer metadata (context length etc.) via /api/show.
            # This is optional — we skip gracefully if it fails or is slow.
            try:
                show_resp = requests.post(
                    f"{api_url}/api/show",
                    json={"name": model_name},
                    timeout=timeout,
                )
                if show_resp.status_code == 200:
                    show_data  = show_resp.json()
                    details    = show_data.get("details", details)
                    model_info = show_data.get("model_info", {})
            except Exception:
                pass  # Non-fatal — we proceed without extended metadata

            models_out.append({
                "name":     model_name,
                "instance": name,
                "size":     _parse_size(details),
                "quant":    _parse_quant(details),
                "ctx":      _parse_ctx(model_info),
                "family":   details.get("family", ""),
            })
    except Exception as e:
        logger.warning(f"Could not query instance '{name}' at {api_url}: {e}")
    return models_out


def _build_model_list(vera_instances: dict) -> List[Dict]:
    """
    Walk every healthy Ollama instance and collect annotated models.

    We reach into the vera instance pool rather than reimplementing instance
    discovery here — vera_instances is the shared dict from session.py.
    """
    all_models: List[Dict] = []
    seen: set = set()  # deduplicate by (name, instance)

    # Grab any live vera instance to access its ollama manager
    vera = None
    for v in vera_instances.values():
        if v is not None:
            vera = v
            break

    if vera is None:
        logger.warning("No active vera instances — cannot query cluster models")
        return []

    mgr = getattr(vera, 'ollama_manager', None) \
       or getattr(vera, 'llm_manager', None)

    if mgr is None or not hasattr(mgr, 'pool'):
        logger.warning("No Ollama manager found on vera instance")
        return []

    pool = mgr.pool
    for inst_name, inst_config in pool.instances.items():
        stats = pool.stats.get(inst_name)
        if stats and not stats.is_healthy:
            logger.debug(f"Skipping unhealthy instance '{inst_name}'")
            continue
        for m in _fetch_models_from_instance(inst_name, inst_config.api_url):
            key = (m["name"], m["instance"])
            if key not in seen:
                seen.add(key)
                all_models.append(m)

    # Sort: instance asc, then model name asc (embedding models last)
    def sort_key(m):
        is_embed = "embed" in m["name"].lower()
        return (m["instance"], int(is_embed), m["name"].lower())

    all_models.sort(key=sort_key)
    return all_models


@router.get("/api/models/cluster")
async def get_cluster_models():
    """
    Return all models available across the Ollama cluster.

    Response shape:
    {
        "models": [
            {
                "name":     "mistral:7b",
                "instance": "remote",
                "size":     "7B",
                "quant":    "Q4_K_M",
                "ctx":      "32k",
                "family":   "llama"
            },
            ...
        ],
        "cached": false,
        "count":  12
    }
    """
    global _cache

    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < MODEL_CACHE_TTL:
        return {
            "models": _cache["data"],
            "cached": True,
            "count":  len(_cache["data"]),
        }

    # Import here to avoid circular imports
    from Vera.ChatUI.api.session import vera_instances

    models = _build_model_list(vera_instances)

    _cache["ts"]   = now
    _cache["data"] = models

    return {
        "models": models,
        "cached": False,
        "count":  len(models),
    }


@router.post("/api/models/cluster/refresh")
async def refresh_cluster_models():
    """Force-invalidate the model cache and re-fetch immediately."""
    global _cache
    _cache = {"ts": 0.0, "data": None}

    from Vera.ChatUI.api.session import vera_instances
    models = _build_model_list(vera_instances)
    _cache["ts"]   = time.time()
    _cache["data"] = models

    return {
        "models": models,
        "cached": False,
        "count":  len(models),
        "refreshed": True,
    }