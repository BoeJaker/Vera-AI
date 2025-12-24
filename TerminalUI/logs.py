#!/usr/bin/env python3
"""
Vera TUI Enhanced - Direct integration with Vera's unified logging system
Captures logs in real-time from Vera's logger
"""

import logging
import queue
import threading
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Input, Button, TabbedContent, TabPane
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel
from rich.table import Table as RichTable
import psutil


class VeraLogHandler(logging.Handler):
    """Custom logging handler that sends logs to the TUI"""
    
    def __init__(self, message_queue: queue.Queue):
        super().__init__()
        self.message_queue = message_queue
        self.setLevel(logging.DEBUG)
    
    def emit(self, record):
        """Called when a log record is emitted"""
        try:
            # Extract context from record
            context = {
                'timestamp': datetime.fromtimestamp(record.created),
                'level': record.levelname,
                'message': self.format(record),
                'source': getattr(record, 'agent', 'vera'),
                'session_id': getattr(record, 'session_id', None),
                'model': getattr(record, 'model', None),
                'task_id': getattr(record, 'task_id', None),
            }
            
            self.message_queue.put({
                'type': 'log',
                **context
            })
        except Exception:
            # Don't let logging errors break the app
            pass


class EnhancedSystemStats(Static):
    """Enhanced system statistics with more detail"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        
    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_stats)
    
    def update_stats(self) -> None:
        """Update comprehensive system statistics"""
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=False)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Network I/O
        net_io = psutil.net_io_counters()
        
        # Create table
        table = RichTable.grid(padding=(0, 2))
        table.add_column(style="cyan bold", width=18)
        table.add_column(style="white")
        
        # CPU Section
        table.add_row("[bold]CPU[/bold]", "")
        table.add_row("  Overall:", f"{cpu_percent:.1f}%")
        table.add_row("  Cores:", f"{len(cpu_per_core)} ({max(cpu_per_core):.1f}% max)")
        
        # Memory Section
        table.add_row("", "")
        table.add_row("[bold]Memory[/bold]", "")
        table.add_row("  Used:", f"{memory.percent:.1f}% ({memory.used // (1024**3)}GB)")
        table.add_row("  Available:", f"{memory.available // (1024**3)}GB")
        
        # Disk Section
        table.add_row("", "")
        table.add_row("[bold]Disk[/bold]", "")
        table.add_row("  Used:", f"{disk.percent:.1f}% ({disk.used // (1024**3)}GB)")
        table.add_row("  Free:", f"{disk.free // (1024**3)}GB")
        
        # Network Section
        table.add_row("", "")
        table.add_row("[bold]Network[/bold]", "")
        table.add_row("  Sent:", f"{net_io.bytes_sent // (1024**2)}MB")
        table.add_row("  Received:", f"{net_io.bytes_recv // (1024**2)}MB")
        
        # Vera-specific stats
        if self.vera:
            table.add_row("", "")
            table.add_row("[bold]Vera Status[/bold]", "")
            
            if hasattr(self.vera, 'sess'):
                sess_id = str(self.vera.sess.id)[:8]
                table.add_row("  Session:", f"{sess_id}...")
            
            if hasattr(self.vera, 'orchestrator') and self.vera.orchestrator.running:
                table.add_row("  Orchestrator:", "🟢 Running")
                
                # Worker stats
                if hasattr(self.vera.orchestrator, 'worker_pool'):
                    workers = self.vera.orchestrator.worker_pool
                    active = len([w for w in workers.values() if w.is_alive()])
                    total = len(workers)
                    table.add_row("  Workers:", f"{active}/{total} active")
            
            if hasattr(self.vera, 'focus_manager') and self.vera.focus_manager:
                if self.vera.focus_manager.focus:
                    focus = self.vera.focus_manager.focus[:25]
                    table.add_row("  Focus:", f"{focus}...")
        
        self.update(Panel(table, title="[bold cyan]System Status", border_style="cyan"))


class EnhancedLogViewer(RichLog):
    """Enhanced log viewer with filtering and better formatting"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_lines = 2000
        self.filter_level = "DEBUG"  # Show all by default
    
    def write_log(self, log_data: dict):
        """Write a formatted log entry"""
        timestamp = log_data['timestamp'].strftime("%H:%M:%S.%f")[:-3]
        level = log_data['level']
        message = log_data['message']
        source = log_data['source']
        
        # Color coding
        level_styles = {
            "DEBUG": "dim white",
            "INFO": "cyan",
            "SUCCESS": "green bold",
            "WARNING": "yellow",
            "ERROR": "red bold",
            "CRITICAL": "red bold reverse",
            "THOUGHT": "yellow italic",
            "RESPONSE": "green",
            "TOOL": "magenta",
            "MEMORY": "blue",
        }
        
        style = level_styles.get(level, "white")
        
        # Build log line
        log_line = Text()
        log_line.append(f"[{timestamp}] ", style="dim")
        log_line.append(f"{level:10} ", style=style)
        log_line.append(f"[{source:12}] ", style="blue")
        
        # Add context if available
        if log_data.get('model'):
            log_line.append(f"<{log_data['model'][:15]}> ", style="dim magenta")
        
        log_line.append(message)
        
        self.write(log_line)
    
    def set_filter_level(self, level: str):
        """Set minimum log level to display"""
        self.filter_level = level


class PerformanceMonitor(Static):
    """Monitor Vera's performance metrics"""
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.metrics = {
            'queries_processed': 0,
            'avg_response_time': 0,
            'total_tokens': 0,
            'cache_hits': 0,
        }
    
    def on_mount(self) -> None:
        self.set_interval(2.0, self.update_metrics)
    
    def update_metrics(self) -> None:
        """Update performance metrics"""
        table = RichTable.grid(padding=(0, 2))
        table.add_column(style="green bold", width=20)
        table.add_column(style="white")
        
        table.add_row("[bold]Performance[/bold]", "")
        table.add_row("  Queries:", str(self.metrics['queries_processed']))
        table.add_row("  Avg Time:", f"{self.metrics['avg_response_time']:.2f}s")
        table.add_row("  Tokens:", str(self.metrics['total_tokens']))
        
        if self.vera and hasattr(self.vera, 'logger'):
            # Try to get stats from logger if available
            if hasattr(self.vera.logger, 'get_stats'):
                stats = self.vera.logger.get_stats()
                
                if 'timers' in stats:
                    table.add_row("", "")
                    table.add_row("[bold]Timers[/bold]", "")
                    for timer_name, timer_data in list(stats['timers'].items())[:5]:
                        avg = timer_data.get('avg', 0)
                        table.add_row(f"  {timer_name}:", f"{avg:.3f}s")
        
        self.update(Panel(table, title="[bold green]Performance", border_style="green"))


class EnhancedVeraTUI(App):
    """Enhanced Vera TUI with direct logging integration"""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        height: 100%;
    }
    
    #stats-sidebar {
        width: 40;
        height: 100%;
        border-right: solid $primary;
    }
    
    #content-area {
        width: 1fr;
        height: 100%;
    }
    
    #log-viewer {
        height: 1fr;
    }
    
    #input-area {
        height: auto;
        background: $panel;
        padding: 1;
        border-top: solid $accent;
    }
    
    .stat-panel {
        height: auto;
        margin: 1 1;
    }
    
    QueryInput {
        width: 100%;
    }
    
    RichLog {
        background: $surface;
        border: solid $accent;
        margin: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "submit_query", "Submit"),
        Binding("ctrl+c", "clear_input", "Clear"),
        Binding("ctrl+l", "clear_logs", "Clear Logs"),
        Binding("f1", "show_help", "Help"),
        Binding("f2", "toggle_debug", "Toggle Debug"),
    ]
    
    def __init__(self, vera_instance=None):
        super().__init__()
        self.vera = vera_instance
        self.message_queue = queue.Queue()
        self.processing = False
        
        # Integrate with Vera's logger
        if self.vera and hasattr(self.vera, 'logger'):
            self._integrate_logging()
    
    def _integrate_logging(self):
        """Integrate with Vera's unified logging system"""
        # Add our custom handler to Vera's logger
        handler = VeraLogHandler(self.message_queue)
        
        # Set formatter to match Vera's format
        formatter = logging.Formatter(
            '%(message)s'  # We'll handle formatting in the TUI
        )
        handler.setFormatter(formatter)
        
        # Add handler to Vera's logger
        # Note: This assumes Vera's logger is a standard Python logger
        # Adjust based on your actual logging implementation
        if hasattr(self.vera.logger, 'logger'):
            self.vera.logger.logger.addHandler(handler)
        elif hasattr(self.vera.logger, 'addHandler'):
            self.vera.logger.addHandler(handler)
    
    def compose(self) -> ComposeResult:
        """Compose the UI"""
        yield Header(show_clock=True, name="Vera AI System Monitor")
        
        with Horizontal(id="main-container"):
            # Left sidebar
            with Vertical(id="stats-sidebar"):
                yield EnhancedSystemStats(self.vera, classes="stat-panel")
                yield PerformanceMonitor(self.vera, classes="stat-panel")
            
            # Main content
            with Vertical(id="content-area"):
                with TabbedContent():
                    with TabPane("System Logs", id="logs-tab"):
                        self.log_viewer = EnhancedLogViewer(
                            id="log-viewer",
                            highlight=True,
                            markup=True,
                            wrap=True
                        )
                        yield self.log_viewer
                
                # Input area
                with Container(id="input-area"):
                    with Horizontal():
                        self.query_input = Input(
                            placeholder="Enter query... (Ctrl+S to submit)",
                            id="query-input"
                        )
                        yield self.query_input
                        yield Button("Submit", id="submit-btn", variant="primary")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize when mounted"""
        # Start message processing
        self.set_interval(0.05, self._process_messages)
        
        # Write welcome message
        if self.log_viewer:
            welcome = {
                'timestamp': datetime.now(),
                'level': 'SUCCESS',
                'message': 'Vera TUI initialized successfully',
                'source': 'tui'
            }
            self.log_viewer.write_log(welcome)
        
        # Focus input
        if self.query_input:
            self.query_input.focus()
    
    def _process_messages(self):
        """Process messages from the queue"""
        try:
            while not self.message_queue.empty():
                msg = self.message_queue.get_nowait()
                
                if msg['type'] == 'log' and self.log_viewer:
                    self.log_viewer.write_log(msg)
        
        except queue.Empty:
            pass
        except Exception:
            pass  # Silent error handling
    
    def action_submit_query(self) -> None:
        """Submit query for processing"""
        if self.processing or not self.query_input:
            return
        
        query = self.query_input.value.strip()
        if not query:
            return
        
        # Clear input
        self.query_input.value = ""
        
        # Log query
        self.message_queue.put({
            'type': 'log',
            'timestamp': datetime.now(),
            'level': 'INFO',
            'message': f"Query submitted: {query}",
            'source': 'user'
        })
        
        # Process in background
        self.processing = True
        self.run_worker(self._process_query(query))
    
    async def _process_query(self, query: str):
        """Process query asynchronously"""
        import asyncio
        
        try:
            if not self.vera:
                raise ValueError("Vera instance not available")
            
            loop = asyncio.get_event_loop()
            
            def run_sync():
                results = []
                for chunk in self.vera.async_run(query):
                    results.append(str(chunk))
                return ''.join(results)
            
            result = await loop.run_in_executor(None, run_sync)
            
            self.message_queue.put({
                'type': 'log',
                'timestamp': datetime.now(),
                'level': 'SUCCESS',
                'message': 'Query completed successfully',
                'source': 'vera'
            })
        
        except Exception as e:
            self.message_queue.put({
                'type': 'log',
                'timestamp': datetime.now(),
                'level': 'ERROR',
                'message': f'Query failed: {e}',
                'source': 'error'
            })
        
        finally:
            self.processing = False
    
    def action_clear_input(self) -> None:
        """Clear input field"""
        if self.query_input:
            self.query_input.value = ""
            self.query_input.focus()
    
    def action_clear_logs(self) -> None:
        """Clear log viewer"""
        if self.log_viewer:
            self.log_viewer.clear()
    
    def action_toggle_debug(self) -> None:
        """Toggle debug level filtering"""
        if self.log_viewer:
            current = getattr(self.log_viewer, 'filter_level', 'DEBUG')
            new_level = 'INFO' if current == 'DEBUG' else 'DEBUG'
            self.log_viewer.filter_level = new_level
            
            self.message_queue.put({
                'type': 'log',
                'timestamp': datetime.now(),
                'level': 'INFO',
                'message': f'Log level changed to: {new_level}',
                'source': 'tui'
            })
    
    def action_show_help(self) -> None:
        """Show help"""
        help_msg = {
            'timestamp': datetime.now(),
            'level': 'INFO',
            'message': 'F1=Help | F2=Toggle Debug | Ctrl+S=Submit | Ctrl+L=Clear Logs | Ctrl+Q=Quit',
            'source': 'help'
        }
        if self.log_viewer:
            self.log_viewer.write_log(help_msg)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press"""
        if event.button.id == "submit-btn":
            self.action_submit_query()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        self.action_submit_query()


def run_enhanced_tui(vera_instance=None):
    """Run the enhanced TUI with event loop handling"""
    import asyncio
    
    app = EnhancedVeraTUI(vera_instance=vera_instance)
    
    try:
        # Check if there's already a running event loop
        loop = asyncio.get_running_loop()
        # If we get here, there's already a loop running
        print("Detected running event loop, using nest_asyncio...")
        import nest_asyncio
        nest_asyncio.apply()
        app.run()
    except RuntimeError:
        # No running loop, safe to use app.run()
        app.run()
    except ImportError:
        # nest_asyncio not available, try alternative method
        print("nest_asyncio not found, trying alternative method...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(app.run_async())
        except Exception as e:
            print(f"Failed to run TUI: {e}")
            print("\nRecommended: pip install nest-asyncio")


if __name__ == "__main__":
    run_enhanced_tui()