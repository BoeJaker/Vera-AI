# -----------------------------
# Enhanced NLP Extraction Engine - FIXED VERSION
# -----------------------------

import re
import ast
import uuid
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from urllib.parse import urlparse
import spacy
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
import numpy as np
from collections import defaultdict
from dataclasses import dataclass, field
import os
import hashlib
import time

@dataclass
class ExtractedEntity:
    text: str
    label: str
    span: Tuple[int, int]
    confidence: float
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])  # Unique ID per entity
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_unique_key(self) -> str:
        """Get a unique composite key for this entity"""
        return f"{self.label}:{self.text}@{self.span[0]}"
    
    def get_stable_id(self) -> str:
        """Get a stable ID based on content and position"""
        unique_key = f"{self.text}@{self.span[0]}"
        return f"entity_{hashlib.md5(unique_key.encode('utf-8')).hexdigest()[:8]}"

@dataclass
class ExtractedRelation:
    head: str  # Entity text (for human readability)
    tail: str  # Entity text (for human readability)
    relation: str
    confidence: float
    context: str
    head_id: Optional[str] = None  # Entity ID reference
    tail_id: Optional[str] = None  # Entity ID reference
    metadata: Dict[str, Any] = field(default_factory=dict)


class PatternExtractor:
    """Extract structured patterns like URLs, emails, dates, etc."""
    
    # Comprehensive regex patterns
    PATTERNS = {
        'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'URL': r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&/=]*',
        'IPV4': r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        'IPV6': r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
        'PHONE': r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
        'CREDIT_CARD': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
        'HASH_MD5': r'\b[a-fA-F0-9]{32}\b',
        'HASH_SHA1': r'\b[a-fA-F0-9]{40}\b',
        'HASH_SHA256': r'\b[a-fA-F0-9]{64}\b',
        'UUID': r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
        'SEMANTIC_VERSION': r'\bv?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?\b',
        'HEX_COLOR': r'\B#(?:[0-9a-fA-F]{3}){1,2}\b',
        'FILE_PATH_UNIX': r'(?:/[a-zA-Z0-9_.-]+)+/?',
        'FILE_PATH_WINDOWS': r'[A-Za-z]:\\(?:[^\\\/:*?"<>|\r\n]+\\)*[^\\\/:*?"<>|\r\n]*',
        'DOCKER_IMAGE': r'\b[a-z0-9]+(?:[._-][a-z0-9]+)*/[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[a-z0-9]+(?:[._-][a-z0-9]+)*)?\b',
        'GIT_COMMIT': r'\b[0-9a-f]{7,40}\b',
        'JWT_TOKEN': r'\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b',
        'CURRENCY': r'\$\s*\d+(?:,\d{3})*(?:\.\d{2})?|\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|JPY|CAD|AUD)',
        'PERCENTAGE': r'\b\d+(?:\.\d+)?%',
        'MEASUREMENT': r'\b\d+(?:\.\d+)?\s*(?:mm|cm|m|km|in|ft|yd|mi|g|kg|lb|oz|ml|l|gal|mph|kmh|°C|°F|K)\b',
    }
    
    # Date patterns (multiple formats)
    DATE_PATTERNS = [
        (r'\b\d{4}-\d{2}-\d{2}\b', '%Y-%m-%d'),
        (r'\b\d{2}/\d{2}/\d{4}\b', '%m/%d/%Y'),
        (r'\b\d{2}-\d{2}-\d{4}\b', '%d-%m-%Y'),
        (r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b', None),
        (r'\b\d{4}/\d{2}/\d{2}\b', '%Y/%m/%d'),
    ]
    
    # Date range patterns
    DATE_RANGE_PATTERNS = [
        r'\b\d{4}-\d{2}-\d{2}\s+(?:to|through|until|-|–)\s+\d{4}-\d{2}-\d{2}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\s+(?:to|through|-|–)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
    ]
    
    def extract_patterns(self, text: str) -> List[ExtractedEntity]:
        """Extract all pattern-based entities"""
        entities = []
        seen_spans = set()
        
        for label, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = (match.start(), match.end())
                if span not in seen_spans:
                    metadata = self._enrich_metadata(label, match.group())
                    entities.append(ExtractedEntity(
                        text=match.group(),
                        label=label,
                        span=span,
                        confidence=0.95,
                        metadata=metadata
                    ))
                    seen_spans.add(span)
        
        entities.extend(self._extract_dates(text, seen_spans))
        entities.extend(self._extract_date_ranges(text, seen_spans))
        
        return entities
    
    def _extract_dates(self, text: str, seen_spans: Set) -> List[ExtractedEntity]:
        """Extract and parse dates"""
        entities = []
        for pattern, date_format in self.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = (match.start(), match.end())
                if span not in seen_spans:
                    date_str = match.group()
                    parsed_date = self._parse_date(date_str, date_format)
                    metadata = {'parsed': parsed_date} if parsed_date else {}
                    
                    entities.append(ExtractedEntity(
                        text=date_str,
                        label='DATE',
                        span=span,
                        confidence=0.9,
                        metadata=metadata
                    ))
                    seen_spans.add(span)
        return entities
    
    def _extract_date_ranges(self, text: str, seen_spans: Set) -> List[ExtractedEntity]:
        """Extract date ranges"""
        entities = []
        for pattern in self.DATE_RANGE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = (match.start(), match.end())
                if span not in seen_spans:
                    entities.append(ExtractedEntity(
                        text=match.group(),
                        label='DATE_RANGE',
                        span=span,
                        confidence=0.9,
                        metadata={'type': 'temporal_range'}
                    ))
                    seen_spans.add(span)
        return entities
    
    def _parse_date(self, date_str: str, date_format: Optional[str]) -> Optional[str]:
        """Parse date string into ISO format"""
        if not date_format:
            for fmt in ['%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%b %d %Y']:
                try:
                    return datetime.strptime(date_str, fmt).isoformat()
                except:
                    continue
            return None
        
        try:
            return datetime.strptime(date_str, date_format).isoformat()
        except:
            return None
    
    def _enrich_metadata(self, label: str, text: str) -> Dict[str, Any]:
        """Add contextual metadata based on entity type"""
        metadata = {}
        
        if label == 'URL':
            try:
                parsed = urlparse(text)
                metadata = {
                    'domain': parsed.netloc,
                    'scheme': parsed.scheme,
                    'path': parsed.path,
                    'has_query': bool(parsed.query)
                }
            except:
                pass
        
        elif label == 'EMAIL':
            parts = text.split('@')
            if len(parts) == 2:
                metadata = {
                    'username': parts[0],
                    'domain': parts[1]
                }
        
        elif label in ['HASH_MD5', 'HASH_SHA1', 'HASH_SHA256']:
            metadata = {'hash_type': label.split('_')[1].lower()}
        
        elif label == 'SEMANTIC_VERSION':
            metadata = {'is_prerelease': '-' in text}
        
        return metadata


class PythonCodeParser:
    """Parse Python code into relational graph with proper position tracking"""
    
    def parse(self, code: str) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """Parse Python code using AST with character position tracking"""
        entities = []
        relations = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"Syntax error parsing code: {e}")
            return [], []
        
        # Build line offset map for character position conversion
        line_offsets = self._build_line_offsets(code)
        
        # Track all definitions for cross-referencing
        definitions = {}  # name -> entity
        
        try:
            # Extract class and function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    char_pos = self._ast_pos_to_char(node.lineno, node.col_offset, line_offsets)
                    entity = ExtractedEntity(
                        text=node.name,
                        label='CLASS',
                        span=(char_pos, char_pos + len(node.name)),
                        confidence=1.0,
                        metadata={
                            'bases': [self._get_name(b) for b in node.bases],
                            'decorators': [self._get_name(d) for d in node.decorator_list],
                            'methods': [],
                            'lineno': node.lineno
                        }
                    )
                    entities.append(entity)
                    definitions[node.name] = entity
                    
                    # Extract class methods and attributes
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_char_pos = self._ast_pos_to_char(item.lineno, item.col_offset, line_offsets)
                            method_entity = ExtractedEntity(
                                text=item.name,
                                label='METHOD',
                                span=(method_char_pos, method_char_pos + len(item.name)),
                                confidence=1.0,
                                metadata={
                                    'class': node.name,
                                    'is_private': item.name.startswith('_'),
                                    'is_magic': item.name.startswith('__') and item.name.endswith('__'),
                                    'args': [arg.arg for arg in item.args.args],
                                    'decorators': [self._get_name(d) for d in item.decorator_list],
                                    'lineno': item.lineno
                                }
                            )
                            entities.append(method_entity)
                            definitions[f"{node.name}.{item.name}"] = method_entity
                            entity.metadata['methods'].append(item.name)
                            
                            # HAS_METHOD relation
                            relations.append(ExtractedRelation(
                                head=node.name,
                                tail=item.name,
                                relation='HAS_METHOD',
                                confidence=1.0,
                                context=f"Class {node.name} defines method {item.name}",
                                metadata={'class_name': node.name, 'method_name': item.name}
                            ))
                    
                    # Extract class inheritance relations
                    for base in node.bases:
                        base_name = self._get_name(base)
                        if base_name:
                            relations.append(ExtractedRelation(
                                head=node.name,
                                tail=base_name,
                                relation='INHERITS_FROM',
                                confidence=1.0,
                                context=f"Class {node.name} inherits from {base_name}",
                                metadata={'subclass': node.name, 'superclass': base_name}
                            ))
                
                elif isinstance(node, ast.FunctionDef) and not self._is_method(tree, node):
                    char_pos = self._ast_pos_to_char(node.lineno, node.col_offset, line_offsets)
                    entity = ExtractedEntity(
                        text=node.name,
                        label='FUNCTION',
                        span=(char_pos, char_pos + len(node.name)),
                        confidence=1.0,
                        metadata={
                            'args': [arg.arg for arg in node.args.args],
                            'is_async': isinstance(node, ast.AsyncFunctionDef),
                            'decorators': [self._get_name(d) for d in node.decorator_list],
                            'returns': self._get_name(node.returns) if node.returns else None,
                            'lineno': node.lineno
                        }
                    )
                    entities.append(entity)
                    definitions[node.name] = entity
                
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        char_pos = self._ast_pos_to_char(node.lineno, node.col_offset, line_offsets)
                        entity = ExtractedEntity(
                            text=alias.name,
                            label='IMPORT',
                            span=(char_pos, char_pos + len(alias.name)),
                            confidence=1.0,
                            metadata={'alias': alias.asname, 'lineno': node.lineno}
                        )
                        entities.append(entity)
                        definitions[alias.asname or alias.name] = entity
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        char_pos = self._ast_pos_to_char(node.lineno, node.col_offset, line_offsets)
                        entity = ExtractedEntity(
                            text=node.module,
                            label='IMPORT_FROM',
                            span=(char_pos, char_pos + len(node.module)),
                            confidence=1.0,
                            metadata={
                                'items': [a.name for a in node.names],
                                'level': node.level,
                                'lineno': node.lineno
                            }
                        )
                        entities.append(entity)
                        
                        # Track imported items
                        for alias in node.names:
                            imported_name = alias.asname or alias.name
                            definitions[imported_name] = entity
            
            # Extract function calls and variable usage
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = self._get_call_name(node.func)
                    if func_name:
                        caller = self._find_caller_context(tree, node)
                        if caller:
                            relations.append(ExtractedRelation(
                                head=caller,
                                tail=func_name,
                                relation='CALLS',
                                confidence=0.95,
                                context=f"{caller} calls {func_name}",
                                metadata={
                                    'caller': caller,
                                    'callee': func_name,
                                    'num_args': len(node.args)
                                }
                            ))
                
                elif isinstance(node, ast.Assign):
                    # Track variable assignments
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id
                            # Check if assigned from a function call or class instantiation
                            if isinstance(node.value, ast.Call):
                                func_name = self._get_call_name(node.value.func)
                                if func_name:
                                    relations.append(ExtractedRelation(
                                        head=var_name,
                                        tail=func_name,
                                        relation='INSTANTIATED_FROM',
                                        confidence=0.9,
                                        context=f"{var_name} is created from {func_name}",
                                        metadata={'variable': var_name, 'source': func_name}
                                    ))
                
                elif isinstance(node, ast.Attribute):
                    # Track attribute access (e.g., obj.method())
                    if isinstance(node.value, ast.Name):
                        obj_name = node.value.id
                        attr_name = node.attr
                        relations.append(ExtractedRelation(
                            head=obj_name,
                            tail=attr_name,
                            relation='ACCESSES_ATTRIBUTE',
                            confidence=0.85,
                            context=f"{obj_name} accesses attribute {attr_name}",
                            metadata={'object': obj_name, 'attribute': attr_name}
                        ))
            
            # Add decorator relations
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    for decorator in node.decorator_list:
                        dec_name = self._get_name(decorator)
                        if dec_name:
                            relations.append(ExtractedRelation(
                                head=node.name,
                                tail=dec_name,
                                relation='DECORATED_BY',
                                confidence=1.0,
                                context=f"{node.name} is decorated by {dec_name}",
                                metadata={'target': node.name, 'decorator': dec_name}
                            ))
        
        except Exception as e:
            print(f"Error during code parsing: {e}")
            import traceback
            traceback.print_exc()
        
        return entities, relations
    
    def _build_line_offsets(self, code: str) -> List[int]:
        """Build a map of line number to character offset"""
        offsets = [0]
        for i, char in enumerate(code):
            if char == '\n':
                offsets.append(i + 1)
        return offsets
    
    def _ast_pos_to_char(self, lineno: int, col_offset: int, line_offsets: List[int]) -> int:
        """Convert AST line/column to character position"""
        try:
            if lineno <= 0 or lineno > len(line_offsets):
                return 0
            return line_offsets[lineno - 1] + col_offset
        except (IndexError, TypeError) as e:
            print(f"Warning: Position conversion error at line {lineno}, col {col_offset}: {e}")
            return 0
    
    def _get_name(self, node: ast.AST) -> Optional[str]:
        """Extract name from various AST node types"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value_name = self._get_name(node.value)
            return f"{value_name}.{node.attr}" if value_name else node.attr
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return None
    
    def _is_method(self, tree: ast.AST, func_node: ast.FunctionDef) -> bool:
        """Check if function is a method of a class"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if func_node in node.body:
                    return True
        return False
    
    def _get_call_name(self, node: ast.expr) -> Optional[str]:
        """Extract function name from call node"""
        return self._get_name(node)
    
    def _find_caller_context(self, tree: ast.AST, call_node: ast.Call) -> Optional[str]:
        """Find the function/method/class containing this call"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if self._node_contains(node, call_node):
                    return node.name
        return None
    
    def _node_contains(self, parent: ast.AST, child: ast.AST) -> bool:
        """Check if parent node contains child"""
        for node in ast.walk(parent):
            if node is child:
                return True
        return False


class CodeExtractor:
    """Extract entities and relations from source code"""
    
    SUPPORTED_LANGUAGES = {
        'python': PythonCodeParser,
    }
    
    def __init__(self):
        self.parsers = {
            lang: parser_cls() for lang, parser_cls in self.SUPPORTED_LANGUAGES.items()
        }

    def detect_language(self, code: str) -> Optional[str]:
        """Heuristic language detection"""
        text = code.strip().lower()
        text = re.sub(r'```(?:python)?|`', '', text)
        text = re.sub(r'<code>|</code>|<pre>|</pre>', '', text)
        text = text.strip()

        python_patterns = [
            r'\bdef\s+\w+\s*\(',
            r'\bclass\s+\w+\s*\(?.*?\)?:',
            r'^\s*(?:from\s+\w+(\.\w+)*\s+import\s+|import\s+\w+)',
            r'^\s*@\w+',
            r'\b(lambda|yield|async|await|with|as|elif|except|try|self|None|True|False)\b',
            r':\s*(#.*)?',
            r'f".*?{.*?}.*?"',
            r'\b(print|len|range|open|enumerate|zip|map|filter|isinstance)\s*\(',
            r'\b[a-zA-Z_]\w*\s*:\s*[a-zA-Z_]\w*',
        ]

        if re.search(r'```+\s*python', code, re.IGNORECASE):
            return 'python'

        matches = sum(1 for pattern in python_patterns if re.search(pattern, text, re.MULTILINE))
        if matches >= 2:
            return 'python'

        return None
    
    def extract_code_entities(self, code: str, language: Optional[str] = None) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """Extract entities and relations from code"""
        if not language:
            language = self.detect_language(code)
        
        if not language or language not in self.parsers:
            return self._fallback_extraction(code)
        
        parser = self.parsers[language]
        return parser.parse(code)
    
    def _fallback_extraction(self, code: str) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """Basic extraction when language is unknown"""
        entities = []
        
        for match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', code):
            entities.append(ExtractedEntity(
                text=match.group(1),
                label='FUNCTION_CALL',
                span=(match.start(1), match.end(1)),
                confidence=0.6
            ))
        
        for match in re.finditer(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)', code):
            entities.append(ExtractedEntity(
                text=match.group(1),
                label='CLASS',
                span=(match.start(1), match.end(1)),
                confidence=0.7
            ))
        
        return entities, []


class NLPExtractor:
    """Enhanced schema-less entity and relationship extraction"""
    
    def __init__(self, spacy_model: str = "en_core_web_sm", embedding_model: str = "all-MiniLM-L6-v2"):
        try:
            self.nlp = spacy.load(spacy_model)
        except OSError:
            print(f"Downloading spaCy model {spacy_model}...")
            os.system(f"python -m spacy download {spacy_model}")
            self.nlp = spacy.load(spacy_model)
        
        self.embedding_model = SentenceTransformer(embedding_model)
        self.pattern_extractor = PatternExtractor()
        self.code_extractor = CodeExtractor()
        self.entity_cache: Dict[str, ExtractedEntity] = {}
        
    def extract_entities(self, text: str, custom_patterns: Optional[List[str]] = None, 
                        is_code: bool = False, code_language: Optional[str] = None) -> List[ExtractedEntity]:
        """Enhanced entity extraction"""
        entities = []
        seen_spans = set()
        
        if is_code or self._detect_context_type(text) == 'code':
            code_entities, _ = self.code_extractor.extract_code_entities(text, code_language)
            return code_entities
        
        # Pattern-based extraction
        pattern_entities = self.pattern_extractor.extract_patterns(text)
        for e in pattern_entities:
            entities.append(e)
            seen_spans.add(e.span)
        
        # NLP extraction
        entities.extend(self._extract_nlp_entities(text, seen_spans))
        
        # Custom patterns
        if custom_patterns:
            for pattern in custom_patterns:
                for match in re.finditer(pattern, text):
                    span = (match.start(), match.end())
                    if span not in seen_spans:
                        entities.append(ExtractedEntity(
                            text=match.group(),
                            label='CUSTOM_PATTERN',
                            span=span,
                            confidence=0.8
                        ))
                        seen_spans.add(span)
        
        # Add embeddings
        if entities:
            texts = [e.text for e in entities if len(e.text.strip()) > 0]
            if texts:
                embeddings = self.embedding_model.encode(texts)
                embed_idx = 0
                for e in entities:
                    if len(e.text.strip()) > 0:
                        e.embedding = embeddings[embed_idx].tolist()
                        embed_idx += 1
        
        return entities
    
    def _extract_nlp_entities(self, text: str, seen_spans: Optional[Set] = None) -> List[ExtractedEntity]:
        """Extract entities using spaCy"""
        if seen_spans is None:
            seen_spans = set()
        
        doc = self.nlp(text)
        entities = []
        
        # Named entities
        for ent in doc.ents:
            if ent.text.strip() and ent.start_char not in seen_spans:
                entities.append(ExtractedEntity(
                    text=ent.text,
                    label=ent.label_,
                    span=(ent.start_char, ent.end_char),
                    confidence=1.0,
                    metadata={'source': 'spacy_ner'}
                ))
                seen_spans.add(ent.start_char)
        
        # Noun chunks
        for chunk in doc.noun_chunks:
            if chunk.text.strip() and chunk.start_char not in seen_spans:
                if len(chunk.text.split()) > 1 or chunk.root.pos_ in ["PROPN", "NOUN"]:
                    entities.append(ExtractedEntity(
                        text=chunk.text,
                        label="NOUN_CHUNK",
                        span=(chunk.start_char, chunk.end_char),
                        confidence=0.7,
                        metadata={'source': 'noun_chunk', 'root_pos': chunk.root.pos_}
                    ))
                    seen_spans.add(chunk.start_char)
        
        # Key-value pairs
        for match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*([^\s,;]+)', text):
            span = (match.start(), match.end())
            if span not in seen_spans:
                entities.append(ExtractedEntity(
                    text=match.group(),
                    label='KEY_VALUE',
                    span=span,
                    confidence=0.8,
                    metadata={'key': match.group(1), 'value': match.group(2)}
                ))
                seen_spans.add(span)
        
        return entities
    
    def extract_relations(self, text: str, entities: List[ExtractedEntity], 
                         is_code: bool = False, code_language: Optional[str] = None) -> List[ExtractedRelation]:
        """Enhanced relationship extraction"""
        if is_code:
            _, code_relations = self.code_extractor.extract_code_entities(text, code_language)
            return code_relations
        
        doc = self.nlp(text)
        relations = []
        
        # Build entity index
        entity_map = {}
        for ent in entities:
            entity_map[ent.text.lower()] = ent
        
        # Extract dependency-based relations
        for sent in doc.sents:
            for token in sent:
                # Subject-Verb-Object patterns
                if token.dep_ in ['nsubj', 'nsubjpass'] and token.head.pos_ == 'VERB':
                    subject = token.text
                    verb = token.head.lemma_
                    
                    # Find object
                    for child in token.head.children:
                        if child.dep_ in ['dobj', 'attr', 'prep']:
                            obj = child.text
                            
                            # Check if both are extracted entities
                            if subject.lower() in entity_map and obj.lower() in entity_map:
                                relations.append(ExtractedRelation(
                                    head=subject,
                                    tail=obj,
                                    relation=verb.upper(),
                                    confidence=0.85,
                                    context=sent.text,
                                    metadata={
                                        'pattern': 'SVO',
                                        'verb': verb,
                                        'sentence': sent.text
                                    }
                                ))
                
                # Prepositional relations
                if token.dep_ == 'prep':
                    head_token = token.head
                    prep = token.text
                    
                    # Find object of preposition
                    for child in token.children:
                        if child.dep_ == 'pobj':
                            if head_token.text.lower() in entity_map and child.text.lower() in entity_map:
                                relations.append(ExtractedRelation(
                                    head=head_token.text,
                                    tail=child.text,
                                    relation=f'RELATED_VIA_{prep.upper()}',
                                    confidence=0.75,
                                    context=sent.text,
                                    metadata={
                                        'pattern': 'prepositional',
                                        'preposition': prep
                                    }
                                ))
                
                # Possession relations
                if token.dep_ == 'poss':
                    possessor = token.text
                    possessed = token.head.text
                    
                    if possessor.lower() in entity_map and possessed.lower() in entity_map:
                        relations.append(ExtractedRelation(
                            head=possessor,
                            tail=possessed,
                            relation='POSSESSES',
                            confidence=0.8,
                            context=sent.text,
                            metadata={'pattern': 'possession'}
                        ))
                
                # Compound relations (multi-word entities)
                if token.dep_ == 'compound':
                    relations.append(ExtractedRelation(
                        head=token.text,
                        tail=token.head.text,
                        relation='PART_OF_COMPOUND',
                        confidence=0.9,
                        context=sent.text,
                        metadata={'pattern': 'compound'}
                    ))
        
        # Co-occurrence relations
        relations.extend(self._extract_cooccurrence(doc, entities))
        
        # Coreference-like relations (simple pronoun resolution)
        relations.extend(self._extract_coreference_relations(doc, entities))
        
        return relations
    
    def _extract_cooccurrence(self, doc, entities: List[ExtractedEntity]) -> List[ExtractedRelation]:
        """Extract co-occurrence based relations with proximity weighting"""
        relations = []
        
        for sent in doc.sents:
            sent_entities = [
                e for e in entities 
                if e.span[0] >= sent.start_char and e.span[1] <= sent.end_char
            ]
            
            # Create co-occurrence relations with distance weighting
            for i, head in enumerate(sent_entities):
                for tail in sent_entities[i+1:]:
                    # Calculate token distance
                    distance = abs(head.span[0] - tail.span[0])
                    confidence = max(0.5, 1.0 - (distance / len(sent.text)))
                    
                    relations.append(ExtractedRelation(
                        head=head.text,
                        tail=tail.text,
                        relation='CO_OCCURS',
                        confidence=confidence,
                        context=sent.text,
                        metadata={
                            'sentence_proximity': 'same',
                            'distance': distance
                        }
                    ))
        
        return relations
    
    def _extract_coreference_relations(self, doc, entities: List[ExtractedEntity]) -> List[ExtractedRelation]:
        """Simple pronoun-based coreference relations"""
        relations = []
        entity_map = {e.text.lower(): e for e in entities}
        
        for sent in doc.sents:
            prev_noun = None
            
            for token in sent:
                # Track nouns that are entities
                if token.pos_ in ['NOUN', 'PROPN'] and token.text.lower() in entity_map:
                    prev_noun = token.text
                
                # Link pronouns to previous noun
                elif token.pos_ == 'PRON' and prev_noun:
                    relations.append(ExtractedRelation(
                        head=token.text,
                        tail=prev_noun,
                        relation='REFERS_TO',
                        confidence=0.65,
                        context=sent.text,
                        metadata={'pattern': 'pronoun_resolution'}
                    ))
        
        return relations
    
    def extract_insights_markers(self, text: str, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Extract markers for insight detection"""
        insight_entities = []
        
        insight_patterns = {
            'CONCLUSION': r'\b(?:in conclusion|to conclude|therefore|thus|hence|consequently)\b',
            'INSIGHT': r'\b(?:insight|finding|discovery|observation|key point|important|notably)\b',
            'CAUSAL': r'\b(?:because|due to|caused by|results in|leads to|affects)\b',
            'COMPARISON': r'\b(?:compared to|versus|vs|in contrast|however|whereas|unlike)\b',
            'TREND': r'\b(?:increasing|decreasing|growing|declining|trend|pattern)\b',
            'QUANTIFIER': r'\b(?:significant|substantial|major|minor|slight|dramatic|considerable)\b',
            'TEMPORAL': r'\b(?:recently|previously|historically|currently|future|upcoming)\b',
            'PROBLEM': r'\b(?:issue|problem|challenge|error|failure|bug|vulnerability)\b',
            'SOLUTION': r'\b(?:solution|fix|resolved|implemented|patched|workaround)\b',
            'RECOMMENDATION': r'\b(?:should|recommend|suggest|advise|propose|consider)\b',
        }
        
        for label, pattern in insight_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                context_start = max(0, match.start() - 100)
                context_end = min(len(text), match.end() + 100)
                context = text[context_start:context_end]
                
                insight_entities.append(ExtractedEntity(
                    text=match.group(),
                    label=f'INSIGHT_MARKER_{label}',
                    span=(match.start(), match.end()),
                    confidence=0.85,
                    metadata={
                        'context': context.strip(),
                        'marker_type': label.lower(),
                        'for_insight_detection': True
                    }
                ))
        
        # Extract quantitative evidence
        for match in re.finditer(r'\b\d+(?:,\d{3})*(?:\.\d+)?(?:\s*[%x]|\s+(?:times|percent|fold))\b', text):
            insight_entities.append(ExtractedEntity(
                text=match.group(),
                label='QUANTITATIVE_EVIDENCE',
                span=(match.start(), match.end()),
                confidence=0.9,
                metadata={'for_insight_detection': True}
            ))
        
        return insight_entities
    
    def extract_from_terminal_output(self, output: str) -> List[ExtractedEntity]:
        """Specialized extraction for terminal output"""
        entities = []
        seen_spans = set()
        
        # Extract commands
        for match in re.finditer(r'^[\$#]\s+(.+)', output, re.MULTILINE):
            span = (match.start(1), match.end(1))
            entities.append(ExtractedEntity(
                text=match.group(1),
                label='TERMINAL_COMMAND',
                span=span,
                confidence=0.95,
                metadata={'source': 'terminal'}
            ))
            seen_spans.add(span)
        
        # Extract errors
        error_patterns = [
            (r'\berror:?\s*(.+?)(?:\n|$)', 'ERROR'),
            (r'\bwarning:?\s*(.+?)(?:\n|$)', 'WARNING'),
            (r'\bfailed:?\s*(.+?)(?:\n|$)', 'FAILURE'),
            (r'permission denied', 'PERMISSION_ERROR'),
            (r'command not found', 'COMMAND_NOT_FOUND'),
            (r'no such file or directory', 'FILE_NOT_FOUND'),
        ]
        
        for pattern, label in error_patterns:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                span = (match.start(), match.end())
                if span not in seen_spans:
                    entities.append(ExtractedEntity(
                        text=match.group(),
                        label=label,
                        span=span,
                        confidence=0.9,
                        metadata={'source': 'terminal', 'type': 'error'}
                    ))
                    seen_spans.add(span)
        
        # Extract exit codes
        for match in re.finditer(r'\bexit\s+code\s*:?\s*(\d+)', output, re.IGNORECASE):
            entities.append(ExtractedEntity(
                text=match.group(1),
                label='EXIT_CODE',
                span=(match.start(1), match.end(1)),
                confidence=1.0,
                metadata={'code': int(match.group(1)), 'success': match.group(1) == '0'}
            ))
        
        # Extract file paths
        for match in re.finditer(r'(?:/[\w.-]+)+/?', output):
            span = (match.start(), match.end())
            if span not in seen_spans:
                entities.append(ExtractedEntity(
                    text=match.group(),
                    label='FILE_PATH',
                    span=span,
                    confidence=0.85,
                    metadata={'source': 'terminal'}
                ))
                seen_spans.add(span)
        
        # Extract process IDs
        for match in re.finditer(r'\bPID:?\s*(\d+)', output, re.IGNORECASE):
            entities.append(ExtractedEntity(
                text=match.group(1),
                label='PROCESS_ID',
                span=(match.start(1), match.end(1)),
                confidence=0.95,
                metadata={'pid': int(match.group(1))}
            ))
        
        return entities
    
    def extract_markdown_blocks_with_context(self, text: str) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """
        Extract markdown code blocks, creating a proper hierarchical structure.
        FIXED: Assigns stable IDs and links relations via IDs.
        """
        markdown_entities = []
        markdown_relations = []
        
        pattern = r'```(\w+)?\s*\n(.*?)```'
        
        # Generate unique session ID to prevent collisions across different calls
        session_id = hashlib.md5(f"{time.time()}{text[:100]}".encode()).hexdigest()[:8]
        
        for block_idx, match in enumerate(re.finditer(pattern, text, re.DOTALL)):
            language = match.group(1) or 'text'
            code_content = match.group(2).strip()
            span = (match.start(), match.end())

            # Skip empty blocks
            if not code_content:
                continue
            
            # Create UNIQUE identifier
            block_id = f"code_block_{language}_{session_id}_{block_idx}_{span[0]}"
            
            # Get first line or summary for better naming
            first_line = code_content.split('\n')[0][:50].strip()
            if not first_line:
                first_line = f"{language} code"
            
            # Create code block entity with stable ID
            block_entity = ExtractedEntity(
                text=block_id,
                label='CODE_BLOCK',
                span=span,
                confidence=1.0,
                entity_id=hashlib.md5(f"{block_id}@{span[0]}".encode()).hexdigest()[:8],
                metadata={
                    'language': language,
                    'content_length': len(code_content),
                    'preview': first_line,
                    'full_content': code_content,
                    'block_index': block_idx,
                    'session_id': session_id,
                    'display_name': f"{language}: {first_line}"
                }
            )
            markdown_entities.append(block_entity)
            
            content_offset = match.start() + len(f'```{language}\n')
            
            # Extract entities and relations based on language
            child_entities = []
            child_relations = []
            
            try:
                if language in ['python', 'py']:
                    child_entities, child_relations = self.code_extractor.extract_code_entities(
                        code_content, 
                        language='python'
                    )
                elif language in ['bash', 'sh', 'shell', 'terminal', 'console']:
                    child_entities = self.extract_from_terminal_output(code_content)
                else:
                    child_entities = self.pattern_extractor.extract_patterns(code_content)
            except Exception as e:
                print(f"Error extracting from {language} block: {e}")
            
            # Build entity lookup map for this block
            entity_text_to_id = {}
            
            # Adjust spans and assign stable IDs to child entities
            for entity in child_entities:
                try:
                    # Adjust span to absolute position in full text
                    entity.span = (
                        content_offset + entity.span[0],
                        content_offset + entity.span[1]
                    )
                    
                    # Assign stable ID based on text + position
                    entity.entity_id = entity.get_stable_id()
                    
                    # Add block context to entity metadata
                    entity.metadata['code_block_id'] = block_id
                    entity.metadata['language'] = language
                    entity.metadata['block_index'] = block_idx
                    entity.metadata['session_id'] = session_id
                    
                    # Map text to ID for relation linking
                    entity_text_to_id[entity.text] = entity.entity_id
                    
                    # Create DEFINED_IN relation with IDs
                    markdown_relations.append(ExtractedRelation(
                        head=entity.text,
                        tail=block_id,
                        head_id=entity.entity_id,
                        tail_id=block_entity.entity_id,
                        relation='DEFINED_IN',
                        confidence=1.0,
                        context=f"{entity.label} {entity.text} defined in {language} code block",
                        metadata={
                            'relationship_type': 'hierarchical',
                            'entity_type': entity.label,
                            'block_type': 'CODE_BLOCK',
                            'language': language
                        }
                    ))
                    
                except Exception as e:
                    print(f"Error processing entity: {e}")
                    continue
            
            # Update child relations with entity IDs
            for rel in child_relations:
                rel.head_id = entity_text_to_id.get(rel.head)
                rel.tail_id = entity_text_to_id.get(rel.tail)
            
            # Add child entities and relations
            markdown_entities.extend(child_entities)
            markdown_relations.extend(child_relations)
        
        return markdown_entities, markdown_relations

    def extract_markdown_blocks_flat(self, text: str) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """
        Extract markdown code blocks - FLAT version.
        Only extracts code entities without wrapper blocks.
        """
        all_entities = []
        all_relations = []
        
        pattern = r'```(\w+)?\s*\n(.*?)```'
        
        for match in re.finditer(pattern, text, re.DOTALL):
            language = match.group(1) or 'text'
            code_content = match.group(2).strip()
            
            if not code_content:
                continue
            
            content_offset = match.start() + len(f'```{language}\n')
            
            # Extract based on language
            try:
                if language in ['python', 'py']:
                    entities, relations = self.code_extractor.extract_code_entities(
                        code_content, 
                        language='python'
                    )
                elif language in ['bash', 'sh', 'shell', 'terminal', 'console']:
                    entities = self.extract_from_terminal_output(code_content)
                    relations = []
                else:
                    entities = self.pattern_extractor.extract_patterns(code_content)
                    relations = []
            except Exception as e:
                print(f"Error extracting from {language} block: {e}")
                continue
            
            # Adjust spans and add minimal metadata
            for entity in entities:
                entity.span = (
                    content_offset + entity.span[0],
                    content_offset + entity.span[1]
                )
                entity.metadata['language'] = language
                entity.metadata['from_code_block'] = True
            
            all_entities.extend(entities)
            all_relations.extend(relations)
        
        return all_entities, all_relations

    def extract_all(self, text: str, context_type: Optional[str] = None, 
                    keep_block_context: bool = True, **kwargs) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """
        Unified extraction with proper markdown and code handling.
        
        Args:
            text: Input text
            context_type: Type hint - 'code', 'terminal', 'llm_output', 'user_input', None
            keep_block_context: If True, create CODE_BLOCK entities; if False, extract flat
            **kwargs: Additional parameters
        """
        all_entities = []
        all_relations = []
        
        try:
            # Extract markdown blocks first
            if keep_block_context:
                markdown_entities, markdown_relations = self.extract_markdown_blocks_with_context(text)
            else:
                markdown_entities, markdown_relations = self.extract_markdown_blocks_flat(text)
            
            if markdown_entities:
                print(f"✓ Extracted {len(markdown_entities)} entities from code blocks")
                print(f"✓ Extracted {len(markdown_relations)} relations from code blocks")
                
                all_entities.extend(markdown_entities)
                all_relations.extend(markdown_relations)
                
                # Remove markdown blocks from text for remaining processing
                text_without_blocks = text
                pattern = r'```\w*\s*\n.*?```'
                for match in re.finditer(pattern, text, re.DOTALL):
                    text_without_blocks = text_without_blocks.replace(
                        match.group(0), 
                        ' ' * len(match.group(0))
                    )
                
                # Process remaining text (non-code parts)
                if text_without_blocks.strip():
                    remaining_entities = self.extract_entities(text_without_blocks, **kwargs)
                    remaining_relations = self.extract_relations(text_without_blocks, remaining_entities)
                    insight_entities = self.extract_insights_markers(text_without_blocks, remaining_entities)
                    
                    print(f"✓ Extracted {len(remaining_entities)} entities from remaining text")
                    print(f"✓ Extracted {len(remaining_relations)} relations from remaining text")
                    print(f"✓ Extracted {len(insight_entities)} insight markers")
                    
                    all_entities.extend(remaining_entities)
                    all_relations.extend(remaining_relations)
                    all_entities.extend(insight_entities)
            
            else:
                # No markdown blocks - standard processing
                if context_type is None:
                    context_type = self._detect_context_type(text)
                
                if context_type == 'code':
                    code_entities, code_relations = self.code_extractor.extract_code_entities(text, **kwargs)
                    all_entities.extend(code_entities)
                    all_relations.extend(code_relations)
                elif context_type == 'terminal':
                    terminal_entities = self.extract_from_terminal_output(text)
                    all_entities.extend(terminal_entities)
                    # Also do standard extraction
                    standard_entities = self.extract_entities(text, **kwargs)
                    standard_relations = self.extract_relations(text, standard_entities)
                    all_entities.extend(standard_entities)
                    all_relations.extend(standard_relations)
                else:
                    standard_entities = self.extract_entities(text, **kwargs)
                    standard_relations = self.extract_relations(text, standard_entities)
                    insight_entities = self.extract_insights_markers(text, standard_entities)
                    all_entities.extend(standard_entities)
                    all_relations.extend(standard_relations)
                    all_entities.extend(insight_entities)
                
                print(f"✓ Extracted {len(all_entities)} entities (standard processing)")
                print(f"✓ Extracted {len(all_relations)} relations (standard processing)")
            
        except Exception as e:
            print(f"✗ Error in extract_all: {e}")
            import traceback
            traceback.print_exc()
            return [], []
        
        print(f"\n=== Total: {len(all_entities)} entities, {len(all_relations)} relations ===")
        return all_entities, all_relations

    def _detect_context_type(self, text: str) -> str:
        """Auto-detect content type"""
        code_indicators = [
            r'^(?:import|from|def|class|function|var|const|let)\s+',
            r'\bpublic\s+(?:class|interface|static)',
            r'^\s*[{}\[\]();]',
        ]
        
        if any(re.search(pattern, text, re.MULTILINE) for pattern in code_indicators):
            return 'code'
        
        terminal_indicators = [
            r'^[\$#]\s+',
            r'\b(?:sudo|apt|yum|brew|npm|pip|git)\s+',
            r'exit code|permission denied|command not found',
        ]
        
        if any(re.search(pattern, text, re.MULTILINE | re.IGNORECASE) for pattern in terminal_indicators):
            return 'terminal'
        
        return 'text'
    
    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove duplicate entities with overlapping spans"""
        if not entities:
            return entities
        
        try:
            sorted_entities = sorted(entities, key=lambda e: (e.confidence, e.span[1] - e.span[0]), reverse=True)
            
            kept_entities = []
            used_spans = set()
            
            for entity in sorted_entities:
                try:
                    overlaps = False
                    for start in range(entity.span[0], entity.span[1]):
                        if start in used_spans:
                            overlaps = True
                            break
                    
                    if not overlaps:
                        kept_entities.append(entity)
                        for start in range(entity.span[0], entity.span[1]):
                            used_spans.add(start)
                except Exception as e:
                    print(f"Error processing entity {entity.text}: {e}")
                    continue
            
            return sorted(kept_entities, key=lambda e: e.span[0])
        except Exception as e:
            print(f"Error in deduplication: {e}")
            return entities

    def cluster_entities(self, entities: List[ExtractedEntity], eps: float = 0.3) -> Dict[str, List[ExtractedEntity]]:
        """Cluster entities by embedding similarity"""
        if not entities or not any(e.embedding for e in entities):
            return {"cluster_0": entities}
        
        entities_with_emb = [e for e in entities if e.embedding]
        if not entities_with_emb:
            return {"cluster_0": entities}
        
        embeddings = np.array([e.embedding for e in entities_with_emb])
        clustering = DBSCAN(eps=eps, min_samples=1, metric='cosine').fit(embeddings)
        
        clusters = defaultdict(list)
        for idx, label in enumerate(clustering.labels_):
            clusters[f"cluster_{label}"].append(entities_with_emb[idx])
        
        return dict(clusters)
    
    def normalize_entity(self, entity: ExtractedEntity, cluster: List[ExtractedEntity]) -> str:
        """Normalize entity text from a cluster"""
        candidates = sorted(cluster, key=lambda e: (e.confidence, len(e.text)), reverse=True)
        return candidates[0].text


# Testing
if __name__ == "__main__":
    print("=" * 60)
    print("FIXED NLP Extractor - Testing Suite")
    print("=" * 60)
    
    try:
        extractor = NLPExtractor()
        print("✓ Extractor initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize extractor: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # Test 1: Simple text
    print("\n" + "=" * 60)
    print("Test 1: Simple Text")
    print("=" * 60)
    try:
        simple_text = "John works at Google in Mountain View. He started on 2024-01-15."
        entities, relations = extractor.extract_all(simple_text)
        print(f"✓ Extracted {len(entities)} entities, {len(relations)} relations")
        for e in entities[:5]:
            print(f"  {e.label:15} | {e.text}")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Python code without markdown
    print("\n" + "=" * 60)
    print("Test 2: Python Code (no markdown)")
    print("=" * 60)
    try:
        code = """
def greet(name):
    return f"Hello {name}"

class Person:
    def __init__(self, name):
        self.name = name
"""
        entities, relations = extractor.extract_all(code, context_type='code')
        print(f"✓ Extracted {len(entities)} entities, {len(relations)} relations")
        print("\nEntities:")
        for e in entities:
            print(f"  {e.label:15} | {e.text}")
        print("\nRelations:")
        for r in relations:
            print(f"  {r.head} --[{r.relation}]--> {r.tail}")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Markdown with Python code
    print("\n" + "=" * 60)
    print("Test 3: Markdown with Python Code")
    print("=" * 60)
    try:
        test_text = """
Here's a sample implementation:

```python
class DataProcessor:
    def __init__(self, config):
        self.config = config
    
    def process(self, data):
        result = self.transform(data)
        return result
    
    def transform(self, data):
        return data.upper()

def main():
    processor = DataProcessor(config={})
    data = processor.process("input")
    print(data)
```

This implementation provides a robust solution for data processing.
The DataProcessor class handles transformation efficiently.
"""
        
        entities, relations = extractor.extract_all(test_text)
        print(f"\n✓ Extracted {len(entities)} entities, {len(relations)} relations")
        
        print("\nCode Entities:")
        code_entities = [e for e in entities if e.label in ['CLASS', 'METHOD', 'FUNCTION', 'CODE_BLOCK']]
        for e in code_entities:
            print(f"  {e.label:15} | {e.text:30} | span: {e.span}")
        
        print("\nText Entities:")
        text_entities = [e for e in entities if e.label not in ['CLASS', 'METHOD', 'FUNCTION', 'CODE_BLOCK']]
        for e in text_entities[:10]:
            print(f"  {e.label:15} | {e.text:30}")
        
        print("\nRelations:")
        for r in relations[:15]:
            print(f"  {r.head:20} --[{r.relation:20}]--> {r.tail:20}")
            
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Multiple code blocks (collision test)
    print("\n" + "=" * 60)
    print("Test 4: Multiple Code Blocks (Collision Test)")
    print("=" * 60)
    try:
        multi_block = """
First implementation:

```python
def func_a():
    return "A"
```

Second implementation:

```python
def func_b():
    return "B"
```

Third implementation:

```python
class MyClass:
    pass
```
"""
        entities, relations = extractor.extract_all(multi_block)
        
        # Check for unique block IDs
        block_entities = [e for e in entities if e.label == 'CODE_BLOCK']
        block_ids = [e.text for e in block_entities]
        
        print(f"✓ Extracted {len(block_entities)} code blocks")
        print(f"✓ Block IDs are unique: {len(block_ids) == len(set(block_ids))}")
        
        if len(block_ids) != len(set(block_ids)):
            print("✗ COLLISION DETECTED!")
            print("Block IDs:", block_ids)
        else:
            print("✓ No collisions - all block IDs are unique")
            for block_id in block_ids:
                print(f"  - {block_id}")
        
        print(f"\n✓ Total entities: {len(entities)}")
        print(f"✓ Total relations: {len(relations)}")
        
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 5: Mixed content
    print("\n" + "=" * 60)
    print("Test 5: Mixed Content")
    print("=" * 60)
    try:
        mixed = """
The system uses Python for processing. Key components:

```python
def calculate(x, y):
    return x + y
```

Error logs show issues:

```bash
$ python script.py
Error: File not found
exit code: 1
```

Contact support@example.com for help.
"""
        entities, relations = extractor.extract_all(mixed)
        print(f"✓ Extracted {len(entities)} entities, {len(relations)} relations")
        
        # Group by type
        by_type = {}
        for e in entities:
            if e.label not in by_type:
                by_type[e.label] = []
            by_type[e.label].append(e.text)
        
        print("\nEntities by type:")
        for label, texts in sorted(by_type.items()):
            sample = texts[:3] if len(texts) > 3 else texts
            print(f"  {label:20}: {len(texts):3} entities (e.g., {', '.join(sample)})")
            
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)