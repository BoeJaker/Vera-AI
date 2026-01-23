#!/usr/bin/env python3
"""
Calendar Integration for Proactive Focus
========================================
Integrates with local calendar (ICS format) to schedule proactive thoughts.

Features:
- Schedule proactive thinking sessions
- Recurring thought schedules
- Calendar-aware execution
- Automatic rescheduling based on system availability
- Integration with existing calendar UI
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
from ics import Calendar, Event
from ics.grammar.parse import ContentLine
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY
import uuid

logger = logging.getLogger(__name__)


class ProactiveThoughtEvent:
    """Represents a scheduled proactive thought session"""
    
    def __init__(
        self,
        name: str,
        begin: datetime,
        end: datetime,
        focus: str,
        stages: Optional[List[str]] = None,
        priority: str = "normal",
        recurrence_rule: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.uid = str(uuid.uuid4())
        self.name = name
        self.begin = begin
        self.end = end
        self.focus = focus
        self.stages = stages or []
        self.priority = priority
        self.recurrence_rule = recurrence_rule
        self.metadata = metadata or {}
    
    def to_ics_event(self) -> Event:
        """Convert to ICS event"""
        event = Event()
        event.uid = self.uid
        event.name = f"[Proactive] {self.name}"
        event.begin = self.begin
        event.end = self.end
        event.description = f"""Proactive Thought Session
Focus: {self.focus}
Stages: {', '.join(self.stages) if self.stages else 'All'}
Priority: {self.priority}

Metadata:
{self.metadata}
"""
        
        # Add custom metadata as ContentLine objects
        event.extra.append(ContentLine(name="X-PROACTIVE-FOCUS", value=self.focus))
        event.extra.append(ContentLine(name="X-PROACTIVE-PRIORITY", value=self.priority))
        
        if self.stages:
            event.extra.append(ContentLine(name="X-PROACTIVE-STAGES", value=','.join(self.stages)))
        
        if self.recurrence_rule:
            event.extra.append(ContentLine(name="RRULE", value=self.recurrence_rule))
        
        return event
    
    @classmethod
    def from_ics_event(cls, event: Event) -> Optional['ProactiveThoughtEvent']:
        """Create from ICS event"""
        # Check if it's a proactive thought event
        if not event.name or '[Proactive]' not in event.name:
            return None
        
        # Extract metadata from extra fields
        focus = None
        stages = []
        priority = "normal"
        recurrence_rule = None
        
        for extra_line in event.extra:
            if extra_line.startswith('X-PROACTIVE-FOCUS:'):
                focus = extra_line.split(':', 1)[1]
            elif extra_line.startswith('X-PROACTIVE-STAGES:'):
                stages = extra_line.split(':', 1)[1].split(',')
            elif extra_line.startswith('X-PROACTIVE-PRIORITY:'):
                priority = extra_line.split(':', 1)[1]
            elif extra_line.startswith('RRULE:'):
                recurrence_rule = extra_line
        
        if not focus:
            # Try to extract from description
            if event.description and 'Focus:' in event.description:
                for line in event.description.split('\n'):
                    if line.startswith('Focus:'):
                        focus = line.split(':', 1)[1].strip()
                        break
        
        if not focus:
            return None  # Not a valid proactive thought event
        
        thought_event = cls(
            name=event.name.replace('[Proactive]', '').strip(),
            begin=event.begin.datetime if hasattr(event.begin, 'datetime') else event.begin,
            end=event.end.datetime if hasattr(event.end, 'datetime') else event.end,
            focus=focus,
            stages=stages if stages else None,
            priority=priority,
            recurrence_rule=recurrence_rule
        )
        
        thought_event.uid = event.uid
        
        return thought_event


class CalendarScheduler:
    """Manages scheduling of proactive thoughts in local calendar"""
    
    def __init__(self, calendar_file: str = "./local_calendar.ics"):
        self.calendar_file = Path(calendar_file)
        self.calendar = Calendar()
        
        if os.path.exists(self.calendar_file):
            with open(self.calendar_file, 'r') as f:
                content = f.read()
                
                if not content.strip():
                    logger.info("[Calendar] File is empty, creating new calendar")
                    self.calendar = Calendar()
                else:
                    try:
                        # Try normal parsing first
                        self.calendar = Calendar(content)
                    except NotImplementedError:
                        # Handle multiple calendars in one file
                        calendars = list(Calendar.parse_multiple(content))
                        self.calendar = calendars[0] if calendars else Calendar()
                        if len(calendars) > 1:
                            logger.info(f"[Calendar] Using first of {len(calendars)} calendars")
    
    def save_calendar(self):
        """Save calendar to file"""
        try:
            with open(self.calendar_file, 'w') as f:
                f.writelines(self.calendar.serialize_iter())
            logger.debug("[Calendar] Calendar saved successfully")
        except Exception as e:
            logger.error(f"Failed to save calendar: {e}")
            raise
    
    def schedule_thought_session(
        self,
        start_time: datetime,
        duration_minutes: int = 30,
        recurrence: str = None,
        focus: str = None,
        stages: list = None,
        priority: str = "normal"
    ):
        """Schedule a proactive thinking session"""
        
        event = Event()
        event.name = f"Proactive Focus: {focus or 'Current Focus'}"
        event.begin = start_time
        event.duration = timedelta(minutes=duration_minutes)
        event.description = f"Automated proactive thinking session"
        
        # Add custom properties using ContentLine objects
        if focus:
            event.extra.append(ContentLine(name="X-VERA-FOCUS", value=focus))
        
        if stages:
            event.extra.append(ContentLine(name="X-VERA-STAGES", value=",".join(stages)))
        
        # Add session type marker
        event.extra.append(ContentLine(name="X-VERA-TYPE", value="PROACTIVE-SESSION"))
        
        # Add priority
        event.extra.append(ContentLine(name="X-VERA-PRIORITY", value=priority))
        
        # Handle recurrence
        if recurrence == "daily":
            # Daily for 7 days
            event.extra.append(ContentLine(name="RRULE", value="FREQ=DAILY;COUNT=7"))
        elif recurrence == "weekly":
            # Weekly for 4 weeks
            event.extra.append(ContentLine(name="RRULE", value="FREQ=WEEKLY;COUNT=4"))
        
        self.calendar.events.add(event)
        self.save_calendar()
        
        # Create ProactiveThoughtEvent for return
        thought_event = ProactiveThoughtEvent(
            name=event.name,
            begin=event.begin,
            end=event.begin + timedelta(minutes=duration_minutes),
            focus=focus or 'Current Focus',
            stages=stages,
            priority=priority,
            recurrence_rule=recurrence
        )
        thought_event.uid = event.uid
        
        logger.info(f"[Calendar] Scheduled thought session: {focus} at {start_time}")
        
        return thought_event


    def schedule_daily_thoughts(
        self,
        focus: str,
        start_time: str,  # e.g., "14:00"
        duration_minutes: int = 30,
        days: int = 7,
        stages: Optional[List[str]] = None
    ) -> List[ProactiveThoughtEvent]:
        """Schedule daily thought sessions"""
        hour, minute = map(int, start_time.split(':'))
        
        events = []
        start_date = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        for day in range(days):
            session_time = start_date + timedelta(days=day)
            
            event = self.schedule_thought_session(
                focus=focus,
                start_time=session_time,
                duration_minutes=duration_minutes,
                stages=stages
            )
            
            events.append(event)
        
        logger.info(f"[Calendar] Scheduled {len(events)} daily thought sessions")
        return events
    
    def schedule_weekly_thoughts(
        self,
        focus: str,
        day_of_week: int,  # 0=Monday, 6=Sunday
        start_time: str,
        duration_minutes: int = 60,
        weeks: int = 4,
        stages: Optional[List[str]] = None
    ) -> List[ProactiveThoughtEvent]:
        """Schedule weekly thought sessions"""
        hour, minute = map(int, start_time.split(':'))
        
        # Find next occurrence of day_of_week
        today = datetime.now()
        days_ahead = day_of_week - today.weekday()
        if days_ahead < 0:
            days_ahead += 7
        
        next_occurrence = today + timedelta(days=days_ahead)
        start_date = next_occurrence.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        events = []
        
        for week in range(weeks):
            session_time = start_date + timedelta(weeks=week)
            
            event = self.schedule_thought_session(
                focus=focus,
                start_time=session_time,
                duration_minutes=duration_minutes,
                stages=stages
            )
            
            events.append(event)
        
        logger.info(f"[Calendar] Scheduled {len(events)} weekly thought sessions")
        return events
    
    def get_upcoming_thought_sessions(
        self,
        days_ahead: int = 7
    ) -> List[ProactiveThoughtEvent]:
        """Get upcoming proactive thought sessions"""
        now = datetime.now()
        future_limit = now + timedelta(days=days_ahead)
        
        upcoming = []
        
        for event in self.calendar.events:
            # Check if it's a proactive thought event
            thought_event = ProactiveThoughtEvent.from_ics_event(event)
            
            if thought_event:
                event_time = thought_event.begin
                
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
                
                now_aware = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
                future_aware = future_limit if future_limit.tzinfo else future_limit.replace(tzinfo=timezone.utc)
                
                if now_aware <= event_time <= future_aware:
                    upcoming.append(thought_event)
        
        # Sort by start time
        upcoming.sort(key=lambda e: e.begin)
        
        logger.debug(f"[Calendar] Found {len(upcoming)} upcoming thought sessions")
        return upcoming
    
    def get_next_thought_session(self) -> Optional[ProactiveThoughtEvent]:
        """Get the next scheduled thought session"""
        upcoming = self.get_upcoming_thought_sessions(days_ahead=30)
        
        if upcoming:
            return upcoming[0]
        
        return None
    
    def cancel_thought_session(self, event_uid: str) -> bool:
        """Cancel a scheduled thought session"""
        for event in list(self.calendar.events):
            if event.uid == event_uid:
                self.calendar.events.remove(event)
                self.save_calendar()
                logger.info(f"Cancelled thought session: {event_uid}")
                return True
        
        logger.warning(f"Thought session not found: {event_uid}")
        return False
    
    def reschedule_thought_session(
        self,
        event_uid: str,
        new_start_time: datetime,
        new_duration_minutes: Optional[int] = None
    ) -> bool:
        """Reschedule a thought session"""
        for event in self.calendar.events:
            if event.uid == event_uid:
                # Extract thought event
                thought_event = ProactiveThoughtEvent.from_ics_event(event)
                
                if not thought_event:
                    return False
                
                # Remove old event
                self.calendar.events.remove(event)
                
                # Calculate new duration
                if new_duration_minutes is None:
                    original_duration = (thought_event.end - thought_event.begin).total_seconds() / 60
                    new_duration_minutes = int(original_duration)
                
                # Schedule new event
                self.schedule_thought_session(
                    focus=thought_event.focus,
                    start_time=new_start_time,
                    duration_minutes=new_duration_minutes,
                    stages=thought_event.stages,
                    priority=thought_event.priority,
                    recurrence=thought_event.recurrence_rule
                )
                
                logger.info(f"Rescheduled thought session: {event_uid} to {new_start_time}")
                
                return True
        
        logger.warning(f"Thought session not found for rescheduling: {event_uid}")
        return False
    
    def suggest_optimal_time(
        self,
        duration_minutes: int = 30,
        days_ahead: int = 7,
        preferred_hours: Optional[List[int]] = None
    ) -> Optional[datetime]:
        """
        Suggest optimal time for thought session based on calendar availability.
        
        Args:
            duration_minutes: Required duration
            days_ahead: How many days ahead to search
            preferred_hours: Preferred hours of day (e.g., [9, 10, 14, 15])
        
        Returns:
            Suggested datetime or None if no suitable time found
        """
        if preferred_hours is None:
            preferred_hours = [9, 10, 11, 14, 15, 16]  # Default work hours
        
        now = datetime.now()
        
        # Get all events in the next week
        future_events = [
            event for event in self.calendar.events
            if hasattr(event.begin, 'datetime') and
            now <= event.begin.datetime <= now + timedelta(days=days_ahead)
        ]
        
        # Check each day
        for day_offset in range(days_ahead):
            check_date = now + timedelta(days=day_offset)
            
            # Check each preferred hour
            for hour in preferred_hours:
                candidate_time = check_date.replace(
                    hour=hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                
                # Skip if in the past
                if candidate_time <= now:
                    continue
                
                candidate_end = candidate_time + timedelta(minutes=duration_minutes)
                
                # Check if this time slot is free
                is_free = True
                
                for event in future_events:
                    event_start = event.begin.datetime if hasattr(event.begin, 'datetime') else event.begin
                    event_end = event.end.datetime if hasattr(event.end, 'datetime') else event.end
                    
                    # Check for overlap
                    if not (candidate_end <= event_start or candidate_time >= event_end):
                        is_free = False
                        break
                
                if is_free:
                    logger.info(f"Suggested optimal time: {candidate_time}")
                    return candidate_time
        
        logger.warning("No optimal time found in the specified range")
        return None


    def get_upcoming_sessions(self, days_ahead: int = 7) -> List[Event]:
        """Alias for get_upcoming_thought_sessions for API compatibility"""
        return self.get_upcoming_thought_sessions(days_ahead=days_ahead)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scheduler = CalendarScheduler()
    
    # Schedule a one-time thought session
    focus = "Vera AI Development"
    start_time = datetime.now() + timedelta(hours=2)
    
    event = scheduler.schedule_thought_session(
        focus=focus,
        start_time=start_time,
        duration_minutes=30,
        stages=["Research", "Evaluation", "Steering"]
    )
    
    print(f"\nScheduled thought session:")
    print(f"  Focus: {event.focus}")
    print(f"  Start: {event.begin}")
    print(f"  Duration: {(event.end - event.begin).total_seconds() / 60:.0f} minutes")
    print(f"  Stages: {', '.join(event.stages)}")
    
    # Schedule daily thoughts for a week
    daily_events = scheduler.schedule_daily_thoughts(
        focus="Daily Review",
        start_time="14:00",
        duration_minutes=15,
        days=7,
        stages=["Introspection", "Evaluation"]
    )
    
    print(f"\nScheduled {len(daily_events)} daily thought sessions")
    
    # Get upcoming sessions
    upcoming = scheduler.get_upcoming_thought_sessions(days_ahead=7)
    
    print(f"\nUpcoming thought sessions ({len(upcoming)}):")
    for session in upcoming[:5]:
        print(f"  - {session.begin.strftime('%Y-%m-%d %H:%M')}: {session.focus}")
    
    # Suggest optimal time
    optimal = scheduler.suggest_optimal_time(
        duration_minutes=30,
        days_ahead=3
    )
    
    if optimal:
        print(f"\nSuggested optimal time for next session: {optimal}")