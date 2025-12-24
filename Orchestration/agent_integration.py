#!/usr/bin/env python3
# Vera/Orchestration/agent_task_integration.py

"""
Agent-Task Integration
Utilities for routing tasks to configured agents
"""

from typing import Optional, Dict, Any
from Vera.Orchestration.orchestration import task, TaskType, Priority
from Vera.Logging.logging import LogContext


class AgentTaskRouter:
    """
    Routes tasks to appropriate agents based on configuration
    """
    
    def __init__(self, vera_instance):
        self.vera = vera_instance
        self.agents = vera_instance.agents if hasattr(vera_instance, 'agents') else None
        self.logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
        
        if self.logger:
            agent_count = len(self.agents.list_loaded_agents()) if self.agents else 0
            self.logger.info(
                f"AgentTaskRouter initialized (agents_available={agent_count})",
                context=LogContext(extra={'component': 'agent_router'})
            )
            
            if self.agents:
                self.logger.debug(
                    f"Available agents: {', '.join(str(self.agents.list_loaded_agents()))}",
                    context=LogContext(extra={'component': 'agent_router'})
                )
    
    def get_agent_for_task(self, task_type: str) -> str:
        """Get agent name for a task type"""
        context = LogContext(extra={'component': 'agent_router', 'task_type': task_type})
        
        if self.logger:
            self.logger.debug(f"Selecting agent for task type: {task_type}", context=context)
        
        if not self.agents:
            # Fallback to base models (with your fixes)
            fallback_map = {
                'triage': self.vera.selected_models.fast_llm,
                'fast': self.vera.selected_models.fast_llm,
                'tool_execution': self.vera.selected_models.tool_llm or self.vera.selected_models.fast_llm,
                'reasoning': self.vera.selected_models.reasoning_llm or self.vera.selected_models.fast_llm,
                'conversation': self.vera.selected_models.fast_llm,
                'planning': self.vera.selected_models.intermediate_llm or self.vera.selected_models.fast_llm,
                'review': self.vera.selected_models.deep_llm or self.vera.selected_models.fast_llm,
            }
            agent_name = fallback_map.get(task_type, self.vera.selected_models.fast_llm)
        else:
            # Get from agent configuration
            agent_name = self.vera.config.agents.default_agents.get(
                task_type,
                self.vera.selected_models.fast_llm
            )
        
        # ✓ CRITICAL: Ensure agent_name is never None regardless of path
        if agent_name is None:
            agent_name = "gemma2"  # Ultimate hardcoded fallback
            if self.logger:
                self.logger.warning(
                    f"Agent name was None for task_type '{task_type}', using hardcoded fallback: {agent_name}",
                    context=context
                )
        
        if self.logger:
            self.logger.info(f"Agent routing: {task_type} → {agent_name}", context=context)
        
        return agent_name
        
    def create_llm_for_agent(self, agent_name: str, override_params: Optional[Dict] = None):
        """
        Create LLM using agent configuration
        
        Args:
            agent_name: Name of agent
            override_params: Optional parameter overrides
        
        Returns:
            Configured LLM instance
        """
        context = LogContext(
            agent=agent_name,
            extra={'component': 'agent_router'}
        )
        
        if self.logger:
            self.logger.info(f"Creating LLM for agent: {agent_name}", context=context)
            self.logger.start_timer(f"create_llm_{agent_name}")
        
        if self.agents:
            try:
                if self.logger:
                    self.logger.debug("Attempting agent config LLM creation", context=context)
                
                llm = self.agents.create_llm_with_agent_config(
                    agent_name,
                    self.vera.ollama_manager
                )
                
                if self.logger:
                    duration = self.logger.stop_timer(f"create_llm_{agent_name}", context=context)
                    duration = duration if duration is not None else 0.0
                    # Get agent config for logging
                    agent_config = self.agents.get_agent_config(agent_name)
                    if agent_config:
                        self.logger.success(
                            f"LLM created from agent config in {duration:.3f}s",
                            context=LogContext(
                                agent=agent_name,
                                model=agent_config.base_model,
                                extra={
                                    'component': 'agent_router',
                                    'temperature': agent_config.parameters.temperature,  # ← Fixed: nested access
                                    'context_length': agent_config.num_ctx  # ← Fixed: correct attribute name
                                }
                            )
                        )
                    else:
                        self.logger.success(f"LLM created in {duration:.3f}s", context=context)
                
                return llm
            
            except Exception as e:
                if self.logger:
                    duration = self.logger.stop_timer(f"create_llm_{agent_name}", context=context)
                    duration = duration if duration is not None else 0.0
                    self.logger.warning(
                        f"Failed to create LLM from agent config after {duration:.3f}s: {e}, using fallback",
                        context=context
                    )
        
        # Fallback to standard model
        if self.logger:
            self.logger.info("Using fallback LLM creation", context=context)
        
        params = {'model': agent_name, 'temperature': 0.7}
        if override_params:
            params.update(override_params)
            if self.logger:
                self.logger.debug(f"Applying overrides: {override_params}", context=context)
        
        llm = self.vera.ollama_manager.create_llm(**params)
        
        if self.logger:
            duration = self.logger.stop_timer(f"create_llm_{agent_name}", context=context)
            self.logger.success(f"Fallback LLM created in {duration:.3f}s", context=context)
        
        return llm
    
    def get_agent_memory_config(self, agent_name: str) -> Dict[str, Any]:
        """Get memory configuration for agent"""
        context = LogContext(
            agent=agent_name,
            extra={'component': 'agent_router'}
        )
        
        if self.logger:
            self.logger.debug(f"Retrieving memory config for: {agent_name}", context=context)
        
        if self.agents:
            config = self.agents.get_agent_memory_config(agent_name)
            
            if self.logger:
                self.logger.trace(
                    f"Memory config: vector={config.get('use_vector')}, "
                    f"neo4j={config.get('use_neo4j')}, "
                    f"triage={config.get('enable_triage')}",
                    context=context
                )
            
            return config
        
        # Default memory config
        default_config = {
            'use_vector': True,
            'use_neo4j': True,
            'vector_top_k': 8,
            'neo4j_limit': 16,
            'enable_triage': False
        }
        
        if self.logger:
            self.logger.debug("Using default memory config", context=context)
        
        return default_config
    
    def get_agent_tools(self, agent_name: str) -> list:
        """Get allowed tools for agent"""
        return self.vera.tools
        # context = LogContext(
        #     agent=agent_name,
        #     extra={'component': 'agent_router'}
        # )
        
        # if self.logger:
        #     self.logger.debug(f"Retrieving tools for: {agent_name}", context=context)
        
        # if not self.agents:
        #     if self.logger:
        #         self.logger.debug(
        #             f"No agent system, returning all {len(self.vera.tools)} tools",
        #             context=context
        #         )
        #     return self.vera.tools
        
        # config = self.agents.get_agent_config(agent_name)
        # if not config or not config.tools:
        #     if self.logger:
        #         self.logger.debug(
        #             f"No tool restrictions, returning all {len(self.vera.tools)} tools",
        #             context=context
        #         )
        #     return self.vera.tools
        
        # # Filter tools based on agent config
        # allowed_tool_names = set(config.tools)
        # filtered_tools = [t for t in self.vera.tools if t.name in allowed_tool_names]
        
        # if self.logger:
        #     excluded_count = len(self.vera.tools) - len(filtered_tools)
        #     self.logger.info(
        #         f"Tool filtering: {len(filtered_tools)}/{len(self.vera.tools)} allowed",
        #         context=context
        #     )
            
        #     if filtered_tools:
        #         self.logger.debug(
        #             f"Allowed tools: {', '.join([t.name for t in filtered_tools])}",
        #             context=context
        #         )
            
        #     if excluded_count > 0:
        #         excluded_names = [t.name for t in self.vera.tools if t.name not in allowed_tool_names]
        #         self.logger.debug(
        #             f"Excluded tools ({excluded_count}): {', '.join(excluded_names)}",
        #             context=context
        #         )
        
        # return filtered_tools


# =============================================================================
# AGENT-AWARE TASK DECORATORS
# =============================================================================

def agent_task(
    task_name: str,
    agent_type: str,
    task_type: TaskType = TaskType.LLM,
    priority: Priority = Priority.NORMAL,
    **task_kwargs
):
    """
    Decorator for agent-aware tasks
    
    Usage:
        @agent_task("reasoning.analyze", agent_type="reasoning")
        def analyze_with_reasoning(vera_instance, query: str):
            router = AgentTaskRouter(vera_instance)
            agent_name = router.get_agent_for_task("reasoning")
            llm = router.create_llm_for_agent(agent_name)
            # ... use llm
    """
    def decorator(func):
        # Wrap the function to inject agent routing
        def wrapped(vera_instance, *args, **kwargs):
            router = AgentTaskRouter(vera_instance)
            
            # Add router to kwargs
            kwargs['agent_router'] = router
            kwargs['agent_name'] = router.get_agent_for_task(agent_type)
            
            return func(vera_instance, *args, **kwargs)
        
        # Apply the @task decorator
        return task(task_name, task_type=task_type, priority=priority, **task_kwargs)(wrapped)
    
    return decorator


# =============================================================================
# AGENT-SPECIFIC TASKS
# =============================================================================

@agent_task("agent.triage", agent_type="triage", priority=Priority.CRITICAL, estimated_duration=2.0)
def agent_triage(vera_instance, query: str, agent_router=None, agent_name=None):
    """
    Triage using configured agent.
    Agent has classification instructions baked in.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(
        agent=agent_name,
        extra={'component': 'agent_task', 'task': 'triage'}
    )
    
    if logger:
        logger.info(f"Starting triage task with agent: {agent_name}", context=context)
        logger.start_timer("agent_triage")
    
    llm = agent_router.create_llm_for_agent(agent_name)
    
    # Agent already has triage instructions - just provide context
    focus = vera_instance.focus_manager.focus if hasattr(vera_instance, 'focus_manager') else 'None'
    user_prompt = f"Current focus: {focus}\n\nQuery: {query}"
    
    if logger:
        logger.debug(f"Triage query: {len(query)} chars, focus: {focus}", context=context)
    
    chunk_count = 0
    for chunk in llm.stream(user_prompt):
        chunk_count += 1
        yield chunk
    
    if logger:
        duration = logger.stop_timer("agent_triage", context=context)
        logger.success(f"Triage complete in {duration:.2f}s ({chunk_count} chunks)", context=context)


@agent_task("agent.reason", agent_type="reasoning", priority=Priority.HIGH, estimated_duration=15.0)
def agent_reasoning(vera_instance, prompt: str, agent_router=None, agent_name=None):
    """
    Reasoning task using configured agent.
    Agent has reasoning instructions baked in.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(
        agent=agent_name,
        extra={'component': 'agent_task', 'task': 'reasoning'}
    )
    
    if logger:
        logger.info(f"Starting reasoning task with agent: {agent_name}", context=context)
        logger.start_timer("agent_reasoning")
    
    llm = agent_router.create_llm_for_agent(agent_name)
    
    # Get memory config for this agent
    memory_config = agent_router.get_agent_memory_config(agent_name)
    
    if logger:
        logger.debug(
            f"Memory config: vector={memory_config['use_vector']}, "
            f"neo4j={memory_config['use_neo4j']}",
            context=context
        )
    
    # Agent has reasoning guidelines - just add memory context if allowed
    if memory_config['use_vector']:
        if logger:
            logger.debug("Loading vector memory context", context=context)
        
        past_context = vera_instance.memory.load_memory_variables(
            {"input": prompt}
        ).get("chat_history", "")
        
        full_prompt = f"Previous conversation:\n{past_context}\n\nUser query: {prompt}"
        
        if logger:
            logger.debug(f"Added {len(past_context)} chars of context", context=context)
    else:
        full_prompt = prompt
        if logger:
            logger.debug("Memory disabled for this agent", context=context)
    
    chunk_count = 0
    for chunk in llm.stream(full_prompt):
        chunk_count += 1
        yield chunk
    
    if logger:
        duration = logger.stop_timer("agent_reasoning", context=context)
        logger.success(f"Reasoning complete in {duration:.2f}s ({chunk_count} chunks)", context=context)


@agent_task("agent.plan", agent_type="planning", priority=Priority.HIGH, estimated_duration=10.0)
def agent_planning(vera_instance, goal: str, agent_router=None, agent_name=None):
    """
    Planning task using configured agent.
    Agent has planning instructions baked in.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(
        agent=agent_name,
        extra={'component': 'agent_task', 'task': 'planning'}
    )
    
    if logger:
        logger.info(f"Starting planning task with agent: {agent_name}", context=context)
        logger.start_timer("agent_planning")
    
    llm = agent_router.create_llm_for_agent(agent_name)
    
    # Agent knows how to plan - just provide context
    available_tools = [t.name for t in agent_router.get_agent_tools(agent_name)]
    
    if logger:
        logger.debug(f"Available tools: {len(available_tools)}", context=context)
        logger.trace(f"Tools: {', '.join(available_tools)}", context=context)
    
    planning_prompt = f"""Goal: {goal}

Available tools: {', '.join(available_tools)}

Create a step-by-step plan."""
    
    chunk_count = 0
    for chunk in llm.stream(planning_prompt):
        chunk_count += 1
        yield chunk
    
    if logger:
        duration = logger.stop_timer("agent_planning", context=context)
        logger.success(f"Planning complete in {duration:.2f}s ({chunk_count} chunks)", context=context)

@agent_task("agent.tool_execute", agent_type="tool_execution", task_type=TaskType.TOOL, priority=Priority.HIGH, estimated_duration=20.0)
def agent_tool_execution(vera_instance, query: str, agent_router=None, agent_name=None):
    """Tool execution using agent configuration"""
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(
        agent=agent_name,
        extra={'component': 'agent_task', 'task': 'tool_execution'}
    )
    
    if logger:
        logger.info(f"Starting tool execution with agent: {agent_name}", context=context)
        logger.start_timer("agent_tool_execution")
    
    llm = agent_router.create_llm_for_agent(agent_name)
    tools = agent_router.get_agent_tools(agent_name)
    
    # CHECK: Is this a pre-built agent with instructions baked in?
    agent_config = agent_router.agents.get_agent_config(agent_name) if agent_router.agents else None
    
    if agent_config:
        # Agent has instructions - use minimal prompt, manual tool loop
        if logger:
            logger.debug(f"Using agent-native tool execution (minimal prompt)", context=context)
        
        # Simple tool execution loop without framework overhead
        chunk_count = 0
        
        # Just stream with the query - agent knows what to do
        for chunk in llm.stream(query):
            chunk_count += 1
            yield chunk
        
        if logger:
            duration = logger.stop_timer("agent_tool_execution", context=context)
            logger.success(
                f"Tool execution complete in {duration:.2f}s ({chunk_count} chunks)",
                context=context
            )
    else:
        # Fall back to standard toolchain with full instructions
        if logger:
            logger.debug(f"Using standard toolchain (adding instructions)", context=context)
        
        original_llm = vera_instance.tool_llm
        original_tools = vera_instance.toolkit
        
        try:
            vera_instance.tool_llm = llm
            vera_instance.toolkit = tools
            
            chunk_count = 0
            for chunk in vera_instance.toolchain.execute_tool_chain(query):
                chunk_count += 1
                yield chunk
            
            if logger:
                duration = logger.stop_timer("agent_tool_execution", context=context)
                logger.success(
                    f"Tool execution complete in {duration:.2f}s ({chunk_count} chunks)",
                    context=context
                )
        
        finally:
            vera_instance.tool_llm = original_llm
            vera_instance.toolkit = original_tools


@agent_task("agent.review", agent_type="review", priority=Priority.NORMAL, estimated_duration=10.0)
def agent_review(vera_instance, content: str, agent_router=None, agent_name=None):
    """
    Review content using configured agent.
    Agent has review criteria baked in.
    """
    logger = vera_instance.logger if hasattr(vera_instance, 'logger') else None
    context = LogContext(
        agent=agent_name,
        extra={'component': 'agent_task', 'task': 'review'}
    )
    
    if logger:
        logger.info(f"Starting review task with agent: {agent_name}", context=context)
        logger.start_timer("agent_review")
        logger.debug(f"Content length: {len(content)} chars", context=context)
    
    llm = agent_router.create_llm_for_agent(agent_name)
    
    # Agent knows how to review - just provide the content
    review_prompt = f"Please review this content:\n\n{content}"
    
    chunk_count = 0
    for chunk in llm.stream(review_prompt):
        chunk_count += 1
        yield chunk
    
    if logger:
        duration = logger.stop_timer("agent_review", context=context)
        logger.success(f"Review complete in {duration:.2f}s ({chunk_count} chunks)", context=context)


# =============================================================================
# REGISTER AGENT TASKS
# =============================================================================

print("[AgentTaskIntegration] Registered agent-aware tasks:")
print("  • agent.triage (CRITICAL, 2s)")
print("  • agent.reason (HIGH, 15s)")
print("  • agent.plan (HIGH, 10s)")
print("  • agent.tool_execute (HIGH, 20s)")
print("  • agent.review (NORMAL, 10s)")