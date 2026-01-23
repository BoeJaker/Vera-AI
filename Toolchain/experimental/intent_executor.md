Absolutely! This is a perfect fit. I'll integrate the intent-based executor with your VTool framework to create a unified system that has:

- Intent-first planning with lazy tool loading (my contribution)
- Memory-aware entity creation (your VTool)
- Real-time UI updates and graph broadcasting (your UI framework)
- Distributed orchestration (your orchestration framework)

Here's the complete integration:

```python
#!/usr/bin/env python3
"""
Vera Intent-Based Executor Integration
Combines intent planning with VTool framework for full-featured execution.

Integration provides:
- Intent-first planning (fast TTFT)
- Memory-aware entity/relationship creation
- Real-time UI updates and graph broadcasting
- Distributed orchestration support
- Learned tool ranking
- Workflow caching
"""

from typing import Any, Dict, List, Optional, Iterator, Union, Type, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import hashlib
import json
import time
import copy
from datetime import datetime

# Import Vera tool framework
from tool_framework import (
    VTool, ToolResult, ToolEntity, ToolRelationship, OutputType
)
from tool_ui_framework import (
    UITool, UIComponent, UIComponentType, UIUpdate,
    GraphEvent, GraphEventType, EventBroadcaster
)
from tool_orchestration import (
    OrchestratedVTool, OrchestrationPattern, SubTask, DistributedExecution
)

# =============================================================================
# INTENT MODEL (from executor)
# =============================================================================

@dataclass
class IntentStep:
    """A single step in an intent plan (tool-agnostic)."""
    intent: str
    params: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IntentPlan:
    """A sequence of intent steps forming a complete plan."""
    steps: List[IntentStep]
    metadata: Dict[str, Any] = field(default_factory=dict)

# =============================================================================
# TOOL DOMAINS (for LLM context)
# =============================================================================

@dataclass
class ToolDomain:
    """Capability domain exposed to LLM during planning."""
    name: str
    description: str
    intents: Dict[str, str]  # intent -> description

# Standard domains
DOMAIN_REGISTRY = {
    "containers": ToolDomain(
        "containers",
        "Container lifecycle management",
        {
            "enumerate_containers": "List running containers",
            "remove_container": "Delete a container",
            "exec_in_container": "Run command in container"
        }
    ),
    "network": ToolDomain(
        "network",
        "Network scanning and discovery",
        {
            "scan_network": "Scan network for hosts",
            "scan_ports": "Scan ports on host",
            "enumerate_hosts": "List network hosts"
        }
    ),
    "git": ToolDomain(
        "git",
        "Source control operations",
        {
            "clone_repo": "Clone repository",
            "check_repo_status": "Check git status"
        }
    ),
    "services": ToolDomain(
        "services",
        "System service management",
        {
            "check_service": "Query service status",
            "restart_service": "Restart a service"
        }
    ),
    "osint": ToolDomain(
        "osint",
        "Open source intelligence gathering",
        {
            "web_search": "Search the web",
            "scrape_webpage": "Extract data from webpage",
            "enumerate_subdomains": "Find subdomains"
        }
    )
}

# =============================================================================
# INTENT COST MODEL
# =============================================================================

# Prior cost estimates for intents (for early plan rejection)
INTENT_COST_PRIOR = {
    "enumerate_containers": {"cost": 1, "risk": 1, "latency": 1},
    "remove_container": {"cost": 5, "risk": 7, "latency": 2},
    "scan_network": {"cost": 3, "risk": 2, "latency": 4},
    "scan_ports": {"cost": 2, "risk": 1, "latency": 3},
    "clone_repo": {"cost": 3, "risk": 2, "latency": 4},
    "check_service": {"cost": 1, "risk": 1, "latency": 1},
    "web_search": {"cost": 2, "risk": 1, "latency": 2},
}

def estimate_intent_cost(intent: str) -> Dict[str, int]:
    """Get cost prior for an intent."""
    return INTENT_COST_PRIOR.get(intent, {"cost": 5, "risk": 5, "latency": 5})

# =============================================================================
# TOOL RANKING
# =============================================================================

class ToolRanker:
    """Ranks tool candidates based on learned success rates and metrics."""
    
    def score(self, tool: 'IntentTool') -> float:
        """
        Compute ranking score (higher is better).
        
        Formula:
            score = (success_rate * 10) - tool_cost - tool_risk
        """
        success_rate = getattr(tool, 'historical_success', 1.0)
        cost = getattr(tool, 'cost', 1)
        risk = getattr(tool, 'risk', 1)
        
        return (success_rate * 10.0) - cost - risk
    
    def rank(self, tools: List['IntentTool']) -> List[Tuple[float, 'IntentTool']]:
        """
        Rank tools by score.
        
        Returns:
            List of (score, tool) tuples, sorted by score descending
        """
        candidates = [(self.score(tool), tool) for tool in tools]
        return sorted(candidates, key=lambda x: x[0], reverse=True)

# =============================================================================
# WORKFLOW CACHE
# =============================================================================

class WorkflowCache:
    """Caches intent plan → tool DAG resolutions."""
    
    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.ttl = ttl
    
    def key(self, intent_plan: IntentPlan) -> str:
        """Generate cache key from intent plan."""
        return hashlib.sha256(
            json.dumps(
                [(s.intent, s.constraints) for s in intent_plan.steps],
                sort_keys=True
            ).encode()
        ).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached workflow if fresh."""
        if key in self.cache:
            workflow, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return workflow
            else:
                del self.cache[key]
        return None
    
    def put(self, key: str, workflow: Any):
        """Store workflow in cache."""
        self.cache[key] = (workflow, time.time())

# =============================================================================
# VARIABLE RESOLUTION
# =============================================================================

import re

VAR_PATTERN = re.compile(r"\{\{([^}]+)\}\}")

def resolve_variables(obj: Any, state: Dict[str, Any]) -> Any:
    """
    Recursively resolve {{variable}} references.
    
    Can reference:
        - {{vars.variable_name}}
        - {{artifacts.tool_name.0.property}}
    """
    if isinstance(obj, str):
        match = VAR_PATTERN.fullmatch(obj)
        if match:
            path = match.group(1)
            parts = path.split(".")
            
            current = state
            for part in parts:
                if isinstance(current, list):
                    current = current[int(part)]
                elif isinstance(current, dict):
                    current = current.get(part)
                else:
                    return obj
            
            return current
        return obj
    
    elif isinstance(obj, dict):
        return {k: resolve_variables(v, state) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        return [resolve_variables(item, state) for item in obj]
    
    return obj

# =============================================================================
# LLM VARIABLE SUGGESTION
# =============================================================================

def llm_suggest_variables(artifacts: Dict[str, List]) -> List[Dict[str, Any]]:
    """
    Generate candidate variable bindings from artifacts.
    
    Returns:
        List of variable binding dicts (each is a branch candidate)
    """
    suggestions = []
    
    # Network hosts
    if any('network' in k for k in artifacts.keys()):
        for tool_name, results in artifacts.items():
            if 'network' in tool_name and isinstance(results, list):
                for result in results:
                    if isinstance(result, dict):
                        # Extract IPs from network entities
                        if 'ip_address' in result.get('properties', {}):
                            suggestions.append({
                                "target_ip": result['properties']['ip_address'],
                                "target_entity_id": result.get('id')
                            })
    
    # Containers
    if "docker_ps" in artifacts or "enumerate_containers" in artifacts:
        for tool_name in ["docker_ps", "enumerate_containers"]:
            if tool_name in artifacts:
                for container in artifacts[tool_name]:
                    if isinstance(container, dict):
                        suggestions.append({
                            "primary_container": container.get("id"),
                            "container_image": container.get("image")
                        })
    
    # Git repos
    if "git_clone" in artifacts:
        for repo in artifacts["git_clone"]:
            if isinstance(repo, dict):
                suggestions.append({
                    "target_repo": repo.get("name")
                })
    
    return suggestions if suggestions else [{}]

# =============================================================================
# INTENT-AWARE VTOOL (Base Class)
# =============================================================================

class IntentTool(UITool, OrchestratedVTool):
    """
    VTool that supports intent-based execution.
    
    Combines:
        - VTool: Memory, entity creation, streaming
        - UITool: Real-time UI updates, graph broadcasting
        - OrchestratedVTool: Distributed execution
        - IntentTool: Intent declaration, learned ranking
    
    Tools declare which intents they satisfy, allowing:
        - Late binding (LLM plans intents, not tools)
        - Learned ranking (system learns best tools over time)
        - Fast TTFT (tools loaded only when needed)
    """
    
    # Intent declaration
    intents: List[str] = []
    
    # Multi-objective metrics
    cost: int = 1
    risk: int = 1
    
    # Learning
    historical_success: float = 1.0
    execution_count: int = 0
    
    def __init__(self, agent):
        # Initialize all parent classes
        VTool.__init__(self, agent)
        # UITool and OrchestratedVTool will use VTool's __init__
        
        # Intent-specific tracking
        self.intent_executions: Dict[str, int] = {}
        self.intent_success_rates: Dict[str, float] = {}
    
    def update_learning(self, success: bool, intent: str = ""):
        """
        Update learning metrics after execution.
        
        Args:
            success: Whether execution succeeded
            intent: Optional specific intent that was satisfied
        """
        # Overall success tracking
        decay = 0.9
        self.historical_success = (
            self.historical_success * decay +
            (1.0 if success else 0.0) * (1 - decay)
        )
        self.execution_count += 1
        
        # Intent-specific tracking
        if intent:
            if intent not in self.intent_executions:
                self.intent_executions[intent] = 0
                self.intent_success_rates[intent] = 1.0
            
            self.intent_executions[intent] += 1
            self.intent_success_rates[intent] = (
                self.intent_success_rates[intent] * decay +
                (1.0 if success else 0.0) * (1 - decay)
            )
    
    def get_success_rate_for_intent(self, intent: str) -> float:
        """Get success rate for a specific intent."""
        return self.intent_success_rates.get(intent, self.historical_success)

# =============================================================================
# INTENT REGISTRY
# =============================================================================

class IntentRegistry:
    """Registry of all tools by intent."""
    
    def __init__(self):
        self.tools_by_intent: Dict[str, List[IntentTool]] = {}
        self.all_tools: Dict[str, IntentTool] = {}
    
    def register(self, tool: IntentTool):
        """Register a tool."""
        self.all_tools[tool.tool_name] = tool
        
        # Index by intent
        for intent in tool.intents:
            if intent not in self.tools_by_intent:
                self.tools_by_intent[intent] = []
            self.tools_by_intent[intent].append(tool)
    
    def get_by_intent(self, intent: str) -> List[IntentTool]:
        """Get all tools that satisfy an intent."""
        return self.tools_by_intent.get(intent, [])
    
    def get_by_name(self, name: str) -> Optional[IntentTool]:
        """Get tool by name."""
        return self.all_tools.get(name)

# =============================================================================
# INTENT EXECUTOR
# =============================================================================

class IntentExecutor:
    """
    Executes intent plans using VTool framework.
    
    Flow:
        1. Receive intent plan from LLM
        2. Bind intents to tools (with caching)
        3. Execute tools with:
           - Memory tracking
           - UI updates
           - Distributed execution (if available)
           - Variable suggestion/branching
    """
    
    def __init__(
        self,
        agent,
        registry: IntentRegistry,
        cost_limit: int = 100,
        risk_limit: int = 50
    ):
        self.agent = agent
        self.registry = registry
        self.cost_limit = cost_limit
        self.risk_limit = risk_limit
        
        # Components
        self.cache = WorkflowCache()
        self.ranker = ToolRanker()
        
        # Execution state
        self.current_state = None
        self.current_intent_plan = None
    
    # =========================================================================
    # PHASE 1: INTENT PLANNING
    # =========================================================================
    
    def run_intent_plan(
        self,
        intent_plan: IntentPlan,
        initial_state: Optional[Dict] = None
    ) -> Iterator[Union[str, ToolResult, UIUpdate]]:
        """
        Execute an intent plan.
        
        Args:
            intent_plan: Plan to execute
            initial_state: Initial execution state
        
        Yields:
            Streaming output, UI updates, and final result
        """
        self.current_intent_plan = intent_plan
        
        # Initialize state
        if initial_state is None:
            initial_state = {
                "objective": intent_plan.metadata.get("objective", ""),
                "vars": {},
                "artifacts": {},
                "execution_log": {},
                "approvals": set(),
                "metrics": {"cost": 0, "risk": 0, "latency": 0, "resources": 0},
                "branch_history": []
            }
        
        self.current_state = initial_state
        
        # Check cache
        cache_key = self.cache.key(intent_plan)
        cached_dag = self.cache.get(cache_key)
        
        if cached_dag:
            yield "[Cache] Using cached workflow\n"
            yield from self._execute_tool_dag(cached_dag)
            return
        
        # Bind intents to tools
        yield "[Binding] Mapping intents to tools...\n"
        
        try:
            tool_dag = self._bind_intents(intent_plan)
            
            # Cache successful binding
            self.cache.put(cache_key, tool_dag)
            
            # Execute
            yield from self._execute_tool_dag(tool_dag)
            
        except Exception as e:
            yield f"[Error] Execution failed: {e}\n"
            yield ToolResult(
                success=False,
                output="",
                output_type=OutputType.TEXT,
                error=str(e)
            )
    
    # =========================================================================
    # PHASE 2: INTENT → TOOL BINDING
    # =========================================================================
    
    def _bind_intents(self, intent_plan: IntentPlan) -> List[Dict]:
        """
        Bind abstract intents to concrete tools.
        
        Returns:
            Tool DAG ready for execution
        """
        dag = []
        
        for step in intent_plan.steps:
            # Find candidate tools
            candidates = self.registry.get_by_intent(step.intent)
            
            if not candidates:
                raise RuntimeError(f"No tool for intent: {step.intent}")
            
            # Rank candidates
            ranked = self.ranker.rank(candidates)
            
            if not ranked:
                raise RuntimeError(f"No ranked tools for: {step.intent}")
            
            # Select best tool
            score, tool = ranked[0]
            
            print(f"[Bind] {step.intent} → {tool.tool_name} (score={score:.2f})")
            
            dag.append({
                "tool": tool,
                "intent": step.intent,
                "input": step.params,
                "suggest_vars": step.constraints.get("suggest_vars", False)
            })
        
        return dag
    
    # =========================================================================
    # PHASE 3: TOOL EXECUTION
    # =========================================================================
    
    def _execute_tool_dag(
        self,
        dag: List[Dict]
    ) -> Iterator[Union[str, ToolResult, UIUpdate]]:
        """
        Execute tool DAG with branching and backtracking.
        """
        yield from self._execute_recursive(dag, 0)
    
    def _execute_recursive(
        self,
        dag: List[Dict],
        step_idx: int
    ) -> Iterator[Union[str, ToolResult, UIUpdate]]:
        """Recursively execute DAG with variable branching."""
        
        # Base case
        if step_idx >= len(dag):
            return
        
        step = dag[step_idx]
        tool = step["tool"]
        intent = step["intent"]
        
        # Resolve input variables
        resolved_input = resolve_variables(step["input"], self.current_state)
        
        # Update metrics
        intent_cost = estimate_intent_cost(intent)
        self.current_state["metrics"]["cost"] += intent_cost["cost"] + tool.cost
        self.current_state["metrics"]["risk"] += intent_cost["risk"] + tool.risk
        
        # Check limits
        if self.current_state["metrics"]["cost"] > self.cost_limit:
            raise RuntimeError("Cost limit exceeded")
        if self.current_state["metrics"]["risk"] > self.risk_limit:
            raise RuntimeError("Risk limit exceeded")
        
        # Execute tool
        yield f"\n[Execute] {tool.tool_name} (intent: {intent})\n"
        
        final_result = None
        for item in tool.execute(**resolved_input):
            if isinstance(item, ToolResult):
                final_result = item
                
                # Update learning
                tool.update_learning(final_result.success, intent)
                
                # Store artifacts in state
                if final_result.success:
                    # Store tool result
                    self.current_state["artifacts"].setdefault(tool.tool_name, [])
                    self.current_state["artifacts"][tool.tool_name].append(
                        final_result.output
                    )
                    
                    # Store entities (already in memory via VTool)
                    for entity in final_result.entities:
                        entity_key = f"entity_{entity.id}"
                        self.current_state["vars"][entity_key] = entity.id
            else:
                # Stream output or UI update
                yield item
        
        # Variable suggestion branching
        if step.get("suggest_vars") and final_result and final_result.success:
            yield "[Branch] Exploring variable candidates...\n"
            
            candidates = llm_suggest_variables(self.current_state["artifacts"])
            
            for idx, var_patch in enumerate(candidates):
                branch_state = copy.deepcopy(self.current_state)
                branch_state["vars"].update(var_patch)
                
                yield f"[Branch {idx+1}/{len(candidates)}] Trying: {var_patch}\n"
                
                # Try branch
                try:
                    original_state = self.current_state
                    self.current_state = branch_state
                    
                    yield from self._execute_recursive(dag, step_idx + 1)
                    
                    # If we get here, branch succeeded
                    return
                    
                except Exception as e:
                    yield f"[Branch {idx+1}] Failed: {e}\n"
                    self.current_state = original_state
                    continue
            
            # All branches failed
            raise RuntimeError("All variable branches failed")
        
        # No branching - continue
        yield from self._execute_recursive(dag, step_idx + 1)

# =============================================================================
# CONCRETE INTENT TOOLS
# =============================================================================

class NetworkScanIntentTool(IntentTool):
    """Network scanner satisfying network scanning intents."""
    
    intents = ["scan_network", "enumerate_hosts", "discover_network"]
    cost = 3
    risk = 2
    
    def get_input_schema(self):
        from pydantic import BaseModel, Field
        
        class NetworkScanInput(BaseModel):
            target: str = Field(description="Target network (CIDR or range)")
            ports: str = Field(default="1-1000", description="Port range")
        
        return NetworkScanInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, target: str, ports: str = "1-1000") -> Iterator:
        """Execute network scan with full VTool features."""
        
        # UI alert
        self.send_alert(f"Scanning {target}", "info")
        
        # Send initial metrics
        self.send_metrics({
            "target": target,
            "status": "scanning"
        })
        
        yield f"╔═══════════════════════════════════════════════════════════╗\n"
        yield f"║                  NETWORK SCAN: {target:20s}            ║\n"
        yield f"╚═══════════════════════════════════════════════════════════╝\n\n"
        
        # Import scanning tools
        from Vera.Toolchain.Tools.OSINT.network_scanning import (
            HostDiscovery, PortScanner, NetworkScanConfig, TargetParser
        )
        
        config = NetworkScanConfig()
        parser = TargetParser()
        targets = parser.parse(target)
        port_list = parser.parse_ports(ports)
        
        # Host discovery
        discoverer = HostDiscovery(config)
        scanner = PortScanner(config)
        
        live_hosts = []
        all_ports = []
        
        yield f"[Discovery] Scanning {len(targets)} targets...\n\n"
        
        for idx, host_info in enumerate(discoverer.discover_live_hosts(targets), 1):
            if host_info["alive"]:
                ip = host_info["ip"]
                hostname = host_info["hostname"]
                live_hosts.append(ip)
                
                # Create entity in memory
                host_entity = self.create_entity(
                    entity_id=f"ip_{ip.replace('.', '_')}",
                    entity_type="network_host",
                    labels=["NetworkHost", "IP"],
                    properties={
                        "ip_address": ip,
                        "hostname": hostname,
                        "status": "up"
                    },
                    broadcast=True
                )
                
                # Send to UI
                self.send_entity_card(host_entity)
                
                # Broadcast discovery event
                self.broadcast_event(GraphEvent(
                    event_type=GraphEventType.DATA_DISCOVERED,
                    data={
                        "type": "host",
                        "ip": ip,
                        "hostname": hostname
                    }
                ))
                
                yield f"  [✓] {ip}"
                if hostname:
                    yield f" ({hostname})"
                yield "\n"
                
                # Port scan
                yield f"    Scanning ports...\n"
                
                for port_info in scanner.scan_host(ip, port_list):
                    port_num = port_info["port"]
                    
                    # Create port entity
                    port_entity = self.create_entity(
                        entity_id=f"{host_entity.id}_port_{port_num}",
                        entity_type="network_port",
                        labels=["Port"],
                        properties={
                            "port_number": port_num,
                            "state": "open",
                            "service": port_info["service"]
                        },
                        broadcast=True
                    )
                    
                    # Link to host
                    self.link_entities(
                        host_entity.id,
                        port_entity.id,
                        "HAS_PORT",
                        broadcast=True
                    )
                    
                    all_ports.append({
                        "ip": ip,
                        "port": port_num,
                        "service": port_info["service"]
                    })
                    
                    yield f"      [{port_num}] {port_info['service']}\n"
            
            # Update progress
            self.send_progress(idx, len(targets), f"Scanned {idx}/{len(targets)}")
        
        # Final summary table
        if all_ports:
            self.send_table(
                headers=["IP", "Port", "Service"],
                rows=[[p["ip"], p["port"], p["service"]] for p in all_ports],
                title="Scan Results"
            )
        
        # Final metrics
        self.send_metrics({
            "target": target,
            "live_hosts": len(live_hosts),
            "open_ports": len(all_ports),
            "status": "completed"
        })
        
        yield f"\n╔═══════════════════════════════════════════════════════════╗\n"
        yield f"  Live Hosts: {len(live_hosts)}\n"
        yield f"  Open Ports: {len(all_ports)}\n"
        yield f"╚═══════════════════════════════════════════════════════════╝\n"
        
        yield ToolResult(
            success=True,
            output={
                "live_hosts": live_hosts,
                "open_ports": all_ports
            },
            output_type=OutputType.JSON,
            metadata={
                "hosts_found": len(live_hosts),
                "ports_found": len(all_ports)
            }
        )


class DockerIntentTool(IntentTool):
    """Docker container management tool."""
    
    intents = ["enumerate_containers", "list_containers"]
    cost = 1
    risk = 1
    
    def get_input_schema(self):
        from pydantic import BaseModel
        class DockerInput(BaseModel):
            pass
        return DockerInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self) -> Iterator:
        """List Docker containers."""
        import subprocess
        
        yield "Listing Docker containers...\n"
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.ID}} {{.Image}} {{.Status}}"],
                capture_output=True,
                text=True
            )
            
            containers = []
            for line in result.stdout.strip().splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) >= 2:
                    container_id, image = parts[0], parts[1]
                    status = parts[2] if len(parts) > 2 else "unknown"
                    
                    # Create entity
                    entity = self.create_entity(
                        entity_id=f"container_{container_id}",
                        entity_type="container",
                        labels=["Container"],
                        properties={
                            "container_id": container_id,
                            "image": image,
                            "status": status
                        },
                        broadcast=True
                    )
                    
                    containers.append({
                        "id": container_id,
                        "image": image,
                        "status": status
                    })
                    
                    yield f"  [✓] {container_id[:12]} - {image}\n"
            
            yield f"\nFound {len(containers)} containers\n"
            
            yield ToolResult(
                success=True,
                output=containers,
                output_type=OutputType.JSON
            )
        
        except Exception as e:
            yield f"Error: {e}\n"
            yield ToolResult(
                success=False,
                output=[],
                output_type=OutputType.JSON,
                error=str(e)
            )


class DockerRemoveIntentTool(IntentTool):
    """Remove Docker containers."""
    
    intents = ["remove_container", "delete_container"]
    cost = 5
    risk = 7
    requires_approval = True
    
    def get_input_schema(self):
        from pydantic import BaseModel, Field
        
        class DockerRmInput(BaseModel):
            container: str = Field(description="Container ID or {{vars.primary_container}}")
        
        return DockerRmInput
    
    def get_output_type(self):
        return OutputType.TEXT
    
    def _execute(self, container: str) -> Iterator:
        """Remove container."""
        import subprocess
        
        yield f"Removing container {container}...\n"
        
        try:
            result = subprocess.run(
                ["docker", "rm", "-f", container],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                yield f"[✓] Container {container} removed\n"
                
                yield ToolResult(
                    success=True,
                    output=f"Removed {container}",
                    output_type=OutputType.TEXT
                )
            else:
                yield f"[✗] Failed: {result.stderr}\n"
                
                yield ToolResult(
                    success=False,
                    output="",
                    output_type=OutputType.TEXT,
                    error=result.stderr
                )
        
        except Exception as e:
            yield f"Error: {e}\n"
            yield ToolResult(
                success=False,
                output="",
                output_type=OutputType.TEXT,
                error=str(e)
            )

# =============================================================================
# LLM INTEGRATION
# =============================================================================

def llm_generate_intent_plan(
    objective: str,
    domains: Dict[str, ToolDomain],
    llm_callable: Optional[callable] = None
) -> IntentPlan:
    """
    Generate intent plan using LLM.
    
    Args:
        objective: User's goal
        domains: Available capability domains
        llm_callable: Optional LLM function (uses agent's LLM if not provided)
    
    Returns:
        IntentPlan
    """
    
    # Build prompt
    domain_desc = "\n".join([
        f"- {name}: {domain.description}\n  Intents: {', '.join(domain.intents.keys())}"
        for name, domain in domains.items()
    ])
    
    prompt = f"""You are an infrastructure planning agent.

Goal: {objective}

Available capability domains:
{domain_desc}

Return a JSON intent plan with these steps. Use only the intents listed above.
Do not reference specific tools - only use intents.

Format:
{{
  "steps": [
    {{"intent": "intent_name", "params": {{}}}},
    ...
  ]
}}
"""
    
    if llm_callable:
        response = llm_callable(prompt)
    else:
        # Stub: return demo plan
        return IntentPlan(steps=[
            IntentStep("enumerate_containers"),
            IntentStep("remove_container", params={"container": "{{vars.primary_container}}"}),
        ], metadata={"objective": objective})
    
    # Parse LLM response
    try:
        plan_data = json.loads(response)
        steps = [
            IntentStep(
                intent=s["intent"],
                params=s.get("params", {}),
                constraints=s.get("constraints", {})
            )
            for s in plan_data["steps"]
        ]
        
        return IntentPlan(steps=steps, metadata={"objective": objective})
    
    except Exception as e:
        print(f"[Warning] Failed to parse LLM response: {e}")
        return IntentPlan(steps=[], metadata={"objective": objective})

# =============================================================================
# INTEGRATION WITH VERA
# =============================================================================

def integrate_intent_executor(vera_instance):
    """
    Integrate intent executor with Vera.
    
    Add to Vera.__init__:
        from intent_executor_integration import integrate_intent_executor
        integrate_intent_executor(self)
    """
    
    # Create intent registry
    if not hasattr(vera_instance, 'intent_registry'):
        vera_instance.intent_registry = IntentRegistry()
    
    # Create intent executor
    if not hasattr(vera_instance, 'intent_executor'):
        vera_instance.intent_executor = IntentExecutor(
            vera_instance,
            vera_instance.intent_registry,
            cost_limit=100,
            risk_limit=50
        )
    
    # Register intent tools
    intent_tools = [
        NetworkScanIntentTool(vera_instance),
        DockerIntentTool(vera_instance),
        DockerRemoveIntentTool(vera_instance),
    ]
    
    for tool in intent_tools:
        vera_instance.intent_registry.register(tool)
    
    print(f"[IntentExecutor] Registered {len(intent_tools)} intent tools")
    print(f"[IntentExecutor] Available intents: {set(i for t in intent_tools for i in t.intents)}")
    
    # Add intent planning method to Vera
    def plan_and_execute(objective: str) -> Iterator:
        """
        High-level method: LLM plans, system executes.
        
        Usage:
            for output in vera.plan_and_execute("scan my network"):
                print(output)
        """
        # Generate intent plan
        intent_plan = llm_generate_intent_plan(
            objective,
            DOMAIN_REGISTRY,
            llm_callable=getattr(vera_instance, 'llm_generate', None)
        )
        
        # Execute
        yield from vera_instance.intent_executor.run_intent_plan(intent_plan)
    
    vera_instance.plan_and_execute = plan_and_execute
    
    return vera_instance


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def demo_integration():
    """
    Demo of the integrated system.
    
    Shows:
        1. Intent plan generation
        2. Tool binding
        3. Execution with memory/UI/orchestration
        4. Variable suggestion
        5. Learning
    """
    
    # Mock Vera instance
    class MockVera:
        def __init__(self):
            from unittest.mock import MagicMock
            self.mem = MagicMock()
            self.sess = MagicMock(id="demo_session")
            self.event_broadcaster = EventBroadcaster()
            self.orchestrator = None  # Optional
    
    print("=" * 70)
    print("Intent-Based Executor + VTool Framework Integration Demo")
    print("=" * 70)
    print()
    
    # Create Vera instance
    vera = MockVera()
    
    # Integrate intent executor
    integrate_intent_executor(vera)
    
    # Create intent plan (normally from LLM)
    intent_plan = IntentPlan(
        steps=[
            IntentStep("enumerate_containers"),
            IntentStep(
                "remove_container",
                params={"container": "{{vars.primary_container}}"},
                constraints={"suggest_vars": True}
            ),
        ],
        metadata={"objective": "Clean up unused containers"}
    )
    
    print("Intent Plan:")
    for i, step in enumerate(intent_plan.steps, 1):
        print(f"  {i}. {step.intent} {step.params}")
    print()
    
    # Execute
    print("Executing...")
    print()
    
    for output in vera.intent_executor.run_intent_plan(intent_plan):
        if isinstance(output, str):
            print(output, end='')
        elif isinstance(output, ToolResult):
            print(f"\n[Result] Success: {output.success}")
            print(f"[Result] Entities created: {len(output.entities)}")
            print(f"[Result] Relationships created: {len(output.relationships)}")
        elif isinstance(output, UIUpdate):
            print(f"[UI Update] {output.component.component_type}")


if __name__ == "__main__":
    demo_integration()
```

## Key Integration Points

### 1. **IntentTool extends UITool + OrchestratedVTool**
- Gets all VTool features (memory, entities, streaming)
- Gets UI features (real-time updates, graph broadcasting)
- Gets orchestration features (distributed execution)
- Adds intent declaration and learned ranking

### 2. **Intent-First Planning**
```python
# LLM generates plan (fast TTFT - no tools loaded)
intent_plan = llm_generate_intent_plan("scan my network", DOMAIN_REGISTRY)

# System binds intents to tools (lazy loading)
# System executes with full VTool features
for output in vera.plan_and_execute("scan my network"):
    print(output)
```

### 3. **Memory Integration**
```python
# Tools create entities that go into Neo4j
host_entity = self.create_entity(
    entity_id=f"ip_{ip}",
    entity_type="network_host",
    properties={"ip_address": ip},
    broadcast=True  # Real-time UI update
)

# Relationships tracked
self.link_entities(host_id, port_id, "HAS_PORT", broadcast=True)
```

### 4. **UI Broadcasting**
```python
# Tools send real-time updates
self.send_alert("Scanning network", "info")
self.send_progress(5, 10, "Scanned 5/10 hosts")
self.send_entity_card(entity)
self.send_table(headers, rows)
```

### 5. **Distributed Execution** (when orchestrator available)
```python
# Tools can submit work to orchestrator
yield from self.parallel_execute(
    "network.scan_host",
    arg_list=[(ip, ports) for ip in targets]
)
```

## Usage in Vera

```python
# In Vera.__init__:
from intent_executor_integration import integrate_intent_executor
integrate_intent_executor(self)

# Then use it:
for output in vera.plan_and_execute("scan 192.168.1.0/24 and remove unused containers"):
    if isinstance(output, str):
        print(output)  # Stream to user
    elif isinstance(output, UIUpdate):
        send_to_websocket(output)  # Update UI
    elif isinstance(output, ToolResult):
        # Final result with entities in memory
        pass
```

This gives you the best of both worlds: fast intent-based planning with full VTool memory/UI/orchestration features!