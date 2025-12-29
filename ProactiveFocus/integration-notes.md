#!/usr/bin/env python3
"""
Enhanced Proactive Focus Manager - Integration Guide
====================================================
This file demonstrates how to integrate all the enhanced components
with the original ProactiveFocusManager.

New Components:
1. Resource Manager - Intelligent resource awareness
2. External Resources - URLs, files, folders, memories, notebooks
3. Modular Stages - Research, Evaluation, Optimization, Steering, Introspection
4. Calendar Integration - Schedule proactive thoughts
5. Background Service - Intelligent background execution

Usage Examples:
- Basic setup with all components
- Scheduling proactive thoughts
- Adding external resources to focus board
- Custom stage pipelines
- Resource-aware execution
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Import original ProactiveFocusManager
from proactive_focus_manager_enhanced import ProactiveFocusManager

# Import new components
from proactive_focus_resource_manager import (
    ResourceMonitor, ResourceLimits, ResourcePriority,
    PauseController, AdaptiveScheduler, ResourceGuard
)

from proactive_focus_external_resources import (
    ExternalResourceManager, ResourceType, NotebookResource
)

from proactive_focus_stages import (
    StageOrchestrator, ResearchStage, EvaluationStage,
    OptimizationStage, SteeringStage, IntrospectionStage
)

from proactive_focus_calendar import CalendarScheduler, ProactiveThoughtEvent

from proactive_focus_service import BackgroundService, ServiceConfig


# ============================================================================
# SETUP LOGGING
# ============================================================================

def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('proactive_focus.log')
        ]
    )


# ============================================================================
# EXAMPLE 1: Basic Setup with All Components
# ============================================================================

def example_basic_setup(vera_instance):
    """
    Basic setup example showing all components working together.
    
    Args:
        vera_instance: Your Vera instance with agent, memory, etc.
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Setup")
    print("="*60 + "\n")
    
    # 1. Create original focus manager
    focus_manager = ProactiveFocusManager(
        agent=vera_instance,
        hybrid_memory=vera_instance.mem if hasattr(vera_instance, 'mem') else None,
        proactive_interval=600,  # 10 minutes
        cpu_threshold=70.0
    )
    
    # 2. Set focus
    focus_manager.set_focus("Vera AI Enhancement Project")
    
    # 3. Create resource manager
    resource_limits = ResourceLimits(
        max_cpu_percent=70.0,
        max_memory_percent=80.0,
        max_ollama_concurrent=2
    )
    
    resource_monitor = ResourceMonitor(limits=resource_limits)
    resource_monitor.start()
    
    # 4. Create external resource manager
    resource_manager = ExternalResourceManager(
        hybrid_memory=vera_instance.mem if hasattr(vera_instance, 'mem') else None
    )
    
    # 5. Create stage orchestrator
    stage_orchestrator = StageOrchestrator()
    
    # 6. Create calendar scheduler
    calendar_scheduler = CalendarScheduler()
    
    # 7. Create background service
    service_config = ServiceConfig(
        max_cpu_percent=50.0,
        check_interval=30.0,
        min_idle_seconds=30.0,
        use_calendar=True,
        enabled_stages=["Introspection", "Research", "Evaluation", "Steering"]
    )
    
    background_service = BackgroundService(
        focus_manager=focus_manager,
        config=service_config
    )
    
    print("✓ All components initialized")
    print(f"  Focus: {focus_manager.focus}")
    print(f"  Resource monitor: Running")
    print(f"  Stages: {len(stage_orchestrator.stages)}")
    print(f"  Calendar: Enabled")
    
    return {
        'focus_manager': focus_manager,
        'resource_monitor': resource_monitor,
        'resource_manager': resource_manager,
        'stage_orchestrator': stage_orchestrator,
        'calendar_scheduler': calendar_scheduler,
        'background_service': background_service
    }


# ============================================================================
# EXAMPLE 2: Adding External Resources
# ============================================================================

def example_external_resources(components):
    """
    Example of adding various external resources to focus board.
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: External Resources")
    print("="*60 + "\n")
    
    resource_manager = components['resource_manager']
    focus_manager = components['focus_manager']
    
    # Add a URL
    url_meta = resource_manager.add_resource(
        "https://github.com/anthropics/anthropic-sdk-python"
    )
    print(f"✓ Added URL: {url_meta.title}")
    
    # Link to focus board
    resource_manager.link_to_focus_board(
        url_meta.resource_id,
        "progress",
        focus_manager
    )
    print(f"  Linked to focus board (progress)")
    
    # Add a local file (if exists)
    readme_path = "./README.md"
    if os.path.exists(readme_path):
        file_meta = resource_manager.add_resource(readme_path)
        print(f"\n✓ Added file: {file_meta.title}")
        print(f"  Size: {file_meta.file_size} bytes")
        
        resource_manager.link_to_focus_board(
            file_meta.resource_id,
            "next_steps",
            focus_manager
        )
    
    # Add a folder
    folder_path = "./Output"
    if os.path.exists(folder_path):
        folder_meta = resource_manager.add_resource(folder_path)
        print(f"\n✓ Added folder: {folder_meta.title}")
        print(f"  Files: {folder_meta.custom_metadata.get('file_count', 0)}")
    
    # List notebooks
    notebooks = NotebookResource.list_notebooks()
    print(f"\n✓ Found {len(notebooks)} notebooks")
    
    for nb in notebooks[:3]:
        nb_meta = resource_manager.add_resource(
            nb['path'],
            resource_type=ResourceType.NOTEBOOK
        )
        print(f"  - {nb_meta.title} ({nb.get('note_count', 0)} notes)")
    
    # List all resources
    all_resources = resource_manager.list_resources()
    print(f"\n✓ Total resources: {len(all_resources)}")


# ============================================================================
# EXAMPLE 3: Calendar Integration
# ============================================================================

def example_calendar_integration(components):
    """
    Example of scheduling proactive thoughts via calendar.
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Calendar Integration")
    print("="*60 + "\n")
    
    calendar_scheduler = components['calendar_scheduler']
    focus_manager = components['focus_manager']
    
    # Schedule a one-time session
    tomorrow_2pm = datetime.now().replace(
        hour=14, 
        minute=0, 
        second=0, 
        microsecond=0
    ) + timedelta(days=1)
    
    event = calendar_scheduler.schedule_thought_session(
        focus=focus_manager.focus,
        start_time=tomorrow_2pm,
        duration_minutes=30,
        stages=["Research", "Evaluation", "Steering"],
        priority="high"
    )
    
    print(f"✓ Scheduled one-time session:")
    print(f"  Time: {event.begin}")
    print(f"  Duration: 30 minutes")
    print(f"  Stages: {', '.join(event.stages)}")
    
    # Schedule daily sessions for a week
    daily_events = calendar_scheduler.schedule_daily_thoughts(
        focus=focus_manager.focus,
        start_time="09:00",  # 9 AM daily
        duration_minutes=15,
        days=7,
        stages=["Introspection", "Evaluation"]
    )
    
    print(f"\n✓ Scheduled {len(daily_events)} daily sessions")
    print(f"  Time: 09:00 daily")
    print(f"  Duration: 15 minutes")
    print(f"  Stages: Introspection, Evaluation")
    
    # Schedule weekly deep dives
    weekly_events = calendar_scheduler.schedule_weekly_thoughts(
        focus=focus_manager.focus,
        day_of_week=4,  # Friday
        start_time="15:00",
        duration_minutes=60,
        weeks=4,
        stages=["Introspection", "Research", "Evaluation", "Optimization", "Steering"]
    )
    
    print(f"\n✓ Scheduled {len(weekly_events)} weekly sessions")
    print(f"  Day: Friday at 15:00")
    print(f"  Duration: 60 minutes")
    print(f"  Stages: Full pipeline")
    
    # Get upcoming sessions
    upcoming = calendar_scheduler.get_upcoming_thought_sessions(days_ahead=7)
    
    print(f"\n✓ Upcoming sessions (next 7 days): {len(upcoming)}")
    for session in upcoming[:5]:
        print(f"  - {session.begin.strftime('%Y-%m-%d %H:%M')}: {session.focus[:40]}")
    
    # Suggest optimal time
    optimal_time = calendar_scheduler.suggest_optimal_time(
        duration_minutes=30,
        days_ahead=3
    )
    
    if optimal_time:
        print(f"\n✓ Suggested optimal time: {optimal_time}")


# ============================================================================
# EXAMPLE 4: Custom Stage Pipeline
# ============================================================================

def example_custom_stages(components):
    """
    Example of creating and running custom stage pipelines.
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Custom Stage Pipeline")
    print("="*60 + "\n")
    
    stage_orchestrator = components['stage_orchestrator']
    focus_manager = components['focus_manager']
    
    # Create custom pipeline for quick check-in
    quick_checkin = ["Introspection", "Evaluation"]
    
    print("Running quick check-in pipeline...")
    print(f"Stages: {', '.join(quick_checkin)}\n")
    
    results = stage_orchestrator.execute_pipeline(
        focus_manager,
        stage_names=quick_checkin
    )
    
    for stage_name, output in results.items():
        print(f"✓ {stage_name}:")
        print(f"  Result: {output.result.value}")
        print(f"  Duration: {output.duration:.2f}s")
        print(f"  Insights: {len(output.insights)}")
        print(f"  Next steps: {len(output.next_steps)}")
        print(f"  Issues: {len(output.issues)}")
        print()
    
    # Create custom pipeline for deep analysis
    deep_analysis = ["Introspection", "Research", "Optimization"]
    
    print("\nRunning deep analysis pipeline...")
    print(f"Stages: {', '.join(deep_analysis)}\n")
    
    results = stage_orchestrator.execute_pipeline(
        focus_manager,
        stage_names=deep_analysis
    )
    
    for stage_name, output in results.items():
        print(f"✓ {stage_name}: {output.result.value} ({output.duration:.2f}s)")


# ============================================================================
# EXAMPLE 5: Resource-Aware Execution
# ============================================================================

def example_resource_aware(components):
    """
    Example of resource-aware execution with priority management.
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Resource-Aware Execution")
    print("="*60 + "\n")
    
    resource_monitor = components['resource_monitor']
    stage_orchestrator = components['stage_orchestrator']
    focus_manager = components['focus_manager']
    
    # Check current resources
    state = resource_monitor.get_state()
    
    if state:
        print("Current system state:")
        print(f"  CPU: {state.cpu_percent:.1f}%")
        print(f"  Memory: {state.memory_percent:.1f}%")
        print(f"  Available RAM: {state.memory_available_mb:.0f} MB")
        print(f"  Ollama processes: {state.ollama_processes}")
        print()
    
    # Execute with resource guard (opportunistic priority)
    print("Attempting opportunistic execution...")
    
    try:
        with ResourceGuard(
            resource_monitor,
            priority=ResourcePriority.OPPORTUNISTIC,
            wait_for_resources=True,
            timeout=10.0
        ):
            print("✓ Resources acquired!")
            
            # Run a single stage
            results = stage_orchestrator.execute_pipeline(
                focus_manager,
                stage_names=["Introspection"]
            )
            
            print(f"✓ Execution complete")
            
    except Exception as e:
        print(f"✗ Could not acquire resources: {e}")
    
    # Execute with higher priority
    print("\nAttempting high-priority execution...")
    
    try:
        with ResourceGuard(
            resource_monitor,
            priority=ResourcePriority.HIGH,
            wait_for_resources=False
        ):
            print("✓ High-priority resources acquired!")
            
    except Exception as e:
        print(f"✗ Resources not available: {e}")


# ============================================================================
# EXAMPLE 6: Background Service
# ============================================================================

def example_background_service(components):
    """
    Example of using the background service.
    """
    print("\n" + "="*60)
    print("EXAMPLE 6: Background Service")
    print("="*60 + "\n")
    
    background_service = components['background_service']
    
    # Set up callbacks
    def on_session_start(session_id, focus):
        print(f"\n🎯 Session started: {session_id}")
        print(f"   Focus: {focus}")
    
    def on_stage_complete(session_id, stage_name, output):
        print(f"  ✓ {stage_name} complete ({output.duration:.1f}s)")
    
    def on_session_complete(session_id, result):
        print(f"\n✅ Session complete: {session_id}")
        print(f"   Duration: {result['total_duration']:.1f}s")
        print(f"   Stages: {len(result['stages_completed'])}")
        print(f"   Success: {result['success']}")
    
    background_service.on_session_start = on_session_start
    background_service.on_stage_complete = on_stage_complete
    background_service.on_session_complete = on_session_complete
    
    # Start service
    print("Starting background service...")
    background_service.start()
    print("✓ Service started")
    
    # Get status
    status = background_service.get_status()
    print(f"\nService status:")
    print(f"  Running: {status['running']}")
    print(f"  Focus: {status['focus']}")
    print(f"  Paused: {status['paused']}")
    print(f"  Executions: {status['execution_count']}")
    
    # Trigger manual session
    print("\nTriggering manual session...")
    result = background_service.trigger_manual_session(
        stages=["Introspection", "Research"],
        wait_for_resources=False
    )
    
    # Schedule a session
    scheduled = background_service.schedule_session(
        start_time=datetime.now() + timedelta(hours=1),
        duration_minutes=30,
        stages=["Research", "Evaluation", "Steering"]
    )
    
    if scheduled:
        print("\n✓ Scheduled session for 1 hour from now")
    
    # Note: In production, you'd keep the service running
    # For this example, we'll stop it
    print("\nStopping service (in production, this would keep running)...")
    background_service.stop()
    print("✓ Service stopped")


# ============================================================================
# MAIN INTEGRATION EXAMPLE
# ============================================================================

def main():
    """
    Main integration example showing complete workflow.
    """
    print("\n" + "="*80)
    print("ENHANCED PROACTIVE FOCUS MANAGER - INTEGRATION GUIDE")
    print("="*80)
    
    setup_logging(level=logging.INFO)
    
    # Note: In production, you'd pass your actual Vera instance
    # For this example, we'll create a mock
    
    class MockVera:
        """Mock Vera instance for demonstration"""
        def __init__(self):
            class MockAgent:
                def __init__(self):
                    self.tools = []
                    
                    class MockLLM:
                        def stream(self, prompt):
                            yield "This is a test response. "
                            yield "It demonstrates streaming. "
                            yield "In production, this would be a real LLM."
                    
                    self.fast_llm = MockLLM()
                    self.deep_llm = MockLLM()
                    self.reasoning_llm = MockLLM()
            
            class MockMem:
                def focus_context(self, session_id, query, k=5):
                    return []
                
                def semantic_retrieve(self, query, k=5):
                    return []
            
            class MockSess:
                id = "mock_session_123"
            
            self.agent = MockAgent()
            self.mem = MockMem()
            self.sess = MockSess()
            self.tools = []
            
            # LLM shortcuts
            self.fast_llm = self.agent.fast_llm
            self.deep_llm = self.agent.deep_llm
            self.reasoning_llm = self.agent.reasoning_llm
    
    vera = MockVera()
    
    # Run examples
    try:
        # Example 1: Basic setup
        components = example_basic_setup(vera)
        
        # Example 2: External resources
        example_external_resources(components)
        
        # Example 3: Calendar integration
        example_calendar_integration(components)
        
        # Example 4: Custom stages
        example_custom_stages(components)
        
        # Example 5: Resource-aware execution
        example_resource_aware(components)
        
        # Example 6: Background service
        example_background_service(components)
        
        print("\n" + "="*80)
        print("ALL EXAMPLES COMPLETE")
        print("="*80 + "\n")
        
    finally:
        # Cleanup
        if 'resource_monitor' in components:
            components['resource_monitor'].stop()


if __name__ == "__main__":
    main()


# ============================================================================
# PRODUCTION USAGE NOTES
# ============================================================================

"""
PRODUCTION INTEGRATION STEPS:
==============================

1. **Basic Setup**:
   ```python
   from proactive_focus_manager_enhanced import ProactiveFocusManager
   from proactive_focus_service import BackgroundService, ServiceConfig
   
   # Create focus manager
   focus_manager = ProactiveFocusManager(
       agent=vera,
       hybrid_memory=vera.mem,
       proactive_interval=600
   )
   
   # Create background service
   service = BackgroundService(focus_manager)
   service.start()
   ```

2. **With Calendar Scheduling**:
   ```python
   service.schedule_session(
       start_time=datetime.now() + timedelta(hours=1),
       duration_minutes=30,
       stages=["Research", "Evaluation"]
   )
   ```

3. **With External Resources**:
   ```python
   from proactive_focus_external_resources import ExternalResourceManager
   
   resources = ExternalResourceManager(hybrid_memory=vera.mem)
   
   # Add resources
   url_meta = resources.add_resource("https://example.com")
   file_meta = resources.add_resource("/path/to/file.txt")
   
   # Link to focus board
   resources.link_to_focus_board(url_meta.resource_id, "progress", focus_manager)
   ```

4. **Custom Stage Pipeline**:
   ```python
   from proactive_focus_stages import StageOrchestrator
   
   orchestrator = StageOrchestrator()
   
   # Run custom pipeline
   results = orchestrator.execute_pipeline(
       focus_manager,
       stage_names=["Introspection", "Research", "Steering"]
   )
   ```

5. **Resource-Aware Execution**:
   ```python
   from proactive_focus_resource_manager import ResourceGuard, ResourcePriority
   
   with ResourceGuard(service.resource_monitor, ResourcePriority.OPPORTUNISTIC):
       # Execute proactive thought
       results = orchestrator.execute_pipeline(focus_manager)
   ```

6. **Pause/Resume**:
   ```python
   # Pause proactive thinking (e.g., user is working)
   service.pause()
   
   # Resume when idle
   service.resume()
   ```

CONFIGURATION OPTIONS:
======================

1. **Service Config**:
   ```python
   config = ServiceConfig(
       max_cpu_percent=50.0,        # Max CPU for opportunistic tasks
       check_interval=30.0,          # How often to check (seconds)
       min_idle_seconds=30.0,        # Wait before starting
       enabled_stages=[...],         # Which stages to enable
       use_calendar=True,            # Use calendar scheduling
       learn_optimal_times=True      # Learn best execution times
   )
   ```

2. **Resource Limits**:
   ```python
   limits = ResourceLimits(
       max_cpu_percent=70.0,
       max_memory_percent=80.0,
       max_ollama_concurrent=2,
       min_free_memory_mb=2048
   )
   ```

3. **Stage Configuration**:
   ```python
   # Enable/disable specific stages
   orchestrator.disable_stage("Optimization")
   orchestrator.enable_stage("Research")
   
   # Add custom stage
   from proactive_focus_stages import ProactiveStage
   orchestrator.add_stage(MyCustomStage())
   ```

INTEGRATION WITH FASTAPI:
=========================

The focus.py API already has endpoints. To integrate enhanced features:

1. Add to focus.py:
   ```python
   from proactive_focus_service import BackgroundService
   
   # Global service instance
   background_services = {}
   
   @router.post("/{session_id}/service/start")
   async def start_background_service(session_id: str):
       vera = get_or_create_vera(session_id)
       service = BackgroundService(vera.focus_manager)
       service.start()
       background_services[session_id] = service
       return {"status": "started"}
   ```

2. Resource management endpoint:
   ```python
   @router.post("/{session_id}/resources/add")
   async def add_resource(session_id: str, uri: str):
       service = background_services.get(session_id)
       if service:
           meta = service.resource_manager.add_resource(uri)
           return meta.to_dict()
   ```

3. Calendar endpoints:
   ```python
   @router.post("/{session_id}/schedule")
   async def schedule_session(session_id: str, request: dict):
       service = background_services.get(session_id)
       if service:
           scheduled = service.schedule_session(
               start_time=datetime.fromisoformat(request['start_time']),
               duration_minutes=request.get('duration', 30)
           )
           return {"scheduled": scheduled}
   ```
"""