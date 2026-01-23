"""
Vera Agents API v2
==================
REST API for the new YAML-based agent management system.

Endpoints:
- GET    /api/agents/v2/list              - List all agent directories
- GET    /api/agents/v2/{name}            - Get full agent details
- GET    /api/agents/v2/{name}/config     - Get agent YAML config
- POST   /api/agents/v2/{name}/config     - Update agent YAML config
- GET    /api/agents/v2/{name}/template   - Get prompt template
- POST   /api/agents/v2/{name}/template   - Update prompt template
- POST   /api/agents/v2/{name}/build      - Build agent (Modelfile + Ollama)
- POST   /api/agents/v2/{name}/validate   - Validate agent configuration
- GET    /api/agents/v2/{name}/files      - List agent files
- GET    /api/agents/v2/{name}/files/{path} - Get specific file content
- POST   /api/agents/v2/new               - Create new agent
- DELETE /api/agents/v2/{name}            - Delete agent
- GET    /api/agents/v2/templates/shared  - List shared templates
- POST   /api/agents/v2/build-all         - Build all agents
"""

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import yaml
import os
from pathlib import Path
from datetime import datetime

router = APIRouter(prefix="/api/agents/v2", tags=["agents-v2"])

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENTS_DIR = Path("./Vera/Agents/agents")
TEMPLATES_DIR = Path("./Vera/Agents/templates")
BUILD_DIR = Path("./Vera/Agents/build")

# Ensure directories exist
AGENTS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
BUILD_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AgentMemoryConfig(BaseModel):
    use_vector: bool = True
    use_neo4j: bool = True
    vector_top_k: int = 8
    neo4j_limit: int = 16
    enable_triage: bool = False

class AgentParameters(BaseModel):
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.05
    num_predict: int = -1
    stop_sequences: List[str] = []

class SystemPromptConfig(BaseModel):
    template: str = "prompt_template.j2"
    variables: Dict[str, Any] = {}
    includes: List[str] = []

class AgentConfigModel(BaseModel):
    name: str
    description: str = ""
    base_model: str = "gemma2"
    quantization: Optional[str] = None
    num_ctx: int = 4096
    gpu_layers: int = 99
    parameters: AgentParameters = Field(default_factory=AgentParameters)
    memory: AgentMemoryConfig = Field(default_factory=AgentMemoryConfig)
    system_prompt: SystemPromptConfig = Field(default_factory=SystemPromptConfig)
    includes: List[str] = []
    capabilities: List[str] = []
    tools: List[str] = []
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = []

class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""
    base_model: str = "gemma2"
    template_content: Optional[str] = None

class BuildAgentRequest(BaseModel):
    create_ollama_model: bool = True

class UpdateTemplateRequest(BaseModel):
    content: str

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_agent_yaml(agent_name: str) -> Dict:
    """Load agent YAML configuration"""
    agent_dir = AGENTS_DIR / agent_name
    config_file = agent_dir / "agent.yaml"
    
    if not config_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_name}"
        )
    
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load agent config: {str(e)}"
        )

def save_agent_yaml(agent_name: str, config: Dict):
    """Save agent YAML configuration"""
    agent_dir = AGENTS_DIR / agent_name
    config_file = agent_dir / "agent.yaml"
    
    try:
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save agent config: {str(e)}"
        )

def get_agent_template_path(agent_name: str, template_name: str = None) -> Path:
    """Get path to agent's template file"""
    agent_dir = AGENTS_DIR / agent_name
    
    if template_name:
        return agent_dir / template_name
    
    # Get from config
    config = load_agent_yaml(agent_name)
    template_name = config.get('system_prompt', {}).get('template', 'prompt_template.j2')
    return agent_dir / template_name

def list_agent_files(agent_name: str) -> List[Dict[str, Any]]:
    """List all files in agent directory"""
    agent_dir = AGENTS_DIR / agent_name
    
    if not agent_dir.exists():
        return []
    
    files = []
    for file_path in agent_dir.rglob('*'):
        if file_path.is_file():
            rel_path = file_path.relative_to(agent_dir)
            files.append({
                'path': str(rel_path),
                'name': file_path.name,
                'size': file_path.stat().st_size,
                'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                'type': 'yaml' if file_path.suffix == '.yaml' else
                        'template' if file_path.suffix == '.j2' else
                        'text' if file_path.suffix in ['.txt', '.md'] else
                        'other'
            })
    
    return files

def get_agent_status(agent_name: str) -> Dict[str, Any]:
    """Get agent build and validation status"""
    agent_dir = AGENTS_DIR / agent_name
    modelfile_path = BUILD_DIR / f"{agent_name}.Modelfile"
    
    status = {
        'exists': agent_dir.exists(),
        'has_config': (agent_dir / "agent.yaml").exists(),
        'has_modelfile': modelfile_path.exists(),
        'modelfile_age': None,
        'validation_issues': []
    }
    
    if modelfile_path.exists():
        age_seconds = datetime.now().timestamp() - modelfile_path.stat().st_mtime
        status['modelfile_age'] = age_seconds
    
    # Quick validation
    if status['has_config']:
        try:
            config = load_agent_yaml(agent_name)
            template_path = get_agent_template_path(agent_name)
            
            if not template_path.exists():
                status['validation_issues'].append(
                    f"Template not found: {template_path.name}"
                )
            
            # Check includes
            for include in config.get('includes', []):
                include_path = agent_dir / include
                if not include_path.exists():
                    status['validation_issues'].append(
                        f"Include file not found: {include}"
                    )
        except Exception as e:
            status['validation_issues'].append(f"Config error: {str(e)}")
    
    return status

# ============================================================================
# AGENT MANAGER INTEGRATION
# ============================================================================

def get_agent_manager():
    """Get or create AgentManager instance"""
    try:
        from Vera.Ollama.Agents.agent_manager import AgentManager
        
        # Try to get Vera logger
        try:
            from Vera.Logging.logging import get_logger
            logger = get_logger("agents_api")
        except:
            logger = None
        
        return AgentManager(
            agents_dir=str(AGENTS_DIR),
            templates_dir=str(TEMPLATES_DIR),
            build_dir=str(BUILD_DIR),
            logger=logger
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AgentManager not available: {str(e)}"
        )

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/list")
async def list_agents():
    """List all agent directories with status"""
    try:
        agents = []
        
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if agent_dir.is_dir() and not agent_dir.name.startswith('.'):
                agent_name = agent_dir.name
                
                try:
                    config = load_agent_yaml(agent_name)
                    status = get_agent_status(agent_name)
                    
                    agents.append({
                        'id': agent_name,
                        'name': config.get('name', agent_name),
                        'description': config.get('description', ''),
                        'base_model': config.get('base_model', 'unknown'),
                        'version': config.get('version', '1.0.0'),
                        'tags': config.get('tags', []),
                        'capabilities': config.get('capabilities', []),
                        'tools': config.get('tools', []),
                        'status': status
                    })
                except Exception as e:
                    # Agent directory exists but has issues
                    agents.append({
                        'id': agent_name,
                        'name': agent_name,
                        'description': '',
                        'base_model': 'unknown',
                        'version': '1.0.0',
                        'tags': [],
                        'capabilities': [],
                        'tools': [],
                        'status': {
                            'exists': True,
                            'has_config': False,
                            'has_modelfile': False,
                            'validation_issues': [f"Error loading: {str(e)}"]
                        }
                    })
        
        return JSONResponse({
            'status': 'success',
            'agents': agents,
            'count': len(agents)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_name}")
async def get_agent_details(agent_name: str):
    """Get complete agent details"""
    try:
        config = load_agent_yaml(agent_name)
        status = get_agent_status(agent_name)
        files = list_agent_files(agent_name)
        
        return JSONResponse({
            'status': 'success',
            'agent': {
                'id': agent_name,
                'config': config,
                'status': status,
                'files': files
            }
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_name}/config")
async def get_agent_config(agent_name: str):
    """Get agent YAML configuration"""
    try:
        config = load_agent_yaml(agent_name)
        
        return JSONResponse({
            'status': 'success',
            'agent_name': agent_name,
            'config': config
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_name}/config")
async def update_agent_config(agent_name: str, config: AgentConfigModel):
    """Update agent YAML configuration"""
    try:
        # Convert to dict
        config_dict = config.dict()
        
        # Save YAML
        save_agent_yaml(agent_name, config_dict)
        
        return JSONResponse({
            'status': 'success',
            'message': f'Configuration updated for {agent_name}',
            'agent_name': agent_name
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_name}/template")
async def get_agent_template(agent_name: str):
    """Get agent's prompt template"""
    try:
        template_path = get_agent_template_path(agent_name)
        
        if not template_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {template_path.name}"
            )
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        return JSONResponse({
            'status': 'success',
            'agent_name': agent_name,
            'template_name': template_path.name,
            'content': content,
            'size': len(content)
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_name}/template")
async def update_agent_template(agent_name: str, request: UpdateTemplateRequest):
    """Update agent's prompt template"""
    try:
        template_path = get_agent_template_path(agent_name)
        
        # Backup existing template
        if template_path.exists():
            backup_path = template_path.with_suffix('.j2.bak')
            with open(template_path, 'r') as f:
                with open(backup_path, 'w') as backup:
                    backup.write(f.read())
        
        # Write new template
        with open(template_path, 'w') as f:
            f.write(request.content)
        
        return JSONResponse({
            'status': 'success',
            'message': f'Template updated for {agent_name}',
            'agent_name': agent_name,
            'template_name': template_path.name
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_name}/files")
async def get_agent_files(agent_name: str):
    """List all files in agent directory"""
    try:
        files = list_agent_files(agent_name)
        
        return JSONResponse({
            'status': 'success',
            'agent_name': agent_name,
            'files': files,
            'count': len(files)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_name}/files/{file_path:path}")
async def get_agent_file(agent_name: str, file_path: str):
    """Get specific file content from agent directory"""
    try:
        agent_dir = AGENTS_DIR / agent_name
        full_path = agent_dir / file_path
        
        # Security: ensure path is within agent directory
        if not full_path.resolve().is_relative_to(agent_dir.resolve()):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside agent directory"
            )
        
        if not full_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        with open(full_path, 'r') as f:
            content = f.read()
        
        return PlainTextResponse(content)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_name}/validate")
async def validate_agent(agent_name: str):
    """Validate agent configuration"""
    try:
        manager = get_agent_manager()
        issues = manager.validate_agent_config(agent_name)
        
        return JSONResponse({
            'status': 'success' if not issues else 'warning',
            'agent_name': agent_name,
            'valid': len(issues) == 0,
            'issues': issues
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_name}/build")
async def build_agent(agent_name: str, request: BuildAgentRequest = BuildAgentRequest()):
    """Build agent (render template, create Modelfile, optionally create Ollama model)"""
    try:
        manager = get_agent_manager()
        
        # Validate first
        issues = manager.validate_agent_config(agent_name)
        if issues:
            return JSONResponse({
                'status': 'error',
                'message': 'Validation failed',
                'issues': issues
            }, status_code=400)
        
        # Build agent
        config = manager.build_agent(
            agent_name,
            create_model=request.create_ollama_model
        )
        
        if not config:
            raise HTTPException(
                status_code=500,
                detail="Failed to build agent"
            )
        
        modelfile_path = BUILD_DIR / f"{agent_name}.Modelfile"
        
        return JSONResponse({
            'status': 'success',
            'message': f'Agent built successfully: {agent_name}',
            'agent_name': agent_name,
            'modelfile': str(modelfile_path),
            'ollama_model_created': request.create_ollama_model
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_name}/modelfile")
async def get_agent_modelfile(agent_name: str):
    """Get generated Modelfile content"""
    try:
        modelfile_path = BUILD_DIR / f"{agent_name}.Modelfile"
        
        if not modelfile_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Modelfile not found. Build agent first."
            )
        
        with open(modelfile_path, 'r') as f:
            content = f.read()
        
        return PlainTextResponse(content)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/new")
async def create_new_agent(request: CreateAgentRequest):
    """Create new agent directory and files"""
    try:
        agent_dir = AGENTS_DIR / request.name
        
        if agent_dir.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Agent already exists: {request.name}"
            )
        
        # Create directory
        agent_dir.mkdir(parents=True)
        
        # Create default config
        config = {
            'name': request.name,
            'description': request.description,
            'base_model': request.base_model,
            'num_ctx': 4096,
            'gpu_layers': 99,
            'parameters': {
                'temperature': 0.7,
                'top_p': 0.9,
                'top_k': 40,
                'repeat_penalty': 1.05,
                'num_predict': -1,
                'stop_sequences': []
            },
            'memory': {
                'use_vector': True,
                'use_neo4j': True,
                'vector_top_k': 8,
                'neo4j_limit': 16,
                'enable_triage': False
            },
            'system_prompt': {
                'template': 'prompt_template.j2',
                'variables': {},
                'includes': []
            },
            'includes': [],
            'capabilities': [],
            'tools': [],
            'version': '1.0.0',
            'tags': []
        }
        
        # Save config
        with open(agent_dir / 'agent.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        # Create default template
        template_content = request.template_content or """You are {{ name }}, an AI assistant.

{{ description }}

Current date: {{ current_date }}

Instructions:
- Be helpful and concise
- Provide accurate information
- Ask for clarification when needed

Respond to the user's query below:
"""
        
        with open(agent_dir / 'prompt_template.j2', 'w') as f:
            f.write(template_content)
        
        return JSONResponse({
            'status': 'success',
            'message': f'Agent created: {request.name}',
            'agent_name': request.name,
            'path': str(agent_dir)
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{agent_name}")
async def delete_agent(agent_name: str, confirm: bool = False):
    """Delete agent directory and files"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete agent"
        )
    
    try:
        agent_dir = AGENTS_DIR / agent_name
        
        if not agent_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {agent_name}"
            )
        
        # Delete directory
        import shutil
        shutil.rmtree(agent_dir)
        
        # Delete Modelfile if exists
        modelfile_path = BUILD_DIR / f"{agent_name}.Modelfile"
        if modelfile_path.exists():
            modelfile_path.unlink()
        
        return JSONResponse({
            'status': 'success',
            'message': f'Agent deleted: {agent_name}',
            'agent_name': agent_name
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/shared")
async def list_shared_templates():
    """List shared templates in templates directory"""
    try:
        templates = []
        
        for template_path in TEMPLATES_DIR.rglob('*.j2'):
            rel_path = template_path.relative_to(TEMPLATES_DIR)
            
            templates.append({
                'name': template_path.name,
                'path': str(rel_path),
                'size': template_path.stat().st_size,
                'modified': datetime.fromtimestamp(
                    template_path.stat().st_mtime
                ).isoformat()
            })
        
        return JSONResponse({
            'status': 'success',
            'templates': templates,
            'count': len(templates)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/build-all")
async def build_all_agents(create_models: bool = False):
    """Build all agents"""
    try:
        manager = get_agent_manager()
        
        built_agents = manager.build_all_agents(create_models=create_models)
        
        results = []
        for agent_name, config in built_agents.items():
            results.append({
                'agent_name': agent_name,
                'status': 'success',
                'base_model': config.base_model
            })
        
        return JSONResponse({
            'status': 'success',
            'message': f'Built {len(built_agents)} agents',
            'results': results,
            'count': len(built_agents)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# SYSTEM INFO
# ============================================================================

@router.get("/system/info")
async def get_system_info():
    """Get system information"""
    try:
        agent_count = len(list(AGENTS_DIR.iterdir()))
        template_count = len(list(TEMPLATES_DIR.rglob('*.j2')))
        modelfile_count = len(list(BUILD_DIR.glob('*.Modelfile')))
        
        return JSONResponse({
            'status': 'success',
            'paths': {
                'agents_dir': str(AGENTS_DIR),
                'templates_dir': str(TEMPLATES_DIR),
                'build_dir': str(BUILD_DIR)
            },
            'counts': {
                'agents': agent_count,
                'shared_templates': template_count,
                'modelfiles': modelfile_count
            },
            'agent_manager_available': True
        })
    
    except Exception as e:
        return JSONResponse({
            'status': 'error',
            'error': str(e),
            'agent_manager_available': False
        })

# ============================================================================
# INITIALIZATION
# ============================================================================

print("[Agents API v2] Loaded")
print(f"  Agents directory: {AGENTS_DIR}")
print(f"  Templates directory: {TEMPLATES_DIR}")
print(f"  Build directory: {BUILD_DIR}")