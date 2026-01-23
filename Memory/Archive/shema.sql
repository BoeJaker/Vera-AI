-- Graph Archive Database Schema with Versioning, Telemetry, and Analytics

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =====================================================
-- CORE GRAPH STORAGE
-- =====================================================

-- Full graph snapshots for point-in-time recovery
CREATE TABLE graph_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_type VARCHAR(50) NOT NULL, -- 'manual', 'auto', 'checkpoint'
    description TEXT,
    graph_data JSONB NOT NULL, -- Complete graph structure
    node_count INTEGER NOT NULL,
    edge_count INTEGER NOT NULL,
    metadata JSONB,
    compressed BOOLEAN DEFAULT FALSE,
    size_bytes BIGINT,
    checksum VARCHAR(64)
);

CREATE INDEX idx_snapshots_created ON graph_snapshots(created_at DESC);
CREATE INDEX idx_snapshots_type ON graph_snapshots(snapshot_type);

-- Event sourcing for all graph changes
CREATE TABLE graph_events (
    event_id BIGSERIAL PRIMARY KEY,
    event_uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL, -- 'node_added', 'node_removed', 'edge_added', etc.
    entity_type VARCHAR(20) NOT NULL, -- 'node', 'edge'
    entity_id VARCHAR(255) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    delta JSONB, -- Specific changes
    user_id VARCHAR(255),
    session_id UUID,
    source VARCHAR(100), -- 'ui', 'api', 'import', 'system'
    metadata JSONB
);

CREATE INDEX idx_events_occurred ON graph_events(occurred_at DESC);
CREATE INDEX idx_events_type ON graph_events(event_type);
CREATE INDEX idx_events_entity ON graph_events(entity_type, entity_id);
CREATE INDEX idx_events_session ON graph_events(session_id);
CREATE INDEX idx_events_user ON graph_events(user_id);

-- Current state of nodes (optimized for queries)
CREATE TABLE nodes (
    node_id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    node_type VARCHAR(100),
    label TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_nodes_type ON nodes(node_type);
CREATE INDEX idx_nodes_updated ON nodes(updated_at DESC);
CREATE INDEX idx_nodes_properties ON nodes USING GIN(properties);
CREATE INDEX idx_nodes_label_search ON nodes USING GIN(to_tsvector('english', label));

-- Current state of edges
CREATE TABLE edges (
    edge_id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_id VARCHAR(255) NOT NULL REFERENCES nodes(node_id),
    target_id VARCHAR(255) NOT NULL REFERENCES nodes(node_id),
    edge_type VARCHAR(100),
    weight NUMERIC(10, 4) DEFAULT 1.0,
    properties JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_edges_type ON edges(edge_type);
CREATE INDEX idx_edges_updated ON edges(updated_at DESC);
CREATE INDEX idx_edges_properties ON edges USING GIN(properties);

-- =====================================================
-- TELEMETRY & ANALYTICS
-- =====================================================

-- User sessions
CREATE TABLE user_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    ip_address INET,
    user_agent TEXT,
    device_type VARCHAR(50),
    browser VARCHAR(100),
    os VARCHAR(100),
    metadata JSONB
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_started ON user_sessions(started_at DESC);

-- User interactions and actions
CREATE TABLE user_interactions (
    interaction_id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES user_sessions(session_id),
    user_id VARCHAR(255),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_type VARCHAR(100) NOT NULL, -- 'click', 'search', 'zoom', 'select', etc.
    target_type VARCHAR(50), -- 'node', 'edge', 'canvas', 'control'
    target_id VARCHAR(255),
    action VARCHAR(100),
    details JSONB,
    duration_ms INTEGER,
    metadata JSONB
);

CREATE INDEX idx_interactions_session ON user_interactions(session_id);
CREATE INDEX idx_interactions_occurred ON user_interactions(occurred_at DESC);
CREATE INDEX idx_interactions_type ON user_interactions(interaction_type);

-- Performance metrics
CREATE TABLE performance_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES user_sessions(session_id),
    metric_type VARCHAR(100) NOT NULL, -- 'render_time', 'query_time', 'load_time', etc.
    metric_name VARCHAR(255) NOT NULL,
    value NUMERIC(12, 4) NOT NULL,
    unit VARCHAR(50), -- 'ms', 'seconds', 'bytes', etc.
    context JSONB, -- Additional context (graph size, query params, etc.)
    tags JSONB
);

CREATE INDEX idx_metrics_recorded ON performance_metrics(recorded_at DESC);
CREATE INDEX idx_metrics_type ON performance_metrics(metric_type);
CREATE INDEX idx_metrics_name ON performance_metrics(metric_name);

-- System events and errors
CREATE TABLE system_events (
    event_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_level VARCHAR(20) NOT NULL, -- 'info', 'warning', 'error', 'critical'
    event_category VARCHAR(100) NOT NULL, -- 'database', 'api', 'ui', 'background_job'
    event_name VARCHAR(255) NOT NULL,
    message TEXT,
    stack_trace TEXT,
    session_id UUID,
    user_id VARCHAR(255),
    context JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_system_events_occurred ON system_events(occurred_at DESC);
CREATE INDEX idx_system_events_level ON system_events(event_level);
CREATE INDEX idx_system_events_resolved ON system_events(resolved, occurred_at);

-- =====================================================
-- QUERY & ANALYSIS HISTORY
-- =====================================================

-- Search and query history
CREATE TABLE query_history (
    query_id BIGSERIAL PRIMARY KEY,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES user_sessions(session_id),
    user_id VARCHAR(255),
    query_type VARCHAR(100) NOT NULL, -- 'search', 'filter', 'path', 'algorithm'
    query_params JSONB NOT NULL,
    results_count INTEGER,
    execution_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    cached BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_query_history_executed ON query_history(executed_at DESC);
CREATE INDEX idx_query_history_type ON query_history(query_type);
CREATE INDEX idx_query_history_user ON query_history(user_id);

-- Saved views/filters
CREATE TABLE saved_views (
    view_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    view_config JSONB NOT NULL, -- Filter, layout, visibility settings
    is_public BOOLEAN DEFAULT FALSE,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ
);

CREATE INDEX idx_saved_views_user ON saved_views(user_id);
CREATE INDEX idx_saved_views_public ON saved_views(is_public, created_at);

-- =====================================================
-- COMPUTED METRICS & CACHE
-- =====================================================

-- Graph metrics cache (PageRank, centrality, etc.)
CREATE TABLE computed_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    metric_type VARCHAR(100) NOT NULL, -- 'pagerank', 'betweenness', 'clustering', etc.
    scope VARCHAR(50) NOT NULL, -- 'global', 'node', 'edge', 'subgraph'
    entity_id VARCHAR(255),
    metric_value NUMERIC(15, 8),
    metric_data JSONB,
    computation_time_ms INTEGER,
    graph_version UUID, -- Reference to snapshot
    invalidated BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_computed_metrics_type ON computed_metrics(metric_type, scope);
CREATE INDEX idx_computed_metrics_entity ON computed_metrics(entity_id);
CREATE INDEX idx_computed_metrics_valid ON computed_metrics(valid_until) WHERE NOT invalidated;

-- Community detection results
CREATE TABLE communities (
    community_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    algorithm VARCHAR(100) NOT NULL, -- 'louvain', 'label_propagation', etc.
    parameters JSONB,
    node_id VARCHAR(255) NOT NULL REFERENCES nodes(node_id),
    community_label INTEGER NOT NULL,
    modularity_score NUMERIC(10, 6),
    metadata JSONB
);

CREATE INDEX idx_communities_node ON communities(node_id);
CREATE INDEX idx_communities_label ON communities(community_label);

-- =====================================================
-- AUDIT & COMPLIANCE
-- =====================================================

-- Audit log for sensitive operations
CREATE TABLE audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(255) NOT NULL,
    session_id UUID,
    action VARCHAR(100) NOT NULL, -- 'export', 'delete', 'bulk_edit', 'access_restricted'
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    success BOOLEAN DEFAULT TRUE,
    risk_level VARCHAR(20) -- 'low', 'medium', 'high', 'critical'
);

CREATE INDEX idx_audit_occurred ON audit_log(occurred_at DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_risk ON audit_log(risk_level, occurred_at);

-- Data exports tracking
CREATE TABLE data_exports (
    export_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    user_id VARCHAR(255) NOT NULL,
    session_id UUID,
    export_type VARCHAR(50) NOT NULL, -- 'full', 'filtered', 'snapshot'
    format VARCHAR(20) NOT NULL, -- 'json', 'csv', 'graphml'
    filters JSONB,
    record_count INTEGER,
    file_size_bytes BIGINT,
    file_path TEXT,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT
);

CREATE INDEX idx_exports_user ON data_exports(user_id);
CREATE INDEX idx_exports_requested ON data_exports(requested_at DESC);

-- =====================================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- =====================================================

-- Daily graph statistics
CREATE MATERIALIZED VIEW daily_graph_stats AS
SELECT 
    DATE(occurred_at) as date,
    COUNT(*) as total_events,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) FILTER (WHERE event_type LIKE 'node_%') as node_events,
    COUNT(*) FILTER (WHERE event_type LIKE 'edge_%') as edge_events,
    AVG(CASE WHEN event_type = 'node_added' THEN 1 ELSE 0 END) as avg_nodes_added
FROM graph_events
GROUP BY DATE(occurred_at)
ORDER BY date DESC;

CREATE UNIQUE INDEX idx_daily_stats_date ON daily_graph_stats(date);

-- User activity summary
CREATE MATERIALIZED VIEW user_activity_summary AS
SELECT 
    user_id,
    COUNT(DISTINCT session_id) as total_sessions,
    MIN(occurred_at) as first_seen,
    MAX(occurred_at) as last_seen,
    COUNT(*) as total_interactions,
    COUNT(*) FILTER (WHERE interaction_type = 'search') as searches,
    COUNT(*) FILTER (WHERE interaction_type = 'select') as selections,
    AVG(duration_ms) as avg_interaction_duration
FROM user_interactions
WHERE user_id IS NOT NULL
GROUP BY user_id;

CREATE UNIQUE INDEX idx_user_activity_user ON user_activity_summary(user_id);

-- =====================================================
-- FUNCTIONS & TRIGGERS
-- =====================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER nodes_update_timestamp
    BEFORE UPDATE ON nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER edges_update_timestamp
    BEFORE UPDATE ON edges
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Log graph changes to events table
CREATE OR REPLACE FUNCTION log_graph_event()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO graph_events (event_type, entity_type, entity_id, after_state)
        VALUES (
            TG_TABLE_NAME || '_added',
            TG_TABLE_NAME,
            CASE 
                WHEN TG_TABLE_NAME = 'nodes' THEN NEW.node_id
                ELSE NEW.edge_id
            END,
            row_to_json(NEW)
        );
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO graph_events (event_type, entity_type, entity_id, before_state, after_state)
        VALUES (
            TG_TABLE_NAME || '_updated',
            TG_TABLE_NAME,
            CASE 
                WHEN TG_TABLE_NAME = 'nodes' THEN NEW.node_id
                ELSE NEW.edge_id
            END,
            row_to_json(OLD),
            row_to_json(NEW)
        );
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO graph_events (event_type, entity_type, entity_id, before_state)
        VALUES (
            TG_TABLE_NAME || '_removed',
            TG_TABLE_NAME,
            CASE 
                WHEN TG_TABLE_NAME = 'nodes' THEN OLD.node_id
                ELSE OLD.edge_id
            END,
            row_to_json(OLD)
        );
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER nodes_event_logger
    AFTER INSERT OR UPDATE OR DELETE ON nodes
    FOR EACH ROW
    EXECUTE FUNCTION log_graph_event();

CREATE TRIGGER edges_event_logger
    AFTER INSERT OR UPDATE OR DELETE ON edges
    FOR EACH ROW
    EXECUTE FUNCTION log_graph_event();

-- Invalidate computed metrics on graph changes
CREATE OR REPLACE FUNCTION invalidate_metrics()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE computed_metrics 
    SET invalidated = TRUE 
    WHERE NOT invalidated 
    AND (valid_until IS NULL OR valid_until > NOW());
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER invalidate_on_node_change
    AFTER INSERT OR UPDATE OR DELETE ON nodes
    FOR EACH STATEMENT
    EXECUTE FUNCTION invalidate_metrics();

CREATE TRIGGER invalidate_on_edge_change
    AFTER INSERT OR UPDATE OR DELETE ON edges
    FOR EACH STATEMENT
    EXECUTE FUNCTION invalidate_metrics();

-- =====================================================
-- UTILITY FUNCTIONS
-- =====================================================

-- Get graph state at a specific time
CREATE OR REPLACE FUNCTION get_graph_at_time(target_time TIMESTAMPTZ)
RETURNS TABLE (
    nodes JSONB,
    edges JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        jsonb_agg(jsonb_build_object(
            'id', n.node_id,
            'type', n.node_type,
            'label', n.label,
            'properties', n.properties
        )) as nodes,
        jsonb_agg(jsonb_build_object(
            'id', e.edge_id,
            'source', e.source_id,
            'target', e.target_id,
            'type', e.edge_type,
            'weight', e.weight,
            'properties', e.properties
        )) as edges
    FROM 
        nodes n
        CROSS JOIN edges e
    WHERE 
        n.created_at <= target_time 
        AND (n.deleted_at IS NULL OR n.deleted_at > target_time)
        AND e.created_at <= target_time
        AND (e.deleted_at IS NULL OR e.deleted_at > target_time);
END;
$$ LANGUAGE plpgsql;

-- Refresh materialized views
CREATE OR REPLACE FUNCTION refresh_analytics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_graph_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_activity_summary;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- PARTITIONING FOR LARGE TABLES
-- =====================================================

-- Partition graph_events by month for better performance
-- (Uncomment and adjust if you expect high volume)

/*
CREATE TABLE graph_events_y2025m01 PARTITION OF graph_events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE graph_events_y2025m02 PARTITION OF graph_events
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
-- Add more partitions as needed
*/

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE graph_snapshots IS 'Complete graph snapshots for point-in-time recovery';
COMMENT ON TABLE graph_events IS 'Event sourcing log of all graph changes';
COMMENT ON TABLE nodes IS 'Current state of all graph nodes';
COMMENT ON TABLE edges IS 'Current state of all graph edges';
COMMENT ON TABLE user_sessions IS 'User session tracking';
COMMENT ON TABLE user_interactions IS 'Detailed user interaction telemetry';
COMMENT ON TABLE performance_metrics IS 'Application performance metrics';
COMMENT ON TABLE system_events IS 'System events, warnings, and errors';
COMMENT ON TABLE query_history IS 'Search and query execution history';
COMMENT ON TABLE computed_metrics IS 'Cached graph algorithm results';
COMMENT ON TABLE audit_log IS 'Audit trail for compliance and security';