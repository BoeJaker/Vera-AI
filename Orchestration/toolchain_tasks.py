
"""
Enhanced Toolchain Task Registration
Adds support for:
- Step-by-step execution (plan as you go)
- Parallel execution (independent branches)
- Adaptive execution (intelligent mode selection)
"""

from Vera.Orchestration.orchestration import task, TaskType, Priority
from Vera.Logging.logging import LogContext
from toolchain_planner_enhanced import EnhancedToolChainPlanner, ExecutionMode

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