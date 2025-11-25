"""
Vera External API Integration - Examples
=========================================

Demonstrates how to use external compute and LLM APIs with the orchestration system.
"""

import time
import json
from vera_orchestrator_external import (
    ExternalAPIOrchestrator,
    ExternalProvider,
    ExternalTaskMetadata
)
from vera_orchestrator import EventBus, task, TaskType


# ============================================================================
# EXAMPLE 1: OPENAI GPT-4 INTEGRATION
# ============================================================================

def example_openai_basic():
    """Basic OpenAI API usage"""
    print("=" * 70)
    print("EXAMPLE 1: OpenAI GPT-4 Integration")
    print("=" * 70)
    
    # Configuration
    config = {
        'openai': {
            'api_key': 'your-openai-api-key',  # Replace with your key
            'base_url': None  # Optional: for custom endpoints
        }
    }
    
    # Initialize
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    try:
        print("\n1. Simple completion...")
        metadata = ExternalTaskMetadata(
            provider=ExternalProvider.OPENAI,
            model="gpt-3.5-turbo"
        )
        
        result = orchestrator.execute_task(
            ExternalProvider.OPENAI,
            "llm.summarize",
            metadata,
            prompt="Explain quantum computing in simple terms"
        )
        
        print(f"   ✓ Result: {result[:100]}...")
        
        print("\n2. Streaming completion...")
        for chunk in orchestrator.stream_task(
            ExternalProvider.OPENAI,
            "llm.generate",
            metadata,
            prompt="Write a haiku about AI"
        ):
            print(chunk, end='', flush=True)
        print()
        
        print("\n3. Usage statistics...")
        stats = orchestrator.get_stats(ExternalProvider.OPENAI)
        print(f"   Total requests: {stats['stats']['total_requests']}")
        print(f"   Total cost: ${stats['stats']['total_cost_usd']:.4f}")
        print(f"   Avg latency: {stats['stats']['avg_latency_ms']:.0f}ms")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 2: ANTHROPIC CLAUDE INTEGRATION
# ============================================================================

def example_anthropic_claude():
    """Anthropic Claude API usage"""
    print("=" * 70)
    print("EXAMPLE 2: Anthropic Claude Integration")
    print("=" * 70)
    
    config = {
        'anthropic': {
            'api_key': 'your-anthropic-api-key'  # Replace with your key
        }
    }
    
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    try:
        print("\n1. Claude Sonnet completion...")
        metadata = ExternalTaskMetadata(
            provider=ExternalProvider.ANTHROPIC,
            model="claude-3-sonnet-20240229",
            extra_params={"max_tokens": 1024}
        )
        
        result = orchestrator.execute_task(
            ExternalProvider.ANTHROPIC,
            "llm.analyze",
            metadata,
            prompt="Analyze the pros and cons of renewable energy"
        )
        
        print(f"   ✓ Result: {result[:100]}...")
        
        print("\n2. Streaming with Claude...")
        print("   Response: ", end='')
        for chunk in orchestrator.stream_task(
            ExternalProvider.ANTHROPIC,
            "llm.generate",
            metadata,
            prompt="Write a brief overview of machine learning"
        ):
            print(chunk, end='', flush=True)
        print()
        
        print("\n3. Cost tracking...")
        print(f"   Total cost: ${orchestrator.get_total_cost():.4f}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 3: MULTI-PROVIDER LLM ROUTING
# ============================================================================

def example_multi_provider():
    """Use multiple LLM providers with automatic routing"""
    print("=" * 70)
    print("EXAMPLE 3: Multi-Provider LLM Routing")
    print("=" * 70)
    
    config = {
        'openai': {
            'api_key': 'your-openai-api-key'
        },
        'anthropic': {
            'api_key': 'your-anthropic-api-key'
        },
        'google': {
            'api_key': 'your-google-api-key'
        }
    }
    
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    # Define tasks with different providers
    tasks = [
        {
            'name': 'Quick summary',
            'provider': ExternalProvider.OPENAI,
            'model': 'gpt-3.5-turbo',
            'prompt': 'Summarize the water cycle in one sentence'
        },
        {
            'name': 'Detailed analysis',
            'provider': ExternalProvider.ANTHROPIC,
            'model': 'claude-3-sonnet-20240229',
            'prompt': 'Analyze the impact of AI on healthcare'
        },
        {
            'name': 'Creative writing',
            'provider': ExternalProvider.GOOGLE,
            'model': 'gemini-pro',
            'prompt': 'Write a creative description of a futuristic city'
        }
    ]
    
    print("\n1. Executing tasks on different providers...")
    results = []
    
    for task_def in tasks:
        try:
            print(f"\n   Task: {task_def['name']}")
            print(f"   Provider: {task_def['provider'].value}")
            
            metadata = ExternalTaskMetadata(
                provider=task_def['provider'],
                model=task_def['model']
            )
            
            result = orchestrator.execute_task(
                task_def['provider'],
                f"llm.{task_def['name'].lower().replace(' ', '_')}",
                metadata,
                prompt=task_def['prompt']
            )
            
            results.append({
                'task': task_def['name'],
                'provider': task_def['provider'].value,
                'result': result[:80] + '...'
            })
            
            print(f"   ✓ Completed")
            
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\n2. Results summary...")
    for r in results:
        print(f"\n   {r['task']} ({r['provider']}):")
        print(f"   {r['result']}")
    
    print("\n3. Cost breakdown by provider...")
    all_stats = orchestrator.get_stats()
    for provider, stats in all_stats.items():
        if stats['total_requests'] > 0:
            print(f"   {provider}:")
            print(f"     Requests: {stats['total_requests']}")
            print(f"     Cost: ${stats['total_cost_usd']:.4f}")
            print(f"     Latency: {stats['avg_latency_ms']:.0f}ms")
    
    print(f"\n   Total cost: ${orchestrator.get_total_cost():.4f}")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 4: AWS LAMBDA COMPUTE
# ============================================================================

def example_aws_lambda():
    """Execute tasks on AWS Lambda"""
    print("=" * 70)
    print("EXAMPLE 4: AWS Lambda Compute")
    print("=" * 70)
    
    config = {
        'aws_lambda': {
            'access_key': 'your-aws-access-key',
            'secret_key': 'your-aws-secret-key',
            'region': 'us-east-1'
        }
    }
    
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    try:
        print("\n1. Execute data processing on Lambda...")
        metadata = ExternalTaskMetadata(
            provider=ExternalProvider.AWS_LAMBDA,
            extra_params={
                'function_name': 'data-processor',
                'memory_mb': 512
            }
        )
        
        result = orchestrator.execute_task(
            ExternalProvider.AWS_LAMBDA,
            "process_data",
            metadata,
            data=[1, 2, 3, 4, 5],
            operation="sum"
        )
        
        print(f"   ✓ Result: {result}")
        
        print("\n2. Cost statistics...")
        stats = orchestrator.get_stats(ExternalProvider.AWS_LAMBDA)
        print(f"   Executions: {stats['stats']['total_requests']}")
        print(f"   Cost: ${stats['stats']['total_cost_usd']:.6f}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("   Note: Requires AWS credentials and Lambda function")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 5: RUNPOD GPU WORKLOADS
# ============================================================================

def example_runpod_gpu():
    """Execute GPU workloads on RunPod"""
    print("=" * 70)
    print("EXAMPLE 5: RunPod GPU Workloads")
    print("=" * 70)
    
    config = {
        'runpod': {
            'api_key': 'your-runpod-api-key'
        }
    }
    
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    try:
        print("\n1. Execute ML training on RunPod GPU...")
        metadata = ExternalTaskMetadata(
            provider=ExternalProvider.RUNPOD,
            extra_params={
                'endpoint_id': 'your-endpoint-id',
                'gpu_type': 'A40'
            }
        )
        
        result = orchestrator.execute_task(
            ExternalProvider.RUNPOD,
            "ml.train_model",
            metadata,
            model_name="resnet50",
            epochs=10,
            batch_size=32
        )
        
        print(f"   ✓ Training result: {result}")
        
        print("\n2. Cost tracking...")
        stats = orchestrator.get_stats(ExternalProvider.RUNPOD)
        print(f"   GPU time cost: ${stats['stats']['total_cost_usd']:.4f}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("   Note: Requires RunPod account and endpoint")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 6: GENERIC HTTP ENDPOINT
# ============================================================================

def example_http_endpoint():
    """Use generic HTTP endpoints for custom services"""
    print("=" * 70)
    print("EXAMPLE 6: Generic HTTP Endpoint")
    print("=" * 70)
    
    config = {
        'http_endpoints': {}
    }
    
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    try:
        print("\n1. Call custom API endpoint...")
        metadata = ExternalTaskMetadata(
            provider=ExternalProvider.HTTP_ENDPOINT,
            endpoint="https://api.example.com/process",
            api_key="your-api-key",
            extra_params={
                'method': 'POST',
                'headers': {
                    'Content-Type': 'application/json'
                }
            }
        )
        
        result = orchestrator.execute_task(
            ExternalProvider.HTTP_ENDPOINT,
            "custom.process",
            metadata,
            data="some data to process"
        )
        
        print(f"   ✓ Result: {result}")
        
        print("\n2. Stream from HTTP endpoint...")
        metadata.stream = True
        
        for chunk in orchestrator.stream_task(
            ExternalProvider.HTTP_ENDPOINT,
            "custom.stream",
            metadata,
            prompt="generate stream"
        ):
            print(f"   Chunk: {chunk}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("   Note: Requires accessible HTTP endpoint")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 7: COST OPTIMIZATION
# ============================================================================

def example_cost_optimization():
    """Demonstrate cost-aware provider selection"""
    print("=" * 70)
    print("EXAMPLE 7: Cost Optimization")
    print("=" * 70)
    
    # Provider cost profiles (per 1M tokens)
    cost_profiles = {
        'gpt-4': {'input': 30.0, 'output': 60.0},
        'gpt-3.5-turbo': {'input': 0.5, 'output': 1.5},
        'claude-3-opus': {'input': 15.0, 'output': 75.0},
        'claude-3-sonnet': {'input': 3.0, 'output': 15.0},
        'gemini-pro': {'input': 0.5, 'output': 1.5},
    }
    
    print("\n1. Cost profiles for different models:")
    for model, costs in cost_profiles.items():
        print(f"   {model}:")
        print(f"     Input:  ${costs['input']}/1M tokens")
        print(f"     Output: ${costs['output']}/1M tokens")
    
    print("\n2. Selecting optimal provider...")
    
    # Task characteristics
    tasks = [
        {
            'name': 'Simple classification',
            'tokens_in': 100,
            'tokens_out': 10,
            'quality_needed': 'low'
        },
        {
            'name': 'Complex analysis',
            'tokens_in': 5000,
            'tokens_out': 2000,
            'quality_needed': 'high'
        },
        {
            'name': 'Long generation',
            'tokens_in': 500,
            'tokens_out': 10000,
            'quality_needed': 'medium'
        }
    ]
    
    # Quality tiers
    quality_tiers = {
        'low': ['gpt-3.5-turbo', 'gemini-pro'],
        'medium': ['claude-3-sonnet', 'gpt-3.5-turbo'],
        'high': ['gpt-4', 'claude-3-opus']
    }
    
    for task_def in tasks:
        print(f"\n   Task: {task_def['name']}")
        print(f"   Input tokens: {task_def['tokens_in']}")
        print(f"   Output tokens: {task_def['tokens_out']}")
        print(f"   Quality needed: {task_def['quality_needed']}")
        
        # Calculate cost for eligible models
        eligible_models = quality_tiers[task_def['quality_needed']]
        costs = {}
        
        for model in eligible_models:
            if model in cost_profiles:
                profile = cost_profiles[model]
                cost = (
                    task_def['tokens_in'] * profile['input'] +
                    task_def['tokens_out'] * profile['output']
                ) / 1_000_000
                costs[model] = cost
        
        # Select cheapest
        best_model = min(costs.items(), key=lambda x: x[1])
        print(f"   Recommended: {best_model[0]} (${best_model[1]:.6f})")
        
        # Show alternatives
        print(f"   Alternatives:")
        for model, cost in sorted(costs.items(), key=lambda x: x[1]):
            if model != best_model[0]:
                savings = ((best_model[1] - cost) / cost) * 100 if cost > 0 else 0
                print(f"     {model}: ${cost:.6f} ({savings:+.1f}%)")
    
    print("\n✅ Example completed\n")


# ============================================================================
# EXAMPLE 8: FAILOVER AND REDUNDANCY
# ============================================================================

def example_failover():
    """Demonstrate failover between providers"""
    print("=" * 70)
    print("EXAMPLE 8: Failover and Redundancy")
    print("=" * 70)
    
    config = {
        'openai': {'api_key': 'key1'},
        'anthropic': {'api_key': 'key2'},
        'google': {'api_key': 'key3'}
    }
    
    event_bus = EventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    # Provider priority order
    fallback_chain = [
        (ExternalProvider.OPENAI, 'gpt-3.5-turbo'),
        (ExternalProvider.ANTHROPIC, 'claude-3-sonnet-20240229'),
        (ExternalProvider.GOOGLE, 'gemini-pro')
    ]
    
    prompt = "Explain the concept of edge computing"
    
    print("\n1. Attempting with failover chain...")
    print(f"   Fallback order: {' → '.join(p[0].value for p in fallback_chain)}")
    
    result = None
    for provider, model in fallback_chain:
        try:
            print(f"\n   Trying {provider.value} ({model})...")
            
            metadata = ExternalTaskMetadata(
                provider=provider,
                model=model,
                timeout=10.0
            )
            
            result = orchestrator.execute_task(
                provider,
                "llm.explain",
                metadata,
                prompt=prompt
            )
            
            print(f"   ✓ Success with {provider.value}")
            print(f"   Result: {result[:100]}...")
            break
            
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            continue
    
    if not result:
        print("\n   ✗ All providers failed")
    else:
        print("\n2. Statistics:")
        stats = orchestrator.get_stats()
        for provider_name, provider_stats in stats.items():
            if provider_stats['total_requests'] > 0:
                success_rate = (
                    provider_stats['successful_requests'] /
                    provider_stats['total_requests'] * 100
                )
                print(f"   {provider_name}: {success_rate:.0f}% success rate")
    
    print("\n✅ Example completed\n")


# ============================================================================
# MAIN MENU
# ============================================================================

def main():
    """Run example demonstrations"""
    print("\n" + "=" * 70)
    print("VERA EXTERNAL API INTEGRATION - EXAMPLES")
    print("=" * 70)
    print("\nAvailable examples:")
    print("  1. OpenAI GPT-4 Integration")
    print("  2. Anthropic Claude Integration")
    print("  3. Multi-Provider LLM Routing")
    print("  4. AWS Lambda Compute")
    print("  5. RunPod GPU Workloads")
    print("  6. Generic HTTP Endpoint")
    print("  7. Cost Optimization")
    print("  8. Failover and Redundancy")
    print("  0. Run All Examples")
    
    choice = input("\nSelect example (0-8): ").strip()
    
    examples = {
        "1": example_openai_basic,
        "2": example_anthropic_claude,
        "3": example_multi_provider,
        "4": example_aws_lambda,
        "5": example_runpod_gpu,
        "6": example_http_endpoint,
        "7": example_cost_optimization,
        "8": example_failover,
    }
    
    if choice == "0":
        for key in examples:
            try:
                examples[key]()
                time.sleep(1)
            except Exception as e:
                print(f"Example {key} failed: {e}\n")
    elif choice in examples:
        examples[choice]()
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    main()