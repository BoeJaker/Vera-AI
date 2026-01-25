#!/usr/bin/env python3
# Configuration/config_manager.py

"""
Vera Configuration Management System (Updated)
Now with enhanced logging configuration support.
"""

import os
import json
import yaml
import threading
import time
from typing import Any, Dict, Optional, Callable, List
from pathlib import Path
from dataclasses import dataclass, asdict, field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
from dataclasses import dataclass, asdict, field
from typing import List, Union
logger = logging.getLogger(__name__)

@dataclass
class AgentSystemConfig:
    """Agent configuration system settings"""
    enabled: bool = True
    auto_load: bool = True
    auto_build: bool = False
    
    agents_dir: str = "./Vera/Ollama/Agents/agents"
    templates_dir: str = "./Vera/Ollama/Agents/templates"
    build_dir: str = "./Vera/Ollama/build/agents"
    
    # Default agents for different tasks
    default_agents: Dict[str, str] = field(default_factory=lambda: {
        'triage': 'triage-agent',
        'tool_execution': 'tool-agent',
        'reasoning': 'reasoning-agent',
        'conversation': 'gemma2'
    })
    
    # Agent-specific config overrides
    agent_configs: Dict[str, Dict] = field(default_factory=dict)
    
    hot_reload: bool = True
    check_interval: int = 60
    validate_on_load: bool = True
    strict_validation: bool = False

@dataclass
class MemoryConfig:
    """Memory system configuration"""
    chroma_path: str = "./Memory/vera_agent_memory"
    chroma_dir: str = "./Memory/chroma_store"
    archive_path: str = "./Memory/archive/memory_archive.jsonl"
    
    # Neo4j settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "testpassword"
    
    # Vector store settings
    vector_search_k: int = 5
    plan_vector_search_k: int = 5
    
    # Memory management
    enable_memory_triage: bool = False
    auto_persist: bool = True
    persist_interval: int = 300  # seconds


@dataclass
class OrchestratorConfig:
    """Task orchestration configuration"""
    redis_url: str = "redis://localhost:6379"
    cpu_threshold: float = 75.0
    
    # Task type worker counts
    llm_workers: int = 3
    whisper_workers: int = 1
    tool_workers: int = 4
    ml_model_workers: int = 1
    background_workers: int = 2
    general_workers: int = 2
    
    # Timeouts
    triage_timeout: float = 10.0
    toolchain_timeout: float = 120.0
    llm_timeout: float = 60.0
    fast_llm_timeout: float = 30.0


@dataclass
class InfrastructureConfig:
    """Infrastructure orchestration configuration"""
    enable_infrastructure: bool = False
    enable_docker: bool = False
    enable_proxmox: bool = False
    auto_scale: bool = True
    max_resources: int = 10
    
    # Docker settings
    docker_url: str = "unix://var/run/docker.sock"
    docker_registry: Optional[str] = None
    
    # Proxmox settings
    proxmox_host: Optional[str] = None
    proxmox_user: Optional[str] = None
    proxmox_password: Optional[str] = None
    proxmox_verify_ssl: bool = False
    proxmox_node: str = "pve"
    
    # Resource cleanup
    idle_resource_cleanup_interval: int = 300  # seconds
    max_idle_time: int = 600  # seconds


@dataclass
class ProactiveFocusConfig:
    """Proactive focus manager configuration"""
    enabled: bool = True
    default_focus: Optional[str] = None
    iteration_interval: int = 600  # seconds
    auto_execute: bool = True
    max_iterations: Optional[int] = None


@dataclass
class PlaywrightConfig:
    """Playwright browser configuration"""
    enabled: bool = True
    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    timeout: int = 30000


@dataclass
class LoggingConfig:
    """Enhanced logging configuration"""
    # Global settings
    level: str = "INFO"  # TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
    file: Optional[str] = "./logs/vera.log"
    json_file: Optional[str] = "./logs/vera.jsonl"
    console: bool = True
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5
    
    # Component-specific levels
    component_levels: Dict[str, str] = field(default_factory=dict)
    
    # Display options
    enable_colors: bool = True
    enable_timestamps: bool = True
    enable_thread_info: bool = False
    enable_session_info: bool = True
    enable_model_info: bool = True
    show_milliseconds: bool = True
    
    # Formatting
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Legacy format field for compatibility
    timestamp_format: str = "%Y-%m-%d %H:%M:%S.%f"
    max_line_width: int = 100
    
    # Special output
    box_thoughts: bool = True
    box_responses: bool = False
    box_tools: bool = True
    
    # Verbose debugging
    show_raw_ollama_chunks: bool = False
    show_orchestrator_details: bool = True
    show_memory_operations: bool = False
    show_infrastructure_events: bool = True
    
    # Performance tracking
    enable_performance_tracking: bool = True
    track_llm_latency: bool = True
    track_tool_latency: bool = True
    
    # Stream handling
    stream_thoughts_inline: bool = True



@dataclass
class OllamaInstanceConfig:
    """Configuration for a single Ollama instance"""
    name: str
    api_url: str
    priority: int = 1
    max_concurrent: int = 2
    enabled: bool = True
    timeout: int = 2400
    
    @classmethod
    def from_dict(cls, data: dict) -> 'OllamaInstanceConfig':
        """Create from dictionary"""
        return cls(
            name=data.get('name', 'unknown'),
            api_url=data.get('api_url', 'http://localhost:11434'),
            priority=data.get('priority', 1),
            max_concurrent=data.get('max_concurrent', 2),
            enabled=data.get('enabled', True),
            timeout=data.get('timeout', 2400)
        )


@dataclass
class OllamaConfig:
    """Ollama API configuration with multi-instance support"""
    # Primary instance (backward compatible)
    api_url: str = "http://192.168.0.250:11435"
    timeout: int = 2400
    use_local_fallback: bool = False  # DISABLE local fallback
    connection_retry_attempts: int = 3
    connection_retry_delay: float = 1.0
    
    # Multi-instance configuration
    instances: List[OllamaInstanceConfig] = field(default_factory=list)
    
    # Load balancing settings (with defaults)
    load_balance_strategy: str = "least_loaded"
    enable_request_queue: bool = True
    max_queue_size: int = 100
    
    # Legacy fields for backward compatibility
    enable_thought_capture: bool = True
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.9
    num_predict: int = -1
    repeat_penalty: float = 1.1
    cache_model_metadata: bool = True
    metadata_cache_ttl: int = 3600
    
    def __post_init__(self):
        """Convert dict instances to OllamaInstanceConfig objects and set defaults"""
        if self.instances:
            converted_instances = []
            for instance in self.instances:
                if isinstance(instance, dict):
                    converted_instances.append(OllamaInstanceConfig.from_dict(instance))
                elif isinstance(instance, OllamaInstanceConfig):
                    converted_instances.append(instance)
                else:
                    raise TypeError(f"Invalid instance type: {type(instance)}")
            self.instances = converted_instances
        else:
            # Default instances if none provided
            self.instances = [
                OllamaInstanceConfig(
                    name="remote",
                    api_url="http://192.168.0.250:11435",
                    priority=2,
                    max_concurrent=2
                ),
                OllamaInstanceConfig(
                    name="local",
                    api_url="http://localhost:11434",
                    priority=1,
                    max_concurrent=2
                )
            ]


@dataclass
class ModelConfig:
    """Model selection configuration"""
    embedding_model: str = "mistral:7b"
    fast_llm: str = "gemma2"
    intermediate_llm: str = "gemma3:12b"
    deep_llm: str = "gpt-oss:20b"
    reasoning_llm: str = "gpt-oss:20b"
    tool_llm: str = "gemma2"
    
    # Temperature settings per model
    fast_temperature: float = 0.6
    intermediate_temperature: float = 0.4
    deep_temperature: float = 0.6
    reasoning_temperature: float = 0.7
    tool_temperature: float = 0.1
    
    # REMOVED: fast_top_k, fast_top_p, etc. - these should be set at runtime
    # If you need these, add them as separate fields:
    # fast_top_k: int = 40
    # fast_top_p: float = 0.9

@dataclass
class VeraConfig:
    """Main Vera configuration"""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    infrastructure: InfrastructureConfig = field(default_factory=InfrastructureConfig)
    proactive_focus: ProactiveFocusConfig = field(default_factory=ProactiveFocusConfig)
    playwright: PlaywrightConfig = field(default_factory=PlaywrightConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    agents: AgentSystemConfig = field(default_factory=AgentSystemConfig) 
    
    # General settings
    enable_hot_reload: bool = True
    config_file: str = "./Vera/Configuration/vera_config.yaml"


class ConfigFileHandler(FileSystemEventHandler):
    """Watch for config file changes"""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.last_modified = 0
        self.debounce_seconds = 1.0
    
    def on_modified(self, event):
        if event.src_path == str(self.config_manager.config_path.absolute()):
            current_time = time.time()
            if current_time - self.last_modified > self.debounce_seconds:
                self.last_modified = current_time
                logger.info(f"Config file modified: {event.src_path}")
                self.config_manager.reload_config()


class ConfigManager:
    """
    Configuration manager with hot-reloading support
    """
    
    def __init__(
        self, 
        config_file: str = "./Vera/Configuration/vera_config.yaml",
        auto_create: bool = True
    ):
        self.config_path = Path(config_file)
        self.config: VeraConfig = VeraConfig()
        self.callbacks: List[Callable[[VeraConfig, VeraConfig], None]] = []
        self.lock = threading.RLock()
        self.observer: Optional[Observer] = None
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or create config
        if self.config_path.exists():
            self.load_config()
        elif auto_create:
            self.save_config()
            logger.info(f"Created default config at {self.config_path}")
        
        # Start file watcher if hot-reload enabled
        if self.config.enable_hot_reload:
            self.start_file_watcher()
    
    def load_config(self) -> VeraConfig:
        """Load configuration from file"""
        with self.lock:
            try:
                with open(self.config_path, 'r') as f:
                    if self.config_path.suffix == '.json':
                        data = json.load(f)
                    elif self.config_path.suffix in ['.yaml', '.yml']:
                        data = yaml.safe_load(f)
                    else:
                        raise ValueError(f"Unsupported config format: {self.config_path.suffix}")
                
                # Apply environment variable overrides
                data = self._apply_env_overrides(data)
                
                self.config = self._dict_to_config(data)
                logger.info(f"Loaded config from {self.config_path}")
                return self.config
            
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                logger.info("Using default configuration")
                return self.config
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        with self.lock:
            try:
                data = self._config_to_dict(self.config)
                
                with open(self.config_path, 'w') as f:
                    if self.config_path.suffix == '.json':
                        json.dump(data, f, indent=2)
                    elif self.config_path.suffix in ['.yaml', '.yml']:
                        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                
                logger.info(f"Saved config to {self.config_path}")
                return True
            
            except Exception as e:
                logger.error(f"Failed to save config: {e}")
                return False
    
    def reload_config(self):
        """Reload configuration and notify callbacks"""
        with self.lock:
            old_config = self.config
            new_config = self.load_config()
            
            # Notify all registered callbacks
            for callback in self.callbacks:
                try:
                    callback(old_config, new_config)
                except Exception as e:
                    logger.error(f"Config callback error: {e}")
    
    def register_callback(self, callback: Callable[[VeraConfig, VeraConfig], None]):
        """Register a callback for config changes"""
        with self.lock:
            self.callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[VeraConfig, VeraConfig], None]):
        """Unregister a config change callback"""
        with self.lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)
    
    def start_file_watcher(self):
        """Start watching config file for changes"""
        if self.observer is not None:
            return
        
        try:
            event_handler = ConfigFileHandler(self)
            self.observer = Observer()
            self.observer.schedule(
                event_handler, 
                str(self.config_path.parent), 
                recursive=False
            )
            self.observer.start()
            logger.info(f"Started config file watcher for {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
    
    def stop_file_watcher(self):
        """Stop watching config file"""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Stopped config file watcher")
    
    def _apply_env_overrides(self, data: Dict) -> Dict:
        """Apply environment variable overrides to config"""
        env_mappings = {
            'VERA_OLLAMA_API_URL': ('ollama', 'api_url'),
            'VERA_NEO4J_URI': ('memory', 'neo4j_uri'),
            'VERA_NEO4J_USER': ('memory', 'neo4j_user'),
            'VERA_NEO4J_PASSWORD': ('memory', 'neo4j_password'),
            'VERA_REDIS_URL': ('orchestrator', 'redis_url'),
            'VERA_PROXMOX_HOST': ('infrastructure', 'proxmox_host'),
            'VERA_PROXMOX_USER': ('infrastructure', 'proxmox_user'),
            'VERA_PROXMOX_PASSWORD': ('infrastructure', 'proxmox_password'),
            'VERA_LOG_LEVEL': ('logging', 'level'),
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if section not in data:
                    data[section] = {}
                data[section][key] = value
                logger.debug(f"Applied env override: {env_var} -> {section}.{key}")
        
        return data
            
    def _dict_to_config(self, data: Dict) -> VeraConfig:
        """Convert dictionary to VeraConfig object"""
        
        # Handle Ollama config specially
        ollama_data = data.get('ollama', {})
        
        # Convert instances list if present
        if 'instances' in ollama_data:
            instances_data = ollama_data.pop('instances')
            ollama_config = OllamaConfig(**ollama_data)
            
            # Manually set instances (will trigger __post_init__)
            ollama_config.instances = [
                OllamaInstanceConfig.from_dict(inst) if isinstance(inst, dict) else inst
                for inst in instances_data
            ]
        else:
            ollama_config = OllamaConfig(**ollama_data)
        
        config_dict = {
            'ollama': ollama_config,
            'models': ModelConfig(**data.get('models', {})),
            'memory': MemoryConfig(**data.get('memory', {})),
            'orchestrator': OrchestratorConfig(**data.get('orchestrator', {})),
            'infrastructure': InfrastructureConfig(**data.get('infrastructure', {})),
            'proactive_focus': ProactiveFocusConfig(**data.get('proactive_focus', {})),
            'playwright': PlaywrightConfig(**data.get('playwright', {})),
            'logging': LoggingConfig(**data.get('logging', {})),
            'agents': AgentSystemConfig(**data.get('agents', {})),
            'enable_hot_reload': data.get('enable_hot_reload', True),
            'config_file': data.get('config_file', str(self.config_path)),
        }
        return VeraConfig(**config_dict)

    def _config_to_dict(self, config: VeraConfig) -> Dict:
        """Convert VeraConfig object to dictionary"""
        
        ollama_dict = asdict(config.ollama)
        
        # Convert instances to dicts properly
        if 'instances' in ollama_dict:
            ollama_dict['instances'] = [
                asdict(inst) if not isinstance(inst, dict) else inst
                for inst in ollama_dict['instances']
            ]
        
        return {
            'ollama': ollama_dict,
            'models': asdict(config.models),
            'memory': asdict(config.memory),
            'orchestrator': asdict(config.orchestrator),
            'infrastructure': asdict(config.infrastructure),
            'proactive_focus': asdict(config.proactive_focus),
            'playwright': asdict(config.playwright),
            'logging': asdict(config.logging),
            'agents': asdict(config.agents),
            'enable_hot_reload': config.enable_hot_reload,
            'config_file': config.config_file,
        }
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value"""
        with self.lock:
            section_obj = getattr(self.config, section, None)
            if section_obj is None:
                return default
            
            if key is None:
                return section_obj
            
            return getattr(section_obj, key, default)
    
    def set(self, section: str, key: str, value: Any, persist: bool = True):
        """Set configuration value"""
        with self.lock:
            section_obj = getattr(self.config, section, None)
            if section_obj is None:
                raise ValueError(f"Invalid config section: {section}")
            
            setattr(section_obj, key, value)
            
            if persist:
                self.save_config()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_file_watcher()


# Utility functions for config validation
def validate_config(config: VeraConfig) -> List[str]:
    """Validate configuration and return list of issues"""
    issues = []
    
    # Validate URLs
    if not config.ollama.api_url.startswith(('http://', 'https://')):
        issues.append("ollama.api_url must start with http:// or https://")
    
    # Validate timeouts
    if config.ollama.timeout < 10:
        issues.append("ollama.timeout should be at least 10 seconds")
    
    # Validate worker counts
    if config.orchestrator.llm_workers < 1:
        issues.append("orchestrator.llm_workers must be at least 1")
    
    # Validate infrastructure settings
    if config.infrastructure.enable_infrastructure:
        if not config.infrastructure.enable_docker and not config.infrastructure.enable_proxmox:
            issues.append("infrastructure enabled but no providers (docker/proxmox) enabled")
    
    if config.infrastructure.enable_proxmox:
        if not config.infrastructure.proxmox_host:
            issues.append("proxmox enabled but proxmox_host not set")
    
    # Validate paths
    memory_paths = [
        config.memory.chroma_path,
        config.memory.chroma_dir,
    ]
    for path in memory_paths:
        if not path:
            issues.append(f"Memory path cannot be empty: {path}")
    
    # Validate logging level
    valid_levels = ['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL', 'SILENT']
    if config.logging.level not in valid_levels:
        issues.append(f"logging.level must be one of {valid_levels}")
    
    return issues


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create config manager
    config_manager = ConfigManager("./Vera/Configuration/vera_config.yaml")
    
    # Validate configuration
    issues = validate_config(config_manager.config)
    if issues:
        print("\n[Configuration Issues]")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n[Configuration Valid]")
    
    # Register a callback for config changes
    def on_config_change(old_config: VeraConfig, new_config: VeraConfig):
        print("\n[Config Changed]")
        print(f"Ollama API URL: {old_config.ollama.api_url} -> {new_config.ollama.api_url}")
        print(f"Fast LLM: {old_config.models.fast_llm} -> {new_config.models.fast_llm}")
        print(f"Log Level: {old_config.logging.level} -> {new_config.logging.level}")
        
        # Re-validate
        issues = validate_config(new_config)
        if issues:
            print("[Validation Issues After Reload]")
            for issue in issues:
                print(f"  - {issue}")
    
    config_manager.register_callback(on_config_change)
    
    # Access configuration
    print("\n[Current Configuration]")
    print(f"Ollama API: {config_manager.config.ollama.api_url}")
    print(f"Fast LLM: {config_manager.config.models.fast_llm}")
    print(f"Memory Path: {config_manager.config.memory.chroma_path}")
    print(f"Infrastructure Enabled: {config_manager.config.infrastructure.enable_infrastructure}")
    print(f"Log Level: {config_manager.config.logging.level}")
    print(f"Show Raw Chunks: {config_manager.config.logging.show_raw_ollama_chunks}")
    
    # Modify and save
    print("\n[Modifying Configuration]")
    config_manager.set('models', 'fast_llm', 'llama3:8b')
    config_manager.set('logging', 'level', 'DEBUG')
    
    # Access via get method
    fast_llm = config_manager.get('models', 'fast_llm')
    log_level = config_manager.get('logging', 'level')
    print(f"Updated Fast LLM: {fast_llm}")
    print(f"Updated Log Level: {log_level}")
    
    print("\nConfig system ready. Modify vera_config.yaml to test hot-reload.")
    print("Press Ctrl+C to exit...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")