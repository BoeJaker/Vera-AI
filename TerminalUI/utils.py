#!/usr/bin/env python3
"""
Vera TUI Utilities
Additional widgets and helper functions for the Vera Terminal UI
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque
import threading

from textual.widgets import Static, ProgressBar, DataTable
from textual.containers import Container, Vertical, Horizontal
from rich.table import Table as RichTable
from rich.panel import Panel
from rich.bar import Bar
from rich.text import Text
import psutil


class TaskMonitor(Static):
    """Monitor active tasks in the orchestrator"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.tasks = {}
    
    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_tasks)
    
    def update_tasks(self) -> None:
        """Update task status display"""
        if not self.vera or not hasattr(self.vera, 'orchestrator'):
            self.update("No orchestrator available")
            return
        
        table = RichTable(show_header=True, header_style="bold cyan")
        table.add_column("Task ID", style="cyan", width=12)
        table.add_column("Type", style="green", width=15)
        table.add_column("Status", style="yellow", width=12)
        table.add_column("Duration", style="white", width=10)
        
        # Get active tasks from orchestrator
        if hasattr(self.vera.orchestrator, 'active_tasks'):
            for task_id, task_info in list(self.vera.orchestrator.active_tasks.items())[:10]:
                task_type = task_info.get('type', 'Unknown')
                status = task_info.get('status', 'Running')
                start_time = task_info.get('start_time', 0)
                duration = f"{time.time() - start_time:.1f}s" if start_time else "N/A"
                
                table.add_row(
                    task_id[:12],
                    task_type,
                    status,
                    duration
                )
        
        if table.row_count == 0:
            table.add_row("—", "No active tasks", "—", "—")
        
        self.update(Panel(table, title="[bold]Active Tasks", border_style="cyan"))


class ResourceGraph(Static):
    """Simple ASCII graph for resource usage over time"""
    
    def __init__(self, resource_name: str = "CPU", max_points: int = 50):
        super().__init__()
        self.resource_name = resource_name
        self.max_points = max_points
        self.data_points = deque(maxlen=max_points)
        self.lock = threading.Lock()
    
    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_graph)
    
    def add_data_point(self, value: float):
        """Add a new data point"""
        with self.lock:
            self.data_points.append(value)
    
    def update_graph(self) -> None:
        """Update the graph display"""
        # Get current resource value
        if self.resource_name == "CPU":
            value = psutil.cpu_percent(interval=0.1)
        elif self.resource_name == "Memory":
            value = psutil.virtual_memory().percent
        elif self.resource_name == "Disk":
            value = psutil.disk_usage('/').percent
        else:
            value = 0
        
        self.add_data_point(value)
        
        # Generate ASCII graph
        graph = self._generate_graph()
        
        self.update(Panel(
            graph,
            title=f"[bold]{self.resource_name} Usage",
            border_style="green"
        ))
    
    def _generate_graph(self) -> str:
        """Generate simple ASCII graph"""
        if not self.data_points:
            return "No data yet..."
        
        height = 10
        width = len(self.data_points)
        
        # Normalize data to graph height
        max_val = max(self.data_points) if self.data_points else 100
        normalized = [int((val / 100) * height) for val in self.data_points]
        
        # Build graph
        lines = []
        for row in range(height, 0, -1):
            line = ""
            for col in range(width):
                if col < len(normalized) and normalized[col] >= row:
                    line += "█"
                else:
                    line += " "
            
            # Add scale
            scale_val = int((row / height) * 100)
            lines.append(f"{scale_val:3d}%│{line}│")
        
        # Add bottom axis
        lines.append("   └" + "─" * width + "┘")
        lines.append(f"   Current: {self.data_points[-1]:.1f}% | Avg: {sum(self.data_points)/len(self.data_points):.1f}%")
        
        return "\n".join(lines)


class ModelPerformanceTable(Static):
    """Table showing performance metrics for each model"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.metrics = {}
    
    def on_mount(self) -> None:
        self.set_interval(2.0, self.update_table)
    
    def update_table(self) -> None:
        """Update performance metrics table"""
        table = RichTable(show_header=True, header_style="bold magenta")
        table.add_column("Model", style="cyan", width=20)
        table.add_column("Calls", justify="right", width=8)
        table.add_column("Avg Time", justify="right", width=10)
        table.add_column("Tokens/s", justify="right", width=10)
        table.add_column("Errors", justify="right", width=8)
        
        if self.vera and hasattr(self.vera, 'logger'):
            # Try to get metrics from logger
            if hasattr(self.vera.logger, 'get_model_stats'):
                stats = self.vera.logger.get_model_stats()
                
                for model_name, model_stats in stats.items():
                    table.add_row(
                        model_name[:20],
                        str(model_stats.get('calls', 0)),
                        f"{model_stats.get('avg_time', 0):.2f}s",
                        f"{model_stats.get('tokens_per_sec', 0):.0f}",
                        str(model_stats.get('errors', 0))
                    )
        
        if table.row_count == 0:
            table.add_row("No data", "—", "—", "—", "—")
        
        self.update(Panel(table, title="[bold]Model Performance", border_style="magenta"))


class InfrastructureStatus(Static):
    """Show infrastructure status (Docker, Proxmox)"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
    
    def on_mount(self) -> None:
        self.set_interval(3.0, self.update_status)
    
    def update_status(self) -> None:
        """Update infrastructure status"""
        if not self.vera or not self.vera.enable_infrastructure:
            self.update(Panel(
                "[dim]Infrastructure orchestration disabled[/dim]",
                title="Infrastructure",
                border_style="dim"
            ))
            return
        
        table = RichTable.grid(padding=(0, 2))
        table.add_column(style="cyan bold", width=20)
        table.add_column(style="white")
        
        # Get infrastructure stats
        try:
            stats = self.vera.get_infrastructure_stats()
            
            # Docker stats
            if stats.get('docker_enabled'):
                table.add_row("[bold]Docker[/bold]", "")
                table.add_row("  Containers:", str(stats.get('docker_containers', 0)))
                table.add_row("  Running:", str(stats.get('docker_running', 0)))
                table.add_row("  CPU Usage:", f"{stats.get('docker_cpu', 0):.1f}%")
            
            # Proxmox stats
            if stats.get('proxmox_enabled'):
                table.add_row("", "")
                table.add_row("[bold]Proxmox[/bold]", "")
                table.add_row("  VMs:", str(stats.get('proxmox_vms', 0)))
                table.add_row("  Active:", str(stats.get('proxmox_active', 0)))
                table.add_row("  Node:", stats.get('proxmox_node', 'N/A'))
            
            # Resource pools
            if stats.get('resource_pools'):
                table.add_row("", "")
                table.add_row("[bold]Resource Pools[/bold]", "")
                for pool_name, pool_stats in stats['resource_pools'].items():
                    table.add_row(f"  {pool_name}:", str(pool_stats.get('size', 0)))
        
        except Exception as e:
            table.add_row("Error:", str(e)[:30])
        
        self.update(Panel(table, title="[bold]Infrastructure", border_style="blue"))


class MemoryUsageGraph(Static):
    """Graph showing memory usage breakdown"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
    
    def on_mount(self) -> None:
        self.set_interval(2.0, self.update_graph)
    
    def update_graph(self) -> None:
        """Update memory usage visualization"""
        if not self.vera:
            self.update("Vera not available")
            return
        
        # Get memory info
        lines = []
        
        # Vector store
        try:
            if hasattr(self.vera, 'vectorstore'):
                collection = self.vera.vectorstore._collection
                doc_count = collection.count() if hasattr(collection, 'count') else 0
                lines.append(f"Vector Store: {doc_count} documents")
                
                # Simple bar
                max_docs = 10000
                bar_width = min(40, int((doc_count / max_docs) * 40))
                bar = "█" * bar_width + "░" * (40 - bar_width)
                lines.append(f"  [{bar}] {(doc_count/max_docs)*100:.1f}%")
        except:
            lines.append("Vector Store: N/A")
        
        lines.append("")
        
        # Buffer memory
        try:
            if hasattr(self.vera, 'buffer_memory'):
                messages = len(self.vera.buffer_memory.chat_memory.messages)
                lines.append(f"Buffer: {messages} messages")
                
                max_msgs = 100
                bar_width = min(40, int((messages / max_msgs) * 40))
                bar = "█" * bar_width + "░" * (40 - bar_width)
                lines.append(f"  [{bar}] {(messages/max_msgs)*100:.1f}%")
        except:
            lines.append("Buffer: N/A")
        
        lines.append("")
        
        # Neo4j (if available)
        try:
            if hasattr(self.vera, 'mem'):
                # Get node count from Neo4j
                lines.append("Neo4j Graph: Connected")
        except:
            lines.append("Neo4j Graph: N/A")
        
        content = "\n".join(lines)
        self.update(Panel(content, title="[bold]Memory Usage", border_style="yellow"))


class QuickActionsPanel(Static):
    """Panel with quick action buttons/shortcuts"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
    
    def compose(self) -> ComposeResult:
        """Compose the quick actions panel"""
        yield Static("[bold]Quick Actions[/bold]\n")
        yield Static("F1  - Help")
        yield Static("F2  - Toggle Debug")
        yield Static("F3  - Clear Logs")
        yield Static("F4  - System Info")
        yield Static("F5  - Reload Config")
        yield Static("\n[bold]Commands[/bold]\n")
        yield Static("/stats  - Performance")
        yield Static("/infra  - Infrastructure")
        yield Static("/agents - List Agents")
        yield Static("/clear  - Clear Memory")


class SessionInfo(Static):
    """Display current session information"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.session_start = datetime.now()
    
    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_info)
    
    def update_info(self) -> None:
        """Update session information"""
        table = RichTable.grid(padding=(0, 1))
        table.add_column(style="blue bold", width=15)
        table.add_column(style="white")
        
        # Session duration
        duration = datetime.now() - self.session_start
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        seconds = int(duration.total_seconds() % 60)
        
        table.add_row("Uptime:", f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        if self.vera and hasattr(self.vera, 'sess'):
            table.add_row("Session ID:", str(self.vera.sess.id)[:16] + "...")
            
            if hasattr(self.vera.sess, 'metadata'):
                for key, value in self.vera.sess.metadata.items():
                    table.add_row(f"  {key}:", str(value)[:30])
        
        # Vera version/build info
        table.add_row("", "")
        table.add_row("Version:", "Vera AI v0.9")
        table.add_row("Build:", datetime.now().strftime("%Y-%m-%d"))
        
        self.update(Panel(table, title="[bold]Session Info", border_style="blue"))


# ============================================================================
# Helper Functions
# ============================================================================

def format_bytes(bytes_value: int) -> str:
    """Format bytes to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f}PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def get_system_info() -> Dict[str, Any]:
    """Get comprehensive system information"""
    import platform
    
    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': psutil.cpu_count(),
        'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
        'total_memory': psutil.virtual_memory().total,
        'python_version': platform.python_version(),
    }


def create_status_indicator(status: str, active: bool = True) -> Text:
    """Create a colored status indicator"""
    if active:
        return Text("● ", style="green bold") + Text(status)
    else:
        return Text("○ ", style="dim") + Text(status, style="dim")


# ============================================================================
# Export all widgets
# ============================================================================

__all__ = [
    'TaskMonitor',
    'ResourceGraph',
    'ModelPerformanceTable',
    'InfrastructureStatus',
    'MemoryUsageGraph',
    'QuickActionsPanel',
    'SessionInfo',
    'format_bytes',
    'format_duration',
    'get_system_info',
    'create_status_indicator',
]