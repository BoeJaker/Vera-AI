
# TODO
---
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


# Chatbots:
    Fix Slackbot
    implement multiple input streams specialised to tasks i.e. drop in a news url and vera will research the topic and return a report / be able to converse in detail about it. Or a stream that can schedule events sent to it 


# Proactive Focus:
    Scaffold_project tool that can create the perfect project stub and file structure
    Add Memories, sessions, notebooks and files to the focus board
    https://claude.ai/chat/73835203-021c-4292-8353-b949fc389013
    Human in the loop system - allow vera to ask for permission to complete an action
    per file name tagging in console output - https://claude.ai/chat/dee1a706-c56f-45fb-aa57-54b88c5e21a7
    <!-- Questions & workspace - https://claude.ai/chat/f0f19265-34d2-4a5b-b415-15f9b46785c2 -->

# UI:
    Robot breaks when header is collapsed
    Status bar with current task, agents, progress, load, notifications
    Unify UI output of single tool run vs toolchain tool run
    Add loading graphic to other places
    review current placement in graph
    https://claude.ai/chat/cd2797e2-ee05-494c-9bc6-32e5be9b4ff6

# Analytics:
    visualiser tab - can visualise data
    stats and health into a analytics tab
    Visualiser / backtester
    Implement performance and analytics tracking using logger

# Agents:
    Agents page does not load without going to system panel and reloading
    should be move to the orchestration tab

# Orchestration
    Orchestration api and ui need better integration.
    Infrastructure section needs more control and more proxmox
    Task orchestrator shows as stopped even when running 
        "orchestrator.js:191 [Orchestrator UI] Task tracking appears inactive"
        active tasks are not listed
    System monitor works but could be styled much better
    Running tasks is hard as the json payload input is ambiguous

# Scheduler
    Integrate scheduling agent with orchestrator task system

    Chatting with the scheduling agent is blocking
    Scheduling agent returns "I've processed your request. Check your calendar for any updates." rather than agent output
    Scheduling agent chatbox has a better implementation of "thinking" and chat input to bubble animation.
    But does not clar the chat input after submission.

    Scheduling agent needs dynamic agent building using the new agent system.
    Build in the users current schedule and calendar events?

    Organiser overlays - 
        plot sessions and nodes onto the calendar
        plot scheduled tasks onto the calendar

# Researcher 
    Uses two to three models 1 heavy CPU and 1+ fast GPU/CPU
    databases, html, web archives
    large context thought stream (nemotron3-super) & orchestrator
    fast reasoning agent (qwen3.5:9b) for output
    Plugins ML, MCP etc

# Toolchain (Tool Eecutor)
    log errors as nodes and on the event bus
    Build in MCP
    Fuzzy search context builder
    build in api?
    unified python/js module system
    a way to package modules that adds ui and backend
    unify n8n authentication between ui and tool
    No tool streaming when using th toolchian query
    workflows button disappears - the toolchain tab panel buttons need fixing
    N8N execution not working (toolchain workflows)
    Human in the loop system - allow vera to ask for permission to complete an action
    Chat streaming makes tool menu scroll up
    Unify UI output of single tool run vs toolchain tool run
    Retry Mechanism - https://claude.ai/chat/c4a483f7-093e-4007-9e9a-b4539953fcb3
<!-- tool stream and chat stream output race condition (chatUI)
tool stream and chat stream output one after the other - with long outputs the chat stream may never complete leading to a locked interface (quick fix allow chat input durig streaming) 
toolstream seems to go first with the chat output chasing -->


# Memory:
    integrate cyber qury with memory tab
    <!-- integrate graph settings with memory + quick control from graph -->
    Implement performance and analytics tracking using logger
    Flatten function - simplifies relationships for processing

    Memory.py add edges for inferred relationships, same node links i.e. ip addresses, and allow you to flatten/collapse them into one point with "history" 
    REL = Direct session relationship
    INF_REL = inferred relationship
    ENT_REL = Entites are tied across sessions i.e. ip address, ideas, 
    parsers / extracters bash/code/text to turn output into entities

    Temporal edges that decay over time - records context probe hits
    Agent graphs - allow agents to build shortcuts between nodes or entire networks of edges that tie together concepts in memory in order to help achieve a goal

# Database:
    Stores redis event bus (all events) - some are elevated to neo4j

# Graph
    Move Context Graph to Graph Panel
    Graph view modes, context, discovery, entities & relationships, hybrid
    better graph styling
    build in force directed from the click menu
    broadcast session graph updates to the event bus
        Live Graph - Graph that updates live - continuously rescans/reanalyses nodes
    auto focus graph canvas on last node after chat response
    graph ui has a bit of vertical overflow - the same hight as the top toolbar

    unified graph styling from query to context menu - 
    still needs some improvement
    query should slide ito the graph element not the window
    Settings needs to be removed

# Context probe
    search modules
    search orchestrator can expand search as needed
    better controls
probe takes  vectors matching quesry and gets nearby graph objects

probe takes duplicate vectors and discards


# Context builder
    better controls
    agent feedback/control


# Skills
    skills are MD files that can augment capabilities of a model.
    Skills can be written by the user or generated by the skill builder.
    skills can be fuzzy searched at runtime
    Skills can be made uttlising "agent graphs" - see Memory section

# Capabilities
    a combination of Skills, Tools, Pipelines and Tasks,
    Can be Fuzzy searched 
    Worker/ Agent / Task / Tool / Plugin Framework
    Define the architecture of the framework its componnts & how it all fits together

# Event Bus
    Remove usage of websockets where possible and replace with redis event bus submissions
    Broadcast session graph updates to the event bus
    Logging integration with event bus allows vera to search for errors
    "World View" page for event bus
        Add a redis / pubsub page - with some kind of push system?
    Daily info packet  for vera.

# World View:
    Docker data broker stack - https://claude.ai/chat/ccb76b88-a76e-4d91-9837-acd5019856d9
    
# Chat
    initial error "Connection failed. Running in offline mode."
    llm.fast should prohibit thought
    preamble should prohibit thought

    New button "send to graph/extract entities" like send to canvas  - turns the text/code/json into a graph
    file:///X:/Programming/Machine%20Learning/knowledge-graph.html
    file:///X:/Programming/Machine%20Learning/code-graph.html

    chatui triage, focus mode changes but input is not processed by agent
    focus changed to is blank

    Model selector in routing doesnt load 1 fast enough 2 at all, needs a reload button or empty/retry loop

# Chat History
    Fix chat History session loading
    Chat history takes ages to load and reloads on tab switch

    session history
    https://claude.ai/chat/dafcc308-907f-4fff-98cc-ce2ec1d35681

# Canvas
    Canvas to be able to load all code in the graph - same with notes and visualisations
    Canvas Execution backend integration
    https://claude.ai/chat/858411bf-05aa-4493-80be-117a00dc658d

# Notebook
    Notebook (obsidian) integration

# Ollama multi instance mananger
    Make it a modular pipeline with a plugin & api interface
    Ollama Manager, Each model needs more information in the UI - 
    move UI into "Orchestration" tab
    Instance profiles for tasks i.e. research is CPU nemotron3 + GPU qwen3.5

# Error Warden
    Agent to insepct errors on the eventbus and provide useful feedback

# Podcast Generation

# Whisper worker handling

# Websearch
    websearch container (docker)
    search cache that indexes the most relevant and useful pages

# Deep Search
    web archive  search
    database search
    api explore

# Project Assistant
    https://claude.ai/chat/1e3b5fff-f573-4813-8340-c38d46144c84

could we integrate an ML plugin system that can augment / insert in / replace the current flow.  i would like something that constantly tries to improve context of whatever input is buffered into the system. ideally the system should be able to be used like a tool so the llm can query its own memory with the plugins
builder uses a stack dictated by relevance items stay in context whilst they are the most rel


thats not quite right, the frames are currently being generated as text is input into chat box. Also its sending partial queries as i type, maybe a slightly longer timeout is required? really if a portion of a statement is sent off and a user continues typing the result of the previous query should be discarded not rendered to the UI.

I need to be able to see what in the graph is in context for the LLM and what is out-of-context.



It needs better dampening on the graph as if a highly connected cluster is loaded it snaps about as nodes load in, its not smooth at all.



