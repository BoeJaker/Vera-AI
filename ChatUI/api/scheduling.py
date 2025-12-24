#!/usr/bin/env python3
"""
Calendar Router for Vera AI - DEBUGGABLE VERSION
Provides REST API and WebSocket endpoints for calendar management
Integrates with executive agent for multi-source calendar display
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import asyncio
import traceback
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# ====== Models ======

class CalendarEvent(BaseModel):
    """Unified calendar event model"""
    id: str
    title: str
    start: str  # ISO format
    end: Optional[str] = None
    source: str  # 'google', 'local', 'cron', 'apscheduler'
    description: Optional[str] = None
    color: Optional[str] = None
    recurrence: Optional[str] = None
    all_day: bool = False
    
class CreateEventRequest(BaseModel):
    """Request model for creating events"""
    title: str = Field(..., description="Event title")
    start: str = Field(..., description="Start datetime (ISO format)")
    end: str = Field(..., description="End datetime (ISO format)")
    source: str = Field(default="local", description="Calendar source")
    description: Optional[str] = None
    recurrence: Optional[str] = None
    
class CronJob(BaseModel):
    """Cron job representation"""
    id: str
    name: str
    schedule: str  # Cron expression
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    enabled: bool = True

# ====== WebSocket Manager ======

class CalendarConnectionManager:
    """Manages WebSocket connections for real-time calendar updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[Calendar WS] Client connected. Total: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"[Calendar WS] Client disconnected. Total: {len(self.active_connections)}")
        
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"[Calendar WS] Error broadcasting: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

calendar_manager = CalendarConnectionManager()

# ====== Calendar Service ======

class CalendarService:
    """Service layer for calendar operations"""
    
    def __init__(self, executive_agent=None):
        self.executive = executive_agent
        logger.info(f"[Calendar Service] Initialized with executive: {executive_agent is not None}")
        
    def get_all_events(self, days_ahead: int = 30) -> List[CalendarEvent]:
        """Get events from all sources"""
        events = []
        
        # Get Google Calendar events
        try:
            if self.executive and hasattr(self.executive, 'get_events_google'):
                logger.info("[Calendar] Fetching Google events...")
                google_events = self.executive.get_events_google(days_ahead)
                logger.info(f"[Calendar] Got {len(google_events)} Google events")
                
                events.extend([
                    CalendarEvent(
                        id=e.get('event_id', f"google_{i}"),
                        title=e.get('title', 'Untitled'),
                        start=e.get('start'),
                        end=e.get('end'),
                        source='google',
                        color='#4285f4'
                    )
                    for i, e in enumerate(google_events)
                ])
            else:
                logger.warning("[Calendar] Executive agent not available or missing get_events_google")
        except Exception as e:
            logger.error(f"[Calendar] Error fetching Google events: {e}")
            logger.error(traceback.format_exc())
        
        # Get local calendar events
        try:
            if self.executive and hasattr(self.executive, 'get_events_local'):
                logger.info("[Calendar] Fetching local events...")
                local_events = self.executive.get_events_local(days_ahead)
                logger.info(f"[Calendar] Got {len(local_events)} local events")
                
                events.extend([
                    CalendarEvent(
                        id=e.get('event_id', f"local_{i}"),
                        title=e.get('title', 'Untitled'),
                        start=e.get('start'),
                        end=e.get('end'),
                        source='local',
                        color='#34a853'
                    )
                    for i, e in enumerate(local_events)
                ])
            else:
                logger.warning("[Calendar] Executive agent not available or missing get_events_local")
        except Exception as e:
            logger.error(f"[Calendar] Error fetching local events: {e}")
            logger.error(traceback.format_exc())
        
        logger.info(f"[Calendar] Total events: {len(events)}")
        return sorted(events, key=lambda x: x.start)
    
    def get_cron_jobs(self) -> List[CronJob]:
        """Get all scheduled cron jobs"""
        jobs = []
        
        try:
            # Check if executive has a scheduler attribute
            if self.executive and hasattr(self.executive, 'scheduler'):
                logger.info("[Calendar] Fetching scheduled jobs...")
                # This would need APScheduler integration in executive
                # For now, return empty list
                logger.warning("[Calendar] Scheduler integration not yet implemented")
            else:
                logger.warning("[Calendar] No scheduler found on executive agent")
        except Exception as e:
            logger.error(f"[Calendar] Error fetching cron jobs: {e}")
            logger.error(traceback.format_exc())
        
        return jobs
    
    def create_event(self, event_data: CreateEventRequest) -> CalendarEvent:
        """Create a new calendar event"""
        if not self.executive:
            logger.error("[Calendar] Executive agent not available for event creation")
            raise HTTPException(status_code=500, detail="Executive agent not available")
        
        try:
            start_dt = datetime.fromisoformat(event_data.start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(event_data.end.replace('Z', '+00:00'))
            
            logger.info(f"[Calendar] Creating {event_data.source} event: {event_data.title}")
            
            if event_data.source == 'google':
                if not hasattr(self.executive, 'add_event_google'):
                    raise HTTPException(status_code=500, detail="Google calendar not configured")
                    
                if event_data.recurrence:
                    result = self.executive.add_recuring_event_google(
                        event_data.title,
                        start_dt,
                        end_dt,
                        event_data.recurrence
                    )
                else:
                    result = self.executive.add_event_google(
                        event_data.title,
                        start_dt,
                        end_dt
                    )
            else:  # local
                if not hasattr(self.executive, 'add_event_local'):
                    raise HTTPException(status_code=500, detail="Local calendar not configured")
                    
                if event_data.recurrence:
                    result = self.executive.add_recurring_event_local(
                        event_data.title,
                        start_dt,
                        end_dt,
                        event_data.recurrence
                    )
                else:
                    result = self.executive.add_event_local(
                        event_data.title,
                        start_dt,
                        end_dt
                    )
            
            logger.info(f"[Calendar] Event created successfully")
            
            # Create response event
            new_event = CalendarEvent(
                id=f"{event_data.source}_{int(datetime.now().timestamp())}",
                title=event_data.title,
                start=event_data.start,
                end=event_data.end,
                source=event_data.source,
                description=event_data.description,
                recurrence=event_data.recurrence
            )
            
            return new_event
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[Calendar] Error creating event: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"Failed to create event: {str(e)}")
    
    def delete_event(self, event_id: str, source: str) -> bool:
        """Delete a calendar event"""
        if not self.executive:
            raise HTTPException(status_code=500, detail="Executive agent not available")
        
        try:
            logger.info(f"[Calendar] Deleting {source} event: {event_id}")
            
            if source == 'google':
                if not hasattr(self.executive, 'delete_event_google'):
                    raise HTTPException(status_code=500, detail="Google calendar not configured")
                result = self.executive.delete_event_google(event_id)
            elif source == 'local':
                if not hasattr(self.executive, 'delete_event_local'):
                    raise HTTPException(status_code=500, detail="Local calendar not configured")
                result = self.executive.delete_event_local(event_id)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")
            
            logger.info(f"[Calendar] Event deleted successfully")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[Calendar] Error deleting event: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"Failed to delete event: {str(e)}")

# Initialize service (will be set up with executive agent from main app)
calendar_service: Optional[CalendarService] = None

def initialize_calendar_service(executive_agent):
    """Initialize the calendar service with executive agent"""
    global calendar_service
    logger.info(f"[Calendar] Initializing service with executive: {executive_agent}")
    calendar_service = CalendarService(executive_agent)
    return calendar_service

# ====== REST Endpoints ======

@router.get("/events", response_model=List[CalendarEvent])
async def get_events(
    days_ahead: int = Query(default=30, ge=1, le=365, description="Days to look ahead")
):
    """Get all calendar events from all sources"""
    logger.info(f"[Calendar API] GET /events?days_ahead={days_ahead}")
    
    if not calendar_service:
        logger.error("[Calendar API] Calendar service not initialized!")
        raise HTTPException(status_code=500, detail="Calendar service not initialized")
    
    try:
        events = calendar_service.get_all_events(days_ahead)
        logger.info(f"[Calendar API] Returning {len(events)} events")
        return events
    except Exception as e:
        logger.error(f"[Calendar API] Error in get_events: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")

@router.get("/events/{source}", response_model=List[CalendarEvent])
async def get_events_by_source(
    source: str,
    days_ahead: int = Query(default=30, ge=1, le=365)
):
    """Get events from a specific source"""
    logger.info(f"[Calendar API] GET /events/{source}?days_ahead={days_ahead}")
    
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Calendar service not initialized")
    
    try:
        all_events = calendar_service.get_all_events(days_ahead)
        filtered = [e for e in all_events if e.source == source]
        logger.info(f"[Calendar API] Returning {len(filtered)} {source} events")
        return filtered
    except Exception as e:
        logger.error(f"[Calendar API] Error in get_events_by_source: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")

@router.post("/events", response_model=CalendarEvent, status_code=201)
async def create_event(event: CreateEventRequest):
    """Create a new calendar event"""
    logger.info(f"[Calendar API] POST /events - {event.title}")
    
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Calendar service not initialized")
    
    try:
        new_event = calendar_service.create_event(event)
        
        # Broadcast to WebSocket clients
        await calendar_manager.broadcast({
            "type": "event_created",
            "data": new_event.dict()
        })
        
        return new_event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Calendar API] Error in create_event: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")

@router.delete("/events/{source}/{event_id}")
async def delete_event(source: str, event_id: str):
    """Delete a calendar event"""
    logger.info(f"[Calendar API] DELETE /events/{source}/{event_id}")
    
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Calendar service not initialized")
    
    try:
        success = calendar_service.delete_event(event_id, source)
        
        # Broadcast to WebSocket clients
        await calendar_manager.broadcast({
            "type": "event_deleted",
            "data": {"source": source, "id": event_id}
        })
        
        return {"success": success, "message": "Event deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Calendar API] Error in delete_event: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")

@router.get("/cron", response_model=List[CronJob])
async def get_cron_jobs():
    """Get all scheduled cron jobs"""
    logger.info("[Calendar API] GET /cron")
    
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Calendar service not initialized")
    
    try:
        jobs = calendar_service.get_cron_jobs()
        logger.info(f"[Calendar API] Returning {len(jobs)} cron jobs")
        return jobs
    except Exception as e:
        logger.error(f"[Calendar API] Error in get_cron_jobs: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch cron jobs: {str(e)}")

@router.get("/sources")
async def get_calendar_sources():
    """Get available calendar sources"""
    logger.info("[Calendar API] GET /sources")
    
    sources = [
        {"id": "google", "name": "Google Calendar", "color": "#4285f4", "enabled": True},
        {"id": "local", "name": "Local Calendar", "color": "#34a853", "enabled": True},
        {"id": "apscheduler", "name": "Scheduled Jobs", "color": "#fbbc04", "enabled": True},
    ]
    
    # Check if executive agent has the required methods
    if calendar_service and calendar_service.executive:
        if not hasattr(calendar_service.executive, 'get_events_google'):
            sources[0]["enabled"] = False
            logger.warning("[Calendar] Google calendar not available")
        if not hasattr(calendar_service.executive, 'get_events_local'):
            sources[1]["enabled"] = False
            logger.warning("[Calendar] Local calendar not available")
    
    return {"sources": sources}

@router.get("/debug")
async def debug_info():
    """Debug endpoint to check calendar service status"""
    return {
        "service_initialized": calendar_service is not None,
        "executive_available": calendar_service.executive is not None if calendar_service else False,
        "has_google": hasattr(calendar_service.executive, 'get_events_google') if calendar_service and calendar_service.executive else False,
        "has_local": hasattr(calendar_service.executive, 'get_events_local') if calendar_service and calendar_service.executive else False,
        "active_ws_connections": len(calendar_manager.active_connections)
    }

# ====== Agent Chat Endpoint ======

class AgentChatRequest(BaseModel):
    """Request model for agent chat"""
    message: str = Field(..., description="User message to the scheduling agent")

class AgentChatResponse(BaseModel):
    """Response model for agent chat"""
    response: str
    events_changed: bool = False

@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest):
    """Chat with the scheduling agent"""
    logger.info(f"[Calendar Agent] Chat request: {request.message[:50]}...")
    
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Calendar service not initialized")
    
    if not calendar_service.executive:
        raise HTTPException(status_code=500, detail="Executive agent not available")
    
    try:
        # Process the message through the executive agent
        response_text = calendar_service.executive.process_query(request.message)
        
        # Check if response is None or empty
        if not response_text:
            response_text = "I've processed your request. Check your calendar for any updates."
        
        logger.info(f"[Calendar Agent] Response: {response_text[:50]}...")
        
        return AgentChatResponse(
            response=response_text,
            events_changed=True  # Assume events may have changed
        )
        
    except Exception as e:
        logger.error(f"[Calendar Agent] Error: {e}")
        logger.error(traceback.format_exc())
        
        # Return a friendly error message
        return AgentChatResponse(
            response=f"I encountered an error processing your request. Please try rephrasing or check the logs.",
            events_changed=False
        )

# ====== WebSocket Endpoint ======

@router.websocket("/ws")
async def calendar_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time calendar updates"""
    await calendar_manager.connect(websocket)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle different message types
            msg_type = data.get("type")
            
            if msg_type == "subscribe":
                # Client subscribing to updates
                await websocket.send_json({
                    "type": "subscribed",
                    "message": "Successfully subscribed to calendar updates"
                })
            
            elif msg_type == "refresh":
                # Client requesting data refresh
                if calendar_service:
                    try:
                        events = calendar_service.get_all_events(30)
                        await websocket.send_json({
                            "type": "events_update",
                            "data": [e.dict() for e in events]
                        })
                    except Exception as e:
                        logger.error(f"[Calendar WS] Error refreshing events: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e)
                        })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        calendar_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[Calendar WS] Error: {e}")
        logger.error(traceback.format_exc())
        calendar_manager.disconnect(websocket)

# ====== Background Tasks ======

async def periodic_event_broadcast():
    """Periodically broadcast updated events to all clients"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        
        if calendar_service and calendar_manager.active_connections:
            try:
                events = calendar_service.get_all_events(30)
                await calendar_manager.broadcast({
                    "type": "events_update",
                    "data": [e.dict() for e in events]
                })
            except Exception as e:
                logger.error(f"[Calendar] Error in periodic broadcast: {e}")