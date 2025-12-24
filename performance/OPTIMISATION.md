

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

# Ollama Performance Optimisation Guide

This document provides a comprehensive, systems-level guide to optimising **Ollama** for maximum performance, with particular emphasis on **CPU-based inference**, **virtualised environments (Proxmox/KVM)**, and **NUMA-aware multi-socket servers**. The guidance is equally applicable to bare metal and containerised deployments, with notes where behaviour diverges.

The target audience is experienced system administrators, infrastructure engineers, and homelab operators who want deterministic, explainable performance from Ollama and its underlying `llama.cpp` runtime.

---

## 1. Architectural Overview

Ollama is a model management and inference service built on top of `llama.cpp`. Its performance characteristics are therefore governed by:

* CPU vector instruction availability (AVX, AVX2, FMA, AVX-512)
* Memory bandwidth and latency
* NUMA locality
* Thread scheduling efficiency
* Model quantisation format
* Context length and KV cache size

Unlike GPU inference, CPU inference scales *non-linearly* with core count and is highly sensitive to memory topology and cache behaviour.

---

## 2. Hardware Prerequisites and Expectations

### 2.1 CPU Capabilities

For acceptable performance, CPUs **must** support:

* AVX2 (mandatory for modern models)
* FMA (highly recommended)
* Large shared L3 caches

Verify inside the runtime environment:

```bash
lscpu | grep -E 'avx|fma'
```

If AVX2 is not present, performance will be severely degraded regardless of core count.

### 2.2 Multi-Socket Considerations

Dual- and quad-socket systems introduce NUMA domains. Cross-socket memory access can cost **2–4×** the latency of local access. Ollama does not automatically NUMA-partition workloads; this must be enforced at the OS or process level.

---

## 3. Virtualisation Strategy

### 3.1 VM vs Container vs Bare Metal

| Deployment    | Performance        | Notes                              |
| ------------- | ------------------ | ---------------------------------- |
| Bare Metal    | Best               | Full NUMA and cache control        |
| LXC Container | Near-native        | Preferred on Proxmox               |
| KVM VM        | Good (with tuning) | Requires careful CPU & NUMA config |

If using Proxmox, **LXC containers with CPU pinning** generally outperform full VMs for Ollama workloads.

---

## 4. Proxmox VM Optimisation (Critical Section)

### 4.1 CPU Configuration

* **CPU Type**: `host`
* **NUMA**: Enabled
* **Sockets**: Match physical socket count
* **Cores per Socket**: Match physical cores per socket

Example for a dual-socket, 2×24-core system:

```
Sockets: 2
Cores: 24
NUMA: enabled
CPU Type: host
```

This ensures:

* Correct exposure of AVX extensions
* Predictable NUMA memory allocation

### 4.2 CPU Pinning

Pin vCPUs to physical cores to avoid scheduler migration:

* Prevents cache thrashing
* Reduces cross-NUMA execution
* Improves tail latency

This can be done via Proxmox advanced CPU settings or `taskset` inside the VM.

### 4.3 Huge Pages

Enable huge pages to reduce TLB pressure:

On host:

```bash
echo 128 > /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages
```

In VM configuration:

```
hugepages: 1024
```

Both 2MB and 1GB hugepages should be benchmarked; results vary by workload.

---

## 5. Operating System Tuning

### 5.1 CPU Governor

Set to performance mode:

```bash
cpupower frequency-set -g performance
```

### 5.2 Swap and Memory Policy

Disable swap entirely:

```bash
swapoff -a
```

LLM inference is extremely sensitive to swap activity and memory compaction.

### 5.3 Transparent Huge Pages (THP)

Test both modes:

```bash
echo always > /sys/kernel/mm/transparent_hugepage/enabled
```

or

```bash
echo never > /sys/kernel/mm/transparent_hugepage/enabled
```

There is no universal best setting; benchmark both.

---

## 6. Ollama Runtime Configuration

### 6.1 Thread Control

Ollama does not always auto-scale optimally.

Explicitly configure threads:

```bash
export OLLAMA_NUM_THREADS=48
export OLLAMA_NUM_PARALLEL=1
```

Guidelines:

* Use **90–95%** of physical cores
* Avoid SMT oversubscription initially
* Scale parallel requests only after single-instance saturation

### 6.2 NUMA Binding

Bind Ollama to NUMA nodes explicitly:

```bash
numactl --cpunodebind=0,1 --membind=0,1 ollama serve
```

For multi-instance setups:

* Run one Ollama instance per NUMA node
* Bind each instance exclusively to its node

---

## 7. Model Selection and Quantisation

### 7.1 Quantisation Impact

Quantisation has a greater performance impact than adding cores.

Recommended formats for CPU inference:

| Format | Performance | Quality |
| ------ | ----------- | ------- |
| Q4_K_M | Excellent   | Good    |
| Q5_K_M | Very Good   | Better  |
| Q8_0   | Poor        | High    |
| FP16   | Very Poor   | Maximum |

Example:

```bash
ollama pull llama3:8b-instruct-q4_K_M
```

### 7.2 Context Length

Long context sizes increase KV cache memory traffic:

* Reduce context length where possible
* Avoid exceeding per-socket L3 cache capacity

---

## 8. Storage Optimisation

### 8.1 Model Storage

* Use **local NVMe** storage
* Avoid Ceph or network-backed volumes

Recommended disk settings:

* `virtio-scsi-single`
* `cache=none`
* `discard=on`

### 8.2 Model Warm-Up

Reduce first-token latency:

```bash
ollama run model "warmup"
```

---

## 9. Monitoring and Benchmarking

Deep visibility into CPU, memory, and NUMA behaviour is essential for serious Ollama optimisation. This section expands on tooling and concrete commands to observe and validate performance characteristics.

### 9.1 CPU and Thread-Level Monitoring

#### htop (NUMA-aware)

Run with NUMA awareness enabled:

```bash
htop
```

Inside htop:

* Enable **CPU NUMA nodes** view (F2 → Display options)
* Verify threads are evenly distributed
* Watch for migration between NUMA nodes

If threads constantly move between nodes, CPU pinning or numactl binding is insufficient.

#### perf (instruction efficiency)

Measure instructions per cycle and vector usage:

```bash
perf stat -e cycles,instructions,cache-misses,branch-misses \
  ollama run model "test"
```

Indicators:

* Low IPC (<1) suggests memory bottlenecks
* High cache-miss rate indicates poor locality or excessive context size

---

### 9.2 NUMA and Memory Diagnostics

#### numastat

Check memory locality:

```bash
numastat -p $(pidof ollama)
```

Healthy output:

* Majority of memory allocated on local nodes
* Minimal remote memory usage

High remote allocation indicates NUMA misbinding.

#### numactl validation

Verify runtime binding:

```bash
cat /proc/$(pidof ollama)/numa_maps | head
```

Look for dominant `N0=` / `N1=` mappings rather than even spread across all nodes.

---

### 9.3 Memory Bandwidth Saturation

LLM inference often saturates memory bandwidth before CPU.

#### pcm-memory (Intel)

```bash
pcm-memory.x
```

Watch:

* Local vs remote bandwidth
* Read-heavy workloads dominating

If remote bandwidth is high, reduce cross-socket usage.

#### perf memory counters

```bash
perf stat -e mem_load_retired.l3_miss,mem_load_retired.l2_miss \
  ollama run model "test"
```

---

### 9.4 Scheduler and CPU Migration

Check scheduler behaviour:

```bash
perf sched record ollama run model "test"
perf sched latency
```

High scheduling latency suggests:

* CPU overcommit
* Missing pinning
* Competing workloads

---

### 9.5 Disk and I/O Monitoring

While inference is CPU-bound, model loading and context growth can hit storage.

#### iostat

```bash
iostat -xz 1
```

Ensure:

* Near-zero await during inference
* NVMe operating within expected latency

#### blktrace (advanced)

```bash
blktrace -d /dev/nvme0n1
```

Useful for diagnosing unexpected disk stalls.

---

### 9.6 Ollama-Specific Debugging

Enable verbose runtime diagnostics:

```bash
OLLAMA_DEBUG=1 OLLAMA_NUM_THREADS=48 ollama run model
```

Look for:

* Backend selection (AVX2/AVX512)
* Thread count confirmation
* Context size allocation

---

### 9.7 Throughput Benchmarking

Use consistent prompts and measure tokens/sec manually:

```bash
time ollama run model "Write 500 words about NUMA optimisation"
```

Calculate:

```
Tokens per second = output_tokens / wall_time
```

Repeat across:

* Thread counts
* Quantisation formats
* NUMA bindings

Log results for comparison.

---

### 9.8 Power and Thermal Constraints

Thermal throttling silently kills performance.

#### turbostat (Intel)

```bash
turbostat --Summary --quiet
```

Check:

* Frequency stability
* Package power limits

#### sensors

```bash
sensors
```

Sustained inference should not trigger thermal throttling.

---

----|-------------|
| Low TPS, high CPU | Missing AVX2 |
| One socket idle | NUMA misconfiguration |
| High latency spikes | Swap or CPU migration |
| Poor scaling | Memory bandwidth saturation |

---

## 10. Scaling Strategies

### 10.1 Vertical Scaling Limits

CPU inference hits diminishing returns beyond:

* Memory bandwidth saturation
* L3 cache eviction
* NUMA interconnect limits

### 10.2 Horizontal Scaling

For multi-user workloads:

* Run multiple Ollama instances
* Pin each to a NUMA node or core group
* Front with a simple load balancer

---

## 11. When to Reconsider Architecture

Consider alternative approaches if:

* Tokens/sec does not scale beyond ~60–70% of theoretical
* Cross-NUMA traffic dominates runtime
* Power efficiency becomes unacceptable

At that point:

* GPU inference
* Model distillation
* Smaller expert models

may yield better results.

---

## 12. Summary Checklist

Highest-impact optimisations:

1. CPU type = `host`
2. NUMA enabled and aligned
3. Huge pages configured
4. Explicit thread control
5. Proper quantisation
6. NUMA-aware process binding
7. Swap disabled

---

End of document.
