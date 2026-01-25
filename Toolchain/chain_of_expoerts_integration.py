"""
Enhanced Toolchain Integration for Vera
========================================

Provides both standard and expert toolchain modes:
- Standard: Original ToolChainPlanner (fast, simple)
- Expert: Three-stage expert system (intelligent, specialized)

Can switch between modes or use both simultaneously.
"""

from typing import Optional, List, Dict, Any
from enum import Enum

# Import both toolchain systems
from Vera.Toolchain.toolchain import ToolChainPlanner
from Vera.Toolchain.toolchain_expert import (
    ExpertToolChainPlanner,
    Domain,
    DomainExpert,
    create_expert_toolchain,
    register_custom_tool,
    register_custom_expert
)


class ToolchainMode(Enum):
    """Toolchain execution mode"""
    STANDARD = "standard"      # Original toolchain
    EXPERT = "expert"          # Expert three-stage system
    HYBRID = "hybrid"          # Try expert first, fallback to standard
    AUTO = "auto"              # Auto-select based on query complexity


class HybridToolchainManager:
    """
    Manages both standard and expert toolchain modes
    
    Features:
    - Mode switching
    - Auto-selection based on complexity
    - Fallback mechanisms
    - Performance tracking
    """
    
    def __init__(self, agent, tools):
        self.agent = agent
        self.tools = tools
        
        # Initialize both toolchains
        self.standard_toolchain = ToolChainPlanner(agent, tools)
        self.expert_toolchain = ExpertToolChainPlanner(agent, tools)
        
        # Default mode
        self.mode = ToolchainMode.AUTO
        
        # Track usage
        self.stats = {
            'standard_uses': 0,
            'expert_uses': 0,
            'auto_selections': {'standard': 0, 'expert': 0},
            'fallbacks': 0
        }
        
        print("[Hybrid Toolchain] Initialized with both standard and expert modes")
    
    def set_mode(self, mode: ToolchainMode):
        """Set toolchain execution mode"""
        self.mode = mode
        print(f"[Hybrid Toolchain] Mode set to: {mode.value}")
    
    def register_tool_domain(self, tool_name: str, domains: List[str], priority: int = 1):
        """Register tool with domain tags (for expert mode)"""
        register_custom_tool(self.expert_toolchain, tool_name, domains, priority)
    
    def register_expert(self, name: str, domain: str, description: str, 
                       model: str = "gemma2", system_prompt: Optional[str] = None):
        """Register custom expert (for expert mode)"""
        register_custom_expert(
            self.expert_toolchain, name, domain, description, model, system_prompt
        )
    
    def _assess_complexity(self, query: str) -> str:
        """
        Assess query complexity to determine appropriate toolchain
        
        Returns: 'simple', 'moderate', 'complex'
        """
        
        # Simple heuristics
        indicators = {
            'complex': [
                'security', 'secure', 'vulnerability', 'penetration',
                'optimize', 'analyze deeply', 'comprehensive',
                'multi-step', 'workflow', 'automation',
                'research and', 'investigate', 'full analysis'
            ],
            'moderate': [
                'create', 'build', 'develop', 'implement',
                'analyze', 'research', 'find', 'search',
                'integrate', 'connect', 'setup'
            ]
        }
        
        query_lower = query.lower()
        
        # Check for complex indicators
        complex_score = sum(1 for term in indicators['complex'] if term in query_lower)
        moderate_score = sum(1 for term in indicators['moderate'] if term in query_lower)
        
        # Length also matters
        word_count = len(query.split())
        
        if complex_score >= 2 or word_count > 50:
            return 'complex'
        elif moderate_score >= 1 or word_count > 20:
            return 'moderate'
        else:
            return 'simple'
    
    def _select_mode_auto(self, query: str) -> ToolchainMode:
        """
        Automatically select appropriate mode based on query
        
        Logic:
        - Simple queries → Standard (faster)
        - Moderate queries → Expert (better quality)
        - Complex queries → Expert (required)
        """
        
        complexity = self._assess_complexity(query)
        
        if complexity == 'simple':
            selected = ToolchainMode.STANDARD
            self.stats['auto_selections']['standard'] += 1
        else:
            selected = ToolchainMode.EXPERT
            self.stats['auto_selections']['expert'] += 1
        
        print(f"[Auto-Select] Complexity: {complexity} → Mode: {selected.value}")
        
        return selected
    
    def execute_tool_chain(self, query: str, plan=None):
        """
        Execute toolchain using configured mode
        
        Modes:
        - STANDARD: Use original toolchain
        - EXPERT: Use expert three-stage system
        - HYBRID: Try expert, fallback to standard if fails
        - AUTO: Auto-select based on complexity
        """
        
        # Determine execution mode
        if self.mode == ToolchainMode.AUTO:
            exec_mode = self._select_mode_auto(query)
        else:
            exec_mode = self.mode
        
        # Execute based on mode
        try:
            if exec_mode == ToolchainMode.STANDARD:
                print("\n[Hybrid Toolchain] Using STANDARD mode")
                self.stats['standard_uses'] += 1
                
                for chunk in self.standard_toolchain.execute_tool_chain(query, plan):
                    yield chunk
            
            elif exec_mode == ToolchainMode.EXPERT:
                print("\n[Hybrid Toolchain] Using EXPERT mode")
                self.stats['expert_uses'] += 1
                
                for chunk in self.expert_toolchain.execute_tool_chain(query, plan):
                    yield chunk
            
            elif exec_mode == ToolchainMode.HYBRID:
                print("\n[Hybrid Toolchain] Using HYBRID mode (expert with fallback)")
                
                try:
                    self.stats['expert_uses'] += 1
                    
                    for chunk in self.expert_toolchain.execute_tool_chain(query, plan):
                        yield chunk
                
                except Exception as e:
                    print(f"\n[Hybrid Toolchain] Expert mode failed: {e}")
                    print("[Hybrid Toolchain] Falling back to STANDARD mode")
                    
                    self.stats['fallbacks'] += 1
                    
                    for chunk in self.standard_toolchain.execute_tool_chain(query, plan):
                        yield chunk
        
        except Exception as e:
            error_msg = f"\n[Hybrid Toolchain Error] {str(e)}\n"
            print(error_msg)
            yield error_msg
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            **self.stats,
            'current_mode': self.mode.value,
            'expert_registry': {
                'experts': len(self.expert_toolchain.expert_registry.experts),
                'tagged_tools': len(self.expert_toolchain.tool_registry.tool_domains)
            }
        }
    
    def print_stats(self):
        """Print usage statistics"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("HYBRID TOOLCHAIN STATISTICS")
        print("="*60)
        print(f"Current Mode: {stats['current_mode']}")
        print(f"\nExecution Counts:")
        print(f"  Standard Uses: {stats['standard_uses']}")
        print(f"  Expert Uses: {stats['expert_uses']}")
        print(f"  Fallbacks: {stats['fallbacks']}")
        print(f"\nAuto-Selection:")
        print(f"  → Standard: {stats['auto_selections']['standard']}")
        print(f"  → Expert: {stats['auto_selections']['expert']}")
        print(f"\nExpert System:")
        print(f"  Registered Experts: {stats['expert_registry']['experts']}")
        print(f"  Domain-Tagged Tools: {stats['expert_registry']['tagged_tools']}")
        print("="*60 + "\n")


# ============================================================================
# INTEGRATION FUNCTION FOR VERA
# ============================================================================

def integrate_hybrid_toolchain(vera_instance):
    """
    Integrate hybrid toolchain into Vera instance
    
    Usage in vera.py __init__:
        from Vera.Toolchain.enhanced_toolchain_integration import integrate_hybrid_toolchain
        integrate_hybrid_toolchain(self)
    
    This adds:
        vera.toolchain_hybrid    - HybridToolchainManager instance
        vera.toolchain_expert    - Direct access to expert toolchain
        vera.toolchain_standard  - Direct access to standard toolchain (original)
    
    Original vera.toolchain is preserved for backward compatibility.
    """
    
    print("\n[Integration] Setting up hybrid toolchain system...")
    
    # Create hybrid manager
    hybrid = HybridToolchainManager(vera_instance, vera_instance.tools)
    
    # Add to Vera instance
    vera_instance.toolchain_hybrid = hybrid
    vera_instance.toolchain_expert = hybrid.expert_toolchain
    vera_instance.toolchain_standard = hybrid.standard_toolchain
    
    # Keep original as default (backward compatibility)
    # vera_instance.toolchain already exists from original initialization
    
    print("[Integration] ✓ Hybrid toolchain integrated")
    print(f"[Integration]   - Standard toolchain: vera.toolchain (original)")
    print(f"[Integration]   - Expert toolchain: vera.toolchain_expert")
    print(f"[Integration]   - Hybrid manager: vera.toolchain_hybrid")
    
    return hybrid


# ============================================================================
# EXAMPLE: REGISTERING CUSTOM TOOLS & EXPERTS
# ============================================================================

def register_custom_domains_example(vera_instance):
    """
    Example of registering custom tool domains and experts
    
    Call this after integrate_hybrid_toolchain() to add your custom mappings
    """
    
    if not hasattr(vera_instance, 'toolchain_hybrid'):
        print("[Error] Hybrid toolchain not integrated. Call integrate_hybrid_toolchain() first.")
        return
    
    hybrid = vera_instance.toolchain_hybrid
    
    # Example: Register custom tool domains
    hybrid.register_tool_domain(
        "my_api_tool",
        domains=["api_integration", "backend_development"],
        priority=2
    )
    
    # Example: Register custom expert
    hybrid.register_expert(
        name="API Integration Specialist",
        domain="api_integration",
        description="Expert in RESTful API design, authentication, and integration",
        model="gemma2",
        system_prompt="""You are an API integration specialist.
        Focus on:
        - RESTful design principles
        - Authentication (OAuth, JWT, API keys)
        - Rate limiting and error handling
        - API documentation and testing
        """
    )
    
    print("\n[Custom Domains] Example registrations complete")


# ============================================================================
# CONVENIENCE WRAPPER FOR EASY SWITCHING
# ============================================================================

class ToolchainExecutor:
    """
    Simple wrapper for easy toolchain execution
    
    Usage:
        executor = ToolchainExecutor(vera)
        
        # Use expert mode
        for chunk in executor.run("Analyze security vulnerabilities", mode="expert"):
            print(chunk, end='')
        
        # Use standard mode
        for chunk in executor.run("Simple task", mode="standard"):
            print(chunk, end='')
        
        # Auto-select
        for chunk in executor.run("Some task", mode="auto"):
            print(chunk, end='')
    """
    
    def __init__(self, vera_instance):
        if not hasattr(vera_instance, 'toolchain_hybrid'):
            integrate_hybrid_toolchain(vera_instance)
        
        self.vera = vera_instance
        self.hybrid = vera_instance.toolchain_hybrid
    
    def run(self, query: str, mode: str = "auto", plan=None):
        """
        Execute toolchain with specified mode
        
        Args:
            query: Task to execute
            mode: 'standard', 'expert', 'hybrid', or 'auto'
            plan: Optional pre-made plan
        """
        
        # Set mode
        mode_enum = ToolchainMode(mode.lower())
        self.hybrid.set_mode(mode_enum)
        
        # Execute
        for chunk in self.hybrid.execute_tool_chain(query, plan):
            yield chunk
    
    def stats(self):
        """Print statistics"""
        self.hybrid.print_stats()