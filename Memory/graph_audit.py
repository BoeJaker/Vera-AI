from neo4j import GraphDatabase
import pandas as pd
from typing import List, Dict, Any, Optional
import json
import os
import sys

class Neo4jGraphAuditor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.resolutions_file = "Output/graph_audit_resolutions.json"
        self.resolutions = self.load_resolutions()
    
    def close(self):
        self.driver.close()
    
    def load_resolutions(self):
        """Load previously saved resolutions"""
        if os.path.exists(self.resolutions_file):
            with open(self.resolutions_file, 'r') as f:
                return json.load(f)
        return {
            "ignored_issues": [],
            "resolved_issues": [],
            "custom_fixes": {}
        }
    
    def save_resolutions(self):
        """Save resolutions to file"""
        with open(self.resolutions_file, 'w') as f:
            json.dump(self.resolutions, f, indent=2)
    
    def is_issue_ignored(self, issue_type, issue_key):
        """Check if an issue is ignored"""
        for ignored in self.resolutions["ignored_issues"]:
            if ignored.get("type") == issue_type and ignored.get("key") == issue_key:
                return True
        return False
    
    def is_issue_resolved(self, issue_type, issue_key):
        """Check if an issue is marked as resolved"""
        for resolved in self.resolutions["resolved_issues"]:
            if resolved.get("type") == issue_type and resolved.get("key") == issue_key:
                return True
        return False
    
    def mark_issue_ignored(self, issue_type, issue_key, reason=""):
        """Mark an issue as ignored"""
        self.resolutions["ignored_issues"].append({
            "type": issue_type,
            "key": issue_key,
            "reason": reason,
            "timestamp": pd.Timestamp.now().isoformat()
        })
        self.save_resolutions()
    
    def mark_issue_resolved(self, issue_type, issue_key, resolution_method=""):
        """Mark an issue as resolved"""
        self.resolutions["resolved_issues"].append({
            "type": issue_type,
            "key": issue_key,
            "resolution_method": resolution_method,
            "timestamp": pd.Timestamp.now().isoformat()
        })
        self.save_resolutions()
    
    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]
    
    def safe_to_string(self, value):
        """Safely convert any value to string, handling arrays and complex types"""
        if value is None:
            return ""
        try:
            return str(value)
        except:
            return "[Unable to convert to string]"
    
    def get_database_stats(self):
        """Get basic database statistics without APOC"""
        stats = {}
        
        # Node count
        query = "MATCH (n) RETURN count(n) as nodeCount"
        stats['nodeCount'] = self.run_query(query)[0]['nodeCount']
        
        # Relationship count
        query = "MATCH ()-[r]->() RETURN count(r) as relCount"
        stats['relCount'] = self.run_query(query)[0]['relCount']
        
        # Labels
        query = """
        MATCH (n) 
        UNWIND labels(n) as label 
        RETURN label, count(*) as count
        """
        labels_result = self.run_query(query)
        stats['labels'] = {item['label']: item['count'] for item in labels_result}
        
        # Relationship types
        query = """
        MATCH ()-[r]->() 
        RETURN type(r) as type, count(*) as count
        """
        rels_result = self.run_query(query)
        stats['relTypes'] = {item['type']: item['count'] for item in rels_result}
        
        return stats
    
    def find_orphaned_nodes(self):
        """Find nodes with no relationships"""
        query = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN labels(n) as labels, count(*) as count
        ORDER BY count DESC
        """
        return self.run_query(query)
    
    def resolve_orphaned_nodes(self, action="delete"):
        """Resolve orphaned nodes"""
        if action == "delete":
            query = """
            MATCH (n)
            WHERE NOT (n)--()
            WITH n LIMIT 1000
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
            result = self.run_query(query)
            return f"Deleted {result[0]['deleted_count']} orphaned nodes"
        elif action == "connect_to_root":
            # Create a root node and connect orphaned nodes to it
            query = """
            MERGE (root:OrphanRoot {name: 'Orphaned Nodes Root'})
            WITH root
            MATCH (n)
            WHERE NOT (n)--() AND n <> root
            WITH n, root LIMIT 1000
            MERGE (n)-[:ORPHAN_LINK]->(root)
            RETURN count(n) as connected_count
            """
            result = self.run_query(query)
            return f"Connected {result[0]['connected_count']} orphaned nodes to root"
        
        return "No action taken"
    
    def find_high_degree_nodes(self, threshold=100):
        """Find nodes with very high degree"""
        query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]-()
        WITH n, labels(n) as labels, count(r) as degree
        WHERE degree > $threshold
        RETURN labels, elementId(n) as node_id, degree
        ORDER BY degree DESC
        """
        return self.run_query(query, {"threshold": threshold})
    
    def resolve_high_degree_nodes(self, node_id, action="add_clustering"):
        """Resolve high degree nodes"""
        if action == "add_clustering":
            # Add a clustering property to help with visualization
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            SET n.high_degree_cluster = true
            RETURN n
            """
            self.run_query(query, {"node_id": node_id})
            return f"Added clustering property to node {node_id}"
        
        return "No action taken"
    
    def check_property_lengths(self, max_length=100):
        """Find properties with very long values"""
        query = """
        MATCH (n)
        UNWIND keys(n) as key
        RETURN labels(n) as labels, key, n[key] as raw_value, elementId(n) as node_id
        LIMIT 1000
        """
        results = self.run_query(query)
        
        long_properties = []
        for item in results:
            try:
                value_str = self.safe_to_string(item['raw_value'])
                if len(value_str) > max_length:
                    long_properties.append({
                        'labels': item['labels'],
                        'key': item['key'],
                        'length': len(value_str),
                        'preview': value_str[:50] + "..." if len(value_str) > 50 else value_str,
                        'node_id': item['node_id']
                    })
            except Exception as e:
                long_properties.append({
                    'labels': item['labels'],
                    'key': item['key'],
                    'length': -1,
                    'preview': f"[Conversion error: {str(e)}]",
                    'node_id': item['node_id']
                })
        
        return sorted(long_properties, key=lambda x: x['length'], reverse=True)[:50]
    
    def resolve_long_property(self, node_id, property_key, action="truncate"):
        """Resolve long property values"""
        if action == "truncate":
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            WITH n, n[$property_key] as original_value
            SET n[$property_key] = substring(toString(original_value), 0, 100)
            RETURN n[$property_key] as new_value
            """
            result = self.run_query(query, {"node_id": node_id, "property_key": property_key})
            return f"Truncated {property_key} to 100 characters"
        elif action == "move_to_separate_node":
            # Create a separate node for long text
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            WITH n, n[$property_key] as long_value
            CREATE (textNode:LongText {value: substring(toString(long_value), 0, 500)})
            MERGE (n)-[:HAS_LONG_TEXT]->(textNode)
            REMOVE n[$property_key]
            RETURN textNode
            """
            self.run_query(query, {"node_id": node_id, "property_key": property_key})
            return f"Moved long {property_key} to separate node"
        
        return "No action taken"
    
    def check_data_types(self):
        """Check for problematic data types"""
        query = """
        MATCH (n)
        UNWIND keys(n) as key
        RETURN labels(n) as labels, key, n[key] as raw_value, elementId(n) as node_id
        LIMIT 500
        """
        results = self.run_query(query)
        
        type_issues = []
        for item in results:
            raw_value = item['raw_value']
            value_str = self.safe_to_string(raw_value)
            
            if isinstance(raw_value, list):
                type_issues.append({
                    'labels': item['labels'],
                    'key': item['key'],
                    'value_preview': value_str[:100],
                    'issue_type': 'Array property',
                    'node_id': item['node_id']
                })
            
            key_fields = ['id', 'name', 'title', 'label']
            if item['key'].lower() in key_fields and len(value_str) > 50:
                type_issues.append({
                    'labels': item['labels'],
                    'key': item['key'],
                    'value_preview': value_str[:50],
                    'issue_type': 'Long identifier',
                    'node_id': item['node_id']
                })
        
        return type_issues[:20]
    
    def resolve_array_property(self, node_id, property_key, action="convert_to_string"):
        """Resolve array properties"""
        if action == "convert_to_string":
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            WITH n, n[$property_key] as array_value
            SET n[$property_key] = substring(toString(array_value), 0, 200)
            RETURN n[$property_key] as new_value
            """
            result = self.run_query(query, {"node_id": node_id, "property_key": property_key})
            return f"Converted array {property_key} to string"
        elif action == "create_relationships":
            # Create nodes for each array element and relationships
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            WITH n, n[$property_key] as array_value
            UNWIND array_value as element
            CREATE (elementNode:ArrayElement {value: toString(element)})
            MERGE (n)-[:HAS_ELEMENT]->(elementNode)
            REMOVE n[$property_key]
            RETURN count(elementNode) as elements_created
            """
            result = self.run_query(query, {"node_id": node_id, "property_key": property_key})
            return f"Created {result[0]['elements_created']} element nodes"
        
        return "No action taken"
    
    def find_duplicate_nodes(self, properties_to_check=None):
        """Find potentially duplicate nodes"""
        if properties_to_check:
            results = []
            for prop in properties_to_check:
                query = f"""
                MATCH (n)
                WHERE n.{prop} IS NOT NULL
                WITH n.{prop} as value, collect(elementId(n)) as node_ids
                WHERE size(node_ids) > 1
                RETURN '{prop}' as property, value, size(node_ids) as duplicate_count, node_ids
                ORDER BY duplicate_count DESC
                LIMIT 10
                """
                results.extend(self.run_query(query))
            return results
        else:
            query = """
            MATCH (n)
            WHERE n.name IS NOT NULL OR n.title IS NOT NULL OR n.id IS NOT NULL
            WITH 
                coalesce(n.name, n.title, n.id) as identifier,
                labels(n) as node_labels,
                collect(elementId(n)) as node_ids
            WHERE size(node_ids) > 1
            RETURN node_labels, identifier, size(node_ids) as duplicate_count, node_ids
            ORDER BY duplicate_count DESC
            LIMIT 20
            """
            return self.run_query(query)
    
    def resolve_duplicate_nodes(self, node_ids, action="merge"):
        """Resolve duplicate nodes"""
        if action == "merge" and len(node_ids) > 1:
            # Keep the first node, merge properties from others, then delete duplicates
            keep_node_id = node_ids[0]
            delete_node_ids = node_ids[1:]
            
            # Merge properties (this is a simplified version)
            query = """
            MATCH (keep) WHERE elementId(keep) = $keep_node_id
            MATCH (dup) WHERE elementId(dup) IN $delete_node_ids
            WITH keep, dup
            UNWIND keys(dup) as key
            WITH keep, key, collect(distinct dup[key]) as values
            WHERE keep[key] IS NULL AND size(values) = 1
            SET keep[key] = values[0]
            RETURN count(key) as properties_merged
            """
            self.run_query(query, {"keep_node_id": keep_node_id, "delete_node_ids": delete_node_ids})
            
            # Delete duplicate nodes
            query = """
            MATCH (n) WHERE elementId(n) IN $delete_node_ids
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
            result = self.run_query(query, {"delete_node_ids": delete_node_ids})
            
            return f"Merged properties and deleted {result[0]['deleted_count']} duplicates"
        
        return "No action taken"
    
    def analyze_relationship_distribution(self):
        """Analyze relationship types and their frequencies"""
        query = """
        MATCH ()-[r]->()
        RETURN type(r) as relationship_type, count(*) as count
        ORDER BY count DESC
        """
        return self.run_query(query)
    
    def find_isolated_subgraphs(self):
        """Find disconnected components in the graph"""
        query = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN labels(n) as labels, count(*) as isolated_count
        ORDER BY isolated_count DESC
        """
        return self.run_query(query)
    
    def check_missing_properties(self, important_properties=None):
        """Check for nodes missing important properties"""
        results = []
        
        if important_properties:
            for prop in important_properties:
                query = f"""
                MATCH (n)
                WHERE n.{prop} IS NULL
                RETURN labels(n) as labels, count(*) as missing_count
                ORDER BY missing_count DESC
                """
                results.extend(self.run_query(query))
        
        return results
    
    def find_self_relationships(self):
        """Find relationships where start and end node are the same"""
        query = """
        MATCH (n)-[r]->(n)
        RETURN labels(n) as labels, type(r) as relationship_type, count(*) as count
        ORDER BY count DESC
        """
        return self.run_query(query)
    
    def check_relationship_properties(self):
        """Check for relationships with problematic properties"""
        # Handle relationship properties in Python to avoid type conversion issues
        query = """
        MATCH ()-[r]->()
        UNWIND keys(r) as key
        RETURN type(r) as rel_type, key, r[key] as raw_value
        LIMIT 500
        """
        results = self.run_query(query)
        
        problematic_rels = []
        for item in results:
            try:
                value_str = self.safe_to_string(item['raw_value'])
                if len(value_str) > 50:
                    problematic_rels.append({
                        'rel_type': item['rel_type'],
                        'key': item['key'],
                        'length': len(value_str),
                        'preview': value_str[:30]
                    })
            except Exception as e:
                problematic_rels.append({
                    'rel_type': item['rel_type'],
                    'key': item['key'],
                    'length': -1,
                    'preview': f"[Error: {str(e)}]"
                })
        
        return sorted(problematic_rels, key=lambda x: x['length'], reverse=True)[:20]
    
    def find_empty_labels(self):
        """Find nodes with empty string labels or properties"""
        query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE trim(label) = '')
        RETURN labels(n) as labels, count(*) as count
        """
        empty_labels = self.run_query(query)
        
        # Also check for empty property values - FIXED SYNTAX
        query_empty_props = """
        MATCH (n)
        UNWIND keys(n) as key
        WITH n, key
        WHERE n[key] = ''
        RETURN labels(n) as labels, key, count(*) as count
        ORDER BY count DESC
        LIMIT 10
        """
        empty_props = self.run_query(query_empty_props)
        
        return {
            'empty_labels': empty_labels,
            'empty_properties': empty_props
        }
    
    def detect_array_properties(self):
        """Specifically detect and analyze array properties"""
        query = """
        MATCH (n)
        UNWIND keys(n) as key
        RETURN labels(n) as labels, key, n[key] as value
        LIMIT 1000
        """
        results = self.run_query(query)
        
        array_props = []
        for item in results:
            if isinstance(item['value'], list):
                array_props.append({
                    'labels': item['labels'],
                    'key': item['key'],
                    'array_length': len(item['value']),
                    'preview': str(item['value'])[:100]
                })
        
        return array_props
    
    def check_unicode_and_special_chars(self):
        """Check for problematic Unicode characters or special chars"""
        query = """
        MATCH (n)
        UNWIND keys(n) as key
        WITH n, key, n[key] as value
        WHERE value IS NOT NULL AND 
              (toString(value) CONTAINS '\\u0000' OR 
               toString(value) CONTAINS '\\n' OR
               toString(value) CONTAINS '\\t' OR
               toString(value) CONTAINS '\\r')
        RETURN labels(n) as labels, key, 
               substring(toString(value), 0, 50) as preview,
               'Special characters' as issue_type
        LIMIT 20
        """
        try:
            return self.run_query(query)
        except:
            return []
    
    def find_circular_references(self, max_depth=3):
        """Find potential circular references in the graph"""
        query = """
        MATCH path = (a)-[*1..$max_depth]->(a)
        RETURN labels(a) as labels, 
               length(path) as path_length,
               [r IN relationships(path) | type(r)] as rel_types,
               count(*) as count
        ORDER BY count DESC
        LIMIT 10
        """
        try:
            return self.run_query(query, {"max_depth": max_depth})
        except:
            return []
    
    def generate_audit_report(self, output_file="Output/graph_audit_report.json"):
        """Generate a comprehensive audit report"""
        print("Generating audit report...")
        
        report = {
            "database_statistics": self.get_database_stats(),
            "orphaned_nodes": self.find_orphaned_nodes(),
            "high_degree_nodes": self.find_high_degree_nodes(threshold=50),
            "long_properties": self.check_property_lengths(),
            "data_type_issues": self.check_data_types(),
            "relationship_distribution": self.analyze_relationship_distribution(),
            "duplicate_nodes": self.find_duplicate_nodes(),
            "isolated_nodes": self.find_isolated_subgraphs(),
            "self_relationships": self.find_self_relationships(),
            "relationship_properties": self.check_relationship_properties(),
            "empty_labels": self.find_empty_labels(),
            "array_properties": self.detect_array_properties(),
            "unicode_issues": self.check_unicode_and_special_chars(),
            "circular_references": self.find_circular_references(),
            "resolutions": self.resolutions
        }
        
        with open(output_file, 'w') as f:
            class CustomEncoder(json.JSONEncoder):
                def default(self, obj):
                    try:
                        return super().default(obj)
                    except:
                        return str(obj)
            json.dump(report, f, indent=2, cls=CustomEncoder)
        
        return report
    
    def print_summary(self):
        """Print a summary of potential issues"""
        print("Collecting database statistics...")
        stats = self.get_database_stats()
        
        print("=== Neo4j Graph Database Audit Summary ===")
        print(f"Total Nodes: {stats['nodeCount']}")
        print(f"Total Relationships: {stats['relCount']}")
        print(f"Labels: {list(stats['labels'].keys())}")
        print(f"Relationship Types: {list(stats['relTypes'].keys())}")
        print()
        
        # Orphaned nodes
        print("Checking for orphaned nodes...")
        orphans = self.find_orphaned_nodes()
        if orphans and any(orphan['count'] > 0 for orphan in orphans):
            print("⚠️  Orphaned Nodes (no relationships):")
            for orphan in orphans:
                if orphan['count'] > 0:
                    print(f"   {orphan['labels']}: {orphan['count']}")
        else:
            print("✓ No orphaned nodes found")
        print()
        
        # High degree nodes
        print("Checking for high-degree nodes...")
        high_degree = self.find_high_degree_nodes(threshold=50)
        if high_degree:
            print("⚠️  High Degree Nodes (may cause visualization issues):")
            for node in high_degree[:5]:
                print(f"   {node['labels']} (ID: {node['node_id'][:20]}...): {node['degree']} connections")
        else:
            print("✓ No extremely high-degree nodes found")
        print()
        
        # Data type issues
        print("Checking for data type issues...")
        type_issues = self.check_data_types()
        if type_issues:
            print("⚠️  Data Type Issues:")
            for issue in type_issues[:5]:
                print(f"   {issue['labels']}.{issue['key']}: {issue['issue_type']}")
                print(f"     Preview: {issue.get('value_preview', 'N/A')}")
        else:
            print("✓ No major data type issues found")
        print()
        
        # Array properties
        print("Checking for array properties...")
        array_props = self.detect_array_properties()
        if array_props:
            print("⚠️  Array Properties (may not visualize well):")
            for prop in array_props[:5]:
                print(f"   {prop['labels']}.{prop['key']}: {prop['array_length']} items")
                print(f"     Preview: {prop['preview']}")
        else:
            print("✓ No array properties found")
        print()
        
        # Self relationships
        print("Checking for self-relationships...")
        self_rels = self.find_self_relationships()
        if self_rels:
            print("⚠️  Self Relationships:")
            for rel in self_rels:
                print(f"   {rel['labels']} -[{rel['relationship_type']}]-> {rel['labels']}: {rel['count']}")
        else:
            print("✓ No self-relationships found")
        print()
        
        # Relationship distribution
        print("Checking relationship distribution...")
        rel_dist = self.analyze_relationship_distribution()
        if rel_dist:
            print("📊 Relationship Distribution:")
            for rel in rel_dist[:5]:
                print(f"   {rel['relationship_type']}: {rel['count']}")
        print()
    
    def interactive_resolution(self):
        """Interactive mode to resolve issues one by one"""
        print("\n=== Interactive Issue Resolution ===")
        
        issues = self.collect_all_issues()
        
        for i, issue in enumerate(issues, 1):
            if self.is_issue_ignored(issue['type'], issue.get('key', '')):
                continue
                
            if self.is_issue_resolved(issue['type'], issue.get('key', '')):
                continue
            
            print(f"\n--- Issue {i}/{len(issues)} ---")
            print(f"Type: {issue['type']}")
            print(f"Description: {issue.get('description', 'N/A')}")
            print(f"Details: {issue.get('details', {})}")
            
            while True:
                print("\nOptions:")
                print("1. Ignore this issue")
                print("2. Ignore all issues of this type")
                print("3. Resolve automatically")
                print("4. Resolve manually")
                print("5. Skip for now")
                print("6. View resolution help")
                
                choice = input("\nChoose an option (1-6): ").strip()
                
                if choice == '1':
                    reason = input("Reason for ignoring: ").strip()
                    self.mark_issue_ignored(issue['type'], issue.get('key', ''), reason)
                    print("✓ Issue ignored")
                    break
                    
                elif choice == '2':
                    reason = input("Reason for ignoring all of this type: ").strip()
                    # Mark all similar issues as ignored
                    for similar_issue in [iss for iss in issues if iss['type'] == issue['type']]:
                        self.mark_issue_ignored(similar_issue['type'], similar_issue.get('key', ''), reason)
                    print(f"✓ All {issue['type']} issues ignored")
                    break
                    
                elif choice == '3':
                    result = self.auto_resolve_issue(issue)
                    if result:
                        print(f"✓ {result}")
                        self.mark_issue_resolved(issue['type'], issue.get('key', ''), "auto")
                    else:
                        print("❌ Could not resolve automatically")
                    break
                    
                elif choice == '4':
                    print("Manual resolution options:")
                    self.show_manual_resolution_options(issue)
                    method = input("Enter resolution method: ").strip()
                    self.mark_issue_resolved(issue['type'], issue.get('key', ''), f"manual: {method}")
                    print("✓ Marked as manually resolved")
                    break
                    
                elif choice == '5':
                    print("Skipping...")
                    break
                    
                elif choice == '6':
                    self.show_resolution_help(issue['type'])
                    
                else:
                    print("Invalid choice, please try again")
    
    def collect_all_issues(self):
        """Collect all issues from the audit"""
        issues = []
        
        # Orphaned nodes
        orphans = self.find_orphaned_nodes()
        for orphan in orphans:
            if orphan['count'] > 0:
                issues.append({
                    'type': 'orphaned_nodes',
                    'key': f"orphaned_{orphan['labels']}",
                    'description': f"{orphan['count']} orphaned nodes with labels {orphan['labels']}",
                    'details': orphan
                })
        
        # High degree nodes
        high_degree = self.find_high_degree_nodes(threshold=50)
        for node in high_degree:
            issues.append({
                'type': 'high_degree_node',
                'key': node['node_id'],
                'description': f"High degree node ({node['degree']} connections) with labels {node['labels']}",
                'details': node
            })
        
        # Long properties
        long_props = self.check_property_lengths()
        for prop in long_props:
            issues.append({
                'type': 'long_property',
                'key': f"{prop['node_id']}_{prop['key']}",
                'description': f"Long property {prop['key']} ({prop['length']} chars) in {prop['labels']}",
                'details': prop
            })
        
        # Data type issues
        type_issues = self.check_data_types()
        for issue in type_issues:
            issues.append({
                'type': 'data_type_issue',
                'key': f"{issue['node_id']}_{issue['key']}",
                'description': f"{issue['issue_type']} in {issue['labels']}.{issue['key']}",
                'details': issue
            })
        
        # Duplicate nodes
        duplicates = self.find_duplicate_nodes()
        for dup in duplicates:
            issues.append({
                'type': 'duplicate_nodes',
                'key': f"duplicate_{dup.get('identifier', 'unknown')}",
                'description': f"{dup['duplicate_count']} duplicate nodes with identifier {dup.get('identifier', 'unknown')}",
                'details': dup
            })
        
        return issues
    
    def auto_resolve_issue(self, issue):
        """Attempt to automatically resolve an issue"""
        issue_type = issue['type']
        details = issue['details']
        
        try:
            if issue_type == 'orphaned_nodes':
                return self.resolve_orphaned_nodes("connect_to_root")
            elif issue_type == 'high_degree_node':
                return self.resolve_high_degree_nodes(details['node_id'], "add_clustering")
            elif issue_type == 'long_property':
                return self.resolve_long_property(details['node_id'], details['key'], "truncate")
            elif issue_type == 'data_type_issue' and details['issue_type'] == 'Array property':
                return self.resolve_array_property(details['node_id'], details['key'], "convert_to_string")
            elif issue_type == 'duplicate_nodes':
                return self.resolve_duplicate_nodes(details['node_ids'], "merge")
        except Exception as e:
            return f"Auto-resolution failed: {str(e)}"
        
        return None
    
    def show_manual_resolution_options(self, issue):
        """Show manual resolution options for an issue type"""
        issue_type = issue['type']
        
        if issue_type == 'orphaned_nodes':
            print("- Run: MATCH (n) WHERE NOT (n)--() DELETE n")
            print("- Create relationships to connect orphaned nodes")
            print("- Add labels to categorize orphaned nodes")
        
        elif issue_type == 'high_degree_node':
            print("- Add clustering properties")
            print("- Create intermediate nodes to reduce degree")
            print("- Use filtering in visualization")
        
        elif issue_type == 'long_property':
            print("- Truncate the property value")
            print("- Move to a separate node")
            print("- Split into multiple properties")
        
        elif issue_type == 'data_type_issue':
            print("- Convert arrays to strings")
            print("- Create relationships for array elements")
            print("- Normalize data types")
        
        elif issue_type == 'duplicate_nodes':
            print("- Merge duplicate nodes")
            print("- Add distinguishing properties")
            print("- Create hierarchy relationships")
    
    def show_resolution_help(self, issue_type):
        """Show help for resolving specific issue types"""
        help_texts = {
            'orphaned_nodes': """
Orphaned nodes have no relationships. They can:
- Be deleted if not needed
- Be connected to other nodes
- Be categorized with special labels
            """,
            'high_degree_node': """
High degree nodes can cause visualization performance issues:
- Use clustering algorithms
- Add intermediate nodes
- Filter in visualization tools
            """,
            'long_property': """
Long properties can clutter visualizations:
- Truncate for display purposes
- Store in separate nodes
- Use summary properties
            """,
            'data_type_issue': """
Data type issues affect consistency:
- Convert arrays to appropriate formats
- Ensure consistent typing
- Use proper Neo4j data types
            """,
            'duplicate_nodes': """
Duplicate nodes indicate data quality issues:
- Merge nodes with same identifiers
- Add unique constraints
- Establish clear entity resolution rules
            """
        }
        
        print(help_texts.get(issue_type, "No specific help available for this issue type."))

# Example usage with interactive mode
if __name__ == "__main__":
    try:
        auditor = Neo4jGraphAuditor(
            uri="bolt://localhost:7687",
            user="neo4j", 
            password="your_password_here"
        )
        
        print("Testing database connection...")
        stats = auditor.get_database_stats()
        print("✓ Connected successfully!")
        
        # Generate report
        report = auditor.generate_audit_report()
        
        # Print summary
        auditor.print_summary()
        
        # Ask if user wants interactive resolution
        response = input("\nWould you like to resolve issues interactively? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            auditor.interactive_resolution()
        
        print(f"\n✓ Audit completed! Report saved to Output/graph_audit_report.json")
        print(f"✓ Resolutions saved to {auditor.resolutions_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'auditor' in locals():
            auditor.close()