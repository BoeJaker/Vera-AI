Based on the current research and best practices in LLM agent memory systems, here are several advanced improvements you could implement:

## 🧠 Advanced Memory Architecture Improvements

# TODO
each node/edge has a scratchpad area for the AI to comment
nouncunks can be vectorised
runtime vector edges that can be generated upon request in the UI showing semantic edges

### 1. **Hierarchical Memory Consolidation**
Implement automatic abstraction of general principles from specific episodes, creating increasingly sophisticated semantic memory over time, with mathematical models that dynamically quantify memory consolidation considering contextual relevance, elapsed time, and repetition.

```python
class MemoryConsolidator:
    def __init__(self, consolidation_threshold=0.7, decay_rate=0.1):
        self.consolidation_threshold = consolidation_threshold
        self.decay_rate = decay_rate
    
    def calculate_consolidation_score(self, memory_item, current_time, access_count):
        """Calculate consolidation score based on recency, frequency, and relevance"""
        time_factor = math.exp(-self.decay_rate * (current_time - memory_item.created_at))
        frequency_factor = math.log(1 + access_count)
        return time_factor * frequency_factor
    
    def promote_memories(self, session_memories):
        """Automatically promote high-scoring memories to long-term"""
        for memory in session_memories:
            score = self.calculate_consolidation_score(memory, time.time(), memory.access_count)
            if score > self.consolidation_threshold:
                yield memory
```

### 2. **Adaptive Forgetting Mechanism**
Implement compression strategies that mirror how the brain consolidates information, allowing the system to forget irrelevant details while preserving important patterns.

```python
class AdaptiveForgetting:
    def __init__(self, importance_threshold=0.3):
        self.importance_threshold = importance_threshold
    
    def calculate_memory_importance(self, memory_item, related_memories, recent_queries):
        """Calculate importance based on connections and relevance to recent queries"""
        connection_score = len(related_memories) / 10  # Normalized connection count
        query_relevance = self._calculate_query_relevance(memory_item, recent_queries)
        recency_score = self._calculate_recency_score(memory_item)
        
        return (connection_score + query_relevance + recency_score) / 3
    
    def should_forget(self, memory_item, context):
        """Decide whether a memory should be forgotten or compressed"""
        importance = self.calculate_memory_importance(memory_item, context.related, context.queries)
        return importance < self.importance_threshold
```

### 3. **Dynamic Memory Cue Recall**
Adopt human memory cue recall as a trigger for accurate and efficient memory recall.

```python
class CueBasedRecall:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
        self.cue_threshold = 0.8
    
    def extract_memory_cues(self, current_context, conversation_history):
        """Extract relevant cues from current context that might trigger memories"""
        cues = []
        # Extract entities, emotions, topics, temporal markers
        entities = self._extract_entities(current_context)
        emotions = self._extract_emotional_context(current_context)
        topics = self._extract_topics(current_context)
        
        return {"entities": entities, "emotions": emotions, "topics": topics}
    
    def trigger_recall(self, cues, memory_store):
        """Use cues to trigger relevant memory recall"""
        triggered_memories = []
        for cue_type, cue_values in cues.items():
            for cue in cue_values:
                memories = memory_store.search_by_cue(cue, cue_type)
                triggered_memories.extend(memories)
        
        return self._rank_and_filter_memories(triggered_memories)
```

### 4. **Multi-Modal Memory Integration**
Support different types of memory beyond text:

```python
class MultiModalMemory:
    def __init__(self):
        self.modalities = {
            "text": TextMemoryHandler(),
            "image": ImageMemoryHandler(),
            "audio": AudioMemoryHandler(),
            "structured": StructuredDataHandler(),
            "temporal": TemporalMemoryHandler()
        }
    
    def store_multimodal_memory(self, content, modality, metadata):
        """Store memory with appropriate modality handler"""
        handler = self.modalities.get(modality)
        if handler:
            return handler.store(content, metadata)
        raise ValueError(f"Unsupported modality: {modality}")
    
    def cross_modal_search(self, query, target_modalities):
        """Search across multiple modalities with cross-modal embeddings"""
        results = {}
        for modality in target_modalities:
            if modality in self.modalities:
                results[modality] = self.modalities[modality].search(query)
        return self._fuse_cross_modal_results(results)
```

### 5. **Reinforcement Learning for Memory Management**
Use reinforcement learning to empower LLM agents with active, data-efficient memory management.

```python
class RLMemoryManager:
    def __init__(self):
        self.q_table = {}  # State-action values for memory operations
        self.learning_rate = 0.1
        self.epsilon = 0.1  # Exploration rate
    
    def choose_memory_action(self, state):
        """Choose memory action (store, recall, forget, consolidate) based on RL policy"""
        if random.random() < self.epsilon:
            return random.choice(["store", "recall", "forget", "consolidate"])
        
        state_key = self._state_to_key(state)
        if state_key not in self.q_table:
            self.q_table[state_key] = {action: 0 for action in ["store", "recall", "forget", "consolidate"]}
        
        return max(self.q_table[state_key], key=self.q_table[state_key].get)
    
    def update_policy(self, state, action, reward, next_state):
        """Update Q-values based on action outcomes"""
        state_key = self._state_to_key(state)
        next_state_key = self._state_to_key(next_state)
        
        if state_key not in self.q_table:
            self.q_table[state_key] = {a: 0 for a in ["store", "recall", "forget", "consolidate"]}
        
        current_q = self.q_table[state_key][action]
        max_next_q = max(self.q_table.get(next_state_key, {}).values(), default=0)
        
        self.q_table[state_key][action] = current_q + self.learning_rate * (
            reward + 0.9 * max_next_q - current_q
        )
```

### 6. **Temporal Memory Reasoning**
Address temporal reasoning challenges which current systems lag behind human levels by 73%.

```python
class TemporalMemoryManager:
    def __init__(self):
        self.timeline = defaultdict(list)
        self.temporal_relationships = ["before", "after", "during", "overlaps", "contains"]
    
    def add_temporal_memory(self, memory_item, timestamp, duration=None):
        """Add memory with temporal context"""
        temporal_node = {
            "memory": memory_item,
            "timestamp": timestamp,
            "duration": duration,
            "temporal_links": []
        }
        self.timeline[timestamp].append(temporal_node)
        self._update_temporal_relationships(temporal_node)
    
    def query_temporal_context(self, query, time_range=None, temporal_relation=None):
        """Query memories with temporal constraints"""
        if time_range:
            start_time, end_time = time_range
            relevant_times = [t for t in self.timeline.keys() if start_time <= t <= end_time]
        else:
            relevant_times = self.timeline.keys()
        
        results = []
        for timestamp in relevant_times:
            for temporal_node in self.timeline[timestamp]:
                if self._matches_temporal_query(temporal_node, query, temporal_relation):
                    results.append(temporal_node)
        
        return sorted(results, key=lambda x: x["timestamp"])
```

### 7. **Memory Compression and Summarization**
Implement intelligent compression for long-term storage:

```python
class MemoryCompressor:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.compression_ratios = {"low": 0.8, "medium": 0.5, "high": 0.2}
    
    def compress_memory_cluster(self, memory_cluster, compression_level="medium"):
        """Compress related memories into a summary while preserving key information"""
        ratio = self.compression_ratios[compression_level]
        
        # Extract key themes and entities
        themes = self._extract_themes(memory_cluster)
        entities = self._extract_entities(memory_cluster)
        temporal_markers = self._extract_temporal_info(memory_cluster)
        
        # Generate compressed summary
        prompt = f"""
        Compress the following related memories into a concise summary that preserves:
        - Key themes: {themes}
        - Important entities: {entities}  
        - Temporal context: {temporal_markers}
        - Critical relationships and outcomes
        
        Original memories: {memory_cluster}
        Target length: {int(len(str(memory_cluster)) * ratio)} characters
        """
        
        compressed_summary = self.llm_client.generate(prompt)
        return {
            "summary": compressed_summary,
            "original_count": len(memory_cluster),
            "compression_ratio": ratio,
            "preserved_entities": entities,
            "themes": themes
        }
```

### 8. **Memory Quality Assessment**
Add quality metrics and validation:

```python
class MemoryQualityAssessor:
    def __init__(self):
        self.quality_metrics = [
            "coherence", "relevance", "completeness", 
            "temporal_accuracy", "factual_consistency"
        ]
    
    def assess_memory_quality(self, memory_item, context):
        """Assess memory quality across multiple dimensions"""
        scores = {}
        
        scores["coherence"] = self._assess_coherence(memory_item.text)
        scores["relevance"] = self._assess_relevance(memory_item, context)
        scores["completeness"] = self._assess_completeness(memory_item)
        scores["temporal_accuracy"] = self._assess_temporal_accuracy(memory_item)
        scores["factual_consistency"] = self._assess_factual_consistency(memory_item, context)
        
        overall_score = sum(scores.values()) / len(scores)
        
        return {
            "overall_score": overall_score,
            "dimension_scores": scores,
            "recommendations": self._generate_quality_recommendations(scores)
        }
    
    def filter_low_quality_memories(self, memories, threshold=0.6):
        """Filter out memories below quality threshold"""
        high_quality_memories = []
        for memory in memories:
            quality = self.assess_memory_quality(memory, {})
            if quality["overall_score"] >= threshold:
                high_quality_memories.append(memory)
        return high_quality_memories
```

### 9. **Distributed Memory Architecture**
For scalability, implement distributed memory across multiple nodes:

```python
class DistributedMemoryManager:
    def __init__(self, node_configs):
        self.nodes = {}
        self.memory_router = MemoryRouter()
        
        for node_id, config in node_configs.items():
            self.nodes[node_id] = MemoryNode(node_id, config)
    
    def route_memory_operation(self, operation, memory_item):
        """Route memory operations to appropriate nodes"""
        target_node = self.memory_router.select_node(memory_item, operation)
        return self.nodes[target_node].execute_operation(operation, memory_item)
    
    def replicate_critical_memories(self, memory_items, replication_factor=3):
        """Replicate important memories across multiple nodes"""
        for memory in memory_items:
            target_nodes = self.memory_router.select_replication_nodes(
                memory, replication_factor
            )
            for node_id in target_nodes:
                self.nodes[node_id].store_replica(memory)
```

### 10. **Memory Analytics and Insights**
Add analytics to understand memory usage patterns:

```python
class MemoryAnalytics:
    def __init__(self, memory_system):
        self.memory_system = memory_system
        self.metrics_collector = MetricsCollector()
    
    def generate_memory_insights(self):
        """Generate insights about memory usage and patterns"""
        insights = {
            "memory_growth_rate": self._calculate_growth_rate(),
            "most_accessed_memories": self._get_top_accessed_memories(),
            "memory_cluster_analysis": self._analyze_memory_clusters(),
            "temporal_access_patterns": self._analyze_temporal_patterns(),
            "quality_trends": self._analyze_quality_trends(),
            "consolidation_opportunities": self._identify_consolidation_opportunities()
        }
        
        return insights
    
    def recommend_optimizations(self):
        """Recommend memory system optimizations"""
        insights = self.generate_memory_insights()
        recommendations = []
        
        if insights["memory_growth_rate"] > 0.1:  # Growing too fast
            recommendations.append("Consider more aggressive memory consolidation")
        
        if len(insights["consolidation_opportunities"]) > 100:
            recommendations.append("Run memory consolidation job")
        
        return recommendations
```


### Overview

The Memory Explorer transforms Vera's complex memory structure into an intuitive, interactive visualization that enables:

- **Real-time exploration** of the knowledge graph's entities and relationships
- **Temporal analysis** of memory evolution and patterns over time  
- **Hybrid data access** combining graph relationships with vector store content
- **Subgraph isolation** for focused analysis of specific memory neighborhoods
- **Semantic search** across both structured and unstructured memory content

### Core Architecture

#### Visualization Engine
- **PyVis Integration**: Powered by PyVis network visualization with custom enhancements
- **Streamlit Dashboard**: Web-based interface for interactive memory exploration
- **Enhanced HTML Components**: Custom JavaScript addons for rich interactivity
- **Real-time Physics Simulation**: Force-directed layouts with temporal weighting

#### Data Integration Layer
```python
# Dual data source integration
neo4j_driver = GraphDatabase.driver("bolt://localhost:7687")
vector_client = VectorClient(persist_dir="./chroma_store")

# Unified query execution
results = execute_hybrid_query(neo4j_query, vector_search)
```

#### Temporal Analysis System
- **Timestamp Extraction**: Automatic parsing of creation times from node IDs
- **Multiple Layout Algorithms**: Time-based positioning strategies
- **Time Range Filtering**: Dynamic filtering by creation periods
- **Evolution Tracking**: Visualization of memory growth patterns

---

### Key Features

#### 🔍 Interactive Graph Exploration

| Feature | Capability | Implementation |
|---------|------------|----------------|
| **Intelligent Search** | Real-time node search across labels, properties, and content | Semantic matching with hybrid indexing |
| **Dynamic Filtering** | Relationship type filtering with cascade options | Real-time edge filtering with isolated node detection |
| **Rich Node Inspection** | Detailed property panels with vector content | Sidebar display with ChromaDB integration |
| **Subgraph Extraction** | Focused neighborhood analysis around selected nodes | Cypher queries with configurable depth |
| **Multiple Visual Styles** | Card view, boxes, circles, diamonds, and custom shapes | PyVis node styling with dynamic sizing |

#### ⏰ Temporal Visualization

**Layout Algorithms:**
- **Temporal Horizontal**: Oldest nodes on left, newest on right with vertical stacking
- **Temporal Vertical**: Oldest at top, newest at bottom with horizontal distribution  
- **Hierarchical Time**: Time-based levels with relationship-aware positioning
- **Circular Time**: Radial arrangement ordered by creation timestamp
- **Force-Directed with Time Weights**: Physics simulation with temporal influence factors

**Time Filtering:**
```python
# Dynamic time range queries
time_filter = "Last Week"
custom_start = datetime.now() - timedelta(days=7)
custom_end = datetime.now()

where_clause = get_time_range_query_clause(time_filter, custom_start, custom_end)
```

#### 🎨 Visualization Customization

**Color Schemes:**
- **Pastel Palette**: Soft, distinct colors for clear differentiation
- **Material Design**: Google Material color palette for professional appearance
- **Vibrant Colors**: High-contrast, energetic coloring for emphasis
- **HSL-Based**: Hue-systematic coloring for categorical organization

**Node Styling:**
- **Dynamic Sizing**: Node size proportional to connection degree
- **Label-Based Coloring**: Consistent colors for same entity types
- **Mass-Based Physics**: Heavier nodes for high-degree hubs
- **Enhanced Tooltips**: Rich hover information with property previews

#### 🔗 Vector Store Integration

**ChromaDB Browser:**
- **Collection Overview**: Browse all vector collections with sample content
- **Semantic Search**: Cross-collection search with similarity scoring
- **Document Inspection**: Full content viewing with metadata
- **Real-time Querying**: Live search across all vector stores

**Hybrid Data Display:**
```
1. Graph Structure (Neo4j) → Entity relationships and properties
2. Semantic Content (ChromaDB) → Document chunks and embeddings  
3. Unified Property Inspection → Combined view in detail panels
```

### Technical Implementation

#### Data Flow Architecture
```python
def create_enhanced_visualization(neo4j_rows, vector_data, layout_type="temporal"):
    # 1. Build network graph from Neo4j results
    net, nodes_data = create_graph_visualization(neo4j_rows, layout_type=layout_type)
    
    # 2. Enhance with vector store content
    vector_content = fetch_vector_content_for_nodes(nodes_data, vector_client)
    
    # 3. Generate interactive HTML with custom addons
    interactive_html = create_enhanced_graph_html(net, vector_content)
    
    return interactive_html, nodes_data
```

#### Performance Optimizations
- **Node Capping**: Configurable maximum nodes (default: 5000) to prevent browser overload
- **Lazy Loading**: Vector content loaded on-demand during node inspection
- **Connection Counting**: Smart edge length calculation based on node degree
- **Efficient Serialization**: Custom serialization for Neo4j objects and complex types

#### Error Resilience
- **Graceful Degradation**: Continues operation with partial data availability
- **Corrupted Index Recovery**: Automatic skipping of inaccessible ChromaDB collections
- **Robust Timestamp Parsing**: Multiple pattern matching for timestamp extraction
- **Property Sanitization**: Safe handling of complex and nested data types

---

### Usage Examples

#### Basic Memory Exploration
```python
# Initialize the explorer
from memory_explorer import create_graph_visualization, VectorClient

# Create visualization with temporal layout
net, nodes_data = create_graph_visualization(
    neo4j_rows,
    color_scheme="pastel", 
    layout_type="temporal_horizontal",
    max_nodes=2000
)

# Display in Streamlit
components.html(interactive_html, height=900)
```

#### Advanced Temporal Analysis
```python
# Analyze memory evolution over time
time_filter = "Last Month"
custom_range = (datetime(2024, 1, 1), datetime(2024, 1, 31))

# Execute time-filtered query
cypher_query = f"""
MATCH (n) 
{get_time_range_query_clause("Custom Range", *custom_range)}
OPTIONAL MATCH (n)-[r]->(m) 
RETURN n, r, m 
LIMIT 1000
"""

# Visualize with hierarchical time layout
execute_query_and_display(
    driver, vector_client, cypher_query,
    layout_type="hierarchical_time"
)
```

#### Vector Store Integration
```python
# Browse ChromaDB collections
def browse_collection(collection_name):
    col = vector_client.get_collection(collection_name)
    items = col.get(limit=50, include=["documents", "metadatas"])
    
    # Display in expandable sections
    for i, (doc_id, content) in enumerate(zip(items["ids"], items["documents"])):
        with st.expander(f"Document {i+1}: {doc_id}"):
            st.text_area("Content", value=content, height=150)
```

---

### Integration Points

#### Memory Layer Connectivity
- **Layer 3 Access**: Direct Neo4j + ChromaDB integration for long-term knowledge
- **Session Context**: Working memory visualization with session-scoped data
- **Macro Buffer Support**: Cross-sessional associative recall visualization
- **External Knowledge**: Layer 5 API data integration and display

#### Tool Chain Integration
```
Memory Explorer → Tool Chain Planner → Automated Analysis

1. Visual pattern detection in memory graph
2. Automated subgraph extraction for focused analysis  
3. Tool chain generation for memory optimization
4. Results visualization and impact assessment
```

#### Proactive Focus Management
- **Memory Gap Detection**: Visual identification of disconnected components
- **Relationship Pattern Analysis**: Discovery of emerging connection patterns
- **Temporal Trend Visualization**: Tracking of memory evolution for proactive planning

---

### Component Status

| Component | Status | Dependencies | Notes |
|-----------|--------|--------------|-------|
| **Graph Visualization Core** | ✅ Production | PyVis, Streamlit | Stable with enhanced interactivity |
| **Temporal Layout System** | ✅ Production | Custom algorithms | Multiple layout strategies |
| **ChromaDB Integration** | ✅ Production | ChromaDB client | Full collection browsing |
| **Neo4j Connectivity** | ✅ Production | Neo4j Python driver | Optimized query execution |
| **Streamlit Dashboard** | ✅ Production | Streamlit components | Responsive web interface |
| **Advanced Filtering** | ✅ Production | Real-time updates | Cascade and type filters |
| **Vector Content Display** | ✅ Production | Metadata binding | Hybrid data presentation |

### Configuration

#### Environment Setup
```bash
# Required dependencies
pip install streamlit pyvis neo4j chromadb

# Neo4j connection
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j" 
NEO4J_PASSWORD="your_password"

# ChromaDB storage
CHROMA_PERSIST_DIR="./chroma_store"
```

#### Performance Tuning

```python
# Visualization settings
VISUALIZATION_CONFIG = {
    "max_nodes": 5000,           # Prevent browser overload
    "default_physics": True,     # Enable force-directed layout
    "node_size_base": 14,        # Base node size
    "edge_length_base": 200,     # Base edge length
    "color_scheme": "pastel",    # Default coloring
    "layout_type": "default"     # Default layout algorithm
}
```
# Hybrid Memory System - Documentation

A two-tier memory architecture combining long-term graph storage with session-based episodic memory, enhanced with dynamic NLP extraction and semantic vector search.

## Overview

This system implements a hybrid memory model consisting of:

- **Long-term Memory (Tier 1)**: Neo4j graph database storing persistent knowledge graphs with semantic relationships
- **Short-term Memory (Tier 2)**: Session-based in-memory and vector store for contextual, temporal data
- **Vector Store**: ChromaDB for semantic similarity search and document retrieval
- **NLP Engine**: Dynamic entity and relationship extraction without fixed schemas
- **Archive**: JSONL logging for auditability and recovery

## Installation

### Prerequisites

- Python 3.8+
- Neo4j 5.x (local or remote)
- Docker (optional, for Neo4j)

### Dependencies

```bash
pip install neo4j chromadb pydantic spacy sentence-transformers scikit-learn langchain langchain-community
python -m spacy download en_core_web_sm
```

### Docker Setup (Neo4j)

```bash
docker run --name neo4j -p7474:7474 -p7687:7687 -d \
  -e NEO4J_AUTH=neo4j/testpassword \
  neo4j:5.22

# Start/stop
docker start neo4j
docker stop neo4j
```

## Architecture

### Core Components

#### 1. **HybridMemory API** (`HybridMemory` class)
Main interface for all memory operations. Manages both tiers transparently.

```python
from memory import HybridMemory

mem = HybridMemory(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="testpassword",
    chroma_dir="./chroma_store",
    archive_jsonl="./memory_archive.jsonl",
    enable_llm_enrichment=False
)
```

#### 2. **GraphClient** (Neo4j wrapper)
Handles all graph database operations with automatic constraint management.

**Key Methods:**
- `upsert_entity()` - Create/update nodes
- `upsert_edge()` - Create/update relationships
- `get_subgraph()` - Extract knowledge subgraphs
- `link_session_to_entity()` - Connect sessions to entities

#### 3. **VectorClient** (ChromaDB wrapper)
Manages semantic vector storage and similarity search.

**Key Methods:**
- `get_collection()` - Get or create collection
- `add_texts()` - Add documents with embeddings
- `query()` - Semantic similarity search
- `delete()` - Remove documents

#### 4. **NLPExtractor** (Dynamic schema extraction)
Extracts entities and relationships using spaCy and transformers without pre-defined schemas.

**Key Methods:**
- `extract_entities()` - Named entities + noun chunks with embeddings
- `extract_relations()` - Dependency-based relationship discovery
- `cluster_entities()` - Find duplicates using semantic similarity (DBSCAN)
- `normalize_entity()` - Canonical form selection from clusters

## Usage Guide

### Session Management

Sessions represent temporal contexts for episodic memory.

```python
# Start a session
session = mem.start_session(
    session_id="conv_001",
    metadata={"agent": "nlp_assistant", "context": "research"}
)

# Add memories during session
mem.add_session_memory(
    session_id=session.id,
    text="Important finding about machine learning",
    node_type="Thought",
    labels=["Research", "AI"],
    metadata={"topic": "ML"},
    auto_extract=True  # Automatically extract entities
)

# End session
mem.end_session(session.id)
```

### NLP Extraction

Automatically extract structured knowledge from unstructured text.

```python
text = """
Apple Inc. announced a partnership with Microsoft Corporation.
Tim Cook, CEO of Apple, will meet with Satya Nadella next week.
The collaboration focuses on AI and cloud technologies.
"""

extraction = mem.extract_and_link(
    session_id=session.id,
    text=text,
    auto_promote=True  # Move high-confidence extractions to long-term
)

# Results include:
# - Extracted entities with embeddings
# - Clustered entity groups (handles variants)
# - Dependency-based relationships
# - Confidence scores
```

### Long-term Memory Operations

#### Storing Entities

```python
mem.upsert_entity(
    entity_id="org_apple",
    etype="Organization",
    labels=["Company", "Tech"],
    properties={
        "name": "Apple Inc.",
        "industry": "Technology",
        "founded": "1976"
    }
)
```

#### Linking Entities

```python
# Direct linking
mem.link(
    src="org_apple",
    dst="person_tim_cook",
    rel="EMPLOYS",
    properties={"role": "CEO", "since": 2011}
)

# Linking by property values
mem.link_by_property(
    src_property="name",
    src_value="Apple Inc.",
    dst_property="name",
    dst_value="Tim Cook",
    rel="EMPLOYS"
)
```

#### Attaching Documents

```python
mem.attach_document(
    entity_id="org_apple",
    doc_id="doc_apple_2024_report",
    text="Full annual report content...",
    metadata={"year": 2024, "type": "annual_report"}
)
```

#### Semantic Search

```python
results = mem.semantic_retrieve(
    query="AI partnerships and collaborations",
    k=5,
    where={"type": "partnership"}  # Optional metadata filter
)

for hit in results:
    print(f"{hit['id']}: {hit['text'][:200]}...")
    print(f"Distance: {hit['distance']}")
```

### Subgraph Extraction

Extract focused knowledge subgraphs for specific entities.

```python
subgraph = mem.extract_subgraph(
    seed_entity_ids=["org_apple", "org_microsoft"],
    depth=2  # 2-hop neighborhood
)

print(f"Nodes: {len(subgraph['nodes'])}")
print(f"Relationships: {len(subgraph['rels'])}")
```

### File Storage and Retrieval

Store and retrieve files with automatic chunking and semantic indexing.

```python
# Store file
file_id = mem.store_file(
    file_path="./documents/research_paper.pdf",
    chunk_size=1000,
    chunk_overlap=100
)

# Retrieve with semantic query
results = mem.retrieve_file(
    file_id=file_id,
    query="machine learning algorithms",
    top_k=3
)

# Get full content
content = mem.retrieve_file(file_id=file_id, query=None)
```

## Data Models

### Entity (Node)

```python
{
    "id": "unique_identifier",
    "type": "Category",
    "labels": ["Label1", "Label2"],
    "properties": {
        "name": "Display Name",
        "created_at": "2024-01-15T10:30:00",
        "source_process": "module:function",
        ...custom properties
    }
}
```

### Relationship (Edge)

```python
{
    "src": "source_node_id",
    "dst": "destination_node_id",
    "rel": "RELATIONSHIP_TYPE",
    "properties": {
        "confidence": 0.95,
        "context": "Source context string",
        ...custom properties
    }
}
```

### Extracted Entity

```python
{
    "text": "Entity text",
    "label": "ENTITY_TYPE",  # Dynamic label (PERSON, ORG, NOUN_CHUNK, etc.)
    "span": (start_char, end_char),
    "confidence": 0.85,
    "embedding": [0.1, 0.2, ...]  # Semantic embedding
}
```

### Extracted Relation

```python
{
    "head": "Apple Inc.",
    "tail": "Tim Cook",
    "relation": "EMPLOYS",
    "confidence": 0.78,
    "context": "Sentence containing the relationship"
}
```

## Configuration

### Environment Variables

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="testpassword"
export CHROMA_DIR="./Memory/chroma_store"
export ARCHIVE_PATH="./Memory/archive/memory_archive.jsonl"
```

### NLP Models

Default models used:
- **spaCy**: `en_core_web_sm` (NER, dependency parsing)
- **Embeddings**: `all-MiniLM-L6-v2` (sentence-transformers)

To use different models:

```python
nlp = NLPExtractor(
    spacy_model="en_core_web_lg",
    embedding_model="all-mpnet-base-v2"
)
```

## Performance Considerations

### Graph Scaling

- **Node limit**: 100K+ nodes performant with proper indexing
- **Relationship limit**: 1M+ edges with physics simulation disabled
- **Query depth**: Keep to 2-3 hops for responsive queries

### Vector Store

- Default embedding: 384-dimensional vectors
- Indexed with Chroma's HNSW algorithm
- Collections scale to millions of documents

### NLP Extraction

- Batch processing recommended for large documents
- DBSCAN clustering: O(n log n) with cosine distance
- Entity embeddings cached for reuse

## LLM Enrichment (Optional)

Enable optional LLM-based enhancements via Ollama:

```python
mem = HybridMemory(
    ...,
    enable_llm_enrichment=True,
    ollama_endpoint="http://localhost:11434"
)
```

Supported enrichment:
- Entity normalization (variant consolidation)
- Relationship expansion (implicit relationships)
- Contextual metadata generation
- Relationship validation
- Subgraph summarization

## Visualization & Dashboard

Interactive Streamlit dashboard for exploration:

```bash
streamlit run streamlit_dashboard.py
```

Features:
- Real-time graph visualization with pyvis
- Temporal layout options (time-based positioning)
- Semantic search across vector store
- Interactive node inspection
- Subgraph extraction and navigation
- ChromaDB collection browser

## Archive & Recovery

All operations are logged to JSONL archive for auditability:

```json
{
  "ts": "2024-01-15T10:30:45.123456",
  "type": "session_start|entity_upsert|edge_upsert|nlp_extraction|semantic_retrieve",
  "session_id": "...",
  "data": {...}
}
```

Recover from archives:

```python
import json

with open("memory_archive.jsonl") as f:
    for line in f:
        record = json.loads(line)
        # Process historical record
```

## Troubleshooting

### Neo4j Connection Issues

```python
# Test connection
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))
with driver.session() as session:
    result = session.run("RETURN 1")
    print(result.single())
```

### Chroma Index Corruption

```bash
# Rebuild ChromaDB
rm -rf ./chroma_store
# Re-index documents

mem.store_file("./documents/file.txt")
```

### Out of Memory

For large-scale extraction:
- Process documents in smaller chunks
- Use `batch_size` parameter in NLP operations
- Clear old sessions: `mem.end_session(session_id)`

## Examples

See `__main__` section of `memory.py` for complete usage examples including:
- Session-based memory with NLP
- Entity/relationship creation and linking
- File storage and retrieval
- Semantic search
- Subgraph extraction

## API Reference

Full method signatures available in docstrings. Key entry points:

- `HybridMemory.start_session()`
- `HybridMemory.add_session_memory()`
- `HybridMemory.extract_and_link()`
- `HybridMemory.upsert_entity()`
- `HybridMemory.link()`
- `HybridMemory.semantic_retrieve()`
- `HybridMemory.extract_subgraph()`
- `HybridMemory.store_file()`

## License

Specify your license here

## Contributing

Guidelines for contributions and PRs