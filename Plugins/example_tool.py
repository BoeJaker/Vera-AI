"""
Example custom tool - save this as: tools/example_tool.py

Functions decorated with @tool will be automatically loaded.
Functions without decorator can be called via call_custom_tool.
"""

from Vera.Toolchain.dynamic_loader import tool
from typing import Optional

@tool(
    name="greet_user",
    description="Greet a user with a personalized message",
    category="examples"
)
def greet_user(agent, name: str, greeting: str = "Hello") -> str:
    """
    Greet a user by name with a custom greeting.
    
    Args:
        agent: Agent instance (auto-injected)
        name: User's name
        greeting: Greeting word (default: "Hello")
    
    Returns:
        Personalized greeting message
    """
    return f"{greeting}, {name}! Nice to meet you."


@tool(
    name="calculate_stats",
    description="Calculate basic statistics for a list of numbers",
    category="examples"
)
def calculate_stats(agent, numbers: str) -> str:
    """
    Calculate mean, median, and sum for comma-separated numbers.
    
    Args:
        agent: Agent instance (auto-injected)
        numbers: Comma-separated numbers (e.g., "1,2,3,4,5")
    
    Returns:
        Statistics as formatted string
    """
    try:
        nums = [float(x.strip()) for x in numbers.split(",")]
        
        mean = sum(nums) / len(nums)
        sorted_nums = sorted(nums)
        median = sorted_nums[len(sorted_nums) // 2]
        
        return f"Count: {len(nums)}\nSum: {sum(nums)}\nMean: {mean:.2f}\nMedian: {median}"
    except Exception as e:
        return f"Error: {str(e)}"


# Function without decorator - callable via call_custom_tool
def process_text(text: str, operation: str = "upper") -> str:
    """
    Process text with various operations.
    
    Args:
        text: Input text
        operation: Operation to perform (upper, lower, reverse, length)
    
    Returns:
        Processed text
    """
    operations = {
        "upper": lambda t: t.upper(),
        "lower": lambda t: t.lower(),
        "reverse": lambda t: t[::-1],
        "length": lambda t: f"Length: {len(t)}"
    }
    
    if operation not in operations:
        return f"Unknown operation. Available: {', '.join(operations.keys())}"
    
    return operations[operation](text)
