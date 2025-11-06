from typing import Dict, Any, List
from collections import defaultdict
from fastapi import WebSocket
from your_project.core.vera import Vera

# ============================================================
# Global storage
# ============================================================
vera_instances: Dict[str, Vera] = {}
sessions: Dict[str, Dict[str, Any]] = {}
tts_queue: List[Dict[str, Any]] = []
tts_playing = False

# Toolchain monitoring storage
toolchain_executions: Dict[str, Dict[str, Any]] = defaultdict(dict)  # session_id -> execution_id -> execution_data
active_toolchains: Dict[str, str] = {}  # session_id -> current execution_id
websocket_connections: Dict[str, List[WebSocket]] = defaultdict(list)  # session_id -> [websockets]
