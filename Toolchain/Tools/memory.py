"""
Memory Introspection Tools for LLM Self-Awareness
Enables the LLM to deeply inspect, traverse, and interact with its own memory graph.

Features:
- Semantic memory search
- Graph traversal and exploration
- Pattern recognition and insights
- Note-taking and annotation
- Entity linking and relationship discovery
- Memory consolidation and summarization
"""

from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class MemorySearchInput(BaseModel):
    """Input schema for semantic memory search."""
    query: str = Field(..., description="Natural language query to search memory")
    k: int = Field(default=10, description="Number of results to return (1-50)")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters as JSON object")
    search_type: str = Field(default="semantic", description="Type: semantic, graph, hybrid")


class EntityInspectInput(BaseModel):
    """Input schema for inspecting specific entities."""
    entity_id: str = Field(..., description="ID of the entity to inspect")
    depth: int = Field(default=1, description="Depth of connections to retrieve (1-3)")
    include_properties: bool = Field(default=True, description="Include all entity properties")


class GraphTraverseInput(BaseModel):
    """Input schema for graph traversal."""
    start_entity_id: str = Field(..., description="Starting entity ID")
    relationship_type: Optional[str] = Field(default=None, description="Filter by relationship type (e.g., MENTIONS, FOLLOWS)")
    max_depth: int = Field(default=2, description="Maximum traversal depth (1-5)")
    direction: str = Field(default="both", description="Direction: outgoing, incoming, both")


class AddNoteInput(BaseModel):
    """Input schema for adding notes/annotations."""
    note_text: str = Field(..., description="The note or insight to record")
    note_type: str = Field(default="insight", description="Type: insight, observation, question, hypothesis, summary")
    linked_entities: Optional[List[str]] = Field(default=None, description="Entity IDs to link this note to")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class AnnotateEntityInput(BaseModel):
    """Input schema for annotating existing entities."""
    entity_id: str = Field(..., description="Entity ID to annotate")
    property_name: str = Field(..., description="Property name to add/update")
    property_value: Any = Field(..., description="Property value")
    annotation_type: str = Field(default="observation", description="Type of annotation")


class FindPatternsInput(BaseModel):
    """Input schema for pattern discovery."""
    pattern_type: str = Field(..., description="Type: clusters, frequent_connections, temporal, co_occurrence")
    entity_types: Optional[List[str]] = Field(default=None, description="Filter by entity types")
    min_frequency: int = Field(default=2, description="Minimum frequency for patterns")


class LinkEntitiesInput(BaseModel):
    """Input schema for creating entity relationships."""
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Relationship type (e.g., RELATED_TO, IMPLIES, CONTRADICTS)")
    properties: Optional[Dict[str, Any]] = Field(default=None, description="Relationship properties")
    confidence: float = Field(default=0.8, description="Confidence score (0.0-1.0)")


class ConsolidateMemoryInput(BaseModel):
    """Input schema for memory consolidation."""
    session_id: str = Field(..., description="Session ID to consolidate")
    consolidation_type: str = Field(default="summarize", description="Type: summarize, cluster, promote")
    threshold: float = Field(default=0.7, description="Similarity threshold for clustering")


class MemoryInsightInput(BaseModel):
    """Input schema for generating insights."""
    focus_area: str = Field(..., description="Area to analyze (e.g., 'recent conversations', 'coding patterns')")
    insight_type: str = Field(default="connections", description="Type: connections, trends, contradictions, gaps")
    time_range: Optional[str] = Field(default=None, description="Time range: today, this_week, this_month, all")


class QueryGraphInput(BaseModel):
    """Input schema for Cypher queries."""
    query_description: str = Field(..., description="Natural language description of what to find")
    entity_types: Optional[List[str]] = Field(default=None, description="Entity types to focus on")
    limit: int = Field(default=10, description="Maximum results")


# ============================================================================
# MEMORY TOOLS CLASS
# ============================================================================

class MemoryTools:
    """
    Comprehensive memory introspection tools for LLM self-awareness.
    Provides deep access to the hybrid memory system.
    """
    
    def __init__(self, agent):
        """
        Initialize memory tools with agent's memory system.
        
        Args:
            agent: Vera agent instance with .mem (HybridMemory)
        """
        self.agent = agent
        self.mem = agent.mem
        self.sess = agent.sess
    
    # ------------------------------------------------------------------------
    # SEARCH & RETRIEVAL TOOLS
    # ------------------------------------------------------------------------
    
    def search_memory(self, query: str, k: int = 10, filters: Optional[Dict] = None, 
                     search_type: str = "semantic") -> str:
        """
        Search memory using semantic similarity or graph queries.
        
        Use this to recall information, find related concepts, or explore what you know.
        Search across all sessions and entities in your knowledge graph.
        
        Returns: JSON with matching memories, entities, and their connections.
        """
        try:
            k = min(max(k, 1), 50)  # Clamp between 1-50
            
            results = {
                "query": query,
                "search_type": search_type,
                "results": []
            }
            
            if search_type in ["semantic", "hybrid"]:
                # Semantic search in long-term memory
                hits = self.mem.semantic_retrieve(query, k=k, where=filters)
                results["semantic_results"] = [
                    {
                        "id": hit["id"],
                        "text": hit["text"][:500],  # Truncate
                        "metadata": hit.get("metadata", {}),
                        "relevance": 1.0 - hit.get("distance", 0.5)
                    }
                    for hit in hits
                ]
            
            if search_type in ["graph", "hybrid"]:
                # Extract entities from query using NLP
                entities, _ = self.mem.nlp.extract_all(query)
                
                if entities:
                    # Find matching entities in graph
                    entity_texts = [e.text for e in entities[:5]]  # Top 5
                    
                    # Search for similar entities in graph
                    graph_hits = []
                    for entity_text in entity_texts:
                        # Semantic search in vector store to find entity IDs
                        vec_hits = self.mem.semantic_retrieve(entity_text, k=5)
                        
                        for hit in vec_hits:
                            entity_id = hit.get("metadata", {}).get("entity_id") or hit["id"]
                            
                            # Get entity details from graph
                            try:
                                subgraph = self.mem.extract_subgraph([entity_id], depth=1)
                                graph_hits.append({
                                    "entity_id": entity_id,
                                    "match_text": entity_text,
                                    "subgraph": subgraph
                                })
                            except:
                                continue
                    
                    results["graph_results"] = graph_hits[:k]
            
            # Add session context if available
            if hasattr(self, 'sess') and self.sess:
                session_hits = self.mem.focus_context(self.sess.id, query, k=min(k, 5))
                results["current_session_context"] = [
                    {
                        "id": hit["id"],
                        "text": hit["text"][:300],
                        "metadata": hit.get("metadata", {})
                    }
                    for hit in session_hits
                ]
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e), "query": query})
    
    def inspect_entity(self, entity_id: str, depth: int = 1, 
                      include_properties: bool = True) -> str:
        """
        Deep inspection of a specific entity and its connections.
        
        Use this to understand what you know about a specific entity,
        see all its relationships, and explore its context in the knowledge graph.
        
        Returns: Complete entity profile with connections and properties.
        """
        try:
            depth = min(max(depth, 1), 3)  # Clamp 1-3
            
            # Get entity subgraph
            subgraph = self.mem.extract_subgraph([entity_id], depth=depth)
            
            # Find the target entity in nodes
            target_node = None
            for node in subgraph.get("nodes", []):
                if node.get("id") == entity_id:
                    target_node = node
                    break
            
            if not target_node:
                return json.dumps({
                    "error": f"Entity {entity_id} not found",
                    "entity_id": entity_id
                })
            
            # Organize connections
            connections = {
                "outgoing": [],
                "incoming": [],
                "bidirectional": []
            }
            
            for rel in subgraph.get("rels", []):
                if not rel:
                    continue
                
                rel_data = {
                    "type": rel.get("type"),
                    "properties": rel.get("properties", {})
                }
                
                if rel.get("start") == entity_id:
                    rel_data["target"] = rel.get("end")
                    connections["outgoing"].append(rel_data)
                elif rel.get("end") == entity_id:
                    rel_data["source"] = rel.get("start")
                    connections["incoming"].append(rel_data)
            
            # Build comprehensive profile
            profile = {
                "entity_id": entity_id,
                "type": target_node.get("properties", {}).get("type"),
                "labels": target_node.get("labels", []),
                "connections": connections,
                "connection_count": {
                    "outgoing": len(connections["outgoing"]),
                    "incoming": len(connections["incoming"]),
                    "total": len(connections["outgoing"]) + len(connections["incoming"])
                },
                "neighborhood_size": len(subgraph.get("nodes", [])) - 1
            }
            
            if include_properties:
                profile["properties"] = target_node.get("properties", {})
            
            # Add semantic context if available
            try:
                entity_text = target_node.get("properties", {}).get("text", entity_id)
                context = self.mem.semantic_retrieve(entity_text, k=3)
                profile["semantic_context"] = [
                    {"text": hit["text"][:200], "relevance": 1.0 - hit.get("distance", 0.5)}
                    for hit in context
                ]
            except:
                pass
            
            return json.dumps(profile, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "entity_id": entity_id
            })
    
    def traverse_graph(self, start_entity_id: str, relationship_type: Optional[str] = None,
                      max_depth: int = 2, direction: str = "both") -> str:
        """
        Traverse the knowledge graph from a starting point.
        
        Use this to explore connections, follow chains of relationships,
        and discover how concepts are linked in your memory.
        
        Returns: Graph traversal results showing the path and discovered entities.
        """
        try:
            max_depth = min(max(max_depth, 1), 5)
            
            # Get subgraph
            subgraph = self.mem.extract_subgraph([start_entity_id], depth=max_depth)
            
            # Filter by relationship type if specified
            if relationship_type:
                filtered_rels = [
                    rel for rel in subgraph.get("rels", [])
                    if rel and rel.get("properties", {}).get("rel") == relationship_type
                ]
                subgraph["rels"] = filtered_rels
            
            # Filter by direction
            if direction != "both":
                filtered_rels = []
                for rel in subgraph.get("rels", []):
                    if not rel:
                        continue
                    if direction == "outgoing" and rel.get("start") == start_entity_id:
                        filtered_rels.append(rel)
                    elif direction == "incoming" and rel.get("end") == start_entity_id:
                        filtered_rels.append(rel)
                subgraph["rels"] = filtered_rels
            
            # Build traversal result
            result = {
                "start_entity": start_entity_id,
                "depth": max_depth,
                "direction": direction,
                "relationship_filter": relationship_type,
                "nodes_found": len(subgraph.get("nodes", [])),
                "relationships_found": len(subgraph.get("rels", [])),
                "subgraph": subgraph
            }
            
            # Add path summaries
            paths = []
            for rel in subgraph.get("rels", [])[:10]:  # Top 10 paths
                if not rel:
                    continue
                paths.append({
                    "from": rel.get("start"),
                    "to": rel.get("end"),
                    "via": rel.get("properties", {}).get("rel", "REL"),
                    "properties": rel.get("properties", {})
                })
            result["sample_paths"] = paths
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "start_entity": start_entity_id
            })
    
    # ------------------------------------------------------------------------
    # INSIGHT & PATTERN TOOLS
    # ------------------------------------------------------------------------
    
    def find_patterns(self, pattern_type: str, entity_types: Optional[List[str]] = None,
                     min_frequency: int = 2) -> str:
        """
        Discover patterns in your knowledge graph.
        
        Use this to find clusters of related concepts, frequently co-occurring entities,
        temporal patterns, or structural patterns in how you organize knowledge.
        
        Pattern types:
        - clusters: Groups of tightly connected entities
        - frequent_connections: Most common relationship patterns
        - temporal: Time-based patterns in memory creation
        - co_occurrence: Entities that frequently appear together
        
        Returns: Discovered patterns with statistics and examples.
        """
        try:
            patterns = {
                "pattern_type": pattern_type,
                "entity_types": entity_types,
                "min_frequency": min_frequency,
                "patterns_found": []
            }
            
            if pattern_type == "clusters":
                # Find densely connected clusters
                # Get all entities
                seeds = self.mem.graph.list_subgraph_seeds()
                entity_ids = seeds.get("entity_ids", [])[:100]  # Limit for performance
                
                if entity_types:
                    # Filter by type
                    filtered_ids = []
                    for eid in entity_ids:
                        try:
                            subgraph = self.mem.extract_subgraph([eid], depth=0)
                            node = next((n for n in subgraph.get("nodes", []) if n.get("id") == eid), None)
                            if node and node.get("properties", {}).get("type") in entity_types:
                                filtered_ids.append(eid)
                        except:
                            continue
                    entity_ids = filtered_ids
                
                # Build clusters based on connection density
                clusters = []
                processed = set()
                
                for eid in entity_ids[:50]:  # Limit for performance
                    if eid in processed:
                        continue
                    
                    # Get neighborhood
                    subgraph = self.mem.extract_subgraph([eid], depth=1)
                    neighbors = [n.get("id") for n in subgraph.get("nodes", []) if n.get("id") != eid]
                    
                    if len(neighbors) >= min_frequency:
                        clusters.append({
                            "center": eid,
                            "size": len(neighbors),
                            "members": neighbors[:10]  # Top 10
                        })
                        processed.add(eid)
                        processed.update(neighbors)
                
                patterns["patterns_found"] = clusters
            
            elif pattern_type == "frequent_connections":
                # Find most common relationship types
                seeds = self.mem.graph.list_subgraph_seeds()
                entity_ids = seeds.get("entity_ids", [])[:50]
                
                rel_counts = {}
                for eid in entity_ids:
                    try:
                        subgraph = self.mem.extract_subgraph([eid], depth=1)
                        for rel in subgraph.get("rels", []):
                            if not rel:
                                continue
                            rel_type = rel.get("properties", {}).get("rel", "UNKNOWN")
                            rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
                    except:
                        continue
                
                # Filter and sort
                frequent = [
                    {"relationship_type": k, "count": v}
                    for k, v in rel_counts.items()
                    if v >= min_frequency
                ]
                frequent.sort(key=lambda x: x["count"], reverse=True)
                patterns["patterns_found"] = frequent
            
            elif pattern_type == "temporal":
                # Analyze temporal patterns
                sessions = self.mem.list_sessions()
                
                temporal_patterns = {
                    "total_sessions": len(sessions),
                    "active_sessions": len([s for s in sessions if not s.ended_at]),
                    "recent_activity": []
                }
                
                # Sort by start time
                sessions.sort(key=lambda s: s.started_at, reverse=True)
                
                for sess in sessions[:10]:
                    temporal_patterns["recent_activity"].append({
                        "session_id": sess.id,
                        "started_at": sess.started_at,
                        "ended_at": sess.ended_at,
                        "metadata": sess.metadata
                    })
                
                patterns["patterns_found"] = [temporal_patterns]
            
            return json.dumps(patterns, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "pattern_type": pattern_type
            })
    
    def generate_insights(self, focus_area: str, insight_type: str = "connections",
                         time_range: Optional[str] = None) -> str:
        """
        Generate insights about your knowledge and memory patterns.
        
        Use this to understand connections between concepts, identify trends,
        spot contradictions, or find gaps in your knowledge.
        
        Insight types:
        - connections: Discover unexpected links between concepts
        - trends: Identify evolving patterns over time  
        - contradictions: Find conflicting information
        - gaps: Identify areas with sparse information
        
        Returns: Generated insights with supporting evidence.
        """
        try:
            insights = {
                "focus_area": focus_area,
                "insight_type": insight_type,
                "time_range": time_range,
                "insights": []
            }
            
            # Search for entities related to focus area
            search_results = json.loads(self.search_memory(focus_area, k=20, search_type="hybrid"))
            
            if insight_type == "connections":
                # Find unexpected connections
                entity_ids = []
                
                # Extract entity IDs from search results
                for result in search_results.get("semantic_results", []):
                    entity_id = result.get("metadata", {}).get("entity_id") or result.get("id")
                    if entity_id:
                        entity_ids.append(entity_id)
                
                for result in search_results.get("graph_results", []):
                    entity_ids.append(result.get("entity_id"))
                
                # Find connections between these entities
                connections = []
                for i, eid1 in enumerate(entity_ids[:10]):
                    for eid2 in entity_ids[i+1:10]:
                        try:
                            # Check if connected
                            subgraph = self.mem.extract_subgraph([eid1, eid2], depth=2)
                            
                            # Find paths between them
                            for rel in subgraph.get("rels", []):
                                if not rel:
                                    continue
                                if (rel.get("start") == eid1 and rel.get("end") == eid2) or \
                                   (rel.get("start") == eid2 and rel.get("end") == eid1):
                                    connections.append({
                                        "entity_1": eid1,
                                        "entity_2": eid2,
                                        "relationship": rel.get("properties", {}).get("rel"),
                                        "strength": "direct"
                                    })
                        except:
                            continue
                
                insights["insights"] = connections[:10]
            
            elif insight_type == "gaps":
                # Identify sparse areas
                entity_ids = []
                for result in search_results.get("semantic_results", []):
                    entity_id = result.get("metadata", {}).get("entity_id") or result.get("id")
                    if entity_id:
                        entity_ids.append(entity_id)
                
                gaps = []
                for eid in entity_ids[:20]:
                    try:
                        subgraph = self.mem.extract_subgraph([eid], depth=1)
                        connection_count = len(subgraph.get("rels", []))
                        
                        if connection_count < 2:  # Weakly connected
                            gaps.append({
                                "entity_id": eid,
                                "connections": connection_count,
                                "status": "isolated" if connection_count == 0 else "sparse"
                            })
                    except:
                        continue
                
                insights["insights"] = gaps
            
            return json.dumps(insights, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "focus_area": focus_area
            })
    
    # ------------------------------------------------------------------------
    # NOTE-TAKING & ANNOTATION TOOLS
    # ------------------------------------------------------------------------
    
    def add_note(self, note_text: str, note_type: str = "insight",
                linked_entities: Optional[List[str]] = None,
                metadata: Optional[Dict] = None) -> str:
        """
        Add a note, insight, or observation to your knowledge graph.
        
        Use this to record insights, hypotheses, questions, or summaries
        as you process information. Notes can be linked to relevant entities.
        
        Note types: insight, observation, question, hypothesis, summary, todo
        
        Returns: ID of created note for future reference.
        """
        try:
            import time
            note_id = f"note_{int(time.time()*1000)}"
            
            # Create note entity
            note_node = self.mem.upsert_entity(
                entity_id=note_id,
                etype=note_type,
                labels=["Note", note_type.capitalize()],
                properties={
                    "text": note_text,
                    "note_type": note_type,
                    "created_at": time.time(),
                    **(metadata or {})
                }
            )
            
            # Link to session
            if hasattr(self, 'sess') and self.sess:
                self.mem.link_to_session(self.sess.id, note_id, "HAS_NOTE")
            
            # Link to entities
            if linked_entities:
                for entity_id in linked_entities:
                    try:
                        self.mem.link(note_id, entity_id, "REFERENCES")
                    except Exception as e:
                        logger.warning(f"Could not link to {entity_id}: {e}")
            
            # Add to vector store for semantic search
            self.mem.vec.add_texts(
                "long_term_docs",
                [note_id],
                [note_text],
                [{"type": note_type, "is_note": True, **(metadata or {})}]
            )
            
            return json.dumps({
                "success": True,
                "note_id": note_id,
                "note_type": note_type,
                "linked_entities": linked_entities or [],
                "message": f"Note created and linked to {len(linked_entities or [])} entities"
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            })
    
    def annotate_entity(self, entity_id: str, property_name: str,
                       property_value: Any, annotation_type: str = "observation") -> str:
        """
        Add or update a property on an existing entity.
        
        Use this to enrich entities with additional context, observations,
        classifications, or metadata as you learn more about them.
        
        Returns: Confirmation of annotation.
        """
        try:
            # Get existing entity
            subgraph = self.mem.extract_subgraph([entity_id], depth=0)
            entity_node = next((n for n in subgraph.get("nodes", []) if n.get("id") == entity_id), None)
            
            if not entity_node:
                return json.dumps({
                    "success": False,
                    "error": f"Entity {entity_id} not found"
                })
            
            # Update properties
            existing_props = entity_node.get("properties", {})
            
            # Store annotation history
            if "annotations" not in existing_props:
                existing_props["annotations"] = {}
            
            import time
            existing_props["annotations"][property_name] = {
                "value": property_value,
                "type": annotation_type,
                "timestamp": time.time()
            }
            
            # Update main property
            existing_props[property_name] = property_value
            
            # Upsert entity with new properties
            from Memory.memory import Node
            updated_node = Node(
                id=entity_id,
                type=entity_node.get("properties", {}).get("type", "unknown"),
                labels=entity_node.get("labels", []),
                properties=existing_props
            )
            self.mem.graph.upsert_entity(updated_node)
            
            return json.dumps({
                "success": True,
                "entity_id": entity_id,
                "property": property_name,
                "value": property_value,
                "annotation_type": annotation_type
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "entity_id": entity_id
            })
    
    def link_entities(self, source_entity_id: str, target_entity_id: str,
                     relationship_type: str, properties: Optional[Dict] = None,
                     confidence: float = 0.8) -> str:
        """
        Create a relationship between two entities in your knowledge graph.
        
        Use this to explicitly connect concepts, indicate implications,
        note contradictions, or establish any semantic relationship.
        
        Common relationship types:
        - RELATED_TO: General association
        - IMPLIES: Logical implication
        - CONTRADICTS: Conflicting information
        - PART_OF: Hierarchical relationship
        - SIMILAR_TO: Semantic similarity
        - CAUSES: Causal relationship
        
        Returns: Confirmation of link creation.
        """
        try:
            # Verify both entities exist
            for eid in [source_entity_id, target_entity_id]:
                subgraph = self.mem.extract_subgraph([eid], depth=0)
                if not any(n.get("id") == eid for n in subgraph.get("nodes", [])):
                    return json.dumps({
                        "success": False,
                        "error": f"Entity {eid} not found"
                    })
            
            # Create relationship
            import time
            rel_props = {
                "confidence": confidence,
                "created_by": "llm_introspection",
                "created_at": time.time(),
                **(properties or {})
            }
            
            self.mem.link(source_entity_id, target_entity_id, relationship_type, rel_props)
            
            return json.dumps({
                "success": True,
                "source": source_entity_id,
                "target": target_entity_id,
                "relationship": relationship_type,
                "confidence": confidence
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            })
    
    # ------------------------------------------------------------------------
    # CONSOLIDATION & MANAGEMENT TOOLS
    # ------------------------------------------------------------------------
    
    def consolidate_memory(self, session_id: str, consolidation_type: str = "summarize",
                          threshold: float = 0.7) -> str:
        """
        Consolidate session memory into long-term knowledge.
        
        Use this to process and organize information from a session,
        creating summaries, promoting important entities, or clustering related concepts.
        
        Consolidation types:
        - summarize: Create summary nodes
        - promote: Move high-value entities to long-term
        - cluster: Group related memories
        
        Returns: Consolidation results and statistics.
        """
        try:
            results = {
                "session_id": session_id,
                "consolidation_type": consolidation_type,
                "actions_taken": []
            }
            
            # Get session memories
            memories = self.mem.get_session_memory(session_id)
            
            if consolidation_type == "summarize":
                # Create a summary node
                summary_texts = [m.text for m in memories]
                combined_text = "\n".join(summary_texts)
                
                # Use LLM to summarize if available
                summary_text = f"Session summary: {len(memories)} memories recorded"
                
                import time
                summary_id = f"summary_{session_id}_{int(time.time())}"
                
                self.mem.upsert_entity(
                    entity_id=summary_id,
                    etype="summary",
                    labels=["Summary", "Consolidated"],
                    properties={
                        "text": summary_text,
                        "source_session": session_id,
                        "memory_count": len(memories),
                        "created_at": time.time()
                    }
                )
                
                # Link to session
                self.mem.link(session_id, summary_id, "HAS_SUMMARY")
                
                results["actions_taken"].append({
                    "action": "created_summary",
                    "summary_id": summary_id
                })
            
            elif consolidation_type == "promote":
                # Promote high-value memories
                promoted = 0
                for memory in memories:
                    # Simple heuristic: promote if text is long enough and has metadata
                    if len(memory.text) > 100 and memory.metadata:
                        try:
                            self.mem.promote_session_memory_to_long_term(memory)
                            promoted += 1
                        except:
                            pass
                
                results["actions_taken"].append({
                    "action": "promoted_memories",
                    "count": promoted
                })
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "session_id": session_id
            })
    
    def query_graph(self, query_description: str, entity_types: Optional[List[str]] = None,
                   limit: int = 10) -> str:
        """
        Query the knowledge graph using natural language.
        
        Use this to ask complex questions about your knowledge graph structure,
        find entities meeting specific criteria, or explore relationships.
        
        Examples:
        - "Find all entities related to machine learning"
        - "What entities have the most connections?"
        - "Show me all notes from the last session"
        
        Returns: Query results with matching entities and relationships.
        """
        try:
            # Use semantic search to find relevant entities
            search_results = json.loads(self.search_memory(
                query_description, 
                k=limit, 
                search_type="hybrid"
            ))
            
            # Enrich with graph context
            enriched_results = []
            
            for result in search_results.get("semantic_results", [])[:limit]:
                entity_id = result.get("metadata", {}).get("entity_id") or result.get("id")
                
                try:
                    # Get entity details
                    profile = json.loads(self.inspect_entity(entity_id, depth=1, include_properties=True))
                    
                    # Filter by entity type if specified
                    if entity_types:
                        entity_type = profile.get("type")
                        if entity_type not in entity_types:
                            continue
                    
                    enriched_results.append({
                        "entity_id": entity_id,
                        "relevance": result.get("relevance", 0.5),
                        "profile": profile
                    })
                except:
                    continue
            
            return json.dumps({
                "query": query_description,
                "results_count": len(enriched_results),
                "results": enriched_results
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "query": query_description
            })


# ============================================================================
# TOOL LOADER FUNCTION
# ============================================================================

def load_memory_tools(agent) -> List:
    """
    Load all memory introspection tools for the agent.
    
    Usage:
        memory_tools = load_memory_tools(agent)
        agent.tools.extend(memory_tools)
    
    Or add to ToolLoader in tools.py:
        # In ToolLoader function:
        from memory_tools import load_memory_tools
        tool_list.extend(load_memory_tools(agent))
    """
    from langchain.tools import StructuredTool
    
    tools_instance = MemoryTools(agent)
    
    tool_list = [
        # Search & Retrieval
        StructuredTool.from_function(
            func=tools_instance.search_memory,
            name="search_memory",
            description="Search your knowledge graph using semantic or graph queries. Recall information, find related concepts, explore what you know.",
            args_schema=MemorySearchInput
        ),
        
        StructuredTool.from_function(
            func=tools_instance.inspect_entity,
            name="inspect_entity",
            description="Deep inspection of a specific entity. See all properties, connections, and context for any entity in your knowledge graph.",
            args_schema=EntityInspectInput
        ),
        
        StructuredTool.from_function(
            func=tools_instance.traverse_graph,
            name="traverse_graph",
            description="Traverse the knowledge graph from a starting point. Follow chains of relationships and discover how concepts are linked.",
            args_schema=GraphTraverseInput
        ),
        
        # Insights & Patterns
        StructuredTool.from_function(
            func=tools_instance.find_patterns,
            name="find_patterns",
            description="Discover patterns in your knowledge: clusters, frequent connections, temporal patterns, or co-occurring entities.",
            args_schema=FindPatternsInput
        ),
        
        StructuredTool.from_function(
            func=tools_instance.generate_insights,
            name="generate_insights",
            description="Generate insights about knowledge patterns: unexpected connections, trends, contradictions, or gaps in knowledge.",
            args_schema=MemoryInsightInput
        ),
        
        # Note-taking & Annotation
        StructuredTool.from_function(
            func=tools_instance.add_note,
            name="add_note",
            description="Add a note, insight, observation, question, or hypothesis to your knowledge graph. Link to relevant entities.",
            args_schema=AddNoteInput
        ),
        
        StructuredTool.from_function(
            func=tools_instance.annotate_entity,
            name="annotate_entity",
            description="Add or update properties on existing entities. Enrich entities with observations, classifications, or metadata.",
            args_schema=AnnotateEntityInput
        ),
        
        StructuredTool.from_function(
            func=tools_instance.link_entities,
            name="link_entities",
            description="Create relationships between entities. Connect concepts, indicate implications, note contradictions, or establish semantic links.",
            args_schema=LinkEntitiesInput
        ),
        
        # Management & Consolidation
        StructuredTool.from_function(
            func=tools_instance.consolidate_memory,
            name="consolidate_memory",
            description="Consolidate session memory into long-term knowledge. Summarize, promote important entities, or cluster related concepts.",
            args_schema=ConsolidateMemoryInput
        ),
        
        StructuredTool.from_function(
            func=tools_instance.query_graph,
            name="query_graph",
            description="Query the knowledge graph using natural language. Ask complex questions about graph structure or find specific entities.",
            args_schema=QueryGraphInput
        ),
    ]
    
    return tool_list


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """
    Example of how to integrate memory tools with Vera.
    
    In your ToolLoader function (tools.py), add:
    
    from memory_tools import load_memory_tools
    
    # At the end of tool_list:
    tool_list.extend(load_memory_tools(agent))
    
    return tool_list
    """
    print("Memory Introspection Tools")
    print("=" * 60)
    print("\nAvailable Tools:")
    print("  1. search_memory - Search knowledge graph")
    print("  2. inspect_entity - Deep entity inspection")
    print("  3. traverse_graph - Graph traversal")
    print("  4. find_patterns - Pattern discovery")
    print("  5. generate_insights - Insight generation")
    print("  6. add_note - Create notes/annotations")
    print("  7. annotate_entity - Enrich entity properties")
    print("  8. link_entities - Create relationships")
    print("  9. consolidate_memory - Memory consolidation")
    print(" 10. query_graph - Natural language graph queries")
    print("\nIntegration:")
    print("  from memory_tools import load_memory_tools")
    print("  tool_list.extend(load_memory_tools(agent))")