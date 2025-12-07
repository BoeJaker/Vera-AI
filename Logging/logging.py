#!/usr/bin/env python3
# Vera/Utils/logging.py

"""
Vera Unified Logging System
Provides structured, configurable logging with rich formatting and metadata.
"""

import sys
import logging
import threading
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import traceback


class LogLevel(Enum):
    """Enhanced log levels for Vera"""
    TRACE = 5      # Most verbose - every detail
    DEBUG = 10     # Debug information
    INFO = 20      # General information
    SUCCESS = 25   # Success messages
    WARNING = 30   # Warnings
    ERROR = 40     # Errors
    CRITICAL = 50  # Critical errors
    SILENT = 100   # No output


class OutputType(Enum):
    """Types of output with special formatting"""
    SYSTEM = "system"           # System messages
    THOUGHT = "thought"         # Model reasoning
    RESPONSE = "response"       # Model responses
    TOOL = "tool"              # Tool execution
    MEMORY = "memory"          # Memory operations
    ORCHESTRATOR = "orchestrator"  # Task orchestration
    INFRASTRUCTURE = "infrastructure"  # Resource management
    NETWORK = "network"        # Network operations
    PERFORMANCE = "performance"  # Performance metrics
    USER = "user"              # User input/interaction


@dataclass
class LogContext:
    """Context information for log messages"""
    session_id: Optional[str] = None
    agent: Optional[str] = None
    model: Optional[str] = None
    task_id: Optional[str] = None
    thread_id: Optional[int] = None
    timestamp: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            'session_id': self.session_id,
            'agent': self.agent,
            'model': self.model,
            'task_id': self.task_id,
            'thread_id': self.thread_id,
            'timestamp': self.timestamp or time.time(),
        }
        data.update(self.extra)
        return {k: v for k, v in data.items() if v is not None}


class ColorCodes:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Standard colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


@dataclass
class LoggingConfig:
    """Configuration for Vera logging system"""
    # Verbosity levels per component
    global_level: LogLevel = LogLevel.INFO
    component_levels: Dict[str, LogLevel] = field(default_factory=dict)
    
    # Output options
    enable_colors: bool = True
    enable_timestamps: bool = True
    enable_thread_info: bool = False
    enable_session_info: bool = True
    enable_model_info: bool = True
    enable_performance_tracking: bool = True
    
    # Formatting
    timestamp_format: str = "%Y-%m-%d %H:%M:%S.%f"
    show_milliseconds: bool = True
    max_line_width: int = 100
    indent_size: int = 2
    
    # Special output formatting
    box_thoughts: bool = True
    box_responses: bool = False
    box_tools: bool = True
    show_raw_streams: bool = False
    
    # File logging
    log_to_file: bool = True
    log_file: str = "./logs/vera.log"
    log_file_level: LogLevel = LogLevel.DEBUG
    rotate_logs: bool = True
    max_log_size: int = 10485760  # 10MB
    backup_count: int = 5
    
    # JSON logging for analysis
    json_log_file: Optional[str] = "./logs/vera.jsonl"
    log_to_json: bool = False
    
    # Performance tracking
    track_llm_latency: bool = True
    track_tool_latency: bool = True
    track_memory_operations: bool = True
    
    # Component-specific
    show_ollama_raw_chunks: bool = False
    show_orchestrator_details: bool = True
    show_memory_triage: bool = False
    show_infrastructure_stats: bool = True
    
    # Console output control
    stream_thoughts_inline: bool = True
    buffer_responses: bool = False


class VeraLogger:
    """
    Unified logger for Vera with structured output and rich formatting
    """
    
    def __init__(self, config: LoggingConfig, component: str = "vera"):
        self.config = config
        self.component = component
        self.context_stack: List[LogContext] = []
        self.performance_timers: Dict[str, float] = {}
        self.lock = threading.RLock()
        
        # Setup Python logging
        self.logger = logging.getLogger(f"vera.{component}")
        self._setup_logging()
        
        # Statistics
        self.stats = {
            'messages_logged': 0,
            'errors_logged': 0,
            'thoughts_captured': 0,
            'tools_executed': 0,
        }
    
    def _setup_logging(self):
        """Setup Python logging handlers"""
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.config.global_level.value)
        console_handler.setFormatter(self._create_formatter())
        self.logger.addHandler(console_handler)
        
        # File handler
        if self.config.log_to_file:
            Path(self.config.log_file).parent.mkdir(parents=True, exist_ok=True)
            
            if self.config.rotate_logs:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    self.config.log_file,
                    maxBytes=self.config.max_log_size,
                    backupCount=self.config.backup_count
                )
            else:
                file_handler = logging.FileHandler(self.config.log_file)
            
            file_handler.setLevel(self.config.log_file_level.value)
            file_handler.setFormatter(self._create_formatter(colors=False))
            self.logger.addHandler(file_handler)
        
        # JSON handler
        if self.config.log_to_json and self.config.json_log_file:
            Path(self.config.json_log_file).parent.mkdir(parents=True, exist_ok=True)
            json_handler = logging.FileHandler(self.config.json_log_file)
            json_handler.setLevel(logging.DEBUG)
            json_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(json_handler)
    
    def _create_formatter(self, colors: bool = None) -> logging.Formatter:
        """Create log formatter"""
        if colors is None:
            colors = self.config.enable_colors
        
        parts = []
        
        if self.config.enable_timestamps:
            if colors:
                parts.append(f"{ColorCodes.DIM}%(asctime)s{ColorCodes.RESET}")
            else:
                parts.append("%(asctime)s")
        
        if self.config.enable_thread_info:
            if colors:
                parts.append(f"{ColorCodes.BRIGHT_BLACK}[%(threadName)s]{ColorCodes.RESET}")
            else:
                parts.append("[%(threadName)s]")
        
        # Component and level
        if colors:
            parts.append(f"{ColorCodes.BOLD}[%(name)s]{ColorCodes.RESET}")
            parts.append("%(levelname)s")
        else:
            parts.append("[%(name)s]")
            parts.append("%(levelname)s")
        
        parts.append("%(message)s")
        
        format_str = " ".join(parts)
        
        if self.config.show_milliseconds:
            date_fmt = self.config.timestamp_format
        else:
            date_fmt = "%Y-%m-%d %H:%M:%S"
        
        return logging.Formatter(format_str, datefmt=date_fmt)
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on levels"""
        # Check component-specific level
        component_level = self.config.component_levels.get(
            self.component, 
            self.config.global_level
        )
        return level.value >= component_level.value
    
    def _colorize(self, text: str, color: str) -> str:
        """Add color to text if enabled"""
        if not self.config.enable_colors:
            return text
        return f"{color}{text}{ColorCodes.RESET}"
    
    def _format_context(self, context: Optional[LogContext] = None) -> str:
        """Format context information"""
        if not context and not self.context_stack:
            return ""
        
        ctx = context or (self.context_stack[-1] if self.context_stack else None)
        if not ctx:
            return ""
        
        parts = []
        
        if self.config.enable_session_info and ctx.session_id:
            parts.append(f"session={ctx.session_id[:8]}")
        
        if ctx.agent:
            parts.append(f"agent={ctx.agent}")
        
        if self.config.enable_model_info and ctx.model:
            parts.append(f"model={ctx.model}")
        
        if ctx.task_id:
            parts.append(f"task={ctx.task_id[:8]}")
        
        if parts:
            return self._colorize(f"[{', '.join(parts)}]", ColorCodes.DIM) + " "
        
        return ""
    
    def push_context(self, context: LogContext):
        """Push a logging context"""
        with self.lock:
            self.context_stack.append(context)
    
    def pop_context(self):
        """Pop a logging context"""
        with self.lock:
            if self.context_stack:
                self.context_stack.pop()
    
    def trace(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log trace message (most verbose)"""
        if self._should_log(LogLevel.TRACE):
            ctx_str = self._format_context(context)
            self.logger.log(LogLevel.TRACE.value, f"{ctx_str}{message}", **kwargs)
            self.stats['messages_logged'] += 1
    
    def debug(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log debug message"""
        if self._should_log(LogLevel.DEBUG):
            ctx_str = self._format_context(context)
            msg = self._colorize(f"{ctx_str}{message}", ColorCodes.BRIGHT_BLACK)
            self.logger.debug(msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def info(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log info message"""
        if self._should_log(LogLevel.INFO):
            ctx_str = self._format_context(context)
            self.logger.info(f"{ctx_str}{message}", **kwargs)
            self.stats['messages_logged'] += 1
    
    def success(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log success message"""
        if self._should_log(LogLevel.SUCCESS):
            ctx_str = self._format_context(context)
            msg = self._colorize(f"✓ {ctx_str}{message}", ColorCodes.GREEN)
            self.logger.log(LogLevel.SUCCESS.value, msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def warning(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log warning message"""
        if self._should_log(LogLevel.WARNING):
            ctx_str = self._format_context(context)
            msg = self._colorize(f"⚠ {ctx_str}{message}", ColorCodes.YELLOW)
            self.logger.warning(msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def error(self, message: str, exc_info: bool = False, context: Optional[LogContext] = None, **kwargs):
        """Log error message"""
        if self._should_log(LogLevel.ERROR):
            ctx_str = self._format_context(context)
            msg = self._colorize(f"✗ {ctx_str}{message}", ColorCodes.RED)
            self.logger.error(msg, exc_info=exc_info, **kwargs)
            self.stats['errors_logged'] += 1
    
    def critical(self, message: str, exc_info: bool = True, context: Optional[LogContext] = None, **kwargs):
        """Log critical message"""
        if self._should_log(LogLevel.CRITICAL):
            ctx_str = self._format_context(context)
            msg = self._colorize(f"🔥 {ctx_str}{message}", ColorCodes.BG_RED + ColorCodes.WHITE)
            self.logger.critical(msg, exc_info=exc_info, **kwargs)
            self.stats['errors_logged'] += 1
    
    def thought(self, content: str, context: Optional[LogContext] = None):
        """Log model thought/reasoning"""
        if not self._should_log(LogLevel.INFO):
            return
        
        self.stats['thoughts_captured'] += 1
        
        if self.config.box_thoughts:
            self._print_boxed(
                content, 
                title="💭 Reasoning",
                color=ColorCodes.CYAN,
                context=context
            )
        else:
            ctx_str = self._format_context(context)
            print(f"\n{self._colorize('💭 Thought:', ColorCodes.CYAN)} {ctx_str}{content}\n")
    
    def response(self, content: str, context: Optional[LogContext] = None, stream: bool = False):
        """Log model response"""
        if not self._should_log(LogLevel.INFO):
            return
        
        if stream:
            # For streaming, just write directly
            sys.stdout.write(content)
            sys.stdout.flush()
        elif self.config.box_responses:
            self._print_boxed(
                content,
                title="🤖 Response",
                color=ColorCodes.GREEN,
                context=context
            )
        else:
            ctx_str = self._format_context(context)
            print(f"\n{self._colorize('🤖 Response:', ColorCodes.GREEN)} {ctx_str}\n{content}\n")
    
    def tool_execution(self, tool_name: str, args: Dict[str, Any], result: Any = None, 
                       duration: Optional[float] = None, context: Optional[LogContext] = None):
        """Log tool execution"""
        if not self._should_log(LogLevel.INFO):
            return
        
        self.stats['tools_executed'] += 1
        
        ctx_str = self._format_context(context)
        
        if self.config.box_tools:
            lines = [
                f"Tool: {tool_name}",
                f"Args: {json.dumps(args, indent=2) if args else 'None'}",
            ]
            
            if duration is not None:
                lines.append(f"Duration: {duration:.3f}s")
            
            if result is not None:
                result_str = str(result)
                if len(result_str) > 200:
                    result_str = result_str[:200] + "..."
                lines.append(f"Result: {result_str}")
            
            self._print_boxed(
                "\n".join(lines),
                title="🔧 Tool Execution",
                color=ColorCodes.YELLOW,
                context=context
            )
        else:
            parts = [f"{self._colorize('🔧 Tool:', ColorCodes.YELLOW)} {ctx_str}{tool_name}"]
            if duration:
                parts.append(f"({duration:.3f}s)")
            print(" ".join(parts))
    
    def memory_operation(self, operation: str, details: Dict[str, Any], context: Optional[LogContext] = None):
        """Log memory operation"""
        if not self._should_log(LogLevel.DEBUG if self.config.show_memory_triage else LogLevel.INFO):
            return
        
        ctx_str = self._format_context(context)
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        msg = f"{self._colorize('💾 Memory:', ColorCodes.MAGENTA)} {ctx_str}{operation} ({detail_str})"
        print(msg)
    
    def orchestrator_event(self, event: str, task_id: Optional[str] = None, 
                          details: Optional[Dict[str, Any]] = None, context: Optional[LogContext] = None):
        """Log orchestrator event"""
        if not self._should_log(LogLevel.DEBUG if not self.config.show_orchestrator_details else LogLevel.INFO):
            return
        
        ctx_str = self._format_context(context)
        detail_str = f" ({json.dumps(details)})" if details else ""
        task_str = f"[task={task_id[:8]}]" if task_id else ""
        msg = f"{self._colorize('⚙️ Orchestrator:', ColorCodes.BLUE)} {ctx_str}{task_str} {event}{detail_str}"
        print(msg)
    
    def infrastructure_event(self, event: str, resource_type: Optional[str] = None,
                            details: Optional[Dict[str, Any]] = None, context: Optional[LogContext] = None):
        """Log infrastructure event"""
        if not self._should_log(LogLevel.INFO if self.config.show_infrastructure_stats else LogLevel.DEBUG):
            return
        
        ctx_str = self._format_context(context)
        resource_str = f"[{resource_type}]" if resource_type else ""
        detail_str = f" ({json.dumps(details)})" if details else ""
        msg = f"{self._colorize('🏗️ Infrastructure:', ColorCodes.BRIGHT_BLUE)} {ctx_str}{resource_str} {event}{detail_str}"
        print(msg)
    
    def performance_metric(self, metric_name: str, value: float, unit: str = "s",
                          context: Optional[LogContext] = None):
        """Log performance metric"""
        if not self._should_log(LogLevel.DEBUG if not self.config.enable_performance_tracking else LogLevel.INFO):
            return
        
        ctx_str = self._format_context(context)
        msg = f"{self._colorize('📊 Performance:', ColorCodes.BRIGHT_MAGENTA)} {ctx_str}{metric_name}: {value:.3f}{unit}"
        print(msg)
    
    def raw_stream_chunk(self, chunk_data: Dict[str, Any], chunk_num: int):
        """Log raw stream chunk (for debugging)"""
        if not self.config.show_ollama_raw_chunks:
            return
        
        print("\n" + "▼" * 60)
        print(f"RAW CHUNK #{chunk_num} FROM OLLAMA:")
        print("▼" * 60)
        print(json.dumps(chunk_data, indent=2, ensure_ascii=False))
        print("▲" * 60 + "\n")
        sys.stdout.flush()
    
    def _print_boxed(self, content: str, title: str = "", color: str = "", context: Optional[LogContext] = None):
        """Print content in a box"""
        lines = content.split('\n')
        max_width = min(max(len(line) for line in lines) + 4, self.config.max_line_width)
        
        ctx_str = self._format_context(context)
        
        # Top border
        print(self._colorize(f"\n╔{'═' * (max_width - 2)}╗", color))
        
        # Title
        if title:
            title_line = f"║ {title}{' ' * (max_width - len(title) - 3)}║"
            print(self._colorize(title_line, color))
            print(self._colorize(f"╠{'═' * (max_width - 2)}╣", color))
        
        # Content
        for line in lines:
            wrapped = self._wrap_line(line, max_width - 4)
            for wrapped_line in wrapped:
                content_line = f"║ {wrapped_line}{' ' * (max_width - len(wrapped_line) - 3)}║"
                print(content_line)
        
        # Bottom border
        print(self._colorize(f"╚{'═' * (max_width - 2)}╝\n", color))
    
    def _wrap_line(self, line: str, width: int) -> List[str]:
        """Wrap a line to fit within width"""
        if len(line) <= width:
            return [line]
        
        words = line.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                current_line += f"{word} "
            else:
                if current_line:
                    lines.append(current_line.rstrip())
                current_line = f"{word} "
        
        if current_line:
            lines.append(current_line.rstrip())
        
        return lines
    
    def start_timer(self, name: str):
        """Start a performance timer"""
        if self.config.enable_performance_tracking:
            with self.lock:
                self.performance_timers[name] = time.time()
    
    def stop_timer(self, name: str, context: Optional[LogContext] = None) -> Optional[float]:
        """Stop a performance timer and log result"""
        if not self.config.enable_performance_tracking:
            return None
        
        with self.lock:
            if name not in self.performance_timers:
                return None
            
            duration = time.time() - self.performance_timers[name]
            del self.performance_timers[name]
            
            self.performance_metric(name, duration, "s", context)
            return duration
    
    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        return self.stats.copy()
    
    def print_stats(self):
        """Print logging statistics"""
        print("\n" + "=" * 60)
        print("Logging Statistics")
        print("=" * 60)
        for key, value in self.stats.items():
            print(f"  {key}: {value}")
        print("=" * 60 + "\n")


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_data['exception'] = ''.join(traceback.format_exception(*record.exc_info))
        
        return json.dumps(log_data)


# Global logger instance
_global_logger: Optional[VeraLogger] = None


def get_logger(component: str = "vera", config: Optional[LoggingConfig] = None) -> VeraLogger:
    """Get or create a logger for a component"""
    global _global_logger
    
    if _global_logger is None:
        if config is None:
            config = LoggingConfig()
        _global_logger = VeraLogger(config, component)
        
        # Register custom log levels
        logging.addLevelName(LogLevel.TRACE.value, "TRACE")
        logging.addLevelName(LogLevel.SUCCESS.value, "SUCCESS")
    
    return _global_logger


def configure_logging(config: LoggingConfig):
    """Configure global logging"""
    global _global_logger
    _global_logger = VeraLogger(config, "vera")


# Example usage
if __name__ == "__main__":
    # Create config with various options
    config = LoggingConfig(
        global_level=LogLevel.DEBUG,
        enable_colors=True,
        enable_timestamps=True,
        enable_thread_info=True,
        enable_session_info=True,
        enable_model_info=True,
        box_thoughts=True,
        box_responses=False,
        box_tools=True,
        show_ollama_raw_chunks=False,
        enable_performance_tracking=True,
        log_to_file=True,
        log_to_json=True,
    )
    
    # Get logger
    logger = get_logger("test", config)
    
    # Test various log types
    logger.info("Vera initialized successfully")
    logger.debug("Loading configuration from file")
    logger.success("Model loaded: gemma2:latest")
    logger.warning("High memory usage detected")
    logger.error("Connection timeout", exc_info=False)
    
    # Test with context
    context = LogContext(
        session_id="abc123def456",
        agent="fast",
        model="gemma2",
        task_id="task-001"
    )
    
    logger.info("Processing query", context=context)
    
    # Test thought output
    logger.thought(
        "Let me analyze this query step by step:\n"
        "1. First, I need to understand the user's intent\n"
        "2. Then, I should break down the problem\n"
        "3. Finally, I can formulate a response",
        context=context
    )
    
    # Test tool execution
    logger.tool_execution(
        "web_search",
        {"query": "quantum computing", "max_results": 5},
        result={"found": 5, "sources": ["arxiv.org", "nature.com"]},
        duration=1.234,
        context=context
    )
    
    # Test memory operation
    logger.memory_operation(
        "add_to_graph",
        {"node_type": "Entity", "properties": {"name": "Tesla"}},
        context=context
    )
    
    # Test orchestrator event
    logger.orchestrator_event(
        "task_submitted",
        task_id="task-001",
        details={"type": "llm.generate", "priority": "high"},
        context=context
    )
    
    # Test infrastructure event
    logger.infrastructure_event(
        "container_provisioned",
        resource_type="docker",
        details={"image": "vera-worker:latest", "cpu": 2, "memory": "2GB"},
        context=context
    )
    
    # Test performance tracking
    logger.start_timer("query_processing")
    time.sleep(0.1)
    logger.stop_timer("query_processing", context=context)
    
    # Print statistics
    logger.print_stats()