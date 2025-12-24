#!/usr/bin/env python3
""" 
# executive.py
# A comprehensive scheduling agent that integrates various tools and LLMs.
# Combines proactive scheduling, memory management, and LangChain tools.
# Capable of handling Google Calendar, local calendar, and project management.
# Can be run as a standalone script or imported as a module.
# Usage: python executive.py
# Requires: langchain, ollama, chromadb, apscheduler, ics, dateutil
# 
# Components:
# - Google Calendar Integration: Uses service account to manage events.
# - Local Calendar Management: Uses ICS format for local calendar events.
# - Proactive Scheduler: Checks tasks and deadlines every hour.
# - LangChain Tools: Provides various tools for calendar management, project tracking, and more.
# - Memory Management: Uses ChromaDB for storing conversation history and context.
# - LLMs: Uses Ollama models for fast and deep reasoning tasks.
# 
# Structure:
# - Initializes memory and tools
# - Starts the proactive scheduler
# - Provides a command-line interface for user interaction
# """

import os
import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from ics import Calendar, Event
from dateutil import parser
import dateparser
import psutil

# Google Calendar imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from langchain.agents import initialize_agent, Tool, AgentType

# from langchain.chat_models import ChatOllama
from langchain_ollama import ChatOllama
# from langchain_community.llms import Ollama
# from langchain_community.chat_models import ChatOllama
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.memory import ConversationBufferMemory

# ====== CONFIG ======
MODEL = "gemma3:12b"
PROJECTS_DIR = Path("./projects")
LOCAL_CALENDAR_FILE = Path("./local_calendar.ics")
SERVICE_ACCOUNT_FILE = "./Vera/Configuration/keys/service.json"  # <-- New
GOOGLE_CALENDAR_ID = "primary"  # Replace with calendar ID if not using primary
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class executive:
    def __init__(self, vera_instance):

        self.vera_instance = vera_instance

        self.query = None
        self.query_prefix = "User: "
        self.query_suffix = "\nAssistant: "
        self.debug_header = f"[Executive Agent {MODEL}]"
        # ====== Initialize Memory and LLMs ======
        if not self.vera_instance:
            self.llm = ChatOllama(model=MODEL, temperature=0)
            self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        else:
            # self.llm = self.vera_instance.fast_llm
            self.llm = self.vera_instance.deep_llm
            # self.agent = self.vera_instance.deep_agent
            self.memory = self.vera_instance.memory
            # self.memory = ChromaDBMemory(
            #     collection_name="executive_memory",
            #     embedding_function=self.llm.embed_query,
            #     return_messages=True,
            #     client=None,  # Use default client
            #     persist_directory="./chroma_db"
            # )

        # ====== LangChain Tools ======
        self.tools = [
        Tool(
            name="Get the time and date",
            func=lambda q: datetime.datetime.now().isoformat(),
            description="Get the current time and date in ISO format."
        ),
        Tool(
            name="Add Google Calendar Event",
            func=lambda q: self.add_event_google(
                *self.parse_args(
                    q,
                    [
                        "Test Event", 
                        datetime.datetime.utcnow(), 
                        datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                    ]
                )
            ),
            description="Add an event to Google Calendar. Format: 'title|start_datetime|end_datetime'"
        ),
        Tool(
            name="Add Recurring Google Calendar Event",
            func=lambda q: self.add_recuring_event_google(
                *self.parse_args(q,["","","","RRULE:FREQ=DAILY;COUNT=10"])
            ),
            description="Add a recurring event to Google Calendar. Format: 'title|start_datetime|end_datetime|recurrence_rule' (e.g., 'RRULE:FREQ=DAILY;COUNT=10')."
        ),
        Tool(
            name="Delete Google Calendar Event",
            func=lambda q: self.delete_event_google(q),
            description="Delete an event from Google Calendar. Input: 'event_id' (the ID of the event to delete)."
        ),
        Tool(
            name="Get Google Calendar Events",
            func=lambda q: self.get_events_google(q),
            description="Get upcoming Google Calendar events. Inputs: integer 'days_ahead' (default 7 days) i.e. 7. how many days ahead from today to check for events. returns a list of events from today to today+days_ahead with title, start, end."
        ),
        Tool(
            name="Add Local Calendar Event",
            func=lambda q: self.add_event_local(
                *self.parse_args(
                    q,
                    [
                        "Test Event", 
                        datetime.datetime.utcnow(), 
                        datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                    ]
                )
            ),
            description="Add an event to the local calendar. Format: 'title|start_datetime|end_datetime'"
        ),
        Tool(
            name="Add Recurring Local Calendar Event",
            func=lambda q: self.add_recurring_event_local(
                *self.parse_args(q,["","","","RRULE:FREQ=DAILY;COUNT=10"])
            ),
            description="Add a recurring event to the local calendar. Format: 'title|start_datetime|end_datetime|recurrence_rule' (e.g., 'RRULE:FREQ=DAILY;COUNT=10')."
        ),
        
        Tool(
            name="Delete Local Calendar Event",
            func=lambda q: self.delete_event_local(q),
            description="Delete an event from Google Calendar. Input: 'event_name' (the name of the event to delete)."
        ),

        Tool(
            name="Get Local Calendar Events",
            func=lambda q: self.get_events_local(q),
            description="Get upcoming local calendar events. Inputs: type=integer name='days_ahead' (default 7 days) i.e. 7 . How many days ahead to check for events."
        ),
        Tool(
            name="List Projects",
            func=lambda q: self.list_projects(),
            description="List available projects. Ignores arguments."
        ),
        Tool(
            name="Read Project",
            func=lambda q: self.read_project(
                *self.parse_args(q, ["default_project"])
            ),
            description="Read files from a project folder. Format: 'project_name'"
        ),
        Tool(
            name="Update Project",
            func=lambda q: self.update_project(
                *self.parse_args(q, ["default_project", "No updates yet"])
            ),
            description="Update project progress. Format: 'project_name|note'"
        ),
        Tool(
            name="Ask_User",
            func=lambda q: input(9),  # expects a natural language date string
            description="Ask the user for input. can be used to clarify, detail about a query, the best course of action, conflict resolution. Expects a user input prompt as a string"
        )        
        ]
        # ====== Fallback Agent ======
        # if not self.vera_instance:
        self.agent = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True, # Fail gracefully
        )

    # ====== Google Calendar Setup ======
    def get_google_calendar_service(self):
        """
        Returns a Google Calendar API service object using a service account.
        """
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )

        # If accessing a user's calendar rather than the service account's own calendar:
        # creds = creds.with_subject("user@example.com")

        return build("calendar", "v3", credentials=creds)

    # ====== Calendar Tools ======
    def add_event_google(self, summary, start_time, end_time):
        service = self.get_google_calendar_service()
        event = {
            "summary": summary,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        }
        service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        return f"Event '{summary}' added to Google Calendar."
    
    def add_recuring_event_google(self, summary, start_time, end_time, recurrence_rule):
        service = self.get_google_calendar_service()
        event = {
            "summary": summary,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
            "recurrence": [recurrence_rule]  # e.g. "RRULE:FREQ=DAILY;COUNT=10"
        }
        service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        return f"Recurring event '{summary}' added to Google Calendar with rule '{recurrence_rule}'."
    
    def delete_event_google(self, event_id):
        service = self.get_google_calendar_service()
        try:
            service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
            return f"Event with ID '{event_id}' deleted from Google Calendar."
        except Exception as e:
            return f"Failed to delete event: {str(e)}"
        
    def get_events_google(self, days_ahead=7):
        service = self.get_google_calendar_service()
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        future_limit = now + datetime.timedelta(days=int(days_ahead))
        days_ahead = int(days_ahead) if isinstance(days_ahead, int) else 7
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=future_limit.isoformat(),
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        items = events_result.get("items", [])
        events = []

        for e in items:
            start = e["start"].get("dateTime", e["start"].get("date"))
            end = e["end"].get("dateTime", e["end"].get("date"))

            # Parse to datetime (handles date-only and datetime formats)
            start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))

            events.append({
                "title": e.get("summary", "No Title"),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "source": "google",
                "event_id": e.get("id", "No ID")
            })

        return events


    def add_event_local(self, summary, start_time, end_time):
        cal = Calendar()
        if LOCAL_CALENDAR_FILE.exists():
            with open(LOCAL_CALENDAR_FILE, "r") as f:
                cal = Calendar(f.read())
        event = Event()
        event.name = summary
        event.begin = start_time
        event.end = end_time
        cal.events.add(event)
        with open(LOCAL_CALENDAR_FILE, "w") as f:
            f.writelines(cal.serialize_iter())
        return f"Event '{summary}' added to local calendar."

    def add_recurring_event_local(self, summary, start_time, end_time, recurrence_rule):
        """
        Adds a recurring event to the local calendar file.
        
        Args:
            summary (str): The title of the event.
            start_time (datetime): The start time of the event.
            end_time (datetime): The end time of the event.
            recurrence_rule (str): The recurrence rule in iCalendar format (e.g., "RRULE:FREQ=DAILY;COUNT=10").
        """
        cal = Calendar()
        if LOCAL_CALENDAR_FILE.exists():
            with open(LOCAL_CALENDAR_FILE, "r") as f:
                cal = Calendar(f.read())
        
        event = Event()
        event.name = summary
        event.begin = start_time
        event.end = end_time
        event.extra.append(recurrence_rule)  # Add the recurrence rule to the event
        
        cal.events.add(event)
        
        with open(LOCAL_CALENDAR_FILE, "w") as f:
            f.writelines(cal.serialize_iter())
        
        return f"Recurring event '{summary}' added to local calendar with rule '{recurrence_rule}'."
        

    def delete_event_local(self, event_name):
        if not LOCAL_CALENDAR_FILE.exists():
            return "Local calendar file does not exist."
        with open(LOCAL_CALENDAR_FILE, "r") as f:
            cal = Calendar(f.read())
        for event in cal.events:
            if event.name == event_id:
                cal.events.remove(event)
                with open(LOCAL_CALENDAR_FILE, "w") as f:
                    f.writelines(cal.serialize_iter())
                return f"Event '{event_id}' deleted from local calendar."
            
    def get_events_local(self, days_ahead=7):
        if not LOCAL_CALENDAR_FILE.exists():
            return []

        try:
            days_ahead = int(days_ahead)
        except (ValueError, TypeError):
            days_ahead = 7  # fallback default

        with open(LOCAL_CALENDAR_FILE, "r") as f:
            cal = Calendar(f.read())

        now = datetime.datetime.now(datetime.timezone.utc)
        future_limit = now + datetime.timedelta(days=int(days_ahead))

        events = []
        for e in cal.events:
            if not e.begin:
                continue
            try:
                start = e.begin.datetime.astimezone(datetime.timezone.utc)
                end = e.end.datetime.astimezone(datetime.timezone.utc) if e.end else None

                if now <= start <= future_limit:
                    events.append({
                        "title": e.name,
                        "start": start.isoformat(),
                        "end": end.isoformat() if end else None,
                        "source": "local",
                        "event_id": e.name  # Using name as ID for simplicity
                    })
            except Exception as ex:
                print(f"Skipping event {e} due to error: {ex}")
                continue

        return events

    # ====== Project File Tools ======
    # needs moving to a separate module
    def list_projects(self):
        projects = [p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()]
        return f"Projects: {', '.join(projects)}" if projects else "No projects found."

    def read_project(self, project_name):
        project_path = PROJECTS_DIR / project_name
        if not project_path.exists():
            return "Project not found."
        files = []
        for f in project_path.glob("**/*"):
            if f.is_file():
                with open(f, "r") as file:
                    files.append(f"{f.name}:\n{file.read()}")
        return "\n\n".join(files)

    def update_project(self, project_name, note):
        project_path = PROJECTS_DIR / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        note_file = project_path / "progress.txt"
        with open(note_file, "a") as f:
            f.write(f"{datetime.datetime.now()}: {note}\n")
        return f"Progress updated for {project_name}."

    def parse_natural_date(self, date_str):
        dt = dateparser.parse(date_str)
        if dt is None:
            raise ValueError(f"Could not parse date: {date_str}")
        return dt

    def parse_args(self, q, defaults):
        parts = str(q).split("|") if q else []
        results = []
        for i, default in enumerate(defaults):
            if i < len(parts) and parts[i]:
                val = parts[i]
                # Try parsing datetime if default is a datetime object
                if isinstance(default, datetime.datetime):
                    val = self.parse_natural_date(val)
                results.append(val)
            else:
                results.append(default)
        return results

    # ====== Proactive Scheduler ======
    def proactive_check(self):
        print("[Proactive] Starting proactive task check...")

        # 1. Get events from calendars
        gcal_events = self.get_events_google()
        local_events = self.get_events_local()
        
        # 2. Get projects and progress
        projects = self.list_projects()

        # 3. Let LLM decide best actions
        context = f"""
    You are a productivity assistant. 
    Here is the current situation:

    Google Calendar events:
    {gcal_events}

    Local Calendar events:
    {local_events}

    Active projects:
    {projects}

    Progress notes for each project:
    """

        for project in PROJECTS_DIR.iterdir():
            if project.is_dir():
                notes = self.read_project(project.name)
                context += f"\n--- {project.name} ---\n{notes}\n"

        context += """
    Analyze this information. Identify:
    1. Any deadlines within the next 7 days.
    2. Any overdue tasks.
    3. Any large empty time blocks in the next 48 hours.
    4. Which project(s) need the most urgent work.
    5. Suggest specific work sessions to schedule during free time.
    6. Suggest splitting or re-prioritizing tasks if needed.

    Respond in a short action plan format.
    """

        suggestions = self.llm.invoke(context)
        print("[Proactive] Suggested plan:")
        print(suggestions)

        # 4. Optionally auto-add suggestions to calendar
        if "AUTO_APPROVE" in os.environ.get("ASSISTANT_MODE", ""):
            for line in suggestions.split("\n"):
                if "Schedule:" in line:
                    try:
                        task, time_info = line.split("Schedule:", 1)
                        start_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                        end_time = start_time + datetime.timedelta(hours=2)
                        self.add_event_google(task.strip(), start_time, end_time)
                        print(f"[Proactive] Scheduled: {task.strip()}")
                    except Exception as e:
                        print(f"[Proactive] Failed to schedule: {e}")

    def process_query(self, query):
        query += f"""System: You are a scheduling assistant. Your role is to help the user manage their calendar responsibly and flexibly.
                    Rules:
                    1. Treat all scheduled events (work, leisure, personal, social, projects, etc.) as important by default.  
                    2. Do not double-book events unless the user explicitly approves or context strongly implies it (e.g., meetings during work shifts).  
                    3. If a new request conflicts with an existing event:
                    - Inform the user of the conflict.  
                    - Suggest alternative times (nearest available slots before or after).  
                    - Offer options to reschedule, replace, or merge events if appropriate (e.g., replace “programming project” with “beach trip”).  
                    4. If the user clearly indicates a replacement, update the calendar accordingly.  
                    5. If the user insists on a conflict, confirm before scheduling.  
                    6. Always use ISO8601 datetime format when calling tools.  
                    7. Only output one of the following at a time:
                    - An **Action** with its input  
                    - A **Final Answer**  
                    Never both in the same step.   

                    Your goal is to keep the user’s calendar manageable, conflict-free, and flexible, while respecting their intent.
                    \n"""
        query += f"System: Please be careful to precisely fulfil the users request, do not mix up dates like today and tomorrow. tools may output excess or unrealted data that you will need to filter \n"
        query += f"system: If you can answer the user query with the information below, please avoid using tools, as you will likely be pulling the same data\n"
        query += f"system: The current date and time: {datetime.datetime.now().isoformat(),}\n"
        query += f"system: Day of the week: {datetime.datetime.now().strftime('%A')}\n"
        query += f"system: Local calendar events (next 7 days) \n{self.get_events_local()}\n"
        query += f"system: Google calendar events (next 7 days)\n{self.get_events_google()}\n"
        # query += """You are an agent that decides between taking an action or returning a final answer. 
        #             - If you must call a tool, output ONLY in the format:
        #             Action: <tool name>
        #             Action Input: <input>
        #             - If you are ready to answer the user directly, output ONLY:
        #             Final Answer: <answer>
        #             Do not output both in the same step."""
        response = self.agent.run(query)
        print(f"Assistant: {response}")
        query = None  # Reset query for next iteration

    # ====== Main Loop ======
    def main(self, query, agent=None):
        if agent is None: agent = self.agent
        print(self.debug_header + " Starting executive agent...")
        if query is None: 
            while True:
                query = input("User: ")
                if query.lower() in ["exit", "quit"]:
                    break
                self.process_query(query)
        else:
            self.process_query(query)
                
def run_when_idle(func, threshold=20):
    def wrapper():
        if psutil.cpu_percent(interval=1) < threshold:
            func()
        else:
            print("[Scheduler] Skipped: CPU load too high.")
    return wrapper
    
if __name__ == "__main__":
    
    executive_instance = executive(vera_instance=None)    

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_when_idle(executive_instance.proactive_check), "interval", minutes=60)  # every hour
    scheduler.start()
    # executive_instance.proactive_check()
    executive_instance.main(None)

# # Fast Agent
# # ==========
# from langchain.agents import initialize_agent, Tool
# from langchain.memory import ConversationBufferMemory
# from langchain_community.llms import Ollama
# import json

# def load_memory():
#     try:
#         with open("assistant_memory.json", "r") as f:
#             return json.load(f)
#     except FileNotFoundError:
#         return {"thoughts": [], "suggested_actions": [], "upcoming_deadlines": []}

# def greet_user():
#     mem = load_memory()
#     if mem["thoughts"]:
#         greeting = "Here's what I’ve been thinking since we last spoke:\n"
#         for t in mem["thoughts"]:
#             greeting += f" - {t}\n"
#         return greeting
#     return "Good to see you! No new thoughts since last time."

# def fast_agent():
#     llm = Ollama(model="gemma3:12b")
#     tools = [
#         Tool(name="Google Calendar", func=read_google_calendar, description="Read Google calendar events"),
#         Tool(name="Local Calendar", func=read_local_calendar, description="Read local calendar events"),
#         Tool(name="Write File", func=write_file, description="Save notes or progress")
#     ]
#     memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
#     agent = initialize_agent(tools, llm, agent="zero-shot-react-description", memory=memory, verbose=True)
    
#     print(greet_user())
#     while True:
#         query = input("You: ")
#         print(agent.run(query))


# # Slow Planner
# # =================================
# import json
# import psutil
# from datetime import datetime
# from langchain_community.llms import Ollama

# def is_system_idle(threshold=20):
#     return psutil.cpu_percent(interval=1) < threshold

# def load_projects():
#     # Example: read local files with project notes
#     return "Alpha: 80% done, Beta: delayed testing, Gamma: no updates."

# def update_memory(new_thoughts, new_suggestions):
#     try:
#         with open("assistant_memory.json", "r") as f:
#             mem = json.load(f)
#     except FileNotFoundError:
#         mem = {}
#     mem["thoughts"] = new_thoughts
#     mem["suggested_actions"] = new_suggestions
#     mem["last_check"] = datetime.utcnow().isoformat()
#     with open("assistant_memory.json", "w") as f:
#         json.dump(mem, f, indent=2)

# def slow_planner():
#     if not is_system_idle():
#         return
#     llm = Ollama(model="gemma3:12b", temperature=0.4)
#     projects = load_projects()
#     prompt = f"""
#     Analyze these project statuses and suggest improvements:
#     {projects}

#     Provide:
#     1. Observations
#     2. Suggested actions
#     """
#     analysis = llm(prompt)
#     new_thoughts = [line.strip() for line in analysis.split("\n") if line.strip()]
#     update_memory(new_thoughts, ["Follow up on delayed Beta testing"])

# if __name__ == "__main__":
#     slow_planner()
