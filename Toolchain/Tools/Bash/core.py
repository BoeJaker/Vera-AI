import os
from typing import Optional
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import CommandInput


def truncate_output(text: str, max_length: int = 5000) -> str:
    if len(text) > max_length:
        return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
    return text


class BashTool:
    def __init__(self, agent):
        self.agent = agent

    def _get_sandbox(self):
        fm = getattr(self.agent, "focus_manager", None)
        if fm is not None:
            sb = getattr(fm, "_sandbox", None)
            if sb is not None:
                return sb
        return getattr(self.agent, "runtime_sandbox", None)

    def run_bash_command(self, command: str, working_dir: Optional[str] = None) -> str:
        """Execute a bash shell command and return output."""
        try:
            sandbox = self._get_sandbox()
            if sandbox is None:
                return "[Error] No sandbox available"

            result = sandbox.run(
                command,
                timeout=60,
                working_dir=working_dir or str(sandbox.project_root),
            )

            try:
                m1 = self.agent.mem.upsert_entity(
                    command, "command",
                    labels=["Command"],
                    properties={"shell": "bash", "priority": "high", "working_dir": working_dir or "current"}
                )
                m2 = self.agent.mem.add_session_memory(
                    self.agent.sess.id, command, "Command",
                    {"topic": "bash_command", "agent": "system", "working_dir": working_dir or "current"}
                )
                self.agent.mem.link(m1.id, m2.id, "Executed")
                if result:
                    m3 = self.agent.mem.add_session_memory(
                        self.agent.sess.id, result, "CommandOutput",
                        {"topic": "bash_output", "agent": "system"}
                    )
                    self.agent.mem.link(m1.id, m3.id, "Output")
            except Exception as mem_err:
                print(f"[BashTool] Memory logging failed (non-fatal): {mem_err}")

            return truncate_output(result or "[No output]")

        except Exception as e:
            return f"[Error] Failed to execute command: {str(e)}"


def add_bash_tools(tool_list: list, agent) -> list:
    tools = BashTool(agent)
    tool_list.extend([
        StructuredTool.from_function(
            func=tools.run_bash_command,
            name="bash",
            description="Execute bash command. Returns command output. Use with caution.",
            args_schema=CommandInput
        )
    ])
    return tool_list