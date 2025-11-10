#!/usr/bin/env python3
""" 
Streamlit UI for the Proactive Background Engine Task Orchestrator
Provides web interface for monitoring and controlling distributed task execution
"""
from proactive_background_focus import ProactiveFocusManager, Priority, ScheduledTask, PriorityWorkerPool, ClusterWorkerPool, RemoteNode, GLOBAL_TASK_REGISTRY as R, TaskRegistry, ContextProvider, serve_http_executor, HttpJsonClient
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import queue
import psutil

# Import the task orchestrator modules
# from tasks import Priority, ScheduledTask
# from worker_pool import PriorityWorkerPool
# from cluster import ClusterWorkerPool, RemoteNode
# from registry import GLOBAL_TASK_REGISTRY as R, TaskRegistry

# from context_providers import ContextProvider
# from transport_http import serve_http_executor, HttpJsonClient


class StreamlitTaskUI:
    """Main Streamlit UI class for the task orchestrator"""
    
    def __init__(self):
        self.setup_page_config()
        self.initialize_session_state()
        
    def setup_page_config(self):
        st.set_page_config(
            page_title="Task Orchestrator Dashboard",
            page_icon="🔧",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if 'local_pool' not in st.session_state:
            st.session_state.local_pool = None
        if 'cluster_pool' not in st.session_state:
            st.session_state.cluster_pool = None
        if 'focus_manager' not in st.session_state:
            st.session_state.focus_manager = None
        if 'task_history' not in st.session_state:
            st.session_state.task_history = []
        if 'system_metrics' not in st.session_state:
            st.session_state.system_metrics = []
        if 'remote_nodes' not in st.session_state:
            st.session_state.remote_nodes = []
        if 'registered_tasks' not in st.session_state:
            st.session_state.registered_tasks = {}
            
    def run(self):
        """Main application entry point"""
        self.render_header()
        
        # Sidebar navigation
        page = st.sidebar.selectbox(
            "Navigate to:",
            ["Dashboard", "Worker Pool Control", "Cluster Management", 
             "Task Registry", "Proactive Focus", "System Monitor", 
             "Task Submission", "Settings"]
        )
        
        # Route to appropriate page
        if page == "Dashboard":
            self.render_dashboard()
        elif page == "Worker Pool Control":
            self.render_worker_pool_control()
        elif page == "Cluster Management":
            self.render_cluster_management()
        elif page == "Task Registry":
            self.render_task_registry()
        elif page == "Proactive Focus":
            self.render_proactive_focus()
        elif page == "System Monitor":
            self.render_system_monitor()
        elif page == "Task Submission":
            self.render_task_submission()
        elif page == "Settings":
            self.render_settings()
            
    def render_header(self):
        """Render main header"""
        st.title("🔧 Task Orchestrator Dashboard")
        st.markdown("---")
        
        # System status indicators
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pool_status = "🟢 Running" if st.session_state.local_pool and st.session_state.local_pool._running else "🔴 Stopped"
            st.metric("Local Pool", pool_status)
            
        with col2:
            cluster_status = "🟢 Active" if st.session_state.cluster_pool else "🟡 Inactive"
            st.metric("Cluster", cluster_status)
            
        with col3:
            focus_status = "🟢 Active" if st.session_state.focus_manager and st.session_state.focus_manager._running else "🔴 Inactive"
            st.metric("Focus Manager", focus_status)
            
        with col4:
            cpu_usage = psutil.cpu_percent(interval=0.1) if psutil else 0
            st.metric("CPU Usage", f"{cpu_usage:.1f}%")
            
    def render_dashboard(self):
        """Render main dashboard"""
        st.header("📊 System Overview")
        
        # Queue metrics
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Queue Status")
            if st.session_state.local_pool:
                queue_size = st.session_state.local_pool._q.qsize()
                st.metric("Pending Tasks", queue_size)
                
                # Queue composition by priority
                if queue_size > 0:
                    priorities = {"CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0}
                    # Note: In real implementation, you'd need to access queue contents
                    # This is a simplified visualization
                    fig = px.pie(
                        values=[1, 2, 5, 2], 
                        names=list(priorities.keys()),
                        title="Queue by Priority"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Local pool not initialized")
                
        with col2:
            st.subheader("Worker Status")
            if st.session_state.local_pool:
                worker_count = st.session_state.local_pool.worker_count
                active_workers = len([t for t in st.session_state.local_pool._threads if t.is_alive()])
                st.metric("Total Workers", worker_count)
                st.metric("Active Workers", active_workers)
                
                # Worker utilization chart
                utilization = (active_workers / worker_count * 100) if worker_count > 0 else 0
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=utilization,
                    title={'text': "Worker Utilization %"},
                    gauge={'axis': {'range': [None, 100]},
                           'bar': {'color': "darkblue"},
                           'steps': [{'range': [0, 50], 'color': "lightgray"},
                                   {'range': [50, 80], 'color': "yellow"},
                                   {'range': [80, 100], 'color': "red"}]}
                ))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Local pool not initialized")
                
        # Recent task history
        st.subheader("📝 Recent Task History")
        if st.session_state.task_history:
            df = pd.DataFrame(st.session_state.task_history[-20:])  # Last 20 tasks
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No task history available")
            
    def render_worker_pool_control(self):
        """Render worker pool control interface"""
        st.header("🏭 Worker Pool Control")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Pool Configuration")
            
            worker_count = st.number_input("Worker Count", min_value=1, max_value=32, value=4)
            cpu_threshold = st.slider("CPU Threshold (%)", min_value=50, max_value=100, value=85)
            max_processes = st.number_input("Max Processes", min_value=1, value=24)
            max_process_name = st.text_input("Process Name to Monitor", value="ollama")
            
            if st.button("Initialize Local Pool"):
                self.initialize_local_pool(
                    worker_count=worker_count,
                    cpu_threshold=cpu_threshold,
                    max_processes=max_processes,
                    max_process_name=max_process_name
                )
                st.success("Local pool initialized!")
                st.rerun()
                
        with col2:
            st.subheader("Pool Controls")
            
            if st.session_state.local_pool:
                col2a, col2b = st.columns(2)
                
                with col2a:
                    if st.button("Start Pool"):
                        st.session_state.local_pool.start()
                        st.success("Pool started!")
                        
                    if st.button("Pause Pool"):
                        st.session_state.local_pool.pause()
                        st.warning("Pool paused!")
                        
                with col2b:
                    if st.button("Resume Pool"):
                        st.session_state.local_pool.resume()
                        st.success("Pool resumed!")
                        
                    if st.button("Stop Pool"):
                        st.session_state.local_pool.stop()
                        st.error("Pool stopped!")
                        
        # Rate limits configuration
        st.subheader("⚡ Rate Limits")
        st.write("Configure rate limits per label")
        
        rate_limit_data = []
        if st.session_state.local_pool and hasattr(st.session_state.local_pool, 'rate_buckets'):
            for label, bucket in st.session_state.local_pool.rate_buckets.items():
                rate_limit_data.append({
                    "Label": label,
                    "Fill Rate": bucket.fill_rate,
                    "Capacity": bucket.capacity,
                    "Current Tokens": bucket.tokens
                })
                
        if rate_limit_data:
            st.dataframe(pd.DataFrame(rate_limit_data), use_container_width=True)
        else:
            st.info("No rate limits configured")
            
        # Add new rate limit
        with st.expander("Add Rate Limit"):
            new_label = st.text_input("Label")
            fill_rate = st.number_input("Fill Rate (tokens/sec)", min_value=0.1, value=1.0)
            capacity = st.number_input("Capacity", min_value=1, value=5)
            
            if st.button("Add Rate Limit"):
                if new_label and st.session_state.local_pool:
                    from worker_pool import TokenBucket
                    st.session_state.local_pool.rate_buckets[new_label] = TokenBucket(fill_rate, capacity)
                    st.success(f"Rate limit added for label: {new_label}")
                    
    def render_cluster_management(self):
        """Render cluster management interface"""
        st.header("🌐 Cluster Management")
        
        # Initialize cluster
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Cluster Status")
            if st.session_state.cluster_pool:
                node_count = len(st.session_state.cluster_pool.nodes)
                st.metric("Remote Nodes", node_count)
                
                if st.session_state.cluster_pool.nodes:
                    nodes_data = []
                    for node in st.session_state.cluster_pool.nodes:
                        nodes_data.append({
                            "Name": node.name,
                            "URL": node.base_url,
                            "Labels": ", ".join(node.labels),
                            "Weight": node.weight,
                            "Inflight": node.inflight,
                            "Last OK": datetime.fromtimestamp(node.last_ok).strftime("%H:%M:%S") if node.last_ok else "Never"
                        })
                    st.dataframe(pd.DataFrame(nodes_data), use_container_width=True)
                else:
                    st.info("No remote nodes configured")
            else:
                if st.button("Initialize Cluster"):
                    if st.session_state.local_pool:
                        st.session_state.cluster_pool = ClusterWorkerPool(st.session_state.local_pool)
                        st.success("Cluster initialized!")
                        st.rerun()
                    else:
                        st.error("Initialize local pool first")
                        
        with col2:
            st.subheader("Add Remote Node")
            
            with st.form("add_node_form"):
                node_name = st.text_input("Node Name")
                node_url = st.text_input("Base URL", placeholder="http://host:port")
                node_labels = st.text_input("Labels (comma-separated)", placeholder="llm,exec")
                auth_token = st.text_input("Auth Token", type="password")
                weight = st.number_input("Weight", min_value=1, value=1)
                
                if st.form_submit_button("Add Node"):
                    if node_name and node_url and st.session_state.cluster_pool:
                        labels = tuple(l.strip() for l in node_labels.split(",") if l.strip())
                        node = RemoteNode(
                            name=node_name,
                            base_url=node_url,
                            labels=labels,
                            auth_token=auth_token,
                            weight=weight
                        )
                        st.session_state.cluster_pool.add_node(node)
                        st.session_state.remote_nodes.append(node)
                        st.success(f"Added node: {node_name}")
                        st.rerun()
                        
        # Node health checks
        st.subheader("🔍 Node Health Check")
        if st.session_state.cluster_pool and st.session_state.cluster_pool.nodes:
            if st.button("Check All Nodes"):
                self.check_node_health()
        else:
            st.info("No nodes to check")
            
    def render_task_registry(self):
        """Render task registry interface"""
        st.header("📋 Task Registry")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Registered Tasks")
            
            # Show registered tasks
            registry_tasks = list(R._h.keys()) if hasattr(R, '_h') else []
            if registry_tasks:
                for task_name in registry_tasks:
                    with st.expander(f"📝 {task_name}"):
                        st.write(f"**Name:** {task_name}")
                        st.write("**Handler:** Registered")
                        
                        # Test button
                        if st.button(f"Test {task_name}", key=f"test_{task_name}"):
                            self.test_task(task_name)
            else:
                st.info("No tasks registered")
                
        with col2:
            st.subheader("Register New Task")
            
            with st.form("register_task_form"):
                task_name = st.text_input("Task Name")
                task_code = st.text_area(
                    "Handler Code",
                    placeholder="""def handler(payload, context):
    # Your task logic here
    return {"result": "success"}""",
                    height=200
                )
                
                if st.form_submit_button("Register Task"):
                    if task_name and task_code:
                        self.register_dynamic_task(task_name, task_code)
                        st.success(f"Task registered: {task_name}")
                        st.rerun()
                        
        # Task execution logs
        st.subheader("🔍 Task Execution Logs")
        if st.session_state.task_history:
            # Filter by task type
            task_types = list(set([t.get('name', 'unknown') for t in st.session_state.task_history]))
            selected_type = st.selectbox("Filter by Task Type", ["All"] + task_types)
            
            filtered_history = st.session_state.task_history
            if selected_type != "All":
                filtered_history = [t for t in filtered_history if t.get('name') == selected_type]
                
            df = pd.DataFrame(filtered_history[-50:])  # Last 50 entries
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No execution history available")
            
    def render_proactive_focus(self):
        """Render proactive focus manager interface"""
        st.header("🎯 Proactive Focus Manager")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Focus Configuration")
            
            if st.session_state.focus_manager:
                current_focus = st.session_state.focus_manager.focus
                st.write(f"**Current Focus:** {current_focus or 'Not set'}")
                
                # Focus board
                if hasattr(st.session_state.focus_manager, 'focus_board'):
                    focus_board = st.session_state.focus_manager.focus_board
                    
                    for category, items in focus_board.items():
                        if items:
                            with st.expander(f"{category.title()} ({len(items)})"):
                                for i, item in enumerate(items[-10:]):  # Last 10 items
                                    st.write(f"• {item}")
                                    
            else:
                st.info("Focus manager not initialized")
                
            # Focus controls
            new_focus = st.text_input("Set New Focus")
            if st.button("Set Focus"):
                if new_focus:
                    if not st.session_state.focus_manager:
                        self.initialize_focus_manager()
                    st.session_state.focus_manager.set_focus(new_focus)
                    st.success(f"Focus set to: {new_focus}")
                    st.rerun()
                    
            col1a, col1b = st.columns(2)
            with col1a:
                if st.button("Start Focus Manager"):
                    if st.session_state.focus_manager:
                        st.session_state.focus_manager.start()
                        st.success("Focus manager started!")
                        
            with col1b:
                if st.button("Stop Focus Manager"):
                    if st.session_state.focus_manager:
                        st.session_state.focus_manager.stop()
                        st.warning("Focus manager stopped!")
                        
        with col2:
            st.subheader("Context Providers")
            
            # Mock agent for demo purposes
            if not hasattr(st.session_state, 'mock_agent'):
                st.session_state.mock_agent = type('MockAgent', (), {
                    'deep_llm': type('MockLLM', (), {'predict': lambda self, prompt: f"Mock response to: {prompt[:50]}..."})(),
                    'fast_llm': type('MockLLM', (), {'invoke': lambda self, prompt: "YES"})(),
                    'toolchain': type('MockToolchain', (), {'execute_tool_chain': lambda self, plan: [f"Executed: {plan}"]})(),
                    'tools': []
                })()
                
            # Context provider status
            if st.session_state.focus_manager:
                providers = st.session_state.focus_manager.context_providers
                for provider in providers:
                    st.write(f"📡 **{provider.name}**")
                    try:
                        context = provider.collect()
                        st.write(f"Status: ✅ Active ({len(context)} items)")
                    except Exception as e:
                        st.write(f"Status: ❌ Error - {str(e)}")
            else:
                st.info("Focus manager not initialized")
                
            # Add custom provider
            with st.expander("Add Context Provider"):
                provider_name = st.text_input("Provider Name")
                provider_code = st.text_area(
                    "Provider Code",
                    placeholder="""def collect():
    return {"key": "value"}""",
                    height=100
                )
                
                if st.button("Add Provider"):
                    if provider_name and provider_code and st.session_state.focus_manager:
                        # This would need proper implementation
                        st.success(f"Provider added: {provider_name}")
                        
    def render_system_monitor(self):
        """Render system monitoring interface"""
        st.header("📈 System Monitor")
        
        # Real-time metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 0
            st.metric("CPU Usage", f"{cpu_percent:.1f}%")
            
        with col2:
            memory = psutil.virtual_memory() if psutil else type('Memory', (), {'percent': 0})()
            st.metric("Memory Usage", f"{memory.percent:.1f}%")
            
        with col3:
            if st.session_state.local_pool:
                queue_size = st.session_state.local_pool._q.qsize()
                st.metric("Queue Size", queue_size)
            else:
                st.metric("Queue Size", "N/A")
                
        # System metrics over time
        st.subheader("📊 Metrics Over Time")
        
        # Add current metrics to history
        current_time = datetime.now()
        current_metrics = {
            "timestamp": current_time,
            "cpu": cpu_percent,
            "memory": memory.percent,
            "queue_size": queue_size if st.session_state.local_pool else 0
        }
        
        st.session_state.system_metrics.append(current_metrics)
        
        # Keep only last 100 data points
        if len(st.session_state.system_metrics) > 100:
            st.session_state.system_metrics = st.session_state.system_metrics[-100:]
            
        if len(st.session_state.system_metrics) > 1:
            df_metrics = pd.DataFrame(st.session_state.system_metrics)
            
            # Create subplots
            fig = make_subplots(
                rows=3, cols=1,
                subplot_titles=('CPU Usage (%)', 'Memory Usage (%)', 'Queue Size'),
                vertical_spacing=0.1
            )
            
            fig.add_trace(
                go.Scatter(x=df_metrics['timestamp'], y=df_metrics['cpu'], name='CPU'),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=df_metrics['timestamp'], y=df_metrics['memory'], name='Memory'),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=df_metrics['timestamp'], y=df_metrics['queue_size'], name='Queue'),
                row=3, col=1
            )
            
            fig.update_layout(height=600, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
        # Process information
        st.subheader("🔍 Process Information")
        if psutil:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            # Show top 10 processes by CPU
            df_proc = pd.DataFrame(processes)
            if not df_proc.empty:
                df_proc = df_proc.sort_values('cpu_percent', ascending=False).head(10)
                st.dataframe(df_proc, use_container_width=True)
        else:
            st.info("psutil not available for process monitoring")
            
    def render_task_submission(self):
        """Render task submission interface"""
        st.header("📤 Task Submission")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Submit New Task")
            
            with st.form("task_submission_form"):
                # Task selection
                registry_tasks = list(R._h.keys()) if hasattr(R, '_h') else []
                selected_task = st.selectbox("Task Type", registry_tasks or ["No tasks registered"])
                
                # Priority selection
                priority_map = {"CRITICAL": Priority.CRITICAL, "HIGH": Priority.HIGH, 
                              "NORMAL": Priority.NORMAL, "LOW": Priority.LOW}
                selected_priority = st.selectbox("Priority", list(priority_map.keys()))
                
                # Labels
                labels_input = st.text_input("Labels (comma-separated)", placeholder="llm,exec")
                
                # Delay
                delay = st.number_input("Delay (seconds)", min_value=0.0, value=0.0)
                
                # Payload
                payload_json = st.text_area(
                    "Payload (JSON)",
                    value='{"example": "data"}',
                    height=150
                )
                
                # Context
                context_json = st.text_area(
                    "Context (JSON)",
                    value='{}',
                    height=100
                )
                
                submit_button = st.form_submit_button("Submit Task")
                
                if submit_button:
                    if selected_task and selected_task != "No tasks registered":
                        try:
                            payload = json.loads(payload_json)
                            context = json.loads(context_json)
                            labels = [l.strip() for l in labels_input.split(",") if l.strip()]
                            
                            if st.session_state.cluster_pool:
                                task_id = st.session_state.cluster_pool.submit_task(
                                    name=selected_task,
                                    payload=payload,
                                    priority=priority_map[selected_priority],
                                    labels=labels,
                                    delay=delay,
                                    context=context
                                )
                                st.success(f"Task submitted! ID: {task_id}")
                                
                                # Add to history
                                st.session_state.task_history.append({
                                    "timestamp": datetime.now(),
                                    "task_id": task_id,
                                    "name": selected_task,
                                    "priority": selected_priority,
                                    "labels": ", ".join(labels),
                                    "status": "submitted"
                                })
                                
                            elif st.session_state.local_pool:
                                task_id = st.session_state.local_pool.submit(
                                    lambda: R.run(selected_task, payload, context),
                                    priority=priority_map[selected_priority],
                                    delay=delay,
                                    name=selected_task,
                                    labels=labels
                                )
                                st.success(f"Task submitted to local pool! ID: {task_id}")
                                
                            else:
                                st.error("No worker pool available")
                                
                        except json.JSONDecodeError as e:
                            st.error(f"Invalid JSON: {e}")
                        except Exception as e:
                            st.error(f"Error submitting task: {e}")
                            
        with col2:
            st.subheader("Quick Actions")
            
            # Predefined task templates
            templates = {
                "Test Task": {
                    "payload": {"message": "Hello World"},
                    "labels": ["test"],
                    "priority": "NORMAL"
                },
                "LLM Generation": {
                    "payload": {"prompt": "Summarize recent activities"},
                    "labels": ["llm"],
                    "priority": "HIGH"
                },
                "Heavy Computation": {
                    "payload": {"data": "large_dataset"},
                    "labels": ["exec"],
                    "priority": "LOW"
                }
            }
            
            for template_name, template_data in templates.items():
                if st.button(f"Load {template_name} Template"):
                    st.session_state.template_data = template_data
                    st.success(f"Loaded {template_name} template")
                    
            # Bulk task submission
            st.subheader("📦 Bulk Submission")
            
            bulk_count = st.number_input("Number of Tasks", min_value=1, max_value=100, value=5)
            bulk_task = st.selectbox("Bulk Task Type", registry_tasks or ["No tasks registered"], key="bulk_task")
            
            if st.button("Submit Bulk Tasks"):
                if bulk_task and bulk_task != "No tasks registered":
                    submitted_count = 0
                    for i in range(bulk_count):
                        try:
                            if st.session_state.local_pool:
                                task_id = st.session_state.local_pool.submit(
                                    lambda: R.run(bulk_task, {"batch_id": i}, {}),
                                    name=f"{bulk_task}_batch_{i}",
                                    priority=Priority.NORMAL
                                )
                                submitted_count += 1
                        except Exception as e:
                            st.error(f"Failed to submit task {i}: {e}")
                            break
                            
                    st.success(f"Submitted {submitted_count}/{bulk_count} tasks")
                    
    def render_settings(self):
        """Render settings interface"""
        st.header("⚙️ Settings")
        
        # Configuration export/import
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Configuration Export")
            
            config = self.export_configuration()
            st.text_area("Current Configuration", json.dumps(config, indent=2), height=300)
            
            if st.download_button(
                "Download Configuration",
                json.dumps(config, indent=2),
                "task_orchestrator_config.json",
                "application/json"
            ):
                st.success("Configuration downloaded!")
                
        with col2:
            st.subheader("Configuration Import")
            
            uploaded_file = st.file_uploader("Upload Configuration", type="json")
            if uploaded_file:
                try:
                    config = json.load(uploaded_file)
                    st.json(config)
                    
                    if st.button("Apply Configuration"):
                        self.import_configuration(config)
                        st.success("Configuration applied!")
                        st.rerun()
                        
                except json.JSONDecodeError:
                    st.error("Invalid JSON file")
                    
        # System settings
        st.subheader("🔧 System Settings")
        
        # Auto-refresh settings
        auto_refresh = st.checkbox("Auto-refresh Dashboard", value=False)
        if auto_refresh:
            refresh_interval = st.slider("Refresh Interval (seconds)", 1, 60, 5)
            st.info(f"Dashboard will refresh every {refresh_interval} seconds")
            # Note: In a real implementation, you'd use st.rerun() with a timer
            
        # Logging settings
        log_level = st.selectbox("Log Level", ["DEBUG", "INFO", "WARNING", "ERROR"])
        
        # Reset options
        st.subheader("🔄 Reset Options")
        
        col_reset1, col_reset2 = st.columns(2)
        
        with col_reset1:
            if st.button("Clear Task History", type="secondary"):
                st.session_state.task_history = []
                st.success("Task history cleared!")
                
            if st.button("Clear System Metrics", type="secondary"):
                st.session_state.system_metrics = []
                st.success("System metrics cleared!")
                
        with col_reset2:
            if st.button("Reset All Settings", type="secondary"):
                # Reset to defaults
                for key in ['local_pool', 'cluster_pool', 'focus_manager']:
                    if key in st.session_state:
                        if hasattr(st.session_state[key], 'stop'):
                            st.session_state[key].stop()
                        del st.session_state[key]
                st.warning("All settings reset!")
                st.rerun()
    
    # Helper methods
    def initialize_local_pool(self, worker_count=4, cpu_threshold=85.0, max_processes=24, max_process_name="ollama"):
        """Initialize the local worker pool"""
        rate_limits = {
            "llm": (0.5, 2),      # 0.5 tokens/sec, capacity 2
            "exec": (2.0, 5),     # 2 tokens/sec, capacity 5  
            "heavy": (0.2, 1)     # 0.2 tokens/sec, capacity 1
        }
        
        st.session_state.local_pool = PriorityWorkerPool(
            worker_count=worker_count,
            cpu_threshold=cpu_threshold,
            max_process_name=max_process_name,
            max_processes=max_processes,
            rate_limits=rate_limits,
            on_task_start=self.on_task_start,
            on_task_end=self.on_task_end,
            name="StreamlitPool"
        )
        
        # Set some default concurrency limits
        st.session_state.local_pool.set_concurrency_limit("llm", 2)
        st.session_state.local_pool.set_concurrency_limit("exec", 3)
        st.session_state.local_pool.set_concurrency_limit("heavy", 1)
        
    def initialize_focus_manager(self):
        """Initialize the proactive focus manager"""
        if not st.session_state.local_pool:
            st.error("Initialize local pool first!")
            return
            
        # Use mock agent for demo
        if not hasattr(st.session_state, 'mock_agent'):
            st.session_state.mock_agent = type('MockAgent', (), {
                'deep_llm': type('MockLLM', (), {
                    'predict': lambda self, prompt: f"Generated action based on: {prompt[:100]}..."
                })(),
                'fast_llm': type('MockLLM', (), {
                    'invoke': lambda self, prompt: "YES" if "actionable" in prompt.lower() else "NO"
                })(),
                'toolchain': type('MockToolchain', (), {
                    'execute_tool_chain': lambda self, plan: [f"Mock execution result for: {plan[:50]}..."]
                })(),
                'tools': [{'name': 'mock_tool'}]
            })()
            
        st.session_state.focus_manager = ProactiveFocusManager(
            agent=st.session_state.mock_agent,
            pool=st.session_state.local_pool,
            proactive_interval=60.0,  # 1 minute for demo
            proactive_callback=self.on_proactive_action
        )
        
    def on_task_start(self, task: ScheduledTask):
        """Callback when task starts"""
        task_info = {
            "timestamp": datetime.now(),
            "task_id": task.task_id,
            "name": task.name,
            "priority": task.priority.name,
            "labels": ", ".join(task.labels),
            "status": "started"
        }
        st.session_state.task_history.append(task_info)
        
    def on_task_end(self, task: ScheduledTask, result: Any, error: Exception):
        """Callback when task ends"""
        task_info = {
            "timestamp": datetime.now(),
            "task_id": task.task_id,
            "name": task.name,
            "priority": task.priority.name,
            "labels": ", ".join(task.labels),
            "status": "completed" if error is None else "failed",
            "error": str(error) if error else None,
            "result": str(result)[:200] if result else None  # Truncate long results
        }
        st.session_state.task_history.append(task_info)
        
    def on_proactive_action(self, action: str):
        """Callback for proactive actions"""
        st.session_state.task_history.append({
            "timestamp": datetime.now(),
            "task_id": "proactive",
            "name": "proactive_action",
            "priority": "AUTO",
            "labels": "focus",
            "status": "generated",
            "result": action[:200]
        })
        
    def check_node_health(self):
        """Check health of all remote nodes"""
        if not st.session_state.cluster_pool:
            return
            
        results = []
        for node in st.session_state.cluster_pool.nodes:
            try:
                client = HttpJsonClient(node.base_url, auth_token=node.auth_token)
                response = client.heartbeat()
                status = "✅ Healthy" if response.get("status") == "ok" else "⚠️ Degraded"
                node.last_ok = time.time()
            except Exception as e:
                status = f"❌ Error: {str(e)[:50]}"
                
            results.append({
                "Node": node.name,
                "Status": status,
                "URL": node.base_url,
                "Last Check": datetime.now().strftime("%H:%M:%S")
            })
            
        st.dataframe(pd.DataFrame(results), use_container_width=True)
        
    def test_task(self, task_name: str):
        """Test a registered task"""
        try:
            test_payload = {"test": True, "timestamp": time.time()}
            test_context = {"source": "ui_test"}
            
            if st.session_state.local_pool:
                task_id = st.session_state.local_pool.submit(
                    lambda: R.run(task_name, test_payload, test_context),
                    priority=Priority.HIGH,
                    name=f"test_{task_name}",
                    labels=("test",)
                )
                st.success(f"Test task submitted: {task_id}")
            else:
                st.error("No local pool available for testing")
                
        except Exception as e:
            st.error(f"Test failed: {str(e)}")
            
    def register_dynamic_task(self, task_name: str, task_code: str):
        """Register a task dynamically from code"""
        try:
            # Create a safe execution environment
            safe_globals = {
                "__builtins__": {
                    "print": print,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                    "dict": dict,
                    "list": list,
                    "tuple": tuple,
                    "set": set,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "sorted": sorted,
                    "range": range,
                    "enumerate": enumerate,
                    "zip": zip
                },
                "json": json,
                "time": time,
                "datetime": datetime
            }
            
            # Execute the code
            exec(f"handler = {task_code}", safe_globals)
            handler_func = safe_globals["handler"]
            
            # Register with the global registry
            R._h[task_name] = handler_func
            
            st.session_state.registered_tasks[task_name] = {
                "code": task_code,
                "registered_at": datetime.now()
            }
            
        except Exception as e:
            st.error(f"Failed to register task: {str(e)}")
            
    def export_configuration(self) -> dict:
        """Export current configuration"""
        config = {
            "local_pool": {
                "active": st.session_state.local_pool is not None,
                "worker_count": st.session_state.local_pool.worker_count if st.session_state.local_pool else 4,
                "cpu_threshold": getattr(st.session_state.local_pool, 'cpu_threshold', 85.0) if st.session_state.local_pool else 85.0
            },
            "cluster_nodes": [
                {
                    "name": node.name,
                    "base_url": node.base_url,
                    "labels": list(node.labels),
                    "weight": node.weight
                } for node in (st.session_state.cluster_pool.nodes if st.session_state.cluster_pool else [])
            ],
            "focus_manager": {
                "active": st.session_state.focus_manager is not None,
                "focus": getattr(st.session_state.focus_manager, 'focus', None) if st.session_state.focus_manager else None
            },
            "registered_tasks": st.session_state.registered_tasks,
            "export_timestamp": datetime.now().isoformat()
        }
        return config
        
    def import_configuration(self, config: dict):
        """Import configuration"""
        try:
            # Import local pool settings
            if config.get("local_pool", {}).get("active"):
                pool_config = config["local_pool"]
                self.initialize_local_pool(
                    worker_count=pool_config.get("worker_count", 4),
                    cpu_threshold=pool_config.get("cpu_threshold", 85.0)
                )
                
            # Import cluster nodes
            if config.get("cluster_nodes"):
                if not st.session_state.cluster_pool and st.session_state.local_pool:
                    st.session_state.cluster_pool = ClusterWorkerPool(st.session_state.local_pool)
                    
                for node_config in config["cluster_nodes"]:
                    node = RemoteNode(
                        name=node_config["name"],
                        base_url=node_config["base_url"],
                        labels=tuple(node_config["labels"]),
                        weight=node_config.get("weight", 1)
                    )
                    st.session_state.cluster_pool.add_node(node)
                    
            # Import focus manager
            focus_config = config.get("focus_manager", {})
            if focus_config.get("active"):
                self.initialize_focus_manager()
                if focus_config.get("focus"):
                    st.session_state.focus_manager.set_focus(focus_config["focus"])
                    
            # Import registered tasks
            if config.get("registered_tasks"):
                st.session_state.registered_tasks.update(config["registered_tasks"])
                for task_name, task_info in config["registered_tasks"].items():
                    if "code" in task_info:
                        self.register_dynamic_task(task_name, task_info["code"])
                        
        except Exception as e:
            st.error(f"Failed to import configuration: {str(e)}")


# Example task registrations for demo purposes
@R.register("demo.hello_world")
def demo_hello_world(payload, context):
    """Demo task that returns a greeting"""
    name = payload.get("name", "World")
    return {"message": f"Hello, {name}!", "timestamp": time.time()}

@R.register("demo.cpu_intensive")
def demo_cpu_intensive(payload, context):
    """Demo CPU-intensive task"""
    iterations = payload.get("iterations", 1000000)
    result = sum(i * i for i in range(iterations))
    return {"result": result, "iterations": iterations}

@R.register("demo.simulate_llm")
def demo_simulate_llm(payload, context):
    """Demo task that simulates LLM processing"""
    prompt = payload.get("prompt", "Default prompt")
    # Simulate processing time
    time.sleep(1)
    return {
        "response": f"Simulated LLM response to: {prompt}",
        "tokens": len(prompt.split()) * 2,
        "model": context.get("model", "demo-model")
    }

@R.register("demo.data_processing")
def demo_data_processing(payload, context):
    """Demo data processing task"""
    data = payload.get("data", [1, 2, 3, 4, 5])
    operation = payload.get("operation", "sum")
    
    if operation == "sum":
        result = sum(data)
    elif operation == "product":
        result = 1
        for x in data:
            result *= x
    elif operation == "average":
        result = sum(data) / len(data) if data else 0
    else:
        result = data
        
    return {"result": result, "operation": operation, "input_size": len(data)}


def main():
    """Main entry point for the Streamlit app"""
    ui = StreamlitTaskUI()
    ui.run()
    
    # Auto-refresh functionality (basic implementation)
    if hasattr(st.session_state, 'auto_refresh') and st.session_state.auto_refresh:
        time.sleep(1)  # Basic refresh delay
        st.rerun()


if __name__ == "__main__":
    main()