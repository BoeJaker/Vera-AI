#!/usr/bin/env python3
# Vera/Ollama/multi_instance_manager.py

"""
Multi-Instance Ollama Manager with Load Balancing
Distributes requests across multiple Ollama instances
"""

import threading
import time
import queue
import requests
import json
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass, field
from collections import defaultdict

# LangChain imports for proper LLM compatibility
from langchain.llms.base import LLM
from langchain_core.outputs import GenerationChunk
from pydantic import Field

try:
    from Vera.Logging.logging import LogContext
    from Vera.Configuration.config_manager import OllamaConfig, OllamaInstanceConfig
except ImportError:
    from Logging.logging import LogContext
    from Configuration.config_manager import OllamaConfig, OllamaInstanceConfig

from Vera.Ollama.manager import ThoughtCapture  # Reuse the existing implementation

@dataclass
class InstanceStats:
    """Statistics for an Ollama instance"""
    name: str
    active_requests: int = 0
    total_requests: int = 0
    total_failures: int = 0
    total_duration: float = 0.0
    last_request_time: float = 0.0
    is_healthy: bool = True
    last_health_check: float = 0.0


class OllamaInstancePool:
    """
    Manages multiple Ollama instances with load balancing
    """
    
    def __init__(self, config: OllamaConfig, logger=None):
        self.config = config
        self.logger = logger
        
        # Instance management
        self.instances: Dict[str, OllamaInstanceConfig] = {}
        self.stats: Dict[str, InstanceStats] = {}
        self.locks: Dict[str, threading.Lock] = {}
        
        # Request queue
        self.request_queue = queue.Queue(maxsize=config.max_queue_size)
        self.queue_enabled = config.enable_request_queue
        
        # Health monitoring
        self.health_check_interval = 30.0  # seconds
        self.health_check_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Initialize instances
        self._initialize_instances()
        
        # Start health monitoring
        self.start()
        
        if self.logger:
            self.logger.success(f"Initialized {len(self.instances)} Ollama instances")

    def _initialize_instances(self):
        """Initialize all configured instances"""
        for instance_config in self.config.instances:
            # Safety check - convert dict if needed
            if isinstance(instance_config, dict):
                from Vera.Configuration.config_manager import OllamaInstanceConfig
                instance_config = OllamaInstanceConfig.from_dict(instance_config)
            
            if not instance_config.enabled:
                continue
            
            self.instances[instance_config.name] = instance_config
            self.stats[instance_config.name] = InstanceStats(name=instance_config.name)
            self.locks[instance_config.name] = threading.Lock()
            
            if self.logger:
                self.logger.debug(
                    f"Configured instance: {instance_config.name} @ {instance_config.api_url}"
                )
                
    def start(self):
        """Start health monitoring"""
        if self.running:
            return
        
        self.running = True
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self.health_check_thread.start()
        
        if self.logger:
            self.logger.debug("Health monitoring started")
    
    def stop(self):
        """Stop health monitoring"""
        self.running = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5.0)
    
    def _health_check_loop(self):
        """Background health check loop"""
        while self.running:
            for name in self.instances.keys():
                self._check_instance_health(name)
            
            time.sleep(self.health_check_interval)
    
    def _check_instance_health(self, name: str):
        """Check health of a single instance"""
        instance = self.instances[name]
        stats = self.stats[name]
        
        try:
            response = requests.get(
                f"{instance.api_url}/api/tags",
                timeout=5
            )
            
            was_unhealthy = not stats.is_healthy
            stats.is_healthy = response.status_code == 200
            stats.last_health_check = time.time()
            
            if was_unhealthy and stats.is_healthy:
                if self.logger:
                    self.logger.success(f"Instance {name} recovered")
            
        except Exception as e:
            was_healthy = stats.is_healthy
            stats.is_healthy = False
            stats.last_health_check = time.time()
            
            if was_healthy:
                if self.logger:
                    self.logger.warning(f"Instance {name} unhealthy: {e}")
    
    def get_best_instance(self, allowed_instances: Optional[List[str]] = None) -> Optional[str]:
        """
        Select best instance based on load balancing strategy
        
        Args:
            allowed_instances: If provided, only select from these instances
        """
        strategy = self.config.load_balance_strategy
        
        # Filter healthy instances
        healthy = [
            name for name, stats in self.stats.items()
            if stats.is_healthy
        ]
        
        # Further filter by allowed instances if specified
        if allowed_instances is not None:
            healthy = [name for name in healthy if name in allowed_instances]
        
        if not healthy:
            if self.logger:
                filter_msg = f" (filtered to: {allowed_instances})" if allowed_instances else ""
                self.logger.error(f"No healthy Ollama instances available{filter_msg}!")
            return None
        
        if strategy == "round_robin":
            return self._round_robin_select(healthy)
        
        elif strategy == "least_loaded":
            return self._least_loaded_select(healthy)
        
        elif strategy == "priority":
            return self._priority_select(healthy)
        
        else:
            return healthy[0]
    
    def _round_robin_select(self, healthy: List[str]) -> str:
        """Round-robin selection"""
        if not hasattr(self, '_round_robin_index'):
            self._round_robin_index = 0
        
        selected = healthy[self._round_robin_index % len(healthy)]
        self._round_robin_index += 1
        
        return selected
    
    def _least_loaded_select(self, healthy: List[str]) -> str:
        """Select instance with least active requests"""
        def load_score(name: str) -> tuple:
            instance = self.instances[name]
            stats = self.stats[name]
            
            # Calculate load (active / max)
            load = stats.active_requests / instance.max_concurrent
            
            # Return (load, -priority) for sorting
            return (load, -instance.priority)
        
        return min(healthy, key=load_score)
    
    def _priority_select(self, healthy: List[str]) -> str:
        """Select highest priority instance with capacity"""
        available = [
            name for name in healthy
            if self.stats[name].active_requests < self.instances[name].max_concurrent
        ]
        
        if not available:
            # All at capacity, pick highest priority
            return max(healthy, key=lambda n: self.instances[n].priority)
        
        return max(available, key=lambda n: self.instances[n].priority)
    
    def acquire_instance(
        self, 
        timeout: float = 30.0,
        allowed_instances: Optional[List[str]] = None
    ) -> Optional[tuple]:
        """
        Acquire an instance for a request
        
        Args:
            timeout: How long to wait for an available instance
            allowed_instances: If provided, only acquire from these instances
        
        Returns: (instance_name, instance_config, release_func) or None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            instance_name = self.get_best_instance(allowed_instances)
            
            if not instance_name:
                time.sleep(0.5)
                continue
            
            instance = self.instances[instance_name]
            stats = self.stats[instance_name]
            lock = self.locks[instance_name]
            
            # Try to acquire
            with lock:
                if stats.active_requests < instance.max_concurrent:
                    stats.active_requests += 1
                    stats.total_requests += 1
                    stats.last_request_time = time.time()
                    
                    if self.logger:
                        self.logger.trace(
                            f"Acquired {instance_name}: {stats.active_requests}/{instance.max_concurrent} active"
                        )
                    
                    # Create release function
                    def release():
                        with lock:
                            stats.active_requests = max(0, stats.active_requests - 1)
                            if self.logger:
                                self.logger.trace(
                                    f"Released {instance_name}: {stats.active_requests}/{instance.max_concurrent} active"
                                )
                    
                    return (instance_name, instance, release)
            
            # No capacity, wait a bit
            time.sleep(0.1)
        
        # Timeout
        if self.logger:
            filter_msg = f" (filtered to: {allowed_instances})" if allowed_instances else ""
            self.logger.warning(f"Failed to acquire instance within {timeout}s{filter_msg}")
        
        return None
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all instances"""
        result = {}
        
        for name, stats in self.stats.items():
            instance = self.instances[name]
            
            result[name] = {
                "api_url": instance.api_url,
                "priority": instance.priority,
                "max_concurrent": instance.max_concurrent,
                "active_requests": stats.active_requests,
                "total_requests": stats.total_requests,
                "total_failures": stats.total_failures,
                "avg_duration": stats.total_duration / max(stats.total_requests, 1),
                "is_healthy": stats.is_healthy,
                "last_health_check": stats.last_health_check
            }
        
        return result


class MultiInstanceOllamaManager:
    """Ollama manager that uses multiple instances with load balancing"""
    
    def __init__(self, config: OllamaConfig, thought_callback=None, logger=None):
        self.config = config
        self.logger = logger
        self.thought_callback = thought_callback
        
        # Initialize instance pool
        self.pool = OllamaInstancePool(config, logger)
        
        # Model metadata cache
        self.model_metadata_cache: Dict[str, Any] = {}
        
        # Model location cache (instance_name -> set of model names)
        self._model_location_cache: Dict[str, set] = {}
        self._model_location_cache_time: float = 0
        self._model_location_cache_ttl: float = 300  # 5 minutes
        
        # Connection tested flag
        self.connection_tested = False
        
        if self.logger:
            self.logger.success("Multi-instance Ollama manager initialized")
    
    def _refresh_model_location_cache(self):
        """Refresh the cache of which models are on which instances"""
        current_time = time.time()
        
        # Check if cache is still valid
        if current_time - self._model_location_cache_time < self._model_location_cache_ttl:
            return
        
        if self.logger:
            self.logger.debug("Refreshing model location cache...")
        
        self._model_location_cache = {}
        
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            
            try:
                response = requests.get(
                    f"{instance.api_url}/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    
                    # Store model names for this instance
                    self._model_location_cache[name] = {
                        m.get("name", m.get("model", ""))
                        for m in models
                    }
            
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"Failed to cache models from {name}: {e}")
                continue
        
        self._model_location_cache_time = current_time
        
        if self.logger:
            total_models = sum(len(models) for models in self._model_location_cache.values())
            self.logger.debug(f"Model location cache refreshed: {total_models} models across {len(self._model_location_cache)} instances")
    
    def find_instances_with_model(self, model: str, use_cache: bool = True) -> List[str]:
        """
        Find which instances have a specific model
        Returns list of instance names, sorted by priority (highest first)
        
        Args:
            model: Model name to find (automatically adds :latest if no tag specified)
            use_cache: Use cached model locations (faster, may be stale)
        """
        # Normalize model name - add :latest if no tag specified
        model_to_find = model if ':' in model else f"{model}:latest"
        
        if self.logger:
            if model != model_to_find:
                self.logger.debug(f"Model name normalized: '{model}' → '{model_to_find}'")
        
        if use_cache:
            self._refresh_model_location_cache()
            
            instances_with_model = [
                name for name, models in self._model_location_cache.items()
                if model_to_find in models and self.pool.stats[name].is_healthy
            ]
        else:
            # Direct check (slower but always current)
            instances_with_model = []
            
            for name, instance in self.pool.instances.items():
                if not self.pool.stats[name].is_healthy:
                    continue
                
                try:
                    response = requests.get(
                        f"{instance.api_url}/api/tags",
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        models = data.get("models", [])
                        
                        # Check if this instance has the model
                        model_names = [
                            m.get("name", m.get("model", ""))
                            for m in models
                        ]
                        
                        if model_to_find in model_names:
                            instances_with_model.append(name)
                            if self.logger:
                                self.logger.debug(f"Instance {name} has model {model_to_find}")
                
                except Exception as e:
                    if self.logger:
                        self.logger.debug(f"Could not check {name} for model {model_to_find}: {e}")
                    continue
        
        # Sort by priority (highest first)
        instances_with_model.sort(
            key=lambda name: self.pool.instances[name].priority,
            reverse=True
        )
        
        return instances_with_model
    
    def test_connection(self) -> bool:
        """Test connection to all instances"""
        if self.connection_tested:
            return True
        
        healthy_count = 0
        
        for name, instance in self.pool.instances.items():
            try:
                response = requests.get(
                    f"{instance.api_url}/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    healthy_count += 1
                    self.pool.stats[name].is_healthy = True
                    
                    if self.logger:
                        self.logger.success(
                            f"Instance {name} connected: {instance.api_url}"
                        )
                else:
                    self.pool.stats[name].is_healthy = False
                    if self.logger:
                        self.logger.warning(
                            f"Instance {name} returned status {response.status_code}"
                        )
            
            except Exception as e:
                self.pool.stats[name].is_healthy = False
                if self.logger:
                    self.logger.warning(
                        f"Instance {name} connection failed: {e}"
                    )
        
        self.connection_tested = healthy_count > 0
        
        if self.logger:
            self.logger.info(
                f"Connection test: {healthy_count}/{len(self.pool.instances)} instances healthy"
            )
        
        return self.connection_tested
    
    def list_models(self) -> List[Dict]:
        """
        List models using API ONLY - returns plain dicts
        """
        if not self.connection_tested:
            self.test_connection()
        
        if self.logger:
            self.logger.debug("Listing models via API")
        
        # Try to get models from any healthy instance
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            
            try:
                response = requests.get(
                    f"{instance.api_url}/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models_data = data.get("models", [])
                    
                    # Convert to simple dict format
                    model_list = []
                    for m in models_data:
                        # Extract just the name/model field
                        model_name = m.get("name") or m.get("model", "unknown")
                        
                        model_list.append({
                            "model": model_name,
                            "name": model_name,  # For compatibility
                            "size": m.get("size", 0),
                            "modified_at": m.get("modified_at", ""),
                        })
                    
                    if self.logger:
                        self.logger.success(
                            f"Found {len(model_list)} models from {name}"
                        )
                    
                    return model_list
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to list models from {name}: {e}")
                continue
        
        # No healthy instances
        if self.logger:
            self.logger.error("No healthy instances available to list models")
        
        return []
    
    def get_model_metadata(self, model_name: str, force_refresh: bool = False):
        """Get model metadata via API ONLY"""
        if not force_refresh and model_name in self.model_metadata_cache:
            return self.model_metadata_cache[model_name]
        
        if self.logger:
            self.logger.debug(f"Fetching metadata for {model_name}")
        
        # Try each healthy instance
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            
            try:
                response = requests.post(
                    f"{instance.api_url}/api/show",
                    json={"name": model_name},
                    timeout=10
                )
                
                if response.status_code == 200:
                    metadata = response.json()
                    
                    # Cache it
                    self.model_metadata_cache[model_name] = metadata
                    
                    if self.logger:
                        self.logger.success(f"Got metadata for {model_name} from {name}")
                    
                    return metadata
            
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"Failed to get metadata from {name}: {e}")
                continue
        
        if self.logger:
            self.logger.warning(f"Could not fetch metadata for {model_name}")
        
        return {}
    
    def pull_model(self, model_name: str, stream: bool = True) -> bool:
        """Pull model via API ONLY"""
        if self.logger:
            self.logger.info(f"Pulling model: {model_name}")
        
        # Use first healthy instance
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            
            try:
                response = requests.post(
                    f"{instance.api_url}/api/pull",
                    json={"name": model_name, "stream": stream},
                    timeout=300 if not stream else None,
                    stream=stream
                )
                
                if stream:
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                status = data.get('status', '')
                                
                                if 'total' in data and 'completed' in data:
                                    pct = int((data['completed'] / data['total']) * 100)
                                    if self.logger and pct % 10 == 0:
                                        self.logger.info(f"Pull progress: {pct}%")
                            except:
                                pass
                
                if response.status_code == 200:
                    if self.logger:
                        self.logger.success(f"Model pulled: {model_name}")
                    
                    # Invalidate model location cache
                    self._model_location_cache_time = 0
                    
                    return True
            
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to pull model from {name}: {e}")
                continue
        
        return False

    def create_llm(self, model: str, temperature: float = 0.7, **kwargs):
        """Create LLM that uses the instance pool - API ONLY with intelligent routing"""
        # Normalize model name - add :latest if no tag specified
        model_normalized = model if ':' in model else f"{model}:latest"
        
        if self.logger:
            if model != model_normalized:
                self.logger.debug(f"Model name normalized: '{model}' → '{model_normalized}'")
            self.logger.info(f"Creating LLM: {model_normalized} (temp={temperature})")
        
        # Find instances that have this model
        instances_with_model = self.find_instances_with_model(model_normalized, use_cache=True)
        
        if not instances_with_model:
            # Model not found on any instance - try without cache to be sure
            if self.logger:
                self.logger.debug("Model not in cache, checking instances directly...")
            
            instances_with_model = self.find_instances_with_model(model_normalized, use_cache=False)
            
            if not instances_with_model:
                # Model truly not found - try to suggest alternatives
                all_models = self.list_models()
                available_model_names = list(set(
                    m.get("model", m.get("name", ""))
                    for m in all_models
                ))
                
                from difflib import get_close_matches
                suggestions = get_close_matches(model_normalized, available_model_names, n=3, cutoff=0.6)
                
                error_msg = f"Model '{model_normalized}' not found on any healthy Ollama instance."
                if suggestions:
                    error_msg += f" Did you mean: {', '.join(suggestions)}?"
                else:
                    available_preview = sorted(available_model_names)[:10]
                    if len(available_model_names) > 10:
                        error_msg += f" Available models (showing {len(available_preview)} of {len(available_model_names)}): {', '.join(available_preview)}"
                    else:
                        error_msg += f" Available models: {', '.join(available_preview)}"
                
                if self.logger:
                    self.logger.error(error_msg)
                
                raise ValueError(error_msg)
        
        # Log which instances have the model
        if self.logger:
            self.logger.success(
                f"Model '{model_normalized}' available on {len(instances_with_model)} instance(s): "
                f"{', '.join(instances_with_model)}"
            )
        
        # Get model metadata if available
        metadata = {}
        try:
            metadata = self.get_model_metadata(model_normalized)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"Could not get metadata for {model_normalized}: {e}")
        
        # Extract known parameters
        top_k = kwargs.pop('top_k', 40)
        top_p = kwargs.pop('top_p', 0.9)
        num_predict = kwargs.pop('num_predict', -1)
        max_retries = kwargs.pop('max_retries', 2)
        
        # Create pooled LLM with proper field assignment (use NORMALIZED model name)
        llm = PooledOllamaLLM(
            model=model_normalized,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            num_predict=num_predict,
            max_retries=max_retries
        )
        
        # Set non-Pydantic fields after creation
        llm.pool = self.pool
        llm.timeout = self.config.timeout
        llm.thought_callback = self.thought_callback
        
        # CRITICAL FIX: Create a NEW ThoughtCapture instance for this LLM
        # Each LLM gets its own capture instance to avoid interference between concurrent requests
        # But they all share the same callback function for unified thought handling
        llm.thought_capture = ThoughtCapture(
            enabled=getattr(self.config, 'enable_thought_capture', True),
            callback=self.thought_callback,  # Shared callback
            logger=self.logger
        )
        
        llm.model_metadata = metadata
        llm.logger = self.logger
        llm.extra_kwargs = kwargs
        
        # IMPORTANT: Restrict this LLM to only use instances that have the model
        llm.allowed_instances = instances_with_model
        
        if self.logger:
            self.logger.info(
                f"LLM will route to instances (by priority): {', '.join(instances_with_model)}"
            )
        
        return llm
    
    def create_embeddings(self, model: str, **kwargs):
        """Create embeddings using API ONLY"""
        # Use highest priority healthy instance
        best_instance = None
        best_priority = -1
        
        for name, instance in self.pool.instances.items():
            if self.pool.stats[name].is_healthy and instance.priority > best_priority:
                best_instance = instance
                best_priority = instance.priority
        
        if not best_instance:
            raise RuntimeError("No healthy instances available for embeddings")
        
        from langchain_community.embeddings import OllamaEmbeddings
        
        if self.logger:
            self.logger.info(
                f"Creating embeddings with {model} via {best_instance.api_url}"
            )
        
        return OllamaEmbeddings(
            model=model,
            base_url=best_instance.api_url,
            **kwargs
        )
    
    def get_pool_stats(self) -> Dict:
        """Get statistics for all instances"""
        return self.pool.get_stats()
    
    def print_model_info(self, model_name: str):
        """Print model information via API"""
        metadata = self.get_model_metadata(model_name)
        
        if not metadata:
            if self.logger:
                self.logger.error(f"No metadata available for {model_name}")
            return
        
        if self.logger:
            self.logger.info("=" * 60)
            self.logger.info(f"Model: {model_name}")
            self.logger.info("=" * 60)
            
            details = metadata.get('details', {})
            if details:
                self.logger.info(f"Family:       {details.get('family', 'Unknown')}")
                self.logger.info(f"Parameters:   {details.get('parameter_size', 'Unknown')}")
                self.logger.info(f"Quantization: {details.get('quantization_level', 'Unknown')}")
            
            model_info = metadata.get('model_info', {})
            if model_info:
                ctx_len = model_info.get('context_length') or model_info.get('n_ctx', 'Unknown')
                self.logger.info(f"Context:      {ctx_len} tokens")
            
            self.logger.info("=" * 60)

    def list_models_by_instance(self) -> Dict[str, List[Dict]]:
        """Get models from each instance separately"""
        models_by_instance = {}
        
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                if self.logger:
                    self.logger.warning(f"Skipping unhealthy instance: {name}")
                continue
            
            try:
                response = requests.get(
                    f"{instance.api_url}/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models_data = data.get("models", [])
                    
                    models_by_instance[name] = [
                        {
                            "name": m.get("name") or m.get("model", "unknown"),
                            "size": m.get("size", 0),
                            "modified_at": m.get("modified_at", ""),
                            "digest": m.get("digest", ""),
                            "details": m.get("details", {})
                        }
                        for m in models_data
                    ]
                    
                    if self.logger:
                        self.logger.info(
                            f"Instance {name}: {len(models_by_instance[name])} models"
                        )
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to list models from {name}: {e}")
                models_by_instance[name] = []
        
        return models_by_instance


    def compare_instances(self) -> Dict[str, Any]:
        """Compare models across instances"""
        models_by_instance = self.list_models_by_instance()
        
        if len(models_by_instance) < 2:
            return {
                "error": "Need at least 2 healthy instances to compare",
                "instances": list(models_by_instance.keys())
            }
        
        # Get all unique model names
        all_models = set()
        for models in models_by_instance.values():
            all_models.update(m["name"] for m in models)
        
        # Build comparison
        comparison = {
            "instances": list(models_by_instance.keys()),
            "total_unique_models": len(all_models),
            "models": {}
        }
        
        for model_name in sorted(all_models):
            comparison["models"][model_name] = {
                instance_name: any(m["name"] == model_name for m in models)
                for instance_name, models in models_by_instance.items()
            }
        
        # Find missing models per instance
        comparison["missing_by_instance"] = {}
        for instance_name in models_by_instance.keys():
            instance_models = {m["name"] for m in models_by_instance[instance_name]}
            missing = all_models - instance_models
            comparison["missing_by_instance"][instance_name] = sorted(missing)
        
        if self.logger:
            self.logger.info("Model comparison complete:")
            for instance, missing in comparison["missing_by_instance"].items():
                if missing:
                    self.logger.warning(f"  {instance} missing {len(missing)} models: {missing[:5]}")
                else:
                    self.logger.success(f"  {instance} has all models")
        
        return comparison

    
    def analyze_model_dependencies(self, model_name: str, instance_name: str) -> Dict[str, Any]:
        """
        Analyze a model's dependencies (base models, files, etc.)
        Useful for debugging copy failures
        """
        if instance_name not in self.pool.instances:
            return {"error": f"Instance '{instance_name}' not found"}
        
        instance = self.pool.instances[instance_name]
        
        try:
            # Get model info
            response = requests.post(
                f"{instance.api_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            
            if response.status_code != 200:
                return {"error": f"Model '{model_name}' not found on {instance_name}"}
            
            metadata = response.json()
            modelfile = metadata.get("modelfile", "")
            
            # Parse dependencies
            dependencies = {
                "base_model": None,
                "adapters": [],
                "system_prompt": None,
                "parameters": {},
                "template": None
            }
            
            for line in modelfile.split('\n'):
                line = line.strip()
                
                if line.upper().startswith('FROM '):
                    dependencies["base_model"] = line[5:].strip()
                
                elif line.upper().startswith('ADAPTER '):
                    dependencies["adapters"].append(line[8:].strip())
                
                elif line.upper().startswith('SYSTEM '):
                    dependencies["system_prompt"] = line[7:].strip()
                
                elif line.upper().startswith('PARAMETER '):
                    param_line = line[10:].strip()
                    if ' ' in param_line:
                        key, value = param_line.split(' ', 1)
                        dependencies["parameters"][key] = value
                
                elif line.upper().startswith('TEMPLATE '):
                    dependencies["template"] = line[9:].strip()
            
            return {
                "model": model_name,
                "instance": instance_name,
                "dependencies": dependencies,
                "modelfile": modelfile,
                "modelfile_size": len(modelfile)
            }
        
        except Exception as e:
            return {"error": f"Failed to analyze model: {e}"}
    
    def copy_model(
        self, 
        model_name: str, 
        from_instance: str, 
        to_instance: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Copy a model from one instance to another
        Uses a smarter approach that checks for base model dependencies
        """
        if self.logger:
            self.logger.info(
                f"Copying model '{model_name}': {from_instance} → {to_instance}"
            )
        
        # Validate instances
        if from_instance not in self.pool.instances:
            return {"error": f"Source instance '{from_instance}' not found"}
        
        if to_instance not in self.pool.instances:
            return {"error": f"Destination instance '{to_instance}' not found"}
        
        source = self.pool.instances[from_instance]
        dest = self.pool.instances[to_instance]
        
        # Get source model metadata
        try:
            response = requests.post(
                f"{source.api_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    "error": f"Model '{model_name}' not found on {from_instance}",
                    "status_code": response.status_code
                }
            
            source_metadata = response.json()
            
        except Exception as e:
            return {"error": f"Failed to get model info from {from_instance}: {e}"}
        
        # Check if destination already has it
        if not force:
            try:
                response = requests.post(
                    f"{dest.api_url}/api/show",
                    json={"name": model_name},
                    timeout=10
                )
                
                if response.status_code == 200:
                    return {
                        "status": "skipped",
                        "message": f"Model already exists on {to_instance} (use force=True to overwrite)",
                        "model": model_name
                    }
            except:
                pass  # Model doesn't exist, proceed with copy
        
        # Get the Modelfile
        modelfile = source_metadata.get("modelfile", "")
        
        if not modelfile:
            return {
                "error": f"Could not get Modelfile from {from_instance}",
                "model": model_name
            }
        
        if self.logger:
            self.logger.info(f"Retrieved Modelfile ({len(modelfile)} chars)")
            self.logger.debug(f"Modelfile content:\n{modelfile}")
        
        # Parse the Modelfile to find base model (FROM line)
        base_model = None
        for line in modelfile.split('\n'):
            line = line.strip()
            if line.upper().startswith('FROM '):
                base_model = line[5:].strip()
                break
        
        if self.logger:
            self.logger.info(f"Base model: {base_model or 'none (standalone)'}")
        
        # If there's a base model, check if destination has it
        if base_model:
            try:
                response = requests.post(
                    f"{dest.api_url}/api/show",
                    json={"name": base_model},
                    timeout=10
                )
                
                if response.status_code != 200:
                    # Base model missing on destination
                    if self.logger:
                        self.logger.warning(
                            f"Base model '{base_model}' not found on {to_instance}. "
                            f"Attempting to pull it first..."
                        )
                    
                    # Try to pull the base model
                    pull_response = requests.post(
                        f"{dest.api_url}/api/pull",
                        json={"name": base_model},
                        stream=True,
                        timeout=600
                    )
                    
                    if pull_response.status_code != 200:
                        return {
                            "error": f"Base model '{base_model}' not available on {to_instance} and pull failed",
                            "model": model_name,
                            "suggestion": f"Please pull '{base_model}' on {to_instance} first"
                        }
                    
                    # Stream pull progress
                    if self.logger:
                        self.logger.info(f"Pulling base model {base_model}...")
                    
                    for line in pull_response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                status = data.get('status', '')
                                if self.logger and status:
                                    self.logger.debug(f"  {status}")
                            except:
                                pass
                    
                    if self.logger:
                        self.logger.success(f"Base model {base_model} pulled successfully")
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not verify base model: {e}")
        
        # Now create the model on destination
        try:
            if self.logger:
                self.logger.info(f"Creating model on {to_instance}...")
            
            create_payload = {
                "name": model_name,
                "modelfile": modelfile,
                "stream": True
            }
            
            if self.logger:
                self.logger.debug(f"Create payload: {json.dumps(create_payload, indent=2)}")
            
            response = requests.post(
                f"{dest.api_url}/api/create",
                json=create_payload,
                stream=True,
                timeout=600
            )
            
            if response.status_code != 200:
                error_text = response.text[:500]
                if self.logger:
                    self.logger.error(
                        f"Create failed with status {response.status_code}:\n{error_text}"
                    )
                
                return {
                    "error": f"Failed to create model on {to_instance}",
                    "status_code": response.status_code,
                    "response": error_text,
                    "suggestion": "Check if all dependencies (base models, files) exist on destination"
                }
            
            # Stream the creation progress
            last_status = None
            error_in_stream = None
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        status = data.get("status", "")
                        
                        # Log status changes
                        if status and status != last_status:
                            if self.logger:
                                self.logger.info(f"  {status}")
                            last_status = status
                        
                        # Check for errors in stream
                        if "error" in data:
                            error_in_stream = data["error"]
                            if self.logger:
                                self.logger.error(f"Stream error: {error_in_stream}")
                    
                    except json.JSONDecodeError:
                        continue
            
            if error_in_stream:
                return {
                    "error": f"Model creation failed: {error_in_stream}",
                    "model": model_name
                }
            
            if self.logger:
                self.logger.success(f"✓ Model '{model_name}' copied successfully")
            
            # Invalidate model location cache
            self._model_location_cache_time = 0
            
            return {
                "status": "success",
                "message": f"Model '{model_name}' copied from {from_instance} to {to_instance}",
                "model": model_name,
                "source": from_instance,
                "destination": to_instance
            }
        
        except requests.exceptions.Timeout:
            return {
                "error": "Model creation timed out (took longer than 10 minutes)",
                "model": model_name,
                "suggestion": "Try copying a smaller model or increase timeout"
            }
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Copy failed with exception: {e}", exc_info=True)
            
            return {
                "error": f"Failed to copy model: {e}",
                "model": model_name
            }

    def sync_models(
        self, 
        source_instance: str,
        target_instances: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        force: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Sync models from source to target instances
        
        Args:
            source_instance: Instance to copy models from
            target_instances: Instances to copy to (None = all other instances)
            models: Specific models to sync (None = all models)
            force: Overwrite existing models
            dry_run: Just report what would be synced, don't actually sync
        
        Returns:
            Detailed sync report
        """
        if self.logger:
            self.logger.info(f"{'[DRY RUN] ' if dry_run else ''}Syncing models from {source_instance}")
        
        # Validate source
        if source_instance not in self.pool.instances:
            return {"error": f"Source instance '{source_instance}' not found"}
        
        # Determine target instances
        if target_instances is None:
            target_instances = [
                name for name in self.pool.instances.keys()
                if name != source_instance
            ]
        
        # Validate targets
        for target in target_instances:
            if target not in self.pool.instances:
                return {"error": f"Target instance '{target}' not found"}
        
        # Get source models
        try:
            response = requests.get(
                f"{self.pool.instances[source_instance].api_url}/api/tags",
                timeout=5
            )
            
            if response.status_code != 200:
                return {"error": f"Failed to list models on {source_instance}"}
            
            source_models = [
                m.get("name") or m.get("model", "")
                for m in response.json().get("models", [])
            ]
        
        except Exception as e:
            return {"error": f"Failed to get models from {source_instance}: {e}"}
        
        # Filter to requested models
        if models is not None:
            source_models = [m for m in source_models if m in models]
            
            # Check for requested models that don't exist
            missing = set(models) - set(source_models)
            if missing:
                if self.logger:
                    self.logger.warning(
                        f"Requested models not found on {source_instance}: {missing}"
                    )
        
        if not source_models:
            return {
                "status": "nothing_to_sync",
                "message": "No models to sync",
                "source": source_instance,
                "targets": target_instances
            }
        
        # Build sync plan
        sync_plan = {
            "source": source_instance,
            "targets": target_instances,
            "models": source_models,
            "total_models": len(source_models),
            "dry_run": dry_run,
            "operations": []
        }
        
        # For each target, determine what needs to be synced
        for target in target_instances:
            try:
                # Get target's existing models
                response = requests.get(
                    f"{self.pool.instances[target].api_url}/api/tags",
                    timeout=5
                )
                
                target_models = []
                if response.status_code == 200:
                    target_models = [
                        m.get("name") or m.get("model", "")
                        for m in response.json().get("models", [])
                    ]
                
                # Determine what to copy
                for model in source_models:
                    exists = model in target_models
                    
                    if exists and not force:
                        action = "skip"
                        reason = "already exists"
                    else:
                        action = "copy" if not dry_run else "would_copy"
                        reason = "overwrite" if exists else "new"
                    
                    sync_plan["operations"].append({
                        "model": model,
                        "target": target,
                        "action": action,
                        "reason": reason,
                        "exists": exists
                    })
            
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to check {target}: {e}")
                continue
        
        # Summary
        sync_plan["summary"] = {
            "total_operations": len(sync_plan["operations"]),
            "will_copy": sum(1 for op in sync_plan["operations"] if op["action"] in ["copy", "would_copy"]),
            "will_skip": sum(1 for op in sync_plan["operations"] if op["action"] == "skip")
        }
        
        if self.logger:
            self.logger.info(
                f"Sync plan: {sync_plan['summary']['will_copy']} to copy, "
                f"{sync_plan['summary']['will_skip']} to skip"
            )
        
        # Execute if not dry run
        if not dry_run:
            results = []
            
            for op in sync_plan["operations"]:
                if op["action"] == "copy":
                    if self.logger:
                        self.logger.info(f"Copying {op['model']} → {op['target']}...")
                    
                    result = self.copy_model(
                        op["model"],
                        source_instance,
                        op["target"],
                        force=force
                    )
                    
                    results.append({
                        **op,
                        "result": result
                    })
            
            sync_plan["results"] = results
            sync_plan["execution"] = {
                "success": sum(1 for r in results if r["result"].get("status") == "success"),
                "failed": sum(1 for r in results if "error" in r["result"]),
                "skipped": sum(1 for r in results if r["result"].get("status") == "skipped")
            }
            
            if self.logger:
                self.logger.success(
                    f"Sync complete: {sync_plan['execution']['success']} succeeded, "
                    f"{sync_plan['execution']['failed']} failed"
                )
        
        return sync_plan
  
    def set_manual_routing(self, instance_names: List[str]):
        """
        Enable manual routing to specific instances
        Temporarily filters the pool to only use specified instances
        
        Args:
            instance_names: List of instance names to use
        """
        if not instance_names:
            raise ValueError("Must specify at least one instance for manual routing")
        
        # Validate instances exist
        invalid = set(instance_names) - set(self.pool.instances.keys())
        if invalid:
            raise ValueError(f"Invalid instance names: {invalid}")
        
        # Store original instances if not already stored
        if not hasattr(self, '_original_instances'):
            self._original_instances = self.pool.instances.copy()
        
        # Filter to selected instances
        self.pool.instances = {
            name: config 
            for name, config in self._original_instances.items()
            if name in instance_names
        }
        
        if self.logger:
            self.logger.info(f"Manual routing enabled: {instance_names}")
    
    def set_auto_routing(self):
        """
        Restore automatic routing (use all instances)
        """
        if hasattr(self, '_original_instances'):
            self.pool.instances = self._original_instances.copy()
            delattr(self, '_original_instances')
        
        if self.logger:
            self.logger.info("Automatic routing restored")
    
    def get_routing_mode(self) -> dict:
        """
        Get current routing configuration
        
        Returns:
            Dict with routing mode and active instances
        """
        is_manual = hasattr(self, '_original_instances')
        
        return {
            "mode": "manual" if is_manual else "auto",
            "active_instances": list(self.pool.instances.keys()),
            "total_instances": len(self._original_instances) if is_manual else len(self.pool.instances),
            "filtered": is_manual
        }
    
    def create_llm_with_routing(
        self, 
        model: str, 
        routing_mode: str = "auto",
        selected_instances: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Create LLM with explicit routing control
        
        Args:
            model: Model name
            routing_mode: 'auto' or 'manual'
            selected_instances: Instance names for manual mode
            **kwargs: Additional LLM parameters
        
        Returns:
            Configured LLM instance
        """
        # Apply routing if manual mode
        if routing_mode == "manual" and selected_instances:
            self.set_manual_routing(selected_instances)
        elif routing_mode == "auto":
            self.set_auto_routing()
        
        # Create LLM with current routing
        return self.create_llm(model, **kwargs)



from langchain.llms.base import LLM
from langchain_core.outputs import GenerationChunk
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from typing import Any, List, Optional, Iterator, Dict
from pydantic import Field
import time
import json
import requests

class PooledOllamaLLM(LLM):
    """
    LLM wrapper that uses instance pool for all requests
    Fully compatible with LangChain by properly inheriting from LLM base class
    """
    
    # Required Pydantic fields
    model: str = Field(description="Model name")
    temperature: float = Field(default=0.7, description="Temperature for generation")
    top_k: int = Field(default=40, description="Top-k sampling parameter")
    top_p: float = Field(default=0.9, description="Top-p sampling parameter")
    num_predict: int = Field(default=-1, description="Number of tokens to predict")
    max_retries: int = Field(default=2, description="Max retries across instances")
    
    # Non-Pydantic fields (excluded from validation)
    pool: Any = Field(default=None, exclude=True, repr=False)
    timeout: int = Field(default=2400, exclude=True)
    thought_callback: Optional[Any] = Field(default=None, exclude=True, repr=False)
    thought_capture: Any = Field(default=None, exclude=True, repr=False)
    model_metadata: Optional[Dict] = Field(default=None, exclude=True)
    logger: Any = Field(default=None, exclude=True, repr=False)
    extra_kwargs: Dict = Field(default_factory=dict, exclude=True)
    allowed_instances: Optional[List[str]] = Field(default=None, exclude=True)  # NEW: restricts routing
    
    class Config:
        """Pydantic config"""
        arbitrary_types_allowed = True
        extra = "forbid"  # Don't allow extra fields
    
    @property
    def _llm_type(self) -> str:
        """Return identifier for LLM type - REQUIRED by LangChain"""
        return "pooled_ollama"
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters - used by LangChain"""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "pool_instances": len(self.pool.instances) if self.pool and hasattr(self.pool, 'instances') else 0,
            "allowed_instances": self.allowed_instances
        }
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call method REQUIRED by LangChain LLM base class
        This is NOT a property - it's a regular method
        """
        return self._invoke_with_retry(prompt, stop=stop, **kwargs)
    
    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """
        Stream method for LangChain compatibility
        Yields GenerationChunk objects
        """
        for chunk_text in self._stream_with_retry(prompt, stop=stop, **kwargs):
            chunk = GenerationChunk(text=chunk_text)
            if run_manager:
                run_manager.on_llm_new_token(chunk_text)
            yield chunk
    
    def _invoke_with_retry(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Internal method: Non-streaming generation with automatic failover"""
        last_error = None
        attempts = 0
        
        # Use allowed_instances if set, otherwise try all
        available_instances = self.allowed_instances if self.allowed_instances else list(self.pool.instances.keys())
        max_attempts = min(self.max_retries, len(available_instances))
        
        # Reset thought capture if present
        if self.thought_capture:
            self.thought_capture.reset()
        
        while attempts < max_attempts:
            attempts += 1
            
            if not self.pool:
                raise RuntimeError("Pool not initialized")
            
            # Acquire instance with routing restriction
            acquisition = self.pool.acquire_instance(
                timeout=30.0,
                allowed_instances=self.allowed_instances
            )
            
            if not acquisition:
                if self.logger:
                    filter_msg = f" (filtered to: {self.allowed_instances})" if self.allowed_instances else ""
                    self.logger.warning(
                        f"Attempt {attempts}/{max_attempts}: No instances available{filter_msg}"
                    )
                
                if attempts < max_attempts:
                    time.sleep(1.0)
                    continue
                
                raise RuntimeError(f"No Ollama instances available after retries (allowed: {self.allowed_instances})")
            
            instance_name, instance, release = acquisition
            
            try:
                if self.logger:
                    self.logger.debug(
                        f"Attempt {attempts}: Invoking {self.model} on {instance_name}"
                    )
                
                start_time = time.time()
                
                # Build request
                request_data = {
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": False,
                    "top_k": self.top_k,
                    "top_p": self.top_p,
                    "num_predict": self.num_predict,
                    **self.extra_kwargs
                }
                
                if stop:
                    request_data["stop"] = stop
                
                url = f"{instance.api_url}/api/generate"
                
                response = requests.post(
                    url,
                    json=request_data,
                    timeout=self.timeout
                )
                
                duration = time.time() - start_time
                
                # SUCCESS
                if response.status_code == 200:
                    data = response.json()
                    
                    # PROCESS THOUGHTS using ThoughtCapture
                    if self.thought_capture:
                        modified_response = self.thought_capture.process_chunk(data)
                        result = modified_response if modified_response is not None else data.get("response", "")
                    else:
                        result = data.get("response", "")
                    
                    # Update stats
                    if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                        self.pool.stats[instance_name].total_duration += duration
                    
                    if self.logger:
                        self.logger.success(
                            f"✓ Completed on {instance_name} in {duration:.2f}s"
                        )
                    
                    return result
                
                # FAILURE
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    
                    if self.logger:
                        self.logger.warning(
                            f"✗ Instance {instance_name} failed: {error_msg}"
                        )
                    
                    # Mark unhealthy ONLY if it's a server error (5xx), not if model is missing (4xx)
                    if response.status_code >= 500:
                        if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                            self.pool.stats[instance_name].is_healthy = False
                    
                    if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                        self.pool.stats[instance_name].total_failures += 1
                    
                    last_error = RuntimeError(error_msg)
                    
                    # Retry
                    if attempts < max_attempts:
                        if self.logger:
                            self.logger.info(f"Retrying ({attempts + 1}/{max_attempts})...")
                        continue
            
            except requests.exceptions.Timeout as e:
                if self.logger:
                    self.logger.warning(f"✗ Timeout on {instance_name}")
                
                if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                    self.pool.stats[instance_name].is_healthy = False
                    self.pool.stats[instance_name].total_failures += 1
                
                last_error = e
                if attempts < max_attempts:
                    continue
            
            except Exception as e:
                if self.logger:
                    self.logger.error(f"✗ Error on {instance_name}: {e}")
                
                if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                    self.pool.stats[instance_name].total_failures += 1
                
                last_error = e
                if attempts < max_attempts:
                    continue
            
            finally:
                release()
        
        # All attempts failed
        if self.logger:
            self.logger.error(f"All {attempts} attempts failed")
        
        raise last_error or RuntimeError(f"Generation failed after {attempts} attempts")
    
    def _stream_with_retry(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> Iterator[str]:
        """Internal method: Streaming generation with automatic failover"""
        last_error = None
        attempts = 0
        
        # Use allowed_instances if set, otherwise try all
        available_instances = self.allowed_instances if self.allowed_instances else list(self.pool.instances.keys())
        max_attempts = min(self.max_retries, len(available_instances))
        
        # Reset thought capture if present
        if self.thought_capture:
            self.thought_capture.reset()
        
        while attempts < max_attempts:
            attempts += 1
            
            if not self.pool:
                raise RuntimeError("Pool not initialized")
            
            # Acquire instance with routing restriction
            acquisition = self.pool.acquire_instance(
                timeout=30.0,
                allowed_instances=self.allowed_instances
            )
            
            if not acquisition:
                if attempts < max_attempts:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"No instances available (allowed: {self.allowed_instances})")
            
            instance_name, instance, release = acquisition
            
            try:
                if self.logger:
                    self.logger.debug(f"Stream attempt {attempts}: Using {instance_name}")
                
                request_data = {
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": True,
                    "top_k": self.top_k,
                    "top_p": self.top_p,
                    "num_predict": self.num_predict,
                    **self.extra_kwargs
                }
                
                if stop:
                    request_data["stop"] = stop
                
                url = f"{instance.api_url}/api/generate"
                
                response = requests.post(
                    url,
                    json=request_data,
                    stream=True,
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    
                    if self.logger:
                        self.logger.warning(f"✗ Stream failed on {instance_name}: {error_msg}")
                    
                    # Mark unhealthy ONLY for server errors
                    if response.status_code >= 500:
                        if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                            self.pool.stats[instance_name].is_healthy = False
                    
                    if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                        self.pool.stats[instance_name].total_failures += 1
                    
                    last_error = RuntimeError(error_msg)
                    
                    if attempts < max_attempts:
                        continue
                    else:
                        raise last_error
                
                # SUCCESS - stream chunks with THOUGHT PROCESSING
                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            
                            # PROCESS THOUGHTS using ThoughtCapture
                            if self.thought_capture:
                                modified_chunk = self.thought_capture.process_chunk(data)
                                chunk_text = modified_chunk
                            else:
                                chunk_text = data.get('response', '')
                            
                            # Only yield if we have actual response text (thoughts go to callback)
                            if chunk_text:
                                chunk_count += 1
                                yield chunk_text
                        
                        except json.JSONDecodeError:
                            continue
                
                if self.logger:
                    self.logger.success(f"✓ Stream completed: {chunk_count} chunks")
                
                return  # Success - exit
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"✗ Stream error on {instance_name}: {e}")
                
                if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                    self.pool.stats[instance_name].total_failures += 1
                
                last_error = e
                if attempts < max_attempts:
                    continue
            
            finally:
                release()
        
        # All attempts failed
        raise last_error or RuntimeError("Stream failed after retries")