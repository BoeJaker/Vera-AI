#!/usr/bin/env python3
"""
n8n Integration for Vera Toolchain
Converts toolchain plans to n8n workflows and vice versa
"""

import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import os


class N8nToolchainBridge:
    """Bridge between Vera toolchains and n8n workflows"""
    
    def __init__(self, n8n_url: str = "http://localhost:5678", api_key: Optional[str] = None):
        self.n8n_url = n8n_url.rstrip('/')
        self.api_key = api_key or os.getenv("N8N_API_KEY")
        self.headers = {
            "Content-Type": "application/json",
            "X-N8N-API-KEY": self.api_key
        } if self.api_key else {"Content-Type": "application/json"}
    
    def toolchain_to_n8n_workflow(self, tool_plan: List[Dict], workflow_name: str = None) -> Dict:
        """
        Convert a Vera toolchain plan to an n8n workflow format
        
        Args:
            tool_plan: List of tool steps from ToolChainPlanner
            workflow_name: Name for the n8n workflow
            
        Returns:
            n8n workflow JSON
        """
        if not workflow_name:
            workflow_name = f"Vera_Toolchain_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        nodes = []
        connections = {}
        
        # Start node (trigger)
        nodes.append({
            "parameters": {},
            "name": "Manual Trigger",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [250, 300]
        })
        
        # Convert each tool step to an n8n node
        for idx, step in enumerate(tool_plan):
            tool_name = step.get("tool")
            tool_input = step.get("input", "")
            
            # Create HTTP Request node for each tool
            # (You could map to specific n8n nodes based on tool type)
            node = {
                "parameters": {
                    "method": "POST",
                    "url": f"http://localhost:8000/tools/{tool_name}",  # Your tool endpoint
                    "options": {},
                    "bodyParametersJson": json.dumps({
                        "input": tool_input,
                        "step_number": idx + 1
                    })
                },
                "name": f"Step_{idx + 1}_{tool_name}",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [250 + (idx * 200), 300],
                "notes": f"Tool: {tool_name}\nInput: {tool_input}"
            }
            
            # Handle {prev} and {step_X} references in input
            if "{prev}" in tool_input or "{step_" in tool_input:
                # Use n8n expressions to reference previous node output
                node["parameters"]["bodyParametersJson"] = self._convert_placeholders_to_n8n_expressions(
                    tool_input, idx
                )
            
            nodes.append(node)
            
            # Create connections
            if idx == 0:
                # Connect from trigger
                connections["Manual Trigger"] = {
                    "main": [[{"node": node["name"], "type": "main", "index": 0}]]
                }
            else:
                # Connect from previous node
                prev_node_name = nodes[idx]["name"]
                connections[prev_node_name] = {
                    "main": [[{"node": node["name"], "type": "main", "index": 0}]]
                }
        
        # Create the workflow structure
        workflow = {
            "name": workflow_name,
            "nodes": nodes,
            "connections": connections,
            "active": False,
            "settings": {
                "executionOrder": "v1"
            },
            "tags": ["vera-toolchain", "auto-generated"]
        }
        
        return workflow
    
    def _convert_placeholders_to_n8n_expressions(self, input_str: str, current_step: int) -> str:
        """Convert {prev} and {step_X} to n8n expression syntax"""
        # n8n uses {{ $json.output }} syntax to reference previous node output
        result = input_str
        
        # Replace {prev} with reference to previous step
        if "{prev}" in result:
            prev_node = f"Step_{current_step}"
            result = result.replace("{prev}", f"{{{{ $node['{prev_node}'].json['output'] }}}}")
        
        # Replace {step_X} with reference to specific step
        import re
        step_refs = re.findall(r'\{step_(\d+)\}', result)
        for step_num in step_refs:
            node_name = f"Step_{step_num}_*"  # You'd need to track actual names
            result = result.replace(
                f"{{step_{step_num}}}", 
                f"{{{{ $node['{node_name}'].json['output'] }}}}"
            )
        
        return result
    
    def n8n_workflow_to_toolchain(self, workflow: Dict) -> List[Dict]:
        """
        Convert an n8n workflow back to Vera toolchain format
        
        Args:
            workflow: n8n workflow JSON
            
        Returns:
            List of tool steps compatible with ToolChainPlanner
        """
        tool_plan = []
        nodes = workflow.get("nodes", [])
        
        # Filter out trigger nodes and convert HTTP request nodes
        for node in nodes:
            if node.get("type") == "n8n-nodes-base.httpRequest":
                # Extract tool name and input from node
                tool_name = self._extract_tool_name_from_node(node)
                tool_input = self._extract_tool_input_from_node(node)
                
                tool_plan.append({
                    "tool": tool_name,
                    "input": tool_input
                })
        
        return tool_plan
    
    def _extract_tool_name_from_node(self, node: Dict) -> str:
        """Extract tool name from n8n node"""
        # Parse from URL or node name
        name = node.get("name", "")
        if "Step_" in name:
            parts = name.split("_")
            return parts[-1] if len(parts) > 2 else name
        return name
    
    def _extract_tool_input_from_node(self, node: Dict) -> str:
        """Extract tool input from n8n node parameters"""
        params = node.get("parameters", {})
        body_json = params.get("bodyParametersJson", "{}")
        
        if isinstance(body_json, str):
            try:
                body = json.loads(body_json)
                return body.get("input", "")
            except json.JSONDecodeError:
                return body_json
        return str(body_json)
    
    def create_workflow(self, workflow: Dict) -> Dict:
        """Create a new workflow in n8n"""
        response = requests.post(
            f"{self.n8n_url}/api/v1/workflows",
            headers=self.headers,
            json=workflow
        )
        response.raise_for_status()
        return response.json()
    
    def execute_workflow(self, workflow_id: str, input_data: Dict = None) -> Dict:
        """Execute a workflow in n8n"""
        endpoint = f"{self.n8n_url}/api/v1/workflows/{workflow_id}/execute"
        
        payload = {"data": input_data} if input_data else {}
        
        response = requests.post(
            endpoint,
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_workflow(self, workflow_id: str) -> Dict:
        """Fetch a workflow from n8n"""
        response = requests.get(
            f"{self.n8n_url}/api/v1/workflows/{workflow_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_workflows(self, tags: List[str] = None) -> List[Dict]:
        """List workflows from n8n, optionally filtered by tags"""
        response = requests.get(
            f"{self.n8n_url}/api/v1/workflows",
            headers=self.headers
        )
        response.raise_for_status()
        
        workflows = response.json().get("data", [])
        
        # Filter by tags if specified
        if tags:
            workflows = [
                w for w in workflows 
                if any(tag in w.get("tags", []) for tag in tags)
            ]
        
        return workflows
    
    def update_workflow(self, workflow_id: str, workflow: Dict) -> Dict:
        """Update an existing workflow in n8n"""
        response = requests.put(
            f"{self.n8n_url}/api/v1/workflows/{workflow_id}",
            headers=self.headers,
            json=workflow
        )
        response.raise_for_status()
        return response.json()
    
    def export_toolchain_to_n8n(self, tool_plan: List[Dict], workflow_name: str = None) -> str:
        """
        Export a toolchain to n8n and return the workflow ID
        
        Args:
            tool_plan: Vera toolchain plan
            workflow_name: Optional name for the workflow
            
        Returns:
            workflow_id: ID of created n8n workflow
        """
        workflow = self.toolchain_to_n8n_workflow(tool_plan, workflow_name)
        result = self.create_workflow(workflow)
        return result.get("id")
    
    def import_n8n_workflow_as_toolchain(self, workflow_id: str) -> List[Dict]:
        """
        Import an n8n workflow and convert to toolchain format
        
        Args:
            workflow_id: n8n workflow ID
            
        Returns:
            tool_plan: Vera toolchain plan
        """
        workflow = self.get_workflow(workflow_id)
        return self.n8n_workflow_to_toolchain(workflow)


class N8nToolchainExecutor:
    """Execute toolchains using n8n as the execution engine"""
    
    def __init__(self, bridge: N8nToolchainBridge):
        self.bridge = bridge
    
    def execute_via_n8n(self, tool_plan: List[Dict], save_workflow: bool = True) -> Dict:
        """
        Execute a toolchain via n8n
        
        Args:
            tool_plan: Vera toolchain plan
            save_workflow: Whether to save the workflow permanently
            
        Returns:
            Execution results
        """
        # Convert to n8n workflow
        workflow_name = f"Temp_Execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        workflow = self.bridge.toolchain_to_n8n_workflow(tool_plan, workflow_name)
        
        # Create workflow
        created = self.bridge.create_workflow(workflow)
        workflow_id = created.get("id")
        
        try:
            # Execute it
            result = self.bridge.execute_workflow(workflow_id)
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "execution_data": result,
                "workflow_name": workflow_name
            }
        finally:
            # Clean up if not saving
            if not save_workflow and workflow_id:
                try:
                    requests.delete(
                        f"{self.bridge.n8n_url}/api/v1/workflows/{workflow_id}",
                        headers=self.bridge.headers
                    )
                except:
                    pass
    
    def execute_saved_workflow(self, workflow_id: str, input_data: Dict = None) -> Dict:
        """Execute a previously saved n8n workflow"""
        return self.bridge.execute_workflow(workflow_id, input_data)


# Example usage and integration points
if __name__ == "__main__":
    # Initialize the bridge
    bridge = N8nToolchainBridge(
        n8n_url="http://localhost:5678",
        api_key=os.getenv("N8N_API_KEY")
    )
    
    # Example: Convert a Vera toolchain to n8n
    sample_toolchain = [
        {"tool": "web_search", "input": "Python tutorials"},
        {"tool": "summarize_text", "input": "{prev}"},
        {"tool": "save_to_file", "input": "{step_2}"}
    ]
    
    # Export to n8n
    workflow_id = bridge.export_toolchain_to_n8n(
        sample_toolchain, 
        "Python_Tutorial_Search"
    )
    print(f"Created n8n workflow: {workflow_id}")
    
    # Later, import it back
    imported_plan = bridge.import_n8n_workflow_as_toolchain(workflow_id)
    print(f"Imported toolchain: {json.dumps(imported_plan, indent=2)}")