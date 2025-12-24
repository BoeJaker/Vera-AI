performance issues, graph-info-card / rcm context menus

ability to restrict graph view to current session only / switch to current view + context
Color legend doesnt always show

unified graph loading system - 
graphs loaded via query have the wrong edge tags, 
graphs loaded using the memory tab lack porperties,
graphs loaded using chat event handlers work great
none load in with correct styling, need a master style control combined with style.js

unified graph styling from query to context menu

query should slide ito the graph element not the window

settings should be moved to the query window

add a button - layout - that opens the query slider on layout

FOLDER:
GRAPH_


Memory.py add edges for inferred relationships, same node links i.e. ip addresses, and allow you to flatten/collapse them into one point with "history" 
REL = Direct session relationship
INF_REL = inferred relationship
ENT_REL = Entites are tied across sessions i.e. ip address, ideas, 

Memory.py 
Flatten function - simplifies relationships for processing

FILE:
MEMORY

proactive focus - suggest similar focus or ask if you would like to create a new one

💭 Generating proactive thought... bubbles need to format the json output into "thoughts"

Add controls for complexity of thought, number of iterations, 

Finish proactive background thought - improve scaling - docker

"Error streaming ideas response: 'run_manager'" in Actions & Next Steps

Actions stage must deconstruct next steps into toolplans using the toolchain planner and action prompt
Should optionally be able to prompt the user before each action

PFB Orchestrator agent that ensrues each stages output makes sense - manages marco progress toward the focus

FILES:

PROACTIVE_FOCUS_MANAGER


Fix thought streaming to UI - it works when proactive focus is triggered by vera, but in no other case.

Dual output of thought to terminal. streamed chars output are appended with newline :(

FILES:
VERA, OLLAMA_MANAGER


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