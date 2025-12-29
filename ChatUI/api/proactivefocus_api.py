# ============================================================
# Imports
# ============================================================
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
# ============================================================
# Internal dependencies (adjust paths as needed)
# ============================================================
from Vera.ChatUI.api.session import sessions, get_or_create_vera, vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections

# Enhanced API Endpoints for Proactive Focus Manager
# Add these to your existing focus.py router

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import time
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import time
import re  # Add this if not already there
# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/focus", tags=["focus"])
wsrouter = APIRouter(prefix="/ws/focus", tags=["wsfocus"])



# Try to import enhancement modules with graceful fallback
try:
    from Vera.ProactiveFocus.manager import (
        ResourceMonitor, ResourceLimits, ResourcePriority,
        PauseController, AdaptiveScheduler
    )
    RESOURCE_MANAGER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Resource manager not available: {e}")
    RESOURCE_MANAGER_AVAILABLE = False
    ResourceMonitor = None
    ResourceLimits = None
    ResourcePriority = None

try:
    from Vera.ProactiveFocus.resources import (
        ExternalResourceManager, ResourceType, NotebookResource
    )
    EXTERNAL_RESOURCES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"External resources not available: {e}")
    EXTERNAL_RESOURCES_AVAILABLE = False
    ExternalResourceManager = None

try:
    from Vera.ProactiveFocus.stages import StageOrchestrator
    STAGES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Stages not available: {e}")
    STAGES_AVAILABLE = False
    StageOrchestrator = None

try:
    from Vera.ProactiveFocus.calendar import CalendarScheduler, ProactiveThoughtEvent
    CALENDAR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Calendar not available: {e}")
    CALENDAR_AVAILABLE = False
    CalendarScheduler = None

try:
    from Vera.ProactiveFocus.service import BackgroundService, ServiceConfig
    BACKGROUND_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Background service not available: {e}")
    BACKGROUND_SERVICE_AVAILABLE = False
    BackgroundService = None




# ============================================================
# Request/Response Models
# ============================================================

class BackgroundConfigRequest(BaseModel):
    mode: str  # 'off', 'manual', 'scheduled', 'continuous'
    interval: Optional[int] = None
    start_time: Optional[str] = None  # "09:00"
    end_time: Optional[str] = None    # "17:00"

class EntityReferenceRequest(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    metadata: Optional[dict] = None

class ToolExecutionRequest(BaseModel):
    category: str
    item_index: int
    tool_name: str
    tool_input: Optional[dict] = None

class EnrichItemRequest(BaseModel):
    category: str
    item_index: int
    auto_discover: bool = True

# ============================================================
# Background Control Endpoints
# ============================================================

@router.post("/{session_id}/background/config")
async def configure_background_mode(session_id: str, config: BackgroundConfigRequest):
    """Configure background thinking mode and schedule."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    from proactive_focus_manager_enhanced import BackgroundMode
    
    try:
        mode = BackgroundMode(config.mode)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode. Must be one of: {[m.value for m in BackgroundMode]}"
        )
    
    vera.focus_manager.set_background_mode(
        mode=mode,
        interval=config.interval,
        start_time=config.start_time,
        end_time=config.end_time
    )
    
    return {
        "status": "success",
        "mode": mode.value,
        "interval": vera.focus_manager.proactive_interval,
        "schedule": {
            "start": config.start_time,
            "end": config.end_time
        }
    }

@router.post("/{session_id}/background/pause")
async def pause_background(session_id: str):
    """Temporarily pause background thinking."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    vera.focus_manager.pause_background()
    
    return {"status": "paused"}

@router.post("/{session_id}/background/resume")
async def resume_background(session_id: str):
    """Resume paused background thinking."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    vera.focus_manager.resume_background()
    
    return {"status": "resumed"}

# @router.get("/{session_id}/background/status")
# async def get_background_status(session_id: str):
#     """Get current background thinking status and configuration."""
#     if session_id not in sessions:
#         raise HTTPException(status_code=404, detail="Session not found")
    
#     vera = get_or_create_vera(session_id)
    
#     if not hasattr(vera, 'focus_manager'):
#         raise HTTPException(status_code=400, detail="Focus manager not available")
    
#     fm = vera.focus_manager
#     next_run = fm.get_next_scheduled_run()
    
#     return {
#         "mode": fm.background_mode.value,
#         "running": fm.running,
#         "paused": not fm.pause_event.is_set(),
#         "interval": fm.proactive_interval,
#         "cpu_threshold": fm.cpu_threshold,
#         "schedule": {
#             "start_time": str(fm.schedule_start_time) if fm.schedule_start_time else None,
#             "end_time": str(fm.schedule_end_time) if fm.schedule_end_time else None,
#             "within_schedule": fm.is_within_schedule(),
#             "next_run": next_run.isoformat() if next_run else None
#         }
#     }

# ============================================================
# Entity Reference Endpoints
# ============================================================

@router.get("/{session_id}/entities/discover")
async def discover_related_entities(session_id: str):
    """Discover entities related to current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    entities = vera.focus_manager.discover_related_entities()
    
    # Convert EntityReference objects to dicts
    serialized = {}
    for entity_type, refs in entities.items():
        serialized[entity_type] = [ref.to_dict() for ref in refs]
    
    return {
        "status": "success",
        "entities": serialized,
        "total": sum(len(refs) for refs in entities.values())
    }

@router.get("/{session_id}/entities/{entity_id}/content")
async def get_entity_content(session_id: str, entity_id: str, max_length: int = 500):
    """Get content/summary for a specific entity."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Check if entity is in cache
    if entity_id not in vera.focus_manager._entity_cache:
        raise HTTPException(status_code=404, detail="Entity not found in cache")
    
    entity_ref = vera.focus_manager._entity_cache[entity_id]
    content = vera.focus_manager.get_entity_content(entity_ref, max_length=max_length)
    
    return {
        "entity_id": entity_id,
        "entity_type": entity_ref.entity_type,
        "name": entity_ref.name,
        "content": content
    }

@router.post("/{session_id}/board/item/enrich")
async def enrich_board_item(session_id: str, request: EnrichItemRequest):
    """Enrich a focus board item with entity references."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    if request.category not in fm.focus_board:
        raise HTTPException(status_code=400, detail=f"Invalid category: {request.category}")
    
    items = fm.focus_board[request.category]
    if request.item_index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    
    item = items[request.item_index]
    fm.enrich_item_with_entities(item, auto_discover=request.auto_discover)
    
    return {
        "status": "enriched",
        "item": item.to_dict()
    }

# ============================================================
# Tool Integration Endpoints
# ============================================================

@router.get("/{session_id}/tools/available")
async def get_available_tools(session_id: str, refresh: bool = False):
    """Get list of available tools."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if refresh:
        vera.focus_manager.refresh_available_tools()
    
    return {
        "tools": vera.focus_manager._available_tools,
        "total": len(vera.focus_manager._available_tools)
    }

@router.post("/{session_id}/board/item/suggest-tools")
async def suggest_tools_for_item(session_id: str, request: dict):
    """Suggest relevant tools for a focus board item."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    category = request.get("category")
    item_index = request.get("item_index")
    
    if not category or item_index is None:
        raise HTTPException(status_code=400, detail="Category and item_index required")
    
    fm = vera.focus_manager
    
    if category not in fm.focus_board:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    items = fm.focus_board[category]
    if item_index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    
    item = items[item_index]
    
    # Run in background thread to avoid blocking
    import threading
    
    def suggest():
        fm.suggest_tools_for_item(item)
    
    thread = threading.Thread(target=suggest, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "message": "Tool suggestion generation started"
    }

@router.post("/{session_id}/tools/execute")
async def execute_tool_for_item(session_id: str, request: ToolExecutionRequest):
    """Execute a specific tool for a focus board item."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    if request.category not in fm.focus_board:
        raise HTTPException(status_code=400, detail=f"Invalid category: {request.category}")
    
    items = fm.focus_board[request.category]
    if request.item_index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    
    item = items[request.item_index]
    
    # Execute tool in background thread
    import threading
    
    result_container = {"result": None, "error": None}
    
    def execute():
        try:
            result = fm.execute_tool_for_item(
                item, 
                request.tool_name, 
                request.tool_input
            )
            result_container["result"] = result
        except Exception as e:
            result_container["error"] = str(e)
    
    thread = threading.Thread(target=execute, daemon=True)
    thread.start()
    thread.join(timeout=30)  # Wait up to 30 seconds
    
    if result_container["error"]:
        raise HTTPException(status_code=500, detail=result_container["error"])
    
    return {
        "status": "executed",
        "tool": request.tool_name,
        "result": result_container["result"],
        "item": item.to_dict()
    }

@router.get("/{session_id}/tools/usage-history")
async def get_tool_usage_history(session_id: str, limit: int = 20):
    """Get tool usage history."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    history = vera.focus_manager._tool_usage_history[-limit:]
    
    return {
        "history": history,
        "total": len(vera.focus_manager._tool_usage_history)
    }

# ============================================================
# Enhanced Board Retrieval
# ============================================================

@router.get("/{session_id}/board/enhanced")
async def get_enhanced_board(session_id: str, include_content: bool = False):
    """Get focus board with full entity references and tool suggestions."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    # Serialize board with all enhancements
    board = {}
    for category, items in fm.focus_board.items():
        board[category] = []
        for item in items:
            item_dict = item.to_dict()
            
            # Optionally fetch content for entity refs
            if include_content:
                for ref in item.entity_refs:
                    if not ref.content_summary:
                        content = fm.get_entity_content(ref, max_length=200)
                        if content:
                            ref.content_summary = content
                
                # Update dict with content
                item_dict["entity_refs"] = [ref.to_dict() for ref in item.entity_refs]
            
            board[category].append(item_dict)
    
    return {
        "focus": fm.focus,
        "project_id": fm.project_id,
        "board": board,
        "related_entities": {
            "sessions": list(fm._related_sessions),
            "notebooks": list(fm._related_notebooks),
            "folders": list(fm._related_folders)
        },
        "stats": {
            "total_items": sum(len(items) for items in fm.focus_board.values()),
            "total_entity_refs": sum(
                len(item.entity_refs) 
                for items in fm.focus_board.values() 
                for item in items
            ),
            "tools_used": len(fm._tool_usage_history)
        }
    }


# ============================================================
# Proactive Focus Manager Endpoints
# ============================================================

@router.get("/{session_id}/boards/list")
async def list_focus_boards(session_id: str):
    """Get list of all saved focus board files."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    try:
        boards = vera.focus_manager.list_saved_boards()
        
        return {
            "status": "success",
            "boards": boards,
            "total": len(boards)
        }
    except Exception as e:
        logger.error(f"Failed to list focus boards: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list boards: {str(e)}")


@router.post("/{session_id}/boards/load")
async def load_focus_board_file(session_id: str, request: dict):
    """Load a focus board from file."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    filename = request.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
    
    try:
        success = vera.focus_manager.load_focus_board(filename)
        
        if not success:
            return {
                "status": "error",
                "message": f"Focus board not found: {filename}"
            }
        
        # Broadcast the loaded state
        vera.focus_manager._broadcast_sync("focus_loaded", {
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "filename": filename
        })
        
        return {
            "status": "success",
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "project_id": vera.focus_manager.project_id,
            "filename": filename
        }
        
    except Exception as e:
        logger.error(f"Failed to load focus board: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load: {str(e)}")


@router.delete("/{session_id}/boards/delete")
async def delete_focus_board_file(session_id: str, request: dict):
    """Delete a saved focus board file."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    filename = request.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
    
    try:
        import os
        filepath = os.path.join(vera.focus_manager.focus_boards_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                "status": "error",
                "message": f"File not found: {filename}"
            }
        
        # Delete the file
        os.remove(filepath)
        
        logger.info(f"Deleted focus board file: {filepath}")
        
        return {
            "status": "success",
            "message": f"Deleted: {filename}"
        }
        
    except Exception as e:
        logger.error(f"Failed to delete focus board: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")
    
@router.get("/{session_id}")
async def get_focus_status(session_id: str):
    '''Get current focus manager status.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        return {
            "focus": None,
            "focus_board": {},
            "running": False
        }
    
    fm = vera.focus_manager
    
    return {
        "focus": fm.focus,
        "focus_board": fm.focus_board,
        "running": fm.running,
        "latest_conversation": fm.latest_conversation,
        "proactive_interval": fm.proactive_interval,
        "cpu_threshold": fm.cpu_threshold
    }


def set_focus(self, focus: str, project_name: Optional[str] = None, create_project: bool = True):
    """Set focus and optionally link to a project in hybrid memory."""
    
    # Check if we already have a saved board for this focus
    existing_board = self._find_matching_focus_board(focus)
    
    if existing_board:
        print(f"[FocusManager] Found existing focus board: {existing_board['filename']}")
        # Load the existing board
        if self.load_focus_board(existing_board['filename']):
            print(f"[FocusManager] Loaded existing focus board for: {focus}")
            self._broadcast_sync("focus_changed", {
                "focus": focus, 
                "project_id": self.project_id,
                "loaded_existing": True,
                "filename": existing_board['filename']
            })
            return
    
    # No existing board found, set new focus and clear board
    old_focus = self.focus
    
    # Save current board if there was a previous focus
    if old_focus and old_focus != focus:
        print(f"[FocusManager] Saving previous focus: {old_focus}")
        self.save_focus_board()
    
    # Set new focus
    self.focus = focus
    
    # Clear the focus board for new focus
    self.focus_board = {
        "progress": [],
        "next_steps": [],
        "issues": [],
        "ideas": [],
        "actions": [],
        "completed": []
    }
    
    print(f"[FocusManager] Focus set to: {focus} (new board)")
    
    # Create or link to project in hybrid memory
    if self.hybrid_memory and (project_name or create_project):
        project_name = project_name or focus
        self.project_id = self._ensure_project(project_name, focus)
        print(f"[FocusManager] Linked to project: {self.project_id}")
    
    # Store in agent memory with sanitized metadata
    metadata = {"topic": "focus"}
    if self.project_id:
        metadata["project_id"] = self.project_id
    
    self.agent.mem.add_session_memory(
        self.agent.sess.id, 
        f"[FocusManager] Focus set to: {focus}", 
        "Thought", 
        metadata
    )
    
    # Auto-save the new empty board
    filepath = self.save_focus_board()
    print(f"[FocusManager] Auto-saved new focus board: {filepath}")
    
    # Broadcast focus change
    self._broadcast_sync("focus_changed", {
        "focus": focus, 
        "project_id": self.project_id,
        "loaded_existing": False,
        "filepath": filepath
    })

@router.post("/{session_id}/clear")
async def clear_focus(session_id: str):
    '''Clear the current focus.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    vera.focus_manager.clear_focus()
    
    return {"status": "success", "focus": None}

@router.post("/{session_id}/set")
async def set_focus(session_id: str, request: dict):
    '''Set the focus for proactive thinking.'''
    logger.info(f"set_focus called for session: {session_id}")
    
    if session_id not in sessions:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        logger.error("Focus manager not available")
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    focus_text = request.get("focus", "")
    force_new = request.get("force_new", False)  # NEW: Check if user wants to force create new
    
    if not focus_text:
        raise HTTPException(status_code=400, detail="Focus text required")
    
    try:
        logger.info(f"Setting focus to: {focus_text} (force_new={force_new})")
        
        if force_new:
            # Force create new focus - skip the existing board check
            old_focus = vera.focus_manager.focus
            
            # Save current board if there was a previous focus
            if old_focus and old_focus != focus_text:
                logger.info(f"Saving previous focus: {old_focus}")
                vera.focus_manager.save_focus_board()
            
            # Set new focus and clear board
            vera.focus_manager.focus = focus_text
            vera.focus_manager.focus_board = {
                "progress": [],
                "next_steps": [],
                "issues": [],
                "ideas": [],
                "actions": [],
                "completed": []
            }
            
            logger.info(f"Created new focus: {focus_text}")
            
            # Create or link to project if available
            if vera.focus_manager.hybrid_memory:
                project_name = focus_text
                vera.focus_manager.project_id = vera.focus_manager._ensure_project(project_name, focus_text)
                logger.info(f"Linked to project: {vera.focus_manager.project_id}")
            
            # Store in agent memory
            metadata = {"topic": "focus"}
            if vera.focus_manager.project_id:
                metadata["project_id"] = vera.focus_manager.project_id
            
            vera.mem.add_session_memory(
                vera.sess.id, 
                f"[FocusManager] Created new focus: {focus_text}", 
                "Thought", 
                metadata
            )
            
            # Auto-save the new empty board
            filepath = vera.focus_manager.save_focus_board()
            logger.info(f"Auto-saved new focus board: {filepath}")
            
            # Broadcast focus change
            vera.focus_manager._broadcast_sync("focus_changed", {
                "focus": focus_text, 
                "project_id": vera.focus_manager.project_id,
                "loaded_existing": False,
                "force_new": True,
                "filepath": filepath
            })
        else:
            # Use existing set_focus method (which checks for existing boards)
            vera.focus_manager.set_focus(focus_text)
        
        return {
            "status": "success",
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "force_new": force_new
        }
    except Exception as e:
        logger.error(f"Error setting focus: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to set focus: {str(e)}")

@router.post("/{session_id}/board/add")
async def add_to_focus_board(
    session_id: str, 
    category: str = Body(..., embed=True),
    note: str = Body(..., embed=True),
    metadata: dict = Body(default={}, embed=True)
):
    """Add item to focus board."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    # Validate category
    if category not in fm.focus_board:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    try:
        # Create item with timestamp
        item = {
            "note": note,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata
        }
        
        # Add to board
        fm.focus_board[category].append(item)
        
        logger.info(f"Added to {category}: {note[:50]}...")
        
        # Store in hybrid memory if available
        if fm.hybrid_memory and fm.project_id:
            item_id = f"focus_item_{category}_{int(time.time()*1000)}"
            category_label = ''.join(word.capitalize() for word in category.split('_'))
            
            fm.hybrid_memory.upsert_entity(
                entity_id=item_id,
                etype="focus_item",
                labels=["FocusItem", category_label],
                properties={
                    "category": category,
                    "note": note,
                    "project_id": fm.project_id,
                    **metadata
                }
            )
            fm.hybrid_memory.link(fm.project_id, item_id, f"HAS_{category.upper()}")
        
        # Broadcast update
        fm._broadcast_sync("board_updated", {
            "category": category,
            "item": item,
            "focus_board": fm.focus_board
        })
        
        # Auto-save
        fm.save_focus_board()
        
        return {
            "status": "success",
            "category": category,
            "item": item,
            "focus_board": fm.focus_board
        }
        
    except Exception as e:
        logger.error(f"Failed to add board item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add: {str(e)}")

@staticmethod
def _to_camel_case(text: str) -> str:
    """
    Convert text to valid Neo4j label (CamelCase, alphanumeric only).
    
    Neo4j label requirements:
    - Must start with a letter
    - Can only contain letters, numbers, and underscores
    - Best practice: Use CamelCase without underscores
    
    Examples:
        'next_steps' -> 'NextSteps'
        'action-items' -> 'ActionItems'
        'ideas!' -> 'Ideas'
        '123test' -> 'Test123'
        '' -> 'UnknownCategory'
    """
    if not text or not isinstance(text, str):
        return "UnknownCategory"
    
    # Remove all non-alphanumeric characters except spaces and underscores
    # This handles punctuation, special chars, etc.
    cleaned = re.sub(r'[^a-zA-Z0-9\s_]', '', text)
    
    # Split on underscores, spaces, and hyphens
    words = re.split(r'[\s_-]+', cleaned)
    
    # Filter out empty strings and capitalize each word
    words = [word.capitalize() for word in words if word]
    
    if not words:
        return "UnknownCategory"
    
    result = ''.join(words)
    
    # Ensure it starts with a letter (Neo4j requirement)
    if result and not result[0].isalpha():
        result = 'Category' + result
    
    # Fallback for edge cases
    return result if result else "UnknownCategory"


@router.post("/{session_id}/board/clear")
async def clear_focus_board_category(session_id: str, request: dict):
    '''Clear a specific category on the focus board.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    category = request.get("category")
    if not category:
        raise HTTPException(status_code=400, detail="Category required")
    
    # Clear the category
    if category in vera.focus_manager.focus_board:
        vera.focus_manager.focus_board[category] = []
    
    # Broadcast update
    if hasattr(vera.focus_manager, '_broadcast_sync'):
        vera.focus_manager._broadcast_sync("board_updated", {
            "focus_board": vera.focus_manager.focus_board
        })
    
    return {
        "status": "success",
        "category": category,
        "focus_board": vera.focus_manager.focus_board
    }

@router.delete("/{session_id}/board/delete")
async def delete_board_item(session_id: str, request: dict):
    """Delete a specific item from the focus board by index."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    category = request.get("category")
    index = request.get("index")
    
    if not category:
        raise HTTPException(status_code=400, detail="Category required")
    if index is None:
        raise HTTPException(status_code=400, detail="Index required")
    
    fm = vera.focus_manager
    
    # Validate category exists
    if category not in fm.focus_board:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    items = fm.focus_board[category]
    
    # Validate index
    if index < 0 or index >= len(items):
        raise HTTPException(status_code=404, detail=f"Item index {index} not found in {category}")
    
    try:
        # Remove the item
        deleted_item = items.pop(index)
        
        logger.info(f"Deleted item {index} from {category}: {deleted_item}")
        
        # Broadcast update
        fm._broadcast_sync("board_updated", {
            "category": category,
            "action": "deleted",
            "index": index,
            "focus_board": fm.focus_board
        })
        
        # Auto-save
        fm.save_focus_board()
        
        return {
            "status": "success",
            "category": category,
            "deleted_index": index,
            "focus_board": fm.focus_board
        }
        
    except Exception as e:
        logger.error(f"Failed to delete board item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")

# @app.get("/api/focus/{session_id}/start")
# async def start_proactive_thought(session_id: str):
#     """Start the proactive focus manager."""
#     if session_id not in sessions:
#         raise HTTPException(status_code=404, detail="Session not found")
    
#     vera = get_or_create_vera(session_id)
    
#     if not hasattr(vera, 'focus_manager'):
#         raise HTTPException(status_code=400, detail="Focus manager not available")
    
#     vera.focus_manager.iterative_workflow( 
#         max_iterations = None, 
#         iteration_interval = 600,
#         auto_execute = True
#         # stream_output = True
#     )
    
#     return {
#         "status": "started",
#         "focus": vera.focus_manager.focus
#     }


@router.post("/{session_id}/stop")
async def stop_proactive_thought(session_id: str):
    """Stop the proactive focus manager."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Stop the focus manager
    vera.focus_manager.running = False
    
    # Broadcast update
    if hasattr(vera.focus_manager, '_broadcast_sync'):
        vera.focus_manager._broadcast_sync("focus_stopped", {
            "focus": vera.focus_manager.focus
        })
    
    return {
        "status": "stopped",
        "focus": vera.focus_manager.focus
    }


@router.get("/{session_id}/start")
async def start_proactive_thought(session_id: str):
    """Start the proactive focus manager."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Remove the invalid stream_output parameter
    vera.focus_manager.start_workflow_thread(
        max_iterations=None, 
        iteration_interval=600,
        auto_execute=True
    )
    
    return {
        "status": "started",
        "focus": vera.focus_manager.focus
    }


@router.post("/{session_id}/trigger")
async def trigger_proactive_thought(session_id: str):
    """Manually trigger a proactive thought generation."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Use the new async trigger method
    vera.focus_manager.trigger_proactive_thought_async()
    
    return {
        "status": "triggered",
        "message": "Proactive thought generation started"
    }
# ============================================================
# Granular Workflow Stage Control Endpoints
# ============================================================

@router.post("/{session_id}/stage/ideas")
async def run_ideas_stage(session_id: str, request: dict = None):
    """Generate ideas for the current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Run in background thread
    import threading
    
    def run():
        context = request.get("context") if request else None
        vera.focus_manager.generate_ideas_stage(context=context)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "ideas"
    }


@router.post("/{session_id}/stage/next_steps")
async def run_next_steps_stage(session_id: str, request: dict = None):
    """Generate next steps for the current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Run in background thread
    import threading
    
    def run():
        context = request.get("context") if request else None
        vera.focus_manager.generate_next_steps_stage(context=context)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "next_steps"
    }


@router.post("/{session_id}/stage/actions")
async def run_actions_stage(session_id: str, request: dict = None):
    """Generate actions for the current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Run in background thread
    import threading
    
    def run():
        context = request.get("context") if request else None
        vera.focus_manager.generate_actions_stage(context=context)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "actions"
    }


@router.post("/{session_id}/stage/execute")
async def run_execute_stage(session_id: str, request: dict = None):
    """Execute actions from the focus board."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Get parameters
    max_executions = request.get("max_executions", 2) if request else 2
    priority_filter = request.get("priority", "high") if request else "high"
    
    # Run in background thread
    import threading
    
    def run():
        vera.focus_manager.execute_actions_stage(
            max_executions=max_executions,
            priority_filter=priority_filter
        )
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "execute",
        "max_executions": max_executions,
        "priority": priority_filter
    }


@router.post("/{session_id}/action/execute")
async def execute_single_action(session_id: str, request: dict):
    """Execute a single action directly."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    action = request.get("action")
    if not action:
        raise HTTPException(status_code=400, detail="Action required")
    
    # Run in background thread
    import threading
    
    def run():
        try:
            logger.info(f"Executing single action: {action.get('description', '')}")
            result = vera.focus_manager.handoff_to_toolchain(action)
            logger.info(f"Action execution result: {result}")
        except Exception as e:
            logger.error(f"Error executing action: {e}", exc_info=True)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "action": action.get("description", str(action))
    }


@router.post("/{session_id}/stage/stop")
async def stop_stage(session_id: str):
    """Stop any running stage (best effort - threads may not stop immediately)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Broadcast stop signal
    vera.focus_manager._broadcast_sync("stage_stopped", {
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "status": "stop_requested",
        "message": "Stop signal sent (active stages will complete their current operation)"
    }

@wsrouter.websocket("/{session_id}")
async def websocket_focus(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time focus manager updates."""
    await websocket.accept()

    if session_id not in sessions:
        try:
            await websocket.send_json({"type": "error", "message": "Invalid session"})
        except Exception:
            pass
        try:
            await websocket.close()
        except RuntimeError:
            # websocket already closed — safe to ignore
            pass
        return

    vera = get_or_create_vera(session_id)

    if not hasattr(vera, "focus_manager"):
        await websocket.send_json({"type": "error", "error": "Focus manager not available"})
        await websocket.close()
        return

    # Register websocket for focus updates
    if not hasattr(vera.focus_manager, "_websockets"):
        vera.focus_manager._websockets = []
    vera.focus_manager._websockets.append(websocket)

    # Send initial state
    try:
        await websocket.send_json({
            "type": "focus_status",
            "data": {
                "focus": vera.focus_manager.focus,
                "focus_board": vera.focus_manager.focus_board,
                "running": vera.focus_manager.running,
            },
        })
    except RuntimeError:
        # Socket closed before first send
        return

    try:
        # Keep connection alive, only send updates on changes
        last_state = {
            "focus": vera.focus_manager.focus,
            "focus_board": json.dumps(vera.focus_manager.focus_board),
            "running": vera.focus_manager.running,
        }

        while True:
            await asyncio.sleep(5)  # check every 5 seconds

            current_state = {
                "focus": vera.focus_manager.focus,
                "focus_board": json.dumps(vera.focus_manager.focus_board),
                "running": vera.focus_manager.running,
            }

            if current_state != last_state:
                try:
                    # Only send if still connected
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "focus_status",
                            "data": {
                                "focus": vera.focus_manager.focus,
                                "focus_board": vera.focus_manager.focus_board,
                                "running": vera.focus_manager.running,
                            },
                        })
                        last_state = current_state
                    else:
                        logger.info(f"WebSocket closed for {session_id}, exiting loop")
                        break
                except (RuntimeError, WebSocketDisconnect):
                    logger.info(f"WebSocket send failed, exiting loop: {session_id}")
                    break

    except WebSocketDisconnect:
        logger.info(f"Focus WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Focus WebSocket error: {e}", exc_info=True)
    finally:
        if websocket in getattr(vera.focus_manager, "_websockets", []):
            vera.focus_manager._websockets.remove(websocket)

@router.get("/{session_id}/save")
async def save_focus_state(session_id: str):
    """Save current focus and board state to memory AND file."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    try:
        # Save to file system using FocusManager's method
        filepath = fm.save_focus_board()  # <-- ADD THIS LINE
        
        # Also save to Neo4j memory (keep existing behavior)
        focus_state = {
            "focus": fm.focus,
            "focus_board": fm.focus_board,
            "running": fm.running,
            "saved_at": datetime.utcnow().isoformat()
        }
        
        vera.mem.add_session_memory(
            vera.sess.id,
            json.dumps(focus_state, indent=2),
            "FocusState",
            {
                "topic": "focus_state",
                "focus": fm.focus or "none",
                "saved_at": focus_state["saved_at"],
                "filepath": filepath  # <-- ADD THIS TOO
            },
            promote=True
        )
        
        return {
            "status": "saved",
            "focus_state": focus_state,
            "filepath": filepath  # <-- RETURN THE FILEPATH
        }
    except Exception as e:
        logger.error(f"Failed to save focus state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")
@router.get("/{session_id}/load")
async def load_focus_state(session_id: str):
    """Load last saved focus state from memory."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    try:
        # Query Neo4j for last saved focus state
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (n:FocusState)
                WHERE n.session_id = $session_id
                RETURN n.text AS state, n.saved_at AS saved_at
                ORDER BY n.saved_at DESC
                LIMIT 1
            """, {"session_id": vera.sess.id})
            
            record = result.single()
            if not record:
                return {
                    "status": "not_found",
                    "message": "No saved focus state found"
                }
            
            focus_state = json.loads(record["state"])
            
            # Restore focus manager state
            fm = vera.focus_manager
            fm.focus = focus_state.get("focus")
            fm.focus_board = focus_state.get("focus_board", {
                "progress": [],
                "next_steps": [],
                "issues": [],
                "ideas": [],
                "actions": []
            })
            
            # Broadcast the loaded state
            fm._broadcast_sync("focus_loaded", {
                "focus": fm.focus,
                "focus_board": fm.focus_board,
                "loaded_from": record["saved_at"]
            })
            
            return {
                "status": "loaded",
                "focus_state": focus_state,
                "loaded_from": record["saved_at"]
            }
            
    except Exception as e:
        logger.error(f"Failed to load focus state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load: {str(e)}")


@router.get("/{session_id}/history")
async def get_focus_history(session_id: str):
    """Get history of saved focus states."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (n:FocusState)
                WHERE n.session_id = $session_id
                RETURN n.text AS state, n.saved_at AS saved_at, n.focus AS focus
                ORDER BY n.saved_at DESC
                LIMIT 20
            """, {"session_id": vera.sess.id})
            
            history = []
            for record in result:
                try:
                    state = json.loads(record["state"])
                    history.append({
                        "focus": state.get("focus"),
                        "saved_at": record["saved_at"],
                        "board_items": sum(len(items) for items in state.get("focus_board", {}).values())
                    })
                except:
                    continue
            
            return {
                "status": "success",
                "history": history,
                "total": len(history)
            }
            
    except Exception as e:
        logger.error(f"Failed to get focus history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")
# Add these to your router in focus.py

@router.get("/{session_id}/similar")
async def get_similar_focuses(session_id: str, limit: int = 10):
    """Get similar/recent focuses to help user choose."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    try:
        similar_focuses = []
        
        # Method 1: Get from saved board files
        boards = vera.focus_manager.list_saved_boards()
        for board in boards:
            total_items = sum(
                len(board.get('focus_board', {}).get(cat, []))
                for cat in ['actions', 'progress', 'next_steps', 'issues', 'ideas', 'completed']
            )
            
            similar_focuses.append({
                'focus': board.get('focus', 'Untitled'),
                'filename': board.get('filename'),
                'last_used': board.get('created_at'),  # or last_modified if available
                'total_items': total_items,
                'project_id': board.get('project_id')
            })
        
        # Method 2: Also check Neo4j memory for recent focuses
        if hasattr(vera, 'mem'):
            try:
                driver = vera.mem.graph._driver
                
                with driver.session() as db_sess:
                    result = db_sess.run("""
                        MATCH (n:FocusState)
                        WHERE n.session_id = $session_id
                        RETURN DISTINCT n.focus AS focus, n.saved_at AS saved_at
                        ORDER BY n.saved_at DESC
                        LIMIT $limit
                    """, {"session_id": vera.sess.id, "limit": limit})
                    
                    for record in result:
                        focus_text = record["focus"]
                        # Check if not already in list from files
                        if not any(f['focus'] == focus_text for f in similar_focuses):
                            similar_focuses.append({
                                'focus': focus_text,
                                'filename': None,
                                'last_used': record["saved_at"],
                                'total_items': 0,
                                'project_id': None,
                                'source': 'memory'
                            })
            except Exception as e:
                logger.warning(f"Could not query Neo4j for focuses: {e}")
        
        # Sort by last_used (most recent first)
        similar_focuses.sort(
            key=lambda x: x.get('last_used', ''), 
            reverse=True
        )
        
        # Limit results
        similar_focuses = similar_focuses[:limit]
        
        return {
            "status": "success",
            "similar_focuses": similar_focuses,
            "total": len(similar_focuses)
        }
        
    except Exception as e:
        logger.error(f"Failed to get similar focuses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get similar focuses: {str(e)}")


@router.post("/{session_id}/load-by-focus")
async def load_focus_by_text(session_id: str, request: dict):
    """Load a focus board by focus text (finds matching board file)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    focus_text = request.get("focus")
    if not focus_text:
        raise HTTPException(status_code=400, detail="Focus text required")
    
    try:
        fm = vera.focus_manager
        
        # Find matching board file
        matching_board = fm._find_matching_focus_board(focus_text)
        
        if matching_board:
            # Load the board file
            success = fm.load_focus_board(matching_board['filename'])
            
            if success:
                # Broadcast the loaded state
                fm._broadcast_sync("focus_loaded", {
                    "focus": fm.focus,
                    "focus_board": fm.focus_board,
                    "filename": matching_board['filename']
                })
                
                return {
                    "status": "loaded",
                    "focus_state": {
                        "focus": fm.focus,
                        "focus_board": fm.focus_board,
                        "project_id": fm.project_id
                    },
                    "filename": matching_board['filename']
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to load board file")
        else:
            # No matching board found - try to load from Neo4j memory
            driver = vera.mem.graph._driver
            
            with driver.session() as db_sess:
                result = db_sess.run("""
                    MATCH (n:FocusState)
                    WHERE n.session_id = $session_id AND n.focus = $focus
                    RETURN n.text AS state, n.saved_at AS saved_at
                    ORDER BY n.saved_at DESC
                    LIMIT 1
                """, {"session_id": vera.sess.id, "focus": focus_text})
                
                record = result.single()
                if record:
                    focus_state = json.loads(record["state"])
                    
                    # Restore focus manager state
                    fm.focus = focus_state.get("focus")
                    fm.focus_board = focus_state.get("focus_board", {
                        "progress": [],
                        "next_steps": [],
                        "issues": [],
                        "ideas": [],
                        "actions": [],
                        "completed": []
                    })
                    
                    # Broadcast the loaded state
                    fm._broadcast_sync("focus_loaded", {
                        "focus": fm.focus,
                        "focus_board": fm.focus_board,
                        "loaded_from": record["saved_at"]
                    })
                    
                    return {
                        "status": "loaded",
                        "focus_state": focus_state,
                        "loaded_from": record["saved_at"],
                        "source": "memory"
                    }
                else:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"No saved board found for focus: {focus_text}"
                    )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load focus by text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load: {str(e)}")

"""
Enhanced Proactive Focus Manager API Endpoints
==============================================
Add these endpoints to your existing focus.py router to integrate:
- Resource monitoring and control
- External resources (URLs, files, folders, memories, notebooks)
- Modular stage orchestration
- Calendar scheduling
- Background service management
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Import the new enhancement modules
from Vera.ProactiveFocus.manager import (
    ResourceMonitor, ResourceLimits, ResourcePriority,
    PauseController, AdaptiveScheduler, ResourceGuard
)
from Vera.ProactiveFocus.resources import (
    ExternalResourceManager, ResourceType, NotebookResource
)
from Vera.ProactiveFocus.stages import (
    StageOrchestrator, ResearchStage, EvaluationStage,
    OptimizationStage, SteeringStage, IntrospectionStage
)
from Vera.ProactiveFocus.schedule import CalendarScheduler, ProactiveThoughtEvent
from Vera.ProactiveFocus.service import BackgroundService, ServiceConfig

# logger = logging.getLogger(__name__)

# ============================================================
# Request/Response Models
# ============================================================

class ResourceConfigRequest(BaseModel):
    max_cpu_percent: Optional[float] = 70.0
    max_memory_percent: Optional[float] = 80.0
    max_ollama_concurrent: Optional[int] = 2

class ExternalResourceRequest(BaseModel):
    uri: str  # URL, file path, folder path, neo4j:entity_id, chroma:doc_id, notebook:sess_id/notebook_id
    description: Optional[str] = None
    category: Optional[str] = None  # Which focus board category to link to

class StageExecutionRequest(BaseModel):
    stages: List[str]  # e.g., ["Introspection", "Research", "Evaluation"]
    context: Optional[Dict[str, Any]] = None

class CalendarScheduleRequest(BaseModel):
    focus: Optional[str] = None
    start_time: str  # ISO format datetime
    duration_minutes: int = 30
    stages: Optional[List[str]] = None
    recurrence: Optional[str] = None  # "daily", "weekly", or RRULE format

class BackgroundServiceConfigRequest(BaseModel):
    max_cpu_percent: Optional[float] = 50.0
    check_interval: Optional[float] = 30.0
    min_idle_seconds: Optional[float] = 30.0
    enabled_stages: Optional[List[str]] = None
    use_calendar: Optional[bool] = True
    learn_optimal_times: Optional[bool] = True

# ============================================================
# Global Service Instances (keyed by session_id)
# ============================================================

resource_monitors: Dict[str, ResourceMonitor] = {}
resource_managers: Dict[str, ExternalResourceManager] = {}
stage_orchestrators: Dict[str, StageOrchestrator] = {}
calendar_schedulers: Dict[str, CalendarScheduler] = {}
background_services: Dict[str, BackgroundService] = {}
pause_controllers: Dict[str, PauseController] = {}

# ============================================================
# Helper Functions
# ============================================================


def get_or_create_resource_monitor(session_id: str):
    """Get or create resource monitor for session"""
    if not RESOURCE_MANAGER_AVAILABLE or ResourceMonitor is None:
        raise HTTPException(
            status_code=501, 
            detail="Resource monitoring not available. Install required dependencies: pip install psutil"
        )
    
    if session_id not in resource_monitors:
        try:
            monitor = ResourceMonitor(limits=ResourceLimits())
            monitor.start()
            resource_monitors[session_id] = monitor
            logger.info(f"Created resource monitor for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to create resource monitor: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize resource monitor: {str(e)}")
    
    return resource_monitors[session_id]


def get_or_create_resource_manager(session_id: str, vera) -> ExternalResourceManager:
    """Get or create external resource manager for session"""
    if session_id not in resource_managers:
        hybrid_memory = vera.mem if hasattr(vera, 'mem') else None
        manager = ExternalResourceManager(hybrid_memory=hybrid_memory)
        resource_managers[session_id] = manager
        logger.info(f"Created resource manager for session {session_id}")
    return resource_managers[session_id]

def get_or_create_pause_controller(session_id: str) -> PauseController:
    """Get or create pause controller for session"""
    if session_id not in pause_controllers:
        pause_controllers[session_id] = PauseController()
        logger.info(f"Created pause controller for session {session_id}")
    return pause_controllers[session_id]


def get_or_create_background_service(session_id: str, vera):
    """Get or create background service for session"""
    if not BACKGROUND_SERVICE_AVAILABLE or BackgroundService is None:
        raise HTTPException(
            status_code=501,
            detail="Background service not available. Ensure all enhancement modules are installed."
        )
    
    if session_id not in background_services:
        if not hasattr(vera, 'focus_manager'):
            raise HTTPException(status_code=400, detail="Focus manager not available")
        
        try:
            service = BackgroundService(vera.focus_manager)
            background_services[session_id] = service
            logger.info(f"Created background service for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to create background service: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize background service: {str(e)}")
    
    return background_services[session_id]


# ============================================================
# Resource Monitoring Endpoints
# ============================================================

@router.get("/{session_id}/resources/status")
async def get_resource_status(session_id: str):
    """Get current system resource status - FINAL WORKING VERSION"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        monitor = get_or_create_resource_monitor(session_id)
        state = monitor.get_state()
        
        if not state:
            return {
                "status": "initializing",
                "message": "Resource monitor starting up..."
            }
        
        # Safe attribute access
        cpu_percent = float(getattr(state, 'cpu_percent', 0.0))
        memory_percent = float(getattr(state, 'memory_percent', 0.0))
        ollama_count = getattr(state, 'ollama_process_count', 
                              getattr(state, 'ollama_processes', 0))
        
        # Handle timestamp safely
        timestamp_value = getattr(state, 'timestamp', None)
        if isinstance(timestamp_value, datetime):
            timestamp_iso = timestamp_value.isoformat()
        elif isinstance(timestamp_value, (int, float)):
            timestamp_iso = datetime.fromtimestamp(timestamp_value).isoformat()
        else:
            timestamp_iso = datetime.now().isoformat()
        
        # Calculate availability manually instead of calling is_available method
        def check_availability(limits, priority_name):
            """Manually check if resources are available for a priority level"""
            priority_limits = getattr(limits, 'priority_limits', {})
            
            if priority_name == 'CRITICAL':
                max_cpu = priority_limits.get('CRITICAL', {}).get('cpu', 95.0)
                max_mem = priority_limits.get('CRITICAL', {}).get('memory', 95.0)
            elif priority_name == 'HIGH':
                max_cpu = priority_limits.get('HIGH', {}).get('cpu', 80.0)
                max_mem = priority_limits.get('HIGH', {}).get('memory', 85.0)
            elif priority_name == 'NORMAL':
                max_cpu = getattr(limits, 'max_cpu_percent', 70.0)
                max_mem = getattr(limits, 'max_memory_percent', 80.0)
            elif priority_name == 'LOW':
                max_cpu = priority_limits.get('LOW', {}).get('cpu', 50.0)
                max_mem = priority_limits.get('LOW', {}).get('memory', 70.0)
            else:  # OPPORTUNISTIC
                max_cpu = priority_limits.get('OPPORTUNISTIC', {}).get('cpu', 30.0)
                max_mem = priority_limits.get('OPPORTUNISTIC', {}).get('memory', 60.0)
            
            return cpu_percent < max_cpu and memory_percent < max_mem
        
        return {
            "status": "active",
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory_percent, 1),
            "ollama_process_count": int(ollama_count),
            "timestamp": timestamp_iso,
            "limits": {
                "cpu": float(getattr(monitor.limits, 'max_cpu_percent', 70.0)),
                "memory": float(getattr(monitor.limits, 'max_memory_percent', 80.0)),
                "ollama": int(getattr(monitor.limits, 'max_ollama_processes', 2))
            },
            "available": {
                "critical": check_availability(monitor.limits, 'CRITICAL'),
                "high": check_availability(monitor.limits, 'HIGH'),
                "normal": check_availability(monitor.limits, 'NORMAL'),
                "low": check_availability(monitor.limits, 'LOW'),
                "opportunistic": check_availability(monitor.limits, 'OPPORTUNISTIC')
            }
        }
    except Exception as e:
        logger.error(f"Error getting resource status: {e}", exc_info=True)
        # Return minimal response instead of raising
        return {
            "status": "error",
            "message": str(e),
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "ollama_process_count": 0,
            "timestamp": datetime.now().isoformat(),
            "limits": {"cpu": 70.0, "memory": 80.0, "ollama": 2},
            "available": {
                "critical": True, "high": True, "normal": True,
                "low": False, "opportunistic": False
            }
        }


@router.post("/{session_id}/resources/configure")
async def configure_resource_limits(session_id: str, config: ResourceConfigRequest):
    """Configure resource monitoring limits"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    monitor = get_or_create_resource_monitor(session_id)
    
    monitor.limits.max_cpu_percent = config.max_cpu_percent
    monitor.limits.max_memory_percent = config.max_memory_percent
    monitor.limits.max_ollama_concurrent = config.max_ollama_concurrent
    
    logger.info(f"Updated resource limits for session {session_id}: "
                f"CPU={config.max_cpu_percent}%, Memory={config.max_memory_percent}%, "
                f"Ollama={config.max_ollama_concurrent}")
    
    return {
        "status": "updated",
        "limits": {
            "cpu": config.max_cpu_percent,
            "memory": config.max_memory_percent,
            "ollama": config.max_ollama_concurrent
        }
    }

@router.post("/{session_id}/resources/pause")
async def pause_resource_intensive_operations(session_id: str, priority: Optional[str] = None):
    """Pause resource-intensive operations"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    pause_controller = get_or_create_pause_controller(session_id)
    
    if priority:
        try:
            priority_enum = ResourcePriority[priority.upper()]
            pause_controller.pause("user_request", priority_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")
    else:
        pause_controller.pause("user_request")
    
    return {
        "status": "paused",
        "priority": priority or "all",
        "reasons": pause_controller.get_pause_reasons()
    }

@router.post("/{session_id}/resources/resume")
async def resume_resource_intensive_operations(session_id: str, priority: Optional[str] = None):
    """Resume resource-intensive operations"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    pause_controller = get_or_create_pause_controller(session_id)
    
    if priority:
        try:
            priority_enum = ResourcePriority[priority.upper()]
            pause_controller.resume("user_request", priority_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")
    else:
        pause_controller.resume("user_request")
    
    return {
        "status": "resumed",
        "priority": priority or "all"
    }

# ============================================================
# External Resources Endpoints
# ============================================================

@router.get("/{session_id}/external-resources")
async def list_external_resources(session_id: str, resource_type: Optional[str] = None):
    """List all external resources"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    manager = get_or_create_resource_manager(session_id, vera)
    
    resources = []
    for res_id, metadata in manager.resources.items():
        if resource_type and metadata.resource_type.value != resource_type:
            continue
        
        resources.append({
            "id": res_id,
            "uri": metadata.uri,
            "type": metadata.resource_type.value,
            "title": metadata.title,
            "description": metadata.description,
            "accessible": metadata.accessible,
            "last_checked": metadata.last_checked.isoformat() if metadata.last_checked else None,
            "metadata": metadata.metadata
        })
    
    return {
        "status": "success",
        "resources": resources,
        "total": len(resources)
    }

@router.post("/{session_id}/external-resources/add")
async def add_external_resource(session_id: str, request: ExternalResourceRequest):
    """Add an external resource"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    manager = get_or_create_resource_manager(session_id, vera)
    
    try:
        metadata = manager.add_resource(request.uri, request.description)
        
        # Link to focus board if category specified
        if request.category and hasattr(vera, 'focus_manager'):
            manager.link_to_focus_board(
                metadata.resource_id,
                request.category,
                vera.focus_manager
            )
        
        return {
            "status": "added",
            "resource": {
                "id": metadata.resource_id,
                "uri": metadata.uri,
                "type": metadata.resource_type.value,
                "title": metadata.title,
                "description": metadata.description,
                "accessible": metadata.accessible,
                "linked_to": request.category
            }
        }
    except Exception as e:
        logger.error(f"Failed to add resource: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{session_id}/external-resources/{resource_id}")
async def remove_external_resource(session_id: str, resource_id: str):
    """Remove an external resource"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    manager = get_or_create_resource_manager(session_id, vera)
    
    if resource_id not in manager.resources:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    del manager.resources[resource_id]
    
    return {
        "status": "removed",
        "resource_id": resource_id
    }

@router.post("/{session_id}/external-resources/{resource_id}/refresh")
async def refresh_resource_metadata(session_id: str, resource_id: str):
    """Refresh metadata for a specific resource"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    manager = get_or_create_resource_manager(session_id, vera)
    
    if resource_id not in manager.resources:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    metadata = manager.resources[resource_id]
    
    # Re-extract metadata
    try:
        if metadata.resource_type == ResourceType.URL:
            from proactive_focus_external_resources import URLResource
            new_metadata = URLResource.extract_metadata(metadata.uri)
        elif metadata.resource_type == ResourceType.FILE:
            from proactive_focus_external_resources import FileResource
            new_metadata = FileResource.extract_metadata(metadata.uri)
        elif metadata.resource_type == ResourceType.FOLDER:
            from proactive_focus_external_resources import FolderResource
            new_metadata = FolderResource.extract_metadata(metadata.uri)
        elif metadata.resource_type == ResourceType.NOTEBOOK:
            from proactive_focus_external_resources import NotebookResource
            new_metadata = NotebookResource.extract_metadata(metadata.uri)
        else:
            new_metadata = metadata
        
        # Update in manager
        manager.resources[resource_id] = new_metadata
        
        return {
            "status": "refreshed",
            "resource": {
                "id": resource_id,
                "uri": new_metadata.uri,
                "type": new_metadata.resource_type.value,
                "title": new_metadata.title,
                "accessible": new_metadata.accessible,
                "last_checked": new_metadata.last_checked.isoformat() if new_metadata.last_checked else None
            }
        }
    except Exception as e:
        logger.error(f"Failed to refresh resource: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/notebooks/discover")
async def discover_notebooks(session_id: str):
    """Discover all notebooks for current session"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        notebooks = NotebookResource.list_notebooks(session_id)
        
        return {
            "status": "success",
            "notebooks": notebooks,
            "total": len(notebooks)
        }
    except Exception as e:
        logger.error(f"Failed to discover notebooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Stage Orchestration Endpoints
# ============================================================

@router.post("/{session_id}/stages/execute")
async def execute_stage_pipeline(session_id: str, request: StageExecutionRequest):
    """Execute a pipeline of proactive thinking stages"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if session_id not in stage_orchestrators:
        stage_orchestrators[session_id] = StageOrchestrator()
    
    orchestrator = stage_orchestrators[session_id]
    
    # Run pipeline in background thread
    import threading
    
    result_container = {"results": None, "error": None}
    
    def run_pipeline():
        try:
            results = orchestrator.execute_pipeline(
                vera.focus_manager,
                stage_names=request.stages
            )
            result_container["results"] = results
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            result_container["error"] = str(e)
    
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    
    # Wait briefly for quick stages
    thread.join(timeout=2.0)
    
    if thread.is_alive():
        # Still running
        return {
            "status": "started",
            "stages": request.stages,
            "message": "Pipeline execution started in background"
        }
    else:
        # Completed quickly
        if result_container["error"]:
            raise HTTPException(status_code=500, detail=result_container["error"])
        
        return {
            "status": "completed",
            "results": _serialize_stage_results(result_container["results"])
        }

@router.get("/{session_id}/stages/available")
async def get_available_stages(session_id: str):
    """Get list of available stages"""
    return {
        "status": "success",
        "stages": [
            {
                "name": "Introspection",
                "description": "Deep memory analysis to identify patterns and consolidate knowledge",
                "icon": "🧠"
            },
            {
                "name": "Research",
                "description": "Information gathering using tools and memory queries",
                "icon": "🔍"
            },
            {
                "name": "Evaluation",
                "description": "Current state analysis with metrics and progress evaluation",
                "icon": "📊"
            },
            {
                "name": "Optimization",
                "description": "Identify efficiency improvements and automation opportunities",
                "icon": "⚡"
            },
            {
                "name": "Steering",
                "description": "Strategic direction assessment and priority alignment",
                "icon": "🎯"
            }
        ]
    }

def _serialize_stage_results(results: Dict) -> Dict:
    """Serialize stage results for JSON response"""
    serialized = {}
    for stage_name, output in results.items():
        serialized[stage_name] = {
            "insights": output.insights,
            "actions": output.actions,
            "ideas": output.ideas,
            "next_steps": output.next_steps,
            "issues": output.issues,
            "tool_calls_count": len(output.tool_calls),
            "memory_refs_count": len(output.memory_refs)
        }
    return serialized

# ============================================================
# Calendar Scheduling Endpoints
# ============================================================

@router.get("/{session_id}/calendar/sessions")
async def get_scheduled_sessions(session_id: str, days_ahead: int = 7):
    """Get upcoming scheduled thought sessions"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if session_id not in calendar_schedulers:
        calendar_schedulers[session_id] = CalendarScheduler()
    
    scheduler = calendar_schedulers[session_id]
    
    try:
        upcoming = scheduler.get_upcoming_sessions(days_ahead=days_ahead)
        
        return {
            "status": "success",
            "sessions": [
                {
                    "uid": event.uid,
                    "focus": event.focus,
                    "start_time": event.start_time.isoformat(),
                    "duration_minutes": event.duration_minutes,
                    "stages": event.stages,
                    "priority": event.priority.value if event.priority else None,
                    "recurrence_rule": event.recurrence_rule
                }
                for event in upcoming
            ],
            "total": len(upcoming)
        }
    except Exception as e:
        logger.error(f"Failed to get scheduled sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/calendar/schedule")
async def schedule_thought_session(session_id: str, request: CalendarScheduleRequest):
    """Schedule a proactive thought session - FIXED VERSION"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if session_id not in calendar_schedulers:
        calendar_schedulers[session_id] = CalendarScheduler()
    
    scheduler = calendar_schedulers[session_id]
    
    try:
        start_time = datetime.fromisoformat(request.start_time)
        focus = request.focus or (vera.focus_manager.focus if hasattr(vera, 'focus_manager') else "")
        
        if request.recurrence == "daily":
            # Schedule daily for 7 days
            events = []
            for i in range(7):
                event_time = start_time + timedelta(days=i)
                # Don't pass recurrence_rule parameter
                event = scheduler.schedule_thought_session(
                    focus=focus,
                    start_time=event_time,
                    duration_minutes=request.duration_minutes,
                    stages=request.stages
                )
                events.append(event)
            return {
                "status": "scheduled",
                "message": f"Scheduled {len(events)} daily sessions starting {start_time.isoformat()}",
                "count": len(events)
            }
            
        elif request.recurrence == "weekly":
            # Schedule weekly for 4 weeks
            events = []
            for i in range(4):
                event_time = start_time + timedelta(weeks=i)
                event = scheduler.schedule_thought_session(
                    focus=focus,
                    start_time=event_time,
                    duration_minutes=request.duration_minutes,
                    stages=request.stages
                )
                events.append(event)
            return {
                "status": "scheduled",
                "message": f"Scheduled {len(events)} weekly sessions starting {start_time.isoformat()}",
                "count": len(events)
            }
            
        else:
            # Single session - don't pass recurrence_rule
            event = scheduler.schedule_thought_session(
                focus=focus,
                start_time=start_time,
                duration_minutes=request.duration_minutes,
                stages=request.stages
                # DON'T PASS: recurrence_rule=request.recurrence
            )
            return {
                "status": "scheduled",
                "message": f"Session scheduled for {start_time.isoformat()}",
                "uid": event.uid
            }
            
    except Exception as e:
        logger.error(f"Failed to schedule session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}/calendar/sessions/{uid}")
async def cancel_scheduled_session(session_id: str, uid: str):
    """Cancel a scheduled thought session"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in calendar_schedulers:
        raise HTTPException(status_code=404, detail="No calendar scheduler found")
    
    scheduler = calendar_schedulers[session_id]
    
    try:
        scheduler.cancel_session(uid)
        
        return {
            "status": "cancelled",
            "uid": uid
        }
    except Exception as e:
        logger.error(f"Failed to cancel session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Background Service Endpoints
# ============================================================

@router.get("/{session_id}/background/status")
async def get_background_status(session_id: str):
    """Get background service status - FIXED VERSION"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if background service exists
    if session_id in background_services:
        service = background_services[session_id]
        
        try:
            # Safely get execution count
            execution_count = 0
            if hasattr(service, 'execution_history'):
                execution_count = len(service.execution_history)
            elif hasattr(service, '_execution_history'):
                execution_count = len(service._execution_history)
            
            return {
                "status": "active",
                "running": bool(getattr(service, 'running', False)),
                "paused": bool(service.pause_controller.is_paused(ResourcePriority.NORMAL)) if hasattr(service, 'pause_controller') else False,
                "config": {
                    "max_cpu_percent": float(getattr(service.config, 'max_cpu_percent', 50.0)),
                    "check_interval": float(getattr(service.config, 'check_interval', 30.0)),
                    "min_idle_seconds": float(getattr(service.config, 'min_idle_seconds', 30.0)),
                    "enabled_stages": list(getattr(service.config, 'enabled_stages', [])),
                    "use_calendar": bool(getattr(service.config, 'use_calendar', True)),
                    "learn_optimal_times": bool(getattr(service.config, 'learn_optimal_times', True))
                },
                "execution_count": execution_count
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "active",
                "running": False,
                "paused": False,
                "config": {
                    "max_cpu_percent": 50.0,
                    "check_interval": 30.0,
                    "min_idle_seconds": 30.0,
                    "enabled_stages": ["Introspection", "Research", "Evaluation"],
                    "use_calendar": True,
                    "learn_optimal_times": True
                },
                "execution_count": 0,
                "error": str(e)
            }
    else:
        return {
            "status": "not_started",
            "running": False,
            "message": "Background service not yet initialized"
        }


@router.post("/{session_id}/background/start")
async def start_background_service(session_id: str, config: Optional[BackgroundServiceConfigRequest] = None):
    """Start the background service"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        service = get_or_create_background_service(session_id, vera)
        
        # Update config if provided
        if config:
            service.config.max_cpu_percent = config.max_cpu_percent or service.config.max_cpu_percent
            service.config.check_interval = config.check_interval or service.config.check_interval
            service.config.min_idle_seconds = config.min_idle_seconds or service.config.min_idle_seconds
            if config.enabled_stages:
                service.config.enabled_stages = config.enabled_stages
            service.config.use_calendar = config.use_calendar if config.use_calendar is not None else service.config.use_calendar
            service.config.learn_optimal_times = config.learn_optimal_times if config.learn_optimal_times is not None else service.config.learn_optimal_times
        
        # Start service
        service.start()
        
        return {
            "status": "started",
            "config": {
                "max_cpu_percent": service.config.max_cpu_percent,
                "enabled_stages": service.config.enabled_stages,
                "use_calendar": service.config.use_calendar
            }
        }
    except Exception as e:
        logger.error(f"Failed to start background service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/background/stop")
async def stop_background_service(session_id: str):
    """Stop the background service"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in background_services:
        raise HTTPException(status_code=404, detail="Background service not found")
    
    service = background_services[session_id]
    service.stop()
    
    return {
        "status": "stopped"
    }

@router.post("/{session_id}/background/trigger")
async def trigger_manual_session(session_id: str, request: Optional[StageExecutionRequest] = None):
    """Manually trigger a background session"""
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        service = get_or_create_background_service(session_id, vera)
        
        stages = request.stages if request else None
        
        # Trigger in background thread
        import threading
        
        def trigger():
            # Don't pass stages if None, let service use defaults
            if stages:
                service.trigger_manual_session(stages=stages, wait_for_resources=True)
            else:
                service.trigger_manual_session(wait_for_resources=True)
        thread = threading.Thread(target=trigger, daemon=True)
        thread.start()
        
        return {
            "status": "triggered",
            "stages": stages or service.config.enabled_stages
        }
    except Exception as e:
        logger.error(f"Failed to trigger session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/background/history")
async def get_execution_history(session_id: str, limit: int = 20):
    """Get background execution history - FIXED VERSION"""
    from Vera.ChatUI.api.session import sessions
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in background_services:
        return {
            "status": "success",
            "history": [],
            "total": 0,
            "message": "Background service not started"
        }
    
    service = background_services[session_id]
    
    # Try to get history from different possible attributes
    history = []
    if hasattr(service, 'execution_history'):
        history = service.execution_history[-limit:]
    elif hasattr(service, '_execution_history'):
        history = service._execution_history[-limit:]
    
    # Format history entries
    formatted_history = []
    for entry in history:
        try:
            formatted_history.append({
                "session_id": entry.get("session_id", "unknown"),
                "start_time": entry.get("start_time", ""),
                "end_time": entry.get("end_time", ""),
                "duration": entry.get("duration", 0),
                "stages_executed": entry.get("stages_executed", []),
                "success": entry.get("success", False),
                "error": entry.get("error")
            })
        except Exception as e:
            logger.debug(f"Error formatting history entry: {e}")
            continue
    
    return {
        "status": "success",
        "history": formatted_history,
        "total": len(history) if hasattr(service, 'execution_history') or hasattr(service, '_execution_history') else 0
    }
    
# ============================================================================
# HELPER: Safe attribute access
# ============================================================================

def safe_getattr(obj, attr, default=None):
    """Safely get attribute with fallback"""
    try:
        value = getattr(obj, attr, default)
        return value if value is not None else default
    except Exception:
        return default
