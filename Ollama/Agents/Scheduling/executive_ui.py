#!/usr/bin/env python3
"""
streamlit_ui.py
A modern Streamlit UI for the Executive Scheduling Agent
Usage: streamlit run streamlit_ui.py
"""

import streamlit as st
import datetime
from pathlib import Path
import sys

# Import the executive agent
from Agents.Scheduling.executive_0_9 import executive

# Page configuration
st.set_page_config(
    page_title="Executive Scheduling Agent",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .event-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    .google-event {
        background-color: #e8f4f8;
        border-color: #4285f4;
    }
    .local-event {
        background-color: #f0f8e8;
        border-color: #34a853;
    }
    .stButton>button {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'executive_agent' not in st.session_state:
    st.session_state.executive_agent = None
    st.session_state.chat_history = []
    st.session_state.initialized = False

def initialize_agent():
    """Initialize the executive agent"""
    try:
        with st.spinner("Initializing agent..."):
            st.session_state.executive_agent = executive(vera_instance=None)
            st.session_state.initialized = True
            st.success("✅ Agent initialized successfully!")
    except Exception as e:
        st.error(f"❌ Failed to initialize agent: {str(e)}")
        st.session_state.initialized = False

def format_event(event):
    """Format an event for display"""
    source_color = "google-event" if event['source'] == 'google' else "local-event"
    source_icon = "🌐" if event['source'] == 'google' else "💾"
    
    start = datetime.datetime.fromisoformat(event['start'])
    end_str = ""
    if event.get('end'):
        end = datetime.datetime.fromisoformat(event['end'])
        end_str = f" → {end.strftime('%H:%M')}"
    
    return f"""
    <div class="event-card {source_color}">
        <strong>{source_icon} {event['title']}</strong><br>
        📅 {start.strftime('%A, %B %d, %Y')}<br>
        🕐 {start.strftime('%H:%M')}{end_str}
    </div>
    """

# Main UI
st.markdown('<p class="main-header">📅 Executive Scheduling Agent</p>', unsafe_allow_html=True)
st.markdown("*Your intelligent assistant for calendar and project management*")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    if not st.session_state.initialized:
        if st.button("🚀 Initialize Agent", use_container_width=True):
            initialize_agent()
    else:
        st.success("✅ Agent Active")
        if st.button("🔄 Restart Agent", use_container_width=True):
            st.session_state.executive_agent = None
            st.session_state.initialized = False
            st.rerun()
    
    st.divider()
    
    st.header("📊 Quick Stats")
    if st.session_state.initialized:
        try:
            google_events = st.session_state.executive_agent.get_events_google(7)
            local_events = st.session_state.executive_agent.get_events_local(7)
            
            st.metric("Google Events (7d)", len(google_events))
            st.metric("Local Events (7d)", len(local_events))
            st.metric("Total Events", len(google_events) + len(local_events))
        except Exception as e:
            st.warning("Unable to fetch stats")
    
    st.divider()
    
    st.header("🔧 Quick Actions")
    if st.button("🔍 Run Proactive Check", use_container_width=True, disabled=not st.session_state.initialized):
        with st.spinner("Running proactive analysis..."):
            try:
                st.session_state.executive_agent.proactive_check()
                st.success("Proactive check completed!")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Main content tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["💬 Chat", "📅 Calendar", "➕ Add Event", "📁 Projects", "📊 Dashboard"])

# Tab 1: Chat Interface
with tab1:
    st.header("Chat with Assistant")
    
    if not st.session_state.initialized:
        st.warning("⚠️ Please initialize the agent from the sidebar first.")
    else:
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
        
        # Chat input
        user_input = st.chat_input("Ask me anything about your schedule...")
        
        if user_input:
            # Add user message to history
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            with st.chat_message("user"):
                st.write(user_input)
            
            # Get agent response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.executive_agent.agent.run(user_input)
                        st.write(response)
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

# Tab 2: Calendar View
with tab2:
    st.header("Calendar Overview")
    
    if not st.session_state.initialized:
        st.warning("⚠️ Please initialize the agent from the sidebar first.")
    else:
        col1, col2 = st.columns([1, 3])
        
        with col1:
            days_ahead = st.slider("Days to show", 1, 30, 7)
            source_filter = st.multiselect(
                "Filter by source",
                ["google", "local"],
                default=["google", "local"]
            )
        
        with col2:
            try:
                # Fetch events
                google_events = st.session_state.executive_agent.get_events_google(days_ahead)
                local_events = st.session_state.executive_agent.get_events_local(days_ahead)
                
                all_events = []
                if "google" in source_filter:
                    all_events.extend(google_events)
                if "local" in source_filter:
                    all_events.extend(local_events)
                
                # Sort by start time
                all_events.sort(key=lambda x: x['start'])
                
                if all_events:
                    st.subheader(f"📅 Upcoming Events ({len(all_events)})")
                    for event in all_events:
                        st.markdown(format_event(event), unsafe_allow_html=True)
                else:
                    st.info("No events found in the selected time range.")
                    
            except Exception as e:
                st.error(f"Error loading events: {str(e)}")

# Tab 3: Add Event
with tab3:
    st.header("Add New Event")
    
    if not st.session_state.initialized:
        st.warning("⚠️ Please initialize the agent from the sidebar first.")
    else:
        calendar_type = st.radio("Calendar Type", ["Google Calendar", "Local Calendar"])
        
        col1, col2 = st.columns(2)
        
        with col1:
            event_title = st.text_input("Event Title*", placeholder="Team Meeting")
            start_date = st.date_input("Start Date*", datetime.date.today())
            start_time = st.time_input("Start Time*", datetime.time(9, 0))
        
        with col2:
            is_recurring = st.checkbox("Recurring Event")
            end_date = st.date_input("End Date*", datetime.date.today())
            end_time = st.time_input("End Time*", datetime.time(10, 0))
        
        if is_recurring:
            recurrence = st.text_input(
                "Recurrence Rule*",
                placeholder="RRULE:FREQ=DAILY;COUNT=10",
                help="Enter in iCalendar format"
            )
        
        if st.button("➕ Add Event", type="primary"):
            if not event_title:
                st.error("Please enter an event title")
            else:
                try:
                    start_datetime = datetime.datetime.combine(start_date, start_time)
                    end_datetime = datetime.datetime.combine(end_date, end_time)
                    
                    if calendar_type == "Google Calendar":
                        if is_recurring and recurrence:
                            result = st.session_state.executive_agent.add_recuring_event_google(
                                event_title, start_datetime, end_datetime, recurrence
                            )
                        else:
                            result = st.session_state.executive_agent.add_event_google(
                                event_title, start_datetime, end_datetime
                            )
                    else:
                        if is_recurring and recurrence:
                            result = st.session_state.executive_agent.add_recurring_event_local(
                                event_title, start_datetime, end_datetime, recurrence
                            )
                        else:
                            result = st.session_state.executive_agent.add_event_local(
                                event_title, start_datetime, end_datetime
                            )
                    
                    st.success(result)
                except Exception as e:
                    st.error(f"Error adding event: {str(e)}")

# Tab 4: Projects
with tab4:
    st.header("Project Management")
    
    if not st.session_state.initialized:
        st.warning("⚠️ Please initialize the agent from the sidebar first.")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("📁 Projects")
            try:
                projects_list = st.session_state.executive_agent.list_projects()
                st.info(projects_list)
                
                project_name = st.text_input("Project to view/update")
                
                if st.button("📖 Read Project"):
                    if project_name:
                        content = st.session_state.executive_agent.read_project(project_name)
                        st.session_state.selected_project_content = content
                    else:
                        st.warning("Please enter a project name")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
        
        with col2:
            st.subheader("📝 Project Details")
            
            if hasattr(st.session_state, 'selected_project_content'):
                st.text_area(
                    "Content",
                    st.session_state.selected_project_content,
                    height=300,
                    disabled=True
                )
            
            st.subheader("Update Progress")
            update_project = st.text_input("Project Name", key="update_project")
            update_note = st.text_area("Progress Note", key="update_note")
            
            if st.button("💾 Save Update"):
                if update_project and update_note:
                    result = st.session_state.executive_agent.update_project(
                        update_project, update_note
                    )
                    st.success(result)
                else:
                    st.warning("Please fill in both fields")

# Tab 5: Dashboard
with tab5:
    st.header("Dashboard")
    
    if not st.session_state.initialized:
        st.warning("⚠️ Please initialize the agent from the sidebar first.")
    else:
        try:
            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            
            google_events = st.session_state.executive_agent.get_events_google(7)
            local_events = st.session_state.executive_agent.get_events_local(7)
            
            with col1:
                st.metric("🌐 Google Events", len(google_events))
            with col2:
                st.metric("💾 Local Events", len(local_events))
            with col3:
                st.metric("📊 Total Events", len(google_events) + len(local_events))
            with col4:
                today_events = [e for e in google_events + local_events 
                               if datetime.datetime.fromisoformat(e['start']).date() == datetime.date.today()]
                st.metric("📅 Today", len(today_events))
            
            st.divider()
            
            # Timeline view
            st.subheader("📈 Week Overview")
            
            all_events = google_events + local_events
            all_events.sort(key=lambda x: x['start'])
            
            if all_events:
                # Group by day
                days_dict = {}
                for event in all_events:
                    event_date = datetime.datetime.fromisoformat(event['start']).date()
                    if event_date not in days_dict:
                        days_dict[event_date] = []
                    days_dict[event_date].append(event)
                
                for date, day_events in sorted(days_dict.items()):
                    with st.expander(f"📅 {date.strftime('%A, %B %d')} ({len(day_events)} events)"):
                        for event in day_events:
                            st.markdown(format_event(event), unsafe_allow_html=True)
            else:
                st.info("No events scheduled for the next 7 days")
                
        except Exception as e:
            st.error(f"Error loading dashboard: {str(e)}")

# Footer
st.divider()
st.markdown("""
    <div style='text-align: center; color: gray;'>
    Executive Scheduling Agent | Built with Streamlit & LangChain
    </div>
""", unsafe_allow_html=True)