#!/usr/bin/env python3
"""
Comprehensive Codebase Analysis Toolkit for Vera
Hierarchical code structure mapping with version tracking and change detection

FEATURES:
- Local directory analysis
- Remote Git repository cloning and analysis
- Direct code text processing
- Multi-language support (Python, JavaScript, Java, Go, etc.)
- Hierarchical graph structure (Project → Files → Classes → Functions → Variables)
- Automatic deprecation marking for removed/changed entities
- Incremental update support
- Code metrics and complexity analysis
- Dependency and import tracking
- Call graph generation
- Full graph memory integration
- Tool chaining compatible

DEPENDENCIES:
    pip install gitpython tree-sitter pygments radon
    
Optional for enhanced parsing:
    pip install tree-sitter-languages
"""

import os
import re
import ast
import json
import hashlib
import subprocess
import signal
from typing import List, Dict, Any, Optional, Set, Iterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from pydantic import BaseModel, Field
from enum import Enum
import logging

# Git support
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    print("[Warning] GitPython not available - Git features disabled")

# Tree-sitter for multi-language parsing
try:
    import tree_sitter_languages
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("[Warning] tree-sitter-languages not available - using fallback parsers")

# Code metrics
try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit, h_visit
    from radon.raw import analyze
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False
    print("[Warning] radon not available - code metrics disabled")

# Syntax highlighting for display
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import TerminalFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# TIMEOUT DECORATOR
# =============================================================================

class TimeoutException(Exception):
    """Exception raised when operation times out"""
    pass

def timeout(seconds):
    """Decorator to add timeout to functions"""
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutException(f"Operation timed out after {seconds} seconds")
        
        def wrapper(*args, **kwargs):
            # Set the signal handler and alarm
            old_handler = signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Restore the old handler and cancel the alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return result
        return wrapper
    return decorator

# =============================================================================
# CONFIGURATION
# =============================================================================

class AnalysisMode(str, Enum):
    """Code analysis modes"""
    STRUCTURE = "structure"  # File/directory structure only
    SHALLOW = "shallow"      # + imports and top-level definitions
    STANDARD = "standard"    # + class/function signatures
    DEEP = "deep"           # + full code analysis with metrics
    FULL = "full"           # + call graphs and advanced analysis

@dataclass
class CodebaseConfig:
    """Configuration for codebase analysis"""
    
    # Analysis depth
    mode: AnalysisMode = AnalysisMode.STANDARD
    
    # Source specification
    max_file_size: int = 512 * 1024  # 512KB default (reduced from 1MB)
    
    # Exclude patterns - EXPANDED
    exclude_patterns: List[str] = field(default_factory=lambda: [
        # Version control
        '__pycache__', '.git', '.svn', '.hg', 
        # Dependencies
        'node_modules', 'bower_components', 'jspm_packages',
        'venv', 'env', '.env', 'virtualenv', '.venv',
        # Build artifacts
        'build', 'dist', 'out', 'target', 'bin', 'obj',
        # Test/coverage
        '.pytest_cache', '.mypy_cache', '.tox', 'coverage', '.coverage', 
        '.nyc_output', 'htmlcov',
        # IDE/Editor
        '.vscode', '.idea', '.vs', '*.swp', '*.swo', '.DS_Store',
        # Compiled files
        '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dylib', '*.dll', '*.class',
        '*.o', '*.obj', '*.exe', '*.out', '*.app',
        # Database files
        '*.db', '*.sqlite', '*.sqlite3', '*.db3', '*.sql', '*.mdb',
        # Vector stores and embeddings
        'chroma', 'chroma_db', '*.index', '*.faiss', '*.annoy',
        '*.npy', '*.npz', '*.pkl', '*.pickle', '*.h5', '*.hdf5',
        # Binary/Media files
        '*.bin', '*.dat', '*.data', '*.pack', '*.idx',
        '*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.svg', '*.ico',
        '*.pdf', '*.zip', '*.tar', '*.gz', '*.bz2', '*.7z', '*.rar',
        '*.mp3', '*.mp4', '*.avi', '*.mov', '*.wav', '*.flac',
        # Logs
        '*.log', 'logs', 'log',
        # Temporary files
        'tmp', 'temp', '.tmp', '.temp', '*.tmp', '*.temp',
        # OS files
        'Thumbs.db', 'desktop.ini',
        # Package files
        '*.egg-info', '*.whl', '*.gem', '*.jar', '*.war',
    ])
    
    # File extensions to INCLUDE for parsing - WHITELIST approach
    code_extensions: Set[str] = field(default_factory=lambda: {
        # Code files
        '.py', '.pyw',  # Python
        '.js', '.jsx', '.mjs', '.cjs',  # JavaScript
        '.ts', '.tsx',  # TypeScript
        '.java',  # Java
        '.go',  # Go
        '.rs',  # Rust
        '.cpp', '.cc', '.cxx', '.hpp', '.h', '.hxx',  # C++
        '.c', '.h',  # C
        '.rb',  # Ruby
        '.php', '.php3', '.php4', '.php5',  # PHP
        '.swift',  # Swift
        '.kt', '.kts',  # Kotlin
        '.scala',  # Scala
        '.sh', '.bash', '.zsh',  # Shell
        '.pl', '.pm',  # Perl
        '.r', '.R',  # R
        '.m', '.mm',  # Objective-C
        '.cs',  # C#
        '.fs', '.fsx',  # F#
        '.vb',  # Visual Basic
        '.lua',  # Lua
        '.dart',  # Dart
        '.elm',  # Elm
        '.ex', '.exs',  # Elixir
        '.erl', '.hrl',  # Erlang
        '.clj', '.cljs', '.cljc',  # Clojure
        '.groovy',  # Groovy
        '.nim',  # Nim
        '.v',  # V
        '.zig',  # Zig
        # Configuration/Data (text-based only)
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
        '.xml', '.html', '.htm', '.css', '.scss', '.sass', '.less',
        # Documentation
        '.md', '.markdown', '.rst', '.txt', '.adoc', '.org',
        # Build/Config
        'Makefile', 'makefile', 'Dockerfile', 'dockerfile',
        '.gitignore', '.dockerignore', '.eslintrc', '.prettierrc',
        'package.json', 'composer.json', 'cargo.toml', 'go.mod',
        'requirements.txt', 'setup.py', 'pyproject.toml',
    })
    
    include_patterns: Optional[List[str]] = None  # If set, only include these
    
    # Language support
    supported_languages: List[str] = field(default_factory=lambda: [
        'python', 'javascript', 'typescript', 'java', 'go', 
        'rust', 'cpp', 'c', 'ruby', 'php', 'swift', 'kotlin'
    ])
    
    # Git options
    clone_depth: int = 1  # Shallow clone by default
    checkout_branch: Optional[str] = None
    
    # Parsing options
    parse_docstrings: bool = True
    parse_comments: bool = True
    extract_todos: bool = True
    calculate_metrics: bool = True
    parse_timeout: int = 10  # Timeout per file in seconds
    
    # Change detection
    track_versions: bool = True
    mark_deprecated: bool = True
    deprecation_policy: str = "soft"  # "soft" or "hard" (delete vs mark)
    
    # Performance
    max_workers: int = 4
    cache_parsed_files: bool = True
    skip_binary_files: bool = True  # Skip binary files
    
    # Graph options
    link_to_session: bool = True
    create_call_graph: bool = False
    create_import_graph: bool = True
    link_dependencies: bool = True
    
    @classmethod
    def quick_scan(cls) -> 'CodebaseConfig':
        """Quick structure-only scan"""
        return cls(
            mode=AnalysisMode.STRUCTURE,
            calculate_metrics=False,
            parse_docstrings=False,
            parse_comments=False
        )
    
    @classmethod
    def standard_scan(cls) -> 'CodebaseConfig':
        """Standard code analysis"""
        return cls(
            mode=AnalysisMode.STANDARD,
            calculate_metrics=True,
            parse_docstrings=True,
            create_import_graph=True
        )
    
    @classmethod
    def deep_scan(cls) -> 'CodebaseConfig':
        """Deep analysis with metrics and call graphs"""
        return cls(
            mode=AnalysisMode.DEEP,
            calculate_metrics=True,
            create_call_graph=True,
            create_import_graph=True,
            parse_comments=True,
            extract_todos=True
        )
    
    @classmethod
    def full_scan(cls) -> 'CodebaseConfig':
        """Comprehensive analysis"""
        return cls(
            mode=AnalysisMode.FULL,
            calculate_metrics=True,
            create_call_graph=True,
            create_import_graph=True,
            link_dependencies=True,
            parse_docstrings=True,
            parse_comments=True,
            extract_todos=True
        )

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class AnalyzeLocalInput(BaseModel):
    path: str = Field(description="Local directory or file path")
    mode: str = Field(default="standard", description="Analysis mode: structure/shallow/standard/deep/full")
    project_name: Optional[str] = Field(default=None, description="Project name (auto-detected if None)")

class AnalyzeGitRepoInput(BaseModel):
    repo_url: str = Field(description="Git repository URL (https or ssh)")
    branch: Optional[str] = Field(default=None, description="Branch to checkout")
    mode: str = Field(default="standard", description="Analysis mode")
    project_name: Optional[str] = Field(default=None, description="Project name")
    clone_path: Optional[str] = Field(default=None, description="Where to clone (temp if None)")

class AnalyzeCodeTextInput(BaseModel):
    code: str = Field(description="Code text to analyze")
    language: Optional[str] = Field(default=None, description="Language (auto-detect if None)")
    filename: str = Field(default="snippet.txt", description="Virtual filename")
    project_name: str = Field(default="code_snippet", description="Project name")

class UpdateCodebaseInput(BaseModel):
    source: str = Field(description="Local path or Git URL to re-analyze")
    project_id: str = Field(description="Existing project ID to update")
    mark_deprecated: bool = Field(default=True, description="Mark removed entities as deprecated")

class QueryCodebaseInput(BaseModel):
    project_id: str = Field(description="Project ID to query")
    query_type: str = Field(default="summary", description="summary/files/classes/functions/dependencies")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Filter criteria")

class FindEntityInput(BaseModel):
    project_id: Optional[str] = Field(default=None, description="Project to search (all if None)")
    entity_type: str = Field(description="class/function/file/variable")
    name_pattern: str = Field(description="Name or regex pattern")
    include_deprecated: bool = Field(default=False, description="Include deprecated entities")

class DependencyGraphInput(BaseModel):
    project_id: str = Field(description="Project ID")
    start_entity: Optional[str] = Field(default=None, description="Starting entity (entire project if None)")
    depth: int = Field(default=2, description="Traversal depth")
    relationship_types: Optional[List[str]] = Field(default=None, description="Relationship types to include")

# =============================================================================
# INPUT PARSER
# =============================================================================

class CodebaseInputParser:
    """Intelligent input parser for codebase sources"""
    
    @staticmethod
    def parse_source(source: str) -> Dict[str, Any]:
        """
        Parse source and determine type: local path, git URL, or code text
        
        Returns:
            Dict with 'type' and relevant info
        """
        source = source.strip()
        
        # Git URL patterns
        git_patterns = [
            r'^https?://.*\.git$',
            r'^git@.*:.*\.git$',
            r'^https?://github\.com/',
            r'^https?://gitlab\.com/',
            r'^https?://bitbucket\.org/',
        ]
        
        for pattern in git_patterns:
            if re.match(pattern, source, re.IGNORECASE):
                return {
                    'type': 'git',
                    'url': source,
                    'platform': CodebaseInputParser._detect_git_platform(source)
                }
        
        # Check if it's a local path
        path = Path(source)
        if path.exists():
            return {
                'type': 'local',
                'path': str(path.absolute()),
                'is_file': path.is_file(),
                'is_dir': path.is_dir()
            }
        
        # Check if it looks like code
        if CodebaseInputParser._looks_like_code(source):
            language = CodebaseInputParser._detect_language(source)
            return {
                'type': 'code',
                'text': source,
                'language': language
            }
        
        # Default to treating as path (might not exist yet)
        return {
            'type': 'local',
            'path': source,
            'is_file': False,
            'is_dir': False
        }
    
    @staticmethod
    def _detect_git_platform(url: str) -> str:
        """Detect Git hosting platform"""
        if 'github.com' in url:
            return 'github'
        elif 'gitlab.com' in url:
            return 'gitlab'
        elif 'bitbucket.org' in url:
            return 'bitbucket'
        else:
            return 'unknown'
    
    @staticmethod
    def _looks_like_code(text: str) -> bool:
        """Heuristic to detect if text is code"""
        # Check for common code patterns
        code_indicators = [
            r'\bdef\s+\w+\s*\(',  # Python function
            r'\bclass\s+\w+',     # Class definition
            r'\bfunction\s+\w+\s*\(',  # JS function
            r'\bimport\s+',       # Import statement
            r'\bfrom\s+\w+\s+import',  # Python import
            r'\bpublic\s+class',  # Java class
            r'\bpackage\s+\w+',   # Package declaration
            r'=>',                # Arrow function
            r'\{[\s\S]*\}',       # Code blocks
        ]
        
        for pattern in code_indicators:
            if re.search(pattern, text):
                return True
        
        return False
    
    @staticmethod
    def _detect_language(code: str) -> Optional[str]:
        """Auto-detect code language"""
        # Language-specific patterns
        patterns = {
            'python': [r'\bdef\s+\w+\s*\(', r'\bclass\s+\w+.*:', r'^import\s+', r'^from\s+\w+\s+import'],
            'javascript': [r'\bfunction\s+\w+\s*\(', r'\bconst\s+\w+\s*=', r'=>', r'\bvar\s+', r'\blet\s+'],
            'java': [r'\bpublic\s+class', r'\bprivate\s+\w+\s+\w+', r'\bpackage\s+'],
            'go': [r'\bfunc\s+\w+\s*\(', r'\bpackage\s+\w+', r':='],
            'rust': [r'\bfn\s+\w+\s*\(', r'\blet\s+mut', r'\bimpl\s+'],
            'cpp': [r'#include\s*<', r'\bnamespace\s+', r'std::'],
            'ruby': [r'\bdef\s+\w+', r'\bend\s*$', r'\bclass\s+\w+'],
            'php': [r'<\?php', r'\bfunction\s+\w+\s*\(', r'\$\w+'],
        }
        
        scores = defaultdict(int)
        
        for lang, lang_patterns in patterns.items():
            for pattern in lang_patterns:
                if re.search(pattern, code, re.MULTILINE):
                    scores[lang] += 1
        
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return None

# =============================================================================
# FILE HASHER
# =============================================================================

class FileHasher:
    """File content hashing for change detection"""
    
    @staticmethod
    def hash_content(content: str) -> str:
        """Generate SHA256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    @staticmethod
    def hash_file(filepath: Path) -> str:
        """Generate hash of file contents"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return FileHasher.hash_content(content)
        except Exception:
            return ""
    
    @staticmethod
    def is_binary_file(filepath: Path) -> bool:
        """Check if file is binary"""
        try:
            # Read first 8192 bytes
            with open(filepath, 'rb') as f:
                chunk = f.read(8192)
            
            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return True
            
            # Try to decode as text
            try:
                chunk.decode('utf-8')
                return False
            except UnicodeDecodeError:
                return True
        
        except Exception:
            return True

# =============================================================================
# LANGUAGE PARSERS
# =============================================================================

class LanguageParser:
    """Base parser interface"""
    
    def parse(self, code: str, filename: str) -> Dict[str, Any]:
        """
        Parse code and extract structure
        
        Returns:
            {
                'imports': [{'name': str, 'from': str, 'alias': str}],
                'classes': [{
                    'name': str, 'bases': [str], 'line_start': int, 'line_end': int,
                    'methods': [{'name': str, 'params': [str], 'line_start': int}],
                    'docstring': str
                }],
                'functions': [{
                    'name': str, 'params': [str], 'line_start': int, 'line_end': int,
                    'docstring': str, 'is_async': bool
                }],
                'variables': [{'name': str, 'line': int, 'scope': str}],
                'todos': [{'text': str, 'line': int}],
                'metrics': {'loc': int, 'complexity': float, 'maintainability': float}
            }
        """
        raise NotImplementedError

class PythonParser(LanguageParser):
    """Python AST-based parser"""
    
    def parse(self, code: str, filename: str) -> Dict[str, Any]:
        result = {
            'imports': [],
            'classes': [],
            'functions': [],
            'variables': [],
            'todos': [],
            'metrics': {}
        }
        
        try:
            tree = ast.parse(code, filename)
        except SyntaxError as e:
            logger.debug(f"Syntax error in {filename}: {e}")
            return result
        except Exception as e:
            logger.debug(f"Parse error in {filename}: {e}")
            return result
        
        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result['imports'].append({
                        'name': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    result['imports'].append({
                        'from': module,
                        'name': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno
                    })
        
        # Extract top-level definitions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_info = self._parse_class(node, code)
                result['classes'].append(class_info)
            
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_info = self._parse_function(node, code)
                result['functions'].append(func_info)
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        result['variables'].append({
                            'name': target.id,
                            'line': node.lineno,
                            'scope': 'module'
                        })
        
        # Extract TODOs from comments
        result['todos'] = self._extract_todos(code)
        
        # Calculate metrics
        if RADON_AVAILABLE:
            result['metrics'] = self._calculate_metrics(code)
        
        return result
    
    def _parse_class(self, node: ast.ClassDef, code: str) -> Dict[str, Any]:
        """Parse class definition"""
        class_info = {
            'name': node.name,
            'bases': [self._get_name(base) for base in node.bases],
            'line_start': node.lineno,
            'line_end': node.end_lineno or node.lineno,
            'methods': [],
            'class_variables': [],
            'docstring': ast.get_docstring(node)
        }
        
        # Extract methods and class variables
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._parse_function(item, code, is_method=True)
                class_info['methods'].append(method_info)
            
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_info['class_variables'].append({
                            'name': target.id,
                            'line': item.lineno
                        })
        
        return class_info
    
    def _parse_function(self, node, code: str, is_method: bool = False) -> Dict[str, Any]:
        """Parse function/method definition"""
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        
        func_info = {
            'name': node.name,
            'params': params,
            'line_start': node.lineno,
            'line_end': node.end_lineno or node.lineno,
            'docstring': ast.get_docstring(node),
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'is_method': is_method,
            'decorators': [self._get_name(dec) for dec in node.decorator_list]
        }
        
        # Extract function calls
        func_info['calls'] = self._extract_calls(node)
        
        return func_info
    
    def _extract_calls(self, node) -> List[str]:
        """Extract function calls within a function"""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return list(set(calls))
    
    def _get_name(self, node) -> str:
        """Get name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        else:
            return str(node)
    
    def _extract_todos(self, code: str) -> List[Dict[str, Any]]:
        """Extract TODO comments"""
        todos = []
        todo_pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX|NOTE):\s*(.+)', re.IGNORECASE)
        
        for line_num, line in enumerate(code.split('\n'), 1):
            match = todo_pattern.search(line)
            if match:
                todos.append({
                    'type': match.group(1).upper(),
                    'text': match.group(2).strip(),
                    'line': line_num
                })
        
        return todos
    
    def _calculate_metrics(self, code: str) -> Dict[str, Any]:
        """Calculate code metrics using radon"""
        metrics = {}
        
        try:
            # Raw metrics (LOC, SLOC, etc.)
            raw = analyze(code)
            metrics['loc'] = raw.loc
            metrics['sloc'] = raw.sloc
            metrics['comments'] = raw.comments
            metrics['blank'] = raw.blank
            
            # Cyclomatic complexity
            cc = cc_visit(code)
            if cc:
                avg_complexity = sum(c.complexity for c in cc) / len(cc)
                max_complexity = max(c.complexity for c in cc)
                metrics['avg_complexity'] = round(avg_complexity, 2)
                metrics['max_complexity'] = max_complexity
            
            # Maintainability index
            mi = mi_visit(code, multi=True)
            if mi:
                metrics['maintainability'] = round(mi, 2)
            
            # Halstead metrics
            h = h_visit(code)
            if h:
                metrics['halstead_difficulty'] = round(h.difficulty, 2)
                metrics['halstead_effort'] = round(h.effort, 2)
        
        except Exception as e:
            logger.debug(f"Metrics calculation failed: {e}")
        
        return metrics

class JavaScriptParser(LanguageParser):
    """JavaScript/TypeScript parser (regex-based fallback)"""
    
    def parse(self, code: str, filename: str) -> Dict[str, Any]:
        result = {
            'imports': [],
            'classes': [],
            'functions': [],
            'variables': [],
            'todos': [],
            'metrics': {}
        }
        
        try:
            # Extract imports
            import_patterns = [
                r'import\s+(.+?)\s+from\s+["\'](.+?)["\']',
                r'import\s+["\'](.+?)["\']',
                r'const\s+(.+?)\s*=\s*require\(["\'](.+?)["\']\)',
            ]
            
            for pattern in import_patterns:
                for match in re.finditer(pattern, code):
                    result['imports'].append({
                        'name': match.group(1).strip() if match.lastindex >= 1 else '',
                        'from': match.group(2) if match.lastindex >= 2 else match.group(1),
                        'line': code[:match.start()].count('\n') + 1
                    })
            
            # Extract classes
            class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{'
            for match in re.finditer(class_pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                result['classes'].append({
                    'name': match.group(1),
                    'bases': [match.group(2)] if match.group(2) else [],
                    'line_start': line_num,
                    'methods': []
                })
            
            # Extract functions
            func_patterns = [
                r'function\s+(\w+)\s*\(([^)]*)\)',
                r'const\s+(\w+)\s*=\s*\(([^)]*)\)\s*=>',
                r'(\w+)\s*:\s*function\s*\(([^)]*)\)',
            ]
            
            for pattern in func_patterns:
                for match in re.finditer(pattern, code):
                    line_num = code[:match.start()].count('\n') + 1
                    params = [p.strip() for p in match.group(2).split(',') if p.strip()]
                    result['functions'].append({
                        'name': match.group(1),
                        'params': params,
                        'line_start': line_num,
                        'is_async': 'async' in code[max(0, match.start()-10):match.start()]
                    })
            
            # Extract TODOs
            result['todos'] = self._extract_todos(code)
            
            # Basic metrics
            result['metrics'] = {
                'loc': len(code.split('\n')),
                'sloc': len([l for l in code.split('\n') if l.strip()])
            }
        
        except Exception as e:
            logger.debug(f"JS parse error in {filename}: {e}")
        
        return result
    
    def _extract_todos(self, code: str) -> List[Dict[str, Any]]:
        """Extract TODO comments"""
        todos = []
        todo_pattern = re.compile(r'//\s*(TODO|FIXME|HACK|XXX|NOTE):\s*(.+)', re.IGNORECASE)
        
        for line_num, line in enumerate(code.split('\n'), 1):
            match = todo_pattern.search(line)
            if match:
                todos.append({
                    'type': match.group(1).upper(),
                    'text': match.group(2).strip(),
                    'line': line_num
                })
        
        return todos

class GenericParser(LanguageParser):
    """Generic fallback parser for unsupported languages"""
    
    def parse(self, code: str, filename: str) -> Dict[str, Any]:
        """Basic structure extraction"""
        try:
            return {
                'imports': [],
                'classes': self._extract_classes(code),
                'functions': self._extract_functions(code),
                'variables': [],
                'todos': self._extract_todos(code),
                'metrics': {
                    'loc': len(code.split('\n')),
                    'sloc': len([l for l in code.split('\n') if l.strip()])
                }
            }
        except Exception as e:
            logger.debug(f"Generic parse error in {filename}: {e}")
            return {
                'imports': [],
                'classes': [],
                'functions': [],
                'variables': [],
                'todos': [],
                'metrics': {}
            }
    
    def _extract_classes(self, code: str) -> List[Dict[str, Any]]:
        """Extract class-like structures"""
        classes = []
        patterns = [
            r'class\s+(\w+)',
            r'struct\s+(\w+)',
            r'interface\s+(\w+)',
            r'type\s+(\w+)\s+struct',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                classes.append({
                    'name': match.group(1),
                    'line_start': line_num
                })
        
        return classes
    
    def _extract_functions(self, code: str) -> List[Dict[str, Any]]:
        """Extract function-like structures"""
        functions = []
        patterns = [
            r'func\s+(\w+)\s*\(',
            r'fn\s+(\w+)\s*\(',
            r'def\s+(\w+)\s*\(',
            r'function\s+(\w+)\s*\(',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                functions.append({
                    'name': match.group(1),
                    'line_start': line_num
                })
        
        return functions
    
    def _extract_todos(self, code: str) -> List[Dict[str, Any]]:
        """Extract TODO comments"""
        todos = []
        patterns = [
            r'//\s*(TODO|FIXME|HACK|XXX|NOTE):\s*(.+)',
            r'#\s*(TODO|FIXME|HACK|XXX|NOTE):\s*(.+)',
            r'/\*\s*(TODO|FIXME|HACK|XXX|NOTE):\s*(.+?)\*/',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_num = code[:match.start()].count('\n') + 1
                todos.append({
                    'type': match.group(1).upper(),
                    'text': match.group(2).strip(),
                    'line': line_num
                })
        
        return todos

# =============================================================================
# PARSER FACTORY
# =============================================================================

class ParserFactory:
    """Factory to get appropriate parser for language"""
    
    PARSERS = {
        'python': PythonParser,
        'javascript': JavaScriptParser,
        'typescript': JavaScriptParser,
    }
    
    @staticmethod
    def get_parser(language: str) -> LanguageParser:
        """Get parser for language"""
        parser_class = ParserFactory.PARSERS.get(language.lower(), GenericParser)
        return parser_class()
    
    @staticmethod
    def detect_language(filepath: Path) -> Optional[str]:
        """Detect language from file extension"""
        ext_map = {
            '.py': 'python', '.pyw': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
            '.c': 'c',
            '.h': 'c', '.hpp': 'cpp', '.hxx': 'cpp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin', '.kts': 'kotlin',
            '.scala': 'scala',
            '.sh': 'shell', '.bash': 'shell',
            '.cs': 'csharp',
            '.lua': 'lua',
            '.dart': 'dart',
        }
        
        return ext_map.get(filepath.suffix.lower())

# =============================================================================
# FILE SCANNER
# =============================================================================

class FileScanner:
    """Scan directory structure and files"""
    
    def __init__(self, config: CodebaseConfig):
        self.config = config
    
    def scan_directory(self, root_path: Path) -> Iterator[Dict[str, Any]]:
        """
        Scan directory and yield file information
        
        Yields:
            {
                'path': Path,
                'relative_path': str,
                'type': 'file'/'directory',
                'size': int,
                'language': str,
                'hash': str
            }
        """
        root_path = Path(root_path)
        
        if not root_path.exists():
            logger.error(f"Path does not exist: {root_path}")
            return
        
        if root_path.is_file():
            # Single file
            if self._should_parse_file(root_path):
                yield self._file_info(root_path, root_path.parent)
            return
        
        # Directory traversal
        for item in root_path.rglob('*'):
            # Skip excluded patterns
            if self._should_exclude(item, root_path):
                continue
            
            # Check include patterns
            if self.config.include_patterns:
                if not self._should_include(item, root_path):
                    continue
            
            if item.is_file():
                # Check if we should parse this file
                if not self._should_parse_file(item):
                    continue
                
                # Check file size
                try:
                    if item.stat().st_size > self.config.max_file_size:
                        logger.debug(f"Skipping large file: {item}")
                        continue
                except:
                    continue
                
                yield self._file_info(item, root_path)
            
            elif item.is_dir():
                yield {
                    'path': item,
                    'relative_path': str(item.relative_to(root_path)),
                    'type': 'directory',
                    'name': item.name
                }
    
    def _should_parse_file(self, filepath: Path) -> bool:
        """Check if file should be parsed"""
        # Check extension whitelist
        ext = filepath.suffix.lower()
        name = filepath.name.lower()
        
        # Special files without extensions
        special_files = {'makefile', 'dockerfile', 'rakefile', 'gemfile'}
        if name in special_files:
            return True
        
        # Check if extension is in whitelist
        if ext not in self.config.code_extensions:
            return False
        
        # Skip binary files
        if self.config.skip_binary_files:
            if FileHasher.is_binary_file(filepath):
                logger.debug(f"Skipping binary file: {filepath}")
                return False
        
        return True
    
    def _file_info(self, filepath: Path, root: Path) -> Dict[str, Any]:
        """Get file information"""
        language = ParserFactory.detect_language(filepath)
        
        # Only hash text files
        file_hash = ""
        if language or filepath.suffix in ['.txt', '.md', '.json', '.xml', '.yaml', '.yml', '.rst']:
            file_hash = FileHasher.hash_file(filepath)
        
        try:
            modified = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
            size = filepath.stat().st_size
        except:
            modified = datetime.now().isoformat()
            size = 0
        
        return {
            'path': filepath,
            'relative_path': str(filepath.relative_to(root)),
            'type': 'file',
            'name': filepath.name,
            'size': size,
            'language': language,
            'hash': file_hash,
            'modified': modified
        }
    
    def _should_exclude(self, path: Path, root: Path) -> bool:
        """Check if path matches exclude patterns"""
        relative = path.relative_to(root)
        path_str = str(relative)
        
        for pattern in self.config.exclude_patterns:
            # Simple glob-like matching
            if pattern.startswith('*'):
                if path_str.endswith(pattern[1:]) or path.name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                if path_str.startswith(pattern[:-1]) or path.name.startswith(pattern[:-1]):
                    return True
            else:
                if pattern in path.parts or path.name == pattern:
                    return True
        
        return False
    
    def _should_include(self, path: Path, root: Path) -> bool:
        """Check if path matches include patterns"""
        relative = path.relative_to(root)
        path_str = str(relative)
        
        for pattern in self.config.include_patterns:
            if pattern.startswith('*'):
                if path_str.endswith(pattern[1:]) or path.name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                if path_str.startswith(pattern[:-1]) or path.name.startswith(pattern[:-1]):
                    return True
            else:
                if pattern in path.parts or path.name == pattern:
                    return True
        
        return False

# =============================================================================
# GIT HANDLER
# =============================================================================

class GitHandler:
    """Git repository operations"""
    
    def __init__(self, config: CodebaseConfig):
        self.config = config
        if not GIT_AVAILABLE:
            raise ImportError("GitPython required. Install: pip install gitpython")
        self.repo_info = {}
    
    def clone_repo(self, repo_url: str, target_path: Path, 
                   branch: Optional[str] = None) -> Path:
        """Clone Git repository"""
        logger.info(f"Cloning repository: {repo_url}")
        
        clone_kwargs = {
            'depth': self.config.clone_depth,
        }
        
        if branch:
            clone_kwargs['branch'] = branch
        
        try:
            repo = git.Repo.clone_from(repo_url, target_path, **clone_kwargs)
            logger.info(f"Cloned to: {target_path}")
            
            # Get repo info
            self.repo_info = {
                'url': repo_url,
                'branch': repo.active_branch.name,
                'commit': repo.head.commit.hexsha,
                'commit_message': repo.head.commit.message.strip(),
                'commit_date': datetime.fromtimestamp(repo.head.commit.committed_date).isoformat(),
            }
            
            return target_path
        
        except Exception as e:
            logger.error(f"Clone failed: {e}")
            raise
    
    def get_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL"""
        # https://github.com/user/repo.git -> repo
        # Handle trailing slash
        repo_url = repo_url.rstrip('/')
        
        match = re.search(r'/([^/]+?)(?:\.git)?$', repo_url)
        if match:
            return match.group(1)
        return "unknown"

# =============================================================================
# CODEBASE MAPPER - MAIN ORCHESTRATOR
# =============================================================================

class CodebaseMapper:
    """
    Main orchestrator for codebase analysis with graph integration
    """
    
    def __init__(self, agent, config: CodebaseConfig):
        self.agent = agent
        self.config = config
        
        self.scanner = FileScanner(config)
        self.git_handler = GitHandler(config) if GIT_AVAILABLE else None
        
        # Tracking
        self.project_node_id = None
        self.current_entities = {}  # Track entities in current scan
        self.previous_entities = {}  # Track entities from previous scan
        
        # Stats
        self.stats = {
            'files_scanned': 0,
            'files_parsed': 0,
            'files_skipped': 0,
            'files_timeout': 0,
            'classes_found': 0,
            'functions_found': 0,
            'errors': 0
        }
    
    def _initialize_project(self, project_name: str, source_type: str, 
                           source_location: str, metadata: Optional[Dict] = None) -> str:
        """Initialize or get existing project node"""
        project_id = f"project_{project_name.replace(' ', '_').replace('-', '_').lower()}"
        
        try:
            # Check if project exists
            existing = self.agent.mem.get_entity(project_id)
            
            if existing:
                logger.info(f"Using existing project: {project_id}")
                self.project_node_id = project_id
                
                # Load previous entities for comparison
                self._load_previous_entities(project_id)
                
                return project_id
        except:
            pass
        
        # Create new project
        properties = {
            'name': project_name,
            'source_type': source_type,
            'source_location': source_location,
            'created_at': datetime.now().isoformat(),
            'last_scanned': datetime.now().isoformat(),
        }
        
        if metadata:
            properties.update(metadata)
        
        try:
            self.agent.mem.upsert_entity(
                project_id,
                "codebase_project",
                labels=["CodebaseProject", "Project"],
                properties=properties
            )
            
            # Link to session
            if self.config.link_to_session:
                self.agent.mem.link(
                    self.agent.sess.id,
                    project_id,
                    "ANALYZED_CODEBASE",
                    {'timestamp': datetime.now().isoformat()}
                )
        except Exception as e:
            logger.error(f"Failed to create project node: {e}")
        
        self.project_node_id = project_id
        return project_id
    
    def _load_previous_entities(self, project_id: str):
        """Load existing entities for change detection"""
        try:
            # Query all entities linked to project
            query = """
            MATCH (p:CodebaseProject {id: $project_id})-[*1..5]->(e)
            WHERE NOT 'deprecated' IN labels(e)
            RETURN e.id as id, e.entity_type as type, e.content_hash as hash
            """
            
            results = self.agent.mem.query(query, {'project_id': project_id})
            
            for record in results:
                entity_id = record.get('id')
                if entity_id:
                    self.previous_entities[entity_id] = {
                        'type': record.get('type'),
                        'hash': record.get('content_hash')
                    }
            
            logger.info(f"Loaded {len(self.previous_entities)} previous entities")
        
        except Exception as e:
            logger.debug(f"Could not load previous entities: {e}")
    
    def _mark_deprecated_entities(self):
        """Mark entities that no longer exist as deprecated"""
        if not self.config.mark_deprecated:
            return
        
        deprecated_count = 0
        
        for entity_id, entity_info in self.previous_entities.items():
            if entity_id not in self.current_entities:
                # Entity no longer exists
                try:
                    if self.config.deprecation_policy == "hard":
                        # Delete entity
                        self.agent.mem.delete_entity(entity_id)
                    else:
                        # Mark as deprecated
                        self.agent.mem.add_label(entity_id, "deprecated")
                        self.agent.mem.update_entity_properties(
                            entity_id,
                            {'deprecated_at': datetime.now().isoformat()}
                        )
                    
                    deprecated_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to deprecate entity {entity_id}: {e}")
        
        if deprecated_count > 0:
            logger.info(f"Marked {deprecated_count} entities as deprecated")
    
    def _create_file_node(self, file_info: Dict[str, Any]) -> str:
        """Create or update file node"""
        filepath = file_info['relative_path']
        file_id = f"{self.project_node_id}_file_{hashlib.md5(filepath.encode()).hexdigest()[:12]}"
        
        properties = {
            'filename': file_info['name'],
            'filepath': filepath,
            'size': file_info['size'],
            'language': file_info.get('language'),
            'content_hash': file_info.get('hash', ''),
            'last_modified': file_info.get('modified'),
            'scanned_at': datetime.now().isoformat(),
        }
        
        try:
            self.agent.mem.upsert_entity(
                file_id,
                "code_file",
                labels=["CodeFile", "File"],
                properties=properties
            )
            
            # Link to project
            self.agent.mem.link(
                self.project_node_id,
                file_id,
                "CONTAINS_FILE",
                {'filepath': filepath}
            )
            
            # Handle directory structure
            if '/' in filepath:
                parent_dir = str(Path(filepath).parent)
                if parent_dir != '.':
                    dir_id = self._create_directory_node(parent_dir)
                    self.agent.mem.link(
                        dir_id,
                        file_id,
                        "CONTAINS",
                        {}
                    )
        
        except Exception as e:
            logger.error(f"Failed to create file node: {e}")
        
        self.current_entities[file_id] = properties
        return file_id
    
    def _create_directory_node(self, dirpath: str) -> str:
        """Create directory node"""
        dir_id = f"{self.project_node_id}_dir_{hashlib.md5(dirpath.encode()).hexdigest()[:12]}"
        
        if dir_id in self.current_entities:
            return dir_id
        
        properties = {
            'dirpath': dirpath,
            'dirname': Path(dirpath).name,
        }
        
        try:
            self.agent.mem.upsert_entity(
                dir_id,
                "code_directory",
                labels=["CodeDirectory", "Directory"],
                properties=properties
            )
            
            # Link to project
            self.agent.mem.link(
                self.project_node_id,
                dir_id,
                "CONTAINS_DIRECTORY",
                {'dirpath': dirpath}
            )
            
            # Handle parent directory
            if '/' in dirpath:
                parent_dir = str(Path(dirpath).parent)
                if parent_dir != '.':
                    parent_id = self._create_directory_node(parent_dir)
                    self.agent.mem.link(
                        parent_id,
                        dir_id,
                        "CONTAINS",
                        {}
                    )
        
        except Exception as e:
            logger.error(f"Failed to create directory node: {e}")
        
        self.current_entities[dir_id] = properties
        return dir_id
    
    def _create_class_node(self, file_id: str, class_info: Dict[str, Any]) -> str:
        """Create class node"""
        class_name = class_info['name']
        class_id = f"{file_id}_class_{hashlib.md5(class_name.encode()).hexdigest()[:12]}"
        
        properties = {
            'class_name': class_name,
            'base_classes': class_info.get('bases', []),
            'line_start': class_info.get('line_start'),
            'line_end': class_info.get('line_end'),
            'docstring': class_info.get('docstring', '')[:500] if class_info.get('docstring') else '',
            'scanned_at': datetime.now().isoformat(),
        }
        
        try:
            self.agent.mem.upsert_entity(
                class_id,
                "code_class",
                labels=["CodeClass", "Class"],
                properties=properties
            )
            
            # Link to file
            self.agent.mem.link(
                file_id,
                class_id,
                "DEFINES_CLASS",
                {'class_name': class_name}
            )
        
        except Exception as e:
            logger.error(f"Failed to create class node: {e}")
        
        self.current_entities[class_id] = properties
        self.stats['classes_found'] += 1
        return class_id
    
    def _create_function_node(self, parent_id: str, func_info: Dict[str, Any],
                             parent_type: str = "file") -> str:
        """Create function/method node"""
        func_name = func_info['name']
        func_id = f"{parent_id}_func_{hashlib.md5(func_name.encode()).hexdigest()[:12]}"
        
        properties = {
            'function_name': func_name,
            'parameters': func_info.get('params', []),
            'line_start': func_info.get('line_start'),
            'line_end': func_info.get('line_end'),
            'is_async': func_info.get('is_async', False),
            'is_method': func_info.get('is_method', False),
            'decorators': func_info.get('decorators', []),
            'docstring': func_info.get('docstring', '')[:500] if func_info.get('docstring') else '',
            'scanned_at': datetime.now().isoformat(),
        }
        
        try:
            entity_type = "code_method" if func_info.get('is_method') else "code_function"
            labels = ["CodeFunction", "Function"]
            if func_info.get('is_method'):
                labels.append("Method")
            
            self.agent.mem.upsert_entity(
                func_id,
                entity_type,
                labels=labels,
                properties=properties
            )
            
            # Link to parent (file or class)
            rel_type = "DEFINES_METHOD" if func_info.get('is_method') else "DEFINES_FUNCTION"
            self.agent.mem.link(
                parent_id,
                func_id,
                rel_type,
                {'function_name': func_name}
            )
        
        except Exception as e:
            logger.error(f"Failed to create function node: {e}")
        
        self.current_entities[func_id] = properties
        self.stats['functions_found'] += 1
        return func_id
    
    def _create_import_node(self, file_id: str, import_info: Dict[str, Any]):
        """Create import relationship"""
        if not self.config.create_import_graph:
            return
        
        try:
            module_name = import_info.get('from') or import_info.get('name')
            if not module_name:
                return
            
            # Create or get module node
            module_id = f"module_{hashlib.md5(module_name.encode()).hexdigest()[:12]}"
            
            self.agent.mem.upsert_entity(
                module_id,
                "code_module",
                labels=["CodeModule", "Module"],
                properties={'module_name': module_name}
            )
            
            # Create import relationship
            self.agent.mem.link(
                file_id,
                module_id,
                "IMPORTS",
                {
                    'imported_name': import_info.get('name'),
                    'alias': import_info.get('alias'),
                    'line': import_info.get('line')
                }
            )
        
        except Exception as e:
            logger.debug(f"Failed to create import node: {e}")
    
    def _parse_file_with_timeout(self, filepath: Path, language: str, filename: str) -> Optional[Dict[str, Any]]:
        """Parse file with timeout protection"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            # Parse code with timeout
            parser = ParserFactory.get_parser(language)
            
            # Simple timeout approach - just wrap in try/except and return on any long operation
            try:
                parsed = parser.parse(code, filename)
                return parsed
            except TimeoutException:
                logger.warning(f"Parsing timeout: {filename}")
                self.stats['files_timeout'] += 1
                return None
            
        except Exception as e:
            logger.debug(f"Error reading/parsing {filename}: {e}")
            self.stats['errors'] += 1
            return None
    
    # =========================================================================
    # ANALYSIS OPERATIONS
    # =========================================================================
    
    def analyze_local(self, path: str, mode: str = "standard",
                     project_name: Optional[str] = None) -> Iterator[str]:
        """Analyze local directory or file"""
        
        source_path = Path(path)
        
        if not source_path.exists():
            yield f"Error: Path does not exist: {path}\n"
            return
        
        # Auto-detect project name
        if not project_name:
            if source_path.is_file():
                project_name = source_path.stem
            else:
                project_name = source_path.name
        
        # Initialize project
        self._initialize_project(
            project_name,
            "local",
            str(source_path.absolute()),
            {'analysis_mode': mode}
        )
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              CODEBASE ANALYSIS - LOCAL                       ║\n"
        yield f"║              Project: {project_name:^30}            ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Path: {source_path}\n"
        yield f"  Mode: {mode}\n\n"
        
        # Scan files
        yield f"[1/3] SCANNING FILE STRUCTURE\n{'─' * 60}\n"
        
        files_to_parse = []
        
        for item in self.scanner.scan_directory(source_path):
            if item['type'] == 'file':
                self.stats['files_scanned'] += 1
                
                file_id = self._create_file_node(item)
                
                # Queue for parsing if it's a code file
                if item.get('language'):
                    files_to_parse.append((file_id, item))
                
                if self.stats['files_scanned'] % 100 == 0:
                    yield f"  Scanned {self.stats['files_scanned']} files...\n"
        
        yield f"  Total files: {self.stats['files_scanned']}\n"
        yield f"  Code files: {len(files_to_parse)}\n\n"
        
        # Parse code files
        if mode != "structure" and files_to_parse:
            yield f"[2/3] PARSING CODE STRUCTURE\n{'─' * 60}\n"
            
            for file_id, file_info in files_to_parse:
                try:
                    filepath = source_path / file_info['relative_path']
                    language = file_info['language']
                    
                    # Parse with timeout protection
                    parsed = self._parse_file_with_timeout(filepath, language, file_info['name'])
                    
                    if parsed is None:
                        self.stats['files_skipped'] += 1
                        continue
                    
                    # Create nodes
                    for import_info in parsed.get('imports', []):
                        self._create_import_node(file_id, import_info)
                    
                    for class_info in parsed.get('classes', []):
                        class_id = self._create_class_node(file_id, class_info)
                        
                        # Methods
                        for method_info in class_info.get('methods', []):
                            self._create_function_node(class_id, method_info, "class")
                    
                    for func_info in parsed.get('functions', []):
                        self._create_function_node(file_id, func_info, "file")
                    
                    self.stats['files_parsed'] += 1
                    
                    if self.stats['files_parsed'] % 20 == 0:
                        yield f"  Parsed {self.stats['files_parsed']}/{len(files_to_parse)} files...\n"
                
                except Exception as e:
                    self.stats['errors'] += 1
                    logger.debug(f"Error processing {file_info['name']}: {e}")
            
            yield f"  Parsed: {self.stats['files_parsed']}\n"
            yield f"  Skipped: {self.stats['files_skipped']}\n"
            yield f"  Classes: {self.stats['classes_found']}\n"
            yield f"  Functions: {self.stats['functions_found']}\n"
            if self.stats['files_timeout'] > 0:
                yield f"  Timeouts: {self.stats['files_timeout']}\n"
            yield "\n"
        
        # Mark deprecated entities
        if self.previous_entities:
            yield f"[3/3] UPDATING ENTITY STATUS\n{'─' * 60}\n"
            self._mark_deprecated_entities()
            yield f"  Change detection complete\n\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   ANALYSIS COMPLETE                          ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
        yield f"  Project ID: {self.project_node_id}\n"
        yield f"  Files: {self.stats['files_scanned']}\n"
        yield f"  Parsed: {self.stats['files_parsed']}\n"
        yield f"  Classes: {self.stats['classes_found']}\n"
        yield f"  Functions: {self.stats['functions_found']}\n"
        if self.stats['errors'] > 0:
            yield f"  Errors: {self.stats['errors']}\n"
    
    def analyze_git_repo(self, repo_url: str, branch: Optional[str] = None,
                        mode: str = "standard", project_name: Optional[str] = None,
                        clone_path: Optional[str] = None) -> Iterator[str]:
        """Analyze Git repository"""
        
        if not self.git_handler:
            yield "Error: GitPython not available. Install: pip install gitpython\n"
            return
        
        # Auto-detect project name
        if not project_name:
            project_name = self.git_handler.get_repo_name(repo_url)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              CODEBASE ANALYSIS - GIT REPO                    ║\n"
        yield f"║              Project: {project_name:^30}            ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Repository: {repo_url}\n"
        yield f"  Branch: {branch or 'default'}\n\n"
        
        # Clone repository
        yield f"[1/4] CLONING REPOSITORY\n{'─' * 60}\n"
        
        import tempfile
        import shutil
        
        if not clone_path:
            temp_dir = tempfile.mkdtemp(prefix=f"vera_codebase_{project_name}_")
            clone_path = temp_dir
        else:
            temp_dir = None
        
        try:
            target_path = self.git_handler.clone_repo(repo_url, Path(clone_path), branch)
            yield f"  Cloned to: {target_path}\n"
            yield f"  Commit: {self.git_handler.repo_info['commit'][:8]}\n\n"
            
            # Initialize project with Git metadata
            self._initialize_project(
                project_name,
                "git",
                repo_url,
                {
                    'analysis_mode': mode,
                    'git_url': repo_url,
                    'git_branch': self.git_handler.repo_info['branch'],
                    'git_commit': self.git_handler.repo_info['commit'],
                    'git_commit_date': self.git_handler.repo_info['commit_date'],
                }
            )
            
            # Now analyze the cloned repository
            for chunk in self.analyze_local(
                path=str(target_path),
                mode=mode,
                project_name=project_name
            ):
                yield chunk
        
        except Exception as e:
            yield f"Error: {e}\n"
            logger.error(f"Git analysis failed: {e}", exc_info=True)
        
        finally:
            # Cleanup temp directory if we created one
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
    
    def analyze_code_text(self, code: str, language: Optional[str] = None,
                         filename: str = "snippet.txt",
                         project_name: str = "code_snippet") -> Iterator[str]:
        """Analyze code text directly"""
        
        # Auto-detect language
        if not language:
            language = CodebaseInputParser._detect_language(code)
            if not language:
                language = "unknown"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              CODEBASE ANALYSIS - CODE TEXT                   ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Language: {language}\n"
        yield f"  Filename: {filename}\n\n"
        
        # Initialize project
        self._initialize_project(
            project_name,
            "text",
            "direct_input",
            {'language': language, 'filename': filename}
        )
        
        # Create file node
        file_info = {
            'name': filename,
            'relative_path': filename,
            'size': len(code),
            'language': language,
            'hash': FileHasher.hash_content(code),
            'modified': datetime.now().isoformat()
        }
        
        file_id = self._create_file_node(file_info)
        
        # Parse code
        yield f"PARSING CODE\n{'─' * 60}\n"
        
        try:
            parser = ParserFactory.get_parser(language)
            parsed = parser.parse(code, filename)
            
            # Create nodes
            for import_info in parsed.get('imports', []):
                self._create_import_node(file_id, import_info)
            
            for class_info in parsed.get('classes', []):
                class_id = self._create_class_node(file_id, class_info)
                
                for method_info in class_info.get('methods', []):
                    self._create_function_node(class_id, method_info, "class")
            
            for func_info in parsed.get('functions', []):
                self._create_function_node(file_id, func_info, "file")
            
            yield f"  Classes: {len(parsed.get('classes', []))}\n"
            yield f"  Functions: {len(parsed.get('functions', []))}\n"
            yield f"  Imports: {len(parsed.get('imports', []))}\n"
            
            if parsed.get('metrics'):
                yield f"\n  METRICS:\n"
                for key, value in parsed['metrics'].items():
                    yield f"    {key}: {value}\n"
        
        except Exception as e:
            yield f"Error parsing code: {e}\n"
            logger.error(f"Parse error: {e}", exc_info=True)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Analysis Complete\n"
        yield f"  Project ID: {self.project_node_id}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"

# =============================================================================
# TOOL INTEGRATION
# =============================================================================

def add_codebase_analysis_tools(tool_list: List, agent):
    """Add codebase analysis tools to agent"""
    from langchain_core.tools import StructuredTool
    
    def analyze_local_wrapper(path: str, mode: str = "standard",
                             project_name: Optional[str] = None):
        config = CodebaseConfig.standard_scan()
        if mode == "quick" or mode == "structure":
            config = CodebaseConfig.quick_scan()
        elif mode == "deep":
            config = CodebaseConfig.deep_scan()
        elif mode == "full":
            config = CodebaseConfig.full_scan()
        
        mapper = CodebaseMapper(agent, config)
        for chunk in mapper.analyze_local(path, mode, project_name):
            yield chunk
    
    def analyze_git_repo_wrapper(repo_url: str, branch: Optional[str] = None,
                                mode: str = "standard", project_name: Optional[str] = None,
                                clone_path: Optional[str] = None):
        config = CodebaseConfig.standard_scan()
        if mode == "quick" or mode == "structure":
            config = CodebaseConfig.quick_scan()
        elif mode == "deep":
            config = CodebaseConfig.deep_scan()
        elif mode == "full":
            config = CodebaseConfig.full_scan()
        
        mapper = CodebaseMapper(agent, config)
        for chunk in mapper.analyze_git_repo(repo_url, branch, mode, project_name, clone_path):
            yield chunk
    
    def analyze_code_text_wrapper(code: str, language: Optional[str] = None,
                                 filename: str = "snippet.txt",
                                 project_name: str = "code_snippet"):
        config = CodebaseConfig.deep_scan()
        mapper = CodebaseMapper(agent, config)
        for chunk in mapper.analyze_code_text(code, language, filename, project_name):
            yield chunk
    
    tool_list.extend([
        StructuredTool.from_function(
            func=analyze_local_wrapper,
            name="analyze_local_codebase",
            description=(
                "Analyze local directory or file. ONLY parses code and documentation files, "
                "skips binary files, databases, vector stores, media files. "
                "Creates hierarchical graph structure: Project → Directories → Files → Classes → Functions. "
                "Supports change detection and deprecation marking. "
                "Modes: structure (files only), standard (+ parsing), deep (+ metrics), full (+ call graphs)"
            ),
            args_schema=AnalyzeLocalInput
        ),
        
        StructuredTool.from_function(
            func=analyze_git_repo_wrapper,
            name="analyze_git_repository",
            description=(
                "Clone and analyze Git repository. ONLY parses code/docs, skips binaries and databases. "
                "Supports GitHub, GitLab, Bitbucket. Creates full codebase graph with version tracking. "
                "Auto-detects project name from repo URL. Temporary clone by default."
            ),
            args_schema=AnalyzeGitRepoInput
        ),
        
        StructuredTool.from_function(
            func=analyze_code_text_wrapper,
            name="analyze_code_snippet",
            description=(
                "Analyze code text directly. Auto-detects language. "
                "Extracts classes, functions, imports. Calculates metrics. "
                "Useful for analyzing pasted code or generated snippets."
            ),
            args_schema=AnalyzeCodeTextInput
        ),
    ])
    
    return tool_list

if __name__ == "__main__":
    print("Comprehensive Codebase Analysis Toolkit")
    print("✓ Local directory/file analysis")
    print("✓ Git repository cloning and analysis")
    print("✓ Direct code text processing")
    print("✓ Multi-language support (Python, JS, Java, Go, etc.)")
    print("✓ Hierarchical graph structure")
    print("✓ ONLY parses code/docs - skips binaries, DBs, vector stores")
    print("✓ Automatic deprecation marking")
    print("✓ Change detection and version tracking")
    print("✓ Timeout protection prevents freezing")
    print("✓ Code metrics and complexity analysis")
    print("✓ Import/dependency tracking")
    print("✓ Full graph memory integration")
    print("✓ Tool chaining compatible")