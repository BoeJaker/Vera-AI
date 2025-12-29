#!/usr/bin/env python3
"""
Proactive Focus Background Service
===================================
Intelligent background service that orchestrates proactive thinking.

Features:
- Runs when system is idle
- Resource-aware execution
- Calendar-driven scheduling
- Automatic pause/resume
- Seamless integration with all components
- Adaptive learning and optimization
"""

import time
import threading
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

from Vera.ProactiveFocus.manager import (
    ResourceMonitor, ResourceLimits, ResourcePriority,
    PauseController, AdaptiveScheduler, ResourceGuard
)

@dataclass
class ServiceConfig:
    """Configuration for background service"""
    # Resource management
    max_cpu_percent: float = 50.0
    max_memory_percent: float = 70.0
    min_idle_seconds: float = 30.0  # Wait this long before starting
    
    # Scheduling
    check_interval: float = 30.0  # How often to check if we should run
    session_duration_minutes: int = 30  # Default session duration
    
    # Stage configuration
    enabled_stages: List[str] = None  # None = all stages
    default_stage_order: List[str] = None
    
    # Calendar integration
    use_calendar: bool = True
    reschedule_on_conflict: bool = True
    
    # Learning
    learn_optimal_times: bool = True
    adapt_to_usage: bool = True
    
    def __post_init__(self):
        if self.enabled_stages is None:
            self.enabled_stages = [
                "Introspection",
                "Research",
                "Evaluation",
                "Optimization",
                "Steering"
            ]
        
        if self.default_stage_order is None:
            self.default_stage_order = self.enabled_stages.copy()


class BackgroundService:
    """Main background service for proactive focus"""
    
    def __init__(
        self,
        focus_manager,
        config: Optional[ServiceConfig] = None
    ):
        """
        Initialize background service.
        
        Args:
            focus_manager: ProactiveFocusManager instance
            config: Service configuration
        """
        self.focus_manager = focus_manager
        self.config = config or ServiceConfig()
        
        # Import components
        from Vera.ProactiveFocus.stages import StageOrchestrator
        from Vera.ProactiveFocus.schedule import CalendarScheduler
        from Vera.ProactiveFocus.resources import ExternalResourceManager
        
        # Resource management
        limits = ResourceLimits(
            max_cpu_percent=self.config.max_cpu_percent,
            max_memory_percent=self.config.max_memory_percent
        )
        
        self.resource_monitor = ResourceMonitor(limits=limits, poll_interval=2.0)
        self.pause_controller = PauseController()
        self.adaptive_scheduler = AdaptiveScheduler(self.resource_monitor)
        
        # Stage orchestration
        self.stage_orchestrator = StageOrchestrator()
        
        # Disable stages not in config
        for stage_name in list(self.stage_orchestrator.stages.keys()):
            if stage_name not in self.config.enabled_stages:
                self.stage_orchestrator.disable_stage(stage_name)
        
        # Calendar integration
        if self.config.use_calendar:
            self.calendar_scheduler = CalendarScheduler()
        else:
            self.calendar_scheduler = None
        
        # External resources
        self.resource_manager = ExternalResourceManager(
            hybrid_memory=getattr(focus_manager, 'hybrid_memory', None)
        )
        
        # Service state
        self.running = False
        self.service_thread: Optional[threading.Thread] = None
        self.last_execution: Optional[datetime] = None
        self.execution_count = 0
        
        # Callbacks
        self.on_session_start: Optional[Callable] = None
        self.on_session_complete: Optional[Callable] = None
        self.on_stage_complete: Optional[Callable] = None
        
        logger.info("Background service initialized")
    
    def start(self):
        """Start the background service"""
        if self.running:
            logger.warning("Service already running")
            return
        
        self.running = True
        
        # Start resource monitor
        self.resource_monitor.start()
        
        # Start service thread
        self.service_thread = threading.Thread(
            target=self._service_loop,
            daemon=True,
            name="ProactiveFocusService"
        )
        self.service_thread.start()
        
        logger.info("✓ Background service started")
    
    def stop(self):
        """Stop the background service"""
        if not self.running:
            return
        
        logger.info("Stopping background service...")
        
        self.running = False
        
        # Stop resource monitor
        self.resource_monitor.stop()
        
        # Wait for thread
        if self.service_thread:
            self.service_thread.join(timeout=10.0)
        
        logger.info("✓ Background service stopped")
    
    def pause(self):
        """Pause proactive thinking"""
        self.pause_controller.pause(ResourcePriority.OPPORTUNISTIC)
        logger.info("⏸ Proactive thinking paused")
    
    def resume(self):
        """Resume proactive thinking"""
        self.pause_controller.resume(ResourcePriority.OPPORTUNISTIC)
        logger.info("▶ Proactive thinking resumed")
    
    def trigger_manual_session(
        self,
        stages: Optional[List[str]] = None,
        wait_for_resources: bool = True
    ) -> Dict[str, Any]:
        """
        Manually trigger a proactive thinking session.
        
        Args:
            stages: Specific stages to run (None = all enabled)
            wait_for_resources: Whether to wait for resources
        
        Returns:
            Session results
        """
        logger.info("Manual session triggered")
        
        return self._execute_session(
            stages=stages,
            priority=ResourcePriority.NORMAL,
            wait_for_resources=wait_for_resources,
            manual=True
        )
    
    def _service_loop(self):
        """Main service loop"""
        logger.info("Service loop started")
        
        idle_start: Optional[datetime] = None
        
        while self.running:
            try:
                # Check pause
                if self.pause_controller.is_paused(ResourcePriority.OPPORTUNISTIC):
                    logger.debug("Service paused, waiting...")
                    self.pause_controller.wait(ResourcePriority.OPPORTUNISTIC, timeout=5.0)
                    continue
                
                # Check if we have a focus
                if not self.focus_manager.focus:
                    logger.debug("No active focus, waiting...")
                    time.sleep(self.config.check_interval)
                    continue
                
                # Check if system is idle
                if self.resource_monitor.is_idle():
                    if idle_start is None:
                        idle_start = datetime.now()
                        logger.debug("System became idle")
                    
                    # Check if we've been idle long enough
                    idle_duration = (datetime.now() - idle_start).total_seconds()
                    
                    if idle_duration >= self.config.min_idle_seconds:
                        # Check calendar for scheduled sessions
                        should_run = True
                        scheduled_stages = None
                        
                        if self.calendar_scheduler:
                            next_session = self.calendar_scheduler.get_next_thought_session()
                            
                            if next_session:
                                # Check if session is due
                                time_until = (next_session.begin - datetime.now()).total_seconds()
                                
                                if -300 <= time_until <= 0:  # Within 5 minutes past due
                                    logger.info(f"Scheduled session due: {next_session.name}")
                                    scheduled_stages = next_session.stages
                                    should_run = True
                                elif time_until > 0 and time_until < self.config.check_interval * 2:
                                    # Session coming up soon, wait for it
                                    logger.debug(f"Session in {time_until:.0f}s, waiting...")
                                    should_run = False
                        
                        # Check adaptive scheduler for optimal time
                        if should_run and self.config.learn_optimal_times:
                            task_name = f"proactive_{self.focus_manager.focus[:30]}"
                            
                            if not self.adaptive_scheduler.is_optimal_time(task_name):
                                logger.debug("Not optimal time for proactive thinking")
                                should_run = False
                        
                        # Execute session if appropriate
                        if should_run:
                            self._execute_session(
                                stages=scheduled_stages,
                                priority=ResourcePriority.OPPORTUNISTIC
                            )
                            
                            # Reset idle timer
                            idle_start = None
                
                else:
                    # Not idle
                    if idle_start is not None:
                        idle_duration = (datetime.now() - idle_start).total_seconds()
                        logger.debug(f"System no longer idle after {idle_duration:.0f}s")
                    
                    idle_start = None
                
                # Sleep before next check
                time.sleep(self.config.check_interval)
                
            except Exception as e:
                logger.error(f"Service loop error: {e}", exc_info=True)
                time.sleep(self.config.check_interval)
    
    def _execute_session(
        self,
        stages: Optional[List[str]] = None,
        priority: ResourcePriority = ResourcePriority.OPPORTUNISTIC,
        wait_for_resources: bool = True,
        manual: bool = False
    ) -> Dict[str, Any]:
        """Execute a proactive thinking session"""
        session_start = time.time()
        session_id = f"session_{int(session_start * 1000)}"
        
        logger.info(f"{'='*60}")
        logger.info(f"Starting proactive session: {session_id}")
        logger.info(f"Focus: {self.focus_manager.focus}")
        logger.info(f"Priority: {priority.name}")
        logger.info(f"Stages: {stages or 'all enabled'}")
        logger.info(f"{'='*60}")
        
        result = {
            'session_id': session_id,
            'focus': self.focus_manager.focus,
            'start_time': datetime.fromtimestamp(session_start).isoformat(),
            'manual': manual,
            'success': False,
            'stages_completed': [],
            'stage_results': {},
            'total_duration': 0.0,
            'resource_wait_time': 0.0
        }
        
        try:
            # Callback
            if self.on_session_start:
                self.on_session_start(session_id, self.focus_manager.focus)
            
            # Wait for resources
            resource_wait_start = time.time()
            
            with ResourceGuard(
                self.resource_monitor,
                priority=priority,
                wait_for_resources=wait_for_resources,
                timeout=300.0  # 5 minute timeout
            ) as guard:
                resource_wait_time = time.time() - resource_wait_start
                result['resource_wait_time'] = resource_wait_time
                
                if resource_wait_time > 1.0:
                    logger.info(f"Waited {resource_wait_time:.1f}s for resources")
                
                # Determine stages to run
                if stages is None:
                    stages = self.config.default_stage_order
                
                # Execute stage pipeline
                stage_results = self.stage_orchestrator.execute_pipeline(
                    self.focus_manager,
                    stage_names=stages
                )
                
                # Process results
                for stage_name, stage_output in stage_results.items():
                    result['stages_completed'].append(stage_name)
                    result['stage_results'][stage_name] = stage_output.to_dict()
                    
                    # Callback
                    if self.on_stage_complete:
                        self.on_stage_complete(session_id, stage_name, stage_output)
                
                result['success'] = True
                
                logger.info(f"Session complete: {len(stage_results)} stages executed")
        
        except Exception as e:
            logger.error(f"Session failed: {e}", exc_info=True)
            result['error'] = str(e)
        
        finally:
            # Calculate duration
            session_duration = time.time() - session_start
            result['total_duration'] = session_duration
            result['end_time'] = datetime.now().isoformat()
            
            # Update tracking
            self.last_execution = datetime.now()
            self.execution_count += 1
            
            # Record for adaptive learning
            if self.config.learn_optimal_times:
                task_name = f"proactive_{self.focus_manager.focus[:30]}"
                self.adaptive_scheduler.record_execution(
                    task_name=task_name,
                    duration=session_duration,
                    success=result['success'],
                    resources_waited=(result['resource_wait_time'] > 1.0)
                )
            
            # Save focus board
            try:
                self.focus_manager.save_focus_board()
            except Exception as e:
                logger.error(f"Failed to save focus board: {e}")
            
            # Callback
            if self.on_session_complete:
                self.on_session_complete(session_id, result)
            
            logger.info(f"{'='*60}")
            logger.info(f"Session {session_id} complete")
            logger.info(f"Duration: {session_duration:.1f}s")
            logger.info(f"Success: {result['success']}")
            logger.info(f"Stages: {len(result['stages_completed'])}/{len(stages)}")
            logger.info(f"{'='*60}")
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            'running': self.running,
            'focus': self.focus_manager.focus,
            'paused': self.pause_controller.is_paused(ResourcePriority.OPPORTUNISTIC),
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
            'execution_count': self.execution_count,
            'resource_state': self.resource_monitor.get_state().to_dict() if self.resource_monitor.get_state() else None,
            'enabled_stages': self.config.enabled_stages,
            'next_scheduled': None
        }
    
    def get_next_scheduled_session(self) -> Optional[Dict[str, Any]]:
        """Get next scheduled session from calendar"""
        if not self.calendar_scheduler:
            return None
        
        next_session = self.calendar_scheduler.get_next_thought_session()
        
        if next_session:
            return {
                'focus': next_session.focus,
                'start_time': next_session.begin.isoformat(),
                'duration_minutes': (next_session.end - next_session.begin).total_seconds() / 60,
                'stages': next_session.stages,
                'priority': next_session.priority
            }
        
        return None
    
    def schedule_session(
        self,
        focus: Optional[str] = None,
        start_time: Optional[datetime] = None,
        duration_minutes: int = 30,
        stages: Optional[List[str]] = None,
        recurrence: Optional[str] = None
    ) -> bool:
        """
        Schedule a proactive thinking session.
        
        Args:
            focus: Focus for session (None = use current)
            start_time: When to start (None = suggest optimal time)
            duration_minutes: Session duration
            stages: Stages to run (None = all)
            recurrence: Recurrence rule
        
        Returns:
            True if scheduled successfully
        """
        if not self.calendar_scheduler:
            logger.error("Calendar scheduler not enabled")
            return False
        
        # Use current focus if not specified
        if focus is None:
            focus = self.focus_manager.focus
            
            if not focus:
                logger.error("No focus specified or active")
                return False
        
        # Suggest optimal time if not specified
        if start_time is None:
            start_time = self.calendar_scheduler.suggest_optimal_time(
                duration_minutes=duration_minutes,
                days_ahead=7
            )
            
            if not start_time:
                logger.warning("Could not find optimal time, using default")
                start_time = datetime.now() + timedelta(hours=1)
        
        # Schedule
        try:
            event = self.calendar_scheduler.schedule_thought_session(
                focus=focus,
                start_time=start_time,
                duration_minutes=duration_minutes,
                stages=stages,
                recurrence=recurrence
            )
            
            logger.info(f"✓ Scheduled session: {focus} at {start_time}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule session: {e}")
            return False


# Example usage
if __name__ == "__main__":
    import sys
    import os
    
    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Mock focus manager for testing
    class MockFocusManager:
        def __init__(self):
            self.focus = "Test Project"
            self.focus_board = {
                "progress": [],
                "next_steps": [],
                "issues": [],
                "ideas": [],
                "actions": [],
                "completed": []
            }
            
            class MockAgent:
                def __init__(self):
                    self.tools = []
                    
                    class MockLLM:
                        def stream(self, prompt):
                            yield "Test response"
                    
                    self.fast_llm = MockLLM()
                    self.deep_llm = MockLLM()
                    self.reasoning_llm = MockLLM()
            
            self.agent = MockAgent()
        
        def add_to_focus_board(self, category, note, metadata=None):
            self.focus_board[category].append({
                "note": note,
                "metadata": metadata or {}
            })
        
        def save_focus_board(self):
            pass
    
    # Create service
    config = ServiceConfig(
        max_cpu_percent=50.0,
        check_interval=10.0,
        min_idle_seconds=5.0,
        use_calendar=False  # Disable for test
    )
    
    focus_manager = MockFocusManager()
    service = BackgroundService(focus_manager, config=config)
    
    # Set up callbacks
    def on_start(session_id, focus):
        print(f"\n🎯 Session started: {session_id} - {focus}")
    
    def on_stage(session_id, stage_name, output):
        print(f"  ✓ Stage complete: {stage_name} ({output.duration:.1f}s)")
    
    def on_complete(session_id, result):
        print(f"✅ Session complete: {session_id}")
        print(f"   Duration: {result['total_duration']:.1f}s")
        print(f"   Stages: {len(result['stages_completed'])}")
    
    service.on_session_start = on_start
    service.on_stage_complete = on_stage
    service.on_session_complete = on_complete
    
    # Start service
    print("Starting background service...")
    service.start()
    
    try:
        # Let it run
        print("\nService running. Press Ctrl+C to stop.\n")
        
        # Trigger manual session after a few seconds
        time.sleep(3)
        print("\nTriggering manual session...")
        result = service.trigger_manual_session(
            stages=["Introspection", "Research"],
            wait_for_resources=False
        )
        
        print("\nManual session result:")
        print(f"  Success: {result['success']}")
        print(f"  Duration: {result['total_duration']:.1f}s")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nStopping service...")
        service.stop()
        print("Service stopped.")