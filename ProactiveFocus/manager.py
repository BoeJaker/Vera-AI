#!/usr/bin/env python3
"""
Resource Manager for Proactive Focus System
===========================================
Handles intelligent resource awareness, scheduling, and throttling.

Features:
- System resource monitoring (CPU, RAM, GPU)
- Ollama process detection and load monitoring
- Intelligent wait/pause mechanisms
- Priority-based resource allocation
- Background service coordination
"""

import psutil
import time
import threading
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ResourcePriority(IntEnum):
    """Priority levels for resource allocation"""
    CRITICAL = 0    # User interaction
    HIGH = 1        # Active tasks
    NORMAL = 2      # Background tasks
    LOW = 3         # Idle processing
    OPPORTUNISTIC = 4  # Only when completely idle


@dataclass
class ResourceLimits:
    """Resource usage limits"""
    max_cpu_percent: float = 70.0
    max_memory_percent: float = 80.0
    max_ollama_concurrent: int = 2
    min_free_memory_mb: int = 2048
    
    # Priority-specific limits
    priority_cpu_limits: Dict[ResourcePriority, float] = None
    
    def __post_init__(self):
        if self.priority_cpu_limits is None:
            self.priority_cpu_limits = {
                ResourcePriority.CRITICAL: 95.0,
                ResourcePriority.HIGH: 80.0,
                ResourcePriority.NORMAL: 70.0,
                ResourcePriority.LOW: 50.0,
                ResourcePriority.OPPORTUNISTIC: 30.0
            }


@dataclass
class ResourceState:
    """Current system resource state"""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: int
    ollama_processes: int
    ollama_cpu_percent: float
    timestamp: datetime
    
    def is_idle(self, limits: ResourceLimits) -> bool:
        """Check if system is idle enough for opportunistic tasks"""
        return (
            self.cpu_percent < 20.0 and
            self.ollama_processes == 0 and
            self.memory_percent < 50.0
        )
    
    def can_run(self, priority: ResourcePriority, limits: ResourceLimits) -> bool:
        """Check if resources available for given priority"""
        cpu_limit = limits.priority_cpu_limits.get(priority, limits.max_cpu_percent)
        
        # Memory check
        if self.memory_available_mb < limits.min_free_memory_mb:
            return False
        
        # CPU check
        if self.cpu_percent > cpu_limit:
            return False
        
        # Ollama concurrent limit check
        if priority >= ResourcePriority.NORMAL:
            if self.ollama_processes >= limits.max_ollama_concurrent:
                return False
        
        return True


class ResourceMonitor:
    """Monitor system resources continuously"""
    
    def __init__(self, limits: Optional[ResourceLimits] = None, poll_interval: float = 2.0):
        self.limits = limits or ResourceLimits()
        self.poll_interval = poll_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.current_state: Optional[ResourceState] = None
        self._lock = threading.Lock()
        self._state_callbacks: List[Callable[[ResourceState], None]] = []
    
    def start(self):
        """Start monitoring"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Resource monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info("Resource monitor stopped")
    
    def register_state_callback(self, callback: Callable[[ResourceState], None]):
        """Register callback for state changes"""
        self._state_callbacks.append(callback)
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                state = self._get_current_state()
                
                with self._lock:
                    self.current_state = state
                
                # Notify callbacks
                for callback in self._state_callbacks:
                    try:
                        callback(state)
                    except Exception as e:
                        logger.error(f"State callback error: {e}")
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(self.poll_interval)
    
    def _get_current_state(self) -> ResourceState:
        """Get current resource state"""
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Count Ollama processes
        ollama_processes = 0
        ollama_cpu = 0.0
        
        for proc in psutil.process_iter(['name', 'cpu_percent']):
            try:
                if 'ollama' in proc.info['name'].lower():
                    ollama_processes += 1
                    ollama_cpu += proc.info['cpu_percent'] or 0.0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return ResourceState(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            ollama_processes=ollama_processes,
            ollama_cpu_percent=ollama_cpu,
            timestamp=datetime.now()
        )
    
    def get_state(self) -> Optional[ResourceState]:
        """Get current state snapshot"""
        with self._lock:
            return self.current_state
    
    def wait_for_resources(
        self, 
        priority: ResourcePriority,
        timeout: Optional[float] = None,
        check_interval: float = 2.0
    ) -> bool:
        """
        Wait until resources available for given priority.
        Returns True if resources became available, False if timeout.
        """
        start_time = time.time()
        
        while True:
            state = self.get_state()
            
            if state and state.can_run(priority, self.limits):
                logger.debug(f"Resources available for {priority.name}")
                return True
            
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"Resource wait timeout for {priority.name}")
                return False
            
            logger.debug(
                f"Waiting for resources ({priority.name}): "
                f"CPU={state.cpu_percent:.1f}%, "
                f"Mem={state.memory_percent:.1f}%, "
                f"Ollama={state.ollama_processes}"
            )
            
            time.sleep(check_interval)
    
    def is_idle(self) -> bool:
        """Check if system is idle"""
        state = self.get_state()
        return state.is_idle(self.limits) if state else False


class ResourceGuard:
    """Context manager for resource-aware execution"""
    
    def __init__(
        self, 
        monitor: ResourceMonitor,
        priority: ResourcePriority = ResourcePriority.NORMAL,
        wait_for_resources: bool = True,
        timeout: Optional[float] = None
    ):
        self.monitor = monitor
        self.priority = priority
        self.wait_for_resources = wait_for_resources
        self.timeout = timeout
        self.acquired = False
    
    def __enter__(self):
        """Acquire resources"""
        if self.wait_for_resources:
            self.acquired = self.monitor.wait_for_resources(
                self.priority,
                timeout=self.timeout
            )
            
            if not self.acquired:
                raise ResourceError(
                    f"Could not acquire resources for {self.priority.name}"
                )
        else:
            state = self.monitor.get_state()
            if state:
                self.acquired = state.can_run(self.priority, self.monitor.limits)
            
            if not self.acquired:
                raise ResourceError(
                    f"Resources not available for {self.priority.name}"
                )
        
        logger.debug(f"Resource guard acquired ({self.priority.name})")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release resources"""
        logger.debug(f"Resource guard released ({self.priority.name})")
        self.acquired = False


class ResourceError(Exception):
    """Resource availability error"""
    pass


class PauseController:
    """
    Controller for pausing/resuming proactive operations.
    Supports priority-based pausing.
    """
    
    def __init__(self):
        self._pause_events: Dict[ResourcePriority, threading.Event] = {
            priority: threading.Event() for priority in ResourcePriority
        }
        
        # Start all unpaused
        for event in self._pause_events.values():
            event.set()
        
        self._global_pause = threading.Event()
        self._global_pause.set()
    
    def pause(self, priority: Optional[ResourcePriority] = None):
        """
        Pause operations at or below given priority.
        If priority is None, pause everything.
        """
        if priority is None:
            self._global_pause.clear()
            logger.info("Global pause activated")
        else:
            for p in ResourcePriority:
                if p.value >= priority.value:
                    self._pause_events[p].clear()
            logger.info(f"Paused operations at/below {priority.name}")
    
    def resume(self, priority: Optional[ResourcePriority] = None):
        """
        Resume operations at or below given priority.
        If priority is None, resume everything.
        """
        if priority is None:
            self._global_pause.set()
            for event in self._pause_events.values():
                event.set()
            logger.info("Global pause lifted")
        else:
            for p in ResourcePriority:
                if p.value >= priority.value:
                    self._pause_events[p].set()
            logger.info(f"Resumed operations at/below {priority.name}")
    
    def wait(self, priority: ResourcePriority, timeout: Optional[float] = None) -> bool:
        """
        Wait until not paused for given priority.
        Returns True if resumed, False if timeout.
        """
        # Check global pause first
        if not self._global_pause.wait(timeout=timeout):
            return False
        
        # Check priority-specific pause
        return self._pause_events[priority].wait(timeout=timeout)
    
    def is_paused(self, priority: ResourcePriority) -> bool:
        """Check if paused for given priority"""
        if not self._global_pause.is_set():
            return True
        
        return not self._pause_events[priority].is_set()


class AdaptiveScheduler:
    """
    Adaptive scheduler that learns optimal execution times.
    Tracks success rates and adjusts scheduling.
    """
    
    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
        self.execution_history: List[Dict] = []
        self.optimal_windows: Dict[str, List[tuple]] = {}  # task -> [(hour_start, hour_end)]
    
    def record_execution(
        self,
        task_name: str,
        duration: float,
        success: bool,
        resources_waited: bool
    ):
        """Record execution for learning"""
        record = {
            'task': task_name,
            'timestamp': datetime.now(),
            'hour': datetime.now().hour,
            'duration': duration,
            'success': success,
            'resources_waited': resources_waited,
            'state': self.monitor.get_state()
        }
        
        self.execution_history.append(record)
        
        # Keep only last 1000 records
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]
        
        # Update optimal windows
        self._update_optimal_windows(task_name)
    
    def _update_optimal_windows(self, task_name: str):
        """Update optimal execution windows based on history"""
        # Get successful executions for this task
        task_history = [
            r for r in self.execution_history
            if r['task'] == task_name and r['success'] and not r['resources_waited']
        ]
        
        if len(task_history) < 10:
            return  # Not enough data
        
        # Group by hour and calculate success rate
        hour_success: Dict[int, List[bool]] = {}
        for record in task_history:
            hour = record['hour']
            if hour not in hour_success:
                hour_success[hour] = []
            hour_success[hour].append(True)
        
        # Find consecutive hours with high success
        windows = []
        current_window = None
        
        for hour in range(24):
            success_count = len(hour_success.get(hour, []))
            
            if success_count >= 3:  # At least 3 successful executions
                if current_window is None:
                    current_window = [hour, hour]
                else:
                    current_window[1] = hour
            else:
                if current_window:
                    windows.append(tuple(current_window))
                    current_window = None
        
        if current_window:
            windows.append(tuple(current_window))
        
        self.optimal_windows[task_name] = windows
        logger.debug(f"Updated optimal windows for {task_name}: {windows}")
    
    def is_optimal_time(self, task_name: str) -> bool:
        """Check if current time is optimal for task"""
        current_hour = datetime.now().hour
        
        windows = self.optimal_windows.get(task_name, [])
        if not windows:
            return True  # No data yet, assume any time is fine
        
        for start, end in windows:
            if start <= current_hour <= end:
                return True
        
        return False
    
    def get_next_optimal_time(self, task_name: str) -> Optional[datetime]:
        """Get next optimal execution time"""
        windows = self.optimal_windows.get(task_name, [])
        if not windows:
            return None
        
        current_hour = datetime.now().hour
        now = datetime.now()
        
        # Find next window
        for start, end in sorted(windows):
            if start > current_hour:
                # Next window today
                return now.replace(hour=start, minute=0, second=0, microsecond=0)
        
        # Next window tomorrow
        first_window = sorted(windows)[0]
        return (now + timedelta(days=1)).replace(
            hour=first_window[0], 
            minute=0, 
            second=0, 
            microsecond=0
        )


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Create monitor
    limits = ResourceLimits(
        max_cpu_percent=70.0,
        max_memory_percent=80.0,
        max_ollama_concurrent=2
    )
    
    monitor = ResourceMonitor(limits=limits, poll_interval=1.0)
    monitor.start()
    
    # Create pause controller
    pause_ctrl = PauseController()
    
    # Create adaptive scheduler
    scheduler = AdaptiveScheduler(monitor)
    
    try:
        # Wait for idle state
        print("Waiting for idle state...")
        while not monitor.is_idle():
            time.sleep(1)
        
        print("System is idle!")
        
        # Try to acquire resources for background task
        print("\nAcquiring resources for OPPORTUNISTIC task...")
        with ResourceGuard(monitor, ResourcePriority.OPPORTUNISTIC):
            print("Resources acquired! Doing work...")
            time.sleep(5)
        
        print("Resources released!")
        
        # Test pause/resume
        print("\nTesting pause/resume...")
        pause_ctrl.pause(ResourcePriority.LOW)
        print(f"LOW priority paused: {pause_ctrl.is_paused(ResourcePriority.LOW)}")
        
        pause_ctrl.resume(ResourcePriority.LOW)
        print(f"LOW priority paused: {pause_ctrl.is_paused(ResourcePriority.LOW)}")
        
    finally:
        monitor.stop()