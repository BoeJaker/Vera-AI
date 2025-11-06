#!/usr/bin/env python3
# Vera.py - Vera

"""
Vera - AI System
Multi-agent system with proactive focus management and tool execution.
"""

# --- Imports ---
import sys, os, io
import subprocess
import json
from typing import List, Dict, Any, Type, Optional, Callable, Iterator, Union
import threading
import time
# import inspect
import psutil
import re
import traceback
import ollama
import requests
from collections.abc import Iterator
from urllib.parse import quote_plus, quote
import asyncio
from playwright.async_api import async_playwright
from langchain_core.outputs import GenerationChunk
from langchain.llms.base import LLM
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
from langchain.llms.base import LLM

# --- Local Imports ---
from Agents.executive_0_9 import executive
sys.path.append(os.path.join(os.path.dirname(__file__), 'Memory'))
from Memory.memory import *
from Toolchain.tools import ToolLoader
from Agents.reviewer import Reviewer
from Agents.planning import Planner
from proactive_focus_manager import ProactiveFocusManager
import hashlib

#---- Constants ---
MODEL_CONFIG_FILE = "Configuration/vera_models.json"

# --- Ollama Connection Manager ---
class OllamaConnectionManager:
    """Manages connection to Ollama API with local fallback"""
    
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        self.use_local = False
        self.connection_tested = False
        
    def test_connection(self) -> bool:
        """Test if Ollama API is accessible"""
        try:
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"[Ollama] Connected to API at {self.api_url}")
                self.use_local = False
                self.connection_tested = True
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"[Ollama] API connection failed: {e}")
        
        # Fallback to local
        print("[Ollama] Falling back to local Ollama process")
        self.use_local = True
        self.connection_tested = True
        return False
    
    def list_models(self) -> List[Dict]:
        """List available models from API or local"""
        if not self.connection_tested:
            self.test_connection()
        
        if not self.use_local:
            try:
                response = requests.get(f"{self.api_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models_data = response.json().get("models", [])
                    # API returns models in a different format, normalize it
                    return [{"model": m.get("name", m.get("model", ""))} for m in models_data]
            except Exception as e:
                print(f"[Ollama] API list failed, trying local: {e}")
                self.use_local = True
        
        # Use local ollama import
        try:
            return ollama.list()["models"]
        except Exception as e:
            raise RuntimeError(f"[Ollama] Both API and local connection failed: {e}")
    
    def pull_model(self, model_name: str) -> bool:
        """Pull/download a model from API or local"""
        if not self.connection_tested:
            self.test_connection()
        
        if not self.use_local:
            try:
                print(f"[Ollama] Pulling model {model_name} via API...")
                response = requests.post(
                    f"{self.api_url}/api/pull",
                    json={"name": model_name, "stream": False},
                    timeout=300
                )
                return response.status_code == 200
            except Exception as e:
                print(f"[Ollama] API pull failed, trying local: {e}")
                self.use_local = True
        
        # Use local ollama import
        try:
            ollama.pull(model_name)
            return True
        except Exception as e:
            print(f"[Ollama] Failed to pull model: {e}")
            return False
    
    def create_llm(self, model: str, temperature: float = 0.7, **kwargs):
        """Create an Ollama LLM instance with API or local configuration"""
        if not self.connection_tested:
            self.test_connection()
        
        if not self.use_local:
            # Use API mode
            print(f"[Ollama] Using API mode for model {model}")
            return OllamaAPIWrapper(
                model=model,
                temperature=temperature,
                api_url=self.api_url,
                **kwargs
            )
        else:
            # Use local Ollama
            print(f"[Ollama] Using local Ollama for model {model}")
            return Ollama(
                model=model,
                temperature=temperature,
                **kwargs
            )
    
    def create_embeddings(self, model: str, **kwargs):
        """Create an Ollama embeddings instance with API or local configuration"""
        if not self.connection_tested:
            self.test_connection()
        
        if not self.use_local:
            # Use API mode
            return OllamaEmbeddings(
                model=model,
                base_url=self.api_url,
                **kwargs
            )
        else:
            # Use local Ollama
            return OllamaEmbeddings(
                model=model,
                **kwargs
            )

# --- Ollama API Wrapper ---
class OllamaAPIWrapper(LLM):
    """Wrapper for Ollama API calls with fallback to local"""
    
    model: str
    temperature: float = 0.7
    api_url: str = "http://localhost:11434"
    
    @property
    def _llm_type(self) -> str:
        return "ollama_api"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> str:
        """Call Ollama API, fallback to local if it fails"""
        try:
            # Filter out non-serializable kwargs
            api_kwargs = {k: v for k, v in kwargs.items() 
                         if k not in ['run_manager', 'callbacks'] and 
                         isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            
            # Try API call
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": False,
                    **api_kwargs
                },
                timeout=2400
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                print(f"[Ollama API] Request failed with status {response.status_code}, falling back to local")
                return self._fallback_call(prompt, stop, run_manager, **kwargs)
                
        except Exception as e:
            print(f"[Ollama API] Error: {e}, falling back to local")
            return self._fallback_call(prompt, stop, run_manager, **kwargs)
    
    def _stream(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> Iterator[GenerationChunk]:
        """Stream responses from Ollama API, fallback to local if it fails"""
        try:
            # Filter out non-serializable kwargs
            api_kwargs = {k: v for k, v in kwargs.items() 
                         if k not in ['run_manager', 'callbacks'] and 
                         isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            
            # Try API streaming call
            print(f"[Ollama API] Starting stream request to {self.api_url}")
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": True,
                    **api_kwargs
                },
                stream=True,
                timeout=2400
            )
            
            if response.status_code == 200:
                print(f"[Ollama API] Stream connected, receiving data...")
                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        # print(f"[DEBUG] Line: {line.decode('utf-8')}", flush=True)
                        try:
                            json_response = json.loads(line)
                            if "response" in json_response:
                                chunk_text = json_response["response"]
                                if chunk_text:  # Only yield non-empty chunks
                                    chunk_count += 1
                                    # print(f"[DEBUG] Chunk {chunk_count}: '{chunk_text}'", flush=True)
                                    # Create a GenerationChunk object like LangChain expects
                                    chunk = GenerationChunk(text=chunk_text)
                                    if run_manager:
                                        run_manager.on_llm_new_token(chunk_text)
                                    yield chunk
                        except json.JSONDecodeError as e:
                            print(f"[Ollama API] JSON decode error: {e}")
                            continue
                print(f"[Ollama API] Stream completed, yielded {chunk_count} chunks")
            else:
                print(f"[Ollama API] Stream failed with status {response.status_code}, falling back to local")
                yield from self._fallback_stream(prompt, stop, run_manager, **kwargs)
                
        except Exception as e:
            print(f"[Ollama API] Stream error: {e}, falling back to local")
            traceback.print_exc()
            yield from self._fallback_stream(prompt, stop, run_manager, **kwargs)
    
    def _fallback_call(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> str:
        """Fallback to local Ollama"""
        fallback_llm = Ollama(model=self.model, temperature=self.temperature)
        print(f"[Ollama API] Using local fallback for model {self.model}")
        
        # Pass run_manager if available
        call_kwargs = kwargs.copy()
        if run_manager:
            call_kwargs['run_manager'] = run_manager
        
        return fallback_llm.invoke(prompt, stop=stop, **call_kwargs)
    
    def _fallback_stream(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs):
        """Fallback streaming to local Ollama"""
        fallback_llm = Ollama(model=self.model, temperature=self.temperature)
        print(f"[Ollama API] Using local streaming fallback for model {self.model}")
        print(f"[Ollama API] Starting local stream...")
        chunk_count = 0
        
        # Pass run_manager to the fallback if available
        stream_kwargs = kwargs.copy()
        if run_manager:
            stream_kwargs['run_manager'] = run_manager
        
        for chunk in fallback_llm.stream(prompt, stop=stop, **stream_kwargs):
            chunk_count += 1
            # LangChain's stream should return GenerationChunk objects
            # But handle both cases
            if isinstance(chunk, str):
                yield GenerationChunk(text=chunk)
            elif hasattr(chunk, 'text'):
                yield chunk
            elif hasattr(chunk, 'content'):
                yield GenerationChunk(text=chunk.content)
            else:
                yield GenerationChunk(text=str(chunk))
        print(f"\n[Ollama API] Local stream completed, yielded {chunk_count} chunks")
    
    async def _acall(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Async call - falls back to sync for now"""
        return self._call(prompt, stop, **kwargs)


# --- Model Selection ---
def choose_models_from_installed(ollama_manager: OllamaConnectionManager, MODEL_CONFIG_FILE: str = MODEL_CONFIG_FILE):
    """Choose models with support for API or local Ollama"""
    
    # Get list of installed Ollama models
    try:
        models_list = ollama_manager.list_models()
        available_models = [m["model"] for m in models_list]
    except Exception as e:
        print(f"[Vera Model Loader] Error listing models: {e}")
        available_models = []
    
    if not available_models:
        print("[Vera Model Loader] No Ollama models found!")
        print("Would you like to pull some default models? (y/n): ", end="")
        response = input().strip().lower()
        
        if response == 'y':
            default_to_pull = ["gemma2", "mistral:7b"]
            for model in default_to_pull:
                print(f"[Vera Model Loader] Pulling {model}...")
                if ollama_manager.pull_model(model):
                    print(f"[Vera Model Loader] Successfully pulled {model}")
                else:
                    print(f"[Vera Model Loader] Failed to pull {model}")
            
            # Refresh model list
            try:
                models_list = ollama_manager.list_models()
                available_models = [m["model"] for m in models_list]
            except Exception as e:
                print(f"[Vera Model Loader] Error refreshing model list: {e}")
        
        if not available_models:
            raise RuntimeError("[Vera Model Loader] No Ollama models available! Please install models manually.")

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
    if os.path.exists(MODEL_CONFIG_FILE):
        try:
            with open(MODEL_CONFIG_FILE, "r") as f:
                saved_models = json.load(f)
                default_models.update(saved_models)
        except Exception:
            print("[Vera Model Loader] Warning: could not read config file, using defaults.")
    
    chosen_models = {}
    print("\n[Vera Model Loader] Select a model for each category:")
    for key, default in default_models.items():
        # Check if default model is available, otherwise use first available
        if default not in available_models and available_models:
            default = available_models[0]
            print(f"[Vera Model Loader] Default model '{default_models[key]}' not found, using '{default}'")
        
        print(f"\nSelect model for {key.replace('_', ' ').title()} (default: {default})")
        for idx, model in enumerate(available_models, 1):
            marker = " ← current default" if model == default else ""
            print(f"{idx}. {model}{marker}")
        
        choice = input(f"Enter choice (1-{len(available_models)}) or press Enter for default: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(available_models):
            chosen_models[key] = available_models[int(choice) - 1]
        else:
            chosen_models[key] = default

    # Save chosen models for next run
    try:
        with open(MODEL_CONFIG_FILE, "w") as f:
            json.dump(chosen_models, f, indent=2)
        print(f"[Vera Model Loader] Configuration saved to {MODEL_CONFIG_FILE}")
    except Exception as e:
        print(f"[Vera Model Loader] Warning: could not save config: {e}")

    print("\n[Vera Model Loader] Selected Models:")
    for key, model in chosen_models.items():
        print(f"  {key}: {model}")
    print()

    return chosen_models


# --- Agent Class ---
class Vera:
    """Vera class that manages multiple LLMs and tools for complex tasks.
    Started off as a triple agent, but now it has grown into a multi-agent system."""

    def __init__(self, chroma_path="./Memory/vera_agent_memory", ollama_api_url: Optional[str] = None):
        # Initialize Ollama connection manager
        self.ollama_manager = OllamaConnectionManager(api_url=ollama_api_url)
        
        # Select models
        self.selected_models = choose_models_from_installed(self.ollama_manager)
        
        # Initialize LLMs using the manager (automatically handles API/local)
        self.embedding_llm = self.selected_models["embedding_model"]
        self.fast_llm = self.ollama_manager.create_llm(
            model=self.selected_models["fast_llm"], 
            temperature=0.6
        )
        self.intermediate_llm = self.ollama_manager.create_llm(
            model=self.selected_models["intermediate_llm"], 
            temperature=0.4
        )
        self.deep_llm = self.ollama_manager.create_llm(
            model=self.selected_models["deep_llm"], 
            temperature=0.6
        )
        self.reasoning_llm = self.ollama_manager.create_llm(
            model=self.selected_models["reasoning_llm"], 
            temperature=0.7
        )
        self.tool_llm = self.ollama_manager.create_llm(
            model=self.selected_models["tool_llm"], 
            temperature=0.1
        )
        
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

        # --- Shared ChromaDB Memory Tier 1---
        embeddings = self.ollama_manager.create_embeddings(model=self.embedding_llm)
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
            memory_key="chat_history",
            input_key="input",
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
        
        # Playwright browser setup
        self.sync_browser = create_sync_playwright_browser()
        self.playwright_toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=self.sync_browser)
        self.playwright_tools = self.playwright_toolkit.get_tools()
        print(f"[Vera] Loaded {len(self.playwright_tools)} Playwright tools.")
        
        self.executive_instance = executive(vera_instance=self)

        # Tool setup
        self.toolkit=ToolLoader(self)
        self.tools = self.toolkit + self.playwright_tools
        print(f"[Vera] Loaded {len(self.tools)} tools.")
        
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

        # Set callback
        self.focus_manager.proactive_callback = handle_proactive
    
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

        output = []
        for chunk in self.stream_llm(llm, full_prompt):
            output.append(chunk)
            yield chunk

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


    # def execute_tool_chain(self, query):
    #     """Plan and execute multiple tools in sequence, replacing inputs based on previous outputs."""

    #     planning_prompt = f"""
    #         You are a planning assistant.
    #         Available tools: {[(tool.name, tool.description) for tool in self.tools]}.
    #         The query is: {query}

    #         Plan a sequence of tool calls to solve the request.

    #         Rules for planning:
    #         - If a tool's input depends on the output data of a previous tool, write "{{prev}}" as the placeholder for that data.
    #         - DO NOT try to guess values that depend on previous outputs.
    #         - Use the exact tool names provided above.

    #         Respond ONLY in this pure JSON format:
    #         [
    #         {{ "tool": "<tool name>", "input": "<tool input or '{{prev}}'>" }},
    #         {{ "tool": "<tool name>", "input": "<tool input or '{{prev}}'>" }}
    #         ]
    #         """
    #     plan_json=""
    #     # Get the plan from the LLM and clean up any leading/trailing ```json or ```
    #     for r in self.stream_llm(self.deep_llm, planning_prompt):
    #         # print(r)
    #         yield(r)
    #         plan_json += r

    #     print(f"\n[ Planning Agent ]\nPlan: {plan_json}")

    #     for prefix in ("```json", "```"):
    #         if plan_json.startswith(prefix):
    #             plan_json = plan_json[len(prefix):].strip()
    #     if plan_json.endswith("```"):
    #         plan_json = plan_json[:-3].strip()

    #     try:
    #         tool_plan = json.loads(plan_json)
    #     except Exception as e:
    #         print(f"Failed to parse tool plan JSON: {e}")
    #         return f"Planning failed: {e} \n\n{plan_json}"

    #     tool_outputs = {}
    #     prev_output = None

    #     for step in tool_plan:
    #         print(f"Executing step: {step}")
    #         yield(f"Executing step: {step}")
    #         tool_name = step.get("tool")
    #         tool_input = step.get("input", "")
    #         tool_input = tool_input.replace("{prev}", str(prev_output if prev_output is not None else ""))
    #         print(f"{tool_name} input: {tool_input}")
    #         yield((f"{tool_name} input: {tool_input}"))
    #         # Find tool
    #         tool = next((t for t in self.tools if t.name == tool_name), None)
    #         if not tool:
    #             tool_outputs[tool_name] = f"Tool not found: {tool_name}"
    #             prev_output = None
    #             continue

    #         try:
    #             if hasattr(tool, "run") and callable(tool.run):
    #                 func = tool.run
    #             elif hasattr(tool, "func") and callable(tool.func):
    #                 func = tool.func
    #             elif callable(tool):
    #                 func = tool
    #             else:
    #                 raise ValueError(f"Tool is not callable")

    #             collected = []
    #             result=""
    #             try:
    #                 for r in func(tool_input):
    #                     # print(f"Step result: {r}")
    #                     yield r
    #                     collected.append(r)
    #             except TypeError:
    #                 # Not iterable — call again and yield single result
    #                 result = func(tool_input)
    #                 # print(f"Step result: {result}")
    #                 yield result
    #             else:
    #                 # You can combine collected results here if needed:
    #                 result = "".join(str(c) for c in collected)
    #                 yield result
    #             # store result or return if you want
    #             # tool_outputs[tool_name] = result
    #             prev_output = result
    #             tool_outputs[tool_name] = result
    #             self.save_to_memory(query, tool_outputs[tool_name])

    #         except Exception as e:
    #             tool_outputs[tool_name] = f"Error executing {tool_name}: {e}"
    #             prev_output = None
    #             print(tool_outputs) 

    #     # Merge results into a final answer
    #     merge_prompt = f"""
    #         The query was: {query}
    #         The following tools were executed with their outputs:
    #         {tool_outputs}

    #         Create a final answer that combines all the results.
    #         """
    #     final_answer = self.deep_llm.invoke(merge_prompt)
    #     return final_answer

    # --- Coordinator ---
#     def run(self, query):
#         self.mem.add_session_memory(self.sess.id, f"{query}", "Query", {"topic": "query"})
#         # Quick triage with Fast Agent (streamed)
#         print("\n[ Triage Agent ]\n")
#         triage_prompt =""
#         fast_response=""
#         deep_response=""
#         reasoning_response=""
#         tool_chain_response=""
#         tool_response=""
#         # if self.triage_memory is True: triage_prompt += (f"Given the conversation so far: {self.buffer_memory.load_memory_variables({})['chat_history']}\n")
#         # if self.long_term_triage is True: triage_prompt += (f"Given the conversation so far: {self.buffer_memory.load_memory_variables({})['chat_history']}\n")
#         triage_prompt += (
#                     f"""
#                     Classify this Query into one of the following categories:
#                         - 'focus'      → Change the focus of background thought.
#                         - 'proactive'  → Trigger proactive thinking.
#                         - 'simple'     → Simple textual response.
#                         - 'toolchain'  → Requires a series of tools or step-by-step planning and execution.
#                         - 'reasoning'  → Requires deep reasoning.
#                         - 'complex'    → Complex written response with high-quality output.
#                         - 'scheduling' → Requires scheduling or time management tasks.

#                     Current focus: {self.focus_manager.focus}  
#                     If you detect a change in focus or topic, you may specify new focus terms by appending the output with the.

#                     Available tools: {', '.join(t.name for t in self.tools)}

#                     Query: {query}

#                     Rules:
#                     - If 'simple' is the chosen category, disregard these rules and answer the Query using as many words as you like.
#                     - Respond with a single classification term (e.g., 'simple', 'tool', 'complex') on the first line, then any optional extra info.
#                     - You may optionally append focus terms.
#                     - If setting a 'focus', also specify the focus term to set (e.g., "focus project management").
#                     - Do NOT provide reasoning in your output nor formatting not mentioned in this prompt.
#                     """
# #                   - 'tool'       → Requires execution of a single tool.
#         )
#         for r in self.stream_llm(self.fast_llm, triage_prompt):
#             fast_response += r
#         self.mem.add_session_memory(self.sess.id, f"{fast_response}", "Triage", {"topic": "fast"})
        
#         if "focus" in fast_response.lower():
#             # If the query is about focus, use the proactive focus manager
#             print("\n[ Proactive Focus Manager ]\n")
#             self.focus_manager.set_focus(fast_response.lower().split("focus", 1)[-1].strip())
#             # proactive_response = self.focus_manager.relate_to_focus(query, fast_response)
#             # self.save_to_memory(query, proactive_response)
#             # return {"fast": fast_response}
        
#         # Decide routing
#         if "complex" in fast_response.lower():
#             print("\n[ Deep Agent ]\n")
#             for r in self.stream_llm_with_memory(self.deep_llm, query, extra_context=fast_response):
#                 deep_response += r
#             self.save_to_memory(query, deep_response) # Save to legacy memory
#             return {"fast": fast_response, "deep": deep_response}
        
#         elif "reasoning" in fast_response.lower():
#             print("\n[ Reasoning Agent ]\n")
#             for r in self.stream_llm_with_memory(self.reasoning_llm, query, extra_context=fast_response):
#                 reasoning_response += r
#             self.save_to_memory(query, reasoning_response) # Save to legacy memory
#             return {"fast": fast_response, "reasoning": reasoning_response}
        
#         elif "toolchain" in fast_response.lower():
#             print("\n[ Tool Chain Agent ]\n")
#             for r in self.toolchain.execute_tool_chain(query):
#                 tool_chain_response += str(r)
#             self.save_to_memory(query, tool_chain_response)
#             self.mem.add_session_memory(self.sess.id, f"{tool_chain_response}", "Response", {"topic": "toolchain"}, promote=True)
#             return {"fast": fast_response, "toolchain": tool_chain_response}
                
#         elif "tool" in fast_response.lower():
#             print("\n[ Tool Agent ]\n")

#             tool_response = self.light_agent.invoke(query)         
            
#             # Save both the user query and the full tool agent output (including intermediate steps if available)

#             if hasattr(self.light_agent, "agent_executor") and hasattr(self.light_agent.agent_executor, "intermediate_steps"):
#                 # If intermediate steps are available, save them as well
#                 intermediate_steps = self.light_agent.agent_executor.intermediate_steps
#                 self.save_to_memory(query, {"output": tool_response['output'], "intermediate_steps": tool_response['intermediate_steps']})
#                 return {"fast": fast_response, "tool": tool_response['output']}
#             else:
#                 self.save_to_memory(query, tool_response)
#                 self.mem.add_session_memory(self.sess.id, f"{tool_response}", "Response", {"topic": "tool"}, promote=True)
#             return {"fast": fast_response, "tool": tool_response}

#         elif "proactive" in fast_response.lower():
#             # If the query is about proactive thinking, use the proactive focus manager
#             print("\n[ Proactive Focus Manager ]\n")
#             proactive_thought = self.focus_manager._generate_proactive_thought()
#             if proactive_thought:
#                 self.focus_manager.add_to_focus_board("actions", proactive_thought)
#                 self.save_to_memory(query, proactive_thought)
#                 self.mem.add_session_memory(self.sess.id, f"{proactive_thought}", "Thought", {"topic": "proactive"}, promote=True)
#                 return {"fast": fast_response, "proactive": proactive_thought}
#             else:
#                 return {"fast": fast_response, "proactive": "No proactive thought generated."}
        
#         elif "scheduling" in fast_response.lower():
#             print("\n[ Scheduling Assistant ]\n")
#             scheduling_response = self.executive_instance.main(query)
#             self.save_to_memory(query, scheduling_response)
#             self.mem.add_session_memory(self.sess.id, f"{scheduling_response}", "Response", {"topic": "scheduling"}, promote=True)
#             return {"fast": fast_response, "scheduling": scheduling_response}
        
#         else:
#         #     # Simple case, just fast agent again
#         #     final_fast_response = self.stream_llm_with_memory(self.fast_llm, query, extra_context=fast_response)
#         #     self.save_to_memory(query, final_fast_response)
#         #     return {"fast": final_fast_response}
#             self.save_to_memory(query, fast_response)
#             return {"fast": fast_response}
        
        
    def async_run(self, query):
        self.mem.add_session_memory(self.sess.id, f"{query}", "Query", {"topic": "plan"}, promote=True)
        # Stream triage prompt output chunk-by-chunk
        # - 'tool'       → Requires execution of a single tool.
        triage_prompt = (
            f"""
            Classify this Query into one of the following categories:
                - 'focus'      → Change the focus of background thought.
                - 'proactive'  → Trigger proactive thinking.
                - 'simple'     → Simple textual response.
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
            
        # Branch logic based on triage
        # if "simple" in triage_lower:
        #     # stream deep llm output
        #     for fast_chunk in self.stream_llm(self.fast_llm, query): #, extra_context=triage_lower):
        #         fast_response += fast_chunk
        #         yield  fast_chunk
        #     self.mem.add_session_memory(self.sess.id, f"{fast_response}", "Response", {"topic": "response", "agent": "simple"}) #"model":self.fast_llm})
        #     total_response += fast_response
        if triage_lower.startswith("proactive"):
            # old code:
            # If the query is about proactive thinking, use the proactive focus manager
            # print("\n[ Proactive Focus Manager ]\n")
            # proactive_thought = self.focus_manager._generate_proactive_thought_streaming()
            # if proactive_thought:
            #     self.focus_manager.add_to_focus_board("actions", proactive_thought)
            #     yield proactive_thought
            #     self.mem.add_session_memory(self.sess.id, f"{proactive_thought}", "Thought", {"topic": "proactive"})
            #     total_response += proactive_thought

            self.focus_manager.iterative_workflow(
                max_iterations=None,
                iteration_interval=600,  # 10 minutes
                auto_execute=True
            )
        elif triage_lower.startswith("complex"):
            # stream deep llm output
            for deep_chunk in self.stream_llm(self.deep_llm, query): #, extra_context=triage_lower):
                deep_response += deep_chunk
                yield  deep_chunk
            self.mem.add_session_memory(self.sess.id, f"{deep_response}", "Response", {"topic": "response", "agent": "complex"}) #"model":self.deep_llm})
            total_response += deep_response
        
        elif triage_lower.startswith("reasoning"):
            for reason_chunk in self.stream_llm(self.reasoning_llm, query): #, extra_context=triage_lower):
                reason_response += reason_chunk
                yield reason_chunk
            self.mem.add_session_memory(self.sess.id, f"{reason_response}", "Response", {"topic": "response", "agent": "reasoning"})
            total_response += reason_response
        
        elif triage_lower.startswith("toolchain"):
            print("\n[ Tool Chain Agent ]\n")
            # return {"fast": fast_response, "toolchain": tool_chain_response}
            for toolchain_chunk in self.toolchain.execute_tool_chain(query):
                toolchain_response += str(toolchain_chunk)
                yield toolchain_chunk
            self.mem.add_session_memory(self.sess.id, f"{toolchain_response}", "Response", {"topic": "response", "agent": "toolchain"})
            total_response += toolchain_response    
            # self.save_to_memory(query, tool_chain_response)
        # elif "tool" in triage_lower:
        #     for tool_chunk in self.light_agent.invoke(query):
        #         tool_response += str(tool_chunk)
        #         yield tool_chunk
        #     yield tool_response
        #     self.mem.add_session_memory(self.sess.id, f"{tool_response}", "Response", {"topic": "response", "agent": "tool"})
        #     total_response += tool_response      

        else:
            pass
        
        self.save_to_memory(query, total_response) # Legavy Memory
        # self.mem.add_session_memory(self.sess.id, f"{total_response}", "Response", {"topic": "response"}) 


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
            You are a rigorous expert planning assistant.
            Available tools: {[(tool.name, tool.description) for tool in self.tools]}.
            The query is: {query}

            Previous attempts and their outputs:\n{history_context if history_context else ""}

            Plan a comprehensive sequence of tool calls to solve the request.


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
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self.agent.mem.add_session_memory(self.agent.sess.id, f"{json.dumps(tool_plan)}", "Plan", {"topic": "plan","plan id" : plan_id}, promote=True)
        yield tool_plan

    def execute_tool_chain(self, query: str, plan=None ) -> str:
        """Execute a tool chain, allowing reference to any step output."""
        try:
            if plan == None:
                gen = self.plan_tool_chain(query)
                for r in gen:
                    yield r
                    tool_plan = r
            else:
                tool_plan = plan

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
                        self.agent.mem.add_session_memory(self.agent.sess.id, f"Step {step_num} - {tool_name}\n{result}", "Step", {"topic": "step","author": "toolchain", "toolchain step": step_num, "tool": tool_name, "plan id": plan_id})
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
            return self.execute_tool_chain(query, plan=recovery_plan)  # re-run with recovery

        # Final goal check
        review_prompt = f"""
            The query was: {query}
            Execution results: {json.dumps(tool_outputs.get(f"step_{step_num}", ""), indent=2)}

            Does the final result meet the goal? 
            Answer only 'yes' or 'no' and explain briefly.
        """
        review = self.agent.fast_llm.invoke(review_prompt)
        if "no" in review.lower():
            print("[ Toolchain Agent ] Goal not achieved, replanning...")
            yield("[ Toolchain Agent ] Goal not achieved, replanning...")
            retry_plan = self.plan_tool_chain(
                f"Retry the task ensuring the goal is met. Original query: {query}",
                history_context=json.dumps(tool_outputs, indent=2)
            )
            return self.execute_tool_chain(query)

        # # Merge results into a final answer
        # merge_prompt = f"""
        #     The query was: {query}
        #     The following tools were executed with their outputs:
        #     {tool_outputs}

        #     Create a final answer that combines all the results.
        #     """
        # final_answer = self.deep_llm.invoke(merge_prompt)

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
        if user_query.lower() == "/replay":
            print("Replaying last tool plan...")
            with open("./Configuration/last_tool_plan.json", "r", encoding="utf-8") as f:
                last_plan = f.read()
            tcp = ToolChainPlanner(vera, vera.tools)
            print(tcp.execute_tool_chain(vera, "Replaying last plan", plan=json.loads(last_plan)))
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