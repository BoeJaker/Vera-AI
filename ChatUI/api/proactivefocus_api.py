# ============================================================
# Imports
# ============================================================
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

# ============================================================
# Internal dependencies (adjust paths as needed)
# ============================================================
from Vera.ChatUI.api.session import sessions, get_or_create_vera, vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections


# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/focus", tags=["focus"])
wsrouter = APIRouter(prefix="/ws/focus", tags=["wsfocus"])

# ============================================================
# Proactive Focus Manager Endpoints
# ============================================================
# ============================================================
# Proactive Focus Manager Endpoints - FIXED
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
    logger.info(f"Available sessions: {list(sessions.keys())}")
    
    if session_id not in sessions:
        logger.error(f"Session not found: {session_id}")
        logger.error(f"Available sessions: {list(sessions.keys())}")
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        logger.error("Focus manager not available")
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    focus_text = request.get("focus", "")
    if not focus_text:
        raise HTTPException(status_code=400, detail="Focus text required")
    
    try:
        logger.info(f"Setting focus to: {focus_text}")
        vera.focus_manager.set_focus(focus_text)
        
        return {
            "status": "success",
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board
        }
    except Exception as e:
        logger.error(f"Error setting focus: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to set focus: {str(e)}")

@router.post("/{session_id}/board/add")
def add_to_focus_board(self, category: str, note: str, metadata: Optional[Dict[str, Any]] = None):
    """Add item to focus board with optional metadata."""
    if category not in self.focus_board:
        self.focus_board[category] = []
    
    item = {
        "note": note,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {}
    }
    
    self.focus_board[category].append(item)
    
    # Store in hybrid memory if available
    if self.hybrid_memory and self.project_id:
        item_id = f"focus_item_{category}_{int(time.time()*1000)}"
        
        # Convert category to valid Neo4j label (CamelCase, no spaces/underscores)
        category_label = self._to_camel_case(category)
        
        self.hybrid_memory.upsert_entity(
            entity_id=item_id,
            etype="focus_item",
            labels=["FocusItem", category_label],
            properties={
                "category": category,
                "note": note,
                "project_id": self.project_id,
                **item["metadata"]
            }
        )
        self.hybrid_memory.link(self.project_id, item_id, f"HAS_{category.upper()}")
    
    # Broadcast board update
    self._broadcast_sync("board_updated", {
        "category": category,
        "item": item,
        "focus_board": self.focus_board
    })
    
    print(f"[FocusManager] Added to {category}: {note}")
    
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
    '''WebSocket endpoint for real-time focus manager updates.'''
    await websocket.accept()
    
    if session_id not in sessions:
        try:
            await websocket.send_json({"type": "error", "message": "..."})
        except:
            pass
        return
                
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        await websocket.send_json({"type": "error", "error": "Focus manager not available"})
        await websocket.close()
        return
    
    # Register websocket for focus updates
    if not hasattr(vera.focus_manager, '_websockets'):
        vera.focus_manager._websockets = []
    vera.focus_manager._websockets.append(websocket)
    
    # Send initial state
    await websocket.send_json({
        "type": "focus_status",
        "data": {
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "running": vera.focus_manager.running
        }
    })
    
    try:
        # Keep connection alive, only send updates on changes
        last_state = {
            "focus": vera.focus_manager.focus,
            "focus_board": json.dumps(vera.focus_manager.focus_board),
            "running": vera.focus_manager.running
        }
        
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds instead of 1
            
            # Only send if state changed
            current_state = {
                "focus": vera.focus_manager.focus,
                "focus_board": json.dumps(vera.focus_manager.focus_board),
                "running": vera.focus_manager.running
            }
            
            if current_state != last_state:
                await websocket.send_json({
                    "type": "focus_status",
                    "data": {
                        "focus": vera.focus_manager.focus,
                        "focus_board": vera.focus_manager.focus_board,
                        "running": vera.focus_manager.running
                    }
                })
                last_state = current_state
    
    except WebSocketDisconnect:
        logger.info(f"Focus WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Focus WebSocket error: {str(e)}", exc_info=True)
    finally:
        if websocket in vera.focus_manager._websockets:
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
