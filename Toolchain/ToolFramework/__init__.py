# """
# Vera Enhanced Tool Framework
# ==============================
# Drop-in compatible framework for building rich, categorized, service-capable tools
# with optional UI injection, event bus integration, memory/graph access,
# orchestrator routing, and streaming output.

# Backwards compatible with existing LangChain Tool / StructuredTool usage.

# Modules:
#     - core: Base classes, decorators, enums, capability model
#     - registry: Central tool registry with dynamic filtering
#     - services: Background service manager for long-running tools
#     - ui: UI descriptor system for tool-associated frontend elements
#     - events: EventBus stubs and integration points
#     - loader: Drop-in replacement for ToolLoader with full backwards compat
# """

# from Vera.Toolchain.tool_framework.core import (
#     ToolCapability,
#     ToolCategory,
#     ToolMode,
#     ToolUIType,
#     ToolDescriptor,
#     ToolContext,
#     enhanced_tool,
#     service_tool,
#     ui_tool,
#     sensor_tool,
# )

# from Vera.Toolchain.tool_framework.registry import ToolRegistry, global_registry

# from Vera.Toolchain.tool_framework.services import (
#     ServiceManager,
#     ServiceState,
#     ServiceHandle,
# )

# from Vera.Toolchain.tool_framework.ui import (
#     UIDescriptor,
#     UIComponentType,
#     build_console_ui,
#     build_schema_ui,
#     build_monitor_ui,
# )

# from Vera.Toolchain.tool_framework.events import (
#     ToolEventBus,
#     ToolEvent,
#     EventType,
# )

# from Vera.Toolchain.tool_framework.loader import EnhancedToolLoader

# __all__ = [
#     # Core
#     "ToolCapability", "ToolCategory", "ToolMode", "ToolUIType",
#     "ToolDescriptor", "ToolContext",
#     "enhanced_tool", "service_tool", "ui_tool", "sensor_tool",
#     # Registry
#     "ToolRegistry", "global_registry",
#     # Services
#     "ServiceManager", "ServiceState", "ServiceHandle",
#     # UI
#     "UIDescriptor", "UIComponentType",
#     "build_console_ui", "build_schema_ui", "build_monitor_ui",
#     # Events
#     "ToolEventBus", "ToolEvent", "EventType",
#     # Loader
#     "EnhancedToolLoader",
# ]