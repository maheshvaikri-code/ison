"""
OpenAI Function Calling Integration for ISON

Provides utilities for using ISON format with OpenAI's function calling API.
Enables token-efficient structured outputs in OpenAI workflows.

Usage:
    from openai import OpenAI
    from ison_parser.integrations import OpenAIISONTools

    client = OpenAI()
    tools = OpenAIISONTools()

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=tools.get_tool_definitions(),
    )

    # Parse ISON from function call result
    if tools.is_ison_response(response):
        doc = tools.parse_response(response)

    # With ISONantic typed models
    from isonantic import TableModel, Field

    class User(TableModel):
        __ison_block__ = "table.users"
        id: int = Field(primary_key=True)
        name: str

    tools = OpenAIISONTools(model=User)
    users = tools.parse_response_typed(response)  # Returns List[User]

Requirements:
    pip install openai
    pip install isonantic  # Optional, for typed models
"""

import json
from typing import Any, Dict, List, Optional, Union, Type
from dataclasses import dataclass

try:
    from openai import OpenAI
    from openai.types.chat import (
        ChatCompletionMessageToolCall,
        ChatCompletionMessage,
    )
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

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
class ISONFunctionResult:
    """Result from ISON function call processing."""
    success: bool
    document: Optional[Document]
    data: Any
    error: Optional[str] = None


class OpenAIISONTools:
    """
    OpenAI Function Calling integration for ISON format.

    Provides tool definitions and parsing utilities for using ISON
    with OpenAI's function calling API. Supports ISONantic models
    for typed validation.

    Features:
    - Pre-built ISON tool definitions
    - Response parsing with type inference
    - ISONantic model validation
    - Token usage optimization
    - Error handling and recovery

    Example (raw):
        >>> tools = OpenAIISONTools()
        >>> doc = tools.parse_response(response)

    Example (with ISONantic):
        >>> from isonantic import TableModel, Field
        >>> class User(TableModel):
        ...     __ison_block__ = "table.users"
        ...     id: int
        ...     name: str
        >>> tools = OpenAIISONTools(model=User)
        >>> users = tools.parse_response_typed(response)  # List[User]
    """

    def __init__(
        self,
        strict_parsing: bool = False,
        model: Optional[Type] = None,
    ):
        """
        Initialize OpenAI ISON tools.

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
        Get OpenAI tool definitions for ISON operations.

        Returns:
            List of tool definitions compatible with OpenAI API.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "return_ison_table",
                    "description": "Return structured data as an ISON table. "
                                   "ISON is 30-70% more token-efficient than JSON.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Name for the table (e.g., 'users', 'products')"
                            },
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Column/field names"
                            },
                            "rows": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {}
                                },
                                "description": "Data rows as arrays of values"
                            }
                        },
                        "required": ["table_name", "fields", "rows"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "return_ison_object",
                    "description": "Return key-value data as an ISON object. "
                                   "More token-efficient than JSON objects.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_name": {
                                "type": "string",
                                "description": "Name for the object (e.g., 'config', 'result')"
                            },
                            "data": {
                                "type": "object",
                                "description": "Key-value pairs to include"
                            }
                        },
                        "required": ["object_name", "data"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "return_ison_document",
                    "description": "Return a complete ISON document with multiple blocks. "
                                   "Use for complex data with multiple tables/objects.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ison_text": {
                                "type": "string",
                                "description": "Complete ISON document text"
                            }
                        },
                        "required": ["ison_text"]
                    }
                }
            },
        ]

    def get_format_instruction(self) -> str:
        """
        Get system instruction for ISON formatting.

        If an ISONantic model is configured, uses schema-aware instructions.

        Returns:
            Instruction string for system message.
        """
        # Use ISONantic model schema if available
        if self.model is not None and ISONANTIC_AVAILABLE:
            return prompt_for_model(self.model)

        return """When returning structured data, use ISON format for token efficiency.

ISON Format:
- Tables: `table.name` followed by fields, then data rows
- Objects: `object.name` followed by key-value pairs
- Values: space-separated, quote strings with spaces
- References: :id for foreign keys

Example table:
```
table.users
id name email
1 Alice alice@example.com
2 "Bob Smith" bob@example.com
```

Example object:
```
object.config
timeout 30
debug true
```

Use the return_ison_table, return_ison_object, or return_ison_document functions."""

    def parse_tool_call(self, tool_call: Any) -> ISONFunctionResult:
        """
        Parse an OpenAI tool call response into ISON Document.

        Args:
            tool_call: ChatCompletionMessageToolCall from response.

        Returns:
            ISONFunctionResult with parsed document.
        """
        try:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            if function_name == "return_ison_table":
                doc = self._parse_table_call(arguments)
            elif function_name == "return_ison_object":
                doc = self._parse_object_call(arguments)
            elif function_name == "return_ison_document":
                doc = self._parse_document_call(arguments)
            else:
                return ISONFunctionResult(
                    success=False,
                    document=None,
                    data=None,
                    error=f"Unknown function: {function_name}"
                )

            return ISONFunctionResult(
                success=True,
                document=doc,
                data=doc.to_dict()
            )

        except json.JSONDecodeError as e:
            return ISONFunctionResult(
                success=False,
                document=None,
                data=None,
                error=f"Invalid JSON in arguments: {e}"
            )
        except Exception as e:
            if self.strict_parsing:
                raise
            return ISONFunctionResult(
                success=False,
                document=None,
                data=None,
                error=str(e)
            )

    def _parse_table_call(self, args: Dict[str, Any]) -> Document:
        """Parse return_ison_table function call."""
        table_name = args["table_name"]
        fields = args["fields"]
        rows_data = args["rows"]

        # Convert array rows to dict rows
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

    def _parse_object_call(self, args: Dict[str, Any]) -> Document:
        """Parse return_ison_object function call."""
        object_name = args["object_name"]
        data = args["data"]

        fields = list(data.keys())
        rows = [data]

        block = Block(
            kind="object",
            name=object_name,
            fields=fields,
            rows=rows
        )

        return Document(blocks=[block])

    def _parse_document_call(self, args: Dict[str, Any]) -> Document:
        """Parse return_ison_document function call."""
        ison_text = args["ison_text"]
        return loads(ison_text)

    def parse_response(self, response: Any) -> Optional[Document]:
        """
        Parse OpenAI chat completion response for ISON data.

        Args:
            response: ChatCompletion response object.

        Returns:
            Parsed Document or None if no ISON found.
        """
        message = response.choices[0].message

        # Check for tool calls
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name.startswith("return_ison"):
                    result = self.parse_tool_call(tool_call)
                    if result.success:
                        return result.document

        # Check message content for inline ISON
        if message.content:
            try:
                return self._extract_ison_from_text(message.content)
            except:
                pass

        return None

    def parse_response_typed(self, response: Any) -> List[Any]:
        """
        Parse OpenAI response to typed ISONantic model instances.

        Requires an ISONantic model to be configured.

        Args:
            response: ChatCompletion response object.

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
            if '.' in line.strip() and len(line.strip().split()) == 1:
                # Might be ISON from here
                potential_ison = '\n'.join(lines[i:])
                try:
                    return loads(potential_ison)
                except:
                    continue

        return None

    def is_ison_response(self, response: Any) -> bool:
        """
        Check if response contains ISON data.

        Args:
            response: ChatCompletion response.

        Returns:
            True if response contains ISON.
        """
        message = response.choices[0].message

        if message.tool_calls:
            for tc in message.tool_calls:
                if tc.function.name.startswith("return_ison"):
                    return True

        return False

    def create_ison_message(
        self,
        data: Union[Dict, List, Document],
        name: str = "data"
    ) -> Dict[str, Any]:
        """
        Create a message with ISON-formatted data.

        Args:
            data: Data to format as ISON.
            name: Name for the block.

        Returns:
            Message dict for OpenAI API.
        """
        if isinstance(data, Document):
            ison_text = dumps(data)
        elif isinstance(data, dict):
            doc = from_dict({name: data})
            ison_text = dumps(doc)
        elif isinstance(data, list):
            doc = from_dict({name: data})
            ison_text = dumps(doc)
        else:
            ison_text = str(data)

        return {
            "role": "user",
            "content": f"Data in ISON format:\n```ison\n{ison_text}\n```"
        }


class OpenAIISONChat:
    """
    High-level wrapper for ISON-based OpenAI chat interactions.

    Simplifies using ISON format with OpenAI chat completions.

    Example:
        >>> chat = OpenAIISONChat(client)
        >>> users = chat.query_as_table(
        ...     "List 5 sample users with name and email",
        ...     table_name="users",
        ...     fields=["id", "name", "email"]
        ... )
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = "gpt-4",
        **kwargs
    ):
        """
        Initialize ISON chat wrapper.

        Args:
            client: OpenAI client instance (creates one if None).
            model: Model to use for completions.
            **kwargs: Additional default parameters.
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI package required. Install with: pip install openai"
            )

        self.client = client or OpenAI()
        self.model = model
        self.default_params = kwargs
        self.tools = OpenAIISONTools()

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
            {"role": "system", "content": self.tools.get_format_instruction()},
            {"role": "user", "content": f"{prompt}\n\nReturn as table '{table_name}' with fields: {', '.join(fields)}"}
        ]

        params = {**self.default_params, **kwargs}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools.get_tool_definitions(),
            tool_choice={"type": "function", "function": {"name": "return_ison_table"}},
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
            {"role": "system", "content": self.tools.get_format_instruction()},
            {"role": "user", "content": f"{prompt}\n\nReturn as object '{object_name}'"}
        ]

        params = {**self.default_params, **kwargs}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools.get_tool_definitions(),
            tool_choice={"type": "function", "function": {"name": "return_ison_object"}},
            **params
        )

        doc = self.tools.parse_response(response)
        if doc and doc.blocks and doc.blocks[0].rows:
            return doc.blocks[0].rows[0]
        return {}

    def chat_with_ison_context(
        self,
        messages: List[Dict[str, str]],
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

        # Add context message
        context_msg = {
            "role": "system",
            "content": f"Reference data (ISON format):\n```\n{context_text}\n```"
        }

        full_messages = [context_msg] + messages

        params = {**self.default_params, **kwargs}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            **params
        )

        return response.choices[0].message.content or ""
