#!/usr/bin/env python3
# Vera/Agents/integration.py

"""
Vera Agent System Integration
Binds agent configuration system to Vera's runtime environment.
"""

import os
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

try:
    from Vera.Ollama.Agents.agent_manager import AgentManager, AgentConfig
    from Vera.Configuration.config_manager import ConfigManager, VeraConfig
    from Vera.Logging.logging import get_logger, LogContext, LogLevel
except ImportError:
    from agent_manager import AgentManager, AgentConfig
    from Configuration.config_manager import ConfigManager, VeraConfig
    try:
        from Logging.logging import get_logger, LogContext, LogLevel
    except ImportError:
        # Fallback to basic logging
        import logging
        get_logger = lambda name, config: logging.getLogger(name)
        LogContext = None
        LogLevel = None


class VeraAgentIntegration:
    """
    Integration layer between Vera and Agent Configuration System
    """
    
    def __init__(
        self,
        vera_instance,
        config_manager: ConfigManager,
        logger=None
    ):
        """
        Initialize agent integration
        
        Args:
            vera_instance: Vera instance
            config_manager: ConfigManager instance
            logger: VeraLogger instance
        """
        self.vera = vera_instance
        self.config_manager = config_manager
        self.config = config_manager.config.agents
        self.logger = logger or get_logger("agent_integration", None)
        
        # Get directories from config with robust path resolution
        self.agents_dir = self._resolve_path(self.config.agents_dir)
        self.templates_dir = self._resolve_path(self.config.templates_dir)
        self.build_dir = self._resolve_path(self.config.build_dir)
        
        # Create agent manager
        self.agent_manager = AgentManager(
            agents_dir=str(self.agents_dir),
            templates_dir=str(self.templates_dir),
            build_dir=str(self.build_dir),
            logger=self.logger
        )
        
        # Loaded agents
        self.loaded_agents: Dict[str, AgentConfig] = {}
        
        # Auto-load agents if configured
        if self.config.auto_load:
            self._auto_load_agents()
    
    def _resolve_path(self, path_str: str) -> Path:
        """
        Resolve a path robustly, working from any execution location.
        
        Strategy:
        1. If path is absolute, use it directly
        2. If path is relative, try multiple base directories:
           - Current working directory
           - Script's directory
           - Project root (found by looking for markers)
           - Environment variable VERA_ROOT
        
        Args:
            path_str: Path string from config
        
        Returns:
            Resolved absolute Path object
        """
        path = Path(path_str)
        
        # If already absolute, return it
        if path.is_absolute():
            if hasattr(self.logger, 'debug'):
                self.logger.debug(f"Using absolute path: {path}")
            return path
        
        # List of base directories to try (in order of priority)
        base_candidates = []
        
        # 1. Environment variable VERA_ROOT
        vera_root = os.environ.get('VERA_ROOT')
        if vera_root:
            base_candidates.append(Path(vera_root))
        
        # 2. Current working directory
        base_candidates.append(Path.cwd())
        
        # 3. Script's directory (this file's location)
        script_dir = Path(__file__).resolve().parent
        base_candidates.append(script_dir)
        
        # 4. Project root (look for marker files/directories)
        project_root = self._find_project_root()
        if project_root:
            base_candidates.append(project_root)
        
        # 5. Parent directories of script (walk up looking for Vera/)
        current = script_dir
        for _ in range(5):  # Don't go more than 5 levels up
            if (current / "Vera").exists():
                base_candidates.append(current)
            current = current.parent
            if current == current.parent:  # Reached filesystem root
                break
        
        # Try each base directory
        for base_dir in base_candidates:
            candidate_path = (base_dir / path).resolve()
            
            # For directories, check if they exist
            # For files, check if parent exists (we might create the file later)
            if candidate_path.exists():
                if hasattr(self.logger, 'debug'):
                    self.logger.debug(f"Resolved path '{path_str}' -> {candidate_path}")
                return candidate_path
            elif candidate_path.parent.exists():
                # Parent exists, so we can potentially create this path
                if hasattr(self.logger, 'debug'):
                    self.logger.debug(f"Resolved path '{path_str}' -> {candidate_path} (parent exists)")
                return candidate_path
        
        # If nothing worked, create from first candidate (typically CWD or VERA_ROOT)
        fallback_path = (base_candidates[0] / path).resolve()
        
        if hasattr(self.logger, 'warning'):
            self.logger.warning(
                f"Could not find existing path for '{path_str}', "
                f"using fallback: {fallback_path}"
            )
        
        # Create the directory if it doesn't exist
        try:
            fallback_path.mkdir(parents=True, exist_ok=True)
            if hasattr(self.logger, 'info'):
                self.logger.info(f"Created directory: {fallback_path}")
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to create directory {fallback_path}: {e}")
        
        return fallback_path
    
    def _find_project_root(self) -> Optional[Path]:
        """
        Find the project root by looking for marker files/directories.
        
        Looks for:
        - .git directory
        - vera_config.yaml
        - Vera directory
        
        Returns:
            Project root Path or None
        """
        markers = ['.git', 'vera_config.yaml', 'Configuration', 'Vera']
        
        # Start from script directory
        current = Path(__file__).resolve().parent
        
        # Walk up directory tree
        for _ in range(10):  # Don't search more than 10 levels up
            for marker in markers:
                if (current / marker).exists():
                    return current
            
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent
        
        return None
    
    def _auto_load_agents(self):
        """Auto-load all agent configurations"""
        if hasattr(self.logger, 'info'):
            self.logger.info("Auto-loading agent configurations...")
        
        try:
            # Ensure agents directory exists
            if not self.agents_dir.exists():
                if hasattr(self.logger, 'warning'):
                    self.logger.warning(f"Agents directory does not exist: {self.agents_dir}")
                    self.logger.warning("Creating agents directory...")
                self.agents_dir.mkdir(parents=True, exist_ok=True)
                return
            
            # Discover agents
            agent_dirs = [d for d in self.agents_dir.iterdir() 
                         if d.is_dir() and not d.name.startswith('.')]
            
            if hasattr(self.logger, 'debug'):
                self.logger.debug(f"Found {len(agent_dirs)} agent directories in {self.agents_dir}")
            
            # Load each agent
            for agent_dir in sorted(agent_dirs):
                agent_name = agent_dir.name
                
                try:
                    # Load config
                    config = self.agent_manager.load_agent_config(agent_name)
                    
                    # Validate if configured
                    if self.config.validate_on_load:
                        issues = self.agent_manager.validate_agent_config(agent_name)
                        if issues:
                            if self.config.strict_validation:
                                if hasattr(self.logger, 'error'):
                                    self.logger.error(
                                        f"Agent validation failed: {agent_name}",
                                        context=LogContext(agent=agent_name) if LogContext else None
                                    )
                                    for issue in issues:
                                        self.logger.error(f"  • {issue}")
                                continue
                            else:
                                if hasattr(self.logger, 'warning'):
                                    self.logger.warning(f"Agent validation issues: {agent_name}")
                                    for issue in issues:
                                        self.logger.warning(f"  • {issue}")
                    
                    # Apply config overrides
                    if agent_name in self.config.agent_configs:
                        overrides = self.config.agent_configs[agent_name]
                        config = self._apply_overrides(config, overrides)
                    
                    # Store loaded agent
                    self.loaded_agents[agent_name] = config
                    
                    if hasattr(self.logger, 'debug'):
                        self.logger.debug(f"Loaded agent: {agent_name}")
                
                except Exception as e:
                    if hasattr(self.logger, 'error'):
                        self.logger.error(
                            f"Failed to load agent {agent_name}: {e}",
                            exc_info=True
                        )
            
            if hasattr(self.logger, 'success'):
                self.logger.success(f"Loaded {len(self.loaded_agents)} agent configurations")
            
            # Auto-build if configured
            if self.config.auto_build and self.loaded_agents:
                self._auto_build_agents()
        
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Auto-load failed: {e}", exc_info=True)
    
    def _auto_build_agents(self):
        """Auto-build Ollama models for loaded agents"""
        if hasattr(self.logger, 'info'):
            self.logger.info("Auto-building agent Ollama models...")
        
        built_count = 0
        for agent_name in self.loaded_agents:
            try:
                config = self.loaded_agents[agent_name]
                
                # Render system prompt
                system_prompt = self.agent_manager.render_system_prompt(agent_name, config)
                
                # Build modelfile
                modelfile_path = self.agent_manager.build_modelfile(
                    agent_name, 
                    config, 
                    system_prompt
                )
                
                # Create Ollama model
                success = self.agent_manager.create_ollama_model(agent_name, modelfile_path)
                if success:
                    built_count += 1
            
            except Exception as e:
                if hasattr(self.logger, 'warning'):
                    self.logger.warning(f"Failed to build agent {agent_name}: {e}")
        
        if hasattr(self.logger, 'success'):
            self.logger.success(f"Built {built_count}/{len(self.loaded_agents)} agent models")
    
    def _apply_overrides(self, config: AgentConfig, overrides: Dict[str, Any]) -> AgentConfig:
        """Apply config overrides to agent config"""
        for key, value in overrides.items():
            if key == 'memory' and isinstance(value, dict):
                # Apply memory config overrides
                for mem_key, mem_value in value.items():
                    if hasattr(config.memory, mem_key):
                        setattr(config.memory, mem_key, mem_value)
            
            elif key == 'parameters' and isinstance(value, dict):
                # Apply parameter overrides
                for param_key, param_value in value.items():
                    if hasattr(config.parameters, param_key):
                        setattr(config.parameters, param_key, param_value)
            
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """
        Get agent configuration
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            AgentConfig or None
        """
        return self.loaded_agents.get(agent_name)
    
    def create_llm_with_agent_config(self, agent_name: str, ollama_manager):
        """
        Create LLM instance using agent configuration
        
        Args:
            agent_name: Name of the agent
            ollama_manager: OllamaConnectionManager instance
        
        Returns:
            Configured LLM instance
        """
        config = self.get_agent_config(agent_name)
        
        if not config:
            # Try to load if not already loaded
            try:
                config = self.agent_manager.load_agent_config(agent_name)
                self.loaded_agents[agent_name] = config
            except Exception as e:
                if hasattr(self.logger, 'error'):
                    self.logger.error(f"Agent not found: {agent_name}")
                raise ValueError(f"Agent not found: {agent_name}")
        
        # Create LLM with agent's parameters
        llm = ollama_manager.create_llm(
            model=agent_name,  # Use agent name as model name
            temperature=config.parameters.temperature,
            top_k=config.parameters.top_k,
            top_p=config.parameters.top_p,
            num_predict=config.parameters.num_predict,
        )
        
        if hasattr(self.logger, 'debug'):
            context = LogContext(
                agent=agent_name,
                model=agent_name,
                extra={
                    'temperature': config.parameters.temperature,
                    'context_length': config.num_ctx
                }
            ) if LogContext else None
            
            self.logger.debug(
                f"Created LLM with agent config: {agent_name}",
                context=context
            )
        
        return llm
    
    def get_agent_memory_config(self, agent_name: str) -> Dict[str, Any]:
        """
        Get memory configuration for agent
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            Memory configuration dictionary
        """
        config = self.get_agent_config(agent_name)
        
        if not config:
            # Return default memory config
            return {
                'use_vector': True,
                'use_neo4j': True,
                'vector_top_k': 8,
                'neo4j_limit': 16,
                'enable_triage': False
            }
        
        return {
            'use_vector': config.memory.use_vector,
            'use_neo4j': config.memory.use_neo4j,
            'vector_top_k': config.memory.vector_top_k,
            'neo4j_limit': config.memory.neo4j_limit,
            'enable_triage': config.memory.enable_triage
        }
    
    def reload_agent(self, agent_name: str, rebuild_model: bool = True) -> Optional[AgentConfig]:
        """
        Reload agent configuration (hot reload)
        
        Args:
            agent_name: Name of the agent
            rebuild_model: Whether to rebuild Ollama model
        
        Returns:
            Reloaded AgentConfig or None
        """
        if hasattr(self.logger, 'info'):
            context = LogContext(agent=agent_name) if LogContext else None
            self.logger.info(f"Reloading agent: {agent_name}", context=context)
        
        try:
            # Load fresh config
            config = self.agent_manager.load_agent_config(agent_name)
            
            # Apply overrides
            if agent_name in self.config.agent_configs:
                overrides = self.config.agent_configs[agent_name]
                config = self._apply_overrides(config, overrides)
            
            # Rebuild model if requested
            if rebuild_model:
                system_prompt = self.agent_manager.render_system_prompt(agent_name, config)
                modelfile_path = self.agent_manager.build_modelfile(agent_name, config, system_prompt)
                self.agent_manager.create_ollama_model(agent_name, modelfile_path)
            
            # Update loaded agents
            self.loaded_agents[agent_name] = config
            
            if hasattr(self.logger, 'success'):
                self.logger.success(f"Agent reloaded: {agent_name}")
            
            return config
        
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to reload agent {agent_name}: {e}", exc_info=True)
            return None
    
    def list_loaded_agents(self) -> List[Dict[str, str]]:
        """
        List all loaded agents
        
        Returns:
            List of agent info dictionaries
        """
        agents = []
        for name, config in self.loaded_agents.items():
            agents.append({
                'name': name,
                'description': config.description,
                'base_model': config.base_model,
                'temperature': config.parameters.temperature,
                'context_length': config.num_ctx
            })
        return sorted(agents, key=lambda x: x['name'])
    
    def get_agent_for_model(self, model_name: str) -> Optional[str]:
        """
        Get agent name for a given model name
        
        Args:
            model_name: Model name
        
        Returns:
            Agent name or None
        """
        for agent_name, config in self.loaded_agents.items():
            if config.base_model == model_name or agent_name == model_name:
                return agent_name
        return None
    
    def discover_agents(self) -> List[str]:
        """
        Discover all agent directories
        
        Returns:
            List of agent directory names
        """
        if not self.agents_dir.exists():
            return []
        
        return [d.name for d in self.agents_dir.iterdir() 
                if d.is_dir() and not d.name.startswith('.')]
    
    def load_agent(self, agent_name: str, build_model: bool = False) -> Optional[AgentConfig]:
        """
        Load a specific agent
        
        Args:
            agent_name: Name of the agent
            build_model: Whether to build Ollama model
        
        Returns:
            AgentConfig or None
        """
        try:
            # Load config
            config = self.agent_manager.load_agent_config(agent_name)
            
            # Apply overrides
            if agent_name in self.config.agent_configs:
                overrides = self.config.agent_configs[agent_name]
                config = self._apply_overrides(config, overrides)
            
            # Build model if requested
            if build_model:
                system_prompt = self.agent_manager.render_system_prompt(agent_name, config)
                modelfile_path = self.agent_manager.build_modelfile(agent_name, config, system_prompt)
                self.agent_manager.create_ollama_model(agent_name, modelfile_path)
            
            # Store
            self.loaded_agents[agent_name] = config
            
            if hasattr(self.logger, 'success'):
                self.logger.success(f"Loaded agent: {agent_name}")
            
            return config
        
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to load agent {agent_name}: {e}", exc_info=True)
            return None
    
    def build_agent(self, agent_name: str) -> bool:
        """
        Build Ollama model for agent
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            True if successful
        """
        config = self.get_agent_config(agent_name)
        if not config:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Agent not loaded: {agent_name}")
            return False
        
        try:
            system_prompt = self.agent_manager.render_system_prompt(agent_name, config)
            modelfile_path = self.agent_manager.build_modelfile(agent_name, config, system_prompt)
            return self.agent_manager.create_ollama_model(agent_name, modelfile_path)
        
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to build agent {agent_name}: {e}", exc_info=True)
            return False
    
    def validate_agent(self, agent_name: str) -> List[str]:
        """
        Validate agent configuration
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            List of validation issues
        """
        return self.agent_manager.validate_agent_config(agent_name)


def integrate_agent_system(vera_instance, config_manager: ConfigManager, logger=None) -> VeraAgentIntegration:
    """
    Helper function to integrate agent system with Vera
    
    Args:
        vera_instance: Vera instance
        config_manager: ConfigManager instance
        logger: VeraLogger instance
    
    Returns:
        VeraAgentIntegration instance
    """
    return VeraAgentIntegration(vera_instance, config_manager, logger)


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vera Agent Integration CLI")
    parser.add_argument(
        'command',
        choices=['list', 'load', 'build', 'validate', 'reload', 'discover'],
        help='Command to execute'
    )
    parser.add_argument('--agent', help='Agent name')
    parser.add_argument('--all', action='store_true', help='Apply to all agents')
    parser.add_argument('--config', default='Configuration/vera_config.yaml', help='Config file')
    
    args = parser.parse_args()
    
    # Setup logging
    try:
        from Vera.Logging.logging import get_logger, LoggingConfig, LogLevel
        log_config = LoggingConfig(global_level=LogLevel.INFO)
        logger = get_logger("agent_integration", log_config)
    except ImportError:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("agent_integration")
    
    # Load config
    config_manager = ConfigManager(args.config)
    
    # Create integration (without Vera instance for CLI)
    class DummyVera:
        pass
    
    integration = VeraAgentIntegration(DummyVera(), config_manager, logger)
    
    # Execute command
    if args.command == 'list':
        agents = integration.list_loaded_agents()
        if agents:
            logger.info("Loaded agents:")
            for agent in agents:
                logger.info(
                    f"  • {agent['name']}: {agent['description']} "
                    f"(base: {agent['base_model']}, temp: {agent['temperature']}, "
                    f"ctx: {agent['context_length']})"
                )
        else:
            logger.info("No agents loaded")
    
    elif args.command == 'discover':
        agents = integration.discover_agents()
        logger.info(f"Found {len(agents)} agent directories:")
        for agent in agents:
            logger.info(f"  • {agent}")
    
    elif args.command == 'load':
        if args.all:
            integration._auto_load_agents()
        elif args.agent:
            config = integration.load_agent(args.agent, build_model=False)
            if config:
                logger.info(f"✓ Loaded agent: {args.agent}")
            else:
                logger.error(f"✗ Failed to load agent: {args.agent}")
                sys.exit(1)
        else:
            logger.error("--agent or --all required")
            sys.exit(1)
    
    elif args.command == 'build':
        if args.all:
            for agent_name in integration.loaded_agents:
                integration.build_agent(agent_name)
        elif args.agent:
            # Load if not loaded
            if args.agent not in integration.loaded_agents:
                integration.load_agent(args.agent, build_model=False)
            
            success = integration.build_agent(args.agent)
            if success:
                logger.info(f"✓ Built agent: {args.agent}")
            else:
                logger.error(f"✗ Failed to build agent: {args.agent}")
                sys.exit(1)
        else:
            logger.error("--agent or --all required")
            sys.exit(1)
    
    elif args.command == 'validate':
        if args.all:
            all_valid = True
            for agent_name in integration.discover_agents():
                issues = integration.validate_agent(agent_name)
                if issues:
                    logger.warning(f"Validation issues for {agent_name}:")
                    for issue in issues:
                        logger.warning(f"  • {issue}")
                    all_valid = False
                else:
                    logger.info(f"✓ {agent_name}: valid")
            
            if not all_valid:
                sys.exit(1)
        
        elif args.agent:
            issues = integration.validate_agent(args.agent)
            if issues:
                logger.warning(f"Validation issues for {args.agent}:")
                for issue in issues:
                    logger.warning(f"  • {issue}")
                sys.exit(1)
            else:
                logger.info(f"✓ Agent config valid: {args.agent}")
        else:
            logger.error("--agent or --all required")
            sys.exit(1)
    
    elif args.command == 'reload':
        if args.agent:
            config = integration.reload_agent(args.agent, rebuild_model=True)
            if config:
                logger.info(f"✓ Reloaded agent: {args.agent}")
            else:
                logger.error(f"✗ Failed to reload agent: {args.agent}")
                sys.exit(1)
        else:
            logger.error("--agent required for reload")
            sys.exit(1)