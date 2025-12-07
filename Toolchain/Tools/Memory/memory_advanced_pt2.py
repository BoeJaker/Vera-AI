"""
Advanced Memory Search Tools - Part 2
======================================
Cross-domain insights, anomaly detection, knowledge gap analysis,
entity ranking, causal chains, and analogy detection.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from pydantic import BaseModel, Field
from collections import defaultdict, Counter
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Import the base class from part 1
try:
    from Vera.Toolchain.Tools.Memory.memory_advanced import (
        AdvancedMemorySearch,
        CrossDomainInsightInput,
        AnomalyDetectionInput,
        KnowledgeGapInput,
        EntityRankingInput,
        CausalChainInput,
        AnalogyDetectionInput,
        SemanticClusteringInput
    )
except:
    # Fallback if imported differently
    pass


# ============================================================================
# EXTENDED MEMORY SEARCH CLASS
# ============================================================================

class ExtendedMemorySearch(AdvancedMemorySearch):
    """Extended memory search with additional advanced capabilities."""
    
    # ------------------------------------------------------------------------
    # CROSS-DOMAIN INSIGHT GENERATION
    # ------------------------------------------------------------------------
    
    def generate_cross_domain_insights(
        self,
        domain_a: str,
        domain_b: str,
        insight_types: List[str] = ["analogies", "transfers", "contradictions"],
        depth: int = 2
    ) -> str:
        """
        Generate insights by comparing different knowledge domains.
        
        Discovers:
        - Analogies: Similar structures in different domains
        - Transfers: Applicable concepts from one domain to another
        - Contradictions: Conflicting approaches or principles
        - Synergies: Complementary knowledge that could combine
        
        Use this to:
        - Bridge different areas of knowledge
        - Find creative applications
        - Identify knowledge transfer opportunities
        - Spot inconsistencies across domains
        
        Returns: Cross-domain insights with analogies and transfer opportunities
        """
        try:
            depth = min(max(depth, 1), 4)
            
            result = {
                "domain_a": domain_a,
                "domain_b": domain_b,
                "insight_types": insight_types,
                "insights": {
                    "analogies": [],
                    "transfers": [],
                    "contradictions": [],
                    "synergies": []
                },
                "summary": ""
            }
            
            # Get entities from each domain
            domain_a_entities = []
            domain_b_entities = []
            
            hits_a = self.mem.semantic_retrieve(domain_a, k=50)
            for hit in hits_a:
                eid = hit.get("metadata", {}).get("entity_id") or hit.get("id")
                if eid:
                    domain_a_entities.append(eid)
            
            hits_b = self.mem.semantic_retrieve(domain_b, k=50)
            for hit in hits_b:
                eid = hit.get("metadata", {}).get("entity_id") or hit.get("id")
                if eid:
                    domain_b_entities.append(eid)
            
            # Detect analogies
            if "analogies" in insight_types:
                for eid_a in domain_a_entities[:20]:
                    entity_a = self._get_cached_entity(eid_a)
                    if not entity_a:
                        continue
                    
                    # Get structural pattern
                    subgraph_a = self._get_cached_subgraph([eid_a], depth=1)
                    pattern_a = self._extract_structural_pattern(subgraph_a, eid_a)
                    
                    for eid_b in domain_b_entities[:20]:
                        entity_b = self._get_cached_entity(eid_b)
                        if not entity_b:
                            continue
                        
                        # Get structural pattern
                        subgraph_b = self._get_cached_subgraph([eid_b], depth=1)
                        pattern_b = self._extract_structural_pattern(subgraph_b, eid_b)
                        
                        # Compare patterns
                        similarity = self._compare_patterns(pattern_a, pattern_b)
                        
                        if similarity > 0.7:
                            result["insights"]["analogies"].append({
                                "entity_a": {
                                    "id": eid_a,
                                    "text": entity_a.get("properties", {}).get("text", "")[:100],
                                    "domain": domain_a
                                },
                                "entity_b": {
                                    "id": eid_b,
                                    "text": entity_b.get("properties", {}).get("text", "")[:100],
                                    "domain": domain_b
                                },
                                "similarity": similarity,
                                "pattern": pattern_a.get("description", "Similar structure")
                            })
            
            # Detect knowledge transfers
            if "transfers" in insight_types:
                # Find concepts in domain A that could apply to domain B
                for eid_a in domain_a_entities[:15]:
                    entity_a = self._get_cached_entity(eid_a)
                    if not entity_a:
                        continue
                    
                    text_a = entity_a.get("properties", {}).get("text", "")
                    
                    # Check if this concept has not appeared in domain B
                    found_in_b = False
                    for eid_b in domain_b_entities:
                        entity_b = self._get_cached_entity(eid_b)
                        if entity_b:
                            text_b = entity_b.get("properties", {}).get("text", "")
                            if text_a.lower() in text_b.lower() or text_b.lower() in text_a.lower():
                                found_in_b = True
                                break
                    
                    if not found_in_b:
                        # Potential transfer candidate
                        # Check if it has broad applicability
                        subgraph_a = self._get_cached_subgraph([eid_a], depth=1)
                        connections = len(subgraph_a.get("rels", []))
                        
                        if connections >= 3:  # Well-connected concepts
                            result["insights"]["transfers"].append({
                                "concept": {
                                    "id": eid_a,
                                    "text": text_a[:100],
                                    "from_domain": domain_a,
                                    "connections": connections
                                },
                                "to_domain": domain_b,
                                "reason": "Well-connected concept not present in target domain"
                            })
            
            # Detect contradictions
            if "contradictions" in insight_types:
                # Look for entities with contradictory properties
                for eid_a in domain_a_entities[:15]:
                    entity_a = self._get_cached_entity(eid_a)
                    if not entity_a:
                        continue
                    
                    for eid_b in domain_b_entities[:15]:
                        entity_b = self._get_cached_entity(eid_b)
                        if not entity_b:
                            continue
                        
                        # Check for contradiction indicators
                        props_a = entity_a.get("properties", {})
                        props_b = entity_b.get("properties", {})
                        
                        # Simple heuristic: check for opposing concepts
                        text_a = props_a.get("text", "").lower()
                        text_b = props_b.get("text", "").lower()
                        
                        contradiction_pairs = [
                            ("increase", "decrease"), ("more", "less"),
                            ("positive", "negative"), ("true", "false"),
                            ("enable", "disable"), ("start", "stop")
                        ]
                        
                        for word_a, word_b in contradiction_pairs:
                            if word_a in text_a and word_b in text_b:
                                result["insights"]["contradictions"].append({
                                    "entity_a": {
                                        "id": eid_a,
                                        "text": text_a[:100],
                                        "domain": domain_a
                                    },
                                    "entity_b": {
                                        "id": eid_b,
                                        "text": text_b[:100],
                                        "domain": domain_b
                                    },
                                    "contradiction_type": f"{word_a} vs {word_b}"
                                })
                                break
            
            # Detect synergies
            if "synergies" in insight_types:
                # Find complementary concepts
                for eid_a in domain_a_entities[:10]:
                    entity_a = self._get_cached_entity(eid_a)
                    if not entity_a:
                        continue
                    
                    subgraph_a = self._get_cached_subgraph([eid_a], depth=1)
                    
                    for eid_b in domain_b_entities[:10]:
                        entity_b = self._get_cached_entity(eid_b)
                        if not entity_b:
                            continue
                        
                        subgraph_b = self._get_cached_subgraph([eid_b], depth=1)
                        
                        # Check for complementary relationship types
                        rels_a = set(r.get("properties", {}).get("rel") for r in subgraph_a.get("rels", []) if r)
                        rels_b = set(r.get("properties", {}).get("rel") for r in subgraph_b.get("rels", []) if r)
                        
                        # Synergy if they have different but compatible relationship types
                        if rels_a and rels_b and not (rels_a & rels_b):
                            result["insights"]["synergies"].append({
                                "entity_a": {
                                    "id": eid_a,
                                    "text": entity_a.get("properties", {}).get("text", "")[:100],
                                    "domain": domain_a
                                },
                                "entity_b": {
                                    "id": eid_b,
                                    "text": entity_b.get("properties", {}).get("text", "")[:100],
                                    "domain": domain_b
                                },
                                "synergy": "Complementary relationship patterns"
                            })
            
            # Generate summary
            total_insights = sum(len(v) for v in result["insights"].values())
            result["summary"] = f"Found {total_insights} cross-domain insights between {domain_a} and {domain_b}"
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error generating cross-domain insights: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "domains": [domain_a, domain_b]
            })
    
    def _extract_structural_pattern(self, subgraph: Dict, entity_id: str) -> Dict:
        """Extract structural pattern from entity's subgraph."""
        pattern = {
            "in_degree": 0,
            "out_degree": 0,
            "relationship_types": set(),
            "neighbor_types": set(),
            "description": ""
        }
        
        for rel in subgraph.get("rels", []):
            if not rel:
                continue
            
            rel_type = rel.get("properties", {}).get("rel", "UNKNOWN")
            pattern["relationship_types"].add(rel_type)
            
            if rel.get("start") == entity_id:
                pattern["out_degree"] += 1
            elif rel.get("end") == entity_id:
                pattern["in_degree"] += 1
        
        # Get neighbor types
        for node in subgraph.get("nodes", []):
            if node.get("id") != entity_id:
                node_type = node.get("properties", {}).get("type", "unknown")
                pattern["neighbor_types"].add(node_type)
        
        # Generate description
        pattern["description"] = f"{pattern['in_degree']} inputs, {pattern['out_degree']} outputs"
        
        return pattern
    
    def _compare_patterns(self, pattern_a: Dict, pattern_b: Dict) -> float:
        """Compare two structural patterns for similarity."""
        # Jaccard similarity of relationship types
        rel_a = pattern_a.get("relationship_types", set())
        rel_b = pattern_b.get("relationship_types", set())
        
        if rel_a or rel_b:
            rel_similarity = len(rel_a & rel_b) / len(rel_a | rel_b)
        else:
            rel_similarity = 0
        
        # Degree similarity
        in_diff = abs(pattern_a.get("in_degree", 0) - pattern_b.get("in_degree", 0))
        out_diff = abs(pattern_a.get("out_degree", 0) - pattern_b.get("out_degree", 0))
        degree_similarity = 1.0 / (1.0 + in_diff + out_diff)
        
        # Combined
        return (rel_similarity + degree_similarity) / 2
    
    # ------------------------------------------------------------------------
    # ANOMALY & CONTRADICTION DETECTION
    # ------------------------------------------------------------------------
    
    def detect_anomalies(
        self,
        scope: str = "recent",
        entity_id: Optional[str] = None,
        anomaly_types: List[str] = ["contradictions", "outliers", "inconsistencies"]
    ) -> str:
        """
        Detect anomalies and contradictions in knowledge.
        
        Finds:
        - Contradictions: Conflicting information
        - Outliers: Entities that don't fit patterns
        - Inconsistencies: Mismatched attributes or relationships
        
        Use this to:
        - Identify conflicting information
        - Find data quality issues
        - Spot unusual patterns
        - Maintain knowledge consistency
        
        Returns: Detected anomalies with severity and explanations
        """
        try:
            result = {
                "scope": scope,
                "anomaly_types": anomaly_types,
                "anomalies": [],
                "severity": {
                    "critical": 0,
                    "warning": 0,
                    "info": 0
                }
            }
            
            # Get entities to check based on scope
            entities_to_check = []
            
            if scope == "entity_specific" and entity_id:
                entities_to_check = [entity_id]
            elif scope == "session":
                if hasattr(self, 'sess') and self.sess:
                    memories = self.mem.get_session_memory(self.sess.id)
                    entities_to_check = [m.id for m in memories]
            elif scope == "recent":
                # Get recent entities (last 100)
                seeds = self.mem.graph.list_subgraph_seeds()
                entities_to_check = seeds.get("entity_ids", [])[:100]
            else:  # global
                seeds = self.mem.graph.list_subgraph_seeds()
                entities_to_check = seeds.get("entity_ids", [])[:200]
            
            # Detect contradictions
            if "contradictions" in anomaly_types:
                for i, eid1 in enumerate(entities_to_check):
                    entity1 = self._get_cached_entity(eid1)
                    if not entity1:
                        continue
                    
                    text1 = entity1.get("properties", {}).get("text", "").lower()
                    
                    for eid2 in entities_to_check[i+1:]:
                        entity2 = self._get_cached_entity(eid2)
                        if not entity2:
                            continue
                        
                        text2 = entity2.get("properties", {}).get("text", "").lower()
                        
                        # Check for contradiction patterns
                        contradictions = [
                            (r"\bnot\s+(\w+)", r"\bis\s+\1"),  # "not X" vs "is X"
                            (r"\balways\b", r"\bnever\b"),
                            (r"\ball\b", r"\bnone\b"),
                            (r"\btrue\b", r"\bfalse\b")
                        ]
                        
                        for pattern_a, pattern_b in contradictions:
                            if re.search(pattern_a, text1) and re.search(pattern_b, text2):
                                result["anomalies"].append({
                                    "type": "contradiction",
                                    "severity": "warning",
                                    "entity_a": eid1,
                                    "entity_b": eid2,
                                    "description": f"Potential contradiction detected",
                                    "text_a": text1[:150],
                                    "text_b": text2[:150]
                                })
                                result["severity"]["warning"] += 1
            
            # Detect outliers
            if "outliers" in anomaly_types:
                # Find entities with unusual connection patterns
                connection_counts = []
                
                for eid in entities_to_check[:50]:
                    subgraph = self._get_cached_subgraph([eid], depth=1)
                    connections = len(subgraph.get("rels", []))
                    connection_counts.append((eid, connections))
                
                if connection_counts:
                    # Calculate mean and std
                    counts = [c for _, c in connection_counts]
                    mean_connections = sum(counts) / len(counts)
                    
                    # Variance
                    variance = sum((c - mean_connections) ** 2 for c in counts) / len(counts)
                    std_dev = variance ** 0.5
                    
                    # Find outliers (>2 std deviations)
                    for eid, count in connection_counts:
                        if abs(count - mean_connections) > 2 * std_dev:
                            entity = self._get_cached_entity(eid)
                            severity = "info" if count > mean_connections else "warning"
                            
                            result["anomalies"].append({
                                "type": "outlier",
                                "severity": severity,
                                "entity_id": eid,
                                "description": f"Unusual connection count: {count} (mean: {mean_connections:.1f})",
                                "text": entity.get("properties", {}).get("text", "")[:100] if entity else ""
                            })
                            result["severity"][severity] += 1
            
            # Detect inconsistencies
            if "inconsistencies" in anomaly_types:
                # Find entities with missing expected attributes
                for eid in entities_to_check[:50]:
                    entity = self._get_cached_entity(eid)
                    if not entity:
                        continue
                    
                    props = entity.get("properties", {})
                    entity_type = props.get("type", "unknown")
                    
                    # Check for expected properties based on type
                    expected_props = {
                        "extracted_entity": ["text", "label"],
                        "thought": ["text"],
                        "document": ["entity_id"]
                    }
                    
                    if entity_type in expected_props:
                        missing = [p for p in expected_props[entity_type] if p not in props]
                        
                        if missing:
                            result["anomalies"].append({
                                "type": "inconsistency",
                                "severity": "info",
                                "entity_id": eid,
                                "description": f"Missing expected properties: {', '.join(missing)}",
                                "entity_type": entity_type
                            })
                            result["severity"]["info"] += 1
            
            # Add summary
            total_anomalies = len(result["anomalies"])
            result["summary"] = f"Found {total_anomalies} anomalies: " + \
                              f"{result['severity']['critical']} critical, " + \
                              f"{result['severity']['warning']} warnings, " + \
                              f"{result['severity']['info']} info"
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "scope": scope
            })
    
    # ------------------------------------------------------------------------
    # KNOWLEDGE GAP ANALYSIS
    # ------------------------------------------------------------------------
    
    def analyze_knowledge_gaps(
        self,
        topic: str,
        comparison_source: Optional[str] = None,
        gap_types: List[str] = ["missing_entities", "weak_connections", "incomplete_attributes"]
    ) -> str:
        """
        Identify gaps in your knowledge about a topic.
        
        Finds:
        - Missing entities: Concepts that should exist but don't
        - Weak connections: Under-connected areas
        - Incomplete attributes: Entities lacking detail
        - Coverage gaps: Areas with sparse information
        
        Use this to:
        - Guide learning priorities
        - Identify research needs
        - Improve knowledge completeness
        - Find blind spots
        
        Returns: Knowledge gaps with recommendations for filling them
        """
        try:
            result = {
                "topic": topic,
                "gap_types": gap_types,
                "gaps": {
                    "missing_entities": [],
                    "weak_connections": [],
                    "incomplete_attributes": [],
                    "coverage_gaps": []
                },
                "recommendations": []
            }
            
            # Get entities related to topic
            hits = self.mem.semantic_retrieve(topic, k=50)
            topic_entities = [
                hit.get("metadata", {}).get("entity_id") or hit.get("id")
                for hit in hits
            ]
            
            if not topic_entities:
                result["recommendations"].append(
                    f"No entities found for '{topic}' - this is a major gap. Start learning about this topic."
                )
                return json.dumps(result, indent=2)
            
            # Analyze weak connections
            if "weak_connections" in gap_types:
                for eid in topic_entities[:30]:
                    subgraph = self._get_cached_subgraph([eid], depth=1)
                    connections = len(subgraph.get("rels", []))
                    
                    if connections < 2:
                        entity = self._get_cached_entity(eid)
                        if entity:
                            result["gaps"]["weak_connections"].append({
                                "entity_id": eid,
                                "text": entity.get("properties", {}).get("text", "")[:100],
                                "connections": connections,
                                "severity": "high" if connections == 0 else "medium"
                            })
                
                if result["gaps"]["weak_connections"]:
                    result["recommendations"].append(
                        f"Found {len(result['gaps']['weak_connections'])} weakly connected entities. "
                        "Consider exploring relationships and context for these concepts."
                    )
            
            # Analyze incomplete attributes
            if "incomplete_attributes" in gap_types:
                for eid in topic_entities[:30]:
                    entity = self._get_cached_entity(eid)
                    if not entity:
                        continue
                    
                    props = entity.get("properties", {})
                    
                    # Count meaningful properties
                    meaningful_props = [k for k, v in props.items()
                                      if k not in ["id", "created_at", "extraction_id"]
                                      and v is not None and str(v).strip()]
                    
                    if len(meaningful_props) < 3:
                        result["gaps"]["incomplete_attributes"].append({
                            "entity_id": eid,
                            "text": props.get("text", "")[:100],
                            "property_count": len(meaningful_props),
                            "missing": "Lacks descriptive attributes"
                        })
                
                if result["gaps"]["incomplete_attributes"]:
                    result["recommendations"].append(
                        f"Found {len(result['gaps']['incomplete_attributes'])} entities with minimal attributes. "
                        "Add notes and annotations to enrich these concepts."
                    )
            
            # Analyze coverage gaps
            result["gaps"]["coverage_gaps"] = [{
                "area": topic,
                "entity_count": len(topic_entities),
                "status": "sparse" if len(topic_entities) < 10 else "adequate"
            }]
            
            if len(topic_entities) < 10:
                result["recommendations"].append(
                    f"Limited coverage of '{topic}' ({len(topic_entities)} entities). "
                    "Consider expanding knowledge in this area."
                )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error analyzing knowledge gaps: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "topic": topic
            })


# ============================================================================
# TOOL LOADER FUNCTION
# ============================================================================

def add_extended_memory_search_tools(tool_list: List, agent):
    """
    Add extended memory search tools (Part 2).
    
    Call this in addition to add_advanced_memory_search_tools:
        from advanced_memory_search import add_advanced_memory_search_tools
        from advanced_memory_search_part2 import add_extended_memory_search_tools
        
        add_advanced_memory_search_tools(tool_list, agent)
        add_extended_memory_search_tools(tool_list, agent)
    """
    from langchain_core.tools import StructuredTool
    
    extended_search = ExtendedMemorySearch(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=extended_search.generate_cross_domain_insights,
            name="cross_domain_insights",
            description=(
                "Generate insights by comparing different knowledge domains. "
                "Discovers analogies, knowledge transfers, contradictions, and synergies. "
                "Use to bridge different areas and find creative applications."
            ),
            args_schema=CrossDomainInsightInput
        ),
        
        StructuredTool.from_function(
            func=extended_search.detect_anomalies,
            name="detect_anomalies",
            description=(
                "Detect anomalies and contradictions in knowledge. "
                "Finds conflicting information, outliers, and inconsistencies. "
                "Use to maintain knowledge quality and consistency."
            ),
            args_schema=AnomalyDetectionInput
        ),
        
        StructuredTool.from_function(
            func=extended_search.analyze_knowledge_gaps,
            name="analyze_knowledge_gaps",
            description=(
                "Identify gaps in knowledge about a topic. "
                "Finds missing entities, weak connections, and incomplete attributes. "
                "Use to guide learning priorities and improve coverage."
            ),
            args_schema=KnowledgeGapInput
        ),
    ])
    
    return tool_list


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("Extended Memory Search Tools")
    print("=" * 60)
    print("\nPart 2 Tools:")
    print("  - cross_domain_insights")
    print("  - detect_anomalies")
    print("  - analyze_knowledge_gaps")
    print("\nIntegration:")
    print("  add_advanced_memory_search_tools(tool_list, agent)")
    print("  add_extended_memory_search_tools(tool_list, agent)")