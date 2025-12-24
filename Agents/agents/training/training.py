class TrainingAgent:
    """
    Training-focused agent with fixed system prompt,
    online learning, vector/graph optimisation,
    and tool reinforcement capabilities.
    """

    def __init__(self, vera, config):
        self.vera = vera
        self.config = config

        # System prompt fixed at init
        self.system_prompt = config["system_prompt"]
        self.model_config = config.get("model", {})
        self.training_config = config.get("training", {})

        self.vector_cfg = config.get("vectorstore_optimisation", {})
        self.graph_cfg = config.get("graphstore_optimisation", {})

        self.enable_tool_training = (
            config.get("tools", {}).get("enable_tool_training", False)
        )

        self.eval_metrics = self.training_config.get("evaluation_metrics", [])

        # Initialise metrics storage
        self.training_history = []
        self.score_history = []

    # ----------------------------------------------------------------------
    # MODEL INVOCATION
    # ----------------------------------------------------------------------
    def _run_model(self, prompt):
        """Run the configured LLM with system prompt prepended."""
        llm_type = self.model_config.get("llm", "deep")

        full_prompt = f"{self.system_prompt}\n\nUser:\n{prompt}\n\nTrainingAgent:"
        return self.vera.llm_generate(llm_type, full_prompt)

    # ----------------------------------------------------------------------
    # PUBLIC: USER QUERY ENTRY POINT
    # ----------------------------------------------------------------------
    def query(self, prompt):
        """User-facing call into the training agent."""
        response = self._run_model(prompt)
        return response

    # ----------------------------------------------------------------------
    # TRAINING CORE
    # ----------------------------------------------------------------------
    def train_on_examples(self, examples):
        """
        Accepts a list of training examples like:
        [{"input": "...", "ideal_output": "..."}]
        """
        results = []

        for ex in examples:
            generated = self.query(ex["input"])
            score = self.evaluate_output(generated, ex["ideal_output"])
            self.score_history.append(score)

            if self.training_config.get("online_learning"):
                self._update_model_heuristics(ex, generated, score)

            results.append({
                "input": ex["input"],
                "ideal_output": ex["ideal_output"],
                "generated": generated,
                "score": score
            })

        self.training_history.append(results)
        return results

    # ----------------------------------------------------------------------
    # EVALUATION
    # ----------------------------------------------------------------------
    def evaluate_output(self, predicted, ideal):
        """Semantic + similarity + reasoning scoring."""
        score = 0.0

        if "similarity" in self.eval_metrics and hasattr(self.vera, "vector_memory"):
            emb_pred = self.vera.vector_memory.embed(predicted)
            emb_ideal = self.vera.vector_memory.embed(ideal)
            score += emb_pred.cosine_similarity(emb_ideal)

        if "semantic_accuracy" in self.eval_metrics:
            score += self._semantic_eval(predicted, ideal)

        if "reasoning_depth" in self.eval_metrics:
            score += self._reasoning_eval(predicted, ideal)

        if "tool_quality" in self.eval_metrics and self.enable_tool_training:
            score += self._tool_eval(predicted)

        return round(score, 3)

    # ----------------------------------------------------------------------
    # ONLINE MODEL IMPROVEMENT
    # ----------------------------------------------------------------------
    def _update_model_heuristics(self, example, output, score):
        """
        Create a training fragment that the agent uses to refine future reasoning.
        This is prompt-internal, not weight-based (safe).
        """
        training_note = f"""
        TRAINING UPDATE
        ----------------
        Input: {example['input']}
        Ideal Output: {example['ideal_output']}
        Model Output: {output}
        Score: {score}

        Summary of pattern improvement for future operations:
        """

        refinement = self.query(training_note)
        self.vera.memory.save_training_note("training_agent", refinement)

    # ----------------------------------------------------------------------
    # VECTORSTORE ANALYSIS
    # ----------------------------------------------------------------------
    def optimise_vectorstore(self):
        if not self.vector_cfg.get("enabled"):
            return None

        report = {}

        if hasattr(self.vera, "vectorstore"):
            index = self.vera.vectorstore

            if self.vector_cfg.get("compute_density"):
                report["density"] = index.compute_vector_density()

            if self.vector_cfg.get("compute_cluster_health"):
                report["cluster_health"] = index.compute_cluster_health()

            if self.vector_cfg.get("compute_outlier_nodes"):
                report["outliers"] = index.detect_outliers()

        return report

    # ----------------------------------------------------------------------
    # GRAPHSTORE (NEO4J) ANALYSIS
    # ----------------------------------------------------------------------
    def optimise_graphstore(self):
        if not self.graph_cfg.get("enabled"):
            return None

        report = {}

        if hasattr(self.vera, "mem") and hasattr(self.vera, "sess"):
            g = self.vera.mem.graph

            if self.graph_cfg.get("analyse_node_density"):
                report["node_density"] = g.compute_node_density()

            if self.graph_cfg.get("analyse_relation_cohesion"):
                report["relation_cohesion"] = g.compute_relation_cohesion()

            if self.graph_cfg.get("detect_sparse_paths"):
                report["sparse_paths"] = g.detect_sparse_paths()

        return report
