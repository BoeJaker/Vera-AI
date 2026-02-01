#!/usr/bin/env python3
"""
Ollama Model Synchronization Tool - Complete Edition

Full-featured model sync with:
- Parallel model pulls with retry logic and dynamic timeouts
- Custom model building from YAML configs and Jinja2 templates
- Auto-discovery of Vera config files
- Interactive configuration wizard
- Activity-based timeout monitoring for large models
- Connection pooling and progress tracking
"""

import os
import sys
import json
import yaml
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time
import re


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


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
    
    @staticmethod
    def calculate_timeout(model_name: str, base: int = 300) -> int:
        """Calculate timeout: base + 5min/GB (min 5min, max 2hr)"""
        size_gb = ModelSizeEstimator.estimate_size_gb(model_name)
        timeout = int(base + (size_gb * 300))
        return max(300, min(7200, timeout))


class ProgressTracker:
    """Thread-safe progress tracking with ETA"""
    
    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.current = 0
        self.description = description
        self.lock = Lock()
        self.start_time = time.time()
        self.successes = 0
        self.failures = 0
    
    def increment(self, success: bool = True):
        with self.lock:
            self.current += 1
            if success:
                self.successes += 1
            else:
                self.failures += 1
            self._print_progress()
    
    def _print_progress(self):
        elapsed = time.time() - self.start_time
        percent = (self.current / self.total) * 100 if self.total > 0 else 0
        bar_length = 40
        filled = int(bar_length * self.current / self.total) if self.total > 0 else 0
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # ETA calculation
        if self.current > 0:
            eta = int((elapsed / self.current) * (self.total - self.current))
            eta_str = f"ETA:{eta}s"
        else:
            eta_str = "ETA:--"
        
        print(f"\r{Colors.CYAN}{self.description}: [{bar}] {percent:.1f}% "
              f"({self.current}/{self.total}) "
              f"✓{self.successes} ✗{self.failures} "
              f"{int(elapsed)}s {eta_str}{Colors.END}", end='', flush=True)
        
        if self.current >= self.total:
            print()


class OllamaModelSync:
    """Synchronize custom Ollama models between hosts with full feature set"""
    
    def __init__(self, source_host: str = "localhost:11434", verbose: bool = False, 
                 vera_config: Optional[Dict] = None, max_workers: int = 4,
                 max_retries: int = 3):
        self.source_host = source_host
        self.source_url = f"http://{source_host}"
        self.verbose = verbose
        self.jinja_env = None
        self.vera_config = vera_config
        self.ollama_instances = []
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.log_lock = Lock()
        
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
            self._load_ollama_instances()
    
    def log(self, message: str, level: str = "info", force: bool = False):
        """Thread-safe colored logging output"""
        if not self.verbose and not force:
            if level not in ["error", "warning", "header", "success"]:
                return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "info": Colors.CYAN,
            "success": Colors.GREEN,
            "warning": Colors.YELLOW,
            "error": Colors.RED,
            "header": Colors.HEADER,
            "dim": Colors.DIM
        }
        color = colors.get(level, Colors.END)
        
        with self.log_lock:
            print(f"{color}[{timestamp}] {message}{Colors.END}")
    
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
    
    def _load_ollama_instances(self):
        """Load Ollama instances from Vera config"""
        try:
            instances = self.vera_config.get('ollama', {}).get('instances', [])
            
            for instance in instances:
                if not instance.get('enabled', True):
                    continue
                    
                api_url = instance.get('api_url', '')
                if api_url:
                    host_port = api_url.replace('http://', '').replace('https://', '')
                    self.ollama_instances.append({
                        'name': instance.get('name', 'unknown'),
                        'host': host_port,
                        'priority': instance.get('priority', 0),
                        'enabled': instance.get('enabled', True),
                        'max_concurrent': instance.get('max_concurrent', 1)
                    })
            
            if self.ollama_instances:
                self.log(f"Loaded {len(self.ollama_instances)} Ollama instances from Vera config", "success", force=True)
                if self.verbose:
                    for inst in self.ollama_instances:
                        self.log(f"  • {inst['name']}: {inst['host']} (priority: {inst['priority']})", "info")
        except Exception as e:
            self.log(f"Warning: Could not load Ollama instances from config: {e}", "warning", force=True)
    
    def get_enabled_instances(self, exclude_source: bool = True) -> List[str]:
        """Get list of enabled Ollama instance hosts"""
        hosts = []
        for inst in self.ollama_instances:
            if inst['enabled']:
                if exclude_source and inst['host'] == self.source_host:
                    continue
                hosts.append(inst['host'])
        return hosts
    
    def load_model_config(self, config_path: Path) -> Dict[str, Any]:
        """Load and validate model configuration from YAML"""
        self.log(f"Loading config: {config_path}", "info")
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        required = ['name', 'base_model']
        missing = [field for field in required if field not in config]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        return config
    
    def render_modelfile(self, config: Dict[str, Any], config_dir: Path) -> str:
        """Render Modelfile from config using Jinja2 template"""
        self.log(f"Rendering Modelfile for: {config['name']}", "info")
        
        self.setup_jinja_env(config_dir)
        
        system_prompt_config = config.get('system_prompt', {})
        template_file = system_prompt_config.get('template', 'prompt_template.j2')
        template_vars = system_prompt_config.get('variables', {})
        
        # Pre-load includes
        includes = config.get('includes', [])
        included_content = {}
        for include_path in includes:
            full_path = config_dir / include_path
            if full_path.exists():
                included_content[include_path] = full_path.read_text()
                if self.verbose:
                    self.log(f"  Loaded include: {include_path} ({len(included_content[include_path])} chars)", "info")
            else:
                self.log(f"  Warning: Include not found: {include_path}", "warning")
        
        template_vars['_includes'] = included_content
        
        # Render system prompt
        template_path = config_dir / template_file
        if template_path.exists():
            template = self.jinja_env.get_template(template_file)
            system_prompt = template.render(**template_vars)
        else:
            self.log(f"Template not found: {template_file}, using default", "warning")
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
    
    def check_ollama_connection(self, host: str) -> bool:
        """Check if Ollama is reachable on host"""
        try:
            url = f"http://{host}/api/tags"
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            if self.verbose:
                self.log(f"Connection failed to {host}: {e}", "error")
            return False
    
    def list_models(self, host: str) -> List[str]:
        """List models available on Ollama host"""
        try:
            url = f"http://{host}/api/tags"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            self.log(f"Failed to list models on {host}: {e}", "error")
            return []
    
    def build_model(self, name: str, modelfile: str) -> bool:
        """Build/create model on source Ollama host"""
        self.log(f"Building model: {name}", "header", force=True)
        
        modelfile_path = Path(f"/tmp/Modelfile.{name}.{os.getpid()}")
        modelfile_path.write_text(modelfile)
        
        try:
            cmd = ["ollama", "create", name, "-f", str(modelfile_path)]
            
            if self.verbose:
                self.log(f"Running: {' '.join(cmd)}", "info")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env={**os.environ, "OLLAMA_HOST": self.source_host}
            )
            
            if result.returncode == 0:
                self.log(f"✓ Model built successfully: {name}", "success", force=True)
                if self.verbose and result.stdout:
                    print(result.stdout)
                return True
            else:
                self.log(f"✗ Failed to build model: {name}", "error", force=True)
                if result.stderr:
                    print(result.stderr)
                return False
                
        except Exception as e:
            self.log(f"Error building model: {e}", "error", force=True)
            return False
        finally:
            if modelfile_path.exists():
                modelfile_path.unlink()
    
    def pull_model_to_host_with_retry(self, name: str, host: str, skip_existing: bool = False) -> Tuple[str, bool, str]:
        """Pull model with retry logic, dynamic timeout, and activity monitoring"""
        
        # Check if exists
        if skip_existing:
            existing_models = self.list_models(host)
            if name in existing_models or f"{name}:latest" in existing_models:
                self.log(f"⊙ Model already exists on {host}: {name}", "dim")
                return (host, True, "Already exists")
        
        # Calculate dynamic timeout
        timeout = ModelSizeEstimator.calculate_timeout(name)
        size_est = ModelSizeEstimator.estimate_size_gb(name)
        
        self.log(f"Pulling {name} to {host} (~{size_est:.1f}GB, timeout:{timeout}s)", "info")
        
        # Retry loop with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                wait = (2 ** (attempt - 1)) * 5
                self.log(f"Retry {attempt}/{self.max_retries} for {name} on {host} (wait:{wait}s)", "warning", force=True)
                time.sleep(wait)
            
            try:
                cmd = ["ollama", "pull", name]
                env = {**os.environ, "OLLAMA_HOST": host}
                
                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    bufsize=0
                )
                
                # Activity-based monitoring
                start_time = time.time()
                last_activity = start_time
                activity_timeout = 120  # 2 minutes no activity = stalled
                
                while process.poll() is None:
                    current_time = time.time()
                    
                    # Check total timeout
                    if current_time - start_time > timeout:
                        process.kill()
                        raise TimeoutError(f"Total timeout ({timeout}s) exceeded")
                    
                    # Check activity timeout
                    if current_time - last_activity > activity_timeout:
                        process.kill()
                        raise TimeoutError(f"No activity for {activity_timeout}s")
                    
                    # Monitor for activity
                    try:
                        if process.stdout:
                            import select
                            if select.select([process.stdout], [], [], 0.1)[0]:
                                chunk = process.stdout.read(1024)
                                if chunk:
                                    last_activity = current_time
                    except:
                        pass
                    
                    time.sleep(0.5)
                
                # Check result
                if process.returncode == 0:
                    self.log(f"✓ {name} pulled to {host} (attempt {attempt})", "success")
                    return (host, True, f"Success attempt {attempt}")
                else:
                    stderr = process.stderr.read().decode('utf-8', errors='ignore') if process.stderr else ""
                    error_msg = stderr[:200] if stderr else f"Exit code {process.returncode}"
                    
                    if attempt < self.max_retries:
                        self.log(f"✗ Attempt {attempt} failed: {error_msg[:50]}", "error", force=True)
                        continue
                    return (host, False, f"Failed: {error_msg}")
                    
            except TimeoutError as e:
                if attempt < self.max_retries:
                    self.log(f"✗ Timeout on attempt {attempt}: {e}", "error", force=True)
                    continue
                return (host, False, f"Timeout: {e}")
                
            except Exception as e:
                if attempt < self.max_retries:
                    self.log(f"✗ Error on attempt {attempt}: {e}", "error", force=True)
                    continue
                return (host, False, f"Exception: {e}")
        
        return (host, False, "Max retries exceeded")
    
    def pull_model_to_all_parallel(self, model_name: str, targets: List[str], 
                                   skip_existing: bool = True) -> Dict[str, Dict]:
        """Pull model to all target hosts in parallel with retry logic"""
        self.log(f"\n{'='*80}", "header", force=True)
        self.log(f"Pulling model to all instances (parallel): {model_name}", "header", force=True)
        
        size_est = ModelSizeEstimator.estimate_size_gb(model_name)
        timeout = ModelSizeEstimator.calculate_timeout(model_name)
        
        self.log(f"Est. size: {size_est:.1f}GB | Timeout/attempt: {timeout}s | Retries: {self.max_retries}", "info", force=True)
        self.log(f"{'='*80}", "header", force=True)
        
        results = {}
        
        # Connection check in parallel
        self.log(f"Checking connections to {len(targets)} instances...", "info", force=True)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            connection_futures = {
                executor.submit(self.check_ollama_connection, host): host 
                for host in targets
            }
            
            for future in as_completed(connection_futures):
                host = connection_futures[future]
                try:
                    connected = future.result()
                    if not connected:
                        self.log(f"Cannot connect to {host}", "error", force=True)
                        results[host] = {'success': False, 'message': 'Connection failed'}
                except Exception as e:
                    self.log(f"Error checking connection to {host}: {e}", "error", force=True)
                    results[host] = {'success': False, 'message': f'Connection error: {e}'}
        
        # Filter connected hosts
        connected_hosts = [host for host in targets if host not in results]
        
        if not connected_hosts:
            self.log("No hosts available for pulling", "error", force=True)
            return results
        
        self.log(f"Pulling to {len(connected_hosts)} connected instances...", "info", force=True)
        
        # Progress tracker
        progress = ProgressTracker(len(connected_hosts), f"Pulling {model_name}")
        
        # Pull in parallel with retry
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            pull_futures = {
                executor.submit(self.pull_model_to_host_with_retry, model_name, host, skip_existing): host 
                for host in connected_hosts
            }
            
            for future in as_completed(pull_futures):
                try:
                    host, success, message = future.result()
                    results[host] = {'success': success, 'message': message}
                    progress.increment(success)
                except Exception as e:
                    host = pull_futures[future]
                    self.log(f"Exception pulling to {host}: {e}", "error", force=True)
                    results[host] = {'success': False, 'message': f'Exception: {e}'}
                    progress.increment(False)
        
        return results
    
    def copy_model_direct(self, name: str, target_host: str) -> Tuple[str, bool]:
        """Copy model directly by recreating on target (thread-safe)"""
        self.log(f"Copying model to {target_host}", "info")
        
        try:
            # Get model info from source
            show_url = f"{self.source_url}/api/show"
            response = self.session.post(
                show_url,
                json={"name": name},
                timeout=30
            )
            response.raise_for_status()
            model_info = response.json()
            
            modelfile = model_info.get('modelfile', '')
            if not modelfile:
                self.log("No modelfile found in model info", "error", force=True)
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
                self.log(f"✓ Model copied to {target_host}", "success")
                return (target_host, True)
            else:
                self.log(f"✗ Failed to copy model to {target_host}", "error", force=True)
                if result.stderr:
                    with self.log_lock:
                        print(result.stderr)
                return (target_host, False)
                
        except Exception as e:
            self.log(f"Error copying model to {target_host}: {e}", "error", force=True)
            return (target_host, False)
    
    def sync_model_parallel(self, config_path: Path, target_hosts: List[str], 
                           rebuild: bool = False, verify: bool = True) -> bool:
        """Sync a single model to target hosts in parallel"""
        
        # Load configuration
        config = self.load_model_config(config_path)
        model_name = config['name']
        config_dir = config_path.parent
        
        # Check if model exists on source
        source_models = self.list_models(self.source_host)
        model_exists = model_name in source_models
        
        if model_exists and not rebuild:
            self.log(f"Model already exists on source: {model_name}", "info", force=True)
        else:
            # Render and build model
            modelfile = self.render_modelfile(config, config_dir)
            
            if self.verbose:
                self.log("Generated Modelfile:", "info", force=True)
                print("-" * 80)
                print(modelfile)
                print("-" * 80)
            
            if not self.build_model(model_name, modelfile):
                return False
        
        # Connection check
        self.log(f"Checking connections to {len(target_hosts)} instances...", "info", force=True)
        connected_hosts = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            connection_futures = {
                executor.submit(self.check_ollama_connection, host): host 
                for host in target_hosts
            }
            
            for future in as_completed(connection_futures):
                host = connection_futures[future]
                if future.result():
                    connected_hosts.append(host)
                else:
                    self.log(f"Cannot connect to {host}", "error", force=True)
        
        if not connected_hosts:
            return False
        
        # Sync in parallel
        self.log(f"Syncing to {len(connected_hosts)} instances...", "info", force=True)
        progress = ProgressTracker(len(connected_hosts), f"Syncing {model_name}")
        
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            copy_futures = {
                executor.submit(self.copy_model_direct, model_name, host): host 
                for host in connected_hosts
            }
            
            for future in as_completed(copy_futures):
                host, success = future.result()
                results[host] = success
                progress.increment(success)
        
        # Verify if requested
        if verify:
            self.log("Verifying models...", "info", force=True)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                verify_futures = {
                    executor.submit(self.verify_model, model_name, host): host 
                    for host in connected_hosts if results.get(host, False)
                }
                
                for future in as_completed(verify_futures):
                    if not future.result():
                        host = verify_futures[future]
                        results[host] = False
        
        return all(results.values())
    
    def verify_model(self, name: str, host: str) -> bool:
        """Verify model exists on host"""
        models = self.list_models(host)
        if name in models or f"{name}:latest" in models:
            self.log(f"✓ Model verified on {host}: {name}", "dim")
            return True
        else:
            self.log(f"✗ Model not found on {host}: {name}", "error", force=True)
            return False
    
    def sync_directory_parallel(self, config_dir: Path, target_hosts: List[str],
                                pattern: str = "*.yaml", rebuild: bool = False) -> Dict[str, bool]:
        """Sync all model configs in directory with parallel processing"""
        
        self.log(f"\nScanning directory: {config_dir}", "header", force=True)
        
        config_files = list(config_dir.glob(pattern))
        
        if not config_files:
            self.log(f"No config files found matching: {pattern}", "warning", force=True)
            return {}
        
        self.log(f"Found {len(config_files)} config(s)", "info", force=True)
        
        results = {}
        
        # Process configs sequentially (but each sync is parallel internally)
        for config_file in config_files:
            self.log(f"\n{'='*80}", "header", force=True)
            self.log(f"Processing: {config_file.name}", "header", force=True)
            self.log(f"{'='*80}", "header", force=True)
            
            try:
                success = self.sync_model_parallel(config_file, target_hosts, rebuild=rebuild)
                results[config_file.name] = success
            except Exception as e:
                self.log(f"Error processing {config_file.name}: {e}", "error", force=True)
                results[config_file.name] = False
        
        return results


def find_vera_config() -> Optional[Path]:
    """Auto-discover Vera config file in common locations"""
    search_paths = [
        Path.cwd() / "vera_config.yaml",
        Path.cwd() / "config" / "vera_config.yaml",
        Path.home() / ".config" / "vera" / "vera_config.yaml",
        Path("/etc/vera/vera_config.yaml"),
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None


def interactive_config_setup() -> Tuple[Optional[Path], List[str]]:
    """Interactive wizard for configuration"""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}Ollama Model Sync - Configuration Setup{Colors.END}")
    print(f"{Colors.HEADER}{'='*80}{Colors.END}\n")
    
    # Try to find Vera config
    vera_config_path = find_vera_config()
    
    if vera_config_path:
        print(f"{Colors.GREEN}✓ Found Vera config: {vera_config_path}{Colors.END}")
        use_vera = input(f"{Colors.CYAN}Use this config? [Y/n]: {Colors.END}").strip().lower()
        
        if use_vera != 'n':
            return (vera_config_path, [])
    
    print(f"\n{Colors.YELLOW}No Vera config found or not using auto-detected config.{Colors.END}")
    print(f"{Colors.CYAN}Please provide configuration:{Colors.END}\n")
    
    # Ask for Vera config path
    config_input = input(f"{Colors.CYAN}Path to Vera config (or press Enter to skip): {Colors.END}").strip()
    
    if config_input:
        config_path = Path(config_input)
        if config_path.exists():
            return (config_path, [])
        else:
            print(f"{Colors.RED}✗ Config file not found: {config_path}{Colors.END}")
    
    # Manual target specification
    print(f"\n{Colors.CYAN}Enter target Ollama hosts (one per line, empty line to finish):{Colors.END}")
    print(f"{Colors.DIM}Format: hostname:port (e.g., 192.168.0.250:11434){Colors.END}")
    
    targets = []
    while True:
        target = input(f"{Colors.CYAN}Target {len(targets) + 1}: {Colors.END}").strip()
        if not target:
            break
        targets.append(target)
    
    if not targets:
        print(f"{Colors.RED}✗ No targets specified. Exiting.{Colors.END}")
        sys.exit(1)
    
    return (None, targets)


def main():
    parser = argparse.ArgumentParser(
        description="Sync custom Ollama models - Complete Edition with Retry & Dynamic Timeouts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pull large model with auto-scaled timeout and retries
  %(prog)s --pull qwen2.5:72b --vera-config vera_config.yaml --sync-all
  
  # Pull with custom retry count
  %(prog)s --pull llama3.2:latest --vera-config vera_config.yaml --sync-all --retries 5
  
  # Sync custom models from directory
  %(prog)s -d ./models --vera-config vera_config.yaml --sync-all --workers 8
  
  # Interactive mode
  %(prog)s --interactive
        """
    )
    
    # Model pulling options
    pull_group = parser.add_argument_group('Model Pulling')
    pull_group.add_argument(
        '--pull',
        nargs='+',
        metavar='MODEL',
        help='Pull model(s) from Ollama registry to all instances'
    )
    
    pull_group.add_argument(
        '--force-pull',
        action='store_true',
        help='Force pull even if model exists'
    )
    
    # Model syncing options
    sync_group = parser.add_argument_group('Custom Model Syncing')
    sync_group.add_argument(
        '-c', '--config',
        type=Path,
        help='Path to model YAML config file'
    )
    
    sync_group.add_argument(
        '-d', '--directory',
        type=Path,
        help='Directory containing model configs'
    )
    
    sync_group.add_argument(
        '-p', '--pattern',
        default='*.yaml',
        help='File pattern for directory mode (default: *.yaml)'
    )
    
    sync_group.add_argument(
        '--rebuild',
        action='store_true',
        help='Rebuild model even if it exists'
    )
    
    # Target configuration
    target_group = parser.add_argument_group('Target Configuration')
    target_group.add_argument(
        '-t', '--targets',
        nargs='+',
        help='Target Ollama hosts (host:port)'
    )
    
    target_group.add_argument(
        '-s', '--source',
        default='localhost:11434',
        help='Source Ollama host (default: localhost:11434)'
    )
    
    target_group.add_argument(
        '--vera-config',
        type=Path,
        help='Path to Vera config YAML file'
    )
    
    target_group.add_argument(
        '--sync-all',
        action='store_true',
        help='Sync to all instances in Vera config'
    )
    
    target_group.add_argument(
        '--exclude-source',
        action='store_true',
        help='Exclude source host from sync targets'
    )
    
    target_group.add_argument(
        '--priority-filter',
        type=int,
        help='Only sync to instances with priority >= this value'
    )
    
    # Performance options
    perf_group = parser.add_argument_group('Performance & Reliability')
    perf_group.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Max parallel workers (default: 4)'
    )
    
    perf_group.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Max retry attempts per model (default: 3)'
    )
    
    # General options
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip verification after sync'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive configuration mode'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Interactive mode if no operation specified
    if args.interactive or (not args.pull and not args.config and not args.directory):
        if not args.pull and not args.config and not args.directory:
            print(f"{Colors.YELLOW}No operation specified, entering interactive mode...{Colors.END}\n")
        
        vera_config_path, manual_targets = interactive_config_setup()
        
        if vera_config_path:
            args.vera_config = vera_config_path
            args.sync_all = True
        elif manual_targets:
            args.targets = manual_targets
        
        # If still no operation, ask what to do
        if not args.pull and not args.config and not args.directory:
            print(f"\n{Colors.CYAN}What would you like to do?{Colors.END}")
            print(f"  1. Pull models from Ollama registry")
            print(f"  2. Sync custom models from config")
            print(f"  3. Sync all configs in directory")
            
            choice = input(f"{Colors.CYAN}Choice [1-3]: {Colors.END}").strip()
            
            if choice == '1':
                models = input(f"{Colors.CYAN}Model names (space-separated): {Colors.END}").strip().split()
                args.pull = models if models else None
            elif choice == '2':
                config_path = input(f"{Colors.CYAN}Path to config file: {Colors.END}").strip()
                args.config = Path(config_path) if config_path else None
            elif choice == '3':
                dir_path = input(f"{Colors.CYAN}Path to config directory: {Colors.END}").strip()
                args.directory = Path(dir_path) if dir_path else None
    
    # Validate arguments
    if not args.pull and not args.config and not args.directory:
        parser.error("Either --pull, --config, or --directory must be specified")
    
    if args.config and args.directory:
        parser.error("Cannot specify both --config and --directory")
    
    # Load Vera config
    vera_config = None
    if args.vera_config:
        if not args.vera_config.exists():
            print(f"{Colors.RED}✗ Vera config file not found: {args.vera_config}{Colors.END}")
            return 1
        
        print(f"{Colors.CYAN}Loading Vera config: {args.vera_config}{Colors.END}")
        with open(args.vera_config, 'r') as f:
            vera_config = yaml.safe_load(f)
    
    # Determine targets
    targets = args.targets or []
    
    if args.sync_all and vera_config:
        instances = vera_config.get('ollama', {}).get('instances', [])
        for inst in instances:
            if not inst.get('enabled', True):
                continue
            
            if args.priority_filter is not None:
                if inst.get('priority', 0) < args.priority_filter:
                    continue
            
            api_url = inst.get('api_url', '')
            if api_url:
                host_port = api_url.replace('http://', '').replace('https://', '')
                
                if args.exclude_source and host_port == args.source:
                    continue
                    
                targets.append(host_port)
        
        if targets:
            print(f"{Colors.GREEN}Found {len(targets)} target(s) from Vera config:{Colors.END}")
            for t in targets:
                print(f"  • {t}")
        else:
            print(f"{Colors.YELLOW}No targets found in Vera config{Colors.END}")
            return 1
    
    elif not targets:
        print(f"{Colors.RED}✗ No targets specified{Colors.END}")
        return 1
    
    # Initialize syncer
    syncer = OllamaModelSync(
        source_host=args.source,
        verbose=args.verbose,
        vera_config=vera_config,
        max_workers=args.workers,
        max_retries=args.retries
    )
    
    # Check source connection (only needed for custom model sync)
    if (args.config or args.directory) and not syncer.check_ollama_connection(args.source):
        print(f"{Colors.RED}Cannot connect to source: {args.source}{Colors.END}")
        return 1
    
    try:
        # Handle model pulling
        if args.pull:
            skip_existing = not args.force_pull
            all_results = {}
            
            for model_name in args.pull:
                results = syncer.pull_model_to_all_parallel(
                    model_name,
                    targets,
                    skip_existing=skip_existing
                )
                all_results[model_name] = results
            
            # Print summary
            print(f"\n{Colors.HEADER}{'='*80}{Colors.END}")
            print(f"{Colors.HEADER}PULL SUMMARY{Colors.END}")
            print(f"{Colors.HEADER}{'='*80}{Colors.END}")
            
            for model_name, results in all_results.items():
                print(f"\n{Colors.BOLD}{model_name}:{Colors.END}")
                total = len(results)
                successful = sum(1 for v in results.values() if v['success'])
                failed = total - successful
                
                for host, result in results.items():
                    if result['success']:
                        status = f"{Colors.GREEN}✓{Colors.END}"
                        message = f"[{result['message']}]"
                    else:
                        status = f"{Colors.RED}✗{Colors.END}"
                        message = f"[{Colors.RED}{result['message']}{Colors.END}]"
                    
                    print(f"  {status} {host:30} {message}")
                
                print(f"\n  {Colors.CYAN}Total: {total} | Success: {successful} | Failed: {failed}{Colors.END}")
                
                if failed > 0:
                    print(f"  {Colors.YELLOW}💡 Try: --retries {args.retries + 2} or --workers {max(1, args.workers - 1)}{Colors.END}")
            
            return 0 if all(all(r['success'] for r in res.values()) for res in all_results.values()) else 1
        
        # Handle custom model sync
        elif args.config:
            success = syncer.sync_model_parallel(
                args.config,
                targets,
                rebuild=args.rebuild,
                verify=not args.no_verify
            )
            return 0 if success else 1
        
        else:
            # Sync directory
            results = syncer.sync_directory_parallel(
                args.directory,
                targets,
                pattern=args.pattern,
                rebuild=args.rebuild
            )
            
            # Print summary
            print(f"\n{Colors.HEADER}{'='*80}{Colors.END}")
            print(f"{Colors.HEADER}SYNC SUMMARY{Colors.END}")
            print(f"{Colors.HEADER}{'='*80}{Colors.END}")
            
            total = len(results)
            successful = sum(1 for v in results.values() if v)
            failed = total - successful
            
            for config, success in results.items():
                status = f"{Colors.GREEN}✓{Colors.END}" if success else f"{Colors.RED}✗{Colors.END}"
                print(f"{status} {config}")
            
            print(f"\n{Colors.CYAN}Total: {total} | Success: {successful} | Failed: {failed}{Colors.END}")
            
            return 0 if failed == 0 else 1
    
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        return 130
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())