# view_history.py
import json
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from chromadb import PersistentClient

CHROMA_DIR = "chroma"  # path to your Chroma DB

def load_conversation():
    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection("conversation_memory")

    # You may need to adjust depending on your memory schema
    results = collection.get()
    conversations = []

    for doc, meta in zip(results["documents"], results["metadatas"]):
        conversations.append({
            "role": meta.get("role", "unknown"),
            "text": doc,
            "timestamp": meta.get("timestamp", "unknown"),
            "model": meta.get("model", "unknown")
        })

    return conversations

def display_conversation(conversations):
    console = Console()
    table = Table(title="Conversation History")

    table.add_column("Timestamp", style="dim", width=20)
    table.add_column("Role", style="cyan", width=10)
    table.add_column("Model", style="magenta", width=15)
    table.add_column("Message", style="white")

    for c in conversations:
        text_preview = c["text"][:60] + ("..." if len(c["text"]) > 60 else "")
        table.add_row(c["timestamp"], c["role"], c["model"], text_preview)

    console.print(table)

if __name__ == "__main__":
    conversations = load_conversation()
    display_conversation(conversations)

    while True:
        query = Prompt.ask("Filter (or 'q' to quit)", default="")
        if query.lower() == "q":
            break
        if query:
            filtered = [c for c in conversations if query.lower() in c["text"].lower()]
            display_conversation(filtered)
        else:
            display_conversation(conversations)
#