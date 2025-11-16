"""
Additional Tools for SSH, PostgreSQL, and Neo4j
Add these to your existing tools.py file
"""

import paramiko
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import io
from contextlib import contextmanager
from langchain_core.tools import tool, StructuredTool
from Vera.Toolchain.schemas import *
# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class SSHConnectionInput(BaseModel):
    """Input schema for SSH connection."""
    host: str = Field(..., description="SSH host address")
    username: str = Field(..., description="SSH username")
    password: Optional[str] = Field(None, description="SSH password (if not using key)")
    key_path: Optional[str] = Field(None, description="Path to SSH private key file")
    port: int = Field(default=22, description="SSH port (default: 22)")


class SSHCommandInput(BaseModel):
    """Input schema for SSH command execution."""
    connection_id: str = Field(..., description="SSH connection ID from connect_ssh")
    command: str = Field(..., description="Command to execute on remote server")


class SSHFileInput(BaseModel):
    """Input schema for SSH file operations."""
    connection_id: str = Field(..., description="SSH connection ID")
    remote_path: str = Field(..., description="Remote file/directory path")
    local_path: Optional[str] = Field(None, description="Local file path (for upload/download)")


class PostgresConnectionInput(BaseModel):
    """Input schema for PostgreSQL connection."""
    host: str = Field(..., description="PostgreSQL host address")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    port: int = Field(default=5432, description="PostgreSQL port (default: 5432)")


class PostgresQueryInput(BaseModel):
    """Input schema for PostgreSQL queries."""
    connection_id: str = Field(..., description="Postgres connection ID")
    query: str = Field(..., description="SQL query to execute")
    params: Optional[List[Any]] = Field(None, description="Query parameters for prepared statements")


class Neo4jConnectionInput(BaseModel):
    """Input schema for Neo4j connection."""
    uri: str = Field(..., description="Neo4j URI (e.g., bolt://localhost:7687)")
    username: str = Field(..., description="Neo4j username")
    password: str = Field(..., description="Neo4j password")
    database: Optional[str] = Field("neo4j", description="Database name (default: neo4j)")


class Neo4jQueryInput(BaseModel):
    """Input schema for Neo4j queries."""
    connection_id: str = Field(..., description="Neo4j connection ID")
    query: str = Field(..., description="Cypher query to execute")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters")


# ============================================================================
# CONNECTION MANAGERS
# ============================================================================

class SSHConnectionManager:
    """Manages SSH connections with connection pooling."""
    
    def __init__(self):
        self.connections: Dict[str, paramiko.SSHClient] = {}
        self.sftp_clients: Dict[str, paramiko.SFTPClient] = {}
    
    def create_connection(self, conn_id: str, host: str, username: str, 
                         password: Optional[str] = None, 
                         key_path: Optional[str] = None, 
                         port: int = 22) -> str:
        """Create and store SSH connection."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if key_path:
                key = paramiko.RSAKey.from_private_key_file(key_path)
                client.connect(host, port=port, username=username, pkey=key)
            else:
                client.connect(host, port=port, username=username, password=password)
            
            self.connections[conn_id] = client
            return f"✓ SSH connected: {username}@{host}:{port} [ID: {conn_id}]"
        
        except Exception as e:
            return f"[SSH Connection Error] {str(e)}"
    
    def get_connection(self, conn_id: str) -> Optional[paramiko.SSHClient]:
        """Get existing SSH connection."""
        return self.connections.get(conn_id)
    
    def get_sftp(self, conn_id: str) -> Optional[paramiko.SFTPClient]:
        """Get or create SFTP client for connection."""
        if conn_id not in self.sftp_clients:
            conn = self.get_connection(conn_id)
            if conn:
                self.sftp_clients[conn_id] = conn.open_sftp()
        return self.sftp_clients.get(conn_id)
    
    def close_connection(self, conn_id: str) -> str:
        """Close SSH connection."""
        try:
            if conn_id in self.sftp_clients:
                self.sftp_clients[conn_id].close()
                del self.sftp_clients[conn_id]
            
            if conn_id in self.connections:
                self.connections[conn_id].close()
                del self.connections[conn_id]
                return f"✓ SSH connection closed: {conn_id}"
            
            return f"[Error] Connection not found: {conn_id}"
        except Exception as e:
            return f"[SSH Close Error] {str(e)}"
    
    def list_connections(self) -> List[str]:
        """List active connections."""
        return list(self.connections.keys())


class PostgresConnectionManager:
    """Manages PostgreSQL connections."""
    
    def __init__(self):
        self.connections: Dict[str, psycopg2.extensions.connection] = {}
    
    def create_connection(self, conn_id: str, host: str, database: str,
                         username: str, password: str, port: int = 5432) -> str:
        """Create PostgreSQL connection."""
        try:
            conn = psycopg2.connect(
                host=host,
                database=database,
                user=username,
                password=password,
                port=port
            )
            self.connections[conn_id] = conn
            return f"✓ PostgreSQL connected: {database}@{host}:{port} [ID: {conn_id}]"
        
        except Exception as e:
            return f"[Postgres Connection Error] {str(e)}"
    
    def get_connection(self, conn_id: str) -> Optional[psycopg2.extensions.connection]:
        """Get existing connection."""
        return self.connections.get(conn_id)
    
    def close_connection(self, conn_id: str) -> str:
        """Close connection."""
        try:
            if conn_id in self.connections:
                self.connections[conn_id].close()
                del self.connections[conn_id]
                return f"✓ PostgreSQL connection closed: {conn_id}"
            return f"[Error] Connection not found: {conn_id}"
        except Exception as e:
            return f"[Postgres Close Error] {str(e)}"


class Neo4jConnectionManager:
    """Manages Neo4j connections."""
    
    def __init__(self):
        self.drivers: Dict[str, GraphDatabase.driver] = {}
        self.database_names: Dict[str, str] = {}
    
    def create_connection(self, conn_id: str, uri: str, username: str, 
                         password: str, database: str = "neo4j") -> str:
        """Create Neo4j connection."""
        try:
            driver = GraphDatabase.driver(uri, auth=(username, password))
            # Test connection
            driver.verify_connectivity()
            
            self.drivers[conn_id] = driver
            self.database_names[conn_id] = database
            return f"✓ Neo4j connected: {uri} [DB: {database}, ID: {conn_id}]"
        
        except Exception as e:
            return f"[Neo4j Connection Error] {str(e)}"
    
    def get_driver(self, conn_id: str) -> Optional[GraphDatabase.driver]:
        """Get existing driver."""
        return self.drivers.get(conn_id)
    
    def get_database(self, conn_id: str) -> str:
        """Get database name for connection."""
        return self.database_names.get(conn_id, "neo4j")
    
    def close_connection(self, conn_id: str) -> str:
        """Close connection."""
        try:
            if conn_id in self.drivers:
                self.drivers[conn_id].close()
                del self.drivers[conn_id]
                if conn_id in self.database_names:
                    del self.database_names[conn_id]
                return f"✓ Neo4j connection closed: {conn_id}"
            return f"[Error] Connection not found: {conn_id}"
        except Exception as e:
            return f"[Neo4j Close Error] {str(e)}"


# ============================================================================
# SSH TOOLS
# ============================================================================

class SSHTools:
    """SSH and SFTP operations."""
    
    def __init__(self, agent):
        self.agent = agent
        self.ssh_manager = SSHConnectionManager()
    
    def connect_ssh(self, host: str, username: str, password: Optional[str] = None,
                   key_path: Optional[str] = None, port: int = 22) -> str:
        """
        Connect to SSH server. Returns connection ID for use in other SSH commands.
        Use either password or key_path for authentication.
        """
        try:
            conn_id = f"ssh_{host}_{username}_{port}"
            result = self.ssh_manager.create_connection(
                conn_id, host, username, password, key_path, port
            )
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id, conn_id, "ssh_connection",
                metadata={"host": host, "username": username, "port": port}
            )
            
            return result
        except Exception as e:
            return f"[SSH Connect Error] {str(e)}"
    
    def ssh_execute(self, connection_id: str, command: str) -> str:
        """
        Execute command on remote SSH server.
        Returns command output (stdout and stderr combined).
        """
        try:
            client = self.ssh_manager.get_connection(connection_id)
            if not client:
                return f"[Error] SSH connection '{connection_id}' not found. Connect first using connect_ssh."
            
            stdin, stdout, stderr = client.exec_command(command)
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            exit_status = stdout.channel.recv_exit_status()
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id, command, "ssh_command",
                metadata={"connection": connection_id, "exit_status": exit_status}
            )
            
            result = f"Exit Status: {exit_status}\n"
            if output:
                result += f"Output:\n{truncate_output(output)}"
            if error:
                result += f"\nErrors:\n{truncate_output(error)}"
            
            return result if output or error else "[No output]"
        
        except Exception as e:
            return f"[SSH Execute Error] {str(e)}"
    
    def ssh_list_directory(self, connection_id: str, remote_path: str = ".") -> str:
        """
        List contents of remote directory via SFTP.
        """
        try:
            sftp = self.ssh_manager.get_sftp(connection_id)
            if not sftp:
                return f"[Error] SSH connection '{connection_id}' not found."
            
            items = sftp.listdir_attr(remote_path)
            
            output = [f"Directory: {remote_path}\n"]
            for item in sorted(items, key=lambda x: x.filename):
                item_type = "[DIR]" if item.st_mode & 0o040000 else "[FILE]"
                size = item.st_size if item.st_size else 0
                output.append(f"{item_type} {item.filename:40s} {size:>12,} bytes")
            
            return "\n".join(output)
        
        except Exception as e:
            return f"[SSH List Error] {str(e)}"
    
    def ssh_read_file(self, connection_id: str, remote_path: str) -> str:
        """
        Read contents of remote file via SFTP.
        """
        try:
            sftp = self.ssh_manager.get_sftp(connection_id)
            if not sftp:
                return f"[Error] SSH connection '{connection_id}' not found."
            
            with sftp.open(remote_path, 'r') as f:
                content = f.read().decode('utf-8')
            
            return truncate_output(content)
        
        except Exception as e:
            return f"[SSH Read Error] {str(e)}"
    
    def ssh_download_file(self, connection_id: str, remote_path: str, local_path: str) -> str:
        """
        Download file from remote server via SFTP.
        """
        try:
            sftp = self.ssh_manager.get_sftp(connection_id)
            if not sftp:
                return f"[Error] SSH connection '{connection_id}' not found."
            
            sftp.get(remote_path, local_path)
            
            size = os.path.getsize(local_path)
            return f"✓ Downloaded: {remote_path} → {local_path} ({size:,} bytes)"
        
        except Exception as e:
            return f"[SSH Download Error] {str(e)}"
    
    def ssh_upload_file(self, connection_id: str, local_path: str, remote_path: str) -> str:
        """
        Upload file to remote server via SFTP.
        """
        try:
            sftp = self.ssh_manager.get_sftp(connection_id)
            if not sftp:
                return f"[Error] SSH connection '{connection_id}' not found."
            
            if not os.path.exists(local_path):
                return f"[Error] Local file not found: {local_path}"
            
            sftp.put(local_path, remote_path)
            
            size = os.path.getsize(local_path)
            return f"✓ Uploaded: {local_path} → {remote_path} ({size:,} bytes)"
        
        except Exception as e:
            return f"[SSH Upload Error] {str(e)}"
    
    def ssh_disconnect(self, connection_id: str) -> str:
        """
        Close SSH connection and clean up resources.
        """
        return self.ssh_manager.close_connection(connection_id)


# ============================================================================
# POSTGRESQL TOOLS
# ============================================================================

class PostgresTools:
    """PostgreSQL database operations."""
    
    def __init__(self, agent):
        self.agent = agent
        self.pg_manager = PostgresConnectionManager()
    
    def connect_postgres(self, host: str, database: str, username: str,
                        password: str, port: int = 5432) -> str:
        """
        Connect to PostgreSQL database. Returns connection ID for use in other postgres commands.
        """
        try:
            conn_id = f"pg_{host}_{database}_{port}"
            result = self.pg_manager.create_connection(
                conn_id, host, database, username, password, port
            )
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id, conn_id, "postgres_connection",
                metadata={"host": host, "database": database, "port": port}
            )
            
            return result
        except Exception as e:
            return f"[Postgres Connect Error] {str(e)}"
    
    def postgres_query(self, connection_id: str, query: str, 
                      params: Optional[List] = None) -> str:
        """
        Execute PostgreSQL query (SELECT, INSERT, UPDATE, DELETE).
        Returns results for SELECT, row count for modifications.
        Use params for safe parameterized queries.
        """
        try:
            conn = self.pg_manager.get_connection(connection_id)
            if not conn:
                return f"[Error] Postgres connection '{connection_id}' not found. Connect first."
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                # Store query in memory
                self.agent.mem.add_session_memory(
                    self.agent.sess.id, query, "postgres_query",
                    metadata={"connection": connection_id}
                )
                
                # Handle SELECT queries
                if query.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    
                    if not results:
                        return "[No results]"
                    
                    # Format as table
                    output = [f"Rows returned: {len(results)}\n"]
                    
                    if len(results) <= 100:
                        output.append(format_json(results))
                    else:
                        output.append(f"[Large result set: {len(results)} rows]")
                        output.append(format_json(results[:50]))
                        output.append(f"\n... [{len(results) - 50} more rows]")
                    
                    return "\n".join(output)
                
                # Handle modification queries
                else:
                    conn.commit()
                    return f"✓ Query executed. Rows affected: {cursor.rowcount}"
        
        except Exception as e:
            return f"[Postgres Query Error] {str(e)}"
    
    def postgres_list_tables(self, connection_id: str, schema: str = "public") -> str:
        """
        List all tables in a schema with row counts.
        """
        try:
            query = """
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                FROM pg_tables 
                WHERE schemaname = %s
                ORDER BY tablename;
            """
            return self.postgres_query(connection_id, query, [schema])
        
        except Exception as e:
            return f"[Postgres List Tables Error] {str(e)}"
    
    def postgres_describe_table(self, connection_id: str, table_name: str, 
                               schema: str = "public") -> str:
        """
        Get detailed table structure including columns, types, and constraints.
        """
        try:
            query = """
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """
            return self.postgres_query(connection_id, query, [schema, table_name])
        
        except Exception as e:
            return f"[Postgres Describe Error] {str(e)}"
    
    def postgres_list_schemas(self, connection_id: str) -> str:
        """
        List all schemas in the database.
        """
        try:
            query = """
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT LIKE 'pg_%' 
                AND schema_name != 'information_schema'
                ORDER BY schema_name;
            """
            return self.postgres_query(connection_id, query)
        
        except Exception as e:
            return f"[Postgres List Schemas Error] {str(e)}"
    
    def postgres_disconnect(self, connection_id: str) -> str:
        """
        Close PostgreSQL connection.
        """
        return self.pg_manager.close_connection(connection_id)


# ============================================================================
# NEO4J TOOLS
# ============================================================================

class Neo4jTools:
    """Neo4j graph database operations."""
    
    def __init__(self, agent):
        self.agent = agent
        self.neo4j_manager = Neo4jConnectionManager()
    
    def connect_neo4j(self, uri: str, username: str, password: str, 
                     database: str = "neo4j") -> str:
        """
        Connect to Neo4j database. Returns connection ID for use in other neo4j commands.
        URI format: bolt://localhost:7687 or neo4j://localhost:7687
        """
        try:
            conn_id = f"neo4j_{uri.replace('://', '_').replace(':', '_')}"
            result = self.neo4j_manager.create_connection(
                conn_id, uri, username, password, database
            )
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id, conn_id, "neo4j_connection",
                metadata={"uri": uri, "database": database}
            )
            
            return result
        except Exception as e:
            return f"[Neo4j Connect Error] {str(e)}"
    
    def neo4j_query(self, connection_id: str, query: str, 
                   parameters: Optional[Dict] = None) -> str:
        """
        Execute Cypher query on Neo4j.
        Use parameters for safe parameterized queries.
        Examples:
        - MATCH (n:Person) RETURN n LIMIT 10
        - CREATE (n:Person {name: $name}) RETURN n
        """
        try:
            driver = self.neo4j_manager.get_driver(connection_id)
            if not driver:
                return f"[Error] Neo4j connection '{connection_id}' not found. Connect first."
            
            database = self.neo4j_manager.get_database(connection_id)
            parameters = parameters or {}
            
            with driver.session(database=database) as session:
                result = session.run(query, parameters)
                records = list(result)
                
                # Store query in memory
                self.agent.mem.add_session_memory(
                    self.agent.sess.id, query, "neo4j_query",
                    metadata={"connection": connection_id}
                )
                
                if not records:
                    return "[No results]"
                
                # Format results
                output = [f"Records returned: {len(records)}\n"]
                
                formatted_records = []
                for record in records[:100]:  # Limit to 100 records
                    record_dict = dict(record)
                    formatted_records.append(record_dict)
                
                output.append(format_json(formatted_records))
                
                if len(records) > 100:
                    output.append(f"\n... [{len(records) - 100} more records]")
                
                return "\n".join(output)
        
        except Exception as e:
            return f"[Neo4j Query Error] {str(e)}"
    
    def neo4j_create_node(self, connection_id: str, label: str, 
                         properties: Dict[str, Any]) -> str:
        """
        Create a single node with label and properties.
        Example: label="Person", properties={"name": "Alice", "age": 30}
        """
        try:
            query = f"CREATE (n:{label} $props) RETURN n"
            return self.neo4j_query(connection_id, query, {"props": properties})
        
        except Exception as e:
            return f"[Neo4j Create Node Error] {str(e)}"
    
    def neo4j_create_relationship(self, connection_id: str, 
                                 from_label: str, from_property: str, from_value: Any,
                                 to_label: str, to_property: str, to_value: Any,
                                 rel_type: str, rel_properties: Optional[Dict] = None) -> str:
        """
        Create relationship between two nodes.
        Example: Connect Person(name="Alice") to Person(name="Bob") with KNOWS relationship
        """
        try:
            rel_properties = rel_properties or {}
            
            query = f"""
                MATCH (a:{from_label} {{{from_property}: $from_value}})
                MATCH (b:{to_label} {{{to_property}: $to_value}})
                CREATE (a)-[r:{rel_type} $rel_props]->(b)
                RETURN a, r, b
            """
            
            params = {
                "from_value": from_value,
                "to_value": to_value,
                "rel_props": rel_properties
            }
            
            return self.neo4j_query(connection_id, query, params)
        
        except Exception as e:
            return f"[Neo4j Create Relationship Error] {str(e)}"
    
    def neo4j_find_nodes(self, connection_id: str, label: str, 
                        property_name: Optional[str] = None,
                        property_value: Optional[Any] = None,
                        limit: int = 10) -> str:
        """
        Search for nodes by label and optional property.
        If property not specified, returns all nodes with that label.
        """
        try:
            if property_name and property_value:
                query = f"""
                    MATCH (n:{label} {{{property_name}: $value}})
                    RETURN n
                    LIMIT $limit
                """
                params = {"value": property_value, "limit": limit}
            else:
                query = f"""
                    MATCH (n:{label})
                    RETURN n
                    LIMIT $limit
                """
                params = {"limit": limit}
            
            return self.neo4j_query(connection_id, query, params)
        
        except Exception as e:
            return f"[Neo4j Find Nodes Error] {str(e)}"
    
    def neo4j_get_schema(self, connection_id: str) -> str:
        """
        Get database schema including node labels, relationship types, and property keys.
        """
        try:
            driver = self.neo4j_manager.get_driver(connection_id)
            if not driver:
                return f"[Error] Neo4j connection '{connection_id}' not found."
            
            database = self.neo4j_manager.get_database(connection_id)
            
            with driver.session(database=database) as session:
                # Get labels
                labels = list(session.run("CALL db.labels()"))
                
                # Get relationship types
                rel_types = list(session.run("CALL db.relationshipTypes()"))
                
                # Get property keys
                prop_keys = list(session.run("CALL db.propertyKeys()"))
                
                output = ["=== Neo4j Database Schema ===\n"]
                
                output.append(f"Node Labels ({len(labels)}):")
                for record in labels:
                    output.append(f"  - {record['label']}")
                
                output.append(f"\nRelationship Types ({len(rel_types)}):")
                for record in rel_types:
                    output.append(f"  - {record['relationshipType']}")
                
                output.append(f"\nProperty Keys ({len(prop_keys)}):")
                for record in prop_keys:
                    output.append(f"  - {record['propertyKey']}")
                
                return "\n".join(output)
        
        except Exception as e:
            return f"[Neo4j Schema Error] {str(e)}"
    
    def neo4j_get_statistics(self, connection_id: str) -> str:
        """
        Get database statistics including node count, relationship count, etc.
        """
        try:
            queries = {
                "Total Nodes": "MATCH (n) RETURN count(n) as count",
                "Total Relationships": "MATCH ()-[r]->() RETURN count(r) as count",
                "Node Labels": "MATCH (n) RETURN labels(n) as labels, count(*) as count ORDER BY count DESC",
                "Relationship Types": "MATCH ()-[r]->() RETURN type(r) as type, count(*) as count ORDER BY count DESC"
            }
            
            output = ["=== Neo4j Database Statistics ===\n"]
            
            for title, query in queries.items():
                result = self.neo4j_query(connection_id, query)
                output.append(f"\n{title}:")
                output.append(result)
            
            return "\n".join(output)
        
        except Exception as e:
            return f"[Neo4j Statistics Error] {str(e)}"
    
    def neo4j_disconnect(self, connection_id: str) -> str:
        """
        Close Neo4j connection.
        """
        return self.neo4j_manager.close_connection(connection_id)


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_ssh_postgres_neo4j_tools(tool_list: List, agent):
    """
    Add SSH, PostgreSQL, and Neo4j tools to the tool list.
    Call this function at the end of your ToolLoader function:
    
    tool_list = ToolLoader(agent)
    add_ssh_postgres_neo4j_tools(tool_list, agent)
    return tool_list
    """
    
    ssh_tools = SSHTools(agent)
    pg_tools = PostgresTools(agent)
    neo4j_tools = Neo4jTools(agent)
    
    # SSH Tools
    tool_list.extend([
        StructuredTool.from_function(
            func=ssh_tools.connect_ssh,
            name="ssh_connect",
            description="Connect to SSH server. Returns connection ID for other SSH operations.",
            args_schema=SSHConnectionInput
        ),
        StructuredTool.from_function(
            func=ssh_tools.ssh_execute,
            name="ssh_execute",
            description="Execute command on remote SSH server. Returns command output.",
            args_schema=SSHCommandInput
        ),
        StructuredTool.from_function(
            func=ssh_tools.ssh_list_directory,
            name="ssh_ls",
            description="List contents of remote directory via SFTP.",
            args_schema=SSHFileInput
        ),
        StructuredTool.from_function(
            func=ssh_tools.ssh_read_file,
            name="ssh_read",
            description="Read contents of remote file via SFTP.",
            args_schema=SSHFileInput
        ),
        StructuredTool.from_function(
            func=ssh_tools.ssh_download_file,
            name="ssh_download",
            description="Download file from remote server via SFTP.",
            args_schema=SSHFileInput
        ),
        StructuredTool.from_function(
            func=ssh_tools.ssh_upload_file,
            name="ssh_upload",
            description="Upload file to remote server via SFTP.",
            args_schema=SSHFileInput
        ),
        StructuredTool.from_function(
            func=ssh_tools.ssh_disconnect,
            name="ssh_disconnect",
            description="Close SSH connection and clean up resources.",
            args_schema=LLMQueryInput
        ),
    ])
    
    # PostgreSQL Tools
    tool_list.extend([
        StructuredTool.from_function(
            func=pg_tools.connect_postgres,
            name="postgres_connect",
            description="Connect to PostgreSQL database. Returns connection ID for queries.",
            args_schema=PostgresConnectionInput
        ),
        StructuredTool.from_function(
            func=pg_tools.postgres_query,
            name="postgres_query",
            description="Execute SQL query on PostgreSQL. Supports SELECT, INSERT, UPDATE, DELETE with parameterized queries.",
            args_schema=PostgresQueryInput
        ),
        StructuredTool.from_function(
            func=pg_tools.postgres_list_tables,
            name="postgres_tables",
            description="List all tables in a PostgreSQL schema with sizes.",
            args_schema=PostgresQueryInput
        ),
        StructuredTool.from_function(
            func=pg_tools.postgres_describe_table,
            name="postgres_describe",
            description="Get detailed table structure including columns, types, constraints.",
            args_schema=PostgresQueryInput
        ),
        StructuredTool.from_function(
            func=pg_tools.postgres_list_schemas,
            name="postgres_schemas",
            description="List all schemas in PostgreSQL database.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=pg_tools.postgres_disconnect,
            name="postgres_disconnect",
            description="Close PostgreSQL connection.",
            args_schema=LLMQueryInput
        ),
    ])
    
    # Neo4j Tools
    tool_list.extend([
        StructuredTool.from_function(
            func=neo4j_tools.connect_neo4j,
            name="neo4j_connect",
            description="Connect to Neo4j graph database. Returns connection ID for queries.",
            args_schema=Neo4jConnectionInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_query,
            name="neo4j_query",
            description="Execute Cypher query on Neo4j. Supports all Cypher operations with parameterized queries.",
            args_schema=Neo4jQueryInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_create_node,
            name="neo4j_create_node",
            description="Create a node in Neo4j with label and properties.",
            args_schema=Neo4jQueryInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_create_relationship,
            name="neo4j_create_rel",
            description="Create relationship between two nodes in Neo4j.",
            args_schema=Neo4jQueryInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_find_nodes,
            name="neo4j_find",
            description="Search for nodes in Neo4j by label and optional property.",
            args_schema=Neo4jQueryInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_get_schema,
            name="neo4j_schema",
            description="Get Neo4j database schema including labels, relationships, and properties.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_get_statistics,
            name="neo4j_stats",
            description="Get Neo4j database statistics including counts and distributions.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=neo4j_tools.neo4j_disconnect,
            name="neo4j_disconnect",
            description="Close Neo4j connection.",
            args_schema=LLMQueryInput
        ),
    ])
    
    return tool_list


# Required dependencies (add to requirements.txt):
# paramiko>=3.0.0
# psycopg2-binary>=2.9.0
# neo4j>=5.0.0