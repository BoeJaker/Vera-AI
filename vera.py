#!/usr/bin/env python3
# Vera.py - Vera - Sans corps - Sine corpore - без тела - 体なしで 

"""
Vera - AI System
Toolchain, multi-agent system with proactive focus management and tool execution.


TODO
    CPU pinning pools
    Memory
    Agents
    Tools

    Add
    Clean up tools and make them dynamically loaded
"""
 
# --- Imports ---
import sys
import os
import subprocess
import json
from typing import List, Dict, Any, Type
from typing import Optional, Callable
import threading
import time
# import asyncio
import inspect
import psutil
import re
from pydantic import BaseModel, Field
import io
import traceback
import ollama
# import types
from collections.abc import Iterator
from urllib.parse import quote_plus, quote

from duckduckgo_search import DDGS
from langchain_core.tools import tool
from langchain_community.llms import Ollama
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.memory import ConversationBufferMemory, VectorStoreRetrieverMemory, CombinedMemory
from langchain.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import (
    create_sync_playwright_browser,
    create_async_playwright_browser,
)
from langchain.tools import BaseTool
# --- Local Imports ---
from executive_0_9 import executive
sys.path.append(os.path.join(os.path.dirname(__file__), 'Memory'))
from memory import *

# sys.path.append(os.path.join(os.path.dirname(__file__), 'Toolchain'))
# from toolchain import ToolChainPlanner
# from corpus_crawler import *
# from total_crawl import *

# from models import fast_llm, deep_llm
# from memory import init_memory
# from speech import listen, speak
# from executor import tools
# from executive 

class PythonInput(BaseModel):
    code: str = Field(..., description="Python code to execute")


class UnrestrictedPythonTool(BaseTool):
    name: str = "unrestricted_python"
    description: str = "Executes arbitrary Python code. Full access to Python runtime. For advanced tasks."
    args_schema: Type[BaseModel] = PythonInput

    def _run(self, code: str) -> str:
        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()

        local_vars = {}

        try:
            try:
                result = eval(code, globals(), local_vars)
                if result is not None:
                    print(result)
            except SyntaxError:
                exec(code, globals(), local_vars)

            output = redirected_output.getvalue()
            return output.strip() or "[No output]"

        except Exception:
            return f"[Error]\n{traceback.format_exc()}"

        finally:
            sys.stdout = old_stdout

    def _arun(self, code: str):
        raise NotImplementedError("Async execution not supported.")

CONFIG_FILE = "vera_models.json"

def choose_models_from_installed():
    # Get list of installed Ollama models
    available_models = [m["model"] for m in ollama.list()["models"]]
    if not available_models:
        raise RuntimeError("[Vera Model Loader] No Ollama models found! Please install some models first.")

    # Default models (used if config file doesn't exist)
    default_models = {
        "embedding_model": "mistral:7b",
        "fast_llm": "gemma2",
        "intermediate_llm": "gemma3:12b",
        "deep_llm": "gemma3:27b",
        "reasoning_llm": "gpt-oss:20b",
        "tool_llm": "gemma2"
    }

    # Load last used models if available
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved_models = json.load(f)
                default_models.update(saved_models)
        except Exception:
            print("[Vera Model Loader] Warning: could not read config file, using defaults.")
    
    chosen_models = {}
    print("\n[Vera Model Loader] Select a model for each category:")
    for key, default in default_models.items():
        print(f"\nSelect model for {key.replace('_', ' ').title()} (default: {default})")
        for idx, model in enumerate(available_models, 1):
            print(f"{idx}. {model}")
        choice = input(f"Enter choice (1-{len(available_models)}) or press Enter for default: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(available_models):
            chosen_models[key] = available_models[int(choice) - 1]
        else:
            chosen_models[key] = default

    # Save chosen models for next run
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(chosen_models, f, indent=2)
    except Exception as e:
        print(f"[Vera Model Loader] Warning: could not save config: {e}")

    print("\n[Vera Model Loader] Selected Models:")
    for key, model in chosen_models.items():
        print(f"{key}: {model}")
    print()

    return chosen_models

# --- Agent Class ---
class Vera:
    """Vera class that manages multiple LLMs and tools for complex tasks.
    Started off as a triple agent, but now it has grown into a multi-agent system."""

    def __init__(self, chroma_path="./Memory/vera_agent_memory"):
        self.selected_models = choose_models_from_installed()
        self.embedding_llm = model=self.selected_models["embedding_model"]
        self.fast_llm = Ollama(model=self.selected_models["fast_llm"], temperature=0.2)
        self.intermediate_llm = Ollama(model=self.selected_models["intermediate_llm"], temperature=0.4)
        self.deep_llm = Ollama(model=self.selected_models["deep_llm"], temperature=0.6)
        self.reasoning_llm = Ollama(model=self.selected_models["reasoning_llm"], temperature=0.7)
        self.tool_llm = Ollama(model=self.selected_models["tool_llm"], temperature=0)
        
        # --- Setup Memory ---
        NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")
        CHROMA_DIR = "./Memory/chroma_store"
        ARCHIVE_PATH = "./Memory/archive/memory_archive.jsonl"

        self.mem = HybridMemory(
            neo4j_uri=NEO4J_URI,
            neo4j_user=NEO4J_USER,
            neo4j_password=NEO4J_PASSWORD,
            chroma_dir=CHROMA_DIR,
            archive_jsonl=ARCHIVE_PATH,
    )
        # Start a session (Tier 2)
        print("Starting a session...")
        self.sess = self.mem.start_session(metadata={"agent": "vera"})
        self.mem.add_session_memory(self.sess.id, "Session", "Session", metadata={"topic": "conversation"})
        # mem.link_session_focus(sess.id, ["proj_alpha"])  # Session focuses on the project
        # Add session thoughts and optionally promote one
        # print("Adding session thoughts...")
        # t1 = mem.add_session_memory(sess.id, "Investigate API rate limits for upstream service.", {"topic": "risk"})
        # t2 = mem.add_session_memory(sess.id, "Decision: use exponential backoff with jitter.", {"topic": "decision"}, promote=True)

        # --- Shared ChromaDB Memory ---
        embeddings = OllamaEmbeddings(model=self.embedding_llm)
        self.vectorstore = Chroma(
            persist_directory=chroma_path,
            embedding_function=embeddings
        )

        # Vector memory (long-term)
        self.vector_memory = VectorStoreRetrieverMemory(
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 5})
        )

        # Short-term conversation memory (buffer)
        self.buffer_memory = ConversationBufferMemory(
            memory_key="chat_history",  # Where chat history is stored
            input_key="input",     # Explicitly say which is the actual input
            return_messages=True
        )
        # Plan memory (short-term, for storing plans in buffer)
        self.plan_memory = ConversationBufferMemory(
            memory_key="plan_history",
            input_key="input",
            return_messages=True
        )
        # Plan long-term memory (vector store for plans)
        self.plan_vectorstore = Chroma(
            persist_directory=os.path.join(chroma_path, "plans"),
            embedding_function=embeddings
        )
        self.plan_vector_memory = VectorStoreRetrieverMemory(
            retriever=self.plan_vectorstore.as_retriever(search_kwargs={"k": 5})
        )
        # --- Proactive Focus Manager ---
        self.focus_manager = ProactiveFocusManager(agent=self)
        self.triage_memory = False
        # Combined memory = short-term + long-term
        self.memory = CombinedMemory(memories=[self.buffer_memory, self.vector_memory])
        # --- Fast Agent (small Gemma for quick replies) ---
        self.fast_llm = Ollama(model="gemma2", temperature=0.2)
        # --- Intermediate Agent (medium Gemma for more complex tasks) ---
        self.intermediate_llm = Ollama(model="gemma3:12b", temperature=0.4)
        # --- Deep Agent (larger Gemma for reasoning) ---
        self.deep_llm = Ollama(model="gemma3:27b", temperature=0.6)
        # --- Reasoning Agent --- (Reasoning-heavy tasks)
        self.reasoning_llm = Ollama(model="gpt-oss:20b", temperature=0.7)
        # --- Tool Executor ---
        self.tool_llm = Ollama(model="gemma2", temperature=0)
        
        # Playwright browser setup
        self.sync_browser = create_sync_playwright_browser()
        self.toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=self.sync_browser)
        self.playwright_tools = self.toolkit.get_tools()
        print(f"[Vera] Loaded {self.playwright_tools} Playwright tools.")
        
        self.executive_instance = executive(vera_instance=self)

        # Tool setup
        self.tools = self.load_tools() + self.playwright_tools
        print(f"[Vera] Loaded {self.tools} tools.")
        # Fast Agent that can handle simple tool queries
        self.light_agent = initialize_agent(
            self.tools,
            self.tool_llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True
        )
        # Deep Agent that can call tools itself
        self.deep_agent = initialize_agent(
            self.tools,
            self.deep_llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True
        )
        self.toolchain = ToolChainPlanner(self, self.tools)
                
        # Define callback to handle proactive thoughts:
        def handle_proactive(thought):
            print(f"Proactive Thought: {thought}")
            # Here, you could also feed it to fast_llm or notify the user interface
            # e.g., self.fast_llm.predict(thought) or queue message

        # Set callback
        self.focus_manager.proactive_callback = handle_proactive

    # @tool
    def review_output(self, query, response):
        """ Review output for correctness """
        review_prompt = f"""
            You are a reviewer.
            Here is the original query: {query}
            Here is the response: {response}

            Decide:
            - Is this response correct and complete? (yes/no)
            - If no, explain briefly what is missing or wrong.

            Output 'YES' if correct, or 'NO: <brief reason>' if not.
            """
        review = self.fast_llm.invoke(review_prompt)
        return review.strip()
    
    # @tool
    def read_own_source(self) -> str:
        """
        Reads and returns the full Python source code of the file this function is called from.
        """
        try:
            # Get the path of the current running script (the file this function is defined in)
            current_file = inspect.getfile(inspect.currentframe())
            with open(current_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
            return source_code
        except Exception as e:
            return f"Error reading source code: {e}"

    # @tool    
    def fast_llm_func(self, q):
        """ Query a fast LLM"""
        result=""
        for x in self.stream_llm_with_memory(self.fast_llm, q, long_term=False, short_term=True):
            text = x if isinstance(x, str) else str(x)
            # print(r)
            result += x
            yield x
        self.mem.add_session_memory(self.sess.id, text, "Answer", {"topic": "decision", "agent": self.selected_models["fast_llm"]})
        # return result

    # @tool
    def deep_llm_func(self, q):
        """ Query a deep LLM"""
        result=""
        for x in self.stream_llm_with_memory(self.deep_llm, q, long_term=True, short_term=True):
            text = x if isinstance(x, str) else str(x)
            # print(r)
            result += x
            yield x
        self.mem.add_session_memory(self.sess.id, text, "Answer", {"topic": "decision", "agent": self.selected_models["deep_llm"]})
        # return result
    
    # @tool
    def write_file_tool(self, q):
        """ Write a file """
        try:
            # Expecting "path::content"
            path, content = str(q).split("|||", 1)
            with open(path.strip(), 'w', encoding='utf-8') as f:
                f.write(content)
            m1 = self.mem.add_session_memory(self.sess.id, path, "file", metadata={"status": "active", "priority": "high"}, labels=["File"], promote=True) # Add memory metadata
            m2 = self.mem.attach_document(self.sess.id, path, content, {"topic": "write file", "agent": "Vera"}) # Add document content
            # m2 = self.mem.attach_document(path.strip(), os.path.basename(path.strip()), content, {"doc_type": "generated"})
            self.mem.link(m1.id, m2.id, "Written")
            return f"File written successfully to {path}"
        except ValueError:
            return "Invalid write_to_file input format. Use: path|||content"
        except Exception as e:
            return f"Error writing file: {e}"

    # @tool
    def read_file_tool(self, q):
        """Read a file and return its contents."""
        try:
            if os.path.exists(q):
                with open(q, 'r', encoding='utf-8') as f:
                    content = f.read()
                m1 = self.mem.add_session_memory(self.sess.id, q, "file", metadata={"status": "active", "priority": "high"},  labels=["File"], promote=True) # Add memory metadata
                m2 = self.mem.attach_document(self.sess.id, q, content, {"topic": "write file", "agent": "Vera"}) # Add document content
                # m2 = self.mem.attach_document(path.strip(), os.path.basename(path.strip()), content, {"doc_type": "generated"})
                self.mem.link(m1.id, m2.id, "Read")
                return content
        except Exception as e:
            return f"Error reading file {q}: {e}"
    
    # @tool
    def run_command_stream(self, q):
        """ Run a Bash command """
        # Start the process
        process = subprocess.Popen(
            q,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # line-buffered
        )

        # Yield lines as they appear
        for line in process.stdout:
            result += line
            # yield line.rstrip()  # remove trailing newline if desired
        m1 = self.mem.upsert_entity(q, "command", labels=["Command"], properties={"shell": "bash", "priority": "high"})
        m2 = self.mem.add_session_memory(self.sess.id, q, "Command", {"topic": "bash command", "agent": "Vera"})
        self.mem.link(m1.id, m2.id, "Run")
        m3 = self.mem.add_session_memory(self.sess.id, result, "Command Result", {"topic": "bash output", "agent": "Vera"})
        self.mem.link(m1.id, m3.id, "Output")
        # self.mem.add_session_memory(self.sess.id, f"Executed command: {q}", "Command", {"topic": "bash"})
        # self.mem.add_session_memory(self.sess.id, f"Command Result: {result}", "Command", {"topic": "bash"})
        process.stdout.close()
        return_code = process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, q)
        return process.stdout


    # @tool
    def run_python(self, code: str) -> str:
        """Run arbitrary Python code and return its output. Ensure to use print statements to output results."""
        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()
        local_vars = {}

        try:
            try:
                result = eval(code, globals(), local_vars)
                if result is not None:
                    print(result)
            except SyntaxError:
                exec(code, globals(), local_vars)

            output = redirected_output.getvalue()
            m1 = self.mem.upsert_entity(code, "python", labels=["Python"], properties={"shell": "python", "priority": "high"})
            m2 = self.mem.add_session_memory(self.sess.id, code, "Python", {"topic": "bash command", "agent": "Vera"})
            self.mem.link(m1.id, m2.id, "Create")
            m3 = self.mem.add_session_memory(self.sess.id, result, "Result", {"topic": "python output", "agent": "Vera"})
            self.mem.link(m1.id, m3.id, "Output")
            return output.strip() or "[No output]"

        except Exception:
            return f"[Error]\n{traceback.format_exc()}"

        finally:
            sys.stdout = old_stdout
        
    # @tool
    def duckduckgo_search(self, query: str, max_results: int = 10) -> str:
        """Search the web using DuckDuckGo and return the top results as a string of titles, urls, and short descriptions. Further processing may be required to extract useful information."""
        print(query)
        query_encoded = quote_plus(query)
        print(query_encoded)
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, region="us-en", max_results=max_results)
                search = self.mem.add_session_memory(self.sess.id, query, "web_search", metadata={"author":"duck duck go search"})
                output = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "")
                    href = r.get("href", "")
                    body = r.get("body", "")
                    search_result = self.mem.upsert_entity(href,f"search_result",properties={"title:":title,"body:":body}, labels=["Search_result"])
                    self.mem.link(search.id,search_result.id,"RESULT")
                    output.append(f"{idx}. {title}\n{href}\n{body}\n")
                return "\n".join(output) if output else "No results found."
        except Exception as e:
            return f"[DuckDuckGo Search Error] {e}"

    def duckduckgo_search_news(self, query, max_results=10):
        """Search for news articles using DuckDuckGo and return the top results."""
        query_encoded = quote_plus(query)
        try:
            with DDGS() as ddgs:
                results = ddgs.news(query, region="us-en", max_results=max_results)
                search = self.mem.add_session_memory(self.sess.id, query, "news_search", metadata={"author": "duck duck go news"})
                output = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "")
                    href = r.get("url", "")
                    body = r.get("body", "")
                    search_result = self.mem.upsert_entity(href, "news_result", properties={"title": title, "body": body}, labels=["Search_result"])
                    self.mem.link(search.id, search_result.id, "RESULT")
                    output.append(f"{idx}. {title}\n{href}\n{body}\n")
                return "\n".join(output) if output else "No news articles found."
        except Exception as e:
            return f"[DuckDuckGo News Search Error] {e}"
        
    def load_tools(self):
        return [
            Tool( 
            name="Query Fast LLM",
            func=self.fast_llm_func,
            description="capable of creative writing, reviewing text, summarizing, combining text, improving text. Fast but can be inaccurate"
            #"Given a query and context, reviews or summarizes the response for clarity and brevity. Acts as a quick reviewer, extractor, transformer or summarizer, not a solution provider."
           ),
            Tool( 
            name="Query Deep LLM",
            func=self.deep_llm_func,
            description="capable of creative writing, reviewing text, summarizing, combining text, improving text. slow and accurate"
            #"Given a query and context, reviews, improves or summarizes the response. Acts as a detailed reviewer, extractor, transformer  or summarizer, not a solution provider."
            ),
            Tool(
            name="Bash Shell",
            func=lambda q: subprocess.check_output(q, shell=True, text=True, stderr=__import__('subprocess').STDOUT), # REMOVE inline import
            # func=self.run_command_stream,
            description="Execute a bash shell command or script, and return its output."
            ),
            Tool(
            name="Run Python Code",
            func=self.run_python,
            description="Execute a Python code snippet."
            ),
            Tool(
            name="Read File",
            func=self.read_file_tool,
            description="Read the contents of a file. Provide the full path to the file."
            ),
            Tool(
            name="Write File",
            func=self.write_file_tool,
            description="Given a filepath and content, saves content to a file. Input format: filepath, followed by '|||' delimiter, then the file content. Example input: /path/to/file.txt|||This is the file content. Do NOT use newlines as delimiter."
            ),
            Tool(
            name="List Python Modules",
            func=lambda q: sorted(list(sys.modules.keys())),
            description="List all currently loaded Python modules."
            ),
            Tool(
                name="List Installed Programs",
                func=lambda q: subprocess.check_output(
                    "wmic product get name" if sys.platform == "win32" else "dpkg --get-selections" if sys.platform.startswith("linux") else "brew list",
                    shell=True,
                    text=True,
                    stderr=subprocess.STDOUT
                ),
                description="List all installed programs on this system."
            ),
            # Tool(
            #     name="Review Output",
            #     func=lambda q: self.review_output(q.get("query", ""), q.get("response", "")) if isinstance(q, dict) and "query" in q and "response" in q else "Input must be a dict with 'query' and 'response' keys.",
            #     description="Review an output given the original query and response. Input should be a dict: {'query': <query>, 'response': <response>}."
            # ),
            Tool(
                name="Search Memory",
                func=lambda q: "\n".join(
                    [doc.page_content for doc in self.vectorstore.similarity_search(q, k=5)]
                ),
                description="Searches long-term memory for relevant information given a query."
            ),
            Tool(
                name="DuckDuckGo Web Search",
                func=self.duckduckgo_search,
                description="Search the web using DuckDuckGo and return the top results."
            ),
            Tool(
                name="DuckDuckGo News Search",
                func=self.duckduckgo_search_news,
                description="Searches the web for news using DuckDuckGo."
            ),
            Tool(
                name="inspect system source code",
                func=lambda q: self.read_own_source(),
                description="Allows you to peer at your own code. helpful for understanding your own inner workings. not used for most tasks."
            ),
            Tool(
            name="Scheduling Assistant",
            func=self.executive_instance.main,
            description="Run the executive scheduling assistant with a query. It has access to the users calendars todo lists and scheduling apps, It can plan and execute scheduling and time management tasks, manage events, calendars, and more. Input should be a query string."
        )
        
            # UnrestrictedPythonTool
        ]

    # --- Streaming wrapper ---
    def stream_llm(self, llm, prompt):
        sys.stdout.write("\n")
        sys.stdout.flush()
        output = []
        for chunk in llm.stream(prompt):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            output.append(chunk)
            yield(chunk)
        print()  # final newline
        return "".join(output)
    
    import requests

    def stream_ollama_raw(model, prompt):
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True
        }
        with requests.post(url, json=payload, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    data = line.decode("utf-8")
                    print(data)  # raw JSON string

    
    # --- Streaming wrapper with memory injection ---
    def stream_llm_with_memory(self, llm, user_input, extra_context=None, long_term=True, short_term=True):
        # Retrieve relevant memory context
        past_context = ""
        relevant_history = ""
        if short_term:
            past_context = self.memory.load_memory_variables({"input": user_input}).get("chat_history", "")
           
        if long_term:
            relevant_history = self.vector_memory.load_memory_variables({"input": user_input})

        # hits = self.mem.focus_context(self.sess.id, user_input, top_k=5)

        # Combine past context + any extra agent reasoning
        full_prompt = f"Conversation so far:\n{str(past_context)}"
        full_prompt += f"Relevant conversation history{relevant_history}"

        print(f"Memory:\n\n{full_prompt}\n\n")

        if extra_context:
            full_prompt += f"\n\nExtra reasoning/context from another agent:\n{extra_context}"
        full_prompt += f"\n\nUser: {user_input}\nAssistant:"

        full_prompt += f"\n\nTools available via the agent system:{[tool.name for tool in self.tools]}\n"
        # print(full_prompt)
        sys.stdout.write("\n")
        sys.stdout.flush()
        output = []
        for chunk in llm.stream(full_prompt):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            output.append(chunk)
            yield(chunk)
        print()

        # Save both question and answer to shared memory
        ai_output = "".join(output)
        self.memory.save_context({"input": user_input}, {"output": ai_output})
        self.vectorstore.persist()
        self.focus_manager.update_latest_conversation(f"User Query: {user_input}")
        self.focus_manager.update_latest_conversation(f"Agent Response: {user_input}")
        self.mem.add_session_memory(self.sess.id, user_input, "Query", {"topic": "query"})
        self.mem.add_session_memory(self.sess.id, ai_output, "Response", {"topic": "response"})
        
        return ai_output

    # --- Save memory entry ---
    def save_to_memory(self, user_input, llm_output):
        """Save both user query and LLM reply to shared memory."""
        self.buffer_memory.chat_memory.add_user_message(user_input)
        self.buffer_memory.chat_memory.add_ai_message(llm_output)
        self.vector_memory.save_context({"input": user_input}, {"output": llm_output})
        self.vectorstore.persist()
        # self.mem.add_session_memory(self.sess.id, f"input: {user_input}\noutput: {llm_output}", "Thought", {"topic": "decision"}, promote=True)


    def execute_tool_chain(self, query):
        """Plan and execute multiple tools in sequence, replacing inputs based on previous outputs."""

        planning_prompt = f"""
            You are a planning assistant.
            Available tools: {[(tool.name, tool.description) for tool in self.tools]}.
            The query is: {query}

            Plan a sequence of tool calls to solve the request.

            Rules for planning:
            - If a tool's input depends on the output data of a previous tool, write "{{prev}}" as the placeholder for that data.
            - DO NOT try to guess values that depend on previous outputs.
            - Use the exact tool names provided above.

            Respond ONLY in this pure JSON format:
            [
            {{ "tool": "<tool name>", "input": "<tool input or '{{prev}}'>" }},
            {{ "tool": "<tool name>", "input": "<tool input or '{{prev}}'>" }}
            ]
            """
        plan_json=""
        # Get the plan from the LLM and clean up any leading/trailing ```json or ```
        for r in self.stream_llm(self.deep_llm, planning_prompt):
            # print(r)
            yield(r)
            plan_json += r

        print(f"\n[ Planning Agent ]\nPlan: {plan_json}")

        for prefix in ("```json", "```"):
            if plan_json.startswith(prefix):
                plan_json = plan_json[len(prefix):].strip()
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3].strip()

        try:
            tool_plan = json.loads(plan_json)
        except Exception as e:
            print(f"Failed to parse tool plan JSON: {e}")
            return f"Planning failed: {e} \n\n{plan_json}"

        tool_outputs = {}
        prev_output = None

        for step in tool_plan:
            print(f"Executing step: {step}")
            yield(f"Executing step: {step}")
            tool_name = step.get("tool")
            tool_input = step.get("input", "")
            tool_input = tool_input.replace("{prev}", str(prev_output if prev_output is not None else ""))
            print(f"{tool_name} input: {tool_input}")
            yield((f"{tool_name} input: {tool_input}"))
            # Find tool
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if not tool:
                tool_outputs[tool_name] = f"Tool not found: {tool_name}"
                prev_output = None
                continue

            try:
                if hasattr(tool, "run") and callable(tool.run):
                    func = tool.run
                elif hasattr(tool, "func") and callable(tool.func):
                    func = tool.func
                elif callable(tool):
                    func = tool
                else:
                    raise ValueError(f"Tool is not callable")

                collected = []
                result=""
                try:
                    for r in func(tool_input):
                        # print(f"Step result: {r}")
                        yield r
                        collected.append(r)
                except TypeError:
                    # Not iterable — call again and yield single result
                    result = func(tool_input)
                    # print(f"Step result: {result}")
                    yield result
                else:
                    # You can combine collected results here if needed:
                    result = "".join(str(c) for c in collected)
                    yield result
                # store result or return if you want
                # tool_outputs[tool_name] = result
                prev_output = result
                tool_outputs[tool_name] = result
                self.save_to_memory(query, tool_outputs[tool_name])

            except Exception as e:
                tool_outputs[tool_name] = f"Error executing {tool_name}: {e}"
                prev_output = None
                print(tool_outputs)
            
            
        
                

        # Merge results into a final answer
        merge_prompt = f"""
            The query was: {query}
            The following tools were executed with their outputs:
            {tool_outputs}

            Create a final answer that combines all the results.
            """
        final_answer = self.deep_llm.invoke(merge_prompt)
        return final_answer

    # --- Run with feedback ---
    def run_with_feedback(self, agent_fn, query):
        """Run an agent function with feedback loop where the reviewer can accept or reject the output."""
        # First attempt
        response = agent_fn(query)
        
        # Review
        review_result = self.review_output(query, response)
        if review_result.startswith("NO"):
            feedback = review_result[4:].strip()
            print(f"\n[ Reviewer ] Feedback: {feedback}")
            # Retry with feedback
            retry_prompt = f"{query}\n\nThe reviewer says: {feedback}\nPlease improve your answer."
            response = agent_fn(retry_prompt)
        
        return response

    # --- Coordinator ---
    def run(self, query):
        self.mem.add_session_memory(self.sess.id, f"{query}", "Query", {"topic": "query"})
        # Quick triage with Fast Agent (streamed)
        print("\n[ Triage Agent ]\n")
        triage_prompt =""
        fast_response=""
        deep_response=""
        reasoning_response=""
        tool_chain_response=""
        tool_response=""
        # if self.triage_memory is True: triage_prompt += (f"Given the conversation so far: {self.buffer_memory.load_memory_variables({})['chat_history']}\n")
        # if self.long_term_triage is True: triage_prompt += (f"Given the conversation so far: {self.buffer_memory.load_memory_variables({})['chat_history']}\n")
        triage_prompt += (
                    f"""
                    Classify this Query into one of the following categories:
                        - 'focus'      → Change the focus of background thought.
                        - 'proactive'  → Trigger proactive thinking.
                        - 'simple'     → Simple textual response.
                        - 'tool'       → Requires execution of a single tool.
                        - 'toolchain'  → Requires a series of tools or step-by-step planning and execution.
                        - 'reasoning'  → Requires deep reasoning.
                        - 'complex'    → Complex written response with high-quality output.
                        - 'scheduling' → Requires scheduling or time management tasks.

                    Current focus: {self.focus_manager.focus}  
                    If you detect a change in focus or topic, you may specify new focus terms by appending the output with the.

                    Available tools: {', '.join(t.name for t in self.tools)}

                    Query: {query}

                    Rules:
                    - If 'simple' is the chosen category, disregard these rules and answer the Query using as many words as you like.
                    - Respond with a single classification term (e.g., 'simple', 'tool', 'complex') on the first line, then any optional extra info.
                    - You may optionally append focus terms.
                    - If setting a 'focus', also specify the focus term to set (e.g., "focus project management").
                    - Do NOT provide reasoning in your output nor formatting not mentioned in this prompt.
                    """
        )
        for r in self.stream_llm(self.fast_llm, triage_prompt):
            fast_response += r
        self.mem.add_session_memory(self.sess.id, f"{fast_response}", "Triage", {"topic": "fast"})
        
        if "focus" in fast_response.lower():
            # If the query is about focus, use the proactive focus manager
            print("\n[ Proactive Focus Manager ]\n")
            self.focus_manager.set_focus(fast_response.lower().split("focus", 1)[-1].strip())
            # proactive_response = self.focus_manager.relate_to_focus(query, fast_response)
            # self.save_to_memory(query, proactive_response)
            # return {"fast": fast_response}
        
        # Decide routing
        if "complex" in fast_response.lower():
            print("\n[ Deep Agent ]\n")
            for r in self.stream_llm_with_memory(self.deep_llm, query, extra_context=fast_response):
                deep_response += r
            self.save_to_memory(query, deep_response) # Save to legacy memory
            return {"fast": fast_response, "deep": deep_response}
        
        elif "reasoning" in fast_response.lower():
            print("\n[ Reasoning Agent ]\n")
            for r in self.stream_llm_with_memory(self.reasoning_llm, query, extra_context=fast_response):
                reasoning_response += r
            self.save_to_memory(query, reasoning_response) # Save to legacy memory
            return {"fast": fast_response, "reasoning": reasoning_response}
        
        elif "toolchain" in fast_response.lower():
            print("\n[ Tool Chain Agent ]\n")
            for r in self.toolchain.execute_tool_chain(query):
                tool_chain_response += str(r)
            self.save_to_memory(query, tool_chain_response)
            self.mem.add_session_memory(self.sess.id, f"{tool_chain_response}", "Response", {"topic": "toolchain"}, promote=True)
            return {"fast": fast_response, "toolchain": tool_chain_response}
                
        elif "tool" in fast_response.lower():
            print("\n[ Tool Agent ]\n")

            tool_response = self.light_agent.invoke(query)         
            
            # Save both the user query and the full tool agent output (including intermediate steps if available)

            if hasattr(self.light_agent, "agent_executor") and hasattr(self.light_agent.agent_executor, "intermediate_steps"):
                # If intermediate steps are available, save them as well
                intermediate_steps = self.light_agent.agent_executor.intermediate_steps
                self.save_to_memory(query, {"output": tool_response['output'], "intermediate_steps": tool_response['intermediate_steps']})
                return {"fast": fast_response, "tool": tool_response['output']}
            else:
                self.save_to_memory(query, tool_response)
                self.mem.add_session_memory(self.sess.id, f"{tool_response}", "Response", {"topic": "tool"}, promote=True)
            return {"fast": fast_response, "tool": tool_response}

        elif "proactive" in fast_response.lower():
            # If the query is about proactive thinking, use the proactive focus manager
            print("\n[ Proactive Focus Manager ]\n")
            proactive_thought = self.focus_manager._generate_proactive_thought()
            if proactive_thought:
                self.focus_manager.add_to_focus_board("actions", proactive_thought)
                self.save_to_memory(query, proactive_thought)
                self.mem.add_session_memory(self.sess.id, f"{proactive_thought}", "Thought", {"topic": "proactive"}, promote=True)
                return {"fast": fast_response, "proactive": proactive_thought}
            else:
                return {"fast": fast_response, "proactive": "No proactive thought generated."}
        
        elif "scheduling" in fast_response.lower():
            print("\n[ Scheduling Assistant ]\n")
            scheduling_response = self.executive_instance.main(query)
            self.save_to_memory(query, scheduling_response)
            self.mem.add_session_memory(self.sess.id, f"{scheduling_response}", "Response", {"topic": "scheduling"}, promote=True)
            return {"fast": fast_response, "scheduling": scheduling_response}
        
        else:
        #     # Simple case, just fast agent again
        #     final_fast_response = self.stream_llm_with_memory(self.fast_llm, query, extra_context=fast_response)
        #     self.save_to_memory(query, final_fast_response)
        #     return {"fast": final_fast_response}
            self.save_to_memory(query, fast_response)
            return {"fast": fast_response}
        
        
    def async_run(self, query):
        self.mem.add_session_memory(self.sess.id, f"{query}", "Query", {"topic": "plan"}, promote=True)
        # 1. Stream triage prompt output chunk-by-chunk
        triage_prompt = (
            f"""
            Classify this Query into one of the following categories:
                - 'focus'      → Change the focus of background thought.
                - 'proactive'  → Trigger proactive thinking.
                - 'simple'     → Simple textual response.
                - 'tool'       → Requires execution of a single tool.
                - 'toolchain'  → Requires a series of tools or step-by-step planning and execution.
                - 'reasoning'  → Requires deep reasoning.
                - 'complex'    → Complex written response with high-quality output.

            Current focus: {self.focus_manager.focus}  
            If you detect a change in focus or topic, you may specify new focus terms by appending the output with the.

            Available tools: {', '.join(t.name for t in self.tools)}

            Query: {query}

            Rules:
            - If 'simple' is the chosen category, disregard these rules and answer the Query using as many words as you like.
            - Respond with a single classification term (e.g., 'simple', 'tool', 'complex') on the first line, then any optional extra info.
            - You may optionally append focus terms.
            - If setting a 'focus', also specify the focus term to set (e.g., "focus project management").
            - Do NOT provide reasoning in your output nor formatting not mentioned in this prompt.
            """
        )

        # Assume self.stream_llm returns a generator (or wrap to async generator)
        full_triage=""
        for triage_chunk in self.stream_llm(self.fast_llm, triage_prompt):
            # print(triage_chunk)
            full_triage+=triage_chunk
            yield triage_chunk
        self.mem.add_session_memory(self.sess.id, f"{full_triage}", "Response", {"topic": "triage"}, promote=True)
        total_response = full_triage
        triage_lower = full_triage.lower()
        total_response = ""
        fast_response = ""
        deep_response = ""
        reason_response = ""
        tool_response = ""
        toolchain_response = ""
        
        if "focus" in triage_lower:
            # If the query is about focus, use the proactive focus manager
            print("\n[ Proactive Focus Manager ]\n")
            self.focus_manager.set_focus(full_triage.lower().split("focus", 1)[-1].strip())
            
        # 2. Branch logic based on triage
        if "simple" in triage_lower:
            # stream deep llm output
            for fast_chunk in self.stream_llm(self.fast_llm, query): #, extra_context=triage_lower):
                fast_response += fast_chunk
                yield  fast_chunk
            self.mem.add_session_memory(self.sess.id, f"{fast_response}", "Query", {"topic": "query"}) #"model":self.fast_llm})
            total_response += fast_response
        if "complex" in triage_lower:
            # stream deep llm output
            for deep_chunk in self.stream_llm(self.deep_llm, query): #, extra_context=triage_lower):
                deep_response += deep_chunk
                yield  deep_chunk
            self.mem.add_session_memory(self.sess.id, f"{deep_response}", "Query", {"topic": "query"}) #"model":self.deep_llm})
            total_response += deep_response
        elif "reasoning" in triage_lower:
            for reason_chunk in self.stream_llm(self.reasoning_llm, query): #, extra_context=triage_lower):
                reason_response += reason_chunk
                yield reason_chunk
            self.mem.add_session_memory(self.sess.id, f"{reason_response}", "Query", {"topic": "query"})
            total_response += reason_response
        elif "toolchain" in triage_lower:
            print("\n[ Tool Chain Agent ]\n")
            # return {"fast": fast_response, "toolchain": tool_chain_response}
            for toolchain_chunk in self.toolchain.execute_tool_chain(query):
                toolchain_response += str(toolchain_chunk)
                yield toolchain_chunk
            self.mem.add_session_memory(self.sess.id, f"{toolchain_response}", "Query", {"topic": "query"})
            total_response += toolchain_response    
            # self.save_to_memory(query, tool_chain_response)
        elif "tool" in triage_lower:
            for tool_chunk in self.light_agent.invoke(query):
                tool_response += str(tool_chunk)
                yield tool_chunk
            yield tool_response
            self.mem.add_session_memory(self.sess.id, f"{tool_response}", "Query", {"topic": "query"})
            total_response += tool_response      

        else:
            pass
        
        self.save_to_memory(query, total_response)
        self.mem.add_session_memory(self.sess.id, f"{total_response}", "Response", {"topic": "query"})
            


    def print_llm_models(self):
        """Print the variable name and model name for each Ollama LLM."""
        for attr_name, attr_value in vars(self).items():
            if isinstance(attr_value, Ollama):
                print(f"{attr_name} -> {attr_value.model}")
        
    def print_agents(self):
        """Recursively find and print all LLM models and agents inside Vera."""
        visited = set()

        def inspect_obj(obj, path="self"):
            if id(obj) in visited:
                return
            visited.add(id(obj))

            # Check if this is an agent
            if hasattr(obj, "llm") and hasattr(obj.llm, "model"):
                agent_type = getattr(obj, "agent", None)
                model_name = getattr(obj.llm, "model", "Unknown")
                print(f"{path} -> Model: {model_name}, Agent Type: {agent_type}")

            # # Check if this is a bare LLM
            # elif hasattr(obj, "model") and isinstance(getattr(obj, "model"), str):
            #     print(f"{path} -> Model: {obj.model}")

            # Recurse into attributes
            if hasattr(obj, "__dict__"):
                for attr_name, attr_value in vars(obj).items():
                    inspect_obj(attr_value, f"{path}.{attr_name}")

        inspect_obj(self)

    

class ToolChainPlanner:
    def __init__(self, agent, tools):
        self.agent = agent
        self.deep_llm = self.agent.deep_llm
        self.tools = self.agent.tools
        self.history = self.agent.buffer_memory.load_memory_variables({})['chat_history']

    def plan_tool_chain(self, query: str, history_context: str = "") -> List[Dict[str, str]]:
        """Generate a plan from the LLM."""
        planning_prompt = f"""
            You are a planning assistant.
            Available tools: {[(tool.name, tool.description) for tool in self.tools]}.
            The query is: {query}

            Previous attempts and their outputs:\n{history_context if history_context else ""}

            Plan a sequence of tool calls to solve the request.

            Rules for planning:
            - You can reference ANY previous step output using {{step_1}}, {{step_2}}, etc.
            - You can still use {{prev}} to mean the last step's output.
            - DO NOT guess values that depend on previous outputs.
            - Use the exact tool names provided above.

            Respond ONLY in this pure JSON format, no markdown:
            [
            {{ "tool": "<tool name>", "input": "<tool input or '{{step_1}}'>" }},
            {{ "tool": "<tool name>", "input": "<tool input or '{{prev}}'>" }}
            ]
        """
        # plan_json = self.agent.stream_llm_with_memory(self.agent.deep_llm, planning_prompt)
        plan_json=""
        # Get the plan from the LLM and clean up any leading/trailing ```json or ```
        for r in self.agent.stream_llm(self.deep_llm, planning_prompt):
            # print(r)
            yield(r)
            plan_json += r

        # Clean formatting
        for prefix in ("```json", "```"):
            if plan_json.startswith(prefix):
                plan_json = plan_json[len(prefix):].strip()
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3].strip()

        try:
            tool_plan = json.loads(plan_json)
        except Exception as e:
            raise ValueError(f"Planning failed: {e} \n\n{plan_json}")
        print("DEBUG:", type(tool_plan), tool_plan)
        # Save plan for replay
        with open("./Configuration/last_tool_plan.json", "w", encoding="utf-8") as f:
            f.write(plan_json)

        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        elif isinstance(tool_plan, list):
            if not all(isinstance(s, dict) for s in tool_plan):
                raise ValueError(f"Unexpected tool plan format: {tool_plan}")
        else:
            raise ValueError(f"Unexpected tool plan type: {type(tool_plan)}")
        self.agent.mem.add_session_memory(self.agent.sess.id, f"{json.dumps(tool_plan)}", "Plan", {"topic": "plan"}, promote=True)
        yield tool_plan

    def execute_tool_chain(self, query: str) -> str:
        """Execute a tool chain, allowing reference to any step output."""
        try:
            gen = self.plan_tool_chain(query)
            for r in gen:
                yield r
                tool_plan = r
        except StopIteration as e:
            print(f"[ Toolchain Agent ]\nTool Plan: {json.dumps(e.value, indent=2)}")
            tool_plan = e.value
        except Exception as e:
            print(f"[ Toolchain Agent ] Error planning tool chain: {e}")
        print(f"[ Toolchain Agent ]\nTool Plan: {json.dumps(tool_plan, indent=2)}")
        # tool_plan = self.plan_tool_chain(query)
        tool_outputs = {}
        step_num = 0
        errors_detected = False

        for step in tool_plan:
            step_num += 1
            tool_name = step.get("tool")
            tool_input = str(step.get("input", ""))
            # yield(f"\nExecuting step: {step}\n{tool_name} input: {tool_input}"))
            # Resolve placeholders like {prev} or {step_2}
            if "{prev}" in tool_input:
                tool_input = tool_input.replace("{prev}", str(tool_outputs.get(f"step_{step_num-1}", "")))
            for i in range(1, step_num):
                tool_input = tool_input.replace(f"{{step_{i}}}", str(tool_outputs.get(f"step_{i}", "")))

            # Inject memory for LLM tools
            if "llm" in tool_name:
                tool_input = f"Context: {self.agent.buffer_memory.load_memory_variables({})['chat_history']}\n" + tool_input

            print(f"[ Toolchain Agent ] Step {step_num} - Executing Tool: {tool_name}, Input: {tool_input}")
            yield(f"[ Toolchain Agent ] Step {step_num} - Executing Tool: {tool_name}, Input: {tool_input}")
            tool = next((t for t in self.tools if t.name == tool_name), None)

            if not tool:
                result = f"Tool not found: {tool_name}"
                errors_detected = True
            else:
                try:
                    if hasattr(tool, "run") and callable(tool.run):
                        func = tool.run
                    elif hasattr(tool, "func") and callable(tool.func):
                        func = tool.func
                    elif callable(tool):
                        func = tool
                    else:
                        raise ValueError(f"Tool is not callable")

                    collected = []
                    result=""
                    try:
                        for r in func(tool_input):
                            # print(f"Step result: {r}")
                            yield r
                            collected.append(r)
                    except TypeError:
                        # Not iterable — call again and yield single result
                        result = func(tool_input)
                        # print(f"Step result: {result}")
                        yield result
                    else:
                        # Combine collected results here if needed:
                        result = "".join(str(c) for c in collected)
                        self.agent.mem.add_session_memory(self.agent.sess.id, f"Step {step_num} - {tool_name}\n{result}", "Step", {"topic": "step","author": "toolchain", "step": step_num, "tool": tool_name})
                        yield result
                    # store result or return if you want
                    # tool_outputs[tool_name] = result
                    prev_output = result
                    tool_outputs[tool_name] = result
                    # self.save_to_memory(query, tool_outputs[tool_name])
                except Exception as e:
                    tool_outputs[tool_name] = f"Error executing {tool_name}: {e}"
                    prev_output = None
                    print(tool_outputs)
            
                # try:
                #     if hasattr(tool, "run") and callable(tool.run):
                #         result = tool.run(tool_input)
                #     elif hasattr(tool, "func") and callable(tool.func):
                #         result = tool.func(tool_input)
                #     elif callable(tool):
                #         result = tool(tool_input)
                #     else:
                #         raise ValueError(f"Tool {tool_name} is not callable.")
                # except Exception as e:
                #     result = f"Error executing {tool_name}: {str(e)}"
                #     errors_detected = True

                print(f"Step {step_num} result: {result}")
                yield(f"Step {step_num} result: {result}")
                tool_outputs[f"step_{step_num}"] = result
                self.agent.save_to_memory(f"Step {step_num} - {tool_name}", result)
                # try:
                #     self.agent.mem.add_session_memory(self.agent.sess.id, f"Step {step_num} - {tool_name}: {result}", "Step", {"topic": "toolchain"})
                # except:
                #     pass

        # If error detected → re-plan recovery step
        if errors_detected:
            print("[ Toolchain Agent ] Errors detected, replanning recovery steps...")
            recovery_plan = self.plan_tool_chain(
                f"Recover from the errors and complete the query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            tool_plan.extend(recovery_plan)
            return self.execute_tool_chain(query)  # re-run with recovery

        # Final goal check
        review_prompt = f"""
            The query was: {query}
            Execution results: {json.dumps(tool_outputs, indent=2)}

            Does the final result meet the goal? 
            Answer only 'yes' or 'no' and explain briefly.
        """
        review = self.deep_llm.invoke(review_prompt)
        if "no" in review.lower():
            print("[ Toolchain Agent ] Goal not achieved, replanning...")
            yield("[ Toolchain Agent ] Goal not achieved, replanning...")
            retry_plan = self.plan_tool_chain(
                f"Retry the task ensuring the goal is met. Original query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            return self.execute_tool_chain(query)

        return tool_outputs.get(f"step_{step_num}", "")

    def report_history(self) -> str:
        """Generate a report of all tool chains run so far."""
        report_prompt = f"""
            You are a summarization assistant.
            Here is the short-term memory of all executed tool chains:

            {json.dumps(self.history, indent=2)}

            Please produce a clear and concise report that summarizes:
            - Each query and the plan used
            - Key results
            - Any patterns or common findings
        """
        return self.deep_llm.invoke(report_prompt)

class ProactiveFocusManager:
    """
    TODO
    Add calendar visibility
    """
    def __init__(
        self,
        agent,
        proactive_interval: int = 60*10,  # seconds between proactive thoughts
        cpu_threshold: float = 30.0,    # max CPU percent usage allowed for proactive thinking
    ):
        self.agent = agent
        self.focus: Optional[str] = None
        self.focus_board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": []
        }
        self.proactive_interval = proactive_interval
        self.cpu_threshold = cpu_threshold
        self.running = False
        self.thread = None
        self.latest_conversation = ""  # Current conversation/context to steer thoughts
        self.proactive_callback: Optional[Callable[[str], None]] = None  # Optional callback on new proactive thought
        self.max_ollama_processes = 24
        self.pause_event = threading.Event()  # Pauses proactive thinking


    def set_focus(self, focus: str):
        self.focus = focus
        print(f"[FocusManager] Focus set to: {focus}")
        self.agent.mem.add_session_memory(self.agent.sess.id, f"[FocusManager] Focus set to: {focus}", "Thought", {"topic": "focus"})
        # self.start()

    def clear_focus(self):
        self.focus = None
        self.stop()
        print("[FocusManager] Focus cleared")

    def add_to_focus_board(self, category: str, note: str):
        if category in self.focus_board:
            self.focus_board[category].append(note)
        else:
            self.focus_board[category] = [note]

    def update_latest_conversation(self, conversation: str):
        self.latest_conversation = conversation

    def start(self):
        if not self.running and self.focus:
            self.running = True
            self.thread = threading.Thread(target=self._run_proactive_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None

    def _count_ollama_processes(self):
        count = 0
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                if "ollama" in proc.info["name"].lower():
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count

    def _run_proactive_loop(self):
        print("[FocusManager] Proactive loop started")
        while self.running:
            ollama_count = self._count_ollama_processes()
            if ollama_count >= self.max_ollama_processes:
                print(f"[FocusManager] High Ollama demand ({ollama_count} processes) — pausing proactive thinking...")
                self.pause_event.clear()
                while self.running and self._count_ollama_processes() > self.max_ollama_processes:
                    time.sleep(2)
                print("[FocusManager] Ollama demand dropped — resuming proactive thinking...")
                self.pause_event.set()

            self.pause_event.wait()

            proactive_thought = self._generate_proactive_thought()
            
            if proactive_thought:
                if self.proactive_callback:
                    self.proactive_callback(proactive_thought)
                self.add_to_focus_board("actions", proactive_thought)
                # print(f"[FocusManager] Proactive action/thought: {proactive_thought}")
                evaluation_prompt = (
                    f"Evaluate this proactive thought: {proactive_thought}\n"
                    f"Is it actionable given the tools available and relevant to the current focus?"
                    f"The tools available are: {[tool.name for tool in self.agent.tools]}\n"
                    f"The focus is: {self.focus}\n"
                    f"If so, respond with 'YES'. If not, provide a brief reason."
                )
                evaluation = self.agent.fast_llm.invoke(evaluation_prompt)
                if evaluation.strip().lower() == "yes":
                    self.execute_goal_with_vera(proactive_thought)


            time.sleep(self.proactive_interval)

    def _generate_proactive_thought(self) -> Optional[str]:
        print("[FocusManager] Generating proactive thought...")
        if not self.focus:
            return None
        # Compose prompt leveraging focus + latest conversation for actionable advice
        prompt = (
            f"You are assisting with the project: {self.focus}.\n"
            f"Based on this recent conversation/context:\n{self.latest_conversation}\n"
            f"Considering the focus board:\n{self.focus_board}\n"
            f"Suggest the most valuable immediate action or next step to advance the project. "
            f"Focus on concrete, practical actions or investigations."
        )
        try:
            # Use the deep agent (or intermediate) for better reasoning
            # Use streaming disabled here; you want the full response before acting
            response = self.agent.deep_llm.predict(prompt)
            return response.strip()
        except Exception as e:
            print(f"[FocusManager] Error generating proactive thought: {e}")
            return None
            
    def execute_goal_with_vera(self, goal: str):
        """Instruct Vera to achieve the goal using tools if needed and log results."""
        try:
            print(f"[FocusManager] Sending goal to Vera: {goal}")

            for r in self.toolchain.execute_tool_chain(f"Goal: {goal}\n\nFocus: {self.focus}\n\nStatus: {self.focus_board}"):
                tool_chain_response += str(r)

            # Superseded
            # result = self.agent.execute_tool_chain (
            #     f"Goal: {goal}\n\nFocus: {self.focus}\n\nStatus: {self.focus_board}"
            # )

            # Store results in focus board
            if result:
                self.add_to_focus_board("progress", f"Executed goal: {goal}")
                self.add_to_focus_board("progress", f"Result: {result}")

                # If result contains substeps or breakdown, categorize accordingly
                if isinstance(result, dict):
                    if "next_steps" in result:
                        for step in result["next_steps"]:
                            self.add_to_focus_board("next_steps", step)
                    if "issues" in result:
                        for issue in result["issues"]:
                            self.add_to_focus_board("issues", issue)
                    if "ideas" in result:
                        for idea in result["ideas"]:
                            self.add_to_focus_board("ideas", idea)

                print(f"[FocusManager] Logged results to focus board.")

        except Exception as e:
            print(f"[FocusManager] Failed to execute goal with Vera: {e}")
            self.add_to_focus_board("issues", f"Execution failed for '{goal}': {e}")

    def relate_to_focus(self, user_input: str, response: str) -> str:
        # Optionally, can connect any response back to focus by appending a reminder or summary
        if not self.focus:
            return response
        return f"{response}\n\n[Reminder: Current project focus is '{self.focus}']"


def get_active_ollama_threads():
    """Return active Ollama threads with non-zero CPU usage."""
    active_threads = []
    total_cpu = 0.0

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            if "ollama" in (proc.info["name"] or "").lower() or any("ollama" in (part or "").lower() for part in proc.info["cmdline"] or []):
                for thread in proc.threads():
                    thread_cpu = proc.cpu_percent(interval=0.1) / proc.num_threads() if proc.num_threads() else 0
                    if thread_cpu > 0:  # Thread is actively using CPU
                        active_threads.append({
                            "pid": proc.pid,
                            "tid": thread.id,
                            "cpu": thread_cpu
                        })
                        total_cpu += thread_cpu
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print("Active Ollama Threads")
    print("---------------------")
    for t in active_threads:
        print(f"PID: {t['pid']}, TID: {t['tid']}, CPU: {t['cpu']:.2f}%")
    print("---------------------")
    print(f"Total active threads: {len(active_threads)} | Total active CPU: {total_cpu:.2f}%")

    return active_threads

def get_ollama_cpu_load_and_count():
    """Calculate total CPU load and count of threads for all Ollama models in Vera."""
    total_cpu = 0.0
    total_threads = 0
    model_processes = {}

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline", "cpu_percent", "num_threads"]):
        try:
            name = proc.info["name"] or ""
            cmdline = proc.info["cmdline"] or []
            cpu = proc.info["cpu_percent"]
            threads = proc.info["num_threads"]

            # Look for 'ollama' process
            if "ollama" in name.lower() or any("ollama" in part.lower() for part in cmdline):
                total_cpu += cpu
                total_threads += threads

                # Try to guess the model name from cmdline
                model_name = None
                for part in cmdline:
                    if re.match(r"^[a-zA-Z0-9_\-:]+$", part) and ":" in part:
                        model_name = part
                        break

                if not model_name:
                    model_name = "unknown"

                model_processes.setdefault(model_name, {"cpu": 0.0, "threads": 0})
                model_processes[model_name]["cpu"] += cpu
                model_processes[model_name]["threads"] += threads

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print("Ollama CPU Load Report")
    print("----------------------")
    for model, stats in model_processes.items():
        print(f"{model} -> CPU: {stats['cpu']:.2f}%, Threads: {stats['threads']}")
    print("----------------------")
    print(f"TOTAL -> CPU: {total_cpu:.2f}%, Threads: {total_threads}")


# --- Example usage ---
if __name__ == "__main__":
    
    vera = Vera()
    
    os.system("clear")
    vera.print_llm_models()
    vera.print_agents()
    # get_ollama_cpu_load_and_count()
    # get_active_ollama_threads()

    while True:
        user_query = input("\nEnter your query (or 'exit' to quit):\n\n ")
        if user_query.lower() in ["exit", "quit"]:
            break
        print("\nRunning agent...")
        
        if user_query.lower() == "/clear":
            vera.vectorstore.delete_collection("vera_agent_memory")
            vera.buffer_memory.clear()
            print("Memory cleared.")
        if user_query.lower() == "/test":
            print("Testing tool execution...")
            print(vera.execute_tool_chain("List all projects"))
            print(vera.execute_tool_chain("Add a new event to Google Calendar for tomorrow at 10 AM"))
        if user_query.lower() == "/run":
            print("Running a test query...")
            print(vera.run("What is the weather like today?"))
        # if user_query.lower() == "/replay":
        # if user_query.lower() == "/search":
        # if user_query.lower() == "/history":
        # if user_query.lower() == "/model": 
        # if user_query.lower() == "/focus":
        # if user_query.lower() == "/proactive":
            # proactive_thought = self.focus_manager._generate_proactive_thought()
            # if proactive_thought:
            #     self.focus_manager.add_to_focus_board("actions", proactive_thought)
            #     self.save_to_memory(query, proactive_thought)

            # else :
            #     result = vera.run(user_query)

        # print("\n[ Results ]")
        # print("Fast Response:", result.get("fast", "No fast response"))
        # print("Deep Response:", result.get("deep", "No deep response"))
        # print("Tool Response:", result.get("tool", "No tool response"))
        # print("\n---\n")
        result = vera.run(user_query)
        # get_ollama_cpu_load_and_count()
        print(result)

# ジョセフ