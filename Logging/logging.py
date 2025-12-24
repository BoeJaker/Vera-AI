#!/usr/bin/env python3
# Vera/Utils/logging.py

"""
Vera Unified Logging System
Provides structured, configurable logging with rich formatting and metadata.
Enhanced with provenance tracking and full stack trace capabilities.
"""

import sys
import logging
import threading
import time
import json
import inspect
from typing import Optional, Dict, Any, List, Tuple
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
class ProvenanceInfo:
    """Information about where a log originated"""
    filename: str
    line_number: int
    function_name: str
    module_name: str
    class_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'file': self.filename,
            'line': self.line_number,
            'function': self.function_name,
            'module': self.module_name,
            'class': self.class_name
        }
    
    def format_short(self) -> str:
        """Format as short string for display"""
        parts = []
        if self.class_name:
            parts.append(f"{self.class_name}.{self.function_name}")
        else:
            parts.append(self.function_name)
        parts.append(f"{Path(self.filename).name}:{self.line_number}")
        return " @ ".join(parts)
    
    def format_long(self) -> str:
        """Format as detailed string"""
        return f"{self.module_name}::{self.function_name} ({self.filename}:{self.line_number})"


@dataclass
class StackTrace:
    """Captured stack trace information"""
    frames: List[Tuple[str, int, str, str]]  # (filename, line, function, code)
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert to dictionary"""
        return [
            {
                'file': frame[0],
                'line': frame[1],
                'function': frame[2],
                'code': frame[3]
            }
            for frame in self.frames
        ]
    
    def format(self, depth: Optional[int] = None) -> str:
        """Format stack trace for display"""
        frames = self.frames[:depth] if depth else self.frames
        lines = ["Stack trace:"]
        for i, (filename, line, function, code) in enumerate(frames):
            lines.append(f"  {i+1}. {Path(filename).name}:{line} in {function}")
            if code:
                lines.append(f"     > {code.strip()}")
        return "\n".join(lines)


@dataclass
class LogContext:
    """Context information for log messages"""
    session_id: Optional[str] = None
    agent: Optional[str] = None
    model: Optional[str] = None
    task_id: Optional[str] = None
    thread_id: Optional[int] = None
    timestamp: Optional[float] = None
    provenance: Optional[ProvenanceInfo] = None
    stack_trace: Optional[StackTrace] = None
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
        
        if self.provenance:
            data['provenance'] = self.provenance.to_dict()
        
        if self.stack_trace:
            data['stack_trace'] = self.stack_trace.to_dict()
        
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
    global_level: LogLevel = LogLevel.DEBUG
    component_levels: Dict[str, LogLevel] = field(default_factory=dict)
    
    # Output options
    enable_colors: bool = True
    enable_timestamps: bool = True
    enable_thread_info: bool = False
    enable_session_info: bool = True
    enable_model_info: bool = True
    enable_performance_tracking: bool = True
    
    # Provenance and tracing
    enable_provenance: bool = True  # Show file, line, function in logs
    enable_stack_traces: bool = False  # Include full stack traces
    stack_trace_depth: int = 10  # Max frames to include in stack trace
    stack_trace_on_error: bool = True  # Always include stack on errors
    trace_mode: bool = False  # Master switch for full trace capabilities
    trace_exclude_modules: List[str] = field(default_factory=lambda: ['logging', 'threading'])  # Modules to exclude from traces
    
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
    
    def __post_init__(self):
        """Apply trace mode settings if enabled"""
        if self.trace_mode:
            self.enable_provenance = True
            self.enable_stack_traces = True
            self.global_level = LogLevel.TRACE
            self.enable_thread_info = True
            self.enable_performance_tracking = True
            self.show_orchestrator_details = True
            self.show_infrastructure_stats = True


class VeraLogger:
    """
    Unified logger for Vera with structured output and rich formatting
    Enhanced with automatic provenance tracking and stack trace capture
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
            'stack_traces_captured': 0,
        }
    
    def _setup_logging(self):
        """Setup Python logging handlers"""
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        self.logger.propagate = False
        
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
    
    def _capture_provenance(self, skip_frames: int = 2) -> ProvenanceInfo:
        """Capture provenance information from call stack"""
        frame = inspect.currentframe()
        
        # Skip internal frames
        for _ in range(skip_frames):
            if frame is not None:
                frame = frame.f_back
        
        if frame is None:
            return ProvenanceInfo(
                filename="<unknown>",
                line_number=0,
                function_name="<unknown>",
                module_name="<unknown>"
            )
        
        frame_info = inspect.getframeinfo(frame)
        
        # Try to get class name if method
        class_name = None
        if 'self' in frame.f_locals:
            class_name = frame.f_locals['self'].__class__.__name__
        elif 'cls' in frame.f_locals:
            class_name = frame.f_locals['cls'].__name__
        
        return ProvenanceInfo(
            filename=frame_info.filename,
            line_number=frame_info.lineno,
            function_name=frame_info.function,
            module_name=frame.f_globals.get('__name__', '<unknown>'),
            class_name=class_name
        )
    
    def _capture_stack_trace(self, skip_frames: int = 2) -> StackTrace:
        """Capture full stack trace"""
        stack = inspect.stack()
        
        # Skip internal frames and excluded modules
        frames = []
        for frame_info in stack[skip_frames:]:
            module = inspect.getmodule(frame_info.frame)
            module_name = module.__name__ if module else '<unknown>'
            
            # Skip excluded modules
            if any(excluded in module_name for excluded in self.config.trace_exclude_modules):
                continue
            
            frames.append((
                frame_info.filename,
                frame_info.lineno,
                frame_info.function,
                frame_info.code_context[0] if frame_info.code_context else ""
            ))
            
            if len(frames) >= self.config.stack_trace_depth:
                break
        
        self.stats['stack_traces_captured'] += 1
        return StackTrace(frames=frames)
    
    def _enrich_context(self, context: Optional[LogContext], 
                       capture_provenance: bool = True,
                       capture_stack: bool = False) -> LogContext:
        """Enrich context with provenance and stack trace if configured"""
        # Start with provided context or create new one
        if context is None:
            context = LogContext()
        
        # Add provenance if enabled and not already present
        if capture_provenance and self.config.enable_provenance and context.provenance is None:
            context.provenance = self._capture_provenance(skip_frames=3)
        
        # Add stack trace if enabled and not already present
        if capture_stack and self.config.enable_stack_traces and context.stack_trace is None:
            context.stack_trace = self._capture_stack_trace(skip_frames=3)
        
        return context
    
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
        
        # Add provenance if available
        if self.config.enable_provenance and ctx.provenance:
            parts.append(ctx.provenance.format_short())
        
        if parts:
            return self._colorize(f"[{', '.join(parts)}]", ColorCodes.DIM) + " "
        
        return ""
    
    def _format_stack_trace(self, stack: StackTrace) -> str:
        """Format stack trace for output"""
        return "\n" + self._colorize(
            stack.format(self.config.stack_trace_depth),
            ColorCodes.DIM
        )
    
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
            context = self._enrich_context(context, capture_stack=True)
            ctx_str = self._format_context(context)
            
            msg = f"{ctx_str}{message}"
            if context and context.stack_trace:
                msg += self._format_stack_trace(context.stack_trace)
            
            self.logger.log(LogLevel.TRACE.value, msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def debug(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log debug message"""
        if self._should_log(LogLevel.DEBUG):
            context = self._enrich_context(context, capture_stack=self.config.trace_mode)
            ctx_str = self._format_context(context)
            
            msg = f"{ctx_str}{message}"
            if context and context.stack_trace and self.config.trace_mode:
                msg += self._format_stack_trace(context.stack_trace)
            
            msg = self._colorize(msg, ColorCodes.BRIGHT_BLACK)
            self.logger.debug(msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def info(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log info message"""
        if self._should_log(LogLevel.INFO):
            context = self._enrich_context(context, capture_stack=False)
            ctx_str = self._format_context(context)
            self.logger.info(f"{ctx_str}{message}", **kwargs)
            self.stats['messages_logged'] += 1
    
    def success(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log success message"""
        if self._should_log(LogLevel.SUCCESS):
            context = self._enrich_context(context, capture_stack=False)
            ctx_str = self._format_context(context)
            msg = self._colorize(f"✓ {ctx_str}{message}", ColorCodes.GREEN)
            self.logger.log(LogLevel.SUCCESS.value, msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def warning(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log warning message"""
        if self._should_log(LogLevel.WARNING):
            context = self._enrich_context(context, capture_stack=self.config.stack_trace_on_error)
            ctx_str = self._format_context(context)
            
            msg = f"⚠ {ctx_str}{message}"
            if context and context.stack_trace and self.config.stack_trace_on_error:
                msg += self._format_stack_trace(context.stack_trace)
            
            msg = self._colorize(msg, ColorCodes.YELLOW)
            self.logger.warning(msg, **kwargs)
            self.stats['messages_logged'] += 1
    
    def error(self, message: str, exc_info: bool = False, context: Optional[LogContext] = None, **kwargs):
        """Log error message"""
        if self._should_log(LogLevel.ERROR):
            context = self._enrich_context(context, capture_stack=True)
            ctx_str = self._format_context(context)
            
            msg = f"✗ {ctx_str}{message}"
            if context and context.stack_trace:
                msg += self._format_stack_trace(context.stack_trace)
            
            msg = self._colorize(msg, ColorCodes.RED)
            self.logger.error(msg, exc_info=exc_info, **kwargs)
            self.stats['errors_logged'] += 1
    
    def critical(self, message: str, exc_info: bool = True, context: Optional[LogContext] = None, **kwargs):
        """Log critical message"""
        if self._should_log(LogLevel.CRITICAL):
            context = self._enrich_context(context, capture_stack=True)
            ctx_str = self._format_context(context)
            
            msg = f"🔥 {ctx_str}{message}"
            if context and context.stack_trace:
                msg += self._format_stack_trace(context.stack_trace)
            
            msg = self._colorize(msg, ColorCodes.BG_RED + ColorCodes.WHITE)
            self.logger.critical(msg, exc_info=exc_info, **kwargs)
            self.stats['errors_logged'] += 1
    
    def thought(self, content: str, context: Optional[LogContext] = None):
        """Log model thought/reasoning"""
        if not self._should_log(LogLevel.INFO):
            return
        
        context = self._enrich_context(context, capture_stack=False)
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
        
        context = self._enrich_context(context, capture_stack=False)
        
        if stream:
            # For streaming, just write directly
            sys.stdout.write(content)
            sys.stdout.flush()
        elif self.config.box_responses:
            self._print_boxed(
                content,
                title="Response",
                color=ColorCodes.GREEN,
                context=context
            )
        else:
            ctx_str = self._format_context(context)
            print(f"\n{self._colorize('Response:', ColorCodes.GREEN)} {ctx_str}\n{content}\n")
    
    def tool_execution(self, tool_name: str, args: Dict[str, Any], result: Any = None, 
                       duration: Optional[float] = None, context: Optional[LogContext] = None):
        """Log tool execution"""
        if not self._should_log(LogLevel.INFO):
            return
        
        context = self._enrich_context(context, capture_stack=self.config.trace_mode)
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
            
            # Add stack trace in trace mode
            if context and context.stack_trace and self.config.trace_mode:
                lines.append("\n" + context.stack_trace.format(5))
            
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
        
        context = self._enrich_context(context, capture_stack=self.config.trace_mode)
        ctx_str = self._format_context(context)
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        msg = f"{self._colorize('Memory:', ColorCodes.MAGENTA)} {ctx_str}{operation} ({detail_str})"
        print(msg)
    
    def orchestrator_event(self, event: str, task_id: Optional[str] = None, 
                          details: Optional[Dict[str, Any]] = None, context: Optional[LogContext] = None):
        """Log orchestrator event"""
        if not self._should_log(LogLevel.DEBUG if not self.config.show_orchestrator_details else LogLevel.INFO):
            return
        
        context = self._enrich_context(context, capture_stack=self.config.trace_mode)
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
        
        context = self._enrich_context(context, capture_stack=self.config.trace_mode)
        ctx_str = self._format_context(context)
        resource_str = f"[{resource_type}]" if resource_type else ""
        detail_str = f" ({json.dumps(details)})" if details else ""
        msg = f"{self._colorize('Infrastructure:', ColorCodes.BRIGHT_BLUE)} {ctx_str}{resource_str} {event}{detail_str}"
        print(msg)
    
    def performance_metric(self, metric_name: str, value: float, unit: str = "s",
                          context: Optional[LogContext] = None):
        """Log performance metric"""
        if not self._should_log(LogLevel.DEBUG if not self.config.enable_performance_tracking else LogLevel.INFO):
            return
        
        context = self._enrich_context(context, capture_stack=False)
        ctx_str = self._format_context(context)
        msg = f"{self._colorize('Performance:', ColorCodes.BRIGHT_MAGENTA)} {ctx_str}{metric_name}: {value:.3f}{unit}"
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
        
        # Add any extra context from LogContext if present
        if hasattr(record, 'context'):
            log_data['context'] = record.context.to_dict()
        
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


# Example usage and tests
if __name__ == "__main__":
    print("=" * 80)
    print("VERA LOGGING SYSTEM - ENHANCED WITH PROVENANCE AND STACK TRACING")
    print("=" * 80)
    print()
    
    # Test 1: Normal mode
    print("Test 1: Normal mode with provenance")
    print("-" * 80)
    config = LoggingConfig(
        global_level=LogLevel.DEBUG,
        enable_colors=True,
        enable_timestamps=True,
        enable_provenance=True,
        enable_stack_traces=False,
        trace_mode=False,
    )
    
    logger = get_logger("test", config)
    
    def test_function():
        """Test function to show provenance"""
        logger.info("This log shows where it came from")
        logger.debug("Debug message with provenance")
        logger.success("Success with provenance")
    
    test_function()
    
    print("\n")
    
    # Test 2: Trace mode (everything enabled)
    print("Test 2: TRACE MODE - Full provenance and stack traces")
    print("-" * 80)
    
    trace_config = LoggingConfig(
        trace_mode=True,  # This enables everything
        enable_colors=True,
    )
    
    trace_logger = get_logger("trace_test", trace_config)
    
    def nested_function():
        """Nested function to show stack trace"""
        trace_logger.debug("Debug with full stack trace")
    
    def calling_function():
        """Calling function"""
        nested_function()
    
    calling_function()
    
    print("\n")
    
    # Test 3: Error with automatic stack trace
    print("Test 3: Error logging with automatic stack trace")
    print("-" * 80)
    
    error_config = LoggingConfig(
        global_level=LogLevel.INFO,
        enable_provenance=True,
        stack_trace_on_error=True,
        enable_colors=True,
    )
    
    error_logger = get_logger("error_test", error_config)
    
    def buggy_function():
        """Function that logs an error"""
        error_logger.error("Something went wrong!")
        error_logger.warning("This is also concerning")
    
    buggy_function()
    
    print("\n")
    
    # Test 4: Complex scenario with context
    print("Test 4: Complex scenario with rich context")
    print("-" * 80)
    
    complex_config = LoggingConfig(
        global_level=LogLevel.DEBUG,
        enable_provenance=True,
        enable_stack_traces=False,
        enable_session_info=True,
        enable_model_info=True,
        trace_mode=False,
    )
    
    complex_logger = get_logger("complex_test", complex_config)
    
    context = LogContext(
        session_id="abc123def456",
        agent="fast",
        model="gemma2",
        task_id="task-001"
    )
    
    complex_logger.info("Processing query", context=context)
    
    # Test tool execution with provenance
    complex_logger.tool_execution(
        "web_search",
        {"query": "quantum computing", "max_results": 5},
        result={"found": 5, "sources": ["arxiv.org"]},
        duration=1.234,
        context=context
    )
    
    print("\n")
    
    # Test 5: Performance tracking
    print("Test 5: Performance tracking with provenance")
    print("-" * 80)
    
    complex_logger.start_timer("operation")
    time.sleep(0.1)
    complex_logger.stop_timer("operation", context=context)
    
    print("\n")
    
    # Print statistics
    complex_logger.print_stats()
    
    print("=" * 80)
    print("Tests completed!")
    print("=" * 80)