"""
Advanced usage examples for the Unified Orchestrator
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from BackgroundCognition.orchestrator import (
    UnifiedOrchestrator,
    OrchestratorConfig,
    Task,
    TaskType,
    TaskPriority,
    BaseWorker,
    WorkerCapability,
    TaskResult,
)
from BackgroundCognition.orchestrator.workers.base import WorkerStatus, WorkerConfig
from BackgroundCognition.orchestrator.resources import APIQuota


async def example_custom_worker():
    """Example: Create and use a custom worker"""
    print("\n=== Example 1: Custom Worker ===\n")

    # Define custom worker
    class EchoWorker(BaseWorker):
        """Simple echo worker that returns input"""

        def __init__(self):
            super().__init__(
                worker_id="echo-worker",
                capabilities=[WorkerCapability.CUSTOM],
                config=WorkerConfig(max_concurrent_tasks=5),
            )

        async def start(self) -> bool:
            self.status = WorkerStatus.IDLE
            print("Echo worker started")
            return True

        async def stop(self) -> bool:
            self.status = WorkerStatus.OFFLINE
            print("Echo worker stopped")
            return True

        async def execute_task(self, task: Task) -> TaskResult:
            message = task.payload.get('message', '')
            return TaskResult(
                success=True,
                data=f"Echo: {message}",
            )

        async def health_check(self) -> bool:
            return True

    # Initialize orchestrator
    config = OrchestratorConfig(docker_pool_size=0)
    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Register custom worker
        echo_worker = EchoWorker()
        await echo_worker.start()
        await orchestrator.worker_registry.register(echo_worker)

        # Use custom worker
        task = Task(
            type=TaskType.CUSTOM,
            payload={'message': 'Hello, custom worker!'},
            requirements=Task.requirements.__class__(
                worker_capabilities=[WorkerCapability.CUSTOM.value]
            ),
        )

        result = await orchestrator.submit_task(task, wait=True)
        print(f"Result: {result.data}")

    finally:
        await orchestrator.stop()


async def example_llm_api_with_quotas():
    """Example: Register LLM APIs with quotas"""
    print("\n=== Example 2: LLM API with Quotas ===\n")

    config = OrchestratorConfig(docker_pool_size=0)
    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Note: Replace with actual API keys to test
        print("Registering OpenAI API with quota...")

        # Define strict quota
        quota = APIQuota(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000,
            tokens_per_day=100000,
            cost_limit_per_day=5.0,
        )

        # Register (will fail without valid API key, but demonstrates usage)
        try:
            worker_id = await orchestrator.register_llm_api(
                api_type='openai',
                api_key='sk-test-key',  # Replace with real key
                rate_limit_per_minute=10,
                cost_per_1k_tokens=0.002,
                quota=quota,
            )
            print(f"Registered OpenAI worker: {worker_id}")

            # Get resource stats
            stats = orchestrator.resource_manager.get_resource_stats()
            print("\nAPI Usage Summary:")
            print(stats['llm_api_usage'])

        except Exception as e:
            print(f"Note: API registration failed (expected without valid key): {e}")

    finally:
        await orchestrator.stop()


async def example_remote_workers():
    """Example: Work with remote workers"""
    print("\n=== Example 3: Remote Workers ===\n")

    config = OrchestratorConfig(docker_pool_size=0)
    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Register remote worker
        print("Registering remote worker...")

        try:
            worker_id = await orchestrator.register_remote_worker(
                remote_url='http://localhost:8001',  # Example URL
                worker_id='remote-1',
            )
            print(f"Registered remote worker: {worker_id}")

            # List all workers
            worker_list = orchestrator.worker_registry.to_dict()
            print(f"\nTotal workers: {len(worker_list['workers'])}")

        except Exception as e:
            print(f"Note: Remote worker registration failed (expected if not running): {e}")

    finally:
        await orchestrator.stop()


async def example_docker_workers():
    """Example: Use Docker workers"""
    print("\n=== Example 4: Docker Workers ===\n")

    # Enable Docker workers
    config = OrchestratorConfig(
        docker_pool_size=2,
        docker_image='python:3.11-slim',  # Use standard Python image
    )

    orchestrator = UnifiedOrchestrator(config)

    try:
        print("Starting orchestrator with Docker workers...")
        await orchestrator.start()

        # Check workers
        status = orchestrator.get_status()
        print(f"Docker workers: {status['workers']['workers_by_capability'].get('docker', 0)}")

        if status['workers']['total_workers'] > 0:
            # Execute code in Docker
            task = Task(
                type=TaskType.CODE_EXECUTION,
                payload={
                    'code': 'print("Hello from Docker!")\nprint(2 + 2)',
                    'language': 'python',
                },
            )

            result = await orchestrator.submit_task(task, wait=True)

            if result.success:
                print(f"\nCode output:\n{result.data}")
            else:
                print(f"Error: {result.error}")
        else:
            print("No Docker workers available (Docker may not be running)")

    except Exception as e:
        print(f"Docker example error (expected if Docker not running): {e}")

    finally:
        await orchestrator.stop()


async def example_event_hooks():
    """Example: Use event hooks"""
    print("\n=== Example 5: Event Hooks ===\n")

    config = OrchestratorConfig(docker_pool_size=0)
    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Track events
        events = []

        def on_complete(task, result):
            events.append({
                'type': 'complete',
                'task_id': task.id,
                'success': result.success,
                'time': result.execution_time_ms,
            })
            print(f"✓ Task {task.id[:8]} completed in {result.execution_time_ms:.2f}ms")

        def on_failure(task, error):
            events.append({
                'type': 'failure',
                'task_id': task.id,
                'error': error,
            })
            print(f"✗ Task {task.id[:8]} failed: {error}")

        # Set hooks
        orchestrator.on_task_complete = on_complete
        orchestrator.on_task_failed = on_failure

        # Execute some tasks
        print("Executing tasks...\n")

        for i in range(3):
            await orchestrator.execute_llm_request(
                prompt=f"What is {i} + {i}? Answer with just the number.",
            )

        print(f"\nTotal events captured: {len(events)}")
        print(f"Successful: {sum(1 for e in events if e['type'] == 'complete')}")
        print(f"Failed: {sum(1 for e in events if e['type'] == 'failure')}")

    finally:
        await orchestrator.stop()


async def example_complex_workflow():
    """Example: Complex workflow with dependencies and parallel execution"""
    print("\n=== Example 6: Complex Workflow ===\n")

    config = OrchestratorConfig(
        max_concurrent_tasks=5,
        docker_pool_size=0,
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        print("Creating a complex workflow...")
        print("  Task 1: Generate 3 research topics")
        print("  Tasks 2-4: Research each topic (parallel, depends on task 1)")
        print("  Task 5: Synthesize findings (depends on tasks 2-4)\n")

        # Task 1: Generate topics
        task1 = Task(
            id="generate-topics",
            type=TaskType.OLLAMA_REQUEST,
            priority=TaskPriority.HIGH,
            payload={
                'prompt': 'List 3 interesting AI research topics. Reply with just the topics, one per line.',
            },
        )

        # Tasks 2-4: Research each (depend on task 1)
        research_tasks = [
            Task(
                id=f"research-{i}",
                type=TaskType.OLLAMA_REQUEST,
                priority=TaskPriority.NORMAL,
                payload={
                    'prompt': f'Briefly explain the AI research topic from line {i} of the previous response (one sentence).',
                },
                depends_on=["generate-topics"],
            )
            for i in range(1, 4)
        ]

        # Task 5: Synthesize (depends on all research tasks)
        task5 = Task(
            id="synthesize",
            type=TaskType.OLLAMA_REQUEST,
            priority=TaskPriority.HIGH,
            payload={
                'prompt': 'Based on the previous research, what are the common themes? One sentence.',
            },
            depends_on=["research-1", "research-2", "research-3"],
        )

        all_tasks = [task1] + research_tasks + [task5]

        print("Executing workflow...")
        results = await orchestrator.submit_batch(
            all_tasks,
            execute_parallel=True,
            wait=True,
        )

        # Display results
        print("\n--- Results ---")
        for task, result in zip(all_tasks, results):
            if result.success:
                print(f"\n{task.id}:")
                print(f"  {result.data}")
            else:
                print(f"\n{task.id}: Error - {result.error}")

    finally:
        await orchestrator.stop()


async def main():
    """Run all advanced examples"""
    print("=" * 60)
    print("Unified Orchestrator - Advanced Usage Examples")
    print("=" * 60)

    # Check if Ollama is running
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:11434/api/tags', timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status != 200:
                    print("\nWarning: Ollama may not be running. Some examples may fail.")
    except Exception:
        print("\nWarning: Cannot connect to Ollama. Some examples may fail.")

    # Run examples
    try:
        await example_custom_worker()
        await asyncio.sleep(1)

        await example_llm_api_with_quotas()
        await asyncio.sleep(1)

        await example_remote_workers()
        await asyncio.sleep(1)

        await example_docker_workers()
        await asyncio.sleep(1)

        await example_event_hooks()
        await asyncio.sleep(1)

        await example_complex_workflow()

    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\n\nError running examples: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Advanced examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
