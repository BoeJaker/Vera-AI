from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union, Literal
# ============================================================================
# MISSING INPUT SCHEMAS
# ============================================================================

class SearchFilesInput(BaseModel):
    """Input schema for searching files."""
    path: str = Field(default=".", description="Directory path to search in")
    pattern: str = Field(..., description="Pattern to match (glob or regex)")


class TimezoneInput(BaseModel):
    """Input schema for timezone operations."""
    timezone: str = Field(default="UTC", description="Timezone name (e.g., UTC, America/New_York, Europe/London)")


class TimeDeltaInput(BaseModel):
    """Input schema for time delta calculation."""
    start_time: str = Field(..., description="Start time in format YYYY-MM-DD HH:MM:SS or YYYY-MM-DD")
    end_time: Optional[str] = Field(default=None, description="End time (defaults to current time if not provided)")


class TokenCountInput(BaseModel):
    """Input schema for token counting."""
    text: str = Field(..., description="Text to count tokens for")
    model: str = Field(default="gpt-3.5-turbo", description="Model to use for token counting")


class RegexSearchInput(BaseModel):
    """Input schema for regex search."""
    pattern: str = Field(..., description="Regular expression pattern")
    text: str = Field(..., description="Text to search in")
    flags: str = Field(default="", description="Regex flags: i (ignore case), m (multiline), s (dotall)")


class TextInput(BaseModel):
    """Input schema for text processing."""
    text: str = Field(..., description="Text to process")


class HashInput(BaseModel):
    """Input schema for hashing."""
    text: str = Field(..., description="Text to hash")
    algorithm: str = Field(default="sha256", description="Hash algorithm: md5, sha1, sha256, sha512")


class EnvVarInput(BaseModel):
    """Input schema for environment variable operations."""
    var_name: str = Field(..., description="Name of the environment variable")


class EmptyInput(BaseModel):
    """Input schema for tools that take no parameters."""
    pass

class MemorySearchInput(BaseModel):
    """Input schema for memory search operations."""
    query: str = Field(..., description="Search query for long-term memory")
    k: int = Field(default=5, description="Number of results to return")
# ============================================================================
# INPUT SCHEMAS - Strongly typed inputs for better LLM understanding
# ============================================================================

class FilePathInput(BaseModel):
    """Input schema for file path operations."""
    path: str = Field(..., description="Full path to the file")


class WriteFileInput(BaseModel):
    """Input schema for writing files."""
    path: str = Field(..., description="Full path where file should be written")
    content: str = Field(..., description="Content to write to the file")


class CommandInput(BaseModel):
    """Input schema for shell commands."""
    command: str = Field(..., description="Shell command to execute")


class PythonInput(BaseModel):
    """Input schema for Python code execution."""
    code: str = Field(..., description="Python code to execute")


class SearchInput(BaseModel):
    """Input schema for web searches."""
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=10, description="Maximum number of results to return")
    search_engine: str = Field(default="duckduckgo", description="Search engine to use: duckduckgo, google, bing, brave, perplexity")


class WebReportInput(BaseModel):
    """Input schema for comprehensive web search reports."""
    input_data: str = Field(..., description="Search query or existing search results text")
    max_results: int = Field(default=5, description="Maximum number of pages to scrape")


class LLMQueryInput(BaseModel):
    """Input schema for LLM queries."""
    query: str = Field(..., description="Query or prompt for the LLM")


class MCPInput(BaseModel):
    """Input schema for MCP operations."""
    server_name: str = Field(..., description="Name of the MCP server to use")
    tool_name: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")


class HTTPInput(BaseModel):
    """Input schema for HTTP requests."""
    url: str = Field(..., description="URL to request")
    method: str = Field(default="GET", description="HTTP method (GET, POST, PUT, DELETE)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Request headers")
    body: Optional[str] = Field(default=None, description="Request body for POST/PUT")


class SQLInput(BaseModel):
    """Input schema for SQLite operations."""
    db_path: str = Field(..., description="Path to SQLite database")
    query: str = Field(..., description="SQL query to execute")


class GitInput(BaseModel):
    """Input schema for Git operations."""
    repo_path: str = Field(default=".", description="Path to git repository")
    command: str = Field(..., description="Git command (status, log, diff, etc.)")
    args: str = Field(default="", description="Additional arguments for the command")


class CustomToolInput(BaseModel):
    """Input schema for custom tool operations."""
    tool_name: str = Field(..., description="Name of the tool file (without .py extension)")
    function_name: str = Field(..., description="Name of the function to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the function as key-value pairs")


class ToolDiscoveryInput(BaseModel):
    """Input schema for tool discovery."""
    pattern: str = Field(default="*", description="Pattern to filter tools (e.g., 'data_*' or '*')")


# ============================================================================
# ADDITIONAL TOOLS FOR TOOL MANAGEMENT
# ============================================================================

class DiscoverToolsInput(BaseModel):
    """Input for discovering tools."""
    pattern: str = Field(default="*", description="Pattern to filter tools (e.g., 'data_*' or '*')")


class CallCustomToolInput(BaseModel):
    """Input for calling custom tools."""
    tool_name: str = Field(..., description="Name of the tool file (without .py)")
    function_name: str = Field(..., description="Function name to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments as key-value pairs")


class ListToolFunctionsInput(BaseModel):
    """Input for listing functions in a tool."""
    tool_name: str = Field(..., description="Name of the tool file (without .py)")


# ============================================================================
# BABELFISH INPUT SCHEMAS
# ============================================================================

class BabelfishProtocolInput(BaseModel):
    """Input schema for Babelfish protocol operations."""
    protocol: Literal["http", "ws", "mqtt", "tcp", "udp", "smtp"] = Field(
        ..., description="Protocol to use: http, ws, mqtt, tcp, udp, smtp"
    )
    action: str = Field(..., description="Action to perform (protocol-specific)")
    params: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Protocol-specific parameters"
    )


class BabelfishHandleInput(BaseModel):
    """Input schema for Babelfish handle operations."""
    action: Literal["handles/list", "handles/read", "handles/close"] = Field(
        ..., description="Handle operation: list, read, or close"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters: {kind: str, handle: str, max_items: int}"
    )


class WebServerInput(BaseModel):
    """Input schema for WebServer operations."""
    action: Literal["start", "add_static", "add_dynamic", "remove_route", "list_routes"] = Field(
        ..., description="WebServer action to perform"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters"
    )


# ============================================================================
# WEB CRAWLER INPUT SCHEMAS
# ============================================================================

class WebCrawlInput(BaseModel):
    """Input schema for web crawling operations."""
    url: str = Field(..., description="URL to crawl")
    max_depth: int = Field(default=2, description="Maximum crawl depth (0-5)")
    use_hybrid: bool = Field(default=True, description="Use hybrid mode (live + Common Crawl fallback)")


class WebMemoryQueryInput(BaseModel):
    """Input schema for querying web crawl memory."""
    query: str = Field(..., description="Search query for crawled content")
    n_results: int = Field(default=5, description="Number of results to return")
    min_score: float = Field(default=0.3, description="Minimum similarity score (0.0-1.0)")


class WebNavigateInput(BaseModel):
    """Input schema for intelligent web navigation."""
    instruction: str = Field(..., description="Navigation instruction or question about web content")
    target_url: Optional[str] = Field(default="", description="Optional target URL")
    ensure_context: bool = Field(default=True, description="Auto-crawl if insufficient context")


class WebTechDetectInput(BaseModel):
    """Input schema for technology detection."""
    url: str = Field(..., description="URL to analyze for technologies")

