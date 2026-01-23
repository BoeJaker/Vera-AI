
* Configurable system prompt (fixed after init)
* Dedicated training objectives
* Auto-analysis of graph memory (Neo4j)
* Auto-analysis of vector stores (FAISS / Chroma / LanceDB / etc.)
* Evaluation + scoring
* Self-optimisation loops
* Tool-assisted batch training
* Fully user-queryable (via orchestration)
* Model-specific configuration blocks


# **Example Usage**

## **Init agent**

```python
agent = TrainingAgent(vera_instance, config_yaml_loaded)
```

## **Run training**

```python
examples = [
    {"input": "Sort numbers", "ideal_output": "List sorted numerically ascending."},
    {"input": "Summarise text", "ideal_output": "Short semantic summary."}
]

results = agent.train_on_examples(examples)
print(results)
```

## **Optimise memory systems**

```python
vs_report = agent.optimise_vectorstore()
g_report = agent.optimise_graphstore()
```

## **User query**

```python
agent.query("Based on your training, how should I refine this dataset?")
```

---

