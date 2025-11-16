# Memory Directory

## Overview

The Memory directory implements Vera's sophisticated multi-layered memory system - a hybrid architecture combining graph databases, vector stores, and temporal archives to create a comprehensive knowledge management system inspired by human cognition.

**Size:** 633KB
**Status:** ✅ Production
**Core Technology:** Neo4j (graph) + ChromaDB (vectors) + PostgreSQL (archive)

---

## Files

### Core Memory System

#### `memory.py` (100KB)
**Purpose:** Main hybrid memory system implementation

**Key Features:**
- Dual storage: Neo4j for relationships, ChromaDB for content
- 4-layer memory architecture (Short-term, Working, Long-term, Archive)
- Dynamic entity/relationship extraction via NLP
- Schema-less entity normalization
- Automatic memory promotion
- Graph-accelerated semantic search

**Core Classes:**
```python
class HybridMemory:
    - Manages Neo4j and ChromaDB connections
    - Handles memory CRUD operations
    - Implements promotion workflow
    - Provides graph traversal methods
```

**Usage:**
```python
from Memory.memory import HybridMemory

memory = HybridMemory()
memory.save_memory(
    text="Important finding about quantum computing",
    memory_type="insight",
    metadata={"project": "quantum_research"}
)
```

---

#### `memory_v2.py`
**Purpose:** Enhanced memory system with advanced features

**Improvements over v1:**
- Better NLP extraction
- Improved relationship scoring
- Enhanced search algorithms
- Temporal navigation support
- Batch operations

---

#### `nlp.py`
**Purpose:** Natural Language Processing for entity/relationship extraction

**Key Features:**
- spaCy-based entity recognition
- Dependency parsing for relationships
- Triplet extraction (subject-predicate-object)
- Custom entity types (Person, Organization, Technology, etc.)
- Relationship typing and scoring

**Core Functions:**
```python
def extract_entities(text: str) -> List[Entity]:
    """Extract named entities from text"""

def extract_relationships(text: str) -> List[Relationship]:
    """Extract relationships between entities"""

def extract_triplets(text: str) -> List[Triplet]:
    """Extract subject-predicate-object triplets"""
```

**Example:**
```python
from Memory.nlp import extract_entities, extract_relationships

text = "Vera uses Neo4j for graph storage"
entities = extract_entities(text)
# [Entity(text='Vera', type='PRODUCT'), Entity(text='Neo4j', type='PRODUCT')]

relationships = extract_relationships(text)
# [Relationship(source='Vera', target='Neo4j', type='USES')]
```

---

#### `graph_audit.py`
**Purpose:** Graph validation and consistency checking

**Key Features:**
- Orphaned node detection
- Dangling relationship cleanup
- Schema validation
- Duplicate detection
- Consistency scoring

**Core Functions:**
```python
def audit_graph() -> Dict[str, Any]:
    """Run complete graph audit"""

def find_orphaned_nodes() -> List[str]:
    """Find nodes with no relationships"""

def validate_schema() -> List[str]:
    """Validate node/relationship types"""

def generate_audit_report() -> str:
    """Generate human-readable audit report"""
```

**Usage:**
```bash
python Memory/graph_audit.py
# Generates: graph_audit_report.json
```

---

#### `archive.py`
**Purpose:** Layer 4 temporal archive and long-term storage

**Key Features:**
- Immutable event logging
- Version history tracking
- Temporal navigation (scroll back in time)
- JSONL streaming backup
- PostgreSQL archival

**Core Classes:**
```python
class MemoryArchive:
    - Archive events to PostgreSQL
    - Stream to JSONL backup
    - Query historical states
    - Restore from archive
```

---

### Ingestors

#### `cve_ingestor.py`
**Purpose:** Ingest CVE (Common Vulnerabilities and Exposures) database

**Key Features:**
- Fetch CVE data from NVD API
- Parse CVE JSON format
- Create CVE nodes in graph
- Link to affected products
- Track severity scores

**Usage:**
```python
from Memory.cve_ingestor import CVEIngestor

ingestor = CVEIngestor()
ingestor.ingest_recent_cves(days=7)
```

---

#### `network_ingestor.py`
**Purpose:** Ingest network topology and scan results

**Key Features:**
- Parse nmap XML output
- Create host/service nodes
- Map network topology
- Link vulnerabilities to services
- Track network changes over time

**Usage:**
```python
from Memory.network_ingestor import NetworkIngestor

ingestor = NetworkIngestor()
ingestor.ingest_nmap_scan("scan_results.xml")
```

---

### Dashboard

See `dashboard/README.md` for Memory Explorer UI documentation.

---

## Memory Architecture

### Layer 1: Short-Term Context Buffer
- **Storage:** In-memory Python list
- **Content:** Last 10-20 message exchanges
- **Lifetime:** Current session only
- **Purpose:** Immediate conversation context

### Layer 2: Working Memory
- **Storage:** Neo4j (Session nodes) + ChromaDB (session_<id> collections)
- **Content:** Agent thoughts, notes, task-specific data
- **Lifetime:** Task/session duration
- **Purpose:** Scratchpad for reasoning

### Layer 3: Long-Term Knowledge
- **Storage:** Neo4j (graph structure) + ChromaDB (long_term_docs)
- **Content:** Entities, relationships, promoted memories
- **Lifetime:** Permanent (until explicitly deleted)
- **Purpose:** Persistent knowledge base

### Layer 4: Temporal Archive
- **Storage:** PostgreSQL + JSONL files
- **Content:** Immutable event log, version history
- **Lifetime:** Permanent, append-only
- **Purpose:** Audit trail, temporal navigation

### Layer 5: External Knowledge Bases
- **Storage:** External APIs and services
- **Content:** Wikipedia, DNS, APIs, web docs
- **Lifetime:** Dynamic, fetched on-demand
- **Purpose:** External sources of truth

---

## Memory Buffers

### Micro Buffer (Tactical)
- **Purpose:** Immediate working context
- **Capacity:** 7±2 chunks (Miller's Law)
- **Features:**
  - Attention scoring
  - Real-time pruning
  - Focus tracking
  - NLP processing

### Macro Buffer (Operational)
- **Purpose:** Cross-sessional retrieval
- **Features:**
  - Graph-accelerated search
  - Multi-collection vector search
  - Temporal pattern recognition
  - Context bridging

### Meta Buffer (Strategic)
- **Purpose:** Self-modeling and strategic reasoning
- **Features:**
  - Cognitive pattern recognition
  - Knowledge gap analysis
  - Strategic planning
  - Self-awareness

---

## Node Types

### Core Types

| Type | Description | Properties |
|------|-------------|------------|
| `Memory` | Generic memory node | text, timestamp, type, metadata |
| `Entity` | Named entity | name, type, properties |
| `Insight` | Derived insight | description, confidence, source |
| `Session` | Conversation session | session_id, start_time, context |
| `Document` | Document reference | title, content_id, url |
| `Project` | Project context | name, goals, status |
| `Person` | Person entity | name, role, contact |
| `Technology` | Technology/tool | name, category, version |

### Relationship Types

| Type | Description | Example |
|------|-------------|---------|
| `CONTAINS` | Containment | (Project)-[:CONTAINS]->(Document) |
| `RELATED_TO` | Generic relation | (Entity)-[:RELATED_TO]->(Entity) |
| `DERIVED_FROM` | Derivation | (Insight)-[:DERIVED_FROM]->(Memory) |
| `USES` | Usage | (Project)-[:USES]->(Technology) |
| `AUTHORED_BY` | Authorship | (Document)-[:AUTHORED_BY]->(Person) |
| `FOCUSED_ON` | Focus | (Session)-[:FOCUSED_ON]->(Project) |
| `EVOLVED_FROM` | Evolution | (Concept)-[:EVOLVED_FROM]->(Concept) |

---

## Database Configuration

### Neo4j Setup

```bash
# Default connection
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

**Indexes:**
```cypher
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX memory_timestamp IF NOT EXISTS FOR (m:Memory) ON (m.timestamp);
CREATE INDEX session_id IF NOT EXISTS FOR (s:Session) ON (s.session_id);
```

---

### ChromaDB Setup

```python
# Default configuration
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
```

**Collections:**
- `long_term_docs` - Main persistent collection
- `session_<id>` - Per-session working memory
- `archive_<date>` - Archived memories

---

### PostgreSQL Setup (Archive)

```sql
CREATE TABLE memory_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    event_type VARCHAR(50),
    neo4j_id VARCHAR(100),
    data JSONB,
    version VARCHAR(20)
);

CREATE INDEX idx_timestamp ON memory_events(timestamp);
CREATE INDEX idx_event_type ON memory_events(event_type);
CREATE INDEX idx_neo4j_id ON memory_events(neo4j_id);
```

---

## Memory Operations

### Save Memory

```python
memory.save_memory(
    text="Completed network security audit",
    memory_type="event",
    metadata={
        "project": "security_assessment",
        "severity": "high",
        "findings": 5
    }
)
```

### Retrieve Context

```python
results = memory.retrieve_context(
    query="network security vulnerabilities",
    max_results=10,
    filters={"project": "security_assessment"}
)
```

### Promote to Long-Term

```python
memory.promote_to_long_term(
    session_id="sess_123",
    memory_ids=["mem_1", "mem_2", "mem_3"]
)
```

### Graph Traversal

```python
# Find related entities
related = memory.find_related_entities(
    entity_id="ent_123",
    relationship_type="RELATED_TO",
    max_depth=2
)

# Traverse paths
paths = memory.find_paths(
    start_entity="Project_A",
    end_entity="Technology_X",
    max_length=3
)
```

---

## Performance Optimization

### Vector Search

```python
# Use HNSW for approximate nearest neighbor
collection.add(
    documents=texts,
    embeddings=embeddings,
    metadatas=metadata,
    ids=ids
)

# Optimize index
collection.modify(hnsw_space="cosine", hnsw_ef=100)
```

### Graph Queries

```cypher
-- Use indexes
MATCH (e:Entity {name: $name})
WHERE e.timestamp > $since
RETURN e

-- Limit depth
MATCH path = (start)-[*1..3]-(end)
RETURN path
LIMIT 100
```

### Batch Operations

```python
# Batch insert
memory.batch_insert_nodes(entities)
memory.batch_insert_relationships(relationships)

# Batch search
results = memory.batch_vector_search(queries)
```

---

## Troubleshooting

### Common Issues

**Neo4j Connection Failed**
```bash
# Check Neo4j is running
curl http://localhost:7474

# Verify credentials
NEO4J_USER=neo4j NEO4J_PASSWORD=password python -c "from Memory.memory import HybridMemory; HybridMemory().test_connection()"
```

**ChromaDB Connection Failed**
```bash
# Check ChromaDB is running
curl http://localhost:8000/api/v1/heartbeat

# Start ChromaDB
docker run -p 8000:8000 chromadb/chroma
```

**Slow Vector Search**
- Reduce embedding dimensions
- Use approximate search (HNSW)
- Implement caching layer
- Batch queries

**Graph Query Timeouts**
- Add indexes to frequently queried properties
- Limit traversal depth
- Use query profiling: `PROFILE <query>`

---

## Testing

```bash
# Test memory operations
pytest tests/unit/test_memory.py

# Test NLP extraction
pytest tests/unit/test_nlp.py

# Test graph audit
python Memory/graph_audit.py

# Performance tests
pytest tests/performance/test_vector_search.py
```

---

## Related Documentation

- [Memory Schema](schema.md)
- [Memory Dashboard](dashboard/README.md)
- [Architecture Overview](../ARCHITECTURE.md#memory-architecture)
- [NLP Processing Guide](../docs/nlp_guide.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
