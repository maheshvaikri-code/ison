"""
Anthropic Tool Use Integration for ISON

Provides utilities for using ISON format with Anthropic's Claude tool use API.
Enables token-efficient structured outputs in Claude workflows.

Usage:
    from anthropic import Anthropic
    from ison_parser.integrations import AnthropicISONTools

    client = Anthropic()
    tools = AnthropicISONTools()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=messages,
        tools=tools.get_tool_definitions(),
    )

    # Parse ISON from tool use result
    doc = tools.parse_response(response)

    # With ISONantic typed models
    from isonantic import TableModel, Field

    class User(TableModel):
        __ison_block__ = "table.users"
        id: int = Field(primary_key=True)
        name: str

    tools = AnthropicISONTools(model=User)
    users = tools.parse_response_typed(response)  # Returns List[User]

Requirements:
    pip install anthropic
    pip install isonantic  # Optional, for typed models
"""

import json
from typing import Any, Dict, List, Optional, Union, Type
from dataclasses import dataclass

try:
    from anthropic import Anthropic
    from anthropic.types import (
        Message,
        ContentBlock,
        TextBlock,
        ToolUseBlock,
    )
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None

# Import ISON parser
import ison_parser
from ison_parser import Document, Block, loads, dumps, from_dict, ISONError

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
    ValidationError = Exception


@dataclass
class ISONToolResult:
    """Result from ISON tool use processing."""
    success: bool
    document: Optional[Document]
    data: Any
    tool_use_id: Optional[str] = None
    error: Optional[str] = None


class AnthropicISONTools:
    """
    Anthropic Tool Use integration for ISON format.

    Provides tool definitions and parsing utilities for using ISON
    with Claude's tool use API. Supports ISONantic models for
    typed validation.

    Features:
    - Pre-built ISON tool definitions
    - Response parsing with type inference
    - ISONantic model validation
    - Token usage optimization
    - Error handling and recovery

    Example (raw):
        >>> tools = AnthropicISONTools()
        >>> doc = tools.parse_response(response)

    Example (with ISONantic):
        >>> from isonantic import TableModel, Field
        >>> class User(TableModel):
        ...     __ison_block__ = "table.users"
        ...     id: int
        ...     name: str
        >>> tools = AnthropicISONTools(model=User)
        >>> users = tools.parse_response_typed(response)  # List[User]
    """

    def __init__(
        self,
        strict_parsing: bool = False,
        model: Optional[Type] = None,
    ):
        """
        Initialize Anthropic ISON tools.

        Args:
            strict_parsing: Raise errors on parse failures (default: False).
            model: Optional ISONantic model class for typed parsing.
        """
        self.strict_parsing = strict_parsing
        self.model = model
        if model is not None and not ISONANTIC_AVAILABLE:
            raise ImportError(
                "ISONantic is required for typed model parsing. "
                "Install with: pip install isonantic"
            )

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get Anthropic tool definitions for ISON operations.

        Returns:
            List of tool definitions compatible with Anthropic API.
        """
        return [
            {
                "name": "return_ison_table",
                "description": "Return structured data as an ISON table. "
                               "ISON is 30-70% more token-efficient than JSON. "
                               "Use this for tabular data with multiple records.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name for the table (e.g., 'users', 'products')"
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column/field names for the table"
                        },
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {}
                            },
                            "description": "Data rows as arrays of values matching field order"
                        }
                    },
                    "required": ["table_name", "fields", "rows"]
                }
            },
            {
                "name": "return_ison_object",
                "description": "Return key-value data as an ISON object. "
                               "Use for configuration, settings, or single-record data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "object_name": {
                            "type": "string",
                            "description": "Name for the object (e.g., 'config', 'result')"
                        },
                        "data": {
                            "type": "object",
                            "description": "Key-value pairs to include in the object"
                        }
                    },
                    "required": ["object_name", "data"]
                }
            },
            {
                "name": "return_ison_document",
                "description": "Return a complete ISON document with multiple blocks. "
                               "Use for complex responses with multiple tables/objects.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ison_text": {
                            "type": "string",
                            "description": "Complete ISON document as text"
                        }
                    },
                    "required": ["ison_text"]
                }
            },
            {
                "name": "query_ison_data",
                "description": "Query and filter ISON data provided in the conversation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ison_text": {
                            "type": "string",
                            "description": "ISON document to query"
                        },
                        "block_name": {
                            "type": "string",
                            "description": "Name of block to query"
                        },
                        "filter": {
                            "type": "object",
                            "description": "Field-value pairs to filter by"
                        }
                    },
                    "required": ["ison_text"]
                }
            },
        ]

    def get_system_prompt(self) -> str:
        """
        Get system prompt for ISON-aware Claude interactions.

        If an ISONantic model is configured, includes schema-specific instructions.

        Returns:
            System prompt string.
        """
        # Use ISONantic model schema if available
        if self.model is not None and ISONANTIC_AVAILABLE:
            return prompt_for_model(self.model)

        return """You have access to ISON (Interchange Simple Object Notation) tools for efficient data exchange.

ISON Format Overview:
- Tables: `table.name` followed by space-separated fields, then data rows
- Objects: `object.name` followed by key-value pairs (one per conceptual pair)
- Types are auto-inferred: numbers, true/false, null, :references, "quoted strings"

ISON is 30-70% more token-efficient than JSON. Use ISON tools when returning structured data.

Example ISON table:
```
table.users
id name email active
1 Alice alice@example.com true
2 "Bob Smith" bob@example.com false
```

Example ISON object:
```
object.config
timeout 30
debug true
api_key "sk-xxx"
```

When the user asks for structured data, prefer using return_ison_table or return_ison_object tools."""

    def parse_tool_use(self, tool_use: Any) -> ISONToolResult:
        """
        Parse an Anthropic tool use block into ISON Document.

        Args:
            tool_use: ToolUseBlock from response.

        Returns:
            ISONToolResult with parsed document.
        """
        try:
            tool_name = tool_use.name
            tool_input = tool_use.input
            tool_id = tool_use.id

            if tool_name == "return_ison_table":
                doc = self._parse_table_tool(tool_input)
            elif tool_name == "return_ison_object":
                doc = self._parse_object_tool(tool_input)
            elif tool_name == "return_ison_document":
                doc = self._parse_document_tool(tool_input)
            elif tool_name == "query_ison_data":
                doc = self._parse_query_tool(tool_input)
            else:
                return ISONToolResult(
                    success=False,
                    document=None,
                    data=None,
                    tool_use_id=tool_id,
                    error=f"Unknown tool: {tool_name}"
                )

            return ISONToolResult(
                success=True,
                document=doc,
                data=doc.to_dict(),
                tool_use_id=tool_id
            )

        except Exception as e:
            if self.strict_parsing:
                raise
            return ISONToolResult(
                success=False,
                document=None,
                data=None,
                tool_use_id=getattr(tool_use, 'id', None),
                error=str(e)
            )

    def _parse_table_tool(self, input_data: Dict[str, Any]) -> Document:
        """Parse return_ison_table tool input."""
        table_name = input_data["table_name"]
        fields = input_data["fields"]
        rows_data = input_data["rows"]

        rows = []
        for row_values in rows_data:
            row = {}
            for i, field in enumerate(fields):
                if i < len(row_values):
                    row[field] = row_values[i]
                else:
                    row[field] = None
            rows.append(row)

        block = Block(
            kind="table",
            name=table_name,
            fields=fields,
            rows=rows
        )

        return Document(blocks=[block])

    def _parse_object_tool(self, input_data: Dict[str, Any]) -> Document:
        """Parse return_ison_object tool input."""
        object_name = input_data["object_name"]
        data = input_data["data"]

        fields = list(data.keys())
        rows = [data]

        block = Block(
            kind="object",
            name=object_name,
            fields=fields,
            rows=rows
        )

        return Document(blocks=[block])

    def _parse_document_tool(self, input_data: Dict[str, Any]) -> Document:
        """Parse return_ison_document tool input."""
        ison_text = input_data["ison_text"]
        return loads(ison_text)

    def _parse_query_tool(self, input_data: Dict[str, Any]) -> Document:
        """Parse query_ison_data tool input."""
        ison_text = input_data["ison_text"]
        block_name = input_data.get("block_name")
        filter_dict = input_data.get("filter", {})

        doc = loads(ison_text)

        # Apply filters
        if block_name or filter_dict:
            filtered_blocks = []
            for block in doc.blocks:
                if block_name and block.name != block_name:
                    continue

                if filter_dict:
                    filtered_rows = []
                    for row in block.rows:
                        match = all(
                            str(row.get(k)) == str(v)
                            for k, v in filter_dict.items()
                        )
                        if match:
                            filtered_rows.append(row)

                    if filtered_rows:
                        filtered_block = Block(
                            kind=block.kind,
                            name=block.name,
                            fields=block.fields,
                            rows=filtered_rows
                        )
                        filtered_blocks.append(filtered_block)
                else:
                    filtered_blocks.append(block)

            return Document(blocks=filtered_blocks)

        return doc

    def parse_response(self, response: Any) -> Optional[Document]:
        """
        Parse Anthropic message response for ISON data.

        Args:
            response: Message response object.

        Returns:
            Parsed Document or None if no ISON found.
        """
        for content_block in response.content:
            # Check for tool use
            if hasattr(content_block, 'type') and content_block.type == "tool_use":
                if content_block.name.startswith("return_ison") or content_block.name == "query_ison_data":
                    result = self.parse_tool_use(content_block)
                    if result.success:
                        return result.document

            # Check for text with inline ISON
            if hasattr(content_block, 'text'):
                try:
                    doc = self._extract_ison_from_text(content_block.text)
                    if doc:
                        return doc
                except:
                    pass

        return None

    def parse_response_typed(self, response: Any) -> List[Any]:
        """
        Parse Anthropic response to typed ISONantic model instances.

        Requires an ISONantic model to be configured.

        Args:
            response: Message response object.

        Returns:
            List of validated model instances.

        Raises:
            ValueError: If no model is configured.
        """
        if self.model is None:
            raise ValueError(
                "No ISONantic model configured. "
                "Initialize with model=YourModel or use parse_response() instead."
            )

        if not ISONANTIC_AVAILABLE:
            raise ImportError("ISONantic is required for typed parsing.")

        # Get raw document first
        doc = self.parse_response(response)
        if doc is None:
            return []

        # Convert to ISON text and parse with model
        ison_text = ison_parser.dumps(doc)
        try:
            return parse_llm_output(ison_text, self.model, strict=self.strict_parsing)
        except ValidationError:
            if self.strict_parsing:
                raise
            result = parse_ison_safe(ison_text, self.model)
            return result.partial_data or []

    def _extract_ison_from_text(self, text: str) -> Optional[Document]:
        """Extract ISON from message text."""
        import re

        # Try markdown code blocks
        code_pattern = r'```(?:ison)?\s*\n(.*?)\n```'
        matches = re.findall(code_pattern, text, re.DOTALL)

        if matches:
            ison_text = '\n\n'.join(matches)
            return loads(ison_text)

        # Try to find block headers
        lines = text.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if '.' in stripped and len(stripped.split()) == 1:
                parts = stripped.split('.')
                if len(parts) == 2 and parts[0] in ('table', 'object', 'meta'):
                    potential_ison = '\n'.join(lines[i:])
                    try:
                        return loads(potential_ison)
                    except:
                        continue

        return None

    def get_tool_results(self, response: Any) -> List[ISONToolResult]:
        """
        Get all ISON tool results from response.

        Args:
            response: Message response object.

        Returns:
            List of ISONToolResult objects.
        """
        results = []

        for content_block in response.content:
            if hasattr(content_block, 'type') and content_block.type == "tool_use":
                if content_block.name.startswith("return_ison") or content_block.name == "query_ison_data":
                    result = self.parse_tool_use(content_block)
                    results.append(result)

        return results

    def create_tool_result_message(
        self,
        tool_use_id: str,
        success: bool = True,
        result: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a tool result message for continuing conversation.

        Args:
            tool_use_id: ID of the tool use being responded to.
            success: Whether the tool execution was successful.
            result: Optional result message.

        Returns:
            Message dict for Anthropic API.
        """
        content = result or ("Success" if success else "Failed")

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content
                }
            ]
        }


class AnthropicISONChat:
    """
    High-level wrapper for ISON-based Claude interactions.

    Simplifies using ISON format with Claude messages API.

    Example:
        >>> chat = AnthropicISONChat(client)
        >>> users = chat.query_as_table(
        ...     "List 5 sample users with name and email",
        ...     table_name="users",
        ...     fields=["id", "name", "email"]
        ... )
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        **kwargs
    ):
        """
        Initialize ISON chat wrapper.

        Args:
            client: Anthropic client instance (creates one if None).
            model: Model to use for messages.
            max_tokens: Maximum tokens in response.
            **kwargs: Additional default parameters.
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "Anthropic package required. Install with: pip install anthropic"
            )

        self.client = client or Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.default_params = kwargs
        self.tools = AnthropicISONTools()

    def query_as_table(
        self,
        prompt: str,
        table_name: str,
        fields: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Query and get response as ISON table.

        Args:
            prompt: User prompt.
            table_name: Name for result table.
            fields: Expected field names.
            **kwargs: Additional API parameters.

        Returns:
            List of row dictionaries.
        """
        messages = [
            {
                "role": "user",
                "content": f"{prompt}\n\nReturn as table '{table_name}' with fields: {', '.join(fields)}"
            }
        ]

        params = {**self.default_params, **kwargs}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.tools.get_system_prompt(),
            messages=messages,
            tools=self.tools.get_tool_definitions(),
            tool_choice={"type": "tool", "name": "return_ison_table"},
            **params
        )

        doc = self.tools.parse_response(response)
        if doc and doc.blocks:
            return doc.blocks[0].rows
        return []

    def query_as_object(
        self,
        prompt: str,
        object_name: str = "result",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query and get response as ISON object.

        Args:
            prompt: User prompt.
            object_name: Name for result object.
            **kwargs: Additional API parameters.

        Returns:
            Dictionary of key-value pairs.
        """
        messages = [
            {
                "role": "user",
                "content": f"{prompt}\n\nReturn as object '{object_name}'"
            }
        ]

        params = {**self.default_params, **kwargs}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.tools.get_system_prompt(),
            messages=messages,
            tools=self.tools.get_tool_definitions(),
            tool_choice={"type": "tool", "name": "return_ison_object"},
            **params
        )

        doc = self.tools.parse_response(response)
        if doc and doc.blocks and doc.blocks[0].rows:
            return doc.blocks[0].rows[0]
        return {}

    def query_as_document(
        self,
        prompt: str,
        **kwargs
    ) -> Optional[Document]:
        """
        Query and get response as full ISON document.

        Args:
            prompt: User prompt.
            **kwargs: Additional API parameters.

        Returns:
            ISON Document or None.
        """
        messages = [
            {
                "role": "user",
                "content": f"{prompt}\n\nReturn as complete ISON document."
            }
        ]

        params = {**self.default_params, **kwargs}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.tools.get_system_prompt(),
            messages=messages,
            tools=self.tools.get_tool_definitions(),
            **params
        )

        return self.tools.parse_response(response)

    def chat_with_ison_context(
        self,
        messages: List[Dict[str, Any]],
        ison_context: Union[str, Document, Dict],
        **kwargs
    ) -> str:
        """
        Chat with ISON data as context.

        Args:
            messages: Chat message history.
            ison_context: ISON data to include as context.
            **kwargs: Additional API parameters.

        Returns:
            Assistant response text.
        """
        # Format context
        if isinstance(ison_context, Document):
            context_text = dumps(ison_context)
        elif isinstance(ison_context, dict):
            doc = from_dict(ison_context)
            context_text = dumps(doc)
        else:
            context_text = ison_context

        system = f"""{self.tools.get_system_prompt()}

Reference data (ISON format):
```
{context_text}
```"""

        params = {**self.default_params, **kwargs}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            **params
        )

        # Extract text response
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text

        return ""

    def analyze_ison(
        self,
        ison_text: str,
        analysis_prompt: str,
        **kwargs
    ) -> str:
        """
        Analyze ISON data with a specific prompt.

        Args:
            ison_text: ISON document to analyze.
            analysis_prompt: What to analyze about the data.
            **kwargs: Additional API parameters.

        Returns:
            Analysis text.
        """
        messages = [
            {
                "role": "user",
                "content": f"""Analyze this ISON data:

```ison
{ison_text}
```

{analysis_prompt}"""
            }
        ]

        params = {**self.default_params, **kwargs}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.tools.get_system_prompt(),
            messages=messages,
            **params
        )

        for block in response.content:
            if hasattr(block, 'text'):
                return block.text

        return ""
