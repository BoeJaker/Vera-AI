from typing import List, Dict
import json
import hashlib
import time

class ToolChainPlanner:
    def __init__(self, agent, tools):
        self.agent = agent
        self.deep_llm = self.agent.deep_llm
        self.tools = self.agent.tools
        self.history = self.agent.buffer_memory.load_memory_variables({})['chat_history']

    def plan_tool_chain(self, query: str, history_context: str = "") -> List[Dict[str, str]]:
        """Generate a plan from the LLM."""
        planning_prompt = f"""
            You are a rigorous expert planning assistant.
            Available tools: {[(tool.name, tool.description) for tool in self.tools]}.
            The query is: {query}

            Previous attempts and their outputs:\n{history_context if history_context else ""}

            Plan a comprehensive sequence of tool calls to solve the request.


            Rules for planning:
            - You can reference ANY previous step output using {{step_1}}, {{step_2}}, etc.
            - You can still use {{prev}} to mean the last step's output.
            - DO NOT guess values that depend on previous outputs.
            - Use the exact tool names provided above.

            Respond ONLY in this pure JSON format, no markdown:
            [
            {{ "tool": "<tool name>", "input": "<tool input or '{{step_1}}'>" }},
            {{ "tool": "<tool name>", "input": "<tool input or '{{prev}}'>" }}
            ]
        """
        # plan_json = self.agent.stream_llm_with_memory(self.agent.deep_llm, planning_prompt)
        plan_json=""
        # Get the plan from the LLM and clean up any leading/trailing ```json or ```
        for r in self.agent.stream_llm(self.agent.tool_llm, planning_prompt):
            # print(r)
            yield(r)
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
            raise ValueError(f"Planning failed: {e} \n\n{plan_json}")
        print("DEBUG:", type(tool_plan), tool_plan)
        # Save plan for replay
        with open("./Configuration/last_tool_plan.json", "w", encoding="utf-8") as f:
            f.write(plan_json)

        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        elif isinstance(tool_plan, list):
            if not all(isinstance(s, dict) for s in tool_plan):
                raise ValueError(f"Unexpected tool plan format: {tool_plan}")
        else:
            raise ValueError(f"Unexpected tool plan type: {type(tool_plan)}")
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self.agent.mem.add_session_memory(self.agent.sess.id, f"{json.dumps(tool_plan)}", "Plan", {"topic": "plan","plan id" : plan_id}, promote=True)
        yield tool_plan

    def execute_tool_chain(self, query: str, plan=None ) -> str:
        """Execute a tool chain, allowing reference to any step output."""
        try:
            if plan == None:
                gen = self.plan_tool_chain(query)
                for r in gen:
                    yield r
                    tool_plan = r
            else:
                tool_plan = plan

        except StopIteration as e:
            print(f"[ Toolchain Agent ]\nTool Plan: {json.dumps(e.value, indent=2)}")
            tool_plan = e.value
        except Exception as e:
            print(f"[ Toolchain Agent ] Error planning tool chain: {e}")
        print(f"[ Toolchain Agent ]\nTool Plan: {json.dumps(tool_plan, indent=2)}")
        # tool_plan = self.plan_tool_chain(query)
        tool_outputs = {}
        step_num = 0
        errors_detected = False

        for step in tool_plan:
            step_num += 1
            tool_name = step.get("tool")
            tool_input = str(step.get("input", ""))
            # yield(f"\nExecuting step: {step}\n{tool_name} input: {tool_input}"))
            # Resolve placeholders like {prev} or {step_2}
            if "{prev}" in tool_input:
                tool_input = tool_input.replace("{prev}", str(tool_outputs.get(f"step_{step_num-1}", "")))
            for i in range(1, step_num):
                tool_input = tool_input.replace(f"{{step_{i}}}", str(tool_outputs.get(f"step_{i}", "")))

            # Inject memory for LLM tools
            if "llm" in tool_name:
                tool_input = f"Context: {self.agent.buffer_memory.load_memory_variables({})['chat_history']}\n" + tool_input

            print(f"[ Toolchain Agent ] Step {step_num} - Executing Tool: {tool_name}, Input: {tool_input}")
            yield(f"[ Toolchain Agent ] Step {step_num} - Executing Tool: {tool_name}, Input: {tool_input}")
            tool = next((t for t in self.tools if t.name == tool_name), None)

            if not tool:
                result = f"Tool not found: {tool_name}"
                errors_detected = True
            else:
                try:
                    if hasattr(tool, "run") and callable(tool.run):
                        func = tool.run
                    elif hasattr(tool, "func") and callable(tool.func):
                        func = tool.func
                    elif callable(tool):
                        func = tool
                    else:
                        raise ValueError(f"Tool is not callable")

                    collected = []
                    result=""
                    try:
                        for r in func(tool_input):
                            # print(f"Step result: {r}")
                            yield r
                            collected.append(r)
                    except TypeError:
                        # Not iterable — call again and yield single result
                        result = func(tool_input)
                        # print(f"Step result: {result}")
                        yield result
                    else:
                        # Combine collected results here if needed:
                        result = "".join(str(c) for c in collected)
                        self.agent.mem.add_session_memory(self.agent.sess.id, f"Step {step_num} - {tool_name}\n{result}", "Step", {"topic": "step","author": "toolchain", "toolchain step": step_num, "tool": tool_name, "plan id": plan_id})
                        yield result
                    # store result or return if you want
                    # tool_outputs[tool_name] = result
                    prev_output = result
                    tool_outputs[tool_name] = result
                    # self.save_to_memory(query, tool_outputs[tool_name])
                except Exception as e:
                    tool_outputs[tool_name] = f"Error executing {tool_name}: {e}"
                    prev_output = None
                    print(tool_outputs)
            
                # try:
                #     if hasattr(tool, "run") and callable(tool.run):
                #         result = tool.run(tool_input)
                #     elif hasattr(tool, "func") and callable(tool.func):
                #         result = tool.func(tool_input)
                #     elif callable(tool):
                #         result = tool(tool_input)
                #     else:
                #         raise ValueError(f"Tool {tool_name} is not callable.")
                # except Exception as e:
                #     result = f"Error executing {tool_name}: {str(e)}"
                #     errors_detected = True

                print(f"Step {step_num} result: {result}")
                yield(f"Step {step_num} result: {result}")
                tool_outputs[f"step_{step_num}"] = result
                self.agent.save_to_memory(f"Step {step_num} - {tool_name}", result)
                # try:
                #     self.agent.mem.add_session_memory(self.agent.sess.id, f"Step {step_num} - {tool_name}: {result}", "Step", {"topic": "toolchain"})
                # except:
                #     pass

        # If error detected → re-plan recovery step
        if errors_detected:
            print("[ Toolchain Agent ] Errors detected, replanning recovery steps...")
            recovery_plan = self.plan_tool_chain(
                f"Recover from the errors and complete the query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            tool_plan.extend(recovery_plan)
            return self.execute_tool_chain(query, plan=recovery_plan)  # re-run with recovery

        # Final goal check
        review_prompt = f"""
            The query was: {query}
            Execution results: {json.dumps(tool_outputs.get(f"step_{step_num}", ""), indent=2)}

            Does the final result meet the goal? 
            Answer only 'yes' or 'no' and explain briefly.
        """
        review = self.agent.fast_llm.invoke(review_prompt)
        if "no" in review.lower():
            print("[ Toolchain Agent ] Goal not achieved, replanning...")
            yield("[ Toolchain Agent ] Goal not achieved, replanning...")
            retry_plan = self.plan_tool_chain(
                f"Retry the task ensuring the goal is met. Original query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            return self.execute_tool_chain(query)

        # # Merge results into a final answer
        # merge_prompt = f"""
        #     The query was: {query}
        #     The following tools were executed with their outputs:
        #     {tool_outputs}

        #     Create a final answer that combines all the results.
        #     """
        # final_answer = self.deep_llm.invoke(merge_prompt)

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
