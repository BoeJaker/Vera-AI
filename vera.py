#!/usr/bin/env python3
# Vera.py - Vera with Unified Logging System

"""
Vera - AI System
Multi-agent system with proactive focus management, tool execution,
and infrastructure-aware task orchestration.

NEW: Unified logging system with configurable verbosity and rich formatting
"""

# --- Imports ---
import queue
import sys, os, io
import subprocess
import json
from typing import List, Dict, Any, Type, Optional, Callable, Iterator, Union
import threading
import time
import psutil
import re
import traceback
import ollama
import requests
from collections.abc import Iterator
from urllib.parse import quote_plus, quote
import asyncio
import hashlib
from playwright.async_api import async_playwright
from langchain_core.outputs import GenerationChunk
from langchain.llms.base import LLM
from langchain_core.tools import tool
from langchain_community.llms import Ollama
from langchain.agents import (
    initialize_agent, 
    Tool, 
    AgentType
)
from langchain.memory import (
    ConversationBufferMemory, 
    VectorStoreRetrieverMemory, 
    CombinedMemory
)
from langchain.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import (
    create_sync_playwright_browser,
    create_async_playwright_browser,
)
from langchain.tools import BaseTool
from langchain.llms.base import LLM

# --- Local Imports ---
try:
    from Vera.Agents.executive_0_9 import executive
    from Vera.Memory.memory import *
    from Vera.Toolchain.toolchain import ToolChainPlanner
    from Vera.Toolchain.tools import ToolLoader
    from Vera.Agents.reviewer import Reviewer
    from Vera.Agents.planning import Planner
    from Vera.ProactiveFocus.proactive_focus_manager import ProactiveFocusManager
    from Vera.Ollama.manager import *
    from Vera.Orchestration.vera_tasks import *
    from Vera.Configuration.config_manager import (
        ConfigManager, 
        VeraConfig, 
        validate_config
    )
    from Vera.Logging.logging import (
        get_logger,
        LoggingConfig as VeraLoggingConfig,
        LogContext,
        LogLevel
    )
    from Vera.Agents.integration import integrate_agent_system
    # Import new components
    from Vera.ProactiveFocus.manager import (
        ResourceMonitor, ResourceLimits, ResourcePriority,
        PauseController, AdaptiveScheduler, ResourceGuard
    )

    from Vera.ProactiveFocus.resources import (
        ExternalResourceManager, ResourceType, NotebookResource
    )

    from Vera.ProactiveFocus.stages import (
        StageOrchestrator, ResearchStage, EvaluationStage,
        OptimizationStage, SteeringStage, IntrospectionStage
    )

    from Vera.ProactiveFocus.schedule import CalendarScheduler, ProactiveThoughtEvent

    from Vera.ProactiveFocus.service import BackgroundService, ServiceConfig

except ImportError as e:
    print(f"Import error: {e}")
    from Agents.executive_0_9 import executive
    from Memory.memory import *
    from Toolchain.toolchain import ToolChainPlanner
    from Toolchain.tools import ToolLoader
    from Agents.reviewer import Reviewer
    from Agents.planning import Planner
    from ProactiveFocus.proactive_focus_manager import ProactiveFocusManager
    from Ollama.manager import *
    from Orchestration.vera_tasks import *
    from Configuration.config_manager import (
        ConfigManager, 
        VeraConfig, 
        validate_config
    )
    from Logging.logging import (
        get_logger,
        LoggingConfig as VeraLoggingConfig,
        LogContext,
        LogLevel
    )

#---- Constants ---
MODEL_CONFIG_FILE = "Configuration/vera_models.json"

# Global manager instance (initialized on first use)
_manager: Optional[OllamaConnectionManager] = None


def extract_chunk_text(chunk):
    """Extract text from chunk object"""
    if hasattr(chunk, 'text'):
        return chunk.text
    elif hasattr(chunk, 'content'):
        return chunk.content
    elif isinstance(chunk, str):
        return chunk
    else:
        return str(chunk)
    

class Vera:
    """
    Vera class that manages multiple LLMs and tools for complex tasks.
    
    Features:
    - Infrastructure-aware orchestration with Docker/Proxmox support
    - Unified logging system with configurable verbosity
    - Context tracking across all operations
    - Performance monitoring built-in
    """

    def __init__(
        self, 
        config_file: str = "Configuration/vera_config.yaml",
        chroma_path: Optional[str] = None,
        ollama_api_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Vera with configuration system and unified logging
        
        Args:
            config_file: Path to configuration file
            chroma_path: Override memory path (optional)
            ollama_api_url: Override Ollama API URL (optional)
            **kwargs: Additional overrides for backward compatibility
        """
        
        # --- Load Configuration (using basic print for early setup) ---
        print("[Vera] Loading configuration...")
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.config
        
        # Validate configuration
        issues = validate_config(self.config)
        if issues:
            print("[Vera] Configuration issues detected:")
            for issue in issues:
                print(f"  ⚠ {issue}")
            response = input("\nContinue anyway? (y/n): ").strip().lower()
            if response != 'y':
                raise RuntimeError("Configuration validation failed")
        
        # --- Setup Unified Logging System (FIRST!) ---
        self._setup_unified_logging()
        
        # Now we can use structured logging
        self.logger.info("Configuration loaded successfully")
        self.logger.debug("Configuration details:")
        self.logger.debug(json.dumps(self.config, indent=4, default=str))

        # Register config reload callback
        self.config_manager.register_callback(self._on_config_reload)
        
        # Apply overrides (for backward compatibility)
        if chroma_path:
            self.config.memory.chroma_path = chroma_path
            self.logger.debug(f"Memory path overridden: {chroma_path}")
        if ollama_api_url:
            self.config.ollama.api_url = ollama_api_url
            self.logger.debug(f"Ollama API URL overridden: {ollama_api_url}")
        
        # Apply kwargs overrides
        if 'enable_infrastructure' in kwargs:
            self.config.infrastructure.enable_infrastructure = kwargs['enable_infrastructure']
        if 'enable_docker' in kwargs:
            self.config.infrastructure.enable_docker = kwargs['enable_docker']
        if 'enable_proxmox' in kwargs:
            self.config.infrastructure.enable_proxmox = kwargs['enable_proxmox']
        
        # --- Initialize Ollama Connection Manager ---
        self.logger.info("Initializing Ollama connection manager...")
        self.thoughts_captured = []
        self.thought_queue = queue.Queue()
        self.stream_thoughts_inline = self.config.logging.stream_thoughts_inline
        
        self.ollama_manager = OllamaConnectionManager(
            config=self.config.ollama, 
            thought_callback=self._on_thought_captured,
            logger=self.logger  # Pass logger to manager
        )
        
        # --- Model Selection ---
        self.logger.info("Initializing models...")
        self.selected_models = self.config.models
        
        # Create base context
        self.base_context = LogContext(
            session_id=None,  # Set after session creation
            agent="vera"
        )
        
        # Initialize LLMs using config temperatures
        self.embedding_llm = self.selected_models.embedding_model
        
        self.logger.start_timer("model_initialization")
        
        self.fast_llm = self.ollama_manager.create_llm(
            model=self.selected_models.fast_llm, 
            temperature=self.selected_models.fast_temperature
        )
        
        self.intermediate_llm = self.ollama_manager.create_llm(
            model=self.selected_models.intermediate_llm, 
            temperature=self.selected_models.intermediate_temperature
        )
        
        self.deep_llm = self.ollama_manager.create_llm(
            model=self.selected_models.deep_llm, 
            temperature=self.selected_models.deep_temperature
        )
        
        self.reasoning_llm = self.ollama_manager.create_llm(
            model=self.selected_models.reasoning_llm, 
            temperature=self.selected_models.reasoning_temperature
        )
        
        self.tool_llm = self.ollama_manager.create_llm(
            model=self.selected_models.tool_llm, 
            temperature=self.selected_models.tool_temperature
        )
        
        duration = self.logger.stop_timer("model_initialization")
        self.logger.success(f"Models initialized in {duration:.2f}s")
        
        # --- Setup Memory from Config ---
        self.logger.info("Initializing memory systems...")
        self.logger.start_timer("memory_initialization")
        
        self.mem = HybridMemory(
            neo4j_uri=self.config.memory.neo4j_uri,
            neo4j_user=self.config.memory.neo4j_user,
            neo4j_password=self.config.memory.neo4j_password,
            chroma_dir=self.config.memory.chroma_dir,
            archive_jsonl=self.config.memory.archive_path,
        )
        
        self.sess = self.mem.start_session(metadata={"agent": "vera"})
        
        # Update base context with session ID
        self.base_context.session_id = self.sess.id
        self.logger.push_context(self.base_context)
        
        self.logger.debug(f"Session started: {self.sess.id}")
        
        self.mem.add_session_memory(
            self.sess.id, 
            "Session", 
            "Session", 
            metadata={"topic": "conversation"}
        )

        # --- Shared ChromaDB Memory ---
        embeddings = self.ollama_manager.create_embeddings(
            model=self.embedding_llm
        )
        
        self.vectorstore = Chroma(
            persist_directory=self.config.memory.chroma_path,
            embedding_function=embeddings
        )

        self.vector_memory = VectorStoreRetrieverMemory(
            retriever=self.vectorstore.as_retriever(
                search_kwargs={"k": self.config.memory.vector_search_k}
            )
        )

        self.buffer_memory = ConversationBufferMemory(
            memory_key="chat_history",
            input_key="input",
            return_messages=True
        )
        
        self.plan_memory = ConversationBufferMemory(
            memory_key="plan_history",
            input_key="input",
            return_messages=True
        )
        
        self.plan_vectorstore = Chroma(
            persist_directory=os.path.join(
                self.config.memory.chroma_path, 
                "plans"
            ),
            embedding_function=embeddings
        )
        
        self.plan_vector_memory = VectorStoreRetrieverMemory(
            retriever=self.plan_vectorstore.as_retriever(
                search_kwargs={"k": self.config.memory.plan_vector_search_k}
            )
        )
        
        duration = self.logger.stop_timer("memory_initialization")
        duration = duration if duration is not None else 0.0
        self.logger.success(f"Memory systems initialized in {duration:.2f}s")
        
        # --- Proactive Focus Manager ---
        if self.config.proactive_focus.enabled:
            self.logger.info("Initializing proactive focus manager...")
            self.focus_manager = ProactiveFocusManager(
                agent=self,
                hybrid_memory=self.mem if hasattr(self, 'mem') else None,
                proactive_interval=3600,  # 60 minutes
                cpu_threshold=70.0
            )
            if self.config.proactive_focus.default_focus:
                self.focus_manager.set_focus(
                    self.config.proactive_focus.default_focus
                )
                self.logger.info(f"Default focus set: {self.config.proactive_focus.default_focus}")
        else:
            self.focus_manager = None
            self.logger.debug("Proactive focus manager disabled")
        

        # 3. Create resource manager
        resource_limits = ResourceLimits(
            max_cpu_percent=70.0,
            max_memory_percent=80.0,
            max_ollama_concurrent=1
        )
        
        resource_monitor = ResourceMonitor(limits=resource_limits)
        resource_monitor.start()
        
        # 4. Create external resource manager
        resource_manager = ExternalResourceManager(
            hybrid_memory=self.mem if hasattr(self, 'mem') else None
        )
        # 5. Create stage orchestrator
        self.stage_orchestrator = StageOrchestrator()
        
        # 6. Create calendar scheduler
        self.calendar_scheduler = CalendarScheduler()

        # 7. Create background service
        self.service_config = ServiceConfig(
            max_cpu_percent=50.0,
            check_interval=30.0,
            min_idle_seconds=30.0,
            use_calendar=True,
            enabled_stages=["Introspection", "Research", "Evaluation", "Steering"]
        )
    
        self.background_service = BackgroundService(
            focus_manager=self.focus_manager,
            config=self.service_config
        )
        
        print("✓ All components initialized")
        print(f"  Focus: {self.focus_manager.focus}")
        print(f"  Resource monitor: Running")
        print(f"  Stages: {len(self.stage_orchestrator.stages)}")
        print(f"  Calendar: Enabled")
        
        self.triage_memory = self.config.memory.enable_memory_triage
        self.memory = CombinedMemory(
            memories=[self.buffer_memory, self.vector_memory]
        )
        
        # --- Initialize Orchestrator ---
        self.logger.info("Initializing task orchestrator...")
        self.enable_infrastructure = self.config.infrastructure.enable_infrastructure
        
        from Vera.Orchestration.orchestration import (
            Orchestrator, 
            ProactiveFocusOrchestrator,
            TaskType
        )
        
        orchestrator_config = {
            TaskType.LLM: self.config.orchestrator.llm_workers,
            TaskType.WHISPER: self.config.orchestrator.whisper_workers,
            TaskType.TOOL: self.config.orchestrator.tool_workers,
            TaskType.ML_MODEL: self.config.orchestrator.ml_model_workers,
            TaskType.BACKGROUND: self.config.orchestrator.background_workers,
            TaskType.GENERAL: self.config.orchestrator.general_workers
        }
        
        if self.enable_infrastructure:
            self.logger.info("Using Infrastructure Orchestrator")
            from Vera.Orchestration.infrastructure_orchestration import (
                InfrastructureOrchestrator
            )
            
            proxmox_config = None
            if self.config.infrastructure.enable_proxmox:
                proxmox_config = {
                    "host": self.config.infrastructure.proxmox_host,
                    "user": self.config.infrastructure.proxmox_user,
                    "password": self.config.infrastructure.proxmox_password,
                    "verify_ssl": self.config.infrastructure.proxmox_verify_ssl,
                    "node": self.config.infrastructure.proxmox_node
                }
                self.logger.debug(f"Proxmox configured: {self.config.infrastructure.proxmox_host}")
            
            self.orchestrator = InfrastructureOrchestrator(
                config=orchestrator_config,
                redis_url=self.config.orchestrator.redis_url,
                cpu_threshold=self.config.orchestrator.cpu_threshold,
                enable_docker=self.config.infrastructure.enable_docker,
                enable_proxmox=self.config.infrastructure.enable_proxmox,
                docker_url=self.config.infrastructure.docker_url,
                proxmox_config=proxmox_config,
                auto_scale=self.config.infrastructure.auto_scale,
                max_resources=self.config.infrastructure.max_resources
            )
                # logger=self.logger  # Pass logger to orchestrator
            # )
        else:
            self.logger.info("Using Standard Orchestrator")
            self.orchestrator = Orchestrator(
                config=orchestrator_config,
                redis_url=self.config.orchestrator.redis_url,
                cpu_threshold=self.config.orchestrator.cpu_threshold,
            )
                # logger=self.logger  # Pass logger to orchestrator
            # )

        self.orchestrator.start()
        self.logger.success("Orchestrator started")

        # Integrate with ProactiveFocusManager
        if self.focus_manager:
            self.proactive_orchestrator = ProactiveFocusOrchestrator(
                self.orchestrator, 
                self.focus_manager
            )
            self.logger.debug("Proactive orchestrator integrated")

        # ===== NEW: AGENT CONFIGURATION SYSTEM =====
        if self.config.agents.enabled:
            self.logger.info("Initializing agent configuration system...")
            try:
                self.agents = integrate_agent_system(
                    self,
                    self.config_manager,
                    self.logger
                )
                
                num_agents = len(self.agents.loaded_agents)
                self.logger.success(f"Agent system initialized with {num_agents} agents")
                self.logger.info(f"Loaded agents: {list(self.agents.loaded_agents.keys())}")
                self.logger.debug(f"Agent setup complete: {self.agents}")
                self.logger.debug(f"Agent system directories: agents_dir={self.agents.agents_dir}, templates_dir={self.agents.templates_dir}, build_dir={self.agents.build_dir}")



                # Log loaded agents
                for agent_info in self.agents.list_loaded_agents():
                    self.logger.debug(
                        f"  • {agent_info['name']}: {agent_info['description']}"
                    )
            
            except Exception as e:
                self.logger.error(f"Failed to initialize agent system: {e}", exc_info=True)
                self.agents = None
        else:
            self.agents = None
            self.logger.info("Agent system disabled (set agents.enabled: true in config)")

        # --- Playwright Browser Setup ---
        if self.config.playwright.enabled:
            self.logger.info("Initializing Playwright browser...")
            self.sync_browser = create_sync_playwright_browser()
            self.playwright_toolkit = PlayWrightBrowserToolkit.from_browser(
                sync_browser=self.sync_browser
            )
            self.playwright_tools = self.playwright_toolkit.get_tools()
            self.logger.success(f"Loaded {len(self.playwright_tools)} Playwright tools")
        else:
            self.playwright_tools = []
            self.logger.debug("Playwright browser disabled")

        # # Initialize plugin manager - recon map backwards compatible
        try:
            from Vera.Toolchain.plugin_manager import PluginManager
            self.plugin_manager = PluginManager(
                graph_manager=self.graph_manager if hasattr(self, 'graph_manager') else None,
                socketio=self.socketio if hasattr(self, 'socketio') else None,
                args=self.args if hasattr(self, 'args') else None
            )
            self.plugin_manager.start()
            print(f"✓ Plugin manager initialized with {len(self.plugin_manager.plugins)} plugins")
        except Exception as e:
            print(f"[Warning] Could not initialize plugin manager: {e}")
            self.plugin_manager = None

        # --- Initialize Executive and Tools ---
        self.logger.info("Loading tools...")
        self.executive_instance = executive(vera_instance=self)
        self.toolkit = ToolLoader(self)
        self.tools = self.toolkit + self.playwright_tools

        [(tool.name, tool.description) for tool in self.tools]
        # Write the tool list to a file
        tool_list_path = os.path.join(os.path.dirname(__file__), "Agents", "agents", "tool-agent", "includes", "tool_list.txt")
        os.makedirs(os.path.dirname(tool_list_path), exist_ok=True)

        with open(tool_list_path, "w") as tool_file:
            for tool in self.tools:
                tool_file.write(f"{tool.name}: {tool.description}\n")

        self.logger.info(f"Tool list written to {tool_list_path}")

        self.logger.success(f"Loaded {len(self.tools)} total tools")
        
        # --- Initialize Agents ---
        self.logger.debug("Initializing agents...")
        self.light_agent = initialize_agent(
            self.tools,
            self.tool_llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True
        )
        
        self.deep_agent = initialize_agent(
            self.tools,
            self.deep_llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True
        )
        
        self.toolchain = ToolChainPlanner(self, self.tools)

        if self.focus_manager:
            def handle_proactive(thought):
                self.logger.thought(thought, context=LogContext(agent="proactive"))
            self.focus_manager.proactive_callback = handle_proactive
        
        self.logger.success("Vera initialization complete!")
        self.logger.info(f"Session ID: {self.sess.id}")
    
    def _setup_unified_logging(self):
        """Setup unified logging system from config"""
        # Convert Vera config to logging config
        log_cfg = self.config.logging
        
        # Map component levels
        component_levels = {}
        for component, level_str in getattr(log_cfg, 'component_levels', {}).items():
            try:
                component_levels[component] = LogLevel[level_str.upper()]
            except KeyError:
                component_levels[component] = LogLevel.INFO
        
        # Create logging config
        vera_log_config = VeraLoggingConfig(
            global_level=LogLevel[log_cfg.level.upper()],
            component_levels=component_levels,
            enable_colors=log_cfg.enable_colors,
            enable_timestamps=log_cfg.enable_timestamps,
            enable_thread_info=getattr(log_cfg, 'enable_thread_info', False),
            enable_session_info=getattr(log_cfg, 'enable_session_info', True),
            enable_model_info=getattr(log_cfg, 'enable_model_info', True),
            show_milliseconds=getattr(log_cfg, 'show_milliseconds', True),
            timestamp_format=getattr(log_cfg, 'timestamp_format', "%Y-%m-%d %H:%M:%S.%f"),
            max_line_width=getattr(log_cfg, 'max_line_width', 100),
            box_thoughts=getattr(log_cfg, 'box_thoughts', True),
            box_responses=getattr(log_cfg, 'box_responses', False),
            box_tools=getattr(log_cfg, 'box_tools', True),
            show_raw_streams=getattr(log_cfg, 'show_raw_ollama_chunks', False),
            log_to_file=log_cfg.file is not None,
            log_file=log_cfg.file or "./logs/vera.log",
            log_to_json=getattr(log_cfg, 'json_file', None) is not None,
            json_log_file=getattr(log_cfg, 'json_file', None),
            max_log_size=log_cfg.max_bytes,
            backup_count=log_cfg.backup_count,
            enable_performance_tracking=getattr(log_cfg, 'enable_performance_tracking', True),
            track_llm_latency=getattr(log_cfg, 'track_llm_latency', True),
            track_tool_latency=getattr(log_cfg, 'track_tool_latency', True),
            show_ollama_raw_chunks=getattr(log_cfg, 'show_raw_ollama_chunks', False),
            show_orchestrator_details=getattr(log_cfg, 'show_orchestrator_details', True),
            show_memory_triage=getattr(log_cfg, 'show_memory_operations', False),
            show_infrastructure_stats=getattr(log_cfg, 'show_infrastructure_events', True),
            stream_thoughts_inline=getattr(log_cfg, 'stream_thoughts_inline', True),
        )
        
        # Get logger
        self.logger = get_logger("vera", vera_log_config)
    
    def _on_config_reload(self, old_config: VeraConfig, new_config: VeraConfig):
        """Handle configuration reload"""
        self.logger.info("Configuration reloaded!")
        
        # Update reference
        self.config = new_config
        
        # Check what changed and respond accordingly
        changes = []
        
        if old_config.models.fast_llm != new_config.models.fast_llm:
            changes.append(f"Fast LLM: {old_config.models.fast_llm} → {new_config.models.fast_llm}")
            # Recreate fast LLM
            self.fast_llm = self.ollama_manager.create_llm(
                model=new_config.models.fast_llm,
                temperature=new_config.models.fast_temperature
            )
        
        if old_config.orchestrator.cpu_threshold != new_config.orchestrator.cpu_threshold:
            changes.append(f"CPU Threshold: {old_config.orchestrator.cpu_threshold} → {new_config.orchestrator.cpu_threshold}")
            if hasattr(self.orchestrator, 'cpu_threshold'):
                self.orchestrator.cpu_threshold = new_config.orchestrator.cpu_threshold
        
        if old_config.logging.level != new_config.logging.level:
            changes.append(f"Log Level: {old_config.logging.level} → {new_config.logging.level}")
            # Recreate logger with new config
            self._setup_unified_logging()
        
        if changes:
            self.logger.info("Applied configuration changes:")
            for change in changes:
                self.logger.info(f"  • {change}")
        else:
            self.logger.debug("No critical changes detected in reload")
    
    def reload_config(self):
        """Manually trigger config reload"""
        self.logger.info("Manually reloading configuration...")
        self.config_manager.reload_config()
    
    def get_config_value(self, section: str, key: Optional[str] = None):
        """Get current config value"""
        return self.config_manager.get(section, key)
    
    def set_config_value(self, section: str, key: str, value: Any, persist: bool = True):
        """Set config value and optionally persist"""
        self.logger.debug(f"Setting config: {section}.{key} = {value}")
        self.config_manager.set(section, key, value, persist)
    
    # --- Infrastructure Management Methods ---
    
    def get_infrastructure_stats(self):
        """Get infrastructure statistics (if enabled)"""
        if self.enable_infrastructure and hasattr(self.orchestrator, 'get_infrastructure_stats'):
            stats = self.orchestrator.get_infrastructure_stats()
            self.logger.infrastructure_event(
                "stats_retrieved",
                details=stats
            )
            return stats
        return {"infrastructure": "disabled"}
    
    def provision_docker_resources(self, count: int = 1, spec: Optional[Dict] = None):
        """Provision Docker containers for task execution"""
        if not self.enable_infrastructure:
            self.logger.warning("Infrastructure orchestration not enabled")
            return []
        
        from Vera.Orchestration.infrastructure_orchestration import ResourceType, ResourceSpec
        
        resource_spec = ResourceSpec(**(spec or {
            "cpu_cores": 2,
            "memory_mb": 1024,
            "disk_gb": 10
        }))
        
        self.logger.infrastructure_event(
            "provisioning_resources",
            resource_type="docker",
            details={"count": count, "spec": spec}
        )
        
        resources = self.orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=resource_spec,
            count=count
        )
        
        self.logger.success(f"Provisioned {len(resources)} Docker containers")
        return resources
    
    def cleanup_idle_resources(self, max_idle_seconds: int = 300):
        """Cleanup idle infrastructure resources"""
        if self.enable_infrastructure and hasattr(self.orchestrator, 'cleanup_idle_resources'):
            self.logger.info(f"Cleaning up resources idle >{max_idle_seconds}s...")
            self.orchestrator.cleanup_idle_resources(max_idle_seconds)
            self.logger.success("Resource cleanup complete")
    
    def _on_thought_captured(self, thought: str):
        """Handle captured thoughts - queue them for streaming"""
        # Store
        self.thoughts_captured.append({
            'timestamp': time.time(),
            'thought': thought,
            'session_id': self.sess.id if hasattr(self, 'sess') else None
        })
        
        # Log using unified system
        if hasattr(self, 'logger'):
            context = LogContext(
                session_id=self.sess.id if hasattr(self, 'sess') else None,
                agent="reasoning",
                model="reasoning_llm"
            )
            self.logger.thought(thought, context=context)
        
        # Queue for streaming if enabled
        if self.stream_thoughts_inline:
            self.thought_queue.put(thought)
    
    def _stream_with_thought_polling(self, llm, prompt):
        """Stream LLM output with immediate thought injection"""
        import threading
        from queue import Empty
        
        # Create queues
        chunk_queue = queue.Queue()
        streaming_done = threading.Event()
        
        def stream_in_thread():
            """Run LLM stream in background thread"""
            try:
                for chunk in llm.stream(prompt):
                    chunk_queue.put(('chunk', chunk))
            except Exception as e:
                self.logger.error(f"Stream error: {e}", exc_info=True)
                chunk_queue.put(('error', str(e)))
            finally:
                streaming_done.set()
        
        # Start streaming
        thread = threading.Thread(target=stream_in_thread, daemon=True)
        thread.start()
        
        # Poll both queues with thought priority
        last_check = time.time()
        
        while not streaming_done.is_set() or not chunk_queue.empty() or not self.thought_queue.empty():
            # Check thoughts FIRST (every 50ms)
            if time.time() - last_check > 0.05:
                try:
                    while True:  # Drain all available thoughts
                        thought = self.thought_queue.get_nowait()
                        # Format thought distinctively
                        yield f"\n\n💭 **THOUGHT**: {thought}\n\n"
                except Empty:
                    pass
                last_check = time.time()
            
            # Then check chunks
            try:
                item_type, item_data = chunk_queue.get(timeout=0.05)
                if item_type == 'chunk':
                    yield extract_chunk_text(item_data)
                elif item_type == 'error':
                    self.logger.error(f"Stream error: {item_data}")
                    break
            except Empty:
                continue
        
        # Final drain of thoughts
        try:
            while True:
                thought = self.thought_queue.get_nowait()
                yield f"\n\n💭 **THOUGHT**: {thought}\n\n"
        except Empty:
            pass
        
        thread.join(timeout=1.0)

    def stream_llm(self, llm, prompt):
        """Stream LLM output with immediate thought injection"""
        output = []
        
        context = LogContext(
            session_id=self.sess.id,
            model=llm.model if hasattr(llm, 'model') else "unknown",
            agent="stream"
        )
        
        self.logger.debug("Starting LLM stream", context=context)
        
        # Use the polling wrapper
        for item in self._stream_with_thought_polling(llm, prompt):
            # Stream to console
            self.logger.response(item, context=context, stream=True)
            output.append(item)
            yield item
        
        result = "".join(output)
        self.logger.debug(f"Stream complete: {len(result)} chars", context=context)
        return result

    def stream_llm_with_memory(self, llm, user_input, extra_context=None, long_term=True, short_term=True):
        """Stream LLM with memory context"""
        context = LogContext(
            session_id=self.sess.id,
            model=llm.model if hasattr(llm, 'model') else "unknown",
            agent="memory_stream"
        )
        
        past_context = ""
        relevant_history = ""
        
        if short_term:
            past_context = self.memory.load_memory_variables({"input": user_input}).get("chat_history", "")
            self.logger.debug("Loaded short-term memory", context=context)
           
        if long_term:
            relevant_history = self.vector_memory.load_memory_variables({"input": user_input})
            self.logger.debug("Loaded long-term memory", context=context)

        full_prompt = f"Conversation so far:\n{str(past_context)}"
        full_prompt += f"Relevant conversation history{relevant_history}"

        if extra_context:
            full_prompt += f"\n\nExtra reasoning/context from another agent:\n{extra_context}"
        full_prompt += f"\n\nUser: {user_input}\nAssistant:"
        full_prompt += f"\n\nTools available via the agent system:{[tool.name for tool in self.tools]}\n"

        output = []
        for chunk in self.stream_llm(llm, full_prompt):
            output.append(chunk)
            yield chunk

        ai_output = "".join(output)
        self.memory.save_context({"input": user_input}, {"output": ai_output})
        self.vectorstore.persist()
        
        if self.focus_manager:
            self.focus_manager.update_latest_conversation(f"User Query: {user_input}")
            self.focus_manager.update_latest_conversation(f"Agent Response: {ai_output}")
        
        self.mem.add_session_memory(self.sess.id, user_input, "Query", {"topic": "query"})
        self.mem.add_session_memory(self.sess.id, ai_output, "Response", {"topic": "response"})
        
        self.logger.memory_operation(
            "conversation_saved",
            details={"input_len": len(user_input), "output_len": len(ai_output)},
            context=context
        )
        
        return ai_output

    def save_to_memory(self, query, response):
        """Save interaction to all memory systems"""
        self.memory.save_context({"input": query}, {"output": response})
        self.vectorstore.persist()
        
        if self.config.logging.show_memory_operations:
            self.logger.memory_operation(
                "interaction_saved",
                details={"query_len": len(query), "response_len": len(response)}
            )

    def async_run(self, query):
        """
        Fully orchestrated async_run with unified logging.
        ALWAYS yields - guaranteed to be a generator.
        """
        
        query_context = LogContext(
            session_id=self.sess.id,
            agent="async_run",
            extra={"query_length": len(query)}
        )
        
        self.logger.info(f"Processing query: {query[:100]}{'...' if len(query) > 100 else ''}", context=query_context)
        self.logger.start_timer("total_query_processing")
        
        # Log query to memory
        if hasattr(self, 'mem') and hasattr(self, 'sess'):
            self.mem.add_session_memory(self.sess.id, query, "Query", {"topic": "plan"}, promote=True)
        
        # ====================================================================
        # STEP 1: TRIAGE (streaming through orchestrator)
        # ====================================================================
        
        use_orchestrator = hasattr(self, 'orchestrator') and self.orchestrator and self.orchestrator.running
        
        self.logger.debug(f"Using orchestrator: {use_orchestrator}", context=query_context)
        self.logger.start_timer("triage")
        
        full_triage = ""
        
        if use_orchestrator:
            try:
                triage_task_id = self.orchestrator.submit_task(
                    "llm.triage",
                    vera_instance=self,
                    query=query
                )
                
                self.logger.orchestrator_event(
                    "task_submitted",
                    task_id=triage_task_id,
                    details={"type": "triage"}
                )
                
                for chunk in self.orchestrator.stream_result(triage_task_id, timeout=10.0):
                    full_triage += chunk
                    yield extract_chunk_text(chunk)
            
            except TimeoutError:
                self.logger.warning("Triage timeout, using direct fallback")
                for chunk in self._triage_direct(query):
                    full_triage += chunk
                    yield extract_chunk_text(chunk)
            
            except Exception as e:
                self.logger.error(f"Triage failed: {e}", exc_info=True)
                for chunk in self._triage_direct(query):
                    full_triage += chunk
                    yield extract_chunk_text(chunk)
        
        else:
            for chunk in self._triage_direct(query):
                full_triage += chunk
                yield extract_chunk_text(chunk)
        
        triage_duration = self.logger.stop_timer("triage", context=query_context)
        
        if hasattr(self, 'mem') and hasattr(self, 'sess'):
            self.mem.add_session_memory(self.sess.id, full_triage, "Triage", {"topic": "triage","duration": triage_duration}, promote=True)
        
        # ====================================================================
        # STEP 2: ROUTE based on triage
        # ====================================================================
        
        triage_lower = full_triage.lower()
        total_response = ""
        
        route_context = LogContext(
            session_id=self.sess.id,
            extra={"triage_result": triage_lower[:50]}
        )
        
        # Focus change
        if "focus" in triage_lower:
            self.logger.info("Routing to: Proactive Focus Manager", context=route_context)
            
            if hasattr(self, 'focus_manager'):
                new_focus = full_triage.lower().split("focus", 1)[-1].strip()
                self.focus_manager.set_focus(new_focus)
                message = f"\n✓ Focus changed to: {self.focus_manager.focus}\n"
                yield extract_chunk_text(message)
                total_response = message
                self.logger.success(f"Focus changed to: {self.focus_manager.focus}")
        
        # Proactive thinking
        elif triage_lower.startswith("proactive"):
            self.logger.info("Routing to: Proactive Thinking", context=route_context)
            
            if use_orchestrator:
                try:
                    task_id = self.orchestrator.submit_task(
                        "proactive.generate_thought",
                        vera_instance=self
                    )
                    message = "\n[Proactive thought generation started in background]\n"
                    yield extract_chunk_text(message)
                    total_response = message
                    self.logger.success("Proactive task submitted")
                
                except Exception as e:
                    self.logger.error(f"Failed to submit proactive task: {e}")
                    if hasattr(self, 'focus_manager') and self.focus_manager.focus:
                        self.focus_manager.iterative_workflow(
                            max_iterations=None,
                            iteration_interval=600,
                            auto_execute=True
                        )
                        message = "\n[Proactive workflow started]\n"
                        yield extract_chunk_text(message)
                        total_response = message
                    else:
                        message = "\n[No active focus for proactive thinking]\n"
                        yield extract_chunk_text(message)
                        total_response = message
            
            else:
                if hasattr(self, 'focus_manager') and self.focus_manager.focus:
                    self.focus_manager.iterative_workflow(
                        max_iterations=None,
                        iteration_interval=600,
                        auto_execute=True
                    )
                    message = "\n[Proactive workflow started]\n"
                    yield extract_chunk_text(message)
                    total_response = message
                else:
                    message = "\n[No active focus]\n"
                    yield extract_chunk_text(message)
                    total_response = message

            if hasattr(self, 'mem') and hasattr(self, 'sess'):
                self.mem.add_session_memory(
                    self.sess.id,
                    total_response,
                    "Thought",
                    {"topic": "response", "agent": "toolchain", "task_id": task_id if task_id else None, "duration": duration}
                )
        
        # Toolchain
        elif triage_lower.startswith("toolchain") or "tool" in triage_lower:
            self.logger.info("Routing to: Tool Chain Agent", context=route_context)
            self.logger.start_timer("toolchain_execution")
            
            if use_orchestrator:
                try:
                    task_id = self.orchestrator.submit_task(
                        "toolchain.execute",
                        vera_instance=self,
                        query=query
                    )
                    
                    for chunk in self.orchestrator.stream_result(task_id, timeout=120.0):
                        total_response += str(chunk)
                        yield extract_chunk_text(chunk)
                
                except Exception as e:
                    self.logger.error(f"Toolchain failed: {e}, using direct fallback")
                    for chunk in self.toolchain.execute_tool_chain(query):
                        total_response += str(chunk)
                        yield extract_chunk_text(chunk)
            
            else:
                for chunk in self.toolchain.execute_tool_chain(query):
                    total_response += str(chunk)
                    yield extract_chunk_text(chunk)
            
            duration = self.logger.stop_timer("toolchain_execution", context=route_context)
            
            if hasattr(self, 'mem') and hasattr(self, 'sess'):
                self.mem.add_session_memory(
                    self.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "toolchain", "duration":duration}
                )
        
        # Reasoning
        elif triage_lower.startswith("reasoning"):
            self.logger.info("Routing to: Reasoning Agent", context=route_context)
            self.logger.start_timer("reasoning_generation")
            
            # Use reasoning agent if available
            if self.agents:
                agent_name = self.get_agent_for_task('reasoning')
                reasoning_llm = self.create_llm_for_agent(agent_name)
                agent_context = LogContext(
                    session_id=self.sess.id,
                    agent=agent_name,
                    model=agent_name
                )
            else:
                reasoning_llm = self.reasoning_llm
                agent_context = LogContext(
                    session_id=self.sess.id,
                    agent="reasoning",
                    model=self.selected_models.reasoning_llm
                )
            
            if use_orchestrator:
                try:
                    task_id = self.orchestrator.submit_task(
                        "llm.generate",
                        vera_instance=self,
                        llm_type="reasoning",
                        prompt=query
                    )
                    
                    for chunk in self.orchestrator.stream_result(task_id, timeout=60.0):
                        total_response += chunk
                        yield extract_chunk_text(chunk)
                
                except Exception as e:
                    self.logger.error(f"Reasoning failed: {e}, using direct fallback")
                    for chunk in self.stream_llm(reasoning_llm, query):
                        total_response += chunk
                        yield extract_chunk_text(chunk)
            
            else:
                for chunk in self.stream_llm(reasoning_llm, query):
                    total_response += chunk
                    yield extract_chunk_text(chunk)
            
            duration = self.logger.stop_timer("reasoning_generation", context=agent_context)
        
            if hasattr(self, 'mem') and hasattr(self, 'sess'):
                self.mem.add_session_memory(
                    self.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "reasoning", "duration":duration}
                )
        
        # Complex
        elif triage_lower.startswith("complex"):
            self.logger.info("Routing to: Deep Reasoning Agent", context=route_context)
            self.logger.start_timer("deep_generation")
            
            agent_context = LogContext(
                session_id=self.sess.id,
                agent="deep",
                model=self.selected_models.deep_llm
            )
            
            if use_orchestrator:
                try:
                    task_id = self.orchestrator.submit_task(
                        "llm.generate",
                        vera_instance=self,
                        llm_type="deep",
                        prompt=query
                    )
                    
                    for chunk in self.orchestrator.stream_result(task_id, timeout=60.0):
                        total_response += chunk
                        yield extract_chunk_text(chunk)
                
                except Exception as e:
                    self.logger.error(f"Complex generation failed: {e}, using direct fallback")
                    for chunk in self.stream_llm(self.deep_llm, query):
                        total_response += chunk
                        yield extract_chunk_text(chunk)
            
            else:
                for chunk in self.stream_llm(self.deep_llm, query):
                    total_response += chunk
                    yield extract_chunk_text(chunk)
            
            duration = self.logger.stop_timer("deep_generation", context=agent_context)
            
            if hasattr(self, 'mem') and hasattr(self, 'sess'):
                self.mem.add_session_memory(
                    self.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "complex", "duration":duration}
                )
        
        # Simple/Default - Fast LLM
        else:
            self.logger.info("Routing to: Fast Agent", context=route_context)
            self.logger.start_timer("fast_generation")
            
            agent_context = LogContext(
                session_id=self.sess.id,
                agent="fast",
                model=self.selected_models.fast_llm
            )
            
            if use_orchestrator:
                try:
                    task_id = self.orchestrator.submit_task(
                        "llm.generate",
                        vera_instance=self,
                        llm_type="fast",
                        prompt=query
                    )
                    
                    for chunk in self.orchestrator.stream_result(task_id, timeout=30.0):
                        total_response += chunk
                        yield extract_chunk_text(chunk)
                
                except Exception as e:
                    self.logger.error(f"Fast LLM failed: {e}, using direct fallback")
                    for chunk in self.stream_llm(self.fast_llm, query):
                        total_response += chunk
                        yield extract_chunk_text(chunk)
            
            else:
                for chunk in self.stream_llm(self.fast_llm, query):
                    total_response += chunk
                    yield extract_chunk_text(chunk)
            
            duration = self.logger.stop_timer("fast_generation", context=agent_context)
            
            if hasattr(self, 'mem') and hasattr(self, 'sess'):
                self.mem.add_session_memory(
                    self.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "fast"}
                )
        
        # ====================================================================
        # STEP 3: SAVE TO MEMORY
        # ====================================================================
        
        if total_response:
            self.save_to_memory(query, total_response)
        
        total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
        self.logger.success(
            f"Query complete: {len(total_response)} chars in {total_duration:.2f}s",
            context=query_context
        )

    def _triage_direct(self, query):
        """Direct triage without orchestrator (fallback)"""
        triage_context = LogContext(
            session_id=self.sess.id,
            agent="triage"
        )
        
        # Use triage agent if available
        if self.agents:
            agent_name = self.get_agent_for_task('triage')
            triage_llm = self.create_llm_for_agent(agent_name)
            triage_context.agent = agent_name
            triage_context.model = agent_name
        else:
            triage_llm = self.fast_llm
            triage_context.model = self.selected_models.fast_llm
        
        self.logger.debug("Using triage agent", context=triage_context)
        
        triage_prompt = f"""
        Classify this Query into one of the following categories:
            - 'focus'      → Change the focus of background thought.
            - 'proactive'  → Trigger proactive thinking.
            - 'simple'     → Simple textual response.
            - 'toolchain'  → Requires a series of tools or step-by-step planning.
            - 'reasoning'  → Requires deep reasoning.
            - 'complex'    → Complex written response with high-quality output.

        Current focus: {self.focus_manager.focus if hasattr(self, 'focus_manager') else 'None'}

        Query: {query}

        Respond with a single classification term (e.g., 'simple', 'toolchain', 'complex') on the first line.
        """
        
        for chunk in self.stream_llm(triage_llm, triage_prompt):
            yield chunk

    def print_llm_models(self):
        """Print the variable name and model name for each Ollama LLM."""
        self.logger.info("=== Vera Model Configuration ===")
        for attr_name, attr_value in vars(self).items():
            if isinstance(attr_value, Ollama):
                model_name = attr_value.model
                self.logger.info(f"  {attr_name} → {model_name}")
        self.logger.info("=" * 40)
        
    def print_agents(self):
        """Recursively find and print all LLM models and agents inside Vera."""
        self.logger.info("=== Vera Agent Configuration ===")
        visited = set()

        def inspect_obj(obj, path="self"):
            if id(obj) in visited:
                return
            visited.add(id(obj))

            if hasattr(obj, "llm") and hasattr(obj.llm, "model"):
                agent_type = getattr(obj, "agent", None)
                model_name = getattr(obj.llm, "model", "Unknown")
                self.logger.info(f"  {path} → Model: {model_name}, Agent Type: {agent_type}")

            if hasattr(obj, "__dict__"):
                for attr_name, attr_value in vars(obj).items():
                    inspect_obj(attr_value, f"{path}.{attr_name}")

        inspect_obj(self)
        self.logger.info("=" * 40)

    def get_agent_for_task(self, task_type: str) -> str:
        """Get appropriate agent name for task type"""
        if not self.agents:
            # Fallback to model names
            fallback_map = {
                'triage': self.selected_models.fast_llm,
                'tool_execution': self.selected_models.tool_llm,
                'reasoning': self.selected_models.reasoning_llm,
                'conversation': self.selected_models.fast_llm
            }
            return fallback_map.get(task_type, self.selected_models.fast_llm)
        
        return self.config.agents.default_agents.get(
            task_type,
            self.selected_models.fast_llm
        )

    def create_llm_for_agent(self, agent_name: str):
        """Create LLM using agent configuration if available"""
        if self.agents:
            try:
                llm = self.agents.create_llm_with_agent_config(
                    agent_name,
                    self.ollama_manager
                )
                
                self.logger.debug(
                    f"Created LLM from agent config: {agent_name}",
                    context=LogContext(agent=agent_name)
                )
                
                return llm
            
            except Exception as e:
                self.logger.warning(
                    f"Failed to create LLM from agent {agent_name}: {e}, using fallback"
                )
        
        # Fallback to standard model
        return self.ollama_manager.create_llm(
            model=agent_name,
            temperature=0.7
        )

    def list_available_agents(self) -> List[Dict[str, str]]:
        """List all available agents"""
        if not self.agents:
            return []
        
        return self.agents.list_loaded_agents()

    def reload_agent(self, agent_name: str, rebuild_model: bool = True):
        """Reload an agent configuration (hot reload)"""
        if not self.agents:
            self.logger.warning("Agent system not enabled")
            return None
        
        self.logger.info(f"Reloading agent: {agent_name}")
        config = self.agents.reload_agent(agent_name, rebuild_model=rebuild_model)
        
        if config:
            self.logger.success(f"Agent reloaded: {agent_name}")
        else:
            self.logger.error(f"Failed to reload agent: {agent_name}")
        
        return config


# --- Example usage ---
if __name__ == "__main__":
    import sys
    
    # Example 1: Standard orchestration (no infrastructure)
    vera = Vera(enable_infrastructure=False)
    
    # Example 2: With Docker infrastructure
    # vera = Vera(
    #     enable_infrastructure=True,
    #     enable_docker=True,
    #     auto_scale=True,
    #     max_resources=5
    # )
    
    os.system("clear")
    vera.print_llm_models()
    vera.print_agents()
    
    # Show infrastructure stats if enabled
    if vera.enable_infrastructure:
        vera.logger.info("=== Infrastructure Stats ===")
        stats = vera.get_infrastructure_stats()
        for key, value in stats.items():
            vera.logger.info(f"  {key}: {value}")
        vera.logger.info("=" * 40)

    vera.logger.info("Vera ready! Enter your queries below.")
    vera.logger.info("Special commands: /stats, /infra, /provision, /cleanup, /clear, /exit")
    
    while True:
        try:
            user_query = input("\n\n🔵 Query: ")
        except (EOFError, KeyboardInterrupt):
            vera.logger.info("Shutting down...")
            break
        
        if user_query.lower() in ["exit", "quit", "/exit"]:
            vera.logger.info("Goodbye!")
            break
        
        # Special commands
        if user_query.lower() == "/stats":
            vera.logger.print_stats()
            continue
        
        if user_query.lower() == "/infra":
            if vera.enable_infrastructure:
                stats = vera.get_infrastructure_stats()
            else:
                vera.logger.warning("Infrastructure orchestration not enabled")
            continue
        
        if user_query.lower() == "/provision":
            if vera.enable_infrastructure:
                resources = vera.provision_docker_resources(count=2)
            else:
                vera.logger.warning("Infrastructure orchestration not enabled")
            continue
        
        if user_query.lower() == "/cleanup":
            if vera.enable_infrastructure:
                vera.cleanup_idle_resources(max_idle_seconds=60)
            else:
                vera.logger.warning("Infrastructure orchestration not enabled")
            continue
        if user_query.lower() == "/agents":
            if vera.agents:
                vera.logger.info("=== Available Agents ===")
                for agent in vera.list_available_agents():
                    vera.logger.info(f"  • {agent['name']}: {agent['description']}")
                vera.logger.info("=" * 40)
            else:
                vera.logger.warning("Agent system not enabled")
            continue       
        if user_query.lower() == "/clear":
            vera.logger.warning("Clearing memory...")
            vera.vectorstore.delete_collection("vera_agent_memory")
            vera.buffer_memory.clear()
            vera.logger.success("Memory cleared")
            continue
        
        # Process query
        vera.logger.debug(f"Processing: {user_query}")
        result = ""
        for chunk in vera.async_run(user_query):
            # Chunks are already streamed by logger.response()
            result += str(chunk)
        
        print()  # Newline after response

# ジョセフ