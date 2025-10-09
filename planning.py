#!/usr/bin/env python3

"""
planner.py - LangChain + Ollama Planner with Chroma memory and adaptive updates (streaming version)

Usage:
    python planner.py create "Plan a 3D printing project"
    python planner.py replay "Plan a 3D printing project"
    python planner.py step "Plan a 3D printing project"
    python planner.py execute "Plan a 3D printing project"
    python planner.py list
"""

import os
import sys
import uuid
from typing import List, Optional

from langchain_community.chat_models import ChatOllama
from langchain_community.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain.embeddings import OllamaEmbeddings
from langchain.callbacks.base import BaseCallbackHandler
from langchain.agents import Tool, initialize_agent, AgentType
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from duckduckgo_search import DDGS
import subprocess
# --------------------------
# Config
# --------------------------
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
MODEL_NAME = "gemma3:12b"
EMBED_MODEL = "mistral:7b"

# --------------------------
# Color helper
# --------------------------
def color_llm(text: str, color: str = "cyan") -> str:
    colors = {
        "cyan": "\033[96m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "magenta": "\033[95m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

# --- Utility ---
def run_shell(command: str) -> str:
    """Executes a shell command and returns output or error."""
    try:
        result = subprocess.run(
            command, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = result.stdout.strip() if result.stdout else result.stderr.strip()
        return output or "[No output]"
    except Exception as e:
        return f"[Shell error] {str(e)}"


# def search_web(query: str) -> str:
#     """Performs a quick Wikipedia search for general info."""
#     try:
#         page_summary = wikipedia.summary(query, sentences=2, auto_suggest=True)
#         return page_summary
#     except wikipedia.exceptions.DisambiguationError as e:
#         return f"Multiple results found: {', '.join(e.options[:5])}"
#     except wikipedia.exceptions.PageError:
#         return f"No results found for '{query}'"
#     except Exception as e:
#         return f"[Search error] {str(e)}"


def read_file(filepath: str) -> str:
    """Reads a text file from local disk."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"[File not found] {filepath}"
    except Exception as e:
        return f"[Read error] {str(e)}"


def write_file(params: str) -> str:
    """Writes text to a file. Expects 'filepath|content' format."""
    try:
        if "|" not in params:
            return "[Write error] Invalid format. Use: filepath|content"
        filepath, content = params.split("|", 1)
        with open(filepath.strip(), "w", encoding="utf-8") as f:
            f.write(content.strip())
        return f"[File written] {filepath.strip()}"
    except Exception as e:
        return f"[Write error] {str(e)}"

def search_web(query: str, max_results: int = 5):
    """
    Search DuckDuckGo for the given query and return top results.
    Uses the 'duckduckgo-search' package.
    """
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"No results found for '{query}'"

        formatted_results = []
        for r in results:
            formatted_results.append(f"- {r['title']} ({r['href']})")

        return "\n".join(formatted_results)

    except Exception as e:
        return f"[Search error] {str(e)}"
    
def traverse_website(start_url, max_pages=10, same_domain=True):
    """
    Traverse and scrape a website starting from 'start_url'.
    
    Parameters:
        start_url (str): URL to start crawling from.
        max_pages (int): Max number of pages to visit.
        same_domain (bool): If True, only follow links on the same domain.
    """
    visited = set()
    queue = deque([start_url])
    domain = urlparse(start_url).netloc
    scraped_data = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            scraped_data.append({"url": url, "error": str(e)})
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)
        scraped_data.append({"url": url, "content": text_content[:2000]})  # Limit for memory

        # Extract new links
        for a in soup.find_all("a", href=True):
            next_url = urljoin(url, a["href"])
            if same_domain and urlparse(next_url).netloc != domain:
                continue
            if next_url not in visited:
                queue.append(next_url)

    return scraped_data

def user_input(prompt: str) -> str:
    """Prompt user for input and return the response."""
    try:
        response = input(prompt)
        return response.strip() if response else "[No input provided]"
    except EOFError:
        return "[Input interrupted]"
    
# --------------------------
# Streaming callback
# --------------------------
class StreamHandler(BaseCallbackHandler):
    def __init__(self, color: str = "green"):
        self.color = color
        self.buffer = ""

    def on_llm_new_token(self, token: str, **kwargs):
        print(color_llm(token, self.color), end="", flush=True)
        self.buffer += token

    def get_content(self):
        return self.buffer.strip()

# --------------------------
# Core Planner Class
# --------------------------
class Planner:
    def __init__(self, model_name: str = MODEL_NAME, persist_dir: str = CHROMA_DIR):
        self.embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        self.persist_dir = persist_dir
        self.vstore = Chroma(
            collection_name="plans",
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir
        )
        # Base non-streaming model (still useful for internal similarity)
        self.llm_base = ChatOllama(model=model_name, temperature=0.2)
        # Tool executor setup (stub example)
        tools = [
            Tool(
                name="Search Web",
                func=search_web,
                description="Useful for searching general information from a search engine given a query."
            ),
            Tool(
                name="Traverse Webpage",
                func=traverse_website,
                description="Useful for scraping a website starting from a URL. Input should be the start URL."
            ),
            Tool(
                name="Run Shell",
                func=run_shell,
                description="Executes a shell command on the system and returns the output."
            ),
            Tool(
                name="Read File",
                func=read_file,
                description="Reads a text file from disk. Input must be a full file path."
            ),
            Tool(
                name="Write File",
                func=write_file,
                description="Writes content to a file. Input should be in 'filepath|content' format."
            ),
            Tool(
                name="User Input",
                func=user_input,
                description="Asks the user for input and returns it. Useful for interactive steps."
            )
        ]
        self.tool_executor = initialize_agent(
            tools,
            self.llm_base,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )

    def _is_header(self, step: str) -> bool:
        """Determine if a step is just a header, not an actionable."""
        stripped = step.strip().lower()
        # Heuristic: colon, no verb, or very short
        if stripped.endswith(":"):
            return True
        if len(stripped.split()) <= 3:
            return True
        action_keywords = ["create", "install", "run", "set", "configure", "check", "generate", "test", "verify"]
        if not any(word in stripped for word in action_keywords):
            return True
        return False

    def _execute_actionable(self, step: str, context: str):
        """Send actionable step to tool executor with context."""
        print(color_llm(f"\n[Executing Actionable] {step}", "yellow"))
        # Your persis{tent system prompt
        system_prompt = (
            "You are a precise, reliable tool execution agent. "
            "Always interpret the task carefully and use the correct tool or combination of tools. "
            "If a tool's output is unclear, clarify in your own words. "
            "Prefer accuracy over speed. Dont overuse the web search tool unless necessary."
            "your job is to execute the given step of a plan with the provided context. not to generate new steps."
        )

        input_payload = (
            f"System Prompt:\n{system_prompt}\n\n"
            f"Context:\n{context}\n\n"
            f"Task:\n{step}"
        )
        try:
            result = self.tool_executor.run(input_payload)
            print(color_llm(f"[Tool Result] {result}", "green"))
        except Exception as e:
            print(color_llm(f"[Execution Error] {e}", "red"))

    def execute_plan_with_tools(self, topic: str):
        """Execute a stored plan with tool executor, keeping headers in context."""
        plan = self.get_plan(topic)
        if not plan:
            print(f"No saved plan found for: {topic}")
            return

        steps = [s.strip() for s in plan.split("\n") if s.strip()]
        context_headers = []

        for step in steps:
            if self._is_header(step):
                context_headers.append(step)
                print(color_llm(f"[Header] {step}", "cyan"))
            else:
                context = "\n".join(context_headers)
                self._execute_actionable(step, context)

    def _stream_llm(self, prompt: str, color: str = "green") -> str:
        """Utility to stream an LLM response."""
        stream_handler = StreamHandler(color=color)
        streaming_llm = ChatOllama(
            model=MODEL_NAME,
            temperature=0.2,
            streaming=True,
            callbacks=[stream_handler]
        )
        streaming_llm.predict(prompt)
        print()  # newline after streaming
        return stream_handler.get_content()

    def create_plan(self, topic: str) -> str:
        """Create a detailed step-by-step plan using streamed LLM output."""
        prompt = PromptTemplate(
            input_variables=["topic"],
            template=(
                "You are a detailed planner AI. Create a very detailed numbered step-by-step plan for: {topic}.\n"
                "Include specific actions. Some steps may require prompting the LLM later."
            )
        )
        print(color_llm(f"\n=== New Plan for '{topic}' ===\n", "green"))
        plan_text = self._stream_llm(prompt.format(topic=topic))
        self.save_plan(topic, plan_text)
        return plan_text

    def save_plan(self, topic: str, plan_text: str):
        """Save plan to Chroma memory."""
        doc_id = str(uuid.uuid4())
        self.vstore.add_documents([Document(page_content=plan_text, metadata={"topic": topic, "id": doc_id})])
        self.vstore.persist()

    def get_plan(self, topic: str) -> Optional[str]:
        """Retrieve closest plan from memory."""
        results = self.vstore.similarity_search(topic, k=1)
        if results:
            return results[0].page_content
        return None

    def replay_plan(self, topic: str):
        """Retrieve and print a saved plan."""
        plan = self.get_plan(topic)
        if plan:
            print(f"\n=== Plan for '{topic}' ===\n{plan}\n")
        else:
            print(f"No saved plan found for: {topic}")

    def generate_substeps(self, step: str, context: str) -> str:
        """Stream detailed substeps for a step."""
        prompt = (
            f"Given this step:\n'{step}'\n"
            f"and context:\n{context}\n"
            "Break it down into smaller, actionable substeps."
        )
        print(color_llm("\n=== Generated Substeps ===\n", "cyan"))
        return self._stream_llm(prompt, color="cyan")

    def refine_plan(self, original_plan: str, feedback: List[str]) -> str:
        """Stream an updated plan with execution feedback integrated."""
        prompt = (
            f"Original plan:\n{original_plan}\n\n"
            f"Execution feedback:\n" + "\n".join(feedback) + "\n\n"
            "Update the plan to account for failed steps, new insights, or extra context. "
            "Keep it structured and numbered."
        )
        print(color_llm("\n=== Updated Plan ===\n", "magenta"))
        return self._stream_llm(prompt, color="magenta")

    def step_through_plan(self, topic: str):
        """Interactive streamed step execution."""
        plan = self.get_plan(topic)
        if not plan:
            print(f"No saved plan found for: {topic}")
            return

        steps = [s.strip() for s in plan.split("\n") if s.strip()]
        feedback = []

        for i, step in enumerate(steps, 1):
            print(f"\nStep {i}: {step}")
            action = input(
                "Press [Enter] to continue, 'ask' to query LLM, 'sub' to generate substeps, "
                "'fail' to mark step failed, or 'note' to add context: "
            ).strip().lower()

            if action == "ask":
                question = input("What would you like to ask the LLM about this step? ")
                print(color_llm("\n=== LLM Response ===\n", "yellow"))
                self._stream_llm(question, color="yellow")

            elif action == "sub":
                context = "\n".join(steps[:i])
                self.generate_substeps(step, context)

            elif action == "fail":
                reason = input("Why did this step fail? ")
                feedback.append(f"Step {i} failed: {reason}")

            elif action == "note":
                note = input("Enter context or information to add: ")
                feedback.append(f"Note after step {i}: {note}")

        if feedback:
            updated_plan = self.refine_plan(plan, feedback)
            self.save_plan(topic, updated_plan)
            print("\nPlan saved with updates.")

        print("\nPlan execution completed!")

    def list_plans(self):
        """List all saved plans in Chroma memory."""
        try:
            docs = self.vstore.get(include=["metadatas", "documents"])
            metadatas = docs.get("metadatas", [])
            documents = docs.get("documents", [])

            if not documents:
                print("No saved plans found.")
                return

            print("\nAvailable Plans:")
            for meta, doc in zip(metadatas, documents):
                topic = meta.get("topic", "unknown topic")
                doc_id = meta.get("id", "no-id")
                preview = (doc[:60].replace("\n", " ") + "...") if len(doc) > 60 else doc
                print(f"- {topic} ({doc_id}) : {preview}")

        except Exception as e:
            print(f"Error listing plans: {e}")


# --------------------------
# CLI Mode
# --------------------------
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1].lower()
    try:
        topic = sys.argv[2]
    except:
        topic = None

    planner = Planner()

    if mode == "create":
        if not topic:
            print("Please provide a topic.")
            sys.exit(1)
        planner.create_plan(topic)

    elif mode == "replay":
        if not topic:
            print("Please provide a topic.")
            sys.exit(1)
        planner.replay_plan(topic)

    elif mode == "step":
        if not topic:
            print("Please provide a topic.")
            sys.exit(1)
        planner.step_through_plan(topic)
    
    elif mode == "execute":
        if not topic:
            print("Please provide a topic.")
            sys.exit(1)
        planner.execute_plan_with_tools(topic)

    elif mode == "list":
        planner.list_plans()

    else:
        print("Unknown mode. Use: create | replay | step | list")
        sys.exit(1)


if __name__ == "__main__":
    main()
