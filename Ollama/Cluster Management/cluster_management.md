#!/usr/bin/env python3
"""
Ollama Cluster Manager - Unified TUI
Manages multiple Ollama instances with rich visual feedback
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

console = Console()


def load_vera_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load Vera configuration file."""
    if config_path is None:
        # Try to find vera_config.yaml in current directory
        config_path = "vera_config.yaml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        console.print(f"[red]✗[/red] Config file not found: {config_path}")
        console.print("\nTried: vera_config.yaml in current directory")
        console.print("Use --vera-config to specify path")
        sys.exit(1)
    
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        if 'ollama_instances' not in config:
            console.print(f"[red]✗[/red] No 'ollama_instances' found in {config_path}")
            sys.exit(1)
        
        return config
    
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load config: {e}")
        sys.exit(1)


def check_node_health(node: Dict[str, Any]) -> Dict[str, Any]:
    """Check if a node is online and get basic info."""
    host = node['host']
    url = f"http://{host}/api/tags"
    
    start_time = time.time()
    
    try:
        resp = requests.get(url, timeout=5)
        response_time = (time.time() - start_time) * 1000  # ms
        
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('models', [])
            
            # Try to get version
            version = "unknown"
            try:
                version_resp = requests.get(f"http://{host}/api/version", timeout=2)
                if version_resp.status_code == 200:
                    version = version_resp.json().get('version', 'unknown')
            except:
                pass
            
            # Check for GPU
            gpu_enabled = any('gpu' in m.get('details', {}).get('family', '').lower() 
                            for m in models) or node.get('gpu_enabled', False)
            
            return {
                'name': node.get('name', host),
                'host': host,
                'status': 'online',
                'models': models,
                'model_count': len(models),
                'response_time_ms': response_time,
                'version': version,
                'gpu_enabled': gpu_enabled,
                'priority': node.get('priority', 5),
                'enabled': node.get('enabled', True)
            }
        else:
            return {
                'name': node.get('name', host),
                'host': host,
                'status': 'error',
                'error': f"HTTP {resp.status_code}",
                'models': [],
                'model_count': 0
            }
    
    except requests.exceptions.Timeout:
        return {
            'name': node.get('name', host),
            'host': host,
            'status': 'timeout',
            'error': 'Request timed out',
            'models': [],
            'model_count': 0
        }
    except requests.exceptions.ConnectionError:
        return {
            'name': node.get('name', host),
            'host': host,
            'status': 'offline',
            'error': 'Connection refused',
            'models': [],
            'model_count': 0
        }
    except Exception as e:
        return {
            'name': node.get('name', host),
            'host': host,
            'status': 'error',
            'error': str(e),
            'models': [],
            'model_count': 0
        }


def scan_cluster(nodes: List[Dict[str, Any]], max_workers: int = 8) -> List[Dict[str, Any]]:
    """Scan all nodes in parallel."""
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task("Scanning cluster...", total=len(nodes))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_node_health, node): node for node in nodes}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    node = futures[future]
                    results.append({
                        'name': node.get('name', node['host']),
                        'host': node['host'],
                        'status': 'error',
                        'error': str(e),
                        'models': [],
                        'model_count': 0
                    })
                
                progress.advance(task)
    
    return results


def pull_model_to_node(node: Dict[str, Any], model: str, skip_existing: bool = True) -> Dict[str, Any]:
    """Pull a model to a specific node with progress tracking."""
    host = node['host']
    url = f"http://{host}/api/pull"
    
    # Check if model already exists
    if skip_existing:
        tags_url = f"http://{host}/api/tags"
        try:
            resp = requests.get(tags_url, timeout=5)
            if resp.status_code == 200:
                existing = resp.json().get('models', [])
                if any(m['name'] == model for m in existing):
                    return {
                        'success': True,
                        'skipped': True,
                        'node': node['name'],
                        'model': model
                    }
        except Exception as e:
            # If we can't check, proceed with pull anyway
            pass
    
    # Pull the model with proper streaming
    try:
        resp = requests.post(
            url, 
            json={'name': model, 'stream': True},
            stream=True,
            timeout=600  # 10 minute timeout for large models
        )
        
        if resp.status_code != 200:
            error_text = resp.text[:200] if resp.text else "Unknown error"
            return {
                'success': False,
                'error': f"HTTP {resp.status_code}: {error_text}",
                'node': node['name'],
                'model': model
            }
        
        # Track progress through streaming response
        total = 0
        completed = 0
        status = ""
        last_status = ""
        
        for line in resp.iter_lines():
            if not line:
                continue
                
            try:
                data = json.loads(line.decode('utf-8'))
                
                # Update progress tracking
                if 'total' in data:
                    total = data['total']
                if 'completed' in data:
                    completed = data['completed']
                if 'status' in data:
                    status = data['status']
                    last_status = status
                    
                # Check for completion
                if status == 'success':
                    return {
                        'success': True,
                        'skipped': False,
                        'node': node['name'],
                        'model': model,
                        'size': total if total > 0 else completed
                    }
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                # Continue processing other lines
                continue
        
        # After streaming completes, verify the model exists
        try:
            verify_resp = requests.get(f"http://{host}/api/tags", timeout=5)
            if verify_resp.status_code == 200:
                existing = verify_resp.json().get('models', [])
                if any(m['name'] == model for m in existing):
                    return {
                        'success': True,
                        'skipped': False,
                        'node': node['name'],
                        'model': model,
                        'size': total if total > 0 else completed
                    }
        except:
            pass
            
        # If we got here, something went wrong
        return {
            'success': False,
            'error': f"Pull stream ended without success (last status: {last_status})",
            'node': node['name'],
            'model': model
        }
        
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': "Request timed out after 10 minutes",
            'node': node['name'],
            'model': model
        }
    except requests.exceptions.ConnectionError as e:
        return {
            'success': False,
            'error': f"Connection failed: {str(e)[:100]}",
            'node': node['name'],
            'model': model
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)[:100]}",
            'node': node['name'],
            'model': model
        }


def pull_models(model_names: List[str], target_nodes: List[Dict[str, Any]], 
                skip_existing: bool = True, max_workers: int = 4):
    """Pull multiple models to multiple nodes."""
    
    # Create pull tasks (model, node pairs)
    tasks = [(model, node) for model in model_names for node in target_nodes]
    
    total_tasks = len(tasks)
    completed_tasks = 0
    failed_tasks = []
    skipped_count = 0
    
    console.print(f"\n[cyan]Pulling {len(model_names)} model(s) to {len(target_nodes)} node(s)[/cyan]")
    console.print(f"Total operations: {total_tasks}\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        for model in model_names:
            model_task = progress.add_task(f"Pulling {model}...", total=len(target_nodes))
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(pull_model_to_node, node, model, skip_existing): (model, node) 
                    for node in target_nodes
                }
                
                for future in as_completed(futures):
                    model, node = futures[future]
                    
                    try:
                        result = future.result()
                        
                        if result['success']:
                            if result.get('skipped'):
                                skipped_count += 1
                            completed_tasks += 1
                        else:
                            failed_tasks.append({
                                'model': model,
                                'node': node['name'],
                                'error': result.get('error', 'Unknown error')
                            })
                        
                    except Exception as e:
                        failed_tasks.append({
                            'model': model,
                            'node': node['name'],
                            'error': str(e)
                        })
                    
                    progress.advance(model_task)
            
            # Show result for this model
            if not any(f['model'] == model for f in failed_tasks):
                console.print(f"[green]✓[/green] {model} pulled to all targets")
            else:
                model_failures = [f for f in failed_tasks if f['model'] == model]
                console.print(f"[yellow]⚠[/yellow] {model} had {len(model_failures)} failure(s)")
    
    # Summary
    console.print(f"\n[bold]Pull Summary:[/bold]")
    console.print(f"  Completed: {completed_tasks}/{total_tasks}")
    console.print(f"  Skipped (already exist): {skipped_count}")
    console.print(f"  Failed: {len(failed_tasks)}")
    
    if failed_tasks:
        console.print(f"\n[yellow]Failures:[/yellow]")
        for failure in failed_tasks:
            console.print(f"  • {failure['model']} → {failure['node']}: {failure['error']}")


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}PB"


def create_dashboard(cluster_state: List[Dict[str, Any]]) -> Panel:
    """Create the main dashboard panel."""
    
    # Header with timestamp
    last_scan = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"Last scan: {last_scan}"
    
    # Summary stats
    online_nodes = sum(1 for n in cluster_state if n['status'] == 'online')
    total_nodes = len(cluster_state)
    
    # Collect all unique models
    all_models = {}
    for node in cluster_state:
        if node['status'] == 'online':
            for model in node['models']:
                model_name = model['name']
                if model_name not in all_models:
                    all_models[model_name] = {
                        'name': model_name,
                        'nodes': [],
                        'size': model.get('size', 0)
                    }
                all_models[model_name]['nodes'].append(node['name'])
    
    unique_models = len(all_models)
    total_model_instances = sum(len(v['nodes']) for v in all_models.values())
    
    # Summary table
    summary = Table.grid(padding=(0, 2))
    summary.add_column(justify="right")
    summary.add_column(justify="left")
    summary.add_row("Nodes:", f"{online_nodes}/{total_nodes} online")
    summary.add_row("Models:", f"{unique_models} unique, {total_model_instances} total")
    
    summary_panel = Panel(summary, title="Summary", border_style="cyan")
    
    # Cluster status table
    status_table = Table(show_header=True, header_style="bold cyan", expand=True)
    status_table.add_column("Node", style="bold")
    status_table.add_column("Status", justify="center")
    status_table.add_column("Models", justify="right")
    status_table.add_column("Response", justify="right")
    status_table.add_column("GPU", justify="center")
    status_table.add_column("Ver", justify="center")
    
    # Sort by priority (high to low), then by status
    sorted_nodes = sorted(
        cluster_state, 
        key=lambda n: (n.get('priority', 0), n['status'] == 'online'),
        reverse=True
    )
    
    for node in sorted_nodes:
        # Status indicator
        if node['status'] == 'online':
            status = Text("●", style="green")
        elif node['status'] == 'offline':
            status = Text("●", style="red")
        else:
            status = Text("●", style="yellow")
        
        # GPU indicator
        gpu_icon = "🎮" if node.get('gpu_enabled') else "💻"
        
        # Response time (if available)
        response = ""
        if 'response_time_ms' in node:
            rt = node['response_time_ms']
            if rt < 50:
                response = f"{rt:.0f}ms"
            elif rt < 100:
                response = Text(f"{rt:.0f}ms", style="yellow")
            else:
                response = Text(f"{rt:.0f}ms", style="red")
        
        # Version
        version = node.get('version', '?')
        
        status_table.add_row(
            f"{node['name']}\n{Text(node['host'], style='dim')}",
            status,
            str(node.get('model_count', 0)),
            response,
            gpu_icon,
            version
        )
    
    status_panel = Panel(status_table, title="Cluster Status", border_style="cyan")
    
    # Model distribution table
    if all_models:
        model_table = Table(show_header=True, header_style="bold cyan", expand=True)
        model_table.add_column("Model", style="bold")
        model_table.add_column("Nodes", justify="right")
        model_table.add_column("Distribution", justify="left")
        model_table.add_column("Size", justify="right")
        
        # Sort by coverage (high to low)
        sorted_models = sorted(
            all_models.values(),
            key=lambda m: len(m['nodes']),
            reverse=True
        )
        
        for model_info in sorted_models[:10]:  # Top 10
            node_count = len(model_info['nodes'])
            coverage = node_count / online_nodes if online_nodes > 0 else 0
            
            # Distribution bar (20 chars)
            filled = int(coverage * 20)
            bar = "█" * filled + "░" * (20 - filled)
            
            # Color based on coverage
            if coverage == 1.0:
                bar = Text(bar, style="green")
            elif coverage >= 0.5:
                bar = Text(bar, style="yellow")
            else:
                bar = Text(bar, style="red")
            
            model_table.add_row(
                model_info['name'],
                f"{node_count}/{online_nodes}",
                bar,
                format_size(model_info['size'])
            )
        
        model_panel = Panel(model_table, title="Model Distribution", border_style="cyan")
    else:
        model_panel = Panel(
            Text("No models found", style="dim italic"),
            title="Model Distribution",
            border_style="cyan"
        )
    
    # Combine all panels
    from rich.console import Group
    dashboard_content = Group(
        Text(header, style="dim", justify="center"),
        Text(""),
        summary_panel,
        Text(""),
        status_panel,
        Text(""),
        model_panel
    )
    
    return Panel(
        dashboard_content,
        title="🚀 Ollama Cluster Manager",
        border_style="bold cyan",
        padding=(1, 2)
    )


def export_graph_cypher(cluster_state: List[Dict[str, Any]], output_path: Path):
    """Export cluster as Neo4j Cypher statements."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path.name:
        output_path = output_path / f"cluster_graph_{timestamp}.cypher"
    
    lines = []
    
    # Create cluster hub
    online_count = sum(1 for n in cluster_state if n['status'] == 'online')
    lines.append("// Ollama Cluster Graph - Neo4j Cypher")
    lines.append(f"// Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append("// Create cluster hub")
    lines.append("MERGE (cluster:OllamaCluster {name: 'main'})")
    lines.append("SET cluster.last_scanned = datetime(),")
    lines.append(f"    cluster.total_nodes = {len(cluster_state)},")
    lines.append(f"    cluster.online_nodes = {online_count};")
    lines.append("")
    
    # Create nodes
    lines.append("// Create Ollama nodes")
    for node in cluster_state:
        node_id = node['host'].replace('.', '_').replace(':', '_')
        lines.append(f"MERGE (node_{node_id}:OllamaNode {{host: \"{node['host']}\"}}) ")
        lines.append(f"SET node_{node_id}.name = \"{node['name']}\",")
        lines.append(f"    node_{node_id}.status = \"{node['status']}\",")
        lines.append(f"    node_{node_id}.priority = {node.get('priority', 5)},")
        lines.append(f"    node_{node_id}.enabled = {str(node.get('enabled', True)).lower()},")
        lines.append(f"    node_{node_id}.gpu_enabled = {str(node.get('gpu_enabled', False)).lower()},")
        lines.append(f"    node_{node_id}.model_count = {node.get('model_count', 0)};")
        lines.append(f"MERGE (node_{node_id})-[:PART_OF]->(cluster);")
        lines.append("")
    
    # Create models and relationships
    lines.append("// Create models and relationships")
    processed_models = set()
    
    for node in cluster_state:
        if node['status'] != 'online':
            continue
        
        node_id = node['host'].replace('.', '_').replace(':', '_')
        
        for model in node['models']:
            model_name = model['name']
            model_id = model_name.replace(':', '_').replace('.', '_').replace('/', '_')
            
            # Create model node (only once)
            if model_id not in processed_models:
                lines.append(f"MERGE (model_{model_id}:OllamaModel {{name: \"{model_name}\"}})")
                lines.append(f"SET model_{model_id}.size = {model.get('size', 0)},")
                
                details = model.get('details', {})
                lines.append(f"    model_{model_id}.family = \"{details.get('family', 'unknown')}\",")
                lines.append(f"    model_{model_id}.format = \"{details.get('format', 'unknown')}\";")
                
                processed_models.add(model_id)
            
            # Create relationship
            lines.append(f"MERGE (node_{node_id})-[:HAS_MODEL]->(model_{model_id});")
        
        lines.append("")
    
    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    
    console.print(f"[green]✓[/green] Cypher export saved to: {output_path}")


def export_graph_json(cluster_state: List[Dict[str, Any]], output_path: Path):
    """Export cluster as JSON graph."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path.name:
        output_path = output_path / f"cluster_graph_{timestamp}.json"
    
    nodes = []
    edges = []
    
    # Cluster hub
    online_count = sum(1 for n in cluster_state if n['status'] == 'online')
    nodes.append({
        'id': 'cluster_hub',
        'type': 'cluster',
        'label': 'Ollama Cluster',
        'properties': {
            'scanned_at': datetime.now().isoformat(),
            'total_nodes': len(cluster_state),
            'online_nodes': online_count
        }
    })
    
    # Nodes
    processed_models = set()
    
    for node in cluster_state:
        node_id = f"node_{node['host'].replace('.', '_').replace(':', '_')}"
        
        nodes.append({
            'id': node_id,
            'type': 'ollama_node',
            'label': node['name'],
            'properties': {
                'host': node['host'],
                'status': node['status'],
                'priority': node.get('priority', 5),
                'gpu_enabled': node.get('gpu_enabled', False),
                'model_count': node.get('model_count', 0),
                'response_time_ms': node.get('response_time_ms')
            }
        })
        
        edges.append({
            'source': node_id,
            'target': 'cluster_hub',
            'type': 'PART_OF'
        })
        
        # Models
        if node['status'] == 'online':
            for model in node['models']:
                model_name = model['name']
                model_id = f"model_{model_name.replace(':', '_').replace('.', '_').replace('/', '_')}"
                
                if model_id not in processed_models:
                    nodes.append({
                        'id': model_id,
                        'type': 'model',
                        'label': model_name,
                        'properties': {
                            'name': model_name,
                            'size': model.get('size', 0),
                            'family': model.get('details', {}).get('family', 'unknown'),
                            'format': model.get('details', {}).get('format', 'unknown')
                        }
                    })
                    processed_models.add(model_id)
                
                edges.append({
                    'source': node_id,
                    'target': model_id,
                    'type': 'HAS_MODEL'
                })
    
    graph = {
        'nodes': nodes,
        'edges': edges,
        'metadata': {
            'generated': datetime.now().isoformat(),
            'node_count': len(cluster_state),
            'model_count': len(processed_models)
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(graph, f, indent=2)
    
    console.print(f"[green]✓[/green] JSON export saved to: {output_path}")


def interactive_pull(cluster_state: List[Dict[str, Any]]):
    """Interactive model pulling interface."""
    
    console.print("\n[bold cyan]Pull Models[/bold cyan]\n")
    
    # Show available models
    all_models = set()
    for node in cluster_state:
        if node['status'] == 'online':
            for model in node['models']:
                all_models.add(model['name'])
    
    if all_models:
        console.print("Models currently in cluster:")
        for model in sorted(all_models):
            console.print(f"  • {model}")
        console.print()
    
    # Get model names
    model_input = Prompt.ask("Enter model name(s) to pull (space-separated)")
    if not model_input.strip():
        console.print("[yellow]No models specified[/yellow]")
        return
    
    model_names = model_input.strip().split()
    
    # Get target nodes
    online_nodes = [n for n in cluster_state if n['status'] == 'online']
    
    if not online_nodes:
        console.print("[red]No online nodes available[/red]")
        return
    
    pull_to_all = Confirm.ask("Pull to all online nodes?", default=True)
    
    if pull_to_all:
        target_nodes = online_nodes
    else:
        console.print("\nAvailable nodes:")
        for i, node in enumerate(online_nodes, 1):
            console.print(f"  {i}. {node['name']} ({node['host']})")
        
        selection = Prompt.ask("\nSelect nodes (comma-separated numbers)")
        
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            target_nodes = [online_nodes[i] for i in indices if 0 <= i < len(online_nodes)]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection[/red]")
            return
    
    if not target_nodes:
        console.print("[yellow]No nodes selected[/yellow]")
        return
    
    skip_existing = Confirm.ask("Skip models that already exist?", default=True)
    
    # Pull models
    pull_models(model_names, target_nodes, skip_existing)


def main_menu(config: Dict[str, Any], cluster_state: Optional[List[Dict[str, Any]]] = None):
    """Main interactive menu."""
    
    nodes = config['ollama_instances']
    
    if cluster_state is None:
        # Initial scan
        console.print("\n[cyan]Performing initial cluster scan...[/cyan]")
        cluster_state = scan_cluster(nodes)
    
    while True:
        # Display dashboard
        console.clear()
        dashboard = create_dashboard(cluster_state)
        console.print(dashboard)
        
        # Menu
        console.print("\n[bold]Menu:[/bold]")
        console.print("  1 - Scan cluster")
        console.print("  2 - Pull models")
        console.print("  3 - Export graph")
        console.print("  4 - Refresh dashboard")
        console.print("  q - Quit")
        
        choice = Prompt.ask("\nSelect option", default="4")
        
        if choice == '1':
            console.print("\n[cyan]Scanning cluster...[/cyan]")
            cluster_state = scan_cluster(nodes)
            console.print("[green]✓[/green] Scan complete")
            Prompt.ask("\nPress Enter to continue")
        
        elif choice == '2':
            interactive_pull(cluster_state)
            # Rescan after pulling
            console.print("\n[cyan]Refreshing cluster state...[/cyan]")
            cluster_state = scan_cluster(nodes)
            Prompt.ask("\nPress Enter to continue")
        
        elif choice == '3':
            console.print("\n[bold cyan]Export Graph[/bold cyan]\n")
            console.print("  1 - Neo4j Cypher (.cypher)")
            console.print("  2 - JSON Graph (.json)")
            console.print("  3 - Both formats")
            
            export_choice = Prompt.ask("Select format", default="3")
            
            output_dir = Path.cwd()
            
            if export_choice in ['1', '3']:
                export_graph_cypher(cluster_state, output_dir)
            
            if export_choice in ['2', '3']:
                export_graph_json(cluster_state, output_dir)
            
            Prompt.ask("\nPress Enter to continue")
        
        elif choice == '4':
            continue  # Just refresh the display
        
        elif choice.lower() == 'q':
            console.print("\n[cyan]Goodbye![/cyan]")
            break
        
        else:
            console.print("[yellow]Invalid option[/yellow]")
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        description="Ollama Cluster Manager - Unified TUI"
    )
    parser.add_argument(
        '--vera-config',
        help='Path to vera_config.yaml (default: ./vera_config.yaml)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='Max concurrent workers for scanning (default: 8)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    try:
        # Load config
        config = load_vera_config(args.vera_config)
        
        # Start interactive menu
        main_menu(config)
    
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()