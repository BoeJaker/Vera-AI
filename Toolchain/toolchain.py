import json
import time
import traceback
import logging
import re
import asyncio
import inspect
from typing import List, Dict, Any, Callable, Optional, Generator, Union, AsyncGenerator, Tuple
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from functools import wraps
from contextlib import contextmanager
import threading
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---- Enums ----
class ExecutionMode(Enum):
    BATCH = "batch"
    INCREMENTAL = "incremental"
    SPECULATIVE = "speculative"
    HYBRID = "hybrid"

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

class PlanEvaluationStrategy(Enum):
    FIRST_SUCCESS = "first_success"
    MOST_STEPS = "most_steps"
    LLM_SCORE = "llm_score"
    FASTEST = "fastest"

# ---- Data containers ----
@dataclass
class ToolStep:
    tool: str
    input: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    meta: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = field(default=StepStatus.PENDING)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ToolResult:
    step_id: str
    step_num: int
    tool: str
    raw: Any
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)
    duration: float = field(default=0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ExecutionContext:
    query: str
    executed_steps: Dict[str, Any] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

# ---- Decorators ----
def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying function calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise e
                    sleep_time = delay * (backoff ** (attempts - 1))
                    logger.warning(f"Attempt {attempts} failed for {func.__name__}. Retrying in {sleep_time}s: {e}")
                    time.sleep(sleep_time)
        return wrapper
    return decorator

# ---- Planner ----
class ToolChainPlanner:
    """
    Advanced planner/executor with enhanced capabilities.
    """

    DEFAULT_MAX_STEPS = 60
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_SPECULATIVE_WORKERS = 3
    DEFAULT_STEP_TIMEOUT = 30.0
    DEFAULT_MAX_PARALLEL_STEPS = 5

    def __init__(self, agent, tools: List[Any],
                 max_steps: int = DEFAULT_MAX_STEPS,
                 default_retries: int = 1,
                 default_step_timeout: Optional[float] = DEFAULT_STEP_TIMEOUT,
                 speculative_workers: int = DEFAULT_SPECULATIVE_WORKERS,
                 max_parallel_steps: int = DEFAULT_MAX_PARALLEL_STEPS):
        """
        Initialize the ToolChainPlanner.
        """
        self.agent = agent
        self.deep_llm = getattr(agent, "deep_llm", None)
        if self.deep_llm is None:
            raise ValueError("Agent must have a deep_llm attribute")
            
        self.stream_llm = getattr(agent, "stream_llm", None)
        self.tools = tools
        self.tool_map = self._create_tool_map(tools)
        self.max_steps = max_steps
        self.default_retries = default_retries
        self.default_step_timeout = default_step_timeout
        self.speculative_workers = speculative_workers
        self.max_parallel_steps = max_parallel_steps

        # Execution state
        self._current_context: Optional[ExecutionContext] = None
        self._last_plan: Optional[List[ToolStep]] = None
        self._run_log: List[ToolResult] = []
        self._active_tasks: Dict[str, Any] = {}
        self._cancellation_event = threading.Event()
        self._history_lock = threading.Lock()
        
        # Hooks/callbacks
        self.on_plan: Optional[Callable[[Any], None]] = None
        self.on_step_start: Optional[Callable[[ToolStep], None]] = None
        self.on_step_end: Optional[Callable[[ToolStep, ToolResult], None]] = None
        self.on_error: Optional[Callable[[Exception, Optional[ToolStep]], None]] = None
        self.on_progress: Optional[Callable[[float, str], None]] = None

    # ---------------------------
    # Core Execution Methods
    # ---------------------------
    def execute_tool_chain(self, query: str, *,
                mode: str = "incremental",
                initial_plan: Optional[List[ToolStep]] = None,
                max_steps: Optional[int] = None,
                stop_on_error: bool = False,
                allow_replan_on_error: bool = True,
                allow_partial: bool = True,
                step_retries: Optional[int] = None,
                retry_backoff: float = 1.5,
                speculative_strategy: str = "first_success",
                speculative_workers: Optional[int] = None,
                context: Optional[ExecutionContext] = None
                ) -> Generator[Any, None, Any]:
        """
        Main execution generator.
        """
        # Validate and initialize execution
        if max_steps is None:
            max_steps = self.max_steps
        if speculative_workers is None:
            speculative_workers = self.speculative_workers
        if step_retries is None:
            step_retries = self.default_retries
            
        # Create execution context
        self._current_context = context or ExecutionContext(query=query)
        self._cancellation_event.clear()
        
        try:
            # Dispatch to appropriate execution method
            if mode == ExecutionMode.BATCH.value:
                yield from self._execute_batch(
                    query, initial_plan, max_steps, stop_on_error, 
                    step_retries, retry_backoff
                )
            elif mode == ExecutionMode.INCREMENTAL.value:
                yield from self._execute_incremental(
                    query, max_steps, stop_on_error, allow_replan_on_error,
                    allow_partial, step_retries, retry_backoff
                )
            elif mode == ExecutionMode.SPECULATIVE.value:
                yield from self._execute_speculative(
                    query, initial_plan, step_retries, retry_backoff,
                    speculative_strategy, speculative_workers
                )
            elif mode == ExecutionMode.HYBRID.value:
                yield from self._execute_hybrid(
                    query, initial_plan, max_steps, stop_on_error,
                    allow_replan_on_error, allow_partial, step_retries,
                    retry_backoff
                )
            else:
                raise ValueError(f"Unknown execution mode: {mode}")

        except Exception as exc:
            tb = traceback.format_exc()
            error_msg = f"[Planner] Fatal error: {exc}\n{tb}"
            logger.error(error_msg)
            if self.on_error:
                try:
                    self.on_error(exc, None)
                except Exception:
                    pass
            yield error_msg
        finally:
            # Clean up execution context
            self._current_context = None

    def _execute_batch(self, query: str, initial_plan: Optional[List[ToolStep]],
                      max_steps: int, stop_on_error: bool, step_retries: int,
                      retry_backoff: float) -> Generator[Any, None, Any]:
        """
        Execute in batch mode.
        """
        # Prepare plan
        if initial_plan:
            plans = [[self._format_step(s) for s in initial_plan]]
        else:
            plans = self.plan_full(query)
            
        if not plans or not plans[0]:
            yield "[Planner] No plan generated"
            return {}
            
        plan = plans[0]
        self._last_plan = plan
        
        if self.on_plan:
            try:
                self.on_plan(plan)
            except Exception as e:
                logger.error(f"Error in on_plan callback: {e}")

        # Execute sequentially
        executed = {}
        step_num = 0
        
        for raw_step in plan:
            step_num += 1
            if step_num > max_steps:
                yield f"[Planner] Reached max steps {max_steps}"
                break
                
            # Execute step
            step = self._format_step(raw_step)
            if self.on_step_start:
                try:
                    self.on_step_start(step)
                except Exception as e:
                    logger.error(f"Error in on_step_start callback: {e}")
                    
            yield f"[Step {step_num}] Executing: {step.tool}"
            
            try:
                result = self._execute_plan_sequential(
                    [step], initial_executed=executed, 
                    step_offset=step_num-1, retries=step_retries, 
                    retry_backoff=retry_backoff
                )
                executed.update(result)
                yield f"[Step {step_num}] Completed"
            except Exception as e:
                error_msg = f"[Step {step_num}] Error: {e}"
                yield error_msg
                if stop_on_error:
                    break

        # Final goal check
        final_ok = self._check_goal(query, executed)
        if not final_ok:
            yield "[Planner] Goal not fully achieved"
            
        yield executed

    def _execute_incremental(self, query: str, max_steps: int, stop_on_error: bool,
                            allow_replan_on_error: bool, allow_partial: bool,
                            step_retries: int, retry_backoff: float) -> Generator[Any, None, Any]:
        """
        Execute in incremental mode.
        """
        executed = {}
        step_num = 0
        
        while step_num < max_steps:
            step_num += 1
            
            # Plan next step
            try:
                next_step = self.plan_next_step(query, executed)
                if next_step.tool == "DONE":
                    yield "[Planner] DONE signaled by planner"
                    break
                    
            except Exception as e:
                yield f"[Planner] Next-step planning error: {e}"
                if allow_replan_on_error:
                    # Try full plan fallback
                    try:
                        plans = self.plan_full(query, history_context=json.dumps(executed, indent=2))
                        yield f"[Planner] Fallback got {len(plans)} plan(s) — switching to batch of first"
                        plan = plans[0]
                        # Execute remaining plan sequentially
                        result = self._execute_plan_sequential(
                            plan, initial_executed=executed, 
                            step_offset=step_num-1, retries=step_retries, 
                            retry_backoff=retry_backoff
                        )
                        executed.update(result)
                        break
                    except Exception as e2:
                        yield f"[Planner] Full-plan fallback failed: {e2}"
                        if not allow_partial:
                            break
                else:
                    if not allow_partial:
                        break
                    continue

            # Execute the step
            if self.on_step_start:
                try:
                    self.on_step_start(next_step)
                except Exception as e:
                    logger.error(f"Error in on_step_start callback: {e}")
                    
            yield f"[Planner] Executing step {step_num}: {next_step.tool}"
            
            result = self._execute_plan_sequential(
                [next_step], initial_executed=executed, 
                step_offset=step_num-1, retries=step_retries, 
                retry_backoff=retry_backoff
            )
            executed.update(result)

            # Check for errors and handle accordingly
            last_val = executed.get(f"step_{step_num}", "")
            if isinstance(last_val, str) and last_val.startswith("ERROR"):
                yield f"[Planner] Error recorded on step {step_num}: {last_val}"
                if stop_on_error:
                    break
                if allow_replan_on_error:
                    # Request recovery plan
                    yield "[Planner] Requesting recovery plan..."
                    try:
                        recovery_plans = self.plan_full(
                            f"Recover from errors and complete the query: {query}", 
                            history_context=json.dumps(executed, indent=2)
                        )
                        recovery = recovery_plans[0]
                        rec_result = self._execute_plan_sequential(
                            recovery, initial_executed=executed, 
                            step_offset=step_num, retries=step_retries, 
                            retry_backoff=retry_backoff
                        )
                        executed.update(rec_result)
                    except Exception as e:
                        yield f"[Planner] Recovery planning/execution failed: {e}"
                        if not allow_partial:
                            break

            # Check if goal is completed
            if self._check_goal(query, executed):
                yield "[Planner] Goal check indicates completion"
                break

        # Final verification and retry if needed
        if not self._check_goal(query, executed) and allow_replan_on_error:
            try:
                retry_plans = self.plan_full(
                    f"Retry the task ensuring the goal is met. Original query: {query}", 
                    history_context=json.dumps(executed, indent=2)
                )
                retry = retry_plans[0]
                retry_result = self._execute_plan_sequential(
                    retry, initial_executed=executed, 
                    step_offset=step_num, retries=step_retries, 
                    retry_backoff=retry_backoff
                )
                executed.update(retry_result)
            except Exception as e:
                yield f"[Planner] Retry planning/execution failed: {e}"

        yield executed

    def _execute_speculative(self, query: str, initial_plan: Optional[List[ToolStep]],
                           step_retries: int, retry_backoff: float, speculative_strategy: str,
                           speculative_workers: int) -> Generator[Any, None, Any]:
        """
        Execute in speculative mode.
        """
        # Get alternatives
        if initial_plan:
            if isinstance(initial_plan, list) and initial_plan and isinstance(initial_plan[0], list):
                plans = [[self._format_step(s) for s in p] for p in initial_plan]
            elif isinstance(initial_plan, list) and isinstance(initial_plan[0], (dict, ToolStep)):
                plans = [[self._format_step(s) for s in initial_plan]]
            else:
                raise ValueError("initial_plan must be list of steps or list-of-plans in speculative mode")
        else:
            plans = self.plan_full(query)
            
        if not plans:
            yield "[Planner] No plans generated for speculative execution"
            return {}

        yield f"[Planner] Received {len(plans)} speculative plan(s). Spawning workers..."
        
        # Execute plans in parallel
        results_by_plan = {}
        futures = {}
        best_plan_idx = None
        successful_plan_executed = None
        
        with ThreadPoolExecutor(max_workers=speculative_workers) as executor:
            for idx, plan in enumerate(plans):
                future = executor.submit(
                    self._execute_plan_sequential, plan, 
                    {}, 0, step_retries, retry_backoff
                )
                futures[future] = idx

            # Collect results as they complete
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    executed = future.result()
                    results_by_plan[idx] = executed
                    
                    # Evaluate if goal is satisfied
                    ok = self._check_goal(query, executed)
                    yield f"[Planner] Plan {idx} completed. Goal satisfied: {ok}"
                    
                    if ok and speculative_strategy == "first_success":
                        best_plan_idx = idx
                        successful_plan_executed = executed
                        break
                        
                    # For now, just track the first plan as best if none yet
                    if best_plan_idx is None:
                        best_plan_idx = idx
                        successful_plan_executed = executed
                        
                except Exception as e:
                    yield f"[Planner] Plan {idx} execution failed: {e}"
                    results_by_plan[idx] = {"error": str(e)}

        # Return the best result
        final_result = successful_plan_executed or results_by_plan.get(best_plan_idx, {})
        yield f"[Planner] Selected plan: {best_plan_idx}"
        yield final_result

    def _execute_hybrid(self, query: str, initial_plan: Optional[List[ToolStep]],
                       max_steps: int, stop_on_error: bool, allow_replan_on_error: bool,
                       allow_partial: bool, step_retries: int, retry_backoff: float):
        """
        Hybrid execution: Start with batch mode, switch to incremental if issues occur.
        """
        # First try batch execution
        yield "[Planner] Starting in hybrid mode (batch first)"
        
        batch_result = {}
        try:
            for output in self._execute_batch(
                query, initial_plan, max_steps, stop_on_error, 
                step_retries, retry_backoff
            ):
                if isinstance(output, dict):
                    batch_result = output
                yield output
                
            # Check if batch was successful
            if self._check_goal(query, batch_result):
                yield "[Planner] Batch execution completed successfully"
                yield batch_result
                return
                
        except Exception as e:
            yield f"[Planner] Batch execution failed: {e}"
        
        # Fall back to incremental mode
        yield "[Planner] Switching to incremental mode"
        for output in self._execute_incremental(
            query, max_steps, stop_on_error, allow_replan_on_error,
            allow_partial, step_retries, retry_backoff
        ):
            if isinstance(output, dict):
                yield output
            else:
                yield output

    def _execute_plan_sequential(self, plan: List[ToolStep], *,
                                 initial_executed: Optional[Dict[str, Any]] = None,
                                 step_offset: int = 0,
                                 retries: Optional[int] = None,
                                 retry_backoff: float = 1.5) -> Dict[str, Any]:
        """
        Execute a single plan (list of ToolStep) sequentially.
        """
        executed = {} if initial_executed is None else dict(initial_executed)
        step_num = step_offset
        retries = self.default_retries if retries is None else retries

        for raw_step in plan:
            step_num += 1
            step = self._format_step(raw_step)
            
            # Execute the step
            result, success = self._execute_single_step(
                step, executed, step_num, retries, retry_backoff
            )
            
            # Store results
            executed[f"step_{step_num}"] = result
            executed[step.tool] = result
            
            # Create and store ToolResult
            tool_result = ToolResult(
                step_id=step.id,
                step_num=step_num,
                tool=step.tool,
                raw=result,
                success=success,
                error=None if success else result,
                meta=step.meta
            )
            
            with self._history_lock:
                self._run_log.append(tool_result)
                
            # Call step end hook
            if self.on_step_end:
                try:
                    self.on_step_end(step, tool_result)
                except Exception as e:
                    logger.error(f"Error in on_step_end callback: {e}")

        return executed

    @retry(max_attempts=3)
    def _execute_single_step(self, step: ToolStep, executed: Dict[str, Any], 
                            step_num: int, retries: int, retry_backoff: float) -> Tuple[Any, bool]:
        """
        Execute a single tool step with enhanced error handling.
        Properly handles both generator tools (using yield) and regular functions (using return).
        """
        if self._cancellation_event.is_set():
            raise Exception("Execution cancelled")
            
        tool_name = step.tool
        tool_obj = self._tool_by_name(tool_name)
        if tool_obj is None:
            error_msg = f"Tool not found: {tool_name}"
            logger.error(error_msg)
            return error_msg, False

        # Prepare input with placeholders and context
        tool_input = self._resolve_placeholders(step.input, executed, step_num)
        tool_input = self._add_memory_context(tool_name, tool_input)
        
        # Update step status
        step.status = StepStatus.RUNNING
        if self.on_step_start:
            try:
                self.on_step_start(step)
            except Exception as e:
                logger.error(f"Error in on_step_start callback: {e}")
        
        start_time = time.time()
        attempt = 0
        last_exception = None
        
        while attempt <= retries:
            attempt += 1
            if attempt > 1:
                step.status = StepStatus.RETRYING
                logger.info(f"Retrying step {step.tool}, attempt {attempt}")
            
            try:
                # Execute the tool
                result = self._call_tool(tool_obj, tool_input)
                
                # Handle different types of results
                if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict)):
                    # This is an iterable (generator, list, etc.)
                    collected = []
                    is_generator = inspect.isgenerator(result)
                    
                    # Process each chunk
                    for chunk in result:
                        if self._cancellation_event.is_set():
                            raise Exception("Execution cancelled during streaming")
                        
                        # For generators, we might want to yield intermediate results
                        if is_generator and self.on_step_end:
                            # Create a partial result for streaming
                            partial_result = ToolResult(
                                step_id=step.id,
                                step_num=step_num,
                                tool=step.tool,
                                raw=chunk,
                                success=True,
                                meta=step.meta,
                                duration=time.time() - start_time
                            )
                            
                            try:
                                # Notify about partial result
                                self.on_step_end(step, partial_result)
                            except Exception as e:
                                logger.error(f"Error in on_step_end callback for partial result: {e}")
                        
                        collected.append(str(chunk))
                    
                    final_result = "".join(collected)
                    
                else:
                    # Regular function return
                    final_result = result
                self.on_step_end(step, final_result)
                duration = time.time() - start_time
                
                # Save to memory if available
                self._save_step_to_memory(step_num, tool_name, final_result)
                
                # Update step status
                step.status = StepStatus.COMPLETED
                
                return final_result, True
                
            except Exception as e:
                last_exception = e
                error_msg = f"ERROR: {e}"
                logger.warning(f"Tool {tool_name} failed on attempt {attempt}: {e}")
                
                if attempt <= retries:
                    sleep_time = (retry_backoff ** (attempt-1)) * self.DEFAULT_RETRY_DELAY
                    time.sleep(sleep_time)
        
        # All attempts failed
        duration = time.time() - start_time
        error_msg = f"ERROR: {last_exception}" if last_exception else "Unknown error"
        step.status = StepStatus.FAILED
        
        return error_msg, False

    # ---------------------------
    # Planning Methods
    # ---------------------------
    def plan_full(self, query: str, history_context: Optional[str] = None) -> List[List[ToolStep]]:
        """
        Ask deep LLM to produce a full plan.
        """
        tool_list = [
            (getattr(t, "name", str(i)), getattr(t, "description", "")) 
            for i, t in enumerate(self.tools)
        ]
        
        history_text = history_context or ""
        prompt = f"""
You are a planning assistant.
Available tools: {tool_list}
Query: {query}

Previous attempts and outputs:
{history_text}

Produce one or more alternative plans to solve the query.
Rules:
- Use exact tool names above.
- If a value depends on a previous step, reference with {{step_1}}, {{step_2}} or {{prev}}.
- Output JSON only. Either:
  - a single plan as a JSON array: [ {{ "tool": "...", "input": "..." }}, ... ]
  - OR an object: {{ "alternatives": [ [ ...plan1... ], [ ...plan2... ] ] }}
"""
        try:
            # Try streaming first if available
            if self.stream_llm:
                collected = []
                try:
                    for chunk in self.stream_llm(self.deep_llm, prompt):
                        collected.append(chunk)
                    plan_text = "".join(collected)
                except Exception as e:
                    logger.warning(f"Streaming failed, falling back to invoke: {e}")
                    plan_text = self.deep_llm.invoke(prompt)
            else:
                plan_text = self.deep_llm.invoke(prompt)

            plan_text = self._clean_json_fences(plan_text)
            if not plan_text:
                raise ValueError("Planner returned empty plan")

            # Parse the JSON response
            parsed = self._parse_json_response(plan_text)
            plans = self._extract_plans_from_parsed(parsed)
            
            self._last_plan = plans[0] if plans else None
            self._persist_plans_to_memory(plans)
            
            if self.on_plan:
                try:
                    self.on_plan(plans)
                except Exception as e:
                    logger.error(f"Error in on_plan callback: {e}")

            return plans
            
        except Exception as e:
            logger.error(f"Error in plan_full: {e}")
            if self.on_error:
                try:
                    self.on_error(e, None)
                except Exception:
                    pass
            return [[]]

    def plan_next_step(self, query: str, executed: Dict[str, Any], 
                       history_context: Optional[str] = None) -> ToolStep:
        """
        Ask LLM for a single next step given executed outputs so far.
        """
        tool_list = [
            (getattr(t, "name", str(i)), getattr(t, "description", "")) 
            for i, t in enumerate(self.tools)
        ]
        
        executed_json = json.dumps(executed, indent=2)
        prompt = f"""
You are an incremental planner.
Available tools: {tool_list}
Task: {query}

Executed steps so far and their outputs:
{executed_json}

If the task is complete, reply with JSON: {{ "tool": "DONE", "input": "" }}

Otherwise return a single step: {{ "tool": "<tool name>", "input": "<input>" }}
"""
        resp = self.agent.fast_llm.invoke(prompt)
        resp = self._clean_json_fences(resp)
        
        try:
            parsed = json.loads(resp)
        except json.JSONDecodeError:
            # Try to extract JSON object
            try:
                json_match = re.search(r'\{.*\}', resp, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                else:
                    raise ValueError("No JSON object found in response")
            except Exception as e:
                raise ValueError(f"Failed to parse next-step JSON: {e}\nResp:\n{resp}")
                
        return self._format_step(parsed)

    # ---------------------------
    # Utility Methods
    # ---------------------------
    def _create_tool_map(self, tools: List[Any]) -> Dict[str, Any]:
        """Create a mapping of tool names to tool objects."""
        tool_map = {}
        for i, tool in enumerate(tools):
            name = getattr(tool, "name", getattr(tool, "__name__", f"tool_{i}"))
            tool_map[name] = tool
        return tool_map

    def _format_step(self, raw: Union[Dict[str, Any], ToolStep]) -> ToolStep:
        """Convert raw step data to ToolStep object."""
        if isinstance(raw, ToolStep):
            return raw
        if not isinstance(raw, dict):
            raise ValueError("Step must be dict-like or ToolStep")
        return ToolStep(
            tool=raw.get("tool", ""), 
            input=str(raw.get("input", "")), 
            meta=raw.get("meta", {})
        )

    def _clean_json_fences(self, text: str) -> str:
        """Remove JSON code fences from text."""
        if not text:
            return text
            
        # Remove markdown code fences
        text = re.sub(r'^```json\s*', '', text.strip())
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        return text.strip()

    def _parse_json_response(self, text: str) -> Any:
        """Parse JSON response with multiple fallback strategies."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            json_match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
                    
            # If still failing, try to find the first JSON array or object
            try:
                first_bracket = text.index("[")
                last_bracket = text.rindex("]") + 1
                candidate = text[first_bracket:last_bracket]
                return json.loads(candidate)
            except (ValueError, json.JSONDecodeError):
                try:
                    first_brace = text.index("{")
                    last_brace = text.rindex("}") + 1
                    candidate = text[first_brace:last_brace]
                    return json.loads(candidate)
                except (ValueError, json.JSONDecodeError) as e:
                    raise ValueError(f"Failed to parse plan JSON: {e}\nRaw:\n{text}")

    def _extract_plans_from_parsed(self, parsed: Any) -> List[List[ToolStep]]:
        """Extract plans from parsed JSON response."""
        plans = []
        
        if isinstance(parsed, dict) and "alternatives" in parsed:
            for alt in parsed["alternatives"]:
                if isinstance(alt, list):
                    plans.append([self._format_step(s) for s in alt])
        elif isinstance(parsed, list):
            plans.append([self._format_step(s) for s in parsed])
        else:
            raise ValueError("Planner returned unexpected JSON structure")
            
        return plans

    def _persist_plans_to_memory(self, plans: List[List[ToolStep]]) -> None:
        """Persist plans to agent memory if available."""
        try:
            if hasattr(self.agent, "mem"):
                plans_dict = [[s.to_dict() for s in p] for p in plans]
                self.agent.mem.add_session_memory(
                    getattr(self.agent, "sess", type('obj', (object,), {'id': 'default'})).id, 
                    json.dumps(plans_dict), 
                    "Plan", 
                    {"topic": "plan"}, 
                    promote=True
                )
        except Exception as e:
            logger.warning(f"Failed to persist plans to memory: {e}")

    def _resolve_placeholders(self, text: str, executed: Dict[str, Any], step_num: int) -> str:
        """Resolve placeholders in text."""
        if not text:
            return text
            
        # Replace {prev} with previous step result
        if "{prev}" in text:
            prev_result = executed.get(f"step_{step_num-1}", "")
            text = text.replace("{prev}", str(prev_result))
        
        # Replace {step_n} references
        for i in range(1, step_num):
            placeholder = f"{{step_{i}}}"
            if placeholder in text:
                step_result = executed.get(f"step_{i}", "")
                text = text.replace(placeholder, str(step_result))
                
        return text

    def _add_memory_context(self, tool_name: str, tool_input: str) -> str:
        """Add memory context to tool input for LLM tools."""
        if "llm" in tool_name.lower() or any(keyword in tool_name.lower() for keyword in ["query", "ask", "search"]):
            try:
                chat_hist = self.agent.buffer_memory.load_memory_variables({}).get("chat_history", "")
                if chat_hist:
                    return f"Context: {chat_hist}\n{tool_input}"
            except Exception:
                pass
        return tool_input

    def _tool_by_name(self, name: str) -> Optional[Any]:
        """Get tool by name from tool map."""
        return self.tool_map.get(name)

    def _call_tool(self, tool_obj: Any, tool_input: str) -> Any:
        """Call a tool with the given input."""
        # Get the actual callable
        if hasattr(tool_obj, "run") and callable(tool_obj.run):
            func = tool_obj.run
        elif hasattr(tool_obj, "func") and callable(tool_obj.func):
            func = tool_obj.func
        elif callable(tool_obj):
            func = tool_obj
        else:
            raise ValueError(f"Tool {tool_obj} is not callable")
        
        # Call with appropriate parameters
        try:
            sig = inspect.signature(func)
            if len(sig.parameters) > 0:
                # Tool expects input
                return func(tool_input)
            else:
                # Tool doesn't expect input
                return func()
        except TypeError as e:
            # Fallback for tools with different signatures
            try:
                return func(tool_input)
            except:
                return func()

    def _save_step_to_memory(self, step_num: int, tool_name: str, result: Any) -> None:
        """Save step result to agent memory if available."""
        try:
            if hasattr(self.agent, "save_to_memory"):
                self.agent.save_to_memory(f"Step {step_num} - {tool_name}", result)
            if hasattr(self.agent, "mem"):
                self.agent.mem.add_session_memory(
                    getattr(self.agent, "sess", type('obj', (object,), {'id': 'default'})).id, 
                    f"Step {step_num} - {tool_name}: {result}", 
                    "Step", 
                    {"topic": "toolchain"}
                )
        except Exception as e:
            logger.warning(f"Failed to save step to memory: {e}")

    def _check_goal(self, query: str, executed: Dict[str, Any]) -> bool:
        """
        Ask deep_llm to evaluate if the executed outputs meet the query.
        """
        executed_text = json.dumps(executed, indent=2)
        prompt = f"""
You are an evaluator. 
Query: {query}
Execution outputs: {executed_text}

Does the result fully satisfy the query? Answer only 'yes' or 'no'.
"""
        try:
            resp = self.agent.fast_llm.invoke(prompt)
            resp_low = resp.lower().strip()
            
            return resp_low.startswith('yes')
            
        except Exception as e:
            logger.error(f"Goal check failed: {e}")
            return False

    def _check_goal_with_metrics(self, query: str, executed: Dict[str, Any], 
                                metrics: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Enhanced goal checking with performance metrics.
        """
        executed_text = json.dumps(executed, indent=2)
        metrics_text = json.dumps(metrics, indent=2)
        
        prompt = f"""
You are an evaluator. 
Query: {query}
Execution outputs: {executed_text}
Performance metrics: {metrics_text}

Evaluate if the result satisfies the query and provide a quality score (0-100).
Consider:
- Accuracy of the result
- Completeness
- Efficiency (time, cost)
- Resource usage

Respond with JSON: {{"satisfied": boolean, "score": number, "feedback": string}}
"""
        try:
            resp = self.agent.fast_llm.invoke(prompt)
            resp = self._clean_json_fences(resp)
            result = json.loads(resp)
            
            satisfied = result.get("satisfied", False)
            score = result.get("score", 0)
            feedback = result.get("feedback", "")
            
            logger.info(f"Goal check: satisfied={satisfied}, score={score}, feedback={feedback}")
            
            return satisfied, {"score": score, "feedback": feedback}
            
        except Exception as e:
            logger.error(f"Goal check failed: {e}")
            return False, {"error": str(e)}

    # ---------------------------
    # Public Methods
    # ---------------------------
    def cancel_execution(self):
        """Cancel the current execution."""
        self._cancellation_event.set()

    def get_state(self) -> Dict[str, Any]:
        """Get the current state of the planner."""
        return {
            "current_context": self._current_context.to_dict() if self._current_context else None,
            "last_plan": [step.to_dict() for step in self._last_plan] if self._last_plan else None,
            "run_log": [log.to_dict() for log in self._run_log],
            "active_tasks": list(self._active_tasks.keys()),
        }

    def load_state(self, state: Dict[str, Any]):
        """Load a saved state into the planner."""
        if state.get("current_context"):
            self._current_context = ExecutionContext(**state["current_context"])
        
        if state.get("last_plan"):
            self._last_plan = [ToolStep(**step) for step in state["last_plan"]]
        
        if state.get("run_log"):
            self._run_log = [ToolResult(**log) for log in state["run_log"]]

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get metrics about the current execution."""
        if not self._current_context:
            return {}
        
        duration = time.time() - self._current_context.start_time
        successful_steps = sum(1 for log in self._run_log if log.success)
        failed_steps = len(self._run_log) - successful_steps
        
        return {
            "duration": duration,
            "steps_executed": len(self._run_log),
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "success_rate": successful_steps / len(self._run_log) if self._run_log else 0,
        }

    def last_plan(self) -> Optional[List[ToolStep]]:
        return self._last_plan

    def run_log(self) -> List[ToolResult]:
        return self._run_log

    # convenience synchronous runner (consume generator)
    def run_sync(self, *args, **kwargs) -> Dict[str, Any]:
        last = None
        final = {}
        for out in self.execute(*args, **kwargs):
            if isinstance(out, dict):
                final = out
            logger.info(out)
        return final