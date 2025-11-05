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


class MemoryQueryRequest(BaseModel):
    session_id: str
    query: str
    k: int = 5
    retrieval_type: str = "hybrid"  # "vector", "graph", "hybrid"
    filters: Optional[Dict[str, Any]] = None

class MemoryQueryResponse(BaseModel):
    results: List[Dict[str, Any]]
    retrieval_type: str
    query: str
    session_id: str

class EntityExtractionRequest(BaseModel):
    session_id: str
    text: str
    auto_promote: bool = False
    source_node_id: Optional[str] = None

class EntityExtractionResponse(BaseModel):
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    clusters: Dict[str, List[str]]
    session_id: str

class SubgraphRequest(BaseModel):
    session_id: str
    seed_entity_ids: List[str]
    depth: int = 2

class HybridRetrievalRequest(BaseModel):
    session_id: str
    query: str
    k_vector: int = 5
    k_graph: int = 3
    graph_depth: int = 2
    include_entities: bool = True
    filters: Optional[Dict[str, Any]] = None

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
