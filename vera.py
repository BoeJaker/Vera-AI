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

from Vera.vera_chat import VeraChat
from Vera.Ollama.Agents.Scheduling.executive_0_9 import executive
from Vera.Memory.memory import *
from Vera.Toolchain.toolchain import ToolChainPlanner

# ── MIGRATION: replaced direct ToolLoader import ──────────────────────────────
# OLD: from Vera.Toolchain.tools import ToolLoader
# NEW: load_tools() wraps ToolLoader and wires the enhanced framework
from Vera.Toolchain.ToolFramework.bridge import load_tools
# ── MIGRATION: replaced setup_toolchain import ────────────────────────────────
# OLD: from Vera.Toolchain.toolchain import setup_toolchain
# NEW: setup_toolchain_enhanced uses RegistryAwareToolChainPlanner
from Vera.Toolchain.ToolFramework.integration import setup_toolchain_enhanced
# ─────────────────────────────────────────────────────────────────────────────

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
from Vera.EventBus.integration import setup_event_bus_sync
import Vera.Orchestration.toolchain_tasks 

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
    - Enhanced tool framework: registry, event bus, service manager, ToolContext
    """

    def __init__(
        self, 
        config_file: str = "Configuration/vera_config.yaml",
        chroma_path: Optional[str] = None,
        ollama_api_url: Optional[str] = None,
        **kwargs
    ):
        # --- Load Configuration ---
        print("[Vera] Loading configuration...")
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.config
        
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
        
        self.logger.info("Configuration loaded successfully")
        self.logger.debug("Configuration details:")
        self.logger.debug(json.dumps(self.config, indent=4, default=str))

        self.config_manager.register_callback(self._on_config_reload)
        
        if chroma_path:
            self.config.memory.chroma_path = chroma_path
            self.logger.debug(f"Memory path overridden: {chroma_path}")
        if ollama_api_url:
            self.config.ollama.api_url = ollama_api_url
            self.logger.debug(f"Ollama API URL overridden: {ollama_api_url}")
        
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
        
        self.base_context = LogContext(
            session_id=None,
            agent="vera"
        )
        
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
    
        self.coding_llm_llm = self.ollama_manager.create_llm(
            model=self.selected_models.coding_llm, 
            temperature=self.selected_models.coding_temperature
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

        
        # --- Proactive Focus Manager ---
        if self.config.proactive_focus.enabled:
            self.logger.info("Initializing proactive focus manager...")
            self.focus_manager = ProactiveFocusManager(
                agent=self,
                hybrid_memory=self.mem if hasattr(self, 'mem') else None,
                proactive_interval=3600,
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
        

        resource_limits = ResourceLimits(
            max_cpu_percent=70.0,
            max_memory_percent=80.0,
            max_ollama_concurrent=1
        )
        
        resource_monitor = ResourceMonitor(limits=resource_limits)
        resource_monitor.start()
        
        resource_manager = ExternalResourceManager(
            hybrid_memory=self.mem if hasattr(self, 'mem') else None
        )
        self.stage_orchestrator = StageOrchestrator()
        self.calendar_scheduler = CalendarScheduler()

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
        

        # ===== AGENT CONFIGURATION SYSTEM =====
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
        else:
            self.logger.info("Using Standard Orchestrator")
            self.orchestrator = Orchestrator(
                config=orchestrator_config,
                redis_url=self.config.orchestrator.redis_url,
                cpu_threshold=self.config.orchestrator.cpu_threshold,
            )

        self.orchestrator.start()
        self.logger.success("Orchestrator started")
        # ── EVENT BUS ──────────────────────────────────────────────────────────
        self.logger.info("Initialising event bus...")
        try:
            self.bus = setup_event_bus_sync(self)
            if self.bus:
                self.logger.success("Event bus online (Redis + Postgres).")
            else:
                self.logger.warning("Event bus failed to start — continuing without it.")
                self.bus = None
        except Exception as _bus_err:
            self.logger.error(f"Event bus init error: {_bus_err}")
            self.bus = None
        # ───────────────────────────────────────────────────────────────────────
        if self.focus_manager:
            self.proactive_orchestrator = ProactiveFocusOrchestrator(
                self.orchestrator, 
                self.focus_manager
            )
            self.logger.debug("Proactive orchestrator integrated")

        # --- Setup Memory from Config ---
        self.logger.info("Initializing memory systems...")
        self.logger.start_timer("memory_initialization")
        
        self.mem = HybridMemory(
            neo4j_uri=self.config.memory.neo4j_uri,
            neo4j_user=self.config.memory.neo4j_user,
            neo4j_password=self.config.memory.neo4j_password,
            chroma_dir=self.config.memory.chroma_dir,
            archive_jsonl=self.config.memory.archive_path,
            orchestrator=self.orchestrator,
        )
        
        self.sess = self.mem.start_session(metadata={"agent": "vera"})
        
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
        
        self.triage_memory = self.config.memory.enable_memory_triage
        self.memory = CombinedMemory(
            memories=[self.buffer_memory, self.vector_memory]
        )
        

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

        # --- Initialize Unified Project Sandbox ---
        from Vera.Toolchain.sandbox import ProjectSandbox, get_project_sandbox
        _default_project_root = os.path.abspath("./Output/Default")
        self._project_sandbox_root = _default_project_root
        self._sandbox = ProjectSandbox(_default_project_root)
        self._sandbox._agent_ref = self        
        self.runtime_sandbox = self._sandbox
       
        # --- Initialize Executive ---
        self.logger.info("Loading tools...")
        self.executive_instance = executive(vera_instance=self)
        
        # ── MIGRATION: replaced ToolLoader(self) with load_tools(self) ────────
        # This is the only change in the tool-loading block.
        # load_tools() calls ToolLoader internally, then:
        #   - registers all tools in a ToolRegistry (heuristic categories)
        #   - attaches self.tool_registry, self.tool_event_bus,
        #     self.service_manager, self.create_tool_context to this agent
        #   - returns the identical List[BaseTool] ToolLoader would have returned
        #
        # Playwright tools are appended afterwards exactly as before so they
        # are in self.tools but do NOT go through the registry (they have no
        # args_schema and don't need category filtering).
        raw_toolkit = load_tools(self)
        self.tools = raw_toolkit + self.playwright_tools
        # ─────────────────────────────────────────────────────────────────────

        # Sandbox wrapping (unchanged)
        self.tools = self._sandbox.wrap_tools(self.tools)
        self.toolkit = self.tools
        self.logger.success(
            f"Tools wrapped with sandbox (root={self._sandbox.project_root})"
        )

        # Multi-param compatibility (unchanged)
        from Vera.Toolchain.multiparam import wrap_tools_multiarg
        self.tools = wrap_tools_multiarg(self.tools)

        # Log loaded tools
        tool_list_path = os.path.join(
            os.path.dirname(__file__),
            "Ollama", "Agents", "agents", "tool-agent", "includes", "tool_list.txt"
        )
        os.makedirs(os.path.dirname(tool_list_path), exist_ok=True)
        self.save_tool_list_with_schemas(tool_list_path)
        self.logger.info(f"Tool list with schemas written to {tool_list_path}")
        self.logger.success(f"Loaded {len(self.tools)} total tools")

        # Warm up fast LLM
        fast_task_id = self.orchestrator.submit_task(
            "llm.fast",
            vera_instance=self,
            prompt="hello"
        )

        # --- Initialize LangChain Agents ---
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

        # ── MIGRATION: replaced setup_toolchain() with setup_toolchain_enhanced()
        # Must come AFTER load_tools() so self.tool_registry already exists.
        # Sets vera.toolchain, vera.toolchain_expert, vera._adaptive_toolchain
        # All three point to a RegistryAwareToolChainPlanner which is a
        # transparent drop-in for ToolChainPlanner with O(1) tool lookup and
        # optional agent_type= filtering on execute_tool_chain().
        setup_toolchain_enhanced(self)
        # ─────────────────────────────────────────────────────────────────────

        if self.focus_manager:
            def handle_proactive(thought):
                self.logger.thought(thought, context=LogContext(agent="proactive"))
            self.focus_manager.proactive_callback = handle_proactive
        
        # Initialize chat handler
        self.chat = VeraChat(self)

        # --- Messaging Bots ---
        self.telegram_bot = None
        self.bot_manager = None

        if self.config.bots.enabled and self.config.bots.auto_start:
            self.logger.info("Initializing messaging bots...")
            self._initialize_bots()
 
        self.logger.success("Vera initialization complete!")
        self.logger.info(f"Session ID: {self.sess.id}")

        # Log registry summary so it's visible in startup output
        if hasattr(self, 'tool_registry'):
            summary = self.tool_registry.summary()
            self.logger.info(
                f"Tool registry: {summary['total_tools']} tools "
                f"({summary['enhanced']} enhanced, {summary['legacy']} legacy), "
                f"{summary['services']} services, {summary['ui_tools']} with UI"
            )

    # =========================================================================
    # set_project_root — updated to use load_tools instead of ToolLoader
    # =========================================================================

    def set_project_root(self, path: str) -> None:
        """
        Change the active sandbox project root.

        Call this whenever the user (or a stage) selects a different
        working directory. All subsequent tool writes will go to *path*.

        Args:
            path: Absolute or relative path to the new project root.
                  Relative paths are resolved from the current working
                  directory at call time.
        """
        abs_path = os.path.abspath(path)
        self._project_sandbox_root = abs_path
        self._sandbox.set_project_root(abs_path)
        self._sandbox._agent_ref = self      
        self.runtime_sandbox = self._sandbox

        from Vera.Toolchain.multiparam import wrap_tools_multiarg

        # ── MIGRATION: use load_tools instead of ToolLoader ───────────────────
        # load_tools re-registers all tools into the existing registry so the
        # registry stays current after a root change.
        raw_tools = load_tools(self) + self.playwright_tools
        # ─────────────────────────────────────────────────────────────────────
        raw_tools = wrap_tools_multiarg(raw_tools)
        self.tools = self._sandbox.wrap_tools(raw_tools)
        self.toolkit = self.tools

        # Propagate to toolchain planners
        if hasattr(self, 'toolchain') and hasattr(self.toolchain, 'tools'):
            self.toolchain.tools = self.tools
        if hasattr(self, '_enhanced_toolchain') and hasattr(self._enhanced_toolchain, 'tools'):
            self._enhanced_toolchain.tools = self.tools

        # Propagate to focus_manager sandbox cache
        if hasattr(self, 'focus_manager') and self.focus_manager:
            self.focus_manager._sandbox = self._sandbox

        if hasattr(self, 'logger'):
            self.logger.success(f"Project root updated → {abs_path}")

    # =========================================================================
    # All methods below are UNCHANGED from the original vera.py
    # =========================================================================

    def _initialize_bots(self):
        """Initialize and start messaging bots in background"""
        try:
            from Vera.ChatBots.run_bots import BotManager
            import threading
            import asyncio
            
            bot_config = {}
            
            for platform in ['telegram', 'discord', 'slack']:
                platform_cfg = getattr(self.config.bots.platforms, platform, None)
                
                if platform_cfg and platform_cfg.enabled:
                    bot_config[platform] = {
                        'enabled': True,
                        'token': platform_cfg.token,
                    }
                    
                    if platform == 'telegram':
                        bot_config[platform]['allowed_users'] = platform_cfg.allowed_users or []
                        bot_config[platform]['owner_ids'] = self.config.bots.security.owner_ids or []
                    elif platform in ['discord', 'slack']:
                        bot_config[platform]['allowed_channels'] = platform_cfg.allowed_channels or []
            
            enabled_platforms = [p for p, cfg in bot_config.items() if cfg.get('enabled')]
            
            if not enabled_platforms:
                self.logger.warning("Bots enabled but no platforms configured")
                return
            
            self.logger.info(f"Starting bots for: {', '.join(enabled_platforms)}")
            
            self.bot_manager = BotManager(bot_config, vera_instance=self)
            
            if 'telegram' in enabled_platforms:
                from Vera.ChatBots.telegram_bot import TelegramBot
                self.telegram_bot = TelegramBot(self, bot_config['telegram'])
            
            if self.config.bots.background_thread:
                def run_bots():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.bot_manager.run())
                    finally:
                        loop.close()
                
                bot_thread = threading.Thread(target=run_bots, daemon=True, name="BotManager")
                bot_thread.start()
                self.logger.success(f"Bots running in background thread: {', '.join(enabled_platforms)}")
            else:
                self.logger.warning("background_thread=false - bots will run in main thread (blocking)")
        
        except ImportError as e:
            self.logger.error(f"Failed to import bot components: {e}")
            self.logger.info("Install bot dependencies: pip install python-telegram-bot discord.py slack-sdk")
        
        except Exception as e:
            self.logger.error(f"Failed to initialize bots: {e}", exc_info=True)

    def start_bots(self, platforms=None, config_file=None):
        """Start messaging bots using this Vera instance"""
        from Vera.ChatBots.run_bots import BotManager, load_config_from_env, load_config_from_file
        import asyncio
        
        self.logger.info("Starting messaging bots...")
        
        if config_file:
            self.logger.info(f"Loading bot config from {config_file}")
            config = load_config_from_file(config_file)
        elif platforms:
            config = self._build_bot_config_from_vera_config()
            for platform in config:
                config[platform]['enabled'] = platform in platforms
        else:
            config = self._build_bot_config_from_vera_config()
        
        enabled = [p for p, cfg in config.items() if cfg.get('enabled', False)]
        
        if not enabled:
            self.logger.error("❌ No platforms enabled!")
            self.logger.info("Configure in vera_config.yaml under bots.platforms")
            return
        
        self.logger.info(f"Enabled platforms: {', '.join(enabled)}")
            
        self.bot_manager = BotManager(config, vera_instance=self)
        
        if 'telegram' in enabled:
            from Vera.ChatBots.telegram_bot import TelegramBot
            self.telegram_bot = TelegramBot(self, config['telegram'])
        
        self.logger.info(f"Launching bots: {', '.join(enabled)}")
        
        try:
            loop = asyncio.get_running_loop()
            self.logger.warning("Event loop already running - using background thread")
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(self.bot_manager.run())
                finally:
                    new_loop.close()
            
            import threading
            thread = threading.Thread(target=run_in_thread, daemon=True, name="BotManager")
            thread.start()
            self.logger.success("✓ Bots running in background thread")
            
        except RuntimeError:
            self.logger.info("Starting new event loop...")
            try:
                asyncio.run(self.bot_manager.run())
            except KeyboardInterrupt:
                self.logger.info("✓ Shutdown complete")

    def _build_bot_config_from_vera_config(self) -> dict:
        """Build bot config dict from Vera config"""
        config = {}
        
        for platform in ['telegram', 'discord', 'slack']:
            platform_cfg = getattr(self.config.bots.platforms, platform, None)
            
            if platform_cfg:
                token = platform_cfg.token or os.getenv(f'{platform.upper()}_BOT_TOKEN')
                
                config[platform] = {
                    'enabled': platform_cfg.enabled,
                    'token': token,
                    'bot_token': token,
                }
                
                if platform == 'telegram':
                    config[platform]['allowed_users'] = platform_cfg.allowed_users or []
                    config[platform]['owner_ids'] = self.config.bots.security.owner_ids or []
                elif platform in ['discord', 'slack']:
                    config[platform]['allowed_channels'] = platform_cfg.allowed_channels or []
        
        return config

    def save_tool_list_with_schemas(self, tool_list_path: str):
        with open(tool_list_path, "w") as tool_file:
            tool_file.write("=" * 80 + "\n")
            tool_file.write("VERA TOOLCHAIN - AVAILABLE TOOLS\n")
            tool_file.write("=" * 80 + "\n\n")
            
            for idx, tool in enumerate(self.tools, 1):
                tool_file.write(f"\n[{idx}] {tool.name}\n")
                tool_file.write("-" * 80 + "\n")
                tool_file.write(f"DESCRIPTION:\n  {tool.description}\n\n")
                
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        schema = tool.args_schema.schema()
                        tool_file.write("INPUT PARAMETERS:\n")
                        properties = schema.get('properties', {})
                        required_fields = schema.get('required', [])
                        
                        if properties:
                            for param_name, param_info in properties.items():
                                param_type = param_info.get('type', 'string')
                                param_desc = param_info.get('description', 'No description')
                                is_required = param_name in required_fields
                                required_marker = " [REQUIRED]" if is_required else " [OPTIONAL]"
                                tool_file.write(f"  • {param_name}{required_marker}\n")
                                tool_file.write(f"    Type: {param_type}\n")
                                tool_file.write(f"    Description: {param_desc}\n")
                                if 'default' in param_info:
                                    tool_file.write(f"    Default: {param_info['default']}\n")
                                if 'enum' in param_info:
                                    tool_file.write(f"    Allowed values: {', '.join(map(str, param_info['enum']))}\n")
                                tool_file.write("\n")
                        else:
                            tool_file.write("  (No parameters required)\n\n")
                    except Exception as e:
                        tool_file.write(f"INPUT SCHEMA: Error extracting schema - {str(e)}\n")
                else:
                    tool_file.write("INPUT SCHEMA: No schema defined\n")
                
                tool_file.write("\n" + "=" * 80 + "\n")

    def _setup_unified_logging(self):
        """Setup unified logging system from config"""
        log_cfg = self.config.logging
        
        component_levels = {}
        for component, level_str in getattr(log_cfg, 'component_levels', {}).items():
            try:
                component_levels[component] = LogLevel[level_str.upper()]
            except KeyError:
                component_levels[component] = LogLevel.INFO
        
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
        
        self.logger = get_logger("vera", vera_log_config)
    
    def _on_config_reload(self, old_config: VeraConfig, new_config: VeraConfig):
        """Handle configuration reload"""
        self.logger.info("Configuration reloaded!")
        self.config = new_config
        changes = []
        
        if old_config.models.fast_llm != new_config.models.fast_llm:
            changes.append(f"Fast LLM: {old_config.models.fast_llm} → {new_config.models.fast_llm}")
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
    
    def get_infrastructure_stats(self):
        """Get infrastructure statistics (if enabled)"""
        if self.enable_infrastructure and hasattr(self.orchestrator, 'get_infrastructure_stats'):
            stats = self.orchestrator.get_infrastructure_stats()
            self.logger.infrastructure_event("stats_retrieved", details=stats)
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
        self.thoughts_captured.append({
            'timestamp': time.time(),
            'thought': thought,
            'session_id': self.sess.id if hasattr(self, 'sess') else None
        })
        
        if hasattr(self, 'logger'):
            context = LogContext(
                session_id=self.sess.id if hasattr(self, 'sess') else None,
                agent="reasoning",
                model="reasoning_llm"
            )
            self.logger.thought(thought, context=context)
        
        if self.stream_thoughts_inline:
            self.thought_queue.put(thought)
    
    def _stream_with_thought_polling(self, llm, prompt):
        """Stream LLM output with immediate thought injection"""
        import threading
        from queue import Empty
        
        chunk_queue = queue.Queue()
        streaming_done = threading.Event()
        
        def stream_in_thread():
            try:
                for chunk in llm.stream(prompt):
                    text = extract_chunk_text(chunk)
                    text = text.replace('<thought>', '').replace('</thought>', '')
                    chunk_queue.put(('chunk', text))
            except Exception as e:
                self.logger.error(f"Stream error: {e}", exc_info=True)
                chunk_queue.put(('error', str(e)))
            finally:
                streaming_done.set()
        
        thread = threading.Thread(target=stream_in_thread, daemon=True)
        thread.start()
        
        last_check = time.time()
        in_thought = False
        
        while not streaming_done.is_set() or not chunk_queue.empty() or not self.thought_queue.empty():
            if time.time() - last_check > 0.05:
                try:
                    while True:
                        thought_chunk = self.thought_queue.get_nowait()
                        if not in_thought:
                            yield "\n<thought>"
                            in_thought = True
                        yield thought_chunk
                except Empty:
                    pass
                last_check = time.time()
            
            try:
                item_type, item_data = chunk_queue.get(timeout=0.05)
                if item_type == 'chunk':
                    if in_thought:
                        yield "</thought>\n"
                        in_thought = False
                    yield item_data
                elif item_type == 'error':
                    self.logger.error(f"Stream error: {item_data}")
                    break
            except Empty:
                continue
        
        try:
            while True:
                thought_chunk = self.thought_queue.get_nowait()
                if not in_thought:
                    yield "\n<thought>"
                    in_thought = True
                yield thought_chunk
        except Empty:
            pass
        
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
        
        for item in self._stream_with_thought_polling(llm, prompt):
            if not item.startswith('<thought>') and not item.endswith('</thought>'):
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
        
    def async_run(self, query: str, routing_hints: Optional[Dict] = None, **kwargs) -> Iterator[str]:
        """Delegate to chat.async_run with routing hints"""
        if hasattr(self, 'chat') and self.chat:
            yield from self.chat.async_run(query, routing_hints=routing_hints, **kwargs)
        else:
            yield "Error: Chat system not initialized"

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
        in_thought = False
        
        for chunk in self.orchestrator.stream_result(task_id, timeout=timeout):
            if time.time() - last_check > 0.05:
                try:
                    while True:
                        thought_chunk = self.thought_queue.get_nowait()
                        if not in_thought:
                            yield "\n<thought>"
                            in_thought = True
                        yield thought_chunk
                except Empty:
                    pass
                last_check = time.time()
            
            if in_thought:
                yield "</thought>\n"
                in_thought = False
            
            yield chunk
        
        try:
            while True:
                thought_chunk = self.thought_queue.get_nowait()
                if not in_thought:
                    yield "\n<thought>"
                    in_thought = True
                yield thought_chunk
        except Empty:
            pass
        
        if in_thought:
            yield "</thought>\n"

    def telegram_notify(self, message: str, user_id: Optional[int] = None) -> bool:
        """Send a Telegram notification (sync wrapper for async method)."""
        if not hasattr(self, 'telegram_bot') or not self.telegram_bot:
            self.logger.warning("Telegram bot not initialized")
            return False

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if user_id:
            coro = self.telegram_bot.send_to_user(user_id, message)
        else:
            coro = self.telegram_bot.send_to_owners(message)

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=10)
        else:
            return loop.run_until_complete(coro)

    def telegram_queue_message(self, message: str, user_id: Optional[int] = None):
        """Queue a Telegram message for async sending (non-blocking)."""
        if not hasattr(self, 'telegram_bot') or not self.telegram_bot:
            self.logger.warning("Telegram bot not initialized")
            return

        if user_id is None:
            from Vera.ChatBots.telegram_bot import SecurityConfig
            for owner_id in SecurityConfig.OWNERS:
                asyncio.create_task(
                    self.telegram_bot.queue_message(owner_id, message)
                )
        else:
            asyncio.create_task(
                self.telegram_bot.queue_message(user_id, message)
            )

    # async def emit(self, event_type: str, payload: dict, priority: bool = False, **meta):
    #     \"\"\"Convenience: publish a bus event from anywhere that has a vera ref.\"\"\"
    #     if not self.bus:
    #         return
    #     from Vera.EventBus.event_model import Event
    #     meta.setdefault("session_id", self.sess.id if hasattr(self, "sess") else None)
    #     await self.bus.publish(
    #         Event(type=event_type, source="vera", payload=payload, meta=meta),
    #         priority=priority,
    #     )

# --- Entry point ---
if __name__ == "__main__":
    import sys
    
    vera = Vera(enable_infrastructure=False)
    
    os.system("clear")
    vera.print_llm_models()
    vera.print_agents()
    
    if vera.enable_infrastructure:
        vera.logger.info("=== Infrastructure Stats ===")
        stats = vera.get_infrastructure_stats()
        for key, value in stats.items():
            vera.logger.info(f"  {key}: {value}")
        vera.logger.info("=" * 40)

    vera.logger.info("Vera ready! Enter your queries below.")
    vera.logger.info("Special commands: /stats, /infra, /provision, /cleanup, /clear, /agents, /exit")
    
    while True:
        try:
            user_query = input("\n\n🔵 Query: ")
        except (EOFError, KeyboardInterrupt):
            vera.logger.info("Shutting down...")
            break
        
        if user_query.lower() in ["exit", "quit", "/exit"]:
            vera.logger.info("Goodbye!")
            break
        
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
        
        vera.logger.debug(f"Processing: {user_query}")
        result = ""
        for chunk in vera.async_run(user_query):
            result += str(chunk)
        
        print()

        

# ジョセフ