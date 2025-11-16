# Composite Knowledge Graph (CKG)

## Overview

The **Composite Knowledge Graph** is Vera's sophisticated, multi-layered memory system that mirrors human cognition by separating volatile context from persistent knowledge. It enables both coherent real-time dialogue and deep, relational reasoning over a vast, self-curated knowledge base.

## Core Principle

**ChromaDB vectorstores** hold the raw textual content
**Neo4j graph** maps the relationships and context between them
**PostgreSQL database** stores an immutable ledger of changes over time, system logs, and telemetry records

## Purpose

The memory system enables Vera to:
- **Maintain context** across sessions and interactions
- **Derive insights** from large datasets quickly
- **Learn continuously** from all experiences
- **Reason relationally** across disparate information
- **Track evolution** of knowledge over time

## Architecture: Five-Layer Memory System

### Layer 1: Short-Term Context Buffer
**Storage:** In-memory
**Purpose:** Immediate conversational context for smooth multi-turn dialogue
**Content:**
- System prompts
- User input
- Last N chat history entries
- Vector store matches
- NLP-extracted data

**Lifespan:** Active conversation only (volatile)

---

### Layer 2: Working Memory (Session Context)
**Storage:** ChromaDB + Neo4j
**Purpose:** Agent's "scratchpad" for internal monologue, observations, and exploratory thinking during a specific task

**Implementation:**
- **Neo4j:** `Session` nodes linked to relevant entities `(Session)-[:FOCUSED_ON]->(Project)`
- **ChromaDB:** Dedicated collection `session_<id>` for full text of thoughts and notes

**Content:**
- Agent's reasoning chains
- Observed facts and code snippets
- Task-specific summarizations
- Intermediate results

**Lifespan:** Single session/task scope

---

### Layer 3: Long-Term Knowledge
**Storage:** ChromaDB (`long_term_docs`) + Neo4j (relationship graph)
**Purpose:** Persistent, semantically searchable library of validated knowledge

**Implementation:**
```
Vector Database (ChromaDB) ←→ Knowledge Graph (Neo4j)
   Full text content              Relationships & context
   Semantic search                Graph traversal
   Metadata pointers              Entity linking
```

**Content:**
- Documents, code examples, notes
- Promoted "thoughts" from sessions
- Entities: `Project`, `Document`, `Person`, `Feature`, `Memory`
- Relationships: `USES`, `AUTHORED_BY`, `CONTAINS`, `RELATED_TO`

**Retrieval Process:**
1. Semantic query performed on ChromaDB
2. Returns relevant text passages + metadata with `neo4j_id`
3. ID used to fetch node and relationship network from Neo4j
4. Agent receives both text AND full relational context

See [Memory Schema](schema.md) for complete entity and relationship definitions.

---

### Layer 4: Temporal Archive & Telemetry Stream
**Storage:** PostgreSQL + optional JSONL logs
**Purpose:** Immutable historical record for auditing, debugging, and model training

**Content:**
- All agent interactions (timestamped)
- Memory creation/modification events
- Graph changes (links, unlinks, deletions)
- Promotion events from Layer 2 → Layer 3
- System telemetry and performance metrics
- Version-tagged code changes

**Features:**
- **Time Travel:** Scroll back through entire graph history
- **Subgraph History:** Track evolution of specific nodes/relationships
- **Audit Trail:** Complete accountability for compliance

---

### Layer 5: External Knowledge Bases
**Storage:** Remote APIs, web services, databases
**Purpose:** Dynamic external data sources extending the graph beyond local boundaries

**Sources:**
- Web documentation (Wikipedia, technical docs)
- Live APIs (weather, stock prices, CVE databases)
- Git repositories
- DNS records, WHOIS data
- Network topology scans

**Implementation:** HTTP/API calls via requests library, cached results stored in Layer 3

---

## Memory Buffer Hierarchy

### Micro Buffer: Working Context Engine
**Status:** In Development
**Purpose:** Real-time cognitive workspace managing immediate attention span

**Features:**
- **Attention Scoring:** Ranks memories by recency, relevance, relationship strength
- **Cognitive Load Management:** Limits active context to 7±2 chunks (Miller's Law)
- **Real-time Pruning:** Drops low-relevance info, promotes high-value context
- **Focus Tracking:** Maintains attention on salient entities during reasoning
- **NLP Processing:** Extracts triplets, URLs, entities, code structures as graph relationships

**Example Use:** While debugging, keeps focus on current function, related variables, and recent stack traces while filtering unrelated docs.

---

### Macro Buffer: Cross-Sessional Associative Engine
**Status:** In Development
**Purpose:** Breaks down session isolation, enabling holistic reasoning across time

**Features:**
- **Graph-Accelerated Search:** Efficiently finds relevant sessions via Neo4j
- **Multi-Collection Vector Search:** Semantic search across session collections
- **Temporal Pattern Recognition:** Identifies idea evolution across sessions
- **Context Bridging:** Connects seemingly disconnected sessions conceptually

**Example Query:**
*"What were all the challenges we faced when integrating service X?"*

Retrieves notes from:
- Initial research sessions
- Debugging logs
- Final summary document

---

### Meta Buffer: Strategic Reasoning Layer
**Status:** In Development
**Purpose:** Executive control system for reasoning about reasoning itself

**Features:**
- **Cognitive Pattern Recognition:** Identifies successful strategies and failure modes
- **Knowledge Gap Analysis:** Detects missing information, contradictions, underspecified concepts
- **Strategic Planning:** Generates learning agendas, research roadmaps
- **Self-Modeling:** Maintains Vera's understanding of its own capabilities/limitations

**Example:** Faced with a novel quantum computing problem:
1. Identifies knowledge gap in quantum mechanics
2. Generates learning plan (papers, simulations, expert knowledge)
3. Executes learning before problem-solving
4. Updates self-model with new quantum capabilities

---

## Promotion Process: From Thought to Knowledge

The key mechanism for learning - transforms ephemeral session data into permanent knowledge:

1. **Identification:** Content in session collection deemed valuable
2. **Curation:** Agent creates new `Memory`, `Entity`, or `Insight` node in Neo4j
3. **NLP Parsing:** Extract entities, relationships, references
4. **Linking:** Node connected to relevant entities via typed relationships
5. **Storage:** Full text inserted into session's Chroma collection with `neo4j_id` metadata

**Data Flow:**
```
Conversation → Layer 1 (Short-Term Buffer)
    ↓
Agent thinks → Layer 2 (Working Memory)
    ↓
Valuable insight → Layer 3 (Long-Term Knowledge via Promotion)
    ↓
Cross-session query → Macro Buffer orchestrates Graph-Accelerated Search
    ↓
Everything logged → Layer 4 (Archive)
```

## Key Files

| File | Purpose |
|------|---------|
| `memory.py` | Core memory system (Neo4j + ChromaDB integration) |
| `memory_v2.py` | Next-generation memory implementation |
| `memory.md` | Comprehensive memory documentation |
| `schema.md` | Complete node and relationship schema (100+ fields) |
| `nlp.py` | NLP extraction for entities and relationships |
| `graph_audit.py` | Memory graph validation and audit tools |
| `cve_ingestor.py` | CVE/vulnerability data ingestion |
| `network_ingestor.py` | Network topology ingestion |
| `archive.py` | Historical record management (Layer 4) |

## Subdirectories

### dashboard/
Interactive Memory Explorer UI for graph visualization and traversal
- See [Dashboard README](dashboard/README.md)

### database server/
Database stack management and utilities
- See [Database Server README](database%20server/README.md)

## Technologies

- **Neo4j** - Graph database for relationships and context
- **ChromaDB** - Vector database for semantic search
- **PostgreSQL** - Immutable archive and telemetry
- **spaCy** - NLP for entity/relationship extraction
- **Sentence Transformers** - Text embeddings
- **DBSCAN** - Clustering for entity normalization

## Usage Examples

### Storing a Memory
```python
from Memory.memory import VeraMemory

memory = VeraMemory()

# Store a new insight
memory.store_insight(
    content="User prefers detailed technical explanations with examples",
    tags=["user_preference", "communication_style"],
    related_entities=["User", "InteractionPattern"]
)
```

### Querying Memory
```python
# Semantic search across long-term knowledge
results = memory.query(
    "How do I implement OAuth2 authentication?",
    top_k=5,
    include_relationships=True
)

for result in results:
    print(f"Content: {result['text']}")
    print(f"Related entities: {result['entities']}")
    print(f"Relationships: {result['relationships']}")
```

### Cross-Sessional Retrieval (Macro Buffer)
```python
# Find all sessions related to a topic
sessions = memory.find_related_sessions(
    topic="authentication",
    time_range="last_3_months"
)

# Get full context from those sessions
context = memory.build_cross_session_context(sessions)
```

### Memory Promotion
```python
# Promote session thought to long-term knowledge
memory.promote_to_long_term(
    session_id="session_abc123",
    thought_id="thought_xyz789",
    create_entity=True,
    entity_type="Insight"
)
```

## Memory Explorer UI

The **Memory Explorer** provides visual traversal of the knowledge graph.

**Features:**
- Interactive graph visualization
- Temporal navigation (scroll through history)
- Entity search and filtering
- Relationship analysis
- Session history timeline
- Network topology visualization
- Codebase structure mapping

**Access:**
```bash
python3 Memory/dashboard/dashboard.py
# Opens on localhost:8501
```

See [Memory Explorer Documentation](dashboard/dashboard.md) for details.

## Ingestors

Ingestors pull external data into the memory system:

### Network Ingestor
```python
from Memory.network_ingestor import NetworkIngestor

ingestor = NetworkIngestor(memory)
ingestor.ingest("192.168.1.0/24")  # Scans network, creates topology graph
```

### CVE Ingestor
```python
from Memory.cve_ingestor import CVEIngestor

ingestor = CVEIngestor(memory)
ingestor.ingest_cve_database()  # Loads vulnerability data into graph
```

## Memory Lifecycle (Planned)

Future feature for automated memory management:

**Stages:**
1. **Discovery** - New information encountered
2. **Promotion** - Validated content moved to long-term storage
3. **Recall** - Retrieved for reasoning tasks
4. **Enrichment** - Relationships and context added over time
5. **Continuous Evaluation** - Relevance and accuracy assessed
6. **Decay** - Unused/outdated memories deprioritized
7. **Archiving** - Historical memories moved to cold storage

## Configuration

Memory behavior configured via environment variables:

```bash
# Neo4j Database
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# ChromaDB Vector Database
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
CHROMA_PATH=./vera_agent_memory

# PostgreSQL Archive
POSTGRES_URL=postgresql://user:pass@localhost:5432/vera_archive
```

## Memory Maintenance

### Backup
```bash
# Neo4j backup
neo4j-admin dump --database=neo4j --to=/backup/vera-memory.dump

# ChromaDB backup
cp -r ./vera_agent_memory /backup/chroma-backup

# PostgreSQL backup
pg_dump vera_archive > /backup/postgres-archive.sql
```

### Cleanup
```bash
# Clear all memories (irreversible!)
python3 -c "from Memory.memory import VeraMemory; VeraMemory().clear_all()"

# Clear only short-term buffer
python3 -c "from Memory.memory import VeraMemory; VeraMemory().clear_short_term()"
```

### Audit
```python
from Memory.graph_audit import GraphAuditor

auditor = GraphAuditor(memory)
report = auditor.run_full_audit()
print(report)  # Shows inconsistencies, orphaned nodes, relationship integrity
```

## Related Documentation

- [Memory System Deep Dive](memory.md)
- [Memory Schema Reference](schema.md)
- [Knowledge Graph Documentation](../Vera%20Assistant%20Docs/Knowledge%20Graph.md)
- [Knowledge Bases Documentation](../Vera%20Assistant%20Docs/Knowledge%20Bases.md)
- [Memory Explorer UI](dashboard/dashboard.md)

## Best Practices

### Tagging
Always tag memories for efficient retrieval:
```python
memory.store_insight(
    content="...",
    tags=["domain:security", "type:vulnerability", "severity:high"]
)
```

### Relationship Quality
Create meaningful, typed relationships:
```python
memory.create_relationship(
    source="User",
    target="Project_X",
    relationship_type="WORKS_ON",
    properties={"role": "lead_developer", "since": "2024-01-01"}
)
```

### Session Hygiene
End sessions properly to trigger promotion:
```python
memory.end_session(
    session_id="session_abc",
    promote_all=False,  # Manual promotion for quality control
    archive=True
)
```

## Contributing

To extend the memory system:
1. Add new entity types to `schema.md`
2. Implement ingestors for new data sources
3. Extend NLP extraction for domain-specific entities
4. Add memory buffer strategies (Micro, Macro, Meta)
5. Implement memory lifecycle policies

---

**Related Components:**
- [Agents](../Agents/) - Use memory for context and learning
- [Toolchain](../Toolchain/) - Memory introspection tools
- [Background Cognition](../BackgroundCognition/) - Proactive memory enrichment
