"""
StreamingHandler - Manages UI output streaming and progress tracking.
Provides clean interface for stage updates and progress reporting.
"""

from typing import Optional
from datetime import datetime


class StreamingHandler:
    """
    Handles streaming output to UI and progress tracking.
    Maintains current stage state for display.
    """
    
    def __init__(self):
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
        self.output_buffer = []
    
    def set_stage(self, stage: str, activity: str = "", total_steps: int = 0):
        """Set current stage information."""
        self.current_stage = stage
        self.current_activity = activity
        self.stage_progress = 0
        self.stage_total = total_steps
        
        print(f"[Stage] {stage} - {activity}")
    
    def update_progress(self, increment: int = 1):
        """Update stage progress."""
        self.stage_progress += increment
        
        if self.stage_total > 0:
            percentage = (self.stage_progress / self.stage_total) * 100
            print(f"[Progress] {self.stage_progress}/{self.stage_total} ({percentage:.0f}%)")
    
    def stream_output(self, text: str, category: str = "info"):
        """Stream output text with category."""
        
        # Add to buffer
        self.output_buffer.append({
            "text": text,
            "category": category,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Print with category prefix
        prefix = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }.get(category, "•")
        
        print(f"{prefix} {text}")
    
    def clear_stage(self):
        """Clear current stage."""
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
    
    def get_stage_info(self) -> dict:
        """Get current stage information."""
        return {
            "stage": self.current_stage,
            "activity": self.current_activity,
            "progress": self.stage_progress,
            "total": self.stage_total,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_progress_info(self) -> dict:
        """Get current progress information."""
        percentage = 0
        if self.stage_total > 0:
            percentage = (self.stage_progress / self.stage_total) * 100
        
        return {
            "stage": self.current_stage,
            "progress": self.stage_progress,
            "total": self.stage_total,
            "percentage": percentage
        }
    
    def get_output_buffer(self, limit: Optional[int] = None) -> list:
        """Get recent output buffer."""
        if limit:
            return self.output_buffer[-limit:]
        return self.output_buffer
    
    def clear_output_buffer(self):
        """Clear output buffer."""
        self.output_buffer = []