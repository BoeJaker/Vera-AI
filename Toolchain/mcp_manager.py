"""
MCP Docker Server Management Tools
Enables LLM to create and manage MCP servers in Docker containers for various purposes
Add this section to your existing tools.py file
"""

import docker
import json
import time
import subprocess
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool, StructuredTool
from Vera.Toolchain.schemas import *

# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class MCPServerCreateInput(BaseModel):
    """Input schema for creating MCP servers."""
    server_type: Literal[
        "filesystem", "postgres", "github", "slack", "sqlite", 
        "memory", "puppeteer", "time", "fetch", "custom"
    ] = Field(..., description="Type of MCP server to create")
    server_name: str = Field(..., description="Unique name for this server instance")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Server-specific configuration (paths, credentials, etc.)"
    )
    auto_connect: bool = Field(
        default=True,
        description="Automatically connect to server after creation"
    )


class MCPServerControlInput(BaseModel):
    """Input schema for controlling MCP servers."""
    server_name: str = Field(..., description="Name of the MCP server")
    action: Literal["start", "stop", "restart", "remove"] = Field(
        ..., description="Action to perform"
    )


class MCPServerListInput(BaseModel):
    """Input schema for listing MCP servers."""
    status_filter: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all",
        description="Filter by server status"
    )


class MCPServerLogsInput(BaseModel):
    """Input schema for viewing server logs."""
    server_name: str = Field(..., description="Name of the MCP server")
    tail: int = Field(default=100, description="Number of log lines to show")


# ============================================================================
# MCP SERVER TEMPLATES
# ============================================================================

MCP_SERVER_TEMPLATES = {
    "filesystem": {
        "image": "mcp/filesystem:latest",
        "description": "File system access server - read/write files and directories",
        "required_config": ["allowed_directories"],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-filesystem
EXPOSE 3000
CMD ["mcp-server-filesystem"]
""",
        "env_mapping": {
            "allowed_directories": "ALLOWED_DIRECTORIES"
        }
    },
    
    "postgres": {
        "image": "mcp/postgres:latest",
        "description": "PostgreSQL database access server - query and manage databases",
        "required_config": ["connection_string"],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-postgres
EXPOSE 3000
CMD ["mcp-server-postgres"]
""",
        "env_mapping": {
            "connection_string": "DATABASE_URL"
        }
    },
    
    "github": {
        "image": "mcp/github:latest",
        "description": "GitHub API access server - manage repos, issues, PRs",
        "required_config": ["github_token"],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-github
EXPOSE 3000
CMD ["mcp-server-github"]
""",
        "env_mapping": {
            "github_token": "GITHUB_TOKEN",
            "github_owner": "GITHUB_OWNER"
        }
    },
    
    "slack": {
        "image": "mcp/slack:latest",
        "description": "Slack API access server - send messages, manage channels",
        "required_config": ["slack_token"],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-slack
EXPOSE 3000
CMD ["mcp-server-slack"]
""",
        "env_mapping": {
            "slack_token": "SLACK_TOKEN",
            "slack_team_id": "SLACK_TEAM_ID"
        }
    },
    
    "sqlite": {
        "image": "mcp/sqlite:latest",
        "description": "SQLite database access server - query local databases",
        "required_config": ["database_path"],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-sqlite
EXPOSE 3000
CMD ["mcp-server-sqlite"]
""",
        "env_mapping": {
            "database_path": "DATABASE_PATH"
        }
    },
    
    "memory": {
        "image": "mcp/memory:latest",
        "description": "In-memory knowledge graph server - store and query information",
        "required_config": [],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-memory
EXPOSE 3000
CMD ["mcp-server-memory"]
""",
        "env_mapping": {}
    },
    
    "puppeteer": {
        "image": "mcp/puppeteer:latest",
        "description": "Browser automation server - web scraping and testing",
        "required_config": [],
        "dockerfile": """
FROM node:18
WORKDIR /app
RUN apt-get update && apt-get install -y chromium
RUN npm install -g @modelcontextprotocol/server-puppeteer
EXPOSE 3000
CMD ["mcp-server-puppeteer"]
""",
        "env_mapping": {}
    },
    
    "time": {
        "image": "mcp/time:latest",
        "description": "Time and timezone utilities server",
        "required_config": [],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-time
EXPOSE 3000
CMD ["mcp-server-time"]
""",
        "env_mapping": {}
    },
    
    "fetch": {
        "image": "mcp/fetch:latest",
        "description": "HTTP fetch server - make web requests",
        "required_config": [],
        "dockerfile": """
FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-fetch
EXPOSE 3000
CMD ["mcp-server-fetch"]
""",
        "env_mapping": {}
    },
    
    "custom": {
        "image": None,
        "description": "Custom MCP server with user-provided configuration",
        "required_config": ["image", "command"],
        "dockerfile": None,
        "env_mapping": {}
    }
}


# ============================================================================
# MCP DOCKER MANAGER
# ============================================================================

class MCPDockerManager:
    """Manages MCP servers running in Docker containers."""
    
    def __init__(self, agent):
        self.agent = agent
        
        try:
            self.docker_client = docker.from_env()
            self.available = True
        except Exception as e:
            print(f"[Warning] Docker not available: {e}")
            self.docker_client = None
            self.available = False
        
        # Track created servers
        self.servers: Dict[str, Dict[str, Any]] = {}
        
        # Network for MCP servers
        self.network_name = "mcp-network"
        self._ensure_network()
    
    def _ensure_network(self):
        """Ensure MCP Docker network exists."""
        if not self.available:
            return
        
        try:
            self.docker_client.networks.get(self.network_name)
        except docker.errors.NotFound:
            self.docker_client.networks.create(
                self.network_name,
                driver="bridge"
            )
            print(f"[Created Docker network: {self.network_name}]")
    
    def _build_or_get_image(self, server_type: str, config: Dict[str, Any]) -> str:
        """Build or retrieve Docker image for MCP server."""
        template = MCP_SERVER_TEMPLATES.get(server_type)
        
        if not template:
            raise ValueError(f"Unknown server type: {server_type}")
        
        # Custom server type
        if server_type == "custom":
            return config.get("image")
        
        image_name = template["image"]
        
        # Check if image exists
        try:
            self.docker_client.images.get(image_name)
            return image_name
        except docker.errors.ImageNotFound:
            pass
        
        # Build image from Dockerfile
        if template["dockerfile"]:
            print(f"[Building MCP server image: {image_name}]")
            
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                dockerfile_path = os.path.join(tmpdir, "Dockerfile")
                with open(dockerfile_path, 'w') as f:
                    f.write(template["dockerfile"])
                
                image, logs = self.docker_client.images.build(
                    path=tmpdir,
                    tag=image_name,
                    rm=True
                )
                
                for log in logs:
                    if 'stream' in log:
                        print(log['stream'].strip())
            
            return image_name
        
        # Try to pull image
        print(f"[Pulling MCP server image: {image_name}]")
        self.docker_client.images.pull(image_name)
        return image_name
    
    def _prepare_environment(self, server_type: str, config: Dict[str, Any]) -> Dict[str, str]:
        """Prepare environment variables for container."""
        template = MCP_SERVER_TEMPLATES.get(server_type, {})
        env_mapping = template.get("env_mapping", {})
        
        env_vars = {}
        
        for config_key, env_key in env_mapping.items():
            if config_key in config:
                env_vars[env_key] = str(config[config_key])
        
        # Add any additional env vars from config
        if "environment" in config:
            env_vars.update(config["environment"])
        
        return env_vars
    
    def create_server(self, server_type: str, server_name: str, 
                     config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create and start an MCP server in Docker.
        
        Args:
            server_type: Type of MCP server
            server_name: Unique name for this instance
            config: Server-specific configuration
        
        Returns:
            Server information dictionary
        """
        if not self.available:
            raise RuntimeError("Docker not available")
        
        # Validate configuration
        template = MCP_SERVER_TEMPLATES.get(server_type)
        if not template:
            raise ValueError(f"Unknown server type: {server_type}")
        
        required = template.get("required_config", [])
        missing = [key for key in required if key not in config]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        
        # Check if server already exists
        container_name = f"mcp-{server_name}"
        try:
            existing = self.docker_client.containers.get(container_name)
            return {
                "status": "exists",
                "message": f"Server '{server_name}' already exists",
                "container_id": existing.id,
                "state": existing.status
            }
        except docker.errors.NotFound:
            pass
        
        # Build or get image
        image_name = self._build_or_get_image(server_type, config)
        
        # Prepare environment
        env_vars = self._prepare_environment(server_type, config)
        
        # Prepare volumes
        volumes = {}
        if "volumes" in config:
            for vol in config["volumes"]:
                host_path = vol.get("host")
                container_path = vol.get("container")
                if host_path and container_path:
                    volumes[host_path] = {
                        "bind": container_path,
                        "mode": vol.get("mode", "rw")
                    }
        
        # Create container
        ports = config.get("ports", {"3000/tcp": None})
        
        container = self.docker_client.containers.run(
            image=image_name,
            name=container_name,
            environment=env_vars,
            volumes=volumes,
            ports=ports,
            network=self.network_name,
            detach=True,
            restart_policy={"Name": "unless-stopped"}
        )
        
        # Wait for container to start
        time.sleep(2)
        container.reload()
        
        # Get port mapping
        port_bindings = container.attrs['NetworkSettings']['Ports']
        host_port = None
        if '3000/tcp' in port_bindings and port_bindings['3000/tcp']:
            host_port = port_bindings['3000/tcp'][0]['HostPort']
        
        # Store server info
        server_info = {
            "name": server_name,
            "type": server_type,
            "container_id": container.id,
            "container_name": container_name,
            "status": container.status,
            "host_port": host_port,
            "config": config,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.servers[server_name] = server_info
        
        # Store in agent memory
        self.agent.mem.add_session_memory(
            self.agent.sess.id,
            server_name,
            "mcp_server",
            metadata={
                "type": server_type,
                "container_id": container.id,
                "status": "created"
            }
        )
        
        return server_info
    
    def control_server(self, server_name: str, action: str) -> Dict[str, Any]:
        """
        Control an MCP server (start, stop, restart, remove).
        
        Args:
            server_name: Name of the server
            action: Action to perform
        
        Returns:
            Result dictionary
        """
        if not self.available:
            raise RuntimeError("Docker not available")
        
        container_name = f"mcp-{server_name}"
        
        try:
            container = self.docker_client.containers.get(container_name)
        except docker.errors.NotFound:
            return {
                "status": "error",
                "message": f"Server '{server_name}' not found"
            }
        
        try:
            if action == "start":
                container.start()
                message = f"Started server '{server_name}'"
            
            elif action == "stop":
                container.stop()
                message = f"Stopped server '{server_name}'"
            
            elif action == "restart":
                container.restart()
                message = f"Restarted server '{server_name}'"
            
            elif action == "remove":
                container.stop()
                container.remove()
                if server_name in self.servers:
                    del self.servers[server_name]
                message = f"Removed server '{server_name}'"
            
            else:
                return {
                    "status": "error",
                    "message": f"Unknown action: {action}"
                }
            
            # Update memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"{action}:{server_name}",
                "mcp_server_control",
                metadata={"action": action, "server": server_name}
            )
            
            return {
                "status": "success",
                "message": message,
                "server": server_name,
                "action": action
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to {action} server: {str(e)}"
            }
    
    def list_servers(self, status_filter: str = "all") -> List[Dict[str, Any]]:
        """
        List all MCP servers.
        
        Args:
            status_filter: Filter by status (running, stopped, all)
        
        Returns:
            List of server information dictionaries
        """
        if not self.available:
            return []
        
        servers = []
        
        # Get all containers with mcp- prefix
        containers = self.docker_client.containers.list(
            all=True,
            filters={"name": "mcp-"}
        )
        
        for container in containers:
            name = container.name.replace("mcp-", "")
            status = container.status
            
            # Apply filter
            if status_filter == "running" and status != "running":
                continue
            elif status_filter == "stopped" and status == "running":
                continue
            
            # Get server info
            server_info = self.servers.get(name, {})
            
            servers.append({
                "name": name,
                "type": server_info.get("type", "unknown"),
                "container_id": container.id[:12],
                "status": status,
                "created": container.attrs['Created'],
                "ports": container.ports
            })
        
        return servers
    
    def get_logs(self, server_name: str, tail: int = 100) -> str:
        """
        Get logs from an MCP server.
        
        Args:
            server_name: Name of the server
            tail: Number of log lines to retrieve
        
        Returns:
            Log output as string
        """
        if not self.available:
            return "[Error] Docker not available"
        
        container_name = f"mcp-{server_name}"
        
        try:
            container = self.docker_client.containers.get(container_name)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8')
        except docker.errors.NotFound:
            return f"[Error] Server '{server_name}' not found"
        except Exception as e:
            return f"[Error] Failed to get logs: {str(e)}"


# ============================================================================
# MCP DOCKER TOOLS CLASS
# ============================================================================

class MCPDockerTools:
    """Tools for managing MCP servers in Docker."""
    
    def __init__(self, agent):
        self.agent = agent
        self.manager = MCPDockerManager(agent)
    
    def create_mcp_server(self, server_type: str, server_name: str,
                         config: Dict[str, Any], auto_connect: bool = True) -> str:
        """
        Create a new MCP server in Docker for a specific purpose.
        
        Available server types:
        
        - filesystem: File system access (read/write files)
          Config: {allowed_directories: ["/path/to/dir"]}
        
        - postgres: PostgreSQL database access
          Config: {connection_string: "postgresql://user:pass@host/db"}
        
        - github: GitHub API access
          Config: {github_token: "ghp_...", github_owner: "username"}
        
        - slack: Slack API access
          Config: {slack_token: "xoxb-...", slack_team_id: "T..."}
        
        - sqlite: SQLite database access
          Config: {database_path: "/path/to/db.sqlite"}
        
        - memory: In-memory knowledge graph
          Config: {} (no config needed)
        
        - puppeteer: Browser automation and web scraping
          Config: {} (no config needed)
        
        - time: Time and timezone utilities
          Config: {} (no config needed)
        
        - fetch: HTTP fetch utilities
          Config: {} (no config needed)
        
        - custom: Custom MCP server
          Config: {image: "custom/image:tag", command: ["cmd"], environment: {...}}
        
        Examples:
            # Create filesystem server
            create_mcp_server(
                server_type="filesystem",
                server_name="project_files",
                config={"allowed_directories": ["/home/user/projects"]},
                auto_connect=True
            )
            
            # Create GitHub server
            create_mcp_server(
                server_type="github",
                server_name="my_github",
                config={"github_token": "ghp_xxx", "github_owner": "myusername"}
            )
        """
        if not self.manager.available:
            return "[Error] Docker not available. Please install Docker."
        
        try:
            result = self.manager.create_server(server_type, server_name, config)
            
            output = [
                f"✓ MCP Server Created: {server_name}",
                f"Type: {server_type}",
                f"Container ID: {result['container_id'][:12]}",
                f"Status: {result['status']}"
            ]
            
            if result.get('host_port'):
                output.append(f"Port: {result['host_port']}")
            
            # Auto-connect if requested
            if auto_connect and MCP_AVAILABLE:
                try:
                    # Get connection details
                    port = result.get('host_port', '3000')
                    
                    # Connect via existing MCP manager
                    # This assumes you have mcp_manager in your LLMTools
                    # You'll need to add connection logic here
                    output.append(f"\n[Auto-connecting to server...]")
                    output.append(f"Use mcp_call_tool to interact with this server")
                except Exception as e:
                    output.append(f"\n[Warning] Auto-connect failed: {e}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to create server: {str(e)}"
    
    def control_mcp_server(self, server_name: str, action: str) -> str:
        """
        Control an MCP server (start, stop, restart, remove).
        
        Actions:
        - start: Start a stopped server
        - stop: Stop a running server
        - restart: Restart a server
        - remove: Stop and remove a server permanently
        
        Example:
            control_mcp_server(server_name="project_files", action="restart")
        """
        if not self.manager.available:
            return "[Error] Docker not available"
        
        result = self.manager.control_server(server_name, action)
        
        if result["status"] == "success":
            return f"✓ {result['message']}"
        else:
            return f"[Error] {result['message']}"
    
    def list_mcp_servers(self, status_filter: str = "all") -> str:
        """
        List all MCP servers.
        
        Args:
            status_filter: Filter by status (running, stopped, all)
        
        Returns:
            Formatted list of servers
        """
        if not self.manager.available:
            return "[Error] Docker not available"
        
        servers = self.manager.list_servers(status_filter)
        
        if not servers:
            return f"No MCP servers found (filter: {status_filter})"
        
        output = [f"MCP Servers ({len(servers)}):\n"]
        
        for server in servers:
            status_icon = "🟢" if server["status"] == "running" else "🔴"
            output.append(f"{status_icon} {server['name']}")
            output.append(f"   Type: {server['type']}")
            output.append(f"   Status: {server['status']}")
            output.append(f"   Container: {server['container_id']}")
            if server.get('ports'):
                output.append(f"   Ports: {server['ports']}")
            output.append("")
        
        return "\n".join(output)
    
    def get_mcp_server_logs(self, server_name: str, tail: int = 100) -> str:
        """
        Get logs from an MCP server.
        
        Useful for debugging server issues or monitoring activity.
        
        Args:
            server_name: Name of the server
            tail: Number of recent log lines to show (default: 100)
        """
        if not self.manager.available:
            return "[Error] Docker not available"
        
        logs = self.manager.get_logs(server_name, tail)
        return f"Logs for {server_name} (last {tail} lines):\n\n{logs}"
    
    def get_server_templates(self) -> str:
        """
        Get information about available MCP server templates.
        
        Shows what server types are available and what configuration
        they require.
        """
        output = ["Available MCP Server Templates:\n"]
        
        for server_type, template in MCP_SERVER_TEMPLATES.items():
            output.append(f"📦 {server_type}")
            output.append(f"   {template['description']}")
            
            required = template.get('required_config', [])
            if required:
                output.append(f"   Required config: {', '.join(required)}")
            else:
                output.append("   No configuration required")
            
            output.append("")
        
        return "\n".join(output)


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_mcp_docker_tools(tool_list: List, agent):
    """
    Add MCP Docker management tools to the tool list.
    
    Enables LLM to create and manage MCP servers in Docker containers
    for various purposes (file access, databases, APIs, etc.)
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_mcp_docker_tools(tool_list, agent)
        return tool_list
    """
    
    mcp_docker = MCPDockerTools(agent)
    
    if not mcp_docker.manager.available:
        print("[Info] MCP Docker tools not loaded - Docker not available")
        return tool_list
    
    tool_list.extend([
        StructuredTool.from_function(
            func=mcp_docker.create_mcp_server,
            name="create_mcp_server",
            description=(
                "Create a new MCP server in Docker for specific purposes. "
                "Available types: filesystem, postgres, github, slack, sqlite, "
                "memory, puppeteer, time, fetch, custom. "
                "Each server provides specialized tools for different tasks."
            ),
            args_schema=MCPServerCreateInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.control_mcp_server,
            name="control_mcp_server",
            description=(
                "Control MCP servers: start, stop, restart, or remove. "
                "Use to manage server lifecycle and resources."
            ),
            args_schema=MCPServerControlInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.list_mcp_servers,
            name="list_mcp_servers",
            description=(
                "List all MCP servers with their status and details. "
                "Filter by running, stopped, or all servers."
            ),
            args_schema=MCPServerListInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.get_mcp_server_logs,
            name="get_mcp_server_logs",
            description=(
                "View logs from an MCP server for debugging and monitoring. "
                "Shows recent activity and error messages."
            ),
            args_schema=MCPServerLogsInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.get_server_templates,
            name="list_mcp_templates",
            description=(
                "Get information about available MCP server types and their "
                "required configuration. Use before creating servers."
            ),
        ),
    ])
    
    return tool_list


# Required dependencies (add to requirements.txt):
# docker>=7.0.0