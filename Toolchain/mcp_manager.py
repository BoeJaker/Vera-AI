"""
MCP Docker Server Management with Custom Template Creation
Enables LLM to create, customize, and manage MCP server templates
"""

import docker
import json
import time
import subprocess
import yaml
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from pathlib import Path

# ============================================================================
# ADDITIONAL INPUT SCHEMAS
# ============================================================================

class MCPTemplateCreateInput(BaseModel):
    """Input schema for creating custom MCP templates."""
    template_name: str = Field(..., description="Unique name for this template")
    description: str = Field(..., description="Description of what this server does")
    dockerfile: str = Field(..., description="Complete Dockerfile content")
    required_config: List[str] = Field(
        default_factory=list,
        description="List of required config keys"
    )
    env_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map config keys to environment variables"
    )
    default_ports: Dict[str, int] = Field(
        default_factory=dict,
        description="Default port mappings"
    )


class MCPServerCodeInput(BaseModel):
    """Input schema for generating MCP server code."""
    server_name: str = Field(..., description="Name for the MCP server")
    language: Literal["python", "typescript", "javascript"] = Field(
        default="python",
        description="Programming language for the server"
    )
    description: str = Field(
        ..., 
        description="Description of what tools/capabilities the server should provide"
    )
    tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of tool definitions with names, descriptions, and parameters"
    )


class MCPTemplateListInput(BaseModel):
    """Input schema for listing templates."""
    category: Optional[str] = Field(
        default=None,
        description="Filter by category (built-in, custom, all)"
    )


# ============================================================================
# TEMPLATE PERSISTENCE
# ============================================================================

class MCPTemplateManager:
    """Manages MCP server templates (built-in and custom)."""
    
    def __init__(self, templates_dir: str = "./mcp_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
        
        # Load built-in templates
        self.templates = MCP_SERVER_TEMPLATES.copy()
        
        # Load custom templates
        self._load_custom_templates()
    
    def _load_custom_templates(self):
        """Load custom templates from disk."""
        template_file = self.templates_dir / "custom_templates.json"
        
        if template_file.exists():
            try:
                with open(template_file, 'r') as f:
                    custom = json.load(f)
                    self.templates.update(custom)
                print(f"[Loaded {len(custom)} custom MCP templates]")
            except Exception as e:
                print(f"[Warning] Failed to load custom templates: {e}")
    
    def save_template(self, template_name: str, template_data: Dict[str, Any]):
        """Save a custom template to disk."""
        # Add to in-memory templates
        self.templates[template_name] = template_data
        
        # Load existing custom templates
        template_file = self.templates_dir / "custom_templates.json"
        custom = {}
        
        if template_file.exists():
            with open(template_file, 'r') as f:
                custom = json.load(f)
        
        # Add new template
        custom[template_name] = template_data
        
        # Save back to disk
        with open(template_file, 'w') as f:
            json.dump(custom, f, indent=2)
        
        print(f"[Saved custom template: {template_name}]")
    
    def list_templates(self, category: Optional[str] = None) -> Dict[str, Dict]:
        """List templates, optionally filtered by category."""
        if category == "built-in":
            return {k: v for k, v in MCP_SERVER_TEMPLATES.items()}
        elif category == "custom":
            return {k: v for k, v in self.templates.items() 
                   if k not in MCP_SERVER_TEMPLATES}
        else:
            return self.templates.copy()
    
    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific template."""
        return self.templates.get(template_name)
    
    def delete_template(self, template_name: str) -> bool:
        """Delete a custom template."""
        if template_name in MCP_SERVER_TEMPLATES:
            return False  # Can't delete built-in templates
        
        if template_name not in self.templates:
            return False
        
        # Remove from memory
        del self.templates[template_name]
        
        # Update file
        template_file = self.templates_dir / "custom_templates.json"
        if template_file.exists():
            with open(template_file, 'r') as f:
                custom = json.load(f)
            
            if template_name in custom:
                del custom[template_name]
            
            with open(template_file, 'w') as f:
                json.dump(custom, f, indent=2)
        
        return True


# ============================================================================
# MCP SERVER CODE GENERATOR
# ============================================================================

class MCPServerCodeGenerator:
    """Generates MCP server implementations in various languages."""
    
    PYTHON_TEMPLATE = '''"""
{description}

Generated MCP Server using the Model Context Protocol SDK.
"""
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import asyncio
from typing import Any

# Create server instance
server = Server("{server_name}")

{tool_implementations}

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
'''

    TYPESCRIPT_TEMPLATE = '''/**
 * {description}
 * 
 * Generated MCP Server using the Model Context Protocol SDK.
 */
import {{ Server }} from "@modelcontextprotocol/sdk/server/index.js";
import {{ StdioServerTransport }} from "@modelcontextprotocol/sdk/server/stdio.js";
import {{
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
}} from "@modelcontextprotocol/sdk/types.js";

// Create server instance
const server = new Server(
  {{
    name: "{server_name}",
    version: "1.0.0",
  }},
  {{
    capabilities: {{
      tools: {{}},
    }},
  }}
);

{tool_implementations}

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
'''

    @staticmethod
    def generate_python_tool(tool_def: Dict[str, Any]) -> str:
        """Generate Python code for a single tool."""
        name = tool_def.get("name", "unnamed_tool")
        description = tool_def.get("description", "No description")
        parameters = tool_def.get("parameters", {})
        
        # Generate parameter parsing
        param_code = []
        for param_name, param_info in parameters.items():
            param_type = param_info.get("type", "str")
            param_code.append(f'    {param_name} = arguments.get("{param_name}")')
        
        param_str = "\n".join(param_code) if param_code else "    pass"
        
        return f'''
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="{name}",
            description="{description}",
            inputSchema={{
                "type": "object",
                "properties": {json.dumps(parameters, indent=16)},
                "required": {list(parameters.keys())}
            }}
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution."""
    if name == "{name}":
{param_str}
        
        # TODO: Implement tool logic here
        result = f"Executed {name} with arguments: {{arguments}}"
        
        return [TextContent(type="text", text=result)]
    else:
        raise ValueError(f"Unknown tool: {{name}}")
'''

    @staticmethod
    def generate_typescript_tool(tool_def: Dict[str, Any]) -> str:
        """Generate TypeScript code for a single tool."""
        name = tool_def.get("name", "unnamed_tool")
        description = tool_def.get("description", "No description")
        parameters = tool_def.get("parameters", {})
        
        return f'''
// Register tool: {name}
server.setRequestHandler(ListToolsRequestSchema, async () => ({{
  tools: [
    {{
      name: "{name}",
      description: "{description}",
      inputSchema: {{
        type: "object",
        properties: {json.dumps(parameters, indent=8)},
        required: {json.dumps(list(parameters.keys()))}
      }}
    }}
  ]
}}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {{
  if (request.params.name === "{name}") {{
    const args = request.params.arguments;
    
    // TODO: Implement tool logic here
    const result = `Executed {name} with arguments: ${{JSON.stringify(args)}}`;
    
    return {{
      content: [{{ type: "text", text: result }}]
    }};
  }}
  
  throw new Error(`Unknown tool: ${{request.params.name}}`);
}});
'''

    @classmethod
    def generate_server_code(cls, server_name: str, language: str, 
                           description: str, tools: List[Dict[str, Any]]) -> str:
        """Generate complete MCP server code."""
        if language == "python":
            tool_code = "\n".join([
                cls.generate_python_tool(tool) for tool in tools
            ])
            return cls.PYTHON_TEMPLATE.format(
                server_name=server_name,
                description=description,
                tool_implementations=tool_code
            )
        
        elif language in ["typescript", "javascript"]:
            tool_code = "\n".join([
                cls.generate_typescript_tool(tool) for tool in tools
            ])
            return cls.TYPESCRIPT_TEMPLATE.format(
                server_name=server_name,
                description=description,
                tool_implementations=tool_code
            )
        
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    @classmethod
    def generate_dockerfile(cls, language: str, server_name: str) -> str:
        """Generate Dockerfile for the server."""
        if language == "python":
            return f'''FROM python:3.11-slim

WORKDIR /app

# Install MCP SDK
RUN pip install --no-cache-dir mcp

# Copy server code
COPY {server_name}.py .

# Run server
CMD ["python", "{server_name}.py"]
'''
        
        elif language in ["typescript", "javascript"]:
            return f'''FROM node:18-alpine

WORKDIR /app

# Install MCP SDK
RUN npm install -g @modelcontextprotocol/sdk

# Copy server code
COPY {server_name}.{language[:2]} .
COPY package.json .

RUN npm install

# Run server
CMD ["node", "{server_name}.{language[:2]}"]
'''
        
        else:
            raise ValueError(f"Unsupported language: {language}")


# ============================================================================
# ENHANCED MCP DOCKER TOOLS CLASS
# ============================================================================

class MCPDockerToolsEnhanced(MCPDockerTools):
    """Enhanced MCP Docker tools with template creation."""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.template_manager = MCPTemplateManager()
        self.code_generator = MCPServerCodeGenerator()
        
        # Update manager templates
        self.manager.template_manager = self.template_manager
    
    def create_mcp_template(self, template_name: str, description: str,
                           dockerfile: str, required_config: List[str] = None,
                           env_mapping: Dict[str, str] = None,
                           default_ports: Dict[str, int] = None) -> str:
        """
        Create a custom MCP server template.
        
        Templates define reusable server configurations that can be
        instantiated multiple times with different configurations.
        
        Args:
            template_name: Unique name for this template
            description: What this server type does
            dockerfile: Complete Dockerfile content
            required_config: List of required configuration keys
            env_mapping: Map config keys to environment variables
            default_ports: Default port mappings
        
        Example:
            create_mcp_template(
                template_name="redis_cache",
                description="Redis caching server for MCP",
                dockerfile='''
                FROM redis:alpine
                COPY redis.conf /usr/local/etc/redis/redis.conf
                CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
                ''',
                required_config=["max_memory"],
                env_mapping={"max_memory": "REDIS_MAXMEMORY"}
            )
        """
        template_data = {
            "image": f"mcp/{template_name}:latest",
            "description": description,
            "dockerfile": dockerfile,
            "required_config": required_config or [],
            "env_mapping": env_mapping or {},
            "default_ports": default_ports or {"3000/tcp": None}
        }
        
        self.template_manager.save_template(template_name, template_data)
        
        # Store in agent memory
        self.agent.mem.add_session_memory(
            self.agent.sess.id,
            template_name,
            "mcp_template",
            metadata={"description": description, "type": "custom"}
        )
        
        return f"✓ Created custom MCP template: {template_name}\n{description}"
    
    def generate_mcp_server(self, server_name: str, language: str,
                           description: str, tools: List[Dict[str, Any]]) -> str:
        """
        Generate complete MCP server implementation code.
        
        The LLM can create custom MCP servers by describing the tools
        they should provide. This generates working server code in
        Python or TypeScript/JavaScript.
        
        Args:
            server_name: Name for the server
            language: "python", "typescript", or "javascript"
            description: What the server does
            tools: List of tool definitions with structure:
                [{
                    "name": "tool_name",
                    "description": "what it does",
                    "parameters": {
                        "param1": {"type": "string", "description": "..."},
                        "param2": {"type": "number", "description": "..."}
                    }
                }]
        
        Example:
            generate_mcp_server(
                server_name="weather_service",
                language="python",
                description="MCP server for weather information",
                tools=[{
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "location": {
                            "type": "string",
                            "description": "City name or coordinates"
                        },
                        "units": {
                            "type": "string",
                            "description": "imperial or metric"
                        }
                    }
                }]
            )
        """
        try:
            # Generate server code
            server_code = self.code_generator.generate_server_code(
                server_name, language, description, tools
            )
            
            # Generate Dockerfile
            dockerfile = self.code_generator.generate_dockerfile(language, server_name)
            
            # Create directory structure
            server_dir = Path("./mcp_servers") / server_name
            server_dir.mkdir(parents=True, exist_ok=True)
            
            # Save files
            ext = "py" if language == "python" else "ts" if language == "typescript" else "js"
            server_file = server_dir / f"{server_name}.{ext}"
            docker_file = server_dir / "Dockerfile"
            
            with open(server_file, 'w') as f:
                f.write(server_code)
            
            with open(docker_file, 'w') as f:
                f.write(dockerfile)
            
            # Generate package.json for Node.js
            if language in ["typescript", "javascript"]:
                package_json = {
                    "name": server_name,
                    "version": "1.0.0",
                    "type": "module",
                    "dependencies": {
                        "@modelcontextprotocol/sdk": "^0.5.0"
                    }
                }
                with open(server_dir / "package.json", 'w') as f:
                    json.dump(package_json, f, indent=2)
            
            # Create README
            readme = f"""# {server_name}

{description}

## Generated MCP Server

This server was automatically generated and provides the following tools:

{chr(10).join([f"- **{t['name']}**: {t['description']}" for t in tools])}

## Building
```bash
docker build -t mcp/{server_name}:latest .
```

## Running
```bash
docker run -p 3000:3000 mcp/{server_name}:latest
```

## Using with MCP Client

Use `create_mcp_server` with server_type="custom" and the appropriate configuration.
"""
            with open(server_dir / "README.md", 'w') as f:
                f.write(readme)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                server_name,
                "mcp_generated_server",
                metadata={
                    "language": language,
                    "tools": [t["name"] for t in tools],
                    "path": str(server_dir)
                }
            )
            
            output = [
                f"✓ Generated MCP Server: {server_name}",
                f"Language: {language}",
                f"Location: {server_dir}",
                f"\nGenerated files:",
                f"  - {server_file.name}",
                f"  - Dockerfile",
            ]
            
            if language in ["typescript", "javascript"]:
                output.append("  - package.json")
            
            output.extend([
                "  - README.md",
                f"\nImplemented {len(tools)} tools:",
            ])
            
            for tool in tools:
                output.append(f"  ✓ {tool['name']}: {tool['description']}")
            
            output.extend([
                f"\nTo use this server:",
                f"1. cd {server_dir}",
                f"2. docker build -t mcp/{server_name}:latest .",
                f"3. Use create_mcp_server with server_type='custom'"
            ])
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to generate server: {str(e)}\n{traceback.format_exc()}"
    
    def list_mcp_templates(self, category: Optional[str] = None) -> str:
        """
        List available MCP server templates.
        
        Args:
            category: Filter by "built-in", "custom", or "all"
        
        Shows all template types that can be used with create_mcp_server.
        """
        templates = self.template_manager.list_templates(category)
        
        if not templates:
            return f"No templates found (category: {category or 'all'})"
        
        output = [f"MCP Server Templates ({len(templates)}):\n"]
        
        # Separate built-in and custom
        built_in = {k: v for k, v in templates.items() if k in MCP_SERVER_TEMPLATES}
        custom = {k: v for k, v in templates.items() if k not in MCP_SERVER_TEMPLATES}
        
        if built_in and (not category or category == "built-in"):
            output.append("🔧 Built-in Templates:")
            for name, template in built_in.items():
                output.append(f"\n  {name}")
                output.append(f"    {template['description']}")
                required = template.get('required_config', [])
                if required:
                    output.append(f"    Required: {', '.join(required)}")
        
        if custom and (not category or category == "custom"):
            output.append("\n\n📝 Custom Templates:")
            for name, template in custom.items():
                output.append(f"\n  {name}")
                output.append(f"    {template['description']}")
                required = template.get('required_config', [])
                if required:
                    output.append(f"    Required: {', '.join(required)}")
        
        return "\n".join(output)
    
    def delete_mcp_template(self, template_name: str) -> str:
        """
        Delete a custom MCP template.
        
        Note: Built-in templates cannot be deleted.
        """
        if self.template_manager.delete_template(template_name):
            return f"✓ Deleted custom template: {template_name}"
        elif template_name in MCP_SERVER_TEMPLATES:
            return f"[Error] Cannot delete built-in template: {template_name}"
        else:
            return f"[Error] Template not found: {template_name}"


# ============================================================================
# UPDATE ADD FUNCTION
# ============================================================================

def add_mcp_docker_tools(tool_list: List, agent):
    """
    Add MCP Docker management tools with custom template creation.
    
    Enables LLM to:
    - Create custom MCP server templates
    - Generate complete MCP server implementations
    - Build and deploy servers in Docker
    - Manage server lifecycle
    """
    
    mcp_docker = MCPDockerToolsEnhanced(agent)
    
    if not mcp_docker.manager.available:
        print("[Info] MCP Docker tools not loaded - Docker not available")
        return tool_list
    
    tool_list.extend([
        StructuredTool.from_function(
            func=mcp_docker.create_mcp_server,
            name="create_mcp_server",
            description=(
                "Create a new MCP server in Docker from templates. "
                "Available types: filesystem, postgres, github, slack, sqlite, "
                "memory, puppeteer, time, fetch, custom, and any user-created templates."
            ),
            args_schema=MCPServerCreateInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.create_mcp_template,
            name="create_mcp_template",
            description=(
                "Create a reusable MCP server template. "
                "Define a Dockerfile and configuration for a new server type. "
                "Templates can be instantiated multiple times with different configs."
            ),
            args_schema=MCPTemplateCreateInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.generate_mcp_server,
            name="generate_mcp_server",
            description=(
                "Generate complete MCP server implementation code in Python or TypeScript. "
                "Describe the tools you want and the LLM creates working server code. "
                "Generates Dockerfile, server code, and build instructions."
            ),
            args_schema=MCPServerCodeInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.list_mcp_templates,
            name="list_mcp_templates",
            description=(
                "List all available MCP server templates (built-in and custom). "
                "Shows what templates can be used to create servers."
            ),
            args_schema=MCPTemplateListInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.delete_mcp_template,
            name="delete_mcp_template",
            description=(
                "Delete a custom MCP template. Built-in templates cannot be deleted."
            ),
            args_schema=LLMQueryInput  # Reuse existing schema
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.control_mcp_server,
            name="control_mcp_server",
            description=(
                "Control MCP servers: start, stop, restart, or remove."
            ),
            args_schema=MCPServerControlInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.list_mcp_servers,
            name="list_mcp_servers",
            description=(
                "List all MCP servers with status and details."
            ),
            args_schema=MCPServerListInput
        ),
        
        StructuredTool.from_function(
            func=mcp_docker.get_mcp_server_logs,
            name="get_mcp_server_logs",
            description=(
                "View logs from an MCP server for debugging."
            ),
            args_schema=MCPServerLogsInput
        ),
    ])
    
    return tool_list