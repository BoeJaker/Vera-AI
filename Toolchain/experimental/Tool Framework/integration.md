# VTool Framework Integration - Quick Start Guide

**Goal**: Integrate the VTool framework with your existing Vera tools with **MINIMAL code changes**.

**Strategy**: Wrap existing tools, don't rewrite them!

## 📁 Files Provided

1. **tool_framework_adapters.py** - Adapters that wrap your existing code
2. **tool_integration_guide.py** - Detailed migration patterns and examples  
3. **network_scanning_integration_example.py** - Specific examples for network tools
4. **This README** - Quick start guide

## ⚡ 15-Minute Integration

### Step 1: Add the adapter file (2 min)

```bash
# Copy to your Vera project
cp tool_framework_adapters.py Vera/
```

### Step 2: Update your ToolLoader (5 min)

**Before** (your existing code):
```python
# Vera/Toolchain/tools.py

def ToolLoader(agent):
    tool_list = []
    
    from Vera.Toolchain.Tools.OSINT.network_scanning import network_scan
    
    tool_list.append(StructuredTool.from_function(
        func=network_scan,
        name="network_scan"
    ))
    
    return tool_list
```

**After** (with adapters):
```python
# Vera/Toolchain/tools.py

from tool_framework_adapters import MixedToolLoader
from tool_framework import OutputType

def ToolLoader(agent):
    loader = MixedToolLoader(agent)
    
    # Import your existing tools (NO CHANGES)
    from Vera.Toolchain.Tools.OSINT.network_scanning import network_scan
    
    # Just wrap them!
    loader.add_function(
        network_scan,
        output_type=OutputType.JSON
    )
    
    # Get tools (compatible with existing code)
    return loader.get_langchain_tools()
```

### Step 3: Enable backward compatibility (1 min)

```python
# In Vera/vera.py (or wherever your agent is initialized)

from tool_framework_adapters import preserve_existing_behavior

class Vera:
    def __init__(self):
        # ... existing code ...
        
        # Add this ONE line:
        preserve_existing_behavior(self)
```

### Step 4: Test (5 min)

```python
# Test that existing tools still work
python -c "from Vera import Vera; v = Vera(); print(v.tools)"
```

**Done!** Your tools now work with the VTool framework.

## 🔧 Common Integration Patterns

### Pattern 1: Function-based tool

**Your existing code:**
```python
def scan_network(target: str, ports: str = "1-1000") -> str:
    # Your scanning logic
    return json.dumps(results)
```

**Integration:**
```python
loader.add_function(
    scan_network,
    output_type=OutputType.JSON
)
```

### Pattern 2: Class-based tool

**Your existing code:**
```python
class NetworkScanner:
    def __init__(self, agent):
        self.agent = agent
    
    def scan(self, target: str):
        # Your scanning logic
        return results
```

**Integration:**
```python
loader.add_class(
    NetworkScanner,
    execute_method="scan",
    output_type=OutputType.JSON
)
```

### Pattern 3: Tool that creates entities

**Your existing code:**
```python
class HostDiscovery:
    def __init__(self, agent):
        self.mem = agent.mem
        self.discovered = []
    
    def discover(self, network: str):
        for host in scan(network):
            # Already creates entities!
            entity_id = self.mem.upsert_entity(...)
            self.discovered.append(entity_id)
        return self.discovered
```

**Integration:**
```python
loader.add_memory_aware_class(
    HostDiscovery,
    execute_method="discover",
    entity_extractor=lambda instance, result: [
        {"id": entity_id, "type": "network_host"}
        for entity_id in instance.discovered
    ]
)
```

## 🎯 What You Get

With these minimal changes, your existing tools now have:

✅ **Automatic execution tracking** - All executions tracked in Neo4j  
✅ **Entity linking** - Entities automatically linked to executions  
✅ **Standardized interface** - All tools work the same way  
✅ **Error handling** - Consistent error reporting  
✅ **LangChain compatibility** - Works with existing LangChain code  
✅ **Gradual migration path** - Add features tool-by-tool as needed  

## 📈 Optional Enhancements

Once basic integration is working, you can optionally enhance specific tools:

### Add UI Features

```python
# Instead of wrapping, create enhanced version
from tool_framework import UITool

class EnhancedHostDiscovery(UITool):
    def __init__(self, agent):
        super().__init__(agent)
        # Use old implementation internally
        from Vera.Toolchain.Tools.OSINT.network_scanning import HostDiscovery
        self.old_impl = HostDiscovery(agent)
    
    def _execute(self, network: str):
        # Add UI features
        self.send_alert("Starting scan", "info")
        self.send_progress(0, 100, "Scanning...")
        
        # Call old implementation
        results = self.old_impl.discover(network)
        
        # Add more UI
        self.send_table(headers=["IP"], rows=[[r] for r in results])
        
        yield ToolResult(success=True, output=results)
```

### Add Monitoring

```python
from tool_framework import MonitoringTool

class HostMonitor(MonitoringTool):
    def get_monitor_type(self):
        return "host_availability"
    
    async def check_entity(self, entity_id: str, config: dict):
        # Check if host is still up
        ip = config["ip_address"]
        alive = ping(ip)
        
        return {
            "status": "up" if alive else "down",
            "timestamp": datetime.now().isoformat()
        }
```

## 🔍 Analyze Existing Tools

Not sure how to integrate a specific tool? Analyze it:

```python
from tool_framework_adapters import analyze_existing_tool

analysis = analyze_existing_tool(my_tool)
print(analysis["recommendation"])
print(analysis["adapter_code"])
# Outputs ready-to-use wrapper code!
```

## 📚 Documentation

For complete documentation, see:

1. **tool_framework_adapters.py** - All adapter classes and utilities
2. **tool_integration_guide.py** - Detailed patterns and examples
3. **network_scanning_integration_example.py** - Network tool examples
4. **Original framework docs** (documents provided earlier) - Full VTool reference

## 🐛 Troubleshooting

### "Tool doesn't work after wrapping"

Check:
- `execute_method` name matches your actual method
- Your tool's `__init__` takes an `agent` parameter
- Input parameters match method signature

### "Entities not being tracked"

Use `MemoryAwareAdapter` and implement `extract_created_entities()`:

```python
class MyToolVTool(MemoryAwareAdapter):
    wrapped_class = MyTool
    
    def extract_created_entities(self, instance, result):
        return [
            {"id": e, "type": "entity_type"}
            for e in instance.created_entities
        ]
```

### "Import errors"

Make sure you have:
```python
# In Vera/__init__.py or appropriate location
from tool_framework import VTool, UITool, OutputType
from tool_framework_adapters import MixedToolLoader
```

## 🎓 Migration Phases

### Phase 1: Quick Wrap (Day 1)
✅ Add adapter files  
✅ Wrap all existing tools  
✅ Verify they still work  

### Phase 2: Add Tracking (Week 1)  
✅ Enable entity tracking  
✅ Add execution linking  
✅ Verify graph structure  

### Phase 3: Enhance Tools (As needed)
✅ Add UI to important tools  
✅ Add monitoring where useful  
✅ Keep old versions working  

### Phase 4: Full Migration (Later)
✅ Replace old implementations  
✅ Pure VTool everywhere  
✅ Remove adapters  

## 💡 Key Benefits

1. **No rewrites needed** - Wrap existing code as-is
2. **Gradual migration** - Enhance tools one at a time  
3. **Backward compatible** - Old code keeps working
4. **Immediate benefits** - Get tracking and structure now
5. **Future-proof** - Path to full framework features

## 📞 Quick Reference

```python
# Wrap function
loader.add_function(my_func, output_type=OutputType.JSON)

# Wrap class
loader.add_class(MyClass, execute_method="run")

# Wrap memory-aware class
loader.add_memory_aware_class(
    MyClass,
    execute_method="scan",
    entity_extractor=lambda inst, res: [...]
)

# Add VTool
loader.add_vtool(MyVTool)

# Add LangChain tool
loader.add_langchain(existing_langchain_tool)

# Get tools
tools = loader.get_langchain_tools()  # For LangChain
# or
tools = loader.get_tools()  # As VTool instances
```

## 🚀 Next Steps

1. Copy adapter files to your Vera project
2. Update ToolLoader to use MixedToolLoader
3. Add preserve_existing_behavior() to agent
4. Test that tools still work
5. Gradually enhance specific tools as needed

**That's it!** Your tools are now integrated with the VTool framework.

---

## Example: Complete ToolLoader Integration

Here's a complete example showing old and new side-by-side:

```python
# BEFORE
def ToolLoader(agent):
    tool_list = []
    
    from Vera.Toolchain.Tools.OSINT.network_scanning import (
        network_scan,
        port_scan,
        service_detect,
        NetworkMapper
    )
    
    tool_list.append(StructuredTool.from_function(func=network_scan, name="network_scan"))
    tool_list.append(StructuredTool.from_function(func=port_scan, name="port_scan"))
    
    mapper = NetworkMapper(agent)
    tool_list.append(StructuredTool.from_function(func=mapper.scan_network, name="mapper"))
    
    return tool_list


# AFTER (with minimal changes)
from tool_framework_adapters import MixedToolLoader
from tool_framework import OutputType

def ToolLoader(agent):
    loader = MixedToolLoader(agent)
    
    # Same imports - no changes!
    from Vera.Toolchain.Tools.OSINT.network_scanning import (
        network_scan,
        port_scan,
        service_detect,
        NetworkMapper
    )
    
    # Wrap functions
    loader.add_function(network_scan, output_type=OutputType.JSON)
    loader.add_function(port_scan, output_type=OutputType.JSON)
    loader.add_function(service_detect, output_type=OutputType.JSON)
    
    # Wrap class
    loader.add_memory_aware_class(
        NetworkMapper,
        execute_method="scan_network",
        entity_extractor=lambda inst, res: [
            {"id": node_id, "type": "network_entity"}
            for node_id in inst.discovered_nodes
        ]
    )
    
    # Get compatible tool list
    return loader.get_langchain_tools()
```

**Result**: Same functionality, now with:
- ✅ Execution tracking
- ✅ Entity linking  
- ✅ Standardized interface
- ✅ Error handling
- ✅ Ready for UI enhancements

Total time: **15 minutes** ⏱️