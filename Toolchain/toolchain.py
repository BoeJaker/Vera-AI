from typing import List, Dict
import json
import hashlib
import time
import traceback

class ToolChainPlanner:
    def __init__(self, agent, tools):
        self.agent = agent
        self.deep_llm = self.agent.deep_llm
        self.tools = self.agent.tools
        self.history = self.agent.buffer_memory.load_memory_variables({})['chat_history']

    def plan_tool_chain(self, query: str, history_context: str = "") -> List[Dict[str, str]]:
        """Generate a plan from the LLM."""
        planning_prompt = f"""
You are a rigorous, disciplined system planner. You generate ONLY a JSON array describing tool invocations. No commentary, no markdown, no prose.

The user query is:
{query}
"""
        
        plan_json = ""
        
        # Stream and accumulate the plan
        for r in self.agent.stream_llm(self.agent.tool_llm, planning_prompt):
            yield r  # Yield chunks for display
            plan_json += r

        # Clean formatting
        for prefix in ("```json", "```"):
            if plan_json.startswith(prefix):
                plan_json = plan_json[len(prefix):].strip()
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3].strip()

        try:
            tool_plan = json.loads(plan_json)
        except Exception as e:
            raise ValueError(f"Planning failed: {e}\n\n{plan_json}")
        
        print("DEBUG:", type(tool_plan), tool_plan)
        
        # Save plan for replay
        with open("./Configuration/last_tool_plan.json", "w", encoding="utf-8") as f:
            f.write(plan_json)

        # Normalize to list
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        elif isinstance(tool_plan, list):
            if not all(isinstance(s, dict) for s in tool_plan):
                raise ValueError(f"Unexpected tool plan format: {tool_plan}")
        else:
            raise ValueError(f"Unexpected tool plan type: {type(tool_plan)}")
        
        # Store in memory
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self.agent.mem.add_session_memory(
            self.agent.sess.id, 
            f"{json.dumps(tool_plan)}", 
            "Plan", 
            {"topic": "plan", "plan_id": plan_id}, 
            promote=True
        )
        
        # Yield the final parsed plan
        yield tool_plan
    
    # ======================================================================
    # CRITICAL FIX: execute_tool_chain is a CLASS METHOD, not nested!
    # ======================================================================
    def execute_tool_chain(self, query: str, plan=None) -> str:
        """Execute a tool chain, allowing reference to any step output."""
        try:
            if plan is None:
                # Get plan from generator
                gen = self.plan_tool_chain(query)
                tool_plan = None
                
                for r in gen:
                    if isinstance(r, list):  # This is the final plan
                        tool_plan = r
                    else:  # This is a streaming chunk
                        yield r
                
                if tool_plan is None:
                    raise ValueError("No plan generated")
            else:
                tool_plan = plan

        except Exception as e:
            print(f"[ Toolchain Agent ] Error planning tool chain: {e}")
            raise
        
        print(f"[ Toolchain Agent ]\nTool Plan: {json.dumps(tool_plan, indent=2)}")
        
        tool_outputs = {}
        step_num = 0
        errors_detected = False

        for step in tool_plan:
            step_num += 1
            tool_name = step.get("tool")
            raw_input = step.get("input", "")
                        
            # DEBUG: Print the raw_input to see what we're actually getting
            print(f"[ Toolchain Agent ] DEBUG raw_input type: {type(raw_input)}")
            print(f"[ Toolchain Agent ] DEBUG raw_input repr: {repr(raw_input)}")
            if isinstance(raw_input, dict):
                for k, v in raw_input.items():
                    print(f"[ Toolchain Agent ] DEBUG   {k}: {type(v)} = {repr(v)}")
            # ============================================================
            # UNIFIED PLACEHOLDER RESOLUTION
            # ============================================================
            def resolve_placeholders(value, step_num, tool_outputs):
                """Resolve {prev} and {step_N} placeholders in any value."""
                if not isinstance(value, str):
                    return value
                
                # Replace {prev} with previous step output
                if "{prev}" in value:
                    prev_output = str(tool_outputs.get(f"step_{step_num-1}", ""))
                    value = value.replace("{prev}", prev_output)
                
                # Replace {step_N} with that step's output
                for i in range(1, step_num):
                    placeholder = f"{{step_{i}}}"
                    if placeholder in value:
                        step_output = str(tool_outputs.get(f"step_{i}", ""))
                        value = value.replace(placeholder, step_output)
                
                return value
            
            # Handle dict input (multi-parameter tools)
            if isinstance(raw_input, dict):
                tool_input = {}
                for key, value in raw_input.items():
                    tool_input[key] = resolve_placeholders(value, step_num, tool_outputs)
            
            # Handle string input (single-parameter tools)
            else:
                tool_input = resolve_placeholders(str(raw_input), step_num, tool_outputs)
            
            # ============================================================
            # TOOL EXECUTION WITH PROPER ARGUMENT HANDLING
            # ============================================================
            
            # Inject memory context for LLM tools (only for string inputs)
            if "llm" in tool_name and isinstance(tool_input, str):
                context = self.agent.buffer_memory.load_memory_variables({})['chat_history']
                tool_input = f"Context: {context}\n{tool_input}"

            print(f"[ Toolchain Agent ] Step {step_num} - Executing Tool: {tool_name}")
            print(f"[ Toolchain Agent ] Raw input type: {type(raw_input)}")
            print(f"[ Toolchain Agent ] Raw input value: {raw_input}")
            print(f"[ Toolchain Agent ] Processed input type: {type(tool_input)}")
            print(f"[ Toolchain Agent ] Processed input: {json.dumps(tool_input, indent=2) if isinstance(tool_input, dict) else tool_input}")
            yield f"[ Toolchain Agent ] Step {step_num} - Executing Tool: {tool_name}\n"
            
            # Find the tool
            tool = next((t for t in self.tools if t.name == tool_name), None)

            if not tool:
                result = f"Tool not found: {tool_name}"
                errors_detected = True
                yield result
            else:
                try:
                    # ============================================================
                    # CRITICAL FIX: For StructuredTool with dict inputs
                    # ============================================================
                    collected = []
                    result = ""
                    
                    # Check if it's a StructuredTool (has invoke method)
                    if hasattr(tool, 'invoke'):
                        print(f"[ Toolchain Agent ] Using tool.invoke()")
                        
                        try:
                            # Use run() instead of invoke() for StructuredTool
                            if hasattr(tool, 'run'):
                                if isinstance(tool_input, dict):
                                    # StructuredTool.run() with dict should work correctly
                                    result = tool.run(tool_input)
                                else:
                                    result = tool.run(tool_input)
                            else:
                                # Fallback to invoke
                                result = tool.invoke(tool_input)
                            
                            yield result
                            
                        except Exception as e:
                            print(f"[ Toolchain Agent ] Tool execution failed: {e}")
                            print(f"[ Toolchain Agent ] Traceback: {traceback.format_exc()}")
                            raise
                    
                    # Fallback for non-StructuredTool (should rarely happen)
                    else:
                        print(f"[ Toolchain Agent ] Using direct function call")
                        
                        # Get the callable
                        if hasattr(tool, "run") and callable(tool.run):
                            func = tool.run
                        elif hasattr(tool, "func") and callable(tool.func):
                            func = tool.func
                        elif callable(tool):
                            func = tool
                        else:
                            raise ValueError(f"Tool is not callable")
                        
                        try:
                            # Try streaming execution
                            if isinstance(tool_input, dict):
                                # UNPACK dict as keyword arguments
                                for r in func(**tool_input):
                                    yield r
                                    collected.append(r)
                            else:
                                # Pass string directly
                                for r in func(tool_input):
                                    yield r
                                    collected.append(r)
                            
                            result = "".join(str(c) for c in collected)
                            
                        except TypeError:
                            # Not iterable - try non-streaming
                            if isinstance(tool_input, dict):
                                result = func(**tool_input)
                            else:
                                result = func(tool_input)
                            
                            yield result
                    
                    # Store result
                    tool_outputs[f"step_{step_num}"] = result
                    tool_outputs[tool_name] = result
                    
                    # Save to memory
                    self.agent.mem.add_session_memory(
                        self.agent.sess.id, 
                        f"Step {step_num} - {tool_name}\n{result}", 
                        "Step", 
                        {
                            "topic": "step",
                            "author": "toolchain", 
                            "toolchain_step": step_num, 
                            "tool": tool_name
                        }
                    )
                    
                except Exception as e:
                    result = f"Error executing {tool_name}: {str(e)}\n{traceback.format_exc()}"
                    errors_detected = True
                    tool_outputs[f"step_{step_num}"] = result
                    yield result

            print(f"Step {step_num} result: {result[:200]}{'...' if len(result) > 200 else ''}")
            self.agent.save_to_memory(f"Step {step_num} - {tool_name}", result)


        # ============================================================
        # ERROR RECOVERY
        # ============================================================
        if errors_detected:
            print("[ Toolchain Agent ] Errors detected, replanning recovery steps...")
            yield "\n[ Toolchain Agent ] Errors detected, attempting recovery...\n"
            recovery_plan_gen = self.plan_tool_chain(
                f"Recover from the errors and complete the query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            
            recovery_plan = None
            for r in recovery_plan_gen:
                if isinstance(r, list):
                    recovery_plan = r
                    break
            
            if recovery_plan:
                return self.execute_tool_chain(query, plan=recovery_plan)

        # ============================================================
        # GOAL VERIFICATION
        # ============================================================
        review_prompt = f"""
The query was: {query}
Execution results: {json.dumps(tool_outputs.get(f"step_{step_num}", ""), indent=2)}

Does the final result meet the goal? 
Answer only 'yes' or 'no' and explain briefly.
        """
        review = self.agent.fast_llm.invoke(review_prompt)
        
        if "no" in review.lower():
            print("[ Toolchain Agent ] Goal not achieved, replanning...")
            yield "\n[ Toolchain Agent ] Goal not achieved, replanning...\n"
            
            retry_plan_gen = self.plan_tool_chain(
                f"Retry the task ensuring the goal is met. Original query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            
            retry_plan = None
            for r in retry_plan_gen:
                if isinstance(r, list):
                    retry_plan = r
                    break
            
            if retry_plan:
                return self.execute_tool_chain(query, plan=retry_plan)

        return tool_outputs.get(f"step_{step_num}", "")

    def report_history(self) -> str:
        """Generate a report of all tool chains run so far."""
        report_prompt = f"""
You are a summarization assistant.
Here is the short-term memory of all executed tool chains:

{json.dumps(self.history, indent=2)}

Please produce a clear and concise report that summarizes:
- Each query and the plan used
- Key results
- Any patterns or common findings
        """
        return self.deep_llm.invoke(report_prompt)