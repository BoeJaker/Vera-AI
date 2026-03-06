import traceback
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import PythonInput
from typing import List, Optional


def truncate_output(text: str, max_length: int = 5000) -> str:
    if len(text) > max_length:
        return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
    return text


class PythonTool:
    def __init__(self, agent):
        self.agent = agent

    def _get_sandbox(self):
        fm = getattr(self.agent, "focus_manager", None)
        if fm is not None:
            sb = getattr(fm, "_sandbox", None)
            if sb is not None:
                return sb
        return getattr(self.agent, "runtime_sandbox", None)

    def run_python(self, code: str, working_dir: Optional[str] = None) -> str:
        """Execute Python code inside the sandbox."""
        try:
            sandbox = self._get_sandbox()
            if sandbox is None:
                return "[Python Sandbox Error] No sandbox available"

            scripts_dir = sandbox.project_root / ".vera_scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_path = scripts_dir / "_run.py"
            script_path.write_text(code, encoding="utf-8")

            output = sandbox.run(
                f"python3 {script_path}",
                timeout=60,
                working_dir=working_dir or str(sandbox.project_root),
            )

            try:
                script_path.unlink()
            except Exception:
                pass

            try:
                m1 = self.agent.mem.upsert_entity(
                    code, "python",
                    labels=["Python"],
                    properties={"language": "python", "priority": "high"}
                )
                m2 = self.agent.mem.add_session_memory(
                    self.agent.sess.id, code, "Python",
                    {"topic": "python_execution", "agent": "system"}
                )
                self.agent.mem.link(m1.id, m2.id, "Executed")
                if output:
                    m3 = self.agent.mem.add_session_memory(
                        self.agent.sess.id, output, "PythonOutput",
                        {"topic": "python_result", "agent": "system"}
                    )
                    self.agent.mem.link(m1.id, m3.id, "Output")
            except Exception as mem_err:
                print(f"[PythonTool] Memory logging failed (non-fatal): {mem_err}")

            return truncate_output(output.strip() or "[No output]")

        except Exception:
            return f"[Python Sandbox Error]\n{traceback.format_exc()}"


def add_python_tools(tool_list: List, agent) -> List:
    tools = PythonTool(agent)
    tool_list.extend([
        StructuredTool.from_function(
            func=tools.run_python,
            name="python",
            description="Execute Python code. Use print() for output. Supports both expressions and statements.",
            args_schema=PythonInput
        )
    ])
    return tool_list