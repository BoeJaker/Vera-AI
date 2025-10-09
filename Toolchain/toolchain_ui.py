import streamlit as st
import graphviz
import json
import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import hashlib

# Assuming the ToolChainPlanner and related classes are imported
from toolchain import ToolChainPlanner, ToolStep, ToolResult, StepStatus

class EnhancedStepProcessor:
    """Enhanced step processor to handle real-time step updates and graph generation."""
    
    def __init__(self):
        self.steps = {}
        self.step_order = []
        self.start_time = None
        self.current_step_id = None
        
    def start_step(self, step_id: str, tool_name: str, input_data: Any = None) -> dict:
        """Start processing a new step."""
        step_info = {
            'id': step_id,
            'tool_name': tool_name,
            'input_data': str(input_data) if input_data else "",
            'start_time': datetime.now(),
            'end_time': None,
            'duration': None,
            'status': 'RUNNING',
            'output': None,
            'error': None,
            'step_number': len(self.step_order) + 1
        }
        
        self.steps[step_id] = step_info
        self.step_order.append(step_id)
        self.current_step_id = step_id
        
        if self.start_time is None:
            self.start_time = step_info['start_time']
            
        return step_info
    
    def complete_step(self, step_id: str, output: Any = None, error: str = None) -> dict:
        """Complete a step with results."""
        if step_id not in self.steps:
            return None
            
        step = self.steps[step_id]
        step['end_time'] = datetime.now()
        step['duration'] = (step['end_time'] - step['start_time']).total_seconds()
        step['output'] = str(output) if output else ""
        step['error'] = error
        step['status'] = 'ERROR' if error else 'COMPLETED'
        
        return step
    
    def get_current_step(self) -> Optional[dict]:
        """Get the currently running step."""
        return self.steps.get(self.current_step_id) if self.current_step_id else None
    
    def get_all_steps(self) -> List[dict]:
        """Get all steps in execution order."""
        return [self.steps[step_id] for step_id in self.step_order]

class StreamlitToolchainVisualizer:
    """
    Enhanced real-time visualizer for ToolChainPlanner execution with improved graph visualization.
    """
    
    def __init__(self):
        self.execution_log = []
        self.current_plan = None
        self.current_execution = None
        self.update_queue = queue.Queue()
        self.is_running = False
        self.step_processor = EnhancedStepProcessor()
        self.last_chart_signature = ""  # Add this line
        self.last_chart_signature = ""
        self._current_execution_id = None  # Add this
        # Initialize session state
        if 'execution_history' not in st.session_state:
            st.session_state.execution_history = []
        if 'current_execution_id' not in st.session_state:
            st.session_state.current_execution_id = 0
        if 'live_steps' not in st.session_state:
            st.session_state.live_steps = []

    def setup_page(self):
        """Setup the Streamlit page configuration."""
        st.set_page_config(
            page_title="ToolChain Planner Visualizer",
            page_icon="🔗",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("🔗 Enhanced ToolChain Planner Visualizer")
        st.markdown("Monitor and visualize toolchain execution in real-time with detailed step processing")
    # Add this to your StreamlitToolchainVisualizer class
    def _get_steps_signature(self, steps):
        """Create a simple signature of current steps state."""
        if not steps:
            return ""
        return f"{len(steps)}:{':'.join(s['status'] + str(s.get('duration', 0)) for s in steps)}"

    def generate_unique_key(self, base: str, data: Any = None) -> str:
        """Generate a unique key for Streamlit elements to avoid duplicate ID errors."""
        if data:
            # Create hash from data to ensure uniqueness
            data_str = str(data) + str(datetime.now().timestamp())
            hash_suffix = hashlib.md5(data_str.encode()).hexdigest()[:8]
            return f"{base}_{hash_suffix}"
        return f"{base}_{int(datetime.now().timestamp() * 1000)}"

    def print_step_info(self, step_info: dict, container=None):
        """Print detailed step information."""
        if container is None:
            container = st
            
        with container.expander(f"Step {step_info['step_number']}: {step_info['tool_name']}", expanded=True):
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                st.write("**Status:**")
                if step_info['status'] == 'RUNNING':
                    st.info("🔄 Running...")
                elif step_info['status'] == 'COMPLETED':
                    st.success("✅ Completed")
                elif step_info['status'] == 'ERROR':
                    st.error("❌ Error")
                    
            with col2:
                st.write("**Timing:**")
                st.write(f"Started: {step_info['start_time'].strftime('%H:%M:%S')}")
                if step_info['duration']:
                    st.write(f"Duration: {step_info['duration']:.2f}s")
                    
            with col3:
                st.write("**Input:**")
                if step_info['input_data']:
                    st.code(step_info['input_data'][:200] + ("..." if len(step_info['input_data']) > 200 else ""))
                
                if step_info['output'] and step_info['status'] == 'COMPLETED':
                    st.write("**Output:**")
                    st.code(step_info['output'][:200] + ("..." if len(step_info['output']) > 200 else ""))
                    
                if step_info['error']:
                    st.write("**Error:**")
                    st.error(step_info['error'])

    def create_interactive_plotly_graph(self, steps: List[dict], mode: str = "incremental") -> go.Figure:
        """Create an improved interactive execution graph using Plotly with better scaling and navigation."""
        if not steps:
            fig = go.Figure()
            fig.update_layout(
                title="Waiting for execution steps...",
                height=500,
                showlegend=False
            )
            return fig
        
        # Calculate positions for better layout
        n_steps = len(steps)
        
        if mode == "speculative":
            # For speculative mode, arrange in a radial pattern
            import math
            center_x, center_y = 0, 0
            radius = max(2, n_steps * 0.5)
            
            node_x = []
            node_y = []
            
            if n_steps == 1:
                node_x = [0]
                node_y = [0]
            else:
                for i, step in enumerate(steps):
                    angle = 2 * math.pi * i / n_steps
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    node_x.append(x)
                    node_y.append(y)
            
            # Create edges from center to all nodes
            edge_x = []
            edge_y = []
            for x, y in zip(node_x, node_y):
                edge_x.extend([center_x, x, None])
                edge_y.extend([center_y, y, None])
                
        else:
            # For sequential modes, arrange vertically with better spacing
            spacing = max(1, 10 / max(n_steps, 1))  # Adjust spacing based on number of steps
            node_x = [0] * n_steps  # All nodes in center column
            node_y = [i * spacing for i in range(n_steps)]
            
            # Create sequential edges
            edge_x = []
            edge_y = []
            for i in range(n_steps - 1):
                edge_x.extend([node_x[i], node_x[i+1], None])
                edge_y.extend([node_y[i], node_y[i+1], None])
        
        # Create node colors and text based on status
        node_colors = []
        node_symbols = []
        node_text = []
        hover_text = []
        
        for step in steps:
            # Color coding
            if step['status'] == 'COMPLETED':
                node_colors.append('#4CAF50')  # Green
                node_symbols.append('circle')
            elif step['status'] == 'RUNNING':
                node_colors.append('#FF9800')  # Orange
                node_symbols.append('circle-dot')
            elif step['status'] == 'ERROR':
                node_colors.append('#F44336')  # Red
                node_symbols.append('x')
            else:
                node_colors.append('#9E9E9E')  # Gray
                node_symbols.append('circle-open')
            
            # Text labels
            duration_info = f"({step['duration']:.2f}s)" if step['duration'] else ""
            node_text.append(f"Step {step['step_number']}")
            
            # Hover information
            hover_info = (
                f"<b>Step {step['step_number']}: {step['tool_name']}</b><br>"
                f"Status: {step['status']}<br>"
                f"Started: {step['start_time'].strftime('%H:%M:%S')}<br>"
            )
            if step['duration']:
                hover_info += f"Duration: {step['duration']:.2f}s<br>"
            if step['input_data']:
                input_preview = step['input_data'][:100] + "..." if len(step['input_data']) > 100 else step['input_data']
                hover_info += f"Input: {input_preview}<br>"
            if step['error']:
                hover_info += f"Error: {step['error'][:100]}...<br>"
            
            hover_text.append(hover_info)
        
        # Create edge trace
        edge_trace = go.Scatter(
            x=edge_x, 
            y=edge_y,
            line=dict(width=3, color='rgba(125, 125, 125, 0.5)'),
            hoverinfo='none',
            mode='lines',
            name='Connections'
        )
        
        # Create node trace
        node_trace = go.Scatter(
            x=node_x, 
            y=node_y,
            mode='markers+text',
            text=node_text,
            textposition="bottom center",
            textfont=dict(size=12, color="black"),
            hoverinfo='text',
            hovertext=hover_text,
            marker=dict(
                color=node_colors,
                size=25,
                symbol=node_symbols,
                line=dict(width=2, color='white'),
                sizemode='diameter'
            ),
            name='Steps'
        )
        
        # Create the figure
        fig = go.Figure(data=[edge_trace, node_trace])
        
        # Update layout for better visualization
        fig.update_layout(
            title=dict(
                text=f'Execution Graph - {mode.upper()} Mode ({len(steps)} steps)',
                x=0.5,
                font=dict(size=16)
            ),
            showlegend=False,
            hovermode='closest',
            margin=dict(b=40, l=40, r=40, t=60),
            xaxis=dict(
                showgrid=True, 
                zeroline=True, 
                showticklabels=False,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            yaxis=dict(
                showgrid=True, 
                zeroline=True, 
                showticklabels=False,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            height=max(400, min(800, 50 * n_steps + 200)),  # Dynamic height based on steps
            plot_bgcolor='white',
            paper_bgcolor='white',
            # Enable zooming and panning
            dragmode='pan'
        )
        
        # Add status legend as annotations
        legend_y = max(node_y) + (max(node_y) - min(node_y)) * 0.1 if node_y else 0
        legend_items = [
            ("🟢 Completed", '#4CAF50'),
            ("🟡 Running", '#FF9800'),
            ("🔴 Error", '#F44336'),
            ("⚫ Pending", '#9E9E9E')
        ]
        
        for i, (text, color) in enumerate(legend_items):
            fig.add_annotation(
                x=-2,
                y=legend_y - i * 0.5,
                text=text,
                showarrow=False,
                font=dict(size=10),
                xanchor="left"
            )
        
        return fig

    def create_enhanced_execution_graph(self, steps: List[dict], mode: str = "incremental") -> str:
        """
        Create an enhanced graphviz visualization with improved scaling and layout.
        """
        dot = graphviz.Digraph(comment=f'ToolChain Execution ({mode} mode)')
        
        # Improved attributes for better scaling and visibility
        dot.attr(
            rankdir='TB', 
            ratio='fill',  # Changed from 'auto' to 'fill' for better container fitting
            size="12,16!", # Force the size with !
            dpi='100',    # Reduced DPI for better web display
            bgcolor='white',
            pad='0.5',    # Add padding
            nodesep='0.8', # Increase node separation
            ranksep='1.2'  # Increase rank separation
        )
        
        dot.attr('node', 
            shape='box', 
            style='rounded,filled', 
            fontsize='11',
            fontname='Arial',
            width='2.5',   # Increased width
            height='1.5',  # Increased height
            margin='0.3',  # More margin
            penwidth='2'   # Thicker borders
        )
        
        dot.attr('graph', 
            label=f'Execution Mode: {mode.upper()}\\n{len(steps)} Steps', 
            labelloc='t', 
            fontsize='14', 
            fontweight='bold',
            fontname='Arial'
        )
        
        dot.attr('edge', 
            fontsize='10',
            penwidth='2',
            arrowsize='1.2'
        )
        
        # Add nodes with improved formatting
        for i, step in enumerate(steps):
            step_id = f"step_{step['step_number']}"
            tool_name = step['tool_name']
            step_num = step['step_number']
            
            # Truncate and format input for better display
            display_input = ""
            if step['input_data']:
                input_text = step['input_data'].replace('"', "'").replace('\n', ' ')
                if len(input_text) > 30:
                    display_input = input_text[:27] + "..."
                else:
                    display_input = input_text
            
            # Status-based styling
            if step['status'] == 'COMPLETED':
                color = '#E8F5E8'      # Light green
                fontcolor = '#2E7D2E'   # Dark green
                style = 'filled,bold'
                status_icon = "✓"
            elif step['status'] == 'RUNNING':
                color = '#FFF3CD'      # Light yellow
                fontcolor = '#856404'   # Dark yellow
                style = 'filled,dashed'
                status_icon = "⟳"
            elif step['status'] == 'ERROR':
                color = '#F8D7DA'      # Light red
                fontcolor = '#721C24'   # Dark red
                style = 'filled,dotted'
                status_icon = "✗"
            else:
                color = '#F8F9FA'      # Light gray
                fontcolor = '#6C757D'   # Dark gray
                style = 'filled'
                status_icon = "○"
            
            # Create multi-line label with better formatting
            duration_info = f"{step['duration']:.1f}s" if step['duration'] else ""
            label_parts = [
                f"{status_icon} {tool_name}",
                f"Step {step_num}",
            ]
            
            if display_input:
                label_parts.append(f'"{display_input}"')
            
            if duration_info:
                label_parts.append(f"({duration_info})")
            
            label = "\\n".join(label_parts)
            
            dot.node(
                step_id, 
                label, 
                fillcolor=color, 
                fontcolor=fontcolor,
                style=style
            )
            
            # Add edges for sequential execution
            if mode in ["incremental", "batch"] and i < len(steps) - 1:
                next_step_id = f"step_{steps[i + 1]['step_number']}"
                dot.edge(step_id, next_step_id, color='#6C757D')
        
        # Special handling for speculative mode
        if mode == "speculative" and len(steps) > 1:
            # Create a start node
            dot.node(
                'start', 
                'START\\nSpeculative\\nExecution', 
                shape='ellipse', 
                fillcolor='#CCE5FF', 
                fontcolor='#004085',
                style='filled,bold'
            )
            
            # Connect start to all steps
            for step in steps:
                step_id = f"step_{step['step_number']}"
                dot.edge('start', step_id, color='#007BFF', style='dashed')
        
        return dot.source

    def create_real_time_metrics(self, steps: List[dict]) -> None:
        """Create real-time metrics dashboard."""
        if not steps:
            st.info("No steps to display yet...")
            return
            
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate metrics
        total_steps = len(steps)
        completed_steps = len([s for s in steps if s['status'] == 'COMPLETED'])
        running_steps = len([s for s in steps if s['status'] == 'RUNNING'])
        error_steps = len([s for s in steps if s['status'] == 'ERROR'])
        
        total_duration = sum(s['duration'] for s in steps if s['duration'])
        avg_duration = total_duration / max(completed_steps, 1)
        
        with col1:
            st.metric("Total Steps", total_steps)
            
        with col2:
            st.metric("Completed", completed_steps, delta=completed_steps - error_steps)
            
        with col3:
            st.metric("Running", running_steps)
            
        with col4:
            st.metric("Avg Duration", f"{avg_duration:.2f}s" if completed_steps > 0 else "N/A")

    def create_step_timeline_chart(self, steps: List[dict], container_key: str = "") -> None:
        """Create an interactive timeline chart of step execution with unique keys."""
        if not steps:
            return
            
        # Prepare timeline data
        timeline_data = []
        base_time = min(s['start_time'] for s in steps)
        
        for step in steps:
            start_offset = (step['start_time'] - base_time).total_seconds()
            duration = step['duration'] if step['duration'] else (
                (datetime.now() - step['start_time']).total_seconds() if step['status'] == 'RUNNING' else 0
            )
            
            timeline_data.append({
                'Step': f"Step {step['step_number']}: {step['tool_name']}",
                'Start': start_offset,
                'End': start_offset + duration,
                'Duration': duration,
                'Status': step['status'],
                'Tool': step['tool_name']
            })
        
        df = pd.DataFrame(timeline_data)
        
        # Create Gantt chart with unique key
        fig = go.Figure()
        
        colors = {'COMPLETED': '#4CAF50', 'RUNNING': '#FF9800', 'ERROR': '#F44336', 'PENDING': '#9E9E9E'}
        
        for _, row in df.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['Start'], row['End']],
                y=[row['Step'], row['Step']],
                mode='lines+markers',
                line=dict(color=colors.get(row['Status'], '#9E9E9E'), width=8),
                name=row['Status'],
                showlegend=False,
                hovertemplate=f"<b>{row['Step']}</b><br>" +
                            f"Duration: {row['Duration']:.2f}s<br>" +
                            f"Status: {row['Status']}<extra></extra>"
            ))
        
        fig.update_layout(
            title="Step Execution Timeline",
            xaxis_title="Time (seconds)",
            yaxis_title="Steps",
            height=max(300, len(steps) * 40),
            hovermode='closest',
            margin=dict(l=200, r=50, t=50, b=50)  # More left margin for step names
        )
        
        # Use unique key to prevent duplicate ID error
        unique_key = self.generate_unique_key(f"timeline_{container_key}")
        st.plotly_chart(fig, use_container_width=True, key=unique_key)

    def create_live_step_monitor(self, steps: List[dict]) -> None:
        """Create a live monitor showing current step details."""
        st.subheader("📊 Live Step Monitor")
        
        if not steps:
            st.info("Waiting for execution to start...")
            return
            
        # Show current/most recent step
        current_step = None
        for step in reversed(steps):
            if step['status'] == 'RUNNING':
                current_step = step
                break
        
        if not current_step and steps:
            current_step = steps[-1]  # Show most recent step
            
        if current_step:
            st.subheader(f"Current Step: {current_step['tool_name']}")
            self.print_step_info(current_step)
            
        # Show step history in a scrollable container
        st.subheader("Step History")
        step_container = st.container()
        
        with step_container:
            for step in steps:
                with st.expander(f"Step {step['step_number']}: {step['tool_name']} ({step['status']})", 
                               expanded=(step['status'] == 'RUNNING')):
                    self.print_step_info(step)

    def setup_enhanced_planner_hooks(self, planner):
        """Setup enhanced hooks to capture detailed planner events."""
    
        def on_plan_hook(plans):
            self.current_plan = plans[0] if plans else None
            self.update_queue.put(('plan', self.current_plan))
        
        def on_step_start_hook(step):
            # Enhanced step start handling
            step_id = getattr(step, 'id', f"step_{len(self.step_processor.step_order) + 1}")
            tool_name = getattr(step, 'tool', 'Unknown Tool')
            input_data = getattr(step, 'input', getattr(step, 'args', ''))
            
            step_info = self.step_processor.start_step(step_id, tool_name, input_data)
            self.update_queue.put(('step_start', step_info))
            
            # Print step start
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Starting Step {step_info['step_number']}: {tool_name}")
            if input_data:
                print(f"   Input: {str(input_data)[:100]}{'...' if len(str(input_data)) > 100 else ''}")
        
        def on_step_end_hook(step, result):  # Fixed: removed 'self' parameter
            # Enhanced step end handling
            step_id = getattr(step, 'id', self.step_processor.current_step_id)
            output = getattr(result, 'raw', result) if hasattr(result, 'raw') else result
            error = None
            
            # Check for error conditions
            if hasattr(result, 'success') and not result.success:
                error = getattr(result, 'error', 'Unknown error')
            elif hasattr(result, 'error') and result.error:
                error = str(result.error)
            
            step_info = self.step_processor.complete_step(step_id, output, error)
            if step_info:
                self.execution_log.append(step_info)
                self.update_queue.put(('step_end', step_info))
                
                # Print step completion
                status = "✅" if step_info['status'] == 'COMPLETED' else "❌"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {status} Completed Step {step_info['step_number']}: {step_info['tool_name']} ({step_info['duration']:.2f}s)")
                if step_info['error']:
                    print(f"   Error: {step_info['error']}")
                elif step_info['output']:
                    output_preview = str(step_info['output'])[:100]
                    print(f"   Output: {output_preview}{'...' if len(str(step_info['output'])) > 100 else ''}")
        
        def on_error_hook(error, step=None):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Execution Error: {error}")
            self.update_queue.put(('error', (error, step)))
        
        # Attach hooks to planner
        planner.on_plan = on_plan_hook
        planner.on_step_start = on_step_start_hook
        planner.on_step_end = on_step_end_hook
        planner.on_error = on_error_hook

    def run_enhanced_visualization(self, planner, query: str, mode: str = "incremental"):
        """Enhanced visualization runner with improved graph handling."""
        
        # Reset step processor for new execution
        self.step_processor = EnhancedStepProcessor()
        self.execution_log = []
        
        # Setup hooks
        self.setup_enhanced_planner_hooks(planner)
        
        # Create containers for real-time updates
        st.subheader(f"Executing in {mode.upper()} mode")
        
        # Progress and status at the top
        progress_container = st.empty()
        
        # Graph visualization - improved with tabs for different views
        st.subheader(" Execution Visualization")
        
        # Create tabs for different visualization types
        viz_tab1, viz_tab2 = st.tabs(["📈 Interactive Graph", "🔗 Network Diagram"])
        
        with viz_tab1:
            interactive_graph_container = st.empty()
        
        with viz_tab2:
            network_graph_container = st.empty()
        
        # Metrics and timeline in separate sections
        st.subheader("Real-time Metrics")
        metrics_container = st.empty()
        
        st.subheader("Execution Timeline")
        timeline_container = st.empty()
        
        st.subheader("Step Details")
        steps_container = st.empty()
        
        print(f"\n{'='*60}")
        print(f"STARTING TOOLCHAIN EXECUTION")
        print(f"Query: {query}")
        print(f"Mode: {mode}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Start execution in a separate thread
        execution_results = {}
        
        def execution_thread():
            try:
                self.is_running = True
                for output in planner.execute_tool_chain(query, mode=mode):
                    if isinstance(output, dict):
                        execution_results.update(output)
                        self.update_queue.put(('results', execution_results))
                    else:
                        self.update_queue.put(('output', str(output)))
                        
                self.is_running = False
                self.update_queue.put(('done', None))
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ EXECUTION FAILED: {str(e)}")
                self.update_queue.put(('error', str(e)))
                self.is_running = False
        
        # Start execution
        exec_thread = threading.Thread(target=execution_thread)
        exec_thread.start()
        
        # Real-time update loop
        update_counter = 0
        execution_id = st.session_state.current_execution_id
        
        while self.is_running or not self.update_queue.empty():
            try:
                # Process updates
                while not self.update_queue.empty():
                    event_type, data = self.update_queue.get_nowait()
                    
                    if event_type == 'plan':
                        self.current_plan = data
                        try:
                            print(f"📋 Plan generated with {len(data) if data else 0} steps")
                        except Exception:
                            print("📋 Plan generated")
                    
                    elif event_type in ['step_start', 'step_end']:
                        pass  # Already handled in hooks
                    
                    elif event_type == 'results':
                        execution_results.update(data)
                    
                    elif event_type == 'output':
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 Output: {data}")
                    
                    elif event_type == 'done':
                        print(f"\n{'='*60}")
                        print(f"✅ EXECUTION COMPLETED SUCCESSFULLY")
                        print(f"Total Steps: {len(self.step_processor.get_all_steps())}")
                        print(f"Total Time: {(datetime.now() - self.step_processor.start_time).total_seconds():.2f}s")
                        print(f"{'='*60}\n")
                        self.is_running = False
                    
                    elif event_type == 'error':
                        self.is_running = False
                # Update visualizations with better frequency control
                if update_counter % 2 == 0:  # Update every 2 iterations
                    steps = self.step_processor.get_all_steps()
                    current_signature = self._get_steps_signature(steps)
                    
                    # Only update charts if data actually changed
                    if current_signature != self.last_chart_signature:
                        self.last_chart_signature = current_signature
                        
                        # Your existing progress update code...
                        if steps:
                            completed = len([s for s in steps if s['status'] in ['COMPLETED', 'ERROR']])
                            total = len(steps)
                            progress = completed / total if total > 0 else 0
                            
                            with progress_container.container():
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.progress(progress)
                                with col2:
                                    st.write(f"**{completed}/{total}** steps")
                        
                        # Update interactive graph with STABLE key
                        if steps:
                            with interactive_graph_container.container():
                                fig = self.create_interactive_plotly_graph(steps, mode)
                                unique_key = self.generate_unique_key(f"graph_{execution_id}", steps)
                                # Use execution_id as key instead of update_counter
                                st.plotly_chart(fig, use_container_width=True)
                                                # key=unique_key)
                                            # key=f"graph_{execution_id}")
                        
                        # Update other charts similarly...
                        with metrics_container.container():
                            self.create_real_time_metrics(steps)
                        
                        if steps:
                            self.create_step_timeline_chart(steps, f"timeline_{execution_id}")
                        
                        with steps_container.container():
                            self.create_live_step_monitor(steps)
                    
                    # Always update network diagram at lower frequency
                    if update_counter % 8 == 0 and steps:  # Every 8th iteration
                        with network_graph_container.container():
                            try:
                                graph_source = self.create_enhanced_execution_graph(steps, mode)
                                st.graphviz_chart(graph_source, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error rendering network diagram: {str(e)}")
                
                update_counter += 1
                time.sleep(0.5)  # Longer sleep to reduce update frequency
                
            except queue.Empty:
                time.sleep(0.1)

        return execution_results, self.step_processor.get_all_steps()

    def create_enhanced_test_interface(self, planner):
        """Enhanced test interface with better step monitoring."""
        st.subheader("🧪 Enhanced Test Interface")
        
        # Test scenario selection
        test_scenarios = {
            "Simple Sequential": {
                "query": "What is the current weather and then create a brief summary?",
                "mode": "incremental"
            },
            "Multi-step Analysis": {
                "query": "Research AI trends, analyze the data, and create a comprehensive report",
                "mode": "batch"
            },
            "Parallel Processing": {
                "query": "Compare multiple solutions and find the best approach",
                "mode": "speculative"
            },
            "Error Recovery Test": {
                "query": "Call a non-existent tool and demonstrate error handling",
                "mode": "incremental"
            },
            "Custom Query": {
                "query": "",
                "mode": "incremental"
            }
        }
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_scenario = st.selectbox(
                "Choose a test scenario:",
                list(test_scenarios.keys())
            )
            
            scenario = test_scenarios[selected_scenario]
            query = st.text_area(
                "Query:", 
                value=scenario["query"],
                placeholder="Enter your custom query here..."
            )
            
            mode = st.selectbox(
                "Execution Mode:",
                ["incremental", "batch", "speculative", "hybrid"],
                index=["incremental", "batch", "speculative", "hybrid"].index(scenario["mode"])
            )
            
        # with col2:
            max_steps = st.number_input("Max Steps:", min_value=1, max_value=50, value=10)
            
            # Advanced options
            with st.expander("Advanced Options"):
                verbose_logging = st.checkbox("Verbose Console Logging", value=True)
                auto_refresh = st.checkbox("Auto Refresh Display", value=True)
                step_delay = st.slider("Step Delay (seconds)", 0.0, 2.0, 0.1)
            
            # Graph display options
            with st.expander("Graph Display Options"):
                default_graph_height = st.slider("Graph Height (px)", 300, 1000, 600)
                show_node_details = st.checkbox("Show Node Details", value=True)
                enable_zoom = st.checkbox("Enable Graph Zoom/Pan", value=True)
            
            if st.button("🚀 Run Enhanced Test", type="primary"):
                if not query.strip():
                    st.error("Please enter a query!")
                    return
                    
                st.session_state.current_execution_id += 1
                execution_id = st.session_state.current_execution_id
                
                with st.spinner(f"Executing toolchain (ID: {execution_id})..."):
                    results, steps = self.run_enhanced_visualization(planner, query, mode)
                
                # Store detailed results
                st.session_state.execution_history.append({
                    'id': execution_id,
                    'timestamp': datetime.now(),
                    'query': query,
                    'mode': mode,
                    'results': results,
                    'steps': steps,
                    'success': bool(results and not any(s['status'] == 'ERROR' for s in steps)),
                    'total_duration': sum(s['duration'] or 0 for s in steps),
                    'step_count': len(steps)
                })
                
                st.success(f"✅ Test {execution_id} completed!")
                
                # Show summary results with improved layout
                if results or steps:
                    with st.expander("📊 Execution Summary", expanded=True):
                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                        
                        with summary_col1:
                            st.metric("Steps Executed", len(steps))
                            
                        with summary_col2:
                            success_count = len([s for s in steps if s['status'] == 'COMPLETED'])
                            st.metric("Successful Steps", success_count)
                            
                        with summary_col3:
                            total_time = sum(s['duration'] or 0 for s in steps)
                            st.metric("Total Time", f"{total_time:.2f}s")
                        
                        with summary_col4:
                            avg_step_time = total_time / len(steps) if steps else 0
                            st.metric("Avg Step Time", f"{avg_step_time:.2f}s")
                        
                        # Final results display
                        if results:
                            st.subheader("📋 Final Results")
                            
                            # Create expandable sections for large results
                            if len(str(results)) > 1000:
                                with st.expander("View Full Results", expanded=False):
                                    st.json(results)
                                
                                # Show preview
                                st.write("**Results Preview:**")
                                result_preview = str(results)[:500] + "..." if len(str(results)) > 500 else str(results)
                                st.code(result_preview)
                            else:
                                st.json(results)

    def show_enhanced_execution_history(self):
        """Enhanced execution history with detailed analytics and improved graph display."""
        st.subheader("📊 Enhanced Execution History & Analytics")
        
        if not st.session_state.execution_history:
            st.info("No execution history available. Run some tests first!")
            return
        
        # Summary metrics
        history = st.session_state.execution_history
        
        # Top-level metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Executions", len(history))
        with col2:
            successful = len([h for h in history if h['success']])
            st.metric("Successful", successful, delta=f"{(successful/len(history)*100):.1f}%")
        with col3:
            avg_steps = sum(h['step_count'] for h in history) / len(history)
            st.metric("Avg Steps", f"{avg_steps:.1f}")
        with col4:
            avg_duration = sum(h['total_duration'] for h in history) / len(history)
            st.metric("Avg Duration", f"{avg_duration:.2f}s")
        
        # Detailed history table with better formatting
        st.subheader("📋 Execution History")
        
        # Selection interface
        history_col1, history_col2 = st.columns([3, 1])
        
        with history_col1:
            selected_execution = st.selectbox(
                "Select execution to view details:",
                options=range(len(history)),
                format_func=lambda i: f"ID {history[i]['id']}: {history[i]['query'][:50]}..." if len(history[i]['query']) > 50 else f"ID {history[i]['id']}: {history[i]['query']}"
            )
        
        with history_col2:
            show_all_details = st.checkbox("Show All Details", value=False)
        
        # Create history table
        history_data = []
        for i, exec_data in enumerate(reversed(history)):  # Show most recent first
            history_data.append({
                'ID': exec_data['id'],
                'Timestamp': exec_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'Query': exec_data['query'][:60] + "..." if len(exec_data['query']) > 60 else exec_data['query'],
                'Mode': exec_data['mode'].upper(),
                'Steps': exec_data['step_count'],
                'Duration': f"{exec_data['total_duration']:.2f}s",
                'Success': "✅" if exec_data['success'] else "❌"
            })
        
        df = pd.DataFrame(history_data)
        st.dataframe(df, use_container_width=True, height=300)
        
        # Detailed view of selected execution
        if selected_execution is not None:
            exec_details = history[selected_execution]
            
            st.subheader(f"📋 Execution Details - ID {exec_details['id']}")
            
            # Show execution overview
            detail_col1, detail_col2, detail_col3 = st.columns(3)
            
            with detail_col1:
                st.write(f"**Query:** {exec_details['query']}")
                st.write(f"**Mode:** {exec_details['mode']}")
            
            with detail_col2:
                st.write(f"**Timestamp:** {exec_details['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(f"**Success:** {'✅ Yes' if exec_details['success'] else '❌ No'}")
            
            with detail_col3:
                st.write(f"**Total Steps:** {exec_details['step_count']}")
                st.write(f"**Total Duration:** {exec_details['total_duration']:.2f}s")
            
            # Show step-by-step breakdown with improved visualization
            steps = exec_details.get('steps', [])
            if steps:
                st.subheader("📈 Step Timeline")
                
                # Create timeline chart with unique key for history view
                timeline_key = f"history_{exec_details['id']}"
                self.create_step_timeline_chart(steps, timeline_key)
                
                # Show execution graph for this specific execution
                st.subheader("🔗 Execution Graph")
                
                graph_col1, graph_col2 = st.columns([2, 1])
                
                with graph_col1:
                    # Interactive graph
                    fig = self.create_interactive_plotly_graph(steps, exec_details['mode'])
                    unique_graph_key = self.generate_unique_key(f"history_graph_{exec_details['id']}")
                    st.plotly_chart(fig, use_container_width=True, key=unique_graph_key)
                
                with graph_col2:
                    # Graph options
                    st.write("**Graph Options:**")
                    show_network = st.checkbox(f"Show Network Diagram", key=f"network_{exec_details['id']}")
                    
                    if show_network:
                        try:
                            graph_source = self.create_enhanced_execution_graph(steps, exec_details['mode'])
                            st.graphviz_chart(graph_source, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error rendering network diagram: {str(e)}")
                
                # Detailed step information
                if show_all_details:
                    st.subheader("🔍 Detailed Step Information")
                    for step in steps:
                        self.print_step_info(step)
                else:
                    st.subheader("📋 Step Summary")
                    step_summary = []
                    for step in steps:
                        step_summary.append({
                            'Step': step['step_number'],
                            'Tool': step['tool_name'],
                            'Status': step['status'],
                            'Duration': f"{step['duration']:.2f}s" if step['duration'] else "N/A"
                        })
                    
                    step_df = pd.DataFrame(step_summary)
                    st.dataframe(step_df, use_container_width=True)
        
        # Analytics charts with unique keys
        st.subheader("📈 Analytics Dashboard")
        
        if len(history) > 1:
            analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs([
                "📊 Success Metrics", 
                "⏱️ Performance Trends", 
                "🔍 Execution Patterns"
            ])
            
            with analytics_tab1:
                analytics_col1, analytics_col2 = st.columns(2)
                
                with analytics_col1:
                    # Success rate by mode
                    mode_data = {}
                    for h in history:
                        mode = h['mode']
                        if mode not in mode_data:
                            mode_data[mode] = {'total': 0, 'success': 0}
                        mode_data[mode]['total'] += 1
                        if h['success']:
                            mode_data[mode]['success'] += 1
                    
                    mode_df = pd.DataFrame([
                        {
                            'Mode': mode,
                            'Success_Rate': (data['success'] / data['total']) * 100,
                            'Total': data['total']
                        }
                        for mode, data in mode_data.items()
                    ])
                    
                    fig = px.bar(
                        mode_df,
                        x='Mode',
                        y='Success_Rate',
                        title="Success Rate by Execution Mode",
                        color='Success_Rate',
                        color_continuous_scale='RdYlGn',
                        text='Total'
                    )
                    fig.update_traces(texttemplate='%{text} executions', textposition='outside')
                    
                    success_key = self.generate_unique_key("success_rate_chart")
                    st.plotly_chart(fig, use_container_width=True, key=success_key)
                
                with analytics_col2:
                    # Success rate over time
                    time_success = []
                    for i, h in enumerate(history):
                        time_success.append({
                            'Execution': i + 1,
                            'Success': 1 if h['success'] else 0,
                            'Timestamp': h['timestamp']
                        })
                    
                    time_df = pd.DataFrame(time_success)
                    
                    # Calculate rolling success rate
                    window = min(5, len(time_df))
                    if window > 1:
                        time_df['Rolling_Success'] = time_df['Success'].rolling(window=window).mean()
                        
                        fig = px.line(
                            time_df,
                            x='Execution',
                            y='Rolling_Success',
                            title=f"Success Rate Trend (Rolling {window}-execution average)",
                            range_y=[0, 1]
                        )
                        
                        time_success_key = self.generate_unique_key("time_success_chart")
                        st.plotly_chart(fig, use_container_width=True, key=time_success_key)
            
            with analytics_tab2:
                perf_col1, perf_col2 = st.columns(2)
                
                with perf_col1:
                    # Duration vs Steps scatter plot
                    scatter_data = [
                        {
                            'Steps': h['step_count'],
                            'Duration': h['total_duration'],
                            'Mode': h['mode'],
                            'Success': 'Success' if h['success'] else 'Failed',
                            'ID': h['id']
                        }
                        for h in history
                    ]
                    
                    scatter_df = pd.DataFrame(scatter_data)
                    
                    fig = px.scatter(
                        scatter_df,
                        x='Steps',
                        y='Duration',
                        color='Mode',
                        symbol='Success',
                        title="Duration vs Steps Analysis",
                        hover_data=['ID'],
                        size_max=15
                    )
                    
                    scatter_key = self.generate_unique_key("duration_scatter")
                    st.plotly_chart(fig, use_container_width=True, key=scatter_key)
                
                with perf_col2:
                    # Performance trend over time
                    perf_trend = []
                    for i, h in enumerate(history):
                        perf_trend.append({
                            'Execution': i + 1,
                            'Duration': h['total_duration'],
                            'Steps_per_Second': h['step_count'] / max(h['total_duration'], 0.1),
                            'Timestamp': h['timestamp']
                        })
                    
                    trend_df = pd.DataFrame(perf_trend)
                    
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    fig.add_trace(
                        go.Scatter(x=trend_df['Execution'], y=trend_df['Duration'], 
                                 mode='lines+markers', name='Duration (s)'),
                        secondary_y=False,
                    )
                    
                    fig.add_trace(
                        go.Scatter(x=trend_df['Execution'], y=trend_df['Steps_per_Second'], 
                                 mode='lines+markers', name='Steps/Second', 
                                 line=dict(color='orange')),
                        secondary_y=True,
                    )
                    
                    fig.update_xaxes(title_text="Execution Number")
                    fig.update_yaxes(title_text="Duration (seconds)", secondary_y=False)
                    fig.update_yaxes(title_text="Steps per Second", secondary_y=True)
                    fig.update_layout(title_text="Performance Trends Over Time")
                    
                    trend_key = self.generate_unique_key("performance_trend")
                    st.plotly_chart(fig, use_container_width=True, key=trend_key)
            
            with analytics_tab3:
                pattern_col1, pattern_col2 = st.columns(2)
                
                with pattern_col1:
                    # Execution mode distribution
                    mode_counts = pd.Series([h['mode'] for h in history]).value_counts()
                    
                    fig = px.pie(
                        values=mode_counts.values,
                        names=mode_counts.index,
                        title="Execution Mode Distribution"
                    )
                    
                    mode_dist_key = self.generate_unique_key("mode_distribution")
                    st.plotly_chart(fig, use_container_width=True, key=mode_dist_key)
                
                with pattern_col2:
                    # Step count distribution
                    step_counts = [h['step_count'] for h in history]
                    
                    fig = px.histogram(
                        x=step_counts,
                        nbins=min(20, max(step_counts) - min(step_counts) + 1),
                        title="Step Count Distribution",
                        labels={'x': 'Number of Steps', 'y': 'Frequency'}
                    )
                    
                    step_dist_key = self.generate_unique_key("step_distribution")
                    st.plotly_chart(fig, use_container_width=True, key=step_dist_key)

# --------------------------
# Vera singleton
# --------------------------
@st.cache_resource
def get_vera():
    return Vera()

# -----------------------
def main():
    """
    Enhanced main Streamlit app function.
    """
    visualizer = StreamlitToolchainVisualizer()
    visualizer.setup_page()
    
    # Sidebar for enhanced configuration
    with st.sidebar:
        st.header("⚙️ Enhanced Configuration")
        
        # Planner setup section
        st.subheader("🔧 Planner Setup")
        
        # Initialize planner
        try:
            agent = get_vera()
            planner = ToolChainPlanner(agent, agent.tools)
            st.success("✅ Planner initialized successfully!")
            
            # Planner configuration
            with st.expander("Planner Settings"):
                planner.max_steps = st.number_input(
                    "Max Steps", 
                    min_value=1, 
                    max_value=100, 
                    value=getattr(planner, 'max_steps', 10)
                )
                
                # Additional planner settings
                timeout = st.number_input("Timeout (seconds)", min_value=10, max_value=300, value=60)
                parallel_execution = st.checkbox("Enable Parallel Execution", value=False)
                debug_mode = st.checkbox("Debug Mode", value=True)
                
        except Exception as e:
            st.error(f"❌ Failed to initialize planner: {str(e)}")
            planner = None
            st.code("""
# Example planner initialization:
from vera import Vera
from toolchain import ToolChainPlanner

# Initialize your agent and tools
agent = Vera()
tools = agent.tools

# Create planner
planner = ToolChainPlanner(agent, tools)
            """)
        
        st.divider()
        
        # Display configuration
        st.subheader("🎨 Display Settings")
        auto_refresh_interval = st.slider("Auto Refresh Interval (seconds)", 0.1, 5.0, 0.5)
        show_detailed_logs = st.checkbox("Show Detailed Console Logs", value=True)
        compact_view = st.checkbox("Compact View Mode", value=False)
        
        # Export/Import settings
        st.subheader("💾 Data Management")
        if st.button("📥 Export History"):
            if st.session_state.execution_history:
                export_data = {
                    'timestamp': datetime.now().isoformat(),
                    'history': st.session_state.execution_history
                }
                st.download_button(
                    "Download History JSON",
                    data=json.dumps(export_data, indent=2, default=str),
                    file_name=f"toolchain_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            else:
                st.info("No history to export")
        
        if st.button("🗑️ Clear History"):
            st.session_state.execution_history = []
            st.session_state.current_execution_id = 0
            st.success("History cleared!")
            st.experimental_rerun()
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "📍 Navigate to:",
            [
                "🚀 Enhanced Test Runner", 
                "📊 History & Analytics", 
                "🔍 Live Monitor",
                "🛠️ Tool Inspector",
                "📈 Performance Dashboard"
            ]
        )
        
        # Quick stats in sidebar
        if st.session_state.execution_history:
            st.subheader("📈 Quick Stats")
            history = st.session_state.execution_history
            
            total_executions = len(history)
            successful_executions = len([h for h in history if h['success']])
            total_steps = sum(h['step_count'] for h in history)
            
            st.metric("Total Executions", total_executions)
            st.metric("Success Rate", f"{(successful_executions/total_executions*100):.1f}%" if total_executions > 0 else "0%")
            st.metric("Total Steps Executed", total_steps)
    
    # Main content area with enhanced navigation
    if page == "🚀 Enhanced Test Runner":
        if planner:
            visualizer.create_enhanced_test_interface(planner)
        else:
            st.warning("⚠️ Please initialize the planner first!")
            st.info("Check the sidebar for planner setup instructions.")
    
    elif page == "📊 History & Analytics":
        visualizer.show_enhanced_execution_history()
    
    elif page == "🔍 Live Monitor":
        st.subheader("🔍 Live Execution Monitor")
        
        if not planner:
            st.warning("⚠️ Planner not initialized!")
            return
            
        st.info("This section shows real-time monitoring of active executions")
        
        # Live monitoring interface
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # System status
            st.metric("System Status", "🟢 Online")
            
        with col2:
            # Active executions (would be populated during actual execution)
            active_executions = 0  # This would come from actual monitoring
            st.metric("Active Executions", active_executions)
            
        with col3:
            # Queue length
            queue_length = 0  # This would come from actual monitoring
            st.metric("Queue Length", queue_length)
        
        # Real-time log viewer
        st.subheader("📋 Real-time Logs")
        log_container = st.empty()
        
        # Simulated log updates (in real implementation, this would connect to actual logs)
        if st.button("🔄 Refresh Logs"):
            with log_container.container():
                st.text_area(
                    "System Logs",
                    value=f"[{datetime.now().strftime('%H:%M:%S')}] System monitoring active...\n"
                          f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for executions...",
                    height=200,
                    disabled=True
                )
        
        # Performance metrics
        st.subheader("⚡ Real-time Performance")
        
        # Create mock real-time metrics (in real implementation, these would be live)
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        with metric_col1:
            st.metric("CPU Usage", "12%", delta="-3%")
        with metric_col2:
            st.metric("Memory Usage", "456MB", delta="12MB")
        with metric_col3:
            st.metric("Avg Response Time", "1.2s", delta="-0.3s")
        with metric_col4:
            st.metric("Throughput", "8.5 steps/min", delta="1.2")
    
    elif page == "🛠️ Tool Inspector":
        st.subheader("🛠️ Tool Inspector")
        
        if not planner:
            st.warning("⚠️ Planner not initialized!")
            return
            
        st.info("Inspect and test individual tools in your toolchain")
        
        # Tool list and details
        if hasattr(planner, 'tools') and planner.tools:
            tools = planner.tools
            
            # Tool selection
            tool_names = [getattr(tool, 'name', str(tool)) for tool in tools]
            selected_tool = st.selectbox("Select a tool to inspect:", tool_names)
            
            if selected_tool:
                # Find the selected tool
                tool = None
                for t in tools:
                    if getattr(t, 'name', str(t)) == selected_tool:
                        tool = t
                        break
                
                if tool:
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.subheader("📋 Tool Information")
                        
                        # Display tool details
                        tool_info = {
                            "Name": getattr(tool, 'name', 'Unknown'),
                            "Description": getattr(tool, 'description', 'No description available'),
                            "Type": type(tool).__name__,
                            "Module": type(tool).__module__
                        }
                        
                        for key, value in tool_info.items():
                            st.write(f"**{key}:** {value}")
                        
                        # Tool parameters/schema if available
                        if hasattr(tool, 'parameters') or hasattr(tool, 'schema'):
                            st.subheader("🔧 Parameters")
                            params = getattr(tool, 'parameters', getattr(tool, 'schema', {}))
                            if params:
                                st.json(params)
                            else:
                                st.info("No parameter information available")
                    
                    with col2:
                        st.subheader("🧪 Tool Tester")
                        
                        # Simple tool testing interface
                        st.info("Tool testing interface - implement based on your tool structure")
                        
                        test_input = st.text_area(
                            "Test Input:",
                            placeholder="Enter test input for this tool..."
                        )
                        
                        if st.button("🧪 Test Tool"):
                            if test_input:
                                st.info("Tool testing would be implemented here based on your tool interface")
                                # In real implementation:
                                # try:
                                #     result = tool.run(test_input)
                                #     st.success("Tool executed successfully!")
                                #     st.json(result)
                                # except Exception as e:
                                #     st.error(f"Tool execution failed: {e}")
                            else:
                                st.warning("Please enter test input")
        else:
            st.info("No tools available in the planner")
    
    elif page == "📈 Performance Dashboard":
        st.subheader("📈 Performance Dashboard")
        
        if not st.session_state.execution_history:
            st.info("No performance data available. Run some executions first!")
            return
        
        history = st.session_state.execution_history
        
        # Performance overview
        st.subheader("📊 Performance Overview")
        
        # Time series performance chart
        perf_data = []
        for i, exec_data in enumerate(history):
            perf_data.append({
                'Execution': i + 1,
                'Duration': exec_data['total_duration'],
                'Steps': exec_data['step_count'],
                'Success': exec_data['success'],
                'Mode': exec_data['mode'],
                'Timestamp': exec_data['timestamp']
            })
        
        perf_df = pd.DataFrame(perf_data)
        
        # Performance trend chart
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Execution Duration Trend', 'Steps per Execution', 
                          'Success Rate Over Time', 'Performance by Mode'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Duration trend
        fig.add_trace(
            go.Scatter(x=perf_df['Execution'], y=perf_df['Duration'], 
                      mode='lines+markers', name='Duration'),
            row=1, col=1
        )
        
        # Steps trend
        fig.add_trace(
            go.Scatter(x=perf_df['Execution'], y=perf_df['Steps'], 
                      mode='lines+markers', name='Steps', line_color='orange'),
            row=1, col=2
        )
        
        # Success rate (rolling average)
        window_size = min(5, len(perf_df))
        if window_size > 1:
            perf_df['Success_Rolling'] = perf_df['Success'].rolling(window=window_size).mean()
            fig.add_trace(
                go.Scatter(x=perf_df['Execution'], y=perf_df['Success_Rolling'], 
                          mode='lines', name='Success Rate', line_color='green'),
                row=2, col=1
            )
        
        # Performance by mode
        mode_performance = perf_df.groupby('Mode')['Duration'].mean().reset_index()
        fig.add_trace(
            go.Bar(x=mode_performance['Mode'], y=mode_performance['Duration'], 
                   name='Avg Duration by Mode'),
            row=2, col=2
        )
        
        fig.update_layout(height=600, showlegend=True, title_text="Performance Analytics Dashboard")
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed performance metrics
        st.subheader("🔍 Detailed Performance Metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Average Duration", f"{perf_df['Duration'].mean():.2f}s")
            st.metric("Min Duration", f"{perf_df['Duration'].min():.2f}s")
            st.metric("Max Duration", f"{perf_df['Duration'].max():.2f}s")
        
        with col2:
            st.metric("Average Steps", f"{perf_df['Steps'].mean():.1f}")
            st.metric("Min Steps", int(perf_df['Steps'].min()))
            st.metric("Max Steps", int(perf_df['Steps'].max()))
        
        with col3:
            overall_success_rate = (perf_df['Success'].sum() / len(perf_df)) * 100
            st.metric("Overall Success Rate", f"{overall_success_rate:.1f}%")
            
            # Performance efficiency (steps per second)
            efficiency = perf_df['Steps'] / perf_df['Duration']
            st.metric("Avg Steps/Second", f"{efficiency.mean():.1f}")
        
        # Performance recommendations
        st.subheader("💡 Performance Recommendations")
        
        recommendations = []
        
        # Analyze performance patterns
        if perf_df['Duration'].std() > perf_df['Duration'].mean():
            recommendations.append("⚠️ High duration variance detected. Consider optimizing inconsistent steps.")
        
        if overall_success_rate < 90:
            recommendations.append("❌ Success rate below 90%. Review error handling and tool reliability.")
        
        slow_executions = perf_df[perf_df['Duration'] > perf_df['Duration'].quantile(0.8)]
        if not slow_executions.empty:
            recommendations.append(f"🐌 {len(slow_executions)} slow executions detected (>80th percentile).")
        
        if len(set(perf_df['Mode'])) > 1:
            best_mode = mode_performance.loc[mode_performance['Duration'].idxmin(), 'Mode']
            recommendations.append(f"🚀 '{best_mode}' mode shows best performance on average.")
        
        if recommendations:
            for rec in recommendations:
                st.info(rec)
        else:
            st.success("✅ Performance looks good! No specific recommendations at this time.")

if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
    from vera import Vera
    main()