"""
MCP Server for ISON

Implements Model Context Protocol (MCP) server that exposes ISON tools
and resources for AI assistants like Claude.

Features:
- Tools: parse_ison, format_ison, convert_json_to_ison, query_ison
- Resources: ISON documents, database exports, schemas
- Prompts: ISON formatting instructions

Usage:
    # As standalone server
    python -m ison_parser.integrations.mcp_server

    # Programmatic usage
    from ison_parser.integrations import ISONMCPServer
    server = ISONMCPServer()
    server.run()

Requirements:
    pip install mcp
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Sequence
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
        ResourceTemplate,
        Prompt,
        PromptMessage,
        PromptArgument,
        GetPromptResult,
        CallToolResult,
        ReadResourceResult,
        ListToolsResult,
        ListResourcesResult,
        ListPromptsResult,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = object

# Import ISON parser
import ison_parser
from ison_parser import (
    Document, Block, Reference,
    loads, dumps, load, from_dict,
    loads_isonl, dumps_isonl,
    ISONError, ISONSyntaxError
)


class ISONMCPServer:
    """
    MCP Server exposing ISON parsing and formatting tools.

    Provides tools for AI assistants to work with ISON data format,
    enabling token-efficient data exchange in LLM workflows.

    Tools:
        - parse_ison: Parse ISON text to JSON
        - format_ison: Convert JSON to ISON
        - validate_ison: Validate ISON syntax
        - query_ison: Query ISON documents
        - convert_to_isonl: Convert ISON to streaming format

    Resources:
        - ison://schema: ISON format specification
        - ison://examples: Example ISON documents

    Example:
        >>> server = ISONMCPServer()
        >>> await server.run()
    """

    def __init__(
        self,
        name: str = "ison-server",
        version: str = "1.0.0",
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the MCP server.

        Args:
            name: Server name for MCP registration.
            version: Server version string.
            data_dir: Directory for ISON document resources.
        """
        if not MCP_AVAILABLE:
            raise ImportError(
                "MCP package is required for ISONMCPServer. "
                "Install with: pip install mcp"
            )

        self.name = name
        self.version = version
        self.data_dir = Path(data_dir) if data_dir else None
        self.server = Server(name)

        # Register handlers
        self._register_tools()
        self._register_resources()
        self._register_prompts()

    def _register_tools(self):
        """Register ISON tools with the MCP server."""

        @self.server.list_tools()
        async def list_tools() -> ListToolsResult:
            return ListToolsResult(tools=[
                Tool(
                    name="parse_ison",
                    description="Parse ISON text and convert to JSON format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ison_text": {
                                "type": "string",
                                "description": "ISON formatted text to parse"
                            }
                        },
                        "required": ["ison_text"]
                    }
                ),
                Tool(
                    name="format_ison",
                    description="Convert JSON data to token-efficient ISON format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "json_data": {
                                "type": "string",
                                "description": "JSON string to convert to ISON"
                            },
                            "align_columns": {
                                "type": "boolean",
                                "description": "Align columns for readability",
                                "default": True
                            }
                        },
                        "required": ["json_data"]
                    }
                ),
                Tool(
                    name="validate_ison",
                    description="Validate ISON syntax and return structure info",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ison_text": {
                                "type": "string",
                                "description": "ISON text to validate"
                            }
                        },
                        "required": ["ison_text"]
                    }
                ),
                Tool(
                    name="query_ison",
                    description="Query ISON document for specific blocks or rows",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ison_text": {
                                "type": "string",
                                "description": "ISON document to query"
                            },
                            "block_name": {
                                "type": "string",
                                "description": "Name of block to retrieve"
                            },
                            "filter_field": {
                                "type": "string",
                                "description": "Field name to filter by"
                            },
                            "filter_value": {
                                "type": "string",
                                "description": "Value to filter for"
                            }
                        },
                        "required": ["ison_text"]
                    }
                ),
                Tool(
                    name="convert_to_isonl",
                    description="Convert ISON to streaming ISONL format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ison_text": {
                                "type": "string",
                                "description": "ISON text to convert"
                            }
                        },
                        "required": ["ison_text"]
                    }
                ),
                Tool(
                    name="estimate_token_savings",
                    description="Compare token usage between JSON and ISON formats",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "json_data": {
                                "type": "string",
                                "description": "JSON data to analyze"
                            }
                        },
                        "required": ["json_data"]
                    }
                ),
                Tool(
                    name="parse_isonl",
                    description="Parse ISONL (streaming format) text to JSON records",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "isonl_text": {
                                "type": "string",
                                "description": "ISONL formatted text (one record per line)"
                            }
                        },
                        "required": ["isonl_text"]
                    }
                ),
                Tool(
                    name="format_isonl",
                    description="Convert JSON array to streaming ISONL format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "json_array": {
                                "type": "string",
                                "description": "JSON array of records to convert"
                            },
                            "block_name": {
                                "type": "string",
                                "description": "Block name for ISONL records (e.g., 'table.users')",
                                "default": "table.data"
                            }
                        },
                        "required": ["json_array"]
                    }
                ),
            ])

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            try:
                if name == "parse_ison":
                    return await self._handle_parse_ison(arguments)
                elif name == "format_ison":
                    return await self._handle_format_ison(arguments)
                elif name == "validate_ison":
                    return await self._handle_validate_ison(arguments)
                elif name == "query_ison":
                    return await self._handle_query_ison(arguments)
                elif name == "convert_to_isonl":
                    return await self._handle_convert_to_isonl(arguments)
                elif name == "estimate_token_savings":
                    return await self._handle_estimate_savings(arguments)
                elif name == "parse_isonl":
                    return await self._handle_parse_isonl(arguments)
                elif name == "format_isonl":
                    return await self._handle_format_isonl(arguments)
                else:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Unknown tool: {name}")]
                    )
            except Exception as e:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")]
                )

    async def _handle_parse_ison(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle parse_ison tool call."""
        ison_text = args.get("ison_text", "")

        try:
            doc = loads(ison_text)
            json_output = doc.to_json(indent=2)

            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Parsed ISON ({len(doc.blocks)} blocks):\n\n{json_output}"
                )]
            )
        except ISONSyntaxError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Parse error: {e}")]
            )

    async def _handle_format_ison(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle format_ison tool call."""
        json_str = args.get("json_data", "{}")
        align = args.get("align_columns", True)

        try:
            data = json.loads(json_str)
            doc = from_dict(data)
            ison_output = dumps(doc, align_columns=align)

            # Calculate savings
            json_chars = len(json_str)
            ison_chars = len(ison_output)
            savings = ((json_chars - ison_chars) / json_chars * 100) if json_chars > 0 else 0

            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"ISON output ({savings:.1f}% smaller):\n\n{ison_output}"
                )]
            )
        except json.JSONDecodeError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Invalid JSON: {e}")]
            )

    async def _handle_validate_ison(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle validate_ison tool call."""
        ison_text = args.get("ison_text", "")

        try:
            doc = loads(ison_text)

            # Build structure report
            report = ["✓ Valid ISON document", ""]
            for block in doc.blocks:
                report.append(f"Block: {block.kind}.{block.name}")
                report.append(f"  Fields: {', '.join(block.fields)}")
                report.append(f"  Rows: {len(block.rows)}")
                if block.field_info:
                    typed_fields = [f for f in block.field_info if f.type]
                    if typed_fields:
                        report.append(f"  Typed: {', '.join(f'{f.name}:{f.type}' for f in typed_fields)}")

            return CallToolResult(
                content=[TextContent(type="text", text="\n".join(report))]
            )
        except ISONSyntaxError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"✗ Invalid ISON: {e}")]
            )

    async def _handle_query_ison(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle query_ison tool call."""
        ison_text = args.get("ison_text", "")
        block_name = args.get("block_name")
        filter_field = args.get("filter_field")
        filter_value = args.get("filter_value")

        try:
            doc = loads(ison_text)

            # Filter by block name
            if block_name:
                block = doc[block_name]
                if not block:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Block '{block_name}' not found")]
                    )
                blocks = [block]
            else:
                blocks = doc.blocks

            # Filter rows
            results = []
            for block in blocks:
                rows = block.rows
                if filter_field and filter_value:
                    rows = [r for r in rows if str(r.get(filter_field)) == filter_value]

                if rows:
                    results.append({
                        "block": f"{block.kind}.{block.name}",
                        "fields": block.fields,
                        "rows": rows,
                        "count": len(rows)
                    })

            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(results, indent=2, default=str)
                )]
            )
        except ISONError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Query error: {e}")]
            )

    async def _handle_convert_to_isonl(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle convert_to_isonl tool call."""
        ison_text = args.get("ison_text", "")

        try:
            doc = loads(ison_text)
            isonl_output = dumps_isonl(doc)

            line_count = len(isonl_output.strip().split('\n'))

            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"ISONL output ({line_count} lines):\n\n{isonl_output}"
                )]
            )
        except ISONError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Conversion error: {e}")]
            )

    async def _handle_estimate_savings(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle estimate_token_savings tool call."""
        json_str = args.get("json_data", "{}")

        try:
            data = json.loads(json_str)
            doc = from_dict(data)
            ison_output = dumps(doc)

            # Estimate tokens (rough: 4 chars per token)
            json_tokens = len(json_str) / 4
            ison_tokens = len(ison_output) / 4
            savings_pct = ((json_tokens - ison_tokens) / json_tokens * 100) if json_tokens > 0 else 0

            report = [
                "Token Usage Comparison:",
                f"  JSON: ~{int(json_tokens)} tokens ({len(json_str)} chars)",
                f"  ISON: ~{int(ison_tokens)} tokens ({len(ison_output)} chars)",
                f"  Savings: {savings_pct:.1f}% ({int(json_tokens - ison_tokens)} tokens)",
            ]

            return CallToolResult(
                content=[TextContent(type="text", text="\n".join(report))]
            )
        except json.JSONDecodeError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Invalid JSON: {e}")]
            )

    async def _handle_parse_isonl(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle parse_isonl tool call."""
        isonl_text = args.get("isonl_text", "")

        try:
            records = []
            schema_cache = {}

            for line in isonl_text.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Handle schema definition
                if line.startswith('@schema '):
                    parts = line[8:].split(':', 1)
                    if len(parts) == 2:
                        block = parts[0].strip()
                        fields = parts[1].strip().split()
                        schema_cache[block] = fields
                    continue

                # Parse record
                if ':' not in line:
                    continue

                block_part, values_part = line.split(':', 1)
                block_name = block_part.strip()
                values = self._parse_isonl_values(values_part.strip())

                fields = schema_cache.get(block_name)
                if fields:
                    record = {'_block': block_name}
                    for i, field in enumerate(fields):
                        if i < len(values):
                            record[field] = self._convert_isonl_value(values[i])
                    records.append(record)
                else:
                    records.append({
                        '_block': block_name,
                        '_values': [self._convert_isonl_value(v) for v in values]
                    })

            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Parsed {len(records)} ISONL records:\n\n{json.dumps(records, indent=2, default=str)}"
                )]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Parse error: {e}")]
            )

    async def _handle_format_isonl(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle format_isonl tool call."""
        json_str = args.get("json_array", "[]")
        block_name = args.get("block_name", "table.data")

        try:
            data = json.loads(json_str)
            if not isinstance(data, list):
                data = [data]

            if not data:
                return CallToolResult(
                    content=[TextContent(type="text", text="No records to format")]
                )

            # Get fields from first record
            fields = list(data[0].keys()) if data else []

            # Build ISONL output
            lines = []
            lines.append(f"@schema {block_name}: {' '.join(fields)}")

            for record in data:
                values = []
                for field in fields:
                    value = record.get(field)
                    if value is None:
                        values.append("null")
                    elif isinstance(value, bool):
                        values.append("true" if value else "false")
                    elif isinstance(value, str) and ' ' in value:
                        values.append(f'"{value}"')
                    else:
                        values.append(str(value))
                lines.append(f"{block_name}: {' '.join(values)}")

            isonl_output = '\n'.join(lines)

            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"ISONL output ({len(data)} records):\n\n{isonl_output}"
                )]
            )
        except json.JSONDecodeError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Invalid JSON: {e}")]
            )

    def _parse_isonl_values(self, s: str) -> List[str]:
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

    def _convert_isonl_value(self, v: str) -> Any:
        """Convert string to typed value."""
        if v.lower() == 'true': return True
        if v.lower() == 'false': return False
        if v.lower() in ('null', '~'): return None
        try:
            return float(v) if '.' in v else int(v)
        except ValueError:
            return v

    def _register_resources(self):
        """Register ISON resources with the MCP server."""

        @self.server.list_resources()
        async def list_resources() -> ListResourcesResult:
            resources = [
                Resource(
                    uri="ison://schema",
                    name="ISON Format Schema",
                    description="ISON v1.0 format specification and syntax rules",
                    mimeType="text/plain"
                ),
                Resource(
                    uri="ison://examples/table",
                    name="ISON Table Example",
                    description="Example of ISON table format",
                    mimeType="text/plain"
                ),
                Resource(
                    uri="ison://examples/object",
                    name="ISON Object Example",
                    description="Example of ISON object format",
                    mimeType="text/plain"
                ),
                Resource(
                    uri="ison://examples/references",
                    name="ISON References Example",
                    description="Example of ISON reference syntax",
                    mimeType="text/plain"
                ),
            ]

            # Add data directory files if configured
            if self.data_dir and self.data_dir.exists():
                for file in self.data_dir.glob("*.ison"):
                    resources.append(Resource(
                        uri=f"ison://data/{file.name}",
                        name=file.stem,
                        description=f"ISON document: {file.name}",
                        mimeType="text/plain"
                    ))

            return ListResourcesResult(resources=resources)

        @self.server.read_resource()
        async def read_resource(uri: str) -> ReadResourceResult:
            if uri == "ison://schema":
                content = self._get_schema_content()
            elif uri == "ison://examples/table":
                content = self._get_table_example()
            elif uri == "ison://examples/object":
                content = self._get_object_example()
            elif uri == "ison://examples/references":
                content = self._get_references_example()
            elif uri.startswith("ison://data/") and self.data_dir:
                filename = uri.replace("ison://data/", "")
                filepath = self.data_dir / filename
                if filepath.exists():
                    content = filepath.read_text()
                else:
                    content = f"File not found: {filename}"
            else:
                content = f"Unknown resource: {uri}"

            return ReadResourceResult(
                contents=[TextContent(type="text", text=content)]
            )

    def _get_schema_content(self) -> str:
        """Return ISON format schema."""
        return """ISON v1.0 Format Specification

ISON (Interchange Simple Object Notation) is a token-efficient data format
optimized for LLM workflows. It provides 30-70% token savings vs JSON.

## Block Types

### Table (tabular data)
```
table.name
field1 field2 field3
value1 value2 value3
value4 value5 value6
```

### Object (key-value pairs)
```
object.name
key1 value1
key2 value2
```

## Data Types (auto-inferred)

- Integers: 42, -17
- Floats: 3.14, -2.5
- Booleans: true, false
- Null: null
- Strings: unquoted_word, "quoted string"
- References: :id, :type:id

## References

Simple: :123
Namespaced: :user:123
Relationship: :MEMBER_OF:456

## Comments

# This is a comment

## Field Type Annotations (optional)

```
table.users
id:int name:string active:bool
1 Alice true
```
"""

    def _get_table_example(self) -> str:
        """Return table example."""
        return """table.users
id name email active created_at
1 Alice alice@example.com true 2024-01-15
2 Bob "Bob Smith" true 2024-02-20
3 Carol carol@example.com false 2024-03-10

table.orders
id user_id product total status
O1 :1 "Widget Pro" 99.99 shipped
O2 :2 "Gadget X" 149.50 pending
O3 :1 "Tool Kit" 75.00 delivered
"""

    def _get_object_example(self) -> str:
        """Return object example."""
        return """object.config
app_name "My Application"
version 2.1.0
debug false
max_connections 100
timeout_seconds 30
api_endpoint "https://api.example.com"

object.database
host localhost
port 5432
name myapp_db
pool_size 10
ssl_enabled true
"""

    def _get_references_example(self) -> str:
        """Return references example."""
        return """# ISON Reference Examples

# Users table
table.users
id name role
U1 Alice admin
U2 Bob editor
U3 Carol viewer

# Teams with user references
table.teams
id name lead_id
T1 Engineering :U1
T2 Marketing :U2

# Memberships with relationship references
table.memberships
user_id team_id role
:U1 :T1 lead
:U2 :T1 member
:U3 :T2 member

# Graph-style relationships
table.relationships
source_id relationship target_id
:U1 :MANAGES:U2 :U2
:U1 :MANAGES:U3 :U3
:U2 :REPORTS_TO:U1 :U1
"""

    def _register_prompts(self):
        """Register ISON prompts with the MCP server."""

        @self.server.list_prompts()
        async def list_prompts() -> ListPromptsResult:
            return ListPromptsResult(prompts=[
                Prompt(
                    name="format_as_ison",
                    description="Instructions for formatting data as ISON",
                    arguments=[
                        PromptArgument(
                            name="data_description",
                            description="Description of the data to format",
                            required=False
                        )
                    ]
                ),
                Prompt(
                    name="parse_ison_response",
                    description="Instructions for parsing ISON from LLM response",
                    arguments=[]
                ),
            ])

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResult:
            if name == "format_as_ison":
                data_desc = (arguments or {}).get("data_description", "the data")
                return GetPromptResult(
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(
                                type="text",
                                text=f"""Format {data_desc} using ISON format for token efficiency.

ISON Format Rules:
1. Tables: `table.name` header, field names, then data rows
2. Objects: `object.name` header, then key-value pairs
3. Space-separated values, quote strings with spaces
4. Use :id for references
5. Auto-infer types: numbers, booleans (true/false), null

Example table:
```
table.items
id name price
1 Widget 29.99
2 "Super Gadget" 49.99
```

Example object:
```
object.settings
theme dark
notifications true
```

Respond with valid ISON only."""
                            )
                        )
                    ]
                )
            elif name == "parse_ison_response":
                return GetPromptResult(
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(
                                type="text",
                                text="""When the response contains ISON data, parse it as follows:

1. Identify block headers (kind.name format)
2. Extract field names from second line
3. Parse data rows with type inference:
   - Numbers: 42, 3.14
   - Booleans: true, false
   - Null: null
   - References: :id or :type:id
   - Strings: unquoted or "quoted"
4. Build structured data from parsed content"""
                            )
                        )
                    ]
                )

            return GetPromptResult(messages=[])

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Entry point for running ISON MCP server."""
    if not MCP_AVAILABLE:
        print("Error: MCP package not installed. Run: pip install mcp")
        return

    server = ISONMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
