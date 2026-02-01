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

from Vera.vera_chat import VeraChat
# --- Local Imports ---
try:
    from Vera.Ollama.Agents.Scheduling.executive_0_9 import executive
    from Vera.Memory.memory import *
    from Vera.Toolchain.toolchain import ToolChainPlanner
    from Vera.Toolchain.tools import ToolLoader
    from Vera.Toolchain.chain_of_experts_integration import integrate_hybrid_toolchain
    from Vera.Ollama.Agents.experimental.reviewer import Reviewer
    from Vera.Ollama.Agents.experimental.Planning.planning import Planner
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
    from Vera.Ollama.Agents.integration import integrate_agent_system
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
    from Vera.Toolchain.enhanced_toolchain_planner_integration import integrate_hybrid_planner

except ImportError as e:
    print(f"Import error: {e}")
    from Ollama.Agents.Scheduling.executive_0_9 import executive
    from Memory.memory import *
    from Toolchain.toolchain import ToolChainPlanner
    from Toolchain.tools import ToolLoader
    from Ollama.Agents.reviewer import Reviewer
    from Ollama.Agents.Planning.planning import Planner
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
        
        from Vera.Ollama.multi_instance_manager import MultiInstanceOllamaManager

        self.ollama_manager = MultiInstanceOllamaManager(
            config=self.config.ollama,
            thought_callback=self._on_thought_captured,
            logger=self.logger
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

        # Log loaded tools with input schemas to agent tool list file
        tool_list_path = os.path.join(os.path.dirname(__file__), "Ollama","Agents", "agents", "tool-agent", "includes", "tool_list.txt")
        os.makedirs(os.path.dirname(tool_list_path), exist_ok=True)

        with open(tool_list_path, "w") as tool_file:
            tool_file.write("=" * 80 + "\n")
            tool_file.write("VERA TOOLCHAIN - AVAILABLE TOOLS\n")
            tool_file.write("=" * 80 + "\n\n")
            
            for idx, tool in enumerate(self.tools, 1):
                # Write tool header
                tool_file.write(f"\n[{idx}] {tool.name}\n")
                tool_file.write("-" * 80 + "\n")
                tool_file.write(f"DESCRIPTION:\n  {tool.description}\n\n")
                
                # Write input schema
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        # Get the Pydantic schema
                        schema = tool.args_schema.schema()
                        
                        tool_file.write("INPUT PARAMETERS:\n")
                        
                        # Extract properties
                        properties = schema.get('properties', {})
                        required_fields = schema.get('required', [])
                        
                        if properties:
                            for param_name, param_info in properties.items():
                                # Get parameter details
                                param_type = param_info.get('type', 'string')
                                param_desc = param_info.get('description', 'No description')
                                is_required = param_name in required_fields
                                
                                # Format parameter line
                                required_marker = " [REQUIRED]" if is_required else " [OPTIONAL]"
                                tool_file.write(f"  • {param_name}{required_marker}\n")
                                tool_file.write(f"    Type: {param_type}\n")
                                tool_file.write(f"    Description: {param_desc}\n")
                                
                                # Include default value if present
                                if 'default' in param_info:
                                    tool_file.write(f"    Default: {param_info['default']}\n")
                                
                                # Include enum values if present
                                if 'enum' in param_info:
                                    tool_file.write(f"    Allowed values: {', '.join(map(str, param_info['enum']))}\n")
                                
                                tool_file.write("\n")
                        else:
                            tool_file.write("  (No parameters required)\n\n")
                        
                        # Optionally include full JSON schema for reference
                        # tool_file.write("FULL JSON SCHEMA:\n")
                        # tool_file.write("  " + json.dumps(schema, indent=2).replace("\n", "\n  ") + "\n")
                        
                    except Exception as e:
                        tool_file.write(f"INPUT SCHEMA: Error extracting schema - {str(e)}\n")
                else:
                    tool_file.write("INPUT SCHEMA: No schema defined\n")
                
                tool_file.write("\n" + "=" * 80 + "\n")
            # Warm up fast LLM task    
            fast_task_id = self.orchestrator.submit_task(
                "llm.fast",
                vera_instance=self,
                prompt="hello"
            )
        self.logger.info(f"Tool list with schemas written to {tool_list_path}")
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

        # Original toolchain (preserved)
        self.toolchain = ToolChainPlanner(self, self.tools)
        
        #from Vera.Toolchain.unified_toolchain import ToolChainPlanner
        #self.toolchain = ToolChainPlanner(self, self.tools)  # Uses AUTO mode
        # from Vera.Toolchain.unified_toolchain import UnifiedToolChainPlanner, ToolChainMode
        # self.toolchain = UnifiedToolChainPlanner(
        #                 self, 
        #                 self.tools,
        #                 mode=ToolChainMode.AUTO,
        #                 enable_orchestrator=True
        # )

        #  chain of experts
        #integrate_hybrid_toolchain(self)

        #   enhanced toolchain planner
        #integrate_hybrid_planner(self, enable_n8n=True) 

        if self.focus_manager:
            def handle_proactive(thought):
                self.logger.thought(thought, context=LogContext(agent="proactive"))
            self.focus_manager.proactive_callback = handle_proactive
        
        # Initialize chat handler (AFTER all other components)
        self.chat = VeraChat(self)
        
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
        
        chunk_queue = queue.Queue()
        streaming_done = threading.Event()
        
        def stream_in_thread():
            """Run LLM stream in background thread"""
            try:
                for chunk in llm.stream(prompt):
                    # CRITICAL: Filter out any <thought> tags from LLM output
                    text = extract_chunk_text(chunk)
                    # Remove any thought tags the model might generate
                    text = text.replace('<thought>', '').replace('</thought>', '')
                    chunk_queue.put(('chunk', text))
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
        in_thought = False
        
        while not streaming_done.is_set() or not chunk_queue.empty() or not self.thought_queue.empty():
            # Check thoughts FIRST (every 50ms)
            if time.time() - last_check > 0.05:
                try:
                    while True:  # Drain all available thoughts
                        thought_chunk = self.thought_queue.get_nowait()
                        
                        # Start thought block if not already started
                        if not in_thought:
                            yield "\n<thought>"
                            in_thought = True
                        
                        # Yield raw chunk
                        yield thought_chunk
                        
                except Empty:
                    pass
                last_check = time.time()
            
            # Then check chunks
            try:
                item_type, item_data = chunk_queue.get(timeout=0.05)
                
                if item_type == 'chunk':
                    # Close thought if we were in one
                    if in_thought:
                        yield "</thought>\n"
                        in_thought = False
                    
                    # Yield main content chunk (already filtered)
                    yield item_data
                elif item_type == 'error':
                    self.logger.error(f"Stream error: {item_data}")
                    break
            except Empty:
                continue
        
        # Final drain of thoughts
        try:
            while True:
                thought_chunk = self.thought_queue.get_nowait()
                
                if not in_thought:
                    yield "\n<thought>"
                    in_thought = True
                
                yield thought_chunk
        except Empty:
            pass
        
        # Close any open thought
        if in_thought:
            yield "</thought>\n"
        
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
            # Only log regular content, not thoughts (they're wrapped in tags)
            if not item.startswith('<thought>') and not item.endswith('</thought>'):
                # Stream to console (but don't box individual chunks)
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
        for chunk in self._stream_with_thought_polling(llm, full_prompt):
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
    
    # def fast_start_stream(self, query):
    #     prompt = f"""
    #         Answer the user briefly and generically in 1–2 sentences.
    #         Do NOT use tools.
    #         Do NOT assume routing yet.

    #         User: {query}
    #         Assistant:
    #         """
    #     return self.stream_llm(self.fast_llm, prompt)
    
    def async_run(self, query: str, use_parallel: bool = True, ramp_config: Optional[Dict] = None):
        """
        Delegate to chat handler
        
        Args:
            query: User query
            use_parallel: Enable parallel triage+fast execution
            ramp_config: Optional custom ramp configuration
        
        Yields:
            str: Response chunks
        """
        return self.chat.async_run(query, use_parallel, ramp_config)


    # # ====================================================================
    # # HELPER METHODS
    # # ====================================================================

    # def _execute_ramp_tier(self, tier_level, query, accumulated_response, use_orchestrator, context):
    #     """Execute a single ramp tier and yield response"""
        
    #     TIER_NAMES = {1: "Intermediate", 2: "Deep", 3: "Reasoning", 4: "Toolchain"}
        
    #     tier_response = ""
    #     prompt = self._build_ramp_prompt(tier_level, query, accumulated_response)
        
    #     if tier_level == 1:  # Intermediate
    #         llm = self.intermediate_llm if hasattr(self, 'intermediate_llm') else self.fast_llm
            
    #         if use_orchestrator:
    #             task_id = self.orchestrator.submit_task(
    #                 "llm.generate",
    #                 vera_instance=self,
    #                 llm_type="intermediate",
    #                 prompt=prompt
    #             )
                
    #             for chunk in self.orchestrator.stream_result(task_id, timeout=45.0):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
    #         else:
    #             for chunk in self.stream_llm(llm, prompt):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
        
    #     elif tier_level == 2:  # Deep
    #         if use_orchestrator:
    #             task_id = self.orchestrator.submit_task(
    #                 "llm.deep",
    #                 vera_instance=self,
    #                 prompt=prompt
    #             )
                
    #             for chunk in self._stream_orchestrator_with_thoughts(task_id, timeout=60.0):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
    #         else:
    #             for chunk in self.stream_llm(self.deep_llm, prompt):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
        
    #     elif tier_level == 3:  # Reasoning
    #         if use_orchestrator:
    #             task_id = self.orchestrator.submit_task(
    #                 "llm.reasoning",
    #                 vera_instance=self,
    #                 prompt=prompt
    #             )
                
    #             for chunk in self._stream_orchestrator_with_thoughts(task_id, timeout=90.0):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
    #         else:
    #             for chunk in self.stream_llm(self.reasoning_llm, prompt):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
        
    #     elif tier_level == 4:  # Toolchain
    #         if use_orchestrator:
    #             task_id = self.orchestrator.submit_task(
    #                 "toolchain.execute",
    #                 vera_instance=self,
    #                 query=prompt
    #             )
                
    #             for chunk in self.orchestrator.stream_result(task_id, timeout=120.0):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
    #         else:
    #             for chunk in self.toolchain_expert.execute_tool_chain(prompt):
    #                 chunk_text = extract_chunk_text(chunk)
    #                 tier_response += chunk_text
    #                 yield chunk_text
        
    #     return tier_response

    # def _build_ramp_prompt(self, tier_level, base_query, previous_responses):
    #     """Build progressive refinement prompt for a given tier"""
        
    #     if tier_level == 1:  # Intermediate
    #         return f"""Quick answer provided:
    # {previous_responses[:500]}...

    # Expand on this with more detail and context for: {base_query}"""
        
    #     elif tier_level == 2:  # Deep
    #         return f"""Previous analysis:
    # {previous_responses[:800]}...

    # Provide comprehensive, in-depth response for: {base_query}"""
        
    #     elif tier_level == 3:  # Reasoning
    #         return f"""Building on previous work:
    # {previous_responses[:1000]}...

    # Apply deep reasoning, step-by-step analysis for: {base_query}"""
        
    #     elif tier_level == 4:  # Toolchain
    #         return f"""Context from analysis:
    # {previous_responses[:800]}...

    # Execute appropriate tools/actions for: {base_query}"""
        
    #     else:
    #         return base_query
        
    # def _execute_counsel_mode(self, query, context):
    #     """
    #     Counsel mode: Multiple models/instances deliberate on the same query
        
    #     Modes:
    #         - race: Fastest response wins
    #         - synthesis: Combine all responses into one
    #         - vote: Most common/best response wins (uses fast model as judge)
    #     """
        
    #     counsel_config = getattr(self.config, 'counsel', {
    #         'mode': 'vote',
    #         'models': ['fast', 'fast', 'fast'],
    #         'instances': None  # If set, overrides models to use specific instances
    #     })
        
    #     counsel_mode = counsel_config.get('mode', 'race')
    #     counsel_models = counsel_config.get('models', ['fast', 'intermediate', 'reasoning'])
    #     counsel_instances = counsel_config.get('instances', None)
        
    #     # Determine execution strategy
    #     if counsel_instances:
    #         # Use specific Ollama instances (can be same model on different instances)
    #         strategy = "instances"
    #         executors = counsel_instances
    #         self.logger.info(
    #             f"🏛️ Counsel mode: {counsel_mode} using instances: {executors}",
    #             context=context
    #         )
    #     else:
    #         # Use different model tiers
    #         strategy = "models"
    #         executors = counsel_models
    #         self.logger.info(
    #             f"🏛️ Counsel mode: {counsel_mode} using models: {executors}",
    #             context=context
    #         )
        
    #     import threading
    #     import queue
        
    #     response_queue = queue.Queue()
        
    #     # ====================================================================
    #     # INSTANCE-BASED EXECUTION
    #     # ====================================================================
        
    #     if strategy == "instances":
    #         # Map instance names to actual Ollama instances
    #         instance_map = {}
            
    #         for instance_spec in executors:
    #             # Format: "instance_name:model_name" or just "instance_name" (uses default model)
    #             if ':' in instance_spec:
    #                 instance_name, model_name = instance_spec.split(':', 1)
    #             else:
    #                 instance_name = instance_spec
    #                 model_name = self.selected_models.fast_llm  # Default model
                
    #             instance_map[instance_spec] = {
    #                 'instance': instance_name,
    #                 'model': model_name
    #             }
            
    #         def run_instance(spec, instance_info, label):
    #             try:
    #                 self.logger.debug(f"Counsel: Starting {label}", context=context)
    #                 start_time = time.time()
                    
    #                 # Create LLM restricted to this specific instance
    #                 llm = self.ollama_manager.create_llm_with_routing(
    #                     model=instance_info['model'],
    #                     routing_mode='manual',
    #                     selected_instances=[instance_info['instance']],
    #                     temperature=0.7
    #                 )
                    
    #                 response = ""
    #                 for chunk in self.stream_llm(llm, query):
    #                     response += extract_chunk_text(chunk)
                    
    #                 duration = time.time() - start_time
                    
    #                 response_queue.put((label, response, duration, time.time()))
                    
    #                 self.logger.success(
    #                     f"Counsel: {label} completed in {duration:.2f}s",
    #                     context=context
    #                 )
                
    #             except Exception as e:
    #                 self.logger.error(f"Counsel: {label} failed: {e}", context=context)
            
    #         # Launch threads
    #         threads = []
    #         for idx, (spec, info) in enumerate(instance_map.items()):
    #             label = f"{info['model']}@{info['instance']}"
    #             thread = threading.Thread(
    #                 target=run_instance,
    #                 args=(spec, info, label),
    #                 daemon=True
    #             )
    #             thread.start()
    #             threads.append(thread)
        
    #     # ====================================================================
    #     # MODEL-BASED EXECUTION
    #     # ====================================================================
        
    #     else:
    #         # Map model types to LLMs
    #         model_map = {
    #             'fast': self.fast_llm,
    #             'intermediate': self.intermediate_llm if hasattr(self, 'intermediate_llm') else self.fast_llm,
    #             'deep': self.deep_llm,
    #             'reasoning': self.reasoning_llm
    #         }
            
    #         def run_model(model_type, model_llm, label):
    #             try:
    #                 self.logger.debug(f"Counsel: Starting {label}", context=context)
    #                 start_time = time.time()
                    
    #                 response = ""
    #                 for chunk in self.stream_llm(model_llm, query):
    #                     response += extract_chunk_text(chunk)
                    
    #                 duration = time.time() - start_time
                    
    #                 response_queue.put((label, response, duration, time.time()))
                    
    #                 self.logger.success(
    #                     f"Counsel: {label} completed in {duration:.2f}s",
    #                     context=context
    #                 )
                
    #             except Exception as e:
    #                 self.logger.error(f"Counsel: {label} failed: {e}", context=context)
            
    #         # Launch threads
    #         threads = []
    #         for idx, model_type in enumerate(counsel_models):
    #             if model_type in model_map:
    #                 # Add index to label if same model appears multiple times
    #                 count = counsel_models[:idx+1].count(model_type)
    #                 label = f"{model_type.title()}" + (f" #{count}" if counsel_models.count(model_type) > 1 else "")
                    
    #                 thread = threading.Thread(
    #                     target=run_model,
    #                     args=(model_type, model_map[model_type], label),
    #                     daemon=True
    #                 )
    #                 thread.start()
    #                 threads.append(thread)
        
    #     # ====================================================================
    #     # MODE: RACE (Fastest Wins)
    #     # ====================================================================
        
    #     if counsel_mode == 'race':
    #         try:
    #             winner_label, winner_response, duration, completion_time = response_queue.get(timeout=120.0)
                
    #             self.logger.success(
    #                 f"🏆 Counsel winner: {winner_label} ({duration:.2f}s)",
    #                 context=context
    #             )
                
    #             yield f"\n\n--- Counsel Mode: Race Winner ---\n"
    #             yield f"**{winner_label}** (completed in {duration:.2f}s)\n\n"
    #             yield winner_response
                
    #             return winner_response
            
    #         except queue.Empty:
    #             self.logger.error("Counsel: All models timed out", context=context)
    #             yield "\n\n--- Counsel Mode: Error ---\nAll models timed out\n"
    #             return "Error: All counsel models timed out"
        
    #     # ====================================================================
    #     # MODE: SYNTHESIS (Combine All)
    #     # ====================================================================
        
    #     elif counsel_mode == 'synthesis':
    #         responses = []
            
    #         # Wait for all models (with timeout)
    #         for _ in range(len(threads)):
    #             try:
    #                 label, response, duration, completion_time = response_queue.get(timeout=120.0)
    #                 responses.append((label, response, duration))
    #             except queue.Empty:
    #                 break
            
    #         if not responses:
    #             self.logger.error("Counsel: No models completed", context=context)
    #             yield "\n\n--- Counsel Mode: Error ---\nNo models completed\n"
    #             return "Error: No counsel models completed"
            
    #         self.logger.info(
    #             f"Counsel: Collected {len(responses)} responses, synthesizing...",
    #             context=context
    #         )
            
    #         # Display individual responses
    #         yield f"\n\n--- Counsel Mode: Synthesis ({len(responses)} perspectives) ---\n\n"
            
    #         for label, response, duration in responses:
    #             yield f"**{label}** ({duration:.2f}s):\n{response[:300]}{'...' if len(response) > 300 else ''}\n\n"
            
    #         # Synthesize using fast model
    #         synthesis_prompt = f"""Multiple AI perspectives on this query: {query}

    # Perspectives:
    # """
            
    #         for label, response, duration in responses:
    #             synthesis_prompt += f"\n**{label}**:\n{response[:800]}{'...' if len(response) > 800 else ''}\n\n"
            
    #         synthesis_prompt += """
    # Synthesize these perspectives into a single, coherent response that:
    # 1. Captures the best insights from each perspective
    # 2. Highlights areas of agreement
    # 3. Notes any important differences or unique contributions
    # 4. Provides a unified conclusion

    # Keep the synthesis concise and actionable."""
            
    #         yield "--- Synthesis ---\n"
            
    #         synthesis_response = ""
    #         for chunk in self.stream_llm(self.fast_llm, synthesis_prompt):
    #             chunk_text = extract_chunk_text(chunk)
    #             synthesis_response += chunk_text
    #             yield chunk_text
            
    #         return synthesis_response
        
    #     # ====================================================================
    #     # MODE: VOTE (Judge Selects Best)
    #     # ====================================================================
        
    #     elif counsel_mode == 'vote':
    #         responses = []
            
    #         # Wait for all models (with timeout)
    #         for _ in range(len(threads)):
    #             try:
    #                 label, response, duration, completion_time = response_queue.get(timeout=120.0)
    #                 responses.append((label, response, duration))
    #             except queue.Empty:
    #                 break
            
    #         if not responses:
    #             self.logger.error("Counsel: No models completed", context=context)
    #             yield "\n\n--- Counsel Mode: Error ---\nNo models completed\n"
    #             return "Error: No counsel models completed"
            
    #         if len(responses) == 1:
    #             # Only one response, use it
    #             label, response, duration = responses[0]
                
    #             self.logger.info(
    #                 f"Counsel: Only one response from {label}, using it",
    #                 context=context
    #             )
                
    #             yield f"\n\n--- Counsel Mode: Vote (Only One Response) ---\n"
    #             yield f"**{label}** ({duration:.2f}s)\n\n"
    #             yield response
                
    #             return response
            
    #         self.logger.info(
    #             f"Counsel: Collected {len(responses)} responses, voting...",
    #             context=context
    #         )
            
    #         # Display all responses
    #         yield f"\n\n--- Counsel Mode: Vote ({len(responses)} candidates) ---\n\n"
            
    #         for idx, (label, response, duration) in enumerate(responses, 1):
    #             yield f"**Candidate {idx}: {label}** ({duration:.2f}s)\n{response[:200]}{'...' if len(response) > 200 else ''}\n\n"
            
    #         # Judge using fast model (or configurable judge model)
    #         judge_model = getattr(counsel_config, 'judge_model', 'fast')
    #         judge_llm = {
    #             'fast': self.fast_llm,
    #             'intermediate': self.intermediate_llm if hasattr(self, 'intermediate_llm') else self.fast_llm,
    #             'deep': self.deep_llm,
    #             'reasoning': self.reasoning_llm
    #         }.get(judge_model, self.fast_llm)
            
    #         vote_prompt = f"""You are judging multiple AI responses to select the BEST one.

    # Original Query: {query}

    # Candidates:
    # """
            
    #         for idx, (label, response, duration) in enumerate(responses, 1):
    #             vote_prompt += f"\n**Candidate {idx} ({label})**:\n{response}\n\n"
            
    #         vote_prompt += f"""
    # Evaluate each candidate on:
    # 1. Accuracy and correctness
    # 2. Completeness and depth
    # 3. Clarity and coherence
    # 4. Relevance to the query
    # 5. Practical value

    # Respond with ONLY the candidate number (1-{len(responses)}) of the BEST response, followed by a brief 1-2 sentence explanation.
    # Format: "Candidate X: [reason]"
    # """
            
    #         yield "--- Voting ---\n"
            
    #         self.logger.info("Counsel: Judge evaluating responses...", context=context)
            
    #         vote_result = ""
    #         for chunk in self.stream_llm(judge_llm, vote_prompt):
    #             chunk_text = extract_chunk_text(chunk)
    #             vote_result += chunk_text
    #             yield chunk_text
            
    #         yield "\n\n"
            
    #         # Parse vote result to extract winner
    #         import re
    #         match = re.search(r'Candidate\s+(\d+)', vote_result, re.IGNORECASE)
            
    #         if match:
    #             winner_idx = int(match.group(1)) - 1
                
    #             if 0 <= winner_idx < len(responses):
    #                 winner_label, winner_response, winner_duration = responses[winner_idx]
                    
    #                 self.logger.success(
    #                     f"🏆 Counsel vote winner: Candidate {winner_idx + 1} ({winner_label})",
    #                     context=context
    #                 )
                    
    #                 yield f"--- Selected Response ---\n"
    #                 yield f"**{winner_label}** (selected by vote)\n\n"
    #                 yield winner_response
                    
    #                 return winner_response
    #             else:
    #                 self.logger.warning(
    #                     f"Invalid vote index {winner_idx + 1}, using first response",
    #                     context=context
    #                 )
    #         else:
    #             self.logger.warning(
    #                 "Could not parse vote result, using first response",
    #                 context=context
    #             )
            
    #         # Fallback to first response
    #         label, response, duration = responses[0]
            
    #         yield f"--- Selected Response (Fallback) ---\n"
    #         yield f"**{label}**\n\n"
    #         yield response
            
    #         return response
        
    #     else:
    #         self.logger.error(f"Unknown counsel mode: {counsel_mode}", context=context)
    #         yield f"\n\nError: Unknown counsel mode '{counsel_mode}'\n"
    #         return f"Error: Unknown counsel mode '{counsel_mode}'"

    # def _triage_direct(self, query):
    #     """Direct triage without orchestrator (fallback)"""
    #     triage_context = LogContext(
    #         session_id=self.sess.id,
    #         agent="triage"
    #     )
        
    #     # Use triage agent if available
    #     if self.agents:
    #         agent_name = self.get_agent_for_task('triage')
    #         triage_llm = self.create_llm_for_agent(agent_name)
    #         triage_context.agent = agent_name
    #         triage_context.model = agent_name
    #     else:
    #         triage_llm = self.fast_llm
    #         triage_context.model = self.selected_models.fast_llm
        
    #     self.logger.debug("Using triage agent", context=triage_context)
        
    #     triage_prompt = f"""
    #     Classify this Query into one of the following categories:
    #         - 'focus'      → Change the focus of background thought.
    #         - 'proactive'  → Trigger proactive thinking.
    #         - 'simple'     → Simple textual response.
    #         - 'toolchain'  → Requires a series of tools or step-by-step planning.
    #         - 'reasoning'  → Requires deep reasoning.
    #         - 'complex'    → Complex written response with high-quality output.

    #     Current focus: {self.focus_manager.focus if hasattr(self, 'focus_manager') else 'None'}

    #     Query: {query}

    #     Respond with a single classification term (e.g., 'simple', 'toolchain', 'complex') on the first line.
    #     """
        
    #     for chunk in self.stream_llm(triage_llm, triage_prompt):
    #         yield chunk

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

    def _stream_orchestrator_with_thoughts(self, task_id: str, timeout: float = 60.0):
        """Stream orchestrator results while also polling thought queue"""
        from queue import Empty
        import time
        
        last_check = time.time()
        in_thought = False  # Track if we're in a thought stream
        
        for chunk in self.orchestrator.stream_result(task_id, timeout=timeout):
            # Check thoughts every 50ms
            if time.time() - last_check > 0.05:
                try:
                    while True:
                        thought_chunk = self.thought_queue.get_nowait()
                        
                        # Start thought block if not already started
                        if not in_thought:
                            yield "\n<thought>"
                            in_thought = True
                        
                        # Yield the raw chunk (no formatting)
                        yield thought_chunk
                        
                except Empty:
                    pass
                last_check = time.time()
            
            # Regular chunk - close thought if needed
            if in_thought:
                yield "</thought>\n"
                in_thought = False
            
            # Yield orchestrator chunk
            yield chunk
        
        # Final thought drain
        try:
            while True:
                thought_chunk = self.thought_queue.get_nowait()
                
                if not in_thought:
                    yield "\n<thought>"
                    in_thought = True
                
                yield thought_chunk
                
        except Empty:
            pass
        
        # Close any open thought
        if in_thought:
            yield "</thought>\n"
            
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