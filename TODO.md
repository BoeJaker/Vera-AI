chatui triage, focus mode changes but input is not processed by agent
focus changed to is blank

<!-- performance issues, graph-info-card / rcm context menus -->

<!-- ability to restrict graph view to current session only / switch to current view + context -->
Color legend doesnt always show

unified graph loading system - 
graphs loaded via query have the wrong edge tags, 
graphs loaded using the memory tab lack porperties,
graphs loaded using chat event handlers work great
none load in with correct styling, need a master style control combined with style.js

unified graph styling from query to context menu

query should slide ito the graph element not the window

settings should be moved to the query window

add a button - "layout" - that opens the query slider on layout

FOLDER:
GRAPH_


# Node Properties
Title:          Human readable identifier

ID;             Unique ID
Session_ID:     Unique session ID = contains all nodes from the same session
Cluster:        Unique cluster ID - contains all nodes from the same execution

Node Type:      Node category Entity, Extracted_Entity, Inference, Generated, 
Type:           Fixed data category, IP, 
Label:          User amendable labels
Caller:         Function that created tthe node
Intermediate:   A node that symbolizes an internal or hidden process i.e. "tool execution" - can be "collapsed"
Live:           This node can be live updated

Created at:     Datetime
Updated at:     Datetime

Agent:          Agent used to generate
Model:          Model used to generate
Task:           Generated via task type

Text:           Truncated text (500)
Vector_id:      ID to vector-space        
Vector:         Vector representation

Live:           Boolean - Can the node be live monitored
Color

# Additional Tool Properties
Tool:           Human readable identifier
Toolchain:      Unique Toolchain run ID

# Additional Focus properties
Focus:
Current_Step:


**tools need**
parsers / extracters bash/code/text to turn output into entities

Memory.py add edges for inferred relationships, same node links i.e. ip addresses, and allow you to flatten/collapse them into one point with "history" 
REL = Direct session relationship
INF_REL = inferred relationship
ENT_REL = Entites are tied across sessions i.e. ip address, ideas, 

Memory.py 
Flatten function - simplifies relationships for processing

FILE:
MEMORY

proactive focus manager fix header menu

proactive focus manager - no ideas generating

proactive focus manager - recursion, take an existing entry and improve/expand upon it

proactive focus manager - does not execute actions automatically

proactive focus manager - tool execution ui does not exist, not sure if actions are being executed

proactive focus manager - see upcoming actions/tasks and re-order / edit them 

💭 Generating proactive thought... bubbles need to format the json output into "thoughts"

Add controls for complexity of thought, number of iterations, depth of planning

Finish proactive background thought - improve scaling - docker

"Error streaming ideas response: 'run_manager'" in Actions & Next Steps

After next steps and actions are generated the system falls apart, ideas are not returned to the board and string of errors are logged to the graph

Actions stage must deconstruct next steps into toolplans using the toolchain planner and action prompt
Should optionally be able to prompt the user before each action

PFB Orchestrator agent that ensrues each stages output makes sense - manages marco progress toward the focus

FILES:

PROACTIVE_FOCUS_MANAGER



Human in the loop system - allow vera to ask for permission to complete an action

FILE:
ORCHESTRATOR

Live Graph
Graph that updates live - continuously rescans/reanalyses nodes

Unify UI output of single tool run vs toolchain tool run

tools need to link their output to the current sessions last node in the "execution chain" (plan, step, conclusion) usually step as this is where tools are run.
i.e.
    plan -> step -> network_scan - detected_ip -> detected_service -> known_vulnerability
    branch from step -> next step -> web search -> result
    branch from next step etc

    or

    plan -> step -> network_scan - detected_ip -> detected_service -> known_vulnerability
    branch from step -> next step -> web search -> result
    branch from next step etc

FILES:
TOOLCHAIN & MEMORY & TOOLS & TOOLCHAIN_API


Single tool execution not working for lots of tools

tool stream and chat stream output race condition (chatUI)
tool stream and chat stream output one after the other - with long outputs the chat stream may never complete leading to a locked interface (quick fix allow chat input durig streaming) 
toolstream seems to go first with the chat output chasing

Chat history takes ages to load and reloads on tab switch

Chat streaming makes tool menu scroll up

Knowledge graph tool menu, rag and drop node properties does not work.

auto focus canvas on last node after chat response

graph ui has a bit of vertical scroll - the same hight as the top toolbar

Agents page does not load without going to system panel and reloading


Task orchestrator shows as stopped even when running

active tasks are not listed

running tasks is hard as the json payload input is ambiguous

System monitor works but could be styled much better

Infrastructure section needs more control and more proxmox

Add a redis / pubsub page - with some kind of push system?


Scaffold_project tool that can create the perfect project stub and file structure



Organiser overlays - 
    plot sessions and nodes onto the calendar
    plot scheduled tasks onto the calendar



Implement performance and analytics tracking using logger


Ollama Manager, Each model needs more information



Chatting with the scheduling agent is blocking
Scheduling agent returns "I've processed your request. Check your calendar for any updates." rather than agent output
Scheduling agent chatbox has a better implementation of "thinking" and chat input to bubble animation.
But does not clar the chat input after submission.

Scheduling agent needs dynamic agent building using the new agent system.
Build in the users current schedule and calendar events?

Integrate scheduling agent with task system


Visualiser / backtester


Worker/ Agent / Task / Tool / Plugin Framework
    Define the architecture of the framework its componnts & how it all fits together

Status bar with current task, progress, load, notifications




Add Memories, sessions, notebooks and files to the focus board
https://claude.ai/chat/73835203-021c-4292-8353-b949fc389013

session history
https://claude.ai/chat/dafcc308-907f-4fff-98cc-ce2ec1d35681

Add loading graphic to other places
review current placement in graph
https://claude.ai/chat/cd2797e2-ee05-494c-9bc6-32e5be9b4ff6

Notebook (obsidian) integration

Canvas Execution backend integration
https://claude.ai/chat/858411bf-05aa-4493-80be-117a00dc658d

N8N execution not working (toolchain workflows)

Notebooks not loading

integrate cyber qury with memory tab
integrate graph settings with memory + quick control from graph

Fix chat History session loading

No tool streaming when using th toolchian query

Orchestration api and ui need better integration.

toolchain needs integrating with orchestrator

unify n8n authentication between ui and tool

unified python/js module system
a way to package modules that adds ui and backend

workflows button disappears

Canvas to be able to load all code in the graph - same with notes and visualisations

visualiser tab - can visualise data

stats and health into a analytics tab

daily info packet  for vera.

Robot breaks when header is collapsed

New Chat button & Canvas button, like send to canvas - send to graph - turns the text/code/json into a graph - dont work smoothly
file:///X:/Programming/Machine%20Learning/knowledge-graph.html
file:///X:/Programming/Machine%20Learning/code-graph.html









Graph
 - color code edges
 - color code nodes
 - set tags to any property
 - fix node labels, only one showing
 - enlarge node on hover
 