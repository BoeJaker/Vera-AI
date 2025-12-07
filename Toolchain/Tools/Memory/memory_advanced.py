"""
Advanced Memory Search & Insight Discovery Tools
================================================
Enhanced memory introspection with deep relationship discovery,
hidden pattern detection, and multi-hop reasoning capabilities.

Features:
- Multi-hop relationship discovery
- Hidden connection inference
- Temporal pattern analysis
- Semantic clustering and emergence detection
- Cross-domain insight generation
- Anomaly and contradiction detection
- Knowledge gap analysis
- Entity importance ranking
- Causal chain discovery
- Analogy detection
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json
import logging
import time
import re

logger = logging.getLogger(__name__)


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class MultiHopSearchInput(BaseModel):
    """Input for multi-hop relationship discovery."""
    start_entity_id: str = Field(..., description="Starting entity ID")
    target_entity_id: Optional[str] = Field(
        default=None,
        description="Target entity (finds paths to this entity)"
    )
    max_hops: int = Field(default=3, description="Maximum path length (1-5)")
    relationship_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by specific relationship types"
    )
    include_indirect: bool = Field(
        default=True,
        description="Include indirect relationships through intermediaries"
    )


class HiddenConnectionInput(BaseModel):
    """Input for discovering hidden connections."""
    entity_ids: List[str] = Field(..., description="List of entity IDs to analyze")
    discovery_method: str = Field(
        default="semantic",
        description="Method: semantic, structural, temporal, hybrid"
    )
    min_confidence: float = Field(
        default=0.6,
        description="Minimum confidence threshold (0.0-1.0)"
    )
    max_distance: int = Field(
        default=3,
        description="Maximum graph distance to search"
    )


class TemporalAnalysisInput(BaseModel):
    """Input for temporal pattern analysis."""
    time_range: str = Field(
        default="all",
        description="Range: today, week, month, year, all, custom"
    )
    custom_start: Optional[str] = Field(
        default=None,
        description="Custom start time (ISO format)"
    )
    custom_end: Optional[str] = Field(
        default=None,
        description="Custom end time (ISO format)"
    )
    pattern_type: str = Field(
        default="evolution",
        description="Type: evolution, frequency, trends, cycles"
    )
    entity_filter: Optional[str] = Field(
        default=None,
        description="Filter by entity type or property"
    )


class EmergentPatternInput(BaseModel):
    """Input for detecting emergent patterns."""
    focus_area: Optional[str] = Field(
        default=None,
        description="Area to focus on (or None for global analysis)"
    )
    min_cluster_size: int = Field(
        default=3,
        description="Minimum cluster size to report"
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Similarity threshold for clustering (0.0-1.0)"
    )
    include_weak_signals: bool = Field(
        default=True,
        description="Include weak/emerging patterns"
    )


class CrossDomainInsightInput(BaseModel):
    """Input for cross-domain insight generation."""
    domain_a: str = Field(..., description="First domain/topic")
    domain_b: str = Field(..., description="Second domain/topic")
    insight_types: List[str] = Field(
        default=["analogies", "transfers", "contradictions"],
        description="Types: analogies, transfers, contradictions, synergies"
    )
    depth: int = Field(default=2, description="Analysis depth (1-4)")


class AnomalyDetectionInput(BaseModel):
    """Input for anomaly and contradiction detection."""
    scope: str = Field(
        default="recent",
        description="Scope: recent, session, global, entity_specific"
    )
    entity_id: Optional[str] = Field(
        default=None,
        description="Specific entity to check (if scope=entity_specific)"
    )
    anomaly_types: List[str] = Field(
        default=["contradictions", "outliers", "inconsistencies"],
        description="Types to detect"
    )


class KnowledgeGapInput(BaseModel):
    """Input for knowledge gap analysis."""
    topic: str = Field(..., description="Topic area to analyze")
    comparison_source: Optional[str] = Field(
        default=None,
        description="Compare against external knowledge (e.g., 'common knowledge', 'domain expertise')"
    )
    gap_types: List[str] = Field(
        default=["missing_entities", "weak_connections", "incomplete_attributes"],
        description="Types of gaps to identify"
    )


class EntityRankingInput(BaseModel):
    """Input for entity importance ranking."""
    ranking_criteria: str = Field(
        default="centrality",
        description="Criteria: centrality, frequency, recency, diversity, influence"
    )
    entity_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by entity types"
    )
    top_k: int = Field(default=20, description="Number of top entities to return")
    include_scores: bool = Field(
        default=True,
        description="Include detailed scoring breakdown"
    )


class CausalChainInput(BaseModel):
    """Input for causal chain discovery."""
    start_entity: str = Field(..., description="Starting entity/event")
    end_entity: Optional[str] = Field(
        default=None,
        description="Target entity/outcome (or None for open-ended)"
    )
    max_chain_length: int = Field(default=5, description="Maximum chain length")
    causal_indicators: List[str] = Field(
        default=["CAUSES", "LEADS_TO", "IMPLIES", "RESULTS_IN"],
        description="Relationship types indicating causation"
    )


class AnalogyDetectionInput(BaseModel):
    """Input for analogy detection."""
    source_entity: str = Field(..., description="Source entity for analogy")
    search_space: str = Field(
        default="all",
        description="Where to search: all, recent, specific_domain"
    )
    domain_filter: Optional[str] = Field(
        default=None,
        description="Domain to search within (if search_space=specific_domain)"
    )
    min_structural_similarity: float = Field(
        default=0.6,
        description="Minimum structural similarity (0.0-1.0)"
    )


class SemanticClusteringInput(BaseModel):
    """Input for semantic clustering."""
    entities: Optional[List[str]] = Field(
        default=None,
        description="Specific entities to cluster (or None for all)"
    )
    num_clusters: Optional[int] = Field(
        default=None,
        description="Number of clusters (or None for automatic)"
    )
    cluster_method: str = Field(
        default="hierarchical",
        description="Method: hierarchical, dbscan, kmeans, semantic"
    )
    include_visualization: bool = Field(
        default=True,
        description="Include cluster visualization data"
    )


# ============================================================================
# ADVANCED MEMORY SEARCH TOOLS
# ============================================================================

class AdvancedMemorySearch:
    """
    Enhanced memory search with deep pattern discovery and insight generation.
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.mem = agent.mem
        self.sess = agent.sess
        
        # Cache for performance
        self._entity_cache = {}
        self._subgraph_cache = {}
        self._cache_timeout = 300  # 5 minutes
    
    def _get_cached_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity from cache or fetch if needed."""
        cache_key = f"entity_{entity_id}"
        
        if cache_key in self._entity_cache:
            cached_time, data = self._entity_cache[cache_key]
            if time.time() - cached_time < self._cache_timeout:
                return data
        
        try:
            subgraph = self.mem.extract_subgraph([entity_id], depth=0)
            entity = next((n for n in subgraph.get("nodes", []) if n.get("id") == entity_id), None)
            
            if entity:
                self._entity_cache[cache_key] = (time.time(), entity)
            
            return entity
        except:
            return None
    
    def _get_cached_subgraph(self, entity_ids: List[str], depth: int) -> Dict:
        """Get subgraph from cache or fetch if needed."""
        cache_key = f"subgraph_{'-'.join(sorted(entity_ids))}_{depth}"
        
        if cache_key in self._subgraph_cache:
            cached_time, data = self._subgraph_cache[cache_key]
            if time.time() - cached_time < self._cache_timeout:
                return data
        
        try:
            subgraph = self.mem.extract_subgraph(entity_ids, depth=depth)
            self._subgraph_cache[cache_key] = (time.time(), subgraph)
            return subgraph
        except Exception as e:
            logger.error(f"Error fetching subgraph: {e}")
            return {"nodes": [], "rels": []}
    
    # ------------------------------------------------------------------------
    # MULTI-HOP RELATIONSHIP DISCOVERY
    # ------------------------------------------------------------------------
    
    def discover_multihop_paths(
        self,
        start_entity_id: str,
        target_entity_id: Optional[str] = None,
        max_hops: int = 3,
        relationship_types: Optional[List[str]] = None,
        include_indirect: bool = True
    ) -> str:
        """
        Discover multi-hop paths between entities.
        
        Finds direct and indirect relationships by traversing the knowledge graph,
        revealing hidden connections through intermediary entities.
        
        Use this to:
        - Find how two concepts are connected
        - Discover reasoning chains
        - Trace influence paths
        - Understand relationship networks
        
        Args:
            start_entity_id: Starting point
            target_entity_id: Destination (or None to explore all paths)
            max_hops: Maximum path length
            relationship_types: Filter by specific relationship types
            include_indirect: Include paths through intermediaries
        
        Returns: JSON with discovered paths, intermediaries, and connection strengths
        """
        try:
            max_hops = min(max(max_hops, 1), 5)
            
            result = {
                "start": start_entity_id,
                "target": target_entity_id,
                "max_hops": max_hops,
                "paths_found": [],
                "intermediaries": {},
                "connection_summary": {}
            }
            
            # BFS to find all paths
            from collections import deque
            
            queue = deque([(start_entity_id, [start_entity_id], 0)])
            visited_paths = set()
            all_paths = []
            
            while queue:
                current_id, path, depth = queue.popleft()
                
                if depth >= max_hops:
                    continue
                
                # Get neighbors
                try:
                    subgraph = self._get_cached_subgraph([current_id], depth=1)
                    
                    for rel in subgraph.get("rels", []):
                        if not rel:
                            continue
                        
                        # Get relationship type
                        rel_type = rel.get("properties", {}).get("rel", "UNKNOWN")
                        
                        # Filter by relationship type if specified
                        if relationship_types and rel_type not in relationship_types:
                            continue
                        
                        # Find next entity
                        next_id = None
                        if rel.get("start") == current_id:
                            next_id = rel.get("end")
                        elif rel.get("end") == current_id:
                            next_id = rel.get("start")
                        
                        if not next_id or next_id in path:
                            continue
                        
                        new_path = path + [next_id]
                        path_key = tuple(new_path)
                        
                        if path_key in visited_paths:
                            continue
                        
                        visited_paths.add(path_key)
                        
                        # Record path with relationship
                        path_with_rel = {
                            "path": new_path,
                            "relationships": [rel_type],
                            "length": len(new_path) - 1,
                            "depth": depth + 1
                        }
                        
                        # If target specified, check if we reached it
                        if target_entity_id:
                            if next_id == target_entity_id:
                                all_paths.append(path_with_rel)
                                result["paths_found"].append(path_with_rel)
                        else:
                            # Record all paths for exploration
                            if depth + 1 == max_hops:
                                all_paths.append(path_with_rel)
                        
                        # Continue searching
                        if depth + 1 < max_hops:
                            queue.append((next_id, new_path, depth + 1))
                
                except Exception as e:
                    logger.error(f"Error exploring from {current_id}: {e}")
                    continue
            
            # Analyze intermediaries
            intermediary_counts = defaultdict(int)
            for path_info in all_paths:
                path = path_info["path"]
                # Count intermediaries (exclude start and end)
                for entity_id in path[1:-1]:
                    intermediary_counts[entity_id] += 1
            
            # Get entity details for top intermediaries
            top_intermediaries = sorted(
                intermediary_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            for entity_id, count in top_intermediaries:
                entity = self._get_cached_entity(entity_id)
                if entity:
                    result["intermediaries"][entity_id] = {
                        "frequency": count,
                        "text": entity.get("properties", {}).get("text", entity_id),
                        "type": entity.get("properties", {}).get("type", "unknown")
                    }
            
            # Connection summary
            result["connection_summary"] = {
                "total_paths": len(all_paths),
                "average_path_length": sum(p["length"] for p in all_paths) / len(all_paths) if all_paths else 0,
                "unique_intermediaries": len(intermediary_counts),
                "relationship_types_used": list(set(
                    rt for p in all_paths for rt in p.get("relationships", [])
                ))
            }
            
            # Include sample paths
            if not target_entity_id:
                result["paths_found"] = all_paths[:20]  # Top 20 paths
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error in multi-hop discovery: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "start": start_entity_id,
                "target": target_entity_id
            })
    
    # ------------------------------------------------------------------------
    # HIDDEN CONNECTION DISCOVERY
    # ------------------------------------------------------------------------
    
    def discover_hidden_connections(
        self,
        entity_ids: List[str],
        discovery_method: str = "semantic",
        min_confidence: float = 0.6,
        max_distance: int = 3
    ) -> str:
        """
        Discover hidden connections between entities.
        
        Finds non-obvious relationships using:
        - Semantic similarity (shared meaning)
        - Structural patterns (similar graph positions)
        - Temporal correlation (co-occurrence in time)
        - Hybrid analysis (combining methods)
        
        Use this to:
        - Find unexpected connections
        - Discover implicit relationships
        - Identify emerging patterns
        - Bridge knowledge silos
        
        Returns: Hidden connections with confidence scores and supporting evidence
        """
        try:
            min_confidence = max(0.0, min(1.0, min_confidence))
            max_distance = min(max(max_distance, 1), 5)
            
            result = {
                "method": discovery_method,
                "entities_analyzed": len(entity_ids),
                "hidden_connections": [],
                "insights": []
            }
            
            if discovery_method in ["semantic", "hybrid"]:
                # Semantic similarity analysis
                connections = []
                
                for i, eid1 in enumerate(entity_ids):
                    entity1 = self._get_cached_entity(eid1)
                    if not entity1:
                        continue
                    
                    text1 = entity1.get("properties", {}).get("text", "")
                    if not text1:
                        continue
                    
                    for eid2 in entity_ids[i+1:]:
                        entity2 = self._get_cached_entity(eid2)
                        if not entity2:
                            continue
                        
                        text2 = entity2.get("properties", {}).get("text", "")
                        if not text2:
                            continue
                        
                        # Check if already connected
                        direct_connection = self._check_direct_connection(eid1, eid2)
                        
                        if not direct_connection:
                            # Use semantic search to measure similarity
                            try:
                                # Search for entity2's text in context of entity1
                                hits = self.mem.semantic_retrieve(text2, k=10)
                                
                                # Check if entity1 appears in results
                                for hit in hits:
                                    hit_id = hit.get("metadata", {}).get("entity_id") or hit.get("id")
                                    if hit_id == eid1:
                                        # Found semantic connection
                                        confidence = 1.0 - hit.get("distance", 0.5)
                                        
                                        if confidence >= min_confidence:
                                            connections.append({
                                                "entity_a": eid1,
                                                "entity_b": eid2,
                                                "type": "semantic_similarity",
                                                "confidence": confidence,
                                                "evidence": f"Semantically similar: '{text1[:50]}...' <-> '{text2[:50]}...'"
                                            })
                                        break
                            except:
                                continue
                
                result["hidden_connections"].extend(connections)
            
            if discovery_method in ["structural", "hybrid"]:
                # Structural pattern analysis
                # Find entities with similar neighborhood structures
                
                entity_neighborhoods = {}
                for eid in entity_ids:
                    try:
                        subgraph = self._get_cached_subgraph([eid], depth=1)
                        
                        # Get neighbor types and relationships
                        neighbors = set()
                        rel_types = set()
                        
                        for rel in subgraph.get("rels", []):
                            if not rel:
                                continue
                            
                            rel_types.add(rel.get("properties", {}).get("rel", "UNKNOWN"))
                            
                            if rel.get("start") == eid:
                                neighbors.add(rel.get("end"))
                            elif rel.get("end") == eid:
                                neighbors.add(rel.get("start"))
                        
                        entity_neighborhoods[eid] = {
                            "neighbors": neighbors,
                            "rel_types": rel_types,
                            "degree": len(neighbors)
                        }
                    except:
                        continue
                
                # Compare neighborhood structures
                for i, eid1 in enumerate(entity_ids):
                    if eid1 not in entity_neighborhoods:
                        continue
                    
                    for eid2 in entity_ids[i+1:]:
                        if eid2 not in entity_neighborhoods:
                            continue
                        
                        # Check if already connected
                        if self._check_direct_connection(eid1, eid2):
                            continue
                        
                        # Calculate structural similarity
                        n1 = entity_neighborhoods[eid1]
                        n2 = entity_neighborhoods[eid2]
                        
                        # Jaccard similarity of neighbors
                        if n1["neighbors"] and n2["neighbors"]:
                            common_neighbors = n1["neighbors"] & n2["neighbors"]
                            all_neighbors = n1["neighbors"] | n2["neighbors"]
                            
                            neighbor_similarity = len(common_neighbors) / len(all_neighbors)
                            
                            # Relationship type similarity
                            common_rels = n1["rel_types"] & n2["rel_types"]
                            all_rels = n1["rel_types"] | n2["rel_types"]
                            
                            rel_similarity = len(common_rels) / len(all_rels) if all_rels else 0
                            
                            # Combined structural similarity
                            structural_sim = (neighbor_similarity + rel_similarity) / 2
                            
                            if structural_sim >= min_confidence:
                                result["hidden_connections"].append({
                                    "entity_a": eid1,
                                    "entity_b": eid2,
                                    "type": "structural_similarity",
                                    "confidence": structural_sim,
                                    "evidence": f"{len(common_neighbors)} shared neighbors, {len(common_rels)} shared relationship types"
                                })
            
            if discovery_method in ["temporal", "hybrid"]:
                # Temporal correlation analysis
                # Find entities that appear together in time
                
                temporal_patterns = defaultdict(list)
                
                for eid in entity_ids:
                    entity = self._get_cached_entity(eid)
                    if not entity:
                        continue
                    
                    # Get creation time
                    created_at = entity.get("properties", {}).get("created_at")
                    if created_at:
                        # Group by time window (1 hour)
                        try:
                            timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            time_bucket = timestamp.replace(minute=0, second=0, microsecond=0)
                            temporal_patterns[time_bucket].append(eid)
                        except:
                            continue
                
                # Find co-occurring entities
                for time_bucket, entities in temporal_patterns.items():
                    if len(entities) < 2:
                        continue
                    
                    for i, eid1 in enumerate(entities):
                        for eid2 in entities[i+1:]:
                            if self._check_direct_connection(eid1, eid2):
                                continue
                            
                            # Count co-occurrences
                            co_occurrence_count = sum(
                                1 for bucket_entities in temporal_patterns.values()
                                if eid1 in bucket_entities and eid2 in bucket_entities
                            )
                            
                            confidence = min(1.0, co_occurrence_count / 3)  # Normalize
                            
                            if confidence >= min_confidence:
                                result["hidden_connections"].append({
                                    "entity_a": eid1,
                                    "entity_b": eid2,
                                    "type": "temporal_correlation",
                                    "confidence": confidence,
                                    "evidence": f"Co-occurred {co_occurrence_count} times in same time windows"
                                })
            
            # Generate insights
            if result["hidden_connections"]:
                result["insights"].append(
                    f"Found {len(result['hidden_connections'])} hidden connections using {discovery_method} analysis"
                )
                
                # Group by type
                by_type = defaultdict(int)
                for conn in result["hidden_connections"]:
                    by_type[conn["type"]] += 1
                
                for conn_type, count in by_type.items():
                    result["insights"].append(f"  - {count} {conn_type} connections")
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error discovering hidden connections: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "entities": entity_ids
            })
    
    def _check_direct_connection(self, eid1: str, eid2: str) -> bool:
        """Check if two entities are directly connected."""
        try:
            subgraph = self._get_cached_subgraph([eid1, eid2], depth=1)
            
            for rel in subgraph.get("rels", []):
                if not rel:
                    continue
                
                if (rel.get("start") == eid1 and rel.get("end") == eid2) or \
                   (rel.get("start") == eid2 and rel.get("end") == eid1):
                    return True
            
            return False
        except:
            return False
    
    # ------------------------------------------------------------------------
    # TEMPORAL PATTERN ANALYSIS
    # ------------------------------------------------------------------------
    
    def analyze_temporal_patterns(
        self,
        time_range: str = "all",
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
        pattern_type: str = "evolution",
        entity_filter: Optional[str] = None
    ) -> str:
        """
        Analyze temporal patterns in memory formation and evolution.
        
        Discover how your knowledge has evolved over time:
        - Evolution: How concepts and relationships change
        - Frequency: Activity patterns and cycles
        - Trends: Increasing or decreasing focus areas
        - Cycles: Recurring patterns and rhythms
        
        Use this to:
        - Understand knowledge evolution
        - Identify learning patterns
        - Detect shifts in focus
        - Find cyclical behaviors
        
        Returns: Temporal analysis with trends, cycles, and evolution insights
        """
        try:
            result = {
                "time_range": time_range,
                "pattern_type": pattern_type,
                "analysis": {},
                "insights": []
            }
            
            # Parse time range
            now = datetime.now()
            if time_range == "today":
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now
            elif time_range == "week":
                start_time = now - timedelta(days=7)
                end_time = now
            elif time_range == "month":
                start_time = now - timedelta(days=30)
                end_time = now
            elif time_range == "year":
                start_time = now - timedelta(days=365)
                end_time = now
            elif time_range == "custom":
                start_time = datetime.fromisoformat(custom_start) if custom_start else now - timedelta(days=30)
                end_time = datetime.fromisoformat(custom_end) if custom_end else now
            else:  # all
                start_time = datetime(2000, 1, 1)
                end_time = now
            
            # Get sessions in time range
            sessions = self.mem.list_sessions()
            filtered_sessions = []
            
            for sess in sessions:
                try:
                    sess_time = datetime.fromisoformat(sess.started_at.replace('Z', '+00:00'))
                    if start_time <= sess_time <= end_time:
                        filtered_sessions.append(sess)
                except:
                    continue
            
            result["sessions_analyzed"] = len(filtered_sessions)
            
            if pattern_type == "evolution":
                # Track how entities and relationships evolve
                
                entity_timeline = defaultdict(list)
                
                for sess in filtered_sessions:
                    try:
                        sess_time = datetime.fromisoformat(sess.started_at.replace('Z', '+00:00'))
                        
                        # Get session memories
                        memories = self.mem.get_session_memory(sess.id)
                        
                        for memory in memories:
                            entity_id = memory.id
                            entity_type = memory.metadata.get("type", "unknown")
                            
                            entity_timeline[entity_type].append({
                                "timestamp": sess_time.isoformat(),
                                "session": sess.id,
                                "entity_id": entity_id
                            })
                    except:
                        continue
                
                # Analyze evolution
                evolution_summary = {}
                for entity_type, timeline in entity_timeline.items():
                    timeline.sort(key=lambda x: x["timestamp"])
                    
                    evolution_summary[entity_type] = {
                        "total_instances": len(timeline),
                        "first_seen": timeline[0]["timestamp"] if timeline else None,
                        "last_seen": timeline[-1]["timestamp"] if timeline else None,
                        "growth_rate": len(timeline) / max(1, len(filtered_sessions))
                    }
                
                result["analysis"]["evolution"] = evolution_summary
                
                # Insights
                fastest_growing = max(
                    evolution_summary.items(),
                    key=lambda x: x[1]["growth_rate"],
                    default=None
                )
                
                if fastest_growing:
                    result["insights"].append(
                        f"Fastest growing entity type: {fastest_growing[0]} "
                        f"({fastest_growing[1]['total_instances']} instances)"
                    )
            
            elif pattern_type == "frequency":
                # Activity frequency patterns
                
                activity_by_hour = defaultdict(int)
                activity_by_day = defaultdict(int)
                
                for sess in filtered_sessions:
                    try:
                        sess_time = datetime.fromisoformat(sess.started_at.replace('Z', '+00:00'))
                        activity_by_hour[sess_time.hour] += 1
                        activity_by_day[sess_time.strftime("%A")] += 1
                    except:
                        continue
                
                result["analysis"]["frequency"] = {
                    "by_hour": dict(activity_by_hour),
                    "by_day": dict(activity_by_day),
                    "peak_hour": max(activity_by_hour.items(), key=lambda x: x[1])[0] if activity_by_hour else None,
                    "peak_day": max(activity_by_day.items(), key=lambda x: x[1])[0] if activity_by_day else None
                }
                
                if result["analysis"]["frequency"]["peak_hour"] is not None:
                    result["insights"].append(
                        f"Peak activity hour: {result['analysis']['frequency']['peak_hour']}:00"
                    )
            
            elif pattern_type == "trends":
                # Detect increasing/decreasing trends
                
                # Group sessions by week
                weekly_activity = defaultdict(int)
                
                for sess in filtered_sessions:
                    try:
                        sess_time = datetime.fromisoformat(sess.started_at.replace('Z', '+00:00'))
                        week_key = sess_time.strftime("%Y-W%W")
                        weekly_activity[week_key] += 1
                    except:
                        continue
                
                # Calculate trend
                weeks = sorted(weekly_activity.keys())
                if len(weeks) >= 2:
                    first_week_avg = sum(weekly_activity[w] for w in weeks[:len(weeks)//2]) / (len(weeks)//2)
                    last_week_avg = sum(weekly_activity[w] for w in weeks[len(weeks)//2:]) / (len(weeks) - len(weeks)//2)
                    
                    trend_direction = "increasing" if last_week_avg > first_week_avg else "decreasing"
                    trend_magnitude = abs(last_week_avg - first_week_avg) / max(first_week_avg, 1)
                    
                    result["analysis"]["trends"] = {
                        "direction": trend_direction,
                        "magnitude": trend_magnitude,
                        "early_period_avg": first_week_avg,
                        "recent_period_avg": last_week_avg
                    }
                    
                    result["insights"].append(
                        f"Activity is {trend_direction} by {trend_magnitude*100:.1f}%"
                    )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error in temporal analysis: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "time_range": time_range
            })
    
    # ------------------------------------------------------------------------
    # EMERGENT PATTERN DETECTION
    # ------------------------------------------------------------------------
    
    def detect_emergent_patterns(
        self,
        focus_area: Optional[str] = None,
        min_cluster_size: int = 3,
        similarity_threshold: float = 0.7,
        include_weak_signals: bool = True
    ) -> str:
        """
        Detect emergent patterns and weak signals in your knowledge.
        
        Identifies:
        - Emerging clusters of related concepts
        - Weak signals (early indicators of trends)
        - Novel combinations and associations
        - Unexpected pattern formations
        
        Use this to:
        - Spot emerging interests
        - Identify knowledge consolidation
        - Detect pattern shifts
        - Find creative connections
        
        Returns: Emergent patterns with cluster analysis and weak signals
        """
        try:
            result = {
                "focus_area": focus_area,
                "clusters": [],
                "weak_signals": [],
                "novel_patterns": [],
                "insights": []
            }
            
            # Get entities to analyze
            if focus_area:
                # Search for relevant entities
                search_hits = self.mem.semantic_retrieve(focus_area, k=100)
                entity_ids = [
                    hit.get("metadata", {}).get("entity_id") or hit.get("id")
                    for hit in search_hits
                ]
            else:
                # Get all entities (limited for performance)
                seeds = self.mem.graph.list_subgraph_seeds()
                entity_ids = seeds.get("entity_ids", [])[:200]
            
            # Build entity embeddings matrix
            entity_embeddings = {}
            
            for eid in entity_ids:
                entity = self._get_cached_entity(eid)
                if not entity:
                    continue
                
                text = entity.get("properties", {}).get("text", "")
                if not text:
                    continue
                
                try:
                    # Get embedding via semantic search
                    hits = self.mem.semantic_retrieve(text, k=1)
                    if hits and "embedding" in hits[0]:
                        entity_embeddings[eid] = hits[0]["embedding"]
                except:
                    continue
            
            if not entity_embeddings:
                return json.dumps({
                    "error": "No entities with embeddings found",
                    "focus_area": focus_area
                })
            
            # Perform clustering
            try:
                import numpy as np
                from sklearn.cluster import DBSCAN, AgglomerativeClustering
                from sklearn.metrics.pairwise import cosine_similarity
                
                # Convert to matrix
                entity_ids_list = list(entity_embeddings.keys())
                embeddings_matrix = np.array([entity_embeddings[eid] for eid in entity_ids_list])
                
                # Cluster using DBSCAN
                clustering = DBSCAN(
                    eps=1.0 - similarity_threshold,
                    min_samples=min_cluster_size,
                    metric='cosine'
                ).fit(embeddings_matrix)
                
                labels = clustering.labels_
                
                # Group entities by cluster
                clusters = defaultdict(list)
                for idx, label in enumerate(labels):
                    if label >= 0:  # Ignore noise (-1)
                        clusters[label].append(entity_ids_list[idx])
                
                # Analyze clusters
                for cluster_id, cluster_entities in clusters.items():
                    if len(cluster_entities) < min_cluster_size:
                        continue
                    
                    # Get cluster details
                    cluster_info = {
                        "cluster_id": int(cluster_id),
                        "size": len(cluster_entities),
                        "entities": [],
                        "theme": ""
                    }
                    
                    # Get entity details
                    cluster_texts = []
                    for eid in cluster_entities[:10]:  # Top 10
                        entity = self._get_cached_entity(eid)
                        if entity:
                            text = entity.get("properties", {}).get("text", eid)
                            entity_type = entity.get("properties", {}).get("type", "unknown")
                            cluster_info["entities"].append({
                                "id": eid,
                                "text": text[:100],
                                "type": entity_type
                            })
                            cluster_texts.append(text)
                    
                    # Extract theme (most common words)
                    if cluster_texts:
                        all_words = " ".join(cluster_texts).lower().split()
                        word_freq = Counter(all_words)
                        # Filter out common words
                        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
                        meaningful_words = [(w, c) for w, c in word_freq.items() if w not in stopwords and len(w) > 3]
                        top_words = sorted(meaningful_words, key=lambda x: x[1], reverse=True)[:3]
                        cluster_info["theme"] = ", ".join([w for w, _ in top_words])
                    
                    result["clusters"].append(cluster_info)
                
                # Detect weak signals (small but growing clusters)
                if include_weak_signals:
                    # Get recent entities
                    recent_entities = []
                    for eid in entity_ids_list:
                        entity = self._get_cached_entity(eid)
                        if entity:
                            created_at = entity.get("properties", {}).get("created_at")
                            if created_at:
                                try:
                                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    if (datetime.now() - created_time).days < 7:  # Last week
                                        recent_entities.append(eid)
                                except:
                                    pass
                    
                    # Find small clusters with recent growth
                    for cluster_id, cluster_entities in clusters.items():
                        recent_in_cluster = [e for e in cluster_entities if e in recent_entities]
                        
                        if len(cluster_entities) < 10 and len(recent_in_cluster) >= 2:
                            result["weak_signals"].append({
                                "cluster_id": int(cluster_id),
                                "size": len(cluster_entities),
                                "recent_additions": len(recent_in_cluster),
                                "growth_rate": len(recent_in_cluster) / len(cluster_entities),
                                "signal": "Emerging cluster with recent activity"
                            })
                
                # Generate insights
                if result["clusters"]:
                    result["insights"].append(f"Found {len(result['clusters'])} emergent clusters")
                    
                    largest_cluster = max(result["clusters"], key=lambda x: x["size"])
                    result["insights"].append(
                        f"Largest cluster: {largest_cluster['theme']} ({largest_cluster['size']} entities)"
                    )
                
                if result["weak_signals"]:
                    result["insights"].append(
                        f"Detected {len(result['weak_signals'])} weak signals (early emerging patterns)"
                    )
            
            except ImportError:
                result["error"] = "sklearn not available for clustering"
            except Exception as e:
                logger.error(f"Clustering error: {e}", exc_info=True)
                result["error"] = f"Clustering failed: {str(e)}"
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error detecting emergent patterns: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "focus_area": focus_area
            })
    
    # ------------------------------------------------------------------------
    # Continue in next file due to length...
    # ------------------------------------------------------------------------


# ============================================================================
# TOOL LOADER FUNCTION
# ============================================================================

def add_advanced_memory_search_tools(tool_list: List, agent):
    """
    Add advanced memory search tools to the tool list.
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_advanced_memory_search_tools(tool_list, agent)
        return tool_list
    """
    from langchain_core.tools import StructuredTool
    
    search_tools = AdvancedMemorySearch(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=search_tools.discover_multihop_paths,
            name="discover_multihop_paths",
            description=(
                "Discover multi-hop paths between entities in knowledge graph. "
                "Finds direct and indirect relationships through intermediaries. "
                "Use to understand how concepts are connected through reasoning chains."
            ),
            args_schema=MultiHopSearchInput
        ),
        
        StructuredTool.from_function(
            func=search_tools.discover_hidden_connections,
            name="discover_hidden_connections",
            description=(
                "Discover hidden connections using semantic, structural, or temporal analysis. "
                "Finds non-obvious relationships and implicit connections. "
                "Use to bridge knowledge silos and find unexpected patterns."
            ),
            args_schema=HiddenConnectionInput
        ),
        
        StructuredTool.from_function(
            func=search_tools.analyze_temporal_patterns,
            name="analyze_temporal_patterns",
            description=(
                "Analyze temporal patterns in knowledge evolution. "
                "Tracks how concepts change over time, activity patterns, and trends. "
                "Use to understand learning patterns and detect focus shifts."
            ),
            args_schema=TemporalAnalysisInput
        ),
        
        StructuredTool.from_function(
            func=search_tools.detect_emergent_patterns,
            name="detect_emergent_patterns",
            description=(
                "Detect emergent patterns and weak signals in knowledge. "
                "Identifies emerging clusters, novel associations, and early trends. "
                "Use to spot emerging interests and creative connections."
            ),
            args_schema=EmergentPatternInput
        ),
    ])
    
    return tool_list


# Note: Due to length, I'll create a second file for the remaining advanced tools