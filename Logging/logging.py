#!/usr/bin/env python3
# Vera/Utils/logging.py

"""
Vera Unified Logging System
Provides structured, configurable logging with rich formatting and metadata.
Enhanced with provenance tracking, full stack trace capabilities, token tracking,
and comprehensive system resource monitoring.
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
import platform

# Optional imports for system monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not available. Install with: pip install psutil")

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


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
class SystemMetrics:
    """System resource metrics"""
    timestamp: float
    
    # CPU
    cpu_count_physical: int
    cpu_count_logical: int
    cpu_percent: float
    cpu_freq_current: Optional[float] = None  # MHz
    cpu_freq_max: Optional[float] = None
    
    # Memory
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    ram_used_gb: float = 0.0
    ram_percent: float = 0.0
    
    # Swap
    swap_total_gb: float = 0.0
    swap_used_gb: float = 0.0
    swap_percent: float = 0.0
    
    # GPU
    gpu_available: bool = False
    gpu_count: int = 0
    gpu_names: List[str] = field(default_factory=list)
    gpu_memory_total_gb: List[float] = field(default_factory=list)
    gpu_memory_used_gb: List[float] = field(default_factory=list)
    gpu_memory_percent: List[float] = field(default_factory=list)
    gpu_utilization: List[float] = field(default_factory=list)
    gpu_temperature: List[float] = field(default_factory=list)
    cuda_available: bool = False
    
    # Power
    power_plugged: Optional[bool] = None
    battery_percent: Optional[float] = None
    battery_time_left: Optional[int] = None  # seconds
    
    # Disk
    disk_usage_percent: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_free_gb: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp,
            'cpu': {
                'count_physical': self.cpu_count_physical,
                'count_logical': self.cpu_count_logical,
                'percent': self.cpu_percent,
                'freq_current_mhz': self.cpu_freq_current,
                'freq_max_mhz': self.cpu_freq_max,
            },
            'ram': {
                'total_gb': round(self.ram_total_gb, 2),
                'available_gb': round(self.ram_available_gb, 2),
                'used_gb': round(self.ram_used_gb, 2),
                'percent': round(self.ram_percent, 1),
            },
            'swap': {
                'total_gb': round(self.swap_total_gb, 2),
                'used_gb': round(self.swap_used_gb, 2),
                'percent': round(self.swap_percent, 1),
            },
            'gpu': {
                'available': self.gpu_available,
                'cuda_available': self.cuda_available,
                'count': self.gpu_count,
                'devices': [
                    {
                        'name': name,
                        'memory_total_gb': round(total, 2),
                        'memory_used_gb': round(used, 2),
                        'memory_percent': round(percent, 1),
                        'utilization': round(util, 1),
                        'temperature': round(temp, 1) if temp else None,
                    }
                    for name, total, used, percent, util, temp in zip(
                        self.gpu_names,
                        self.gpu_memory_total_gb,
                        self.gpu_memory_used_gb,
                        self.gpu_memory_percent,
                        self.gpu_utilization,
                        self.gpu_temperature,
                    )
                ] if self.gpu_count > 0 else []
            },
            'power': {
                'plugged': self.power_plugged,
                'battery_percent': self.battery_percent,
                'battery_time_left_minutes': self.battery_time_left // 60 if self.battery_time_left else None,
            },
            'disk': {
                'usage_percent': self.disk_usage_percent,
                'total_gb': round(self.disk_total_gb, 2) if self.disk_total_gb else None,
                'free_gb': round(self.disk_free_gb, 2) if self.disk_free_gb else None,
            }
        }
    
    def format_summary(self) -> str:
        """Format as summary string"""
        parts = []
        
        # CPU
        parts.append(f"CPU: {self.cpu_count_physical}C/{self.cpu_count_logical}T @ {self.cpu_percent:.1f}%")
        
        # RAM
        parts.append(f"RAM: {self.ram_used_gb:.1f}/{self.ram_total_gb:.1f}GB ({self.ram_percent:.1f}%)")
        
        # GPU
        if self.gpu_available:
            gpu_info = f"GPU: {self.gpu_count}x"
            if self.gpu_names:
                gpu_info += f" {self.gpu_names[0].split()[0]}"  # Short name
            if self.gpu_utilization:
                avg_util = sum(self.gpu_utilization) / len(self.gpu_utilization)
                gpu_info += f" @ {avg_util:.1f}%"
            parts.append(gpu_info)
        
        # Power
        if self.battery_percent is not None:
            power_str = f"Battery: {self.battery_percent:.0f}%"
            if not self.power_plugged:
                power_str += " (unplugged)"
            parts.append(power_str)
        
        return " | ".join(parts)


@dataclass
class LLMMetrics:
    """LLM performance metrics"""
    start_time: float
    end_time: float
    duration: float
    
    # Token counts
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Throughput
    tokens_per_second: float = 0.0
    input_tokens_per_second: float = 0.0
    output_tokens_per_second: float = 0.0
    
    # Model info
    model: Optional[str] = None
    provider: Optional[str] = None
    
    # Additional metrics
    first_token_latency: Optional[float] = None  # Time to first token (TTFT)
    cache_hit: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': round(self.duration, 3),
            'tokens': {
                'input': self.input_tokens,
                'output': self.output_tokens,
                'total': self.total_tokens,
            },
            'throughput': {
                'tokens_per_second': round(self.tokens_per_second, 2),
                'input_tps': round(self.input_tokens_per_second, 2),
                'output_tps': round(self.output_tokens_per_second, 2),
            },
            'model': self.model,
            'provider': self.provider,
            'first_token_latency': round(self.first_token_latency, 3) if self.first_token_latency else None,
            'cache_hit': self.cache_hit,
        }
    
    def format_summary(self) -> str:
        """Format as summary string"""
        parts = [
            f"{self.total_tokens} tokens",
            f"{self.tokens_per_second:.1f} t/s",
            f"{self.duration:.2f}s",
        ]
        
        if self.first_token_latency:
            parts.append(f"TTFT: {self.first_token_latency:.3f}s")
        
        if self.model:
            parts.append(f"model: {self.model}")
        
        return " | ".join(parts)


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


class SystemMonitor:
    """Monitor system resources"""
    
    def __init__(self):
        self.platform = platform.system()
        self.has_psutil = HAS_PSUTIL
        self.has_gputil = HAS_GPUTIL
        self.has_torch = HAS_TORCH
        
        # Cache static info
        self._cpu_count_physical = psutil.cpu_count(logical=False) if HAS_PSUTIL else 1
        self._cpu_count_logical = psutil.cpu_count(logical=True) if HAS_PSUTIL else 1
        
        # Check CUDA availability once
        self._cuda_available = torch.cuda.is_available() if HAS_TORCH else False
    
    def get_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_count_physical=self._cpu_count_physical,
            cpu_count_logical=self._cpu_count_logical,
            cpu_percent=0.0,
        )
        
        if not HAS_PSUTIL:
            return metrics
        
        # CPU metrics
        try:
            metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                metrics.cpu_freq_current = cpu_freq.current
                metrics.cpu_freq_max = cpu_freq.max
        except Exception:
            pass
        
        # Memory metrics
        try:
            mem = psutil.virtual_memory()
            metrics.ram_total_gb = mem.total / (1024**3)
            metrics.ram_available_gb = mem.available / (1024**3)
            metrics.ram_used_gb = mem.used / (1024**3)
            metrics.ram_percent = mem.percent
            
            swap = psutil.swap_memory()
            metrics.swap_total_gb = swap.total / (1024**3)
            metrics.swap_used_gb = swap.used / (1024**3)
            metrics.swap_percent = swap.percent
        except Exception:
            pass
        
        # GPU metrics
        self._collect_gpu_metrics(metrics)
        
        # Power metrics
        try:
            battery = psutil.sensors_battery()
            if battery:
                metrics.power_plugged = battery.power_plugged
                metrics.battery_percent = battery.percent
                metrics.battery_time_left = battery.secsleft if battery.secsleft != -1 else None
        except Exception:
            pass
        
        # Disk metrics
        try:
            disk = psutil.disk_usage('/')
            metrics.disk_total_gb = disk.total / (1024**3)
            metrics.disk_free_gb = disk.free / (1024**3)
            metrics.disk_usage_percent = disk.percent
        except Exception:
            pass
        
        return metrics
    
    def _collect_gpu_metrics(self, metrics: SystemMetrics):
        """Collect GPU metrics using available libraries"""
        # Check CUDA via PyTorch
        metrics.cuda_available = self._cuda_available
        
        # Try GPUtil first (more detailed)
        if HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    metrics.gpu_available = True
                    metrics.gpu_count = len(gpus)
                    
                    for gpu in gpus:
                        metrics.gpu_names.append(gpu.name)
                        metrics.gpu_memory_total_gb.append(gpu.memoryTotal / 1024)
                        metrics.gpu_memory_used_gb.append(gpu.memoryUsed / 1024)
                        metrics.gpu_memory_percent.append(gpu.memoryUtil * 100)
                        metrics.gpu_utilization.append(gpu.load * 100)
                        metrics.gpu_temperature.append(gpu.temperature)
                    return
            except Exception:
                pass
        
        # Fallback to PyTorch CUDA info
        if HAS_TORCH and self._cuda_available:
            try:
                metrics.gpu_available = True
                metrics.gpu_count = torch.cuda.device_count()
                
                for i in range(metrics.gpu_count):
                    metrics.gpu_names.append(torch.cuda.get_device_name(i))
                    
                    # Memory info
                    mem_allocated = torch.cuda.memory_allocated(i) / (1024**3)
                    mem_reserved = torch.cuda.memory_reserved(i) / (1024**3)
                    
                    # Get total memory (this is a rough estimate)
                    props = torch.cuda.get_device_properties(i)
                    mem_total = props.total_memory / (1024**3)
                    
                    metrics.gpu_memory_total_gb.append(mem_total)
                    metrics.gpu_memory_used_gb.append(mem_allocated)
                    metrics.gpu_memory_percent.append((mem_allocated / mem_total) * 100 if mem_total > 0 else 0)
                    metrics.gpu_utilization.append(0.0)  # Not available via PyTorch
                    metrics.gpu_temperature.append(0.0)  # Not available via PyTorch
            except Exception:
                pass
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get static system information"""
        info = {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
        }
        
        if HAS_PSUTIL:
            info['cpu_count_physical'] = self._cpu_count_physical
            info['cpu_count_logical'] = self._cpu_count_logical
            
            mem = psutil.virtual_memory()
            info['ram_total_gb'] = round(mem.total / (1024**3), 2)
        
        if HAS_TORCH:
            info['cuda_available'] = self._cuda_available
            if self._cuda_available:
                info['cuda_version'] = torch.version.cuda
                info['cudnn_version'] = torch.backends.cudnn.version()
                info['gpu_count'] = torch.cuda.device_count()
                info['gpu_names'] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        
        return info


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
    
    # System monitoring
    enable_system_monitoring: bool = True  # Monitor system resources
    log_system_info_on_start: bool = True  # Log system info at startup
    system_metrics_interval: int = 60  # Seconds between system metric logs (0 to disable)
    show_system_metrics_in_context: bool = False  # Include brief metrics in log context
    
    # LLM metrics tracking
    enable_llm_metrics: bool = True  # Track LLM token usage and throughput
    log_llm_metrics: bool = True  # Automatically log LLM metrics
    track_first_token_latency: bool = True  # Track time to first token
    
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
            self.enable_system_monitoring = True
            self.enable_llm_metrics = True


class VeraLogger:
    """
    Unified logger for Vera with structured output and rich formatting
    Enhanced with automatic provenance tracking, stack trace capture,
    token tracking, and system resource monitoring
    """
    
    def __init__(self, config: LoggingConfig, component: str = "vera"):
        self.config = config
        self.component = component
        self.context_stack: List[LogContext] = []
        self.performance_timers: Dict[str, float] = {}
        self.lock = threading.RLock()
        
        # System monitoring
        self.system_monitor = SystemMonitor() if config.enable_system_monitoring else None
        self._last_system_metrics: Optional[SystemMetrics] = None
        self._system_metrics_timer: Optional[threading.Timer] = None
        
        # LLM metrics tracking
        self._llm_operation_start: Optional[float] = None
        self._llm_first_token_time: Optional[float] = None
        
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
            'llm_calls': 0,
            'total_tokens': 0,
            'total_llm_time': 0.0,
        }
        
        # Log system info on startup
        if config.log_system_info_on_start and self.system_monitor:
            self._log_system_info()
        
        # Start periodic system metrics logging if configured
        if config.system_metrics_interval > 0 and self.system_monitor:
            self._start_system_metrics_logging()
    
    def _log_system_info(self):
        """Log system information at startup"""
        if not self.system_monitor:
            return
        
        info = self.system_monitor.get_system_info()
        metrics = self.system_monitor.get_metrics()
        
        self.info(f"System: {info.get('platform', 'unknown')}")
        self.info(f"Python: {info.get('python_version', 'unknown')}")
        self.info(f"CPU: {metrics.cpu_count_physical} cores / {metrics.cpu_count_logical} threads")
        self.info(f"RAM: {metrics.ram_total_gb:.1f} GB total")
        
        if metrics.gpu_available:
            self.info(f"GPU: {metrics.gpu_count}x available")
            for i, name in enumerate(metrics.gpu_names):
                self.info(f"  GPU {i}: {name} ({metrics.gpu_memory_total_gb[i]:.1f} GB)")
            if metrics.cuda_available:
                self.info(f"CUDA: Available (version {info.get('cuda_version', 'unknown')})")
        else:
            self.debug("GPU: Not available")
    
    def _start_system_metrics_logging(self):
        """Start periodic system metrics logging"""
        def log_metrics():
            if self.system_monitor:
                metrics = self.system_monitor.get_metrics()
                self._last_system_metrics = metrics
                self.info(f"System metrics: {metrics.format_summary()}")
                
                # Schedule next log
                if self.config.system_metrics_interval > 0:
                    self._system_metrics_timer = threading.Timer(
                        self.config.system_metrics_interval,
                        log_metrics
                    )
                    self._system_metrics_timer.daemon = True
                    self._system_metrics_timer.start()
        
        # Start the timer
        log_metrics()
    
    def stop_system_metrics_logging(self):
        """Stop periodic system metrics logging"""
        if self._system_metrics_timer:
            self._system_metrics_timer.cancel()
            self._system_metrics_timer = None
    
    def get_current_system_metrics(self) -> Optional[SystemMetrics]:
        """Get current system metrics"""
        if self.system_monitor:
            return self.system_monitor.get_metrics()
        return None
    
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
        
        # Add brief system metrics if enabled
        if self.config.show_system_metrics_in_context and self._last_system_metrics:
            metrics = self._last_system_metrics
            parts.append(f"cpu={metrics.cpu_percent:.0f}%")
            parts.append(f"ram={metrics.ram_percent:.0f}%")
            if metrics.gpu_available and metrics.gpu_utilization:
                avg_gpu = sum(metrics.gpu_utilization) / len(metrics.gpu_utilization)
                parts.append(f"gpu={avg_gpu:.0f}%")
        
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
    
    # ===== LLM Metrics Tracking =====
    
    def start_llm_operation(self, model: Optional[str] = None, provider: Optional[str] = None):
        """Start tracking an LLM operation"""
        if self.config.enable_llm_metrics:
            self._llm_operation_start = time.time()
            self._llm_first_token_time = None
    
    def mark_first_token(self):
        """Mark when first token is received"""
        if self.config.enable_llm_metrics and self.config.track_first_token_latency:
            if self._llm_operation_start and not self._llm_first_token_time:
                self._llm_first_token_time = time.time()
    
    def end_llm_operation(self, input_tokens: int, output_tokens: int,
                         model: Optional[str] = None, provider: Optional[str] = None,
                         cache_hit: bool = False) -> Optional[LLMMetrics]:
        """End LLM operation tracking and return metrics"""
        if not self.config.enable_llm_metrics or not self._llm_operation_start:
            return None
        
        end_time = time.time()
        duration = end_time - self._llm_operation_start
        total_tokens = input_tokens + output_tokens
        
        # Calculate throughput
        tokens_per_second = total_tokens / duration if duration > 0 else 0
        input_tps = input_tokens / duration if duration > 0 else 0
        output_tps = output_tokens / duration if duration > 0 else 0
        
        # Calculate first token latency
        first_token_latency = None
        if self._llm_first_token_time:
            first_token_latency = self._llm_first_token_time - self._llm_operation_start
        
        metrics = LLMMetrics(
            start_time=self._llm_operation_start,
            end_time=end_time,
            duration=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tokens_per_second=tokens_per_second,
            input_tokens_per_second=input_tps,
            output_tokens_per_second=output_tps,
            model=model,
            provider=provider,
            first_token_latency=first_token_latency,
            cache_hit=cache_hit,
        )
        
        # Update stats
        self.stats['llm_calls'] += 1
        self.stats['total_tokens'] += total_tokens
        self.stats['total_llm_time'] += duration
        
        # Auto-log if enabled
        if self.config.log_llm_metrics:
            self.llm_metrics(metrics)
        
        # Reset tracking
        self._llm_operation_start = None
        self._llm_first_token_time = None
        
        return metrics
    
    def llm_metrics(self, metrics: LLMMetrics, context: Optional[LogContext] = None):
        """Log LLM metrics"""
        if not self._should_log(LogLevel.INFO):
            return
        
        context = self._enrich_context(context, capture_stack=False)
        ctx_str = self._format_context(context)
        
        # Format message
        msg_parts = [
            self._colorize("🤖 LLM:", ColorCodes.BRIGHT_CYAN),
            ctx_str,
            f"{metrics.total_tokens} tokens ({metrics.input_tokens} in / {metrics.output_tokens} out)",
            f"@ {metrics.tokens_per_second:.1f} t/s",
            f"in {metrics.duration:.2f}s"
        ]
        
        if metrics.first_token_latency:
            msg_parts.append(f"(TTFT: {metrics.first_token_latency:.3f}s)")
        
        if metrics.model:
            msg_parts.append(f"[{metrics.model}]")
        
        if metrics.cache_hit:
            msg_parts.append(self._colorize("(cached)", ColorCodes.GREEN))
        
        print(" ".join(msg_parts))
    
    def system_metrics(self, metrics: Optional[SystemMetrics] = None, context: Optional[LogContext] = None):
        """Log system metrics"""
        if not self._should_log(LogLevel.INFO):
            return
        
        if metrics is None:
            if not self.system_monitor:
                return
            metrics = self.system_monitor.get_metrics()
        
        context = self._enrich_context(context, capture_stack=False)
        ctx_str = self._format_context(context)
        
        msg = f"{self._colorize('💻 System:', ColorCodes.BRIGHT_BLUE)} {ctx_str}{metrics.format_summary()}"
        print(msg)
    
    # ===== Standard Logging Methods =====
    
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
        stats = self.stats.copy()
        
        # Add computed metrics
        if stats['llm_calls'] > 0:
            stats['avg_tokens_per_call'] = stats['total_tokens'] / stats['llm_calls']
            stats['avg_time_per_call'] = stats['total_llm_time'] / stats['llm_calls']
            stats['avg_tokens_per_second'] = stats['total_tokens'] / stats['total_llm_time'] if stats['total_llm_time'] > 0 else 0
        
        # Add current system metrics if available
        if self.system_monitor:
            metrics = self.system_monitor.get_metrics()
            stats['current_system_metrics'] = metrics.to_dict()
        
        return stats
    
    def print_stats(self):
        """Print logging statistics"""
        print("\n" + "=" * 60)
        print("Logging Statistics")
        print("=" * 60)
        
        stats = self.get_stats()
        
        # Basic stats
        print(f"  Messages logged: {stats['messages_logged']}")
        print(f"  Errors logged: {stats['errors_logged']}")
        print(f"  Thoughts captured: {stats['thoughts_captured']}")
        print(f"  Tools executed: {stats['tools_executed']}")
        print(f"  Stack traces captured: {stats['stack_traces_captured']}")
        
        # LLM stats
        if stats['llm_calls'] > 0:
            print(f"\n  LLM Calls: {stats['llm_calls']}")
            print(f"  Total Tokens: {stats['total_tokens']}")
            print(f"  Total LLM Time: {stats['total_llm_time']:.2f}s")
            print(f"  Avg Tokens/Call: {stats.get('avg_tokens_per_call', 0):.1f}")
            print(f"  Avg Time/Call: {stats.get('avg_time_per_call', 0):.3f}s")
            print(f"  Avg Throughput: {stats.get('avg_tokens_per_second', 0):.1f} t/s")
        
        # System metrics
        if 'current_system_metrics' in stats:
            print(f"\n  Current System State:")
            sys_metrics = stats['current_system_metrics']
            print(f"    CPU: {sys_metrics['cpu']['percent']:.1f}%")
            print(f"    RAM: {sys_metrics['ram']['used_gb']:.1f}/{sys_metrics['ram']['total_gb']:.1f} GB ({sys_metrics['ram']['percent']:.1f}%)")
            if sys_metrics['gpu']['available']:
                print(f"    GPU: {sys_metrics['gpu']['count']}x available")
        
        print("=" * 60 + "\n")
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop_system_metrics_logging()


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
    print("VERA LOGGING SYSTEM - ENHANCED WITH SYSTEM MONITORING & TOKEN TRACKING")
    print("=" * 80)
    print()
    
    # Test 1: System monitoring
    print("Test 1: System Monitoring")
    print("-" * 80)
    
    config = LoggingConfig(
        global_level=LogLevel.INFO,
        enable_colors=True,
        enable_system_monitoring=True,
        log_system_info_on_start=True,
        system_metrics_interval=0,  # Disable periodic logging for test
    )
    
    logger = get_logger("test", config)
    
    # Get and display system metrics
    if logger.system_monitor:
        metrics = logger.get_current_system_metrics()
        logger.system_metrics(metrics)
        
        print("\nDetailed System Metrics:")
        print(json.dumps(metrics.to_dict(), indent=2))
    
    print("\n")
    
    # Test 2: LLM Token Tracking
    print("Test 2: LLM Token Tracking")
    print("-" * 80)
    
    llm_config = LoggingConfig(
        global_level=LogLevel.INFO,
        enable_llm_metrics=True,
        log_llm_metrics=True,
        track_first_token_latency=True,
    )
    
    llm_logger = get_logger("llm_test", llm_config)
    
    # Simulate LLM call
    llm_logger.start_llm_operation(model="gemma2:27b", provider="ollama")
    time.sleep(0.1)  # Simulate time to first token
    llm_logger.mark_first_token()
    time.sleep(0.3)  # Simulate generation time
    
    metrics = llm_logger.end_llm_operation(
        input_tokens=150,
        output_tokens=450,
        model="gemma2:27b",
        provider="ollama"
    )
    
    if metrics:
        print("\nDetailed LLM Metrics:")
        print(json.dumps(metrics.to_dict(), indent=2))
    
    print("\n")
    
    # Test 3: Combined monitoring
    print("Test 3: Combined System + LLM Monitoring")
    print("-" * 80)
    
    combined_config = LoggingConfig(
        global_level=LogLevel.INFO,
        enable_system_monitoring=True,
        enable_llm_metrics=True,
        show_system_metrics_in_context=True,  # Show metrics in log context
        enable_provenance=True,
    )
    
    combined_logger = get_logger("combined_test", combined_config)
    
    # Simulate a complete workflow
    context = LogContext(
        session_id="test-session-123",
        agent="fast",
        model="gemma2:27b"
    )
    
    combined_logger.info("Starting processing", context=context)
    
    # Tool execution
    combined_logger.start_timer("web_search")
    time.sleep(0.2)
    combined_logger.stop_timer("web_search", context=context)
    
    # LLM call with metrics
    combined_logger.start_llm_operation(model="gemma2:27b")
    time.sleep(0.05)
    combined_logger.mark_first_token()
    time.sleep(0.15)
    combined_logger.end_llm_operation(
        input_tokens=200,
        output_tokens=600,
        model="gemma2:27b"
    )
    
    # System metrics
    if combined_logger.system_monitor:
        sys_metrics = combined_logger.get_current_system_metrics()
        combined_logger.system_metrics(sys_metrics, context=context)
    
    combined_logger.success("Processing complete", context=context)
    
    print("\n")
    
    # Print comprehensive statistics
    combined_logger.print_stats()
    
    print("=" * 80)
    print("Tests completed!")
    print("=" * 80)
    print("\nNote: Install optional dependencies for full functionality:")
    print("  pip install psutil GPUtil torch")
    print("=" * 80)