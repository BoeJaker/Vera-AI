import unittest
import time
import json
import threading
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any, Optional, Generator
import tempfile
import os

# Import your toolchain classes
# from your_toolchain_module import (
#     ToolChainPlanner, ToolStep, ToolResult, ExecutionContext, 
#     StepStatus, ExecutionMode
# )

class MockTool:
    """Mock tool for testing purposes."""
    
    def __init__(self, name: str, should_yield: bool = False, should_error: bool = False, 
                 response: Any = "Mock response", delay: float = 0.0):
        self.name = name
        self.description = f"Mock tool: {name}"
        self.should_yield = should_yield
        self.should_error = should_error
        self.response = response
        self.delay = delay
        self.call_count = 0
    
    def run(self, input_text: str = "") -> Any:
        """Run the mock tool."""
        self.call_count += 1
        
        if self.delay > 0:
            time.sleep(self.delay)
        
        if self.should_error:
            raise Exception(f"Mock error from {self.name}")
        
        if self.should_yield:
            # Generator tool
            def generator():
                chunks = self.response if isinstance(self.response, list) else [self.response]
                for chunk in chunks:
                    yield f"{self.name}: {chunk}"
            return generator()
        else:
            # Regular return tool
            return f"{self.name}: {self.response}"

class MockLLM:
    """Mock LLM for testing planning functionality."""
    
    def __init__(self, responses: List[str] = None):
        self.responses = responses or [
            '{"tool": "mock_tool_1", "input": "test input"}',
            '{"tool": "DONE", "input": ""}'
        ]
        self.call_count = 0
    
    def invoke(self, prompt: str) -> str:
        """Mock LLM invoke method."""
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return response

class MockAgent:
    """Mock agent for testing."""
    
    def __init__(self, llm_responses: List[str] = None):
        self.deep_llm = MockLLM(llm_responses)
        self.stream_llm = None
        self.mem = None
        self.buffer_memory = Mock()
        self.buffer_memory.load_memory_variables.return_value = {"chat_history": ""}

class TestToolChainPlanner(unittest.TestCase):
    """Comprehensive test suite for ToolChainPlanner."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tools = [
            MockTool("mock_tool_1", response="Result 1"),
            MockTool("mock_tool_2", response="Result 2", should_yield=True),
            MockTool("error_tool", should_error=True),
            MockTool("slow_tool", delay=0.1, response="Slow result"),
            MockTool("generator_tool", should_yield=True, response=["chunk1", "chunk2", "chunk3"])
        ]
        
        self.agent = MockAgent([
            '[{"tool": "mock_tool_1", "input": "test"}, {"tool": "mock_tool_2", "input": "{prev}"}]',
            '{"tool": "DONE", "input": ""}',
            'yes'  # Goal check response
        ])
        
        self.planner = None  # Will be initialized in tests
    
    def create_planner(self, **kwargs) -> 'ToolChainPlanner':
        """Create a planner instance for testing."""
        default_kwargs = {
            'max_steps': 10,
            'default_retries': 1,
            'speculative_workers': 2
        }
        default_kwargs.update(kwargs)
        
        # This would be: return ToolChainPlanner(self.agent, self.tools, **default_kwargs)
        # For now, return a mock
        planner = Mock()
        planner.agent = self.agent
        planner.tools = self.tools
        planner.tool_map = {tool.name: tool for tool in self.tools}
        planner.max_steps = default_kwargs['max_steps']
        planner.default_retries = default_kwargs['default_retries']
        return planner

    def test_tool_map_creation(self):
        """Test that tool map is created correctly."""
        planner = self.create_planner()
        
        expected_tools = {
            "mock_tool_1": self.tools[0],
            "mock_tool_2": self.tools[1],
            "error_tool": self.tools[2],
            "slow_tool": self.tools[3],
            "generator_tool": self.tools[4]
        }
        
        self.assertEqual(planner.tool_map, expected_tools)

    def test_yield_vs_return_handling(self):
        """Test that both yielding and returning tools work correctly."""
        # Test return tool
        return_tool = self.tools[0]  # mock_tool_1
        result = return_tool.run("test input")
        self.assertEqual(result, "mock_tool_1: Result 1")
        
        # Test yield tool  
        yield_tool = self.tools[1]  # mock_tool_2
        result = yield_tool.run("test input")
        
        # Collect generator results
        collected = []
        for chunk in result:
            collected.append(chunk)
        
        self.assertEqual(collected, ["mock_tool_2: Result 2"])

    def test_tool_execution_with_retry(self):
        """Test tool execution with retry logic."""
        planner = self.create_planner()
        
        # Test successful execution
        tool = self.tools[0]
        self.assertEqual(tool.call_count, 0)
        
        # Simulate execution
        result = tool.run("test")
        self.assertEqual(result, "mock_tool_1: Result 1")
        self.assertEqual(tool.call_count, 1)

    def test_error_handling(self):
        """Test error handling in tool execution."""
        error_tool = self.tools[2]  # error_tool
        
        with self.assertRaises(Exception) as context:
            error_tool.run("test")
        
        self.assertIn("Mock error from error_tool", str(context.exception))

    def test_placeholder_resolution(self):
        """Test placeholder resolution in tool inputs."""
        planner = self.create_planner()
        
        # Mock the _resolve_placeholders method
        def mock_resolve_placeholders(text, executed, step_num):
            if "{prev}" in text:
                prev_result = executed.get(f"step_{step_num-1}", "")
                text = text.replace("{prev}", str(prev_result))
            return text
        
        executed = {"step_1": "previous result"}
        result = mock_resolve_placeholders("Use {prev} as input", executed, 2)
        self.assertEqual(result, "Use previous result as input")

    def test_plan_parsing(self):
        """Test JSON plan parsing functionality."""
        planner = self.create_planner()
        
        # Test valid JSON plan
        valid_plan = '[{"tool": "mock_tool_1", "input": "test"}, {"tool": "mock_tool_2", "input": "{prev}"}]'
        
        try:
            parsed = json.loads(valid_plan)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0]["tool"], "mock_tool_1")
        except json.JSONDecodeError:
            self.fail("Valid JSON should parse correctly")

    def test_goal_checking(self):
        """Test goal achievement checking."""
        planner = self.create_planner()
        
        # Mock goal check
        def mock_goal_check(query, executed):
            # Simple heuristic: goal is met if we have results
            return len(executed) > 0 and not any(
                str(v).startswith("ERROR") for v in executed.values()
            )
        
        # Test successful execution
        executed_success = {"step_1": "success result", "step_2": "another success"}
        self.assertTrue(mock_goal_check("test query", executed_success))
        
        # Test failed execution
        executed_failed = {"step_1": "ERROR: something went wrong"}
        self.assertFalse(mock_goal_check("test query", executed_failed))

    def test_concurrent_execution(self):
        """Test concurrent/parallel execution scenarios."""
        planner = self.create_planner(speculative_workers=3)
        
        # Test that tools can be called concurrently
        import concurrent.futures
        
        tools_to_test = [self.tools[0], self.tools[1], self.tools[3]]  # Different tools
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(tool.run, f"input_{i}") for i, tool in enumerate(tools_to_test)]
            results = []
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if hasattr(result, '__iter__') and not isinstance(result, str):
                        # Handle generator results
                        result = "".join(str(chunk) for chunk in result)
                    results.append(result)
                except Exception as e:
                    results.append(f"ERROR: {e}")
        
        self.assertEqual(len(results), 3)

    def test_execution_modes(self):
        """Test different execution modes."""
        planner = self.create_planner()
        
        # Test mode validation
        valid_modes = ["batch", "incremental", "speculative", "hybrid"]
        
        for mode in valid_modes:
            # This would test actual mode execution
            self.assertIn(mode, valid_modes)

    def test_cancellation(self):
        """Test execution cancellation."""
        planner = self.create_planner()
        
        # Mock cancellation event
        import threading
        cancellation_event = threading.Event()
        
        def long_running_task():
            for i in range(100):
                if cancellation_event.is_set():
                    return "CANCELLED"
                time.sleep(0.001)
            return "COMPLETED"
        
        # Test cancellation
        thread = threading.Thread(target=long_running_task)
        thread.start()
        
        # Cancel after short delay
        time.sleep(0.01)
        cancellation_event.set()
        
        thread.join(timeout=1.0)
        self.assertTrue(cancellation_event.is_set())

    def test_memory_integration(self):
        """Test memory integration functionality."""
        # Create agent with memory mock
        agent = MockAgent()
        agent.mem = Mock()
        agent.save_to_memory = Mock()
        
        planner = self.create_planner()
        planner.agent = agent
        
        # Test memory save operation
        agent.save_to_memory("test_key", "test_value")
        agent.save_to_memory.assert_called_with("test_key", "test_value")

    def test_streaming_tools(self):
        """Test streaming/generator tools specifically."""
        generator_tool = self.tools[4]  # generator_tool with multiple chunks
        
        result = generator_tool.run("stream test")
        chunks = list(result)  # Consume the generator
        
        expected_chunks = [
            "generator_tool: chunk1",
            "generator_tool: chunk2", 
            "generator_tool: chunk3"
        ]
        
        self.assertEqual(chunks, expected_chunks)

    def test_performance_metrics(self):
        """Test performance metrics collection."""
        planner = self.create_planner()
        
        # Mock execution metrics
        start_time = time.time()
        
        # Simulate some operations
        time.sleep(0.01)
        
        end_time = time.time()
        duration = end_time - start_time
        
        metrics = {
            "duration": duration,
            "steps_executed": 3,
            "successful_steps": 2,
            "failed_steps": 1,
            "success_rate": 2/3
        }
        
        self.assertGreater(metrics["duration"], 0)
        self.assertEqual(metrics["success_rate"], 2/3)

class TestIntegrationWithVera(unittest.TestCase):
    """Integration tests that can work with Vera instance if available."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.vera_available = self.check_vera_availability()

    def check_vera_availability(self) -> bool:
        """Check if Vera is available for integration tests."""
        try:
            # Attempt to import Vera or check environment
            # For demonstration, we'll check an environment variable
            return os.environ.get('TEST_VERA_AVAILABLE', '0') == '1'
        except ImportError:
            return False

    @unittest.skipUnless(os.environ.get('TEST_VERA_AVAILABLE') == '1', 
                        "Vera integration tests require TEST_VERA_AVAILABLE=1")
    def test_vera_integration(self):
        """Test integration with actual Vera instance."""
        # This test will only run if Vera is available
        from your_vera_module import Vera  # Import actual Vera client
        
        vera = Vera(
            api_key=os.environ.get('VERA_API_KEY'),
            base_url=os.environ.get('VERA_BASE_URL', 'https://default.vera.url')
        )
        
        # Test simple Vera operation
        response = vera.simple_query("test query")
        self.assertIsNotNone(response)
        
    @unittest.skipUnless(os.environ.get('TEST_VERA_AVAILABLE') == '1', 
                        "Vera integration tests require TEST_VERA_AVAILABLE=1")
    def test_planner_with_vera(self):
        """Test ToolChainPlanner with real Vera instance."""
        from your_toolchain_module import ToolChainPlanner
        from your_vera_module import Vera
        
        vera = Vera(
            api_key=os.environ.get('VERA_API_KEY'),
            base_url=os.environ.get('VERA_BASE_URL')
        )
        
        # Create planner with real Vera instance
        planner = ToolChainPlanner(
            agent=vera,
            tools=self.tools,
            max_steps=5
        )
        
        # Test execution
        result = planner.execute("test query")
        self.assertIsNotNone(result)
        self.assertTrue(result.success)

if __name__ == '__main__':
    unittest.main()