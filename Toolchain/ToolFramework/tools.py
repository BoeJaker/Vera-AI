"""
NOTE: If you add new tools please run:
python3 -m Vera.Agents.agent_manager build --agent tool-agent
Then sync to all nodes if more than one available.
"""

from langchain.agents import Tool
from langchain_core.tools import tool, StructuredTool
from langchain.tools import BaseTool
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_async_playwright_browser

import os
import subprocess
import sys
# import io
import traceback
import asyncio
import re
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from typing import List, Dict, Any, Type, Optional, Union
from pydantic import BaseModel, Field
from functools import partial
# from contextlib import contextmanager

from duckduckgo_search import DDGS
from playwright.async_api import async_playwright

# MCP Client imports (install: pip install mcp anthropic-mcp-client)
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("[Warning] MCP not available. Install with: pip install mcp anthropic-mcp-client")

from Vera.Toolchain.Tools.Babelfish.protocols import add_ssh_postgres_neo4j_tools
from Vera.Toolchain.schemas import *
import Vera.Toolchain.dynamic_tools as DynamicTools
from Vera.Toolchain.mcp_manager import *
from Vera.Toolchain.Tools.Coding.code_executor import *
from Vera.Toolchain.Tools.Microcontrollers.microcontollers2 import *
from Vera.Toolchain.Tools.Filesystem.version_manager import *
from Vera.Toolchain.n8n.n8n_tools import *
from Vera.Toolchain.Tools.Memory.memory_advanced_pt2 import *
from Vera.Toolchain.Tools.Memory.memory_advanced import *
from Vera.Toolchain.Tools.Memory.memory import *
from Vera.Toolchain.Tools.orchestration import *
# from Vera.Toolchain.Tools.OSINT.loader import add_all_osint_tools
# from Vera.Toolchain.Tools.OSINT.network_loader import add_all_network_osint_tools
# from Vera.Toolchain.Tools.OSINT.network_ingestor_integration import add_network_infrastructure_tools
from Vera.Toolchain.Tools.OSINT.network_scanning import  add_network_scanning_tools
from Vera.Toolchain.Tools.OSINT.osint import  add_osint_tools
from Vera.Toolchain.Tools.OSINT.dorking import  add_dorking_tools
from Vera.Toolchain.Tools.OSINT.webrecon import  add_web_recon_tools
from Vera.Toolchain.Tools.OSINT.vulnerabilities import  add_vulnerability_intelligence_tools
from Vera.Toolchain.Tools.Coding.codebase_mapper import  add_codebase_analysis_tools
from Vera.Toolchain.Tools.Crawlers.web_search import  add_web_search_tools
from Vera.Toolchain.Tools.Filesystem.core import  add_filesystem_tools
from Vera.Toolchain.Tools.TextProcessing.core import add_text_processing_tools
from Vera.Toolchain.Tools.LLM.core import add_llm_tools
from Vera.Toolchain.Tools.Crawlers.web import add_web_crawler_tools
from Vera.Toolchain.Tools.Babelfish.core import add_babelfish_tools
from Vera.Toolchain.Tools.Bash.core import add_bash_tools
from Vera.Toolchain.Tools.Python.core import add_python_tools
from Vera.Toolchain.Tools.Utilities.data import add_data_processing_tools
from Vera.Toolchain.Tools.Utilities.system import add_system_tools
from Vera.Toolchain.Tools.Utilities.time import add_time_tools
from Vera.Toolchain.Tools.git.core import add_git_tools
from Vera.Toolchain.Tools_2.network_monitor import add_network_monitor_tools
# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# @contextmanager
# def redirect_stdout():
#     """Context manager for safely redirecting stdout."""
#     old_stdout = sys.stdout
#     redirected_output = sys.stdout = io.StringIO()
#     try:
#         yield redirected_output
#     finally:
#         sys.stdout = old_stdout


def sanitize_path(path: str) -> str:
    """Sanitize and validate file paths."""
    path = os.path.normpath(path)
    if path.startswith('..'):
        raise ValueError("Path traversal not allowed")
    return path


# def truncate_output(text: str, max_length: int = 5000) -> str:
#     """Truncate long outputs with indication."""
#     if len(text) > max_length:
#         return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
#     return text


def format_json(data: Any) -> str:
    """Format data as pretty JSON."""
    try:
        return json.dumps(data, indent=2, default=str)
    except:
        return str(data)


# ============================================================================
# MCP CLIENT MANAGER
# ============================================================================

class MCPManager:
    """Manages MCP server connections and tool invocations."""
    
    def __init__(self):
        self.servers: Dict[str, Any] = {}
        self.sessions: Dict[str, ClientSession] = {}
        
    async def connect_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """Connect to an MCP server."""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP not available. Install with: pip install mcp anthropic-mcp-client")
        
        server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.servers[name] = server_params
                self.sessions[name] = session
                return f"Connected to MCP server: {name}"
    
    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """List available tools from an MCP server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not connected")
        
        session = self.sessions[server_name]
        response = await session.list_tools()
        return [{"name": tool.name, "description": tool.description} for tool in response.tools]
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on an MCP server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not connected")
        
        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        return format_json(result)


# ============================================================================
# CORE TOOL IMPLEMENTATIONS
# ============================================================================

class LLMTools:
    """Organized collection of LLM tools with proper error handling and memory integration."""
    
    def __init__(self, agent):
        self.agent = agent
        self.mcp_manager = MCPManager() if MCP_AVAILABLE else None
        
    # ------------------------------------------------------------------------
    # HTTP/API TOOLS
    # ------------------------------------------------------------------------
    
    def http_request(self, url: str, method: str = "GET", headers: Optional[Dict] = None, body: Optional[str] = None) -> str:
        """
        Make HTTP requests to APIs or web services.
        Supports GET, POST, PUT, DELETE methods.
        """
        try:
            method = method.upper()
            headers = headers or {}
            
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, data=body, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return f"[Error] Unsupported method: {method}"
            
            result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:5000]  # Truncate large responses
            }
            
            return format_json(result)
            
        except Exception as e:
            return f"[HTTP Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # DATABASE TOOLS
    # ------------------------------------------------------------------------
    
    def sqlite_query(self, db_path: str, query: str) -> str:
        """
        Execute SQLite queries. Supports SELECT, INSERT, UPDATE, DELETE.
        Returns formatted results.
        """
        try:
            db_path = sanitize_path(db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                result = {"columns": columns, "rows": rows, "count": len(rows)}
                output = format_json(result)
            else:
                conn.commit()
                output = f"Query executed successfully. Rows affected: {cursor.rowcount}"
            
            conn.close()
            return output
            
        except Exception as e:
            return f"[SQLite Error] {str(e)}"

    
    # ------------------------------------------------------------------------
    # MCP TOOLS
    # ------------------------------------------------------------------------
    
    def mcp_call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call a tool on an MCP server. 
        MCP servers must be configured first. Common servers:
        - filesystem: File operations
        - github: GitHub API access
        - postgres: PostgreSQL database access
        - slack: Slack messaging
        """
        if not MCP_AVAILABLE:
            return "[Error] MCP not available. Install with: pip install mcp anthropic-mcp-client"
        
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.mcp_manager.call_tool(server_name, tool_name, arguments)
            )
            return result
        except Exception as e:
            return f"[MCP Error] {str(e)}"
    
    def mcp_list_tools(self, server_name: str) -> str:
        """
        List all available tools from an MCP server.
        Use this to discover what tools are available.
        """
        if not MCP_AVAILABLE:
            return "[Error] MCP not available. Install with: pip install mcp anthropic-mcp-client"
        
        try:
            loop = asyncio.get_event_loop()
            tools = loop.run_until_complete(
                self.mcp_manager.list_tools(server_name)
            )
            return format_json(tools)
        except Exception as e:
            return f"[MCP Error] {str(e)}"
    
    
    def search_memory(self, query: str, k: int = 5) -> str:
        """
        Search agent's long-term memory for relevant information.
        Uses vector similarity to find related past interactions.
        """
        try:
            docs = self.agent.vectorstore.similarity_search(query, k=k)
            if not docs:
                return "No relevant memories found."
            
            results = [f"--- Memory {i+1} ---\n{doc.page_content}" 
                      for i, doc in enumerate(docs)]
            return "\n\n".join(results)
        except Exception as e:
            return f"[Memory Search Error] {str(e)}"
        
# ============================================================================
# TOOL LOADER - Creates LangChain Tool instances
# ============================================================================

def ToolLoader(agent):
    """
    Create and return a list of LangChain Tool instances with proper schemas.
    
    Args:
        agent: Agent instance with mem, sess, fast_llm, deep_llm, vectorstore
    
    Returns:
        List[Tool]: Configured tools ready for LangChain agent use
    """
    tools = LLMTools(agent)
    
    tool_list = [
       
        # HTTP/API Tools
        StructuredTool.from_function(
            func=tools.http_request,
            name="http_request",
            description="Make HTTP requests to APIs. Supports GET, POST, PUT, DELETE methods.",
            args_schema=HTTPInput
        ),
        
        # Database Tools
        StructuredTool.from_function(
            func=tools.sqlite_query,
            name="sqlite_query",
            description="Execute SQLite queries. Supports SELECT, INSERT, UPDATE, DELETE.",
            args_schema=SQLInput
        ),
        
        # Memory & Search Tools
        StructuredTool.from_function(
            func=tools.search_memory,
            name="search_memory",
            description="Search agent's long-term memory for relevant past information.",
            args_schema=MemorySearchInput 
        ),

    ]
    
    # DynamicTools.add_dynamic_tools(tool_list, agent)
    
    add_llm_tools(tool_list, agent)
    
    add_git_tools(tool_list, agent)

    add_bash_tools(tool_list, agent)

    add_python_tools(tool_list, agent)
    
    add_data_processing_tools(tool_list, agent)   
    
    add_system_tools(tool_list, agent)
    
    add_time_tools(tool_list, agent)

    add_filesystem_tools(tool_list, agent)
    
    add_text_processing_tools(tool_list, agent)

    add_ssh_postgres_neo4j_tools(tool_list, agent)

    add_mcp_docker_tools(tool_list, agent)

    # add_web_crawler_tools(tool_list, agent)

    # Disabled temporarily to reduce prompt size 
    ##############################################
    
    # add_adhoc_code_tools(tool_list, agent)

    # add_microcontroller_control_tools(tool_list, agent)

    # add_versioned_file_tools(tool_list, agent)

    # add_n8n_tools(tool_list, agent)

    add_web_search_tools(tool_list, agent)

    add_osint_tools(tool_list, agent)

    add_web_recon_tools(tool_list, agent)

    add_vulnerability_intelligence_tools(tool_list, agent)

    add_network_scanning_tools(tool_list, agent)

    add_codebase_analysis_tools(tool_list, agent)

    add_dorking_tools(tool_list, agent)

    add_network_monitor_tools(tool_list, agent)
    
    # Disabled temporarily to reduce prompt size 
    ##############################################

    # # Add Babelfish tools
    # add_babelfish_tools(tool_list, agent)

    # add_orchestrator_tools(tool_list, agent)
    # tool_list.extend(add_memory_tools(agent))
    # add_advanced_memory_search_tools(tool_list, agent)
    # add_extended_memory_search_tools(tool_list, agent)


    # Deprecated - use add_osint_tools instead
    # add_all_osint_tools(tool_list, agent)
    # Deprecated - use add_network_scanning_tools instead
    # add_all_network_osint_tools(tool_list, agent)
    # Deprecated
    # add_network_infrastructure_tools(tool_list, agent)

    # Add MCP tools if available
    if MCP_AVAILABLE:
        tool_list.extend([
            StructuredTool.from_function(
                func=tools.mcp_call_tool,
                name="mcp_call",
                description="Call a tool on an MCP server (filesystem, github, postgres, slack, etc).",
                args_schema=MCPInput
            ),
            StructuredTool.from_function(
                func=tools.mcp_list_tools,
                name="mcp_list_tools",
                description="List all available tools from an MCP server.",
                args_schema=LLMQueryInput
            ),
        ])
    
    # Add executive assistant if available
    if hasattr(agent, 'executive_instance') and agent.executive_instance:
        tool_list.append(
            StructuredTool.from_function(
                func=agent.executive_instance.main,
                name="scheduling_assistant",
                description="Run the executive scheduling assistant. Access to calendars, todos, scheduling apps. Input: query string.",
            )
        )
    # ============================================================================
    # PLUGIN INTEGRATION - Recon Map Backwards Compatibility
    # ============================================================================
    # TODO: Refactor plugin tools to use the same @tool decorator and dynamic loading system as custom tools in Vera.Toolchain.dynamic_tools to simplify this integration and avoid hard dependencies on specific plugin manager implementations.
    # Add plugins as tools if plugin manager is available
    # if hasattr(agent, 'plugin_manager') and agent.plugin_manager:
    #     try:
    #         from Vera.Toolchain.plugin_tool_bridge import add_plugin_tools
    #         tool_list = add_plugin_tools(tool_list, agent)
    #     except ImportError as e:
    #         print(f"[Warning] Could not load plugin bridge: {e}")
    #     except Exception as e:
    #         print(f"[Warning] Error loading plugin tools: {e}")

    return tool_list

    
# # ============================================================================
# # EXAMPLE CUSTOM TOOL FILE (save as custom_tools/example_tool.py)
# # ============================================================================

# EXAMPLE_TOOL_TEMPLATE = '''"""
# Example custom tool - save this as: custom_tools/example_tool.py

# Functions decorated with @tool will be automatically loaded.
# Functions without decorator can be called via call_custom_tool.
# """

# from tools import tool
# from typing import Optional

# @tool(
#     name="greet_user",
#     description="Greet a user with a personalized message",
#     category="examples"
# )
# def greet_user(agent, name: str, greeting: str = "Hello") -> str:
#     """
#     Greet a user by name with a custom greeting.
    
#     Args:
#         agent: Agent instance (auto-injected)
#         name: User\'s name
#         greeting: Greeting word (default: "Hello")
    
#     Returns:
#         Personalized greeting message
#     """
#     return f"{greeting}, {name}! Nice to meet you."


# @tool(
#     name="calculate_stats",
#     description="Calculate basic statistics for a list of numbers",
#     category="examples"
# )
# def calculate_stats(agent, numbers: str) -> str:
#     """
#     Calculate mean, median, and sum for comma-separated numbers.
    
#     Args:
#         agent: Agent instance (auto-injected)
#         numbers: Comma-separated numbers (e.g., "1,2,3,4,5")
    
#     Returns:
#         Statistics as formatted string
#     """
#     try:
#         nums = [float(x.strip()) for x in numbers.split(",")]
        
#         mean = sum(nums) / len(nums)
#         sorted_nums = sorted(nums)
#         median = sorted_nums[len(sorted_nums) // 2]
        
#         return f"Count: {len(nums)}\\nSum: {sum(nums)}\\nMean: {mean:.2f}\\nMedian: {median}"
#     except Exception as e:
#         return f"Error: {str(e)}"


# # Function without decorator - callable via call_custom_tool
# def process_text(text: str, operation: str = "upper") -> str:
#     """
#     Process text with various operations.
    
#     Args:
#         text: Input text
#         operation: Operation to perform (upper, lower, reverse, length)
    
#     Returns:
#         Processed text
#     """
#     operations = {
#         "upper": lambda t: t.upper(),
#         "lower": lambda t: t.lower(),
#         "reverse": lambda t: t[::-1],
#         "length": lambda t: f"Length: {len(t)}"
#     }
    
#     if operation not in operations:
#         return f"Unknown operation. Available: {', '.join(operations.keys())}"
    
#     return operations[operation](text)
# '''


# def create_example_tool_file(tools_directory: str = "./custom_tools"):
#     """
#     Create an example tool file to demonstrate the system.
#     """
#     tools_dir = Path(tools_directory)
#     tools_dir.mkdir(exist_ok=True)
    
#     example_file = tools_dir / "example_tool.py"
    
#     if not example_file.exists():
#         example_file.write_text(EXAMPLE_TOOL_TEMPLATE)
#         print(f"✓ Created example tool file: {example_file}")
#         return str(example_file)
#     else:
#         print(f"ℹ Example tool file already exists: {example_file}")
#         return str(example_file)