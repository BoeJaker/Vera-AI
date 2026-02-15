# ------------------------------------------------------------------------
# DATA PROCESSING TOOLS
# ------------------------------------------------------------------------

import json
import re
from typing import List
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import FilePathInput, HashInput
from typing import Any

def sanitize_path(path: str) -> str:
    """Sanitize and validate file paths."""
    path = os.path.normpath(path)
    if path.startswith('..'):
        raise ValueError("Path traversal not allowed")
    return path


def format_json(data: Any) -> str:
    """Format data as pretty JSON."""
    try:
        return json.dumps(data, indent=2, default=str)
    except:
        return str(data)


class DataProcessingTool:
    def __init__(self, agent):
        self.agent = agent
        self.name = "DataProcessingTool"
    
    def parse_json(self, json_string: str) -> str:
        """
        Parse and validate JSON, returning formatted output.
        Useful for debugging and validating JSON data.
        """
        try:
            data = json.loads(json_string)
            return format_json(data)
        except json.JSONDecodeError as e:
            return f"[JSON Error] {str(e)}"
    
    def convert_csv_to_json(self, csv_path: str) -> str:
        """
        Convert CSV file to JSON format.
        """
        try:
            import csv
            csv_path = sanitize_path(csv_path)
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
            
            return format_json(data)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def hash_text(self, text: str, algorithm: str = "sha256") -> str:
        """
        Generate cryptographic hash of text.
        Algorithms: md5, sha1, sha256, sha512
        """
        try:
            import hashlib
            
            hash_func = getattr(hashlib, algorithm.lower(), None)
            if not hash_func:
                return f"[Error] Unsupported algorithm: {algorithm}"
            
            hash_obj = hash_func(text.encode('utf-8'))
            
            return f"{algorithm.upper()}: {hash_obj.hexdigest()}"
            
        except Exception as e:
            return f"[Error] {str(e)}"

def add_data_processing_tools(tool_list: List, agent) -> List:
    """
    Add data processing tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_data_processing_tools(tool_list, self)
    ```
    """
    tools = DataProcessingTool(agent)

    tool_list.extend(
        [

            # StructuredTool.from_function(
            #     func=tools.parse_json,
            #     name="parse_json",
            #     description="Parse and validate JSON, returning formatted output.",
            #     args_schema=LLMQueryInput
            # ),

            StructuredTool.from_function(
                func=tools.convert_csv_to_json,
                name="csv_to_json",
                description="Convert CSV file to JSON format.",
                args_schema=FilePathInput
            ),

            StructuredTool.from_function(
                func=tools.hash_text,
                name="hash_text",
                description="Generate cryptographic hash (md5, sha1, sha256, sha512) of text.",
                args_schema=HashInput  # FIXED
            ),

        ]
    )
    return tool_list