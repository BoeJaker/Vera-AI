from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

# ============================================================
# Request/Response Models
# ============================================================

class SessionStartResponse(BaseModel):
    session_id: str
    status: str = "started"
    timestamp: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    files: Optional[List[str]] = []


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str


class TTSRequest(BaseModel):
    text: str
    lang: str = "en"

class VectorStoreRequest(BaseModel):
    session_id: str
    collection_name: str

class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    color: str = "#3b82f6"
    properties: Dict[str, Any]
    size: int = 25


class GraphEdge(BaseModel):
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    label: str
    
    class Config:
        populate_by_name = True


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, Any]


class ToolExecutionStep(BaseModel):
    step_number: int
    tool_name: str
    tool_input: str
    tool_output: Optional[str] = None
    status: str  # "pending", "running", "completed", "failed"
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ToolchainExecution(BaseModel):
    execution_id: str
    session_id: str
    query: str
    plan: List[Dict[str, str]]
    steps: List[ToolExecutionStep]
    status: str  # "planning", "executing", "completed", "failed"
    start_time: str
    end_time: Optional[str] = None
    total_steps: int
    completed_steps: int
    final_result: Optional[str] = None


class ToolchainRequest(BaseModel):
    session_id: str
    query: str


# ============================================================
# Request Schemas
# ============================================================

class MemoryQueryRequest(BaseModel):
    """Basic memory query request"""
    session_id: str
    query: str
    k: Optional[int] = Field(default=None, description="Number of results (no limit if None)")
    retrieval_type: str = Field(default="hybrid", description="vector|graph|hybrid")
    filters: Optional[Dict[str, Any]] = None

class HybridRetrievalRequest(BaseModel):
    """Advanced hybrid retrieval request"""
    session_id: str
    query: str
    k_vector: Optional[int] = Field(default=100, description="Number of vector results")
    k_graph: Optional[int] = Field(default=50, description="Number of graph seeds")
    graph_depth: int = Field(default=2, ge=1, le=5)
    include_entities: bool = True
    filters: Optional[Dict[str, Any]] = None

class AdvancedSearchRequest(BaseModel):
    """Comprehensive advanced search request"""
    session_id: str
    query: str
    
    # Search targets
    search_session: bool = Field(default=True, description="Search session vector memory")
    search_long_term: bool = Field(default=True, description="Search long-term vector memory")
    search_graph: bool = Field(default=True, description="Search graph database")
    
    # Filters
    limit: Optional[int] = Field(default=None, description="Maximum results (no limit if None)")
    offset: int = Field(default=0, ge=0, description="Results offset for pagination")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum confidence threshold")
    entity_types: Optional[List[str]] = Field(default=None, description="Filter by entity types")
    relation_types: Optional[List[str]] = Field(default=None, description="Filter by relationship types")
    
    # Date filters
    date_from: Optional[str] = Field(default=None, description="Filter by creation date (ISO format)")
    date_to: Optional[str] = Field(default=None, description="Filter by creation date (ISO format)")
    
    # Additional options
    include_metadata: bool = Field(default=True, description="Include full metadata")
    include_embeddings: bool = Field(default=False, description="Include embedding vectors")
    sort_by: str = Field(default="relevance", description="relevance|confidence|date")
    sort_order: str = Field(default="desc", description="asc|desc")

class EntityExtractionRequest(BaseModel):
    """Entity extraction request"""
    session_id: str
    text: str
    source_node_id: Optional[str] = None
    auto_promote: bool = False

class SubgraphRequest(BaseModel):
    """Subgraph extraction request"""
    session_id: str
    seed_entity_ids: List[str]
    depth: int = Field(default=2, ge=1, le=5)

class PromoteMemoryRequest(BaseModel):
    """Memory promotion request"""
    memory_id: str
    entity_anchor: Optional[str] = None

# Pydantic Models
class NotebookCreate(BaseModel):
    name: str
    description: Optional[str] = None

class NotebookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class NoteSource(BaseModel):
    type: str  # chat_message, graph_node, memory, etc.
    message_id: Optional[str] = None
    role: Optional[str] = None
    timestamp: Optional[str] = None
    node_id: Optional[str] = None
    content: Optional[str] = None

class NoteCreate(BaseModel):
    title: str
    content: str = ""
    source: Optional[NoteSource] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class NoteSearch(BaseModel):
    query: str
    notebook_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    source_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class MemoryQueryResponse(BaseModel):
    """Basic memory query response"""
    results: List[Dict[str, Any]]
    retrieval_type: str
    query: str
    session_id: str
    total_results: int = 0

class AdvancedSearchResponse(BaseModel):
    """Advanced search response with detailed breakdown"""
    results: List[Dict[str, Any]]
    query: str
    session_id: str
    total_results: int
    results_by_source: Dict[str, List[Dict[str, Any]]]
    search_params: Dict[str, Any]
    execution_time_ms: Optional[float] = None

class EntityExtractionResponse(BaseModel):
    """Entity extraction response"""
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    clusters: Dict[str, List[str]]
    session_id: str
    extraction_stats: Optional[Dict[str, Any]] = None

class SubgraphResponse(BaseModel):
    """Subgraph extraction response"""
    session_id: str
    seed_entity_ids: List[str]
    depth: int
    subgraph: Dict[str, Any]
    stats: Dict[str, int]

class EntityListResponse(BaseModel):
    """Entity list response"""
    session_id: str
    entities: List[Dict[str, Any]]
    total: int
    returned: int
    offset: int
    limit: Optional[int]

class RelationshipListResponse(BaseModel):
    """Relationship list response"""
    session_id: str
    relationships: List[Dict[str, Any]]
    total: int
    returned: int
    offset: int
    limit: Optional[int]