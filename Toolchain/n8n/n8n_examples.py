#!/usr/bin/env python3
"""
Example integration of n8n with Vera's toolchain system
Shows how to set up and use the n8n integration
"""

import os
import sys
from typing import Dict, List

# Example 1: Basic setup
def setup_n8n_integration():
    """
    Setup n8n integration with Vera
    
    Prerequisites:
    1. n8n running locally or remotely (default: http://localhost:5678)
    2. n8n API key (if using authentication)
    3. Environment variables set:
       - N8N_URL (optional, default: http://localhost:5678)
       - N8N_API_KEY (optional, if using auth)
    """
    
    # Set environment variables
    os.environ["N8N_URL"] = "http://localhost:5678"
    os.environ["N8N_API_KEY"] = "your-api-key-here"  # Optional
    
    # Import Vera (your existing code)
    # from Vera import Vera
    
    # Initialize Vera with n8n integration
    # vera = Vera()
    
    # Enable n8n in toolchain
    # from enhanced_toolchain_n8n import add_n8n_commands
    # add_n8n_commands(vera)
    
    print("n8n integration enabled!")
    print("You can now:")
    print("1. Export toolchains to n8n for visual editing")
    print("2. Execute toolchains using n8n's workflow engine")
    print("3. Import edited workflows back to Vera")


# Example 2: Export a toolchain to n8n
def example_export_to_n8n():
    """
    Example: Creating a toolchain and exporting it to n8n
    """
    from n8n_toolchain_integration import N8nToolchainBridge
    
    # Create a sample toolchain
    toolchain = [
        {
            "tool": "web_search",
            "input": "latest AI news"
        },
        {
            "tool": "summarize",
            "input": "{prev}"  # Uses output from previous step
        },
        {
            "tool": "send_email",
            "input": "Summary: {step_2}"  # References specific step
        }
    ]
    
    # Initialize bridge
    bridge = N8nToolchainBridge()
    
    # Export to n8n
    workflow_id = bridge.export_toolchain_to_n8n(
        toolchain,
        workflow_name="AI_News_Digest"
    )
    
    print(f"Exported to n8n!")
    print(f"Workflow ID: {workflow_id}")
    print(f"Edit at: http://localhost:5678/workflow/{workflow_id}")
    
    return workflow_id


# Example 3: Edit in n8n and re-import
def example_edit_and_reimport(workflow_id: str):
    """
    Example: Editing a workflow in n8n and importing it back
    
    Steps:
    1. Export toolchain to n8n
    2. Edit visually in n8n web interface
    3. Import the edited workflow back
    4. Execute with Vera
    """
    from n8n_toolchain_integration import N8nToolchainBridge
    
    bridge = N8nToolchainBridge()
    
    # Get the edited workflow from n8n
    workflow = bridge.get_workflow(workflow_id)
    print(f"Retrieved workflow: {workflow['name']}")
    
    # Convert back to toolchain format
    toolchain = bridge.n8n_workflow_to_toolchain(workflow)
    
    print("Converted to toolchain:")
    for i, step in enumerate(toolchain, 1):
        print(f"  Step {i}: {step['tool']} - {step['input']}")
    
    # Now you can execute this with Vera
    # vera.toolchain.execute_tool_chain("Run edited workflow", plan=toolchain)
    
    return toolchain


# Example 4: Execute via n8n
def example_execute_via_n8n():
    """
    Example: Execute a toolchain using n8n's execution engine
    """
    
    # This would be integrated into Vera's command loop
    # In your main loop, you could add:
    
    """
    if user_query.lower() == "/n8n-execute":
        # Execute last plan via n8n
        with open("./Configuration/last_tool_plan.json", "r") as f:
            last_plan = json.load(f)
        
        for chunk in vera.toolchain.execute_tool_chain(
            "Execute via n8n",
            plan=last_plan,
            use_n8n=True  # This flag triggers n8n execution
        ):
            print(chunk)
    """
    pass


# Example 5: Advanced - Custom n8n nodes for Vera tools
def create_custom_n8n_nodes():
    """
    For advanced integration, you can create custom n8n nodes for Vera tools
    
    This would involve:
    1. Creating n8n node packages for your most-used tools
    2. Registering them in n8n
    3. Using them in workflows
    
    Example custom node structure (conceptual):
    """
    
    custom_node_example = {
        "node": "n8n-nodes-vera.veraWebSearch",
        "displayName": "Vera Web Search",
        "description": "Search the web using Vera's search tool",
        "properties": [
            {
                "displayName": "Query",
                "name": "query",
                "type": "string",
                "default": ""
            }
        ],
        "execute": "async function execute(this: IExecuteFunctions) { ... }"
    }
    
    print("Custom nodes allow richer n8n integration")
    print("See n8n documentation for creating custom nodes")


# Example 6: Bidirectional sync
def example_bidirectional_workflow():
    """
    Example: Keep workflows in sync between Vera and n8n
    """
    from n8n_toolchain_integration import N8nToolchainBridge
    
    bridge = N8nToolchainBridge()
    
    # Strategy 1: Export all plans to n8n for archival
    def archive_all_plans():
        # Read all plan files
        import glob
        for plan_file in glob.glob("./Configuration/plans/*.json"):
            with open(plan_file, "r") as f:
                plan = json.load(f)
            
            workflow_id = bridge.export_toolchain_to_n8n(
                plan,
                workflow_name=f"Archived_{os.path.basename(plan_file)}"
            )
            print(f"Archived {plan_file} as workflow {workflow_id}")
    
    # Strategy 2: Pull updates from n8n periodically
    def sync_from_n8n():
        workflows = bridge.list_workflows(tags=["vera-toolchain"])
        
        for workflow in workflows:
            workflow_id = workflow['id']
            toolchain = bridge.import_n8n_workflow_as_toolchain(workflow_id)
            
            # Save locally
            filename = f"./Configuration/plans/from_n8n_{workflow_id}.json"
            with open(filename, "w") as f:
                json.dump(toolchain, f, indent=2)
            
            print(f"Synced workflow {workflow_id} to {filename}")


# Example 7: Command-line interface additions
def enhanced_cli_commands():
    """
    Additional CLI commands for n8n integration
    """
    
    commands = {
        "/n8n-edit": "Open last toolchain in n8n editor",
        "/n8n-list": "List all n8n workflows tagged with 'vera-toolchain'",
        "/n8n-import <id>": "Import workflow from n8n by ID",
        "/n8n-execute": "Execute last plan using n8n engine",
        "/n8n-sync": "Sync all workflows from n8n",
        "/n8n-archive": "Archive all local plans to n8n",
        "/n8n-create <name>": "Create empty workflow in n8n",
        "/n8n-delete <id>": "Delete workflow from n8n"
    }
    
    return commands


# Example 8: Integration in main Vera loop
def integrate_with_vera_main_loop():
    """
    Example of how to integrate n8n commands into Vera's main loop
    """
    
    example_code = """
    # In your Vera.py main loop, add these handlers:
    
    while True:
        user_query = input("\\nEnter your query (or 'exit' to quit):\\n\\n ")
        
        # ... existing commands ...
        
        # n8n commands
        if user_query.lower() == "/n8n-edit":
            url = vera.toolchain.open_in_n8n_editor()
            print(f"Open this URL to edit: {url}")
            continue
        
        elif user_query.lower() == "/n8n-list":
            workflows = vera.toolchain.list_n8n_toolchains()
            for wf in workflows:
                print(f"  {wf['id']}: {wf['name']}")
            continue
        
        elif user_query.lower().startswith("/n8n-import "):
            workflow_id = user_query.split(" ", 1)[1]
            toolchain = vera.toolchain.import_from_n8n(workflow_id)
            print(f"Imported toolchain with {len(toolchain)} steps")
            
            # Save it
            with open("./Configuration/imported_plan.json", "w") as f:
                json.dump(toolchain, f, indent=2)
            continue
        
        elif user_query.lower() == "/n8n-execute":
            with open("./Configuration/last_tool_plan.json", "r") as f:
                plan = json.load(f)
            
            for chunk in vera.toolchain.execute_tool_chain(
                "Execute via n8n",
                plan=plan,
                use_n8n=True
            ):
                print(chunk)
            continue
        
        # ... rest of your existing code ...
    """
    
    print(example_code)


# Example 9: Webhook integration
def example_webhook_integration():
    """
    Example: Using n8n webhooks to trigger Vera toolchains
    """
    
    concept = """
    Advanced integration: n8n → Vera via webhooks
    
    1. Create a webhook in n8n that calls Vera's API
    2. Set up a simple Flask/FastAPI server in Vera:
    
    from flask import Flask, request
    
    app = Flask(__name__)
    
    @app.route('/webhook/toolchain', methods=['POST'])
    def webhook_toolchain():
        data = request.json
        toolchain = data.get('toolchain')
        
        # Execute the toolchain
        result = vera.toolchain.execute_tool_chain(
            "Webhook triggered",
            plan=toolchain
        )
        
        return {'status': 'success', 'result': result}
    
    3. In n8n, create workflows that POST to this endpoint
    4. Now n8n can trigger Vera toolchains on schedules, events, etc.
    """
    
    print(concept)


# Example 10: Error handling and fallback
def example_error_handling():
    """
    Example: Graceful fallback when n8n is unavailable
    """
    
    example = """
    # The EnhancedToolChainPlanner already handles this:
    
    try:
        # Try to execute via n8n
        result = vera.toolchain.execute_tool_chain(
            query,
            plan=plan,
            use_n8n=True
        )
    except Exception as e:
        print(f"n8n execution failed: {e}")
        print("Falling back to local execution...")
        
        # Automatically falls back to local execution
        result = vera.toolchain.execute_tool_chain(
            query,
            plan=plan,
            use_n8n=False
        )
    """
    
    print(example)


if __name__ == "__main__":
    print("=" * 60)
    print("n8n Integration Examples for Vera Toolchain")
    print("=" * 60)
    
    print("\n1. Setup")
    setup_n8n_integration()
    
    print("\n2. Export to n8n")
    # workflow_id = example_export_to_n8n()
    
    print("\n3. Available commands")
    commands = enhanced_cli_commands()
    for cmd, desc in commands.items():
        print(f"  {cmd:30} - {desc}")
    
    print("\n4. See function definitions for more examples")
    print("=" * 60)