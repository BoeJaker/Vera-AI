#!/usr/bin/env python3
"""
Ollama Cluster Manager - Enhanced Edition with Agent Management

Complete TUI with:
- Real-time cluster monitoring
- Model pulling and syncing with retry logic
- Advanced agent management (list, build, inspect, sync, delete)
- Support for nested agent directory structure
- Graph visualization and export
- Interactive operations

Requirements:
    pip install rich pyyaml requests jinja2
"""

import os
import sys
import json
import yaml
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
import re

from jinja2 import Environment, FileSystemLoader

try:
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TaskID
    from rich.tree import Tree
    from rich.text import Text
    from rich.box import ROUNDED, SIMPLE, DOUBLE
    from rich.prompt import Prompt, Confirm
    from rich.align import Align
    from rich.syntax import Syntax
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    print("Error: 'rich' library is required")
    print("Install with: pip install rich pyyaml requests jinja2")
    sys.exit(1)


class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ModelInfo:
    name: str
    size: int = 0
    modified: str = ""
    digest: str = ""
    family: Optional[str] = None
    format: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization: Optional[str] = None


@dataclass
class NodeInfo:
    name: str
    host: str
    status: NodeStatus = NodeStatus.UNKNOWN
    models: List[ModelInfo] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    max_concurrent: int = 1
    gpu_enabled: bool = False
    gpu_count: int = 0
    total_vram: int = 0
    free_vram: int = 0
    cpu_count: int = 0
    total_memory: int = 0
    free_memory: int = 0
    ollama_version: Optional[str] = None
    last_checked: Optional[str] = None
    response_time_ms: Optional[float] = None


@dataclass
class AgentInfo:
    """Information about a custom agent"""
    name: str
    path: Path
    base_model: str
    config_file: Path
    template_file: Optional[Path] = None
    includes: List[Path] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    num_ctx: Optional[int] = None
    gpu_layers: Optional[int] = None
    description: Optional[str] = None


class ModelSizeEstimator:
    """Estimate model sizes for dynamic timeout calculation"""
    
    @staticmethod
    def estimate_size_gb(model_name: str) -> float:
        """Estimate model size in GB from name patterns"""
        model_lower = model_name.lower()
        
        patterns = {
            r'(\d+)b[^a-z]': lambda x: int(x) * 0.5,
            r'(\d+\.\d+)b': lambda x: float(x) * 0.5,
            r':(\d+)gb': lambda x: int(x),
            r'tiny': lambda _: 0.5,
            r'small': lambda _: 2,
            r'medium': lambda _: 7,
            r'large': lambda _: 30,
            r'xl': lambda _: 70,
        }
        
        for pattern, size_func in patterns.items():
            match = re.search(pattern, model_lower)
            if match:
                try:
                    if match.groups():
                        return size_func(match.group(1))
                    return size_func(None)
                except:
                    continue
        
        return 5.0  # Default 5GB


class ClusterManager:
    """Complete cluster management with monitoring and operations"""
    
    def __init__(self, vera_config: Optional[Dict] = None, max_workers: int = 8, 
                 verbose: bool = False, max_retries: int = 3):
        self.vera_config = vera_config
        self.max_workers = max_workers
        self.verbose = verbose
        self.max_retries = max_retries
        self.nodes: Dict[str, NodeInfo] = {}
        self.lock = Lock()
        self.console = Console()
        
        # Agent system paths
        self.agents_dir = None
        self.templates_dir = None
        self.jinja_env = None
        
        # Connection pooling
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers * 2,
            pool_maxsize=max_workers * 2,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        if vera_config:
            self._load_nodes_from_config()
            self._load_agent_paths()
    
    def copy_model_direct(self, name: str, target_host: str, source_host: Optional[str] = None) -> Tuple[str, bool]:
        """Copy model directly by recreating on target (thread-safe)"""
        try:
            # Use provided source_host or find first online node
            if not source_host:
                for host, node in self.nodes.items():
                    if node.status == NodeStatus.ONLINE:
                        source_host = host
                        break
            
            if not source_host:
                return (target_host, False)
            
            source_url = f"http://{source_host}"
            
            # Get model info from source
            show_url = f"{source_url}/api/show"
            response = self.session.post(
                show_url,
                json={"name": name},
                timeout=30
            )
            response.raise_for_status()
            model_info = response.json()
            
            modelfile = model_info.get('modelfile', '')
            if not modelfile:
                return (target_host, False)
            
            # Save modelfile with unique name
            modelfile_path = Path(f"/tmp/Modelfile.{name}.{target_host.replace(':', '_')}.{os.getpid()}")
            modelfile_path.write_text(modelfile)
            
            # Create model on target
            cmd = ["ollama", "create", name, "-f", str(modelfile_path)]
            env = {**os.environ, "OLLAMA_HOST": target_host}
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=300
            )
            
            # Cleanup
            if modelfile_path.exists():
                modelfile_path.unlink()
            
            if result.returncode == 0:
                return (target_host, True)
            else:
                return (target_host, False)
                
        except Exception as e:
            if self.verbose:
                self.console.print(f"[red]Error copying to {target_host}: {e}[/red]")
            return (target_host, False)

    def _load_nodes_from_config(self):
        """Load node definitions from Vera config"""
        try:
            instances = self.vera_config.get('ollama', {}).get('instances', [])
            
            for instance in instances:
                api_url = instance.get('api_url', '')
                if api_url:
                    host_port = api_url.replace('http://', '').replace('https://', '')
                    
                    node = NodeInfo(
                        name=instance.get('name', 'unknown'),
                        host=host_port,
                        priority=instance.get('priority', 0),
                        enabled=instance.get('enabled', True),
                        max_concurrent=instance.get('max_concurrent', 1)
                    )
                    
                    self.nodes[host_port] = node
        except Exception as e:
            self.console.print(f"[red]Error loading nodes: {e}[/red]")
    
    def _load_agent_paths(self):
        """Load agent system paths from config"""
        try:
            agents_config = self.vera_config.get('agents', {})
            if agents_config.get('enabled', False):
                self.agents_dir = Path(agents_config.get('agents_dir', '/Vera/Ollama/Agents/agents'))
                self.templates_dir = Path(agents_config.get('templates_dir', 'Vera/Ollama/Agents/templates'))
            else:
                # Try default paths even if not explicitly enabled
                default_agents = Path('./Vera/Ollama/Agents/agents')
                if default_agents.exists():
                    self.agents_dir = default_agents
                    self.templates_dir = Path('./Vera/Ollama/Agents/templates')
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not load agent paths: {e}[/yellow]")
    
    def setup_jinja_env(self, template_dir: Path):
        """Setup Jinja2 environment with template directory"""
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        def include_file(filename):
            """Custom Jinja2 filter to include files"""
            file_path = template_dir / filename
            if file_path.exists():
                return file_path.read_text()
            return f"<!-- File not found: {filename} -->"
        
        self.jinja_env.filters['include_file'] = include_file
        self.jinja_env.globals['include_file'] = include_file
    
    # ========== MONITORING METHODS ==========
    
    def check_node_status(self, host: str) -> Tuple[NodeStatus, Optional[float]]:
        """Check if node is online and measure response time"""
        try:
            start = time.time()
            url = f"http://{host}/api/tags"
            response = self.session.get(url, timeout=5)
            response_time = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return (NodeStatus.ONLINE, response_time)
            else:
                return (NodeStatus.DEGRADED, response_time)
        except Exception:
            return (NodeStatus.OFFLINE, None)
    
    def get_node_models(self, host: str) -> List[ModelInfo]:
        """Get list of models on node"""
        try:
            url = f"http://{host}/api/tags"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model_data in data.get('models', []):
                model = ModelInfo(
                    name=model_data.get('name', 'unknown'),
                    size=model_data.get('size', 0),
                    modified=model_data.get('modified_at', ''),
                    digest=model_data.get('digest', '')
                )
                
                details = model_data.get('details', {})
                if details:
                    model.family = details.get('family')
                    model.format = details.get('format')
                    model.parameter_size = details.get('parameter_size')
                    model.quantization = details.get('quantization_level')
                
                models.append(model)
            
            return models
        except Exception:
            return []
    
    def get_node_version(self, host: str) -> Optional[str]:
        """Get Ollama version"""
        try:
            url = f"http://{host}/api/version"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                return response.json().get('version', 'unknown')
        except:
            pass
        return None
    
    def probe_node(self, host: str) -> NodeInfo:
        """Fully probe a node for all information"""
        node = self.nodes.get(host, NodeInfo(name=host, host=host))
        
        status, response_time = self.check_node_status(host)
        node.status = status
        node.response_time_ms = response_time
        node.last_checked = datetime.now().isoformat()
        
        if status == NodeStatus.ONLINE:
            node.models = self.get_node_models(host)
            node.ollama_version = self.get_node_version(host)
            
            # Infer GPU usage from model types
            node.gpu_enabled = any(
                m.format == 'gguf' for m in node.models
            )
        
        return node
    
    def scan_cluster(self, progress_callback=None) -> Dict[str, NodeInfo]:
        """Scan all nodes in parallel with optional progress callback"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.probe_node, host): host 
                for host in self.nodes.keys()
            }
            
            for future in as_completed(futures):
                host = futures[future]
                try:
                    node_info = future.result()
                    results[host] = node_info
                    
                    if progress_callback:
                        progress_callback()
                        
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[red]Error probing {host}: {e}[/red]")
        
        with self.lock:
            self.nodes.update(results)
        
        return results
    
    # ========== GRAPH EXPORT METHODS ==========
    
    def export_to_neo4j_cypher(self, output_file: Optional[Path] = None) -> str:
        """Export cluster topology to Neo4j Cypher statements"""
        statements = []
        
        # Cluster hub
        online_count = sum(1 for n in self.nodes.values() if n.status == NodeStatus.ONLINE)
        statements.append(
            "MERGE (cluster:OllamaCluster {name: 'main'})\n"
            "SET cluster.last_scanned = datetime(),\n"
            f"    cluster.total_nodes = {len(self.nodes)},\n"
            f"    cluster.online_nodes = {online_count}"
        )
        statements.append("")
        
        # Nodes and models
        for host, node in self.nodes.items():
            node_id = host.replace(':', '_').replace('.', '_')
            
            # Node properties
            props = {
                'host': host,
                'name': node.name,
                'status': node.status.value,
                'priority': node.priority,
                'enabled': node.enabled,
                'gpu_enabled': node.gpu_enabled,
                'model_count': len(node.models),
                'last_checked': node.last_checked or '',
                'response_time_ms': node.response_time_ms or 0,
                'ollama_version': node.ollama_version or 'unknown'
            }
            
            props_str = ",\n    ".join([f"{k}: {json.dumps(v)}" for k, v in props.items()])
            
            statements.append(
                f"MERGE (node_{node_id}:OllamaNode {{host: {json.dumps(host)}}})\n"
                f"SET {props_str}"
            )
            statements.append(f"MERGE (node_{node_id})-[:PART_OF]->(cluster)")
            statements.append("")
            
            # Models
            for model in node.models:
                model_id = model.name.replace(':', '_').replace('.', '_').replace('/', '_')
                
                model_props = {
                    'name': model.name,
                    'size': model.size,
                    'digest': model.digest[:16],  # Truncate digest
                    'family': model.family or 'unknown',
                    'format': model.format or 'unknown'
                }
                
                model_props_str = ",\n    ".join([f"{k}: {json.dumps(v)}" for k, v in model_props.items()])
                
                statements.append(
                    f"MERGE (model_{model_id}:OllamaModel {{name: {json.dumps(model.name)}}})\n"
                    f"SET {model_props_str}"
                )
                statements.append(f"MERGE (node_{node_id})-[:HAS_MODEL]->(model_{model_id})")
                statements.append("")
        
        cypher_script = "\n".join(statements)
        
        if output_file:
            output_file.write_text(cypher_script)
        
        return cypher_script
    
    def export_to_graph_json(self) -> Dict:
        """Export cluster as JSON graph structure"""
        graph = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'scanned_at': datetime.now().isoformat(),
                'total_nodes': len(self.nodes),
                'online_nodes': sum(1 for n in self.nodes.values() if n.status == NodeStatus.ONLINE)
            }
        }
        
        # Cluster hub
        graph['nodes'].append({
            'id': 'cluster_hub',
            'type': 'cluster',
            'label': 'Ollama Cluster',
            'properties': graph['metadata']
        })
        
        # Nodes
        for host, node in self.nodes.items():
            node_id = f"node_{host.replace(':', '_').replace('.', '_')}"
            
            graph['nodes'].append({
                'id': node_id,
                'type': 'ollama_node',
                'label': node.name,
                'properties': {
                    'host': host,
                    'status': node.status.value,
                    'priority': node.priority,
                    'gpu_enabled': node.gpu_enabled,
                    'model_count': len(node.models),
                    'response_time_ms': node.response_time_ms
                }
            })
            
            graph['edges'].append({
                'source': node_id,
                'target': 'cluster_hub',
                'type': 'PART_OF'
            })
            
            # Models
            for model in node.models:
                model_id = f"model_{model.name.replace(':', '_').replace('.', '_').replace('/', '_')}"
                
                if not any(n['id'] == model_id for n in graph['nodes']):
                    graph['nodes'].append({
                        'id': model_id,
                        'type': 'model',
                        'label': model.name,
                        'properties': {
                            'name': model.name,
                            'size': model.size,
                            'family': model.family
                        }
                    })
                
                graph['edges'].append({
                    'source': node_id,
                    'target': model_id,
                    'type': 'HAS_MODEL'
                })
        
        return graph
    
    # ========== MODEL OPERATIONS ==========
    
    def pull_model_to_host(self, model_name: str, host: str, skip_existing: bool = True,
                           progress_callback=None) -> Tuple[str, bool, str]:
        """Pull model to specific host with streaming progress and retry logic"""
        if skip_existing:
            node = self.nodes.get(host)
            if node and any(m.name == model_name or m.name == f"{model_name}:latest" for m in node.models):
                return (host, True, "Already exists")
        
        # Retry loop
        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                wait = (2 ** (attempt - 1)) * 5
                if progress_callback:
                    progress_callback(host, f"Retry {attempt}/{self.max_retries} (wait:{wait}s)")
                time.sleep(wait)
            
            try:
                cmd = ["ollama", "pull", model_name]
                env = {**os.environ, "OLLAMA_HOST": host}
                
                # Stream output instead of capturing - NO TIMEOUT
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                last_status = ""
                for line in iter(process.stdout.readline, ''):
                    if line:
                        line = line.strip()
                        if line:  # Only update on non-empty lines
                            last_status = line
                            
                            # Call progress callback if provided
                            if progress_callback:
                                progress_callback(host, line)
                
                process.wait()
                success = process.returncode == 0
                
                if success:
                    return (host, True, f"Success (attempt {attempt})")
                elif attempt < self.max_retries:
                    continue
                else:
                    return (host, False, f"Failed: {last_status}")
                    
            except Exception as e:
                if attempt < self.max_retries:
                    continue
                return (host, False, f"Error: {str(e)}")
        
        return (host, False, "Max retries exceeded")
    
    def pull_model_to_all(self, model_name: str, target_hosts: List[str], 
                          skip_existing: bool = True, progress_manager=None) -> Dict[str, Tuple[bool, str]]:
        """Pull model to all targets in parallel with live progress"""
        results = {}
        
        # Track progress for each host
        host_status = {host: "Initializing..." for host in target_hosts}
        status_lock = Lock()
        
        def update_host_status(host: str, status: str):
            with status_lock:
                # Truncate very long status messages
                if len(status) > 80:
                    status = status[:77] + "..."
                host_status[host] = status
                if progress_manager:
                    progress_manager(host_status.copy())
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(target_hosts))) as executor:
            futures = {
                executor.submit(
                    self.pull_model_to_host, 
                    model_name, 
                    host, 
                    skip_existing,
                    lambda h, s: update_host_status(h, s)
                ): host 
                for host in target_hosts
            }
            
            for future in as_completed(futures):
                host = futures[future]
                host_name, success, status = future.result()
                results[host] = (success, status)
                
                # Final status update
                final_status = f"{'✓ Complete' if success else '✗ Failed'}: {status}"
                update_host_status(host, final_status)
        
        return results
    
    def get_all_models_in_cluster(self) -> Set[str]:
        """Get unique set of all models across cluster"""
        all_models = set()
        for node in self.nodes.values():
            if node.status == NodeStatus.ONLINE:
                for model in node.models:
                    all_models.add(model.name)
        return all_models
    
    def get_models_from_config(self) -> Set[str]:
        """Extract all model references from Vera config"""
        models = set()
        
        if not self.vera_config:
            return models
        
        # Get models from the models section
        models_config = self.vera_config.get('models', {})
        for key, value in models_config.items():
            if isinstance(value, str) and not key.endswith('_temperature'):
                models.add(value)
        
        # Get models from counsel instances
        counsel_config = self.vera_config.get('counsel', {})
        for instance in counsel_config.get('instances', []):
            if isinstance(instance, str) and ':' in instance:
                # Format is "host:model"
                model = instance.split(':', 1)[1]
                models.add(model)
        
        # Get GPU-only and GPU-preferred models
        ollama_config = self.vera_config.get('ollama', {})
        for model in ollama_config.get('gpu_only_models', []):
            models.add(model)
        for model in ollama_config.get('gpu_preferred_models', []):
            models.add(model)
        
        return models
    
    # ========== AGENT DISCOVERY AND MANAGEMENT ==========
    
    def discover_agents(self) -> List[AgentInfo]:
        """Discover all agent configurations in the agents directory"""
        agents = []
        
        if not self.agents_dir or not self.agents_dir.exists():
            return agents
        
        # Look for agent directories (each agent in its own folder)
        for agent_path in self.agents_dir.iterdir():
            if not agent_path.is_dir():
                continue
            
            # Look for YAML config files in the agent directory
            config_files = list(agent_path.glob("*.yaml")) + list(agent_path.glob("*.yml"))
            
            if not config_files:
                continue
            
            # Use the first config file found
            config_file = config_files[0]
            
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                agent_name = config.get('name', agent_path.name)
                base_model = config.get('base_model')
                
                if not base_model:
                    continue
                
                # Find template file
                template_file = None
                system_prompt_config = config.get('system_prompt', {})
                template_name = system_prompt_config.get('template')
                
                if template_name:
                    # Check in agent directory first
                    local_template = agent_path / template_name
                    if local_template.exists():
                        template_file = local_template
                    # Then check in shared templates directory
                    elif self.templates_dir:
                        shared_template = self.templates_dir / template_name
                        if shared_template.exists():
                            template_file = shared_template
                
                # Find includes
                includes = []
                includes_dir = agent_path / "includes"
                if includes_dir.exists():
                    includes = list(includes_dir.iterdir())
                
                agent_info = AgentInfo(
                    name=agent_name,
                    path=agent_path,
                    base_model=base_model,
                    config_file=config_file,
                    template_file=template_file,
                    includes=includes,
                    parameters=config.get('parameters', {}),
                    num_ctx=config.get('num_ctx'),
                    gpu_layers=config.get('gpu_layers'),
                    description=config.get('description')
                )
                
                agents.append(agent_info)
                
            except Exception as e:
                if self.verbose:
                    self.console.print(f"[yellow]Warning: Could not parse {config_file}: {e}[/yellow]")
        
        return sorted(agents, key=lambda a: a.name)
    
    def load_agent_config(self, config_path: Path) -> Dict[str, Any]:
        """Load and validate agent configuration from YAML"""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        required = ['name', 'base_model']
        missing = [field for field in required if field not in config]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        return config
    
    def render_modelfile(self, config: Dict[str, Any], agent_path: Path) -> str:
        """Render Modelfile from config using Jinja2 template"""
        # Determine template directory (agent dir or shared templates)
        template_dirs = [agent_path]
        if self.templates_dir and self.templates_dir.exists():
            template_dirs.append(self.templates_dir)
        
        # Setup Jinja environment with multiple search paths
        jinja_env = Environment(
            loader=FileSystemLoader([str(d) for d in template_dirs]),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Custom filter for including files
        def include_file(filename):
            """Include file from agent's includes directory or template directory"""
            # Try includes directory first
            includes_dir = agent_path / "includes"
            include_path = includes_dir / filename
            
            if include_path.exists():
                return include_path.read_text()
            
            # Try template directories
            for template_dir in template_dirs:
                alt_path = template_dir / filename
                if alt_path.exists():
                    return alt_path.read_text()
            
            return f"<!-- File not found: {filename} -->"
        
        jinja_env.filters['include_file'] = include_file
        jinja_env.globals['include_file'] = include_file
        
        # Get template configuration
        system_prompt_config = config.get('system_prompt', {})
        template_file = system_prompt_config.get('template', 'prompt_template.j2')
        template_vars = system_prompt_config.get('variables', {})
        
        # Pre-load includes
        includes = config.get('includes', [])
        included_content = {}
        includes_dir = agent_path / "includes"
        
        for include_path in includes:
            full_path = includes_dir / include_path
            if full_path.exists():
                included_content[include_path] = full_path.read_text()
            else:
                # Try template directories
                for template_dir in template_dirs:
                    alt_path = template_dir / include_path
                    if alt_path.exists():
                        included_content[include_path] = alt_path.read_text()
                        break
        
        template_vars['_includes'] = included_content
        
        # Render system prompt
        try:
            template = jinja_env.get_template(template_file)
            system_prompt = template.render(**template_vars)
        except Exception as e:
            self.console.print(f"[yellow]Template render error: {e}, using default[/yellow]")
            system_prompt = "You are a helpful AI assistant."
        
        # Build Modelfile
        modelfile_lines = [
            f"FROM {config['base_model']}",
            "",
            "# System prompt",
            f'SYSTEM """{system_prompt}"""',
            ""
        ]
        
        if 'parameters' in config:
            modelfile_lines.append("# Parameters")
            for key, value in config['parameters'].items():
                modelfile_lines.append(f"PARAMETER {key} {value}")
            modelfile_lines.append("")
        
        if 'num_ctx' in config:
            modelfile_lines.append(f"PARAMETER num_ctx {config['num_ctx']}")
            modelfile_lines.append("")
        
        if 'gpu_layers' in config and config['gpu_layers']:
            modelfile_lines.append(f"PARAMETER num_gpu {config['gpu_layers']}")
            modelfile_lines.append("")
        
        return "\n".join(modelfile_lines)
    
    def build_agent_on_host(self, agent: AgentInfo, host: str) -> Tuple[str, bool, str]:
        """Build agent model on specific host"""
        try:
            # Load config and render modelfile
            config = self.load_agent_config(agent.config_file)
            modelfile = self.render_modelfile(config, agent.path)
            
            # Save modelfile temporarily
            modelfile_path = Path(f"/tmp/Modelfile.{agent.name}.{host.replace(':', '_')}.{os.getpid()}")
            modelfile_path.write_text(modelfile)
            
            try:
                cmd = ["ollama", "create", agent.name, "-f", str(modelfile_path)]
                env = {**os.environ, "OLLAMA_HOST": host}
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=300
                )
                
                if result.returncode == 0:
                    return (host, True, "Success")
                else:
                    error_msg = result.stderr[:100] if result.stderr else "Build failed"
                    return (host, False, error_msg)
                    
            finally:
                if modelfile_path.exists():
                    modelfile_path.unlink()
                    
        except Exception as e:
            return (host, False, str(e))
    
    def sync_agent_to_all(self, agent: AgentInfo, target_hosts: List[str], 
                          progress_manager=None) -> Dict[str, Tuple[bool, str]]:
        """Sync agent to all target hosts in parallel"""
        results = {}
        host_status = {host: "Building agent..." for host in target_hosts}
        status_lock = Lock()
        
        def update_status(host: str, status: str):
            with status_lock:
                host_status[host] = status
                if progress_manager:
                    progress_manager(host_status.copy())
        
        # Build on all hosts in parallel
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(target_hosts))) as executor:
            futures = {
                executor.submit(self.build_agent_on_host, agent, host): host
                for host in target_hosts
            }
            
            for future in as_completed(futures):
                host = futures[future]
                _, success, message = future.result()
                results[host] = (success, message)
                
                status = f"{'✓ Success' if success else '✗ Failed'}: {message}"
                update_status(host, status)
        
        return results
    
    def delete_agent_from_host(self, agent_name: str, host: str) -> Tuple[bool, str]:
        """Delete agent from a specific host"""
        try:
            cmd = ["ollama", "rm", agent_name]
            env = {**os.environ, "OLLAMA_HOST": host}
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            
            if result.returncode == 0:
                return (True, "Deleted")
            else:
                return (False, result.stderr[:100] if result.stderr else "Delete failed")
                
        except Exception as e:
            return (False, str(e))
    
    def get_agent_deployment_status(self, agent_name: str) -> Dict[str, bool]:
        """Check which nodes have the agent deployed"""
        status = {}
        for host, node in self.nodes.items():
            if node.status == NodeStatus.ONLINE:
                has_agent = any(m.name == agent_name or m.name == f"{agent_name}:latest" 
                               for m in node.models)
                status[host] = has_agent
        return status


class ClusterTUI:
    """Interactive TUI for cluster management"""
    
    def __init__(self, manager: ClusterManager):
        self.manager = manager
        self.console = Console()
        self.current_view = "main_menu"
    
    def render_cluster_table(self) -> Table:
        """Render cluster status table"""
        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED, title="Cluster Status")
        table.add_column("Node", style="cyan", no_wrap=True, width=25)
        table.add_column("Status", justify="center", width=8)
        table.add_column("Models", justify="right", width=7)
        table.add_column("Response", justify="right", width=10)
        table.add_column("GPU", justify="center", width=5)
        table.add_column("Version", justify="left", width=12)
        
        for host, node in sorted(self.manager.nodes.items(), key=lambda x: x[1].priority, reverse=True):
            # Status
            if node.status == NodeStatus.ONLINE:
                status = Text("●", style="green bold")
            elif node.status == NodeStatus.OFFLINE:
                status = Text("●", style="red bold")
            else:
                status = Text("●", style="yellow bold")
            
            # GPU
            gpu = "🎮" if node.gpu_enabled else "💻"
            
            # Response time
            response = f"{node.response_time_ms:.0f}ms" if node.response_time_ms else "N/A"
            
            # Version
            version = node.ollama_version or "unknown"
            
            table.add_row(
                f"{node.name}\n[dim]{host}[/dim]",
                status,
                str(len(node.models)),
                response,
                gpu,
                version
            )
        
        return table
    
    def render_model_distribution_table(self) -> Table:
        """Render model distribution across cluster"""
        # Collect model distribution
        model_dist = {}
        total_online = sum(1 for n in self.manager.nodes.values() if n.status == NodeStatus.ONLINE)
        
        for node in self.manager.nodes.values():
            if node.status == NodeStatus.ONLINE:
                for model in node.models:
                    if model.name not in model_dist:
                        model_dist[model.name] = {
                            'count': 0,
                            'nodes': [],
                            'size': model.size
                        }
                    model_dist[model.name]['count'] += 1
                    model_dist[model.name]['nodes'].append(node.name)
        
        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED, title="Model Distribution")
        table.add_column("Model", style="cyan", width=30)
        table.add_column("Nodes", justify="right", width=8)
        table.add_column("Distribution", justify="left", width=25)
        table.add_column("Size", justify="right", width=10)
        
        for model_name, info in sorted(model_dist.items()):
            count = info['count']
            
            # Distribution bar
            if total_online > 0:
                bar_length = 20
                filled = int((count / total_online) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                
                # Color based on distribution
                if count == total_online:
                    bar_style = "green"
                elif count > total_online / 2:
                    bar_style = "yellow"
                else:
                    bar_style = "red"
                
                bar_text = Text(bar, style=bar_style)
            else:
                bar_text = Text("N/A", style="dim")
            
            # Size formatting
            size_gb = info['size'] / (1024**3)
            size_str = f"{size_gb:.1f} GB" if size_gb > 0 else "N/A"
            
            table.add_row(
                model_name,
                f"{count}/{total_online}",
                bar_text,
                size_str
            )
        
        return table
    
    def show_dashboard(self):
        """Display main dashboard"""
        self.console.clear()
        
        # Header
        header = Panel(
            Text.assemble(
                ("🚀 Ollama Cluster Manager\n", "bold magenta"),
                (f"Last scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "dim")
            ),
            border_style="bright_blue",
            box=ROUNDED
        )
        
        self.console.print(header)
        self.console.print()
        
        # Stats
        total = len(self.manager.nodes)
        online = sum(1 for n in self.manager.nodes.values() if n.status == NodeStatus.ONLINE)
        total_models = sum(len(n.models) for n in self.manager.nodes.values() if n.status == NodeStatus.ONLINE)
        unique_models = len(self.manager.get_all_models_in_cluster())
        
        stats = Table.grid(padding=1)
        stats.add_column(style="cyan", justify="right")
        stats.add_column(style="green")
        
        stats.add_row("Nodes:", f"{online}/{total} online")
        stats.add_row("Models:", f"{unique_models} unique, {total_models} total")
        
        self.console.print(Panel(stats, title="Summary", border_style="blue", box=ROUNDED))
        self.console.print()
        
        # Cluster table
        self.console.print(self.render_cluster_table())
        self.console.print()
        
        # Model distribution
        self.console.print(self.render_model_distribution_table())
    
    def scan_cluster_interactive(self):
        """Scan cluster with progress display"""
        total = len(self.manager.nodes)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            task = progress.add_task("[cyan]Scanning cluster...", total=total)
            
            def update_progress():
                progress.advance(task)
            
            self.manager.scan_cluster(progress_callback=update_progress)
        
        self.console.print("[green]✓ Scan complete[/green]")
    
    def pull_models_interactive(self):
        """Interactive model pull interface with live progress"""
        self.console.print("\n[bold cyan]Pull Models[/bold cyan]\n")
        
        # Show available models in cluster
        all_models = sorted(self.manager.get_all_models_in_cluster())
        
        if all_models:
            self.console.print("[dim]Models currently in cluster:[/dim]")
            for model in all_models[:10]:
                self.console.print(f"  • {model}")
            if len(all_models) > 10:
                self.console.print(f"  ... and {len(all_models) - 10} more")
            self.console.print()
        
        # Get model names
        model_input = Prompt.ask("Enter model name(s) to pull (space-separated)")
        models = model_input.strip().split()
        
        if not models:
            self.console.print("[yellow]No models specified[/yellow]")
            return
        
        # Get targets
        online_hosts = [h for h, n in self.manager.nodes.items() if n.status == NodeStatus.ONLINE]
        
        if not online_hosts:
            self.console.print("[red]No online nodes available[/red]")
            return
        
        pull_to_all = Confirm.ask("Pull to all online nodes?", default=True)
        
        if pull_to_all:
            targets = online_hosts
        else:
            self.console.print("\n[cyan]Available nodes:[/cyan]")
            for i, host in enumerate(online_hosts, 1):
                node = self.manager.nodes[host]
                self.console.print(f"  {i}. {node.name} ({host})")
            
            selections = Prompt.ask("Select nodes (comma-separated numbers)").split(',')
            targets = []
            for sel in selections:
                try:
                    idx = int(sel.strip()) - 1
                    if 0 <= idx < len(online_hosts):
                        targets.append(online_hosts[idx])
                except:
                    pass
        
        if not targets:
            self.console.print("[yellow]No targets selected[/yellow]")
            return
        
        # Pull models
        skip_existing = Confirm.ask("Skip models that already exist?", default=True)
        
        self.console.print()
        
        # Pull each model with live progress display
        for model_name in models:
            self.console.print(f"\n[bold cyan]Pulling {model_name} to {len(targets)} node(s)...[/bold cyan]")
            
            # Create live display table
            def create_progress_table(status_dict):
                table = Table(show_header=True, header_style="bold cyan", box=ROUNDED, 
                             title=f"Progress: {model_name}")
                table.add_column("Node", width=25)
                table.add_column("Status", width=60)
                
                for host in targets:
                    node = self.manager.nodes[host]
                    status = status_dict.get(host, "Waiting...")
                    
                    # Color code the status
                    if "✓" in status:
                        status_text = Text(status, style="green")
                    elif "✗" in status:
                        status_text = Text(status, style="red")
                    elif "Already exists" in status:
                        status_text = Text(status, style="yellow")
                    else:
                        status_text = Text(status, style="white")
                    
                    table.add_row(f"{node.name}\n[dim]{host}[/dim]", status_text)
                
                return table
            
            # Initial table
            current_status = {host: "Initializing..." for host in targets}
            
            # Use Live to update the table in real-time
            with Live(create_progress_table(current_status), console=self.console, refresh_per_second=2) as live:
                def update_display(host_status):
                    nonlocal current_status
                    current_status = host_status
                    live.update(create_progress_table(current_status))
                
                # Pull models
                results = self.manager.pull_model_to_all(
                    model_name,
                    targets,
                    skip_existing=skip_existing,
                    progress_manager=update_display
                )
                
                # Final update with results
                time.sleep(0.5)  # Brief pause to show final state
            
            # Summary
            success_count = sum(1 for success, _ in results.values() if success)
            
            if success_count == len(targets):
                self.console.print(f"[green]✓ {model_name} pulled to all {len(targets)} targets[/green]")
            elif success_count > 0:
                self.console.print(f"[yellow]⚠ {model_name} pulled to {success_count}/{len(targets)} targets[/yellow]")
            else:
                self.console.print(f"[red]✗ {model_name} failed to pull to any targets[/red]")
        
        # Refresh cluster state
        self.console.print("\n[cyan]Refreshing cluster state...[/cyan]")
        self.scan_cluster_interactive()
    
    def equalize_cluster_interactive(self):
        """Equalize all nodes to have the same models"""
        self.console.print("\n[bold cyan]Equalize Cluster[/bold cyan]\n")
        self.console.print("This will ensure all online nodes have the same models.\n")
        
        # Get all unique models
        all_models = sorted(self.manager.get_all_models_in_cluster())
        
        if not all_models:
            self.console.print("[yellow]No models found in cluster[/yellow]")
            return
        
        self.console.print(f"[cyan]Found {len(all_models)} unique model(s):[/cyan]")
        for model in all_models:
            self.console.print(f"  • {model}")
        
        self.console.print()
        
        if not Confirm.ask("Proceed with equalization?", default=True):
            return
        
        # Get online nodes
        online_hosts = [h for h, n in self.manager.nodes.items() if n.status == NodeStatus.ONLINE]
        
        if len(online_hosts) < 2:
            self.console.print("[yellow]Need at least 2 online nodes for equalization[/yellow]")
            return
        
        # Pull each model to all nodes
        for model_name in all_models:
            self.console.print(f"\n[bold cyan]Equalizing: {model_name}[/bold cyan]")
            
            def create_progress_table(status_dict):
                table = Table(show_header=True, header_style="bold cyan", box=ROUNDED,
                             title=f"Progress: {model_name}")
                table.add_column("Node", width=25)
                table.add_column("Status", width=60)
                
                for host in online_hosts:
                    node = self.manager.nodes[host]
                    status = status_dict.get(host, "Waiting...")
                    
                    if "✓" in status or "Already exists" in status:
                        status_text = Text(status, style="green")
                    elif "✗" in status:
                        status_text = Text(status, style="red")
                    else:
                        status_text = Text(status, style="white")
                    
                    table.add_row(f"{node.name}\n[dim]{host}[/dim]", status_text)
                
                return table
            
            current_status = {host: "Checking..." for host in online_hosts}
            
            with Live(create_progress_table(current_status), console=self.console, refresh_per_second=2) as live:
                def update_display(host_status):
                    nonlocal current_status
                    current_status = host_status
                    live.update(create_progress_table(current_status))
                
                results = self.manager.pull_model_to_all(
                    model_name,
                    online_hosts,
                    skip_existing=True,
                    progress_manager=update_display
                )
                
                time.sleep(0.5)
        
        self.console.print("\n[green]✓ Cluster equalization complete[/green]")
        
        # Refresh state
        self.console.print("\n[cyan]Refreshing cluster state...[/cyan]")
        self.scan_cluster_interactive()
    
    def pull_from_config_interactive(self):
        """Pull all models referenced in config and agents"""
        self.console.print("\n[bold cyan]Pull Models from Config & Agents[/bold cyan]\n")
        
        # Get models from config
        config_models = self.manager.get_models_from_config()
        
        # Get base models from agents
        agents = self.manager.discover_agents()
        agent_models = {agent.base_model for agent in agents}
        
        if not config_models and not agent_models:
            self.console.print("[yellow]No models found in config or agents[/yellow]")
            return
        
        # Display what was found
        if config_models:
            self.console.print(f"[cyan]Models from config ({len(config_models)}):[/cyan]")
            for model in sorted(config_models):
                self.console.print(f"  • {model}")
            self.console.print()
        
        if agent_models:
            self.console.print(f"[cyan]Agent base models ({len(agent_models)}):[/cyan]")
            agent_map = {agent.base_model: [] for agent in agents}
            for agent in agents:
                agent_map[agent.base_model].append(agent.name)
            
            for model in sorted(agent_models):
                agent_names = ", ".join(agent_map[model])
                self.console.print(f"  • {model} (used by: {agent_names})")
            self.console.print()
        
        # Combine all models
        all_base_models = config_models | agent_models
        
        self.console.print(f"[bold]Total unique base models: {len(all_base_models)}[/bold]\n")
        
        # Ask for operation mode
        self.console.print("[cyan]Operation mode:[/cyan]")
        self.console.print("  1. Pull all models at once (batch)")
        self.console.print("  2. Pull models one-by-one (sequential)")
        
        mode = Prompt.ask("Select mode", choices=["1", "2"], default="1")
        batch_mode = (mode == "1")
        
        # Get targets
        online_hosts = [h for h, n in self.manager.nodes.items() if n.status == NodeStatus.ONLINE]
        
        if not online_hosts:
            self.console.print("[red]No online nodes available[/red]")
            return
        
        pull_to_all = Confirm.ask("Pull to all online nodes?", default=True)
        
        if pull_to_all:
            targets = online_hosts
        else:
            self.console.print("\n[cyan]Available nodes:[/cyan]")
            for i, host in enumerate(online_hosts, 1):
                node = self.manager.nodes[host]
                self.console.print(f"  {i}. {node.name} ({host})")
            
            selections = Prompt.ask("Select nodes (comma-separated numbers)").split(',')
            targets = []
            for sel in selections:
                try:
                    idx = int(sel.strip()) - 1
                    if 0 <= idx < len(online_hosts):
                        targets.append(online_hosts[idx])
                except:
                    pass
        
        if not targets:
            self.console.print("[yellow]No targets selected[/yellow]")
            return
        
        skip_existing = Confirm.ask("Skip models that already exist?", default=True)
        
        self.console.print()
        
        # Pull models
        if batch_mode:
            # Pull all at once
            for model_name in sorted(all_base_models):
                self.console.print(f"\n[bold cyan]Pulling {model_name}[/bold cyan]")
                
                def create_progress_table(status_dict):
                    table = Table(show_header=True, header_style="bold cyan", box=ROUNDED,
                                 title=f"Progress: {model_name}")
                    table.add_column("Node", width=25)
                    table.add_column("Status", width=60)
                    
                    for host in targets:
                        node = self.manager.nodes[host]
                        status = status_dict.get(host, "Waiting...")
                        
                        if "✓" in status or "Already exists" in status:
                            status_text = Text(status, style="green")
                        elif "✗" in status:
                            status_text = Text(status, style="red")
                        else:
                            status_text = Text(status, style="white")
                        
                        table.add_row(f"{node.name}\n[dim]{host}[/dim]", status_text)
                    
                    return table
                
                current_status = {host: "Initializing..." for host in targets}
                
                with Live(create_progress_table(current_status), console=self.console, refresh_per_second=2) as live:
                    def update_display(host_status):
                        nonlocal current_status
                        current_status = host_status
                        live.update(create_progress_table(current_status))
                    
                    results = self.manager.pull_model_to_all(
                        model_name,
                        targets,
                        skip_existing=skip_existing,
                        progress_manager=update_display
                    )
                    
                    time.sleep(0.5)
        else:
            # Pull one-by-one with confirmation
            for model_name in sorted(all_base_models):
                self.console.print(f"\n[bold cyan]Model: {model_name}[/bold cyan]")
                
                # Show which agents use this model
                using_agents = [agent.name for agent in agents if agent.base_model == model_name]
                if using_agents:
                    self.console.print(f"[dim]Used by agents: {', '.join(using_agents)}[/dim]")
                
                if not Confirm.ask("Pull this model?", default=True):
                    self.console.print("[yellow]Skipped[/yellow]")
                    continue
                
                def create_progress_table(status_dict):
                    table = Table(show_header=True, header_style="bold cyan", box=ROUNDED,
                                 title=f"Progress: {model_name}")
                    table.add_column("Node", width=25)
                    table.add_column("Status", width=60)
                    
                    for host in targets:
                        node = self.manager.nodes[host]
                        status = status_dict.get(host, "Waiting...")
                        
                        if "✓" in status or "Already exists" in status:
                            status_text = Text(status, style="green")
                        elif "✗" in status:
                            status_text = Text(status, style="red")
                        else:
                            status_text = Text(status, style="white")
                        
                        table.add_row(f"{node.name}\n[dim]{host}[/dim]", status_text)
                    
                    return table
                
                current_status = {host: "Initializing..." for host in targets}
                
                with Live(create_progress_table(current_status), console=self.console, refresh_per_second=2) as live:
                    def update_display(host_status):
                        nonlocal current_status
                        current_status = host_status
                        live.update(create_progress_table(current_status))
                    
                    results = self.manager.pull_model_to_all(
                        model_name,
                        targets,
                        skip_existing=skip_existing,
                        progress_manager=update_display
                    )
                    
                    time.sleep(0.5)
        
        self.console.print("\n[green]✓ Config models pull complete[/green]")
        
        # Refresh state
        self.console.print("\n[cyan]Refreshing cluster state...[/cyan]")
        self.scan_cluster_interactive()
    
    def agent_management_menu(self):
        """Agent management submenu"""
        while True:
            self.console.clear()
            
            # Header
            header = Panel(
                Text("🤖 Agent Management", style="bold magenta"),
                border_style="bright_blue",
                box=ROUNDED
            )
            self.console.print(header)
            self.console.print()
            
            # Check if agents directory exists
            if not self.manager.agents_dir or not self.manager.agents_dir.exists():
                self.console.print(f"[red]Agents directory not found or not configured[/red]")
                self.console.print(f"[dim]Expected: {self.manager.agents_dir}[/dim]\n")
                
                if not Confirm.ask("Return to main menu?", default=True):
                    sys.exit(0)
                return
            
            # Discover agents
            agents = self.manager.discover_agents()
            
            if agents:
                self.console.print(f"[cyan]Found {len(agents)} agent(s) in {self.manager.agents_dir}[/cyan]\n")
            else:
                self.console.print(f"[yellow]No agents found in {self.manager.agents_dir}[/yellow]\n")
            
            # Menu
            self.console.print("[bold cyan]Agent Operations:[/bold cyan]")
            self.console.print("  [cyan]1[/cyan] - List all agents")
            self.console.print("  [cyan]2[/cyan] - Inspect agent (config, template, includes)")
            self.console.print("  [cyan]3[/cyan] - Build agent(s) locally")
            self.console.print("  [cyan]4[/cyan] - Sync agent(s) to cluster")
            self.console.print("  [cyan]5[/cyan] - Check agent deployment status")
            self.console.print("  [cyan]6[/cyan] - Delete agent from nodes")
            self.console.print("  [cyan]b[/cyan] - Back to main menu")
            
            choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5", "6", "b"], default="1")
            
            if choice == "1":
                self.list_agents_interactive(agents)
            elif choice == "2":
                self.inspect_agent_interactive(agents)
            elif choice == "3":
                self.build_agents_interactive(agents)
            elif choice == "4":
                self.sync_agents_interactive(agents)
            elif choice == "5":
                self.check_agent_deployment_interactive(agents)
            elif choice == "6":
                self.delete_agent_interactive(agents)
            elif choice == "b":
                break
    
    def list_agents_interactive(self, agents: List[AgentInfo]):
        """Display list of agents with details"""
        if not agents:
            self.console.print("\n[yellow]No agents found[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED, title="Available Agents")
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style="cyan", width=25)
        table.add_column("Base Model", width=25)
        table.add_column("Config", width=12)
        table.add_column("Template", width=12)
        table.add_column("Includes", justify="right", width=8)
        
        for i, agent in enumerate(agents, 1):
            has_config = "✓" if agent.config_file.exists() else "✗"
            has_template = "✓" if agent.template_file and agent.template_file.exists() else "✗"
            includes_count = str(len(agent.includes))
            
            table.add_row(
                str(i),
                agent.name,
                agent.base_model,
                has_config,
                has_template,
                includes_count
            )
        
        self.console.print(table)
        input("\nPress Enter to continue...")
    
    def inspect_agent_interactive(self, agents: List[AgentInfo]):
        """Inspect agent configuration, template, and includes"""
        if not agents:
            self.console.print("\n[yellow]No agents found[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        # Show agent list
        for i, agent in enumerate(agents, 1):
            self.console.print(f"  {i}. {agent.name} (base: {agent.base_model})")
        
        self.console.print()
        
        selection = Prompt.ask("Select agent number to inspect")
        
        try:
            idx = int(selection) - 1
            if idx < 0 or idx >= len(agents):
                self.console.print("[red]Invalid selection[/red]")
                input("\nPress Enter to continue...")
                return
            
            agent = agents[idx]
            
            self.console.clear()
            self.console.print(f"\n[bold cyan]Inspecting Agent: {agent.name}[/bold cyan]\n")
            
            # Agent info
            info_table = Table.grid(padding=1)
            info_table.add_column(style="cyan", justify="right")
            info_table.add_column()
            
            info_table.add_row("Name:", agent.name)
            info_table.add_row("Base Model:", agent.base_model)
            info_table.add_row("Path:", str(agent.path))
            info_table.add_row("Config File:", str(agent.config_file))
            
            if agent.template_file:
                info_table.add_row("Template File:", str(agent.template_file))
            
            if agent.num_ctx:
                info_table.add_row("Context Size:", str(agent.num_ctx))
            
            if agent.gpu_layers:
                info_table.add_row("GPU Layers:", str(agent.gpu_layers))
            
            if agent.description:
                info_table.add_row("Description:", agent.description)
            
            self.console.print(Panel(info_table, title="Agent Info", border_style="cyan", box=ROUNDED))
            self.console.print()
            
            # Parameters
            if agent.parameters:
                self.console.print("[bold cyan]Parameters:[/bold cyan]")
                for key, value in agent.parameters.items():
                    self.console.print(f"  {key}: {value}")
                self.console.print()
            
            # Includes
            if agent.includes:
                self.console.print(f"[bold cyan]Includes ({len(agent.includes)}):[/bold cyan]")
                for include in agent.includes:
                    size = include.stat().st_size if include.exists() else 0
                    self.console.print(f"  • {include.name} ({size} bytes)")
                self.console.print()
            
            # Ask what to view
            self.console.print("[cyan]View detailed files:[/cyan]")
            self.console.print("  1. YAML Config")
            self.console.print("  2. Template (if exists)")
            self.console.print("  3. Includes (if exist)")
            self.console.print("  4. Generated Modelfile")
            self.console.print("  5. Back")
            
            view_choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5"], default="5")
            
            if view_choice == "1":
                # Show YAML config
                self.console.print()
                config_content = agent.config_file.read_text()
                syntax = Syntax(config_content, "yaml", theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title=f"Config: {agent.config_file.name}", border_style="cyan"))
                input("\nPress Enter to continue...")
            
            elif view_choice == "2":
                # Show template
                if agent.template_file and agent.template_file.exists():
                    self.console.print()
                    template_content = agent.template_file.read_text()
                    syntax = Syntax(template_content, "jinja2", theme="monokai", line_numbers=True)
                    self.console.print(Panel(syntax, title=f"Template: {agent.template_file.name}", border_style="cyan"))
                    input("\nPress Enter to continue...")
                else:
                    self.console.print("\n[yellow]No template file found[/yellow]")
                    input("\nPress Enter to continue...")
            
            elif view_choice == "3":
                # Show includes
                if agent.includes:
                    for include in agent.includes:
                        self.console.print()
                        try:
                            content = include.read_text()
                            # Determine syntax from extension
                            ext = include.suffix.lower()
                            syntax_lang = {
                                '.md': 'markdown',
                                '.txt': 'text',
                                '.json': 'json',
                                '.yaml': 'yaml',
                                '.yml': 'yaml',
                                '.py': 'python',
                                '.sh': 'bash'
                            }.get(ext, 'text')
                            
                            syntax = Syntax(content, syntax_lang, theme="monokai", line_numbers=True)
                            self.console.print(Panel(syntax, title=f"Include: {include.name}", border_style="cyan"))
                        except Exception as e:
                            self.console.print(f"[red]Error reading {include.name}: {e}[/red]")
                    
                    input("\nPress Enter to continue...")
                else:
                    self.console.print("\n[yellow]No includes found[/yellow]")
                    input("\nPress Enter to continue...")
            
            elif view_choice == "4":
                # Generate and show Modelfile
                try:
                    config = self.manager.load_agent_config(agent.config_file)
                    modelfile = self.manager.render_modelfile(config, agent.path)
                    
                    self.console.print()
                    syntax = Syntax(modelfile, "dockerfile", theme="monokai", line_numbers=True)
                    self.console.print(Panel(syntax, title=f"Generated Modelfile: {agent.name}", border_style="cyan"))
                    input("\nPress Enter to continue...")
                except Exception as e:
                    self.console.print(f"\n[red]Error generating Modelfile: {e}[/red]")
                    input("\nPress Enter to continue...")
        
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            input("\nPress Enter to continue...")
    
    def build_agents_interactive(self, agents: List[AgentInfo]):
        """Build agent(s) on local Ollama instance"""
        if not agents:
            self.console.print("\n[yellow]No agents found[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        # Ask which agents to build
        self.console.print("[cyan]Build mode:[/cyan]")
        self.console.print("  1. Build all agents")
        self.console.print("  2. Select specific agents")
        
        mode = Prompt.ask("Select mode", choices=["1", "2"], default="1")
        
        selected_agents = agents
        
        if mode == "2":
            for i, agent in enumerate(agents, 1):
                self.console.print(f"  {i}. {agent.name} (base: {agent.base_model})")
            
            selections = Prompt.ask("\nSelect agents (comma-separated numbers)").split(',')
            selected_agents = []
            for sel in selections:
                try:
                    idx = int(sel.strip()) - 1
                    if 0 <= idx < len(agents):
                        selected_agents.append(agents[idx])
                except:
                    pass
        
        if not selected_agents:
            self.console.print("[yellow]No agents selected[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        # Get local host (first node or localhost)
        local_host = None
        for host, node in self.manager.nodes.items():
            if node.status == NodeStatus.ONLINE:
                local_host = host
                break
        
        if not local_host:
            local_host = "localhost:11434"
        
        self.console.print(f"\n[cyan]Building on: {local_host}[/cyan]\n")
        
        # Build each agent
        for agent in selected_agents:
            self.console.print(f"[bold cyan]Building: {agent.name}[/bold cyan]")
            
            _, success, message = self.manager.build_agent_on_host(agent, local_host)
            
            if success:
                self.console.print(f"[green]✓ {agent.name} built successfully[/green]")
            else:
                self.console.print(f"[red]✗ {agent.name} build failed: {message}[/red]")
            
            self.console.print()
        
        input("Press Enter to continue...")
    
    def sync_agents_interactive(self, agents: List[AgentInfo]):
        """Sync custom agents to selected nodes"""
        if not agents:
            self.console.print("\n[yellow]No agents found[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        # Ask which agents to sync
        self.console.print("[cyan]Sync mode:[/cyan]")
        self.console.print("  1. Sync all agents")
        self.console.print("  2. Select specific agents")
        
        mode = Prompt.ask("Select mode", choices=["1", "2"], default="1")
        
        selected_agents = agents
        
        if mode == "2":
            for i, agent in enumerate(agents, 1):
                self.console.print(f"  {i}. {agent.name} (base: {agent.base_model})")
            
            selections = Prompt.ask("\nSelect agents (comma-separated numbers)").split(',')
            selected_agents = []
            for sel in selections:
                try:
                    idx = int(sel.strip()) - 1
                    if 0 <= idx < len(agents):
                        selected_agents.append(agents[idx])
                except:
                    pass
        
        if not selected_agents:
            self.console.print("[yellow]No agents selected[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        # Get source and target hosts
        online_hosts = [h for h, n in self.manager.nodes.items() if n.status == NodeStatus.ONLINE]
        
        if not online_hosts:
            self.console.print("[red]No online nodes available[/red]")
            input("\nPress Enter to continue...")
            return
        
        # Determine source host (first online node)
        source_host = online_hosts[-1]
        self.console.print(f"\n[cyan]Source host: {self.manager.nodes[source_host].name} ({source_host})[/cyan]")
        
        sync_to_all = Confirm.ask("Sync to all other online nodes?", default=True)
        
        if sync_to_all:
            targets = [h for h in online_hosts if h != source_host]
        else:
            self.console.print("\n[cyan]Available target nodes:[/cyan]")
            for i, host in enumerate(online_hosts, 1):
                if host == source_host:
                    continue
                node = self.manager.nodes[host]
                self.console.print(f"  {i}. {node.name} ({host})")
            
            selections = Prompt.ask("\nSelect nodes (comma-separated numbers)").split(',')
            targets = []
            for sel in selections:
                try:
                    idx = int(sel.strip()) - 1
                    if 0 <= idx < len(online_hosts):
                        target_host = online_hosts[idx]
                        if target_host != source_host:
                            targets.append(target_host)
                except:
                    pass
        
        if not targets:
            self.console.print("[yellow]No targets selected[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        # Sync each agent: BUILD on source first, then COPY to targets
        for agent in selected_agents:
            self.console.print(f"\n[bold cyan]Syncing agent: {agent.name}[/bold cyan]")
            
            # STEP 1: Build on source host
            self.console.print(f"[cyan]Building on source ({self.manager.nodes[source_host].name})...[/cyan]")
            
            source_name, source_success, source_msg = self.manager.build_agent_on_host(agent, source_host)
            
            if not source_success:
                self.console.print(f"[red]✗ Failed to build on source: {source_msg}[/red]")
                self.console.print(f"[yellow]Skipping sync for {agent.name}[/yellow]")
                continue
            
            self.console.print(f"[green]✓ Built successfully on source[/green]")
            
            # STEP 2: Copy to all targets in parallel
            self.console.print(f"\n[cyan]Copying to {len(targets)} target node(s)...[/cyan]")
            
            def create_progress_table(status_dict):
                table = Table(show_header=True, header_style="bold cyan", box=ROUNDED,
                            title=f"Copying: {agent.name}")
                table.add_column("Node", width=25)
                table.add_column("Status", width=60)
                
                for host in targets:
                    node = self.manager.nodes[host]
                    status = status_dict.get(host, "Waiting...")
                    
                    if "✓" in status:
                        status_text = Text(status, style="green")
                    elif "✗" in status:
                        status_text = Text(status, style="red")
                    else:
                        status_text = Text(status, style="white")
                    
                    table.add_row(f"{node.name}\n[dim]{host}[/dim]", status_text)
                
                return table
            
            current_status = {host: "Copying..." for host in targets}
            
            # Use copy_model_direct instead of build (since it's already built on source)
            with Live(create_progress_table(current_status), console=self.console, refresh_per_second=2) as live:
                results = {}
                status_lock = Lock()
                
                def update_status(host: str, status: str):
                    with status_lock:
                        current_status[host] = status
                        live.update(create_progress_table(current_status))
                
                with ThreadPoolExecutor(max_workers=min(self.manager.max_workers, len(targets))) as executor:
                    futures = {
                        executor.submit(self.manager.copy_model_direct, agent.name, host, source_host): host
                        for host in targets
                    }
                    
                    for future in as_completed(futures):
                        host = futures[future]
                        _, success = future.result()
                        results[host] = success
                        
                        status = f"{'✓ Success' if success else '✗ Failed'}"
                        update_status(host, status)
                
                time.sleep(0.5)
            
            success_count = sum(1 for success in results.values() if success)
            if success_count == len(targets):
                self.console.print(f"[green]✓ {agent.name} synced to all targets[/green]")
            else:
                self.console.print(f"[yellow]⚠ {agent.name} synced to {success_count}/{len(targets)} targets[/yellow]")
        
        self.console.print("\n[green]✓ Agent sync complete[/green]")
        input("\nPress Enter to continue...")

    def check_agent_deployment_interactive(self, agents: List[AgentInfo]):
        """Check deployment status of agents across cluster"""
        if not agents:
            self.console.print("\n[yellow]No agents found[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        # Refresh cluster state
        self.console.print("[cyan]Refreshing cluster state...[/cyan]")
        self.scan_cluster_interactive()
        
        self.console.print()
        
        # Create deployment matrix
        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED, title="Agent Deployment Status")
        table.add_column("Agent", style="cyan", width=25)
        
        # Add column for each online node
        online_hosts = [h for h, n in self.manager.nodes.items() if n.status == NodeStatus.ONLINE]
        for host in online_hosts:
            node = self.manager.nodes[host]
            table.add_column(node.name, justify="center", width=12)
        
        table.add_column("Total", justify="center", width=8)
        
        # Check each agent
        for agent in agents:
            row = [agent.name]
            deployed_count = 0
            
            for host in online_hosts:
                node = self.manager.nodes[host]
                has_agent = any(m.name == agent.name or m.name == f"{agent.name}:latest" 
                               for m in node.models)
                
                if has_agent:
                    row.append(Text("✓", style="green"))
                    deployed_count += 1
                else:
                    row.append(Text("✗", style="dim"))
            
            # Total column
            if deployed_count == len(online_hosts):
                row.append(Text(f"{deployed_count}/{len(online_hosts)}", style="green"))
            elif deployed_count > 0:
                row.append(Text(f"{deployed_count}/{len(online_hosts)}", style="yellow"))
            else:
                row.append(Text(f"{deployed_count}/{len(online_hosts)}", style="red"))
            
            table.add_row(*row)
        
        self.console.print(table)
        input("\nPress Enter to continue...")
    
    def delete_agent_interactive(self, agents: List[AgentInfo]):
        """Delete agent from selected nodes"""
        if not agents:
            self.console.print("\n[yellow]No agents found[/yellow]")
            input("\nPress Enter to continue...")
            return
        
        self.console.print()
        
        # Show agents
        for i, agent in enumerate(agents, 1):
            self.console.print(f"  {i}. {agent.name}")
        
        selection = Prompt.ask("\nSelect agent number to delete")
        
        try:
            idx = int(selection) - 1
            if idx < 0 or idx >= len(agents):
                self.console.print("[red]Invalid selection[/red]")
                input("\nPress Enter to continue...")
                return
            
            agent = agents[idx]
            
            # Get deployment status
            deployment = self.manager.get_agent_deployment_status(agent.name)
            deployed_hosts = [host for host, deployed in deployment.items() if deployed]
            
            if not deployed_hosts:
                self.console.print(f"\n[yellow]{agent.name} is not deployed on any nodes[/yellow]")
                input("\nPress Enter to continue...")
                return
            
            self.console.print(f"\n[cyan]{agent.name} is deployed on:[/cyan]")
            for host in deployed_hosts:
                node = self.manager.nodes[host]
                self.console.print(f"  • {node.name} ({host})")
            
            self.console.print()
            
            # Confirm deletion
            if not Confirm.ask(f"[bold red]Delete {agent.name} from these nodes?[/bold red]", default=False):
                return
            
            # Delete from each host
            self.console.print()
            for host in deployed_hosts:
                node = self.manager.nodes[host]
                self.console.print(f"Deleting from {node.name}...", end=" ")
                
                success, message = self.manager.delete_agent_from_host(agent.name, host)
                
                if success:
                    self.console.print("[green]✓[/green]")
                else:
                    self.console.print(f"[red]✗ {message}[/red]")
            
            self.console.print("\n[green]✓ Deletion complete[/green]")
            input("\nPress Enter to continue...")
        
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            input("\nPress Enter to continue...")
    
    def export_graph_interactive(self):
        """Interactive graph export"""
        self.console.print("\n[bold cyan]Export Cluster Graph[/bold cyan]\n")
        self.console.print("1. Neo4j Cypher")
        self.console.print("2. JSON Graph")
        self.console.print("3. Both")
        
        choice = Prompt.ask("Select format", choices=["1", "2", "3"], default="3")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if choice in ['1', '3']:
            cypher_file = Path(f"cluster_graph_{timestamp}.cypher")
            self.manager.export_to_neo4j_cypher(cypher_file)
            self.console.print(f"[green]✓ Exported to {cypher_file}[/green]")
        
        if choice in ['2', '3']:
            json_file = Path(f"cluster_graph_{timestamp}.json")
            graph_json = self.manager.export_to_graph_json()
            json_file.write_text(json.dumps(graph_json, indent=2))
            self.console.print(f"[green]✓ Exported to {json_file}[/green]")
    
    def run(self):
        """Main TUI loop"""
        # Initial scan
        self.console.print("[cyan]Initializing cluster scan...[/cyan]\n")
        self.scan_cluster_interactive()
        
        while True:
            self.show_dashboard()
            
            self.console.print("\n[bold cyan]Menu:[/bold cyan]")
            self.console.print("  [cyan]1[/cyan] - Scan cluster")
            self.console.print("  [cyan]2[/cyan] - Pull models (manual)")
            self.console.print("  [cyan]3[/cyan] - Pull from config & agents")
            self.console.print("  [cyan]4[/cyan] - Equalize cluster")
            self.console.print("  [cyan]5[/cyan] - Agent management")
            self.console.print("  [cyan]6[/cyan] - Export graph")
            self.console.print("  [cyan]7[/cyan] - Refresh dashboard")
            self.console.print("  [cyan]q[/cyan] - Quit")
            
            choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5", "6", "7", "q"], default="7")
            
            if choice == "1":
                self.scan_cluster_interactive()
            elif choice == "2":
                self.pull_models_interactive()
            elif choice == "3":
                self.pull_from_config_interactive()
            elif choice == "4":
                self.equalize_cluster_interactive()
            elif choice == "5":
                self.agent_management_menu()
            elif choice == "6":
                self.export_graph_interactive()
            elif choice == "7":
                continue
            elif choice == "q":
                self.console.print("\n[yellow]Goodbye![/yellow]")
                break


def main():
    parser = argparse.ArgumentParser(
        description="Ollama Cluster Manager - Enhanced with Agent Management",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--vera-config',
        type=Path,
        help='Path to Vera config YAML file'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='Max parallel workers (default: 8)'
    )
    
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Max retry attempts per model (default: 3)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Load config
    vera_config = None
    console = Console()
    
    if args.vera_config:
        if not args.vera_config.exists():
            console.print(f"[red]Error: Config file not found: {args.vera_config}[/red]")
            return 1
        
        with open(args.vera_config, 'r') as f:
            vera_config = yaml.safe_load(f)
    else:
        # Try to find config
        search_paths = [
            Path.cwd() / "vera_config.yaml",
            Path.cwd() / "config" / "vera_config.yaml",
            Path.home() / ".config" / "vera" / "vera_config.yaml",
        ]
        
        for path in search_paths:
            if path.exists():
                console.print(f"[green]Found config: {path}[/green]")
                with open(path, 'r') as f:
                    vera_config = yaml.safe_load(f)
                break
    
    if not vera_config:
        console.print("[red]Error: No Vera config found[/red]")
        console.print("Please specify with --vera-config or place vera_config.yaml in current directory")
        return 1
    
    # Initialize manager
    manager = ClusterManager(
        vera_config=vera_config,
        max_workers=args.workers,
        max_retries=args.retries,
        verbose=args.verbose
    )
    
    # Run TUI
    tui = ClusterTUI(manager)
    
    try:
        tui.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())