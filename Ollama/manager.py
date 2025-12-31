#!/usr/bin/env python3
# Vera/Ollama/manager.py

"""
Enhanced Ollama Connection Manager with Comprehensive Logging
"""

import sys
import os
import json
import requests
import traceback
from typing import List, Dict, Any, Optional, Iterator, Callable
from dataclasses import dataclass, field
from collections.abc import Iterator as ABCIterator
import ollama
from langchain.llms.base import LLM
from langchain_core.outputs import GenerationChunk
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings

try:
    from Vera.Logging.logging import LogContext
except ImportError:
    try:
        from Logging.logging import LogContext
    except ImportError:
        from dataclasses import dataclass
        @dataclass
        class LogContext:
            pass


@dataclass
class OllamaModelInfo:
    """Model information with comprehensive metadata"""
    name: str
    size: int = 0
    format: str = ""
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""
    context_length: int = 2048
    embedding_length: int = 0
    capabilities: List[str] = field(default_factory=list)
    license: str = ""
    modified_at: str = ""
    
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.9
    num_predict: int = -1
    stop: List[str] = field(default_factory=list)
    
    supports_thought: bool = False
    supports_streaming: bool = True
    supports_vision: bool = False
    
    def __str__(self):
        return f"Model({self.name}, {self.parameter_size}, ctx={self.context_length})"


class ThoughtCapture:
    """Universal thought capture with detailed logging"""
    
    def __init__(self, enabled: bool = True, callback: Optional[Callable[[str], None]] = None, logger=None):
        self.enabled = enabled
        self.callback = callback
        self.logger = logger
        self.thought_buffer = []
        self.in_thought_mode = False
        self.chunk_count = 0
        self.thoughts_captured = 0
        
        if self.logger:
            self.logger.debug(f"ThoughtCapture initialized (enabled={enabled})")
    
    def process_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Process chunk with immediate streaming - no buffering for thoughts"""
        if self.logger and hasattr(self.logger, 'config') and self.logger.config.show_ollama_raw_chunks:
            self.logger.raw_stream_chunk(chunk_data, self.chunk_count)
        
        self.chunk_count += 1
        
        if not self.enabled:
            response = chunk_data.get('response', '')
            if self.logger:
                self.logger.trace(f"Thought capture disabled, passing through: {len(response)} chars")
            return response
        
        if self.logger:
            self.logger.trace(f"Processing chunk #{self.chunk_count}: {list(chunk_data.keys())}")
        
        # Check direct thought fields
        for field in ['thought', 'reasoning', 'thinking', 'internal']:
            if field in chunk_data and chunk_data[field]:
                thought = chunk_data[field]
                
                if self.logger:
                    self.logger.debug(f"Direct thought field '{field}': {len(thought)} chars")
                
                # STREAM IMMEDIATELY - don't wait for complete thought
                self._stream_thought_chunk(thought)
                return chunk_data.get('response', '')
        
        # Check response content for markers
        response = chunk_data.get('response', '')
        if response:
            if '<think>' in response:
                if self.logger:
                    self.logger.debug("Opening <think> tag detected")
                
                self.in_thought_mode = True
                thought_start = response.find('<think>') + 7
                thought_end = response.find('</think>')
                
                if thought_end > thought_start:
                    # Complete thought in one chunk
                    thought = response[thought_start:thought_end]
                    
                    if self.logger:
                        self.logger.debug(f"Complete thought: {len(thought)} chars")
                    
                    # STREAM IMMEDIATELY
                    self._stream_thought_chunk(thought)
                    self.in_thought_mode = False
                    clean_response = response[:response.find('<think>')] + response[thought_end + 8:]
                    return clean_response if clean_response else None
                else:
                    # Partial thought (start)
                    thought = response[thought_start:]
                    
                    if self.logger:
                        self.logger.debug(f"Partial thought start: {len(thought)} chars - streaming immediately")
                    
                    # STREAM THIS CHUNK IMMEDIATELY - don't buffer!
                    self._stream_thought_chunk(thought)
                    
                    prefix = response[:response.find('<think>')]
                    return prefix if prefix else None
            
            elif '</think>' in response and self.in_thought_mode:
                # End of thought
                if self.logger:
                    self.logger.debug("Closing </think> tag detected")
                
                thought_end = response.find('</think>')
                thought = response[:thought_end]
                
                if self.logger:
                    self.logger.debug(f"Partial thought end: {len(thought)} chars - streaming immediately")
                
                # STREAM THIS FINAL CHUNK IMMEDIATELY
                self._stream_thought_chunk(thought)
                
                self.in_thought_mode = False
                self.thoughts_captured += 1  # Mark thought as complete
                
                suffix = response[thought_end + 8:]
                return suffix if suffix else None
            
            elif self.in_thought_mode:
                # Middle of thought - STREAM IMMEDIATELY, don't buffer!
                if self.logger:
                    self.logger.trace(f"Thought continuation: {len(response)} chars - streaming immediately")
                
                # STREAM THIS CHUNK IMMEDIATELY
                self._stream_thought_chunk(response)
                
                return None
            
            else:
                # Normal response
                if self.logger:
                    self.logger.trace(f"Normal response: {len(response)} chars")
                return response
        
        return None

    def _stream_thought_chunk(self, chunk: str):
        """Stream a thought chunk immediately to the callback"""
        if not chunk:
            return
        
        # Call the callback IMMEDIATELY with this chunk
        if self.callback:
            try:
                self.callback(chunk)
                
                if self.logger:
                    self.logger.trace(f"Streamed thought chunk: {len(chunk)} chars")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Thought callback error: {e}", exc_info=True)
        
        # Also log to console if logger present
        if self.logger:
            # Don't log the full chunk at debug level - too verbose
            self.logger.trace(f"Thought chunk: {chunk[:50]}..." if len(chunk) > 50 else f"Thought chunk: {chunk}")
    
    def _handle_thought(self, thought: str):
        """Handle complete thought (legacy - now we stream chunks directly)"""
        if not thought:
            return
        
        self.thoughts_captured += 1
        
        if self.logger:
            self.logger.info(f"Complete thought #{self.thoughts_captured}: {len(thought)} chars")
        
        # Note: Callback already called during streaming in _stream_thought_chunk
        # This is just for logging the complete thought

    def _flush_thought_buffer(self):
        """Flush buffer (legacy - now we stream immediately)"""
        # With immediate streaming, buffer should be empty
        # Keep for compatibility but it shouldn't be called
        if self.thought_buffer:
            buffer_size = sum(len(s) for s in self.thought_buffer)
            
            if self.logger:
                self.logger.warning(f"Flushing non-empty thought buffer: {len(self.thought_buffer)} segments (shouldn't happen with streaming)")
            
            full_thought = "".join(self.thought_buffer)
            self._stream_thought_chunk(full_thought)
            self.thought_buffer.clear()
    
    def reset(self):
        """Reset with logging"""
        if self.logger:
            self.logger.trace(f"Resetting thought capture (captured={self.thoughts_captured}, chunks={self.chunk_count})")
        
        self.thought_buffer.clear()
        self.in_thought_mode = False
        self.chunk_count = 0


class OllamaConnectionManager:
    """Ollama manager with comprehensive logging"""
    
    def __init__(self, config=None, thought_callback: Optional[Callable[[str], None]] = None, logger=None):
        if config is None:
            from Vera.Configuration.config_manager import OllamaConfig
            config = OllamaConfig()
        
        self.config = config
        self.api_url = config.api_url
        self.timeout = config.timeout
        self.use_local = False
        self.connection_tested = False
        self.model_metadata_cache: Dict[str, OllamaModelInfo] = {}
        
        if logger is None:
            from Vera.Logging.logging import get_logger, LoggingConfig, LogLevel
            log_config = LoggingConfig(global_level=LogLevel.INFO)
            self.logger = get_logger("ollama", log_config)
        else:
            self.logger = logger
        
        self.logger.info(f"OllamaConnectionManager initialized (api_url={self.api_url}, timeout={self.timeout})")
        
        self.thought_capture = ThoughtCapture(
            enabled=getattr(config, 'enable_thought_capture', True),
            callback=thought_callback,
            logger=self.logger
        )
        
        self.logger.debug("OllamaConnectionManager ready")
    
    def test_connection(self) -> bool:
        """Test connection with detailed logging"""
        self.logger.info(f"Testing connection to {self.api_url}")
        self.logger.start_timer("connection_test")
        
        try:
            self.logger.debug("Attempting API connection...")
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            
            if response.status_code == 200:
                duration = self.logger.stop_timer("connection_test")
                
                models_data = response.json().get("models", [])
                self.logger.success(f"API connection successful in {duration:.3f}s ({len(models_data)} models available)")
                
                self.use_local = False
                self.connection_tested = True
                return True
            else:
                self.logger.warning(f"API returned status {response.status_code}")
        
        except requests.exceptions.ConnectionError as e:
            duration = self.logger.stop_timer("connection_test")
            self.logger.warning(f"API connection failed after {duration:.3f}s: {type(e).__name__}")
        
        except requests.exceptions.Timeout as e:
            duration = self.logger.stop_timer("connection_test")
            self.logger.warning(f"API connection timeout after {duration:.3f}s")
        
        except Exception as e:
            duration = self.logger.stop_timer("connection_test")
            self.logger.error(f"Unexpected connection error after {duration:.3f}s: {e}", exc_info=True)
        
        if self.config.use_local_fallback:
            self.logger.info("Falling back to local Ollama process")
            self.use_local = True
            self.connection_tested = True
            return True
        
        self.logger.error("Connection failed with no fallback available")
        return False
    
    def list_models(self) -> List[Dict]:
        """List models with comprehensive logging"""
        if not self.connection_tested:
            self.logger.debug("Connection not tested, testing now...")
            self.test_connection()
        
        self.logger.info("Listing available models")
        self.logger.start_timer("list_models")
        
        for attempt in range(self.config.connection_retry_attempts):
            if not self.use_local:
                try:
                    self.logger.debug(f"API list attempt {attempt + 1}/{self.config.connection_retry_attempts}")
                    response = requests.get(f"{self.api_url}/api/tags", timeout=5)
                    
                    if response.status_code == 200:
                        duration = self.logger.stop_timer("list_models")
                        models_data = response.json().get("models", [])
                        model_list = [{"model": m.get("name", m.get("model", ""))} for m in models_data]
                        
                        self.logger.success(f"Found {len(model_list)} models via API in {duration:.3f}s")
                        
                        if model_list:
                            model_names = [m['model'] for m in model_list[:5]]
                            self.logger.debug(f"Models: {', '.join(model_names)}")
                            if len(model_list) > 5:
                                self.logger.debug(f"... and {len(model_list) - 5} more")
                        
                        return model_list
                
                except Exception as e:
                    self.logger.debug(f"API list attempt {attempt + 1} failed: {e}")
                    
                    if attempt < self.config.connection_retry_attempts - 1:
                        import time
                        self.logger.debug(f"Retrying in {self.config.connection_retry_delay}s...")
                        time.sleep(self.config.connection_retry_delay)
                        continue
                    
                    self.logger.warning("API list failed, switching to local")
                    self.use_local = True
            
            # Local fallback
            try:
                self.logger.debug(f"Local list attempt {attempt + 1}/{self.config.connection_retry_attempts}")
                models = ollama.list()["models"]
                duration = self.logger.stop_timer("list_models")
                
                self.logger.success(f"Found {len(models)} models via local in {duration:.3f}s")
                
                if models:
                    model_names = [m.get('model', m.get('name', 'unknown')) for m in models[:5]]
                    self.logger.debug(f"Models: {', '.join(model_names)}")
                    if len(models) > 5:
                        self.logger.debug(f"... and {len(models) - 5} more")
                
                return models
            
            except Exception as e:
                self.logger.debug(f"Local list attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.connection_retry_attempts - 1:
                    import time
                    time.sleep(self.config.connection_retry_delay)
                    continue
                
                self.logger.error(f"All {self.config.connection_retry_attempts} attempts failed", exc_info=True)
                raise RuntimeError(f"Connection failed after {self.config.connection_retry_attempts} attempts")
        
        return []
    
    def get_model_metadata(self, model_name: str, force_refresh: bool = False) -> OllamaModelInfo:
        """Get metadata with detailed logging"""
        context = LogContext(model=model_name)
        
        # Check cache
        if not force_refresh and model_name in self.model_metadata_cache:
            self.logger.trace(f"Using cached metadata for {model_name}", context=context)
            return self.model_metadata_cache[model_name]
        
        self.logger.info(f"Fetching metadata for {model_name}", context=context)
        self.logger.start_timer(f"metadata_{model_name}")
        
        model_info = OllamaModelInfo(name=model_name)
        
        try:
            # Try API
            if not self.use_local:
                try:
                    self.logger.debug("Attempting API metadata fetch", context=context)
                    response = requests.post(
                        f"{self.api_url}/api/show",
                        json={"name": model_name},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        self.logger.debug(f"API metadata received: {list(data.keys())}", context=context)
                        self._parse_model_metadata(model_info, data)
                    else:
                        self.logger.debug(f"API metadata returned {response.status_code}", context=context)
                
                except Exception as e:
                    self.logger.debug(f"API metadata failed: {e}", context=context)
            
            # Try local
            if self.use_local or model_info.context_length == 2048:
                try:
                    self.logger.debug("Attempting local metadata fetch", context=context)
                    data = ollama.show(model_name)
                    self.logger.debug(f"Local metadata received: {list(data.keys())}", context=context)
                    self._parse_model_metadata(model_info, data)
                
                except Exception as e:
                    self.logger.debug(f"Local metadata failed: {e}", context=context)
            
            # Cache
            self.model_metadata_cache[model_name] = model_info
            duration = self.logger.stop_timer(f"metadata_{model_name}", context=context)
            
            self.logger.success(
                f"Metadata loaded in {duration:.3f}s: {model_info.family} {model_info.parameter_size}, "
                f"ctx={model_info.context_length}, thought={model_info.supports_thought}",
                context=context
            )
            
        except Exception as e:
            duration = self.logger.stop_timer(f"metadata_{model_name}", context=context)
            self.logger.warning(f"Metadata fetch failed after {duration:.3f}s: {e}", context=context)
        
        return model_info
    
    def _parse_model_metadata(self, model_info: OllamaModelInfo, data: Dict[str, Any]):
        """Parse metadata with detailed logging"""
        context = LogContext(model=model_info.name)
        
        self.logger.trace(f"Parsing metadata: {len(data)} fields", context=context)
        
        # Details
        if 'details' in data:
            details = data['details']
            model_info.family = details.get('family', '')
            model_info.parameter_size = details.get('parameter_size', '')
            model_info.quantization_level = details.get('quantization_level', '')
            model_info.format = details.get('format', '')
            
            self.logger.trace(f"Details: family={model_info.family}, params={model_info.parameter_size}", context=context)
        
        # Modelfile
        if 'modelfile' in data:
            modelfile = data['modelfile']
            
            if 'num_ctx' in modelfile:
                try:
                    model_info.context_length = int(modelfile.split('num_ctx')[1].split()[0])
                    self.logger.trace(f"Context from modelfile: {model_info.context_length}", context=context)
                except Exception as e:
                    self.logger.trace(f"Failed to parse num_ctx: {e}", context=context)
        
        # Model info
        if 'model_info' in data:
            info = data['model_info']
            
            for key in ['context_length', 'max_position_embeddings', 'n_ctx']:
                if key in info:
                    model_info.context_length = info[key]
                    self.logger.trace(f"Context from {key}: {model_info.context_length}", context=context)
                    break
            
            for key in ['embedding_length', 'hidden_size', 'n_embd']:
                if key in info:
                    model_info.embedding_length = info[key]
                    self.logger.trace(f"Embeddings: {model_info.embedding_length} dims", context=context)
                    break
        
        # License
        model_info.license = data.get('license', '')
        model_info.modified_at = data.get('modified_at', '')
        
        if 'size' in data:
            model_info.size = data['size']
            size_mb = model_info.size / (1024 * 1024)
            self.logger.trace(f"Model size: {size_mb:.1f} MB", context=context)
        
        # Detect capabilities
        model_lower = model_info.name.lower()
        
        model_info.supports_thought = any(x in model_lower for x in [
            'deepseek', 'gpt-oss', 'reasoning', 'o1', 'qwen-think', 'r1'
        ])
        
        model_info.supports_vision = any(x in model_lower for x in [
            'vision', 'llava', 'minicpm', 'cogvlm', 'internvl'
        ])
        
        model_info.supports_streaming = True
        
        self.logger.debug(
            f"Capabilities: thought={model_info.supports_thought}, "
            f"vision={model_info.supports_vision}, streaming={model_info.supports_streaming}",
            context=context
        )
    
    def pull_model(self, model_name: str, stream: bool = True) -> bool:
        """Pull model with progress logging"""
        context = LogContext(model=model_name)
        
        if not self.connection_tested:
            self.test_connection()
        
        self.logger.info(f"Pulling model: {model_name}", context=context)
        self.logger.start_timer(f"pull_{model_name}")
        
        if not self.use_local:
            try:
                self.logger.debug("Initiating API pull", context=context)
                response = requests.post(
                    f"{self.api_url}/api/pull",
                    json={"name": model_name, "stream": stream},
                    timeout=300 if not stream else None,
                    stream=stream
                )
                
                if stream:
                    last_pct = -1
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                status = data.get('status', '')
                                
                                if 'total' in data and 'completed' in data:
                                    pct = int((data['completed'] / data['total']) * 100)
                                    
                                    if pct != last_pct and pct % 10 == 0:
                                        self.logger.info(f"Pull progress: {pct}% - {status}", context=context)
                                        last_pct = pct
                                else:
                                    self.logger.debug(f"Pull status: {status}", context=context)
                            except:
                                pass
                
                if response.status_code == 200:
                    duration = self.logger.stop_timer(f"pull_{model_name}", context=context)
                    self.logger.success(f"Model pulled successfully in {duration:.1f}s", context=context)
                    return True
                else:
                    self.logger.warning(f"API pull returned {response.status_code}", context=context)
                    
            except Exception as e:
                duration = self.logger.stop_timer(f"pull_{model_name}", context=context)
                self.logger.warning(f"API pull failed after {duration:.1f}s: {e}", context=context)
                self.use_local = True
        
        # Local fallback
        try:
            self.logger.debug("Using local pull", context=context)
            ollama.pull(model_name)
            duration = self.logger.stop_timer(f"pull_{model_name}", context=context)
            
            self.logger.success(f"Model pulled (local) in {duration:.1f}s", context=context)
            return True
        
        except Exception as e:
            duration = self.logger.stop_timer(f"pull_{model_name}", context=context)
            self.logger.error(f"Pull failed after {duration:.1f}s: {e}", context=context, exc_info=True)
            return False
    
    def create_llm(self, model: str, temperature: Optional[float] = None, **kwargs):
        """Create LLM with comprehensive logging"""
        context = LogContext(model=model)
        
        if not self.connection_tested:
            self.logger.debug("Connection not tested, testing now...", context=context)
            self.test_connection()
        
        self.logger.info(f"Creating LLM: {model}", context=context)
        self.logger.start_timer(f"create_llm_{model}")
        
        # Get metadata
        model_info = self.get_model_metadata(model)
        
        # Temperature
        if temperature is None:
            temperature = self.config.temperature if hasattr(self.config, 'temperature') else 0.7
            self.logger.trace(f"Using default temperature: {temperature}", context=context)
        else:
            self.logger.trace(f"Using specified temperature: {temperature}", context=context)
        
        # Merge kwargs
        merged_kwargs = {
            'top_k': getattr(self.config, 'top_k', model_info.top_k),
            'top_p': getattr(self.config, 'top_p', model_info.top_p),
            'num_predict': getattr(self.config, 'num_predict', model_info.num_predict),
        }
        merged_kwargs.update(kwargs)
        
        self.logger.debug(
            f"LLM params: temp={temperature}, top_k={merged_kwargs['top_k']}, "
            f"top_p={merged_kwargs['top_p']}, num_predict={merged_kwargs['num_predict']}",
            context=context
        )
        
        if not self.use_local:
            llm = OllamaAPIWrapper(
                model=model,
                temperature=temperature,
                api_url=self.api_url,
                timeout=self.timeout,
                model_info=model_info,
                thought_capture=self.thought_capture,
                logger=self.logger,
                **merged_kwargs
            )
            
            duration = self.logger.stop_timer(f"create_llm_{model}", context=context)
            
            self.logger.success(
                f"LLM created (API mode) in {duration:.3f}s - "
                f"ctx={model_info.context_length}, thought={model_info.supports_thought}",
                context=context
            )
            
            return llm
        
        else:
            llm = Ollama(
                model=model,
                temperature=temperature,
                **merged_kwargs
            )
            
            duration = self.logger.stop_timer(f"create_llm_{model}", context=context)
            
            self.logger.success(
                f"LLM created (local mode) in {duration:.3f}s - ctx={model_info.context_length}",
                context=context
            )
            
            return llm
    
    def create_embeddings(self, model: str, **kwargs):
        """Create embeddings with logging"""
        context = LogContext(model=model)
        
        if not self.connection_tested:
            self.test_connection()
        
        self.logger.info(f"Creating embeddings: {model}", context=context)
        self.logger.start_timer(f"create_embeddings_{model}")
        
        model_info = self.get_model_metadata(model)
        
        self.logger.debug(f"Embedding dimensions: {model_info.embedding_length}", context=context)
        
        if not self.use_local:
            embeddings = OllamaEmbeddings(model=model, base_url=self.api_url, **kwargs)
            mode = "API"
        else:
            embeddings = OllamaEmbeddings(model=model, **kwargs)
            mode = "local"
        
        duration = self.logger.stop_timer(f"create_embeddings_{model}", context=context)
        
        self.logger.success(f"Embeddings created ({mode}) in {duration:.3f}s", context=context)
        
        return embeddings
    
    def print_model_info(self, model_name: str):
        """Print detailed model info"""
        model_info = self.get_model_metadata(model_name)
        
        context = LogContext(model=model_name)
        
        self.logger.info("=" * 60)
        self.logger.info(f"Model: {model_info.name}")
        self.logger.info("=" * 60)
        self.logger.info(f"Family:        {model_info.family}")
        self.logger.info(f"Parameters:    {model_info.parameter_size}")
        self.logger.info(f"Quantization:  {model_info.quantization_level}")
        self.logger.info(f"Context:       {model_info.context_length} tokens")
        
        if model_info.embedding_length:
            self.logger.info(f"Embeddings:    {model_info.embedding_length} dimensions")
        
        self.logger.info(f"Format:        {model_info.format}")
        
        if model_info.size:
            size_gb = model_info.size / (1024 * 1024 * 1024)
            self.logger.info(f"Size:          {size_gb:.2f} GB")
        
        self.logger.info("\nCapabilities:")
        self.logger.info(f"  • Thought Output:  {'✓' if model_info.supports_thought else '✗'}")
        self.logger.info(f"  • Streaming:       {'✓' if model_info.supports_streaming else '✗'}")
        self.logger.info(f"  • Vision:          {'✓' if model_info.supports_vision else '✗'}")
        
        self.logger.info("\nDefault Parameters:")
        self.logger.info(f"  • Temperature:     {model_info.temperature}")
        self.logger.info(f"  • Top-K:           {model_info.top_k}")
        self.logger.info(f"  • Top-P:           {model_info.top_p}")
        
        if model_info.license:
            self.logger.info(f"\nLicense:       {model_info.license}")
        
        if model_info.modified_at:
            self.logger.info(f"Modified:      {model_info.modified_at}")
        
        self.logger.info("=" * 60)


class OllamaAPIWrapper(LLM):
    """API wrapper with comprehensive logging"""
    
    model: str
    temperature: float = 0.7
    api_url: str = "http://localhost:11434"
    timeout: int = 2400
    model_info: Optional[OllamaModelInfo] = None
    thought_capture: Optional[ThoughtCapture] = None
    logger: Any = None
    
    top_k: int = 40
    top_p: float = 0.9
    num_predict: int = -1
    
    @property
    def _llm_type(self) -> str:
        return "ollama_api_enhanced"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> str:
        """Call with detailed logging"""
        context = LogContext(model=self.model)
        
        try:
            if self.thought_capture:
                self.thought_capture.reset()
            
            if self.logger:
                self.logger.start_timer("llm_call")
                self.logger.info(f"API call: {len(prompt)} char prompt", context=context)
            
            api_kwargs = self._build_api_kwargs(kwargs)
            
            if self.logger:
                self.logger.debug(f"Request params: {list(api_kwargs.keys())}", context=context)
            
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": False,
                    **api_kwargs
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                if self.logger:
                    self.logger.debug(f"Response received: {list(response_data.keys())}", context=context)
                
                # Capture thought
                if self.thought_capture:
                    modified_response = self.thought_capture.process_chunk(response_data)
                    if modified_response is not None:
                        if self.logger:
                            duration = self.logger.stop_timer("llm_call", context=context)
                            self.logger.success(f"Call complete in {duration:.2f}s: {len(modified_response)} chars", context=context)
                        return modified_response
                
                result = response_data.get("response", "")
                
                if self.logger:
                    duration = self.logger.stop_timer("llm_call", context=context)
                    self.logger.success(f"Call complete in {duration:.2f}s: {len(result)} chars", context=context)
                
                return result
            
            else:
                if self.logger:
                    self.logger.warning(f"API call failed (status {response.status_code}), using fallback", context=context)
                return self._fallback_call(prompt, stop, run_manager, **kwargs)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"API call error: {e}, using fallback", context=context, exc_info=True)
            return self._fallback_call(prompt, stop, run_manager, **kwargs)
    
    def _stream(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> Iterator[GenerationChunk]:
        """Stream with comprehensive logging"""
        context = LogContext(model=self.model)
        
        try:
            if self.thought_capture:
                self.thought_capture.reset()
            
            if self.logger:
                self.logger.info(f"Starting stream: {len(prompt)} char prompt", context=context)
                self.logger.start_timer("llm_stream")
            
            api_kwargs = self._build_api_kwargs(kwargs)
            
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": True,
                    **api_kwargs
                },
                stream=True,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                chunk_count = 0
                total_chars = 0
                
                for line in response.iter_lines():
                    if line:
                        try:
                            json_response = json.loads(line)
                            
                            # Process thoughts
                            if self.thought_capture:
                                modified_response = self.thought_capture.process_chunk(json_response)
                                
                                if modified_response is None:
                                    continue
                                
                                chunk_text = modified_response
                            else:
                                chunk_text = json_response.get('response', '')
                            
                            # Yield
                            if chunk_text:
                                chunk_count += 1
                                total_chars += len(chunk_text)
                                
                                chunk = GenerationChunk(text=chunk_text)
                                if run_manager:
                                    run_manager.on_llm_new_token(chunk_text)
                                yield chunk
                                    
                        except json.JSONDecodeError as e:
                            if self.logger:
                                self.logger.trace(f"JSON decode error: {e}", context=context)
                            continue
                        
                        except Exception as e:
                            if self.logger:
                                self.logger.error(f"Chunk processing error: {e}", context=context)
                            continue
                
                if self.logger:
                    duration = self.logger.stop_timer("llm_stream", context=context)
                    self.logger.success(f"Stream complete in {duration:.2f}s: {chunk_count} chunks, {total_chars} chars", context=context)
            
            else:
                if self.logger:
                    self.logger.warning(f"Stream failed (status {response.status_code}), using fallback", context=context)
                yield from self._fallback_stream(prompt, stop, run_manager, **kwargs)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Stream error: {e}, using fallback", context=context, exc_info=True)
            yield from self._fallback_stream(prompt, stop, run_manager, **kwargs)
    
    def _build_api_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build kwargs with logging"""
        api_kwargs = {k: v for k, v in kwargs.items() 
                     if k not in ['run_manager', 'callbacks'] and 
                     isinstance(v, (str, int, float, bool, list, dict, type(None)))}
        
        if self.top_k != 40:
            api_kwargs['top_k'] = self.top_k
        if self.top_p != 0.9:
            api_kwargs['top_p'] = self.top_p
        if self.num_predict != -1:
            api_kwargs['num_predict'] = self.num_predict
        
        if self.logger and api_kwargs:
            self.logger.trace(f"API kwargs: {api_kwargs}", context=LogContext(model=self.model))
        
        return api_kwargs
    
    def _fallback_call(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> str:
        """Fallback with logging"""
        context = LogContext(model=self.model)
        
        if self.logger:
            self.logger.info("Using local fallback for call", context=context)
        
        fallback_llm = Ollama(
            model=self.model, 
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )
        
        call_kwargs = {k: v for k, v in kwargs.items() if k != 'run_manager'}
        if run_manager:
            call_kwargs['run_manager'] = run_manager
        
        return fallback_llm.invoke(prompt, stop=stop, **call_kwargs)
    
    def _fallback_stream(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs):
        """Fallback stream with logging"""
        context = LogContext(model=self.model)
        
        if self.logger:
            self.logger.info("Using local fallback for stream", context=context)
        
        fallback_llm = Ollama(
            model=self.model, 
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )
        
        stream_kwargs = {k: v for k, v in kwargs.items() if k != 'run_manager'}
        if run_manager:
            stream_kwargs['run_manager'] = run_manager
        
        chunk_count = 0
        for chunk in fallback_llm.stream(prompt, stop=stop, **stream_kwargs):
            chunk_count += 1
            
            if isinstance(chunk, str):
                yield GenerationChunk(text=chunk)
            elif hasattr(chunk, 'text'):
                yield chunk
            elif hasattr(chunk, 'content'):
                yield GenerationChunk(text=chunk.content)
            else:
                yield GenerationChunk(text=str(chunk))
        
        if self.logger:
            self.logger.debug(f"Fallback stream complete: {chunk_count} chunks", context=context)
    
    async def _acall(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        return self._call(prompt, stop, **kwargs)


if __name__ == "__main__":
    from Vera.Configuration.config_manager import OllamaConfig
    from Vera.Logging.logging import get_logger, LoggingConfig, LogLevel
    
    log_config = LoggingConfig(
        global_level=LogLevel.DEBUG,
        show_ollama_raw_chunks=False,
        enable_colors=True,
        box_thoughts=True
    )
    
    logger = get_logger("ollama", log_config)
    
    config = OllamaConfig(
        api_url="http://localhost:11434",
        timeout=2400,
        use_local_fallback=True
    )
    
    manager = OllamaConnectionManager(config, logger=logger)
    
    manager.test_connection()
    
    logger.info("Available models:")
    models = manager.list_models()
    for model in models[:5]:
        logger.info(f"  • {model['model']}")
    
    if models:
        test_model = models[0]['model']
        logger.info(f"\nDetailed info for {test_model}:")
        manager.print_model_info(test_model)
        
        llm = manager.create_llm(test_model, temperature=0.8)
        logger.success(f"Created LLM: {llm}")
        
        logger.info("\n" + "="*60)
        logger.info("TESTING LLM")
        logger.info("="*60 + "\n")
        
        response = llm.invoke("Explain quantum entanglement in one sentence.")
        
        logger.info("\n" + "="*60)
        logger.success("COMPLETE")
        logger.info("="*60)