# Todo
---
#### Open AI API Local reverse proxy 
redirect OpenAI api calls to the local api shim server

#### Integrate Cadvisor + Container labels
```
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['<docker-host-ip>:8080']
```
#### Supabase studio cant see all databases ? 
webui n8n
#### Graphiti Integration

#### Clickhouse integration

#### Fix N8N redirect URLS
change from localhost to llm.int  
- link google api to n8n
  
#### Define Memory Structure

ORG
Person
Product

CODEBASE
Function
Variable

Memory structure add-ons allows for new entities and relationships to be added

Write a memory shim
## Neo4j x Supabase

you can integrate **Neo4j** with **Supabase**, but it’s not a direct out-of-the-box integration since Supabase is built on PostgreSQL. You’ll need to bridge the two systems depending on what you want to achieve. Here are the main approaches:

---

### 🔌 Integration Approaches

1. **Application Layer Integration**
    
    - Use Supabase for authentication, storage, and Postgres.
        
    - Use Neo4j as a separate graph database for relationships.
        
    - Your backend (Node.js, Python, etc.) connects to **both Supabase (via PostgREST or Supabase client SDK)** and **Neo4j (via official drivers)**.
        
    - Example: Users and permissions live in Supabase, graph relationships (e.g., social network, dependencies) live in Neo4j.
        
2. **Foreign Data Wrapper (FDW) for PostgreSQL**
    
    - Supabase Postgres can access external data sources via FDWs.
        
    - There are community FDWs for **Neo4j** (like `neo4j_fdw`), though they’re not officially maintained.
        
    - With this, you can run SQL queries in Supabase that fetch from Neo4j.
        
    - ⚠️ Requires enabling custom extensions on your Supabase Postgres, which is not possible on hosted Supabase but works if you self-host.
        
3. **Data Sync / ETL Pipeline**
    
    - Use a tool like **Airbyte**, **Hasura Actions**, or a custom script to sync data between Supabase Postgres and Neo4j.
        
    - Example: A cron job listens for Supabase Postgres changes (via **realtime replication** or **logical replication**) and updates Neo4j accordingly.
        
    - This gives you both relational and graph views of your data.
        
4. **GraphQL Layer**
    
    - Supabase provides a Postgres API, while Neo4j has **GraphQL integration** (`@neo4j/graphql`).
        
    - You can build a **federated GraphQL gateway** (Apollo Federation, GraphQL Mesh) that merges Supabase and Neo4j into a single API.
        
    - This is a clean way to let clients query both without worrying about which database stores what.
        

---

### ✅ Recommended Setup

- If you’re on **hosted Supabase**: Use **application-layer integration** or a **GraphQL gateway**.
    
- If you’re **self-hosting Supabase**: You can experiment with FDWs or direct logical replication into Neo4j.



# Notes
---
## Structure

#### Model Layer:

API Router

Ollama

Classifier

Embedding

  

#### Memory Layer:

Supabase (postgres)

Supabase (vector)

ChromaDB ~

Neo4j - Graph Database

Bloom - Neo4j Visualisation

Graphiti - Knowledge graphing

  

#### Model Interface Layer:

Ollama OpenAI API Shim

  

#### Tool Layer:

MCP Server

  

#### Agent Layer:

Agentic Core

Model Router

Vera

  

#### Workflow Layer:

Flowise

N8N

  

#### UI Layer:

Open-WebUI

  

#### Orchestration:

  

#### Monitoring Layer:

Prometheus

Grafana