

# Ollama performance optimization guide (for large, static prompts)

> Goal: minimize repeated tokenization & KV-cache churn for a *large* system prompt that is mostly static; maximize throughput & reduce latency when serving many user requests that reuse that same context.

---

## 1. Principles — what actually matters

* **Avoid re-tokenizing static text**: sending a huge system prompt every request is expensive. Bake or cache it.
* **Keep model KV cache warm**: reuse the model instance across requests so the context doesn’t need to be recomputed from scratch.
* **Right-sizing context (num_ctx)**: increase the model context if your static prompt + incoming data need more tokens than the default window.
* **Use quantization / GPU offload smartly**: trade accuracy for memory/speed where acceptable.
* **Batch & parallelize**: combine user requests or use concurrent workers with pinned models to achieve higher throughput.
* **Monitor & measure**: measure p50/p95/p99 latency, memory, CPU, and model-resident memory (RSS), and tune accordingly.

---

## 2. Two recommended approaches (choose one)

### A — **Bake the prompt into a custom Modelfile (best for truly static prompts)**

Advantages: one-time cost at model build; runtime is fast; no per-request system message overhead.

Example `Modelfile`:

```text
FROM llama3
SYSTEM """
<VERY LARGE STATIC PROMPT GOES HERE>
"""
PARAMETER num_ctx 65536
PARAMETER keepalive 3600
# optionally set gpu_layers / other model-specific parameters if supported
```

Create:

```bash
ollama create my-baked-model -f Modelfile
# Then run:
ollama run my-baked-model --keepalive 3600
```

Notes:

* `num_ctx` depends on model support. Pick the largest stable value the model supports without OOM.
* This is the single largest win for static prompts.

---

### B — **Cache the tokenized system prompt & reuse model instances (when baking not practical)**

* Send the system prompt exactly once to a long-lived model process or session.
* Keep the model alive with `--keepalive` or an equivalent session feature.
* Use session IDs (if the server supports them) to avoid re-sending the same system message.

Example pattern (pseudocode):

```python
# Start a long-lived session
session = ollama.start_session(model="llama3", system=large_system_prompt)

# Re-use session for multiple users/requests
for request in incoming_requests:
    resp = session.run(user_message=request.text)
```

If sessions are not available, pin a worker process that holds the prompt in memory and exposes a lightweight local API.

---

## 3. System settings & OS tuning

### RAM and swap

* If you have lots of spare RAM, ensure the model process is allowed to use it (no cgroups / container limits blocking it).
* Avoid heavy swap usage — if the model or GPU pages get swapped you'll see huge latency spikes.
* For very large models, ensure `vm.overcommit_memory` is set per your environment; Linux default is usually okay for inference, but check your container runtime.

Commands (Linux examples):

```bash
# show memory limits
free -h
# check swap pressure
vmstat 1 5
```

### CPU affinity & NUMA

* Pin the model process to CPUs close to the memory (NUMA locality) to reduce remote memory access latency.
* Use `taskset` or `numactl`:

```bash
numactl --cpunodebind=0 --membind=0 ollama run ...
```

### Systemd service (example) — long-lived model with keepalive

Create a `systemd` unit so the model stays loaded and restarts if it crashes:

```ini
[Unit]
Description=Ollama model server (my-baked-model)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/ollama run my-baked-model --keepalive 86400
Restart=always
LimitNOFILE=65536
# Optional cpu/memory limits omitted if you want it to use all resources

[Install]
WantedBy=multi-user.target
```

`systemctl enable --now ollama-model.service`

---

## 4. Model configuration & quantization

### num_ctx

* `num_ctx` must be supported by the model. Larger values increase memory usage; find the sweet spot where the static prompt + max expected user message fit comfortably.
* If you set too large `num_ctx`, you may run out of RAM.

### quantization

* Use higher-quality quantizations (Q4/Q5 family if supported) when you need better long-context stability. Lower-bit quantizations save memory and increase throughput but may degrade accuracy.
* If you have huge RAM, prefer higher precision quantizations for stability of embeddings & contextual coherence.

### GPU offload

* If you have a GPU, moving some layers to GPU reduces CPU memory pressure and significantly lowers latency for larger models. Use `gpu_layers`/`offload` settings if Ollama exposes them.
* Keep an eye on PCIe bandwidth if host memory <-> GPU memory transfers happen frequently.

---

## 5. Runtime patterns for throughput and latency

### Keep a pool of worker processes

* Start `N` worker processes each with the baked prompt or session open.
* Use a lightweight load balancer (nginx, haproxy, or an in-process queue) to dispatch requests to workers.

### Batching

* For use-cases that can accept small additional latency, coalesce multiple short requests into a single batch to amortize overhead.
* For chatbots this is often *not* possible; for classification/embedding workloads it usually is.

### Concurrency

* If model instance is single-threaded for inference, more worker processes are beneficial.
* If model scales multi-threaded well, ensure `parallelism` configuration in Ollama (or the runtime) is tuned.

### Fast I/O

* Avoid sending the whole large system prompt over the network each request. Use baked model or local sessions.
* Keep persistent connections (HTTP keep-alive or WebSocket) to avoid TCP/TLS handshake overhead.

---

## 6. Memory & storage hygiene

* If model loads from disk frequently, put model artifacts on NVMe or RAM-disk for faster load times (RAM-disk only for ephemeral/test).
* Monitor memory fragmentation; long-lived processes can fragment memory leading to higher RSS. Restart workers periodically if needed (graceful rolling restarts).

---

## 7. Measuring & benchmarks you should run

Track:

* Latency (p50/p95/p99)
* Throughput (requests/sec)
* CPU and GPU utilization
* RSS, heap, and GPU memory usage
* Tokenization time vs generation time

Suggested microbenchmarks:

* Cold start: load model & run 1 request.
* Warm single-request: after keepalive warmed.
* Concurrency sweep: 1,2,4,8,16 workers.
* Payload size sweep: small (10 tokens), medium (200 tokens), large (2000 tokens).

Use `ab`, `wrk`, or custom load generator. Log results and iterate.

---

## 8. Practical troubleshooting checklist

* OOM / crash: decrease `num_ctx`, switch to a smaller quantization, or add RAM.
* High p99 latency: check for swapping, look for NUMA misbinding, or add more pinned workers.
* Inconsistent outputs: check quantization precision and batch sizes.
* Slow first request: expected; keepalive or baking resolves it.

---

# Neo4j + Vector Search — Design & Performance Guide

> Use case: you want to combine graph relationships (Neo4j) with vector similarity (embeddings) for RAG, recommendations, similarity + graph traversal queries.

---

## 1. Basic options to store embeddings

* **Store vectors as node properties** (e.g., `n.embedding = [0.123, -0.22, ...]`) — easiest.
* **Store vectors externally** (Milvus, Faiss, Qdrant, PGVector) with a reference id stored on Neo4j nodes — better for large-scale vector indexes and high-performance ANN.
* **Use Neo4j vector index** (if your Neo4j version supports a native vector index or a plugin) — convenient, but check performance & scaling limits.

Which to choose:

* If vectors are small in number (<100k) and queries are infrequent, storing on nodes may be fine.
* For >100k vectors or strict latency requirements, use an ANN engine (Milvus/Qdrant/Faiss) and link Neo4j as the graph metadata store.

---

## 2. Indexing & Cypher tips (storing on node as property)

### Create nodes with embeddings

Example (pseudo-prep):

```cypher
CREATE (d:Document {id: $id, title:$title, text:$text, embedding:$embedding})
```

### Create a numeric index for quick filtering (not vector)

```cypher
CREATE INDEX document_title FOR (d:Document) ON (d.title)
```

### Vector similarity in Cypher (if plugin/APOC available)

If you have a user-defined function for cosine similarity (or using APOC), you can do:

```cypher
WITH $query_embedding AS q
MATCH (d:Document)
WHERE d.embedding IS NOT NULL
WITH d, apoc.algo.cosineSimilarity(d.embedding, q) AS score
RETURN d, score
ORDER BY score DESC
LIMIT 10
```

> Note: naive scanning of all nodes is slow for many nodes. For production scale, prefer ANN index.

---

## 3. Using an ANN engine (recommended for scale)

Architecture:

* Neo4j stores node/relationship metadata & IDs.
* Vector index (Milvus/Qdrant/faiss/pgvector) holds embeddings and returns top K ids for a query vector.
* Application layer: query vector DB for top K, then fetch full nodes from Neo4j in a single multi-id Cypher query (or use Neo4j Bolt multi-get).

Flow:

1. Generate embedding for query.
2. ANN search → returns node ids (and distances).
3. Cypher `MATCH (n) WHERE n.id IN $ids RETURN n` to load full graph context.
4. Optionally perform graph traversal / relationships with the returned nodes as seeds.

Batching tip: query ANN for larger K (e.g., 100) and filter/sort in application — reduces round trips.

---

## 4. Hybrid Graph+Vector query pattern (fast)

* Use ANN to shortlist candidates.
* Use graph heuristics in Neo4j (relationship degree, freshness, type) to re-rank.
  Example re-rank cycle:

1. ANN gets top 100 IDs with similarity.
2. Cypher: `MATCH (n) WHERE n.id IN $ids OPTIONAL MATCH (n)-[r:RELATED_TO]->(m) RETURN n, count(r) as relCount ORDER BY relCount DESC, similarity DESC LIMIT 10`

This offloads heavy vector work to the ANN engine while using Neo4j for structural signal.

---

## 5. Neo4j performance tuning (practical tips)

* **Page cache**: allocate adequate `dbms.memory.pagecache.size` to hold your working set (indexes + frequently accessed nodes). If your graph is big, set this to a large fraction of RAM but leave room for OS & other processes.
* **Heap**: set `dbms.memory.heap.initial_size` and `dbms.memory.heap.max_size` appropriately; leave headroom for OS.
* **Indexes**: create indexes and constraints for lookup properties (id, labels).
* **Avoid expensive Cartesian products**: structure queries to use indexed lookups or `UNWIND` + `MATCH` patterns.
* **Use `PROFILE` and `EXPLAIN`**: always profile slow queries and look at the operator costs.
* **Use `apoc.periodic.iterate`** for bulk updates to avoid long transactions.
* **Transaction size**: keep transaction sizes moderate; very large transactions can cause memory spikes.

Example `neo4j.conf` knobs:

```
dbms.memory.heap.initial_size=8G
dbms.memory.heap.max_size=16G
dbms.memory.pagecache.size=32G
```

(Values are illustrative — size to your machine and leave room if Ollama runs on same host.)

---

## 6. Vector index considerations & ANN parameters

* Use **HNSW** for good latency/accuracy. Tune:

  * `M` (connectivity) — higher means better recall but more memory.
  * `efConstruction` — higher improves index quality at build time, increases index build time & memory.
  * `ef` at query time — higher increases recall and latency.
* For Faiss, use IVF+PQ or HNSW depending on dataset size & memory.
* For Milvus/Qdrant, tune collection parameters and shard counts for throughput.

Batching searches: send multiple queries per request when possible to amortize overhead.

---

## 7. Practical Cypher + ANN example (pseudo)

**Step A: ANN search (external)** returns `ids = [123,456,789]`

**Step B: Fetch nodes & relationships (single Cypher)**

```cypher
WITH $ids AS ids
UNWIND ids AS id
MATCH (d:Document {id:id})
OPTIONAL MATCH (d)-[r:RELATED_TO]->(other)
RETURN d, collect(other) AS neighbors
```

This reduces round trips and leverages Neo4j’s strength for relationship traversal.

---

## 8. Caching & denormalization

* Cache ANN results for hot queries in Redis to avoid repeated ANN + Cypher hits.
* Denormalize frequently used graph attributes into node properties so you can re-rank without heavy traversals.
* Precompute neighbors or centrality metrics offline and store results for fast read.

---

## 9. Monitoring & observability

* Monitor Neo4j: query latency, page cache hit ratio, GC pauses, transaction commit times.
* Monitor ANN engine separately: search latency, CPU, memory, and disk usage.
* Monitor the whole pipeline: request time broken into embedding compute, ANN lookup, Neo4j fetch, and application processing.

---

## 10. Example deployment architectures

### Small scale (single host)

* Ollama model baked + systemd worker(s) on host.
* Neo4j server on same host if memory allows (watch page cache).
* ANN engine (Qdrant/Milvus) on host or in a local container.
* Use Unix sockets or local TCP to reduce latency.

### Medium/large scale

* Dedicated Ollama inference nodes (one or more), autoscaled.
* Vector DB cluster (Milvus/Qdrant) with replication & sharding.
* Neo4j cluster for read replicas or causal clustering.
* API layer orchestrates ANN -> Neo4j -> application steps with caching.

---

## 11. Security & data hygiene

* Secure model endpoints and Bolt/HTTP for Neo4j.
* Be careful with embeddings in logs (they’re large).
* If embedding PII, follow data governance.

---

# Quick checklists (copy-paste)

## Ollama checklist (static prompt)

* [ ] Bake static prompt into `Modelfile` if static.
* [ ] Set `num_ctx` big enough for prompt + expected user tokens.
* [ ] Run model as a long-lived process (`--keepalive` / systemd) or session pooling.
* [ ] Use worker pool & load balancer for concurrency.
* [ ] Tune OS (NUMA, no swap, CPU pinning).
* [ ] Monitor p95/p99 and memory usage.

## Neo4j + Vector checklist

* [ ] Choose ANN engine for >100k vectors.
* [ ] Store ids in Neo4j, embeddings in ANN (or use Neo4j native vector index if small).
* [ ] Set `pagecache` and `heap` memory appropriately.
* [ ] Create indexes for lookup properties.
* [ ] Use ANN shortlist → Neo4j multi-get → graph re-rank pattern.
* [ ] Cache hot results in Redis.

---

# Example end-to-end flow (concrete)

1. Build `Modelfile` with static system prompt → create `my-baked-model`.
2. Start systemd service to run `ollama run my-baked-model --keepalive 86400`.
3. Application receives a user query:

   * Generate embedding (if using ANN) or send to model directly if using the model to embed.
   * Query ANN for top K IDs.
   * `MATCH (n) WHERE n.id IN $ids RETURN n, ...` to gather graph context.
   * Compose prompt to model using small dynamic user context only (no huge static prompt).
4. Return response.

---

# Appendix — useful snippets

### Modelfile (template)

```text
FROM llama3
SYSTEM """
<your very large system prompt here>
"""
PARAMETER num_ctx 32768
# optionally specify other params supported by Ollama
```

### Cypher to fetch multiple IDs quickly

```cypher
UNWIND $ids AS id
MATCH (d:Document {id: id})
RETURN d ORDER BY indexOf($ids, d.id)
```

### Re-rank candidate nodes (example pseudo)

```python
# after ANN returns [(id, score), ...]
ids = [id for id,score in ann_results]
nodes = session.run("MATCH (n) WHERE n.id IN $ids RETURN n, n.someMetric", ids=ids)
# re-rank in application by combining ANN score + someMetric
```

---

## Final notes & tradeoffs

* Baking prompts is the most robust speed win but reduces flexibility (every prompt change needs rebuilding).
* Keepalive + session pooling offers a flexible middle-ground.
* For vector search at scale, use an ANN engine — Neo4j alone is not optimized for massive ANN workloads.
* Always measure: small changes in `num_ctx`, quantization, or `ef` settings can give big differences.

---
