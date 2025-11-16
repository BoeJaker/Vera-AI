"""
Integration layer for connecting the Unified Orchestrator with existing Vera components
"""

import asyncio
import sys
import os
from typing import Optional, Dict, Any, List

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from BackgroundCognition.orchestrator import (
    UnifiedOrchestrator,
    OrchestratorConfig,
    Task,
    TaskType,
    TaskPriority,
    TaskResult,
)

# Import existing Vera components
try:
    from Toolchain.toolchain import ToolChainPlanner
    from Toolchain.tools import ToolLoader
    TOOLCHAIN_AVAILABLE = True
except ImportError:
    TOOLCHAIN_AVAILABLE = False
    print("Warning: Toolchain not available")

try:
    from BackgroundCognition.proactive_background_focus import ProactiveFocusManager
    FOCUS_MANAGER_AVAILABLE = True
except ImportError:
    FOCUS_MANAGER_AVAILABLE = False
    print("Warning: ProactiveFocusManager not available")


class VeraOrchestratorIntegration:
    """
    Integration layer between Unified Orchestrator and existing Vera components
    """

    def __init__(self, orchestrator: UnifiedOrchestrator):
        self.orchestrator = orchestrator

        # Initialize existing components
        self.toolchain_planner: Optional[ToolChainPlanner] = None
        self.tool_loader: Optional[ToolLoader] = None
        self.focus_manager: Optional[ProactiveFocusManager] = None

        # Tool execution mapping
        self._tool_handlers: Dict[str, Any] = {}

    async def initialize(self):
        """Initialize integration with existing components"""
        # Setup toolchain if available
        if TOOLCHAIN_AVAILABLE:
            await self._setup_toolchain()

        # Setup focus manager if available
        if FOCUS_MANAGER_AVAILABLE:
            await self._setup_focus_manager()

        # Register task handlers
        self._register_handlers()

    async def _setup_toolchain(self):
        """Setup toolchain integration"""
        try:
            self.tool_loader = ToolLoader()
            # Load tools would go here
            print("Toolchain integration initialized")
        except Exception as e:
            print(f"Failed to setup toolchain: {e}")

    async def _setup_focus_manager(self):
        """Setup focus manager integration"""
        try:
            # Focus manager setup would go here
            print("Focus manager integration initialized")
        except Exception as e:
            print(f"Failed to setup focus manager: {e}")

    def _register_handlers(self):
        """Register task handlers for orchestrator"""
        # Register completion hook
        self.orchestrator.on_task_complete = self._handle_task_complete
        self.orchestrator.on_task_failed = self._handle_task_failed

    def _handle_task_complete(self, task: Task, result: TaskResult):
        """Handle task completion"""
        # Log to memory or update focus board
        pass

    def _handle_task_failed(self, task: Task, error: str):
        """Handle task failure"""
        # Log error or update focus board
        pass

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> TaskResult:
        """
        Execute a tool through the orchestrator

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input parameters
            priority: Task priority

        Returns:
            TaskResult
        """
        return await self.orchestrator.execute_tool_call(
            tool_name=tool_name,
            tool_input=tool_input,
            priority=priority,
        )

    async def execute_tool_chain(
        self,
        tool_plan: List[Dict[str, Any]],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> List[TaskResult]:
        """
        Execute a tool chain (sequence of tools)

        Args:
            tool_plan: List of tool steps
            priority: Task priority

        Returns:
            List of TaskResults
        """
        tasks = []
        prev_task_id = None

        for step in tool_plan:
            task = Task(
                type=TaskType.TOOL_CALL,
                priority=priority,
                payload={
                    'tool_name': step['tool'],
                    'tool_input': step.get('input', {}),
                },
                depends_on=[prev_task_id] if prev_task_id else [],
            )
            tasks.append(task)
            prev_task_id = task.id

        # Execute sequentially (due to dependencies)
        results = await self.orchestrator.submit_batch(
            tasks,
            execute_parallel=True,  # Router will respect dependencies
            wait=True,
        )

        return results

    async def execute_background_cognition(
        self,
        context: Dict[str, Any],
        priority: TaskPriority = TaskPriority.BACKGROUND,
    ) -> TaskResult:
        """
        Execute background cognition task

        Args:
            context: Context for background thinking
            priority: Task priority

        Returns:
            TaskResult
        """
        task = Task(
            type=TaskType.BACKGROUND_COGNITION,
            priority=priority,
            payload=context,
        )

        return await self.orchestrator.submit_task(task, wait=True)

    async def ask_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        prefer_local: bool = True,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """
        Ask LLM through orchestrator

        Args:
            prompt: User prompt
            model: Optional model name
            system: Optional system message
            temperature: Temperature
            prefer_local: Prefer local Ollama
            priority: Task priority

        Returns:
            LLM response text
        """
        result = await self.orchestrator.execute_llm_request(
            prompt=prompt,
            model=model,
            system=system,
            temperature=temperature,
            prefer_ollama=prefer_local,
            priority=priority,
        )

        if result.success:
            return result.data
        else:
            raise Exception(f"LLM request failed: {result.error}")

    async def parallel_llm_requests(
        self,
        prompts: List[str],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> List[str]:
        """
        Execute multiple LLM requests in parallel

        Args:
            prompts: List of prompts
            model: Optional model name
            temperature: Temperature

        Returns:
            List of responses
        """
        tasks = [
            Task(
                type=TaskType.OLLAMA_REQUEST,
                payload={
                    'prompt': prompt,
                    'model': model,
                    'temperature': temperature,
                },
            )
            for prompt in prompts
        ]

        results = await self.orchestrator.submit_batch(
            tasks,
            execute_parallel=True,
            wait=True,
        )

        return [
            result.data if result.success else f"Error: {result.error}"
            for result in results
        ]

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics"""
        status = self.orchestrator.get_status()
        return {
            'orchestrator': status,
            'integration': {
                'toolchain_available': TOOLCHAIN_AVAILABLE,
                'focus_manager_available': FOCUS_MANAGER_AVAILABLE,
            }
        }


# Example usage
async def example_integration():
    """Example of using Vera integration"""
    print("=" * 60)
    print("Vera Orchestrator Integration Example")
    print("=" * 60)

    # Initialize orchestrator
    config = OrchestratorConfig(
        docker_pool_size=0,
        max_concurrent_tasks=5,
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    # Create integration layer
    integration = VeraOrchestratorIntegration(orchestrator)
    await integration.initialize()

    try:
        # Example 1: Simple LLM request
        print("\n1. Simple LLM request:")
        response = await integration.ask_llm(
            prompt="What is 2+2? Answer with just the number.",
            prefer_local=True,
        )
        print(f"   Response: {response}")

        # Example 2: Parallel LLM requests
        print("\n2. Parallel LLM requests:")
        responses = await integration.parallel_llm_requests(
            prompts=[
                "Capital of France?",
                "Capital of Japan?",
                "Capital of Brazil?",
            ],
        )
        for i, resp in enumerate(responses, 1):
            print(f"   {i}. {resp}")

        # Example 3: Get metrics
        print("\n3. System metrics:")
        metrics = integration.get_metrics()
        print(f"   Total workers: {metrics['orchestrator']['workers']['total_workers']}")
        print(f"   Tasks completed: {metrics['orchestrator']['metrics']['tasks_completed']}")
        print(f"   Toolchain available: {metrics['integration']['toolchain_available']}")

    finally:
        await orchestrator.stop()

    print("\n" + "=" * 60)
    print("Integration example completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(example_integration())
