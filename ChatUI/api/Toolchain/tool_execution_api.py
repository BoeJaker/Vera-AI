#!/usr/bin/env python3
"""
Tool Execution API Module - Enhanced with Node Context Linking

Extends the modular tool execution API to link tool results to selected nodes
in the graph, creating rich contextual relationships.

New Features:
- Execute tools against specific graph nodes
- Automatically link tool results to target nodes
- Create hierarchical relationships: Node -> Tool Execution -> Results
- Track tool execution history per node
- Compatible with GraphToolExecutor frontend
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# ============================================================
# Import session management from existing API
# ============================================================
from Vera.ChatUI.api.session import sessions, get_or_create_vera

# ============================================================
# Logging
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/tools", tags=["tools"])

# ============================================================
# Request/Response Schemas - ENHANCED
# ============================================================

class ToolExecutionRequest(BaseModel):
    """Request schema for tool execution - ENHANCED with node context"""
    tool_name: str = Field(..., description="Name of the tool to execute")
    tool_input: Union[str, Dict[str, Any]] = Field(
        ..., 
        description="Tool input as string or parameter dict"
    )
    node_id: Optional[str] = Field(
        None, 
        description="Optional: ID of graph node being operated on"
    )
    link_results: bool = Field(
        True,
        description="Whether to link results to the node (if node_id provided)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "tool_name": "web_search",
                "tool_input": "latest AI developments",
                "node_id": "ip_192_168_1_1",
                "link_results": True
            }
        }


class ToolExecutionResponse(BaseModel):
    """Response schema for tool execution - ENHANCED with graph links"""
    success: bool
    tool_name: str
    input: Union[str, Dict[str, Any]]
    output: str
    duration_ms: float
    executed_at: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    graph_context: Optional[Dict[str, Any]] = None  # NEW: Graph linking info


class ToolSchema(BaseModel):
    """Schema for tool metadata"""
    name: str
    description: str
    parameters: List[Dict[str, Any]]
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class ToolListResponse(BaseModel):
    """Response for tool listing"""
    session_id: str
    tools: List[Dict[str, Any]]
    total: int
    categories: Optional[Dict[str, int]] = None


# ============================================================
# Tool Categorization Helper (same as before)
# ============================================================

def categorize_tool(tool_name: str, description: str) -> str:
    """Categorize tool based on name and description"""
    categories = {
        "Web & Search": ["web", "search", "http", "news", "browser"],
        "File System": ["file", "read", "write", "directory", "path"],
        "Code Execution": ["python", "bash", "command", "execute", "run"],
        "Database": ["sql", "postgres", "neo4j", "database", "query"],
        "Network": ["network", "scan", "port", "host", "ping", "ssh"],
        "Analysis": ["llm", "analyze", "deep", "fast", "summarize"],
        "Memory & Search": ["memory", "search", "recall", "vector"],
        "Time & Date": ["time", "date", "delta", "timezone"],
        "Data Processing": ["json", "csv", "parse", "convert", "hash"],
        "Git": ["git", "commit", "branch", "repository"],
        "Text Processing": ["text", "regex", "token", "count"],
        "System": ["system", "env", "module", "info"],
        "Orchestration": ["orchestrat", "workflow", "agent", "task"],
        "OSINT": ["osint", "reconnaissance", "intel", "gather"],
        "Plugins": ["plugin"],
    }
    
    tool_lower = (tool_name + " " + description).lower()
    
    for category, keywords in categories.items():
        if any(keyword in tool_lower for keyword in keywords):
            return category
    
    return "Other"


def extract_tool_tags(tool_name: str, description: str) -> List[str]:
    """Extract relevant tags from tool name and description"""
    tags = set()
    
    tag_patterns = {
        "streaming": ["stream", "generator"],
        "async": ["async", "concurrent"],
        "external_api": ["api", "http", "request"],
        "file_io": ["read", "write", "file"],
        "network": ["network", "socket", "connection"],
        "security": ["vulnerability", "cve", "scan", "security"],
        "ai": ["llm", "ai", "model", "gpt"],
    }
    
    text = (tool_name + " " + description).lower()
    
    for tag, patterns in tag_patterns.items():
        if any(pattern in text for pattern in patterns):
            tags.add(tag)
    
    return sorted(tags)


# ============================================================
# Graph Linking Helper - NEW
# ============================================================

def link_tool_execution_to_node(
    vera,
    node_id: str,
    tool_name: str,
    tool_input: Union[str, Dict[str, Any]],
    tool_output: str,
    execution_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Link tool execution results to a target node in the graph.
    FIXED: Now handles missing session nodes gracefully.
    """
    try:
        # Verify target node exists
        if not vera.mem.node_exists(node_id):
            logger.warning(f"Target node {node_id} does not exist in graph, creating placeholder")
            # Create a placeholder node so the link doesn't fail
            vera.mem.upsert_entity(
                node_id,
                "unknown",
                labels=["Placeholder"],
                properties={
                    "created_for": "tool_execution",
                    "created_at": datetime.now().isoformat()
                }
            )
        
        # Create execution node
        execution_id = vera.mem.create_tool_execution_node(
            node_id,
            tool_name,
            execution_metadata
        )
        
        # Create result node with output
        result_id = vera.mem.create_tool_result_node(
            execution_id,
            tool_output,
            {
                "tool_name": tool_name,
                **execution_metadata
            }
        )
        
        # Link to session using the new method
        try:
            vera.mem.link_session_to_execution(
                vera.sess.id,
                execution_id,
                "PERFORMED_TOOL_EXECUTION"
            )
        except Exception as e:
            logger.warning(f"Could not link to session {vera.sess.id}: {e}")
        
        # Link to current toolchain step if in toolchain context
        if hasattr(vera, 'toolchain') and hasattr(vera.toolchain, 'current_step_num'):
            try:
                plan_id = vera.toolchain.current_plan_id
                step_num = vera.toolchain.current_step_num
                step_node_id = f"step_{plan_id}_{step_num}"
                
                # Verify step node exists before linking
                if vera.mem.node_exists(step_node_id):
                    vera.mem.link(
                        step_node_id,
                        execution_id,
                        "EXECUTED_TOOL_ON_NODE",
                        {"target": node_id, "tool": tool_name}
                    )
            except Exception as e:
                logger.debug(f"Could not link to toolchain step: {e}")
        
        return {
            "enabled": True,
            "execution_node_id": execution_id,
            "result_node_id": result_id,
            "target_node_id": node_id,
            "links_created": [
                f"{node_id} -[TOOL_EXECUTED]-> {execution_id}",
                f"{execution_id} -[PRODUCED]-> {result_id}",
                f"session_{vera.sess.id} -[PERFORMED_TOOL_EXECUTION]-> {execution_id}",
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to link tool execution to node: {e}", exc_info=True)
        return {
            "enabled": False,
            "error": str(e)
        }
    
# ============================================================
# Tool Execution Core - ENHANCED
# ============================================================
async def execute_tool_safely(
    vera, 
    tool_name: str, 
    tool_input: Union[str, Dict[str, Any]],
    node_id: Optional[str] = None,
    link_results: bool = True
) -> Dict[str, Any]:
    """Execute a tool safely with execution tracking."""
    start_time = datetime.utcnow()
    
    try:
        tool = next((t for t in vera.tools if t.name == tool_name), None)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
        
        # Parse input
        try:
            if isinstance(tool_input, str):
                try:
                    parsed_input = json.loads(tool_input)
                except (json.JSONDecodeError, TypeError):
                    parsed_input = tool_input
            else:
                parsed_input = tool_input
        except Exception as e:
            logger.warning(f"Input parsing warning: {e}")
            parsed_input = tool_input
        
        # Create execution node BEFORE running tool
        execution_id = None
        if node_id and link_results:
            execution_id = vera.mem.create_tool_execution_node(
                node_id,
                tool_name,
                {"executed_at": start_time.isoformat()}
            )
            logger.info(f"[EXECUTION TRACKING] Created execution node: {execution_id}")
        
        # CRITICAL: Wrap tool execution in tracking context
        output = ""
        is_streaming = False
        
        # Use nullcontext if no execution_id
        import contextlib
        tracking_context = (
            vera.mem.track_execution(execution_id) 
            if execution_id 
            else contextlib.nullcontext()
        )
        
        with tracking_context:
            logger.info(f"[EXECUTION TRACKING] Entering track_execution context for {execution_id}")
            
            # Execute tool
            try:
                if isinstance(parsed_input, dict):
                    result = tool.run(parsed_input)
                else:
                    result = tool.run(parsed_input)
                
                # Handle streaming
                if hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                    is_streaming = True
                    for chunk in result:
                        output += str(chunk)
                else:
                    output = str(result)
                    
            except Exception as e:
                logger.warning(f"tool.run() failed, trying direct function call: {e}")
                
                if hasattr(tool, "func") and callable(tool.func):
                    func = tool.func
                    if isinstance(parsed_input, dict):
                        result = func(**parsed_input)
                    else:
                        result = func(parsed_input)
                    
                    if hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                        is_streaming = True
                        for chunk in result:
                            output += str(chunk)
                    else:
                        output = str(result)
                else:
                    raise
        
        # Context exited - all created nodes should now be linked
        logger.info(f"[EXECUTION TRACKING] Exited track_execution context for {execution_id}")
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000
        
        execution_metadata = {
            "success": True,
            "executed_at": start_time.isoformat(),
            "duration_ms": duration,
            "is_streaming": is_streaming,
            "output_length": len(output),
        }
        
        # Create graph context
        graph_context = None
        if node_id and link_results:
            # Create result node
            result_id = vera.mem.create_tool_result_node(
                execution_id,
                output,
                {"tool_name": tool_name, **execution_metadata}
            )
            
            # Link to session
            try:
                vera.mem.link_session_to_execution(
                    vera.sess.id,
                    execution_id,
                    "PERFORMED_TOOL_EXECUTION"
                )
            except Exception as e:
                logger.warning(f"Could not link to session: {e}")
            
            # Get created nodes
            created_nodes = vera.mem.get_execution_created_nodes(execution_id)
            logger.info(f"[EXECUTION TRACKING] Found {len(created_nodes)} created nodes for {execution_id}")
            
            graph_context = {
                "enabled": True,
                "execution_node_id": execution_id,
                "result_node_id": result_id,
                "target_node_id": node_id,
                "created_nodes_count": len(created_nodes),
                "links_created": [
                    f"{node_id} -[TOOL_EXECUTED]-> {execution_id}",
                    f"{execution_id} -[PRODUCED]-> {result_id}",
                    f"session_{vera.sess.id} -[PERFORMED_TOOL_EXECUTION]-> {execution_id}",
                ]
            }
            
            # Add created nodes to display
            for node in created_nodes[:5]:
                node_id_display = node.get('id', 'unknown')[:40]
                graph_context["links_created"].append(
                    f"{execution_id} -[CREATED_NODE]-> {node_id_display}"
                )
            if len(created_nodes) > 5:
                graph_context["links_created"].append(
                    f"... and {len(created_nodes) - 5} more nodes"
                )
        
        return {
            "success": True,
            "tool_name": tool_name,
            "input": tool_input,
            "output": output,
            "duration_ms": duration,
            "executed_at": start_time.isoformat(),
            "error": None,
            "metadata": {
                "is_streaming": is_streaming,
                "output_length": len(output),
                "node_context": node_id is not None,
            },
            "graph_context": graph_context
        }
        
    except HTTPException:
        raise
    except Exception as e:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000
        logger.error(f"Tool execution error: {str(e)}", exc_info=True)
        
        return {
            "success": False,
            "tool_name": tool_name,
            "input": tool_input,
            "output": "",
            "duration_ms": duration,
            "executed_at": start_time.isoformat(),
            "error": str(e),
            "metadata": None,
            "graph_context": None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000
        
        logger.error(f"Tool execution error: {str(e)}", exc_info=True)
        
        return {
            "success": False,
            "tool_name": tool_name,
            "input": tool_input,
            "output": "",
            "duration_ms": duration,
            "executed_at": start_time.isoformat(),
            "error": str(e),
            "metadata": None,
            "graph_context": None
        }
        # Link to graph node if requested
        graph_context = None
        if node_id and link_results:
            graph_context = link_tool_execution_to_node(
                vera,
                node_id,
                tool_name,
                tool_input,
                output,
                execution_metadata
            )
        
        return {
            "success": True,
            "tool_name": tool_name,
            "input": tool_input,
            "output": output,
            "duration_ms": duration,
            "executed_at": start_time.isoformat(),
            "error": None,
            "metadata": {
                "is_streaming": is_streaming,
                "output_length": len(output),
                "node_context": node_id is not None,
            },
            "graph_context": graph_context
        }
        
    except HTTPException:
        raise
    except Exception as e:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000
        
        logger.error(f"Tool execution error: {str(e)}", exc_info=True)
        
        return {
            "success": False,
            "tool_name": tool_name,
            "input": tool_input,
            "output": "",
            "duration_ms": duration,
            "executed_at": start_time.isoformat(),
            "error": str(e),
            "metadata": None,
            "graph_context": None
        }


# ============================================================
# API Endpoints - ENHANCED
# ============================================================

@router.post("/{session_id}/execute")
async def execute_tool(
    session_id: str, 
    request: ToolExecutionRequest
) -> ToolExecutionResponse:
    """
    Execute a single tool with given input, optionally linking to a graph node.
    
    When node_id is provided and link_results is True, creates graph relationships:
        - TargetNode -[TOOL_EXECUTED]-> ToolExecution
        - ToolExecution -[PRODUCED]-> ToolResult
        - Session -[PERFORMED_TOOL_EXECUTION]-> ToolExecution
        - (If in toolchain) Step -[EXECUTED_TOOL_ON_NODE]-> ToolExecution
    
    This creates rich context showing which tools were run against which nodes.
    
    Example:
        POST /api/tools/{session_id}/execute
        {
            "tool_name": "scan_ports",
            "tool_input": {"ports": "1-1000"},
            "node_id": "ip_192_168_1_1",
            "link_results": true
        }
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        # FIXED: Don't use asyncio.run() in executor, just call the function directly
        # This ensures thread-local storage works correctly
        def sync_execute():
            # Run synchronously in the thread
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(execute_tool_safely(
                vera, 
                request.tool_name, 
                request.tool_input,
                node_id=request.node_id,
                link_results=request.link_results
            ))
        
        # Execute in thread pool (for blocking I/O operations)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, sync_execute)
        
        return ToolExecutionResponse(**result)
        
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/node/{node_id}/executions")
async def get_node_tool_executions(
    session_id: str,
    node_id: str,
    limit: int = Query(20, description="Max executions to return", ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get tool execution history for a specific node.
    
    Returns all tools that have been executed against this node,
    with their results and metadata.
    
    Example:
        GET /api/tools/{session_id}/node/ip_192_168_1_1/executions?limit=10
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        # Query graph for tool executions on this node
        with vera.mem.graph._driver.session() as sess:
            result = sess.run("""
                MATCH (node {id: $node_id})-[r:TOOL_EXECUTED]->(exec:ToolExecution)
                OPTIONAL MATCH (exec)-[:PRODUCED]->(result:ToolResult)
                RETURN exec, result, r
                ORDER BY exec.executed_at DESC
                LIMIT $limit
            """, {"node_id": node_id, "limit": limit})
            
            executions = []
            for record in result:
                exec_node = record["exec"]
                result_node = record.get("result")
                relationship = record["r"]
                
                execution_data = {
                    "execution_id": exec_node.get("id"),
                    "tool_name": exec_node.get("tool_name"),
                    "executed_at": exec_node.get("executed_at"),
                    "duration_ms": exec_node.get("duration_ms"),
                    "success": exec_node.get("success", True),
                    "input_summary": exec_node.get("input_summary"),
                }
                
                if result_node:
                    execution_data["result"] = {
                        "result_id": result_node.get("id"),
                        "output_preview": result_node.get("output_preview"),
                        "output_length": result_node.get("output_length"),
                    }
                
                executions.append(execution_data)
        
        return {
            "session_id": session_id,
            "node_id": node_id,
            "executions": executions,
            "total": len(executions)
        }
        
    except Exception as e:
        logger.error(f"Failed to get node executions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/execution/{execution_id}/result")
async def get_execution_result(
    session_id: str,
    execution_id: str
) -> Dict[str, Any]:
    """
    Get full result of a tool execution.
    
    Returns complete output, even if it was truncated in the node view.
    
    Example:
        GET /api/tools/{session_id}/execution/tool_exec_123_web_search_456/result
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as sess:
            # Get execution and result
            result = sess.run("""
                MATCH (exec:ToolExecution {id: $exec_id})-[:PRODUCED]->(result:ToolResult)
                OPTIONAL MATCH (result)-[:FULL_OUTPUT]->(doc)
                RETURN exec, result, doc
            """, {"exec_id": execution_id})
            
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            exec_node = record["exec"]
            result_node = record["result"]
            doc_node = record.get("doc")
            
            # Get full output from document if available
            full_output = result_node.get("output_preview")
            if doc_node:
                full_output = doc_node.get("content", full_output)
            
            return {
                "execution_id": execution_id,
                "tool_name": exec_node.get("tool_name"),
                "target_node": exec_node.get("target_node"),
                "executed_at": exec_node.get("executed_at"),
                "duration_ms": exec_node.get("duration_ms"),
                "success": exec_node.get("success", True),
                "input": exec_node.get("input_summary"),
                "output": full_output,
                "output_length": result_node.get("output_length"),
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get execution result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Keep all other endpoints from previous version
# ============================================================

@router.get("/{session_id}/tool/{tool_name}/schema")
async def get_tool_schema(session_id: str, tool_name: str) -> ToolSchema:
    """Get the input schema for a specific tool."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    tool = next((t for t in vera.tools if t.name == tool_name), None)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    
    description = getattr(tool, "description", "") or ""
    
    schema_info = {
        "name": tool.name,
        "description": description,
        "parameters": [],
        "category": categorize_tool(tool.name, description),
        "tags": extract_tool_tags(tool.name, description)
    }
    
    if hasattr(tool, "args_schema") and tool.args_schema:
        schema = tool.args_schema.schema()
        
        for field_name, field_info in schema.get("properties", {}).items():
            param = {
                "name": field_name,
                "type": field_info.get("type", "string"),
                "description": field_info.get("description", ""),
                "required": field_name in schema.get("required", []),
                "default": field_info.get("default")
            }
            
            if "enum" in field_info:
                param["enum"] = field_info["enum"]
            
            schema_info["parameters"].append(param)
    else:
        schema_info["parameters"] = [{
            "name": "input",
            "type": "string",
            "description": "Tool input",
            "required": True,
            "default": None
        }]
    
    return ToolSchema(**schema_info)


@router.get("/{session_id}/list")
async def list_tools(
    session_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    tag: Optional[str] = Query(None, description="Filter by tag")
) -> ToolListResponse:
    """List all available tools with optional filtering."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    tools_info = []
    category_counts = {}
    
    for tool in vera.tools:
        description = getattr(tool, "description", "") or "No description available"
        tool_category = categorize_tool(tool.name, description)
        tool_tags = extract_tool_tags(tool.name, description)
        
        if category and tool_category != category:
            continue
        
        if search:
            search_lower = search.lower()
            if (search_lower not in tool.name.lower() and 
                search_lower not in description.lower()):
                continue
        
        if tag and tag not in tool_tags:
            continue
        
        category_counts[tool_category] = category_counts.get(tool_category, 0) + 1
        
        tools_info.append({
            "name": tool.name,
            "description": description,
            "type": type(tool).__name__,
            "category": tool_category,
            "tags": tool_tags
        })
    
    return ToolListResponse(
        session_id=session_id,
        tools=tools_info,
        total=len(tools_info),
        categories=category_counts if not category else None
    )


@router.get("/{session_id}/categories")
async def list_categories(session_id: str) -> Dict[str, Any]:
    """List all tool categories with counts."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    category_counts = {}
    all_tags = set()
    
    for tool in vera.tools:
        description = getattr(tool, "description", "") or ""
        category = categorize_tool(tool.name, description)
        tags = extract_tool_tags(tool.name, description)
        
        category_counts[category] = category_counts.get(category, 0) + 1
        all_tags.update(tags)
    
    return {
        "session_id": session_id,
        "categories": dict(sorted(category_counts.items())),
        "total_categories": len(category_counts),
        "total_tools": len(vera.tools),
        "available_tags": sorted(all_tags)
    }


@router.get("/{session_id}/search")
async def search_tools(
    session_id: str,
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Max results", ge=1, le=50)
) -> Dict[str, Any]:
    """Search tools by name and description with relevance scoring."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    query_lower = query.lower()
    
    results = []
    
    for tool in vera.tools:
        description = getattr(tool, "description", "") or ""
        name_lower = tool.name.lower()
        desc_lower = description.lower()
        
        score = 0
        
        if query_lower == name_lower:
            score += 100
        elif query_lower in name_lower:
            score += 50
        if name_lower.startswith(query_lower):
            score += 25
        
        if query_lower in desc_lower:
            score += 10
            score += desc_lower.count(query_lower) * 2
        
        if score > 0:
            results.append({
                "name": tool.name,
                "description": description,
                "category": categorize_tool(tool.name, description),
                "relevance_score": score
            })
    
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    return {
        "session_id": session_id,
        "query": query,
        "results": results[:limit],
        "total_matches": len(results)
    }


@router.get("/{session_id}/info")
async def get_tools_info(session_id: str) -> Dict[str, Any]:
    """Get comprehensive information about the tool system."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    category_counts = {}
    all_tags = set()
    
    for tool in vera.tools:
        description = getattr(tool, "description", "") or ""
        category = categorize_tool(tool.name, description)
        tags = extract_tool_tags(tool.name, description)
        
        category_counts[category] = category_counts.get(category, 0) + 1
        all_tags.update(tags)
    
    return {
        "session_id": session_id,
        "total_tools": len(vera.tools),
        "categories": category_counts,
        "total_categories": len(category_counts),
        "available_tags": sorted(all_tags),
        "plugin_system_available": hasattr(vera, 'plugin_manager') and vera.plugin_manager is not None,
        "toolchain_available": hasattr(vera, 'toolchain') and vera.toolchain is not None,
        "features": {
            "node_linking": True,
            "execution_history": True,
            "streaming_support": True
        }
    }
    # Add to your tools.py API module

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import asyncio
from datetime import datetime

# Global event bus for graph updates
graph_update_events = {}  # session_id -> asyncio.Queue

@router.get("/{session_id}/updates/stream")
async def stream_graph_updates(session_id: str):
    """SSE endpoint for real-time graph update notifications"""
    
    # Create queue for this client
    if session_id not in graph_update_events:
        graph_update_events[session_id] = asyncio.Queue()
    
    queue = graph_update_events[session_id]
    
    async def event_generator():
        try:
            while True:
                # Wait for update event
                event_data = await queue.get()
                yield {
                    "event": "graph_update",
                    "data": json.dumps(event_data)
                }
        except asyncio.CancelledError:
            pass
    
    return EventSourceResponse(event_generator())


def notify_graph_update(session_id: str, update_data: Dict[str, Any]):
    """Notify all listeners of a graph update"""
    if session_id in graph_update_events:
        try:
            graph_update_events[session_id].put_nowait(update_data)
        except:
            pass
        
@router.get("/{session_id}/execution/{execution_id}/created-nodes")
async def get_execution_created_nodes(
    session_id: str,
    execution_id: str
) -> Dict[str, Any]:
    """Get all nodes created during a tool execution"""
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        created_nodes = vera.mem.get_execution_created_nodes(execution_id)
        
        # Get connected edges
        node_ids = [n['id'] for n in created_nodes]
        
        edges = []
        if node_ids:
            with vera.mem.graph._driver.session() as sess:
                result = sess.run("""
                    MATCH (n)-[r]-(m)
                    WHERE n.id IN $node_ids OR m.id IN $node_ids
                    RETURN DISTINCT
                        n.id as from_id,
                        m.id as to_id,
                        type(r) as rel_type,
                        properties(r) as props
                """, {"node_ids": node_ids})
                
                for record in result:
                    edges.append({
                        'from': record['from_id'],
                        'to': record['to_id'],
                        'label': record['rel_type'],
                        'properties': dict(record['props']) if record['props'] else {}
                    })
        
        return {
            "execution_id": execution_id,
            "nodes": created_nodes,
            "edges": edges,
            "total_nodes": len(created_nodes),
            "total_edges": len(edges)
        }
        
    except Exception as e:
        logger.error(f"Failed to get created nodes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))