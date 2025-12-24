#!/usr/bin/env python3
"""
Vera Terminal UI - Professional monitoring interface for Vera AI System
Built with Textual for rich, interactive terminal experience
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import deque
import threading
import queue

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, Log, Input, Button, 
    DataTable, ProgressBar, Label, Tabs, Tab,
    TabbedContent, TabPane, RichLog
)
from textual.binding import Binding
from textual.reactive import reactive
from textual import events
from textual.message import Message
from rich.text import Text
from rich.panel import Panel
from rich.table import Table as RichTable
from rich.syntax import Syntax
from rich.console import Console
from rich.layout import Layout
import psutil


class SystemStatsWidget(Static):
    """Display real-time system statistics"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.update_interval = 1.0
        
    def on_mount(self) -> None:
        """Start update timer when mounted"""
        self.set_interval(self.update_interval, self.update_stats)
    
    def update_stats(self) -> None:
        """Update system statistics"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Create rich table for stats
        table = RichTable.grid(padding=(0, 2))
        table.add_column(style="cyan bold", justify="left")
        table.add_column(style="white")
        
        table.add_row("CPU Usage:", f"{cpu_percent}%")
        table.add_row("Memory:", f"{memory.percent}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)")
        table.add_row("Disk:", f"{disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)")
        
        if self.vera and hasattr(self.vera, 'sess'):
            table.add_row("Session:", str(self.vera.sess.id)[:12] + "...")
        
        if self.vera and hasattr(self.vera, 'enable_infrastructure') and self.vera.enable_infrastructure:
            table.add_row("Infrastructure:", "✓ Enabled")
        
        if self.vera and hasattr(self.vera, 'orchestrator') and self.vera.orchestrator.running:
            table.add_row("Orchestrator:", "✓ Running")
            if hasattr(self.vera.orchestrator, 'worker_pool'):
                active_workers = len([w for w in self.vera.orchestrator.worker_pool.values() if w.is_alive()])
                table.add_row("Active Workers:", str(active_workers))
        
        self.update(Panel(table, title="[bold cyan]System Status", border_style="cyan"))


class AgentStatusWidget(Static):
    """Display active agents and their status"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        
    def on_mount(self) -> None:
        """Start update timer when mounted"""
        self.set_interval(2.0, self.update_agents)
    
    def update_agents(self) -> None:
        """Update agent status display"""
        table = RichTable.grid(padding=(0, 1))
        table.add_column(style="green bold", justify="left", width=20)
        table.add_column(style="white", justify="left")
        
        if self.vera:
            # List configured models
            if hasattr(self.vera, 'selected_models'):
                models = self.vera.selected_models
                table.add_row("Fast LLM:", models.fast_llm)
                table.add_row("Deep LLM:", models.deep_llm)
                table.add_row("Reasoning:", models.reasoning_llm)
                table.add_row("Tool LLM:", models.tool_llm)
            
            # Show active focus if available
            if hasattr(self.vera, 'focus_manager') and self.vera.focus_manager:
                if self.vera.focus_manager.focus:
                    table.add_row("Current Focus:", self.vera.focus_manager.focus[:30] + "...")
            
            # Show agent system status
            if hasattr(self.vera, 'agents') and self.vera.agents:
                num_agents = len(self.vera.agents.loaded_agents)
                table.add_row("Loaded Agents:", f"{num_agents} agents")
        
        self.update(Panel(table, title="[bold green]Agent Configuration", border_style="green"))


class MemoryStatsWidget(Static):
    """Display memory system statistics"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        
    def on_mount(self) -> None:
        """Start update timer when mounted"""
        self.set_interval(3.0, self.update_memory)
    
    def update_memory(self) -> None:
        """Update memory statistics"""
        table = RichTable.grid(padding=(0, 1))
        table.add_column(style="magenta bold", justify="left", width=20)
        table.add_column(style="white", justify="left")
        
        if self.vera and hasattr(self.vera, 'mem'):
            # Vector store stats
            if hasattr(self.vera, 'vectorstore'):
                try:
                    collection = self.vera.vectorstore._collection
                    doc_count = collection.count() if hasattr(collection, 'count') else "N/A"
                    table.add_row("Vector Docs:", str(doc_count))
                except:
                    table.add_row("Vector Store:", "Active")
            
            # Buffer memory
            if hasattr(self.vera, 'buffer_memory'):
                try:
                    chat_history = self.vera.buffer_memory.chat_memory.messages
                    table.add_row("Chat History:", f"{len(chat_history)} messages")
                except:
                    table.add_row("Buffer Memory:", "Active")
            
            # Session info
            if hasattr(self.vera, 'sess'):
                table.add_row("Session ID:", str(self.vera.sess.id)[:16])
        
        self.update(Panel(table, title="[bold magenta]Memory Systems", border_style="magenta"))


class LogViewer(RichLog):
    """Custom log viewer with filtering and search"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_lines = 1000
        self.log_buffer = deque(maxlen=self.max_lines)
        
    def write_log(self, message: str, level: str = "INFO", source: str = "vera"):
        """Write a log message with formatting"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Color coding based on level
        level_colors = {
            "DEBUG": "dim white",
            "INFO": "cyan",
            "SUCCESS": "green",
            "WARNING": "yellow",
            "ERROR": "red bold",
            "CRITICAL": "red bold reverse"
        }
        
        color = level_colors.get(level, "white")
        
        # Format the log line
        log_line = Text()
        log_line.append(f"[{timestamp}] ", style="dim")
        log_line.append(f"{level:8} ", style=color)
        log_line.append(f"[{source}] ", style="blue")
        log_line.append(message)
        
        self.write(log_line)
        self.log_buffer.append(str(log_line))


class ThoughtViewer(VerticalScroll):
    """Display captured reasoning thoughts in real-time"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.thoughts = []
        
    def on_mount(self) -> None:
        """Start monitoring thoughts"""
        self.set_interval(0.5, self.update_thoughts)
    
    def update_thoughts(self) -> None:
        """Check for new thoughts and display them"""
        if self.vera and hasattr(self.vera, 'thoughts_captured'):
            new_thoughts = self.vera.thoughts_captured[-10:]  # Last 10 thoughts
            
            if new_thoughts != self.thoughts:
                self.thoughts = new_thoughts
                
                # Clear and rebuild display
                self.remove_children()
                
                for thought_data in self.thoughts:
                    timestamp = datetime.fromtimestamp(thought_data['timestamp']).strftime("%H:%M:%S")
                    thought = thought_data['thought']
                    
                    thought_panel = Panel(
                        thought,
                        title=f"[dim]{timestamp}[/dim]",
                        border_style="yellow",
                        padding=(0, 1)
                    )
                    self.mount(Static(thought_panel))


class QueryInput(Input):
    """Custom input widget for queries"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Enter your query... (Ctrl+S to submit, Ctrl+C to clear)"


class VeraTUI(App):
    """Vera Terminal UI Application"""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        height: 100%;
    }
    
    #stats-container {
        width: 35;
        height: 100%;
        background: $panel;
        border: solid $primary;
    }
    
    #content-container {
        width: 1fr;
        height: 100%;
    }
    
    #log-container {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }
    
    #thought-container {
        height: 15;
        border: solid yellow;
        margin: 1;
    }
    
    #input-container {
        height: auto;
        background: $panel;
        padding: 1;
    }
    
    QueryInput {
        width: 100%;
    }
    
    Button {
        margin: 0 1;
    }
    
    .stat-widget {
        height: auto;
        margin: 1;
    }
    
    #tabs-container {
        height: 100%;
    }
    
    RichLog {
        background: $surface;
        color: $text;
        height: 100%;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+s", "submit_query", "Submit", show=True),
        Binding("ctrl+c", "clear_input", "Clear", show=True),
        Binding("ctrl+l", "clear_logs", "Clear Logs", show=False),
        Binding("ctrl+r", "reload_config", "Reload Config", show=False),
        Binding("f1", "show_help", "Help", show=True),
    ]
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.log_viewer = None
        self.query_input = None
        self.processing = False
        
        # Message queue for async updates
        self.message_queue = queue.Queue()
        
        # Start background thread to capture Vera logs
        if self.vera:
            self._start_log_capture()
    
    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header(show_clock=True)
        
        with Horizontal(id="main-container"):
            # Left sidebar - Stats
            with Vertical(id="stats-container"):
                yield SystemStatsWidget(self.vera, classes="stat-widget")
                yield AgentStatusWidget(self.vera, classes="stat-widget")
                yield MemoryStatsWidget(self.vera, classes="stat-widget")
            
            # Main content area
            with Vertical(id="content-container"):
                # Tabbed content area
                with TabbedContent(id="tabs-container"):
                    with TabPane("Logs", id="logs-tab"):
                        self.log_viewer = LogViewer(
                            id="log-container",
                            highlight=True,
                            markup=True
                        )
                        yield self.log_viewer
                    
                    with TabPane("Thoughts", id="thoughts-tab"):
                        yield ThoughtViewer(self.vera, id="thought-container")
                    
                    with TabPane("System Info", id="info-tab"):
                        yield Static(self._get_system_info(), id="system-info")
                
                # Input area at bottom
                with Container(id="input-container"):
                    with Horizontal():
                        self.query_input = QueryInput(id="query-input")
                        yield self.query_input
                        yield Button("Submit", id="submit-btn", variant="primary")
                        yield Button("Clear", id="clear-btn", variant="warning")
        
        yield Footer()
    
    def _get_system_info(self) -> str:
        """Generate system information panel"""
        if not self.vera:
            return "Vera instance not initialized"
        
        info_table = RichTable(title="Vera System Information", show_header=True)
        info_table.add_column("Component", style="cyan bold")
        info_table.add_column("Value", style="white")
        
        # Configuration
        if hasattr(self.vera, 'config'):
            config = self.vera.config
            info_table.add_row("Config File", str(config.config_file) if hasattr(config, 'config_file') else "N/A")
            
            if hasattr(config, 'memory'):
                info_table.add_row("Neo4j URI", config.memory.neo4j_uri)
                info_table.add_row("Chroma Path", config.memory.chroma_path)
            
            if hasattr(config, 'ollama'):
                info_table.add_row("Ollama URL", config.ollama.api_url)
        
        # Models
        if hasattr(self.vera, 'selected_models'):
            models = self.vera.selected_models
            info_table.add_row("", "")  # Spacer
            info_table.add_row("Fast Model", models.fast_llm)
            info_table.add_row("Deep Model", models.deep_llm)
            info_table.add_row("Reasoning Model", models.reasoning_llm)
            info_table.add_row("Tool Model", models.tool_llm)
        
        # Infrastructure
        if hasattr(self.vera, 'enable_infrastructure'):
            info_table.add_row("", "")  # Spacer
            info_table.add_row("Infrastructure", "Enabled" if self.vera.enable_infrastructure else "Disabled")
            
            if self.vera.enable_infrastructure and hasattr(self.vera.config, 'infrastructure'):
                infra = self.vera.config.infrastructure
                info_table.add_row("Docker", "Enabled" if infra.enable_docker else "Disabled")
                info_table.add_row("Proxmox", "Enabled" if infra.enable_proxmox else "Disabled")
                info_table.add_row("Auto-Scale", "Enabled" if infra.auto_scale else "Disabled")
        
        return info_table
    
    def _start_log_capture(self):
        """Start capturing logs from Vera's logger"""
        # Hook into Vera's logging system
        if hasattr(self.vera, 'logger'):
            # Store original handlers
            original_handlers = []
            
            # Add custom handler to send logs to TUI
            class TUILogHandler:
                def __init__(self, tui_app):
                    self.tui_app = tui_app
                
                def emit(self, record):
                    """Called when a log record is emitted"""
                    try:
                        self.tui_app.message_queue.put({
                            'type': 'log',
                            'level': record.levelname,
                            'message': record.getMessage(),
                            'source': getattr(record, 'agent', 'vera')
                        })
                    except Exception:
                        pass
            
            # Note: This is simplified - you'd need to integrate with Vera's actual logging system
            # For now, we'll poll the message queue
            self.set_interval(0.1, self._process_message_queue)
    
    def _process_message_queue(self):
        """Process messages from the queue"""
        try:
            while not self.message_queue.empty():
                msg = self.message_queue.get_nowait()
                
                if msg['type'] == 'log' and self.log_viewer:
                    self.log_viewer.write_log(
                        msg['message'],
                        level=msg.get('level', 'INFO'),
                        source=msg.get('source', 'vera')
                    )
        except queue.Empty:
            pass
        except Exception as e:
            pass  # Silently handle errors in message processing
    
    def on_mount(self) -> None:
        """Called when app is mounted"""
        if self.log_viewer:
            self.log_viewer.write_log("Vera TUI initialized", level="SUCCESS", source="tui")
            self.log_viewer.write_log("Ready for queries", level="INFO", source="tui")
        
        if self.query_input:
            self.query_input.focus()
    
    def action_submit_query(self) -> None:
        """Submit the current query"""
        if self.processing:
            if self.log_viewer:
                self.log_viewer.write_log("Already processing a query, please wait...", level="WARNING")
            return
        
        if not self.query_input:
            return
        
        query = self.query_input.value.strip()
        if not query:
            return
        
        # Clear input
        self.query_input.value = ""
        
        # Log query
        if self.log_viewer:
            self.log_viewer.write_log(f"Query: {query}", level="INFO", source="user")
        
        # Process query in background
        self.processing = True
        self.run_worker(self._process_query(query), exclusive=True)
    
    async def _process_query(self, query: str):
        """Process a query asynchronously"""
        try:
            if not self.vera:
                if self.log_viewer:
                    self.log_viewer.write_log("Vera instance not available", level="ERROR")
                return
            
            # Run query in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def run_query():
                result = []
                try:
                    for chunk in self.vera.async_run(query):
                        result.append(str(chunk))
                        # Send chunk to log viewer
                        self.message_queue.put({
                            'type': 'log',
                            'level': 'INFO',
                            'message': str(chunk),
                            'source': 'response'
                        })
                except Exception as e:
                    self.message_queue.put({
                        'type': 'log',
                        'level': 'ERROR',
                        'message': f"Query failed: {e}",
                        'source': 'error'
                    })
                return ''.join(result)
            
            await loop.run_in_executor(None, run_query)
            
            if self.log_viewer:
                self.log_viewer.write_log("Query complete", level="SUCCESS", source="vera")
        
        except Exception as e:
            if self.log_viewer:
                self.log_viewer.write_log(f"Error: {e}", level="ERROR", source="error")
        
        finally:
            self.processing = False
    
    def action_clear_input(self) -> None:
        """Clear the input field"""
        if self.query_input:
            self.query_input.value = ""
            self.query_input.focus()
    
    def action_clear_logs(self) -> None:
        """Clear the log viewer"""
        if self.log_viewer:
            self.log_viewer.clear()
            self.log_viewer.write_log("Logs cleared", level="INFO", source="tui")
    
    def action_reload_config(self) -> None:
        """Reload Vera configuration"""
        if self.vera and hasattr(self.vera, 'reload_config'):
            if self.log_viewer:
                self.log_viewer.write_log("Reloading configuration...", level="INFO", source="config")
            
            try:
                self.vera.reload_config()
                if self.log_viewer:
                    self.log_viewer.write_log("Configuration reloaded successfully", level="SUCCESS", source="config")
            except Exception as e:
                if self.log_viewer:
                    self.log_viewer.write_log(f"Config reload failed: {e}", level="ERROR", source="config")
    
    def action_show_help(self) -> None:
        """Show help message"""
        help_text = """
[bold cyan]Vera TUI Help[/bold cyan]

[bold]Keyboard Shortcuts:[/bold]
  Ctrl+S     - Submit query
  Ctrl+C     - Clear input
  Ctrl+L     - Clear logs
  Ctrl+R     - Reload configuration
  Ctrl+Q     - Quit application
  F1         - Show this help

[bold]Special Commands:[/bold]
  /stats     - Show performance statistics
  /infra     - Show infrastructure status
  /agents    - List available agents
  /clear     - Clear memory
  /exit      - Quit application

[bold]Tabs:[/bold]
  Logs       - View system logs and responses
  Thoughts   - View reasoning thoughts (if enabled)
  System Info - View configuration and status
"""
        if self.log_viewer:
            self.log_viewer.write(Panel(help_text, title="Help", border_style="cyan"))
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "submit-btn":
            self.action_submit_query()
        elif event.button.id == "clear-btn":
            self.action_clear_input()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        if event.input.id == "query-input":
            self.action_submit_query()


def run_tui(vera_instance=None, config_file: str = None):
    """
    Run the Vera TUI
    
    Args:
        vera_instance: Existing Vera instance (optional)
        config_file: Path to Vera config file (if creating new instance)
    """
    import asyncio
    
    # Initialize Vera if not provided
    if vera_instance is None:
        print("Initializing Vera...")
        try:
            from Vera.py import Vera  # Import from your actual module
            vera_instance = Vera(config_file=config_file or "Configuration/vera_config.yaml")
        except Exception as e:
            print(f"Failed to initialize Vera: {e}")
            print("Starting TUI without Vera instance...")
            vera_instance = None
    
    # Run the TUI - handle existing event loop
    app = VeraTUI(vera_instance=vera_instance)
    
    try:
        # Check if there's already a running event loop
        loop = asyncio.get_running_loop()
        # If we get here, there's already a loop running
        print("Detected running event loop, using run_async()...")
        import nest_asyncio
        nest_asyncio.apply()
        app.run()
    except RuntimeError:
        # No running loop, safe to use app.run()
        app.run()
    except ImportError:
        # nest_asyncio not available, try alternative method
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(app.run_async())
        except Exception as e:
            print(f"Failed to run TUI: {e}")
            print("\nTry installing nest_asyncio: pip install nest-asyncio")


if __name__ == "__main__":
    import sys
    
    config_file = sys.argv[1] if len(sys.argv) > 1 else None
    run_tui(config_file=config_file)