#!/usr/bin/env python3
"""
ISON v1.0 Reference Parser
Interchange Simple Object Notation

A minimal, LLM-friendly data serialization format optimized for
graph databases, multi-agent systems, and RAG pipelines.

Usage:
    import ison_parser

    # Parse from string
    doc = ison_parser.loads(ison_string)

    # Parse from file
    doc = ison_parser.load('data.ison')

    # Serialize to ISON
    ison_string = ison_parser.dumps(doc)

    # ISONL streaming
    from ison_parser import loads_isonl, isonl_stream
    doc = loads_isonl(isonl_text)

Author: Mahesh Vaikri
Version: 1.0.0
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Any, Optional, Generator
from pathlib import Path

__version__ = "1.0.0"
__author__ = "Mahesh Vaikri"

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Reference:
    """
    Represents a reference to another record.

    Syntax variants:
        :10              - Simple reference (id only)
        :user:101        - Namespaced reference (type:id)
        :MEMBER_OF:10    - Relationship-typed reference (relationship:target)

    The type field can be:
        - A namespace (e.g., 'user', 'product')
        - A relationship type (e.g., 'MEMBER_OF', 'REPORTS_TO', 'IS_A')
    """
    id: str
    type: Optional[str] = None

    def __repr__(self):
        if self.type:
            return f"Reference({self.type}:{self.id})"
        return f"Reference({self.id})"

    def to_ison(self) -> str:
        """Convert back to ISON reference notation"""
        if self.type:
            return f":{self.type}:{self.id}"
        return f":{self.id}"

    def is_relationship(self) -> bool:
        """Check if this is a relationship-typed reference (uppercase type)"""
        return self.type is not None and self.type.isupper()

    @property
    def relationship_type(self) -> Optional[str]:
        """Get the relationship type if this is a relationship reference"""
        if self.is_relationship():
            return self.type
        return None

    @property
    def namespace(self) -> Optional[str]:
        """Get the namespace if this is a namespaced reference (lowercase type)"""
        if self.type and not self.type.isupper():
            return self.type
        return None


@dataclass
class FieldInfo:
    """
    Represents field metadata including optional type annotation.

    Syntax: field_name:type or field_name (untyped)

    Supported types:
        - int: Integer values
        - float: Floating point numbers
        - string: Text values
        - bool: Boolean (true/false)
        - ref: Reference to another record
        - computed: Derived/calculated field
        - node: Graph node reference
        - edge: Graph edge reference
    """
    name: str
    type: Optional[str] = None
    is_computed: bool = False

    @classmethod
    def parse(cls, field_str: str) -> 'FieldInfo':
        """Parse a field definition like 'name:string' or 'total:computed'"""
        if ':' in field_str:
            parts = field_str.split(':', 1)
            name = parts[0]
            type_hint = parts[1].lower()
            is_computed = type_hint == 'computed'
            return cls(name=name, type=type_hint, is_computed=is_computed)
        return cls(name=field_str)

    def __repr__(self):
        if self.type:
            return f"FieldInfo({self.name}:{self.type})"
        return f"FieldInfo({self.name})"


@dataclass
class Block:
    """Represents an ISON block (object, table, meta, etc.)"""
    kind: str
    name: str
    fields: list[str]
    rows: list[dict[str, Any]]
    field_info: list[FieldInfo] = field(default_factory=list)
    summary: Optional[str] = None  # Summary row after ---

    def __repr__(self):
        return f"Block({self.kind}.{self.name}, {len(self.rows)} rows)"

    @staticmethod
    def _try_parse_json(value: Any) -> Any:
        """Try to parse a string as JSON (for arrays/objects encoded as strings)"""
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        # Only try to parse if it looks like JSON array or object
        if ((trimmed.startswith('[') and trimmed.endswith(']')) or
            (trimmed.startswith('{') and trimmed.endswith('}'))):
            try:
                return json.loads(trimmed)
            except (json.JSONDecodeError, ValueError):
                return value  # Return original if parse fails
        return value

    @staticmethod
    def _process_row_values(row: dict) -> dict:
        """Process row values to restore JSON-encoded arrays/objects"""
        result = {}
        for key, value in row.items():
            result[key] = Block._try_parse_json(value)
        return result

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        # Process rows to restore JSON-encoded values
        processed_rows = [self._process_row_values(row) for row in self.rows]

        if self.kind == "object" and len(processed_rows) == 1:
            return {self.name: processed_rows[0]}
        return {self.name: processed_rows}

    def get_field_type(self, field_name: str) -> Optional[str]:
        """Get the type annotation for a field"""
        for fi in self.field_info:
            if fi.name == field_name:
                return fi.type
        return None

    def get_computed_fields(self) -> list[str]:
        """Get list of computed field names"""
        return [fi.name for fi in self.field_info if fi.is_computed]


@dataclass
class Document:
    """Represents a complete ISON document"""
    blocks: list[Block] = field(default_factory=list)

    def __getitem__(self, name: str) -> Optional[Block]:
        """Get block by name"""
        for block in self.blocks:
            if block.name == name:
                return block
        return None

    def to_dict(self) -> dict:
        """Convert entire document to nested dictionary"""
        result = {}
        for block in self.blocks:
            block_dict = block.to_dict()
            result.update(block_dict)
        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, default=_json_default)


def _json_default(obj):
    """JSON serializer for Reference objects"""
    if isinstance(obj, Reference):
        return obj.to_ison()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# =============================================================================
# Parser Errors
# =============================================================================

class ISONError(Exception):
    """Base exception for ISON parsing errors"""
    pass


class ISONSyntaxError(ISONError):
    """Syntax error in ISON document"""
    def __init__(self, message: str, line: int = 0, col: int = 0):
        self.line = line
        self.col = col
        super().__init__(f"Line {line}, Col {col}: {message}")


class ISONTypeError(ISONError):
    """Type inference error"""
    pass


# =============================================================================
# Tokenizer
# =============================================================================

class Tokenizer:
    """Tokenizes a line into ISON values"""

    ESCAPE_MAP = {
        '"': '"',
        '\\': '\\',
        'n': '\n',
        't': '\t',
        'r': '\r',
    }

    def __init__(self, line: str, line_num: int = 0):
        self.line = line
        self.line_num = line_num
        self.pos = 0
        self.tokens = []

    def tokenize(self) -> list[str]:
        """Tokenize the line into a list of string tokens"""
        self.tokens = []
        self.pos = 0

        while self.pos < len(self.line):
            self._skip_whitespace()
            if self.pos >= len(self.line):
                break

            char = self.line[self.pos]

            if char == '"':
                self.tokens.append(self._read_quoted_string())
            else:
                self.tokens.append(self._read_unquoted_token())

        return self.tokens

    def _skip_whitespace(self):
        """Skip spaces and tabs"""
        while self.pos < len(self.line) and self.line[self.pos] in ' \t':
            self.pos += 1

    def _read_quoted_string(self) -> str:
        """Read a quoted string with escape handling"""
        start_pos = self.pos
        self.pos += 1  # Skip opening quote
        result = []

        while self.pos < len(self.line):
            char = self.line[self.pos]

            if char == '"':
                self.pos += 1  # Skip closing quote
                return ''.join(result)

            if char == '\\':
                self.pos += 1
                if self.pos >= len(self.line):
                    raise ISONSyntaxError(
                        "Unexpected end of line after backslash",
                        self.line_num, self.pos
                    )
                escape_char = self.line[self.pos]
                if escape_char in self.ESCAPE_MAP:
                    result.append(self.ESCAPE_MAP[escape_char])
                else:
                    # Unknown escape, keep as-is
                    result.append(escape_char)
            else:
                result.append(char)

            self.pos += 1

        raise ISONSyntaxError(
            "Unterminated quoted string",
            self.line_num, start_pos
        )

    def _read_unquoted_token(self) -> str:
        """Read an unquoted token until whitespace"""
        start = self.pos
        while self.pos < len(self.line) and self.line[self.pos] not in ' \t':
            self.pos += 1
        return self.line[start:self.pos]


# =============================================================================
# Type Inference
# =============================================================================

class TypeInferrer:
    """Infers types from ISON tokens according to spec rules"""

    # Patterns for type detection
    INTEGER_PATTERN = re.compile(r'^-?[0-9]+$')
    FLOAT_PATTERN = re.compile(r'^-?[0-9]+\.[0-9]+$')
    REFERENCE_PATTERN = re.compile(r'^:(.+)$')

    @classmethod
    def infer(cls, token: str, was_quoted: bool = False) -> Any:
        """
        Infer the type of a token and return the typed value.

        Type inference rules (in order):
        1. If quoted -> string
        2. true/false -> boolean
        3. null -> None
        4. integer pattern -> int
        5. float pattern -> float
        6. starts with : -> reference
        7. else -> string
        """
        # Quoted strings are always strings
        if was_quoted:
            return token

        # Boolean
        if token == 'true':
            return True
        if token == 'false':
            return False

        # Null
        if token == 'null':
            return None

        # Integer
        if cls.INTEGER_PATTERN.match(token):
            return int(token)

        # Float
        if cls.FLOAT_PATTERN.match(token):
            return float(token)

        # Reference
        ref_match = cls.REFERENCE_PATTERN.match(token)
        if ref_match:
            ref_value = ref_match.group(1)
            # Check for namespaced reference :type:id
            if ':' in ref_value:
                parts = ref_value.split(':', 1)
                return Reference(id=parts[1], type=parts[0])
            return Reference(id=ref_value)

        # Default: string
        return token


# =============================================================================
# Parser
# =============================================================================

class Parser:
    """Main ISON parser"""

    def __init__(self, text: str):
        self.text = text
        self.lines = text.split('\n')
        self.line_num = 0
        self.document = Document()

    def parse(self) -> Document:
        """Parse the entire document"""
        while self.line_num < len(self.lines):
            self._skip_empty_and_comments()
            if self.line_num >= len(self.lines):
                break

            block = self._parse_block()
            if block:
                self.document.blocks.append(block)

        return self.document

    def _current_line(self) -> str:
        """Get current line"""
        if self.line_num < len(self.lines):
            return self.lines[self.line_num]
        return ""

    def _skip_empty_and_comments(self):
        """Skip blank lines and comments"""
        while self.line_num < len(self.lines):
            line = self._current_line().strip()
            if line == "" or line.startswith('#'):
                self.line_num += 1
            else:
                break

    def _parse_block(self) -> Optional[Block]:
        """Parse a single block"""
        # Parse header
        header_line = self._current_line().strip()
        if '.' not in header_line:
            raise ISONSyntaxError(
                f"Invalid block header: '{header_line}' (expected 'kind.name')",
                self.line_num + 1, 0
            )

        kind, name = header_line.split('.', 1)
        self.line_num += 1

        # Parse fields
        self._skip_empty_and_comments()
        if self.line_num >= len(self.lines):
            raise ISONSyntaxError(
                f"Block '{kind}.{name}' missing field definitions",
                self.line_num + 1, 0
            )

        fields_line = self._current_line()
        tokenizer = Tokenizer(fields_line, self.line_num + 1)
        raw_fields = tokenizer.tokenize()
        self.line_num += 1

        # Parse field info (extract type annotations like id:int, name:string)
        field_info_list = []
        fields = []
        for raw_field in raw_fields:
            fi = FieldInfo.parse(raw_field)
            field_info_list.append(fi)
            fields.append(fi.name)  # Store just the field name for rows

        # Parse data rows
        rows = []
        summary = None
        while self.line_num < len(self.lines):
            line = self._current_line()
            stripped = line.strip()

            # Stop at blank line (block separator)
            if stripped == "":
                break

            # Skip comments within data section
            if stripped.startswith('#'):
                self.line_num += 1
                continue

            # Check for summary separator (---)
            if stripped.startswith('---'):
                self.line_num += 1
                # Next non-empty line is the summary
                while self.line_num < len(self.lines):
                    summary_line = self._current_line().strip()
                    if summary_line and not summary_line.startswith('#'):
                        summary = summary_line
                        self.line_num += 1
                        break
                    elif summary_line == "":
                        break
                    self.line_num += 1
                continue

            # Check for new block header
            if '.' in stripped and len(stripped.split()) == 1:
                if self._looks_like_header(stripped):
                    break

            row = self._parse_data_row(fields, line)
            rows.append(row)
            self.line_num += 1

        return Block(
            kind=kind,
            name=name,
            fields=fields,
            rows=rows,
            field_info=field_info_list,
            summary=summary
        )

    def _looks_like_header(self, line: str) -> bool:
        """Check if line looks like a block header"""
        if '.' not in line:
            return False
        parts = line.split('.')
        if len(parts) != 2:
            return False
        kind, name = parts
        # Valid identifiers
        id_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_-]*$')
        return bool(id_pattern.match(kind) and id_pattern.match(name))

    def _parse_data_row(self, fields: list[str], line: str) -> dict[str, Any]:
        """Parse a data row into a dictionary"""
        tokenizer = Tokenizer(line, self.line_num + 1)
        raw_tokens = tokenizer.tokenize()

        # Track which tokens were quoted
        values = []
        token_idx = 0
        pos = 0

        for raw_token in raw_tokens:
            # Find this token in the original line to check if quoted
            while pos < len(line) and line[pos] in ' \t':
                pos += 1

            was_quoted = pos < len(line) and line[pos] == '"'
            typed_value = TypeInferrer.infer(raw_token, was_quoted)
            values.append(typed_value)

            # Advance past this token
            if was_quoted:
                # Skip the quoted string
                pos += 1
                while pos < len(line) and line[pos] != '"':
                    if line[pos] == '\\':
                        pos += 1
                    pos += 1
                pos += 1
            else:
                pos += len(raw_token)

        # Build row dictionary
        row = {}
        for i, field_name in enumerate(fields):
            if i < len(values):
                value = values[i]
            else:
                value = None  # Missing trailing value

            # Handle dot-path fields
            if '.' in field_name:
                self._set_nested_value(row, field_name, value)
            else:
                row[field_name] = value

        return row

    def _set_nested_value(self, obj: dict, path: str, value: Any):
        """Set a value in a nested dictionary using dot-path notation"""
        parts = path.split('.')
        current = obj

        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value


# =============================================================================
# Serializer
# =============================================================================

class Serializer:
    """Serialize Python objects to ISON format"""

    @classmethod
    def dumps(cls, doc: Document, align_columns: bool = True) -> str:
        """Serialize a Document to ISON string"""
        blocks_output = []

        for block in doc.blocks:
            block_str = cls._serialize_block(block, align_columns)
            blocks_output.append(block_str)

        return '\n\n'.join(blocks_output)

    @classmethod
    def _serialize_block(cls, block: Block, align_columns: bool) -> str:
        """Serialize a single block"""
        lines = []

        # Header
        lines.append(f"{block.kind}.{block.name}")

        # Fields (with type annotations if present)
        if block.field_info:
            field_strs = []
            for fi in block.field_info:
                if fi.type:
                    field_strs.append(f"{fi.name}:{fi.type}")
                else:
                    field_strs.append(fi.name)
            lines.append(' '.join(field_strs))
        else:
            lines.append(' '.join(block.fields))

        # Calculate column widths for alignment
        if align_columns and block.rows:
            col_widths = cls._calculate_column_widths(block)
        else:
            col_widths = None

        # Data rows
        for row in block.rows:
            values = []
            for i, field in enumerate(block.fields):
                value = cls._get_nested_value(row, field)
                str_value = cls._value_to_ison(value)

                if col_widths:
                    str_value = str_value.ljust(col_widths[i])

                values.append(str_value)

            lines.append(' '.join(values).rstrip())

        # Summary row (if present)
        if block.summary:
            lines.append('---')
            lines.append(block.summary)

        return '\n'.join(lines)

    @classmethod
    def _calculate_column_widths(cls, block: Block) -> list[int]:
        """Calculate maximum width for each column"""
        widths = [len(f) for f in block.fields]

        for row in block.rows:
            for i, field in enumerate(block.fields):
                value = cls._get_nested_value(row, field)
                str_value = cls._value_to_ison(value)
                widths[i] = max(widths[i], len(str_value))

        return widths

    @classmethod
    def _get_nested_value(cls, obj: dict, path: str) -> Any:
        """Get a value from nested dictionary using dot-path"""
        parts = path.split('.')
        current = obj

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    @classmethod
    def _value_to_ison(cls, value: Any) -> str:
        """Convert a Python value to ISON string representation"""
        if value is None:
            return 'null'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, Reference):
            return value.to_ison()

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            return cls._quote_if_needed(value)

        # Handle arrays - JSON encode them as a string
        if isinstance(value, list):
            json_str = json.dumps(value)
            return cls._quote_if_needed(json_str)

        # Handle nested objects - JSON encode them as a string
        if isinstance(value, dict):
            json_str = json.dumps(value)
            return cls._quote_if_needed(json_str)

        # Fallback for other types
        return cls._quote_if_needed(str(value))

    @classmethod
    def _quote_if_needed(cls, s: str) -> str:
        """Quote a string if it contains spaces or special characters"""
        if not s:
            return '""'

        # Check if quoting is needed
        needs_quote = (
            ' ' in s or
            '\t' in s or
            '"' in s or
            '\n' in s or
            s in ('true', 'false', 'null') or
            s.startswith(':') or
            cls._looks_like_number(s)
        )

        if needs_quote:
            # Escape special characters
            escaped = s.replace('\\', '\\\\')
            escaped = escaped.replace('"', '\\"')
            escaped = escaped.replace('\n', '\\n')
            escaped = escaped.replace('\t', '\\t')
            escaped = escaped.replace('\r', '\\r')
            return f'"{escaped}"'

        return s

    @classmethod
    def _looks_like_number(cls, s: str) -> bool:
        """Check if string looks like a number"""
        try:
            float(s)
            return True
        except ValueError:
            return False


# =============================================================================
# Public API
# =============================================================================

def loads(text: str) -> Document:
    """
    Parse an ISON string into a Document.

    Args:
        text: ISON formatted string

    Returns:
        Document object containing parsed blocks

    Raises:
        ISONSyntaxError: If parsing fails
    """
    parser = Parser(text)
    return parser.parse()


def load(path: str | Path) -> Document:
    """
    Load and parse an ISON file.

    Args:
        path: Path to .ison file

    Returns:
        Document object containing parsed blocks
    """
    path = Path(path)
    text = path.read_text(encoding='utf-8')
    return loads(text)


def dumps(doc: Document, align_columns: bool = True) -> str:
    """
    Serialize a Document to ISON string.

    Args:
        doc: Document to serialize
        align_columns: Whether to align columns for readability

    Returns:
        ISON formatted string
    """
    return Serializer.dumps(doc, align_columns)


def dump(doc: Document, path: str | Path, align_columns: bool = True):
    """
    Serialize a Document and write to file.

    Args:
        doc: Document to serialize
        path: Output file path
        align_columns: Whether to align columns
    """
    path = Path(path)
    text = dumps(doc, align_columns)
    path.write_text(text, encoding='utf-8')


def from_dict(data: dict, kind: str = "object") -> Document:
    """
    Create an ISON Document from a dictionary.

    Args:
        data: Dictionary with block names as keys
        kind: Default block kind

    Returns:
        Document object
    """
    doc = Document()

    for name, content in data.items():
        if isinstance(content, list):
            # Table with multiple rows
            if content and isinstance(content[0], dict):
                # Collect all unique fields from all objects in array
                field_set = set()
                for item in content:
                    if isinstance(item, dict):
                        field_set.update(item.keys())
                fields = list(field_set)
                rows = content
            else:
                continue
            block_kind = "table"
        elif isinstance(content, dict):
            # Single object
            fields = list(content.keys())
            rows = [content]
            block_kind = "object"
        else:
            continue

        block = Block(kind=block_kind, name=name, fields=fields, rows=rows)
        doc.blocks.append(block)

    return doc


# =============================================================================
# ISONL (ISON Lines) Support
# =============================================================================

@dataclass
class ISONLRecord:
    """Represents a single ISONL record (one line)"""
    kind: str
    name: str
    fields: list[str]
    values: dict[str, Any]

    def __repr__(self):
        return f"ISONLRecord({self.kind}.{self.name}, {self.values})"

    def to_block_key(self) -> str:
        """Get the block identifier for grouping"""
        return f"{self.kind}.{self.name}"


class ISONLParser:
    """Parser for ISONL (ISON Lines) format"""

    ESCAPE_MAP = {
        '"': '"',
        '\\': '\\',
        'n': '\n',
        't': '\t',
        'r': '\r',
        '|': '|',
    }

    def __init__(self):
        self.line_num = 0

    def parse_line(self, line: str, line_num: int = 0) -> Optional[ISONLRecord]:
        """
        Parse a single ISONL line.

        Format: kind.name|field1 field2 field3|value1 value2 value3

        Args:
            line: The ISONL line to parse
            line_num: Line number for error reporting

        Returns:
            ISONLRecord or None if line is empty/comment
        """
        self.line_num = line_num
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            return None

        # Split by pipe - must have exactly 3 sections
        sections = self._split_by_pipe(line)

        if len(sections) != 3:
            raise ISONSyntaxError(
                f"ISONL line must have exactly 3 pipe-separated sections, got {len(sections)}",
                line_num, 0
            )

        header, fields_str, values_str = sections

        # Parse header (kind.name)
        if '.' not in header:
            raise ISONSyntaxError(
                f"Invalid ISONL header: '{header}' (expected 'kind.name')",
                line_num, 0
            )
        kind, name = header.split('.', 1)

        # Parse fields
        tokenizer = Tokenizer(fields_str, line_num)
        fields = tokenizer.tokenize()

        # Parse values
        values_tokenizer = Tokenizer(values_str, line_num)
        raw_values = values_tokenizer.tokenize()

        # Infer types for values
        typed_values = []
        pos = 0
        for raw_value in raw_values:
            # Find this token to check if quoted
            while pos < len(values_str) and values_str[pos] in ' \t':
                pos += 1
            was_quoted = pos < len(values_str) and values_str[pos] == '"'
            typed_values.append(TypeInferrer.infer(raw_value, was_quoted))
            if was_quoted:
                pos += 1
                while pos < len(values_str) and values_str[pos] != '"':
                    if values_str[pos] == '\\':
                        pos += 1
                    pos += 1
                pos += 1
            else:
                pos += len(raw_value)

        # Zip fields and values
        values_dict = {}
        for i, field in enumerate(fields):
            if i < len(typed_values):
                values_dict[field] = typed_values[i]
            else:
                values_dict[field] = None

        return ISONLRecord(kind=kind, name=name, fields=fields, values=values_dict)

    def _split_by_pipe(self, line: str) -> list[str]:
        """Split line by unquoted pipe characters"""
        sections = []
        current = []
        in_quotes = False
        i = 0

        while i < len(line):
            char = line[i]

            if char == '"' and (i == 0 or line[i-1] != '\\'):
                in_quotes = not in_quotes
                current.append(char)
            elif char == '|' and not in_quotes:
                sections.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

            i += 1

        # Add the last section
        sections.append(''.join(current).strip())

        return sections

    def parse_string(self, text: str) -> list[ISONLRecord]:
        """
        Parse multiple ISONL lines from a string.

        Args:
            text: Multi-line ISONL string

        Returns:
            List of ISONLRecord objects
        """
        records = []
        for i, line in enumerate(text.split('\n'), 1):
            record = self.parse_line(line, i)
            if record:
                records.append(record)
        return records

    def parse_to_document(self, text: str) -> Document:
        """
        Parse ISONL string and convert to ISON Document.

        Groups records by block header and creates ISON blocks.

        Args:
            text: ISONL formatted string

        Returns:
            Document object
        """
        records = self.parse_string(text)
        return self._records_to_document(records)

    def _records_to_document(self, records: list[ISONLRecord]) -> Document:
        """Convert list of records to Document, grouping by block"""
        from collections import OrderedDict

        blocks_map: OrderedDict[str, list[ISONLRecord]] = OrderedDict()

        for record in records:
            key = record.to_block_key()
            if key not in blocks_map:
                blocks_map[key] = []
            blocks_map[key].append(record)

        doc = Document()
        for key, recs in blocks_map.items():
            kind, name = key.split('.', 1)
            # Use fields from first record
            fields = recs[0].fields
            rows = [r.values for r in recs]

            block = Block(kind=kind, name=name, fields=fields, rows=rows)
            doc.blocks.append(block)

        return doc


class ISONLSerializer:
    """Serialize to ISONL format"""

    @classmethod
    def dumps(cls, doc: Document) -> str:
        """
        Serialize a Document to ISONL string.

        Each row becomes a separate line.

        Args:
            doc: Document to serialize

        Returns:
            ISONL formatted string
        """
        lines = []

        for block in doc.blocks:
            header = f"{block.kind}.{block.name}"
            fields_str = ' '.join(block.fields)

            for row in block.rows:
                values = []
                for field in block.fields:
                    value = row.get(field)
                    values.append(cls._value_to_isonl(value))

                values_str = ' '.join(values)
                line = f"{header}|{fields_str}|{values_str}"
                lines.append(line)

        return '\n'.join(lines)

    @classmethod
    def _value_to_isonl(cls, value: Any) -> str:
        """Convert a value to ISONL string representation"""
        if value is None:
            return 'null'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, Reference):
            return value.to_ison()

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            return cls._quote_if_needed(value)

        if isinstance(value, (list, dict)):
            json_str = json.dumps(value)
            return cls._quote_if_needed(json_str)

        return cls._quote_if_needed(str(value))

    @classmethod
    def _quote_if_needed(cls, s: str) -> str:
        """Quote string if it contains special characters"""
        if not s:
            return '""'

        needs_quote = (
            ' ' in s or
            '\t' in s or
            '"' in s or
            '\n' in s or
            '|' in s or
            s in ('true', 'false', 'null') or
            s.startswith(':')
        )

        # Check if it looks like a number
        try:
            float(s)
            needs_quote = True
        except ValueError:
            pass

        if needs_quote:
            escaped = s.replace('\\', '\\\\')
            escaped = escaped.replace('"', '\\"')
            escaped = escaped.replace('\n', '\\n')
            escaped = escaped.replace('\t', '\\t')
            escaped = escaped.replace('\r', '\\r')
            escaped = escaped.replace('|', '\\|')
            return f'"{escaped}"'

        return s


def isonl_stream(file_handle) -> Generator[ISONLRecord, None, None]:
    """
    Stream parse ISONL from a file handle.

    Yields ISONLRecord objects one at a time for memory-efficient processing.

    Args:
        file_handle: File-like object to read from

    Yields:
        ISONLRecord objects

    Example:
        with open('data.isonl') as f:
            for record in isonl_stream(f):
                process(record)
    """
    parser = ISONLParser()
    for i, line in enumerate(file_handle, 1):
        record = parser.parse_line(line, i)
        if record:
            yield record


def loads_isonl(text: str) -> Document:
    """
    Parse an ISONL string into a Document.

    Args:
        text: ISONL formatted string

    Returns:
        Document object containing parsed blocks
    """
    parser = ISONLParser()
    return parser.parse_to_document(text)


def load_isonl(path: str | Path) -> Document:
    """
    Load and parse an ISONL file.

    Args:
        path: Path to .isonl file

    Returns:
        Document object
    """
    path = Path(path)
    text = path.read_text(encoding='utf-8')
    return loads_isonl(text)


def dumps_isonl(doc: Document) -> str:
    """
    Serialize a Document to ISONL string.

    Args:
        doc: Document to serialize

    Returns:
        ISONL formatted string
    """
    return ISONLSerializer.dumps(doc)


def dump_isonl(doc: Document, path: str | Path):
    """
    Serialize a Document and write to ISONL file.

    Args:
        doc: Document to serialize
        path: Output file path
    """
    path = Path(path)
    text = dumps_isonl(doc)
    path.write_text(text, encoding='utf-8')


def ison_to_isonl(ison_text: str) -> str:
    """
    Convert ISON format to ISONL format.

    Args:
        ison_text: ISON formatted string

    Returns:
        ISONL formatted string
    """
    doc = loads(ison_text)
    return dumps_isonl(doc)


def isonl_to_ison(isonl_text: str) -> str:
    """
    Convert ISONL format to ISON format.

    Args:
        isonl_text: ISONL formatted string

    Returns:
        ISON formatted string
    """
    doc = loads_isonl(isonl_text)
    return dumps(doc)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Command-line interface for ISON parser"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='ISON v1.0 Parser - Interchange Simple Object Notation'
    )
    parser.add_argument(
        'input',
        nargs='?',
        help='Input ISON file (or stdin if not provided)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file (stdout if not provided)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['ison', 'json'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate only, no output'
    )

    args = parser.parse_args()

    # Read input
    if args.input:
        try:
            doc = load(args.input)
        except FileNotFoundError:
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        except ISONError as e:
            print(f"Parse error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Read from stdin
        text = sys.stdin.read()
        try:
            doc = loads(text)
        except ISONError as e:
            print(f"Parse error: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate mode
    if args.validate:
        print(f"Valid ISON: {len(doc.blocks)} block(s)")
        for block in doc.blocks:
            print(f"  - {block.kind}.{block.name}: {len(block.rows)} row(s)")
        sys.exit(0)

    # Generate output
    if args.format == 'json':
        output = doc.to_json(indent=2)
    else:
        output = dumps(doc)

    # Write output
    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
    else:
        print(output)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Version
    '__version__',

    # Classes
    'Reference',
    'FieldInfo',
    'Block',
    'Document',
    'ISONError',
    'ISONSyntaxError',
    'ISONTypeError',
    'ISONLRecord',
    'ISONLParser',
    'ISONLSerializer',

    # ISON Functions
    'loads',
    'load',
    'dumps',
    'dump',
    'from_dict',

    # ISONL Functions
    'loads_isonl',
    'load_isonl',
    'dumps_isonl',
    'dump_isonl',
    'isonl_stream',
    'ison_to_isonl',
    'isonl_to_ison',

    # CLI
    'main',

    # Plugins (import from ison_parser.plugins)
    'plugins',

    # Integrations (import from ison_parser.integrations)
    'integrations',
]

# Lazy load plugins and integrations to avoid import errors if dependencies aren't installed
def __getattr__(name):
    if name == 'plugins':
        from . import plugins
        return plugins
    if name == 'integrations':
        from . import integrations
        return integrations
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == '__main__':
    main()
