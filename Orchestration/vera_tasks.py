"""
Vera Task Registrations (Enhanced Logging Version with Streaming Thoughts)
===========================================================================
Register all Vera tasks with comprehensive logging including:
- Full prompt visibility
- Clear fallback paths with reasons
- Agent routing decisions
- Performance metrics
- Tool execution details
- REAL-TIME THOUGHT STREAMING (including proactive tasks)

Enhanced Logging Features:
- Prompts logged at DEBUG level (truncated) and TRACE level (full)
- Fallback reasons clearly stated
- Agent selection logic visible
- Tool chains tracked step-by-step
- Performance context for all operations
- Thoughts stream as they're generated, not buffered
- Proactive tasks now stream thoughts to UI
"""

from Vera.Orchestration.orchestration import task, proactive_task, TaskType, Priority
from Vera.Logging.logging import LogContext
import time
import json

def extract_chunk_text(chunk):
    """
    Extract text from chunk object - ALWAYS returns a string, never dict or None.
    Handles all common chunk formats safely.
    """
    # Handle None immediately
    if chunk is None:
        return ""
    
    # Handle strings directly (fast path)
    if isinstance(chunk, str):
        return chunk
    
    # Handle dict chunks (some LLMs return dicts)
    if isinstance(chunk, dict):
        # Try common dict keys in order of preference
        for key in ['text', 'content', 'message', 'data', 'output', 'delta']:
            if key in chunk and chunk[key] is not None:
                val = chunk[key]
                # Recursively extract if nested
                if isinstance(val, dict):
                    return extract_chunk_text(val)
                return str(val) if not isinstance(val, str) else val
        # If no recognized key, convert whole dict to string
        return str(chunk)
    
    # Handle objects with text/content attributes
    if hasattr(chunk, 'text') and chunk.text is not None:
        val = chunk.text
        return str(val) if not isinstance(val, str) else val
    
    if hasattr(chunk, 'content') and chunk.content is not None:
        val = chunk.content
        return str(val) if not isinstance(val, str) else val
    
    # Ultimate fallback: convert to string
    try:
        return str(chunk)
    except Exception:
        return ""


def truncate_text(text: str, max_length: int = 200, show_length: bool = True) -> str:
    """Truncate text for logging with length indicator"""
    if len(text) <= max_length:
        return text
    
    suffix = f"... ({len(text)} chars total)" if show_length else "..."
    return text[:max_length] + suffix


def log_prompt(logger, prompt: str, context: LogContext, label: str = "Prompt"):
    """Log a prompt at both DEBUG (truncated) and TRACE (full) levels"""
    if logger:
        # DEBUG: Show truncated version
        logger.debug(
            f"{label}: {truncate_text(prompt, max_length=150)}",
            context=context
        )
        
        # TRACE: Show full prompt
        logger.trace(
            f"{label} (FULL):\n{'─' * 60}\n{prompt}\n{'─' * 60}",
            context=context
        )


def log_fallback(logger, reason: str, agent_error: Exception, context: LogContext):
    """Log fallback with clear reason and error details"""
    if logger:
        logger.warning(
            f"🔄 FALLBACK TRIGGERED - Reason: {reason} - {agent_error} - {context}",
            context=context
        )
        logger.debug(
            f"Agent error details: {type(agent_error).__name__}: {str(agent_error)}",
            context=context
        )


def log_agent_selection(logger, task_type: str, agent_name: str, context: LogContext, 
                       extra_info: dict = None):
    """Log agent selection decision with details"""
    if logger:
        info_str = f" ({json.dumps(extra_info)})" if extra_info else ""
        logger.info(
            f"🎯 Agent selected: {agent_name} for {task_type}{info_str}",
            context=LogContext(agent=agent_name, extra={**context.extra, 'task_type': task_type})
        )
    
# ============================================================================
# AGENT INTEGRATION SETUP
# ============================================================================

try:
    from Vera.Orchestration.agent_integration import AgentTaskRouter
    AGENTS_AVAILABLE = True
    print("[TaskRegistrations] ✓ Agent integration available")
except ImportError:
    AGENTS_AVAILABLE = False
    AgentTaskRouter = None
    print("[TaskRegistrations] ⚠ Agent integration not available - using fallbacks")


def _get_router(vera_instance):
    """Get agent router if available, otherwise None"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    
    if not AGENTS_AVAILABLE:
        if logger:
            logger.debug(
                "Agent system unavailable - module not imported",
                context=LogContext(extra={'component': 'task_router', 'reason': 'module_not_found'})
            )
        return None
    
    if not hasattr(vera_instance, '_agent_router_cache'):
        if hasattr(vera_instance, 'agents') and vera_instance.agents:
            vera_instance._agent_router_cache = AgentTaskRouter(vera_instance)
            if logger:
                agent_count = len(vera_instance.agents.list_loaded_agents())
                agent_names = vera_instance.agents.list_loaded_agents()
                logger.success(
                    f"Agent router initialized with {agent_count} agents: {', '.join(str(agent_names))}",
                    context=LogContext(extra={'component': 'task_router', 'agents': agent_names})
                )
        else:
            vera_instance._agent_router_cache = None
            if logger:
                logger.debug(
                    "Agent system not configured in Vera instance",
                    context=LogContext(extra={'component': 'task_router', 'reason': 'not_configured'})
                )
    
    return vera_instance._agent_router_cache


# ============================================================================
# STREAMING LLM TASKS (WITH REAL-TIME THOUGHT STREAMING)
# ============================================================================

@task("llm.triage", task_type=TaskType.LLM, priority=Priority.CRITICAL, estimated_duration=2.0)
def llm_triage(vera_instance, query: str):
    """
    Triage query to determine routing.
    Streams response as it's generated WITH real-time thoughts.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'llm.triage', 'query_length': len(query)})
    
    if logger:
        logger.info(f"🔍 Triage task starting", context=context)
        logger.start_timer("llm_triage")
    
    router = _get_router(vera_instance)
    
    # Try agent first
    if router:
        try:
            agent_name = router.get_agent_for_task('triage')
            log_agent_selection(logger, 'triage', agent_name, context)
            
            llm = router.create_llm_for_agent(agent_name)
            
            focus = vera_instance.focus_manager.focus if hasattr(vera_instance, 'focus_manager') else 'None'
            triage_prompt = f"Current focus: {focus}\n\nQuery: {query}"
            
            log_prompt(logger, triage_prompt, LogContext(agent=agent_name, extra=context.extra), "Triage prompt")
            
            if logger:
                logger.debug(
                    f"Executing triage with focus: {focus}",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'focus': focus})
                )
            
            chunk_count = 0
            response_preview = ""
            for chunk in vera_instance._stream_with_thought_polling(llm, triage_prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                chunk_count += 1
                
                try:
                    if len(response_preview) < 50 and chunk_text:
                        response_preview += str(chunk_text)
                except Exception:
                    pass
                
                yield chunk_text
            yield "\n"  # Ensure newline at end
            if logger:
                duration = logger.stop_timer("llm_triage", context=LogContext(agent=agent_name, extra=context.extra))
                logger.success(
                    f"Triage complete via agent: {agent_name} | {chunk_count} chunks | Preview: {truncate_text(response_preview, 50)}",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration})
                )
            return
            
        except Exception as e:
            log_fallback(logger, "Agent triage execution failed", e, context)
    
    # Original fallback
    if logger:
        logger.info("Using fallback triage (fast_llm)", context=context)
    
    focus = vera_instance.focus_manager.focus if hasattr(vera_instance, 'focus_manager') else 'None'
    triage_prompt = f"""
    Classify this Query into one of the following categories:
        - 'focus'      → Change the focus of background thought.
        - 'proactive'  → Trigger proactive thinking.
        - 'simple'     → Simple textual response.
        - 'toolchain'  → Requires a series of tools or step-by-step planning.
        - 'reasoning'  → Requires deep reasoning.
        - 'complex'    → Complex written response with high-quality output.

    Current focus: {focus}

    Query: {query}

    Respond with a single classification term (e.g., 'simple', 'toolchain', 'complex') on the first line. Nothing else
    """
    
    log_prompt(logger, triage_prompt, context, "Fallback triage prompt")
    
    chunk_count = 0
    response_preview = ""
    for chunk in vera_instance._stream_with_thought_polling(vera_instance.fast_llm, triage_prompt):
        chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
        chunk_count += 1
        
        try:
            if len(response_preview) < 50 and chunk_text:
                response_preview += str(chunk_text)
        except Exception:
            pass
        
        yield chunk_text
    
    if logger:
        duration = logger.stop_timer("llm_triage", context=context)
        logger.success(
            f"Triage complete via fallback | {chunk_count} chunks | Preview: {truncate_text(response_preview, 50)}",
            context=LogContext(extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration, 'fallback': True})
        )


@task("llm.generate", task_type=TaskType.LLM, priority=Priority.HIGH, estimated_duration=10.0)
def llm_generate(vera_instance, llm_type: str, prompt: str, **kwargs):
    """
    Generate text using specified LLM.
    Streams response as it's generated WITH real-time thoughts.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    with_memory = kwargs.get('with_memory', False)
    context = LogContext(extra={
        'component': 'task',
        'task': 'llm.generate',
        'llm_type': llm_type,
        'prompt_length': len(prompt),
        'with_memory': with_memory
    })
    
    if logger:
        logger.info(
            f"📝 Generate task starting: type={llm_type}, memory={with_memory}",
            context=context
        )
        logger.start_timer("llm_generate")
    
    router = _get_router(vera_instance)
    
    # Try agent routing
    if router:
        try:
            agent_type_map = {
                'fast': 'conversation',
                'intermediate': 'planning',
                'deep': 'review',
                'reasoning': 'reasoning'
            }
            
            agent_type = agent_type_map.get(llm_type, 'conversation')
            agent_name = router.get_agent_for_task(agent_type)
            
            log_agent_selection(
                logger, agent_type, agent_name, context,
                extra_info={'llm_type': llm_type, 'mapped_to': agent_type}
            )
            
            llm = router.create_llm_for_agent(agent_name)
            memory_config = router.get_agent_memory_config(agent_name)
            
            # Build prompt with memory if requested
            if with_memory and memory_config.get('use_vector', True):
                past_context = ""
                if hasattr(vera_instance, 'memory'):
                    past_context = vera_instance.memory.load_memory_variables(
                        {"input": prompt}
                    ).get("chat_history", "")
                    
                    if logger:
                        logger.debug(
                            f"Loaded memory context: {len(past_context)} chars",
                            context=LogContext(agent=agent_name, extra={**context.extra, 'memory_size': len(past_context)})
                        )
                
                full_prompt = f"Previous conversation:\n{past_context}\n\nUser query: {prompt}"
            else:
                full_prompt = prompt
                if logger and with_memory:
                    logger.debug(
                        "Memory requested but disabled in agent config",
                        context=LogContext(agent=agent_name, extra=context.extra)
                    )
            
            log_prompt(logger, full_prompt, LogContext(agent=agent_name, extra=context.extra), "Generation prompt")
            
            chunk_count = 0
            response_preview = ""
            for chunk in vera_instance._stream_with_thought_polling(llm, full_prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                chunk_count += 1
                
                try:
                    if len(response_preview) < 100 and chunk_text:
                        response_preview += str(chunk_text)
                except Exception:
                    pass
                
                yield chunk_text
            
            if logger:
                duration = logger.stop_timer("llm_generate", context=LogContext(agent=agent_name, extra=context.extra))
                logger.success(
                    f"Generation complete via agent: {agent_name} | {chunk_count} chunks | {len(response_preview)} chars generated",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration})
                )
            return
            
        except Exception as e:
            log_fallback(logger, f"Agent generation failed for {llm_type}", e, context)
    
    # Original fallback
    llm_map = {
        'fast': vera_instance.fast_llm,
        'intermediate': vera_instance.intermediate_llm if hasattr(vera_instance, 'intermediate_llm') else vera_instance.fast_llm,
        'deep': vera_instance.deep_llm,
        'reasoning': vera_instance.reasoning_llm
    }
    
    llm = llm_map.get(llm_type, vera_instance.fast_llm)
    llm_name = llm_type if llm_type in llm_map else 'fast (default)'
    
    if logger:
        logger.info(
            f"Using fallback generation: {llm_name}",
            context=LogContext(extra={**context.extra, 'fallback_llm': llm_name})
        )
    
    if with_memory:
        past_context = ""
        if hasattr(vera_instance, 'memory'):
            past_context = vera_instance.memory.load_memory_variables(
                {"input": prompt}
            ).get("chat_history", "")
            
            if logger:
                logger.debug(
                    f"Loaded memory context: {len(past_context)} chars",
                    context=LogContext(extra={**context.extra, 'memory_size': len(past_context)})
                )
        
        full_prompt = f"Context: {past_context}\n\nUser: {prompt}\nAssistant:"
    else:
        full_prompt = prompt
    
    log_prompt(logger, full_prompt, context, "Fallback generation prompt")
    
    chunk_count = 0
    response_preview = ""
    for chunk in vera_instance._stream_with_thought_polling(llm, full_prompt):
        chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
        chunk_count += 1
        
        try:
            if len(response_preview) < 100 and chunk_text:
                response_preview += str(chunk_text)
        except Exception:
            pass
        
        yield chunk_text
    
    if logger:
        duration = logger.stop_timer("llm_generate", context=context)
        logger.success(
            f"Generation complete via fallback: {llm_name} | {chunk_count} chunks | {len(response_preview)} chars generated",
            context=LogContext(extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration, 'fallback': True})
        )


@task("llm.fast", task_type=TaskType.LLM, priority=Priority.HIGH, estimated_duration=5.0)
def llm_fast(vera_instance, prompt: str):
    """Fast LLM (streaming WITH real-time thoughts)"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'llm.fast', 'prompt_length': len(prompt)})
    
    if logger:
        logger.info(f"⚡ Fast LLM task starting", context=context)
        logger.start_timer("llm_fast")
    
    router = _get_router(vera_instance)
    
    if router:
        try:
            agent_name = router.get_agent_for_task('conversation')
            log_agent_selection(logger, 'conversation', agent_name, context)
            
            llm = router.create_llm_for_agent(agent_name)
            
            log_prompt(logger, prompt, LogContext(agent=agent_name, extra=context.extra), "Fast LLM prompt")
            
            chunk_count = 0
            response_preview = ""
            for chunk in vera_instance._stream_with_thought_polling(llm, prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                chunk_count += 1
                
                try:
                    if len(response_preview) < 100 and chunk_text:
                        response_preview += str(chunk_text)
                except Exception:
                    pass
                
                yield chunk_text
            
            if logger:
                duration = logger.stop_timer("llm_fast", context=LogContext(agent=agent_name, extra=context.extra))
                logger.success(
                    f"Fast LLM complete via agent: {agent_name} | {chunk_count} chunks",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration})
                )
            return
            
        except Exception as e:
            log_fallback(logger, "Agent fast LLM failed", e, context)
    
    if logger:
        logger.info("Using fallback fast LLM", context=context)
    
    log_prompt(logger, prompt, context, "Fallback fast LLM prompt")
    
    chunk_count = 0
    for chunk in vera_instance._stream_with_thought_polling(vera_instance.fast_llm, prompt):
        chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
        chunk_count += 1
        yield chunk_text
    
    if logger:
        duration = logger.stop_timer("llm_fast", context=context)
        logger.success(
            f"Fast LLM complete via fallback | {chunk_count} chunks",
            context=LogContext(extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration, 'fallback': True})
        )


@task("llm.deep", task_type=TaskType.LLM, priority=Priority.NORMAL, estimated_duration=15.0)
def llm_deep(vera_instance, prompt: str):
    """Deep LLM (streaming WITH real-time thoughts)"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'llm.deep', 'prompt_length': len(prompt)})
    
    if logger:
        logger.info(f"🧠 Deep LLM task starting", context=context)
        logger.start_timer("llm_deep")
    
    router = _get_router(vera_instance)
    
    if router:
        try:
            agent_name = router.get_agent_for_task('review')
            log_agent_selection(logger, 'review', agent_name, context)
            
            llm = router.create_llm_for_agent(agent_name)
            
            log_prompt(logger, prompt, LogContext(agent=agent_name, extra=context.extra), "Deep LLM prompt")
            
            chunk_count = 0
            response_preview = ""
            for chunk in vera_instance._stream_with_thought_polling(llm, prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                chunk_count += 1
                
                try:
                    if len(response_preview) < 100 and chunk_text:
                        response_preview += str(chunk_text)
                except Exception:
                    pass
                
                yield chunk_text
            
            if logger:
                duration = logger.stop_timer("llm_deep", context=LogContext(agent=agent_name, extra=context.extra))
                logger.success(
                    f"Deep LLM complete via agent: {agent_name} | {chunk_count} chunks",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration})
                )
            return
            
        except Exception as e:
            log_fallback(logger, "Agent deep LLM failed", e, context)
    
    if logger:
        logger.info("Using fallback deep LLM", context=context)
    
    log_prompt(logger, prompt, context, "Fallback deep LLM prompt")
    
    chunk_count = 0
    for chunk in vera_instance._stream_with_thought_polling(vera_instance.deep_llm, prompt):
        chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
        chunk_count += 1
        yield chunk_text
    
    if logger:
        duration = logger.stop_timer("llm_deep", context=context)
        logger.success(
            f"Deep LLM complete via fallback | {chunk_count} chunks",
            context=LogContext(extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration, 'fallback': True})
        )


@task("llm.reasoning", task_type=TaskType.LLM, priority=Priority.NORMAL, estimated_duration=20.0)
def llm_reasoning(vera_instance, prompt: str):
    """Reasoning LLM (streaming WITH real-time thoughts)"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'llm.reasoning', 'prompt_length': len(prompt)})
    
    if logger:
        logger.info(f"🤔 Reasoning LLM task starting", context=context)
        logger.start_timer("llm_reasoning")
    
    router = _get_router(vera_instance)
    
    if router:
        try:
            agent_name = router.get_agent_for_task('reasoning')
            log_agent_selection(logger, 'reasoning', agent_name, context)
            
            llm = router.create_llm_for_agent(agent_name)
            
            log_prompt(logger, prompt, LogContext(agent=agent_name, extra=context.extra), "Reasoning LLM prompt")
            
            chunk_count = 0
            response_preview = ""
            for chunk in vera_instance._stream_with_thought_polling(llm, prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                chunk_count += 1
                
                try:
                    if len(response_preview) < 100 and chunk_text:
                        response_preview += str(chunk_text)
                except Exception:
                    pass
                
                yield chunk_text
            
            if logger:
                duration = logger.stop_timer("llm_reasoning", context=LogContext(agent=agent_name, extra=context.extra))
                logger.success(
                    f"Reasoning LLM complete via agent: {agent_name} | {chunk_count} chunks",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration})
                )
            return
            
        except Exception as e:
            log_fallback(logger, "Agent reasoning LLM failed", e, context)
    
    if logger:
        logger.info("Using fallback reasoning LLM", context=context)
    
    log_prompt(logger, prompt, context, "Fallback reasoning LLM prompt")
    
    chunk_count = 0
    for chunk in vera_instance._stream_with_thought_polling(vera_instance.reasoning_llm, prompt):
        chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
        chunk_count += 1
        yield chunk_text
    
    if logger:
        duration = logger.stop_timer("llm_reasoning", context=context)
        logger.success(
            f"Reasoning LLM complete via fallback | {chunk_count} chunks",
            context=LogContext(extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration, 'fallback': True})
        )


# ============================================================================
# STREAMING TOOL TASKS
# ============================================================================

@task("toolchain.execute", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=30.0)
def toolchain_execute(vera_instance, query: str):
    """
    Execute tool chain with streaming output.
    Streams each tool's output as it executes.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'toolchain.execute', 'query_length': len(query)})
    
    if logger:
        logger.info(f"🔧 Toolchain execution starting", context=context)
        logger.start_timer("toolchain_execute")
    
    router = _get_router(vera_instance)
    
    # Try agent with tool restrictions
    if router:
        try:
            agent_name = router.get_agent_for_task('tool_execution')
            llm = router.create_llm_for_agent(agent_name)
            tools = router.get_agent_tools(agent_name)
            
            tool_names = [t.name for t in tools]
            log_agent_selection(
                logger, 'tool_execution', agent_name, context,
                extra_info={'tool_count': len(tools), 'tools': tool_names}
            )
            
            if logger:
                logger.debug(
                    f"Agent tools restricted to: {', '.join(tool_names)}",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'available_tools': tool_names})
                )
            
            log_prompt(logger, query, LogContext(agent=agent_name, extra=context.extra), "Toolchain query")
            
            original_llm = vera_instance.tool_llm
            original_tools = vera_instance.toolkit
            
            try:
                vera_instance.tool_llm = llm
                vera_instance.toolkit = tools
                
                if logger:
                    logger.debug(
                        "Toolchain config swapped to agent settings",
                        context=LogContext(agent=agent_name, extra=context.extra)
                    )
                
                chunk_count = 0
                tool_calls = []
                for chunk in vera_instance.toolchain.execute_tool_chain(query):
                    chunk_text = extract_chunk_text(chunk)
                    chunk_count += 1
                    
                    if 'tool:' in chunk_text.lower():
                        tool_calls.append(chunk_text[:50])
                    
                    yield chunk_text
                
                if logger:
                    duration = logger.stop_timer("toolchain_execute", context=LogContext(agent=agent_name, extra=context.extra))
                    logger.success(
                        f"Toolchain complete via agent: {agent_name} | {chunk_count} chunks | {len(tool_calls)} tool calls detected",
                        context=LogContext(agent=agent_name, extra={
                            **context.extra,
                            'chunk_count': chunk_count,
                            'tool_calls': len(tool_calls),
                            'duration': duration
                        })
                    )
                return

            finally:
                vera_instance.tool_llm = original_llm
                vera_instance.tools = original_tools
                
                if logger:
                    logger.debug(
                        "Toolchain config restored to original",
                        context=LogContext(agent=agent_name, extra=context.extra)
                    )
                    
        except Exception as e:
            log_fallback(logger, "Agent toolchain execution failed", e, context)
    
    # Original fallback
    all_tool_names = [t.name for t in vera_instance.tools] if hasattr(vera_instance, 'tools') else []
    
    if logger:
        logger.info(
            f"Using fallback toolchain with {len(all_tool_names)} tools",
            context=LogContext(extra={**context.extra, 'tool_count': len(all_tool_names), 'tools': all_tool_names})
        )
    
    log_prompt(logger, query, context, "Fallback toolchain query")
    
    chunk_count = 0
    for chunk in vera_instance.toolchain.execute_tool_chain(query):
        chunk_count += 1
        yield extract_chunk_text(chunk)
    
    if logger:
        duration = logger.stop_timer("toolchain_execute", context=context)
        logger.success(
            f"Toolchain complete via fallback | {chunk_count} chunks",
            context=LogContext(extra={**context.extra, 'chunk_count': chunk_count, 'duration': duration, 'fallback': True})
        )


@task("tool.single", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=5.0)
def tool_single(vera_instance, tool_name: str, **kwargs):
    """Execute a single tool"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'tool.single', 'tool_name': tool_name})
    
    if logger:
        logger.info(f"🔨 Single tool execution: {tool_name}", context=context)
        logger.start_timer("tool_single")
        
        arg_summary = {k: f"{type(v).__name__}({len(str(v))} chars)" if isinstance(v, str) and len(str(v)) > 50 else v 
                      for k, v in kwargs.items()}
        logger.debug(
            f"Tool arguments: {json.dumps(arg_summary, indent=2)}",
            context=LogContext(extra={**context.extra, 'args': arg_summary})
        )
    
    tool = next((t for t in vera_instance.tools if t.name == tool_name), None)
    if not tool:
        if logger:
            logger.error(
                f"Tool not found: {tool_name}",
                context=LogContext(extra={
                    **context.extra,
                    'available_tools': [t.name for t in vera_instance.tools] if hasattr(vera_instance, 'tools') else []
                })
            )
        return {"error": f"Tool not found: {tool_name}"}
    
    if logger:
        logger.debug(
            f"Executing tool: {tool_name} with {len(kwargs)} arguments",
            context=context
        )
    
    try:
        result = tool.run(**kwargs)
        
        if logger:
            duration = logger.stop_timer("tool_single", context=context)
            result_type = type(result).__name__
            result_size = len(str(result)) if result else 0
            result_preview = truncate_text(str(result), max_length=100) if result else "None"
            
            logger.success(
                f"Tool execution complete: {tool_name} | {result_type} | {result_size} chars | Preview: {result_preview}",
                context=LogContext(extra={
                    **context.extra,
                    'result_type': result_type,
                    'result_size': result_size,
                    'duration': duration
                })
            )
        
        return result
        
    except Exception as e:
        if logger:
            duration = logger.stop_timer("tool_single", context=context)
            logger.error(
                f"Tool execution failed: {tool_name} - {type(e).__name__}: {str(e)}",
                exc_info=True,
                context=LogContext(extra={**context.extra, 'duration': duration, 'error': str(e)})
            )
        
        return {"error": f"Tool execution failed: {str(e)}"}


# ============================================================================
# WHISPER TASK
# ============================================================================

@task("whisper.transcribe", task_type=TaskType.WHISPER, priority=Priority.NORMAL, 
      estimated_duration=10.0, requires_gpu=True, memory_mb=4096)
def whisper_transcribe(vera_instance, audio_path: str):
    """Transcribe audio using Whisper"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'whisper.transcribe', 'audio_path': audio_path})
    
    if logger:
        logger.info(f"🎤 Whisper transcription starting: {audio_path}", context=context)
        logger.start_timer("whisper_transcribe")
    
    if hasattr(vera_instance, 'whisper_model'):
        if logger:
            logger.debug("Using Whisper model", context=context)
        
        try:
            result = vera_instance.whisper_model.transcribe(audio_path)
            
            if logger:
                duration = logger.stop_timer("whisper_transcribe", context=context)
                text_length = len(result.get('text', '')) if isinstance(result, dict) else 0
                text_preview = truncate_text(result.get('text', ''), max_length=100) if isinstance(result, dict) else ""
                
                logger.success(
                    f"Transcription complete | {text_length} chars | Preview: {text_preview}",
                    context=LogContext(extra={**context.extra, 'text_length': text_length, 'duration': duration})
                )
            
            return result
            
        except Exception as e:
            if logger:
                duration = logger.stop_timer("whisper_transcribe", context=context)
                logger.error(
                    f"Whisper transcription failed: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                    context=LogContext(extra={**context.extra, 'duration': duration, 'error': str(e)})
                )
            
            return {"error": f"Transcription failed: {str(e)}"}
    
    if logger:
        logger.error(
            "Whisper model not available",
            context=LogContext(extra={**context.extra, 'reason': 'whisper_model_not_found'})
        )
    
    return {"error": "Whisper not available"}


# ============================================================================
# MEMORY TASKS (Non-streaming)
# ============================================================================

@task("memory.search", task_type=TaskType.GENERAL, priority=Priority.HIGH, estimated_duration=1.0)
def memory_search(vera_instance, query: str, top_k: int = 5):
    """Search memory systems"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'memory.search', 'top_k': top_k, 'query_length': len(query)})
    
    if logger:
        logger.info(f"💾 Memory search starting: top_k={top_k}", context=context)
        logger.debug(f"Search query: {truncate_text(query, 100)}", context=context)
        logger.start_timer("memory_search")
    
    results = {"query": query}
    searches_performed = []
    
    if hasattr(vera_instance, 'vector_memory'):
        if logger:
            logger.debug("Searching vector memory", context=context)
        
        try:
            results["vector"] = vera_instance.vector_memory.load_memory_variables(
                {"input": query}
            )
            searches_performed.append("vector")
            
            if logger:
                vector_results = len(str(results["vector"]))
                logger.debug(
                    f"Vector memory returned {vector_results} chars",
                    context=LogContext(extra={**context.extra, 'vector_result_size': vector_results})
                )
        except Exception as e:
            if logger:
                logger.warning(f"Vector memory search failed: {str(e)}", context=context)
    
    if hasattr(vera_instance, 'mem') and hasattr(vera_instance, 'sess'):
        if logger:
            logger.debug("Searching graph memory", context=context)
        
        try:
            results["graph"] = vera_instance.mem.focus_context(
                vera_instance.sess.id,
                query,
                top_k=top_k
            )
            searches_performed.append("graph")
            
            if logger:
                graph_results = len(str(results["graph"]))
                logger.debug(
                    f"Graph memory returned {graph_results} chars",
                    context=LogContext(extra={**context.extra, 'graph_result_size': graph_results})
                )
        except Exception as e:
            if logger:
                logger.warning(f"Graph memory search failed: {str(e)}", context=context)
    
    if logger:
        duration = logger.stop_timer("memory_search", context=context)
        logger.success(
            f"Memory search complete | Searched: {', '.join(searches_performed) or 'none'}",
            context=LogContext(extra={
                **context.extra,
                'searches_performed': searches_performed,
                'duration': duration
            })
        )
    
    return results


@task("memory.save", task_type=TaskType.GENERAL, priority=Priority.NORMAL, estimated_duration=0.5)
def memory_save(vera_instance, user_input: str, ai_output: str):
    """Save interaction to memory"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={
        'component': 'task',
        'task': 'memory.save',
        'input_length': len(user_input),
        'output_length': len(ai_output)
    })
    
    if logger:
        logger.info(
            f"💾 Saving to memory: input={len(user_input)} chars, output={len(ai_output)} chars",
            context=context
        )
        logger.start_timer("memory_save")
    
    saves_performed = []
    
    try:
        vera_instance.save_to_memory(user_input, ai_output)
        saves_performed.append("vector")
        
        if logger:
            logger.debug("Saved to vector memory", context=context)
    except Exception as e:
        if logger:
            logger.warning(f"Vector memory save failed: {str(e)}", context=context)
    
    if hasattr(vera_instance, 'mem') and hasattr(vera_instance, 'sess'):
        try:
            if logger:
                logger.debug("Saving to graph memory", context=context)
            
            vera_instance.mem.add_session_memory(
                vera_instance.sess.id,
                user_input,
                "Query",
                {"topic": "query"}
            )
            vera_instance.mem.add_session_memory(
                vera_instance.sess.id,
                ai_output,
                "Response",
                {"topic": "response"}
            )
            saves_performed.append("graph")
            
            if logger:
                logger.debug("Saved to graph memory", context=context)
        except Exception as e:
            if logger:
                logger.warning(f"Graph memory save failed: {str(e)}", context=context)
    
    if logger:
        duration = logger.stop_timer("memory_save", context=context)
        logger.success(
            f"Memory save complete | Saved to: {', '.join(saves_performed) or 'none'}",
            context=LogContext(extra={
                **context.extra,
                'saves_performed': saves_performed,
                'duration': duration
            })
        )
    
    return {"status": "saved", "targets": saves_performed}


@task("memory.consolidate", task_type=TaskType.BACKGROUND, priority=Priority.LOW, estimated_duration=5.0)
def memory_consolidate(vera_instance):
    """Consolidate memory in background"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'memory.consolidate'})
    
    if logger:
        logger.info("💾 Memory consolidation starting", context=context)
        logger.start_timer("memory_consolidate")
    
    consolidations_performed = []
    
    try:
        if hasattr(vera_instance, 'vectorstore'):
            if logger:
                logger.debug("Persisting vectorstore", context=context)
            
            vera_instance.vectorstore.persist()
            consolidations_performed.append("vectorstore")
            
            if logger:
                logger.debug("Vectorstore persisted", context=context)
        
        if hasattr(vera_instance, 'focus_manager') and vera_instance.focus_manager.focus:
            if logger:
                logger.debug("Consolidating focus board", context=context)
            
            vera_instance.focus_manager._consolidate_focus_board()
            consolidations_performed.append("focus_board")
            
            if logger:
                logger.debug("Focus board consolidated", context=context)
        
        if logger:
            duration = logger.stop_timer("memory_consolidate", context=context)
            logger.success(
                f"Memory consolidation complete | Consolidated: {', '.join(consolidations_performed) or 'none'}",
                context=LogContext(extra={
                    **context.extra,
                    'consolidations': consolidations_performed,
                    'duration': duration
                })
            )
        
        return {"status": "consolidated", "targets": consolidations_performed}
        
    except Exception as e:
        if logger:
            duration = logger.stop_timer("memory_consolidate", context=context)
            logger.error(
                f"Memory consolidation failed: {type(e).__name__}: {str(e)}",
                exc_info=True,
                context=LogContext(extra={**context.extra, 'duration': duration, 'error': str(e)})
            )
        
        return {"error": str(e)}


# ============================================================================
# PROACTIVE FOCUS TASKS (Background with thought streaming!)
# ============================================================================

@proactive_task("proactive.generate_thought", estimated_duration=15.0, memory_mb=2048)
def proactive_generate_thought(vera_instance):
    """
    Generate proactive thought in background WITH real-time thought streaming.
    Thoughts stream to UI just like interactive tasks.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'proactive.generate_thought'})
    
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        if logger:
            logger.warning(
                "No active focus for proactive thought",
                context=LogContext(extra={**context.extra, 'reason': 'no_active_focus'})
            )
        return {"error": "No active focus"}
    
    focus = vera_instance.focus_manager.focus
    context.extra['focus'] = focus
    
    if logger:
        logger.info(f"💡 Proactive thought generation starting: focus={focus}", context=context)
        logger.start_timer("proactive_thought")
    
    router = _get_router(vera_instance)
    
    # Try reasoning agent
    if router:
        try:
            agent_name = router.get_agent_for_task('reasoning')
            log_agent_selection(logger, 'reasoning (proactive)', agent_name, context)
            
            llm = router.create_llm_for_agent(agent_name)
            
            recent_context = vera_instance.focus_manager.latest_conversation if hasattr(vera_instance.focus_manager, 'latest_conversation') else 'None'
            board_state = str(vera_instance.focus_manager.focus_board)[:500]
            
            prompt = f"""Project: {focus}

Recent context:
{recent_context}

Focus board state:
{board_state}

What's the most valuable next step?"""
            
            log_prompt(logger, prompt, LogContext(agent=agent_name, extra=context.extra), "Proactive thought prompt")
            
            thought = ""
            chunk_count = 0
            
            # USE SAME THOUGHT POLLING AS INTERACTIVE TASKS - thoughts stream to UI!
            for chunk in vera_instance._stream_with_thought_polling(llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                chunk_count += 1
                thought += chunk_text
            
            if thought.strip():
                # STUB: Add to focus board (can be customized)
                if hasattr(vera_instance.focus_manager, 'add_to_focus_board'):
                    vera_instance.focus_manager.add_to_focus_board("actions", thought)
                    
                    if logger:
                        logger.debug(
                            f"Added thought to focus board: {truncate_text(thought, 100)}",
                            context=LogContext(agent=agent_name, extra={**context.extra, 'thought_length': len(thought)})
                        )
            
            if logger:
                duration = logger.stop_timer("proactive_thought", context=LogContext(agent=agent_name, extra=context.extra))
                logger.success(
                    f"Proactive thought complete via agent: {agent_name} | {chunk_count} chunks | {len(thought)} chars",
                    context=LogContext(agent=agent_name, extra={
                        **context.extra,
                        'chunk_count': chunk_count,
                        'thought_length': len(thought),
                        'duration': duration
                    })
                )
            
            return {
                "thought": thought,
                "focus": focus,
                "status": "completed",
                "agent": agent_name
            }
            
        except Exception as e:
            log_fallback(logger, "Agent proactive thought generation failed", e, context)
    
    # Original fallback
    if logger:
        logger.info("Using fallback proactive thought (deep_llm)", context=context)
    
    recent_context = vera_instance.focus_manager.latest_conversation if hasattr(vera_instance.focus_manager, 'latest_conversation') else 'None'
    board_state = str(vera_instance.focus_manager.focus_board)[:500]
    
    prompt = f"""
    You are assisting with the project: {focus}
    
    Recent context:
    {recent_context}
    
    Focus board state:
    {board_state}
    
    Suggest the most valuable immediate action or next step to advance the project.
    Focus on concrete, practical actions or investigations.
    """
    
    log_prompt(logger, prompt, context, "Fallback proactive thought prompt")
    
    thought = ""
    chunk_count = 0
    
    # USE SAME THOUGHT POLLING - thoughts stream to UI!
    for chunk in vera_instance._stream_with_thought_polling(vera_instance.deep_llm, prompt):
        chunk_text = extract_chunk_text(chunk)
        chunk_count += 1
        thought += chunk_text
    
    if thought.strip():
        # STUB: Add to focus board
        if hasattr(vera_instance.focus_manager, 'add_to_focus_board'):
            vera_instance.focus_manager.add_to_focus_board("actions", thought)
            
            if logger:
                logger.debug(
                    f"Added thought to focus board: {truncate_text(thought, 100)}",
                    context=LogContext(extra={**context.extra, 'thought_length': len(thought)})
                )
    
    if logger:
        duration = logger.stop_timer("proactive_thought", context=context)
        logger.success(
            f"Proactive thought complete via fallback | {chunk_count} chunks | {len(thought)} chars",
            context=LogContext(extra={
                **context.extra,
                'chunk_count': chunk_count,
                'thought_length': len(thought),
                'duration': duration,
                'fallback': True
            })
        )
    
    return {
        "thought": thought,
        "focus": focus,
        "status": "completed"
    }


@proactive_task("proactive.generate_ideas", estimated_duration=15.0)
def proactive_ideas(vera_instance, context=None):
    """Generate ideas for current focus"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    log_context = LogContext(extra={'component': 'task', 'task': 'proactive.generate_ideas'})
    
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        if logger:
            logger.warning("No active focus for idea generation", context=log_context)
        return {"error": "No active focus"}
    
    focus = vera_instance.focus_manager.focus
    log_context.extra['focus'] = focus
    
    if logger:
        logger.info(f"💡 Proactive idea generation starting: focus={focus}", context=log_context)
        logger.start_timer("proactive_ideas")
    
    ideas = vera_instance.focus_manager.generate_ideas(context=context)
    
    if logger:
        duration = logger.stop_timer("proactive_ideas", context=log_context)
        logger.success(
            f"Generated {len(ideas)} ideas",
            context=LogContext(extra={**log_context.extra, 'idea_count': len(ideas), 'duration': duration})
        )
    
    return {
        "ideas": ideas,
        "count": len(ideas),
        "focus": focus
    }


@proactive_task("proactive.generate_next_steps", estimated_duration=15.0)
def proactive_next_steps(vera_instance, context=None):
    """Generate next steps for current focus"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    log_context = LogContext(extra={'component': 'task', 'task': 'proactive.generate_next_steps'})
    
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        if logger:
            logger.warning("No active focus for next steps", context=log_context)
        return {"error": "No active focus"}
    
    focus = vera_instance.focus_manager.focus
    log_context.extra['focus'] = focus
    
    if logger:
        logger.info(f"📋 Proactive next steps generation starting: focus={focus}", context=log_context)
        logger.start_timer("proactive_next_steps")
    
    steps = vera_instance.focus_manager.generate_next_steps(context=context)
    
    if logger:
        duration = logger.stop_timer("proactive_next_steps", context=log_context)
        logger.success(
            f"Generated {len(steps)} next steps",
            context=LogContext(extra={**log_context.extra, 'step_count': len(steps), 'duration': duration})
        )
    
    return {
        "next_steps": steps,
        "count": len(steps),
        "focus": focus
    }


@proactive_task("proactive.generate_actions", priority=Priority.NORMAL, estimated_duration=20.0)
def proactive_actions(vera_instance, context=None):
    """Generate executable actions for current focus"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    log_context = LogContext(extra={'component': 'task', 'task': 'proactive.generate_actions'})
    
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        if logger:
            logger.warning("No active focus for action generation", context=log_context)
        return {"error": "No active focus"}
    
    focus = vera_instance.focus_manager.focus
    log_context.extra['focus'] = focus
    
    if logger:
        logger.info(f"⚡ Proactive action generation starting: focus={focus}", context=log_context)
        logger.start_timer("proactive_actions")
    
    actions = vera_instance.focus_manager.generate_actions(context=context)
    
    if logger:
        duration = logger.stop_timer("proactive_actions", context=log_context)
        logger.success(
            f"Generated {len(actions)} actions",
            context=LogContext(extra={**log_context.extra, 'action_count': len(actions), 'duration': duration})
        )
    
    return {
        "actions": actions,
        "count": len(actions),
        "focus": focus
    }


# ============================================================================
# FOCUS MANAGEMENT TASKS
# ============================================================================

@task("focus.set", task_type=TaskType.GENERAL, priority=Priority.HIGH, estimated_duration=0.5)
def focus_set(vera_instance, focus: str):
    """Set focus"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'focus.set', 'focus': focus})
    
    if not hasattr(vera_instance, 'focus_manager'):
        if logger:
            logger.error("No focus_manager available", context=context)
        return {"error": "No focus_manager"}
    
    if logger:
        logger.info(f"🎯 Setting focus: {focus}", context=context)
        logger.start_timer("focus_set")
    
    vera_instance.focus_manager.set_focus(focus)
    
    if logger:
        duration = logger.stop_timer("focus_set", context=context)
        logger.success(
            f"Focus set successfully",
            context=LogContext(extra={**context.extra, 'duration': duration})
        )
    
    return {
        "status": "set",
        "focus": focus
    }


@task("focus.get", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=0.1)
def focus_get(vera_instance):
    """Get current focus"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'focus.get'})
    
    if hasattr(vera_instance, 'focus_manager'):
        focus = vera_instance.focus_manager.focus
        
        if logger:
            logger.debug(f"Current focus: {focus}", context=LogContext(extra={**context.extra, 'focus': focus}))
        
        return {
            "focus": focus,
            "focus_board": vera_instance.focus_manager.focus_board
        }
    
    if logger:
        logger.debug("No focus_manager available", context=context)
    
    return {"focus": None}


# ============================================================================
# SYSTEM TASKS
# ============================================================================

@task("health_check", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=0.5)
def health_check(vera_instance):
    """Check system health"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={'component': 'task', 'task': 'health_check'})
    
    if logger:
        logger.info("🏥 Health check starting", context=context)
        logger.start_timer("health_check")
    
    health = {
        "llms": {
            "fast": hasattr(vera_instance, 'fast_llm'),
            "deep": hasattr(vera_instance, 'deep_llm'),
            "reasoning": hasattr(vera_instance, 'reasoning_llm')
        },
        "memory": {
            "vectorstore": hasattr(vera_instance, 'vectorstore'),
            "hybrid": hasattr(vera_instance, 'mem')
        },
        "tools": {
            "count": len(vera_instance.tools) if hasattr(vera_instance, 'tools') else 0,
            "names": [t.name for t in vera_instance.tools] if hasattr(vera_instance, 'tools') else []
        },
        "focus": {
            "active": vera_instance.focus_manager.focus if hasattr(vera_instance, 'focus_manager') else None,
            "manager": hasattr(vera_instance, 'focus_manager')
        },
        "orchestrator": {
            "running": vera_instance.orchestrator.running if hasattr(vera_instance, 'orchestrator') else False
        },
        "agents": {
            "enabled": hasattr(vera_instance, 'agents') and vera_instance.agents is not None,
            "count": len(vera_instance.agents.loaded_agents) if hasattr(vera_instance, 'agents') and vera_instance.agents else 0
        }
    }
    
    if logger:
        duration = logger.stop_timer("health_check", context=context)
        
        healthy_llms = sum(health["llms"].values())
        healthy_memory = sum(health["memory"].values())
        
        logger.success(
            f"Health check complete: LLMs={healthy_llms}/3, Memory={healthy_memory}/2, "
            f"Tools={health['tools']['count']}, Agents={health['agents']['count']}",
            context=LogContext(extra={**context.extra, 'duration': duration, 'health': health})
        )
    
    return health


# ============================================================================
# AGENT MANAGEMENT TASKS
# ============================================================================

if AGENTS_AVAILABLE:
    @task("agent.list", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=0.1)
    def agent_list(vera_instance):
        """List available agents"""
        logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
        context = LogContext(extra={'component': 'task', 'task': 'agent.list'})
        
        if not hasattr(vera_instance, 'agents') or not vera_instance.agents:
            if logger:
                logger.warning("Agent system not enabled", context=context)
            return {"agents": [], "message": "Agent system not enabled"}
        
        agents = vera_instance.agents.list_loaded_agents()
        
        if logger:
            logger.debug(
                f"Found {len(agents)} agents: {', '.join(agents)}",
                context=LogContext(extra={**context.extra, 'agent_count': len(agents), 'agents': agents})
            )
        
        return {
            "agents": agents,
            "count": len(agents)
        }
    
    
    @task("agent.reload", task_type=TaskType.GENERAL, priority=Priority.NORMAL, estimated_duration=5.0)
    def agent_reload(vera_instance, agent_name: str, rebuild_model: bool = True):
        """Reload agent configuration"""
        logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
        context = LogContext(agent=agent_name, extra={'component': 'task', 'task': 'agent.reload', 'rebuild_model': rebuild_model})
        
        if not hasattr(vera_instance, 'agents') or not vera_instance.agents:
            if logger:
                logger.error("Agent system not enabled", context=context)
            return {"error": "Agent system not enabled"}
        
        if logger:
            logger.info(
                f"🔄 Reloading agent: {agent_name} (rebuild_model={rebuild_model})",
                context=context
            )
            logger.start_timer("agent_reload")
        
        config = vera_instance.agents.reload_agent(agent_name, rebuild_model=rebuild_model)
        
        if config:
            if logger:
                duration = logger.stop_timer("agent_reload", context=context)
                logger.success(
                    f"Agent reloaded successfully",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'duration': duration})
                )
            
            return {
                "status": "reloaded",
                "agent": agent_name,
                "config": config.to_dict()
            }
        else:
            if logger:
                duration = logger.stop_timer("agent_reload", context=context)
                logger.error(
                    f"Agent reload failed",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'duration': duration})
                )
            
            return {"error": f"Failed to reload agent: {agent_name}"}
    
    
    @task("agent.validate", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=1.0)
    def agent_validate(vera_instance, agent_name: str):
        """Validate agent configuration"""
        logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
        context = LogContext(agent=agent_name, extra={'component': 'task', 'task': 'agent.validate'})
        
        if not hasattr(vera_instance, 'agents') or not vera_instance.agents:
            if logger:
                logger.error("Agent system not enabled", context=context)
            return {"error": "Agent system not enabled"}
        
        if logger:
            logger.info(f"✓ Validating agent: {agent_name}", context=context)
            logger.start_timer("agent_validate")
        
        issues = vera_instance.agents.validate_agent(agent_name)
        
        if logger:
            duration = logger.stop_timer("agent_validate", context=context)
            if len(issues) == 0:
                logger.success(
                    f"Agent validation passed",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'duration': duration})
                )
            else:
                logger.warning(
                    f"Agent validation found {len(issues)} issues",
                    context=LogContext(agent=agent_name, extra={**context.extra, 'issue_count': len(issues), 'duration': duration})
                )
                for issue in issues:
                    logger.debug(f"  • {issue}", context=context)
        
        return {
            "agent": agent_name,
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    
    @task("agent.get_config", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=0.1)
    def agent_get_config(vera_instance, agent_name: str):
        """Get agent configuration"""
        logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
        context = LogContext(agent=agent_name, extra={'component': 'task', 'task': 'agent.get_config'})
        
        if not hasattr(vera_instance, 'agents') or not vera_instance.agents:
            if logger:
                logger.error("Agent system not enabled", context=context)
            return {"error": "Agent system not enabled"}
        
        config = vera_instance.agents.get_agent_config(agent_name)
        
        if config:
            if logger:
                logger.debug(
                    f"Config retrieved: base_model={config.base_model}, temp={config.temperature}",
                    context=LogContext(agent=agent_name, extra={
                        **context.extra,
                        'base_model': config.base_model,
                        'temperature': config.temperature
                    })
                )
            
            return {
                "agent": agent_name,
                "config": config.to_dict()
            }
        else:
            if logger:
                logger.warning(f"Agent not found: {agent_name}", context=context)
            
            return {"error": f"Agent not found: {agent_name}"}

