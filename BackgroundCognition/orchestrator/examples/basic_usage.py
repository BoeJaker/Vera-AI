"""
Basic usage examples for the Unified Orchestrator
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
)


async def example_basic_llm_request():
    """Example: Basic LLM request using Ollama"""
    print("\n=== Example 1: Basic LLM Request ===\n")

    # Initialize orchestrator
    config = OrchestratorConfig(
        docker_pool_size=0,  # Disable Docker for this example
        ollama_url="http://localhost:11434",
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Execute LLM request
        result = await orchestrator.execute_llm_request(
            prompt="What is the capital of France? Answer in one word.",
            prefer_ollama=True,
        )

        if result.success:
            print(f"Answer: {result.data}")
            print(f"Execution time: {result.execution_time_ms:.2f}ms")
        else:
            print(f"Error: {result.error}")

    finally:
        await orchestrator.stop()


async def example_parallel_tasks():
    """Example: Execute multiple tasks in parallel"""
    print("\n=== Example 2: Parallel Task Execution ===\n")

    config = OrchestratorConfig(
        max_concurrent_tasks=5,
        docker_pool_size=0,
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Create multiple LLM tasks
        topics = ['Python', 'JavaScript', 'Rust', 'Go', 'TypeScript']

        tasks = [
            Task(
                type=TaskType.OLLAMA_REQUEST,
                payload={
                    'prompt': f'Explain {topic} in one sentence.',
                    'temperature': 0.5,
                },
                metadata={'topic': topic},
            )
            for topic in topics
        ]

        print(f"Submitting {len(tasks)} tasks...\n")

        # Execute in parallel
        results = await orchestrator.submit_batch(
            tasks,
            execute_parallel=True,
            wait=True,
        )

        # Display results
        for task, result in zip(tasks, results):
            topic = task.metadata['topic']
            if result.success:
                print(f"{topic}: {result.data}")
            else:
                print(f"{topic}: Error - {result.error}")

    finally:
        await orchestrator.stop()


async def example_task_priorities():
    """Example: Task prioritization"""
    print("\n=== Example 3: Task Prioritization ===\n")

    config = OrchestratorConfig(
        max_concurrent_tasks=1,  # Process one at a time to see priority
        docker_pool_size=0,
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Create tasks with different priorities
        tasks = [
            Task(
                type=TaskType.OLLAMA_REQUEST,
                priority=TaskPriority.LOW,
                payload={'prompt': 'Low priority task'},
                metadata={'name': 'Low Priority'},
            ),
            Task(
                type=TaskType.OLLAMA_REQUEST,
                priority=TaskPriority.CRITICAL,
                payload={'prompt': 'Critical task'},
                metadata={'name': 'Critical'},
            ),
            Task(
                type=TaskType.OLLAMA_REQUEST,
                priority=TaskPriority.NORMAL,
                payload={'prompt': 'Normal task'},
                metadata={'name': 'Normal'},
            ),
            Task(
                type=TaskType.OLLAMA_REQUEST,
                priority=TaskPriority.HIGH,
                payload={'prompt': 'High priority task'},
                metadata={'name': 'High Priority'},
            ),
        ]

        print("Submitting tasks in this order: Low, Critical, Normal, High")
        print("They should execute in priority order: Critical, High, Normal, Low\n")

        # Track completion order
        completion_order = []

        def on_complete(task, result):
            completion_order.append(task.metadata['name'])
            print(f"Completed: {task.metadata['name']}")

        orchestrator.on_task_complete = on_complete

        # Submit all tasks
        for task in tasks:
            await orchestrator.submit_task(task, wait=False)

        # Wait a bit for all to complete
        await asyncio.sleep(10)

        print(f"\nCompletion order: {' -> '.join(completion_order)}")

    finally:
        await orchestrator.stop()


async def example_task_dependencies():
    """Example: Tasks with dependencies"""
    print("\n=== Example 4: Task Dependencies ===\n")

    config = OrchestratorConfig(
        max_concurrent_tasks=5,
        docker_pool_size=0,
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Create dependent tasks
        task1 = Task(
            id="generate-story",
            type=TaskType.OLLAMA_REQUEST,
            payload={
                'prompt': 'Write a very short story about a robot (2 sentences max).',
            },
        )

        task2 = Task(
            id="extract-characters",
            type=TaskType.OLLAMA_REQUEST,
            payload={
                'prompt': 'Based on the previous story, list the main characters in one line.',
            },
            depends_on=["generate-story"],
        )

        task3 = Task(
            id="generate-moral",
            type=TaskType.OLLAMA_REQUEST,
            payload={
                'prompt': 'What is the moral of the previous story? One sentence.',
            },
            depends_on=["generate-story"],
        )

        print("Task 1: Generate story")
        print("Task 2: Extract characters (depends on task 1)")
        print("Task 3: Generate moral (depends on task 1)\n")

        # Execute - task2 and task3 will wait for task1
        results = await orchestrator.submit_batch(
            [task1, task2, task3],
            execute_parallel=True,
            wait=True,
        )

        print("Results:")
        print(f"Story: {results[0].data if results[0].success else 'Error'}")
        print(f"Characters: {results[1].data if results[1].success else 'Error'}")
        print(f"Moral: {results[2].data if results[2].success else 'Error'}")

    finally:
        await orchestrator.stop()


async def example_monitoring():
    """Example: Monitor orchestrator status"""
    print("\n=== Example 5: Monitoring ===\n")

    config = OrchestratorConfig(
        docker_pool_size=0,
    )

    orchestrator = UnifiedOrchestrator(config)
    await orchestrator.start()

    try:
        # Get initial status
        status = orchestrator.get_status()

        print("Orchestrator Status:")
        print(f"  Running: {status['is_running']}")
        print(f"  Uptime: {status['uptime_seconds']:.1f}s")
        print(f"\nWorker Statistics:")
        print(f"  Total workers: {status['workers']['total_workers']}")
        print(f"  By status: {status['workers']['workers_by_status']}")
        print(f"  By capability: {status['workers']['workers_by_capability']}")

        # Execute some tasks
        print("\nExecuting 3 tasks...")

        for i in range(3):
            await orchestrator.execute_llm_request(
                prompt=f"Count to {i+1}",
            )

        # Get updated status
        status = orchestrator.get_status()

        print(f"\nMetrics:")
        print(f"  Tasks submitted: {status['metrics']['tasks_submitted']}")
        print(f"  Tasks completed: {status['metrics']['tasks_completed']}")
        print(f"  Tasks failed: {status['metrics']['tasks_failed']}")
        print(f"  Active tasks: {status['metrics']['active_tasks']}")
        print(f"  Avg execution time: {status['metrics']['avg_execution_time_ms']:.2f}ms")

        # Get task history
        history = orchestrator.get_task_history(limit=5)
        print(f"\nRecent tasks: {len(history)}")
        for task_dict in history[:3]:
            print(f"  - {task_dict['type']} [{task_dict['status']}]")

    finally:
        await orchestrator.stop()


async def main():
    """Run all examples"""
    print("=" * 60)
    print("Unified Orchestrator - Basic Usage Examples")
    print("=" * 60)

    # Check if Ollama is running
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:11434/api/tags', timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status != 200:
                    print("\nError: Ollama is not running!")
                    print("Please start Ollama: ollama serve")
                    return
    except Exception:
        print("\nError: Cannot connect to Ollama!")
        print("Please start Ollama: ollama serve")
        return

    # Run examples
    try:
        await example_basic_llm_request()
        await asyncio.sleep(1)

        await example_parallel_tasks()
        await asyncio.sleep(1)

        await example_task_priorities()
        await asyncio.sleep(1)

        await example_task_dependencies()
        await asyncio.sleep(1)

        await example_monitoring()

    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\n\nError running examples: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
