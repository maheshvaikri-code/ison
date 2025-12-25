"""
LangChain ISON OutputParser

Provides LangChain-compatible output parsers for ISON format responses.
Enables token-efficient structured outputs in LangChain workflows.

Usage:
    from langchain.llms import OpenAI
    from ison_parser.integrations import ISONOutputParser

    parser = ISONOutputParser()
    llm = OpenAI()

    # Get ISON response from LLM
    response = llm.predict(prompt + parser.get_format_instructions())
    parsed = parser.parse(response)

    # With ISONantic typed models
    from isonantic import TableModel, Field

    class User(TableModel):
        __ison_block__ = "table.users"
        id: int = Field(primary_key=True)
        name: str
        email: str

    parser = ISONOutputParser(model=User)
    users = parser.parse(response)  # Returns List[User]

Requirements:
    pip install langchain langchain-core
    pip install isonantic  # Optional, for typed models
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Generic
import re

try:
    from langchain_core.output_parsers import BaseOutputParser
    from langchain_core.exceptions import OutputParserException
    LANGCHAIN_AVAILABLE = True
except ImportError:
    # Fallback for older langchain versions
    try:
        from langchain.schema import BaseOutputParser, OutputParserException
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        LANGCHAIN_AVAILABLE = False
        BaseOutputParser = object
        OutputParserException = Exception

# Import ISON parser
import ison_parser
from ison_parser import Document, Block, loads, ISONError, ISONSyntaxError

# Try to import ISONantic for typed model support
try:
    from isonantic import (
        ISONModel, TableModel, ObjectModel,
        parse_ison, parse_llm_output, parse_ison_safe,
        prompt_for_model, generate_schema, ValidationError,
    )
    ISONANTIC_AVAILABLE = True
except ImportError:
    ISONANTIC_AVAILABLE = False
    ISONModel = None
    TableModel = None
    ObjectModel = None


T = TypeVar("T")
M = TypeVar("M")  # For ISONantic models


class ISONOutputParser(BaseOutputParser[Document]):
    """
    LangChain OutputParser for ISON format.

    Parses LLM responses in ISON format to structured Document objects.
    Provides 30-70% token savings compared to JSON output parsers.

    Supports both raw ISON parsing and ISONantic typed models.

    Attributes:
        strict: If True, raises on parse errors. If False, attempts recovery.
        expected_blocks: Optional list of expected block names for validation.
        model: Optional ISONantic model class for typed parsing.

    Example (raw ISON):
        >>> parser = ISONOutputParser()
        >>> doc = parser.parse('''
        ... table.users
        ... id name email
        ... 1 Alice alice@example.com
        ... ''')
        >>> doc['users'].rows[0]['name']
        'Alice'

    Example (ISONantic model):
        >>> from isonantic import TableModel, Field
        >>> class User(TableModel):
        ...     __ison_block__ = "table.users"
        ...     id: int = Field(primary_key=True)
        ...     name: str
        >>> parser = ISONOutputParser(model=User)
        >>> users = parser.parse(response)  # Returns List[User]
    """

    strict: bool = False
    expected_blocks: Optional[List[str]] = None
    model: Optional[Type] = None

    def __init__(
        self,
        strict: bool = False,
        expected_blocks: Optional[List[str]] = None,
        model: Optional[Type] = None,
        **kwargs
    ):
        """
        Initialize the ISON output parser.

        Args:
            strict: If True, raises on any parse error. Default False.
            expected_blocks: Optional list of block names to validate.
            model: Optional ISONantic model class for typed parsing.
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required for ISONOutputParser. "
                "Install with: pip install langchain langchain-core"
            )
        if model is not None and not ISONANTIC_AVAILABLE:
            raise ImportError(
                "ISONantic is required for typed model parsing. "
                "Install with: pip install isonantic"
            )
        super().__init__(**kwargs)
        self.strict = strict
        self.expected_blocks = expected_blocks
        self.model = model

    @property
    def _type(self) -> str:
        """Return the parser type identifier."""
        return "ison"

    def get_format_instructions(self) -> str:
        """
        Get instructions for the LLM on how to format ISON output.

        If an ISONantic model is provided, generates schema-specific instructions.

        Returns:
            String with ISON formatting instructions.
        """
        # If ISONantic model provided, use its schema for instructions
        if self.model is not None and ISONANTIC_AVAILABLE:
            return prompt_for_model(self.model)

        instructions = """Format your response using ISON (Interchange Simple Object Notation).

ISON Format Rules:
1. Tables: Start with `table.name`, followed by field names, then data rows
2. Objects: Start with `object.name`, followed by key-value pairs
3. Values are space-separated, quote strings with spaces
4. Use `:id` for references to other records
5. Booleans: true/false, null for missing values

Example table:
```
table.users
id name email active
1 Alice alice@example.com true
2 Bob "Bob Smith" false
```

Example object:
```
object.config
timeout 30
debug true
api_key "sk-xxx"
```

Respond ONLY with valid ISON, no additional text."""

        if self.expected_blocks:
            instructions += f"\n\nExpected blocks: {', '.join(self.expected_blocks)}"

        return instructions

    def parse(self, text: str) -> Union[Document, List[Any]]:
        """
        Parse LLM output text to ISON Document or typed models.

        If an ISONantic model is configured, returns List[Model].
        Otherwise returns a raw Document.

        Args:
            text: Raw LLM output containing ISON data.

        Returns:
            Parsed Document object, or List[Model] if model is set.

        Raises:
            OutputParserException: If parsing fails and strict mode is enabled.
        """
        # Extract ISON from potential markdown code blocks
        ison_text = self._extract_ison(text)

        # If ISONantic model is configured, use typed parsing
        if self.model is not None and ISONANTIC_AVAILABLE:
            return self._parse_with_model(ison_text, text)

        # Raw ISON parsing
        try:
            doc = loads(ison_text)

            # Validate expected blocks if specified
            if self.expected_blocks:
                self._validate_blocks(doc)

            return doc

        except ISONSyntaxError as e:
            if self.strict:
                raise OutputParserException(
                    f"Failed to parse ISON: {e}\n\nRaw output:\n{text}"
                )
            # Attempt recovery
            return self._attempt_recovery(text, e)

        except ISONError as e:
            if self.strict:
                raise OutputParserException(
                    f"ISON error: {e}\n\nRaw output:\n{text}"
                )
            return Document()

    def _parse_with_model(self, ison_text: str, raw_text: str) -> List[Any]:
        """
        Parse ISON text using ISONantic model for typed validation.

        Args:
            ison_text: Extracted ISON text.
            raw_text: Original raw text for error reporting.

        Returns:
            List of validated model instances.
        """
        try:
            # Use ISONantic's LLM output parser for better error recovery
            models = parse_llm_output(ison_text, self.model, strict=self.strict)
            return models

        except ValidationError as e:
            if self.strict:
                raise OutputParserException(
                    f"Validation failed: {e}\n\nRaw output:\n{raw_text}"
                )
            # Try safe parsing for partial recovery
            result = parse_ison_safe(ison_text, self.model)
            if result.partial_data:
                return result.partial_data
            return []

        except Exception as e:
            if self.strict:
                raise OutputParserException(
                    f"Parse error: {e}\n\nRaw output:\n{raw_text}"
                )
            return []

    def _extract_ison(self, text: str) -> str:
        """
        Extract ISON content from text, handling markdown code blocks.

        Args:
            text: Raw text potentially containing markdown.

        Returns:
            Extracted ISON content.
        """
        # Try to extract from markdown code blocks
        code_block_pattern = r'```(?:ison)?\s*\n(.*?)\n```'
        matches = re.findall(code_block_pattern, text, re.DOTALL)

        if matches:
            return '\n\n'.join(matches)

        # Check for inline code blocks
        inline_pattern = r'`([^`]+)`'

        # If no code blocks, check if it starts with a block header
        lines = text.strip().split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if '.' in stripped and len(stripped.split()) == 1:
                # Looks like a block header, return from here
                return '\n'.join(lines[i:])

        return text

    def _validate_blocks(self, doc: Document) -> None:
        """
        Validate that expected blocks are present.

        Args:
            doc: Parsed document to validate.

        Raises:
            OutputParserException: If expected blocks are missing.
        """
        if not self.expected_blocks:
            return

        found_blocks = {block.name for block in doc.blocks}
        missing = set(self.expected_blocks) - found_blocks

        if missing:
            raise OutputParserException(
                f"Missing expected blocks: {missing}. "
                f"Found: {found_blocks}"
            )

    def _attempt_recovery(self, text: str, error: Exception) -> Document:
        """
        Attempt to recover partial data from malformed ISON.

        Args:
            text: Original text that failed to parse.
            error: The parse error that occurred.

        Returns:
            Partial Document with recovered data.
        """
        doc = Document()

        # Try parsing line by line
        lines = text.strip().split('\n')
        current_block = None
        current_fields = []
        current_rows = []

        for line in lines:
            stripped = line.strip()

            if not stripped or stripped.startswith('#'):
                continue

            # Check for block header
            if '.' in stripped and len(stripped.split()) == 1:
                # Save previous block
                if current_block and current_fields:
                    block = Block(
                        kind=current_block[0],
                        name=current_block[1],
                        fields=current_fields,
                        rows=current_rows
                    )
                    doc.blocks.append(block)

                # Start new block
                parts = stripped.split('.', 1)
                if len(parts) == 2:
                    current_block = (parts[0], parts[1])
                    current_fields = []
                    current_rows = []
                continue

            # If we have a block, try to parse fields or data
            if current_block:
                if not current_fields:
                    # This should be the field line
                    current_fields = stripped.split()
                else:
                    # Try to parse as data row
                    try:
                        values = stripped.split()
                        if len(values) == len(current_fields):
                            row = dict(zip(current_fields, values))
                            current_rows.append(row)
                    except:
                        pass

        # Save final block
        if current_block and current_fields:
            block = Block(
                kind=current_block[0],
                name=current_block[1],
                fields=current_fields,
                rows=current_rows
            )
            doc.blocks.append(block)

        return doc


class ISONListOutputParser(BaseOutputParser[List[Dict[str, Any]]]):
    """
    OutputParser that returns ISON data as a list of dictionaries.

    Useful when you need simple list output without Document wrapper.

    Example:
        >>> parser = ISONListOutputParser(block_name="users")
        >>> users = parser.parse(ison_text)
        >>> users[0]['name']
        'Alice'
    """

    block_name: Optional[str] = None

    def __init__(self, block_name: Optional[str] = None, **kwargs):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required. Install with: pip install langchain"
            )
        super().__init__(**kwargs)
        self.block_name = block_name

    @property
    def _type(self) -> str:
        return "ison_list"

    def get_format_instructions(self) -> str:
        instructions = """Format your response as an ISON table.

Example:
```
table.items
id name value
1 first 100
2 second 200
```"""
        return instructions

    def parse(self, text: str) -> List[Dict[str, Any]]:
        """Parse ISON to list of dictionaries."""
        base_parser = ISONOutputParser(strict=False)
        doc = base_parser.parse(text)

        if not doc.blocks:
            return []

        # Return specified block or first block
        if self.block_name:
            block = doc[self.block_name]
            if block:
                return block.rows
            return []

        return doc.blocks[0].rows


class ISONDictOutputParser(BaseOutputParser[Dict[str, Any]]):
    """
    OutputParser for ISON object blocks returning a single dictionary.

    Example:
        >>> parser = ISONDictOutputParser()
        >>> config = parser.parse('''
        ... object.config
        ... timeout 30
        ... debug true
        ... ''')
        >>> config['timeout']
        30
    """

    object_name: Optional[str] = None

    def __init__(self, object_name: Optional[str] = None, **kwargs):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required. Install with: pip install langchain"
            )
        super().__init__(**kwargs)
        self.object_name = object_name

    @property
    def _type(self) -> str:
        return "ison_dict"

    def get_format_instructions(self) -> str:
        return """Format your response as an ISON object.

Example:
```
object.result
key1 value1
key2 "value with spaces"
count 42
active true
```"""

    def parse(self, text: str) -> Dict[str, Any]:
        """Parse ISON to dictionary."""
        base_parser = ISONOutputParser(strict=False)
        doc = base_parser.parse(text)

        if not doc.blocks:
            return {}

        # Find object block
        for block in doc.blocks:
            if block.kind == "object":
                if self.object_name is None or block.name == self.object_name:
                    if block.rows:
                        return block.rows[0]

        # Fallback to first block
        if doc.blocks[0].rows:
            return doc.blocks[0].rows[0]

        return {}


class ISONanticOutputParser(BaseOutputParser[List[Any]]):
    """
    OutputParser for ISONantic typed models.

    Provides full ISONantic integration with type validation,
    field constraints, and reference resolution.

    Example:
        >>> from isonantic import TableModel, Field, Reference
        >>>
        >>> class User(TableModel):
        ...     __ison_block__ = "table.users"
        ...     id: int = Field(primary_key=True)
        ...     name: str = Field(min_length=1)
        ...     email: str = Field(pattern=r".*@.*")
        ...     team: Optional[Reference["Team"]] = None
        >>>
        >>> parser = ISONanticOutputParser(model=User)
        >>> users = parser.parse(response)
        >>> for user in users:
        ...     print(f"{user.name}: {user.email}")
    """

    model: Type = None
    strict: bool = False
    auto_fix: bool = True

    def __init__(
        self,
        model: Type,
        strict: bool = False,
        auto_fix: bool = True,
        **kwargs
    ):
        """
        Initialize the ISONantic output parser.

        Args:
            model: ISONantic model class (TableModel, ObjectModel, etc.)
            strict: Raise on validation errors (default: False)
            auto_fix: Attempt to fix common LLM output issues (default: True)
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required. Install with: pip install langchain"
            )
        if not ISONANTIC_AVAILABLE:
            raise ImportError(
                "ISONantic is required for ISONanticOutputParser. "
                "Install with: pip install isonantic"
            )
        super().__init__(**kwargs)
        self.model = model
        self.strict = strict
        self.auto_fix = auto_fix

    @property
    def _type(self) -> str:
        return "isonantic"

    def get_format_instructions(self) -> str:
        """
        Get schema-aware format instructions for the model.

        Returns:
            Detailed instructions including field types and constraints.
        """
        return prompt_for_model(self.model)

    def parse(self, text: str) -> List[Any]:
        """
        Parse LLM output to validated ISONantic model instances.

        Args:
            text: Raw LLM response.

        Returns:
            List of validated model instances.

        Raises:
            OutputParserException: If parsing/validation fails in strict mode.
        """
        try:
            models = parse_llm_output(
                text,
                self.model,
                strict=self.strict,
                auto_fix=self.auto_fix
            )
            return models

        except ValidationError as e:
            if self.strict:
                raise OutputParserException(
                    f"Validation failed: {e}\n\n"
                    f"Model: {self.model.__name__}\n"
                    f"Errors: {e.errors()}"
                )
            # Try partial recovery
            result = parse_ison_safe(text, self.model)
            return result.partial_data or []

        except Exception as e:
            if self.strict:
                raise OutputParserException(f"Parse error: {e}")
            return []

    def get_json_schema(self) -> Dict[str, Any]:
        """
        Get JSON Schema for the model.

        Useful for OpenAI function calling or other schema-based tools.

        Returns:
            JSON Schema dictionary.
        """
        return self.model.model_json_schema()

    @classmethod
    def from_model(cls, model: Type, **kwargs) -> "ISONanticOutputParser":
        """
        Create parser from model class.

        Args:
            model: ISONantic model class.
            **kwargs: Additional parser options.

        Returns:
            Configured ISONanticOutputParser.
        """
        return cls(model=model, **kwargs)


class ISONLOutputParser(BaseOutputParser[List[Dict[str, Any]]]):
    """
    LangChain OutputParser for ISONL (ISON Lines) streaming format.

    Parses line-by-line ISONL responses, ideal for streaming LLM outputs,
    fine-tuning datasets, and event logs.

    Supports both batch parsing and incremental streaming parsing.

    Attributes:
        strict: If True, raises on parse errors. If False, skips malformed lines.
        model: Optional ISONantic model class for typed parsing.
        buffer: Internal buffer for incremental parsing.

    Example (batch parsing):
        >>> parser = ISONLOutputParser()
        >>> records = parser.parse('''
        ... table.users: 1 Alice alice@example.com
        ... table.users: 2 Bob bob@example.com
        ... ''')
        >>> records[0]['name']
        'Alice'

    Example (streaming):
        >>> parser = ISONLOutputParser()
        >>> for chunk in llm.stream(prompt):
        ...     records = parser.parse_stream(chunk)
        ...     for record in records:
        ...         process(record)
    """

    strict: bool = False
    model: Optional[Type] = None
    _buffer: str = ""
    _schema_cache: Dict[str, List[str]] = {}

    def __init__(
        self,
        strict: bool = False,
        model: Optional[Type] = None,
        **kwargs
    ):
        """
        Initialize the ISONL output parser.

        Args:
            strict: If True, raises on any parse error. Default False.
            model: Optional ISONantic model class for typed parsing.
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required for ISONLOutputParser. "
                "Install with: pip install langchain langchain-core"
            )
        if model is not None and not ISONANTIC_AVAILABLE:
            raise ImportError(
                "ISONantic is required for typed model parsing. "
                "Install with: pip install isonantic"
            )
        super().__init__(**kwargs)
        self.strict = strict
        self.model = model
        self._buffer = ""
        self._schema_cache = {}

    @property
    def _type(self) -> str:
        """Return the parser type identifier."""
        return "isonl"

    def get_format_instructions(self) -> str:
        """
        Get instructions for the LLM on how to format ISONL output.

        Returns:
            String with ISONL formatting instructions.
        """
        if self.model is not None and ISONANTIC_AVAILABLE:
            schema = prompt_for_model(self.model)
            return f"""Format your response using ISONL (ISON Lines) streaming format.

Each line is a complete record in this format:
block.name: field1 field2 field3 ...

{schema}

Example ISONL:
```
table.users: 1 Alice alice@example.com true
table.users: 2 Bob bob@example.com false
```

Output one record per line. Each line must be parseable independently."""

        return """Format your response using ISONL (ISON Lines) streaming format.

ISONL Format Rules:
1. Each line is a complete record
2. Format: block.name: value1 value2 value3 ...
3. First line can optionally define schema: @schema block.name: field1 field2 field3
4. Values are space-separated, quote strings with spaces
5. Use true/false for booleans, null for missing values

Example:
```
@schema table.users: id name email active
table.users: 1 Alice alice@example.com true
table.users: 2 Bob "Bob Smith" false
table.users: 3 Carol carol@example.com true
```

Output one record per line for streaming compatibility."""

    def parse(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse complete ISONL text to list of records.

        Args:
            text: ISONL formatted text with one record per line.

        Returns:
            List of parsed record dictionaries.

        Raises:
            OutputParserException: If parsing fails and strict mode is enabled.
        """
        records = []
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            record = self._parse_line(line)
            if record is not None:
                records.append(record)

        # If model is configured, validate records
        if self.model is not None and ISONANTIC_AVAILABLE and records:
            return self._validate_with_model(records)

        return records

    def parse_stream(self, chunk: str) -> List[Dict[str, Any]]:
        """
        Parse streaming chunk, returning complete records.

        Buffers partial lines and returns only complete records.
        Call flush() at the end to get any remaining buffered data.

        Args:
            chunk: Incoming text chunk from streaming LLM.

        Returns:
            List of complete records parsed from this chunk.
        """
        self._buffer += chunk
        records = []

        # Process complete lines
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            record = self._parse_line(line)
            if record is not None:
                records.append(record)

        return records

    def flush(self) -> List[Dict[str, Any]]:
        """
        Flush any remaining buffered data.

        Call this after streaming is complete to get the last record
        if it didn't end with a newline.

        Returns:
            List containing the final record, if any.
        """
        records = []
        if self._buffer.strip():
            record = self._parse_line(self._buffer.strip())
            if record is not None:
                records.append(record)
        self._buffer = ""
        return records

    def reset(self) -> None:
        """Reset the parser state for a new stream."""
        self._buffer = ""
        self._schema_cache = {}

    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single ISONL line.

        Args:
            line: Single ISONL line.

        Returns:
            Parsed record dictionary, or None if parsing failed.
        """
        try:
            # Handle schema definition lines
            if line.startswith('@schema '):
                self._parse_schema(line[8:])
                return None

            # Extract block name and values
            if ':' not in line:
                if self.strict:
                    raise OutputParserException(f"Invalid ISONL line (no colon): {line}")
                return None

            block_part, values_part = line.split(':', 1)
            block_name = block_part.strip()
            values_str = values_part.strip()

            # Parse values (handle quoted strings)
            values = self._parse_values(values_str)

            # Get schema for this block
            fields = self._schema_cache.get(block_name)

            if fields:
                # Create record with field names
                record = {'_block': block_name}
                for i, field in enumerate(fields):
                    if i < len(values):
                        record[field] = self._convert_value(values[i])
                return record
            else:
                # No schema, return indexed values
                record = {'_block': block_name, '_values': [self._convert_value(v) for v in values]}
                return record

        except Exception as e:
            if self.strict:
                raise OutputParserException(f"Failed to parse ISONL line: {line}\nError: {e}")
            return None

    def _parse_schema(self, schema_line: str) -> None:
        """
        Parse and cache a schema definition line.

        Args:
            schema_line: Schema definition (block.name: field1 field2 ...)
        """
        if ':' not in schema_line:
            return

        block_part, fields_part = schema_line.split(':', 1)
        block_name = block_part.strip()
        fields = fields_part.strip().split()
        self._schema_cache[block_name] = fields

    def _parse_values(self, values_str: str) -> List[str]:
        """
        Parse space-separated values, handling quoted strings.

        Args:
            values_str: Space-separated values string.

        Returns:
            List of value strings.
        """
        values = []
        current = ""
        in_quotes = False
        quote_char = None

        for char in values_str:
            if char in '"\'':
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                else:
                    current += char
            elif char == ' ' and not in_quotes:
                if current:
                    values.append(current)
                    current = ""
            else:
                current += char

        if current:
            values.append(current)

        return values

    def _convert_value(self, value: str) -> Any:
        """
        Convert string value to appropriate Python type.

        Args:
            value: String value to convert.

        Returns:
            Converted value (int, float, bool, None, or str).
        """
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        if value.lower() == 'null' or value == '~':
            return None

        # Try numeric conversion
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        return value

    def _validate_with_model(self, records: List[Dict[str, Any]]) -> List[Any]:
        """
        Validate records with ISONantic model.

        Args:
            records: List of record dictionaries.

        Returns:
            List of validated model instances.
        """
        try:
            validated = []
            for record in records:
                # Remove metadata fields
                data = {k: v for k, v in record.items() if not k.startswith('_')}
                instance = self.model(**data)
                validated.append(instance)
            return validated
        except Exception as e:
            if self.strict:
                raise OutputParserException(f"Model validation failed: {e}")
            return records  # Return raw records on validation failure


class ISONLStreamingParser:
    """
    Standalone ISONL streaming parser for non-LangChain usage.

    Provides incremental parsing with constant memory usage,
    ideal for processing large ISONL files or streams.

    Example:
        >>> parser = ISONLStreamingParser()
        >>> with open("data.isonl") as f:
        ...     for line in f:
        ...         record = parser.parse_line(line)
        ...         if record:
        ...             process(record)
    """

    def __init__(self, schema: Optional[Dict[str, List[str]]] = None):
        """
        Initialize the streaming parser.

        Args:
            schema: Optional pre-defined schema mapping block names to field lists.
        """
        self._schema = schema or {}

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single ISONL line.

        Args:
            line: Single line of ISONL data.

        Returns:
            Parsed record dictionary, or None for schema/comment lines.
        """
        line = line.strip()
        if not line or line.startswith('#'):
            return None

        # Handle schema
        if line.startswith('@schema '):
            self._handle_schema(line[8:])
            return None

        # Parse record
        if ':' not in line:
            return None

        block_part, values_part = line.split(':', 1)
        block_name = block_part.strip()
        values = self._parse_values(values_part.strip())

        fields = self._schema.get(block_name)
        if fields:
            record = {'_block': block_name}
            for i, field in enumerate(fields):
                if i < len(values):
                    record[field] = self._convert_value(values[i])
            return record

        return {'_block': block_name, '_values': [self._convert_value(v) for v in values]}

    def _handle_schema(self, schema_line: str) -> None:
        """Handle schema definition line."""
        if ':' in schema_line:
            block, fields = schema_line.split(':', 1)
            self._schema[block.strip()] = fields.strip().split()

    def _parse_values(self, s: str) -> List[str]:
        """Parse space-separated values with quote handling."""
        values, current, in_quotes = [], "", False
        for c in s:
            if c == '"':
                in_quotes = not in_quotes
            elif c == ' ' and not in_quotes:
                if current:
                    values.append(current)
                    current = ""
            else:
                current += c
        if current:
            values.append(current)
        return values

    def _convert_value(self, v: str) -> Any:
        """Convert string to typed value."""
        if v.lower() == 'true': return True
        if v.lower() == 'false': return False
        if v.lower() in ('null', '~'): return None
        try:
            return float(v) if '.' in v else int(v)
        except ValueError:
            return v
