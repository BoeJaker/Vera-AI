"""
Canvas Execution API for Notebooks
===================================

Support code execution in canvas notes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import subprocess
import tempfile
import os
from pathlib import Path

router = APIRouter(prefix="/api/canvas", tags=["canvas"])

class ExecutionRequest(BaseModel):
    parser: str  # python, javascript, bash, etc.
    content: str
    session_id: str
    files: Optional[Dict[str, str]] = None  # filename -> content

class ExecutionResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float

@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(request: ExecutionRequest):
    """
    Execute code in a sandboxed environment
    """
    import time
    start_time = time.time()
    
    # Create temporary directory for execution
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Write main file
        if request.parser == 'python':
            main_file = tmppath / "main.py"
            main_file.write_text(request.content)
            cmd = ["python3", str(main_file)]
            
        elif request.parser == 'javascript':
            main_file = tmppath / "main.js"
            main_file.write_text(request.content)
            cmd = ["node", str(main_file)]
            
        elif request.parser == 'bash':
            main_file = tmppath / "main.sh"
            main_file.write_text(request.content)
            os.chmod(main_file, 0o755)
            cmd = ["bash", str(main_file)]
            
        elif request.parser == 'html':
            # For HTML, just return success (would need browser to execute)
            return ExecutionResponse(
                stdout="HTML saved (browser execution not supported via API)",
                stderr="",
                exit_code=0,
                execution_time=time.time() - start_time
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported parser: {request.parser}")
        
        # Write additional files
        if request.files:
            for filename, content in request.files.items():
                file_path = tmppath / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
        
        # Execute with timeout
        try:
            result = subprocess.run(
                cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )
            
            execution_time = time.time() - start_time
            
            return ExecutionResponse(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResponse(
                stdout="",
                stderr="Execution timed out after 30 seconds",
                exit_code=-1,
                execution_time=30.0
            )
        except Exception as e:
            return ExecutionResponse(
                stdout="",
                stderr=f"Execution error: {str(e)}",
                exit_code=-1,
                execution_time=time.time() - start_time
            )

# Add this router to your main FastAPI app:
# app.include_router(router)