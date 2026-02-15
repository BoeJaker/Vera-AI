"""
Vera Tool Framework - UI
==========================
UI descriptor system for tool-associated frontend components.

Tools declare their UI requirements via UIDescriptor objects attached
to their ToolDescriptor. The frontend reads these to render appropriate
components when a tool is active or producing output.

The system supports:
    - Console: Streaming text output (log viewer)
    - Table: Structured data display
    - Chart: Time series, bar charts, etc.
    - Form: Dynamic input form generated from schema
    - Monitor: Live status dashboard with metrics
    - Graph: Knowledge graph visualiser
    - Map: Network topology or geo map
    - Terminal: Interactive command terminal
    - Custom: Arbitrary React component

All UI descriptors are serialisable to JSON for frontend consumption.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("vera.tools.ui")


class UIComponentType(str, Enum):
    """Types of UI components the frontend can render."""
    CONSOLE   = "console"
    TABLE     = "table"
    CHART     = "chart"
    FORM      = "form"
    MONITOR   = "monitor"
    GRAPH     = "graph"
    MAP       = "map"
    TERMINAL  = "terminal"
    CUSTOM    = "custom"


class UIDescriptor(BaseModel):
    """
    Describes a UI component that a tool can inject into the frontend.
    
    Frontend reads this descriptor to render the right component
    and wire it up to the tool's event channel for live updates.
    
    JSON format sent to frontend:
    {
        "component": "console",
        "channel": "tool.port_scanner.ui",
        "title": "Port Scanner Output",
        "position": "panel",
        "config": {
            "max_lines": 500,
            "auto_scroll": true,
            "theme": "dark"
        },
        "actions": [
            {"id": "clear", "label": "Clear", "icon": "trash"},
            {"id": "export", "label": "Export", "icon": "download"}
        ],
        "initial_state": {}
    }
    """
    component: UIComponentType
    channel: str = ""            # Event bus channel for live updates
    title: str = ""
    subtitle: str = ""
    position: str = "panel"      # panel | sidebar | overlay | inline | tab
    width: Optional[str] = None  # CSS width hint (e.g. "600px", "50%")
    height: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, str]] = Field(default_factory=list)  # Toolbar actions
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    
    # For CUSTOM components
    custom_component_id: Optional[str] = None
    custom_props: Dict[str, Any] = Field(default_factory=dict)

    def to_frontend_json(self) -> Dict[str, Any]:
        """Serialise for frontend consumption."""
        data = self.model_dump(exclude_none=True)
        data["component"] = self.component.value
        return data


# ============================================================================
# BUILDER FUNCTIONS - Convenience constructors for common UI patterns
# ============================================================================

def build_console_ui(
    tool_name: str,
    title: Optional[str] = None,
    max_lines: int = 500,
    auto_scroll: bool = True,
    theme: str = "dark",
    show_timestamps: bool = True,
    actions: Optional[List[Dict[str, str]]] = None,
    position: str = "panel",
) -> UIDescriptor:
    """
    Build a streaming console UI descriptor.
    
    The console displays streaming text output from the tool,
    similar to a terminal or log viewer.
    
    Frontend listens on channel for messages of shape:
        {"type": "log", "text": "...", "level": "info|warn|error", "timestamp": ...}
        {"type": "clear"}
    """
    return UIDescriptor(
        component=UIComponentType.CONSOLE,
        channel=f"tool.{tool_name}.ui",
        title=title or f"{tool_name} Output",
        position=position,
        config={
            "max_lines": max_lines,
            "auto_scroll": auto_scroll,
            "theme": theme,
            "show_timestamps": show_timestamps,
            "monospace": True,
        },
        actions=actions or [
            {"id": "clear", "label": "Clear", "icon": "trash"},
            {"id": "export", "label": "Export", "icon": "download"},
            {"id": "pause", "label": "Pause", "icon": "pause"},
        ],
    )


def build_schema_ui(
    tool_name: str,
    input_schema: Dict[str, Any],
    title: Optional[str] = None,
    output_component: UIComponentType = UIComponentType.CONSOLE,
    position: str = "panel",
) -> UIDescriptor:
    """
    Build a form + output UI from a tool's input/output schema.
    
    Generates a dynamic form from the Pydantic/JSON schema,
    with a connected output component for results.
    
    Frontend renders form fields based on schema types:
        string → text input
        integer/number → number input
        boolean → toggle
        enum → dropdown
        array → multi-input
    """
    return UIDescriptor(
        component=UIComponentType.FORM,
        channel=f"tool.{tool_name}.ui",
        title=title or f"{tool_name}",
        position=position,
        config={
            "schema": input_schema,
            "output_component": output_component.value,
            "submit_label": "Execute",
            "auto_submit": False,
        },
        actions=[
            {"id": "submit", "label": "Execute", "icon": "play"},
            {"id": "reset", "label": "Reset", "icon": "refresh"},
        ],
    )


def build_monitor_ui(
    tool_name: str,
    title: Optional[str] = None,
    metrics: Optional[List[Dict[str, str]]] = None,
    refresh_interval_ms: int = 2000,
    position: str = "panel",
) -> UIDescriptor:
    """
    Build a live monitoring dashboard UI.
    
    Displays real-time metrics, status indicators, and recent events.
    
    Frontend listens on channel for messages of shape:
        {"type": "metric", "name": "...", "value": ..., "unit": "..."}
        {"type": "status", "state": "running|warning|error|idle"}
        {"type": "event", "text": "...", "severity": "info|warn|error"}
    """
    default_metrics = [
        {"name": "status", "label": "Status", "type": "badge"},
        {"name": "uptime", "label": "Uptime", "type": "duration"},
        {"name": "events", "label": "Events", "type": "counter"},
    ]
    
    return UIDescriptor(
        component=UIComponentType.MONITOR,
        channel=f"tool.{tool_name}.ui",
        title=title or f"{tool_name} Monitor",
        position=position,
        config={
            "metrics": metrics or default_metrics,
            "refresh_interval_ms": refresh_interval_ms,
            "show_event_log": True,
            "max_events": 100,
        },
        actions=[
            {"id": "refresh", "label": "Refresh", "icon": "refresh"},
            {"id": "stop", "label": "Stop", "icon": "stop"},
            {"id": "restart", "label": "Restart", "icon": "rotate"},
        ],
    )


def build_table_ui(
    tool_name: str,
    columns: List[Dict[str, str]],
    title: Optional[str] = None,
    sortable: bool = True,
    filterable: bool = True,
    position: str = "panel",
) -> UIDescriptor:
    """
    Build a data table UI.
    
    Frontend listens on channel for messages of shape:
        {"type": "data", "rows": [...], "append": true|false}
        {"type": "clear"}
    """
    return UIDescriptor(
        component=UIComponentType.TABLE,
        channel=f"tool.{tool_name}.ui",
        title=title or f"{tool_name} Results",
        position=position,
        config={
            "columns": columns,
            "sortable": sortable,
            "filterable": filterable,
            "pagination": True,
            "page_size": 50,
        },
        actions=[
            {"id": "export_csv", "label": "CSV", "icon": "download"},
            {"id": "export_json", "label": "JSON", "icon": "download"},
            {"id": "clear", "label": "Clear", "icon": "trash"},
        ],
    )


def build_graph_ui(
    tool_name: str,
    title: Optional[str] = None,
    layout: str = "force",
    position: str = "panel",
) -> UIDescriptor:
    """
    Build a knowledge graph visualiser UI.
    
    Frontend listens on channel for messages of shape:
        {"type": "node", "id": "...", "label": "...", "group": "..."}
        {"type": "edge", "source": "...", "target": "...", "label": "..."}
        {"type": "clear"}
        {"type": "highlight", "node_ids": [...]}
    """
    return UIDescriptor(
        component=UIComponentType.GRAPH,
        channel=f"tool.{tool_name}.ui",
        title=title or f"{tool_name} Graph",
        position=position,
        config={
            "layout": layout,
            "physics": True,
            "node_colors": {},
            "edge_colors": {},
            "interactive": True,
        },
        actions=[
            {"id": "fit", "label": "Fit", "icon": "maximize"},
            {"id": "export_png", "label": "Export", "icon": "image"},
            {"id": "clear", "label": "Clear", "icon": "trash"},
        ],
    )


# ============================================================================
# AUTO-UI GENERATION
# ============================================================================

def auto_ui_from_descriptor(tool_name: str, input_schema: Optional[Dict[str, Any]] = None,
                            ui_type: str = "console") -> UIDescriptor:
    """
    Auto-generate a UI descriptor from tool metadata.
    
    Falls back to a console if no specific type is configured.
    """
    type_map = {
        "console": lambda: build_console_ui(tool_name),
        "form": lambda: build_schema_ui(tool_name, input_schema or {}),
        "monitor": lambda: build_monitor_ui(tool_name),
        "table": lambda: build_table_ui(tool_name, []),
        "graph": lambda: build_graph_ui(tool_name),
    }
    
    builder = type_map.get(ui_type, type_map["console"])
    return builder()