

"""
Enhanced Toolchain Task Registration
Adds support for:
- Step-by-step execution (plan as you go)
- Parallel execution (independent branches)
- Adaptive execution (intelligent mode selection)
"""

from Vera.Orchestration.orchestration import task, TaskType, Priority
from Vera.Logging.logging import LogContext
from Vera.Toolchain.enhanced_toolchain_planner import EnhancedToolChainPlanner, ExecutionMode

# Import the extract_chunk_text utility from main task registrations
try:
    from Vera.Orchestration.task_registrations import extract_chunk_text
except ImportError:
    # Fallback implementation
    def extract_chunk_text(chunk):
        if chunk is None:
            return ""
        if isinstance(chunk, str):
            return chunk
        if isinstance(chunk, dict):
            for key in ['text', 'content', 'message', 'data']:
                if key in chunk and chunk[key] is not None:
                    return str(chunk[key])
            return str(chunk)
        if hasattr(chunk, 'text'):
            return str(chunk.text)
        if hasattr(chunk, 'content'):
            return str(chunk.content)
        return str(chunk)


@task("toolchain.execute.stepbystep", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=60.0)
def toolchain_execute_stepbystep(vera_instance, query: str, max_steps: int = 10):
    """
    Execute toolchain in STEP-BY-STEP mode.
    Plans one step, executes it, then plans the next based on results.
    More adaptive than sequential execution.
    
    Args:
        query: The task to accomplish
        max_steps: Maximum number of steps to execute (safety limit)
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={
        'component': 'task',
        'task': 'toolchain.execute.stepbystep',
        'query_length': len(query),
        'max_steps': max_steps
    })
    
    if logger:
        logger.info(
            f"🔧 Step-by-step toolchain execution starting (max {max_steps} steps)",
            context=context
        )
        logger.start_timer("toolchain_stepbystep")
    
    # Create enhanced planner
    if not hasattr(vera_instance, '_enhanced_toolchain'):
        vera_instance._enhanced_toolchain = EnhancedToolChainPlanner(
            vera_instance, 
            vera_instance.tools
        )
    
    planner = vera_instance._enhanced_toolchain
    
    chunk_count = 0
    steps_executed = 0
    
    try:
        for chunk in planner.execute_tool_chain(
            query,
            mode=ExecutionMode.STEP_BY_STEP
        ):
            chunk_text = extract_chunk_text(chunk)
            chunk_count += 1
            
            # Count actual step executions
            if "Executing Tool:" in chunk_text:
                steps_executed += 1
            
            yield chunk_text
        
        if logger:
            duration = logger.stop_timer("toolchain_stepbystep", context=context)
            logger.success(
                f"Step-by-step toolchain complete | {steps_executed} steps | {chunk_count} chunks",
                context=LogContext(extra={
                    **context.extra,
                    'steps_executed': steps_executed,
                    'chunk_count': chunk_count,
                    'duration': duration
                })
            )
    
    except Exception as e:
        if logger:
            duration = logger.stop_timer("toolchain_stepbystep", context=context)
            logger.error(
                f"Step-by-step toolchain failed: {type(e).__name__}: {str(e)}",
                exc_info=True,
                context=LogContext(extra={
                    **context.extra,
                    'steps_executed': steps_executed,
                    'duration': duration,
                    'error': str(e)
                })
            )
        
        yield f"\n[ Toolchain Agent ] ✗ Error: {str(e)}\n"


@task("toolchain.execute.parallel", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=45.0)
def toolchain_execute_parallel(vera_instance, query: str):
    """
    Execute toolchain in PARALLEL mode.
    Plans multiple independent branches and executes them simultaneously.
    Ideal for tasks that can be decomposed into independent subtasks.
    
    Args:
        query: The task to accomplish
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={
        'component': 'task',
        'task': 'toolchain.execute.parallel',
        'query_length': len(query)
    })
    
    if logger:
        logger.info(
            f"🔧 Parallel toolchain execution starting",
            context=context
        )
        logger.start_timer("toolchain_parallel")
    
    # Create enhanced planner
    if not hasattr(vera_instance, '_enhanced_toolchain'):
        vera_instance._enhanced_toolchain = EnhancedToolChainPlanner(
            vera_instance,
            vera_instance.tools
        )
    
    planner = vera_instance._enhanced_toolchain
    
    chunk_count = 0
    branches_detected = 0
    
    try:
        for chunk in planner.execute_tool_chain(
            query,
            mode=ExecutionMode.PARALLEL
        ):
            chunk_text = extract_chunk_text(chunk)
            chunk_count += 1
            
            # Count branches
            if "branches" in chunk_text.lower() and "branch" in chunk_text.lower():
                try:
                    import json
                    # Try to extract branch count from planning output
                    if "{" in chunk_text:
                        # This is approximate - just for logging
                        branches_detected = chunk_text.count('"branch_id"')
                except Exception:
                    pass
            
            yield chunk_text
        
        if logger:
            duration = logger.stop_timer("toolchain_parallel", context=context)
            logger.success(
                f"Parallel toolchain complete | ~{branches_detected} branches | {chunk_count} chunks",
                context=LogContext(extra={
                    **context.extra,
                    'branches_detected': branches_detected,
                    'chunk_count': chunk_count,
                    'duration': duration
                })
            )
    
    except Exception as e:
        if logger:
            duration = logger.stop_timer("toolchain_parallel", context=context)
            logger.error(
                f"Parallel toolchain failed: {type(e).__name__}: {str(e)}",
                exc_info=True,
                context=LogContext(extra={
                    **context.extra,
                    'duration': duration,
                    'error': str(e)
                })
            )
        
        yield f"\n[ Toolchain Agent ] ✗ Error: {str(e)}\n"


@task("toolchain.execute.adaptive", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=50.0)
def toolchain_execute_adaptive(vera_instance, query: str):
    """
    Execute toolchain in ADAPTIVE mode.
    Intelligently chooses between step-by-step and parallel execution
    based on the task structure.
    
    Args:
        query: The task to accomplish
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={
        'component': 'task',
        'task': 'toolchain.execute.adaptive',
        'query_length': len(query)
    })
    
    if logger:
        logger.info(
            f"🔧 Adaptive toolchain execution starting",
            context=context
        )
        logger.start_timer("toolchain_adaptive")
    
    # Create enhanced planner
    if not hasattr(vera_instance, '_enhanced_toolchain'):
        vera_instance._enhanced_toolchain = EnhancedToolChainPlanner(
            vera_instance,
            vera_instance.tools
        )
    
    planner = vera_instance._enhanced_toolchain
    
    chunk_count = 0
    
    try:
        for chunk in planner.execute_tool_chain(
            query,
            mode=ExecutionMode.ADAPTIVE
        ):
            chunk_text = extract_chunk_text(chunk)
            chunk_count += 1
            yield chunk_text
        
        if logger:
            duration = logger.stop_timer("toolchain_adaptive", context=context)
            logger.success(
                f"Adaptive toolchain complete | {chunk_count} chunks",
                context=LogContext(extra={
                    **context.extra,
                    'chunk_count': chunk_count,
                    'duration': duration
                })
            )
    
    except Exception as e:
        if logger:
            duration = logger.stop_timer("toolchain_adaptive", context=context)
            logger.error(
                f"Adaptive toolchain failed: {type(e).__name__}: {str(e)}",
                exc_info=True,
                context=LogContext(extra={
                    **context.extra,
                    'duration': duration,
                    'error': str(e)
                })
            )
        
        yield f"\n[ Toolchain Agent ] ✗ Error: {str(e)}\n"


@task("toolchain.plan.parallel", task_type=TaskType.TOOL, priority=Priority.NORMAL, estimated_duration=10.0)
def toolchain_plan_parallel(vera_instance, query: str):
    """
    Plan a parallel execution strategy without executing.
    Useful for previewing the execution plan.
    
    Args:
        query: The task to plan for
    
    Returns:
        ExecutionPlan object with branches defined
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(extra={
        'component': 'task',
        'task': 'toolchain.plan.parallel',
        'query_length': len(query)
    })
    
    if logger:
        logger.info(f"📋 Planning parallel execution strategy", context=context)
        logger.start_timer("toolchain_plan")
    
    # Create enhanced planner
    if not hasattr(vera_instance, '_enhanced_toolchain'):
        vera_instance._enhanced_toolchain = EnhancedToolChainPlanner(
            vera_instance,
            vera_instance.tools
        )
    
    planner = vera_instance._enhanced_toolchain
    
    plan = None
    chunk_count = 0
    
    try:
        for chunk in planner.plan_parallel_branches(query):
            chunk_count += 1
            
            if hasattr(chunk, 'steps'):  # This is the ExecutionPlan
                plan = chunk
                
                if logger:
                    logger.debug(
                        f"Plan generated: {len(plan.steps)} steps, {len(plan.branches)} branches",
                        context=LogContext(extra={
                            **context.extra,
                            'step_count': len(plan.steps),
                            'branch_count': len(plan.branches)
                        })
                    )
                
                # Yield plan summary
                import json
                yield f"\n[ Toolchain Plan ]\n"
                yield json.dumps(plan.to_dict(), indent=2)
                yield f"\n"
            else:
                # Planning thoughts
                yield extract_chunk_text(chunk)
        
        if logger:
            duration = logger.stop_timer("toolchain_plan", context=context)
            logger.success(
                f"Planning complete | {chunk_count} chunks",
                context=LogContext(extra={
                    **context.extra,
                    'chunk_count': chunk_count,
                    'duration': duration
                })
            )
        
        return plan
    
    except Exception as e:
        if logger:
            duration = logger.stop_timer("toolchain_plan", context=context)
            logger.error(
                f"Planning failed: {type(e).__name__}: {str(e)}",
                exc_info=True,
                context=LogContext(extra={
                    **context.extra,
                    'duration': duration,
                    'error': str(e)
                })
            )
        
        return {"error": str(e)}

@task("toolchain.execute", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=30.0)
def toolchain_execute(vera_instance, query: str, expert:bool=False):
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
                for chunk in (vera_instance.toolchain_expert.execute_tool_chain(query) if expert else vera_instance.toolchain.execute_tool_chain(query)):  
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
        
            except Exception as e:
                log_fallback(logger, "Agent toolchain execution failed", e, context)

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
