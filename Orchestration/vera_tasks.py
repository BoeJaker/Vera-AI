"""
Vera Task Registrations (Streaming Version)
============================================
Register all Vera tasks with streaming support.
Tasks that naturally stream (LLM, toolchain) now yield chunks.
"""

from Vera.Orchestration.orchestration import task, proactive_task, TaskType, Priority

# ============================================================================
# STREAMING LLM TASKS
# ============================================================================

@task("llm.triage", task_type=TaskType.LLM, priority=Priority.CRITICAL, estimated_duration=2.0)
def llm_triage(vera_instance, query: str):
    """
    Triage query to determine routing.
    Streams response as it's generated.
    """
    triage_prompt = f"""
    Classify this Query into one of the following categories:
        - 'focus'      → Change the focus of background thought.
        - 'proactive'  → Trigger proactive thinking.
        - 'simple'     → Simple textual response.
        - 'toolchain'  → Requires a series of tools or step-by-step planning.
        - 'reasoning'  → Requires deep reasoning.
        - 'complex'    → Complex written response with high-quality output.

    Current focus: {vera_instance.focus_manager.focus if hasattr(vera_instance, 'focus_manager') else 'None'}
    

    Query: {query}

    Respond with a single classification term (e.g., 'simple', 'toolchain', 'complex') on the first line.
    """
    # Removed from prompt to reduce length
    # Available tools: {', '.join(t.name for t in vera_instance.tools) if hasattr(vera_instance, 'tools') else 'None'}
    
    # Stream triage response
    for chunk in vera_instance.fast_llm.stream(triage_prompt):
        yield chunk


@task("llm.generate", task_type=TaskType.LLM, priority=Priority.HIGH, estimated_duration=10.0)
def llm_generate(vera_instance, llm_type: str, prompt: str, **kwargs):
    """
    Generate text using specified LLM.
    Streams response as it's generated.
    """
    llm_map = {
        'fast': vera_instance.fast_llm,
        'intermediate': vera_instance.intermediate_llm if hasattr(vera_instance, 'intermediate_llm') else vera_instance.fast_llm,
        'deep': vera_instance.deep_llm,
        'reasoning': vera_instance.reasoning_llm
    }
    
    llm = llm_map.get(llm_type, vera_instance.fast_llm)
    
    # Build prompt with memory if requested
    if kwargs.get('with_memory', False):
        past_context = ""
        if hasattr(vera_instance, 'memory'):
            past_context = vera_instance.memory.load_memory_variables(
                {"input": prompt}
            ).get("chat_history", "")
        
        full_prompt = f"Context: {past_context}\n\nUser: {prompt}\nAssistant:"
    else:
        full_prompt = prompt
    
    # Stream response
    for chunk in llm.stream(full_prompt):
        yield chunk


@task("llm.fast", task_type=TaskType.LLM, priority=Priority.HIGH, estimated_duration=5.0)
def llm_fast(vera_instance, prompt: str):
    """Fast LLM (streaming)"""
    for chunk in vera_instance.fast_llm.stream(prompt):
        yield chunk


@task("llm.deep", task_type=TaskType.LLM, priority=Priority.NORMAL, estimated_duration=15.0)
def llm_deep(vera_instance, prompt: str):
    """Deep LLM (streaming)"""
    for chunk in vera_instance.deep_llm.stream(prompt):
        yield chunk


@task("llm.reasoning", task_type=TaskType.LLM, priority=Priority.NORMAL, estimated_duration=20.0)
def llm_reasoning(vera_instance, prompt: str):
    """Reasoning LLM (streaming)"""
    for chunk in vera_instance.reasoning_llm.stream(prompt):
        yield chunk


# ============================================================================
# STREAMING TOOL TASKS
# ============================================================================

@task("toolchain.execute", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=30.0)
def toolchain_execute(vera_instance, query: str):
    """
    Execute tool chain with streaming output.
    Streams each tool's output as it executes.
    """
    for chunk in vera_instance.toolchain.execute_tool_chain(query):
        yield chunk


@task("tool.single", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=5.0)
def tool_single(vera_instance, tool_name: str, **kwargs):
    """Execute a single tool"""
    tool = next((t for t in vera_instance.tools if t.name == tool_name), None)
    if not tool:
        return {"error": f"Tool not found: {tool_name}"}
    
    result = tool.run(**kwargs)
    return result


# ============================================================================
# WHISPER TASK
# ============================================================================

@task("whisper.transcribe", task_type=TaskType.WHISPER, priority=Priority.NORMAL, 
      estimated_duration=10.0, requires_gpu=True, memory_mb=4096)
def whisper_transcribe(vera_instance, audio_path: str):
    """Transcribe audio using Whisper"""
    if hasattr(vera_instance, 'whisper_model'):
        result = vera_instance.whisper_model.transcribe(audio_path)
        return result
    return {"error": "Whisper not available"}


# ============================================================================
# MEMORY TASKS (Non-streaming)
# ============================================================================

@task("memory.search", task_type=TaskType.GENERAL, priority=Priority.HIGH, estimated_duration=1.0)
def memory_search(vera_instance, query: str, top_k: int = 5):
    """Search memory systems"""
    results = {"query": query}
    
    # Search vector memory
    if hasattr(vera_instance, 'vector_memory'):
        results["vector"] = vera_instance.vector_memory.load_memory_variables(
            {"input": query}
        )
    
    # Search graph memory
    if hasattr(vera_instance, 'mem') and hasattr(vera_instance, 'sess'):
        results["graph"] = vera_instance.mem.focus_context(
            vera_instance.sess.id,
            query,
            top_k=top_k
        )
    
    return results


@task("memory.save", task_type=TaskType.GENERAL, priority=Priority.NORMAL, estimated_duration=0.5)
def memory_save(vera_instance, user_input: str, ai_output: str):
    """Save interaction to memory"""
    vera_instance.save_to_memory(user_input, ai_output)
    
    if hasattr(vera_instance, 'mem') and hasattr(vera_instance, 'sess'):
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
    
    return {"status": "saved"}


@task("memory.consolidate", task_type=TaskType.BACKGROUND, priority=Priority.LOW, estimated_duration=5.0)
def memory_consolidate(vera_instance):
    """Consolidate memory in background"""
    try:
        # Persist vector store
        if hasattr(vera_instance, 'vectorstore'):
            vera_instance.vectorstore.persist()
        
        # Consolidate focus board
        if hasattr(vera_instance, 'focus_manager') and vera_instance.focus_manager.focus:
            vera_instance.focus_manager._consolidate_focus_board()
        
        return {"status": "consolidated"}
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# PROACTIVE FOCUS TASKS (Background, non-streaming)
# ============================================================================

@proactive_task("proactive.generate_thought", estimated_duration=15.0, memory_mb=2048)
def proactive_generate_thought(vera_instance):
    """
    Generate proactive thought in background.
    Returns complete thought (doesn't stream since it's background).
    """
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        return {"error": "No active focus"}
    
    # Collect complete thought
    thought = ""
    
    prompt = f"""
    You are assisting with the project: {vera_instance.focus_manager.focus}
    
    Recent context:
    {vera_instance.focus_manager.latest_conversation if hasattr(vera_instance.focus_manager, 'latest_conversation') else 'None'}
    
    Focus board state:
    {str(vera_instance.focus_manager.focus_board)[:500]}
    
    Suggest the most valuable immediate action or next step to advance the project.
    Focus on concrete, practical actions or investigations.
    """
    
    for chunk in vera_instance.deep_llm.stream(prompt):
        thought += chunk
    
    # Add to focus board
    if thought:
        vera_instance.focus_manager.add_to_focus_board("actions", thought)
    
    return {
        "thought": thought,
        "focus": vera_instance.focus_manager.focus,
        "status": "completed"
    }


@proactive_task("proactive.generate_ideas", estimated_duration=15.0)
def proactive_ideas(vera_instance, context=None):
    """Generate ideas for current focus"""
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        return {"error": "No active focus"}
    
    ideas = vera_instance.focus_manager.generate_ideas(context=context)
    
    return {
        "ideas": ideas,
        "count": len(ideas),
        "focus": vera_instance.focus_manager.focus
    }


@proactive_task("proactive.generate_next_steps", estimated_duration=15.0)
def proactive_next_steps(vera_instance, context=None):
    """Generate next steps for current focus"""
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        return {"error": "No active focus"}
    
    steps = vera_instance.focus_manager.generate_next_steps(context=context)
    
    return {
        "next_steps": steps,
        "count": len(steps),
        "focus": vera_instance.focus_manager.focus
    }


@proactive_task("proactive.generate_actions", priority=Priority.NORMAL, estimated_duration=20.0)
def proactive_actions(vera_instance, context=None):
    """Generate executable actions for current focus"""
    if not hasattr(vera_instance, 'focus_manager') or not vera_instance.focus_manager.focus:
        return {"error": "No active focus"}
    
    actions = vera_instance.focus_manager.generate_actions(context=context)
    
    return {
        "actions": actions,
        "count": len(actions),
        "focus": vera_instance.focus_manager.focus
    }


# ============================================================================
# FOCUS MANAGEMENT TASKS
# ============================================================================

@task("focus.set", task_type=TaskType.GENERAL, priority=Priority.HIGH, estimated_duration=0.5)
def focus_set(vera_instance, focus: str):
    """Set focus"""
    if not hasattr(vera_instance, 'focus_manager'):
        return {"error": "No focus_manager"}
    
    vera_instance.focus_manager.set_focus(focus)
    
    return {
        "status": "set",
        "focus": focus
    }


@task("focus.get", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=0.1)
def focus_get(vera_instance):
    """Get current focus"""
    if hasattr(vera_instance, 'focus_manager'):
        return {
            "focus": vera_instance.focus_manager.focus,
            "focus_board": vera_instance.focus_manager.focus_board
        }
    return {"focus": None}


# ============================================================================
# SYSTEM TASKS
# ============================================================================

@task("health_check", task_type=TaskType.GENERAL, priority=Priority.LOW, estimated_duration=0.5)
def health_check(vera_instance):
    """Check system health"""
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
        }
    }
    
    return health


# ============================================================================
# REGISTER ON IMPORT
# ============================================================================

print("[TaskRegistry] Registered Vera tasks:")
print("  LLM (streaming):")
print("    - llm.triage (CRITICAL, 2s)")
print("    - llm.generate (HIGH, 10s)")
print("    - llm.fast (HIGH, 5s)")
print("    - llm.deep (NORMAL, 15s)")
print("    - llm.reasoning (NORMAL, 20s)")
print("  Tools (streaming):")
print("    - toolchain.execute (HIGH, 30s)")
print("    - tool.single (HIGH, 5s)")
print("  Whisper:")
print("    - whisper.transcribe (NORMAL, 10s, GPU)")
print("  Memory:")
print("    - memory.search (HIGH, 1s)")
print("    - memory.save (NORMAL, 0.5s)")
print("    - memory.consolidate (BACKGROUND/LOW, 5s)")
print("  Proactive (background):")
print("    - proactive.generate_thought (BACKGROUND/LOW, 15s)")
print("    - proactive.generate_ideas (BACKGROUND/LOW, 15s)")      # ← FIXED
print("    - proactive.generate_next_steps (BACKGROUND/LOW, 15s)") # ← FIXED
print("    - proactive.actions (BACKGROUND/NORMAL, 20s)")
print("  Focus:")
print("    - focus.set (HIGH, 0.5s)")
print("    - focus.get (LOW, 0.1s)")
print("  System:")
print("    - health_check (LOW, 0.5s)")


# ============================================================================
# USAGE NOTES
# ============================================================================

"""
STREAMING TASKS:
----------------
These tasks yield chunks as they're generated:
- llm.triage
- llm.generate
- llm.fast
- llm.deep
- llm.reasoning
- toolchain.execute

Usage:
    task_id = orchestrator.submit_task("llm.generate", vera_instance=vera, llm_type="fast", prompt="Hello")
    for chunk in orchestrator.stream_result(task_id):
        print(chunk, end='', flush=True)

NON-STREAMING TASKS:
--------------------
These tasks return complete results:
- All memory tasks
- All proactive tasks
- All focus tasks
- System tasks

Usage:
    task_id = orchestrator.submit_task("memory.search", vera_instance=vera, query="...", top_k=5)
    result = orchestrator.wait_for_result(task_id, timeout=5.0)
    print(result.result)

BACKGROUND TASKS:
-----------------
These run async and don't need to wait:
- memory.consolidate
- proactive.generate_thought
- proactive.ideas
- proactive.next_steps
- proactive.actions

Usage:
    # Submit and forget
    task_id = orchestrator.submit_task("proactive.generate_thought", vera_instance=vera)
    # Don't wait, it runs in background
"""