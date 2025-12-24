#!/usr/bin/env python3
# Vera/Agents/agent_manager.py

"""
Vera Agent Configuration System
Manages agent definitions, templates, and dynamic loading.
"""

import os
import yaml
import json
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import logging

try:
    from Vera.Logging.logging import LogContext
except ImportError:
    LogContext = None


@dataclass
class AgentMemoryConfig:
    """Memory configuration for an agent"""
    use_vector: bool = True
    use_neo4j: bool = True
    vector_top_k: int = 8
    neo4j_limit: int = 16
    enable_triage: bool = False


@dataclass
class AgentParameters:
    """Inference parameters for an agent"""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.05
    num_predict: int = -1
    stop_sequences: List[str] = field(default_factory=list)


@dataclass
class SystemPromptConfig:
    """System prompt template configuration"""
    template: str = "prompt_template.j2"
    variables: Dict[str, Any] = field(default_factory=dict)
    includes: List[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Complete agent configuration"""
    name: str
    description: str = ""
    
    # Model settings
    base_model: str = "gemma2"
    quantization: Optional[str] = None
    num_ctx: int = 4096
    gpu_layers: int = 99
    
    # Inference parameters
    parameters: AgentParameters = field(default_factory=AgentParameters)
    
    # Memory settings
    memory: AgentMemoryConfig = field(default_factory=AgentMemoryConfig)
    
    # System prompt
    system_prompt: SystemPromptConfig = field(default_factory=SystemPromptConfig)
    
    # File includes
    includes: List[str] = field(default_factory=list)
    
    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    
    # Metadata
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        """Create from dictionary"""
        # Handle nested dataclasses
        if 'parameters' in data and isinstance(data['parameters'], dict):
            data['parameters'] = AgentParameters(**data['parameters'])
        
        if 'memory' in data and isinstance(data['memory'], dict):
            data['memory'] = AgentMemoryConfig(**data['memory'])
        
        if 'system_prompt' in data and isinstance(data['system_prompt'], dict):
            data['system_prompt'] = SystemPromptConfig(**data['system_prompt'])
        
        return cls(**data)


class AgentManager:
    """
    Manages agent configurations, templates, and Ollama model building
    """
    
    def __init__(
        self, 
        agents_dir: str = "./Vera/Agents/agents",
        templates_dir: str = "./Vera/Agents/templates",
        build_dir: str = "./Vera/Agents/build",
        logger=None
    ):
        """
        Initialize agent manager
        
        Args:
            agents_dir: Directory containing agent definitions
            templates_dir: Directory containing shared templates
            build_dir: Directory for built Modelfiles
            logger: VeraLogger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.agents_dir = Path(agents_dir)
        self.logger.info(f"{self.agents_dir} agent manager initialized")
        self.templates_dir = Path(templates_dir)
        self.logger.info(f"{self.templates_dir} templates directory set")
        self.build_dir = Path(build_dir)
        self.logger.info(f"{self.build_dir} build directory set")
        
        
        # Create directories if needed
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader([
                str(self.agents_dir),
                str(self.templates_dir),
                "."  # Allow absolute paths
            ]),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Current agent path for includes
        self.current_agent_path: Optional[Path] = None
        
        # Register custom Jinja2 functions
        self.jinja_env.globals['include_file'] = self._include_file
        self.jinja_env.globals['load_json'] = self._load_json
        self.jinja_env.globals['load_yaml'] = self._load_yaml
        
        # Loaded agents
        self.agents: Dict[str, AgentConfig] = {}
        
        if hasattr(self.logger, 'info'):
            self.logger.info(f"AgentManager initialized: {len(list(self.agents_dir.iterdir()))} agent directories found")
    
    def _include_file(self, path: str) -> str:
        """Jinja2 helper: Include file content"""
        if self.current_agent_path:
            full_path = self.current_agent_path / path
        else:
            full_path = Path(path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if hasattr(self.logger, 'trace'):
                self.logger.trace(f"Included file: {full_path} ({len(content)} bytes)")
            
            return content
        except FileNotFoundError:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Include file not found: {full_path}")
            return f"[File not found: {path}]"
    
    def _load_json(self, path: str) -> Any:
        """Jinja2 helper: Load JSON file"""
        if self.current_agent_path:
            full_path = self.current_agent_path / path
        else:
            full_path = Path(path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to load JSON {full_path}: {e}")
            return {}
    
    def _load_yaml(self, path: str) -> Any:
        """Jinja2 helper: Load YAML file"""
        if self.current_agent_path:
            full_path = self.current_agent_path / path
        else:
            full_path = Path(path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to load YAML {full_path}: {e}")
            return {}
    
    def load_agent_config(self, agent_name: str) -> AgentConfig:
        """
        Load agent configuration from YAML
        
        Args:
            agent_name: Name of the agent directory
        
        Returns:
            AgentConfig object
        """
        config_path = self.agents_dir / agent_name / "agent.yaml"
        
        if not config_path.exists():
            config_path = self.agents_dir / agent_name / "agent.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Agent config not found: {config_path}")
        
        if hasattr(self.logger, 'debug'):
            self.logger.debug(f"Loading agent config: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        config = AgentConfig.from_dict(data)
        
        if hasattr(self.logger, 'success'):
            self.logger.success(f"Loaded agent config: {config.name}")
        
        return config
    
    def render_system_prompt(self, agent_name: str, config: AgentConfig) -> str:
        """
        Render system prompt using Jinja2 template
        
        Args:
            agent_name: Name of the agent
            config: AgentConfig object
        
        Returns:
            Rendered system prompt
        """
        # Set current agent path for includes
        self.current_agent_path = self.agents_dir / agent_name
        
        if hasattr(self.logger, 'debug'):
            self.logger.debug(f"Rendering system prompt for {agent_name}")
        
        try:
            # Try to load template
            template_path = f"{agent_name}/{config.system_prompt.template}"
            
            try:
                template = self.jinja_env.get_template(template_path)
            except TemplateNotFound:
                # Try without agent name prefix
                template = self.jinja_env.get_template(config.system_prompt.template)
            
            # Render with variables
            rendered = template.render(**config.system_prompt.variables)
            
            # Check size
            size_kb = len(rendered) / 1024
            if size_kb > 512:
                if hasattr(self.logger, 'warning'):
                    self.logger.warning(
                        f"Large system prompt for {agent_name}: {size_kb:.1f}KB "
                        f"(ensure num_ctx={config.num_ctx} is sufficient)"
                    )
            
            if hasattr(self.logger, 'debug'):
                self.logger.debug(f"Rendered system prompt: {len(rendered)} chars, {size_kb:.1f}KB")
            
            return rendered
            
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to render system prompt for {agent_name}: {e}", exc_info=True)
            raise
        finally:
            self.current_agent_path = None
    
    def build_modelfile(self, agent_name: str, config: AgentConfig, system_prompt: str) -> Path:
        """
        Build Ollama Modelfile from agent config
        
        Args:
            agent_name: Name of the agent
            config: AgentConfig object
            system_prompt: Rendered system prompt
        
        Returns:
            Path to generated Modelfile
        """
        if hasattr(self.logger, 'debug'):
            self.logger.debug(f"Building Modelfile for {agent_name}")
        
        # Build Modelfile content
        lines = []
        lines.append(f"# Modelfile for {agent_name}")
        lines.append(f"# Generated by Vera Agent Manager")
        lines.append(f"# Base: {config.base_model}")
        lines.append("")
        
        # FROM directive
        lines.append(f"FROM {config.base_model}")
        lines.append("")
        
        # PARAMETER directives
        lines.append("# Parameters")
        lines.append(f"PARAMETER temperature {config.parameters.temperature}")
        lines.append(f"PARAMETER top_p {config.parameters.top_p}")
        lines.append(f"PARAMETER top_k {config.parameters.top_k}")
        lines.append(f"PARAMETER repeat_penalty {config.parameters.repeat_penalty}")
        lines.append(f"PARAMETER num_ctx {config.num_ctx}")
        
        if config.parameters.num_predict != -1:
            lines.append(f"PARAMETER num_predict {config.parameters.num_predict}")
        
        for stop in config.parameters.stop_sequences:
            lines.append(f"PARAMETER stop {stop}")
        
        lines.append("")
        
        # SYSTEM directive
        lines.append("# System Prompt")
        lines.append(f"SYSTEM \"\"\"{system_prompt}\"\"\"")
        lines.append("")
        
        # Write Modelfile
        modelfile_path = self.build_dir / f"{agent_name}.Modelfile"
        with open(modelfile_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        if hasattr(self.logger, 'success'):
            self.logger.success(f"Built Modelfile: {modelfile_path}")
        
        return modelfile_path
    
    def create_ollama_model(self, agent_name: str, modelfile_path: Path) -> bool:
        """
        Create Ollama model from Modelfile
        
        Args:
            agent_name: Name for the Ollama model
            modelfile_path: Path to Modelfile
        
        Returns:
            True if successful
        """
        if hasattr(self.logger, 'info'):
            context = LogContext(agent=agent_name) if LogContext else None
            self.logger.info(f"Creating Ollama model: {agent_name}", context=context)
        
        try:
            result = subprocess.run(
                ["ollama", "create", agent_name, "-f", str(modelfile_path)],
                capture_output=True,
                text=True,
                check=True
            )
            
            if hasattr(self.logger, 'success'):
                self.logger.success(f"Ollama model created: {agent_name}")
            
            if hasattr(self.logger, 'debug') and result.stdout:
                self.logger.debug(f"Ollama output: {result.stdout}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to create Ollama model {agent_name}: {e.stderr}")
            return False
        except FileNotFoundError:
            if hasattr(self.logger, 'error'):
                self.logger.error("Ollama not found. Is it installed?")
            return False
    
    def build_agent(self, agent_name: str, create_model: bool = True) -> Optional[AgentConfig]:
        """
        Complete agent build process
        
        Args:
            agent_name: Name of the agent directory
            create_model: Whether to create Ollama model
        
        Returns:
            AgentConfig if successful, None otherwise
        """
        context = LogContext(agent=agent_name) if LogContext else None
        
        try:
            if hasattr(self.logger, 'info'):
                self.logger.info(f"Building agent: {agent_name}", context=context)
            
            # Load config
            config = self.load_agent_config(agent_name)
            
            # Render system prompt
            system_prompt = self.render_system_prompt(agent_name, config)
            
            # Build Modelfile
            modelfile_path = self.build_modelfile(agent_name, config, system_prompt)
            
            # Create Ollama model if requested
            if create_model:
                model_name = config.name if hasattr(config, 'name') else agent_name
                success = self.create_ollama_model(model_name, modelfile_path)
                if not success:
                    if hasattr(self.logger, 'warning'):
                        self.logger.warning(f"Agent built but Ollama model creation failed: {agent_name}")
            
            # Store in cache
            self.agents[agent_name] = config
            
            if hasattr(self.logger, 'success'):
                self.logger.success(f"Agent build complete: {agent_name}", context=context)
            
            return config
            
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to build agent {agent_name}: {e}", exc_info=True)
            return None
    
    def build_all_agents(self, create_models: bool = True) -> Dict[str, AgentConfig]:
        """
        Build all agents in agents directory
        
        Args:
            create_models: Whether to create Ollama models
        
        Returns:
            Dictionary of successfully built agents
        """
        if hasattr(self.logger, 'info'):
            self.logger.info("Building all agents...")
        
        built_agents = {}
        
        for agent_dir in sorted(self.agents_dir.iterdir()):
            if agent_dir.is_dir() and not agent_dir.name.startswith('.'):
                config = self.build_agent(agent_dir.name, create_models)
                if config:
                    built_agents[agent_dir.name] = config
        
        if hasattr(self.logger, 'success'):
            self.logger.success(f"Built {len(built_agents)} agents")
        
        return built_agents
    
    def get_agent(self, agent_name: str) -> Optional[AgentConfig]:
        """Get loaded agent config"""
        return self.agents.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """List all loaded agent names"""
        return list(self.agents.keys())
    
    def export_agent_config(self, agent_name: str, output_path: str):
        """Export agent config to YAML file"""
        config = self.agents.get(agent_name)
        if not config:
            raise ValueError(f"Agent not found: {agent_name}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        if hasattr(self.logger, 'success'):
            self.logger.success(f"Exported agent config: {output_path}")
    
    def validate_agent_config(self, agent_name: str) -> List[str]:
        """
        Validate agent configuration
        
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        try:
            config = self.load_agent_config(agent_name)
            
            # Check required fields
            if not config.name:
                issues.append("Missing agent name")
            
            if not config.base_model:
                issues.append("Missing base model")
            
            # Check template exists
            template_path = self.agents_dir / agent_name / config.system_prompt.template
            if not template_path.exists():
                issues.append(f"Template not found: {config.system_prompt.template}")
            
            # Check includes exist
            for include in config.includes:
                include_path = self.agents_dir / agent_name / include
                if not include_path.exists():
                    issues.append(f"Include file not found: {include}")
            
            # Validate parameters
            if not 0 <= config.parameters.temperature <= 2:
                issues.append(f"Temperature out of range: {config.parameters.temperature}")
            
            if not 0 <= config.parameters.top_p <= 1:
                issues.append(f"Top-P out of range: {config.parameters.top_p}")
            
            if config.num_ctx < 512:
                issues.append(f"num_ctx too small: {config.num_ctx}")
            
        except Exception as e:
            issues.append(f"Failed to load config: {e}")
        
        return issues


# Example usage and CLI
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Vera Agent Manager")
    parser.add_argument('command', 
                       choices=['build', 'build-all', 'list', 'validate', 'test', 'interactive', 'show-prompt'],
                       help='Command to execute')
    parser.add_argument('--agent', help='Agent name (for build/validate/test/show-prompt)')
    parser.add_argument('--agents-dir', default='./Vera/Agents/agents', help='Agents directory')
    parser.add_argument('--no-create', action='store_true', help='Skip Ollama model creation')
    parser.add_argument('--query', help='Test query for agent (with test command)')
    parser.add_argument('--stream', action='store_true', help='Stream responses (with test command)')
    
    args = parser.parse_args()
    
    # Setup logging
    try:
        from Vera.Logging.logging import get_logger, LoggingConfig, LogLevel
        log_config = LoggingConfig(global_level=LogLevel.INFO)
        logger = get_logger("agent_manager", log_config)
    except ImportError:
        # Fallback to basic logging
        import logging
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        logger = logging.getLogger("agent_manager")
    
    # Create manager
    manager = AgentManager(
        agents_dir=args.agents_dir,
        logger=logger
    )
    
    # Execute command
    if args.command == 'build':
        if not args.agent:
            logger.error("--agent required for build command")
            sys.exit(1)
        
        config = manager.build_agent(args.agent, create_model=not args.no_create)
        if config:
            logger.success(f"✓ Agent built: {args.agent}")
        else:
            logger.error(f"✗ Failed to build agent: {args.agent}")
            sys.exit(1)
    
    elif args.command == 'build-all':
        agents = manager.build_all_agents(create_models=not args.no_create)
        logger.success(f"✓ Built {len(agents)} agents")
    
    elif args.command == 'list':
        agents = manager.build_all_agents(create_models=False)
        logger.info("Available agents:")
        for name, config in agents.items():
            logger.info(f"  • {name}: {config.description}")
            logger.info(f"    Base Model: {config.base_model}")
            logger.info(f"    Temperature: {config.parameters.temperature}")
            logger.info(f"    Context Size: {config.num_ctx}")
            if config.capabilities:
                logger.info(f"    Capabilities: {', '.join(config.capabilities)}")
            logger.info("")
    
    elif args.command == 'validate':
        if not args.agent:
            logger.error("--agent required for validate command")
            sys.exit(1)
        
        issues = manager.validate_agent_config(args.agent)
        if issues:
            logger.warning(f"Validation issues for {args.agent}:")
            for issue in issues:
                logger.warning(f"  • {issue}")
            sys.exit(1)
        else:
            logger.success(f"✓ Agent config valid: {args.agent}")
    
    elif args.command == 'show-prompt':
        if not args.agent:
            logger.error("--agent required for show-prompt command")
            sys.exit(1)
        
        try:
            config = manager.load_agent_config(args.agent)
            system_prompt = manager.render_system_prompt(args.agent, config)
            
            print("\n" + "=" * 80)
            print(f"SYSTEM PROMPT FOR: {args.agent}")
            print("=" * 80)
            print(system_prompt)
            print("=" * 80)
            print(f"\nPrompt size: {len(system_prompt)} characters ({len(system_prompt)/1024:.1f} KB)")
            print(f"Context window: {config.num_ctx} tokens")
            print("=" * 80 + "\n")
        
        except Exception as e:
            logger.error(f"Failed to show prompt: {e}")
            sys.exit(1)
    
    elif args.command == 'test':
        if not args.agent:
            logger.error("--agent required for test command")
            sys.exit(1)
        
        # Build the agent
        config = manager.build_agent(args.agent, create_model=not args.no_create)
        if not config:
            logger.error(f"✗ Failed to build agent: {args.agent}")
            sys.exit(1)
        
        # Test the agent
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING AGENT: {args.agent}")
        logger.info(f"{'='*80}\n")
        
        test_query = args.query or "Hello! Please introduce yourself and describe your capabilities."
        
        logger.info(f"Query: {test_query}\n")
        logger.info(f"{'='*80}")
        logger.info("Response:")
        logger.info(f"{'='*80}\n")
        
        try:
            import ollama
            
            model_name = config.name if hasattr(config, 'name') else args.agent
            
            if args.stream:
                # Stream response
                full_response = ""
                for chunk in ollama.chat(
                    model=model_name,
                    messages=[{'role': 'user', 'content': test_query}],
                    stream=True
                ):
                    content = chunk['message']['content']
                    print(content, end='', flush=True)
                    full_response += content
                print("\n")
            else:
                # Non-streaming response
                response = ollama.chat(
                    model=model_name,
                    messages=[{'role': 'user', 'content': test_query}]
                )
                full_response = response['message']['content']
                print(full_response)
                print()
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Response length: {len(full_response)} characters")
            logger.info(f"{'='*80}\n")
            
        except Exception as e:
            logger.error(f"Failed to test agent: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    elif args.command == 'interactive':
        if not args.agent:
            logger.error("--agent required for interactive command")
            sys.exit(1)
        
        # Build the agent
        config = manager.build_agent(args.agent, create_model=not args.no_create)
        if not config:
            logger.error(f"✗ Failed to build agent: {args.agent}")
            sys.exit(1)
        
        # Interactive chat
        logger.info(f"\n{'='*80}")
        logger.info(f"INTERACTIVE MODE: {args.agent}")
        logger.info(f"Description: {config.description}")
        logger.info(f"{'='*80}")
        logger.info("Commands:")
        logger.info("  /exit, /quit     - Exit interactive mode")
        logger.info("  /clear           - Clear conversation history")
        logger.info("  /info            - Show agent information")
        logger.info("  /prompt          - Show system prompt")
        logger.info(f"{'='*80}\n")
        
        try:
            import ollama
            
            model_name = config.name if hasattr(config, 'name') else args.agent
            conversation_history = []
            
            while True:
                try:
                    user_input = input("\n🔵 You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n")
                    logger.info("Exiting interactive mode...")
                    break
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['/exit', '/quit']:
                    logger.info("Goodbye!")
                    break
                
                elif user_input.lower() == '/clear':
                    conversation_history = []
                    logger.info("Conversation history cleared!")
                    continue
                
                elif user_input.lower() == '/info':
                    print(f"\n{'='*80}")
                    print(f"Agent: {config.name}")
                    print(f"Description: {config.description}")
                    print(f"Base Model: {config.base_model}")
                    print(f"Temperature: {config.parameters.temperature}")
                    print(f"Context Size: {config.num_ctx}")
                    print(f"Top-P: {config.parameters.top_p}")
                    print(f"Top-K: {config.parameters.top_k}")
                    if config.capabilities:
                        print(f"Capabilities: {', '.join(config.capabilities)}")
                    if config.tools:
                        print(f"Tools: {', '.join(config.tools)}")
                    print(f"{'='*80}")
                    continue
                
                elif user_input.lower() == '/prompt':
                    try:
                        system_prompt = manager.render_system_prompt(args.agent, config)
                        print(f"\n{'='*80}")
                        print("SYSTEM PROMPT:")
                        print(f"{'='*80}")
                        print(system_prompt)
                        print(f"{'='*80}")
                        print(f"Size: {len(system_prompt)} chars ({len(system_prompt)/1024:.1f} KB)")
                        print(f"{'='*80}")
                    except Exception as e:
                        logger.error(f"Failed to render prompt: {e}")
                    continue
                
                # Add user message to history
                conversation_history.append({
                    'role': 'user',
                    'content': user_input
                })
                
                # Get response
                print("\n🤖 Agent: ", end='', flush=True)
                
                try:
                    full_response = ""
                    for chunk in ollama.chat(
                        model=model_name,
                        messages=conversation_history,
                        stream=True
                    ):
                        content = chunk['message']['content']
                        print(content, end='', flush=True)
                        full_response += content
                    
                    print()  # Newline after response
                    
                    # Add assistant response to history
                    conversation_history.append({
                        'role': 'assistant',
                        'content': full_response
                    })
                
                except Exception as e:
                    print(f"\n\nError: {e}")
                    logger.error(f"Failed to get response: {e}")
                    # Remove the user message since we couldn't respond
                    conversation_history.pop()
        
        except Exception as e:
            logger.error(f"Failed to start interactive mode: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)