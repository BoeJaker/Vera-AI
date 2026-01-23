# Proposed Package layout (single view)

```
agent_framework/
├─ agents/                        # agent configs and prompts (YAML as per Option 1)
│  ├─ network/
│  │  ├─ agent.yaml
│  │  └─ prompt_template.j2
│  ├─ research/
│  └─ ...
├─ ingestion/
│  ├─ ingest_documents.py         # ingest docs into vectorstore + Neo4j (files)
│  ├─ ingest_graph_nodes.py       # ingest graph data into Neo4j (CSV/JSON)
│  └─ connectors/
│     ├─ qdrant_client.py
│     └─ faiss_client.py
├─ orchestrator/
│  ├─ orchestrator.py            # main runtime: model creation, agent registry, request routing
│  ├─ agent_manager.py           # manage agent lifecycle, hot-reload building
│  ├─ memory_manager.py          # unified interface to vector + graph memory
│  ├─ fusion_engine.py           # graph + vector fusion / retrieval pipeline
│  └─ trainer.py                 # reinforcement store & periodic rebuild
├─ eval/
│  ├─ eval_harness.py            # automated evaluation runner
│  ├─ metrics.py                 # metrics computation
│  └─ sample_tests/              # sample testcases (jsonl)
├─ api/
│  └─ app.py                     # FastAPI server exposing agent query endpoints
├─ scripts/
│  ├─ build_agents.py            # builds/bakes agents per YAML (Modelfile creation)
│  └─ rebuild_agent.sh
├─ requirements.txt
└─ README.md
```

---

# Quick notes before you run

* The code uses these core libraries: `neo4j`, `qdrant-client` (or `faiss` fallback), `jinja2`, `pyyaml`, `ollama` (py client), `fastapi`, `uvicorn`, `numpy`, `scikit-learn` (for similarity metrics). See `requirements.txt` below.
* Adjust Neo4j and vectorstore URIs and credentials in each agent's YAML config.
* The system assumes you will use Ollama CLI to create models via generated Modelfiles; `scripts/build_agents.py` ties into that flow.

---

# 1) `requirements.txt`

```
jinja2
pyyaml
neo4j
qdrant-client
faiss-cpu
numpy
scikit-learn
requests
fastapi
uvicorn
python-dotenv
ollama
tqdm
sentence-transformers
pandas
```

Install:

```bash
pip install -r requirements.txt
```

---

# 2) Agent Manager & Orchestrator

`orchestrator/agent_manager.py` — create, rebuild, and run agents; maintains registry.

```python
# orchestrator/agent_manager.py
import os
import subprocess
import yaml
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import logging

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
BUILD_DIR = ROOT / "build"
TEMPLATES_DIR = ROOT / "templates"

os.makedirs(BUILD_DIR, exist_ok=True)

env = Environment(loader=FileSystemLoader(str(ROOT)))

logger = logging.getLogger("agent_manager")
logger.setLevel(logging.INFO)

class AgentManager:
    def __init__(self, ollama_cmd="ollama"):
        self.ollama_cmd = ollama_cmd
        self.registry = {}  # name -> config

    def load_agent_config(self, path: Path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def build_modelfile(self, agent_name: str, cfg: dict):
        # Render system prompt template and includes
        agent_path = AGENTS_DIR / agent_name
        # Provide include_file function for jinja templates within agent folder
        def include_file(rel):
            p = agent_path / rel
            return p.read_text()

        env.globals['include_file'] = include_file

        template_name = cfg["system_prompt"]["template"]
        template = env.get_template(f"agents/{agent_name}/{template_name}")
        system_prompt = template.render(**cfg["system_prompt"].get("variables", {}))

        model_template = env.get_template("templates/Modelfile.j2")
        rendered = model_template.render(
            base_model=cfg["base_model"],
            parameters=cfg.get("parameters", {}),
            num_ctx=cfg["num_ctx"],
            gpu_layers=cfg["gpu_layers"],
            system_prompt=system_prompt
        )

        modelfile_path = BUILD_DIR / f"{agent_name}.Modelfile"
        modelfile_path.write_text(rendered)
        return modelfile_path

    def create_agent(self, agent_name: str):
        cfg_path = AGENTS_DIR / agent_name / "agent.yaml"
        if not cfg_path.exists():
            raise FileNotFoundError(cfg_path)
        cfg = self.load_agent_config(cfg_path)
        modelfile = self.build_modelfile(agent_name, cfg)
        model_name = cfg["name"]

        logger.info(f"Creating model {model_name} from {modelfile}")
        subprocess.run([self.ollama_cmd, "create", model_name, "-f", str(modelfile)],
                       check=True)
        # Optionally run keepalive
        self.registry[model_name] = cfg
        return model_name

    def create_all(self):
        for agent in os.listdir(AGENTS_DIR):
            if (AGENTS_DIR / agent).is_dir():
                try:
                    self.create_agent(agent)
                except Exception as e:
                    logger.exception("Failed to create agent %s: %s", agent, e)

    def get_config(self, model_name):
        return self.registry.get(model_name)
```

`orchestrator/orchestrator.py` — request routing and agent pooling.

```python
# orchestrator/orchestrator.py
from orchestrator.agent_manager import AgentManager
from orchestrator.memory_manager import MemoryManager
from orchestrator.fusion_engine import FusionEngine
import logging
import ollama  # expects ollama python client installed

logger = logging.getLogger("orchestrator")
logger.setLevel(logging.INFO)

class Orchestrator:
    def __init__(self, ollama_client=None):
        self.agent_mgr = AgentManager()
        self.memory = MemoryManager()
        self.fusion = FusionEngine(self.memory)
        self.ollama = ollama if ollama_client is None else ollama_client

    def start(self):
        # Build all models at startup
        self.agent_mgr.create_all()

    def query_agent(self, agent_name, user_query, params=None, use_memory=True):
        """
        1) Use fusion engine to gather context
        2) Build small dynamic user prompt (no system prompt)
        3) Call ollama.chat with model=agent_name and messages=[user]
        """
        cfg = self.agent_mgr.get_config(agent_name)
        if not cfg:
            raise ValueError("Agent not found: " + agent_name)

        # Step 1: retrieval
        context_chunks = []
        if use_memory:
            # FusionEngine merges vector + graph
            context_chunks = self.fusion.retrieve_for_agent(agent_name, user_query, cfg)

        # Build user message (include context short)
        user_message = user_query
        if context_chunks:
            # small injected context summary (short)
            summary = "\n".join(chunk[:1000] for chunk in context_chunks[:8])
            user_message = f"Context:\n{summary}\n\nUser: {user_query}"

        # Step 2: call model (no large system prompt)
        messages = [
            {"role": "user", "content": user_message}
        ]

        # Merge params
        params = params or {}
        response = self.ollama.chat(model=agent_name, messages=messages, **params)
        return response
```

---

# 3) Memory Manager (Vectorstore + Neo4j) & Fusion Engine

`orchestrator/memory_manager.py` — unified interface.

```python
# orchestrator/memory_manager.py
from neo4j import GraphDatabase
from ingestion.connectors.qdrant_client import QdrantClientWrapper
from ingestion.connectors.faiss_client import FaissClientWrapper
import yaml, os, logging

logger = logging.getLogger("memory_manager")
logger.setLevel(logging.INFO)

ROOT = os.path.dirname(os.path.dirname(__file__))
AGENTS_DIR = os.path.join(ROOT, "agents")

class MemoryManager:
    def __init__(self):
        # Lazy init
        self.neo4j_drivers = {}   # agent -> driver
        self.vector_clients = {}  # agent -> client

    def init_neo4j(self, agent_name, cfg):
        gcfg = cfg.get("graph")
        if not gcfg or not gcfg.get("enabled"):
            return None
        uri = gcfg["uri"]
        auth = (gcfg["user"], gcfg["password"])
        driver = GraphDatabase.driver(uri, auth=auth)
        self.neo4j_drivers[agent_name] = driver
        logger.info("Neo4j driver initialized for %s", agent_name)
        return driver

    def init_vector(self, agent_name, cfg):
        vcfg = cfg.get("vectorstore") or cfg.get("vectorstore", {})
        if not vcfg:
            return None
        backend = vcfg.get("backend", "qdrant")
        if backend == "qdrant":
            client = QdrantClientWrapper(vcfg["path"])
        else:
            client = FaissClientWrapper(vcfg["path"])
        self.vector_clients[agent_name] = client
        logger.info("Vector client initialized for %s (%s)", agent_name, backend)
        return client

    def index_document(self, agent_name, doc_id, text, meta=None):
        client = self.vector_clients.get(agent_name)
        if not client:
            raise RuntimeError("Vector client not initialized for " + agent_name)
        client.upsert(doc_id, text, meta or {})

    def query_vector(self, agent_name, text, top_k=10):
        client = self.vector_clients.get(agent_name)
        if not client:
            return []
        return client.search(text, top_k=top_k)

    def query_graph(self, agent_name, cypher, params=None):
        driver = self.neo4j_drivers.get(agent_name)
        if not driver:
            return []
        with driver.session() as s:
            res = s.run(cypher, params or {})
            return [r.data() for r in res]
```

`orchestrator/fusion_engine.py` — combine vector + graph retrieval.

```python
# orchestrator/fusion_engine.py
import logging
logger = logging.getLogger("fusion_engine")
logger.setLevel(logging.INFO)

class FusionEngine:
    def __init__(self, memory_manager):
        self.memory = memory_manager

    def retrieve_for_agent(self, agent_name, query, cfg):
        # 1) Vector retrieval
        results = []
        vcfg = cfg.get("vectorstore") or {}
        top_k = vcfg.get("top_k", 8)
        if vcfg.get("path"):
            vec_hits = self.memory.query_vector(agent_name, query, top_k=top_k)
            results.extend([h['payload']['text'] if 'payload' in h else h['text'] for h in vec_hits])

        # 2) Graph retrieval: map query entities -> cypher seeded search
        gcfg = cfg.get("graph")
        if gcfg and gcfg.get("enabled"):
            # naive: example cypher using full-text index
            cypher = gcfg.get("query_template") or "CALL db.index.fulltext.queryNodes('node_index', $q) YIELD node RETURN node LIMIT $limit"
            graph_hits = self.memory.query_graph(agent_name, cypher, {"q": query, "limit": gcfg.get("max_subgraph_nodes", 50)})
            # Convert to textual context
            for node in graph_hits:
                results.append(str(node))
        # 3) Merge & return top N
        return results[: top_k * 2]
```

---

# 4) Ingestion pipeline

`ingestion/ingest_documents.py` — ingest a folder of documents into vectorstore and optionally create Neo4j metadata nodes.

```python
# ingestion/ingest_documents.py
import os
import argparse
from orchestrator.memory_manager import MemoryManager
from sentence_transformers import SentenceTransformer
from pathlib import Path
import json
from tqdm import tqdm

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ingest_folder(agent_name, folder, mm: MemoryManager, cfg):
    mm.init_vector(agent_name, cfg)  # ensure vector client exists
    mm.init_neo4j(agent_name, cfg)
    model = SentenceTransformer(cfg.get("vectorstore", {}).get("embedder", "all-MiniLM-L6-v2"))
    for p in tqdm(Path(folder).rglob("*.md")):
        text = load_text(p)
        doc_id = f"{agent_name}::docs::{p.name}"
        # Optionally chunk here
        mm.index_document(agent_name, doc_id, text, meta={"path": str(p)})
    print("Ingestion complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--folder", required=True)
    args = parser.parse_args()

    from orchestrator.memory_manager import MemoryManager
    from orchestrator.agent_manager import AgentManager

    am = AgentManager()
    cfg = am.load_agent_config(os.path.join("agents", args.agent, "agent.yaml"))
    mm = MemoryManager()
    ingest_folder(args.agent, args.folder, mm, cfg)
```

`ingestion/ingest_graph_nodes.py` — ingest nodes/edges into Neo4j.

```python
# ingestion/ingest_graph_nodes.py
import csv, argparse
from neo4j import GraphDatabase
import yaml, os

def ingest_csv_to_neo4j(agent_cfg, nodes_csv, relations_csv):
    gcfg = agent_cfg["graph"]
    driver = GraphDatabase.driver(gcfg["uri"], auth=(gcfg["user"], gcfg["password"]))
    with driver.session() as session:
        # nodes CSV: id,label,props(json)
        with open(nodes_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                props = {}
                if row.get("props"):
                    props = yaml.safe_load(row["props"])
                session.run(
                    "MERGE (n:Node {id:$id}) SET n += $props, n.label = $label",
                    id=row["id"], props=props, label=row.get("label")
                )
        # relations CSV: from,to,type,props
        with open(relations_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                props = {}
                if row.get("props"):
                    props = yaml.safe_load(row["props"])
                session.run(
                    """
                    MATCH (a:Node {id:$from}), (b:Node {id:$to})
                    MERGE (a)-[r:REL {type:$type}]->(b)
                    SET r += $props
                    """,
                    from=row["from"], to=row["to"], type=row["type"], props=props
                )
    print("Graph ingestion complete.")
```

`ingestion/connectors/qdrant_client.py` — simple wrapper using qdrant-client.

```python
# ingestion/connectors/qdrant_client.py
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
import numpy as np
from sentence_transformers import SentenceTransformer
import os

class QdrantClientWrapper:
    def __init__(self, collection_name="default", url=None, api_key=None):
        self.collection = collection_name
        self.model = SentenceTransformer(os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2"))
        self.client = QdrantClient(url=url or "http://localhost:6333", api_key=api_key)
        # ensure collection exists
        try:
            self.client.recreate_collection(collection_name=self.collection,
                                            vectors_config=rest.VectorParams(size=self.model.get_sentence_embedding_dimension(),
                                                                            distance=rest.Distance.COSINE))
        except Exception:
            # maybe already exists; ignore
            pass

    def upsert(self, id, text, meta):
        vec = self.model.encode(text).tolist()
        self.client.upsert(collection_name=self.collection, points=[rest.PointStruct(id=id, vector=vec, payload={"text": text, **meta})])

    def search(self, text, top_k=10):
        vec = self.model.encode(text).tolist()
        hits = self.client.search(collection_name=self.collection, query_vector=vec, limit=top_k)
        # convert hits to common structure
        return [{"id": h.id, "score": h.score, "payload": h.payload} for h in hits]
```

`ingestion/connectors/faiss_client.py` — FAISS local fallback.

```python
# ingestion/connectors/faiss_client.py
import faiss
import numpy as np
import os, pickle
from sentence_transformers import SentenceTransformer
from pathlib import Path

class FaissClientWrapper:
    def __init__(self, store_path="faiss_store.pkl"):
        self.path = Path(store_path)
        self.model = SentenceTransformer(os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2"))
        if self.path.exists():
            self._load()
        else:
            self.ids = []
            self.vectors = np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype="float32")
            self.index = faiss.IndexFlatIP(self.vectors.shape[1]) if self.vectors.shape[1] else None

    def _save(self):
        with open(self.path, "wb") as f:
            pickle.dump({"ids": self.ids, "vectors": self.vectors}, f)

    def _load(self):
        with open(self.path, "rb") as f:
            data = pickle.load(f)
        self.ids = data["ids"]
        self.vectors = data["vectors"]
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    def upsert(self, id, text, meta):
        vec = self.model.encode(text).astype("float32")
        if self.vectors.shape[0] == 0:
            self.vectors = vec.reshape(1, -1)
            self.index = faiss.IndexFlatIP(vec.shape[0])
            self.index.add(self.vectors)
            self.ids = [id]
        else:
            self.index.add(vec.reshape(1, -1))
            self.vectors = np.vstack([self.vectors, vec.reshape(1, -1)])
            self.ids.append(id)
        self._save()

    def search(self, text, top_k=10):
        vec = self.model.encode(text).astype("float32").reshape(1, -1)
        if self.index is None or self.vectors.shape[0] == 0:
            return []
        D, I = self.index.search(vec, top_k)
        hits = []
        for score, idx in zip(D[0], I[0]):
            hits.append({"id": self.ids[idx], "score": float(score), "text": ""})
        return hits
```

---

# 5) Trainer & Rebuild flow

`orchestrator/trainer.py` — reinforcement storage and scheduled rebuild.

```python
# orchestrator/trainer.py
import json
from datetime import datetime
import os
import logging

logger = logging.getLogger("trainer")
logger.setLevel(logging.INFO)

TRAINING_STORE = os.path.join(os.path.dirname(__file__), "..", "training_store")

class Trainer:
    def __init__(self, memory_manager):
        os.makedirs(TRAINING_STORE, exist_ok=True)
        self.memory = memory_manager

    def store_example(self, agent_name, question, answer, rating="good"):
        ts = datetime.utcnow().isoformat()
        fname = os.path.join(TRAINING_STORE, f"{agent_name}__{ts}.json")
        with open(fname, "w") as f:
            json.dump({"question": question, "answer": answer, "rating": rating, "ts": ts}, f)
        # If rating good -> add to vector memory immediately
        if rating == "good":
            # small format: store question+answer as text
            self.memory.index_document(agent_name, f"train::{ts}", question + "\n\n" + answer, meta={"rating":rating})
        logger.info("Stored training example for %s -> %s", agent_name, fname)

    def nightly_rebuild(self, agent_name):
        """
        Example: re-embed graph nodes and training examples into vectorstore.
        """
        # find training examples, ingest them into vectorstore (if not already)
        for fname in os.listdir(TRAINING_STORE):
            if fname.startswith(agent_name + "__"):
                path = os.path.join(TRAINING_STORE, fname)
                with open(path, "r") as f:
                    rec = json.load(f)
                # Upsert into vector memory
                self.memory.index_document(agent_name, f"train::{rec['ts']}", rec["question"] + "\n\n" + rec["answer"], meta={"rating": rec["rating"]})
        logger.info("Nightly rebuild complete for %s", agent_name)
```

---

# 6) FastAPI server (API to query agents & push evaluation/reinforcement)

`api/app.py`

```python
# api/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator.orchestrator import Orchestrator
from orchestrator.agent_manager import AgentManager
from orchestrator.trainer import Trainer
import uvicorn

app = FastAPI()
orch = Orchestrator()
orch.start()
trainer = Trainer(orch.memory)

class QueryRequest(BaseModel):
    agent: str
    query: str
    params: dict = None

class ReinforceRequest(BaseModel):
    agent: str
    question: str
    answer: str
    rating: str  # 'good' or 'bad'

@app.post("/query")
def query(req: QueryRequest):
    try:
        res = orch.query_agent(req.agent, req.query, params=req.params or {}, use_memory=True)
        return {"ok": True, "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reinforce")
def reinforce(req: ReinforceRequest):
    try:
        trainer.store_example(req.agent, req.question, req.answer, req.rating)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

# 7) Automated Evaluation Harness

`eval/eval_harness.py` — run tests, log metrics, optional auto-reinforce.

```python
# eval/eval_harness.py
import json, os, time
from orchestrator.orchestrator import Orchestrator
from eval.metrics import compute_retrieval_hit_rate, compute_embedding_similarity
from pathlib import Path

class EvalHarness:
    def __init__(self, tests_dir="eval/sample_tests"):
        self.orch = Orchestrator()
        self.orch.start()
        self.tests_dir = Path(tests_dir)

    def run_test_file(self, agent_name, testfile):
        tests = [json.loads(line) for line in open(testfile)]
        results = []
        for t in tests:
            q = t["question"]
            expected = t.get("expected_answer", "")
            start = time.time()
            res = self.orch.query_agent(agent_name, q)
            latency = time.time() - start
            # compute metrics
            retrieved = res.get("retrieved", []) if isinstance(res, dict) else []
            hit = compute_retrieval_hit_rate(retrieved, expected)
            emb_sim = compute_embedding_similarity(res, expected)
            results.append({"question": q, "latency": latency, "hit": hit, "sim": emb_sim})
        out = {"agent": agent_name, "results": results}
        return out

    def run_all(self):
        reports = []
        for f in self.tests_dir.glob("*.jsonl"):
            # file name format: agentname.tests.jsonl
            agent = f.stem.split(".")[0]
            reports.append(self.run_test_file(agent, f))
        return reports
```

`eval/metrics.py` — helper metrics.

```python
# eval/metrics.py
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np

embedder = SentenceTransformer("all-MiniLM-L6-v2")

def compute_retrieval_hit_rate(retrieved, expected, threshold=0.7):
    # naive: check if expected string appears in any retrieved text
    for r in retrieved:
        t = r.get("payload", {}).get("text") or r.get("text") or str(r)
        if expected and expected.lower() in t.lower():
            return 1.0
    return 0.0

def compute_embedding_similarity(response, expected):
    # compute cosine similarity between response text and expected
    if not expected:
        return 0.0
    text = ""
    if isinstance(response, dict):
        # try extracting message content
        text = response.get("message", {}).get("content", "")
    elif isinstance(response, str):
        text = response
    v1 = embedder.encode([text])[0]
    v2 = embedder.encode([expected])[0]
    sim = cosine_similarity([v1], [v2])[0][0]
    return float(sim)
```

`eval/sample_tests/network.tests.jsonl` — sample format:

```json
{"question": "Is host 192.168.1.42 reachable?", "expected_answer": "reachable"}
{"question": "What is the subnet of gateway 192.168.1.1?", "expected_answer": "192.168.1.0/24"}
```

The harness produces per-question latency, retrieval hit and embedding similarity. Use results to decide whether to `reinforce` automatically or flag for human review.

---

# 8) Example: Automatic ingestion + scheduled rebuild flow

* Use `ingestion/ingest_documents.py` to ingest datasets into vectorstore.
* Use `ingestion/ingest_graph_nodes.py` to populate Neo4j.
* Trainer (`orchestrator/trainer.py`) can be scheduled (cron) to run `nightly_rebuild` per agent — reindex training examples and graph embeddings.

Example crontab entry:

```
0 3 * * * /usr/bin/python3 /path/to/agent_framework/scripts/nightly_rebuild_all.py
```

`nightly_rebuild_all.py` would iterate agents, call `Trainer.nightly_rebuild(agent)`.

---

# 9) Secure production considerations (summary)

* Protect Neo4j and qdrant endpoints with authentication and TLS
* Rate-limit ingestion and evaluation jobs
* Sanitize and validate CSV/JSON inputs to Neo4j
* Avoid storing PII unless encrypted and allowed
* Use RBAC for the API & orchestration layers
* Use container limits (cgroups) to prevent OOM while building agent Modelfiles
* Keep backups of training_store and vector indexes

---


