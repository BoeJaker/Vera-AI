# execution_server.py
from fastapi import HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import docker
import asyncio
import subprocess
import os
from flask import Flask, request, jsonify, send_file
import subprocess, tempfile, os, shutil, pathlib

router = APIRouter(prefix="/api/execution", tags=["graph"])

class ExecuteRequest(BaseModel):
    code: str
    language: str
    useDocker: bool = True
    files: list = []

# Language configurations
LANGUAGE_CONFIG = {
    'python': {
        'image': 'python:3.11-slim',
        'command': ['python', '-c'],
        'file_ext': '.py'
    },
    'javascript': {
        'image': 'node:18-slim',
        'command': ['node', '-e'],
        'file_ext': '.js'
    },
    'cpp': {
        'image': 'gcc:latest',
        'command': ['sh', '-c', 'g++ -o /tmp/prog - && /tmp/prog'],
        'file_ext': '.cpp'
    },
    'rust': {
        'image': 'rust:latest',
        'command': ['sh', '-c', 'rustc - -o /tmp/prog && /tmp/prog'],
        'file_ext': '.rs'
    },
    'go': {
        'image': 'golang:latest',
        'command': ['sh', '-c', 'go run -'],
        'file_ext': '.go'
    }
}

@router.post("/execute")
async def execute_code(request: ExecuteRequest):
    """Execute code and return complete result"""
    if request.language not in LANGUAGE_CONFIG:
        raise HTTPException(400, f"Unsupported language: {request.language}")
    
    config = LANGUAGE_CONFIG[request.language]
    
    if request.useDocker:
        return execute_docker(request.code, config)
    else:
        return execute_local(request.code, config)

def execute_docker(code, config):
    """Execute code in Docker container"""
    client = docker.from_env()
    
    try:
        # Create container with resource limits
        container = client.containers.run(
            config['image'],
            command=config['command'] + [code],
            detach=True,
            mem_limit='256m',
            cpus=0.5,
            network_disabled=True,
            read_only=True,
            tmpfs={'/tmp': 'size=50m'},
            remove=False
        )
        
        # Wait for completion (with timeout)
        result = container.wait(timeout=30)
        
        # Get logs
        stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
        stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
        
        # Clean up
        container.remove()
        
        return {
            'stdout': stdout,
            'stderr': stderr,
            'exitCode': result['StatusCode'],
            'memory': '256m',
            'success': result['StatusCode'] == 0
        }
        
    except docker.errors.ContainerError as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'exitCode': e.exit_status,
            'error': 'Container error'
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'exitCode': 1,
            'error': str(e)
        }

def execute_local(code, config):
    """Execute code locally (UNSAFE - for trusted code only)"""
    try:
        # Create temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix=config['file_ext'], delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        # Execute
        if config['language'] == 'python':
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                timeout=30,
                text=True
            )
        elif config['language'] == 'javascript':
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                timeout=30,
                text=True
            )
        else:
            # Compilation required
            result = subprocess.run(
                config['command'],
                input=code,
                capture_output=True,
                timeout=30,
                text=True
            )
        
        # Clean up
        os.unlink(temp_file)
        
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exitCode': result.returncode,
            'success': result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        return {
            'stdout': '',
            'stderr': 'Execution timeout (30s)',
            'exitCode': 124,
            'error': 'Timeout'
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'exitCode': 1,
            'error': str(e)
        }

@router.get("/execute-stream")
async def execute_stream(code: str, language: str, useDocker: bool = True):
    """Execute code with streaming output (SSE)"""
    
    async def event_generator():
        if language not in LANGUAGE_CONFIG:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Unsupported language'})}\n\n"
            return
        
        config = LANGUAGE_CONFIG[language]
        
        if useDocker:
            # Docker streaming
            client = docker.from_env()
            try:
                container = client.containers.run(
                    config['image'],
                    command=config['command'] + [code],
                    detach=True,
                    mem_limit='256m',
                    network_disabled=True,
                    stream=True
                )
                
                # Stream logs
                for line in container.logs(stream=True, follow=True):
                    yield f"data: {json.dumps({'type': 'stdout', 'content': line.decode()})}\n\n"
                    await asyncio.sleep(0)
                
                result = container.wait()
                yield f"data: {json.dumps({'type': 'complete', 'exitCode': result['StatusCode']})}\n\n"
                container.remove()
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        else:
            # Local streaming
            try:
                process = subprocess.Popen(
                    config['command'] + [code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Stream stdout
                for line in process.stdout:
                    yield f"data: {json.dumps({'type': 'stdout', 'content': line})}\n\n"
                    await asyncio.sleep(0)
                
                process.wait(timeout=30)
                
                # Send stderr if any
                stderr = process.stderr.read()
                if stderr:
                    yield f"data: {json.dumps({'type': 'stderr', 'content': stderr})}\n\n"
                
                yield f"data: {json.dumps({'type': 'complete', 'exitCode': process.returncode})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ports endpoint - simple stub. On Linux replace with pyserial list_ports
@router.get("/ports")
def ports():
    # If you want real serial port enumeration install pyserial and use serial.tools.list_ports.comports()
    try:
        import serial.tools.list_ports as lp
        ports = []
        for p in lp.comports():
            ports.append({ "device": p.device, "description": p.description })
        return jsonify(ports)
    except Exception:
        # fallback stub
        return jsonify([])

# compile+flash using arduino-cli; returns JSON
@router.post("/flash")
def flash():
    data = request.get_json(force=True)
    code = data.get("code","")
    fqbn = data.get("fqbn")
    port = data.get("port")

    if not fqbn or not port:
        return jsonify({"error":"missing fqbn or port"}), 400

    tmpdir = tempfile.mkdtemp(prefix="sketch_")
    try:
        sketch_dir = os.path.join(tmpdir, "sketch")
        os.makedirs(sketch_dir, exist_ok=True)
        sketch_file = os.path.join(sketch_dir, "sketch.ino")
        with open(sketch_file, "w", encoding="utf-8") as f:
            f.write(code)

        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir, exist_ok=True)

        compile_cmd = ["arduino-cli", "compile", "--fqbn", fqbn, "--output-dir", out_dir, sketch_dir]
        proc = subprocess.run(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        if proc.returncode != 0:
            return jsonify({"error":"compile_failed", "stdout":proc.stdout, "stderr":proc.stderr}), 500

        # Upload using arduino-cli upload
        upload_cmd = ["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, sketch_dir]
        proc2 = subprocess.run(upload_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        if proc2.returncode != 0:
            return jsonify({"error":"upload_failed", "stdout":proc2.stdout, "stderr":proc2.stderr}), 500

        return jsonify({"stdout": proc2.stdout + "\n" + proc.stdout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

# wokwi embed proxy (optional) - proxies to local Wokwi embed bridge expected at http://localhost:9000/embed
@router.post("/wokwi/embed")
def wokwi_embed():
    # This endpoint expects the local wokwi-embed-bridge to be running.
    # The embed bridge example is at https://github.com/wokwi/wokwi-embed-bridge-example
    from urllib import request as urlreq, parse
    import json
    data = request.get_json(force=True)
    try:
        bridge_url = "http://localhost:9000/embed"  # adjust if you run the bridge elsewhere
        req = urlreq.Request(bridge_url, data=json.dumps(data).encode("utf-8"), headers={'Content-Type':'application/json'})
        resp = urlreq.urlopen(req, timeout=30)
        body = resp.read().decode('utf-8')
        return router.response_class(body, content_type=resp.headers.get('Content-Type','application/json'))
    except Exception as e:
        return jsonify({"error":"bridge_unreachable", "detail": str(e)}), 502


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(router, host="0.0.0.0", port=8000)