"""
n8n Proxy API Routes
Routes n8n API calls through the Vera backend to avoid CORS issues
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/n8n", tags=["n8n"])

# ============================================================
# Configuration
# ============================================================

class N8nConfig:
    """n8n connection configuration with persistent storage"""
    
    CONFIG_FILE = Path.home() / ".vera" / "n8n_config.json"
    
    def __init__(self):
        self._url = None
        self._api_key = None
        self._load_config()
    
    def _load_config(self):
        """Load config from file or environment variables"""
        # Try loading from file first
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self._url = data.get("url", "http://localhost:5678").rstrip("/")
                    self._api_key = data.get("api_key")
                    logger.info(f"Loaded n8n config from {self.CONFIG_FILE}")
                    return
            except Exception as e:
                logger.warning(f"Failed to load n8n config: {e}")
        
        # Fall back to environment variables
        self._url = os.getenv("N8N_URL", "http://localhost:5678").rstrip("/")
        self._api_key = os.getenv("N8N_API_KEY")
        
        # Save to file if we have config
        if self._url or self._api_key:
            self._save_config()
    
    def _save_config(self):
        """Save config to file"""
        try:
            self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({
                    "url": self._url,
                    "api_key": self._api_key
                }, f, indent=2)
            logger.info(f"Saved n8n config to {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save n8n config: {e}")
    
    @property
    def url(self) -> str:
        return self._url
    
    @url.setter
    def url(self, value: str):
        self._url = value.rstrip("/") if value else None
        self._save_config()
    
    @property
    def api_key(self) -> Optional[str]:
        return self._api_key
    
    @api_key.setter
    def api_key(self, value: Optional[str]):
        self._api_key = value if value else None
        self._save_config()
    
    @property
    def headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-N8N-API-KEY"] = self._api_key
        return headers
    
    def has_api_key(self) -> bool:
        return bool(self._api_key)
    
    def is_configured(self) -> bool:
        return bool(self._url)

n8n_config = N8nConfig()

# ============================================================
# Request/Response Models
# ============================================================

class N8nConfigUpdate(BaseModel):
    url: str
    api_key: Optional[str] = None

class WorkflowExecuteRequest(BaseModel):
    data: Optional[Dict[str, Any]] = None

class ToolchainToWorkflowRequest(BaseModel):
    tool_plan: List[Dict[str, str]]
    workflow_name: Optional[str] = None

class WorkflowUpdateRequest(BaseModel):
    active: Optional[bool] = None
    name: Optional[str] = None
    nodes: Optional[List[Dict]] = None
    connections: Optional[Dict] = None
    settings: Optional[Dict] = None

# ============================================================
# Configuration Endpoints
# ============================================================

@router.get("/config")
async def get_n8n_config():
    """Get current n8n configuration (without exposing API key)"""
    return {
        "url": n8n_config.url or "http://localhost:5678",
        "has_api_key": n8n_config.has_api_key(),
        "is_configured": n8n_config.is_configured()
    }

@router.put("/config")
async def update_n8n_config(config: N8nConfigUpdate):
    """Update n8n configuration"""
    n8n_config.url = config.url
    
    # Only update API key if explicitly provided
    if config.api_key is not None and config.api_key != "":
        n8n_config.api_key = config.api_key
    
    logger.info(f"Updated n8n config: url={n8n_config.url}, has_api_key={n8n_config.has_api_key()}")
    
    return {
        "status": "updated",
        "url": n8n_config.url,
        "has_api_key": n8n_config.has_api_key(),
        "message": "Configuration saved successfully"
    }

@router.get("/test")
async def test_n8n_connection():
    """Test connection to n8n"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/workflows",
                headers=n8n_config.headers,
                params={"limit": 1}
            )
            
            if response.status_code == 200:
                return {
                    "status": "connected",
                    "url": n8n_config.url,
                    "message": "Successfully connected to n8n"
                }
            else:
                return {
                    "status": "error",
                    "url": n8n_config.url,
                    "message": f"n8n returned status {response.status_code}",
                    "detail": response.text[:500]
                }
    except httpx.ConnectError as e:
        return {
            "status": "error",
            "url": n8n_config.url,
            "message": f"Connection failed: Could not connect to {n8n_config.url}",
            "detail": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "url": n8n_config.url,
            "message": f"Connection failed: {str(e)}"
        }

# ============================================================
# Workflow Endpoints
# ============================================================

@router.get("/workflows")
async def list_workflows(
    limit: int = Query(100, ge=1, le=250),
    cursor: Optional[str] = None,
    tags: Optional[str] = None
):
    """List all n8n workflows"""
    try:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if tags:
            params["tags"] = tags
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/workflows",
                headers=n8n_config.headers,
                params=params
            )
            
            # Handle 401 Unauthorized - likely missing/invalid API key
            if response.status_code == 401:
                error_detail = "n8n requires authentication. Please configure your API key in Settings."
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_detail = f"n8n authentication failed: {error_data['message']}"
                except:
                    pass
                
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": "authentication_required",
                        "message": error_detail,
                        "hint": "Configure your n8n API key in the Workflows settings panel"
                    }
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "connection_failed",
                "message": f"Could not connect to n8n at {n8n_config.url}",
                "hint": "Check that n8n is running and the URL is correct"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a specific workflow by ID"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/workflows/{workflow_id}",
                headers=n8n_config.headers
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows")
async def create_workflow(workflow: Dict[str, Any]):
    """Create a new workflow in n8n"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{n8n_config.url}/api/v1/workflows",
                headers=n8n_config.headers,
                json=workflow
            )
            
            if response.status_code not in (200, 201):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, update: WorkflowUpdateRequest):
    """Update a workflow (activate/deactivate, rename, etc.)"""
    try:
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(
                f"{n8n_config.url}/api/v1/workflows/{workflow_id}",
                headers=n8n_config.headers,
                json=update_data
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{n8n_config.url}/api/v1/workflows/{workflow_id}",
                headers=n8n_config.headers
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            if response.status_code not in (200, 204):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return {"status": "deleted", "workflow_id": workflow_id}
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Execution Endpoints
# ============================================================

@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, request: WorkflowExecuteRequest = None):
    """Execute a workflow"""
    try:
        payload = {}
        if request and request.data:
            payload["data"] = request.data
        
        async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for execution
            response = await client.post(
                f"{n8n_config.url}/api/v1/workflows/{workflow_id}/execute",
                headers=n8n_config.headers,
                json=payload
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions")
async def list_executions(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=250)
):
    """List workflow executions"""
    try:
        params = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/executions",
                headers=n8n_config.headers,
                params=params
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing executions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get details of a specific execution"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/executions/{execution_id}",
                headers=n8n_config.headers
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution {execution_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/executions/{execution_id}")
async def delete_execution(execution_id: str):
    """Delete an execution record"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{n8n_config.url}/api/v1/executions/{execution_id}",
                headers=n8n_config.headers
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            if response.status_code not in (200, 204):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return {"status": "deleted", "execution_id": execution_id}
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting execution {execution_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Toolchain Integration Endpoints
# ============================================================

@router.post("/toolchain-to-workflow")
async def convert_toolchain_to_workflow(request: ToolchainToWorkflowRequest):
    """
    Convert a Vera toolchain plan to an n8n workflow and create it
    """
    tool_plan = request.tool_plan
    workflow_name = request.workflow_name or f"Vera_Toolchain_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    nodes = []
    connections = {}
    
    # Manual trigger node
    nodes.append({
        "parameters": {},
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [250, 300]
    })
    
    # Convert each tool step to HTTP request node
    for idx, step in enumerate(tool_plan):
        tool_name = step.get("tool", "unknown")
        tool_input = step.get("input", "")
        
        node = {
            "parameters": {
                "method": "POST",
                "url": "={{$env.VERA_API_URL}}/api/toolchain/{{$env.VERA_SESSION_ID}}/execute-tool",
                "sendQuery": True,
                "queryParameters": {
                    "parameters": [
                        {"name": "tool_name", "value": tool_name},
                        {"name": "tool_input", "value": tool_input}
                    ]
                },
                "options": {}
            },
            "name": f"Step_{idx + 1}_{tool_name}",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [450 + (idx * 200), 300],
            "notes": f"Tool: {tool_name}\nInput: {tool_input}"
        }
        
        # Handle placeholders - convert to n8n expressions
        if "{prev}" in tool_input and idx > 0:
            prev_node_name = f"Step_{idx}_{tool_plan[idx-1].get('tool', 'unknown')}"
            modified_input = tool_input.replace(
                "{prev}", 
                f"{{{{ $node['{prev_node_name}'].json.output }}}}"
            )
            node["parameters"]["queryParameters"]["parameters"][1]["value"] = modified_input
        
        # Handle {step_X} references
        import re
        step_refs = re.findall(r'\{step_(\d+)\}', tool_input)
        for step_num in step_refs:
            step_idx = int(step_num) - 1
            if step_idx < len(tool_plan):
                ref_node_name = f"Step_{step_num}_{tool_plan[step_idx].get('tool', 'unknown')}"
                tool_input = tool_input.replace(
                    f"{{step_{step_num}}}", 
                    f"{{{{ $node['{ref_node_name}'].json.output }}}}"
                )
                node["parameters"]["queryParameters"]["parameters"][1]["value"] = tool_input
        
        nodes.append(node)
        
        # Create connections
        prev_node_name = "Manual Trigger" if idx == 0 else f"Step_{idx}_{tool_plan[idx-1].get('tool', 'unknown')}"
        connections[prev_node_name] = {
            "main": [[{"node": node["name"], "type": "main", "index": 0}]]
        }
    
    workflow = {
        "name": workflow_name,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1"
        },
        "tags": [
            {"name": "vera-toolchain"},
            {"name": "auto-generated"}
        ]
    }
    
    # Create the workflow in n8n
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{n8n_config.url}/api/v1/workflows",
                headers=n8n_config.headers,
                json=workflow
            )
            
            if response.status_code not in (200, 201):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            result = response.json()
            return {
                "status": "created",
                "workflow_id": result.get("id"),
                "workflow_name": workflow_name,
                "workflow": result
            }
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workflow from toolchain: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflow-to-toolchain/{workflow_id}")
async def convert_workflow_to_toolchain(workflow_id: str):
    """
    Convert an n8n workflow back to a Vera toolchain plan
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/workflows/{workflow_id}",
                headers=n8n_config.headers
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            workflow = response.json()
            
        # Convert nodes to toolchain steps
        tool_plan = []
        nodes = workflow.get("nodes", [])
        
        # Sort nodes by position (left to right)
        http_nodes = [n for n in nodes if n.get("type") == "n8n-nodes-base.httpRequest"]
        http_nodes.sort(key=lambda n: n.get("position", [0, 0])[0])
        
        for node in http_nodes:
            # Extract tool name from node name or URL
            node_name = node.get("name", "")
            tool_name = "unknown"
            tool_input = ""
            
            # Try to parse from node name (Step_X_toolname pattern)
            if "_" in node_name:
                parts = node_name.split("_")
                if len(parts) >= 3:
                    tool_name = "_".join(parts[2:])  # Handle tool names with underscores
            
            # Try to get input from query parameters
            params = node.get("parameters", {})
            query_params = params.get("queryParameters", {}).get("parameters", [])
            
            for param in query_params:
                if param.get("name") == "tool_name":
                    tool_name = param.get("value", tool_name)
                elif param.get("name") == "tool_input":
                    tool_input = param.get("value", "")
            
            # Convert n8n expressions back to {prev} format
            if "$node['" in tool_input:
                # Simplistic conversion - could be enhanced
                tool_input = "{prev}"  # Simplified
            
            tool_plan.append({
                "tool": tool_name,
                "input": tool_input
            })
        
        return {
            "workflow_id": workflow_id,
            "workflow_name": workflow.get("name"),
            "tool_plan": tool_plan,
            "total_steps": len(tool_plan)
        }
        
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting workflow to toolchain: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Credentials & Tags (optional endpoints)
# ============================================================

@router.get("/tags")
async def list_tags():
    """List all workflow tags"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{n8n_config.url}/api/v1/tags",
                headers=n8n_config.headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"n8n error: {response.text}"
                )
            
            return response.json()
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to n8n at {n8n_config.url}"
        )
    except Exception as e:
        logger.error(f"Error listing tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))