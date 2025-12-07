"""
Vera Agents API
===============
Complete REST API for managing Vera agent configurations, prompts, and testing.

Endpoints:
- GET  /api/agents/list - List all registered agents/tasks
- GET  /api/agents/{name}/config - Get agent configuration
- POST /api/agents/{name}/config - Update agent configuration
- POST /api/agents/{name}/test - Test agent with sample input
- GET  /api/agents/categories - Get agents grouped by category
- GET  /api/agents/stats - Get agent performance statistics
- POST /api/agents/{name}/enable - Enable/disable agent
- GET  /api/agents/templates - Get prompt templates
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
import os
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENTS_CONFIG_FILE = "Configuration/vera_agents.json"
AGENT_STATS_FILE = "Configuration/agent_stats.json"

# Default agent configurations
DEFAULT_AGENTS = {
    "triage": {
        "name": "Triage Agent",
        "description": "Routes queries to appropriate handlers",
        "category": "routing",
        "enabled": True,
        "task_type": "LLM",
        "priority": "CRITICAL",
        "estimated_duration": 2.0,
        "model": "fast_llm",
        "temperature": 0.3,
        "max_tokens": 500,
        "prompt_template": """Classify this Query into one of the following categories:
    - 'focus'      → Change the focus of background thought.
    - 'proactive'  → Trigger proactive thinking.
    - 'simple'     → Simple textual response.
    - 'toolchain'  → Requires a series of tools or step-by-step planning.
    - 'reasoning'  → Requires deep reasoning.
    - 'complex'    → Complex written response with high-quality output.

Current focus: {focus}
Query: {query}

Respond with a single classification term on the first line.""",
        "parameters": {
            "focus": "Current user focus",
            "query": "User input query"
        }
    },
    
    "toolchain": {
        "name": "Toolchain Agent",
        "description": "Plans and executes tool sequences",
        "category": "execution",
        "enabled": True,
        "task_type": "TOOL",
        "priority": "HIGH",
        "estimated_duration": 30.0,
        "model": "tool_llm",
        "temperature": 0.5,
        "max_tokens": 2000,
        "prompt_template": """You are a tool planning agent. Analyze the query and create a step-by-step plan using available tools.

Available tools: {tools}
Query: {query}

Create a detailed execution plan with:
1. Tool sequence
2. Expected inputs/outputs
3. Error handling

Plan:""",
        "parameters": {
            "tools": "Available tools list",
            "query": "User query"
        }
    },
    
    "scheduler": {
        "name": "Task Scheduler",
        "description": "Schedules and prioritizes tasks",
        "category": "management",
        "enabled": True,
        "task_type": "GENERAL",
        "priority": "HIGH",
        "estimated_duration": 5.0,
        "model": "fast_llm",
        "temperature": 0.4,
        "max_tokens": 1000,
        "prompt_template": """You are a task scheduling agent. Analyze tasks and create an optimal execution schedule.

Current tasks: {tasks}
System load: {load}
Priority rules: {rules}

Create a schedule that:
1. Respects priorities
2. Balances system load
3. Meets deadlines
4. Handles dependencies

Schedule:""",
        "parameters": {
            "tasks": "Task queue",
            "load": "System load metrics",
            "rules": "Scheduling rules"
        }
    },
    
    "idea_generator": {
        "name": "Idea Generator",
        "description": "Generates creative ideas for current focus",
        "category": "proactive",
        "enabled": True,
        "task_type": "BACKGROUND",
        "priority": "LOW",
        "estimated_duration": 15.0,
        "model": "deep_llm",
        "temperature": 0.9,
        "max_tokens": 1500,
        "prompt_template": """You are a creative idea generation agent working on: {focus}

Context: {context}
Recent progress: {progress}

Generate 5 innovative, actionable ideas that could advance this project. For each idea:
1. Brief description
2. Implementation approach
3. Expected impact
4. Required resources

Ideas:""",
        "parameters": {
            "focus": "Current focus area",
            "context": "Project context",
            "progress": "Recent progress"
        }
    },
    
    "action_planner": {
        "name": "Action Planner",
        "description": "Creates concrete action plans",
        "category": "proactive",
        "enabled": True,
        "task_type": "BACKGROUND",
        "priority": "NORMAL",
        "estimated_duration": 20.0,
        "model": "deep_llm",
        "temperature": 0.6,
        "max_tokens": 2000,
        "prompt_template": """You are an action planning agent for: {focus}

Current state: {state}
Goals: {goals}
Constraints: {constraints}

Create a detailed action plan with:
1. Immediate next steps (today)
2. Short-term actions (this week)
3. Medium-term milestones (this month)
4. Success criteria
5. Risk mitigation

Action Plan:""",
        "parameters": {
            "focus": "Focus area",
            "state": "Current state",
            "goals": "Project goals",
            "constraints": "Known constraints"
        }
    },
    
    "reviewer": {
        "name": "Code Reviewer",
        "description": "Reviews code quality and suggests improvements",
        "category": "quality",
        "enabled": True,
        "task_type": "GENERAL",
        "priority": "NORMAL",
        "estimated_duration": 10.0,
        "model": "deep_llm",
        "temperature": 0.3,
        "max_tokens": 2000,
        "prompt_template": """You are a code review agent. Analyze this code for:

Code: {code}
Language: {language}
Context: {context}

Review criteria:
1. Correctness and bugs
2. Performance issues
3. Security concerns
4. Code style and readability
5. Best practices
6. Potential improvements

Review:""",
        "parameters": {
            "code": "Code to review",
            "language": "Programming language",
            "context": "Code context"
        }
    },
    
    "summarizer": {
        "name": "Content Summarizer",
        "description": "Creates concise summaries of content",
        "category": "processing",
        "enabled": True,
        "task_type": "GENERAL",
        "priority": "NORMAL",
        "estimated_duration": 8.0,
        "model": "intermediate_llm",
        "temperature": 0.4,
        "max_tokens": 1000,
        "prompt_template": """You are a summarization agent. Create a clear, concise summary of:

Content: {content}
Target length: {target_length}
Focus: {focus_areas}

Summary requirements:
1. Capture key points
2. Maintain accuracy
3. Stay within length limit
4. Highlight important details

Summary:""",
        "parameters": {
            "content": "Content to summarize",
            "target_length": "Target word count",
            "focus_areas": "Areas to emphasize"
        }
    },
    
    "analyzer": {
        "name": "Data Analyzer",
        "description": "Analyzes data and generates insights",
        "category": "processing",
        "enabled": True,
        "task_type": "GENERAL",
        "priority": "NORMAL",
        "estimated_duration": 15.0,
        "model": "reasoning_llm",
        "temperature": 0.5,
        "max_tokens": 2000,
        "prompt_template": """You are a data analysis agent. Analyze the provided data:

Data: {data}
Type: {data_type}
Questions: {questions}

Analysis should include:
1. Key patterns and trends
2. Statistical insights
3. Anomalies or outliers
4. Actionable recommendations
5. Confidence levels

Analysis:""",
        "parameters": {
            "data": "Data to analyze",
            "data_type": "Data format/type",
            "questions": "Specific questions"
        }
    },
    
    "error_handler": {
        "name": "Error Handler",
        "description": "Diagnoses and suggests fixes for errors",
        "category": "debugging",
        "enabled": True,
        "task_type": "GENERAL",
        "priority": "HIGH",
        "estimated_duration": 10.0,
        "model": "reasoning_llm",
        "temperature": 0.3,
        "max_tokens": 1500,
        "prompt_template": """You are an error diagnosis agent. Analyze this error:

Error message: {error}
Stack trace: {trace}
Context: {context}
Recent changes: {changes}

Provide:
1. Root cause analysis
2. Immediate fix suggestions
3. Prevention strategies
4. Related issues to check

Diagnosis:""",
        "parameters": {
            "error": "Error message",
            "trace": "Stack trace",
            "context": "Error context",
            "changes": "Recent code changes"
        }
    },
    
    "memory_curator": {
        "name": "Memory Curator",
        "description": "Curates and organizes memory content",
        "category": "memory",
        "enabled": True,
        "task_type": "BACKGROUND",
        "priority": "LOW",
        "estimated_duration": 10.0,
        "model": "intermediate_llm",
        "temperature": 0.4,
        "max_tokens": 1000,
        "prompt_template": """You are a memory curation agent. Organize this content:

Content: {content}
Type: {content_type}
Existing tags: {tags}

Curation tasks:
1. Extract key concepts
2. Assign relevant tags
3. Identify relationships
4. Rate importance (1-10)
5. Suggest consolidation

Curation:""",
        "parameters": {
            "content": "Content to curate",
            "content_type": "Content type",
            "tags": "Existing tags"
        }
    }
}

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AgentConfig(BaseModel):
    name: str
    description: str
    category: str
    enabled: bool
    task_type: str
    priority: str
    estimated_duration: float
    model: str
    temperature: float
    max_tokens: int
    prompt_template: str
    parameters: Dict[str, str]

class AgentTestRequest(BaseModel):
    parameters: Dict[str, Any]
    stream: bool = False

class AgentUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    prompt_template: Optional[str] = None
    priority: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_agents_config() -> Dict[str, Dict]:
    """Load agents configuration from file"""
    if os.path.exists(AGENTS_CONFIG_FILE):
        try:
            with open(AGENTS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Agents API] Error loading config: {e}")
    
    # Return defaults if file doesn't exist
    return DEFAULT_AGENTS.copy()

def save_agents_config(config: Dict[str, Dict]):
    """Save agents configuration to file"""
    try:
        os.makedirs(os.path.dirname(AGENTS_CONFIG_FILE), exist_ok=True)
        with open(AGENTS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"[Agents API] Error saving config: {e}")
        return False

def load_agent_stats() -> Dict[str, Dict]:
    """Load agent performance statistics"""
    if os.path.exists(AGENT_STATS_FILE):
        try:
            with open(AGENT_STATS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_agent_stats(stats: Dict[str, Dict]):
    """Save agent statistics"""
    try:
        os.makedirs(os.path.dirname(AGENT_STATS_FILE), exist_ok=True)
        with open(AGENT_STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"[Agents API] Error saving stats: {e}")

def generate_agent_task_code(agent_id: str, agent_config: Dict) -> str:
    """Generate task registration code for a single agent"""
    
    # Extract config values
    name = agent_config.get("name", agent_id)
    description = agent_config.get("description", "")
    task_type = agent_config.get("task_type", "GENERAL")
    priority = agent_config.get("priority", "NORMAL")
    duration = agent_config.get("estimated_duration", 5.0)
    model = agent_config.get("model", "fast_llm")
    temperature = agent_config.get("temperature", 0.7)
    max_tokens = agent_config.get("max_tokens", 1000)
    prompt_template = agent_config.get("prompt_template", "")
    parameters = agent_config.get("parameters", {})
    
    # Generate parameter docstring
    param_docs = "\n    ".join([f"{param}: {desc}" for param, desc in parameters.items()])
    
    # Generate function signature parameters
    func_params = ", ".join(parameters.keys()) if parameters else "**kwargs"
    
    # Generate code
    code = f'''"""
{name}
{description}
"""

from Vera.Orchestration.orchestration import task, TaskType, Priority
import json
import os


def load_agent_config(agent_id: str) -> dict:
    """Load agent configuration from file"""
    config_file = "Configuration/vera_agents.json"
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            return config.get(agent_id, {{}})
    except Exception as e:
        print(f"[Agent] Failed to load config for {{agent_id}}: {{e}}")
        return {{}}


@task("{agent_id}", task_type=TaskType.{task_type}, priority=Priority.{priority}, estimated_duration={duration})
def {agent_id.replace("-", "_")}(vera_instance, {func_params}):
    """
    {description}
    
    Parameters:
    {"    " + param_docs if param_docs else "    **kwargs: Agent parameters"}
    
    Yields:
        str: Response chunks from the LLM
    """
    # Load agent config from file
    config = load_agent_config("{agent_id}")
    
    if not config:
        yield "Error: Agent configuration not found"
        return
    
    # Build parameters dict
    params = {{{", ".join([f'"{p}": {p}' for p in parameters.keys()]) if parameters else "**kwargs"}}}
    
    # Format prompt template with parameters
    try:
        prompt = config["prompt_template"].format(**params)
    except KeyError as e:
        yield f"Error: Missing required parameter {{e}}"
        return
    
    # Get the appropriate LLM
    model_name = config.get("model", "{model}")
    llm = getattr(vera_instance, model_name, vera_instance.fast_llm)
    
    # Optional: Override temperature and max_tokens
    # You can modify the LLM config here if needed
    # llm.temperature = config.get("temperature", {temperature})
    # llm.max_tokens = config.get("max_tokens", {max_tokens})
    
    # Stream the response
    try:
        for chunk in llm.stream(prompt):
            yield chunk
    except Exception as e:
        yield f"Error during generation: {{str(e)}}"


# Example usage in Vera.py:
# from vera_agent_tasks import {agent_id.replace("-", "_")}
#
# # In async_run or wherever you route to agents:
# if route_to == "{agent_id}":
#     for chunk in vera.orchestrator.stream_result(
#         vera.orchestrator.submit_task("{agent_id}", vera_instance=vera, {", ".join([f'{p}="value"' for p in parameters.keys()]) if parameters else '**params'})
#     ):
#         print(chunk, end='', flush=True)
'''
    
    return code

def generate_all_agents_tasks_code(config: Dict[str, Dict]) -> str:
    """Generate task registration code for all enabled agents"""
    
    header = '''"""
Vera Agent Tasks - Auto-generated
==================================
Task registrations for all configured agents.

This file is auto-generated from agent configurations.
To update, modify agents via the Agents UI and regenerate.
"""

from Vera.Orchestration.orchestration import task, TaskType, Priority
import json
import os


def load_agent_config(agent_id: str) -> dict:
    """Load agent configuration from file"""
    config_file = "Configuration/vera_agents.json"
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            return config.get(agent_id, {})
    except Exception as e:
        print(f"[Agent] Failed to load config for {agent_id}: {e}")
        return {}


# ============================================================================
# AGENT TASKS
# ============================================================================

'''
    
    tasks_code = []
    enabled_agents = []
    
    for agent_id, agent_config in config.items():
        if not agent_config.get("enabled", True):
            continue
        
        enabled_agents.append(agent_id)
        
        # Extract config
        name = agent_config.get("name", agent_id)
        description = agent_config.get("description", "")
        task_type = agent_config.get("task_type", "GENERAL")
        priority = agent_config.get("priority", "NORMAL")
        duration = agent_config.get("estimated_duration", 5.0)
        model = agent_config.get("model", "fast_llm")
        parameters = agent_config.get("parameters", {})
        
        # Generate parameter list
        func_params = ", ".join(parameters.keys()) if parameters else "**kwargs"
        param_docs = "\n    ".join([f"{param}: {desc}" for param, desc in parameters.items()])
        params_dict = ", ".join([f'"{p}": {p}' for p in parameters.keys()]) if parameters else "**kwargs"
        
        task_code = f'''
@task("{agent_id}", task_type=TaskType.{task_type}, priority=Priority.{priority}, estimated_duration={duration})
def {agent_id.replace("-", "_")}(vera_instance, {func_params}):
    """
    {name}: {description}
    
    Parameters:
    {"    " + param_docs if param_docs else "    **kwargs: Agent parameters"}
    """
    config = load_agent_config("{agent_id}")
    
    if not config:
        yield "Error: Agent configuration not found"
        return
    
    params = {{{params_dict}}}
    
    try:
        prompt = config["prompt_template"].format(**params)
    except KeyError as e:
        yield f"Error: Missing required parameter {{e}}"
        return
    
    model_name = config.get("model", "{model}")
    llm = getattr(vera_instance, model_name, vera_instance.fast_llm)
    
    try:
        for chunk in llm.stream(prompt):
            yield chunk
    except Exception as e:
        yield f"Error during generation: {{str(e)}}"
'''
        
        tasks_code.append(task_code)
    
    footer = f'''

# ============================================================================
# TASK REGISTRY
# ============================================================================

print("[Agent Tasks] Registered agents:")
{chr(10).join([f'print("  - {agent_id}")' for agent_id in enabled_agents])}
print(f"Total: {len(enabled_agents)} agents")
'''
    
    return header + "\n".join(tasks_code) + footer

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/list")
async def list_agents():
    """List all registered agents"""
    try:
        config = load_agents_config()
        
        agents = []
        for agent_id, agent_data in config.items():
            agents.append({
                "id": agent_id,
                **agent_data
            })
        
        return JSONResponse({
            "status": "success",
            "agents": agents,
            "count": len(agents)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
async def get_categories():
    """Get agents grouped by category"""
    try:
        config = load_agents_config()
        
        categories = {}
        for agent_id, agent_data in config.items():
            category = agent_data.get("category", "uncategorized")
            if category not in categories:
                categories[category] = []
            
            categories[category].append({
                "id": agent_id,
                **agent_data
            })
        
        return JSONResponse({
            "status": "success",
            "categories": categories,
            "count": len(categories)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """Get configuration for specific agent"""
    try:
        config = load_agents_config()
        
        if agent_id not in config:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        return JSONResponse({
            "status": "success",
            "agent_id": agent_id,
            "config": config[agent_id]
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/config")
async def update_agent_config(agent_id: str, update: AgentUpdateRequest):
    """Update agent configuration"""
    try:
        config = load_agents_config()
        
        if agent_id not in config:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        # Update only provided fields
        if update.enabled is not None:
            config[agent_id]["enabled"] = update.enabled
        if update.temperature is not None:
            config[agent_id]["temperature"] = update.temperature
        if update.max_tokens is not None:
            config[agent_id]["max_tokens"] = update.max_tokens
        if update.prompt_template is not None:
            config[agent_id]["prompt_template"] = update.prompt_template
        if update.priority is not None:
            config[agent_id]["priority"] = update.priority
        
        # Save configuration
        if not save_agents_config(config):
            raise HTTPException(status_code=500, detail="Failed to save configuration")
        
        return JSONResponse({
            "status": "success",
            "message": f"Updated configuration for {agent_id}",
            "config": config[agent_id]
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/enable")
async def enable_agent(agent_id: str, enabled: bool = True):
    """Enable or disable an agent"""
    try:
        config = load_agents_config()
        
        if agent_id not in config:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        config[agent_id]["enabled"] = enabled
        
        if not save_agents_config(config):
            raise HTTPException(status_code=500, detail="Failed to save configuration")
        
        status_text = "enabled" if enabled else "disabled"
        return JSONResponse({
            "status": "success",
            "message": f"Agent {agent_id} {status_text}",
            "enabled": enabled
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/test")
async def test_agent(agent_id: str, request: AgentTestRequest):
    """Test agent with sample parameters"""
    try:
        config = load_agents_config()
        
        if agent_id not in config:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        agent_config = config[agent_id]
        
        # Format prompt with parameters
        try:
            formatted_prompt = agent_config["prompt_template"].format(**request.parameters)
        except KeyError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required parameter: {e}"
            )
        
        # Record test
        stats = load_agent_stats()
        if agent_id not in stats:
            stats[agent_id] = {
                "tests": 0,
                "last_test": None
            }
        
        stats[agent_id]["tests"] += 1
        stats[agent_id]["last_test"] = datetime.now().isoformat()
        save_agent_stats(stats)
        
        # Return formatted prompt (actual execution would happen via Vera)
        return JSONResponse({
            "status": "success",
            "agent_id": agent_id,
            "formatted_prompt": formatted_prompt,
            "parameters": request.parameters,
            "model": agent_config["model"],
            "temperature": agent_config["temperature"],
            "max_tokens": agent_config["max_tokens"],
            "note": "This is a test formatting. Actual execution requires Vera instance."
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_agent_stats():
    """Get agent performance statistics"""
    try:
        stats = load_agent_stats()
        config = load_agents_config()
        
        # Combine stats with config
        combined_stats = {}
        for agent_id in config.keys():
            combined_stats[agent_id] = {
                "name": config[agent_id]["name"],
                "enabled": config[agent_id]["enabled"],
                "category": config[agent_id]["category"],
                "tests": stats.get(agent_id, {}).get("tests", 0),
                "last_test": stats.get(agent_id, {}).get("last_test", None)
            }
        
        return JSONResponse({
            "status": "success",
            "stats": combined_stats
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates")
async def get_prompt_templates():
    """Get all prompt templates"""
    try:
        config = load_agents_config()
        
        templates = {}
        for agent_id, agent_data in config.items():
            templates[agent_id] = {
                "name": agent_data["name"],
                "template": agent_data["prompt_template"],
                "parameters": agent_data["parameters"]
            }
        
        return JSONResponse({
            "status": "success",
            "templates": templates,
            "count": len(templates)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_to_defaults():
    """Reset all agents to default configuration"""
    try:
        if not save_agents_config(DEFAULT_AGENTS.copy()):
            raise HTTPException(status_code=500, detail="Failed to reset configuration")
        
        return JSONResponse({
            "status": "success",
            "message": "All agents reset to defaults",
            "count": len(DEFAULT_AGENTS)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_config():
    """Export current configuration as JSON"""
    try:
        config = load_agents_config()
        
        return JSONResponse({
            "status": "success",
            "config": config,
            "exported_at": datetime.now().isoformat()
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_config(config: Dict[str, Dict]):
    """Import configuration from JSON"""
    try:
        # Validate structure
        for agent_id, agent_data in config.items():
            required_fields = ["name", "description", "category", "enabled", 
                             "task_type", "model", "prompt_template"]
            for field in required_fields:
                if field not in agent_data:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing required field '{field}' in agent '{agent_id}'"
                    )
        
        # Save imported config
        if not save_agents_config(config):
            raise HTTPException(status_code=500, detail="Failed to import configuration")
        
        return JSONResponse({
            "status": "success",
            "message": "Configuration imported successfully",
            "count": len(config)
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_id}/generate-task")
async def generate_task_code(agent_id: str):
    """Generate task registration code for an agent"""
    try:
        config = load_agents_config()
        
        if agent_id not in config:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        agent = config[agent_id]
        
        # Generate task code
        task_code = generate_agent_task_code(agent_id, agent)
        
        return JSONResponse({
            "status": "success",
            "agent_id": agent_id,
            "task_code": task_code,
            "filename": f"{agent_id}_task.py"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/generate-all-tasks")
async def generate_all_tasks_code():
    """Generate task registration code for all enabled agents"""
    try:
        config = load_agents_config()
        
        # Generate code for all enabled agents
        all_tasks_code = generate_all_agents_tasks_code(config)
        
        return JSONResponse({
            "status": "success",
            "task_code": all_tasks_code,
            "filename": "vera_agent_tasks.py",
            "agent_count": sum(1 for agent in config.values() if agent.get("enabled", True))
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# INITIALIZATION
# ============================================================================

print("[Agents API] Loaded")
print(f"  Default agents: {len(DEFAULT_AGENTS)}")
print(f"  Config file: {AGENTS_CONFIG_FILE}")
print(f"  Stats file: {AGENT_STATS_FILE}")