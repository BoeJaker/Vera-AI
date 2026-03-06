"""
Vera Tool Framework - Examples
================================
Demonstrates all tool patterns available in the enhanced framework.

These are REAL, usable tool implementations that serve as both
documentation and starting points for new tools.

Patterns demonstrated:
    1. Simple enhanced tool (drop-in for existing tools)
    2. Streaming tool with UI console
    3. Background service tool (e.g. network monitor)
    4. Memory-aware tool that builds graphs
    5. Sensor tool with live monitoring
    6. UI-only tool
    7. Orchestrator-integrated tool
    8. Migrated legacy tool pattern
"""

from __future__ import annotations

import json
import time
import socket
import threading
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from Vera.Toolchain.ToolFramework.core import (
    ToolCapability,
    ToolCategory,
    ToolContext,
    ToolMode,
    ToolUIType,
    enhanced_tool,
    sensor_tool,
    service_tool,
    ui_tool,
)
from Vera.Toolchain.ToolFramework.ui import (
    build_console_ui,
    build_monitor_ui,
    build_table_ui,
    build_graph_ui,
)


# ============================================================================
# PATTERN 1: Simple Enhanced Tool (drop-in replacement for existing tools)
# ============================================================================
# This is the simplest migration path. Take an existing tool function,
# add the @enhanced_tool decorator, and it gains categorisation + metadata
# while remaining fully backwards compatible.

class HashLookupInput(BaseModel):
    hash_value: str = Field(..., description="Hash to look up")
    hash_type: str = Field(default="auto", description="Hash type: md5, sha1, sha256, auto")


@enhanced_tool(
    "hash_lookup",
    "Look up a hash value against known databases",
    category=ToolCategory.SECURITY,
    mode=ToolMode.MULTIPURPOSE,
    tags=["hash", "security", "lookup"],
    input_schema=HashLookupInput,
    cost_hint="low",
)
def hash_lookup(ctx: ToolContext, hash_value: str, hash_type: str = "auto") -> str:
    """
    Simple tool - works exactly like existing tools.
    ctx is a ToolContext but proxies to agent for backwards compat.
    """
    # Can use memory if available
    cached = ctx.memory_search(f"hash {hash_value}", k=1)
    if cached:
        return f"Cached result: {cached[0].get('text', '')}"
    
    # Do the lookup (placeholder)
    result = f"Hash {hash_value} ({hash_type}): No results found in local database"
    
    # Save to memory
    ctx.memory_save(result, {"hash": hash_value, "type": hash_type})
    
    return result


# ============================================================================
# PATTERN 2: Streaming Tool with UI Console
# ============================================================================
# Yields output chunks and pushes them to a console UI component.
# The frontend renders a live console that shows output as it arrives.

class PortScanInput(BaseModel):
    target: str = Field(..., description="Target host or IP")
    ports: str = Field(default="1-1024", description="Port range (e.g. '80,443' or '1-1024')")
    timeout: float = Field(default=1.0, description="Connection timeout per port")


@enhanced_tool(
    "port_scanner",
    "Scan ports on a target host with live output",
    category=ToolCategory.SECURITY,
    mode=ToolMode.MULTIPURPOSE,
    capabilities=ToolCapability.STREAMING | ToolCapability.UI | ToolCapability.GRAPH_BUILD,
    tags=["network", "scanning", "ports", "security"],
    ui_type=ToolUIType.CONSOLE,
    ui_config={"max_lines": 1000, "show_timestamps": True},
    can_run_as_service=True,  # Can also run as continuous background scanner
    input_schema=PortScanInput,
    cost_hint="medium",
    estimated_duration=30.0,
)
def port_scanner(ctx: ToolContext, target: str, ports: str = "1-1024",
                 timeout: float = 1.0, _stop_event=None):
    """
    Streaming port scanner.
    
    Yields results as each port is checked.
    Pushes to UI console for live display.
    Builds graph nodes for discovered services.
    
    Can run as:
        - One-shot tool call: scans and returns results
        - Background service: scans continuously at intervals
    """
    # Parse port range
    port_list = _parse_ports(ports)
    total = len(port_list)
    open_ports = []
    
    ctx.ui_push({"type": "log", "text": f"Starting scan of {target} ({total} ports)", "level": "info"})
    ctx.emit("tool.progress", {"percent": 0, "total_ports": total})
    
    # Start execution tracking for graph
    ctx.start_execution_tracking()
    
    # Create host node in graph
    host_id = f"host_{target.replace('.', '_')}"
    ctx.graph_upsert_entity(host_id, "NetworkHost", 
                            labels=["NetworkHost", "ScanTarget"],
                            props={"ip": target, "scanned_at": time.time()})
    
    for i, port in enumerate(port_list):
        # Check stop signal (for service mode)
        if _stop_event and _stop_event.is_set():
            yield f"\n[Scan interrupted at port {port}]"
            break
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((target, port))
            sock.close()
            
            if result == 0:
                open_ports.append(port)
                service = _guess_service(port)
                line = f"  OPEN  {port:>5}/tcp  {service}"
                
                # Push to UI
                ctx.ui_push({"type": "log", "text": line, "level": "success"})
                
                # Build graph
                port_id = f"{host_id}_port_{port}"
                ctx.graph_upsert_entity(port_id, "NetworkPort",
                                        labels=["NetworkPort", "OpenPort"],
                                        props={"port": port, "service": service, "state": "open"})
                ctx.graph_link(host_id, port_id, "HAS_PORT")
                
                yield line + "\n"
            
        except Exception as e:
            ctx.ui_push({"type": "log", "text": f"Error on port {port}: {e}", "level": "error"})
        
        # Progress
        if (i + 1) % 100 == 0 or i == total - 1:
            pct = ((i + 1) / total) * 100
            ctx.emit("tool.progress", {"percent": pct})
            ctx.ui_push({"type": "status", "progress": pct / 100})
    
    # Summary
    summary = f"\nScan complete: {len(open_ports)} open ports on {target}"
    ctx.ui_push({"type": "log", "text": summary, "level": "info"})
    ctx.memory_save(summary, {"target": target, "open_ports": open_ports})
    ctx.finish_execution_tracking(output=summary)
    
    yield summary


# ============================================================================
# PATTERN 3: Background Service Tool
# ============================================================================
# Runs continuously in the background. Can be queried while running.
# Streams updates to UI via the event bus.

@service_tool(
    "network_monitor",
    "Monitor network connectivity to specified hosts",
    category=ToolCategory.MONITORING,
    tags=["network", "monitoring", "uptime", "ping"],
    ui_type=ToolUIType.MONITOR,
)
def network_monitor(ctx: ToolContext, hosts: str = "8.8.8.8,1.1.1.1",
                    interval: int = 30, _stop_event=None):
    """
    Background service that monitors network hosts.
    
    Yields status updates at each interval.
    Pushes metrics to the monitor UI.
    """
    host_list = [h.strip() for h in hosts.split(",")]
    check_count = 0
    
    ctx.ui_push({"type": "status", "state": "running"})
    ctx.ui_push({"type": "log", "text": f"Monitoring {len(host_list)} hosts every {interval}s"})
    
    while not (_stop_event and _stop_event.is_set()):
        check_count += 1
        results = {}
        
        for host in host_list:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                start = time.time()
                result = sock.connect_ex((host, 80))
                latency = (time.time() - start) * 1000
                sock.close()
                
                status = "up" if result == 0 else "down"
                results[host] = {"status": status, "latency_ms": round(latency, 1)}
            except Exception:
                results[host] = {"status": "error", "latency_ms": -1}
        
        # Push to UI
        for host, data in results.items():
            ctx.ui_push({
                "type": "metric",
                "name": host,
                "value": data["latency_ms"],
                "unit": "ms",
                "status": data["status"],
            })
        
        ctx.ui_push({
            "type": "event",
            "text": f"Check #{check_count}: {sum(1 for d in results.values() if d['status'] == 'up')}/{len(host_list)} hosts up",
            "severity": "info",
        })
        
        yield {
            "check": check_count,
            "timestamp": time.time(),
            "results": results,
        }
        
        # Wait for next interval (interruptible)
        if _stop_event:
            _stop_event.wait(timeout=interval)
        else:
            time.sleep(interval)
    
    ctx.ui_push({"type": "status", "state": "stopped"})


# ============================================================================
# PATTERN 4: Memory-Aware Tool with Graph Building
# ============================================================================
# Reads from and writes to the memory system.
# Builds structured knowledge graph from its output.

@enhanced_tool(
    "dependency_mapper",
    "Map dependencies between code modules and build a dependency graph",
    category=ToolCategory.CODING,
    mode=ToolMode.MULTIPURPOSE,
    capabilities=(
        ToolCapability.MEMORY_READ | ToolCapability.MEMORY_WRITE |
        ToolCapability.GRAPH_BUILD | ToolCapability.STREAMING | ToolCapability.UI
    ),
    tags=["code", "dependencies", "analysis", "graph"],
    ui_type=ToolUIType.GRAPH,
    cost_hint="medium",
    estimated_duration=15.0,
)
def dependency_mapper(ctx: ToolContext, path: str, language: str = "python"):
    """
    Analyses code at the given path and builds a dependency graph in memory.
    
    Pushes graph nodes/edges to the UI for visualisation.
    Stores the dependency tree in the knowledge graph.
    """
    import os
    
    ctx.start_execution_tracking()
    ctx.ui_push({"type": "clear"})
    
    # Check memory for previous scan
    previous = ctx.memory_search(f"dependency scan {path}", k=1)
    if previous:
        ctx.ui_push({"type": "event", "text": "Found previous scan in memory, will compare"})
    
    # Scan files
    modules_found = 0
    deps_found = 0
    
    for root, dirs, files in os.walk(path):
        for f in files:
            if not f.endswith(".py"):
                continue
            
            filepath = os.path.join(root, f)
            module_name = filepath.replace(path, "").replace("/", ".").replace(".py", "").strip(".")
            
            if not module_name:
                continue
            
            modules_found += 1
            module_id = f"module_{module_name.replace('.', '_')}"
            
            # Create module node
            ctx.graph_upsert_entity(module_id, "CodeModule",
                                    labels=["CodeModule", "PythonModule"],
                                    props={"name": module_name, "path": filepath})
            
            # Push to UI graph
            ctx.ui_push({"type": "node", "id": module_id, "label": module_name, "group": "module"})
            
            # Parse imports
            try:
                with open(filepath, "r") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith("import ") or line.startswith("from "):
                            dep = _parse_import(line)
                            if dep:
                                dep_id = f"module_{dep.replace('.', '_')}"
                                ctx.graph_upsert_entity(dep_id, "CodeModule",
                                                        labels=["CodeModule"],
                                                        props={"name": dep})
                                ctx.graph_link(module_id, dep_id, "IMPORTS")
                                ctx.ui_push({
                                    "type": "edge",
                                    "source": module_id,
                                    "target": dep_id,
                                    "label": "imports",
                                })
                                deps_found += 1
            except Exception:
                pass
            
            yield f"Mapped: {module_name} ({deps_found} deps so far)\n"
    
    summary = f"Mapped {modules_found} modules with {deps_found} dependencies"
    ctx.memory_save(summary, {"path": path, "modules": modules_found, "deps": deps_found})
    ctx.finish_execution_tracking(output=summary)
    
    yield f"\n{summary}\n"


# ============================================================================
# PATTERN 5: Sensor Tool
# ============================================================================
# Continuous data producer (like an IoT sensor).
# Emits events at intervals, queryable for latest readings.

@sensor_tool(
    "system_health_sensor",
    "Continuously monitor system health metrics (CPU, memory, disk)",
    category=ToolCategory.MONITORING,
    tags=["system", "health", "metrics", "cpu", "memory"],
)
def system_health_sensor(ctx: ToolContext, interval: int = 5, _stop_event=None):
    """
    Sensor that emits system health metrics at regular intervals.
    """
    import psutil
    
    ctx.ui_push({"type": "status", "state": "running"})
    
    while not (_stop_event and _stop_event.is_set()):
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "timestamp": time.time(),
        }
        
        # Push each metric to UI
        for key, value in metrics.items():
            if key != "timestamp":
                ctx.ui_push({
                    "type": "metric",
                    "name": key,
                    "value": value,
                    "unit": "%",
                })
        
        ctx.emit("sensor.reading", metrics)
        
        yield metrics
        
        if _stop_event:
            _stop_event.wait(timeout=interval)
        else:
            time.sleep(interval)


# ============================================================================
# PATTERN 6: UI-Only Tool
# ============================================================================
# Not callable by LLMs - only rendered in the frontend.

@ui_tool(
    "log_viewer",
    "Interactive log viewer for Vera system logs",
    category=ToolCategory.SYSTEM,
    tags=["logs", "debug", "system"],
    ui_type=ToolUIType.CONSOLE,
)
def log_viewer(ctx: ToolContext, log_path: str = "/var/log/vera/vera.log",
               lines: int = 100):
    """
    UI-only tool that tails a log file into a console component.
    """
    import subprocess
    
    result = subprocess.run(
        ["tail", "-n", str(lines), log_path],
        capture_output=True, text=True
    )
    
    for line in result.stdout.splitlines():
        ctx.ui_push({"type": "log", "text": line})
        yield line + "\n"


# ============================================================================
# PATTERN 7: Orchestrator-Integrated Tool
# ============================================================================
# Submits work to the orchestrator task system for GPU/priority routing.

@enhanced_tool(
    "semantic_analyser",
    "Perform deep semantic analysis using GPU-accelerated embeddings",
    category=ToolCategory.LLM,
    mode=ToolMode.LLM_ONLY,
    capabilities=ToolCapability.ORCHESTRATED | ToolCapability.MEMORY_WRITE,
    tags=["nlp", "analysis", "embeddings", "gpu"],
    task_type="llm",
    priority="high",
    cost_hint="gpu",
    estimated_duration=10.0,
)
def semantic_analyser(ctx: ToolContext, text: str, depth: str = "standard") -> str:
    """
    Submits analysis to the orchestrator for GPU-routed processing.
    Falls back to local execution if orchestrator unavailable.
    """
    if ctx._orchestrator:
        # Route through orchestrator
        task_id = ctx.submit_task(
            "memory.encode_text",
            vera_instance=ctx.agent,
            text=text,
        )
        result = ctx.wait_for_task(task_id, timeout=30.0)
        if result and hasattr(result, "result"):
            embedding = result.result
            ctx.memory_save(f"Semantic analysis: {text[:100]}...",
                          {"embedding_dims": len(embedding.get("embedding", []))})
            return f"Analysis complete: {embedding.get('dimensions', '?')} dimensional embedding"
    
    # Fallback: basic analysis
    return f"Basic analysis of {len(text)} chars (orchestrator unavailable)"


# ============================================================================
# PATTERN 8: Migrating an Existing Tool
# ============================================================================
# Shows the minimal change needed to migrate an existing tool function.
# The original function signature with `agent` still works.

"""
BEFORE (existing tool in add_*_tools):
    def my_existing_tool(query: str) -> str:
        return "result"
    
    tool_list.append(StructuredTool.from_function(
        func=my_existing_tool,
        name="my_tool",
        description="Does something",
    ))

AFTER (enhanced, still backwards compatible):
    @enhanced_tool(
        "my_tool",
        "Does something",
        category=ToolCategory.UTILITY,
    )
    def my_existing_tool(ctx: ToolContext, query: str) -> str:
        return "result"
    
    # In the add_*_tools function:
    from Vera.Toolchain.ToolFramework.loader import register_enhanced_tools
    register_enhanced_tools(tool_list, agent, [my_existing_tool])
"""


# ============================================================================
# HELPERS
# ============================================================================

def _parse_ports(port_spec: str) -> List[int]:
    """Parse port specification like '80,443,8000-8100'."""
    ports = []
    for part in port_spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.extend(range(int(start), int(end) + 1))
        else:
            ports.append(int(part))
    return sorted(set(ports))


def _guess_service(port: int) -> str:
    """Guess service name from port number."""
    services = {
        21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
        53: "dns", 80: "http", 110: "pop3", 143: "imap",
        443: "https", 445: "smb", 993: "imaps", 995: "pop3s",
        3306: "mysql", 5432: "postgresql", 6379: "redis",
        8080: "http-proxy", 8443: "https-alt", 27017: "mongodb",
    }
    return services.get(port, "unknown")


def _parse_import(line: str) -> Optional[str]:
    """Extract module name from an import statement."""
    line = line.strip()
    if line.startswith("from "):
        parts = line.split()
        if len(parts) >= 2:
            return parts[1].split(".")[0]
    elif line.startswith("import "):
        parts = line.split()
        if len(parts) >= 2:
            return parts[1].split(".")[0].rstrip(",")
    return None