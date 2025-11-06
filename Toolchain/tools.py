from langchain.agents import Tool
from langchain_core.tools import tool
from langchain.tools import BaseTool
import os
import subprocess
import sys
import io
import traceback
import inspect
import asyncio
import re
import datetime
from urllib.parse import quote_plus
from duckduckgo_search import DDGS
from playwright.async_api import async_playwright
from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import (
    create_sync_playwright_browser,
    create_async_playwright_browser,
)
from typing import List, Dict, Any, Type
from pydantic import BaseModel, Field
from functools import partial
def ToolLoader(agent):

    # @tool
    def review_output(agent, query, response):
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
        review = agent.fast_llm.invoke(review_prompt)
        return review.strip()
    
    # @tool
    def read_own_source(agent) -> str:
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
    def fast_llm_func(agent, q):
        """ Query a fast LLM"""
        result=""
        for x in agent.stream_llm_with_memory(agent.fast_llm, q, long_term=False, short_term=True):
            text = x if isinstance(x, str) else str(x)
            # print(r)
            result += x
            yield x
        agent.mem.add_session_memory(agent.sess.id, text, "Answer", {"topic": "decision", "agent": agent.selected_models["fast_llm"]})
        # return result

    # @tool
    def deep_llm_func(agent, q):
        """ Query a deep LLM"""
        result=""
        for x in agent.stream_llm_with_memory(agent.deep_llm, q, long_term=True, short_term=True):
            text = x if isinstance(x, str) else str(x)
            # print(r)
            result += x
            yield x
        agent.mem.add_session_memory(agent.sess.id, text, "Answer", {"topic": "decision", "agent": agent.selected_models["deep_llm"]})
        # return result
    
    # @tool
    def write_file_tool(agent, q):
        """ Write a file """
        try:
            # Expecting "path::content"
            path, content = str(q).split("|||", 1)
            with open(path.strip(), 'w', encoding='utf-8') as f:
                f.write(content)
            m1 = agent.mem.add_session_memory(agent.sess.id, path, "file", metadata={"status": "active", "priority": "high"}, labels=["File"], promote=True) # Add memory metadata
            m2 = agent.mem.attach_document(agent.sess.id, path, content, {"topic": "write file", "agent": "Vera"}) # Add document content
            # m2 = agent.mem.attach_document(path.strip(), os.path.basename(path.strip()), content, {"doc_type": "generated"})
            agent.mem.link(m1.id, m2.id, "Written")
            return f"File written successfully to {path}"
        except ValueError:
            return "Invalid write_to_file input format. Use: path|||content"
        except Exception as e:
            return f"Error writing file: {e}"

    # @tool
    def read_file_tool(agent, q):
        """Read a file and return its contents."""
        try:
            if os.path.exists(q):
                with open(q, 'r', encoding='utf-8') as f:
                    content = f.read()
                m1 = agent.mem.add_session_memory(agent.sess.id, q, "file", metadata={"status": "active", "priority": "high"},  labels=["File"], promote=True) # Add memory metadata
                m2 = agent.mem.attach_document(agent.sess.id, q, content, {"topic": "write file", "agent": "Vera"}) # Add document content
                # m2 = agent.mem.attach_document(path.strip(), os.path.basename(path.strip()), content, {"doc_type": "generated"})
                agent.mem.link(m1.id, m2.id, "Read")
                return content
        except Exception as e:
            return f"Error reading file {q}: {e}"
    
    # @tool
    def run_command_stream(agent, q):
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
        m1 = agent.mem.upsert_entity(q, "command", labels=["Command"], properties={"shell": "bash", "priority": "high"})
        m2 = agent.mem.add_session_memory(agent.sess.id, q, "Command", {"topic": "bash command", "agent": "Vera"})
        agent.mem.link(m1.id, m2.id, "Run")
        m3 = agent.mem.add_session_memory(agent.sess.id, result, "Command Result", {"topic": "bash output", "agent": "Vera"})
        agent.mem.link(m1.id, m3.id, "Output")
        # agent.mem.add_session_memory(agent.sess.id, f"Executed command: {q}", "Command", {"topic": "bash"})
        # agent.mem.add_session_memory(agent.sess.id, f"Command Result: {result}", "Command", {"topic": "bash"})
        process.stdout.close()
        return_code = process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, q)
        return process.stdout


    # @tool
    def run_python(agent, code: str) -> str:
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
            m1 = agent.mem.upsert_entity(code, "python", labels=["Python"], properties={"shell": "python", "priority": "high"})
            m2 = agent.mem.add_session_memory(agent.sess.id, code, "Python", {"topic": "bash command", "agent": "Vera"})
            agent.mem.link(m1.id, m2.id, "Create")
            m3 = agent.mem.add_session_memory(agent.sess.id, result, "Result", {"topic": "python output", "agent": "Vera"})
            agent.mem.link(m1.id, m3.id, "Output")
            return output.strip() or "[No output]"

        except Exception:
            return f"[Error]\n{traceback.format_exc()}"

        finally:
            sys.stdout = old_stdout
        
    # @tool
    def duckduckgo_search(agent, query: str, max_results: int = 10) -> str:
        """Search the web using DuckDuckGo and return the top results as a string of titles, urls, and short descriptions. Further processing may be required to extract useful information."""
        print(query)
        query_encoded = quote_plus(query)
        print(query_encoded)
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, region="us-en", max_results=max_results)
                search = agent.mem.add_session_memory(agent.sess.id, query, "web_search", metadata={"author":"duck duck go search"})
                output = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "")
                    href = r.get("href", "")
                    body = r.get("body", "")
                    search_result = agent.mem.upsert_entity(href,f"search_result",properties={"title:":title,"body:":body}, labels=["Search_result"])
                    agent.mem.link(search.id,search_result.id,"RESULT")
                    output.append(f"{idx}. {title}\n{href}\n{body}\n")
                return "\n".join(output) if output else "No results found."
        except Exception as e:
            return f"[DuckDuckGo Search Error] {e}"

    def duckduckgo_search_news(agent, query, max_results=10):
        """Search for news articles using DuckDuckGo and return the top results."""
        query_encoded = quote_plus(query)
        try:
            with DDGS() as ddgs:
                results = ddgs.news(query, region="us-en", max_results=max_results)
                search = agent.mem.add_session_memory(agent.sess.id, query, "news_search", metadata={"author": "duck duck go news"})
                output = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "")
                    href = r.get("url", "")
                    body = r.get("body", "")
                    search_result = agent.mem.upsert_entity(href, "news_result", properties={"title": title, "body": body}, labels=["Search_result"])
                    agent.mem.link(search.id, search_result.id, "RESULT")
                    output.append(f"{idx}. {title}\n{href}\n{body}\n")
                return "\n".join(output) if output else "No news articles found."
        except Exception as e:
            return f"[DuckDuckGo News Search Error] {e}"
    
    def web_search_report(agent, input_data: str, max_results: int = 5) -> str:
        """
        Search the web and scrape content from result pages using Playwright, or process existing search results.
        Accepts either a search query string or raw search results from duckduckgo_search.
        Returns a comprehensive report with titles, URLs, descriptions, and scraped content.
        """
                
        async def scrape_url_with_playwright(url: str) -> str:
            """Scrape a single URL using Playwright and return cleaned text content."""
            try:
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context()
                    
                    # Set a realistic user agent
                    await context.set_extra_http_headers({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    })
                    
                    page = await context.new_page()
                    
                    # Try to handle cookie consent dialogs automatically
                    page.on("dialog", lambda dialog: dialog.accept())
                    
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    
                    # Wait a bit for page to settle
                    await page.wait_for_timeout(3000)
                    
                    # Try to handle common cookie consent buttons
                    consent_selectors = [
                        'button:has-text("Accept")',
                        'button:has-text("Accept All")',
                        'button:has-text("Agree")',
                        'button:has-text("I Agree")',
                        '[aria-label*="accept"]',
                        '[aria-label*="agree"]',
                        '.accept-cookies',
                        '#accept-cookies',
                        'button[data-testid*="accept"]'
                    ]
                    
                    for selector in consent_selectors:
                        try:
                            button = await page.query_selector(selector)
                            if button:
                                await button.click()
                                await page.wait_for_timeout(1000)
                                break
                        except:
                            continue
                    
                    # Wait for main content to load - look for article, main, or content sections
                    content_selectors = [
                        'article',
                        'main',
                        '[role="main"]',
                        '.article',
                        '.story',
                        '.content',
                        '.post',
                        '.entry-content',
                        '#content',
                        '#main',
                        'body'
                    ]
                    
                    # Wait for any of these content elements to appear
                    for selector in content_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            break
                        except:
                            continue
                    
                    # Try multiple content extraction strategies
                    content_text = ""
                    
                    # Strategy 1: Try to get article content first
                    article_selectors = [
                        'article',
                        '.article',
                        '.story',
                        '.post',
                        '.entry-content',
                        '[class*="article"]',
                        '[class*="content"]',
                        '[class*="story"]'
                    ]
                    
                    for selector in article_selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element:
                                text = await element.inner_text()
                                if len(text) > 100:  # Only use if we got substantial content
                                    content_text = text
                                    break
                        except:
                            continue
                    
                    # Strategy 2: If no article content, try main content areas
                    if len(content_text) < 100:
                        for selector in ['main', '[role="main"]', '.content', '#content', 'body']:
                            try:
                                element = await page.query_selector(selector)
                                if element:
                                    text = await element.inner_text()
                                    if len(text) > len(content_text):
                                        content_text = text
                            except:
                                continue
                    
                    # Strategy 3: Look for text-heavy elements
                    if len(content_text) < 200:
                        # Get all paragraph text
                        paragraphs = await page.query_selector_all('p')
                        paragraph_texts = []
                        for p in paragraphs:
                            try:
                                text = await p.inner_text()
                                if len(text) > 50:  # Only substantial paragraphs
                                    paragraph_texts.append(text)
                            except:
                                continue
                        
                        if paragraph_texts:
                            content_text = '\n\n'.join(paragraph_texts)
                    
                    await browser.close()
                    
                    if not content_text:
                        return "[No substantial content found - site may require JavaScript or have paywall]"
                    
                    # Clean up the text
                    lines = (line.strip() for line in content_text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    cleaned_text = ' '.join(chunk for chunk in chunks if chunk)
                    
                    # Remove common cookie/privacy text patterns
                    privacy_patterns = [
                        r'cookie policy.*?privacy policy',
                        r'privacy policy.*?cookie policy',
                        r'accept all.*?reject all',
                        r'we use cookies.*?accept',
                        r'yahoo family of brands',
                        r'aol is part of',
                        r'continue reading$'
                    ]
                    
                    for pattern in privacy_patterns:
                        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
                    
                    # Limit the length to avoid overly long responses
                    if len(cleaned_text) > 2500:
                        cleaned_text = cleaned_text[:2500] + "... [content truncated]"
                    
                    # Final cleanup - remove extra whitespace
                    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
                    
                    if len(cleaned_text) < 50:
                        return "[Content too short after cleaning - site may have paywall or require login]"
                        
                    return cleaned_text
                    
            except Exception as e:
                try:
                    await browser.close()
                except:
                    pass
                return f"[Scraping Error: {str(e)[:100]}]"

        def parse_search_results_from_text(search_text: str) -> list:
            """Parse search results from the string output of duckduckgo_search."""
            results = []
            lines = search_text.split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i].strip()
                # Look for numbered results (e.g., "1. Title")
                if re.match(r'^\d+\.\s+.+', line):
                    title = line.split('. ', 1)[1] if '. ' in line else line
                    url = ""
                    body = ""
                    
                    # Get URL from next line if it looks like a URL
                    if i + 1 < len(lines) and lines[i + 1].startswith('http'):
                        url = lines[i + 1].strip()
                        i += 1
                    
                    # Get description from next line if it exists
                    if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith('http'):
                        body = lines[i + 1].strip()
                        i += 1
                    
                    if url:  # Only add if we found a URL
                        results.append({
                            "title": title,
                            "href": url,
                            "body": body
                        })
                i += 1
            
            return results

        try:
            results = []
            search_query = ""
            
            # Determine input type and get results
            if re.search(r'^\d+\.\s+.+', input_data) and ('http' in input_data):
                print("Parsing existing search results...")
                results = parse_search_results_from_text(input_data)
                search_query = "parsed_from_existing_results"
            else:
                # It's a search query - perform new search
                print(f"Performing new search for: {input_data}")
                search_query = input_data
                
                with DDGS() as ddgs:
                    search_results = ddgs.text(input_data, region="us-en", max_results=max_results)
                    results = list(search_results)

            # Limit results
            results = results[:max_results]
            
            if not results:
                return "No results found to process."

            # Create search memory entry
            search = agent.mem.add_session_memory(
                agent.sess.id, search_query, "web_search_report", 
                metadata={
                    "author": "web search report", 
                    "max_results": max_results,
                    "input_type": "search_query" if search_query != "parsed_from_existing_results" else "existing_results"
                }
            )
            
            output = []
            scraped_data = []
            
            # Create event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            for idx, r in enumerate(results, 1):
                title = r.get("title", "")
                href = r.get("href", "")
                body = r.get("body", "")
                
                if not href:
                    continue
                    
                # Store search result
                search_result = agent.mem.upsert_entity(
                    href, "search_result",
                    properties={"title": title, "body": body},
                    labels=["Search_result"]
                )
                agent.mem.link(search.id, search_result.id, "RESULT")
                
                # Scrape the page content using async Playwright
                output.append(f"\n{'='*80}")
                output.append(f"RESULT {idx}: {title}")
                output.append(f"URL: {href}")
                output.append(f"Description: {body}")
                output.append(f"{'-'*40}")
                
                print(f"Scraping {idx}/{len(results)}: {href}")
                scraped_content = loop.run_until_complete(scrape_url_with_playwright(href))
                
                # Store scraped content
                scraped_entity = agent.mem.upsert_entity(
                    f"{href}_content", "scraped_content",
                    properties={
                        "title": title,
                        "url": href,
                        "content": scraped_content[:500] + "..." if len(scraped_content) > 500 else scraped_content
                    },
                    labels=["Scraped_content"]
                )
                agent.mem.link(search_result.id, scraped_entity.id, "HAS_CONTENT")
                
                output.append(f"Scraped Content:\n{scraped_content}")
                output.append(f"{'='*80}")
                
                scraped_data.append({
                    "title": title,
                    "url": href,
                    "description": body,
                    "content": scraped_content
                })
            
            # Add summary to memory
            summary_entity = agent.mem.upsert_entity(
                f"report_{search.id}", "search_report",
                properties={
                    "query": search_query,
                    "total_results": len(scraped_data),
                    "summary": f"Web search report processed {len(scraped_data)} results"
                },
                labels=["Search_Report"]
            )
            agent.mem.link(search.id, summary_entity.id, "GENERATED_REPORT")
            
            final_output = "\n".join(output) if output else "No results found."
            return final_output
            
        except Exception as e:
            return f"[Web Search Report Error] {e}"

    
    return [
        Tool( 
            name="Query Fast LLM",
            func=partial(fast_llm_func, agent),
            description="capable of creative writing, reviewing text, summarizing, combining text, improving text. Fast but can be inaccurate"
            #"Given a query and context, reviews or summarizes the response for clarity and brevity. Acts as a quick reviewer, extractor, transformer or summarizer, not a solution provider."
        ),
        Tool( 
            name="Query Deep LLM",
            func=partial(deep_llm_func, agent),
            description="capable of creative writing, reviewing text, summarizing, combining text, improving text. slow and accurate"
            #"Given a query and context, reviews, improves or summarizes the response. Acts as a detailed reviewer, extractor, transformer  or summarizer, not a solution provider."
        ),
        Tool(
            name="Bash Shell",
            func=lambda q: subprocess.check_output(q, shell=True, text=True, stderr=__import__('subprocess').STDOUT), # REMOVE inline import
            # func=run_command_stream,
            description="Execute a bash shell command or script, and return its output."
        ),
        Tool(
            name="Run Python Code",
            func=partial(run_python, agent),
            description="Execute a Python code snippet."
        ),
        Tool(
            name="Read File",
            func=partial(read_file_tool, agent),
            description="Read the contents of a file. Provide the full path to the file."
        ),
        Tool(
            name="Write File",
            func=partial(write_file_tool, agent),
            description="Given a filepath and content, saves content to a file. Input format: filepath, followed by '|||' delimiter, then the file content. Example input: /path/to/file.txt|||This is the file content. Do NOT use newlines as delimiter."
        ),
        Tool(
            name="List Python Modules",
            func=lambda q: sorted(list(sys.modules.keys())),
            description="List all currently loaded Python modules."
        ),
        # Tool(
        #     name="List Installed Programs",
        #     func=lambda q: subprocess.check_output(
        #         "wmic product get name" if sys.platform == "win32" else "dpkg --get-selections" if sys.platform.startswith("linux") else "brew list",
        #         shell=True,
        #         text=True,
        #         stderr=subprocess.STDOUT
        #     ),
        #     description="List all installed programs on this system."
        # ),
        # Tool(
        #     name="Review Output",
        #     func=lambda q: agent.review_output(q.get("query", ""), q.get("response", "")) if isinstance(q, dict) and "query" in q and "response" in q else "Input must be a dict with 'query' and 'response' keys.",
        #     description="Review an output given the original query and response. Input should be a dict: {'query': <query>, 'response': <response>}."
        # ),
        Tool(
            name="Search Memory",
            func=lambda q: "\n".join(
                [doc.page_content for doc in agent.vectorstore.similarity_search(q, k=5)]
            ),
            description="Searches long-term memory for relevant information given a query."
        ),
        Tool(
            name="DuckDuckGo Web Search",
            func=partial(duckduckgo_search, agent),
            description="Search the web for relevant websites using DuckDuckGo."
        ),
        Tool(
            name="DuckDuckGo News Search",
            func=partial(duckduckgo_search_news,agent),
            description="Searches the web for news using DuckDuckGo."
        ),
            Tool(
            name="Web Search Report", 
            func=partial(web_search_report,agent),
            description="Comprehensive web search with page scraping using Playwright. Accepts search queries or existing search results. Returns detailed reports with full page content. Use when you need in-depth information from web pages."
        ),
        Tool(
            name="inspect system source code",
            func=lambda q: read_own_source(),
            description="Allows you to peer at your own code. helpful for understanding your own inner workings. not used for most tasks."
        ),
        Tool(
        name="Scheduling Assistant",
        func=agent.executive_instance.main,
        description="Run the executive scheduling assistant with a query. It has access to the users calendars todo lists and scheduling apps, It can plan and execute scheduling and time management tasks, manage events, calendars, and more. Input should be a query string."
    )
    ]

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
