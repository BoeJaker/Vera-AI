"""
API Extensions for Advanced Toolchain Query Builder - ORCHESTRATOR INTEGRATED
Uses orchestrator task submission (like async_run) for agent routing
"""

import json
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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


# ============================================================
# Planning Strategy Definitions
# ============================================================

PLANNING_STRATEGIES = {
    "static": {
        "id": "static",
        "name": "Static",
        "description": "Fixed plan upfront (default)"
    },
    "quick": {
        "id": "quick",
        "name": "Quick",
        "description": "Fast, minimal plan for simple tasks"
    },
    "comprehensive": {
        "id": "comprehensive",
        "name": "Comprehensive",
        "description": "Deep, thorough multi-step plans"
    },
    "dynamic": {
        "id": "dynamic",
        "name": "Dynamic",
        "description": "Plan one step at a time based on results"
    },
    "exploratory": {
        "id": "exploratory",
        "name": "Exploratory",
        "description": "Multiple alternatives explored in parallel"
    },
    "multipath": {
        "id": "multipath",
        "name": "Multi-path",
        "description": "Branch and try different approaches"
    }
}


# ============================================================
# Plan Template Definitions
# ============================================================

PLAN_TEMPLATES = {
    "direct_prompt": {
        "id": "direct_prompt",
        "name": "Direct Prompt",
        "description": "Just describe what you want - AI creates the toolchain",
        "category": "direct",
        "params": [
            {"name": "query", "type": "textarea", "label": "What do you want to do?", "required": True}
        ]
    },
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
    """Generate a preview of the plan that would be executed."""
    logger.info(f"[Preview] Session: {request.session_id}, Template: {request.template}, Strategy: {request.strategy}")
    
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
            if "custom_plan" not in request.params:
                raise HTTPException(status_code=400, detail="custom_plan required for custom template")
            plan = request.params["custom_plan"]
            
        elif request.template == "direct_prompt":
            # For direct prompt, use simple fallback plan
            query = request.params.get("query", "")
            plan = [
                {"tool": "fast_llm", "input": f"Create a plan for: {query}"}
            ]
            logger.info(f"[Preview] Generated direct prompt plan with {len(plan)} steps")
            
        else:
            # Generate from template
            plan = _generate_plan_from_template(request.template, request.params, vera)
            logger.info(f"[Preview] Generated {request.template} plan with {len(plan)} steps")
        
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
    
    Uses orchestrator integration (like async_run) for:
    - Agent routing (tool-agent selection)
    - Parallel execution support
    - Proper resource management
    """
    logger.info(f"[Execute] Starting - Session: {request.session_id}, Template: {request.template}, Strategy: {request.strategy}")
    
    if request.session_id not in sessions:
        logger.error(f"[Execute] Session not found: {request.session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    logger.info(f"[Execute] Vera instance retrieved: {type(vera).__name__}")
    
    async def generate():
        # Check orchestrator availability inside the generator
        use_orchestrator = (
            hasattr(vera, 'orchestrator') and 
            vera.orchestrator and 
            hasattr(vera.orchestrator, 'running') and
            vera.orchestrator.running
        )
        
        logger.info(f"[Execute] Orchestrator available: {use_orchestrator}")
        
        try:
            logger.info(f"[Execute] Generator started")
            
            # Get template
            template = PLAN_TEMPLATES.get(request.template)
            if not template:
                error_msg = f"Error: Unknown template: {request.template}\n"
                logger.error(f"[Execute] {error_msg}")
                yield error_msg
                return
            
            logger.info(f"[Execute] Template found: {template['name']}")
            
            # Generate plan
            plan = None
            if request.template == "custom":
                if "custom_plan" not in request.params:
                    error_msg = "Error: custom_plan required for custom template\n"
                    logger.error(f"[Execute] {error_msg}")
                    yield error_msg
                    return
                plan = request.params["custom_plan"]
                yield f"Using custom toolchain with {len(plan)} steps\n"
                logger.info(f"[Execute] Using custom plan with {len(plan)} steps")
                
            elif request.template == "direct_prompt":
                # Direct prompt - let toolchain decide the plan
                query = request.params.get("query", "")
                yield f"Processing direct prompt: {query[:50]}...\n"
                logger.info(f"[Execute] Direct prompt mode: {query[:100]}")
                plan = None
                
            else:
                # Generate plan from template
                try:
                    plan = _generate_plan_from_template(request.template, request.params, vera)
                    yield f"Generated plan with {len(plan)} steps\n"
                    logger.info(f"[Execute] Generated plan: {json.dumps(plan, indent=2)}")
                except Exception as e:
                    error_msg = f"Error generating plan: {str(e)}\n"
                    logger.error(f"[Execute] {error_msg}", exc_info=True)
                    yield error_msg
                    return
            
            # Format query
            query = _format_query_from_params(request.template, request.params)
            logger.info(f"[Execute] Query: {query}")
            
            yield f"\n{'='*60}\n"
            yield f"Strategy: {request.strategy}\n"
            yield f"Template: {request.template}\n"
            yield f"Execution: {'Orchestrator (with agent routing)' if use_orchestrator else 'Direct (fallback)'}\n"
            yield f"{'='*60}\n\n"
            
            # ORCHESTRATOR INTEGRATION (like async_run)
            if use_orchestrator:
                logger.info(f"[Execute] Using orchestrator integration")
                
                try:
                    # Submit task to orchestrator (this will use agent routing via vera_tasks.py)
                    task_id = vera.orchestrator.submit_task(
                        "toolchain.execute",
                        vera_instance=vera,
                        query=query,
                        plan=plan,
                        strategy=request.strategy
                    )
                    
                    logger.info(f"[Execute] Task submitted to orchestrator: {task_id}")
                    yield f"Task submitted to orchestrator: {task_id}\n\n"
                    
                    # Stream results from orchestrator
                    chunk_count = 0
                    for chunk in vera.orchestrator.stream_result(task_id, timeout=300.0):
                        chunk_count += 1
                        chunk_str = str(chunk)
                        
                        if chunk_count <= 5:
                            logger.info(f"[Execute] Orchestrator chunk {chunk_count}: {chunk_str[:100]}")
                        
                        yield chunk_str
                    
                    logger.info(f"[Execute] Orchestrator execution complete - total chunks: {chunk_count}")
                
                except Exception as e:
                    logger.error(f"[Execute] Orchestrator execution failed: {e}", exc_info=True)
                    yield f"\nOrchestrator execution failed: {str(e)}\n"
                    yield f"Falling back to direct execution...\n\n"
                    use_orchestrator = False  # Fall through to direct execution
            
            # FALLBACK: Direct execution (if orchestrator unavailable or failed)
            if not use_orchestrator:
                logger.info(f"[Execute] Using direct execution (fallback)")
                
                chunk_count = 0
                try:
                    # Try with strategy parameter
                    logger.info(f"[Execute] Attempting execution with strategy parameter")
                    for chunk in vera.toolchain.execute_tool_chain(
                        query, 
                        plan=plan, 
                        strategy=request.strategy
                    ):
                        chunk_count += 1
                        chunk_str = str(chunk)
                        if chunk_count <= 5:
                            logger.info(f"[Execute] Direct chunk {chunk_count}: {chunk_str[:100]}")
                        yield chunk_str
                        
                except TypeError as e:
                    # Fallback if strategy not supported
                    logger.warning(f"[Execute] Toolchain doesn't support strategy parameter: {e}")
                    yield f"\nNote: Using fallback execution (strategy not supported)\n\n"
                    
                    chunk_count = 0
                    for chunk in vera.toolchain.execute_tool_chain(query, plan=plan):
                        chunk_count += 1
                        chunk_str = str(chunk)
                        if chunk_count <= 5:
                            logger.info(f"[Execute] Fallback chunk {chunk_count}: {chunk_str[:100]}")
                        yield chunk_str
                
                logger.info(f"[Execute] Direct execution complete - total chunks: {chunk_count}")
            
            yield f"\n\n{'='*60}\n"
            yield f"Execution completed successfully\n"
            yield f"{'='*60}\n"
                    
        except Exception as e:
            error_msg = f"\n\nError during execution: {str(e)}\n"
            logger.error(f"[Execute] {error_msg}", exc_info=True)
            yield error_msg
    
    logger.info(f"[Execute] Returning StreamingResponse")
    return StreamingResponse(generate(), media_type="text/plain")


# ============================================================
# Helper Functions
# ============================================================

def _generate_plan_from_template(template_id: str, params: Dict[str, Any], vera) -> List[Dict[str, str]]:
    """Generate a plan from a template and parameters."""
    logger.info(f"[PlanGen] Generating plan for template: {template_id}")
    logger.info(f"[PlanGen] Params: {json.dumps(params, indent=2)}")
    
    # Try to use PlanTemplate if available
    try:
        from Vera.Toolchain.enhanced_toolchain_planner import PlanTemplate
        logger.info(f"[PlanGen] Using PlanTemplate class")
        
        templates = PlanTemplate()
        
        if template_id == "web_research":
            query = params.get("query", "")
            depth = params.get("depth", "standard")
            plan = templates.web_research(query, depth)
            
        elif template_id == "data_analysis":
            data_source = params.get("data_source", "")
            analysis_type = params.get("analysis_type", "")
            plan = templates.data_analysis(data_source, analysis_type)
            
        elif template_id == "code_task":
            task_description = params.get("task_description", "")
            language = params.get("language", "python")
            plan = templates.code_task(task_description, language)
            
        elif template_id == "comparison_research":
            topic_a = params.get("topic_a", "")
            topic_b = params.get("topic_b", "")
            plan = templates.comparison_research(topic_a, topic_b)
            
        elif template_id == "document_creation":
            topic = params.get("topic", "")
            doc_type = params.get("doc_type", "report")
            plan = templates.document_creation(topic, doc_type)
            
        else:
            raise ValueError(f"Unknown template: {template_id}")
        
        logger.info(f"[PlanGen] Successfully generated plan with {len(plan)} steps")
        return plan
            
    except ImportError as e:
        # Fallback if enhanced planner not available
        logger.warning(f"[PlanGen] Enhanced toolchain planner not available: {e}, using fallback")
        return _generate_fallback_plan(template_id, params)


def _generate_fallback_plan(template_id: str, params: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate a simple fallback plan when PlanTemplate is not available."""
    logger.info(f"[PlanGen] Generating fallback plan for {template_id}")
    
    if template_id == "web_research":
        query = params.get("query", "")
        return [
            {"tool": "web_search", "input": query},
            {"tool": "fast_llm", "input": f"Analyze and summarize: {{prev}}"}
        ]
    
    elif template_id == "code_task":
        task = params.get("task_description", "")
        return [
            {"tool": "fast_llm", "input": f"Write code for: {task}"},
            {"tool": "python_repl", "input": "{prev}"}
        ]
    
    elif template_id == "data_analysis":
        data_source = params.get("data_source", "")
        analysis = params.get("analysis_type", "")
        return [
            {"tool": "fast_llm", "input": f"Analyze {data_source}: {analysis}"}
        ]
    
    else:
        # Generic fallback
        query_text = json.dumps(params)
        return [
            {"tool": "fast_llm", "input": f"Process this request: {query_text}"}
        ]


def _format_query_from_params(template_id: str, params: Dict[str, Any]) -> str:
    """Format parameters into a natural language query."""
    logger.info(f"[QueryFormat] Formatting query for {template_id}")
    
    if template_id == "direct_prompt":
        return params.get("query", "")
    
    elif template_id == "web_research":
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
    """Integrate the query router into the FastAPI app."""
    app.include_router(router)
    logger.info("[Query API] Advanced toolchain query endpoints registered")
    logger.info("[Query API] Available at /api/toolchain/query/*")
    logger.info("[Query API] Using orchestrator integration (like async_run)")