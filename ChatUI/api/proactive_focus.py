 # ============================================================
# Proactive Focus Manager Endpoints - FIXED
# ============================================================

@app.get("/api/focus/{session_id}")
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


@app.post("/api/focus/{session_id}/set")
async def set_focus(session_id: str, request: dict):
    '''Set the focus for proactive thinking.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    focus_text = request.get("focus", "")
    if not focus_text:
        raise HTTPException(status_code=400, detail="Focus text required")
    
    vera.focus_manager.set_focus(focus_text)
    
    return {
        "status": "success",
        "focus": vera.focus_manager.focus
    }


@app.post("/api/focus/{session_id}/clear")
async def clear_focus(session_id: str):
    '''Clear the current focus.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    vera.focus_manager.clear_focus()
    
    return {"status": "success", "focus": None}


@app.post("/api/focus/{session_id}/board/add")
async def add_to_focus_board(session_id: str, request: dict):
    '''Add an item to the focus board.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    category = request.get("category", "actions")
    note = request.get("note", "")
    
    if not note:
        raise HTTPException(status_code=400, detail="Note text required")
    
    vera.focus_manager.add_to_focus_board(category, note)
    
    return {
        "status": "success",
        "focus_board": vera.focus_manager.focus_board
    }


@app.post("/api/focus/{session_id}/board/clear")
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


@app.get("/api/focus/{session_id}/start")
async def start_proactive_thought(session_id: str):
    """Start the proactive focus manager."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    vera.focus_manager.iterative_workflow( 
        max_iterations = None, 
        iteration_interval = 600,
        auto_execute = True,
        stream_output = True
    )
    
    return {
        "status": "started",
        "focus": vera.focus_manager.focus
    }


@app.post("/api/focus/{session_id}/stop")
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


@app.post("/api/focus/{session_id}/trigger")
async def trigger_proactive_thought(session_id: str):
    """Manually trigger a proactive thought generation."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Trigger thought generation if method exists
    if hasattr(vera.focus_manager, 'generate_proactive_thought'):
        # Run in background
        import asyncio
        asyncio.create_task(vera.focus_manager.generate_proactive_thought())
    
    return {
        "status": "triggered"
    }


@app.websocket("/ws/focus/{session_id}")
async def websocket_focus(websocket: WebSocket, session_id: str):
    '''WebSocket endpoint for real-time focus manager updates.'''
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
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


@app.get("/api/focus/{session_id}/save")
async def save_focus_state(session_id: str):
    """Save current focus and board state to memory."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    # Save to Neo4j memory
    focus_state = {
        "focus": fm.focus,
        "focus_board": fm.focus_board,
        "running": fm.running,
        "saved_at": datetime.utcnow().isoformat()
    }
    
    try:
        vera.mem.add_session_memory(
            vera.sess.id,
            json.dumps(focus_state, indent=2),
            "FocusState",
            {
                "topic": "focus_state",
                "focus": fm.focus or "none",
                "saved_at": focus_state["saved_at"]
            },
            promote=True
        )
        
        return {
            "status": "saved",
            "focus_state": focus_state
        }
    except Exception as e:
        logger.error(f"Failed to save focus state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@app.get("/api/focus/{session_id}/load")
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


@app.get("/api/focus/{session_id}/history")
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