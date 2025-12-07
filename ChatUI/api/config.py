"""
Configuration API Endpoints for Vera
Add these routes to your FastAPI application
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import yaml
import os
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api/config", tags=["config"])

# Track last reload time
_last_reload = None
_config_path = "Configuration/vera_config.yaml"


def load_config_file() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    global _last_reload
    
    try:
        config_path = Path(_config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {_config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        _last_reload = datetime.now().isoformat()
        return config
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")


def save_config_file(config: Dict[str, Any]) -> bool:
    """Save configuration to YAML file"""
    global _last_reload
    
    try:
        config_path = Path(_config_path)
        
        # Create backup
        if config_path.exists():
            backup_path = config_path.with_suffix('.yaml.bak')
            import shutil
            shutil.copy2(config_path, backup_path)
        
        # Save new config
        with open(config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        
        _last_reload = datetime.now().isoformat()
        return True
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@router.get("")
async def get_configuration():
    """
    Get current configuration
    
    Returns the entire configuration as JSON
    """
    config = load_config_file()
    
    return JSONResponse({
        "status": "success",
        "config": config,
        "last_reload": _last_reload
    })


@router.post("")
async def save_configuration(config: Dict[str, Any]):
    """
    Save configuration
    
    Saves the provided configuration to the YAML file
    """
    try:
        # Validate config structure (basic check)
        required_sections = ['ollama', 'models', 'memory', 'orchestrator', 'logging']
        for section in required_sections:
            if section not in config:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required section: {section}"
                )
        
        save_config_file(config)
        
        return JSONResponse({
            "status": "success",
            "message": "Configuration saved successfully",
            "last_reload": _last_reload
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@router.get("/status")
async def get_config_status():
    """
    Get configuration status
    
    Returns hot reload status and last reload time
    """
    config = load_config_file()
    
    return JSONResponse({
        "status": "success",
        "hot_reload_enabled": config.get("enable_hot_reload", False),
        "last_reload": _last_reload,
        "config_file": _config_path,
        "file_exists": Path(_config_path).exists()
    })


@router.get("/validate")
async def validate_configuration():
    """
    Validate current configuration
    
    Checks if all required fields are present and values are valid
    """
    config = load_config_file()
    errors = []
    warnings = []
    
    # Validate ollama section
    if 'ollama' in config:
        if not config['ollama'].get('api_url'):
            errors.append("ollama.api_url is required")
        if config['ollama'].get('timeout', 0) < 1:
            warnings.append("ollama.timeout should be at least 1 second")
    
    # Validate models section
    if 'models' in config:
        required_models = ['embedding_model', 'fast_llm', 'tool_llm']
        for model in required_models:
            if not config['models'].get(model):
                errors.append(f"models.{model} is required")
    
    # Validate memory section
    if 'memory' in config:
        if not config['memory'].get('neo4j_uri'):
            errors.append("memory.neo4j_uri is required")
    
    # Validate orchestrator section
    if 'orchestrator' in config:
        if not config['orchestrator'].get('redis_url'):
            errors.append("orchestrator.redis_url is required")
        
        worker_keys = ['llm_workers', 'tool_workers', 'background_workers']
        for key in worker_keys:
            if config['orchestrator'].get(key, 0) < 1:
                warnings.append(f"orchestrator.{key} should be at least 1")
    
    return JSONResponse({
        "status": "success" if not errors else "error",
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    })


@router.post("/reset")
async def reset_configuration():
    """
    Reset configuration to defaults
    
    Restores configuration from backup or default template
    """
    try:
        config_path = Path(_config_path)
        backup_path = config_path.with_suffix('.yaml.bak')
        
        if backup_path.exists():
            import shutil
            shutil.copy2(backup_path, config_path)
            return JSONResponse({
                "status": "success",
                "message": "Configuration restored from backup"
            })
        else:
            raise HTTPException(status_code=404, detail="No backup found")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")


@router.get("/export")
async def export_configuration():
    """
    Export configuration as downloadable file
    
    Returns the configuration as a YAML file
    """
    config = load_config_file()
    
    from fastapi.responses import Response
    
    yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False)
    
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f"attachment; filename=vera_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        }
    )


# =============================================================================
# Add to your main FastAPI app:
# =============================================================================
"""
from your_config_api import router as config_router

app = FastAPI()
app.include_router(config_router)
"""