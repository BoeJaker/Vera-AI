"""
n8n Workflow Management Tools
Enables LLM to create, edit, query, and execute n8n workflows
Add this section to your existing tools.py file
"""

import json
import requests
import time
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class N8nWorkflowCreateInput(BaseModel):
    """Input schema for creating n8n workflows."""
    workflow_name: str = Field(..., description="Name for the workflow")
    description: str = Field(default="", description="Workflow description")
    nodes: List[Dict[str, Any]] = Field(
        ..., 
        description="List of workflow nodes with their configurations"
    )
    connections: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional connections between nodes (auto-generated if not provided)"
    )
    settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Workflow settings (execution order, timeout, etc.)"
    )


class N8nWorkflowFromToolchainInput(BaseModel):
    """Input schema for creating workflows from toolchains."""
    toolchain_plan: List[Dict[str, Any]] = Field(
        ..., 
        description="Vera toolchain plan to convert"
    )
    workflow_name: str = Field(..., description="Name for the n8n workflow")
    auto_connect: bool = Field(
        default=True,
        description="Automatically connect nodes in sequence"
    )


class N8nWorkflowEditInput(BaseModel):
    """Input schema for editing workflows."""
    workflow_id: str = Field(..., description="ID of the workflow to edit")
    operations: List[Dict[str, Any]] = Field(
        ...,
        description="List of edit operations: add_node, remove_node, update_node, add_connection, etc."
    )


class N8nWorkflowQueryInput(BaseModel):
    """Input schema for querying workflows."""
    workflow_id: Optional[str] = Field(
        default=None, 
        description="Specific workflow ID (optional)"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    active: Optional[bool] = Field(
        default=None,
        description="Filter by active status"
    )


class N8nWorkflowExecuteInput(BaseModel):
    """Input schema for executing workflows."""
    workflow_id: str = Field(..., description="ID of workflow to execute")
    input_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Input data for the workflow execution"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="Wait for execution to complete"
    )


class N8nWorkflowControlInput(BaseModel):
    """Input schema for workflow control operations."""
    workflow_id: str = Field(..., description="Workflow ID")
    action: Literal["activate", "deactivate", "delete", "duplicate"] = Field(
        ..., description="Control action to perform"
    )


class N8nNodeCreateInput(BaseModel):
    """Input schema for creating individual nodes."""
    node_type: str = Field(
        ..., 
        description="Type of node (e.g., 'n8n-nodes-base.httpRequest', 'n8n-nodes-base.code')"
    )
    node_name: str = Field(..., description="Name for the node")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Node parameters and configuration"
    )
    position: Optional[List[int]] = Field(
        default=None,
        description="[x, y] position in workflow canvas"
    )


class N8nExecutionQueryInput(BaseModel):
    """Input schema for querying executions."""
    workflow_id: Optional[str] = Field(
        default=None,
        description="Filter by workflow ID"
    )
    limit: int = Field(
        default=10,
        description="Number of executions to return"
    )
    status: Optional[Literal["success", "error", "waiting", "running"]] = Field(
        default=None,
        description="Filter by execution status"
    )


# ============================================================================
# N8N NODE TEMPLATES
# ============================================================================

class N8nNodeTemplates:
    """Templates for common n8n node types."""
    
    @staticmethod
    def http_request(url: str, method: str = "GET", body: Dict = None, headers: Dict = None) -> Dict:
        """HTTP Request node template."""
        return {
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "method": method.upper(),
                "url": url,
                "options": {},
                "bodyParametersJson": json.dumps(body) if body else "{}",
                "headerParametersJson": json.dumps(headers) if headers else "{}"
            }
        }
    
    @staticmethod
    def code_node(javascript_code: str, mode: str = "runOnceForAllItems") -> Dict:
        """JavaScript code node template."""
        return {
            "type": "n8n-nodes-base.code",
            "parameters": {
                "mode": mode,
                "jsCode": javascript_code
            }
        }
    
    @staticmethod
    def python_code(python_code: str) -> Dict:
        """Python code node template."""
        return {
            "type": "n8n-nodes-base.code",
            "parameters": {
                "language": "python",
                "pythonCode": python_code
            }
        }
    
    @staticmethod
    def webhook(path: str, method: str = "POST") -> Dict:
        """Webhook trigger node template."""
        return {
            "type": "n8n-nodes-base.webhook",
            "parameters": {
                "path": path,
                "httpMethod": method,
                "responseMode": "onReceived"
            }
        }
    
    @staticmethod
    def schedule(interval: str = "hours", hours: int = 1) -> Dict:
        """Schedule trigger node template."""
        return {
            "type": "n8n-nodes-base.scheduleTrigger",
            "parameters": {
                "rule": {
                    "interval": [{
                        "field": interval,
                        "value": hours
                    }]
                }
            }
        }
    
    @staticmethod
    def if_node(condition_type: str, value1: str, operation: str, value2: str) -> Dict:
        """IF conditional node template."""
        return {
            "type": "n8n-nodes-base.if",
            "parameters": {
                "conditions": {
                    "boolean": [{
                        "value1": value1,
                        "value2": value2,
                        "operation": operation
                    }]
                }
            }
        }
    
    @staticmethod
    def postgres_node(operation: str, query: str = "") -> Dict:
        """PostgreSQL node template."""
        return {
            "type": "n8n-nodes-base.postgres",
            "parameters": {
                "operation": operation,
                "query": query if query else "={{ $json.query }}"
            }
        }
    
    @staticmethod
    def set_node(values: Dict[str, Any]) -> Dict:
        """Set node template for data manipulation."""
        return {
            "type": "n8n-nodes-base.set",
            "parameters": {
                "values": values
            }
        }


# ============================================================================
# N8N WORKFLOW BUILDER
# ============================================================================

class N8nWorkflowBuilder:
    """Helper class for building n8n workflows programmatically."""
    
    def __init__(self):
        self.nodes = []
        self.connections = {}
        self.node_counter = 0
    
    def add_node(self, node_config: Dict, name: str = None) -> str:
        """Add a node to the workflow."""
        self.node_counter += 1
        
        if not name:
            name = f"Node_{self.node_counter}"
        
        # Auto-position if not specified
        if "position" not in node_config:
            node_config["position"] = [250 + (self.node_counter * 200), 300]
        
        node = {
            "name": name,
            **node_config
        }
        
        # Add typeVersion if not present
        if "typeVersion" not in node:
            node["typeVersion"] = 1
        
        self.nodes.append(node)
        return name
    
    def connect_nodes(self, from_node: str, to_node: str, 
                     output_index: int = 0, input_index: int = 0):
        """Connect two nodes."""
        if from_node not in self.connections:
            self.connections[from_node] = {"main": [[]]}
        
        # Ensure we have enough output arrays
        while len(self.connections[from_node]["main"]) <= output_index:
            self.connections[from_node]["main"].append([])
        
        self.connections[from_node]["main"][output_index].append({
            "node": to_node,
            "type": "main",
            "index": input_index
        })
    
    def build(self, name: str, tags: List[str] = None, settings: Dict = None) -> Dict:
        """Build the complete workflow."""
        return {
            "name": name,
            "nodes": self.nodes,
            "connections": self.connections,
            "active": False,
            "settings": settings or {"executionOrder": "v1"},
            "tags": tags or []
        }


# ============================================================================
# N8N API CLIENT
# ============================================================================

class N8nApiClient:
    """Client for n8n REST API."""
    
    def __init__(self, base_url: str = "http://localhost:5678", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["X-N8N-API-KEY"] = api_key
    
    def _request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make API request."""
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        
        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            json=data,
            params=params,
            timeout=30
        )
        
        response.raise_for_status()
        
        if response.content:
            return response.json()
        return {}
    
    def create_workflow(self, workflow: Dict) -> Dict:
        """Create a new workflow."""
        return self._request("POST", "workflows", data=workflow)
    
    def get_workflow(self, workflow_id: str) -> Dict:
        """Get workflow by ID."""
        return self._request("GET", f"workflows/{workflow_id}")
    
    def list_workflows(self, tags: List[str] = None, active: bool = None) -> List[Dict]:
        """List all workflows."""
        params = {}
        if tags:
            params["tags"] = ",".join(tags)
        if active is not None:
            params["active"] = str(active).lower()
        
        result = self._request("GET", "workflows", params=params)
        return result.get("data", [])
    
    def update_workflow(self, workflow_id: str, workflow: Dict) -> Dict:
        """Update an existing workflow."""
        return self._request("PUT", f"workflows/{workflow_id}", data=workflow)
    
    def delete_workflow(self, workflow_id: str) -> Dict:
        """Delete a workflow."""
        return self._request("DELETE", f"workflows/{workflow_id}")
    
    def activate_workflow(self, workflow_id: str) -> Dict:
        """Activate a workflow."""
        workflow = self.get_workflow(workflow_id)
        workflow["active"] = True
        return self.update_workflow(workflow_id, workflow)
    
    def deactivate_workflow(self, workflow_id: str) -> Dict:
        """Deactivate a workflow."""
        workflow = self.get_workflow(workflow_id)
        workflow["active"] = False
        return self.update_workflow(workflow_id, workflow)
    
    def execute_workflow(self, workflow_id: str, input_data: Dict = None) -> Dict:
        """Execute a workflow."""
        data = {"data": input_data} if input_data else {}
        return self._request("POST", f"workflows/{workflow_id}/execute", data=data)
    
    def get_execution(self, execution_id: str) -> Dict:
        """Get execution details."""
        return self._request("GET", f"executions/{execution_id}")
    
    def list_executions(self, workflow_id: str = None, limit: int = 10, 
                       status: str = None) -> List[Dict]:
        """List workflow executions."""
        params = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        
        result = self._request("GET", "executions", params=params)
        return result.get("data", [])
    
    def get_execution_data(self, execution_id: str) -> Dict:
        """Get detailed execution data including results."""
        return self._request("GET", f"executions/{execution_id}/data")


# ============================================================================
# N8N TOOLS CLASS
# ============================================================================

class N8nTools:
    """Tools for managing n8n workflows."""
    
    def __init__(self, agent, n8n_url: str = "http://localhost:5678", api_key: Optional[str] = None):
        self.agent = agent
        self.client = N8nApiClient(n8n_url, api_key)
        self.templates = N8nNodeTemplates()
        
        # Try to connect
        try:
            self.client.list_workflows()
            self.available = True
        except Exception as e:
            print(f"[Warning] n8n not available: {e}")
            self.available = False
    
    def create_n8n_workflow(self, workflow_name: str, nodes: List[Dict[str, Any]],
                           connections: Optional[Dict] = None, 
                           description: str = "", 
                           settings: Optional[Dict] = None) -> str:
        """
        Create a new n8n workflow from scratch.
        
        The LLM can design complete workflows by specifying nodes and connections.
        
        Args:
            workflow_name: Name for the workflow
            nodes: List of node configurations
            connections: Optional custom connections (auto-generated if not provided)
            description: Workflow description
            settings: Optional workflow settings
        
        Node structure:
            {
                "name": "Node name",
                "type": "n8n-nodes-base.nodeType",
                "parameters": {...},
                "position": [x, y]  # optional
            }
        
        Example nodes list:
            [
                {
                    "name": "Start",
                    "type": "n8n-nodes-base.manualTrigger",
                    "parameters": {}
                },
                {
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "method": "GET",
                        "url": "https://api.example.com/data"
                    }
                }
            ]
        
        Common node types:
        - n8n-nodes-base.manualTrigger: Manual trigger
        - n8n-nodes-base.scheduleTrigger: Time-based trigger
        - n8n-nodes-base.webhook: Webhook trigger
        - n8n-nodes-base.httpRequest: HTTP requests
        - n8n-nodes-base.code: JavaScript/Python code
        - n8n-nodes-base.if: Conditional logic
        - n8n-nodes-base.postgres: PostgreSQL operations
        - n8n-nodes-base.set: Data manipulation
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            # Build workflow
            builder = N8nWorkflowBuilder()
            
            # Add all nodes
            node_names = []
            for node_config in nodes:
                name = node_config.get("name", f"Node_{len(node_names)+1}")
                builder.add_node(node_config, name)
                node_names.append(name)
            
            # Auto-connect nodes if connections not provided
            if connections is None and len(node_names) > 1:
                for i in range(len(node_names) - 1):
                    builder.connect_nodes(node_names[i], node_names[i+1])
            elif connections:
                builder.connections = connections
            
            # Build workflow
            workflow = builder.build(workflow_name, settings=settings)
            
            # Create in n8n
            result = self.client.create_workflow(workflow)
            workflow_id = result.get("id")
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                workflow_name,
                "n8n_workflow",
                metadata={
                    "workflow_id": workflow_id,
                    "nodes": len(nodes),
                    "description": description
                }
            )
            
            return f"✓ Created n8n workflow: {workflow_name}\nID: {workflow_id}\nNodes: {len(nodes)}\n\nView at: {self.client.base_url}/workflow/{workflow_id}"
            
        except Exception as e:
            return f"[Error] Failed to create workflow: {str(e)}"
    
    def create_workflow_from_toolchain(self, toolchain_plan: List[Dict[str, Any]],
                                      workflow_name: str, auto_connect: bool = True) -> str:
        """
        Convert a Vera toolchain plan to an n8n workflow.
        
        This allows the LLM to create workflows from existing toolchain plans,
        enabling visual editing and scheduling in n8n.
        
        Args:
            toolchain_plan: Vera toolchain plan (list of tool steps)
            workflow_name: Name for the n8n workflow
            auto_connect: Automatically connect nodes in sequence
        
        Example toolchain:
            [
                {"tool": "web_search", "input": "Python tutorials"},
                {"tool": "deep_llm", "input": "Summarize: {prev}"}
            ]
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            from Vera.Toolchain.n8n_toolchain import N8nToolchainBridge
            
            bridge = N8nToolchainBridge(self.client.base_url, self.client.api_key)
            workflow_id = bridge.export_toolchain_to_n8n(toolchain_plan, workflow_name)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                workflow_name,
                "n8n_toolchain_workflow",
                metadata={
                    "workflow_id": workflow_id,
                    "steps": len(toolchain_plan),
                    "source": "toolchain"
                }
            )
            
            return f"✓ Created n8n workflow from toolchain: {workflow_name}\nID: {workflow_id}\nSteps: {len(toolchain_plan)}\n\nView at: {self.client.base_url}/workflow/{workflow_id}"
            
        except Exception as e:
            return f"[Error] Failed to convert toolchain: {str(e)}"
    
    def edit_n8n_workflow(self, workflow_id: str, operations: List[Dict[str, Any]]) -> str:
        """
        Edit an existing n8n workflow.
        
        Operations allow adding, removing, or updating nodes and connections.
        
        Args:
            workflow_id: ID of workflow to edit
            operations: List of edit operations
        
        Operation types:
            {
                "action": "add_node",
                "node": {...node config...}
            }
            
            {
                "action": "remove_node",
                "node_name": "Node to remove"
            }
            
            {
                "action": "update_node",
                "node_name": "Node name",
                "updates": {...parameter updates...}
            }
            
            {
                "action": "add_connection",
                "from": "Source node",
                "to": "Target node"
            }
            
            {
                "action": "remove_connection",
                "from": "Source node",
                "to": "Target node"
            }
        
        Example:
            edit_n8n_workflow(
                workflow_id="123",
                operations=[
                    {
                        "action": "add_node",
                        "node": {
                            "name": "New HTTP Request",
                            "type": "n8n-nodes-base.httpRequest",
                            "parameters": {"method": "POST", "url": "..."}
                        }
                    },
                    {
                        "action": "add_connection",
                        "from": "Start",
                        "to": "New HTTP Request"
                    }
                ]
            )
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            # Get current workflow
            workflow = self.client.get_workflow(workflow_id)
            nodes = workflow.get("nodes", [])
            connections = workflow.get("connections", {})
            
            changes = []
            
            for op in operations:
                action = op.get("action")
                
                if action == "add_node":
                    node_config = op.get("node")
                    # Auto-position
                    if "position" not in node_config:
                        node_config["position"] = [250 + (len(nodes) * 200), 300]
                    if "typeVersion" not in node_config:
                        node_config["typeVersion"] = 1
                    
                    nodes.append(node_config)
                    changes.append(f"Added node: {node_config.get('name')}")
                
                elif action == "remove_node":
                    node_name = op.get("node_name")
                    nodes = [n for n in nodes if n.get("name") != node_name]
                    # Remove connections involving this node
                    connections = {
                        k: v for k, v in connections.items() 
                        if k != node_name
                    }
                    changes.append(f"Removed node: {node_name}")
                
                elif action == "update_node":
                    node_name = op.get("node_name")
                    updates = op.get("updates", {})
                    for node in nodes:
                        if node.get("name") == node_name:
                            node["parameters"].update(updates)
                            changes.append(f"Updated node: {node_name}")
                            break
                
                elif action == "add_connection":
                    from_node = op.get("from")
                    to_node = op.get("to")
                    
                    if from_node not in connections:
                        connections[from_node] = {"main": [[]]}
                    
                    connections[from_node]["main"][0].append({
                        "node": to_node,
                        "type": "main",
                        "index": 0
                    })
                    changes.append(f"Connected: {from_node} → {to_node}")
                
                elif action == "remove_connection":
                    from_node = op.get("from")
                    to_node = op.get("to")
                    
                    if from_node in connections:
                        connections[from_node]["main"][0] = [
                            c for c in connections[from_node]["main"][0]
                            if c.get("node") != to_node
                        ]
                    changes.append(f"Disconnected: {from_node} → {to_node}")
            
            # Update workflow
            workflow["nodes"] = nodes
            workflow["connections"] = connections
            
            self.client.update_workflow(workflow_id, workflow)
            
            return f"✓ Workflow updated: {workflow_id}\nChanges made:\n" + "\n".join(f"  - {c}" for c in changes)
            
        except Exception as e:
            return f"[Error] Failed to edit workflow: {str(e)}"
    
    def query_n8n_workflows(self, workflow_id: Optional[str] = None,
                           tags: Optional[List[str]] = None,
                           active: Optional[bool] = None) -> str:
        """
        Query and list n8n workflows.
        
        Args:
            workflow_id: Get specific workflow by ID
            tags: Filter by tags
            active: Filter by active status
        
        Returns formatted list of workflows with details.
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            if workflow_id:
                # Get specific workflow
                workflow = self.client.get_workflow(workflow_id)
                
                output = [
                    f"Workflow: {workflow.get('name')}",
                    f"ID: {workflow.get('id')}",
                    f"Active: {'Yes' if workflow.get('active') else 'No'}",
                    f"Nodes: {len(workflow.get('nodes', []))}",
                    f"Tags: {', '.join(workflow.get('tags', []))}",
                    f"\nNodes in workflow:"
                ]
                
                for node in workflow.get("nodes", []):
                    output.append(f"  - {node.get('name')} ({node.get('type')})")
                
                return "\n".join(output)
            
            else:
                # List workflows
                workflows = self.client.list_workflows(tags=tags, active=active)
                
                if not workflows:
                    filter_desc = []
                    if tags:
                        filter_desc.append(f"tags={tags}")
                    if active is not None:
                        filter_desc.append(f"active={active}")
                    filter_str = " (" + ", ".join(filter_desc) + ")" if filter_desc else ""
                    return f"No workflows found{filter_str}"
                
                output = [f"n8n Workflows ({len(workflows)}):\n"]
                
                for wf in workflows:
                    status = "🟢" if wf.get("active") else "🔴"
                    output.append(f"{status} {wf.get('name')}")
                    output.append(f"   ID: {wf.get('id')}")
                    output.append(f"   Nodes: {len(wf.get('nodes', []))}")
                    output.append(f"   Tags: {', '.join(wf.get('tags', []))}")
                    output.append("")
                
                return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to query workflows: {str(e)}"
    
    def execute_n8n_workflow(self, workflow_id: str, 
                            input_data: Optional[Dict[str, Any]] = None,
                            wait_for_completion: bool = True) -> str:
        """
        Execute an n8n workflow.
        
        Args:
            workflow_id: ID of workflow to execute
            input_data: Optional input data for the workflow
            wait_for_completion: Wait for execution to finish
        
        Returns execution results or execution ID.
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            # Execute workflow
            result = self.client.execute_workflow(workflow_id, input_data)
            execution_id = result.get("data", {}).get("executionId")
            
            if not execution_id:
                return f"[Error] No execution ID returned"
            
            output = [f"✓ Workflow executed: {workflow_id}"]
            output.append(f"Execution ID: {execution_id}")
            
            if wait_for_completion:
                # Poll for completion
                max_attempts = 30
                for attempt in range(max_attempts):
                    time.sleep(2)
                    
                    exec_details = self.client.get_execution(execution_id)
                    status = exec_details.get("finished")
                    
                    if status is not None:
                        if status:
                            output.append("\nStatus: ✓ Completed successfully")
                            
                            # Get execution data
                            exec_data = self.client.get_execution_data(execution_id)
                            
                            # Show last node output
                            data = exec_data.get("data", {})
                            result_data = data.get("resultData", {})
                            last_node = result_data.get("lastNodeExecuted")
                            
                            if last_node:
                                output.append(f"\nLast node: {last_node}")
                                
                                # Get output from last node
                                run_data = result_data.get("runData", {})
                                if last_node in run_data:
                                    node_data = run_data[last_node][0].get("data", {})
                                    main_data = node_data.get("main", [[]])
                                    if main_data and main_data[0]:
                                        output.append(f"\nOutput:\n{json.dumps(main_data[0][0].get('json', {}), indent=2)[:500]}")
                        else:
                            output.append("\nStatus: ✗ Failed")
                            error = exec_details.get("data", {}).get("error")
                            if error:
                                output.append(f"Error: {error}")
                        
                        break
                else:
                    output.append("\nStatus: ⏳ Still running (timed out waiting)")
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                workflow_id,
                "n8n_execution",
                metadata={"execution_id": execution_id}
            )
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to execute workflow: {str(e)}"
    
    def control_n8n_workflow(self, workflow_id: str, action: str) -> str:
        """
        Control n8n workflow lifecycle.
        
        Actions:
        - activate: Activate the workflow (enable triggers)
        - deactivate: Deactivate the workflow
        - delete: Delete the workflow permanently
        - duplicate: Create a copy of the workflow
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            if action == "activate":
                self.client.activate_workflow(workflow_id)
                return f"✓ Workflow activated: {workflow_id}"
            
            elif action == "deactivate":
                self.client.deactivate_workflow(workflow_id)
                return f"✓ Workflow deactivated: {workflow_id}"
            
            elif action == "delete":
                self.client.delete_workflow(workflow_id)
                return f"✓ Workflow deleted: {workflow_id}"
            
            elif action == "duplicate":
                # Get workflow and create copy
                workflow = self.client.get_workflow(workflow_id)
                workflow["name"] = f"{workflow['name']} (Copy)"
                workflow["active"] = False
                
                result = self.client.create_workflow(workflow)
                new_id = result.get("id")
                
                return f"✓ Workflow duplicated: {workflow_id} → {new_id}"
            
            else:
                return f"[Error] Unknown action: {action}"
            
        except Exception as e:
            return f"[Error] Failed to {action} workflow: {str(e)}"
    
    def query_n8n_executions(self, workflow_id: Optional[str] = None,
                            limit: int = 10, status: Optional[str] = None) -> str:
        """
        Query workflow execution history.
        
        Args:
            workflow_id: Filter by workflow ID
            limit: Number of executions to return
            status: Filter by status (success, error, waiting, running)
        
        Shows recent execution history with status and timing.
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            executions = self.client.list_executions(workflow_id, limit, status)
            
            if not executions:
                return "No executions found"
            
            output = [f"Recent Executions ({len(executions)}):\n"]
            
            for exec in executions:
                exec_id = exec.get("id")
                wf_name = exec.get("workflowData", {}).get("name", "Unknown")
                finished = exec.get("finished")
                started = exec.get("startedAt")
                stopped = exec.get("stoppedAt")
                
                status_icon = "✓" if finished else "✗"
                
                output.append(f"{status_icon} {wf_name}")
                output.append(f"   Execution ID: {exec_id}")
                output.append(f"   Started: {started}")
                if stopped:
                    output.append(f"   Duration: {stopped}")
                output.append("")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to query executions: {str(e)}"
    
    def get_node_templates(self) -> str:
        """
        Get information about available n8n node templates.
        
        Shows common node types and their configurations for workflow building.
        """
        templates_info = """
Available n8n Node Templates:

🎯 Triggers:
  - manualTrigger: Manual workflow start
  - scheduleTrigger: Time-based scheduling
  - webhook: HTTP webhook endpoint

🌐 Actions:
  - httpRequest: HTTP requests (GET, POST, etc)
  - code: JavaScript/Python code execution
  - set: Data manipulation and transformation
  - if: Conditional logic branching

💾 Data:
  - postgres: PostgreSQL database operations
  - mysql: MySQL database operations
  - mongodb: MongoDB operations
  - redis: Redis cache operations

🔧 Utilities:
  - wait: Delay execution
  - merge: Combine data from multiple sources
  - split: Split data into multiple outputs
  - aggregate: Aggregate data

📨 Communication:
  - email: Send emails
  - slack: Slack messaging
  - discord: Discord webhooks
  - telegram: Telegram bot

Use create_n8n_workflow with these node types to build workflows.

Example node types:
  - n8n-nodes-base.manualTrigger
  - n8n-nodes-base.httpRequest
  - n8n-nodes-base.code
  - n8n-nodes-base.postgres
"""
        return templates_info
    
    def import_toolchain_from_n8n(self, workflow_id: str) -> str:
        """
        Import an n8n workflow and convert it to a Vera toolchain plan.
        
        This allows editing workflows visually in n8n and importing them
        back to Vera for execution.
        
        Args:
            workflow_id: n8n workflow ID to import
        
        Returns the imported toolchain plan.
        """
        if not self.available:
            return "[Error] n8n not available"
        
        try:
            from Vera.Toolchain.n8n_toolchain import N8nToolchainBridge
            
            bridge = N8nToolchainBridge(self.client.base_url, self.client.api_key)
            toolchain_plan = bridge.import_n8n_workflow_as_toolchain(workflow_id)
            
            output = [
                f"✓ Imported workflow: {workflow_id}",
                f"Steps: {len(toolchain_plan)}",
                "\nToolchain plan:"
            ]
            
            for i, step in enumerate(toolchain_plan, 1):
                output.append(f"\n{i}. {step.get('tool')}")
                output.append(f"   Input: {step.get('input', '')[:100]}")
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                json.dumps(toolchain_plan),
                "imported_toolchain",
                metadata={"workflow_id": workflow_id, "steps": len(toolchain_plan)}
            )
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to import workflow: {str(e)}"


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_n8n_tools(tool_list: List, agent, n8n_url: str = "http://localhost:5678", 
                 api_key: Optional[str] = None):
    """
    Add n8n workflow management tools to the tool list.
    
    Enables LLM to:
    - Create workflows from scratch or from toolchains
    - Edit existing workflows (add/remove nodes, connections)
    - Query workflows and execution history
    - Execute workflows with input data
    - Control workflow lifecycle (activate, deactivate, delete)
    - Import workflows back as toolchains
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_n8n_tools(tool_list, agent, n8n_url="http://localhost:5678")
        return tool_list
    
    Requires n8n running with API access.
    """
    
    n8n_tools = N8nTools(agent, n8n_url, api_key)
    
    if not n8n_tools.available:
        print("[Info] n8n tools not loaded - n8n not available or not accessible")
        return tool_list
    
    tool_list.extend([
        StructuredTool.from_function(
            func=n8n_tools.create_n8n_workflow,
            name="create_n8n_workflow",
            description=(
                "Create a new n8n workflow from scratch. "
                "Design workflows by specifying nodes and connections. "
                "Supports all n8n node types: triggers, HTTP, code, databases, etc."
            ),
            args_schema=N8nWorkflowCreateInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.create_workflow_from_toolchain,
            name="toolchain_to_n8n",
            description=(
                "Convert a Vera toolchain plan to an n8n workflow. "
                "Enables visual editing and scheduling in n8n. "
                "Toolchain steps become workflow nodes."
            ),
            args_schema=N8nWorkflowFromToolchainInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.edit_n8n_workflow,
            name="edit_n8n_workflow",
            description=(
                "Edit an existing n8n workflow. "
                "Add nodes, remove nodes, update parameters, manage connections. "
                "Supports complex workflow modifications."
            ),
            args_schema=N8nWorkflowEditInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.query_n8n_workflows,
            name="query_n8n_workflows",
            description=(
                "Query and list n8n workflows. "
                "Get specific workflow details or list all workflows. "
                "Filter by tags, active status."
            ),
            args_schema=N8nWorkflowQueryInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.execute_n8n_workflow,
            name="execute_n8n_workflow",
            description=(
                "Execute an n8n workflow with optional input data. "
                "Wait for completion and get results. "
                "Monitor execution status."
            ),
            args_schema=N8nWorkflowExecuteInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.control_n8n_workflow,
            name="control_n8n_workflow",
            description=(
                "Control workflow lifecycle: activate, deactivate, delete, duplicate. "
                "Manage workflow state and create copies."
            ),
            args_schema=N8nWorkflowControlInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.query_n8n_executions,
            name="query_n8n_executions",
            description=(
                "Query workflow execution history. "
                "See recent executions with status, timing, and results. "
                "Filter by workflow, status."
            ),
            args_schema=N8nExecutionQueryInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.import_toolchain_from_n8n,
            name="n8n_to_toolchain",
            description=(
                "Import an n8n workflow as a Vera toolchain plan. "
                "Edit workflows visually in n8n, then import for execution. "
                "Enables bidirectional workflow transfer."
            ),
            args_schema=N8nWorkflowQueryInput
        ),
        
        StructuredTool.from_function(
            func=n8n_tools.get_node_templates,
            name="list_n8n_node_types",
            description=(
                "Get information about available n8n node types and templates. "
                "Shows common nodes for triggers, actions, databases, communication."
            ),
        ),
    ])
    
    return tool_list


# Required dependencies (add to requirements.txt):
# requests>=2.31.0