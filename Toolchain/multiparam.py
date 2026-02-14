"""
multiarg_tool_wrapper.py - Fix multi-parameter tool calls at the TOOL level

The Problem:
    BaseTool.run() expects a single positional arg (str or dict).
    When a toolchain planner gets a dict input for multi-param tools like write_file,
    it may call tool.run(**dict) which unpacks into kwargs, causing:
        "BaseTool.run() missing 1 required positional argument: 'tool_input'"

The Fix:
    Wrap each tool so its .run() method accepts BOTH patterns:
        tool.run({"file_path": "...", "content": "..."})   # dict as single arg  ✓
        tool.run(file_path="...", content="...")             # kwargs              ✓  (NEW)
        tool.run('{"file_path": "...", "content": "..."}')  # JSON string         ✓  (NEW)

Usage in Vera.__init__(), AFTER building self.tools:

    from Vera.Toolchain.multiarg_tool_wrapper import wrap_tools_multiarg
    self.tools = wrap_tools_multiarg(self.tools)

    # Then create toolchain with the wrapped tools
    self.toolchain = ToolChainPlanner(self, self.tools)

This is transparent — wrapped tools behave identically for single-param calls.
"""

import json
import logging
import functools
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_multiarg_tool(tool) -> bool:
    """Check if a tool accepts multiple parameters (not just a single string)."""
    if not hasattr(tool, 'args_schema') or tool.args_schema is None:
        return False

    try:
        schema = tool.args_schema.schema()
        properties = schema.get('properties', {})
        # Multi-arg if more than 1 property, OR if the single property isn't 
        # the default '__arg1' / 'tool_input' pattern
        if len(properties) > 1:
            return True
        if len(properties) == 1:
            key = list(properties.keys())[0]
            # Single-param tools typically have '__arg1' or 'query' etc.
            # If it's something specific like 'file_path', it's probably multi-arg
            # But we only really need to fix tools with 2+ params
            return False
    except Exception:
        return False

    return False


def _parse_string_input(raw_input: str) -> Any:
    """Try to parse a JSON string into a dict."""
    stripped = raw_input.strip()
    if stripped.startswith('{') and stripped.endswith('}'):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            try:
                import ast
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                pass
    return raw_input


def wrap_tool_run(tool):
    """
    Patch a single tool's .run() to accept kwargs for multi-param tools.
    
    Before:  tool.run({"file_path": "x", "content": "y"})  → works
             tool.run(file_path="x", content="y")           → FAILS
             tool.run(**some_dict)                           → FAILS
    
    After:   All three patterns work.
    """
    original_run = tool.run

    @functools.wraps(original_run)
    def patched_run(tool_input=None, *args, **kwargs):
        # Case 1: Called with kwargs only (from **dict unpacking)
        #   tool.run(file_path="x", content="y")
        #   → tool_input will be None, kwargs will have the params
        if tool_input is None and kwargs:
            # Check if these are actual tool params vs run() config kwargs
            # run() config kwargs are things like 'verbose', 'callbacks', etc.
            run_config_keys = {'verbose', 'callbacks', 'tags', 'metadata', 'run_name',
                               'run_id', 'config', 'return_direct'}
            
            tool_params = {k: v for k, v in kwargs.items() if k not in run_config_keys}
            config_params = {k: v for k, v in kwargs.items() if k in run_config_keys}
            
            if tool_params:
                logger.debug(
                    f"[multiarg] {tool.name}: kwargs→dict repack: {list(tool_params.keys())}"
                )
                return original_run(tool_params, *args, **config_params)
            else:
                # All kwargs are config — something else is wrong
                return original_run(tool_input, *args, **kwargs)

        # Case 2: Called with a JSON string that should be a dict
        #   tool.run('{"file_path": "x", "content": "y"}')
        if isinstance(tool_input, str):
            parsed = _parse_string_input(tool_input)
            if isinstance(parsed, dict) and _is_multiarg_tool(tool):
                logger.debug(
                    f"[multiarg] {tool.name}: JSON string→dict: {list(parsed.keys())}"
                )
                return original_run(parsed, *args, **kwargs)

        # Case 3: Mixed — tool_input provided AND extra kwargs that are tool params
        #   tool.run("partial", content="y")  — unlikely but handle it
        if tool_input is not None and kwargs:
            run_config_keys = {'verbose', 'callbacks', 'tags', 'metadata', 'run_name',
                               'run_id', 'config', 'return_direct'}
            tool_params = {k: v for k, v in kwargs.items() if k not in run_config_keys}
            config_params = {k: v for k, v in kwargs.items() if k in run_config_keys}
            
            if tool_params and isinstance(tool_input, dict):
                # Merge
                merged = {**tool_input, **tool_params}
                logger.debug(
                    f"[multiarg] {tool.name}: merged dict+kwargs: {list(merged.keys())}"
                )
                return original_run(merged, *args, **config_params)

        # Case 4: Normal call — pass through unchanged
        return original_run(tool_input, *args, **kwargs)

    # Bypass Pydantic's __setattr__ which blocks setting non-field attributes
    object.__setattr__(tool, 'run', patched_run)
    return tool


def wrap_tools_multiarg(tools: list) -> list:
    """
    Wrap all multi-param tools in a list so they handle any call pattern.
    Single-param tools are left untouched (zero overhead).
    
    Args:
        tools: List of LangChain tools
        
    Returns:
        Same list with multi-param tools patched in-place
    """
    patched_count = 0

    for tool in tools:
        if _is_multiarg_tool(tool):
            wrap_tool_run(tool)
            patched_count += 1
            logger.info(f"[multiarg] Wrapped: {tool.name}")
        else:
            logger.debug(f"[multiarg] Skipped (single-param): {tool.name}")

    logger.info(f"[multiarg] Patched {patched_count}/{len(tools)} tools for multi-param support")
    return tools