#!/usr/bin/env python3
# Vera/Ollama/manager.py (Updated with Unified Logging)

"""
Enhanced Ollama Connection Manager with Unified Logging
- Structured logging instead of print statements
- Model metadata retrieval
- Universal thought capture
- Performance tracking built-in
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

# Import LogContext for structured logging
try:
    from Vera.Logging.logging import LogContext
except ImportError:
    from Logging.logging import LogContext


@dataclass
class OllamaModelInfo:
    """Model information retrieved from Ollama"""
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
    
    # Inference parameters
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.9
    num_predict: int = -1
    stop: List[str] = field(default_factory=list)
    
    # Performance hints
    supports_thought: bool = False
    supports_streaming: bool = True
    supports_vision: bool = False
    
    def __str__(self):
        return f"Model({self.name}, {self.parameter_size}, ctx={self.context_length})"


class ThoughtCapture:
    """Universal thought capture system with integrated logging"""
    
    def __init__(self, enabled: bool = True, callback: Optional[Callable[[str], None]] = None, logger=None):
        self.enabled = enabled
        self.callback = callback
        self.logger = logger
        self.thought_buffer = []
        self.in_thought_mode = False
        self.chunk_count = 0
    
    def process_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Process a chunk and extract thought content if present.
        Supports multiple formats:
        - {"thought": "..."} (DeepSeek)
        - {"reasoning": "..."} (GPT-OSS)
        - {"thinking": "..."} (Generic)
        - Content wrapped in <think>...</think> tags
        
        Returns:
            - Modified response text (with thoughts removed) if content present
            - None if chunk was entirely thought content
            - Original response if no thought detected
        """
        # Log raw chunk if configured
        if self.logger:
            self.logger.raw_stream_chunk(chunk_data, self.chunk_count)
        
        self.chunk_count += 1
        
        if not self.enabled:
            return chunk_data.get('response', '')
        
        if self.logger:
            self.logger.trace(f"Processing chunk: {json.dumps(chunk_data, indent=2)[:200]}...")
        
        # Direct thought fields
        for field in ['thought', 'reasoning', 'thinking', 'internal']:
            if field in chunk_data and chunk_data[field]:
                thought = chunk_data[field]
                if self.logger:
                    self.logger.debug(f"Found thought in '{field}' field: {thought[:100]}...")
                self._handle_thought(thought)
                return chunk_data.get('response', '')
        
        # Check response content for thought markers
        response = chunk_data.get('response', '')
        if response:
            # Handle <think> tags
            if '<think>' in response:
                if self.logger:
                    self.logger.debug("Found <think> opening tag")
                
                self.in_thought_mode = True
                thought_start = response.find('<think>') + 7
                thought_end = response.find('</think>')
                
                if thought_end > thought_start:
                    # Complete thought in this chunk
                    thought = response[thought_start:thought_end]
                    if self.logger:
                        self.logger.debug(f"Complete thought in chunk: {thought[:100]}...")
                    self._handle_thought(thought)
                    self.in_thought_mode = False
                    clean_response = response[:response.find('<think>')] + response[thought_end + 8:]
                    return clean_response if clean_response else None
                else:
                    # Thought continues beyond this chunk
                    thought = response[thought_start:]
                    if self.logger:
                        self.logger.debug(f"Partial thought (start): {thought[:100]}...")
                    self.thought_buffer.append(thought)
                    prefix = response[:response.find('<think>')]
                    return prefix if prefix else None
            
            elif '</think>' in response and self.in_thought_mode:
                # End of thought
                if self.logger:
                    self.logger.debug("Found </think> closing tag")
                
                thought_end = response.find('</think>')
                thought = response[:thought_end]
                if self.logger:
                    self.logger.debug(f"Partial thought (end): {thought[:100]}...")
                
                self.thought_buffer.append(thought)
                self._flush_thought_buffer()
                self.in_thought_mode = False
                suffix = response[thought_end + 8:]
                return suffix if suffix else None
            
            elif self.in_thought_mode:
                # Middle of thought
                if self.logger:
                    self.logger.debug(f"Middle of thought: {response[:100]}...")
                self.thought_buffer.append(response)
                return None
            
            else:
                # No thought markers
                return response
        
        return None
    
    def _handle_thought(self, thought: str):
        """Handle extracted thought content"""
        if not thought:
            return
        
        # Use logger if available
        if self.logger:
            self.logger.thought(thought)
        else:
            # Fallback to direct output
            sys.stdout.write("\n" + "="*60 + "\n")
            sys.stdout.write("💭 THOUGHT CAPTURED:\n")
            sys.stdout.write("="*60 + "\n")
            sys.stdout.write(thought)
            sys.stdout.write("\n" + "="*60 + "\n\n")
            sys.stdout.flush()
        
        if self.callback:
            try:
                self.callback(thought)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Thought callback error: {e}")
    
    def _flush_thought_buffer(self):
        """Flush accumulated thought buffer"""
        if self.thought_buffer:
            full_thought = "".join(self.thought_buffer)
            if self.logger:
                self.logger.debug(f"Flushing thought buffer ({len(full_thought)} chars)")
            self._handle_thought(full_thought)
            self.thought_buffer.clear()
    
    def reset(self):
        """Reset thought capture state"""
        if self.logger:
            self.logger.trace("Resetting thought capture state")
        self.thought_buffer.clear()
        self.in_thought_mode = False
        self.chunk_count = 0


class OllamaConnectionManager:
    """
    Enhanced Ollama connection manager with unified logging
    """
    
    def __init__(self, config=None, thought_callback: Optional[Callable[[str], None]] = None, logger=None):
        """
        Initialize Ollama manager with unified logging
        
        Args:
            config: OllamaConfig object or None for defaults
            thought_callback: Optional callback for thought output
            logger: VeraLogger instance for structured logging
        """
        # Import here to avoid circular dependency
        if config is None:
            from Vera.Configuration.config_manager import OllamaConfig
            config = OllamaConfig()
        
        self.config = config
        self.api_url = config.api_url
        self.timeout = config.timeout
        self.use_local = False
        self.connection_tested = False
        self.model_metadata_cache: Dict[str, OllamaModelInfo] = {}
        
        # Setup logging
        if logger is None:
            # Create basic logger if none provided
            from Vera.Logging.logging import get_logger, LoggingConfig, LogLevel
            log_config = LoggingConfig(global_level=LogLevel.INFO)
            self.logger = get_logger("ollama", log_config)
        else:
            self.logger = logger
        
        # Create thought capture with logger
        self.thought_capture = ThoughtCapture(
            enabled=getattr(config, 'enable_thought_capture', True),
            callback=thought_callback,
            logger=self.logger
        )
    
    def test_connection(self) -> bool:
        """Test if Ollama API is accessible"""
        self.logger.debug(f"Testing connection to {self.api_url}")
        
        try:
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.logger.success(f"Connected to API at {self.api_url}")
                self.use_local = False
                self.connection_tested = True
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self.logger.warning(f"API connection failed: {e}")
        
        if self.config.use_local_fallback:
            self.logger.info("Falling back to local Ollama process")
            self.use_local = True
            self.connection_tested = True
            return True
        
        self.logger.error("Connection failed and no fallback available")
        return False
    
    def list_models(self) -> List[Dict]:
        """List available models"""
        if not self.connection_tested:
            self.test_connection()
        
        self.logger.debug("Listing available models")
        
        for attempt in range(self.config.connection_retry_attempts):
            if not self.use_local:
                try:
                    response = requests.get(f"{self.api_url}/api/tags", timeout=5)
                    if response.status_code == 200:
                        models_data = response.json().get("models", [])
                        model_list = [{"model": m.get("name", m.get("model", ""))} for m in models_data]
                        self.logger.success(f"Found {len(model_list)} models")
                        return model_list
                except Exception as e:
                    if attempt < self.config.connection_retry_attempts - 1:
                        self.logger.debug(f"Retry {attempt + 1}/{self.config.connection_retry_attempts}")
                        import time
                        time.sleep(self.config.connection_retry_delay)
                        continue
                    self.logger.warning(f"API list failed: {e}")
                    self.use_local = True
            
            try:
                models = ollama.list()["models"]
                self.logger.success(f"Found {len(models)} models (local)")
                return models
            except Exception as e:
                if attempt < self.config.connection_retry_attempts - 1:
                    import time
                    time.sleep(self.config.connection_retry_delay)
                    continue
                self.logger.error(f"Connection failed: {e}")
                raise RuntimeError(f"[Ollama] Connection failed: {e}")
        
        return []
    
    def get_model_metadata(self, model_name: str, force_refresh: bool = False) -> OllamaModelInfo:
        """
        Retrieve detailed model metadata including token limits
        
        Args:
            model_name: Name of the model
            force_refresh: Force refresh from API
        
        Returns:
            OllamaModelInfo object with comprehensive model information
        """
        # Check cache
        if not force_refresh and model_name in self.model_metadata_cache:
            self.logger.trace(f"Using cached metadata for {model_name}")
            return self.model_metadata_cache[model_name]
        
        self.logger.debug(f"Fetching metadata for {model_name}")
        model_info = OllamaModelInfo(name=model_name)
        
        try:
            # Try API endpoint
            if not self.use_local:
                try:
                    response = requests.post(
                        f"{self.api_url}/api/show",
                        json={"name": model_name},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        self._parse_model_metadata(model_info, data)
                except Exception as e:
                    self.logger.debug(f"API metadata fetch failed: {e}")
            
            # Fallback to local
            if self.use_local or model_info.context_length == 2048:
                try:
                    data = ollama.show(model_name)
                    self._parse_model_metadata(model_info, data)
                except Exception as e:
                    self.logger.debug(f"Local metadata fetch failed: {e}")
            
            # Cache the metadata
            self.model_metadata_cache[model_name] = model_info
            
            self.logger.debug(
                f"Model metadata: {model_info.name} "
                f"(ctx={model_info.context_length}, "
                f"thought={model_info.supports_thought})"
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to get metadata for {model_name}: {e}")
        
        return model_info
    
    def _parse_model_metadata(self, model_info: OllamaModelInfo, data: Dict[str, Any]):
        """Parse model metadata from Ollama response"""
        # Basic info
        if 'details' in data:
            details = data['details']
            model_info.family = details.get('family', '')
            model_info.parameter_size = details.get('parameter_size', '')
            model_info.quantization_level = details.get('quantization_level', '')
            model_info.format = details.get('format', '')
        
        # Model file info
        if 'modelfile' in data:
            modelfile = data['modelfile']
            
            # Parse context length
            if 'num_ctx' in modelfile:
                try:
                    model_info.context_length = int(modelfile.split('num_ctx')[1].split()[0])
                except:
                    pass
        
        # Parameters from model info
        if 'model_info' in data:
            info = data['model_info']
            
            # Context length
            for key in ['context_length', 'max_position_embeddings', 'n_ctx']:
                if key in info:
                    model_info.context_length = info[key]
                    break
            
            # Embedding dimensions
            for key in ['embedding_length', 'hidden_size', 'n_embd']:
                if key in info:
                    model_info.embedding_length = info[key]
                    break
        
        # License and metadata
        model_info.license = data.get('license', '')
        model_info.modified_at = data.get('modified_at', '')
        
        if 'size' in data:
            model_info.size = data['size']
        
        # Detect capabilities
        model_lower = model_info.name.lower()
        
        # Thought capability
        model_info.supports_thought = any(x in model_lower for x in [
            'deepseek', 'gpt-oss', 'reasoning', 'o1', 'qwen-think', 'r1'
        ])
        
        # Vision capability
        model_info.supports_vision = any(x in model_lower for x in [
            'vision', 'llava', 'minicpm', 'cogvlm', 'internvl'
        ])
        
        model_info.supports_streaming = True
    
    def pull_model(self, model_name: str, stream: bool = True) -> bool:
        """Pull/download a model"""
        if not self.connection_tested:
            self.test_connection()
        
        self.logger.info(f"Pulling model: {model_name}")
        
        if not self.use_local:
            try:
                response = requests.post(
                    f"{self.api_url}/api/pull",
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
                                    pct = (data['completed'] / data['total']) * 100
                                    self.logger.debug(f"{status}: {pct:.1f}%")
                                else:
                                    self.logger.debug(status)
                            except:
                                pass
                
                if response.status_code == 200:
                    self.logger.success(f"Model pulled: {model_name}")
                    return True
                    
            except Exception as e:
                self.logger.warning(f"API pull failed: {e}")
                self.use_local = True
        
        try:
            ollama.pull(model_name)
            self.logger.success(f"Model pulled (local): {model_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to pull model: {e}")
            return False
    
    def create_llm(
        self, 
        model: str, 
        temperature: Optional[float] = None,
        **kwargs
    ):
        """Create an Ollama LLM instance with logging support"""
        if not self.connection_tested:
            self.test_connection()
        
        # Get model metadata
        model_info = self.get_model_metadata(model)
        
        # Use config temperature if not specified
        if temperature is None:
            temperature = self.config.temperature if hasattr(self.config, 'temperature') else 0.7
        
        # Merge kwargs with defaults
        merged_kwargs = {
            'top_k': getattr(self.config, 'top_k', model_info.top_k),
            'top_p': getattr(self.config, 'top_p', model_info.top_p),
            'num_predict': getattr(self.config, 'num_predict', model_info.num_predict),
        }
        merged_kwargs.update(kwargs)
        
        if not self.use_local:
            from Vera.Logging.logging import LogContext
            self.logger.info(
                f"Creating LLM (API mode)",
                context=LogContext(
                    model=model,
                    extra={
                        'mode': 'api',
                        'context_length': model_info.context_length,
                        'supports_thought': model_info.supports_thought,
                        'temperature': temperature
                    }
                )
            )
            
            return OllamaAPIWrapper(
                model=model,
                temperature=temperature,
                api_url=self.api_url,
                timeout=self.timeout,
                model_info=model_info,
                thought_capture=self.thought_capture,
                logger=self.logger,
                **merged_kwargs
            )
        else:
            self.logger.info(
                f"Creating LLM (local mode)",
                context=LogContext(
                    model=model,
                    extra={
                        'mode': 'local',
                        'context_length': model_info.context_length,
                        'temperature': temperature
                    }
                )
            )
            
            return Ollama(
                model=model,
                temperature=temperature,
                **merged_kwargs
            )
    
    def create_embeddings(self, model: str, **kwargs):
        """Create an Ollama embeddings instance"""
        if not self.connection_tested:
            self.test_connection()
        
        model_info = self.get_model_metadata(model)
        
        self.logger.debug(
            f"Creating embeddings",
            context=LogContext(
                model=model,
                extra={'embedding_dim': model_info.embedding_length}
            )
        )
        
        if not self.use_local:
            return OllamaEmbeddings(
                model=model,
                base_url=self.api_url,
                **kwargs
            )
        else:
            return OllamaEmbeddings(
                model=model,
                **kwargs
            )
    
    def print_model_info(self, model_name: str):
        """Pretty print model information"""
        model_info = self.get_model_metadata(model_name)
        
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
        self.logger.info("=" * 60)


class OllamaAPIWrapper(LLM):
    """Enhanced Ollama API wrapper with thought capture and logging"""
    
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
        """Call Ollama API with thought capture and logging"""
        try:
            if self.thought_capture:
                self.thought_capture.reset()
            
            if self.logger:
                self.logger.start_timer("llm_call")
                self.logger.debug(f"Calling API", context=LogContext(model=self.model))
            
            api_kwargs = self._build_api_kwargs(kwargs)
            
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
                
                # Capture thought if present
                if self.thought_capture:
                    modified_response = self.thought_capture.process_chunk(response_data)
                    if modified_response is not None:
                        if self.logger:
                            duration = self.logger.stop_timer("llm_call")
                        return modified_response
                
                result = response_data.get("response", "")
                
                if self.logger:
                    duration = self.logger.stop_timer("llm_call")
                    self.logger.debug(f"API call complete: {len(result)} chars")
                
                return result
            else:
                if self.logger:
                    self.logger.warning(f"API request failed ({response.status_code}), using fallback")
                return self._fallback_call(prompt, stop, run_manager, **kwargs)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"API call error: {e}", exc_info=True)
            return self._fallback_call(prompt, stop, run_manager, **kwargs)
    
    def _stream(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> Iterator[GenerationChunk]:
        """Stream responses with thought capture and logging"""
        try:
            if self.thought_capture:
                self.thought_capture.reset()
            
            if self.logger:
                self.logger.debug(f"Starting stream", context=LogContext(model=self.model))
            
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
                for line in response.iter_lines():
                    if line:
                        try:
                            json_response = json.loads(line)
                            
                            # Process for thoughts
                            if self.thought_capture:
                                modified_response = self.thought_capture.process_chunk(json_response)
                                
                                if modified_response is None:
                                    # Entirely thought content
                                    continue
                                
                                chunk_text = modified_response
                            else:
                                chunk_text = json_response.get('response', '')
                            
                            # Yield chunk
                            if chunk_text:
                                chunk = GenerationChunk(text=chunk_text)
                                if run_manager:
                                    run_manager.on_llm_new_token(chunk_text)
                                yield chunk
                                    
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            if self.logger:
                                self.logger.error(f"Chunk processing error: {e}")
                            continue
            else:
                if self.logger:
                    self.logger.warning(f"Stream request failed ({response.status_code}), using fallback")
                yield from self._fallback_stream(prompt, stop, run_manager, **kwargs)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Stream error: {e}", exc_info=True)
            yield from self._fallback_stream(prompt, stop, run_manager, **kwargs)
    
    def _build_api_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build API kwargs with filtering"""
        api_kwargs = {k: v for k, v in kwargs.items() 
                     if k not in ['run_manager', 'callbacks'] and 
                     isinstance(v, (str, int, float, bool, list, dict, type(None)))}
        
        if self.top_k != 40:
            api_kwargs['top_k'] = self.top_k
        if self.top_p != 0.9:
            api_kwargs['top_p'] = self.top_p
        if self.num_predict != -1:
            api_kwargs['num_predict'] = self.num_predict
        
        return api_kwargs
    
    def _fallback_call(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> str:
        """Fallback to local Ollama"""
        if self.logger:
            self.logger.debug("Using fallback local call")
        
        fallback_llm = Ollama(
            model=self.model, 
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )
        call_kwargs = kwargs.copy()
        if run_manager:
            call_kwargs['run_manager'] = run_manager
        return fallback_llm.invoke(prompt, stop=stop, **call_kwargs)
    
    def _fallback_stream(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs):
        """Fallback streaming to local Ollama"""
        if self.logger:
            self.logger.debug("Using fallback local stream")
        
        fallback_llm = Ollama(
            model=self.model, 
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )
        stream_kwargs = kwargs.copy()
        if run_manager:
            stream_kwargs['run_manager'] = run_manager
        
        for chunk in fallback_llm.stream(prompt, stop=stop, **stream_kwargs):
            if isinstance(chunk, str):
                yield GenerationChunk(text=chunk)
            elif hasattr(chunk, 'text'):
                yield chunk
            elif hasattr(chunk, 'content'):
                yield GenerationChunk(text=chunk.content)
            else:
                yield GenerationChunk(text=str(chunk))
    
    async def _acall(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Async call - falls back to sync"""
        return self._call(prompt, stop, **kwargs)


# Example usage
if __name__ == "__main__":
    from Vera.Configuration.config_manager import OllamaConfig
    from Vera.Logging.logging import get_logger, LoggingConfig, LogLevel
    
    # Create logging config
    log_config = LoggingConfig(
        global_level=LogLevel.DEBUG,
        show_ollama_raw_chunks=False,  # Set to True for full verbosity
        enable_colors=True,
        box_thoughts=True
    )
    
    # Create logger
    logger = get_logger("ollama", log_config)
    
    # Create Ollama config
    config = OllamaConfig(
        api_url="http://localhost:11434",
        timeout=2400,
        use_local_fallback=True
    )
    
    # Create manager with logger
    manager = OllamaConnectionManager(
        config, 
        logger=logger
    )
    
    # Test connection
    manager.test_connection()
    
    # List models
    logger.info("Available models:")
    models = manager.list_models()
    for model in models[:5]:
        logger.info(f"  • {model['model']}")
    
    # Get detailed info
    if models:
        test_model = models[0]['model']
        logger.info(f"\nDetailed info for {test_model}:")
        manager.print_model_info(test_model)
        
        # Create LLM
        llm = manager.create_llm(test_model, temperature=0.8)
        logger.success(f"Created LLM: {llm}")
        
        # Test with prompt
        logger.info("\n" + "="*60)
        logger.info("TESTING LLM")
        logger.info("="*60 + "\n")
        
        response = llm.invoke("Explain quantum entanglement in one sentence.")
        
        logger.info("\n" + "="*60)
        logger.success("COMPLETE")
        logger.info("="*60)