#!/usr/bin/env python3
"""
Modular Proactive Stages System
================================
Flexible stage-based proactive thinking with:
- Research: Gather information using tools
- Evaluation: Analyze current state and progress
- Optimization: Improve efficiency and approach
- Project Steering: Strategic direction and prioritization
- Introspective Memory Analysis: Learn from past

Features:
- Each stage can call tools
- Stages are composable and configurable
- Memory-aware throughout all stages
- Resource-conscious execution
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StageResult(Enum):
    """Execution result of a stage"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageOutput:
    """Output from a proactive stage"""
    stage_name: str
    result: StageResult
    duration: float
    
    # Generated artifacts
    insights: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    ideas: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    
    # Tool execution results
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    # Memory references
    memory_refs: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'stage_name': self.stage_name,
            'result': self.result.value,
            'duration': self.duration,
            'insights': self.insights,
            'actions': self.actions,
            'ideas': self.ideas,
            'next_steps': self.next_steps,
            'issues': self.issues,
            'tool_calls': self.tool_calls,
            'memory_refs': self.memory_refs,
            'metadata': self.metadata,
            'error_message': self.error_message
        }


class ProactiveStage(ABC):
    """Base class for proactive thinking stages"""
    
    def __init__(self, name: str, description: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.description = description
        self.config = config or {}
        self.enabled = True
    
    @abstractmethod
    def execute(
        self,
        focus_manager,
        context: Dict[str, Any]
    ) -> StageOutput:
        """Execute the stage"""
        pass
    
    def _call_tool(
        self,
        focus_manager,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool and return result"""
        logger.info(f"[{self.name}] Calling tool: {tool_name}")
        
        try:
            # Find tool
            tool = next((t for t in focus_manager.agent.tools if t.name == tool_name), None)
            
            if not tool:
                logger.warning(f"Tool not found: {tool_name}")
                return {"error": f"Tool not found: {tool_name}"}
            
            # Execute tool
            result = tool.run(**tool_input)
            
            logger.info(f"[{self.name}] Tool {tool_name} completed")
            
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": result,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"[{self.name}] Tool execution failed: {e}")
            return {
                "tool": tool_name,
                "input": tool_input,
                "error": str(e),
                "success": False
            }
    
    def _query_memory(
        self,
        focus_manager,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Query hybrid memory"""
        logger.debug(f"[{self.name}] Querying memory: {query}")
        
        try:
            # Query session memory
            session_results = []
            if hasattr(focus_manager.agent, 'sess'):
                session_results = focus_manager.agent.mem.focus_context(
                    focus_manager.agent.sess.id,
                    query,
                    k=top_k
                )
            
            # Query long-term memory
            longterm_results = []
            if hasattr(focus_manager.agent, 'mem'):
                longterm_results = focus_manager.agent.mem.semantic_retrieve(
                    query,
                    k=top_k
                )
            
            # Combine results
            all_results = session_results + longterm_results
            
            logger.debug(f"[{self.name}] Found {len(all_results)} memory results")
            
            return all_results
            
        except Exception as e:
            logger.error(f"[{self.name}] Memory query failed: {e}")
            return []
    
    def _generate_with_llm(
        self,
        focus_manager,
        prompt: str,
        llm_type: str = "deep"
    ) -> str:
        """Generate text with LLM"""
        logger.debug(f"[{self.name}] Generating with {llm_type} LLM")
        
        try:
            if llm_type == "fast":
                llm = focus_manager.agent.fast_llm
            elif llm_type == "reasoning":
                llm = focus_manager.agent.reasoning_llm
            else:
                llm = focus_manager.agent.deep_llm
            
            response = ""
            for chunk in llm.stream(prompt):
                response += str(chunk)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"[{self.name}] LLM generation failed: {e}")
            return ""


class ResearchStage(ProactiveStage):
    """Research stage - gather information using tools"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Research",
            description="Gather information and context using available tools",
            config=config
        )
    
    def execute(self, focus_manager, context: Dict[str, Any]) -> StageOutput:
        """Execute research stage"""
        start_time = time.time()
        output = StageOutput(stage_name=self.name, result=StageResult.SUCCESS, duration=0.0)
        
        try:
            logger.info(f"[{self.name}] Starting research stage")
            
            focus = focus_manager.focus
            board_state = focus_manager.focus_board
            
            # 1. Introspective memory analysis
            logger.info(f"[{self.name}] Analyzing memory for context")
            memory_results = self._query_memory(
                focus_manager,
                f"Project: {focus}. Recent progress and decisions.",
                top_k=8
            )
            
            output.memory_refs = [r.get('id', '') for r in memory_results if r.get('id')]
            
            # Extract insights from memory
            memory_context = "\n".join([
                f"- {r.get('text', r.get('content', ''))[:200]}"
                for r in memory_results[:5]
            ])
            
            # 2. Identify information gaps
            gap_prompt = f"""Project Focus: {focus}

Recent Memory Context:
{memory_context}

Current Progress:
{json.dumps(board_state.get('progress', [])[-5:], indent=2)}

Current Issues:
{json.dumps(board_state.get('issues', [])[-3:], indent=2)}

Identify 3-5 specific information gaps or research questions that would help advance this project.
Be specific and actionable.

Respond with a JSON array of research questions."""
            
            gaps_response = self._generate_with_llm(focus_manager, gap_prompt, llm_type="deep")
            
            try:
                research_questions = json.loads(gaps_response.strip().replace('```json', '').replace('```', ''))
                if not isinstance(research_questions, list):
                    research_questions = [gaps_response]
            except:
                research_questions = [gaps_response]
            
            logger.info(f"[{self.name}] Identified {len(research_questions)} research questions")
            
            # 3. Execute research for each question (use tools if available)
            for question in research_questions[:3]:  # Limit to 3 to avoid overload
                logger.info(f"[{self.name}] Researching: {question}")
                
                # Check if we can use web search tool
                web_search_tool = next(
                    (t for t in focus_manager.agent.tools if 'search' in t.name.lower()),
                    None
                )
                
                if web_search_tool:
                    tool_result = self._call_tool(
                        focus_manager,
                        web_search_tool.name,
                        {"query": question}
                    )
                    output.tool_calls.append(tool_result)
                    
                    if tool_result.get('success'):
                        insight = f"Research finding: {question}\nResult: {str(tool_result.get('output', ''))[:300]}"
                        output.insights.append(insight)
                
                # Also query internal memory
                relevant_memory = self._query_memory(focus_manager, question, top_k=3)
                if relevant_memory:
                    memory_insight = f"Internal knowledge: {question}\n"
                    memory_insight += "\n".join([
                        f"- {r.get('text', '')[:150]}"
                        for r in relevant_memory[:2]
                    ])
                    output.insights.append(memory_insight)
            
            # 4. Synthesize research findings
            synthesis_prompt = f"""Project: {focus}

Research Questions Explored:
{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(research_questions[:3])])}

Findings:
{chr(10).join(output.insights)}

Synthesize the key insights from this research. What are the most important discoveries?
What should be prioritized based on this research?

Provide 2-3 key takeaways."""
            
            synthesis = self._generate_with_llm(focus_manager, synthesis_prompt, llm_type="deep")
            
            # Parse synthesis into insights and next steps
            for line in synthesis.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if any(keyword in line.lower() for keyword in ['should', 'recommend', 'next', 'action']):
                        output.next_steps.append(line.lstrip('- •'))
                    else:
                        output.insights.append(line.lstrip('- •'))
            
            logger.info(f"[{self.name}] Research complete: {len(output.insights)} insights, {len(output.next_steps)} next steps")
            
        except Exception as e:
            logger.error(f"[{self.name}] Stage failed: {e}", exc_info=True)
            output.result = StageResult.FAILED
            output.error_message = str(e)
        
        output.duration = time.time() - start_time
        return output


class EvaluationStage(ProactiveStage):
    """Evaluation stage - analyze current state and progress"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Evaluation",
            description="Analyze current state, progress, and effectiveness",
            config=config
        )
    
    def execute(self, focus_manager, context: Dict[str, Any]) -> StageOutput:
        """Execute evaluation stage"""
        start_time = time.time()
        output = StageOutput(stage_name=self.name, result=StageResult.SUCCESS, duration=0.0)
        
        try:
            logger.info(f"[{self.name}] Starting evaluation stage")
            
            focus = focus_manager.focus
            board_state = focus_manager.focus_board
            
            # 1. Query memory for historical context
            memory_results = self._query_memory(
                focus_manager,
                f"Project: {focus}. Previous evaluations, progress assessments, and outcomes.",
                top_k=10
            )
            
            output.memory_refs = [r.get('id', '') for r in memory_results if r.get('id')]
            
            # 2. Calculate metrics
            metrics = {
                'total_items': sum(len(items) for items in board_state.values()),
                'progress_count': len(board_state.get('progress', [])),
                'issues_count': len(board_state.get('issues', [])),
                'actions_count': len(board_state.get('actions', [])),
                'completed_count': len(board_state.get('completed', [])),
                'next_steps_count': len(board_state.get('next_steps', [])),
                'ideas_count': len(board_state.get('ideas', [])),
            }
            
            # Calculate velocity (items moved to completed recently)
            recent_completed = [
                item for item in board_state.get('completed', [])
                if 'completed_at' in item.get('metadata', {})
            ]
            
            metrics['completion_rate'] = len(recent_completed) / max(metrics['total_items'], 1)
            
            output.metadata['metrics'] = metrics
            
            # 3. Evaluate progress against goals
            eval_prompt = f"""Project Focus: {focus}

Current Board State:
- Total items: {metrics['total_items']}
- Progress: {metrics['progress_count']} items
- Issues: {metrics['issues_count']} items
- Actions: {metrics['actions_count']} pending
- Completed: {metrics['completed_count']} items
- Completion rate: {metrics['completion_rate']:.1%}

Recent Progress:
{json.dumps(board_state.get('progress', [])[-5:], indent=2)}

Outstanding Issues:
{json.dumps(board_state.get('issues', [])[-3:], indent=2)}

Pending Actions:
{json.dumps(board_state.get('actions', [])[-5:], indent=2)}

Evaluate:
1. Are we making good progress toward the focus goal?
2. What's working well?
3. What's not working?
4. Are there blockers or risks?
5. Should we adjust our approach?

Provide structured evaluation with insights and recommendations."""
            
            evaluation = self._generate_with_llm(focus_manager, eval_prompt, llm_type="deep")
            
            # Parse evaluation
            for line in evaluation.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if any(keyword in line.lower() for keyword in ['issue', 'problem', 'blocker', 'risk', 'concern']):
                    output.issues.append(line.lstrip('- •'))
                elif any(keyword in line.lower() for keyword in ['recommend', 'should', 'suggest', 'adjust']):
                    output.next_steps.append(line.lstrip('- •'))
                else:
                    output.insights.append(line.lstrip('- •'))
            
            logger.info(f"[{self.name}] Evaluation complete: {len(output.insights)} insights, {len(output.issues)} issues identified")
            
        except Exception as e:
            logger.error(f"[{self.name}] Stage failed: {e}", exc_info=True)
            output.result = StageResult.FAILED
            output.error_message = str(e)
        
        output.duration = time.time() - start_time
        return output


class OptimizationStage(ProactiveStage):
    """Optimization stage - improve efficiency and approach"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Optimization",
            description="Identify and implement efficiency improvements",
            config=config
        )
    
    def execute(self, focus_manager, context: Dict[str, Any]) -> StageOutput:
        """Execute optimization stage"""
        start_time = time.time()
        output = StageOutput(stage_name=self.name, result=StageResult.SUCCESS, duration=0.0)
        
        try:
            logger.info(f"[{self.name}] Starting optimization stage")
            
            focus = focus_manager.focus
            board_state = focus_manager.focus_board
            
            # 1. Memory introspection - learn from past optimizations
            memory_results = self._query_memory(
                focus_manager,
                f"Project: {focus}. Past optimizations, efficiency improvements, lessons learned.",
                top_k=8
            )
            
            output.memory_refs = [r.get('id', '') for r in memory_results if r.get('id')]
            
            past_optimizations = "\n".join([
                f"- {r.get('text', '')[:150]}"
                for r in memory_results[:5]
            ])
            
            # 2. Identify optimization opportunities
            opt_prompt = f"""Project Focus: {focus}

Past Optimizations:
{past_optimizations}

Current State:
Progress: {len(board_state.get('progress', []))} items
Issues: {len(board_state.get('issues', []))} items
Actions: {len(board_state.get('actions', []))} pending

Recent Actions:
{json.dumps(board_state.get('actions', [])[-5:], indent=2)}

Identify specific optimizations:
1. Redundant or duplicate efforts
2. Process improvements
3. Tool/automation opportunities
4. Resource allocation improvements
5. Workflow streamlining

For each, provide:
- What to optimize
- How to optimize it
- Expected benefit

Respond with JSON array of optimization opportunities."""
            
            optimizations_response = self._generate_with_llm(focus_manager, opt_prompt, llm_type="deep")
            
            try:
                optimizations = json.loads(optimizations_response.strip().replace('```json', '').replace('```', ''))
                if not isinstance(optimizations, list):
                    optimizations = [{'description': optimizations_response, 'benefit': 'Efficiency improvement'}]
            except:
                optimizations = [{'description': optimizations_response, 'benefit': 'Efficiency improvement'}]
            
            # 3. Prioritize optimizations
            for opt in optimizations[:5]:  # Top 5 optimizations
                if isinstance(opt, dict):
                    description = opt.get('description', opt.get('what', str(opt)))
                    benefit = opt.get('benefit', opt.get('expected_benefit', 'Unknown benefit'))
                    
                    output.insights.append(f"Optimization: {description}")
                    output.actions.append({
                        'description': f"Implement: {description}",
                        'priority': 'medium',
                        'expected_benefit': benefit,
                        'tools': []
                    })
            
            logger.info(f"[{self.name}] Identified {len(output.actions)} optimizations")
            
        except Exception as e:
            logger.error(f"[{self.name}] Stage failed: {e}", exc_info=True)
            output.result = StageResult.FAILED
            output.error_message = str(e)
        
        output.duration = time.time() - start_time
        return output


class SteeringStage(ProactiveStage):
    """Steering stage - strategic direction and prioritization"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Steering",
            description="Strategic direction setting and priority adjustment",
            config=config
        )
    
    def execute(self, focus_manager, context: Dict[str, Any]) -> StageOutput:
        """Execute steering stage"""
        start_time = time.time()
        output = StageOutput(stage_name=self.name, result=StageResult.SUCCESS, duration=0.0)
        
        try:
            logger.info(f"[{self.name}] Starting steering stage")
            
            focus = focus_manager.focus
            board_state = focus_manager.focus_board
            
            # Get previous stage results if available
            research_insights = context.get('research', {}).get('insights', [])
            eval_insights = context.get('evaluation', {}).get('insights', [])
            
            # 1. Memory introspection - strategic decisions and direction changes
            memory_results = self._query_memory(
                focus_manager,
                f"Project: {focus}. Strategic decisions, direction changes, pivots, and goal adjustments.",
                top_k=8
            )
            
            output.memory_refs = [r.get('id', '') for r in memory_results if r.get('id')]
            
            # 2. Strategic assessment
            steering_prompt = f"""Project Focus: {focus}

Research Insights:
{chr(10).join(research_insights[:5])}

Evaluation Insights:
{chr(10).join(eval_insights[:5])}

Current Focus Board Summary:
- {len(board_state.get('progress', []))} progress items
- {len(board_state.get('issues', []))} issues
- {len(board_state.get('actions', []))} pending actions
- {len(board_state.get('completed', []))} completed items

Strategic Questions:
1. Is the current focus still the right priority?
2. Should we adjust our goals or approach?
3. What should be our top 3 priorities right now?
4. Are there any strategic pivots we should consider?
5. What's the critical path to success?

Provide strategic guidance and priority recommendations."""
            
            steering = self._generate_with_llm(focus_manager, steering_prompt, llm_type="deep")
            
            # Parse strategic guidance
            priorities = []
            pivots = []
            
            for line in steering.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if any(keyword in line.lower() for keyword in ['priority', 'critical', 'must', 'essential']):
                    priorities.append(line.lstrip('- •'))
                elif any(keyword in line.lower() for keyword in ['pivot', 'change', 'shift', 'adjust direction']):
                    pivots.append(line.lstrip('- •'))
                else:
                    output.insights.append(line.lstrip('- •'))
            
            # Add to output
            output.metadata['strategic_priorities'] = priorities[:3]
            output.metadata['potential_pivots'] = pivots
            
            # Generate priority-based actions
            if priorities:
                for i, priority in enumerate(priorities[:3], 1):
                    output.actions.append({
                        'description': priority,
                        'priority': 'high' if i == 1 else 'medium',
                        'strategic': True,
                        'tools': []
                    })
            
            logger.info(f"[{self.name}] Identified {len(priorities)} strategic priorities")
            
        except Exception as e:
            logger.error(f"[{self.name}] Stage failed: {e}", exc_info=True)
            output.result = StageResult.FAILED
            output.error_message = str(e)
        
        output.duration = time.time() - start_time
        return output


class IntrospectionStage(ProactiveStage):
    """Introspection stage - deep memory analysis and learning"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Introspection",
            description="Deep analysis of memory, patterns, and learning",
            config=config
        )
    
    def execute(self, focus_manager, context: Dict[str, Any]) -> StageOutput:
        """Execute introspection stage"""
        start_time = time.time()
        output = StageOutput(stage_name=self.name, result=StageResult.SUCCESS, duration=0.0)
        
        try:
            logger.info(f"[{self.name}] Starting introspection stage")
            
            focus = focus_manager.focus
            
            # 1. Query memory for patterns
            memory_results = self._query_memory(
                focus_manager,
                f"Project: {focus}. All activities, decisions, and outcomes.",
                top_k=20  # Broader memory scan
            )
            
            output.memory_refs = [r.get('id', '') for r in memory_results if r.get('id')]
            
            # 2. Identify patterns
            pattern_prompt = f"""Project: {focus}

Analyzing {len(memory_results)} memory items from this project.

Recent Memory Entries:
{chr(10).join([f"- {r.get('text', '')[:150]}" for r in memory_results[:10]])}

Identify patterns in:
1. What types of activities are most common?
2. What decisions keep recurring?
3. What challenges appear repeatedly?
4. What approaches work best?
5. What should we learn from this history?

Provide insights about patterns and lessons learned."""
            
            patterns = self._generate_with_llm(focus_manager, pattern_prompt, llm_type="reasoning")
            
            # Parse patterns into insights and lessons
            for line in patterns.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if any(keyword in line.lower() for keyword in ['lesson', 'learn', 'takeaway', 'insight']):
                    output.insights.append(line.lstrip('- •'))
                elif any(keyword in line.lower() for keyword in ['should', 'recommend', 'avoid']):
                    output.next_steps.append(line.lstrip('- •'))
            
            # 3. Knowledge consolidation
            consolidation_prompt = f"""Based on the patterns identified:
{chr(10).join(output.insights[:5])}

What are the 2-3 most important pieces of knowledge we should remember for this project?
What principles or heuristics should guide future decisions?"""
            
            consolidation = self._generate_with_llm(focus_manager, consolidation_prompt, llm_type="deep")
            
            output.metadata['consolidated_knowledge'] = consolidation
            
            logger.info(f"[{self.name}] Introspection complete: {len(output.insights)} insights from {len(memory_results)} memories")
            
        except Exception as e:
            logger.error(f"[{self.name}] Stage failed: {e}", exc_info=True)
            output.result = StageResult.FAILED
            output.error_message = str(e)
        
        output.duration = time.time() - start_time
        return output


class StageOrchestrator:
    """Orchestrates execution of proactive stages"""
    
    def __init__(self, stages: Optional[List[ProactiveStage]] = None):
        if stages is None:
            # Default pipeline
            stages = [
                IntrospectionStage(),  # Start with memory analysis
                ResearchStage(),       # Gather information
                EvaluationStage(),     # Evaluate current state
                OptimizationStage(),   # Improve efficiency
                SteeringStage(),       # Strategic direction
            ]
        
        self.stages = {stage.name: stage for stage in stages}
        self.execution_history: List[Dict[str, Any]] = []
    
    def add_stage(self, stage: ProactiveStage):
        """Add a stage to the orchestrator"""
        self.stages[stage.name] = stage
    
    def remove_stage(self, stage_name: str):
        """Remove a stage"""
        self.stages.pop(stage_name, None)
    
    def enable_stage(self, stage_name: str):
        """Enable a stage"""
        if stage_name in self.stages:
            self.stages[stage_name].enabled = True
    
    def disable_stage(self, stage_name: str):
        """Disable a stage"""
        if stage_name in self.stages:
            self.stages[stage_name].enabled = False
    
    def execute_pipeline(
        self,
        focus_manager,
        stage_names: Optional[List[str]] = None
    ) -> Dict[str, StageOutput]:
        """
        Execute a pipeline of stages.
        Returns dict of stage_name -> StageOutput
        """
        if stage_names is None:
            stage_names = list(self.stages.keys())
        
        results = {}
        context = {}  # Shared context between stages
        
        for stage_name in stage_names:
            stage = self.stages.get(stage_name)
            
            if not stage or not stage.enabled:
                logger.info(f"Skipping stage: {stage_name}")
                continue
            
            logger.info(f"Executing stage: {stage_name}")
            
            try:
                # Execute stage
                output = stage.execute(focus_manager, context)
                results[stage_name] = output
                
                # Add to shared context
                context[stage_name.lower()] = output.to_dict()
                
                # Update focus board with stage results
                self._update_focus_board(focus_manager, output)
                
                logger.info(
                    f"Stage {stage_name} complete: {output.result.value} "
                    f"({output.duration:.2f}s, {len(output.insights)} insights)"
                )
                
            except Exception as e:
                logger.error(f"Stage {stage_name} failed: {e}", exc_info=True)
                results[stage_name] = StageOutput(
                    stage_name=stage_name,
                    result=StageResult.FAILED,
                    duration=0.0,
                    error_message=str(e)
                )
        
        # Record execution
        self.execution_history.append({
            'timestamp': datetime.now().isoformat(),
            'stages': list(results.keys()),
            'results': {name: output.to_dict() for name, output in results.items()}
        })
        
        return results
    
    def _update_focus_board(self, focus_manager, output: StageOutput):
        """Update focus board with stage output"""
        # Add insights to ideas
        for insight in output.insights:
            if insight and insight.strip():
                focus_manager.add_to_focus_board("ideas", insight, metadata={
                    'source': f'stage:{output.stage_name}',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Add next steps
        for step in output.next_steps:
            if step and step.strip():
                focus_manager.add_to_focus_board("next_steps", step, metadata={
                    'source': f'stage:{output.stage_name}',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Add actions
        for action in output.actions:
            if action:
                action_desc = action.get('description', str(action))
                focus_manager.add_to_focus_board("actions", action_desc, metadata={
                    'source': f'stage:{output.stage_name}',
                    'priority': action.get('priority', 'medium'),
                    'tools': action.get('tools', []),
                    'timestamp': datetime.now().isoformat()
                })
        
        # Add issues
        for issue in output.issues:
            if issue and issue.strip():
                focus_manager.add_to_focus_board("issues", issue, metadata={
                    'source': f'stage:{output.stage_name}',
                    'timestamp': datetime.now().isoformat()
                })


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create orchestrator with default stages
    orchestrator = StageOrchestrator()
    
    print(f"Orchestrator initialized with {len(orchestrator.stages)} stages:")
    for name in orchestrator.stages.keys():
        print(f"  - {name}")