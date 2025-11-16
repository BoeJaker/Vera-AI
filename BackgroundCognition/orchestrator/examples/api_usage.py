"""
API usage examples for the Unified Orchestrator
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from fastapi import FastAPI
import uvicorn
from BackgroundCognition.orchestrator.api_integration import register_routes


def create_app():
    """Create FastAPI application with orchestrator routes"""
    app = FastAPI(
        title="Vera-AI Orchestrator API",
        description="Unified orchestration backend for compute tasks",
        version="2.0.0",
    )

    # Register orchestrator routes
    register_routes(app, prefix="/api/v2/orchestrator")

    # Add a simple root endpoint
    @app.get("/")
    async def root():
        return {
            "service": "Vera-AI Unified Orchestrator",
            "version": "2.0.0",
            "docs": "/docs",
            "api": "/api/v2/orchestrator",
        }

    return app


def main():
    """Run the API server"""
    app = create_app()

    print("=" * 60)
    print("Vera-AI Unified Orchestrator API Server")
    print("=" * 60)
    print("\nStarting server...")
    print("  URL: http://localhost:8500")
    print("  Docs: http://localhost:8500/docs")
    print("  API: http://localhost:8500/api/v2/orchestrator")
    print("\nPress Ctrl+C to stop\n")
    print("=" * 60)

    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8500,
        log_level="info",
    )


if __name__ == "__main__":
    main()
