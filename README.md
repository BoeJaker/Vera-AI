#python #agentic_ai #llm 

# **Vera:** Une âme sans corps

## A Self-Modifying Multi-Agent Cognitition Architecture with Proactive Background Reflection (SMMAC-PBR)



## What is Vera? 
**A video and audio introduciton**
<!-- 
[![Watch the video](https://img.youtube.com/vi/a3smyPocYZ8/0.jpg)](https://youtu.be/a3smyPocYZ8)   -->

<p align="center">
  <a href="https://img.youtube.com/vi/a3smyPocYZ8/0.jpg"><img src="https://img.youtube.com/vi/a3smyPocYZ8/0.jpg"></a>
</p>

📺 Follow the above linkn to view an 8 minute video giving a basic overview of Vera.  

🎧 [Listen to the Podcast](https://drive.google.com/file/d/1SlxvcZeQEKwKhdWiqwNpCIj9w-nHlBGK/view?usp=sharing) - A 50 minute deep-dive podcast into the architecture of Vera.

<!-- 📖 -->

## Introduction

At its core, **Vera** is an advanced multi-agent AI architecture inspired by principles from cognitive science and agent-based systems. It integrates a framework combining short-term and long-term memory, token prediction, task triage, reasoning, proactive focus management, self-modification, and modular tool execution to deliver flexible, intelligent automation.

Vera **orchestrates multiple large language models** (LLMs) and specialized AI sub-agents synchronously to tackle complex, high-level user requests. It decomposes broad tasks into discrete, manageable steps, then dynamically plans and executes these steps through various external and internal tools to achieve comprehensive outcomes. This distributed agent design enables parallel specialization—some agents focus on rapid query response, others on strategic forward planning—while sharing a unified memory and goal system to maintain coherence across operations.

A hallmark of Vera’s architecture is its capacity for **proactive background processing**. Autonomous sub-agents continuously monitor context and system state, coordinating via dynamic focus prioritization. This allows Vera to orchestrate perceptual inputs, data processing, and environmental interactions adaptively, even without direct user prompts allowing it to enrich its own memories and move progress toward long-term goals forward. The strategic planning layer oversees long-term goals, enabling Vera to anticipate user needs, generate novel insights, and refine internal models on an ongoing basis—resulting in more contextually aware, intelligent, and timely responses.

Vera grounds its intelligence in a highly structured, **multi-layered memory system** (Layers 1-4) that mirrors human cognition by separating volatile context from persistent knowledge. This memory uses a hybrid storage model: the Neo4j Knowledge Graph stores entities and rich, typed relationships, while ChromaDB serves as a vector database for the full text content of documents, notes, and code, binding the textual information to its contextual network. Furthermore, the Macro Buffer mechanism leverages Graph-Accelerated Search to dynamically retrieve relevant knowledge and historical sessions, effectively breaking down isolation between contexts for comprehensive associative recall

Complementing these capabilities is Vera’s integrated program synthesis and self-modification engine. This subsystem empowers Vera to **review, generate, and iteratively improve its own codebase**, extending its functionality autonomously without requiring manual reprogramming. By enabling self-reflection and continuous evolution, Vera maintains adaptability and resilience across rapidly changing task demands and environments.

Together, these components form a flexible, extensible AI platform designed for complex problem solving, adaptive decision making, and seamless interaction across diverse domains.
 
---
## Core Concepts

### 1. Agents vs LLMs vs Encoders in Vera 
**Multi-Level Hierarchy**

Vera’s architecture distinguishes between **LLMs** and **Agents**, each operating at multiple levels of complexity and capability to handle diverse tasks efficiently.

#### Encoders

- Encoders: Extremely light models used to encode memories 

#### Large Language Models (LLMs)

LLMs are the foundational language engines performing natural language understanding and generation. Vera uses several LLMs, each specialized by size, speed, and reasoning ability:
  
- **Fast LLMs:** Smaller, optimized for quick, straightforward responses.
    
- **Intermediate LLMs:** Larger models that balance speed and reasoning capacity.
    
- **Deep LLMs:** Large, resource-intensive models suited for complex reasoning and extended dialogues.
    
- **Specialized Reasoning LLMs:** Models fine-tuned or architected specifically for heavy logical processing and multi-step deduction.
    

Each LLM level provides different trade-offs between speed, resource use, and depth of reasoning. Models can be upgraded in-place meaning when a new model is released it is plug-and-play so to speak. The memories will carry over as if nothing changed.

#### How Levels Interact

- Lower-level LLMs handle quick, direct responses and routine tasks.
    
- Higher-level LLMs monitor overall goals, manage focus, and coordinate lower-level LLMs activities.
    
- LLMs at different levels are selected dynamically depending on task complexity and required depth of reasoning.
    

This multi-level, hierarchical approach allows Vera to balance responsiveness with deep cognitive abilities, making it a flexible and powerful autonomous AI system.

#### Agents

Agents are **LLM instances configured with augmented capabilities**, including memory management, tool integration, task triage, and autonomous goal setting. Vera’s agents also exist at multiple levels:

- **Triage Agents:** Lightweight agents responsible for prioritizing tasks and delegating work among other agents or tools.

- **Tool Agents:** Lightweight agents using fast LLMs to handle immediate simple tool invocations.
    
- **Strategic Agents:** Deep-level agents running large LLMs tasked with long-term planning, proactive reflection, and orchestrating complex tool chains.
    
- **Specialized Agents:** Agents with domain-specific expertise or enhanced reasoning modules, capable of focused tasks like code generation, calendar management, or data analysis.
    
These LLMs & Agents can communicate via shared memory and coordinate through a dynamic 

---

### 2. Central Executive Orchestrator
**Task scheduler & worker orchestrator**

---

### 3. Proactive Background Reflection

Vera maintains a **Focus Manager** that continuously evaluates system priorities, context, and pending goals. During idle moments, it generates **proactive thoughts**—such as reminders, hypotheses, or plans—that enhance its understanding and readiness for future interactions.

This ongoing background reflection helps Vera:

- Detect inconsistencies or gaps in knowledge
    
- Anticipate user needs
    
- Prepare for complex multi-step operations
    
- Improve self-awareness and performance over time
    
---

### 4. Memory Architecture

![Memory UI](images/memory_ui.jpg)
The memory explorer

The Vera agent is powered by a sophisticated, multi-layered memory system designed to mirror human cognition. This architecture separates volatile context from persistent knowledge, enabling both coherent real-time dialogue and deep, relational reasoning over a vast, self-curated knowledge base. The system is built on a core principle: **ChromaDB vectorstores hold the raw textual content, while the Neo4j graph maps the relationships and context between them.**

#### **Architecture Overview**

Vera's memory is structured into four distinct layers, excluding Layer 5 each layer contains all the data from the previous, each serving a specific purpose in the cognitive process:

*   **Layer 1: Short-Term Buffer** - The agent's immediate conversational context.
*   **Layer 2: Working Memory** - Its private scratchpad for a single task, session or memory.
*   **Layer 3: Long-Term Knowledge** - Its persistent, interconnected library of facts and insights.
*   **Layer 4: Archive** - A complete, immutable record of activity.
*   **Layer 5: External Knowledge Bases** - 

A key advanced capability, the **Macro Buffer**, dynamically bridges Layers 2, 3 & 5 to enable unified, cross-sessional, highly enriched reasoning.

#### **Layer 1: Short-Term Context Buffer**

*   **Purpose:** To maintain the immediate context of the active conversation, ensuring smooth and coherent multi-turn dialogue. This is a volatile, rolling window of recent events.
*   **Implementation:** A simple in-memory buffer (e.g., a list of the last 10-20 message exchanges). This data is transient and is not persisted to any database.
*   **Content:** Raw chat history between the user and the agent.

#### **Layer 2: Working Memory (Session Context)**

*   **Purpose:** To provide an isolated "scratchpad" for the agent's internal monologue, observations, and findings during a specific task, problem, or session or recollection. This allows for exploratory thinking.
*   **Implementation:**
    *   **Neo4j (Structure):** A `Session` node is created and linked to relevant entities in the main graph (e.g., `(Session)-[:FOCUSED_ON]->(ProjectX)`).
    *   **ChromaDB (Content):** A dedicated Chroma collection (`session_<id>`) is created to store the **full text** of the agent's thoughts, notes, and relevant snippets generated during this session.
*   **Content:** Agent's "thoughts," observed facts, code snippets, and summarizations. All data is scoped to the session's task.

#### **Layer 3: Long-Term Knowledge**

*   **Purpose:** To serve as the agent's persistent, semantically searchable library of validated knowledge. This is the core of its "intelligence," built over time through a careful process of promotion and curation.
*   **Implementation:**
    Layers 1 and two are continually promoted into Layer 3 before session end
    *   **ChromaDB (Content & Semantic Search):** The primary `long_term_docs` collection stores the **full text** of all important information: documents, code examples, notes, and promoted "thoughts." Each entry contains metadata that points back to the Neo4j graph.
    *   **Neo4j (Context & Relationships):** The graph stores all memories, entities & insights (e.g., `Project`, `Document`, `Person`, `Feature`, `Memory`) and the rich, typed relationships between them (e.g., `USES`, `AUTHORED_BY`, `CONTAINS`). It does not store large text bodies, only pointers to them in Chroma.
*   **How It Works (Basic Retrieval):**
    1.  A semantic query is performed on the `long_term_docs` Chroma collection.
    2.  The search returns the most relevant text passages and their metadata, including a `neo4j_id`.
    3.  This ID is used to fetch the corresponding node and its entire network of relationships from Neo4j.
    4.  The agent receives both the retrieved text *and* its full relational context, enabling deep, multi-hop reasoning.

#### Data Retrieval

*   **How It Works (Advanced Macro Retrieval):** For comprehensive questions, Vera uses a **Graph-Accelerated Search** to power its **Macro Buffer**.
    1.  **Graph-Based Pre-Filtering:** The query is analyzed for key entities. Neo4j finds all `Session` nodes related to these topics.
        **Example Cypher Query:**
        ```cypher
        MATCH (s:Session)-[:FOCUSED_ON|:HAS_TOPIC]->(e)
        WHERE e.name = "Project Phoenix" OR e.name =~ "(?i).*authentication.*"
        RETURN s.session_id
        ```
    2.  **Targeted Vector Search:** The original query is executed semantically, but only against the `long_term_docs` collection and the specific `session_*` collections identified by the graph.
    3.  **Result:** This provides a unified context window from both long-term knowledge and historically relevant sessions, enabling true associative recall.


#### **The Promotion Process: From Thought to Knowledge**

Promotion is the key mechanism for learning. It transforms ephemeral session data into permanent, connected knowledge.
1.  **Identification:** At the moment all content is promoted to Layer 3
<!-- A "thought" or finding in a session collection (`session_<id>`) is deemed valuable for long-term retention. -->
2.  **Curation:** The agent creates a new `Memory`, `Entity` or `Insight` node in the **Neo4j** graph.
3.  **Linking:** This new node is **parsed with nlp** & linked via relationships to all relevant entities (e.g., `(Insight)-[:ABOUT]->(Project), (Insight)-[:DERIVED_FROM]->(Document)`).
4.  **Storage:** The **full text** of the "thought" is inserted into the sessions **Chroma** collection. The metadata for this entry includes the ID of the new Neo4j node (`neo4j_id: <memory_node_id>`), permanently binding the text to its contextual graph.

#### **Layer 4: Archive & Telemetry Stream**

*   **Purpose:** To provide an immutable, historical record of all agent interactions for auditing, debugging, and future model training.
*   **Implementation:** An optional JSONL stream logging sessions, queries, memory creations, and promotion events.
*   **Content:** Raw, timestamped logs of system activity.

### Layer 5: Knowledge Base

*   **Purpose:** External source of truth
*   **Implementation:** HTTP / API calls to external services, via requests to resolve data from archives like OHLCV, OWSAP, etc
*   **Content:** Typically json blobs

#### **Summary of Data Flow**

1.  **Conversation happens** -> Stored in Layer 1 (Short-Term Buffer).
2.  **Agent thinks/acts** -> Thoughts stored in Layer 2 (Working Memory Chroma + Graph links).
3.  **Valuable insight is made** -> Promoted to Layer 3 (LTM Chroma + Graph context).
4.  **Cross-sessional query asked** -> **Macro Buffer** orchestrates a search across LTM and relevant Session stores via **Graph-Accelerated Search**.
5.  **Everything is recorded** -> Logged to Layer 4 (Archive).

This architecture ensures Vera can fluidly operate in the moment while continuously building a structured, retrievable, and intelligent knowledge base, capable of learning from its entire lived experience.

#### **3.1 Advanced Capability: The Macro Buffer**

The Macro Buffer is a dynamic, query-time process that constructs a rich context window by leveraging Vera's entire history. It is not a permanent storage layer but a powerful retrieval mechanism.

*   **Purpose:** To break down the isolation between sessions, allowing Vera to connect ideas, hypotheses, and information that were originally recorded in different contexts. This is the foundation for associative reasoning and holistic problem-solving.
*   **How it Works:** As described in Layer 3's advanced retrieval, it uses Graph-Accelerated Search to efficiently find relevant sessions and perform a targeted, multi-collection vector search.
*   **Benefit:** It allows Vera to answer complex, cross-sessional questions like, "What were all the challenges we faced when integrating service X?" by pulling together notes from initial research, debugging logs, and the final summary document.

#### **3.2 Memory Explorer**
#in-production

**The Cartographer of Consciousness: Mapping the Labyrinth of Thought**

The Memory Explorer serves as **the observatory for Vera's cognitive landscape**—a sophisticated visualization system that transforms complex memory structures into interactive, navigable knowledge graphs. It bridges the abstract relationships within Vera's mind with tangible visual representations, making the architecture of intelligence both accessible and explorable.

This system reveals the **living topology of memory**, where Neo4j graph relationships form the structural skeleton and ChromaDB vector stores provide the semantic flesh. Through dynamic visualization, it exposes how concepts connect, how knowledge evolves over time, and how different memory layers interact to form coherent understanding.

The Explorer enables both **macro-scale pattern recognition** and **micro-scale relationship analysis**, allowing researchers to trace idea genealogies across sessions, identify emerging knowledge clusters, and understand how Vera's understanding matures through interaction. It's not merely a debugging tool—it's a window into the cognitive processes that transform isolated facts into interconnected wisdom.

By rendering the invisible architecture of memory into explorable visual spaces, the Memory Explorer provides unprecedented insight into how an AI system organizes, connects, and evolves its understanding of the world—revealing the hidden structures that make autonomous intelligence possible.

---

The Memory Explorer serves as the primary interface for understanding and interacting with Vera's complex memory architecture, providing both intuitive visualization and powerful analytical capabilities for memory management and optimization.
```



## 5. Tool Integration

Vera is equipped with a **versatile and extensible toolset** powered by Model Context Protocol (MCP) servers, enabling seamless interaction with external systems, environments, and web services. These tools allow Vera to deconstruct complex tasks into discrete actionable steps and execute them efficiently through standardized, bidirectional communication channels.

### MCP Server Architecture

Vera's toolkit operates through **MCP servers** — lightweight, protocol-compliant services that expose capabilities as resources, tools, and prompts. This architecture provides:

- **Standardized Tool Interface**: All tools follow MCP specifications for consistent invocation and error handling
- **Extensibility**: New tools can be added by registering additional MCP servers without modifying core logic
- **Bidirectional Communication**: Tools can stream results, handle long-running operations, and provide progress updates
- **Resource Discovery**: Vera can dynamically discover available tools and their schemas at runtime
- **Error Resilience**: MCP's structured error handling ensures graceful degradation when tools fail

---

### Core Capabilities

#### System & Environment
- **Shell Command Execution**  
    Execute shell commands and scripts across Unix/Linux, macOS, and Windows platforms. Vera captures output, error codes, and streaming results for real-time feedback.
    
- **Python Code Execution**  
    Run Python snippets and scripts dynamically within isolated or shared execution contexts. Supports library imports, async operations, and computational tasks on demand.
    
- **File System Manipulation**  
    Read, write, append, and delete files with support for binary and text modes. Includes directory traversal, permission checks, and atomic operations for safe data handling.
    
- **System Introspection**  
    Query installed programs, loaded Python modules, environment variables, and system properties across different operating systems. Enables Vera to understand and adapt to host capabilities.

#### Data & Memory
- **Hybrid Memory Query & Management**  
    Access long-term graph-based memory (Neo4j) and working memory stores (Chroma vectors). Retrieve, summarize, and dynamically update contextual information with semantic search and graph traversal.
    
- **NLP-Powered Entity Extraction**  
    Leverage the hybrid memory's NLP pipeline to extract entities, relationships, and contextual metadata from text without requiring explicit schema definition.

#### Scheduling & Calendar Integration
- **Google Calendar API**  
    Create, update, delete, and query calendar events. Support for recurring events, attendee management, reminders, and timezone-aware scheduling.
    
- **Project & Task Management**  
    Retrieve available projects, list tasks, and track progress. Integrates with memory system for context-aware task recommendations.

#### Web & Information Retrieval
- **Web Searching**  
    Perform live searches using DuckDuckGo or other search providers. Retrieve top results with metadata, snippets, and relevance scoring.
    
- **Web Scraping & Content Retrieval**  
    Fetch and parse web pages, extract structured data, and monitor content changes. Respects robots.txt and rate-limiting policies.

#### Language Model Operations
- **Fast LLM Queries**  
    Execute quick, lightweight queries optimized for review, extraction, summarization, and classification tasks. Uses smaller models or prompt-optimized endpoints for speed.
    
- **Deep LLM Analysis**  
    Perform thorough, in-depth language model queries for complex reasoning, synthesis, multi-step analysis, and creative problem-solving. Routes to larger or specialized models.

#### Self-Inspection & Debugging
- **Source Code Inspection**  
    Access Vera's own codebase for self-reflection, debugging, and capability auditing. Supports both full-file reads and targeted section extraction.
    
- **MCP Server Enumeration**  
    List all connected MCP servers, their exposed tools, schemas, and current status. Useful for runtime capability discovery and troubleshooting.

---

### MCP Tool Registry

#### System & Environment Tools

| Tool Name | MCP Server | Input Schema | Output | Description |
|-----------|-----------|--------------|--------|-------------|
| **Execute Shell Command** | `stdio:bash` | `command: string`, `timeout?: number`, `cwd?: string` | `{ stdout: string, stderr: string, exit_code: number }` | Run shell commands and capture output. Supports piping, redirection, and environment variable injection. |
| **Run Python Code** | `stdio:python` | `code: string`, `timeout?: number`, `context?: object` | `{ result: any, stdout: string, stderr: string }` | Execute Python snippets with access to shared state and libraries. |
| **Read File** | `stdio:fs` | `path: string`, `encoding?: string` | `{ content: string, size: number, mtime: number }` | Read file contents with encoding support and metadata. |
| **Write File** | `stdio:fs` | `path: string`, `content: string`, `mode?: "write"\|"append"` | `{ path: string, size: number, success: boolean }` | Write or append data to files atomically. |
| **List Directory** | `stdio:fs` | `path: string`, `recursive?: boolean` | `{ files: string[], dirs: string[], total: number }` | Enumerate directory contents with optional recursive traversal. |
| **List Installed Programs** | `stdio:system` | `platform?: "windows"\|"linux"\|"macos"` | `{ programs: {name: string, version: string}[], count: number }` | Discover installed software packages and applications. |
| **List Python Modules** | `stdio:system` | `filter?: string` | `{ modules: string[], count: number }` | Enumerate loaded Python modules with optional filtering. |
| **Get System Info** | `stdio:system` | `keys?: string[]` | `{ cpu: string, memory: string, os: string, hostname: string, ... }` | Query system properties like CPU, memory, OS, and network info. |

#### Memory & Knowledge Tools

| Tool Name | MCP Server | Input Schema | Output | Description |
|-----------|-----------|--------------|--------|-------------|
| **Search Long-Term Memory** | `stdio:memory` | `query: string`, `limit?: number`, `entity_type?: string` | `{ results: Entity[], relationships: Edge[], clusters: object }` | Perform semantic and graph-based searches across long-term memory. |
| **Query Session Memory** | `stdio:memory` | `session_id: string`, `query?: string`, `limit?: number` | `{ memories: MemoryItem[], focus_context: any[] }` | Retrieve working memory for a specific session with semantic search. |
| **Extract & Link Entities** | `stdio:memory` | `session_id: string`, `text: string`, `auto_promote?: boolean` | `{ entities: Entity[], relations: Relation[], clusters: object }` | Run NLP extraction pipeline on text and link results to session graph. |
| **Promote Memory to Long-Term** | `stdio:memory` | `session_id: string`, `memory_ids: string[]`, `entity_anchor?: string` | `{ promoted: MemoryItem[], linked_to: string }` | Move working memories to persistent long-term storage. |
| **List Subgraph Seeds** | `stdio:memory` | (none) | `{ entity_ids: string[], entity_types: string[], sessions: string[] }` | Discover available starting points for knowledge graph exploration. |
| **Extract Subgraph** | `stdio:memory` | `seed_entity_ids: string[]`, `depth?: number` | `{ nodes: Node[], relationships: Edge[], summary: string }` | Extract connected subgraph around seed entities with optional depth limit. |

#### Scheduling & Calendar Tools

| Tool Name | MCP Server | Input Schema | Output | Description |
|-----------|-----------|--------------|--------|-------------|
| **Add Calendar Event** | `stdio:google-calendar` | `title: string`, `start_time: string`, `end_time: string`, `attendees?: string[]`, `description?: string` | `{ event_id: string, link: string, success: boolean }` | Create a new event on the connected Google Calendar. |
| **Update Calendar Event** | `stdio:google-calendar` | `event_id: string`, `updates: object` | `{ event_id: string, updated_fields: string[], success: boolean }` | Modify existing calendar events. |
| **Delete Calendar Event** | `stdio:google-calendar` | `event_id: string` | `{ event_id: string, success: boolean }` | Remove events from the calendar. |
| **List Calendar Events** | `stdio:google-calendar` | `start_time?: string`, `end_time?: string`, `limit?: number` | `{ events: CalendarEvent[], count: number }` | Query calendar events within a time range. |
| **List Projects** | `stdio:project-mgmt` | `filter?: string`, `status?: string` | `{ projects: Project[], count: number }` | Retrieve available projects with metadata. |
| **Get Project Tasks** | `stdio:project-mgmt` | `project_id: string`, `status?: string` | `{ tasks: Task[], total: number, completed: number }` | Query tasks within a project with status filtering. |

#### Web & Information Tools

| Tool Name | MCP Server | Input Schema | Output | Description |
|-----------|-----------|--------------|--------|-------------|
| **Web Search** | `stdio:web-search` | `query: string`, `limit?: number`, `engine?: string` | `{ results: {title: string, url: string, snippet: string}[], total: number }` | Perform live web searches and return top results with snippets. |
| **Fetch Web Content** | `stdio:web-scrape` | `url: string`, `format?: "html"\|"text"\|"markdown"` | `{ content: string, title: string, metadata: object }` | Retrieve and parse web page content in various formats. |
| **Monitor URL Changes** | `stdio:web-scrape` | `url: string`, `check_interval?: number` | `{ changed: boolean, diff?: string, last_check: number }` | Track and detect changes to web content over time. |

#### Language Model Tools

| Tool Name | MCP Server | Input Schema | Output | Description |
|-----------|-----------|--------------|--------|-------------|
| **Query Fast LLM** | `stdio:llm-fast` | `prompt: string`, `context?: string`, `max_tokens?: number` | `{ response: string, tokens_used: number, model: string }` | Execute quick LLM queries optimized for speed and efficiency. Common uses: extraction, classification, summarization, review. |
| **Query Deep LLM** | `stdio:llm-deep` | `prompt: string`, `context?: string`, `reasoning_budget?: number` | `{ response: string, reasoning: string, tokens_used: number, model: string }` | Run in-depth LLM queries for complex analysis and multi-step reasoning. |
| **LLM Batch Process** | `stdio:llm-batch` | `prompts: string[]`, `mode?: "fast"\|"deep"` | `{ responses: string[], total_tokens: number, processing_time: number }` | Process multiple queries efficiently in batch mode. |

#### Self-Inspection & Debugging Tools

| Tool Name | MCP Server | Input Schema | Output | Description |
|-----------|-----------|--------------|--------|-------------|
| **Read Source Code** | `stdio:self-inspect` | `file_path?: string`, `section?: string` | `{ content: string, language: string, lines: number }` | Access Vera's own source code for self-reflection and debugging. |
| **List MCP Servers** | `stdio:mcp-admin` | `include_schemas?: boolean` | `{ servers: {name: string, status: string, tools: string[]}[], total: number }` | Enumerate all connected MCP servers and their capabilities. |
| **Reload MCP Server** | `stdio:mcp-admin` | `server_name: string` | `{ server_name: string, reloaded: boolean, status: string }` | Restart or reload an MCP server (useful for development). |
| **MCP Diagnostics** | `stdio:mcp-admin` | `server_name?: string` | `{ diagnostics: object, uptime: number, errors: string[] }` | Query MCP server health, performance metrics, and error logs. |

---

### Tool Usage Patterns

#### Tool Chaining
Vera chains multiple tools to accomplish complex workflows:
```
1. Query Memory → Search for relevant context
2. Execute Code → Process or analyze the retrieved data
3. Write File → Save results
4. Add Calendar → Schedule a follow-up
5. Query LLM → Generate a summary
```

#### Conditional Tool Selection
Vera selects tools based on task complexity:
- **Fast LLM** for quick reviews, classifications, summaries
- **Deep LLM** for complex reasoning, synthesis, planning
- **Shell/Python** for deterministic, computational tasks

#### Error Handling & Fallback
- Tools that fail are retried with adjusted parameters
- Alternative tools are selected if primary tool is unavailable
- MCP server status is continuously monitored for reliability

#### Async & Streaming
Long-running tools (web scraping, batch LLM queries, file processing) use MCP's streaming capabilities to provide real-time progress and allow cancellation.

---

### Extensibility

Adding new MCP servers:

1. **Implement the MCP Interface**: Create a server that exposes tools, resources, and prompts via the MCP protocol
2. **Register with Vera**: Add server configuration to Vera's MCP client registry
3. **Dynamic Discovery**: Vera automatically discovers new tools at runtime
4. **Version Management**: Track tool versions and breaking changes in the memory system

Example new server types:
- **Database Query Server**: SQL, NoSQL, graph database operations
- **Email & Messaging**: Send/receive emails, Slack messages, notifications
- **API Integration**: Stripe, Twilio, HubSpot, or custom business APIs
- **Version Control**: Git operations, code review, CI/CD pipeline triggers
- **Specialized ML Tools**: Custom model inference, data preprocessing pipelines
---

#### Playwright Toolset: Web Automation and Interaction

Playwright tools extend Vera’s capabilities to interact with web browsers programmatically, enabling complex web workflows, automated browsing, data extraction, and testing.

**Playwright Tools provide functionalities including:**

- **Page Navigation and Control**  
    Open and navigate web pages, follow redirects, and wait for page events to ensure content is fully loaded.
    
- **Element Interaction**  
    Click buttons, fill form fields, select dropdown options, and perform other DOM manipulations to simulate user actions.
    
- **Data Extraction**  
    Extract text, HTML, or attribute values from page elements using CSS selectors or XPath queries for structured data collection.
    
- **Screenshot Capture**  
    Take screenshots of entire pages or specific elements for documentation, verification, or reporting purposes.
    
- **Browser Context Management**  
    Manage cookies, local storage, sessions, user agents, and device emulations to simulate diverse user environments.
    
- **Script Evaluation**  
    Run custom JavaScript within page contexts for advanced manipulation or data processing.
    

This modular Playwright integration allows Vera to automate end-to-end workflows on dynamic websites that require interaction beyond static scraping.

---

### 6. [[ToolChain Planner]]
**Automated Multi-Step Tool Orchestration**

The `ToolChainPlanner` class orchestrates the planning and execution of complex workflows by chaining together multiple tools available to the agent. It leverages a deep language model (LLM) to dynamically generate, execute, and verify a sequence of tool calls tailored to solving a user query.

This class forms the core of an intelligent, multi-tool orchestration framework that empowers the agent to decompose complex queries into manageable actions, execute them with error handling, and iteratively improve results through self-reflection.


#### Overview

- **Planning:** Generates a structured multi-step plan in JSON format, specifying which tools to call and what inputs to provide, based on the query and historical context.
    
- **Execution:** Runs each tool in sequence, supports referencing outputs from previous steps (`{prev}`, `{step_n}`), and handles errors with automatic replanning.
    
- **Memory Integration:** Saves intermediate outputs and execution context to the agent's memory for continuity and accountability.
    
- **Result Validation:** Uses the LLM to verify if the final output meets the original goal, triggering replanning if necessary.
    
- **Reporting:** Summarizes all executed tool chains, providing insight into past queries, plans, and outcomes.
    

---

#### Key Components and Methods

|Method|Description|
|---|---|
|`__init__(agent, tools)`|Initializes the planner with a reference to the agent and its toolset. Loads chat history for context.|
|`plan_tool_chain(query, history_context="")`|Generates a JSON-formatted plan of tool calls for the given query, optionally incorporating prior step outputs as context.|
|`execute_tool_chain(query)`|Executes the planned tool chain step-by-step, resolves references to previous outputs, manages errors, and ensures the goal is met via iterative replanning if needed.|
|`save_to_memory(user_msg, ai_msg="")`|Stores interactions and outputs to the agent’s memory buffer for context continuity.|
|`report_history()`|Produces a summarization report of all tool chains executed so far, highlighting queries, plans, results, and patterns.|

---

#### How It Works

1. **Planning Phase:**  
    The class constructs a prompt describing available tools and the user query, requesting the LLM to generate a JSON array that outlines the sequence of tool calls and their inputs.
    
2. **Execution Phase:**  
    Each tool is invoked in order. Inputs referencing outputs from prior steps (e.g., `{step_1}`, `{prev}`) are resolved to the actual results. Errors in execution trigger automatic recovery plans via replanning.
    
3. **Validation & Retry:**  
    After all steps, the planner prompts the LLM to review whether the final output meets the query’s goal. If not, the planner automatically retries with a revised plan.
    
4. **Memory & Reporting:**  
    All intermediate results and plans are saved to memory for transparency and to aid future planning. The report function provides a concise summary of past activity for audit or review.
    

---

#### Benefits

- **Dynamic, Context-Aware Planning:**  
    Plans tool usage tailored to the problem, reusing historical outputs intelligently.
    
- **Error Resilience:**  
    Automatically detects and recovers from tool failures or incomplete results.
    
- **Extensible & Modular:**  
    Works with any tool exposed by the agent, provided they follow a callable interface.
    
- **Traceability:**  
    Detailed logging and memory save steps ensure all decisions and outputs are recorded.
    

---

#### Example Usage

```python
# Assume you have an initialized agent with tools and a deep LLM model

# Create the planner instance
planner = ToolChainPlanner(agent, agent.tools)

# Simple query example: plan and execute a multi-tool workflow
query = "Retrieve the latest weather for New York and generate a summary report."

final_output = planner.execute_tool_chain(query)
print("Final Output:", final_output)

# Generate a report summarizing all past toolchain executions
history_report = planner.report_history()
print("Execution History Report:\n", history_report)
```

---

#### Integration Notes

- **Agent & Tools Setup:**  
    `ToolChainPlanner` expects an `agent` object that exposes:
    
    - `deep_llm`: a language model instance with an `invoke(prompt: str) -> str` method for prompt completion.
        
    - `tools`: a list of tool objects, each having a `name` attribute and a callable interface (e.g., `run()`, `func()`, or `__call__`).
        
    - `buffer_memory`: an object that manages short-term chat history, providing context for planning and execution.
        
    - `save_to_memory(user_msg, ai_msg)`: method to record interaction steps and outputs.
        
- **Tool Interface:**  
    Tools can be any callable entity that takes a single string input and returns a string output. This abstraction allows mixing LLM-based tools, APIs, or custom functions.
    
- **Plan Format:**  
    The planner expects the LLM to output a pure JSON list of objects like:
    
    ```json
    [
      { "tool": "SearchAPI", "input": "latest weather New York" },
      { "tool": "SummarizerLLM", "input": "{step_1}" }
    ]
    ```
    
    The planner replaces placeholders like `{step_1}` or `{prev}` with actual outputs during execution.
    
- **Error Handling:**  
    If a tool execution fails or an output is missing, the planner automatically triggers a replanning phase to recover and retry.
    
- **Extensibility:**  
    To add new tools, simply ensure they conform to the callable interface and add them to the agent’s `tools` list. The planner will dynamically list them and can invoke them in plans.
    
- **Logging & Debugging:**  
    The planner prints detailed step-by-step execution logs, useful for debugging the tool chain behavior and inspecting intermediate results.
       

---

This comprehensive toolset architecture enables Vera to break down high-level goals into concrete, manageable steps executed with precision across multiple domains, making it a powerful assistant in diverse environments.

Tools can be chained together dynamically by Vera’s **Tool Chain Planner**, which uses deep reasoning to break down complex queries into executable sequences.

### 7. Self-Modifying Code

Vera can generate, test, and modify its own code modules using built-in program synthesis capabilities. This allows it to extend its functionality autonomously without external intervention, adapting to new challenges or environments.

# Roadmap
## 1. [[Corpus Crawler]]
#in-developmet

A system for mapping any corpus, including the internet, within the memory of Vera. Analogous to reading

## 2. [[Scheduler]]
#in-developmet 
A system for overall background processing management 

## 3. [Optimiser](/Agents/Agent - Optimiser)
A System for optimizing prompts, thought processes and workflows

## 4. [Babelfish](Babelfish)
#in-developmet 
**a universal communication toolkit for AI agents and distributed systems.** 
It enables your agent to **speak any digital protocol** — from HTTP and WebSockets, to MQTT, SSH, IRC, LoRa, Matrix, Slack, and even experimental transports like WebRTC and QUIC/HTTP3.

At its core, Babelfish acts like a **networking “translator”**:

- Every protocol looks the same to the agent (`open → send → receive → close`).
    
- The agent can freely **combine multiple carriers** into hybrid tunnels (multi-modal VPNs).
    
- Protocols are grouped into **layers**, similar to a networking stack, for modularity and extensibility.
## 6. Security Analyser
#in-developmet 
Dynamic security analysis toolkit

Pulls from knowledge bases and memory to construct the most appropriate test on-the-
## 7. Memory Explorer
#in-developmet 

---
# Requirements

Vera is compatible with Windows; however, detailed configuration instructions are currently provided only for Linux, WSL, and macOS environments due to Windows’ additional setup complexities. Windows users may need to adapt the setup process accordingly.
### System Requirements

- **Operating System:** Linux, macOS, or Windows (with WSL)
    
- **Python:** Version 3.9 or higher
	

**CPU Build** ( Linux )

-  CPU: 12 cores+ (24 hyper-threaded) 3Ghz+
	
- RAM: 16Gb - 32Gb - 150Gb
	
- HDD: 100Gb 
    

**GPU Build** ( Linux )

-  CPU: Unknown
	
- VRAM: 14 - 150Gb
	
- RAM 8Gb 
	
- HDD: 100Gb 

### Python Dependencies

Install required Python packages via `pip`. The main dependencies include, but are not limited to:

- `llama-index` (or the specific LLM library used)
    
- `chromadb` — for vector-based long-term memory storage
    
- `playwright` — for browser automation and web scraping
    
- `requests` — for HTTP requests to external APIs
    
- `tqdm` — for progress bars during streaming
    
- `rich` — for improved terminal output formatting
    
- `pydantic` — for data validation (if used)
    
- `python-dotenv` — for environment variable management (if used)
    

You can install all required dependencies with:

```bash
pip install -r requirements.txt
```

### External Services and Tools

- **Ollama LLM models**: Ensure you have access to the required local or remote LLM models supported by Vera.
	
``` bash
apt install ollama

ollama run gpt-oss:20b

ollama run gemma2

ollama run mistral:7b
```
    
- **ChromaDB**: Running locally or remotely for semantic vector memory support (python will handle this).
    
- **Google APIs**: API keys/configuration for calendar and other Google services (if using integrated tools).
    
- **Playwright browser drivers**: Install necessary browser engines for Playwright:
    
```bash
playwright install
```

---
# Installation

```bash
# Clone this repo
git clone https://github.com/yourusername/verra-agent.git
cd verra-agent

# Install required dependencies
pip install -r requirements.txt
```

> Note: This project depends on the Ollama Python SDK and ChromaDB, among others. Ensure you have access to the required LLM models and local services.

---
## Quick Start Guide

## Terminal
```bash
cd <your/path/to/vera>

python3 ./vera.py
```
## Web Server
```bash
cd <your/path/to/vera>

python3 ./ui.py

chrome-browser localhost:8000
```
## Python Module

```python
from vera import Vera

# Initialize Vera agent system
vera = Vera(chroma_path="./vera_agent_memory")

# Query Vera with a simple prompt
response = vera.stream_llm(vera.fast_llm, "What is the capital of France?")
print(response)

# Use toolchain execution for complex queries
complex_query = "Schedule a meeting tomorrow and send me the list of projects."
result = vera.execute_tool_chain(complex_query)
print(result)
```


# Configuration

## Vera
## Proactive Thought (PAT)

## Toolchain Executor (TCE)

## Tools

## Web UI
# Usage

## Terminal UI
\<images of the terminal UI>
## Web UI
\<images of the web UI>
## Web Server
\<images of the Webserver Manager UI>
## Python Module
\<more example python useage>
## Flags & System Commands
---

/\<command> into the chat prompt
--<flag_name> at the command line

| Flag  /Command  |     | Description                                        |
| --------------- | --- | -------------------------------------------------- |
| --triage_memory |     | Does triage have memory of past interactions y/n?  |
| --forgetful     |     | No memories will be saved or recalled this session |
| --dumbledore    |     | Wont respond to questions - hes dead harry         |
| --replay        |     | Replays the last plan                              |
|                 |     |                                                    |

## Advanced Usage and Features

### Memory

### Proactive Focus Management

Vera can be configured to trigger **background thinking cycles** during idle time:

```python
# Trigger proactive background reflection
vera.focus_manager.run_proactive_cycle()
```

This generates new goals or alerts based on recent conversations and system state.

### Streaming Responses for Real-Time Interaction

Vera supports streaming partial results from LLMs, improving user experience during long or complex queries:

```python
for chunk in vera.stream_llm(vera.deep_llm, "Explain quantum computing."):
    print(chunk, end="")
```

# Agents

Agents are specialised LLMs

Executive
Co-ordinates the specialised agents in the background

Planning

Scheduling

Tool Execution

Foucus
# Performance Optimisation

## Performance Unit Tests
\<how to use performance unit tests>
## CPU Pinning
\<CPU Pinning best practice>
## NUMA
\<NUMA best practice>
## hugepages
\<hugepages best practice>
## VM
\<VM best practice>

---

# Architecture Overview

```
+------------------------------------------------+
|                    Vera System                  |
|------------------------------------------------|
|  +-------------+   +-------------+   +--------+|
|  | Fast Agent  |   | Deep Agent  |   |Reasoning||
|  | (gemma2)    |   | (gemma3-27b)|   |Agent    ||
|  +-------------+   +-------------+   +--------+|
|          \               |               /       |
|           \              |              /        |
|            \             |             /         |
|             \            |            /          |
|           +----------------------------------+   |
|           |         Memory Management         |  |
|           |  (Short-Term Buffer + Long-Term)  |  |
|           +----------------------------------+   |
|                     |                  |          |
|           +-------------------------------+       |
|           |        Tool Chain Planner      |      |
|           +-------------------------------+       |
|                      |                   |         |
|           +-------------------------------+       |
|           |       Toolset & Browser        |      |
|           |  (Shell, Calendar, Web, etc.)  |      |
|           +-------------------------------+       |
+----------------------------------------------------+
```

---
# Extending Vera

## Tools

You can add new tools by extending the `load_tools` method with new `Tool` objects, defining their name, function, and description.

Simple Example:

```python
def load_tools(self):
    tools = super().load_tools()
    tools.append(
        Tool(
            name="New Custom Tool",
            func=lambda q: custom_function(q),
            description="Description of the new tool."
        )
    )
    return tools
```

Advanced Example:
```python

```

## Agents

You can add new agents by
```python

```


---
# [[Central Executive Orchestrator]]

The **Proactive Focus Manager** is a core component designed to help Vera autonomously advance project goals by periodically generating actionable next steps and managing ongoing progress within a defined focus area.

### What It Does

- Maintains a **focus** — a current project or goal guiding all proactive thinking.
    
- Tracks progress, next steps, issues, ideas, and actions on a dynamic **focus board**.
    
- Periodically (default every 10 minutes) generates **proactive thoughts** based on:
    
    - The current focus
        
    - Recent conversation context
        
    - The evolving focus board content
        
- Uses a fast LLM to **evaluate** whether proposed actions are actionable with the tools available.
    
- Automatically **executes approved goals** via Vera’s tool chain and logs outcomes.
    
- Monitors system CPU and active LLM processes, **pausing proactive thinking** if resource usage is too high, to avoid overload.
    

### Why It Matters

This manager enables Vera to function more like a **self-driven assistant**, continuously pushing a project forward without waiting for user input. It keeps a running record of progress and obstacles, making the AI’s workflow transparent and actionable.

### How to Use

1. **Initialize** the manager with your agent instance:
    
    ```python
    focus_manager = ProactiveFocusManager(agent)
    ```
    
2. **Set a focus** for the project:
    
    ```python
    focus_manager.set_focus("Build automated network monitoring tool")
    ```
    
3. Optionally, **update the latest conversation context** to inform proactive thoughts:
    
    ```python
    focus_manager.update_latest_conversation(latest_chat_text)
    ```
    
4. **Start** the proactive loop:
    
    ```python
    focus_manager.start()
    ```
    
5. The manager will generate, evaluate, and execute proactive steps autonomously, updating its internal focus board.
    
6. Use `add_to_focus_board()` to manually add notes or issues as needed.
    
7. **Stop** the manager to pause proactive thinking:
    
    ```python
    focus_manager.stop()
    ```
    

### Configuration Options

- `proactive_interval` — time (seconds) between proactive thoughts (default: 600)
    
- `cpu_threshold` — maximum CPU usage allowed before pausing proactive thinking
    
- `max_ollama_processes` — max concurrent LLM processes before pausing (default: 24)
    
- `proactive_callback` — optional callback to handle new proactive thoughts in real time
    

### Extending the Focus Manager

- Add calendar visibility to align proactive actions with schedules.
    
- Integrate external knowledge bases or memories for richer context.
    
- Improve resource monitoring or add priority handling on focus board entries.
	

---
# Contributing

Vera is designed to be extensible and modular. Here are ways to contribute:

- **Add new tools:** Implement new `Tool` objects with clearly defined inputs and outputs.
    
- **Improve memory models:** Experiment with alternative vector DBs or memory encoding strategies.
    
- **Enhance planning algorithms:** Optimize or replace the tool chain planner for more efficient workflows.
    
- **Expand self-modification capabilities:** Enable more robust and safe code generation and auto-updating.
    
- **Improve UX:** Add richer streaming output, UI components, or integrations.
    

---

# Safeguarding & Data Privacy



---
# FAQ

**Q: What LLMs does Vera support?**  
A: Vera is currently built around Ollama models (`gemma2`, `gemma3`, `gpt-oss`), but you can adapt it for any compatible LLM with a Python SDK or API.

**Q: Can Vera run headless?**  
A: Yes. Vera is designed for command-line and backend automation, but can be integrated into GUIs or web apps.

**Q: Is Vera safe to run self-modifying code?**  
A: Self-modification is sandboxed and requires careful review. Vera includes safeguards, but users should always review generated code before production use.

---

# Known Issues

**TTS Pacing** - On slower hardware the TTS engine may talk faster than the LLM can generate

**LLM Reasoning not Visible** - If an LLM has reasoning built in ( i.e. deepseek, gpt-oss) it will not display the reasoning in the web or terminal UI leading to a large gap between a query being accepted and answer being given.

---
## License

Specify your license here.

---

## Contact & Support

For questions, feature requests, or help, open issues on the GitHub repo or contact [[your-email@example.com](mailto:your-email@example.com)].

---

### Performance Tiers

| Tier | CPU | RAM | Storage | VRAM | Recommended Use |
|------|-----|-----|---------|------|-----------------|
| **Basic** | 8 cores | 16GB | 100GB | - | Development & testing |
| **Standard** | 12+ cores | 32GB | 100GB | - | Production CPU build |
| **Advanced** | 16+ cores | 64GB | 200GB | 14GB+ | GPU-accelerated |
| **Enterprise** | 24+ cores | 150GB+ | 500GB+ | 80GB+ | Large-scale deployment |

### Model Compatibility

| Model Type | Example Models | Memory | Use Case | Status |
|------------|----------------|---------|----------|--------|
| **Fast LLM** | Mistral 7B, Gemma2 2B | 4-8GB | Triage, quick tasks | ✅ Supported |
| **Intermediate** | Gemma2 9B, Llama 8B | 8-16GB | Tool execution | ✅ Supported |
| **Deep LLM** | Gemma3 27B, GPT-OSS 20B | 16-32GB | Complex reasoning | ✅ Supported |
| **Specialized** | CodeLlama, Math models | Varies | Domain-specific | 🔄 Partial |

### Roadmap Timeline

| Quarter | Focus Areas | Key Deliverables |
|---------|-------------|------------------|
| **Q2 2024** | Core stabilization | Production memory system, tool chains |
| **Q3 2024** | Advanced capabilities | Babelfish, Corpus Crawler alpha |
| **Q4 2024** | Scaling & optimization | Scheduler, Security Analyzer |
| **Q1 2025** | Enterprise features | Memory Explorer, cluster support |

---

## Known Limitations

- Windows configuration requires manual adaptation
- TTS pacing issues on slower hardware
- LLM reasoning not visible in UI for some models
- Resource-intensive on large knowledge graphs