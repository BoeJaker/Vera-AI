# 🔹 Pre-LLM Capabilities (All Modules)

| Module                              | Purpose / Function                                                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **StreamNormalizerCapability**      | Normalize incoming events from multiple domains (news, social media, weather, OHLCV, flights, satellite) into a unified schema with standard fields.                |
| **CorpusParserCapability**          | Chunk and embed large text or code files, store them in Redis/vector DB, produce per-chunk summaries, enable LLM to process large corpora efficiently.              |
| **DriftDetectionCapability**        | Detects time-window drift in metrics or streams (OHLCV, social sentiment, packet data) to identify anomalous behavior.                                              |
| **GraphCentralityCapability**       | Scores nodes in the graph by centrality to prioritize high-impact events or entities.                                                                               |
| **BlastRadiusCapability**           | Simulates propagation of events through a graph to estimate downstream impact.                                                                                      |
| **PacketAnomalyModelingCapability** | Detects anomalies in network packet streams, flags unusual traffic for attention.                                                                                   |
| **EmbeddingNoveltyFilter**          | Computes embeddings of events or code chunks; flags those that are novel compared to stored embeddings for attention.                                               |
| **RelevanceScoringCapability**      | Scores events based on novelty, centrality, source reliability, and domain-specific metrics to filter low-value inputs.                                             |
| **GraphUpdaterCapability**          | Updates the Neo4j or other graph database with new nodes, edges, or properties based on filtered events or code/corpus insights.                                    |
| **InternalMonologueCapability**     | Maintains a structured “thought space” representing the system’s internal state, recent events, code context, hypotheses, risks, and internal notes.                |
| **SemanticRetrievalCapability**     | Enables retrieval of relevant past internal notes or code chunks via embeddings, providing context for reasoning or hypothesis generation.                          |
| **AttentionWeightingCapability**    | Assigns attention weights to events, code chunks, and monologue notes based on novelty, risk, graph centrality, and temporal recency; controls what is sent to LLM. |
| **MultiModelRoutingCapability**     | Chooses the appropriate LLM or model for a given event or corpus type (e.g., general reasoning vs code reasoning) before inference.                                 |
| **PolicyEngineGatingCapability**    | Pre-filters or blocks events or actions according to policy rules before they reach LLM or execution modules.                                                       |

---

# 🔹 Post-LLM Capabilities (All Modules)

| Module                                     | Purpose / Function                                                                                                                                  |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ResponseValidatorCapability**            | Validates LLM output for correctness, formatting, consistency, and compliance with constraints.                                                     |
| **ConfidenceEstimatorCapability**          | Estimates confidence or trustworthiness of LLM-generated output, aiding in decision-making.                                                         |
| **CodeEditorCapability**                   | Applies LLM-suggested edits to code chunks, merges them safely, supports structured large-scale code modifications.                                 |
| **ActionExecutorCapability**               | Executes LLM-proposed actions (alerts, code patches, API calls, system commands) only after policy approval.                                        |
| **MonologueRefinementCapability**          | Periodically summarizes internal monologue into higher-level abstractions, recursive summarization, merges past insights for strategic perspective. |
| **CrossDomainHypothesisLinkingCapability** | Connects events across multiple domains (social, market, weather, flights, satellite, graph) to propose causal hypotheses or forecasts.             |
| **TriggerBasedActionExecutionCapability**  | Monitors triggers (risk thresholds, high centrality, novelty events, code issues) to execute pre-approved or LLM-proposed actions automatically.    |

---

# 🔹 Key Features Integrated Across Modules

* **Redis-backed context memory** → stores monologue, embeddings, chunked summaries.
* **Neo4j graph integration** → updates nodes, edges, and metrics from events and monologue insights.
* **Time-window drift detection** → highlights anomalous trends in metrics or packets.
* **Blast radius simulation** → predicts downstream impact in the graph.
* **Multi-model routing** → selects LLM model optimized for event type or domain.
* **Policy engine gating** → pre-LLM and post-LLM filtering to enforce safety and compliance.
* **Semantic retrieval & novelty detection** → ensures LLM receives relevant, high-value context.
* **Recursive refinement & attention weighting** → compresses internal monologue intelligently.
* **Cross-domain hypothesis linking** → forms higher-level insights from disparate streams.
* **Automatic action execution** → safely carries out LLM-proposed actions triggered by insights.

---

✅ **Summary**

This is the **full set of capabilities we’ve designed for your PoC**, forming a **modular, cognitive-agent pipeline**:

* **Pre-LLM**: normalize, chunk, embed, score, filter, update monologue, compute attention, route models, enforce policy.
* **LLM**: reads filtered, high-value context; performs reasoning, summarization, code editing, hypothesis generation.
* **Post-LLM**: validate, refine, recursively summarize monologue, link cross-domain insights, and trigger safe actions.

---
