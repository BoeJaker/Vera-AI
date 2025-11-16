# Database Server

## Overview

Database infrastructure setup and management for Vera's memory system, including Neo4j, ChromaDB, and PostgreSQL.

## Purpose

This directory contains:
- **Docker Compose** configuration for database stack
- **Database initialization** scripts
- **Maintenance utilities** for cleanup and optimization
- **Backup/restore** procedures

## Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Multi-database stack configuration |
| `purge.py` | Memory cleanup and maintenance utility |

## Database Stack

### Neo4j (Graph Database)
- **Purpose:** Knowledge graph storage (entities, relationships)
- **Port:** 7687 (Bolt), 7474 (HTTP Browser)
- **Usage:** Stores graph structure, relationships, entity metadata

### ChromaDB (Vector Database)
- **Purpose:** Semantic search via text embeddings
- **Port:** 8000
- **Usage:** Full text content storage with vector representations

### PostgreSQL (Relational Database)
- **Purpose:** Immutable archive and telemetry
- **Port:** 5432
- **Usage:** Layer 4 temporal archive, system logs, metrics

## Starting the Database Stack

### Using Docker Compose
```bash
cd Memory/database\ server

# Start all databases
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f neo4j
docker-compose logs -f chroma
docker-compose logs -f postgres
```

### Individual Services
```bash
# Start only Neo4j
docker-compose up -d neo4j

# Start only ChromaDB
docker-compose up -d chroma

# Start only PostgreSQL
docker-compose up -d postgres
```

## Configuration

### Docker Compose (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:latest
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/your_password
    volumes:
      - neo4j_data:/data

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma

  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: vera
      POSTGRES_PASSWORD: your_password
      POSTGRES_DB: vera_archive
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  neo4j_data:
  chroma_data:
  postgres_data:
```

### Environment Variables
```bash
# Neo4j
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# PostgreSQL
POSTGRES_URL=postgresql://vera:your_password@localhost:5432/vera_archive
```

## Memory Cleanup (`purge.py`)

Utility for cleaning up memory databases:

```bash
# Clear all memories (IRREVERSIBLE!)
python3 purge.py --all

# Clear only short-term buffer
python3 purge.py --short-term

# Clear specific session
python3 purge.py --session session_abc123

# Clear old sessions (older than 30 days)
python3 purge.py --older-than 30

# Dry run (preview what would be deleted)
python3 purge.py --all --dry-run
```

**Warning:** Memory deletion is permanent. Always backup before purging.

## Backup and Restore

### Neo4j Backup
```bash
# Dump database
docker exec neo4j neo4j-admin dump --database=neo4j --to=/backup/neo4j-backup.dump

# Copy from container
docker cp neo4j:/backup/neo4j-backup.dump ./backups/

# Restore
docker exec neo4j neo4j-admin load --from=/backup/neo4j-backup.dump --database=neo4j --force
```

### ChromaDB Backup
```bash
# Simply copy the data directory
docker cp chroma:/chroma/chroma ./backups/chroma-backup

# Restore
docker cp ./backups/chroma-backup chroma:/chroma/chroma
```

### PostgreSQL Backup
```bash
# Dump database
docker exec postgres pg_dump -U vera vera_archive > backups/postgres-backup.sql

# Restore
docker exec -i postgres psql -U vera vera_archive < backups/postgres-backup.sql
```

## Maintenance

### Database Health Checks
```bash
# Neo4j
curl http://localhost:7474

# ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# PostgreSQL
docker exec postgres pg_isready -U vera
```

### Performance Optimization

**Neo4j Indexes:**
```cypher
// Create indexes for common queries
CREATE INDEX entity_name FOR (n:Entity) ON (n.name);
CREATE INDEX session_timestamp FOR (s:Session) ON (s.timestamp);
CREATE INDEX memory_tags FOR (m:Memory) ON (m.tags);
```

**Vacuum PostgreSQL:**
```bash
docker exec postgres vacuumdb -U vera -d vera_archive --analyze
```

**ChromaDB Optimization:**
```python
# Rebuild embeddings with better model
from Memory.memory import VeraMemory
memory = VeraMemory()
memory.re_embed_all_documents()
```

### Resource Limits

Edit `docker-compose.yml` to set resource constraints:
```yaml
services:
  neo4j:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          memory: 2G
```

## Troubleshooting

### Neo4j Connection Failed
```bash
# Check if running
docker ps | grep neo4j

# Check logs
docker logs neo4j

# Restart
docker-compose restart neo4j
```

### ChromaDB Not Responding
```bash
# Check status
curl http://localhost:8000/api/v1/heartbeat

# Restart
docker-compose restart chroma
```

### Disk Space Issues
```bash
# Check volume sizes
docker system df -v

# Clean up unused volumes
docker volume prune

# Remove old backups
rm -rf backups/old/*
```

## Security

### Change Default Passwords
```bash
# Edit docker-compose.yml
NEO4J_AUTH: neo4j/strong_password_here
POSTGRES_PASSWORD: strong_password_here
```

### Network Isolation
```yaml
# Add network isolation in docker-compose.yml
networks:
  vera_internal:
    driver: bridge

services:
  neo4j:
    networks:
      - vera_internal
```

### Access Control
- Bind to localhost only: `127.0.0.1:7687`
- Use firewall rules for external access
- Enable SSL/TLS for production

## Monitoring

### Docker Stats
```bash
docker stats neo4j chroma postgres
```

### Database-Specific Monitoring

**Neo4j Metrics:**
```cypher
// Via Neo4j Browser
CALL dbms.listConfig() YIELD name, value
WHERE name STARTS WITH 'metrics'
RETURN name, value
```

**PostgreSQL Stats:**
```sql
SELECT * FROM pg_stat_database WHERE datname = 'vera_archive';
```

## Related Documentation

- [Memory System](../README.md) - Overall memory architecture
- [Memory Schema](../schema.md) - Database schema details
- [Database Setup Guide](../../README.md#installation) - Initial setup instructions

---

**Default Ports:**
- Neo4j Browser: http://localhost:7474
- Neo4j Bolt: bolt://localhost:7687
- ChromaDB API: http://localhost:8000
- PostgreSQL: localhost:5432

**Credentials:** See `docker-compose.yml` or `.env` file
