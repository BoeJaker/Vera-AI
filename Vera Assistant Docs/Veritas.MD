# Veritas (Vera)

### Full‑Duplex Conversational & Agentic AI Assistant

This project implements a conversational & agentic AI assistant using:

- **Ollama** for local LLM inference (fast and deep models)
- **LangChain** for orchestration
- **Chroma** for persistent conversational memory
- **Coqui TTS** for offline text‑to‑speech
- **Full‑duplex conversation** for fast acknowledgements while the deep model is thinking

The assistant can carry on natural conversations, remember past interactions, use programatic tools such as python functions & bash execution. speak & type responses, and acknowledge user queries in context before the full answer is ready.

---

## Features

- **Three‑tier reasoning**:
  - **Fast model** for immediate context‑aware acknowledgements
  - **Executor model** for strategic tool chain use
  - **Deep model** for detailed answers
- **Persistent conversational memory** shared memory using Chroma
- **Offline TTS** using Coqui TTS
- **Full‑duplex**:
  - Listens for queries or input
  - Immediate spoken acknowledgement
  - Detailed spoken answer after processing
- **Extensible architecture** for adding tool use and operator/executor models

## Planning

## WebCrawl

## Vector Memory

---

## Requirements

- Python 3.9 or newer
- 16 GB RAM minimum (200 GB+ recommended for large local models)
- [Ollama](https://ollama.ai/) installed and running locally
- A supported GPU is recommended for optimal performance

---

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourname/conversational-assistant.git
cd conversational-assistant
````

2. **Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

3. **Install Python dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Install Coqui TTS**

```bash
pip install TTS
```

5. **Verify Ollama is running**

```bash
ollama list
```

---

## Configuration

### Models

You will need two models in Ollama:

* **Fast model** for quick acknowledgements
  Example: `mistral:7b` or `llama3:8b`
* **Deep model** for detailed answers
  Example: `llama3:70b` or another large model

Update `main.py` to point to the desired models:

```python
fast_llm = ChatOllama(model="mistral:7b")
deep_llm = ChatOllama(model="llama3:70b")
```

### Memory

Chroma is used for conversational memory. The database will be created in the `chroma/` directory by default.

---

## Usage

Run the assistant:

```bash
python main.py
```

Speak or type a query. The assistant will:

1. Search memory for relevant context
2. If query is simple, answer immediately
3. If query is complex:

   * Generate an in‑context acknowledgement with the fast model
   * Speak the acknowledgement
   * Process the full answer with the deep model in the background
   * Speak the full answer when ready

---

## Example Interaction

**User:**
`Write a short poem about the moon.`

**Assistant (fast model):**
"That sounds poetic — let me think on it."

**Assistant (deep model, after processing):**

```
Silver light spills across the sea,
A quiet dance for you and me.
The moon above, serene and bright,
Guides our hearts through velvet night.
```

---

## Troubleshooting

### "No module named tts"

Ensure Coqui TTS is installed in your active virtual environment:

```bash
pip install TTS
```

Verify you are running the correct Python interpreter:

```bash
which python   # Linux/macOS
where python   # Windows
```

### Ollama connection errors

Make sure Ollama is running locally:

```bash
ollama serve
```

---

## Roadmap

* Performance Optimization
* Multi‑voice TTS with emotion control
* Improved fast‑model style adaptation
* WebSocket API for browser and remote clients
* Operator model for controlling a machine via the UI
---

## License

MIT License

```

---

If you want, I can also make a **matching `requirements.txt`** so this README works end‑to‑end without guessing dependencies.  
Do you want me to make that now?
```
