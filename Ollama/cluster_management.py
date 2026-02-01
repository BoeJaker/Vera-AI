#!/usr/bin/env python3
"""
Ollama Cluster Manager - Complete TUI Edition

Unified terminal interface for:
- Real-time cluster monitoring
- Model pulling and syncing
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
    from rich.box import ROUNDED, SIMPLE
    from rich.prompt import Prompt, Confirm
    from rich.align import Align
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


class ClusterManager:
    """Complete cluster management with monitoring and operations"""
    
    def __init__(self, vera_config: Optional[Dict] = None, max_workers: int = 8, verbose: bool = False):
        self.vera_config = vera_config
        self.max_workers = max_workers
        self.verbose = verbose
        self.nodes: Dict[str, NodeInfo] = {}
        self.lock = Lock()
        self.console = Console()
        
        # Connection pooling
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers * 2,
            pool_maxsize=max_workers * 2,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Jinja for model configs
        self.jinja_env = None
        
        if vera_config:
            self._load_nodes_from_config()
    
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
    
    def pull_model_to_host(self, model_name: str, host: str, skip_existing: bool = True) -> Tuple[str, bool]:
        """Pull model to specific host"""
        if skip_existing:
            node = self.nodes.get(host)
            if node and any(m.name == model_name or m.name == f"{model_name}:latest" for m in node.models):
                return (host, True)
        
        try:
            cmd = ["ollama", "pull", model_name]
            env = {**os.environ, "OLLAMA_HOST": host}
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=600
            )
            
            return (host, result.returncode == 0)
        except Exception:
            return (host, False)
    
    def pull_model_to_all(self, model_name: str, target_hosts: List[str], 
                          skip_existing: bool = True, progress: Optional[Progress] = None,
                          task: Optional[TaskID] = None) -> Dict[str, bool]:
        """Pull model to all targets in parallel"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.pull_model_to_host, model_name, host, skip_existing): host 
                for host in target_hosts
            }
            
            for future in as_completed(futures):
                host, success = future.result()
                results[host] = success
                
                if progress and task:
                    progress.advance(task)
        
        return results
    
    def get_all_models_in_cluster(self) -> Set[str]:
        """Get unique set of all models across cluster"""
        all_models = set()
        for node in self.nodes.values():
            if node.status == NodeStatus.ONLINE:
                for model in node.models:
                    all_models.add(model.name)
        return all_models


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
        """Interactive model pull interface"""
        self.console.print("\n[bold cyan]Pull Models[/bold cyan]\n")
        
        # Show available models in cluster
        all_models = sorted(self.manager.get_all_models_in_cluster())
        
        if all_models:
            self.console.print("[dim]Models currently in cluster:[/dim]")
            for model in all_models[:10]:  # Show first 10
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
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            for model_name in models:
                task = progress.add_task(f"[cyan]Pulling {model_name}...", total=len(targets))
                
                results = self.manager.pull_model_to_all(
                    model_name,
                    targets,
                    skip_existing=skip_existing,
                    progress=progress,
                    task=task
                )
                
                success_count = sum(1 for v in results.values() if v)
                
                if success_count == len(targets):
                    self.console.print(f"[green]✓ {model_name} pulled to all targets[/green]")
                else:
                    self.console.print(f"[yellow]⚠ {model_name} pulled to {success_count}/{len(targets)} targets[/yellow]")
        
        # Refresh cluster state
        self.console.print("\n[cyan]Refreshing cluster state...[/cyan]")
        self.scan_cluster_interactive()
    
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
            self.console.print("  [cyan]2[/cyan] - Pull models")
            self.console.print("  [cyan]3[/cyan] - Export graph")
            self.console.print("  [cyan]4[/cyan] - Refresh dashboard")
            self.console.print("  [cyan]q[/cyan] - Quit")
            
            choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "q"], default="4")
            
            if choice == "1":
                self.scan_cluster_interactive()
            elif choice == "2":
                self.pull_models_interactive()
            elif choice == "3":
                self.export_graph_interactive()
            elif choice == "4":
                continue
            elif choice == "q":
                self.console.print("\n[yellow]Goodbye![/yellow]")
                break


def main():
    parser = argparse.ArgumentParser(
        description="Ollama Cluster Manager - Complete TUI",
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