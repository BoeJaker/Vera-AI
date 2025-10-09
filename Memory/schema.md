# Memory System Schema Reference

## Node Fields

### Core Identification
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | String | ✅ | Unique identifier | `"mem_123456789"`, `"host_webserver_01"` |
| `type` | String | ✅ | Node type/category | `"user_input"`, `"host"`, `"api_endpoint"` |
| `labels` | String[] | ✅ | Neo4j labels | `["Entity", "Host", "Production"]` |

### Importance & Provenance
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `importance` | Enum | ✅ | `primary`, `secondary`, `tertiary` | `"primary"` |
| `generation_depth` | Integer | ✅ | Hops from primary source (0=primary) | `0`, `1`, `2` |
| `source_node` | String | ❌ | ID of node that generated this | `"mem_123456789"` |
| `is_primary_source` | Boolean | ✅ | Whether this is original data | `true` |
| `source_type` | String | ✅ | Creation method | `"user_input"`, `"nlp_extraction"`, `"file_upload"` |
| `source_app` | String | ❌ | Application that created this | `"research_assistant"` |
| `source_session` | String | ❌ | Session ID that created this | `"sess_123456"` |
| `source_user` | String | ❌ | User ID who created this | `"user_789"` |
| `provenance_chain` | String[] | ❌ | Chain of source nodes | `["mem_a", "mem_b"]` |

### Content & Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `text` | String | ❌ | Raw text content | `"Apple announced partnership..."` |
| `content_hash` | String | ❌ | Hash for deduplication | `"a1b2c3..."` |
| `language` | String | ❌ | Content language | `"en"`, `"es"` |
| `content_type` | String | ❌ | Content format | `"text"`, `"code"`, `"document"` |
| `top_keywords` | String[] | ❌ | Extracted keywords | `["AI", "partnership", "cloud"]` |

### Quality & Confidence
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `confidence` | Float | ✅ | 0.0-1.0 confidence score | `0.85` |
| `extraction_confidence` | Float | ❌ | NLP extraction confidence | `0.72` |
| `quality_score` | Float | ❌ | Overall quality metric | `0.91` |
| `verification_status` | String | ❌ | Verification state | `"verified"`, `"unverified"`, `"flagged"` |

### Temporal Management
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `created_at` | Timestamp | ✅ | Creation timestamp | `"2024-01-15T10:30:00Z"` |
| `updated_at` | Timestamp | ✅ | Last update timestamp | `"2024-01-15T10:35:00Z"` |
| `expires_at` | Timestamp | ❌ | Optional expiration | `"2024-02-15T10:30:00Z"` |

### Tool Interaction Capabilities
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `is_interactive` | Boolean | ❌ | Can be acted upon by tools | `true` |
| `supported_protocols` | String[] | ❌ | Interaction protocols | `["ssh", "http"]` |
| `required_tools` | String[] | ❌ | Tools needed for interaction | `["paramiko", "requests"]` |
| `interaction_capabilities` | String[] | ❌ | Possible actions | `["execute_command", "read_file"]` |
| `connection_parameters` | Dict | ❌ | Connection details | `{"hostname": "server", "port": 22}` |
| `security_context` | Dict | ❌ | Auth & security requirements | `{"auth_required": true}` |

### Resource Identifiers (for Interactive Nodes)
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `hostname` | String | ❌ | Network hostname | `"web-01.example.com"` |
| `ip_address` | String | ❌ | IP address | `"192.168.1.100"` |
| `fqdn` | String | ❌ | Fully qualified domain name | `"web-01.prod.example.com"` |
| `resource_id` | String | ❌ | Cloud/provider ID | `"i-1234567890"` |
| `mac_address` | String | ❌ | Hardware address | `"00:1B:44:11:3A:B7"` |

### Operational Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `environment` | String | ❌ | Deployment environment | `"production"` |
| `availability` | String | ❌ | Availability state | `"high"`, `"degraded"` |
| `health_status` | String | ❌ | Current health | `"healthy"`, `"unhealthy"` |
| `maintenance_window` | String | ❌ | Maintenance schedule | `"Sun 02:00-04:00 UTC"` |
| `last_maintenance` | Timestamp | ❌ | Last maintenance time | `"2024-01-15T02:00:00Z"` |

### Semantic & Vector
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `embedding_model` | String | ❌ | Model used for embeddings | `"all-MiniLM-L6-v2"` |
| `embedding_version` | String | ❌ | Model version | `"v1"` |
| `semantic_cluster` | String | ❌ | Cluster assignment | `"cluster_tech_companies"` |

### Domain & Organization
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `domain` | String | ❌ | Business domain | `"technology"`, `"healthcare"` |
| `subdomain` | String | ❌ | Specific area | `"ai_research"`, `"clinical_trials"` |
| `tags` | String[] | ❌ | Custom tags | `["urgent", "review_needed"]` |
| `priority` | String | ❌ | Priority level | `"low"`, `"medium"`, `"high"`, `"critical"` |

### Extraction-Specific (NLP/LLM Nodes)
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `extraction_method` | String | ❌ | Extraction method | `"spacy_ner"`, `"llm_extraction"` |
| `extraction_model` | String | ❌ | Model used | `"en_core_web_sm"` |
| `extraction_timestamp` | Timestamp | ❌ | When extraction occurred | `"2024-01-15T10:31:00Z"` |
| `entity_type` | String | ❌ | NER entity type | `"PERSON"`, `"ORG"`, `"GPE"` |
| `entity_text` | String | ❌ | Original entity text | `"Tim Cook"` |
| `span_start` | Integer | ❌ | Character start position | `25` |
| `span_end` | Integer | ❌ | Character end position | `33` |
| `normalized_text` | String | ❌ | Normalized form | `"Timothy Cook"` |
| `relationship_context` | String | ❌ | Full sentence context | `"Tim Cook will meet Satya Nadella"` |
| `dependency_path` | String | ❌ | Dependency parse path | `"nsubj-meet-dobj"` |
| `semantic_role` | String | ❌ | Semantic role | `"agent"`, `"patient"` |
| `llm_model` | String | ❌ | LLM model used | `"gpt-4"`, `"claude-3"` |
| `llm_temperature` | Float | ❌ | Generation temperature | `0.7` |
| `llm_prompt` | String | ❌ | Prompt used | `"Extract entities from..."` |
| `llm_usage_tokens` | Integer | ❌ | Token usage | `150` |

## Edge Fields

### Core Identification
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `src` | String | ✅ | Source node ID | `"mem_123"` |
| `dst` | String | ✅ | Target node ID | `"mem_456"` |
| `rel` | String | ✅ | Relationship type | `"MENTIONS"`, `"PART_OF"` |
| `edge_id` | String | ❌ | Unique edge identifier | `"edge_789"` |

### Importance & Confidence
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `importance` | Enum | ✅ | `primary`, `secondary`, `tertiary` | `"secondary"` |
| `confidence` | Float | ✅ | 0.0-1.0 confidence | `0.75` |
| `is_direct` | Boolean | ✅ | Direct observation vs inferred | `true` |
| `is_inferred` | Boolean | ✅ | Whether relationship was inferred | `false` |
| `inference_method` | String | ❌ | How relationship was inferred | `"nlp_extraction"`, `"llm_inference"` |
| `extraction_confidence` | Float | ❌ | NLP extraction confidence | `0.82` |

### Relationship Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `context` | String | ❌ | Text context | `"Apple announced partnership with Microsoft"` |
| `strength` | Float | ❌ | 0.0-1.0 relationship strength | `0.8` |
| `frequency` | Integer | ❌ | Occurrence frequency | `3` |
| `temporal_context` | String | ❌ | When valid | `"2024"`, `"Q1 2024"` |

### Temporal Management
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `created_at` | Timestamp | ✅ | Creation timestamp | `"2024-01-15T10:30:00Z"` |
| `updated_at` | Timestamp | ✅ | Last update timestamp | `"2024-01-15T10:35:00Z"` |
| `valid_from` | Timestamp | ❌ | Start validity | `"2024-01-01T00:00:00Z"` |
| `valid_to` | Timestamp | ❌ | End validity | `"2024-12-31T23:59:59Z"` |

### Source & Provenance
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `source_type` | String | ✅ | Establishment method | `"direct_input"`, `"nlp_extraction"` |
| `source_session` | String | ❌ | Creating session | `"sess_123456"` |

### Tool Interaction Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `interaction_method` | String | ❌ | Establishment method | `"ssh_discovery"`, `"api_call"` |
| `tool_used` | String | ❌ | Tool that established | `"nmap"`, `"aws_cli"` |
| `discovery_timestamp` | Timestamp | ❌ | When discovered | `"2024-01-15T10:30:00Z"` |
| `last_verified` | Timestamp | ❌ | Last verification | `"2024-01-16T10:30:00Z"` |

### Operational Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `operational_state` | String | ❌ | Current state | `"active"`, `"inactive"`, `"degraded"` |
| `bandwidth` | Integer | ❌ | Network bandwidth | `1000` (Mbps) |
| `latency` | Integer | ❌ | Connection latency | `50` (ms) |
| `protocol` | String | ❌ | Communication protocol | `"TCP"`, `"HTTP"`, `"SSH"` |

### Domain & Functional
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `domain` | String | ❌ | Business domain | `"technology"` |
| `relationship_type` | String | ❌ | Categorical type | `"business"`, `"technical"`, `"social"` |
| `weight` | Float | ❌ | Graph algorithm weight | `1.0` |
| `bidirectional` | Boolean | ❌ | Works both ways | `false` |

## Session Fields

### Core Identification
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | String | ✅ | Unique session ID | `"sess_123456789"` |
| `session_type` | String | ✅ | Session type | `"user_session"`, `"batch_job"`, `"system"` |

### Application Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `app_name` | String | ✅ | Running application | `"research_assistant"` |
| `app_version` | String | ❌ | Application version | `"2.1.0"` |
| `app_module` | String | ❌ | Specific module/feature | `"web_research"`, `"document_analysis"` |
| `app_config` | JSON | ❌ | Configuration | `{"max_results": 50}` |

### User & Agent Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `user_id` | String | ❌ | User identifier | `"user_789"` |
| `agent_id` | String | ❌ | AI agent identifier | `"agent_llama_70b"` |
| `agent_version` | String | ❌ | Agent model version | `"v3"` |
| `team_id` | String | ❌ | Team/group identifier | `"team_research"` |

### Temporal Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `started_at` | Timestamp | ✅ | Session start time | `"2024-01-15T10:30:00Z"` |
| `ended_at` | Timestamp | ❌ | Session end time | `"2024-01-15T11:30:00Z"` |
| `duration_seconds` | Integer | ❌ | Calculated duration | `3600` |
| `last_activity_at` | Timestamp | ❌ | Last activity | `"2024-01-15T11:25:00Z"` |

### Session Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `purpose` | String | ❌ | Session purpose | `"research_quantum_computing"` |
| `status` | String | ✅ | Current status | `"active"`, `"completed"`, `"failed"` |
| `focus_entities` | String[] | ❌ | Main entities | `["Apple", "Microsoft"]` |
| `topics` | String[] | ❌ | Session topics | `["AI", "partnerships"]` |

### Project Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `project_id` | String | ❌ | Project identifier | `"proj_alpha"` |
| `project_name` | String | ❌ | Project name | `"AI Research Initiative"` |
| `project_phase` | String | ❌ | Current phase | `"planning"`, `"execution"`, `"testing"` |
| `milestone` | String | ❌ | Current milestone | `"M3 - Model Training"` |
| `deliverable` | String | ❌ | Target deliverable | `"Trained transformer model"` |

### Performance & Metrics
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `memory_items_created` | Integer | ❌ | Memory item count | `45` |
| `entities_extracted` | Integer | ❌ | Extracted entities count | `23` |
| `relationships_found` | Integer | ❌ | Relationship count | `15` |
| `error_count` | Integer | ❌ | Error count | `2` |
| `avg_confidence` | Float | ❌ | Average confidence | `0.78` |
| `productivity_score` | Float | ❌ | Productivity metric | `0.85` |
| `focus_metric` | Float | ❌ | Focus level | `0.9` |
| `completion_estimate` | Float | ❌ | Completion estimate | `0.6` |

### System & Environment
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `environment` | String | ❌ | Deployment environment | `"development"`, `"production"` |
| `hostname` | String | ❌ | Server hostname | `"server-01"` |
| `ip_address` | String | ❌ | Client IP address | `"192.168.1.100"` |
| `user_agent` | String | ❌ | HTTP User-Agent | `"Mozilla/5.0..."` |

## Collection/Vector Store Fields

### Collection Context
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `collection_name` | String | ✅ | Vector collection name | `"session_sess_123"` |
| `collection_type` | String | ✅ | Collection type | `"session"`, `"long_term"`, `"entities"` |
| `collection_hierarchy` | String | ❌ | Hierarchical path | `"documents/technical/api_docs"` |

### Embedding Details
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `embedding_model` | String | ✅ | Model used | `"all-MiniLM-L6-v2"` |
| `embedding_dimensions` | Integer | ✅ | Vector dimensions | `384` |
| `embedding_normalized` | Boolean | ✅ | Whether normalized | `true` |

### Indexing & Performance
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `index_type` | String | ❌ | Vector index type | `"hnsw"`, `"flat"`, `"ivf"` |
| `index_params` | JSON | ❌ | Index parameters | `{"M": 16, "ef_construction": 200}` |
| `total_documents` | Integer | ❌ | Document count | `1500` |
| `last_index_update` | Timestamp | ❌ | Last index update | `"2024-01-15T10:30:00Z"` |

## Node Categories & Types

### Core Node Types
| Category | Type | Key Fields | Tool Interaction | Importance |
|----------|------|------------|------------------|------------|
| **Primary Data** | `user_input` | `text`, `user_id`, `timestamp` | ❌ | Primary |
| | `file_upload` | `file_path`, `file_size`, `mime_type` | ❌ | Primary |
| | `api_response` | `endpoint`, `status_code`, `response_data` | ❌ | Primary |
| **Extracted Entities** | `extracted_entity` | `entity_text`, `entity_type`, `span`, `confidence` | ❌ | Secondary |
| | `normalized_entity` | `canonical_form`, `variants`, `cluster_id` | ❌ | Secondary |
| **Interactive Resources** | `host` | `hostname`, `ip_address`, `os_type`, `environment` | ✅ SSH | Primary |
| | `api_endpoint` | `base_url`, `protocol`, `authentication_type` | ✅ HTTP/REST | Primary |
| | `database` | `connection_string`, `db_type`, `schema` | ✅ SQL | Primary |
| | `service` | `service_name`, `port`, `health_status` | ✅ API | Primary |
| **Infrastructure** | `network_device` | `device_type`, `mac_address`, `firmware` | ✅ SNMP/SSH | Primary |
| | `container` | `image`, `container_id`, `status` | ✅ Docker API | Primary |
| | `cloud_resource` | `provider`, `region`, `resource_type` | ✅ Cloud SDK | Primary |
| **Process & Workflow** | `process` | `pid`, `command`, `status` | ✅ Process mgmt | Secondary |
| | `workflow` | `steps`, `current_step`, `status` | ❌ | Secondary |
| | `task` | `assigned_to`, `deadline`, `priority` | ❌ | Tertiary |

## Relationship Taxonomy

### Core Relationship Categories
| Category | Relationships | Description |
|----------|---------------|-------------|
| **Hierarchical & Structural** | `PART_OF`, `CONTAINS`, `HAS_SUBTYPE`, `INSTANCE_OF`, `COMPOSED_OF` | Composition and type relationships |
| **Temporal & Sequential** | `FOLLOWS`, `PRECEDES`, `OCCURRED_DURING`, `TRIGGERED_BY`, `LEADS_TO` | Time-based and causal sequences |
| **Causal & Logical** | `CAUSES`, `DEPENDS_ON`, `REQUIRES`, `ENABLES`, `PREVENTS` | Logical dependencies and effects |
| **Semantic & Content** | `MENTIONS`, `REFERENCES`, `DESCRIBES`, `EXPLAINS`, `RELATED_TO` | Content-based connections |
| **Social & Organizational** | `WORKS_FOR`, `COLLABORATES_WITH`, `MANAGES`, `REPORTS_TO`, `OWNS` | People and organization relationships |
| **Spatial & Geographical** | `LOCATED_IN`, `NEAR`, `CONNECTED_TO`, `WITHIN` | Physical and geographic connections |
| **Functional & Operational** | `USES`, `PRODUCES`, `CONSUMES`, `CONTROLS`, `MONITORS` | System and operational relationships |
| **Similarity & Comparison** | `SIMILAR_TO`, `EQUIVALENT_TO`, `OPPOSITE_OF`, `BETTER_THAN`, `COMPARABLE_TO` | Comparative relationships |
| **Process & Workflow** | `INPUT_TO`, `OUTPUT_OF`, `VALIDATES`, `AFFECTS`, `IMPACTS` | Workflow and process connections |
| **Knowledge & Learning** | `LEARNED_FROM`, `BASED_ON`, `EXTENDS`, `IMPROVES`, `CONTRADICTS` | Knowledge derivation |
| **Session & Memory** | `EXTRACTED_IN`, `FOCUSES_ON`, `DERIVED_FROM`, `INFERRED_FROM`, `PROMOTED_FROM` | Memory system specific |
| **Emotional & Subjective** | `LIKES`, `PREFERS`, `TRUSTS`, `RECOMMENDS`, `AVOIDS` | Personal preferences |
| **Technical & System** | `CALLS`, `IMPLEMENTS`, `INHERITS_FROM`, `DEPLOYS_TO`, `INTEGRATES_WITH` | Technical system relationships |
| **Business & Economic** | `COMPETES_WITH`, `PARTNERS_WITH`, `ACQUIRED`, `INVESTS_IN`, `SELLS_TO` | Business relationships |
| **Creative & Design** | `INSPIRED_BY`, `VARIATION_OF`, `COMBINES`, `EVOLVED_FROM` | Creative relationships |
| **Infrastructure & Technical** | `RUNS_ON`, `CONNECTS_TO`, `DEPENDS_ON`, `MANAGES`, `MONITORS` | Infrastructure relationships |
| **Tool Interaction** | `CAN_EXECUTE_ON`, `CAN_QUERY`, `CAN_CONTROL`, `HAS_ACCESS_TO` | Tool capability relationships |
| **Data Provenance** | `EXECUTED_BY`, `GENERATED_BY`, `CAPTURED_FROM`, `TRANSFORMED_BY` | Data lineage relationships |

## Feature Flags & System Configuration

### System Feature Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `enable_nlp_extraction` | Boolean | `true` | Enable automatic NLP processing |
| `enable_llm_enrichment` | Boolean | `false` | Enable LLM-based enrichment |
| `enable_auto_promotion` | Boolean | `true` | Auto-promote high-confidence items |
| `enable_compression` | Boolean | `false` | Enable memory compression |
| `enable_cross_session_link` | Boolean | `true` | Link entities across sessions |
| `enable_relationship_inference` | Boolean | `true` | Infer implicit relationships |
| `enable_quality_scoring` | Boolean | `true` | Calculate quality scores |
| `enable_duplicate_detection` | Boolean | `true` | Detect duplicate content |
| `enable_real_time_indexing` | Boolean | `true` | Real-time vector indexing |
| `enable_background_cleanup` | Boolean | `false` | Background cleanup tasks |
| `enable_tool_interaction` | Boolean | `true` | Enable tool-based interactions |
| `enable_auto_discovery` | Boolean | `false` | Auto-discover relationships |
| `enable_postgres_logging` | Boolean | `true` | Log to PostgreSQL |
| `enable_backup_management` | Boolean | `true` | Automated backups |

### Extraction & Processing Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `extract_entities` | Boolean | `true` | Extract named entities |
| `extract_relationships` | Boolean | `true` | Extract relationships |
| `extract_keyphrases` | Boolean | `true` | Extract key phrases |
| `extract_sentiment` | Boolean | `false` | Extract sentiment scores |
| `extract_syntax` | Boolean | `false` | Extract syntactic information |
| `cluster_entities` | Boolean | `true` | Cluster similar entities |
| `normalize_entities` | Boolean | `true` | Normalize entity variants |
| `validate_extractions` | Boolean | `false` | Validate extractions |

### Tool Interaction Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `allow_ssh_connections` | Boolean | `true` | Allow SSH interactions |
| `allow_api_calls` | Boolean | `true` | Allow API interactions |
| `allow_database_queries` | Boolean | `true` | Allow database interactions |
| `require_authentication` | Boolean | `true` | Require auth for tools |
| `log_all_interactions` | Boolean | `true` | Log all tool interactions |

### Security Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `encrypt_sensitive_data` | Boolean | `true` | Encrypt sensitive data |
| `audit_tool_usage` | Boolean | `true` | Audit tool usage |
| `require_approval_for_destructive` | Boolean | `true` | Approve destructive ops |
| `limit_tool_permissions` | Boolean | `true` | Limit tool capabilities |
| `validate_tool_inputs` | Boolean | `true` | Validate tool inputs |

### Performance Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `use_caching` | Boolean | `true` | Enable caching |
| `use_batch_processing` | Boolean | `false` | Batch processing |
| `use_async_operations` | Boolean | `true` | Async operations |
| `use_compressed_embeddings` | Boolean | `false` | Compressed embeddings |
| `cache_tool_results` | Boolean | `true` | Cache tool results |
| `async_tool_operations` | Boolean | `true` | Async tool operations |
| `limit_concurrent_tools` | Integer | `5` | Max concurrent tools |
| `tool_timeout_seconds` | Integer | `30` | Tool timeout |
| `limit_relationship_depth` | Integer | `3` | Max relationship depth |
| `max_entities_per_doc` | Integer | `50` | Max entities per document |
| `vector_index_type` | String | `"hnsw"` | Vector index type |

### Node-Level Feature Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `allow_derivatives` | Boolean | `true` | Allow NLP extraction |
| `allow_compression` | Boolean | `true` | Allow compression |
| `enable_indexing` | Boolean | `true` | Include in indexes |
| `retain_indefinitely` | Boolean | `false` | Never auto-delete |
| `allow_tool_interaction` | Boolean | `true` | Allow tool interaction |
| `log_interactions` | Boolean | `true` | Log interactions |
| `require_approval` | Boolean | `false` | Require approval |

### Edge-Level Feature Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `is_autodiscovered` | Boolean | `false` | Auto-discovered |
| `requires_verification` | Boolean | `true` | Needs verification |
| `is_ephemeral` | Boolean | `false` | Temporary |
| `log_changes` | Boolean | `true` | Log changes |
| `allow_automatic_updates` | Boolean | `true` | Allow auto-updates |

## State Indicators

### System Health Indicators
| Indicator | Type | Description | Values |
|-----------|------|-------------|--------|
| `system_status` | String | Overall system status | `"healthy"`, `"degraded"`, `"maintenance"`, `"error"` |
| `memory_usage` | String | Memory utilization | `"low"`, `"normal"`, `"high"`, `"critical"` |
| `storage_health` | String | Storage health | `"healthy"`, `"warning"`, `"error"`, `"full"` |
| `index_status` | String | Vector index status | `"current"`, `"rebuilding"`, `"outdated"`, `"error"` |
| `api_status` | String | API availability | `"online"`, `"degraded"`, `"offline"` |
| `last_backup` | Timestamp | Last backup | ISO timestamp |
| `error_count` | Integer | Recent errors | number |
| `queue_size` | Integer | Processing queue | number |

### Session State Indicators
| Indicator | Type | Description | Values |
|-----------|------|-------------|--------|
| `session_state` | String | Session state | `"active"`, `"paused"`, `"completed"`, `"abandoned"`, `"error"` |
| `processing_state` | String | Processing state | `"idle"`, `"processing"`, `"indexing"`, `"extracting"`, `"completed"` |
| `focus_intensity` | String | Focus level | `"low"`, `"medium"`, `"high"`, `"scattered"` |
| `productivity_score` | Float | Productivity | 0.0-1.0 |
| `attention_span` | Integer | Attention span | minutes |

### Node State Indicators
| Indicator | Type | Description | Values |
|-----------|------|-------------|--------|
| `verification_status` | String | Verification state | `"unverified"`, `"verified"`, `"flagged"` |
| `quality_state` | String | Quality assessment | `"unknown"`, `"low"`, `"medium"`, `"high"` |
| `stability` | String | Data stability | `"volatile"`, `"stable"`, `"archived"` |
| `freshness` | String | Data recency | `"current"`, `"stale"`, `"outdated"` |

## Tag Taxonomies

### Project Management Tags
| Category | Example Tags | Description |
|----------|--------------|-------------|
| **Project Phase** | `planning`, `execution`, `testing`, `deployment`, `maintenance` | Current phase |
| **Priority Level** | `p0-critical`, `p1-high`, `p2-medium`, `p3-low`, `p4-backlog` | Priority |
| **Status** | `not_started`, `in_progress`, `blocked`, `completed`, `cancelled` | Status |
| **Risk Level** | `low_risk`, `medium_risk`, `high_risk`, `critical_risk` | Risk |
| **Complexity** | `simple`, `moderate`, `complex`, `very_complex` | Complexity |

### Domain & Industry Tags
| Domain | Example Tags | Description |
|--------|--------------|-------------|
| **Technology** | `ai-ml`, `web-dev`, `mobile`, `cloud`, `devops`, `cybersecurity` | Tech domains |
| **Business** | `strategy`, `marketing`, `sales`, `finance`, `operations`, `hr` | Business functions |
| **Research** | `academic`, `rnd`, `market-research`, `user-research`, `competitive-analysis` | Research types |
| **Creative** | `design`, `content-creation`, `video-production`, `ui-ux`, `branding` | Creative work |
| **Technical** | `backend`, `frontend`, `database`, `api`, `infrastructure`, `monitoring` | Technical areas |

### Content & Context Tags
| Category | Example Tags | Description |
|----------|--------------|-------------|
| **Content Type** | `documentation`, `code`, `meeting-notes`, `email`, `presentation`, `spec` | Format |
| **Audience** | `internal`, `external`, `technical`, `non-technical`, `executive`, `end-user` | Target |
| **Confidentiality** | `public`, `internal-only`, `confidential`, `restricted`, `secret` | Sensitivity |
| **Temporal** | `urgent`, `time-sensitive`, `long-term`, `archival`, `expiring` | Time relevance |
| **Quality** | `draft`, `reviewed`, `approved`, `final`, `deprecated` | Quality state |

### Process & Workflow Tags
| Category | Example Tags | Description |
|----------|--------------|-------------|
| **Workflow Stage** | `input`, `processing`, `review`, `approval`, `output`, `archive` | Stage |
| **Collaboration** | `individual`, `team`, `cross-team`, `external-partner`, `stakeholder` | Scope |
| **Decision State** | `proposed`, `discussing`, `voting`, `decided`, `implemented` | Progress |
| **Review Status** | `needs-review`, `in-review`, `reviewed`, `changes-requested` | Review state |

### Infrastructure Tags
| Category | Example Tags | Description |
|----------|--------------|-------------|
| **Environment** | `production`, `staging`, `development`, `testing` | Environment |
| **Team** | `team-infra`, `team-security`, `team-database` | Team |
| **Criticality** | `tier-1`, `tier-2`, `tier-3`, `non-critical` | Criticality |
| **Compliance** | `pci-compliant`, `hipaa-compliant`, `gdpr-compliant` | Compliance |

### Tool Interaction Tags
| Category | Example Tags | Description |
|----------|--------------|-------------|
| **Tool Type** | `ssh-tool`, `api-client`, `database-client`, `monitoring` | Category |
| **Access Level** | `read-only`, `read-write`, `admin`, `root` | Permissions |
| **Risk Level** | `low-risk`, `medium-risk`, `high-risk` | Risk |
| **Frequency** | `frequent`, `occasional`, `rare` | Usage frequency |

### Operational Tags
| Category | Example Tags | Description |
|----------|--------------|-------------|
| **Maintenance** | `auto-updated`, `manual-maintenance`, `self-healing` | Maintenance |
| **Availability** | `high-availability`, `redundant`, `single-point` | Availability |
| **Scale** | `small`, `medium`, `large`, `enterprise` | Scale |
| **Lifecycle** | `active`, `deprecated`, `legacy`, `decommissioned` | Lifecycle |



<!-- Processing tiers
A - Short Term

Vectorstore -Short term
    Contains conversational memories

B - Long Term

Micro Knowledge graph
    Tier 0 - Runtime processing
    Relevant knowledge is retrieved and scanned for potential unseen relationships in the given context

    Tier 1 - Light pre processing
    spacy processing for basic entity extraction 

    Tier 2 - Heavy post processing
    async llm processing for deeper inference

Macro Knowledge Graph



Vectorstore - Long term -->