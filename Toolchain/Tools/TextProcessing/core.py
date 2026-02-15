
# ------------------------------------------------------------------------
# TEXT PROCESSING TOOLS
# ------------------------------------------------------------------------

import os
import re
from typing import List

from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import TokenCountInput, RegexSearchInput, TextInput

class TextProcessingTool:
    """Tool for text processing tasks: token counting, regex searching, and text statistics."""

    def __init__(self, agent):
        self.agent = agent
        self.name = "TextProcessingTool"

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Estimate token count for text using tiktoken.
        Useful for managing context windows.
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model)
            tokens = len(encoding.encode(text))
            return f"Token count: {tokens}\nCharacter count: {len(text)}\nWord count: {len(text.split())}"
        except ImportError:
            # Rough estimate if tiktoken not available
            tokens = len(text) // 4
            return f"Estimated tokens: ~{tokens}\nCharacter count: {len(text)}\nWord count: {len(text.split())}"
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def regex_search(self, pattern: str, text: str, flags: str = "") -> str:
        """
        Search text using regular expressions.
        Flags: i (ignore case), m (multiline), s (dotall)
        """
        try:
            flag_map = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL}
            regex_flags = 0
            for f in flags.lower():
                if f in flag_map:
                    regex_flags |= flag_map[f]
            
            matches = re.findall(pattern, text, regex_flags)
            
            if not matches:
                return "No matches found"
            
            result = {
                "pattern": pattern,
                "match_count": len(matches),
                "matches": matches[:100]  # Limit to 100 matches
            }
            return format_json(result)
            
        except Exception as e:
            return f"[Regex Error] {str(e)}"
    
    def text_statistics(self, text: str) -> str:
        """
        Generate comprehensive statistics about text.
        Includes word count, character count, sentence count, etc.
        """
        try:
            lines = text.split('\n')
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            
            stats = {
                "characters": len(text),
                "characters_no_spaces": len(text.replace(' ', '')),
                "words": len(words),
                "lines": len(lines),
                "sentences": len([s for s in sentences if s.strip()]),
                "paragraphs": len([p for p in text.split('\n\n') if p.strip()]),
                "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
                "unique_words": len(set(words))
            }
            
            return format_json(stats)
            
        except Exception as e:
            return f"[Error] {str(e)}"


def add_text_processing_tools(tool_list: List, agent) -> List:
    """
    Add text processing tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_text_processing_tools(tool_list, self)
    ```
    """
    tools = TextProcessingTool(agent)

    tool_list.extend(
        [   
            # Text Processing Tools
        StructuredTool.from_function(
            func=tools.count_tokens,
            name="count_tokens",
            description="Estimate token count for text. Useful for managing context windows.",
            args_schema=TokenCountInput  # FIXED
        ),
        StructuredTool.from_function(
            func=tools.regex_search,
            name="regex_search",
            description="Search text using regular expressions with optional flags.",
            args_schema=RegexSearchInput  # FIXED - NOW UNCOMMENTED
        ),
        StructuredTool.from_function(
            func=tools.text_statistics,
            name="text_stats",
            description="Generate comprehensive statistics about text (word count, sentences, etc).",
            args_schema=TextInput  # FIXED
        ),
        ]
    )

    return tool_list