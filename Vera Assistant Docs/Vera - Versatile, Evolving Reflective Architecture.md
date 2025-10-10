

## Introduction: What is Vera?

**Vera** is an advanced multi-agent AI architecture inspired by principles from cognitive science and agent-based systems. It integrates a framework combining short-term and long-term memory, token prediction, task triage, reasoning, proactive focus management, self-modification, and modular tool execution to deliver flexible, intelligent automation.

Vera **orchestrates multiple large language models** (LLMs) and specialized AI sub-agents synchronously to tackle complex, high-level user requests. It decomposes broad tasks into discrete, manageable steps, then dynamically plans and executes these steps through various external and internal tools to achieve **comprehensive outcomes**. This distributed agent design enables parallel specialization - some agents focus on rapid query response, others on strategic forward planning - while sharing a unified memory and goal system to maintain coherence across operations.

A hallmark of Vera’s architecture is its capacity for **proactive background processing**. Autonomous sub-agents continuously monitor context and system state, coordinating via dynamic focus prioritization. This allows Vera to orchestrate perceptual inputs, data processing, and environmental interactions adaptively, even without direct user prompts allowing it to **enrich its own memories** and progress toward long-term goals. The strategic planning layer oversees long-term goals, enabling Vera to anticipate user needs, generate novel insights, and refine internal models on an ongoing-basis resulting in more contextually aware, intelligent, and timely responses.

Vera grounds its intelligence in a highly structured, **multi-layered memory system** (Layers 1-4) that mirrors human cognition by separating volatile context from persistent knowledge. This memory uses a hybrid storage model: the **Neo4j Knowledge Graph** stores entities and rich, typed relationships, while **ChromaDB** serves as a **vector database** for the full text content of documents, notes, and code, binding the textual information to its contextual network. Furthermore, the Macro Buffer mechanism leverages **Graph-Accelerated Search** to dynamically retrieve relevant knowledge and historical sessions, effectively breaking down isolation between contexts for comprehensive associative recall

Complementing these capabilities is Vera’s integrated program synthesis and self-modification engine. This subsystem empowers Vera to **review, generate, and iteratively improve its own codebase**, extending its functionality autonomously without requiring manual reprogramming. By enabling self-reflection and continuous evolution, Vera maintains adaptability and resilience across rapidly changing task demands and environments.

Together, these components form a flexible, extensible AI platform designed for complex problem solving, adaptive decision making, and seamless interaction across diverse domains.
 
## What is the use-case of Vera?
Vera is designed to help in day-to-day tasks and planning. Coordinating my schedule, advising about projects,  without having to provide the same context over and over again. 

## Why have you made Vera?
Altough many tools like this exist online and developments are manifold i wanted to make something that could be run at home with the right hardware, demonstrating the limits of local compute. Its also an exploration in the art of possible - how far can these models be pushed given the right context and tools?

---

>[!WARNING]
>**Vera has high system requirements**  
> Atleast 16Gb of system RAM, and 12 real cores (24 hyperthreaded) running at 3Ghz+ is the minimum recommended.  
>Please check the requirements section for more info

>[!NOTE]  
>**Vera utilises the Agentic-Stack-POC**  
> To bootstrap the various services required for vera we have built an AI develpoment framework called `Agentic Stack POC` its not required but reccomended.

## Contents:

This readme will cover the following:
* Core capabilities
* Core concepts
* Core components
* Requirements
* Installation
* Configuration
* Usage
* Modification
* Performance optimisation
* Contribution
* Known Issue and limitations
* Safeguarding
* License

---
## Core Capabilities

Vera can perform the following tasks - this is not an exhaustive list.

* Report Generation
* Research
* Trend Discovery
* Media Creation
* Podcast Generation

* Programming
* Debugging
* Documentation generation
* Codebase Monitoring
* Network Security Monitoring
* Vulnerability Discovery
* Disater Recovery
* Infrastructure Monitoring
* System Maintenance and Trroubleshooting
* Platform Administration

* Project Delivery
* Customer Service
* Personal Assistant
* Guided Human-Oriented Plans


## Core Concepts

### 1. Agents vs LLMs vs Encoders in Vera 
**A Multi-Level Hierarchy**

Vera’s architecture distinguishes between **LLMs** and **Agents**, each operating at multiple levels of complexity and capability to handle diverse tasks efficiently.

#### Encoders

- Encoders: Extremely light models specialized to encode text. Parses all data sent the vectorstore. 

#### Large Language Models (LLMs)

LLMs are the foundational language engines performing natural language understanding and generation. Vera uses several LLMs, each specialized by size, speed, and reasoning ability:

- **Fast LLMs:** Smaller, generalized text models, optimized for quick straightforward responses.
    
- **Intermediate LLMs:** Larger generalized text models that balance speed and reasoning capacity.
    
- **Deep LLMs:** Large, resource-intensive text models suited for complex reasoning and extended dialogues.
    
- **Specialized Reasoning LLMs:** Models fine-tuned or architected specifically for heavy logical textual processing and multi-step deduction.
    

Each LLM level provides different trade-offs between speed, resource use, and depth of reasoning. Models can be upgraded in-place meaning when a new model is released it is plug-and-play so to speak. The memories will carry over as if nothing changed.

##### How Levels Interact

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


#### Micro Models
<a><img src="https://img.shields.io/badge/in_development--FF9933?style=for-the-badge&logoColor=white"></a>

- **Micro Models:** Tiny models, specialized to complete one task or read a particular dataset. Can be built and trained on a case-by-case basis. Capable of massive parallel reasoning. 

#### Model Overlays
<a><img src="https://img.shields.io/badge/in_development--FF9933?style=for-the-badge&logoColor=white"></a>

Allows you to overlay additional training onto existing models

<!-- 
### 2. Memories

#### Node
A single entity on the knowledge graph

#### Edge
A relationship between two nodes

#### Knowledge Base
A dynamic external data source like live web documentation or an api

#### Ingestor
Parses external datasets into the memory system i.e. network scans, 

#### Enricher
Enriches the knowledge graph 

#### Micro Buffer
Memory buffer for immediate context

### Meso buffer

#### Macro Buffer
Memory buffer for cross sessional context

#### Meta Buffer
Memory buffer for memory system context


#### Project
Defined in a json file, this is a collection of other memories and pointers relating to a real-world goal

#### Session
A string of interactions (inputs & outputs) connected in sequence. Found in the knowledge graph and vector store

#### Session (Node)
The first node of all sessions, contains information about the dependency versions, codebase versions, available tools, session level errors, resource availability.

#### Memory

#### Entity

#### Insight

#### Collection
A collection of texts relating to a session, entity or insight. Found in the vector store

### 3. Tools

#### Internal
These tools can interact with internal apis and services like the memory system

#### Management
Capable of managing the host system



####


### 4. Orchestration

#### Worker
A local task processor, used for quick low effort tasks

#### ClusterWorker
A remote task processor, computationally seperate from the host, used for sustained or high-effort tasks

#### Pool
The combined pool of workers both local and remote

#### ClusterPool
The remote pool of workers

#### Task
A processing task to be completed by the pool -->

---

## Core Components

#### Top level components:

All top level components are designed to run stand-alone or togehter as a complete framework.

**CEO - Central Executive Orchestrator**  
#in-development #poc-working  
Responsible for routing requests to the correct agent and creating, destroying & allocating system resources via workers.

**PBT- Proactive Background Cognition**  
#in-development #poc-working  
Responsible for co-ordinating long term goals, short term focus and delivering actionables during downtime

**TCE - Toolchain Executor**  
#in-development #poc-working  
Breaks down complex tasks into achievable steps then executes the plan using tools, built in or called via an MCP server.

**KGM - Knowledge Graph Memory**  
#in-development #poc-working  
Stores memories and their relationships in vector and graph stores. 
Systematically enriches information stored within the graph

**BFT - Babelfish Translator**  
#production #poc-working  
A protocol agnostic communication tool with encryption. Facilitates arbitrary webserver creation, ad-hoc network protocol comms. And VPN construction.

**IAS  - Integration API Shim**  
#production #poc-working  
Allows Vera to mimic other LLM APIs. Also allows those same APIs to interface with Veras systems.

**SME - Self Modification Engine**  
#in-development  
A full CI/CD pipeline for Ver to review and edit its own code.

**PF - Perceptron Forge**  
#in-development  
Allows Vera to build new models from the fundamental building blocks of all AI models - perceptrons.

**EP - Edit Pipeline**
#in-development  
Version control for edits the AI makes to files, settings etc


#### User Interfaces

**CUI - Chat UI**  
A web UI with full duplex speech synthesis

**OUI - Orchestrator UI**  
A web UI for management of the orchestrator

**TCEUI - ToolChain Executor UI**  
A standalone UI for managing the ToolChain Executor

**MX - Memory Explorer**  
A web UI enabling broad or targeted traversal of the knowledge graph


---

### 1. Central Executive Orchestrator
**Task scheduler & worker orchestrator**  

<a><img src="https://img.shields.io/badge/in_production--33bf63?style=for-the-badge&logoColor=white"></a>


The Heart of vera, it collects performance data and queues user input then allocates or creates resources either locally or in a remote worker pool.

The Orchestrator can identify where steps and tasks can be completed in parallel and will schedule them as such if the resource is available.

Query recieved
Query Triaged
Handed to the toolchain executor
Toolchain Executor requests resource for a network scanner and light-llm 
Orchestrator identifies that all light-llms are busy and queues the request.
The resources become free
Orchestrator identifies there is resource available for the network scan and allocates it
The network scan runs - in this time a light llm becomes free
Orchestrator dequeues the task and provides the resources
ToolCahin executor returns the results of the step.

---

### 2. Proactive Background Reflection

<a><img src="https://img.shields.io/badge/in_production--33bf63?style=for-the-badge&logoColor=white"></a>


[Proactive Background Reflection Documentation](<Vera Assistant Docs/Central Executive Orchestrator.md>)

Vera maintains a **Proactive Focus Manager** that continuously evaluates system priorities, context, and pending goals. During idle moments, it generates **proactive thoughts**—such as reminders, hypotheses, or plans—that enhance its understanding and readiness for future interactions.

<!-- **Proactive Focus Manager** is an autonomous background cognition engine that runs on top of `PriorityWorkerPool`. It continuously monitors project context, generates actionable tasks via LLMs, validates them, and executes them through your toolchain while logging progress to a focus board. -->

This ongoing background reflection helps Vera:

- Detect inconsistencies or gaps in knowledge
    
- Anticipate user needs
    
- Prepare for complex multi-step operations
    
- Improve self-awareness and performance over time


It is designed to integrate seamlessly with local, remote, and Proxmox-based worker nodes, providing a distributed, scalable, and high-throughput execution environment.

#### Features

- **Context-aware task generation:** Pulls context from multiple providers (`ConversationProvider`, `FocusBoardProvider`, or custom providers)
    
- **LLM-driven reasoning:** Uses a deep LLM to generate actionable next steps
    
- **Action validation:** Uses a fast LLM to check if proposed actions are executable
    
- **Distributed execution:** Integrates with local pools, remote HTTP workers, and Proxmox-hosted nodes
    
- **Focus tracking:** Maintains a focus board with progress, next steps, ideas, actions, and issues
    
- **Non-blocking scheduling:** Periodic autonomous ticks with configurable intervals
    


---

### 3. Memory Architecture

<a><img src="https://img.shields.io/badge/in_development--FF9933?style=for-the-badge&logoColor=white"></a>

![Memory UI](images/memory_ui.jpg)
<i>Above: The memory explorer </i>

[Memory Documentation](<Memory/memory.md>) ⚠
[Memory Schema](<Memory/schema.md>)

The Vera agent is powered by a sophisticated, multi-layered memory system designed to mirror human cognition. This architecture separates volatile context from persistent knowledge, enabling both coherent real-time dialogue and deep, relational reasoning over a vast, self-curated knowledge base. The system is built on a core principle: **ChromaDB** vectorstores hold the raw textual content, while the Neo4j graph maps the relationships and context between them.**

#### **Architecture Overview**

Vera's memory is structured into four distinct storage layers, excluding Layer 5 each layer contains or is derived from data in the previous layer, each serving a specific purpose in the cognitive process:

*   **Layer 1: Short-Term Buffer** - The agent's immediate conversational context.
*   **Layer 2: Working Memory** - Its private scratchpad for a single task, session or memory. Gives vera a place to think, make notes, plan.
*   **Layer 3: Long-Term Knowledge** - A persistent snapshot of Veras entire mind, an interconnected library of interactions, facts and insights. This is how Vera can quickly derive insights from large datasets.
*   **Layer 4: Temporal Archive** - A complete, immutable record of activity logs, metrics, codebase changes, graph changes. Allowing you to 'scroll' back through the entire history of Vera.
*   **Layer 5: External Knowledge Bases** - Dynamic networked data stores. Web documentation, APIs, Git repos. Allows Vera to extend its graph beyond its own boundaries.

A key advanced capability, the **Memory Buffer**, can dynamically bridge Layers to enable unified, cross-sessional, highly enriched reasoning.

#### **Layer 1: Short-Term Context Buffer**

*   **Purpose:** To maintain the immediate context of the active conversation, ensuring smooth and coherent multi-turn dialogue. This is a volatile, rolling window of recent events.
It will contain systenm prompts, user input, the last <i>n</i> chat history entries, vector store matches & nlp data.
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
    *   **Vector Database - ChromaDB (Content & Semantic Search):** The primary `long_term_docs` collection stores the **full text** of all important information: documents, code examples, notes, and promoted "thoughts." Each entry contains metadata that points back to the Neo4j graph.
    *   **Knowledge Graph - Neo4j (Context & Relationships):** The graph stores all memories, entities & insights (e.g., `Project`, `Document`, `Person`, `Feature`, `Memory`) and the rich, typed relationships between them (e.g., `USES`, `AUTHORED_BY`, `CONTAINS`). It does not store large text bodies, only pointers to them in Chroma. 
    See [Memory Schema](<Memory/schema.md>) for more information on types.

*   **How It Works (Basic Retrieval):**
    1.  A semantic query is performed on the `long_term_docs` Chroma collection.
    2.  The search returns the most relevant text passages and their metadata, including a `neo4j_id`.
    3.  This ID is used to fetch the corresponding node and its entire network of relationships from Neo4j.
    4.  The agent receives both the retrieved text *and* its full relational context, enabling deep, multi-hop reasoning.


#### **The Promotion Process: From Thought to Knowledge**

Promotion is the key mechanism for learning. It transforms ephemeral session data into permanent, connected knowledge.
1.  **Identification:** At the moment all content is promoted to Layer 3, selective promotion is on the roadmap
<!-- A "thought" or finding in a session collection (`session_<id>`) is deemed valuable for long-term retention. -->
2.  **Curation:** The agent creates a new `Memory`, `Entity` or `Insight` node in the **Neo4j** graph.
3.  **Linking:** This new node is **parsed with nlp** & linked via relationships to all relevant entities (e.g., `(Insight)-[:ABOUT]->(Project), (Insight)-[:DERIVED_FROM]->(Document)`).
4.  **Storage:** The **full text** of the "thought" is inserted into the sessions **Chroma** collection. The metadata for this entry includes the ID of the new Neo4j node (`neo4j_id: <memory_node_id>`), permanently binding the text to its contextual graph.

#### **Layer 4: Temporal Archive & Telemetry Stream**

*   **Purpose:** To provide an immutable, historical record of all agent interactions for auditing, debugging, and future model training. It also allows the system to 'scroll back in time' for the entire graph, just a particular subgraph, section or node.
*   **Implementation:** An optional JSONL stream logging sessions, queries, memory creations, and promotion events.
*   **Content:** Raw, timestamped logs of system activity.

#### Layer 5: Knowledge Basees

*   **Purpose:** External source of truth
*   **Implementation:** HTTP / API calls to external services, via requests to resolve data from archives like Wikipedia, DNS Records, OHLCV Data, OWSAP, etc
*   **Content:** Typically json blobs

#### **Summary of Data Flow**

1.  **Conversation happens** -> Stored in Layer 1 (Short-Term Buffer).
2.  **Agent thinks/acts** -> Thoughts stored in Layer 2 (Working Memory Chroma + Graph links).
3.  **Valuable insight is made** -> Promoted to Layer 3 (LTM Chroma + Graph context).
4.  **Cross-sessional query asked** -> **Macro Buffer** orchestrates a search across LTM and relevant Session stores via **Graph-Accelerated Search**.
5.  **Everything is recorded** -> Logged to Layer 4 (Archive).

This architecture ensures Vera can fluidly operate in the moment while continuously building a structured, retrievable, and intelligent knowledge base, capable of learning from its entire lived experience.

#### **3.1 Memory Buffer Hierarchy: Micro, Macro, and Meta**
<a><img src="https://img.shields.io/badge/in_development--FF9933?style=for-the-badge&logoColor=white"></a>

Vera employs a sophisticated three-tier memory buffer system that operates at different scales of retrieval and reasoning, enabling seamless cognitive processing across temporal and conceptual dimensions.

Think of them as three zoom lenses focusing memory retrieval and processing to the required scale

---

#### **Micro Buffer: The Working Context Engine**

#in-development

The Micro Buffer is always active and serves as **the real-time cognitive workspace**—managing the immediate context and attention span during active reasoning and task execution.

*   **Purpose:** To maintain optimal cognitive load by dynamically managing the active working set of information. It filters, prioritizes, and sequences relevant memories for the current task moment-by-moment.
*   **How it Works:** 
    - **Attention Scoring**: Continuously scores available memories based on recency, relevance to current task, and relationship strength
    - **Cognitive Load Management**: Limits active context to 7±2 chunks to prevent overload (Miller's Law implementation)
    - **Real-time Pruning**: Drops low-relevance information and promotes high-value context as tasks evolve
    - **Focus Tracking**: Maintains attention on the most salient entities and relationships during complex reasoning
    - **NLP Processing**: Extracts key information and meaning from text and stores them as relationships in the knowledge graph. i.e. triplets, URLs, filepaths, references, entities like person, technology. It can also parse code into relational trees.   
 
*   **Technical Implementation:**
```cypher
// Micro Buffer maintains focus stack during reasoning
MATCH (current:Task {id: $task_id})
MATCH (current)-[:HAS_FOCUS]->(focus_entity)
WITH focus_entity
MATCH (focus_entity)-[r*1..2]-(related)
WHERE r.relevance_score > 0.7
RETURN related 
ORDER BY r.relevance_score DESC 
LIMIT 15  // Working memory constraint
```

*   **Example Usage:** When debugging code, the Micro Buffer automatically maintains focus on the current function, related variables, and recent stack traces while filtering out unrelated project documentation.

---

#### **Macro Buffer: The Cross-Sessional Associative Engine**

#in-development

The Macro Buffer serves as **the connective tissue between cognitive sessions**—enabling holistic reasoning across time and context boundaries.

*   **Purpose:** To break down the isolation between sessions, allowing Vera to connect ideas, hypotheses, and information that were originally recorded in different contexts. This is the foundation for associative reasoning and holistic problem-solving.
*   **How it Works:** 
    - **Graph-Accelerated Search**: Uses Neo4j to efficiently find relevant sessions and entities across time
    - **Multi-Collection Vector Search**: Performs targeted semantic search across relevant session collections
    - **Temporal Pattern Recognition**: Identifies sequences and evolution of ideas across sessions
    - **Context Bridging**: Creates conceptual bridges between seemingly disconnected sessions

*   **Technical Implementation:**
```cypher
// Macro Buffer: Cross-sessional associative retrieval
MATCH (s:Session)-[:HAS_TOPIC|FOCUSED_ON]->(topic)
WHERE topic.name =~ "(?i).*authentication.*"
WITH collect(DISTINCT s.session_id) as relevant_sessions
MATCH (idea:Concept)-[r:EVOLVED_FROM|RELATED_TO*1..3]-(connected)
WHERE idea.session_id IN relevant_sessions
RETURN idea, connected, r
ORDER BY r.temporal_weight DESC
```

*   **Benefit:** It allows Vera to answer complex, cross-sessional questions like, "What were all the challenges we faced when integrating service X?" by pulling together notes from initial research, debugging logs, and the final summary document.

---

#### **Meta Buffer: The Strategic Reasoning Layer**

#in-development

The Meta Buffer operates as **the executive control system**—managing higher-order reasoning about reasoning itself, strategic planning, and self-modeling.

*   **Purpose:** To enable Vera to reason about its own cognitive processes, identify knowledge gaps, and strategically plan learning and problem-solving approaches.
*   **How it Works:**
    - **Cognitive Pattern Recognition**: Identifies recurring reasoning patterns, successful strategies, and common failure modes
    - **Knowledge Gap Analysis**: Detects missing information, contradictory knowledge, and underspecified concepts
    - **Strategic Planning**: Generates learning agendas, research plans, and problem-solving roadmaps
    - **Self-Modeling**: Maintains and updates Vera's understanding of its own capabilities and limitations

*   **Technical Implementation:**
```cypher
// Meta Buffer: Strategic reasoning and gap analysis
MATCH (capability:Capability {name: $current_task})
MATCH (capability)-[r:REQUIRES|BENEFITS_FROM]->(required_knowledge)
OPTIONAL MATCH (vera:SelfModel)-[has:HAS_KNOWLEDGE]->(required_knowledge)
WITH required_knowledge, 
     CASE WHEN has IS NULL THEN 1 ELSE 0 END as knowledge_gap,
     r.importance as importance
WHERE knowledge_gap = 1
RETURN required_knowledge.name as gap, 
       importance,
       "Learning priority: " + toString(importance) as recommendation
ORDER BY importance DESC
```

*   **Example Usage:** When faced with a novel problem, the Meta Buffer might identify that Vera lacks understanding of quantum computing concepts, then generate and execute a learning plan that includes reading research papers, running simulations, and seeking expert knowledge.

---

### **Buffer Interaction Dynamics**

The three buffers work in concert to create a seamless cognitive experience:


Micro Buffer (Tactical) → Manages immediate working context
    ↑ ↓
Macro Buffer (Operational) → Connects cross-sessional knowledge  
    ↑ ↓
Meta Buffer (Strategic) → Guides long-term learning and reasoning


**Real-world Example: Complex Problem-Solving**
1. **Meta Buffer** identifies Vera needs to learn about blockchain for a new project
2. **Macro Buffer** retrieves all past sessions mentioning cryptography, distributed systems, and related concepts
3. **Micro Buffer** manages the immediate context while Vera reads documentation, runs code examples, and tests understanding
4. **Meta Buffer** updates Vera's knowledge base with new blockchain capabilities
5. **Macro Buffer** connects this new knowledge to existing financial and security concepts
6. **Micro Buffer** applies the integrated knowledge to solve the original problem

This hierarchical buffer system enables Vera to operate simultaneously at tactical, operational, and strategic levels—maintaining focus while building comprehensive understanding and planning for future challenges.

This creates a coherent hierarchy where:
- **Micro** = Immediate working memory and attention
- **Macro** = Cross-sessional associative memory  
- **Meta** = Strategic reasoning and self-modeling

Each buffer operates at a different temporal and conceptual scale while working together to enable sophisticated, multi-layered cognitive processing.

#### **3.1 Advanced Capability: Memory Lifecycle**
<a><img src="https://img.shields.io/badge/in_development--FF9933?style=for-the-badge&logoColor=white"></a>

Discovery - Promotion - Recall - Enrinchment - Continuous Evaluation - Decay - Archiving

Planned feature

#### **3.2 Memory Explorer**

**The Cartographer of Consciousness: Mapping the Labyrinth of Thought**

<a><img src="https://img.shields.io/badge/in_production--33bf63?style=for-the-badge&logoColor=white"></a>

[Memory Explorer Documentation](<Memory/dashboard/dashboard.md>)
[Knowledge Graph Documentation](<Vera Assistant Docs/Knowledge Graph.md>)
[Knowledge Bases Documentation](<Vera Assistant Docs/Knowledge Bases.md>)

The Memory Explorer serves as **the observatory for Vera's cognitive landscape**—a sophisticated visualization system that transforms complex memory structures into interactive, navigable knowledge graphs. It bridges the abstract relationships within Vera's mind with tangible visual representations, making the architecture of intelligence both accessible and explorable.

This system reveals the **living topology of memory**, where Neo4j graph relationships form the structural skeleton and ChromaDB vector stores provide the semantic flesh. Through dynamic visualization, it exposes how concepts connect, how knowledge evolves over time, and how different memory layers interact to form coherent understanding.

The Explorer enables both **macro-scale pattern recognition** and **micro-scale relationship analysis**, allowing researchers to trace idea genealogies across sessions, identify emerging knowledge clusters, and understand how Vera's understanding matures through interaction. It's not merely a debugging tool—it's a window into the cognitive processes that transform isolated facts into interconnected wisdom.

By rendering the invisible architecture of memory into explorable visual spaces, the Memory Explorer provides unprecedented insight into how an AI system organizes, connects, and evolves its understanding of the world—revealing the hidden structures that make autonomous intelligence possible.

<!-- 
Meta scale
Temporal Scale 
-->

---

### 4. ToolChain Planner/Executor
**Automated Multi-Step Tool Orchestration**

<a><img src="https://img.shields.io/badge/in_production--33bf63?style=for-the-badge&logoColor=white"></a>


>[!WARNING]  
>**Vera has unrestricted access to Bash & Python execution out of the box**  
>Please be very careful with what you ask for. There is nothing stopping it from running `rm -rf /`. Or Disable these two tools.

[ToolChain Documentation](<Vera Assistant Docs/Toolchain Planner.md>)

The `ToolChain` orchestrates the planning and execution of complex workflows by chaining together multiple tools available to the agent. It leverages a deep language model (LLM) to dynamically generate, execute, and verify a sequence of tool calls tailored to solving a user query.

This forms the core of an intelligent, multi-tool orchestration framework that empowers the agent to decompose complex queries into manageable actions, execute them with error handling, and iteratively improve results through self-reflection.

The ToolChain can utilise various planning formats, best suited to the problem:

Batch Planning

Step Planning

Hybrid Planning 

The ToolChain can execute plans using various execution formats:

Sequential Execution

Parallel Execution

Speculative Execution

#### Overview

- **Planning:** Generates a structured plan in JSON format, specifying which tools to call and what inputs to provide, based on the query and historical context.
    
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
    It decides the best style of plan for the problem, then constructs a prompt describing available tools and the user query, requesting the LLM to generate a JSON array that outlines the sequence of tool calls and their inputs.
    
2. **Execution Phase:**  
    Each tool is invoked in order. Inputs referencing outputs from prior steps (e.g., `{step_1}`, `{prev}`) are resolved to the actual results. Errors in execution trigger automatic recovery plans via replanning.
    
3. **Validation & Retry:**  
    After all steps, the planner prompts the LLM to review whether the final output meets the query’s goal. If not, the planner automatically retries with a revised plan.
    
4. **Memory & Reporting:**  
    All intermediate results and plans are saved to memory for transparency and to aid future planning. The report function provides a concise summary of past activity for audit or review.
    

---

#### Benefits

- **Dynamic, Context-Aware Planning:**  
    Selects the type of plan & plans tool usage tailored to the problem, reusing historical outputs intelligently.
    
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

#### Tools

Internal Tools

Local Tools

MCP Tools

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

---

### 5. API Integration Shim

<a><img src="https://img.shields.io/badge/in_production--33bf63?style=for-the-badge&logoColor=white"></a>


A compatability layer and API endpoint for Vera. Allows vera to take the pace of other LLM APIs like OpenAIs Chat GPT or Anthropics Claude. It also allows these APIs to interface with the Vera framework 

---

### 6. Babelfish

[Babelfih Documentation](<Vera Assistant Docs/Babelfish.md>)

<a><img src="https://img.shields.io/badge/in_production--33bf63?style=for-the-badge&logoColor=white"></a>


**a universal communication toolkit for AI agents and distributed systems.** 
It enables your agent to **speak any digital protocol** — from HTTP and WebSockets, to MQTT, SSH, IRC, LoRa, Matrix, Slack, and even experimental transports like WebRTC and QUIC/HTTP3.

At its core, Babelfish acts like a **networking “translator”**:

- Every protocol looks the same to the agent (`open → send → receive → close`).
    
- The agent can freely **combine multiple carriers** into hybrid tunnels (multi-modal VPNs).
    
- Protocols are grouped into **layers**, similar to a networking stack, for modularity and extensibility.

---

### 7. Self-Modification Engine

**Autonomous Evolution Through Continuous Integration**

Vera's self-modification capability represents a paradigm shift in AI architecture—enabling **continuous, autonomous evolution** of its own codebase through a sophisticated CI/CD pipeline that ensures reliability, traceability, and controlled innovation. This isn't mere code generation; it's a complete software development lifecycle managed by the AI itself.

### Autonomous Development Workflow

#### Code Synthesis & Generation
```python
# Vera analyzes its own performance and identifies improvement opportunities
improvement_plan = vera.analyze_performance_gaps()
new_module = vera.generate_optimized_code(improvement_plan)

# Example: Vera identifies a bottleneck in memory retrieval
# Generates optimized vector search algorithm with proper error handling
```
- **Pattern Recognition**: Identifies inefficiencies, bugs, or missing features through continuous self-monitoring
- **Context-Aware Generation**: Creates code that integrates seamlessly with existing architecture and follows established patterns
- **Multi-LLM Validation**: Uses different LLM specializations for code generation, review, and optimization

#### Testing & Validation Pipeline
```
1. Unit Test Generation → Auto-creates comprehensive test cases for new code
2. Integration Testing → Validates compatibility with existing modules
3. Performance Benchmarking → Ensures improvements meet efficiency targets
4. Safety & Security Scanning → Checks for vulnerabilities and ethical concerns
```

**Automated Test Suite:**
```python
class SelfModificationTestSuite:
    def test_backwards_compatibility(self):
        """Ensure new code doesn't break existing functionality"""
        assert existing_workflows_still_function()
    
    def test_performance_improvement(self):
        """Verify generated code meets performance targets"""
        assert new_algorithm.faster_than(previous_version)
    
    def test_memory_safety(self):
        """Check for memory leaks and resource management"""
        assert no_memory_leaks_detected()
```

### Version-Controlled Evolution

#### Git-Integrated Workflow
Every autonomous code modification follows a structured version control process:

```bash
# Automated commit messages with context
git commit -m "feat(memory-optimizer): Vector search optimization v2.1.3
- Reduced latency by 42% through improved indexing
- Added fallback mechanisms for corrupted vector stores
- Maintains full backwards compatibility
- Generated by Vera-Agent #session-1756642265"
```

**Version Tagging System:**
- **Workflow Versions**: Every autonomous modification cycle receives a unique version tag
- **Session Linking**: Code changes reference the session and reasoning that prompted them
- **Rollback Capability**: Automatic snapshots enable instant reversion if issues detected

#### Change Management
```python
# Every modification is logged with full context
change_record = {
    "version": "memory-optimizer-v2.1.3",
    "timestamp": "2024-01-15T14:30:00Z",
    "trigger": "performance_analysis_session_1756642265",
    "rationale": "Vector search latency exceeding 200ms threshold",
    "changes": {
        "files_modified": ["/core/memory/vector_search.py"],
        "tests_added": ["test_vector_search_optimization.py"],
        "performance_impact": "42% latency reduction",
        "compatibility": "full_backwards_compatible"
    },
    "validation_results": {
        "unit_tests": "passed",
        "integration_tests": "passed", 
        "performance_tests": "exceeded_targets",
        "security_scan": "clean"
    }
}
```

### Comprehensive Change Logging

#### Archive Integration
All self-modification activities are immutably logged to Layer 4 Archive with forensic-level detail:

**Modification Records Include:**
- **Pre-modification State**: Complete snapshot of codebase before changes
- **Generation Context**: LLM prompts, reasoning chains, and alternative approaches considered
- **Validation Evidence**: Test results, performance metrics, security scans
- **Rollback Procedures**: Automated scripts for reverting changes if needed
- **Impact Analysis**: Predicted and actual effects on system performance

```json
{
  "self_modification_event": {
    "event_id": "sm-20240115-143000-1756642265",
    "version_tag": "memory-optimizer-v2.1.3",
    "initiating_session": "session-1756642265",
    "trigger_condition": "vector_search_latency > 200ms",
    "code_generation": {
      "llm_used": "deep-reasoning-llm",
      "prompt_context": "Optimize vector search while maintaining accuracy...",
      "reasoning_chain": ["identified bottleneck", "researched algorithms", "selected approach"],
      "alternatives_considered": 3
    },
    "testing_results": {
      "unit_tests": {"passed": 15, "failed": 0},
      "integration_tests": {"compatibility": "verified", "performance": "improved"},
      "security_scan": {"vulnerabilities": 0, "warnings": 1}
    },
    "deployment_impact": {
      "performance_change": "+42% speed",
      "memory_usage": "-15%",
      "accuracy_change": "+0% maintained"
    }
  }
}
```

### Observability & Monitoring

#### Real-time Modification Dashboard
```
Self-Modification Monitor 🛠️
──────────────────────────────
Current Version: memory-optimizer-v2.1.3
Active Modifications: 1
Tests Passing: 15/15
Performance Impact: +42% ✅
Rollback Ready: Yes

Recent Changes:
✅ 2024-01-15 14:30 - Vector search optimized
✅ 2024-01-15 11:20 - Memory caching improved  
✅ 2024-01-14 16:45 - Error handling enhanced
```

#### Version-Aware Telemetry
Every workflow execution includes version metadata for precise performance tracking:

```python
# All tool executions tagged with code versions
execution_context = {
    "workflow_id": "weather-analysis-1756642300",
    "code_versions": {
        "memory_layer": "v3.2.1",
        "vector_search": "v2.1.3",  # Newly optimized version
        "tool_orchestrator": "v1.5.2"
    },
    "performance_metrics": {
        "vector_search_latency": "116ms",  # Track improvement
        "memory_usage": "45MB",
        "accuracy_score": 0.94
    }
}
```

### Safety & Control Mechanisms

#### Multi-Layer Approval Process
1. **Automated Validation**: Comprehensive test suites must pass
2. **Performance Gates**: New code must meet or exceed performance thresholds
3. **Security Scanning**: Static analysis and vulnerability detection
4. **Human-in-the-Loop** (Optional): Critical changes can require human approval
5. **Gradual Rollout**: Can deploy to staging environment first

#### Emergency Rollback Protocols
```python
def emergency_rollback(detected_issue):
    """Automated rollback if issues detected post-deployment"""
    if performance_degradation_detected() or errors_spiking():
        revert_to_previous_version()
        log_rollback_event(detected_issue)
        trigger_analysis_for_fix()
```

### Adaptive Learning Cycle

The self-modification system creates a **virtuous cycle of improvement**:

```
Performance Monitoring 
    → Gap Identification
    → Code Generation
    → Validation Testing
    → Versioned Deployment
    → Impact Measurement
    → Further Optimization
```

**Continuous Evolution Metrics:**
- **Code Quality**: Test coverage, complexity metrics, documentation completeness
- **Performance Trends**: Latency, accuracy, resource usage over versions
- **Stability Indicators**: Error rates, crash frequency, recovery times
- **Adaptation Speed**: Time from problem identification to deployed solution

This sophisticated self-modification framework transforms Vera from a static AI system into a **continuously evolving intelligence** that can adapt to new challenges, optimize its own performance, and maintain robust reliability through rigorous version control and comprehensive change tracking—all while providing complete observability into its evolutionary journey.

## Agents

### Triage
### Planner
### Sheduler
### Optimiser
### Evaluator
### Extractor
### Researcher
### Summariser
### Editor
### Model Trainer
### Model Builder
### Security Analyser

## Ingestors 
    Ingestors work at micro level

    Corpus Crawler
    Network Ingestor
    Database Ingestor
    Context ingestor - gathers context from memory layers 0 & 1

## Roadmap
### 1. [[Corpus Crawler]]
#in-developmet

A system for mapping any corpus, including the internet, within the memory of Vera. Analogous to reading

### 2. [[Scheduler]]
#in-developmet 
A system for overall background processing management 

### 3. [Optimiser](<Agents/Agent - Optimiser>)
A System for optimizing prompts, thought processes and workflows


### 4. Security Analyser
#in-developmet 
Dynamic security analysis toolkit

Pulls from knowledge bases and memory to construct the most appropriate test on-the-

### Multi Modal IO

### 5. Whisper TTS

### 6. OCR 

### 7. Image Recognition

### 8. STT Worker

---
## Requirements

Vera is compatible with Windows; however, detailed configuration instructions are currently provided only for Linux, WSL, and macOS environments due to Windows’ additional setup complexities. Windows users may need to adapt the setup process accordingly.
### System Requirements

- **Operating System:** Linux, macOS, or Windows (with WSL)
    
- **Python:** Version 3.9 or higher
	

**CPU Build** ( Linux )

-  CPU: 12 cores+ (24 hyper-threaded) 3Ghz+
	
- GPU: None

- RAM: 16Gb - 32Gb - 150Gb
	
- HDD: 100Gb 
    

**GPU Build** ( Linux )

-  CPU: Unknown
	
- VRAM: 14 - 150Gb
	
- RAM 8Gb 
	
- HDD: 100Gb 

### System Dependencies

[Agentic-Stack-POC](https://github.com/BoeJaker/AgenticStack-POC/tree/main) - Contains all the below required system dependencies and additional UIs

Neo4j Server

Ollama

ChromaDB


### Python Dependencies

Install required Python packages via `pip`. The main dependencies include, but are not limited to:

    
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
## Installation

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

### Standalone Apps

#### Terminal
```bash
cd <your/path/to/vera>

python3 ./vera.py
```
#### Web Server
```bash
cd <your/path/to/vera>

streamlit ./ui.py

chrome-browser localhost:8000
```
#### Python Module

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

### Docker Stack

```bash
cd <your/path/to/vera>

docker compose up
```

### Makefile

A makefile is included to expidite common install & tasks

---

## Configuration

### Vera
### Models

### Proactive Thought (PAT)
###

### Toolchain Executor (TCE)
###

### Tools
###

### Web UI

---

## Usage

### Flags & System Commands
---
Use:

    /\<command> 
in chat prompts
    
    --<flag_name> 
at the command line

| Flag  /Command  |     | Description                                        |
| --------------- | --- | -------------------------------------------------- |
| --triage_memory |     | Does triage have memory of past interactions y/n?  |
| --forgetful     |     | No memories will be saved or recalled this session |
| --dumbledore    |     | Wont respond to questions - hes dead harry         |
| --replay        |     | Replays the last plan                              |
|                 |     |                                                    |

### Makefile

A makefile is included to expidite common administration tasks

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

## Performance Optimisation

### Performance Unit Tests
\<how to use performance unit tests>
### CPU Pinning
\<CPU Pinning best practice>
### NUMA
\<NUMA best practice>
### hugepages
\<hugepages best practice>
### VM
\<VM best practice>

---
## Extending Vera

### Tools

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


### Agents

You can add new agents by
```python

```

### Ingestors

You can add new agents by
```python

```

---
## Contributing

Vera is designed to be extensible and modular. Here are ways to contribute:

- **Add new tools:** Implement new `Tool` objects with clearly defined inputs and outputs.
    
- **Improve memory models:** Experiment with alternative vector DBs or memory encoding strategies.
    
- **Enhance planning algorithms:** Optimize or replace the tool chain planner for more efficient workflows.
    
- **Expand self-modification capabilities:** Enable more robust and safe code generation and auto-updating.
    
- **Improve UX:** Add richer streaming output, UI components, or integrations.
    

---

## Safeguarding & Data Privacy



---
## FAQ

**Q: What LLMs does Vera support?**  
A: Vera is currently built around Ollama models (`gemma2`, `gemma3`, `gpt-oss`), but you can adapt it for any compatible LLM with a Python SDK or API.

**Q: Can Vera run headless?**  
A: Yes. Vera is designed for command-line and backend automation, but can be integrated into GUIs or web apps.

**Q: Is Vera safe to run self-modifying code?**  
A: Self-modification is sandboxed and requires careful review. Vera includes safeguards, but users should always review generated code before production use.

---

## Known Issues

**TTS Pacing** - On slower hardware the TTS engine may talk faster than the LLM can generate

**LLM Reasoning not Visible** - If an LLM has reasoning built in ( i.e. deepseek, gpt-oss) it will not display the reasoning in the web or terminal UI leading to a large gap between a query being accepted and answer being given.

---
## License

See the LICENSE file in the root directory of tis project.

---

## Contact & Support

For questions, feature requests, or help, open issues on the GitHub repo or contact [[your-email@example.com](mailto:your-email@example.com)].

---

## Performance Tiers

| Tier | CPU | RAM | Storage | VRAM | Recommended Use |
|------|-----|-----|---------|------|-----------------|
| **Basic** | 8 cores | 16GB | 100GB | - | Development & testing |
| **Standard** | 12+ cores | 32GB | 100GB | - | Production CPU build |
| **Advanced** | 16+ cores | 64GB | 200GB | 14GB+ | GPU-accelerated |
| **Enterprise** | 24+ cores | 150GB+ | 500GB+ | 80GB+ | Large-scale deployment |

## Model Compatibility

| Model Type | Example Models | Memory | Use Case | Status |
|------------|----------------|---------|----------|--------|
| **Fast LLM** | Mistral 7B, Gemma2 2B | 4-8GB | Triage, quick tasks | ✅ Supported |
| **Intermediate** | Gemma2 9B, Llama 8B | 8-16GB | Tool execution | ✅ Supported |
| **Deep LLM** | Gemma3 27B, GPT-OSS 20B | 16-32GB | Complex reasoning | ✅ Supported |
| **Specialized** | CodeLlama, Math models | Varies | Domain-specific | 🔄 Partial |

## Roadmap Timeline

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