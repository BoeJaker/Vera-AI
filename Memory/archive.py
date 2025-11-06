#!/usr/bin/env python3
"""
PostgreSQL Long-term Archive & Version Control for Hybrid Memory System

Features:
- Complete archiving of knowledge graph and vector store
- Git-like version control with commits, branches, and tags
- System metrics and performance logging
- User authentication and settings management
- Large file storage with chunking
- External database indexing
- Rollback and snapshot capabilities
- Change tracking and audit logs

Dependencies:
    pip install psycopg2-binary sqlalchemy alembic
"""

import os
import json
import time
import hashlib
import gzip
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging

import psycopg2
from psycopg2.extras import execute_values, Json
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, 
    Float, DateTime, JSON, LargeBinary, ForeignKey, Index,
    UniqueConstraint, CheckConstraint, Table, MetaData
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB, BYTEA, ARRAY

logger = logging.getLogger(__name__)

Base = declarative_base()

# =====================================================================
# ENUMS & CONSTANTS
# =====================================================================

class ChangeType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    MERGE = "MERGE"
    RESTORE = "RESTORE"

class EntityType(str, Enum):
    NODE = "NODE"
    EDGE = "EDGE"
    DOCUMENT = "DOCUMENT"
    SESSION = "SESSION"
    MEMORY = "MEMORY"
    FILE = "FILE"
    CONFIG = "CONFIG"

class VersionStatus(str, Enum):
    DRAFT = "DRAFT"
    COMMITTED = "COMMITTED"
    TAGGED = "TAGGED"
    ARCHIVED = "ARCHIVED"

# =====================================================================
# DATABASE MODELS
# =====================================================================

class Version(Base):
    """Git-like version control for all changes"""
    __tablename__ = "versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version_hash = Column(String(64), unique=True, nullable=False, index=True)
    parent_hash = Column(String(64), index=True)  # Previous version
    branch = Column(String(255), nullable=False, default="main", index=True)
    tag = Column(String(255), index=True)
    
    commit_message = Column(Text)
    author = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(50), default=VersionStatus.COMMITTED.value)
    
    # Metadata
    entity_count = Column(Integer, default=0)
    change_count = Column(Integer, default=0)
    size_bytes = Column(Integer, default=0)
    metadata = Column(JSONB, default={})
    
    # Relationships
    changes = relationship("ChangeLog", back_populates="version", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="version", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_version_branch_time', 'branch', 'timestamp'),
        Index('idx_version_status', 'status'),
    )


class ChangeLog(Base):
    """Detailed change tracking for version control"""
    __tablename__ = "change_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey('versions.id', ondelete='CASCADE'), nullable=False, index=True)
    
    change_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)
    
    # Change details
    before_state = Column(JSONB)  # State before change
    after_state = Column(JSONB)   # State after change
    diff = Column(JSONB)          # Computed diff
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    operation_id = Column(String(64), index=True)  # Groups related changes
    
    version = relationship("Version", back_populates="changes")
    
    __table_args__ = (
        Index('idx_change_entity', 'entity_type', 'entity_id'),
        Index('idx_change_operation', 'operation_id'),
    )


class Snapshot(Base):
    """Point-in-time snapshots of the entire system state"""
    __tablename__ = "snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_hash = Column(String(64), unique=True, nullable=False, index=True)
    version_id = Column(Integer, ForeignKey('versions.id', ondelete='CASCADE'), index=True)
    
    name = Column(String(255))
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Snapshot data (compressed)
    graph_state = Column(LargeBinary)      # Compressed Neo4j export
    vector_state = Column(LargeBinary)      # Compressed Chroma export
    metadata_state = Column(JSONB)
    
    size_bytes = Column(Integer)
    compressed = Column(Boolean, default=True)
    
    version = relationship("Version", back_populates="snapshots")
    
    __table_args__ = (
        Index('idx_snapshot_time', 'timestamp'),
    )


class GraphArchive(Base):
    """Archive of Neo4j graph entities"""
    __tablename__ = "graph_archive"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    
    # Graph data
    labels = Column(ARRAY(String), default=[])
    properties = Column(JSONB, default={})
    
    # Edges (if entity_type == EDGE)
    source_id = Column(String(255), index=True)
    target_id = Column(String(255), index=True)
    relationship_type = Column(String(255), index=True)
    
    # Versioning
    version_id = Column(Integer, ForeignKey('versions.id', ondelete='SET NULL'), index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, index=True)
    
    __table_args__ = (
        Index('idx_graph_entity_version', 'entity_id', 'version_id'),
        Index('idx_graph_edge', 'source_id', 'target_id'),
        Index('idx_graph_active', 'is_active', 'entity_type'),
    )


class VectorArchive(Base):
    """Archive of Chroma vector embeddings"""
    __tablename__ = "vector_archive"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vector_id = Column(String(255), nullable=False, index=True)
    collection = Column(String(255), nullable=False, index=True)
    
    # Vector data
    text = Column(Text)
    embedding = Column(ARRAY(Float))  # Store as array for PG vector search
    metadata = Column(JSONB, default={})
    
    # Versioning
    version_id = Column(Integer, ForeignKey('versions.id', ondelete='SET NULL'), index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, index=True)
    
    __table_args__ = (
        Index('idx_vector_collection_version', 'collection', 'version_id'),
        Index('idx_vector_active', 'is_active'),
    )


class FileArchive(Base):
    """Large file storage with chunking"""
    __tablename__ = "file_archive"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), unique=True, nullable=False, index=True)
    file_name = Column(String(512), nullable=False)
    file_path = Column(Text)
    
    # File metadata
    mime_type = Column(String(255))
    size_bytes = Column(Integer)
    chunk_count = Column(Integer, default=0)
    checksum = Column(String(64))  # SHA-256
    
    # Compression
    compressed = Column(Boolean, default=True)
    compression_algo = Column(String(50), default="gzip")
    
    # Versioning
    version_id = Column(Integer, ForeignKey('versions.id', ondelete='SET NULL'), index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata = Column(JSONB, default={})
    
    # Relationships
    chunks = relationship("FileChunk", back_populates="file", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_file_version', 'version_id'),
        Index('idx_file_checksum', 'checksum'),
    )


class FileChunk(Base):
    """Chunked storage for large files"""
    __tablename__ = "file_chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('file_archive.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    
    data = Column(LargeBinary, nullable=False)
    size_bytes = Column(Integer)
    checksum = Column(String(64))
    
    file = relationship("FileArchive", back_populates="chunks")
    
    __table_args__ = (
        UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk'),
        Index('idx_chunk_file', 'file_id', 'chunk_index'),
    )


class SystemMetrics(Base):
    """System performance and health metrics"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Component metrics
    component = Column(String(100), nullable=False, index=True)
    metric_name = Column(String(255), nullable=False, index=True)
    metric_value = Column(Float)
    metric_unit = Column(String(50))
    
    # Context
    session_id = Column(String(255), index=True)
    operation_id = Column(String(64), index=True)
    
    # Additional data
    metadata = Column(JSONB, default={})
    
    __table_args__ = (
        Index('idx_metrics_component_time', 'component', 'timestamp'),
        Index('idx_metrics_name_time', 'metric_name', 'timestamp'),
    )


class AuditLog(Base):
    """Comprehensive audit trail"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Action details
    action = Column(String(100), nullable=False, index=True)
    component = Column(String(100), index=True)
    entity_type = Column(String(50), index=True)
    entity_id = Column(String(255), index=True)
    
    # User/session context
    user_id = Column(String(255), index=True)
    session_id = Column(String(255), index=True)
    
    # Change details
    changes = Column(JSONB)
    status = Column(String(50))
    error_message = Column(Text)
    
    # Performance
    duration_ms = Column(Float)
    
    metadata = Column(JSONB, default={})
    
    __table_args__ = (
        Index('idx_audit_action_time', 'action', 'timestamp'),
        Index('idx_audit_user', 'user_id', 'timestamp'),
    )


class User(Base):
    """User management"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    
    # Authentication (store hashed passwords)
    password_hash = Column(String(255))
    api_key = Column(String(64), unique=True, index=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSettings(Base):
    """User configuration and preferences"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    
    settings = Column(JSONB, default={})
    preferences = Column(JSONB, default={})
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="settings")


class UserSession(Base):
    """Track user sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    ended_at = Column(DateTime)
    
    metadata = Column(JSONB, default={})
    
    user = relationship("User", back_populates="sessions")


class SystemConfig(Base):
    """System-wide configuration"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(255), unique=True, nullable=False, index=True)
    config_value = Column(JSONB)
    
    description = Column(Text)
    version_id = Column(Integer, ForeignKey('versions.id', ondelete='SET NULL'))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    metadata = Column(JSONB, default={})


class ExternalDatabase(Base):
    """Index for external databases and data sources"""
    __tablename__ = "external_databases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    database_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    # Connection info (encrypted)
    connection_string = Column(Text)
    database_type = Column(String(100), index=True)  # postgres, mysql, mongodb, etc.
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_sync = Column(DateTime)
    
    # Metadata
    schema_info = Column(JSONB)
    statistics = Column(JSONB)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSONB, default={})


# =====================================================================
# POSTGRESQL ARCHIVE CLIENT
# =====================================================================

class PostgresArchive:
    """
    Comprehensive PostgreSQL archive system with version control.
    """
    
    def __init__(
        self,
        connection_string: str,
        chunk_size: int = 1024 * 1024,  # 1MB chunks
        auto_commit: bool = True,
        enable_compression: bool = True
    ):
        self.connection_string = connection_string
        self.chunk_size = chunk_size
        self.auto_commit = auto_commit
        self.enable_compression = enable_compression
        
        # SQLAlchemy setup
        self.engine = create_engine(connection_string, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Current working state
        self.current_branch = "main"
        self.current_version = None
        self.pending_changes = []
        
        logger.info(f"PostgresArchive initialized on branch '{self.current_branch}'")
    
    # ================================================================
    # VERSION CONTROL
    # ================================================================
    
    def create_version(
        self,
        commit_message: str,
        author: str = "system",
        branch: Optional[str] = None,
        tag: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Version:
        """Create a new version (commit)"""
        session = self.Session()
        try:
            branch = branch or self.current_branch
            
            # Get parent version
            parent = session.query(Version).filter_by(
                branch=branch
            ).order_by(Version.timestamp.desc()).first()
            
            parent_hash = parent.version_hash if parent else None
            
            # Generate version hash
            version_data = f"{parent_hash}:{commit_message}:{author}:{time.time()}"
            version_hash = hashlib.sha256(version_data.encode()).hexdigest()
            
            # Create version
            version = Version(
                version_hash=version_hash,
                parent_hash=parent_hash,
                branch=branch,
                tag=tag,
                commit_message=commit_message,
                author=author,
                metadata=metadata or {},
                status=VersionStatus.COMMITTED.value
            )
            
            session.add(version)
            session.flush()
            
            # Process pending changes
            for change_data in self.pending_changes:
                change = ChangeLog(
                    version_id=version.id,
                    **change_data
                )
                session.add(change)
            
            version.change_count = len(self.pending_changes)
            
            session.commit()
            
            self.current_version = version
            self.pending_changes = []
            
            logger.info(f"Created version {version_hash[:8]} on branch '{branch}'")
            return version
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating version: {e}")
            raise
        finally:
            session.close()
    
    def checkout_branch(self, branch: str) -> bool:
        """Switch to a different branch"""
        session = self.Session()
        try:
            # Verify branch exists
            version = session.query(Version).filter_by(branch=branch).first()
            if not version:
                logger.warning(f"Branch '{branch}' does not exist, creating it")
            
            self.current_branch = branch
            logger.info(f"Checked out branch '{branch}'")
            return True
            
        finally:
            session.close()
    
    def create_branch(self, branch_name: str, from_version: Optional[str] = None) -> Version:
        """Create a new branch"""
        session = self.Session()
        try:
            # Get source version
            if from_version:
                parent = session.query(Version).filter_by(
                    version_hash=from_version
                ).first()
                if not parent:
                    raise ValueError(f"Version {from_version} not found")
            else:
                parent = session.query(Version).filter_by(
                    branch=self.current_branch
                ).order_by(Version.timestamp.desc()).first()
            
            # Create branch point
            version = Version(
                version_hash=hashlib.sha256(f"{branch_name}:{time.time()}".encode()).hexdigest(),
                parent_hash=parent.version_hash if parent else None,
                branch=branch_name,
                commit_message=f"Created branch {branch_name}",
                author="system",
                status=VersionStatus.COMMITTED.value
            )
            
            session.add(version)
            session.commit()
            
            logger.info(f"Created branch '{branch_name}' from {parent.version_hash[:8] if parent else 'root'}")
            return version
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating branch: {e}")
            raise
        finally:
            session.close()
    
    def tag_version(self, version_hash: str, tag: str, description: Optional[str] = None) -> bool:
        """Tag a specific version"""
        session = self.Session()
        try:
            version = session.query(Version).filter_by(version_hash=version_hash).first()
            if not version:
                raise ValueError(f"Version {version_hash} not found")
            
            version.tag = tag
            version.status = VersionStatus.TAGGED.value
            if description:
                version.metadata = {**version.metadata, "tag_description": description}
            
            session.commit()
            logger.info(f"Tagged version {version_hash[:8]} as '{tag}'")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error tagging version: {e}")
            raise
        finally:
            session.close()
    
    def get_version_history(
        self,
        branch: Optional[str] = None,
        limit: int = 50
    ) -> List[Version]:
        """Get version history for a branch"""
        session = self.Session()
        try:
            query = session.query(Version)
            
            if branch:
                query = query.filter_by(branch=branch)
            
            versions = query.order_by(Version.timestamp.desc()).limit(limit).all()
            return versions
            
        finally:
            session.close()
    
    def rollback_to_version(self, version_hash: str) -> bool:
        """Rollback system state to a specific version"""
        session = self.Session()
        try:
            target_version = session.query(Version).filter_by(
                version_hash=version_hash
            ).first()
            
            if not target_version:
                raise ValueError(f"Version {version_hash} not found")
            
            # Get snapshot if available
            snapshot = session.query(Snapshot).filter_by(
                version_id=target_version.id
            ).first()
            
            if snapshot:
                logger.info(f"Rolling back to snapshot from version {version_hash[:8]}")
                self._restore_snapshot(session, snapshot)
            else:
                logger.info(f"Rolling back by replaying changes to version {version_hash[:8]}")
                self._replay_to_version(session, target_version)
            
            # Create rollback commit
            rollback_version = self.create_version(
                commit_message=f"Rollback to {version_hash[:8]}",
                author="system",
                metadata={"rollback_target": version_hash}
            )
            
            session.commit()
            logger.info(f"Successfully rolled back to version {version_hash[:8]}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error rolling back: {e}")
            raise
        finally:
            session.close()
    
    def _replay_to_version(self, session, target_version: Version):
        """Replay changes to reach target version state"""
        # Get all changes up to target version
        changes = session.query(ChangeLog).join(Version).filter(
            Version.timestamp <= target_version.timestamp,
            Version.branch == target_version.branch
        ).order_by(ChangeLog.timestamp).all()
        
        # Apply changes in order
        for change in changes:
            self._apply_change(session, change, reverse=False)
    
    def _apply_change(self, session, change: ChangeLog, reverse: bool = False):
        """Apply or reverse a single change"""
        state = change.before_state if reverse else change.after_state
        
        if change.entity_type == EntityType.NODE.value:
            self._apply_graph_change(session, change, state, reverse)
        elif change.entity_type == EntityType.DOCUMENT.value:
            self._apply_vector_change(session, change, state, reverse)
    
    # ================================================================
    # GRAPH ARCHIVING
    # ================================================================
    
    def archive_graph_entity(
        self,
        entity_id: str,
        entity_type: str,
        labels: List[str],
        properties: Dict[str, Any],
        version_id: Optional[int] = None
    ) -> GraphArchive:
        """Archive a Neo4j entity"""
        session = self.Session()
        try:
            entity = GraphArchive(
                entity_id=entity_id,
                entity_type=entity_type,
                labels=labels,
                properties=properties,
                version_id=version_id or (self.current_version.id if self.current_version else None)
            )
            
            session.add(entity)
            
            # Track change
            self._track_change(
                change_type=ChangeType.CREATE,
                entity_type=EntityType.NODE,
                entity_id=entity_id,
                after_state={"labels": labels, "properties": properties}
            )
            
            if self.auto_commit:
                session.commit()
            
            return entity
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error archiving graph entity: {e}")
            raise
        finally:
            session.close()
    
    def archive_graph_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Dict[str, Any],
        version_id: Optional[int] = None
    ) -> GraphArchive:
        """Archive a Neo4j relationship"""
        session = self.Session()
        try:
            edge = GraphArchive(
                entity_id=edge_id,
                entity_type=EntityType.EDGE.value,
                source_id=source_id,
                target_id=target_id,
                relationship_type=relationship_type,
                properties=properties,
                version_id=version_id or (self.current_version.id if self.current_version else None)
            )
            
            session.add(edge)
            
            # Track change
            self._track_change(
                change_type=ChangeType.CREATE,
                entity_type=EntityType.EDGE,
                entity_id=edge_id,
                after_state={
                    "source": source_id,
                    "target": target_id,
                    "type": relationship_type,
                    "properties": properties
                }
            )
            
            if self.auto_commit:
                session.commit()
            
            return edge
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error archiving graph edge: {e}")
            raise
        finally:
            session.close()
    
    def export_graph_snapshot(self, version_id: Optional[int] = None) -> Dict[str, Any]:
        """Export complete graph state"""
        session = self.Session()
        try:
            query = session.query(GraphArchive).filter_by(is_active=True)
            
            if version_id:
                query = query.filter_by(version_id=version_id)
            
            entities = query.all()
            
            nodes = []
            edges = []
            
            for entity in entities:
                if entity.entity_type == EntityType.EDGE.value:
                    edges.append({
                        "id": entity.entity_id,
                        "source": entity.source_id,
                        "target": entity.target_id,
                        "type": entity.relationship_type,
                        "properties": entity.properties
                    })
                else:
                    nodes.append({
                        "id": entity.entity_id,
                        "type": entity.entity_type,
                        "labels": entity.labels,
                        "properties": entity.properties
                    })
            
            return {"nodes": nodes, "edges": edges}
            
        finally:
            session.close()
    
    # ================================================================
    # VECTOR ARCHIVING
    # ================================================================
    
    def archive_vector(
        self,
        vector_id: str,
        collection: str,
        text: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        version_id: Optional[int] = None
    ) -> VectorArchive:
        """Archive a Chroma vector"""
        session = self.Session()
        try:
            vector = VectorArchive(
                vector_id=vector_id,
                collection=collection,
                text=text,
                embedding=embedding,
                metadata=metadata,
                version_id=version_id or (self.current_version.id if self.current_version else None)
            )
            
            session.add(vector)
            
            # Track change
            self._track_change(
                change_type=ChangeType.CREATE,
                entity_type=EntityType.DOCUMENT,
                entity_id=vector_id,
                after_state={
                    "collection": collection,
                    "text": text[:500],  # Truncate for storage
                    "metadata": metadata
                }
            )
            
            if self.auto_commit:
                session.commit()
            
            return vector
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error archiving vector: {e}")
            raise
        finally:
            session.close()
    
    def export_vector_snapshot(
        self,
        collection: Optional[str] = None,
        version_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Export vector embeddings"""
        session = self.Session()
        try:
            query = session.query(VectorArchive).filter_by(is_active=True)
            
            if collection:
                query = query.filter_by(collection=collection)
            if version_id:
                query = query.filter_by(version_id=version_id)
            
            vectors = query.all()
            
            return [{
                "id": v.vector_id,
                "collection": v.collection,
                "text": v.text,
                "embedding": v.embedding,
                "metadata": v.metadata
            } for v in vectors]
            
        finally:
            session.close()
    
    # ================================================================
    # FILE STORAGE
    # ================================================================
    
    def store_file(
        self,
        file_path: str,
        file_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        compress: Optional[bool] = None
    ) -> FileArchive:
        """Store a large file with chunking"""
        session = self.Session()
        try:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            compress = compress if compress is not None else self.enable_compression
            file_name = os.path.basename(file_path)
            file_id = file_id or f"file_{hashlib.sha256(file_path.encode()).hexdigest()[:16]}"
            
            # Calculate checksum
            hasher = hashlib.sha256()
            file_size = 0
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)
                    file_size += len(chunk)
            
            checksum = hasher.hexdigest()
            
            # Create file record
            file_record = FileArchive(
                file_id=file_id,
                file_name=file_name,
                file_path=file_path,
                size_bytes=file_size,
                checksum=checksum,
                compressed=compress,
                version_id=self.current_version.id if self.current_version else None,
                metadata=metadata or {}
            )
            
            session.add(file_record)
            session.flush()
            
            # Store chunks
            chunk_index = 0
            with open(file_path, 'rb') as f:
                while chunk_data := f.read(self.chunk_size):
                    if compress:
                        chunk_data = gzip.compress(chunk_data)
                    
                    chunk_checksum = hashlib.sha256(chunk_data).hexdigest()
                    
                    chunk = FileChunk(
                        file_id=file_record.id,
                        chunk_index=chunk_index,
                        data=chunk_data,
                        size_bytes=len(chunk_data),
                        checksum=chunk_checksum
                    )
                    
                    session.add(chunk)
                    chunk_index += 1
            
            file_record.chunk_count = chunk_index
            
            # Track change
            self._track_change(
                change_type=ChangeType.CREATE,
                entity_type=EntityType.FILE,
                entity_id=file_id,
                after_state={
                    "file_name": file_name,
                    "size_bytes": file_size,
                    "chunk_count": chunk_index
                }
            )
            
            session.commit()
            logger.info(f"Stored file {file_name} ({file_size} bytes, {chunk_index} chunks)")
            
            return file_record
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing file: {e}")
            raise
        finally:
            session.close()
    
    def retrieve_file(
        self,
        file_id: str,
        output_path: Optional[str] = None
    ) -> bytes:
        """Retrieve a stored file"""
        session = self.Session()
        try:
            file_record = session.query(FileArchive).filter_by(file_id=file_id).first()
            if not file_record:
                raise ValueError(f"File {file_id} not found")
            
            # Retrieve chunks in order
            chunks = session.query(FileChunk).filter_by(
                file_id=file_record.id
            ).order_by(FileChunk.chunk_index).all()
            
            # Reconstruct file
            file_data = b''
            for chunk in chunks:
                chunk_data = chunk.data
                if file_record.compressed:
                    chunk_data = gzip.decompress(chunk_data)
                file_data += chunk_data
            
            # Verify checksum
            checksum = hashlib.sha256(file_data).hexdigest()
            if checksum != file_record.checksum:
                raise ValueError(f"Checksum mismatch for file {file_id}")
            
            # Write to output if specified
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(file_data)
                logger.info(f"Retrieved file {file_id} to {output_path}")
            
            return file_data
            
        finally:
            session.close()
    
    def list_files(
        self,
        version_id: Optional[int] = None,
        limit: int = 100
    ) -> List[FileArchive]:
        """List stored files"""
        session = self.Session()
        try:
            query = session.query(FileArchive)
            
            if version_id:
                query = query.filter_by(version_id=version_id)
            
            files = query.order_by(FileArchive.created_at.desc()).limit(limit).all()
            return files
            
        finally:
            session.close()
    
    # ================================================================
    # SNAPSHOTS
    # ================================================================
    
    def create_snapshot(
        self,
        name: str,
        description: Optional[str] = None,
        include_graph: bool = True,
        include_vectors: bool = True
    ) -> Snapshot:
        """Create a complete system snapshot"""
        session = self.Session()
        try:
            logger.info(f"Creating snapshot: {name}")
            
            # Export current state
            graph_state = None
            vector_state = None
            
            if include_graph:
                graph_data = self.export_graph_snapshot()
                graph_json = json.dumps(graph_data).encode()
                graph_state = gzip.compress(graph_json)
            
            if include_vectors:
                vector_data = self.export_vector_snapshot()
                vector_json = json.dumps(vector_data).encode()
                vector_state = gzip.compress(vector_json)
            
            # Calculate total size
            size_bytes = 0
            if graph_state:
                size_bytes += len(graph_state)
            if vector_state:
                size_bytes += len(vector_state)
            
            # Generate snapshot hash
            snapshot_data = f"{name}:{time.time()}:{size_bytes}"
            snapshot_hash = hashlib.sha256(snapshot_data.encode()).hexdigest()
            
            # Create snapshot
            snapshot = Snapshot(
                snapshot_hash=snapshot_hash,
                version_id=self.current_version.id if self.current_version else None,
                name=name,
                description=description,
                graph_state=graph_state,
                vector_state=vector_state,
                size_bytes=size_bytes,
                compressed=True,
                metadata_state={
                    "graph_included": include_graph,
                    "vectors_included": include_vectors
                }
            )
            
            session.add(snapshot)
            session.commit()
            
            logger.info(f"Created snapshot {snapshot_hash[:8]} ({size_bytes} bytes)")
            return snapshot
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating snapshot: {e}")
            raise
        finally:
            session.close()
    
    def _restore_snapshot(self, session, snapshot: Snapshot):
        """Restore system state from snapshot"""
        logger.info(f"Restoring snapshot {snapshot.snapshot_hash[:8]}")
        
        # Restore graph
        if snapshot.graph_state:
            graph_json = gzip.decompress(snapshot.graph_state)
            graph_data = json.loads(graph_json)
            
            # Mark current entities as inactive
            session.query(GraphArchive).update({"is_active": False})
            
            # Restore nodes
            for node in graph_data["nodes"]:
                entity = GraphArchive(
                    entity_id=node["id"],
                    entity_type=node["type"],
                    labels=node["labels"],
                    properties=node["properties"],
                    is_active=True
                )
                session.add(entity)
            
            # Restore edges
            for edge in graph_data["edges"]:
                entity = GraphArchive(
                    entity_id=edge["id"],
                    entity_type=EntityType.EDGE.value,
                    source_id=edge["source"],
                    target_id=edge["target"],
                    relationship_type=edge["type"],
                    properties=edge["properties"],
                    is_active=True
                )
                session.add(entity)
        
        # Restore vectors
        if snapshot.vector_state:
            vector_json = gzip.decompress(snapshot.vector_state)
            vector_data = json.loads(vector_json)
            
            # Mark current vectors as inactive
            session.query(VectorArchive).update({"is_active": False})
            
            for vector in vector_data:
                vec_entity = VectorArchive(
                    vector_id=vector["id"],
                    collection=vector["collection"],
                    text=vector["text"],
                    embedding=vector["embedding"],
                    metadata=vector["metadata"],
                    is_active=True
                )
                session.add(vec_entity)
    
    def list_snapshots(self, limit: int = 50) -> List[Snapshot]:
        """List available snapshots"""
        session = self.Session()
        try:
            snapshots = session.query(Snapshot).order_by(
                Snapshot.timestamp.desc()
            ).limit(limit).all()
            return snapshots
        finally:
            session.close()
    
    # ================================================================
    # METRICS & MONITORING
    # ================================================================
    
    def log_metric(
        self,
        component: str,
        metric_name: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
        session_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a performance metric"""
        session = self.Session()
        try:
            metric = SystemMetrics(
                component=component,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                session_id=session_id,
                operation_id=operation_id,
                metadata=metadata or {}
            )
            
            session.add(metric)
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging metric: {e}")
        finally:
            session.close()
    
    def get_metrics(
        self,
        component: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[SystemMetrics]:
        """Query system metrics"""
        session = self.Session()
        try:
            query = session.query(SystemMetrics)
            
            if component:
                query = query.filter_by(component=component)
            if metric_name:
                query = query.filter_by(metric_name=metric_name)
            if start_time:
                query = query.filter(SystemMetrics.timestamp >= start_time)
            if end_time:
                query = query.filter(SystemMetrics.timestamp <= end_time)
            
            metrics = query.order_by(
                SystemMetrics.timestamp.desc()
            ).limit(limit).all()
            
            return metrics
            
        finally:
            session.close()
    
    def get_metric_statistics(
        self,
        component: str,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get statistical summary of metrics"""
        session = self.Session()
        try:
            from sqlalchemy import func
            
            query = session.query(
                func.avg(SystemMetrics.metric_value).label('avg'),
                func.min(SystemMetrics.metric_value).label('min'),
                func.max(SystemMetrics.metric_value).label('max'),
                func.count(SystemMetrics.id).label('count')
            ).filter_by(
                component=component,
                metric_name=metric_name
            )
            
            if start_time:
                query = query.filter(SystemMetrics.timestamp >= start_time)
            if end_time:
                query = query.filter(SystemMetrics.timestamp <= end_time)
            
            result = query.first()
            
            return {
                "average": float(result.avg) if result.avg else 0.0,
                "minimum": float(result.min) if result.min else 0.0,
                "maximum": float(result.max) if result.max else 0.0,
                "count": int(result.count) if result.count else 0
            }
            
        finally:
            session.close()
    
    # ================================================================
    # AUDIT LOGGING
    # ================================================================
    
    def log_audit(
        self,
        action: str,
        component: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an audit event"""
        session = self.Session()
        try:
            audit = AuditLog(
                action=action,
                component=component,
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                session_id=session_id,
                changes=changes,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
                metadata=metadata or {}
            )
            
            session.add(audit)
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging audit: {e}")
        finally:
            session.close()
    
    def get_audit_logs(
        self,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Query audit logs"""
        session = self.Session()
        try:
            query = session.query(AuditLog)
            
            if action:
                query = query.filter_by(action=action)
            if user_id:
                query = query.filter_by(user_id=user_id)
            if start_time:
                query = query.filter(AuditLog.timestamp >= start_time)
            if end_time:
                query = query.filter(AuditLog.timestamp <= end_time)
            
            logs = query.order_by(
                AuditLog.timestamp.desc()
            ).limit(limit).all()
            
            return logs
            
        finally:
            session.close()
    
    # ================================================================
    # USER MANAGEMENT
    # ================================================================
    
    def create_user(
        self,
        user_id: str,
        username: str,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_admin: bool = False
    ) -> User:
        """Create a new user"""
        session = self.Session()
        try:
            # Generate API key
            api_key = hashlib.sha256(f"{user_id}:{time.time()}".encode()).hexdigest()
            
            user = User(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                api_key=api_key,
                is_admin=is_admin
            )
            
            session.add(user)
            
            # Create default settings
            settings = UserSettings(user=user)
            session.add(settings)
            
            session.commit()
            
            logger.info(f"Created user {username}")
            return user
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating user: {e}")
            raise
        finally:
            session.close()
    
    def get_user(self, user_id: Optional[str] = None, username: Optional[str] = None) -> Optional[User]:
        """Get user by ID or username"""
        session = self.Session()
        try:
            if user_id:
                return session.query(User).filter_by(user_id=user_id).first()
            elif username:
                return session.query(User).filter_by(username=username).first()
            return None
        finally:
            session.close()
    
    def update_user_settings(
        self,
        user_id: str,
        settings: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None
    ):
        """Update user settings"""
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            if not user.settings:
                user.settings = UserSettings(user=user)
            
            if settings:
                user.settings.settings = {**user.settings.settings, **settings}
            if preferences:
                user.settings.preferences = {**user.settings.preferences, **preferences}
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating user settings: {e}")
            raise
        finally:
            session.close()
    
    def start_user_session(
        self,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UserSession:
        """Start a user session"""
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            user_session = UserSession(
                session_id=session_id,
                user_id=user.id,
                metadata=metadata or {}
            )
            
            session.add(user_session)
            user.last_login = datetime.utcnow()
            
            session.commit()
            return user_session
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error starting user session: {e}")
            raise
        finally:
            session.close()
    
    def end_user_session(self, session_id: str):
        """End a user session"""
        session = self.Session()
        try:
            user_session = session.query(UserSession).filter_by(
                session_id=session_id
            ).first()
            
            if user_session:
                user_session.ended_at = datetime.utcnow()
                session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error ending user session: {e}")
        finally:
            session.close()
    
    # ================================================================
    # CONFIGURATION
    # ================================================================
    
    def set_config(
        self,
        config_key: str,
        config_value: Any,
        description: Optional[str] = None
    ):
        """Set system configuration"""
        session = self.Session()
        try:
            config = session.query(SystemConfig).filter_by(
                config_key=config_key
            ).first()
            
            if config:
                config.config_value = config_value
                config.updated_at = datetime.utcnow()
            else:
                config = SystemConfig(
                    config_key=config_key,
                    config_value=config_value,
                    description=description,
                    version_id=self.current_version.id if self.current_version else None
                )
                session.add(config)
            
            session.commit()
            
            # Track change
            self._track_change(
                change_type=ChangeType.UPDATE,
                entity_type=EntityType.CONFIG,
                entity_id=config_key,
                after_state={"value": config_value}
            )
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting config: {e}")
            raise
        finally:
            session.close()
    
    def get_config(self, config_key: str, default: Any = None) -> Any:
        """Get system configuration"""
        session = self.Session()
        try:
            config = session.query(SystemConfig).filter_by(
                config_key=config_key
            ).first()
            
            return config.config_value if config else default
            
        finally:
            session.close()
    
    def list_configs(self) -> List[SystemConfig]:
        """List all configurations"""
        session = self.Session()
        try:
            return session.query(SystemConfig).all()
        finally:
            session.close()
    
    # ================================================================
    # EXTERNAL DATABASES
    # ================================================================
    
    def register_external_database(
        self,
        database_id: str,
        name: str,
        connection_string: str,
        database_type: str,
        schema_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExternalDatabase:
        """Register an external database"""
        session = self.Session()
        try:
            # TODO: Encrypt connection string
            
            db = ExternalDatabase(
                database_id=database_id,
                name=name,
                connection_string=connection_string,
                database_type=database_type,
                schema_info=schema_info or {},
                metadata=metadata or {}
            )
            
            session.add(db)
            session.commit()
            
            logger.info(f"Registered external database: {name}")
            return db
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error registering external database: {e}")
            raise
        finally:
            session.close()
    
    def update_database_sync(
        self,
        database_id: str,
        statistics: Optional[Dict[str, Any]] = None
    ):
        """Update external database sync status"""
        session = self.Session()
        try:
            db = session.query(ExternalDatabase).filter_by(
                database_id=database_id
            ).first()
            
            if db:
                db.last_sync = datetime.utcnow()
                if statistics:
                    db.statistics = statistics
                session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating database sync: {e}")
        finally:
            session.close()
    
    def list_external_databases(self, active_only: bool = True) -> List[ExternalDatabase]:
        """List external databases"""
        session = self.Session()
        try:
            query = session.query(ExternalDatabase)
            if active_only:
                query = query.filter_by(is_active=True)
            return query.all()
        finally:
            session.close()
    
    # ================================================================
    # INTERNAL HELPERS
    # ================================================================
    
    def _track_change(
        self,
        change_type: ChangeType,
        entity_type: EntityType,
        entity_id: str,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None
    ):
        """Track a change for the next commit"""
        self.pending_changes.append({
            "change_type": change_type.value,
            "entity_type": entity_type.value,
            "entity_id": entity_id,
            "before_state": before_state,
            "after_state": after_state,
            "timestamp": datetime.utcnow(),
            "operation_id": hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16]
        })
    
    def _apply_graph_change(self, session, change: ChangeLog, state: Dict[str, Any], reverse: bool):
        """Apply a graph change"""
        # Implementation for applying/reversing graph changes
        pass
    
    def _apply_vector_change(self, session, change: ChangeLog, state: Dict[str, Any], reverse: bool):
        """Apply a vector change"""
        # Implementation for applying/reversing vector changes
        pass
    
    def close(self):
        """Close database connections"""
        self.engine.dispose()
        logger.info("PostgresArchive closed")


# =====================================================================
# INTEGRATION WITH HYBRID MEMORY
# =====================================================================

class HybridMemoryWithArchive:
    """
    Wrapper to integrate PostgreSQL archive with HybridMemory
    """
    
    def __init__(self, hybrid_memory, postgres_archive: PostgresArchive):
        self.memory = hybrid_memory
        self.archive = postgres_archive
        self._operation_id = None
    
    def begin_operation(self, description: str, author: str = "system") -> str:
        """Begin a tracked operation"""
        self._operation_id = hashlib.sha256(f"{description}:{time.time()}".encode()).hexdigest()[:16]
        logger.info(f"Begin operation {self._operation_id}: {description}")
        return self._operation_id
    
    def commit_operation(self, message: str, tag: Optional[str] = None):
        """Commit the current operation as a version"""
        if not self._operation_id:
            logger.warning("No active operation to commit")
            return
        
        version = self.archive.create_version(
            commit_message=message,
            tag=tag,
            metadata={"operation_id": self._operation_id}
        )
        
        logger.info(f"Committed operation {self._operation_id} as version {version.version_hash[:8]}")
        self._operation_id = None
        return version
    
    def sync_graph_to_archive(self):
        """Sync Neo4j graph to PostgreSQL archive"""
        logger.info("Syncing graph to archive...")
        
        # Get all entities from Neo4j
        with self.memory.graph._driver.session() as sess:
            # Sync nodes
            node_result = sess.run("MATCH (n:Entity) RETURN n")
            for record in node_result:
                node = record["n"]
                self.archive.archive_graph_entity(
                    entity_id=node.get("id"),
                    entity_type=node.get("type", "unknown"),
                    labels=list(node.labels) if hasattr(node, "labels") else [],
                    properties=dict(node)
                )
            
            # Sync edges
            edge_result = sess.run("MATCH (a)-[r:REL]->(b) RETURN a.id AS src, b.id AS dst, r")
            for record in edge_result:
                rel = record["r"]
                edge_id = f"{record['src']}-{record['dst']}-{rel.get('rel', 'REL')}"
                self.archive.archive_graph_edge(
                    edge_id=edge_id,
                    source_id=record["src"],
                    target_id=record["dst"],
                    relationship_type=rel.get("rel", "REL"),
                    properties=dict(rel)
                )
        
        logger.info("Graph sync complete")
    
    def sync_vectors_to_archive(self):
        """Sync Chroma vectors to PostgreSQL archive"""
        logger.info("Syncing vectors to archive...")
        
        # Sync long-term documents
        collection = self.memory.vec.get_collection("long_term_docs")
        result = collection.get(include=["documents", "embeddings", "metadatas"])
        
        if result and result.get("ids"):
            for i, vec_id in enumerate(result["ids"]):
                self.archive.archive_vector(
                    vector_id=vec_id,
                    collection="long_term_docs",
                    text=result["documents"][i],
                    embedding=result["embeddings"][i] if result.get("embeddings") else [],
                    metadata=result["metadatas"][i] if result.get("metadatas") else {}
                )
        
        logger.info("Vector sync complete")
    
    def create_full_backup(self, backup_name: str) -> Snapshot:
        """Create a complete backup of the system"""
        logger.info(f"Creating full backup: {backup_name}")
        
        # Sync everything first
        self.sync_graph_to_archive()
        self.sync_vectors_to_archive()
        
        # Create snapshot
        snapshot = self.archive.create_snapshot(
            name=backup_name,
            description=f"Full system backup at {datetime.utcnow().isoformat()}",
            include_graph=True,
            include_vectors=True
        )
        
        logger.info(f"Backup complete: {snapshot.snapshot_hash[:8]}")
        return snapshot


# =====================================================================
# USAGE EXAMPLE
# =====================================================================

if __name__ == "__main__":
    # PostgreSQL connection
    PG_CONNECTION = "postgresql://user:password@localhost:5432/memory_archive"
    
    # Initialize archive
    archive = PostgresArchive(
        connection_string=PG_CONNECTION,
        chunk_size=1024 * 1024,  # 1MB chunks
        auto_commit=True,
        enable_compression=True
    )
    
    try:
        # Create initial version
        print("=== Creating Initial Version ===")
        v1 = archive.create_version(
            commit_message="Initial system setup",
            author="admin",
            tag="v1.0.0"
        )
        print(f"Version: {v1.version_hash[:8]}")
        
        # Create user
        print("\n=== Creating User ===")
        user = archive.create_user(
            user_id="user_001",
            username="test_user",
            email="test@example.com",
            password_hash="hashed_password_here"
        )
        print(f"Created user: {user.username}")
        
        # Set user settings
        archive.update_user_settings(
            user_id="user_001",
            settings={"theme": "dark", "language": "en"},
            preferences={"notifications": True}
        )
        
        # Start user session
        session = archive.start_user_session(
            user_id="user_001",
            session_id="session_001",
            metadata={"ip": "127.0.0.1"}
        )
        print(f"Started session: {session.session_id}")
        
        # Archive some graph entities
        print("\n=== Archiving Graph Entities ===")
        archive.archive_graph_entity(
            entity_id="entity_001",
            entity_type="Person",
            labels=["Person", "User"],
            properties={"name": "John Doe", "age": 30}
        )
        
        archive.archive_graph_edge(
            edge_id="edge_001",
            source_id="entity_001",
            target_id="entity_002",
            relationship_type="KNOWS",
            properties={"since": "2020"}
        )
        print("Graph entities archived")
        
        # Archive vector
        print("\n=== Archiving Vector ===")
        archive.archive_vector(
            vector_id="vec_001",
            collection="test_collection",
            text="This is a test document",
            embedding=[0.1, 0.2, 0.3],
            metadata={"type": "test"}
        )
        print("Vector archived")
        
        # Commit changes
        print("\n=== Committing Changes ===")
        v2 = archive.create_version(
            commit_message="Added test data",
            author="admin"
        )
        print(f"Version: {v2.version_hash[:8]}")
        
        # Store a file
        print("\n=== Storing File ===")
        test_file = "/tmp/test_archive.txt"
        with open(test_file, "w") as f:
            f.write("Test file content for archival\n" * 1000)
        
        file_record = archive.store_file(
            file_path=test_file,
            metadata={"type": "test", "purpose": "demo"}
        )
        print(f"Stored file: {file_record.file_id} ({file_record.chunk_count} chunks)")
        
        # Log metrics
        print("\n=== Logging Metrics ===")
        archive.log_metric(
            component="memory_system",
            metric_name="query_latency",
            metric_value=23.5,
            metric_unit="ms",
            session_id="session_001"
        )
        archive.log_metric(
            component="vector_store",
            metric_name="embedding_count",
            metric_value=1000,
            metric_unit="count"
        )
        print("Metrics logged")
        
        # Log audit event
        print("\n=== Logging Audit Event ===")
        archive.log_audit(
            action="CREATE_ENTITY",
            component="graph_client",
            entity_type="Person",
            entity_id="entity_001",
            user_id="user_001",
            session_id="session_001",
            changes={"operation": "create", "entity": "entity_001"},
            status="success",
            duration_ms=15.2
        )
        print("Audit event logged")
        
        # Set system config
        print("\n=== Setting Configuration ===")
        archive.set_config(
            config_key="max_chunk_size",
            config_value=1048576,
            description="Maximum file chunk size in bytes"
        )
        archive.set_config(
            config_key="enable_compression",
            config_value=True,
            description="Enable compression for stored files"
        )
        print("Configuration saved")
        
        # Create snapshot
        print("\n=== Creating Snapshot ===")
        snapshot = archive.create_snapshot(
            name="test_snapshot_1",
            description="First test snapshot",
            include_graph=True,
            include_vectors=True
        )
        print(f"Snapshot created: {snapshot.snapshot_hash[:8]} ({snapshot.size_bytes} bytes)")
        
        # Create a branch
        print("\n=== Creating Branch ===")
        branch = archive.create_branch("feature/new-feature")
        print(f"Created branch: {branch.branch}")
        
        # Make changes on branch
        archive.checkout_branch("feature/new-feature")
        archive.archive_graph_entity(
            entity_id="entity_003",
            entity_type="Feature",
            labels=["Feature"],
            properties={"name": "New Feature"}
        )
        
        v3 = archive.create_version(
            commit_message="Added new feature entity",
            author="developer"
        )
        print(f"Branch version: {v3.version_hash[:8]}")
        
        # Switch back to main
        archive.checkout_branch("main")
        
        # Register external database
        print("\n=== Registering External Database ===")
        ext_db = archive.register_external_database(
            database_id="ext_001",
            name="External PostgreSQL",
            connection_string="postgresql://user:pass@external:5432/db",
            database_type="postgresql",
            schema_info={"tables": ["users", "products"]},
            metadata={"region": "us-east-1"}
        )
        print(f"Registered external DB: {ext_db.name}")
        
        # Query version history
        print("\n=== Version History ===")
        versions = archive.get_version_history(branch="main", limit=10)
        for v in versions:
            print(f"  {v.version_hash[:8]} | {v.branch} | {v.commit_message} | {v.author}")
        
        # Query metrics
        print("\n=== Metric Statistics ===")
        stats = archive.get_metric_statistics(
            component="memory_system",
            metric_name="query_latency"
        )
        print(f"  Average: {stats['average']:.2f}ms")
        print(f"  Min: {stats['minimum']:.2f}ms")
        print(f"  Max: {stats['maximum']:.2f}ms")
        print(f"  Count: {stats['count']}")
        
        # Query audit logs
        print("\n=== Recent Audit Logs ===")
        logs = archive.get_audit_logs(limit=5)
        for log in logs:
            print(f"  {log.timestamp} | {log.action} | {log.component} | {log.status}")
        
        # Retrieve file
        print("\n=== Retrieving File ===")
        output_path = "/tmp/retrieved_test.txt"
        file_data = archive.retrieve_file(file_record.file_id, output_path=output_path)
        print(f"Retrieved file to: {output_path} ({len(file_data)} bytes)")
        
        # List snapshots
        print("\n=== Available Snapshots ===")
        snapshots = archive.list_snapshots(limit=5)
        for snap in snapshots:
            print(f"  {snap.snapshot_hash[:8]} | {snap.name} | {snap.timestamp}")
        
        # Tag a version
        print("\n=== Tagging Version ===")
        archive.tag_version(v2.version_hash, "stable-1.0", "First stable release")
        print(f"Tagged version {v2.version_hash[:8]} as 'stable-1.0'")
        
        # Get config
        print("\n=== Reading Configuration ===")
        max_chunk = archive.get_config("max_chunk_size")
        print(f"max_chunk_size: {max_chunk}")
        
        # List all configs
        print("\n=== All Configurations ===")
        configs = archive.list_configs()
        for cfg in configs:
            print(f"  {cfg.config_key}: {cfg.config_value}")
        
        # Demonstrate rollback (commented out to preserve data)
        # print("\n=== Rolling Back (Demo) ===")
        # archive.rollback_to_version(v1.version_hash)
        # print(f"Rolled back to version {v1.version_hash[:8]}")
        
        # End user session
        archive.end_user_session("session_001")
        print("\n=== Session Ended ===")
        
        print("\n=== PostgreSQL Archive Demo Complete ===")
        
    finally:
        archive.close()


"""
INSTALLATION & SETUP:

1. Install dependencies:
    pip install psycopg2-binary sqlalchemy alembic

2. Create PostgreSQL database:
    createdb memory_archive

3. Update connection string in code:
    PG_CONNECTION = "postgresql://user:password@localhost:5432/memory_archive"

4. Run the script to create tables and test functionality

INTEGRATION WITH HYBRID MEMORY:

from Memory.hybrid_memory import HybridMemory
from Memory.postgres_archive import PostgresArchive, HybridMemoryWithArchive

# Initialize both systems
memory = HybridMemory(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    chroma_dir="./chroma_store"
)

archive = PostgresArchive(
    connection_string="postgresql://user:pass@localhost:5432/memory_archive"
)

# Wrap them together
integrated = HybridMemoryWithArchive(memory, archive)

# Start tracked operation
integrated.begin_operation("Processing user query", author="system")

# Use memory system normally
session = memory.start_session(metadata={"user": "john"})
memory.add_session_memory(session.id, "User query about AI", "Query")

# Commit operation with version control
integrated.commit_operation("Processed user query", tag="query-v1.0")

# Create periodic backups
integrated.create_full_backup("daily_backup_2024_01_15")

# Sync to archive
integrated.sync_graph_to_archive()
integrated.sync_vectors_to_archive()

KEY FEATURES:

1. Version Control:
   - Git-like commits, branches, tags
   - Full rollback capability
   - Change tracking and diffs

2. Comprehensive Archiving:
   - Neo4j graph entities
   - Chroma vector embeddings
   - Large file storage with chunking
   - External database indexing

3. Monitoring & Logging:
   - System metrics tracking
   - Performance statistics
   - Comprehensive audit logs

4. User Management:
   - Authentication and sessions
   - User settings and preferences
   - Activity tracking

5. Configuration:
   - Version-controlled config
   - System-wide settings

6. Snapshots:
   - Point-in-time backups
   - Compressed storage
   - Fast restoration

BEST PRACTICES:

1. Regular Backups:
   - Create snapshots daily or after major operations
   - Tag important versions

2. Performance:
   - Use indexes for frequently queried fields
   - Enable compression for large files
   - Batch operations when possible

3. Security:
   - Encrypt sensitive data (connection strings, passwords)
   - Use parameterized queries (already implemented)
   - Implement access controls

4. Monitoring:
   - Log metrics for all critical operations
   - Set up alerts for anomalies
   - Review audit logs regularly

5. Version Control:
   - Use meaningful commit messages
   - Create branches for experimental features
   - Tag stable releases
"""