## Toolchain execution environments:
Linear Toolchain
Expert Toolchain
Bash
Python

## Domain experts
Bash
Python
osint


## Toolchain workflows:
Save and replay toolchain workflows

Toolchain workflow environments:
n8n
cron
internal
Allows federated integration of various automation platforms

## Access Planes & components:

Orchestrator - can delegate tasks to workers

MCP - serves and recieves MCP 

UI Elements - capable of handing ui elements to the UI

Output Streaming - streams the output of tools in realtime
  
## Flow              
Chat Triage -> 
Toolchain Triage (Constructs specialists, intent based planning) ->  
Toolchain Planner (Plans a toolchain given a subset of tool experts and tools) ->  
Toolchain Expert (plans tool input given prior context) -> 
Toolchain Executor (Executes plans using toolchains)

## Expert Toolchain Query Deconstruction Flow
Layer 1
Classifier

Layer 2
Agent Orchestrator

Layer 3
Specialist Agents

