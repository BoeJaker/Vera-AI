"""
NOTE: If you add new tools please run:
python3 -m Vera.Agents.agent_manager build --agent tool-agent
Then sync to all nodes if more than one available.

ENHANCED TOOL FRAMEWORK
========================
New tools can use the enhanced framework for:
    - Categorised, capability-tagged tools
    - UI component injection
    - Background service mode
    - Event bus integration
    - Memory/graph access via ToolContext
    - Streaming/yielding output
    - Orchestrator task routing

See Vera.Toolchain.tool_framework for the framework.
See Vera.Toolchain.tool_framework.examples for patterns.

Migration: Existing tools work unchanged. New tools use @enhanced_tool decorator.
The EnhancedToolLoader wraps ToolLoader and registers everything into the registry.

Usage:
    # Old way (still works):
    tools = ToolLoader(agent)
    
    # New way (adds registry, events, services):
    from Vera.Toolchain.tool_framework import EnhancedToolLoader
    tools = EnhancedToolLoader(agent)
    
    # Then query dynamically:
    security_tools = agent.tool_registry.get_by_category(ToolCategory.SECURITY)
    streaming_tools = agent.tool_registry.get_by_capability(ToolCapability.STREAMING)
    agent_tools = agent.tool_registry.get_for_agent(agent_type="coding")
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

# Enhanced Tool Framework imports
try:
    from Vera.Toolchain.tool_framework.core import (
        ToolCapability, ToolCategory, ToolMode, ToolUIType,
        ToolDescriptor, ToolContext, enhanced_tool, service_tool,
        ui_tool, sensor_tool,
    )
    from Vera.Toolchain.tool_framework.registry import ToolRegistry, global_registry
    from Vera.Toolchain.tool_framework.services import ServiceManager
    from Vera.Toolchain.tool_framework.events import ToolEventBus
    from Vera.Toolchain.tool_framework.loader import EnhancedToolLoader
    ENHANCED_FRAMEWORK_AVAILABLE = True
    print("[Tools] ✓ Enhanced tool framework available")
except ImportError as e:
    ENHANCED_FRAMEWORK_AVAILABLE = False
    print(f"[Tools] ⚠ Enhanced tool framework not available: {e}")

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
        List all available tools from