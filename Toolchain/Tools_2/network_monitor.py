"""
Vera Network Monitor & Scanner
================================
A production tool that demonstrates the full Vera tool framework:

  - @service_tool          long-lived background network monitor
  - @enhanced_tool         one-shot network scanner with streaming output
  - @enhanced_tool         host detail scanner (ports, OS, services)
  - UIDescriptor           monitor dashboard + console + table components
  - ToolContext             memory/graph persistence, event bus, UI push
  - start_execution_tracking / finish_execution_tracking  (auto via decorator)
  - Success/failure classification                       (auto via decorator)

FILE LAYOUT
-----------
Register in tools.py (or any add_*_tools function):

    from Vera.Toolchain.Tools.Network.network_monitor import add_network_monitor_tools
    add_network_monitor_tools(tool_list, agent)

EVENT BUS CHANNELS
------------------
    tool.network_monitor.ui         → monitor dashboard updates
    tool.network_scanner.ui         → scanner console output
    tool.host_scanner.ui            → host detail table rows
    tool.result.success / .failure  → automatic from framework

GRAPH NODES CREATED
-------------------
    NetworkHost     {ip, hostname, state, first_seen, last_seen}
    NetworkPort     {port, protocol, service, state, banner}
    NetworkScan     {target, scan_type, started_at, host_count, port_count}
    ──HOSTS──>      NetworkScan -[DISCOVERED]-> NetworkHost
    ──PORTS──>      NetworkHost -[HAS_PORT]->   NetworkPort
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

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
)
from Vera.Toolchain.ToolFramework.ui import (
    build_console_ui,
    build_monitor_ui,
    build_table_ui,
    UIDescriptor,
    UIComponentType,
)
from Vera.Toolchain.ToolFramework.loader import register_enhanced_tools

import logging
log = logging.getLogger("vera.tools.network_monitor")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class NetworkMonitorInput(BaseModel):
    targets: str = Field(
        default="192.168.1.0/24",
        description="CIDR range(s) to monitor, comma-separated. E.g. '192.168.1.0/24,10.0.0.0/24'",
    )
    interval: int = Field(
        default=60,
        ge=10,
        description="Seconds between full sweeps (minimum 10)",
    )
    port_check: str = Field(
        default="22,80,443,8080,3306,5432",
        description="Comma-separated ports to probe on each discovered host",
    )
    alert_on_new: bool = Field(
        default=True,
        description="Emit alert event when a new host is discovered",
    )
    alert_on_down: bool = Field(
        default=True,
        description="Emit alert event when a previously-up host goes down",
    )


class NetworkScanInput(BaseModel):
    target: str = Field(
        ...,
        description="Target CIDR (e.g. '192.168.1.0/24') or single IP",
    )
    ports: str = Field(
        default="21,22,23,25,53,80,110,143,443,445,3306,3389,5432,6379,8080,8443,27017",
        description="Comma-separated ports or ranges (e.g. '1-1024,3306,5432')",
    )
    timeout: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Connection timeout per port in seconds",
    )
    max_threads: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Parallel threads for port scanning",
    )


class HostScanInput(BaseModel):
    host: str = Field(..., description="Single IP or hostname to scan in detail")
    ports: str = Field(
        default="1-1024",
        description="Port range to scan",
    )
    grab_banners: bool = Field(
        default=True,
        description="Attempt to grab service banners from open ports",
    )
    timeout: float = Field(default=1.0, ge=0.1, le=10.0)


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

# Common service port mapping
_PORT_SERVICES: Dict[int, str] = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis", 7474: "Neo4j", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    9200: "Elasticsearch", 11211: "Memcached", 27017: "MongoDB",
}

# Alert severity colours for the UI
_SEVERITY = {
    "info":    "#4fc3f7",
    "success": "#66bb6a",
    "warning": "#ffa726",
    "error":   "#ef5350",
    "new":     "#ce93d8",
}


def _parse_ports(spec: str) -> List[int]:
    """Parse '22,80,8080-8090,443' → sorted list of ints."""
    ports: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            ports.extend(range(int(lo), int(hi) + 1))
        else:
            ports.append(int(part))
    return sorted(set(ports))


def _parse_targets(spec: str) -> List[str]:
    """Expand CIDR(s) or single IPs into a flat list of IP strings."""
    ips: List[str] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            net = ipaddress.ip_network(part, strict=False)
            ips.extend(str(ip) for ip in net.hosts())
        except ValueError:
            ips.append(part)   # treat as hostname
    return ips


def _ping(host: str, timeout: float = 0.5) -> bool:
    """ICMP ping via subprocess — works without root if kernel allows."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host],
            capture_output=True, timeout=timeout + 2,
        )
        return result.returncode == 0
    except Exception:
        return False


def _tcp_connect(host: str, port: int, timeout: float = 0.5) -> bool:
    """Single TCP connect probe."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _grab_banner(host: str, port: int, timeout: float = 1.0) -> str:
    """Attempt to read a service banner from an open port."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(b"\r\n")
            data = s.recv(256)
            return data.decode("utf-8", errors="replace").strip()[:120]
    except Exception:
        return ""


def _resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts() -> str:
    return datetime.utcnow().strftime("%H:%M:%S")


# ============================================================================
# UI DESCRIPTORS
# ============================================================================

def _monitor_ui(tool_name: str) -> UIDescriptor:
    """Live dashboard UI for the background monitor service."""
    return build_monitor_ui(
        tool_name=tool_name,
        title="Network Monitor",
        metrics=[
            {"name": "hosts_up",      "label": "Hosts Up",       "type": "counter"},
            {"name": "hosts_down",    "label": "Hosts Down",     "type": "counter"},
            {"name": "hosts_new",     "label": "New (session)",  "type": "counter"},
            {"name": "sweep_count",   "label": "Sweeps",         "type": "counter"},
            {"name": "last_sweep",    "label": "Last Sweep",     "type": "text"},
            {"name": "sweep_time_ms", "label": "Sweep ms",       "type": "gauge"},
        ],
        refresh_interval_ms=5000,
        position="panel",
    )


def _scanner_ui(tool_name: str) -> UIDescriptor:
    """Streaming console UI for one-shot scans."""
    return build_console_ui(
        tool_name=tool_name,
        title="Network Scanner",
        max_lines=2000,
        auto_scroll=True,
        theme="dark",
        show_timestamps=True,
        position="panel",
        actions=[
            {"id": "clear",  "label": "Clear",  "icon": "trash"},
            {"id": "export", "label": "Export", "icon": "download"},
            {"id": "pause",  "label": "Pause",  "icon": "pause"},
        ],
    )


def _host_table_ui(tool_name: str) -> UIDescriptor:
    """Tabular results UI for host detail scans."""
    return build_table_ui(
        tool_name=tool_name,
        title="Host Scan Results",
        columns=[
            {"key": "port",     "label": "Port",    "width": "80px"},
            {"key": "state",    "label": "State",   "width": "80px"},
            {"key": "service",  "label": "Service", "width": "100px"},
            {"key": "banner",   "label": "Banner"},
        ],
        sortable=True,
        filterable=True,
        position="panel",
    )


# ============================================================================
# TOOL 1 — Background Network Monitor (service_tool)
# ============================================================================

@service_tool(
    "network_monitor",
    "Monitor one or more network ranges continuously. Detects new hosts, "
    "tracks up/down state, checks key ports, and streams live updates to "
    "the dashboard UI.",
    category=ToolCategory.MONITORING,
    capabilities=(
        ToolCapability.SERVICE |
        ToolCapability.STREAMING |
        ToolCapability.SENSOR |
        ToolCapability.UI |
        ToolCapability.MEMORY_WRITE |
        ToolCapability.GRAPH_BUILD |
        ToolCapability.EVENT_EMITTER
    ),
    tags=["network", "monitor", "discovery", "uptime", "service"],
    ui_type=ToolUIType.MONITOR,
    input_schema=NetworkMonitorInput,
    cost_hint="low",
    estimated_duration=0,  # runs indefinitely
)
def network_monitor(
    ctx: ToolContext,
    targets: str = "192.168.1.0/24",
    interval: int = 60,
    port_check: str = "22,80,443,8080,3306,5432",
    alert_on_new: bool = True,
    alert_on_down: bool = True,
    _stop_event: Optional[threading.Event] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Long-running network monitor service.

    Each sweep:
      1. Pings every host in the target range(s).
      2. For each live host, probes the configured ports.
      3. Updates the knowledge graph and emits UI metrics.
      4. Yields a sweep-summary dict (captured by ServiceManager output buffer).
      5. Sleeps until next interval (honouring _stop_event for clean shutdown).

    UI events emitted (channel: tool.network_monitor.ui):
      {"type": "metric",  "name": ..., "value": ...}   — dashboard counters
      {"type": "event",   "text": ..., "severity": ...} — alert log
      {"type": "status",  "state": ...}                 — running / stopped
    """
    # Attach a UI descriptor to the event bus so the frontend knows what
    # component to render before any data arrives.
    ctx.ui_push({"type": "descriptor", "ui": _monitor_ui("network_monitor").to_frontend_json()})
    ctx.ui_push({"type": "status", "state": "starting"})

    probe_ports = _parse_ports(port_check)
    known_hosts: Dict[str, Dict[str, Any]] = {}   # ip → {state, ports, hostname}
    sweep_count = 0
    session_new = 0

    # Create a scan node in the graph to anchor all discoveries
    scan_node_id = f"scan_monitor_{int(time.time())}"
    ctx.graph_upsert_entity(
        scan_node_id, "NetworkScan",
        labels=["NetworkScan", "MonitorSession"],
        props={
            "targets":    targets,
            "started_at": _now_iso(),
            "type":       "continuous_monitor",
        },
    )

    _log_event(ctx, f"Monitor started | targets={targets} | interval={interval}s", "info")
    ctx.ui_push({"type": "status", "state": "running"})

    while not (_stop_event and _stop_event.is_set()):
        sweep_start = time.time()
        sweep_count += 1
        target_ips  = _parse_targets(targets)

        # ── Ping sweep (parallel) ────────────────────────────────────────
        up_this_sweep: List[str] = []

        with ThreadPoolExecutor(max_workers=100) as pool:
            futures = {pool.submit(_ping, ip): ip for ip in target_ips}
            for fut in as_completed(futures):
                ip = futures[fut]
                try:
                    if fut.result():
                        up_this_sweep.append(ip)
                except Exception:
                    pass

        # ── Detect state changes ─────────────────────────────────────────
        up_set   = set(up_this_sweep)
        known_up = {ip for ip, d in known_hosts.items() if d.get("state") == "up"}

        newly_up   = up_set - known_up
        newly_down = known_up - up_set

        for ip in newly_up:
            hostname = _resolve_hostname(ip)
            known_hosts.setdefault(ip, {})
            known_hosts[ip]["state"]    = "up"
            known_hosts[ip]["hostname"] = hostname
            known_hosts[ip]["last_seen"] = _now_iso()

            if ip not in {h for h in known_hosts if known_hosts[h].get("first_seen")}:
                known_hosts[ip]["first_seen"] = _now_iso()
                session_new += 1

                # Graph
                host_id = _host_node_id(ip)
                ctx.graph_upsert_entity(
                    host_id, "NetworkHost",
                    labels=["NetworkHost", "ActiveHost"],
                    props={
                        "ip": ip, "hostname": hostname,
                        "state": "up",
                        "first_seen": known_hosts[ip]["first_seen"],
                        "last_seen":  known_hosts[ip]["last_seen"],
                    },
                )
                ctx.graph_link(scan_node_id, host_id, "DISCOVERED")

                if alert_on_new:
                    _log_event(ctx, f"NEW HOST  {ip}  {hostname}", "new")
                    ctx.emit("network.alert", {
                        "type": "new_host", "ip": ip, "hostname": hostname,
                    })
            else:
                # Host came back up
                _log_event(ctx, f"BACK UP   {ip}  {known_hosts[ip].get('hostname', '')}", "success")

        for ip in newly_down:
            known_hosts[ip]["state"]   = "down"
            known_hosts[ip]["down_at"] = _now_iso()
            # Update graph
            ctx.graph_upsert_entity(
                _host_node_id(ip), "NetworkHost",
                props={"state": "down", "down_at": known_hosts[ip]["down_at"]},
            )
            if alert_on_down:
                _log_event(ctx, f"DOWN      {ip}  {known_hosts[ip].get('hostname', '')}", "error")
                ctx.emit("network.alert", {"type": "host_down", "ip": ip})

        # ── Port probing on live hosts ───────────────────────────────────
        if probe_ports:
            for ip in up_this_sweep:
                host_id  = _host_node_id(ip)
                open_ports: List[int] = []
                with ThreadPoolExecutor(max_workers=30) as ppool:
                    pfutures = {
                        ppool.submit(_tcp_connect, ip, p, 0.3): p
                        for p in probe_ports
                    }
                    for pf in as_completed(pfutures):
                        port = pfutures[pf]
                        try:
                            if pf.result():
                                open_ports.append(port)
                                port_id  = f"{host_id}_port_{port}"
                                service  = _PORT_SERVICES.get(port, "unknown")
                                ctx.graph_upsert_entity(
                                    port_id, "NetworkPort",
                                    labels=["NetworkPort"],
                                    props={
                                        "port": port, "protocol": "tcp",
                                        "service": service, "state": "open",
                                        "last_seen": _now_iso(),
                                    },
                                )
                                ctx.graph_link(host_id, port_id, "HAS_PORT")
                        except Exception:
                            pass
                known_hosts[ip]["open_ports"] = open_ports

        # ── Metrics push to dashboard UI ─────────────────────────────────
        hosts_up   = len([h for h in known_hosts.values() if h.get("state") == "up"])
        hosts_down = len([h for h in known_hosts.values() if h.get("state") == "down"])
        sweep_ms   = (time.time() - sweep_start) * 1000

        for metric_name, value in [
            ("hosts_up",      hosts_up),
            ("hosts_down",    hosts_down),
            ("hosts_new",     session_new),
            ("sweep_count",   sweep_count),
            ("last_sweep",    _ts()),
            ("sweep_time_ms", round(sweep_ms)),
        ]:
            ctx.ui_push({"type": "metric", "name": metric_name, "value": value})

        sweep_summary = {
            "sweep":        sweep_count,
            "timestamp":    _now_iso(),
            "targets":      targets,
            "hosts_up":     hosts_up,
            "hosts_down":   hosts_down,
            "newly_up":     list(newly_up),
            "newly_down":   list(newly_down),
            "session_new":  session_new,
            "sweep_ms":     round(sweep_ms),
        }

        _log_event(
            ctx,
            f"Sweep #{sweep_count} done | up={hosts_up} down={hosts_down} "
            f"new_session={session_new} | {sweep_ms:.0f}ms",
            "info",
        )

        yield sweep_summary

        # ── Wait for next interval ───────────────────────────────────────
        if _stop_event:
            _stop_event.wait(timeout=interval)
        else:
            time.sleep(interval)

    ctx.ui_push({"type": "status", "state": "stopped"})
    _log_event(ctx, f"Monitor stopped after {sweep_count} sweeps", "info")


# ============================================================================
# TOOL 2 — One-Shot Network Scanner (enhanced_tool, streaming)
# ============================================================================

@enhanced_tool(
    "network_scan",
    "Scan a network range for live hosts and open ports. Streams results "
    "to a console UI as they arrive. Saves all discoveries to the knowledge graph.",
    category=ToolCategory.SECURITY,
    mode=ToolMode.MULTIPURPOSE,
    capabilities=(
        ToolCapability.STREAMING |
        ToolCapability.UI |
        ToolCapability.MEMORY_WRITE |
        ToolCapability.GRAPH_BUILD
    ),
    tags=["network", "scan", "discovery", "ports", "osint"],
    ui_type=ToolUIType.CONSOLE,
    input_schema=NetworkScanInput,
    cost_hint="medium",
    estimated_duration=60.0,
)
def network_scan(
    ctx: ToolContext,
    target: str,
    ports: str = "21,22,23,25,53,80,110,143,443,445,3306,3389,5432,6379,8080,8443,27017",
    timeout: float = 0.5,
    max_threads: int = 50,
) -> Iterator[str]:
    """
    One-shot scanner.  Discovers live hosts in the target range then
    probes each for open ports in parallel.

    Streams progress to the console UI and yields text chunks that the
    toolchain / LLM can read.  Saves all findings to the knowledge graph.
    """
    ctx.ui_push({"type": "descriptor", "ui": _scanner_ui("network_scan").to_frontend_json()})
    ctx.start_execution_tracking()

    port_list   = _parse_ports(ports)
    target_ips  = _parse_targets(target)
    total_hosts = len(target_ips)

    header = (
        f"╔══ Network Scan ══════════════════════════════════════════\n"
        f"║  Target:  {target}\n"
        f"║  Hosts:   {total_hosts}\n"
        f"║  Ports:   {len(port_list)}\n"
        f"║  Threads: {max_threads}\n"
        f"║  Started: {_now_iso()}\n"
        f"╚═══════════════════════════════════════════════════════════\n"
    )
    yield header
    ctx.ui_push({"type": "log", "text": header, "level": "info"})

    # Create a scan node
    scan_id = f"scan_{int(time.time())}"
    ctx.graph_upsert_entity(
        scan_id, "NetworkScan",
        labels=["NetworkScan", "OneShotScan"],
        props={
            "target": target, "port_count": len(port_list),
            "host_count": total_hosts, "started_at": _now_iso(),
            "type": "one_shot",
        },
    )

    # ── Phase 1: Host discovery (ping sweep) ────────────────────────────
    yield "\n[ Phase 1 ] Host discovery...\n"
    ctx.ui_push({"type": "log", "text": "[ Phase 1 ] Host discovery...", "level": "info"})

    live_hosts: List[str] = []
    pinged = 0

    with ThreadPoolExecutor(max_workers=100) as pool:
        futures = {pool.submit(_ping, ip, timeout): ip for ip in target_ips}
        for fut in as_completed(futures):
            ip = futures[fut]
            pinged += 1
            try:
                if fut.result():
                    live_hosts.append(ip)
                    hostname = _resolve_hostname(ip)
                    line = f"  ● {ip:<18} {hostname}"
                    yield line + "\n"
                    ctx.ui_push({"type": "log", "text": line, "level": "success"})

                    # Graph
                    host_id = _host_node_id(ip)
                    ctx.graph_upsert_entity(
                        host_id, "NetworkHost",
                        labels=["NetworkHost"],
                        props={
                            "ip": ip, "hostname": hostname,
                            "state": "up", "first_seen": _now_iso(),
                        },
                    )
                    ctx.graph_link(scan_id, host_id, "DISCOVERED")
            except Exception:
                pass

            if pinged % 50 == 0:
                pct = pinged / total_hosts * 100
                ctx.ui_push({"type": "progress", "percent": pct * 0.5})  # phase 1 = 0-50%

    discovery_line = (
        f"\n  Found {len(live_hosts)} live hosts "
        f"from {total_hosts} probed ({pinged} attempted)\n"
    )
    yield discovery_line
    ctx.ui_push({"type": "log", "text": discovery_line.strip(), "level": "info"})

    if not live_hosts:
        msg = "No live hosts found. Scan complete.\n"
        yield msg
        ctx.ui_push({"type": "log", "text": msg, "level": "warning"})
        ctx.finish_execution_tracking(output=msg)
        return

    # ── Phase 2: Port scanning ──────────────────────────────────────────
    yield "\n[ Phase 2 ] Port scanning...\n"
    ctx.ui_push({"type": "log", "text": "[ Phase 2 ] Port scanning...", "level": "info"})

    total_open  = 0
    hosts_done  = 0

    for ip in live_hosts:
        host_id = _host_node_id(ip)
        open_ports: List[Tuple[int, str]] = []

        with ThreadPoolExecutor(max_workers=max_threads) as pool:
            futures = {pool.submit(_tcp_connect, ip, p, timeout): p for p in port_list}
            for fut in as_completed(futures):
                port = futures[fut]
                try:
                    if fut.result():
                        service = _PORT_SERVICES.get(port, "unknown")
                        open_ports.append((port, service))
                        total_open += 1

                        # Graph
                        port_id = f"{host_id}_port_{port}"
                        ctx.graph_upsert_entity(
                            port_id, "NetworkPort",
                            labels=["NetworkPort", "OpenPort"],
                            props={
                                "port": port, "protocol": "tcp",
                                "service": service, "state": "open",
                            },
                        )
                        ctx.graph_link(host_id, port_id, "HAS_PORT")
                except Exception:
                    pass

        # Emit host block
        hostname = _resolve_hostname(ip)
        block_header = f"\n  ┌─ {ip}  {hostname}\n"
        yield block_header
        ctx.ui_push({"type": "log", "text": block_header.strip(), "level": "info"})

        if open_ports:
            for port, service in sorted(open_ports):
                line = f"  │  {port:<6}/tcp  {service}"
                yield line + "\n"
                ctx.ui_push({"type": "log", "text": line, "level": "success"})
        else:
            line = "  │  (no open ports in range)"
            yield line + "\n"
            ctx.ui_push({"type": "log", "text": line, "level": "warning"})

        hosts_done += 1
        ctx.ui_push({
            "type": "progress",
            "percent": 50 + (hosts_done / len(live_hosts)) * 50,
        })

    # ── Summary ──────────────────────────────────────────────────────────
    summary = (
        f"\n╔══ Scan Complete ═══════════════════════════════════════════\n"
        f"║  Live hosts:  {len(live_hosts)}\n"
        f"║  Open ports:  {total_open}\n"
        f"║  Finished:    {_now_iso()}\n"
        f"╚═══════════════════════════════════════════════════════════\n"
    )
    yield summary
    ctx.ui_push({"type": "log", "text": summary, "level": "info"})
    ctx.ui_push({"type": "progress", "percent": 100})

    ctx.memory_save(
        f"Network scan of {target}: {len(live_hosts)} hosts, {total_open} open ports",
        metadata={"target": target, "live_hosts": live_hosts, "open_ports": total_open},
    )
    # finish_execution_tracking called automatically by @enhanced_tool wrapper


# ============================================================================
# TOOL 3 — Deep Host Scanner (enhanced_tool, streaming + table UI)
# ============================================================================

@enhanced_tool(
    "host_scan",
    "Deep scan a single host: all ports in range, service banners, "
    "hostname resolution. Results stream to both a console and a table UI.",
    category=ToolCategory.SECURITY,
    mode=ToolMode.MULTIPURPOSE,
    capabilities=(
        ToolCapability.STREAMING |
        ToolCapability.UI |
        ToolCapability.MEMORY_WRITE |
        ToolCapability.GRAPH_BUILD
    ),
    tags=["host", "ports", "banner", "scan", "detail"],
    ui_type=ToolUIType.TABLE,
    input_schema=HostScanInput,
    cost_hint="medium",
    estimated_duration=30.0,
)
def host_scan(
    ctx: ToolContext,
    host: str,
    ports: str = "1-1024",
    grab_banners: bool = True,
    timeout: float = 1.0,
) -> Iterator[str]:
    """
    Deep single-host scanner.

    Probes every port in the specified range, optionally grabs banners,
    and pushes rows to a live table UI as each port result arrives.
    Saves full results to the knowledge graph.
    """
    # Push both a table (for structured data) and a console (for log output)
    ctx.ui_push({"type": "descriptor", "ui": _host_table_ui("host_scan").to_frontend_json()})
    ctx.ui_push({"type": "descriptor", "ui": _scanner_ui("host_scan").to_frontend_json()})
    ctx.start_execution_tracking()

    port_list = _parse_ports(ports)
    hostname  = _resolve_hostname(host)

    header = (
        f"Host:      {host}  ({hostname or 'no PTR'})\n"
        f"Ports:     {len(port_list)}\n"
        f"Banners:   {'yes' if grab_banners else 'no'}\n"
        f"Timeout:   {timeout}s\n"
        f"Started:   {_now_iso()}\n"
        f"{'─' * 55}\n"
    )
    yield header
    ctx.ui_push({"type": "log", "text": header, "level": "info"})

    host_id = _host_node_id(host)
    ctx.graph_upsert_entity(
        host_id, "NetworkHost",
        labels=["NetworkHost"],
        props={"ip": host, "hostname": hostname, "state": "scanning"},
    )

    open_count  = 0
    total_done  = 0
    table_rows: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=100) as pool:
        futures = {pool.submit(_tcp_connect, host, p, timeout): p for p in port_list}

        for fut in as_completed(futures):
            port = futures[fut]
            total_done += 1
            try:
                is_open = fut.result()
            except Exception:
                is_open = False

            if is_open:
                open_count += 1
                service = _PORT_SERVICES.get(port, "unknown")
                banner  = _grab_banner(host, port, timeout) if grab_banners else ""

                line = f"  OPEN  {port:>5}/tcp  {service:<14}  {banner[:60]}"
                yield line + "\n"
                ctx.ui_push({"type": "log", "text": line, "level": "success"})

                # Push row to table UI
                row = {
                    "port":    port,
                    "state":   "open",
                    "service": service,
                    "banner":  banner,
                }
                table_rows.append(row)
                ctx.ui_push({"type": "data", "rows": [row], "append": True})

                # Graph
                port_id = f"{host_id}_port_{port}"
                ctx.graph_upsert_entity(
                    port_id, "NetworkPort",
                    labels=["NetworkPort", "OpenPort"],
                    props={
                        "port": port, "protocol": "tcp",
                        "service": service, "state": "open",
                        "banner": banner,
                    },
                )
                ctx.graph_link(host_id, port_id, "HAS_PORT")

            if total_done % 100 == 0:
                pct = total_done / len(port_list) * 100
                ctx.ui_push({"type": "progress", "percent": pct})

    ctx.graph_upsert_entity(
        host_id, "NetworkHost",
        props={"state": "up", "scanned_at": _now_iso(), "open_ports": open_count},
    )

    summary = (
        f"{'─' * 55}\n"
        f"Done: {open_count} open / {len(port_list)} probed | {_now_iso()}\n"
    )
    yield summary
    ctx.ui_push({"type": "log",      "text": summary,       "level": "info"})
    ctx.ui_push({"type": "progress", "percent": 100})

    ctx.memory_save(
        f"Host scan {host}: {open_count} open ports",
        metadata={"host": host, "hostname": hostname, "open_ports": open_count},
    )
    # finish_execution_tracking called automatically by @enhanced_tool wrapper


# ============================================================================
# REGISTRATION
# ============================================================================

def add_network_monitor_tools(tool_list: list, agent) -> None:
    """
    Register all three network tools into the agent's tool list and registry.

    Call from tools.py or any add_*_tools function:

        from Vera.Toolchain.Tools.Network.network_monitor import add_network_monitor_tools
        add_network_monitor_tools(tool_list, agent)
    """
    register_enhanced_tools(
        tool_list,
        agent,
        [network_monitor],
    )
    log.info(
        "[NetworkMonitor] Registered: network_monitor, network_scan, host_scan"
    )


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _host_node_id(ip: str) -> str:
    return f"host_{ip.replace('.', '_')}"


def _log_event(ctx: ToolContext, text: str, severity: str = "info") -> None:
    """Push a formatted event line to the monitor UI event log."""
    ctx.ui_push({
        "type":     "event",
        "text":     f"[{_ts()}]  {text}",
        "severity": severity,
    })