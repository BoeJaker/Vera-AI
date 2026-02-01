# Vera/Orchestration/ollama_integration.py

"""
Integration between Task Orchestrator and Multi-Instance Ollama Manager
"""

from typing import Any, Dict, Iterator, Optional
from Vera.Orchestration.orchestrator import task, TaskType, Priority, extract_chunk_text
from Vera.Ollama.multi_instance_manager import MultiInstanceOllamaManager
from Vera.Configuration.config_manager import OllamaConfig

# Global manager instance (initialized once)
_ollama_manager: Optional[MultiInstanceOllamaManager] = None


def initialize_ollama_orchestration(config: OllamaConfig, logger=None):
    """
    Initialize Ollama manager for orchestration.
    Call this once at startup before using LLM tasks.
    """
    global _ollama_manager
    
    if _ollama_manager is None:
        _ollama_manager = MultiInstanceOllamaManager(
            config=config,
            logger=logger
        )
        
        # Test connection
        _ollama_manager.test_connection()
        
        if logger:
            logger.success(
                f"Ollama orchestration initialized with {len(_ollama_manager.pool.instances)} instances"
            )
    
    return _ollama_manager


def get_ollama_manager() -> MultiInstanceOllamaManager:
    """Get the global Ollama manager instance"""
    if _ollama_manager is None:
        raise RuntimeError(
            "Ollama manager not initialized. Call initialize_ollama_orchestration() first."
        )
    return _ollama_manager


# ============================================================================
# REGISTERED TASKS
# ============================================================================

@task(
    name="llm.generate",
    task_type=TaskType.LLM,
    priority=Priority.HIGH,
    estimated_duration=5.0,
    requires_gpu=False,  # Ollama handles GPU allocation
    requires_cpu_cores=1,
    memory_mb=2048
)
def llm_generate(
    prompt: str,
    model: str,
    temperature: float = 0.7,
    stream: bool = False,
    **kwargs
) -> Iterator[str] | str:
    """
    Generate text using Ollama with automatic instance routing.
    
    Args:
        prompt: Input prompt
        model: Model name (will auto-add :latest if no tag)
        temperature: Generation temperature
        stream: Whether to stream results (generator)
        **kwargs: Additional LLM parameters (top_k, top_p, etc.)
    
    Returns:
        Generator yielding chunks if stream=True, else complete text
    """
    manager = get_ollama_manager()
    
    # Create LLM with intelligent routing (finds instances with model)
    llm = manager.create_llm(
        model=model,
        temperature=temperature,
        **kwargs
    )
    
    if stream:
        # Stream mode - yield chunks
        for chunk in llm.stream(prompt):
            # Extract text from chunk object
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
    else:
        # Non-stream mode - return complete result
        result = llm.invoke(prompt)
        return result


@task(
    name="llm.chat",
    task_type=TaskType.LLM,
    priority=Priority.HIGH,
    estimated_duration=5.0,
    requires_cpu_cores=1,
    memory_mb=2048
)
def llm_chat(
    messages: list,
    model: str,
    temperature: float = 0.7,
    stream: bool = False,
    **kwargs
) -> Iterator[str] | str:
    """
    Chat completion using Ollama with automatic instance routing.
    
    Args:
        messages: List of message dicts [{"role": "user", "content": "..."}]
        model: Model name
        temperature: Generation temperature
        stream: Whether to stream results
        **kwargs: Additional parameters
    
    Returns:
        Generator yielding chunks if stream=True, else complete text
    """
    manager = get_ollama_manager()
    
    # Convert messages to prompt (simple approach - you may want more sophisticated)
    prompt = "\n".join([
        f"{msg['role']}: {msg['content']}"
        for msg in messages
    ])
    
    llm = manager.create_llm(
        model=model,
        temperature=temperature,
        **kwargs
    )
    
    if stream:
        for chunk in llm.stream(prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
    else:
        return llm.invoke(prompt)


@task(
    name="llm.embed",
    task_type=TaskType.LLM,
    priority=Priority.NORMAL,
    estimated_duration=1.0,
    requires_cpu_cores=1,
    memory_mb=1024
)
def llm_embed(
    text: str | list[str],
    model: str = "nomic-embed-text:latest",
    **kwargs
) -> list[list[float]]:
    """
    Generate embeddings using Ollama.
    
    Args:
        text: Single text or list of texts
        model: Embedding model name
        **kwargs: Additional parameters
    
    Returns:
        List of embedding vectors
    """
    manager = get_ollama_manager()
    
    embeddings = manager.create_embeddings(model=model, **kwargs)
    
    if isinstance(text, str):
        return [embeddings.embed_query(text)]
    else:
        return embeddings.embed_documents(text)


@task(
    name="llm.pull_model",
    task_type=TaskType.BACKGROUND,
    priority=Priority.LOW,
    estimated_duration=300.0,  # Can take 5+ minutes
    requires_cpu_cores=1,
    memory_mb=512
)
def llm_pull_model(model: str, stream: bool = True) -> bool:
    """
    Pull/download a model from Ollama registry.
    
    Args:
        model: Model name to pull
        stream: Whether to stream download progress
    
    Returns:
        True if successful
    """
    manager = get_ollama_manager()
    return manager.pull_model(model, stream=stream)


@task(
    name="llm.list_models",
    task_type=TaskType.GENERAL,
    priority=Priority.NORMAL,
    estimated_duration=0.5,
    requires_cpu_cores=1,
    memory_mb=256
)
def llm_list_models() -> list[dict]:
    """
    List all available models across all Ollama instances.
    
    Returns:
        List of model metadata dicts
    """
    manager = get_ollama_manager()
    return manager.list_models()


@task(
    name="llm.get_stats",
    task_type=TaskType.GENERAL,
    priority=Priority.LOW,
    estimated_duration=0.1,
    requires_cpu_cores=1,
    memory_mb=128
)
def llm_get_stats() -> dict:
    """
    Get Ollama instance pool statistics.
    
    Returns:
        Dict with stats for each instance
    """
    manager = get_ollama_manager()
    return manager.get_pool_stats()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def submit_llm_task(
    orchestrator,
    prompt: str,
    model: str,
    stream: bool = False,
    **kwargs
) -> str:
    """
    Convenience function to submit LLM generation task.
    
    Usage:
        # Non-streaming
        task_id = submit_llm_task(orchestrator, "Explain quantum computing", "llama3.2:latest")
        result = orchestrator.wait_for_result(task_id, timeout=30)
        print(result.result)
        
        # Streaming
        task_id = submit_llm_task(orchestrator, "Write a story", "llama3.2:latest", stream=True)
        for chunk in orchestrator.stream_result(task_id):
            print(chunk, end='', flush=True)
    """
    return orchestrator.submit_task(
        "llm.generate",
        prompt=prompt,
        model=model,
        stream=stream,
        **kwargs
    )


def submit_chat_task(
    orchestrator,
    messages: list,
    model: str,
    stream: bool = False,
    **kwargs
) -> str:
    """
    Convenience function to submit chat task.
    """
    return orchestrator.submit_task(
        "llm.chat",
        messages=messages,
        model=model,
        stream=stream,
        **kwargs
    )