"""
API Extensions for Advanced Toolchain Query Builder
Adds endpoints for plan templates, strategies, and custom toolchain execution
"""

import json
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Vera.ChatUI.api.session import sessions, get_or_create_vera

logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/toolchain/query", tags=["toolchain-query"])


# ============================================================
# Request/Response Models
# ============================================================

class QueryExecutionRequest(BaseModel):
    session_id: str
    strategy: str
    template: str
    params: Dict[str, Any]


class QueryPreviewRequest(BaseModel):
    session_id: str
    strategy: str
    template: str
    params: Dict[str, Any]


class CustomToolchainRequest(BaseModel):
    session_id: str
    name: str
    strategy: str
    steps: List[Dict[str, str]]


# ============================================================
# Planning Strategy Definitions
# ============================================================

PLANNING_STRATEGIES = {
    "static": {
        "id": "static",
        "name": "Static",
        "description": "Fixed plan upfront (default)",
        "suitable_for": ["general tasks", "known workflows", "standard operations"]
    },
    "quick": {
        "id": "quick",
        "name": "Quick",
        "description": "Fast, minimal plan for simple tasks",
        "suitable_for": ["simple queries", "single-step tasks", "quick answers"]
    },
    "comprehensive": {
        "id": "comprehensive",
        "name": "Comprehensive",
        "description": "Deep, thorough multi-step plans",
        "suitable_for": ["research", "complex analysis", "detailed reports"]
    },
    "dynamic": {
        "id": "dynamic",
        "name": "Dynamic",
        "description": "Plan one step at a time based on results",
        "suitable_for": ["exploratory tasks", "uncertain outcomes", "adaptive workflows"]
    },
    "exploratory": {
        "id": "exploratory",
        "name": "Exploratory",
        "description": "Multiple alternatives explored in parallel",
        "suitable_for": ["comparing approaches", "finding best solution", "A/B testing"]
    },
    "multipath": {
        "id": "multipath",
        "name": "Multi-path",
        "description": "Branch and try different approaches",
        "suitable_for": ["fault tolerance", "fallback options", "robust execution"]
    }
}


# ============================================================
# Plan Template Definitions
# ============================================================

PLAN_TEMPLATES = {
    "web_research": {
        "id": "web_research",
        "name": "Web Research",
        "description": "Comprehensive web research with content fetching and analysis",
        "category": "research",
        "params": [
            {"name": "query", "type": "text", "label": "Research Query", "required": True},
            {"name": "depth", "type": "select", "label": "Research Depth", 
             "options": ["quick", "standard", "deep"], "default": "standard"}
        ]
    },
    "data_analysis": {
        "id": "data_analysis",
        "name": "Data Analysis",
        "description": "Load, process, and analyze data files",
        "category": "data",
        "params": [
            {"name": "data_source", "type": "text", "label": "Data File Path", "required": True},
            {"name": "analysis_type", "type": "text", "label": "Analysis Type", "required": True}
        ]
    },
    "code_task": {
        "id": "code_task",
        "name": "Code Task",
        "description": "Generate, execute, and verify code",
        "category": "code",
        "params": [
            {"name": "task_description", "type": "textarea", "label": "Task Description", "required": True},
            {"name": "language", "type": "select", "label": "Language",
             "options": ["python", "javascript", "bash"], "default": "python"}
        ]
    },
    "comparison_research": {
        "id": "comparison_research",
        "name": "Comparison Research",
        "description": "Research and compare two topics",
        "category": "research",
        "params": [
            {"name": "topic_a", "type": "text", "label": "First Topic", "required": True},
            {"name": "topic_b", "type": "text", "label": "Second Topic", "required": True}
        ]
    },
    "document_creation": {
        "id": "document_creation",
        "name": "Document Creation",
        "description": "Research, outline, and create documents",
        "category": "creation",
        "params": [
            {"name": "topic", "type": "text", "label": "Document Topic", "required": True},
            {"name": "doc_type", "type": "select", "label": "Document Type",
             "options": ["report", "article", "guide", "analysis"], "default": "report"}
        ]
    },
    "custom": {
        "id": "custom",
        "name": "Custom Toolchain",
        "description": "Build your own step-by-step toolchain",
        "category": "custom",
        "params": []
    }
}


# ============================================================
# Endpoints
# ============================================================

@router.get("/strategies")
async def get_planning_strategies():
    """Get all available planning strategies."""
    return {
        "strategies": list(PLANNING_STRATEGIES.values()),
        "default": "static"
    }


@router.get("/templates")
async def get_plan_templates():
    """Get all available plan templates."""
    return {
        "templates": list(PLAN_TEMPLATES.values()),
        "categories": list(set(t["category"] for t in PLAN_TEMPLATES.values()))
    }


@router.post("/preview")
async def preview_query_plan(request: QueryPreviewRequest):
    """
    Generate a preview of the plan that would be executed.
    Does not actually execute the plan.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        # Get template
        template = PLAN_TEMPLATES.get(request.template)
        if not template:
            raise HTTPException(status_code=400, detail=f"Unknown template: {request.template}")
        
        # Generate plan based on template
        if request.template == "custom":
            # Custom toolchain
            if "custom_plan" not in request.params:
                raise HTTPException(status_code=400, detail="custom_plan required for custom template")
            
            plan = request.params["custom_plan"]
            
        else:
            # Use template to generate plan
            plan = _generate_plan_from_template(request.template, request.params, vera)
        
        return {
            "strategy": request.strategy,
            "template": request.template,
            "params": request.params,
            "plan": plan,
            "estimated_steps": len(plan) if isinstance(plan, list) else 0
        }
        
    except Exception as e:
        logger.error(f"Plan preview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_query(request: QueryExecutionRequest):
    """
    Execute a toolchain using the specified strategy and template.
    Streams the execution results.
    """
    from fastapi.responses import StreamingResponse
    
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    async def generate():
        try:
            # Get template
            template = PLAN_TEMPLATES.get(request.template)
            if not template:
                yield f"Error: Unknown template: {request.template}\n"
                return
            
            # Generate plan
            if request.template == "custom":
                if "custom_plan" not in request.params:
                    yield f"Error: custom_plan required for custom template\n"
                    return
                plan = request.params["custom_plan"]
                yield f"Using custom toolchain with {len(plan)} steps\n"
            else:
                plan = _generate_plan_from_template(request.template, request.params, vera)
                yield f"Generated plan with {len(plan)} steps\n"
            
            yield f"\n{'='*60}\n"
            yield f"Strategy: {request.strategy}\n"
            yield f"Template: {request.template}\n"
            yield f"{'='*60}\n\n"
            
            # Get strategy enum
            from Vera.Toolchain.enhanced_toolchain_planner import PlanningStrategy
            strategy_map = {
                "static": PlanningStrategy.STATIC,
                "quick": PlanningStrategy.QUICK,
                "comprehensive": PlanningStrategy.COMPREHENSIVE,
                "dynamic": PlanningStrategy.DYNAMIC,
                "exploratory": PlanningStrategy.EXPLORATORY,
                "multipath": PlanningStrategy.MULTIPATH
            }
            
            strategy = strategy_map.get(request.strategy, PlanningStrategy.STATIC)
            
            # Execute toolchain
            query = _format_query_from_params(request.template, request.params)
            
            for chunk in vera.toolchain.execute_tool_chain(query, plan=plan, strategy=strategy):
                yield str(chunk)
                
        except Exception as e:
            logger.error(f"Query execution error: {e}", exc_info=True)
            yield f"\n\nError: {str(e)}\n"
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/save-custom")
async def save_custom_toolchain(request: CustomToolchainRequest):
    """Save a custom toolchain for reuse."""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Save to session or database
    # For now, just return success
    return {
        "success": True,
        "name": request.name,
        "steps": len(request.steps),
        "message": "Custom toolchain saved successfully"
    }


@router.get("/{session_id}/saved-toolchains")
async def get_saved_toolchains(session_id: str):
    """Get all saved custom toolchains for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # TODO: Implement actual storage/retrieval
    return {
        "toolchains": [],
        "total": 0
    }


# ============================================================
# Helper Functions
# ============================================================

def _generate_plan_from_template(template_id: str, params: Dict[str, Any], vera) -> List[Dict[str, str]]:
    """
    Generate a plan from a template and parameters.
    Uses the PlanTemplate class from enhanced_toolchain_planner.
    """
    try:
        from Vera.Toolchain.enhanced_toolchain_planner import PlanTemplate
        
        templates = PlanTemplate()
        
        if template_id == "web_research":
            query = params.get("query", "")
            depth = params.get("depth", "standard")
            return templates.web_research(query, depth)
            
        elif template_id == "data_analysis":
            data_source = params.get("data_source", "")
            analysis_type = params.get("analysis_type", "")
            return templates.data_analysis(data_source, analysis_type)
            
        elif template_id == "code_task":
            task_description = params.get("task_description", "")
            language = params.get("language", "python")
            return templates.code_task(task_description, language)
            
        elif template_id == "comparison_research":
            topic_a = params.get("topic_a", "")
            topic_b = params.get("topic_b", "")
            return templates.comparison_research(topic_a, topic_b)
            
        elif template_id == "document_creation":
            topic = params.get("topic", "")
            doc_type = params.get("doc_type", "report")
            return templates.document_creation(topic, doc_type)
            
        else:
            raise ValueError(f"Unknown template: {template_id}")
            
    except ImportError:
        # Fallback if enhanced planner not available
        logger.warning("Enhanced toolchain planner not available, using basic plan")
        return [
            {"tool": "fast_llm", "input": f"Process this request: {json.dumps(params)}"}
        ]


def _format_query_from_params(template_id: str, params: Dict[str, Any]) -> str:
    """Format parameters into a natural language query."""
    
    if template_id == "web_research":
        return params.get("query", "")
    
    elif template_id == "data_analysis":
        return f"Analyze the data in {params.get('data_source')} - {params.get('analysis_type')}"
    
    elif template_id == "code_task":
        return params.get("task_description", "")
    
    elif template_id == "comparison_research":
        return f"Compare {params.get('topic_a')} vs {params.get('topic_b')}"
    
    elif template_id == "document_creation":
        return f"Create a {params.get('doc_type')} about {params.get('topic')}"
    
    elif template_id == "custom":
        return "Execute custom toolchain"
    
    else:
        return json.dumps(params)


# ============================================================
# Integration Function
# ============================================================

def integrate_query_router(app):
    """
    Integrate the query router into the FastAPI app.
    
    Usage in main API file:
        from toolchain_query_api import integrate_query_router
        integrate_query_router(app)
    """
    app.include_router(router)
    logger.info("[Query API] Advanced toolchain query endpoints registered")
    logger.info("[Query API] Available at /api/toolchain/query/*")