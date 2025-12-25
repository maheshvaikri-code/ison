"""
MCP Client for ISON

Implements Model Context Protocol (MCP) client for consuming ISON data
from MCP servers in AI assistant workflows.

Features:
- Connect to ISON MCP servers
- Execute ISON tools (parse, format, query)
- Access ISON resources
- Stream ISONL data

Usage:
    from ison_parser.integrations import ISONMCPClient

    async with ISONMCPClient("ison-server") as client:
        # Parse ISON
        result = await client.parse_ison(ison_text)

        # Convert JSON to ISON
        ison = await client.format_ison(json_data)

        # Query ISON document
        rows = await client.query_ison(doc, block="users", filter={"active": True})

Requirements:
    pip install mcp
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass

try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.types import (
        TextContent,
        CallToolResult,
        ReadResourceResult,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = object

# Import ISON parser for local operations
import ison_parser
from ison_parser import Document, Block, loads, dumps, from_dict


@dataclass
class ISONToolResult:
    """Result from an ISON MCP tool call."""
    success: bool
    data: Any
    message: str
    raw_response: Optional[str] = None


class ISONMCPClient:
    """
    MCP Client for consuming ISON data from MCP servers.

    Provides a high-level interface for ISON operations via MCP,
    with fallback to local operations when server is unavailable.

    Attributes:
        server_name: Name of the MCP server to connect to.
        session: Active MCP client session.
        use_local_fallback: Fall back to local parsing if server unavailable.

    Example:
        >>> async with ISONMCPClient() as client:
        ...     doc = await client.parse_ison(ison_text)
        ...     print(doc['users'].rows)
    """

    def __init__(
        self,
        server_name: str = "ison-server",
        server_command: Optional[List[str]] = None,
        use_local_fallback: bool = True,
    ):
        """
        Initialize the MCP client.

        Args:
            server_name: Name of the ISON MCP server.
            server_command: Command to start the server if not running.
            use_local_fallback: Use local parser if server unavailable.
        """
        if not MCP_AVAILABLE:
            if not use_local_fallback:
                raise ImportError(
                    "MCP package is required for ISONMCPClient. "
                    "Install with: pip install mcp"
                )

        self.server_name = server_name
        self.server_command = server_command or [
            "python", "-m", "ison_parser.integrations.mcp_server"
        ]
        self.use_local_fallback = use_local_fallback
        self.session: Optional[ClientSession] = None
        self._connected = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> bool:
        """
        Connect to the ISON MCP server.

        Returns:
            True if connected, False if using local fallback.
        """
        if not MCP_AVAILABLE:
            self._connected = False
            return False

        try:
            server_params = StdioServerParameters(
                command=self.server_command[0],
                args=self.server_command[1:] if len(self.server_command) > 1 else [],
            )

            # Create client session
            read, write = await stdio_client(server_params).__aenter__()
            self.session = ClientSession(read, write)
            await self.session.__aenter__()

            # Initialize session
            await self.session.initialize()
            self._connected = True
            return True

        except Exception as e:
            if self.use_local_fallback:
                self._connected = False
                return False
            raise ConnectionError(f"Failed to connect to MCP server: {e}")

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except:
                pass
            self.session = None
        self._connected = False

    async def parse_ison(self, ison_text: str) -> ISONToolResult:
        """
        Parse ISON text to structured data.

        Args:
            ison_text: ISON formatted text.

        Returns:
            ISONToolResult with parsed document.
        """
        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "parse_ison",
                    {"ison_text": ison_text}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            doc = loads(ison_text)
            return ISONToolResult(
                success=True,
                data=doc.to_dict(),
                message=f"Parsed {len(doc.blocks)} blocks (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Parse error: {e}"
            )

    async def format_ison(
        self,
        data: Union[str, Dict[str, Any]],
        align_columns: bool = True
    ) -> ISONToolResult:
        """
        Convert JSON/dict to ISON format.

        Args:
            data: JSON string or dictionary to convert.
            align_columns: Align columns for readability.

        Returns:
            ISONToolResult with ISON formatted text.
        """
        json_str = data if isinstance(data, str) else json.dumps(data)

        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "format_ison",
                    {"json_data": json_str, "align_columns": align_columns}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            data_dict = json.loads(json_str) if isinstance(data, str) else data
            doc = from_dict(data_dict)
            ison_output = dumps(doc, align_columns=align_columns)
            return ISONToolResult(
                success=True,
                data=ison_output,
                message="Formatted to ISON (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Format error: {e}"
            )

    async def validate_ison(self, ison_text: str) -> ISONToolResult:
        """
        Validate ISON syntax.

        Args:
            ison_text: ISON text to validate.

        Returns:
            ISONToolResult with validation status.
        """
        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "validate_ison",
                    {"ison_text": ison_text}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            doc = loads(ison_text)
            info = {
                "valid": True,
                "blocks": [
                    {
                        "kind": b.kind,
                        "name": b.name,
                        "fields": b.fields,
                        "row_count": len(b.rows)
                    }
                    for b in doc.blocks
                ]
            }
            return ISONToolResult(
                success=True,
                data=info,
                message="Valid ISON (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data={"valid": False, "error": str(e)},
                message=f"Invalid ISON: {e}"
            )

    async def query_ison(
        self,
        ison_text: str,
        block_name: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> ISONToolResult:
        """
        Query ISON document.

        Args:
            ison_text: ISON document to query.
            block_name: Optional block to filter.
            filter_field: Field name to filter by.
            filter_value: Value to match.

        Returns:
            ISONToolResult with matching data.
        """
        if self._connected and self.session:
            try:
                args = {"ison_text": ison_text}
                if block_name:
                    args["block_name"] = block_name
                if filter_field:
                    args["filter_field"] = filter_field
                if filter_value:
                    args["filter_value"] = str(filter_value)

                result = await self.session.call_tool("query_ison", args)
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            doc = loads(ison_text)
            results = []

            blocks = [doc[block_name]] if block_name and doc[block_name] else doc.blocks

            for block in blocks:
                if block is None:
                    continue
                rows = block.rows
                if filter_field and filter_value is not None:
                    rows = [r for r in rows if str(r.get(filter_field)) == str(filter_value)]
                if rows:
                    results.append({
                        "block": f"{block.kind}.{block.name}",
                        "rows": rows,
                        "count": len(rows)
                    })

            return ISONToolResult(
                success=True,
                data=results,
                message=f"Found {sum(r['count'] for r in results)} rows (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Query error: {e}"
            )

    async def convert_to_isonl(self, ison_text: str) -> ISONToolResult:
        """
        Convert ISON to streaming ISONL format.

        Args:
            ison_text: ISON text to convert.

        Returns:
            ISONToolResult with ISONL output.
        """
        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "convert_to_isonl",
                    {"ison_text": ison_text}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            doc = loads(ison_text)
            isonl = ison_parser.dumps_isonl(doc)
            return ISONToolResult(
                success=True,
                data=isonl,
                message="Converted to ISONL (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Conversion error: {e}"
            )

    async def parse_isonl(self, isonl_text: str) -> ISONToolResult:
        """
        Parse ISONL streaming format to records.

        Args:
            isonl_text: ISONL formatted text (one record per line).

        Returns:
            ISONToolResult with parsed records.
        """
        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "parse_isonl",
                    {"isonl_text": isonl_text}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            records = self._parse_isonl_local(isonl_text)
            return ISONToolResult(
                success=True,
                data=records,
                message=f"Parsed {len(records)} ISONL records (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Parse error: {e}"
            )

    async def format_isonl(
        self,
        data: Union[str, List[Dict]],
        block_name: str = "table.data"
    ) -> ISONToolResult:
        """
        Convert JSON array to streaming ISONL format.

        Args:
            data: JSON array string or list of dictionaries.
            block_name: Block name for ISONL records.

        Returns:
            ISONToolResult with ISONL output.
        """
        json_str = data if isinstance(data, str) else json.dumps(data)

        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "format_isonl",
                    {"json_array": json_str, "block_name": block_name}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            records = json.loads(json_str) if isinstance(data, str) else data
            if not isinstance(records, list):
                records = [records]

            isonl = self._format_isonl_local(records, block_name)
            return ISONToolResult(
                success=True,
                data=isonl,
                message=f"Formatted {len(records)} records to ISONL (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Format error: {e}"
            )

    def _parse_isonl_local(self, isonl_text: str) -> List[Dict]:
        """Parse ISONL text locally."""
        records = []
        schema_cache = {}

        for line in isonl_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('@schema '):
                parts = line[8:].split(':', 1)
                if len(parts) == 2:
                    block = parts[0].strip()
                    fields = parts[1].strip().split()
                    schema_cache[block] = fields
                continue

            if ':' not in line:
                continue

            block_part, values_part = line.split(':', 1)
            block_name = block_part.strip()
            values = self._parse_values(values_part.strip())

            fields = schema_cache.get(block_name)
            if fields:
                record = {'_block': block_name}
                for i, field in enumerate(fields):
                    if i < len(values):
                        record[field] = self._convert_value(values[i])
                records.append(record)
            else:
                records.append({
                    '_block': block_name,
                    '_values': [self._convert_value(v) for v in values]
                })

        return records

    def _format_isonl_local(self, records: List[Dict], block_name: str) -> str:
        """Format records to ISONL locally."""
        if not records:
            return ""

        fields = list(records[0].keys())
        lines = [f"@schema {block_name}: {' '.join(fields)}"]

        for record in records:
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

        return '\n'.join(lines)

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

    async def estimate_token_savings(self, json_data: Union[str, Dict]) -> ISONToolResult:
        """
        Estimate token savings from using ISON vs JSON.

        Args:
            json_data: JSON data to analyze.

        Returns:
            ISONToolResult with savings analysis.
        """
        json_str = json_data if isinstance(json_data, str) else json.dumps(json_data)

        if self._connected and self.session:
            try:
                result = await self.session.call_tool(
                    "estimate_token_savings",
                    {"json_data": json_str}
                )
                return self._process_tool_result(result)
            except Exception as e:
                if not self.use_local_fallback:
                    return ISONToolResult(
                        success=False,
                        data=None,
                        message=f"MCP call failed: {e}"
                    )

        # Local fallback
        try:
            data = json.loads(json_str) if isinstance(json_data, str) else json_data
            doc = from_dict(data)
            ison_output = dumps(doc)

            json_tokens = len(json_str) / 4
            ison_tokens = len(ison_output) / 4
            savings = ((json_tokens - ison_tokens) / json_tokens * 100) if json_tokens > 0 else 0

            return ISONToolResult(
                success=True,
                data={
                    "json_tokens": int(json_tokens),
                    "ison_tokens": int(ison_tokens),
                    "savings_percent": round(savings, 1),
                    "tokens_saved": int(json_tokens - ison_tokens)
                },
                message=f"Estimated {savings:.1f}% savings (local)"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Analysis error: {e}"
            )

    async def get_resource(self, uri: str) -> ISONToolResult:
        """
        Get ISON resource from MCP server.

        Args:
            uri: Resource URI (e.g., "ison://schema").

        Returns:
            ISONToolResult with resource content.
        """
        if not self._connected or not self.session:
            return ISONToolResult(
                success=False,
                data=None,
                message="Not connected to MCP server"
            )

        try:
            result = await self.session.read_resource(uri)

            if result.contents:
                content = result.contents[0]
                if hasattr(content, 'text'):
                    return ISONToolResult(
                        success=True,
                        data=content.text,
                        message=f"Retrieved resource: {uri}"
                    )

            return ISONToolResult(
                success=False,
                data=None,
                message=f"Empty resource: {uri}"
            )
        except Exception as e:
            return ISONToolResult(
                success=False,
                data=None,
                message=f"Resource error: {e}"
            )

    async def list_tools(self) -> List[str]:
        """
        List available ISON tools from server.

        Returns:
            List of tool names.
        """
        if not self._connected or not self.session:
            # Return local tool names
            return [
                "parse_ison",
                "format_ison",
                "validate_ison",
                "query_ison",
                "convert_to_isonl",
                "parse_isonl",
                "format_isonl",
                "estimate_token_savings"
            ]

        try:
            result = await self.session.list_tools()
            return [tool.name for tool in result.tools]
        except:
            return []

    async def list_resources(self) -> List[str]:
        """
        List available ISON resources from server.

        Returns:
            List of resource URIs.
        """
        if not self._connected or not self.session:
            return []

        try:
            result = await self.session.list_resources()
            return [res.uri for res in result.resources]
        except:
            return []

    def _process_tool_result(self, result: Any) -> ISONToolResult:
        """Process MCP tool result into ISONToolResult."""
        if hasattr(result, 'content') and result.content:
            content = result.content[0]
            if hasattr(content, 'text'):
                text = content.text
                # Try to parse JSON from result
                try:
                    data = json.loads(text)
                except:
                    data = text

                return ISONToolResult(
                    success=True,
                    data=data,
                    message="Success",
                    raw_response=text
                )

        return ISONToolResult(
            success=False,
            data=None,
            message="Empty response"
        )


class ISONMCPClientSync:
    """
    Synchronous wrapper for ISONMCPClient.

    Provides blocking API for environments that don't support async.

    Example:
        >>> client = ISONMCPClientSync()
        >>> result = client.parse_ison(ison_text)
    """

    def __init__(self, **kwargs):
        """Initialize sync client with same args as async client."""
        self._async_client = ISONMCPClient(**kwargs)
        self._loop = None

    def _get_loop(self):
        """Get or create event loop."""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _run(self, coro):
        """Run coroutine synchronously."""
        loop = self._get_loop()
        return loop.run_until_complete(coro)

    def connect(self) -> bool:
        """Connect to server synchronously."""
        return self._run(self._async_client.connect())

    def disconnect(self):
        """Disconnect synchronously."""
        self._run(self._async_client.disconnect())

    def parse_ison(self, ison_text: str) -> ISONToolResult:
        """Parse ISON synchronously."""
        return self._run(self._async_client.parse_ison(ison_text))

    def format_ison(self, data: Union[str, Dict], align: bool = True) -> ISONToolResult:
        """Format to ISON synchronously."""
        return self._run(self._async_client.format_ison(data, align))

    def validate_ison(self, ison_text: str) -> ISONToolResult:
        """Validate ISON synchronously."""
        return self._run(self._async_client.validate_ison(ison_text))

    def query_ison(self, ison_text: str, **kwargs) -> ISONToolResult:
        """Query ISON synchronously."""
        return self._run(self._async_client.query_ison(ison_text, **kwargs))

    def convert_to_isonl(self, ison_text: str) -> ISONToolResult:
        """Convert to ISONL synchronously."""
        return self._run(self._async_client.convert_to_isonl(ison_text))

    def parse_isonl(self, isonl_text: str) -> ISONToolResult:
        """Parse ISONL synchronously."""
        return self._run(self._async_client.parse_isonl(isonl_text))

    def format_isonl(self, data: Union[str, List[Dict]], block_name: str = "table.data") -> ISONToolResult:
        """Format to ISONL synchronously."""
        return self._run(self._async_client.format_isonl(data, block_name))

    def estimate_token_savings(self, json_data: Union[str, Dict]) -> ISONToolResult:
        """Estimate savings synchronously."""
        return self._run(self._async_client.estimate_token_savings(json_data))
