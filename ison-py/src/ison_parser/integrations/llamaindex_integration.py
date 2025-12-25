"""
LlamaIndex ISON Reader

Provides LlamaIndex-compatible readers for ISON documents.
Enables token-efficient data loading for RAG pipelines.

Usage:
    from llama_index import VectorStoreIndex
    from ison_parser.integrations import ISONReader

    reader = ISONReader()
    documents = reader.load_data("data.ison")
    index = VectorStoreIndex.from_documents(documents)

    # With ISONantic typed models
    from isonantic import TableModel, Field

    class User(TableModel):
        __ison_block__ = "table.users"
        id: int = Field(primary_key=True)
        name: str

    reader = ISONReader(model=User)
    documents = reader.load_data("users.ison")  # Validated loading

Requirements:
    pip install llama-index llama-index-core
    pip install isonantic  # Optional, for typed models
"""

from typing import Any, Dict, List, Optional, Type
from pathlib import Path

try:
    from llama_index.core import Document as LlamaDocument
    from llama_index.core.readers.base import BaseReader
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    try:
        # Fallback for older versions
        from llama_index import Document as LlamaDocument
        from llama_index.readers.base import BaseReader
        LLAMAINDEX_AVAILABLE = True
    except ImportError:
        LLAMAINDEX_AVAILABLE = False
        BaseReader = object
        LlamaDocument = None

# Import ISON parser
import ison_parser
from ison_parser import Document, Block, load, loads, load_isonl, loads_isonl

# Try to import ISONantic for typed model support
try:
    from isonantic import (
        ISONModel, TableModel, ObjectModel,
        parse_ison, parse_ison_safe, prompt_for_model,
    )
    ISONANTIC_AVAILABLE = True
except ImportError:
    ISONANTIC_AVAILABLE = False
    ISONModel = None


class ISONReader(BaseReader if LLAMAINDEX_AVAILABLE else object):
    """
    LlamaIndex Reader for ISON and ISONL files.

    Converts ISON documents to LlamaIndex Document objects for indexing.
    Supports both standard ISON and streaming ISONL formats.
    Optionally validates with ISONantic models.

    Attributes:
        concat_rows: If True, concatenate all rows into single document.
        include_metadata: Include ISON block metadata in documents.
        row_separator: Separator between rows when concatenating.
        model: Optional ISONantic model for typed validation.

    Example (raw):
        >>> reader = ISONReader()
        >>> docs = reader.load_data("users.ison")

    Example (with ISONantic):
        >>> from isonantic import TableModel, Field
        >>> class User(TableModel):
        ...     __ison_block__ = "table.users"
        ...     id: int
        ...     name: str
        >>> reader = ISONReader(model=User)
        >>> docs = reader.load_data("users.ison")  # Validates data
    """

    def __init__(
        self,
        concat_rows: bool = False,
        include_metadata: bool = True,
        row_separator: str = "\n",
        model: Optional[Type] = None,
    ):
        """
        Initialize the ISON reader.

        Args:
            concat_rows: Concatenate all rows in a block to single document.
            include_metadata: Include block info as document metadata.
            row_separator: String separator between concatenated rows.
            model: Optional ISONantic model class for typed validation.
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is required for ISONReader. "
                "Install with: pip install llama-index llama-index-core"
            )
        if model is not None and not ISONANTIC_AVAILABLE:
            raise ImportError(
                "ISONantic is required for typed model validation. "
                "Install with: pip install isonantic"
            )
        self.concat_rows = concat_rows
        self.include_metadata = include_metadata
        self.row_separator = row_separator
        self.model = model

    def load_data(
        self,
        file: Optional[Path] = None,
        text: Optional[str] = None,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> List[LlamaDocument]:
        """
        Load ISON data and convert to LlamaIndex documents.

        If an ISONantic model is configured, validates data before loading.

        Args:
            file: Path to ISON or ISONL file.
            text: ISON/ISONL text content (alternative to file).
            extra_info: Additional metadata to include in documents.

        Returns:
            List of LlamaIndex Document objects.
        """
        if file is not None:
            file = Path(file)
            if file.suffix == '.isonl':
                ison_doc = load_isonl(file)
            else:
                ison_doc = load(file)
            source = str(file)
            raw_text = file.read_text()
        elif text is not None:
            # Auto-detect format
            if '|' in text.split('\n')[0]:
                ison_doc = loads_isonl(text)
            else:
                ison_doc = loads(text)
            source = "text_input"
            raw_text = text
        else:
            raise ValueError("Either 'file' or 'text' must be provided")

        # Validate with ISONantic model if provided
        validated_models = None
        if self.model is not None and ISONANTIC_AVAILABLE:
            result = parse_ison_safe(raw_text, self.model)
            if result.success:
                validated_models = result.data
            elif result.partial_data:
                validated_models = result.partial_data

        return self._convert_to_documents(
            ison_doc, source, extra_info, validated_models
        )

    def _convert_to_documents(
        self,
        ison_doc: Document,
        source: str,
        extra_info: Optional[Dict[str, Any]] = None,
        validated_models: Optional[List[Any]] = None,
    ) -> List[LlamaDocument]:
        """
        Convert ISON Document to LlamaIndex documents.

        Args:
            ison_doc: Parsed ISON document.
            source: Source identifier for metadata.
            extra_info: Additional metadata.
            validated_models: Optional list of validated ISONantic model instances.

        Returns:
            List of LlamaIndex documents.
        """
        documents = []

        for block in ison_doc.blocks:
            if self.concat_rows:
                # Create single document per block
                doc = self._block_to_single_document(block, source, extra_info)
                documents.append(doc)
            else:
                # Create document per row
                docs = self._block_to_row_documents(
                    block, source, extra_info, validated_models
                )
                documents.extend(docs)

        return documents

    def _block_to_single_document(
        self,
        block: Block,
        source: str,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> LlamaDocument:
        """
        Convert a block to a single LlamaIndex document.

        Args:
            block: ISON block to convert.
            source: Source identifier.
            extra_info: Additional metadata.

        Returns:
            Single LlamaIndex document with all rows.
        """
        # Format rows as text
        row_texts = []
        for row in block.rows:
            row_text = self._row_to_text(row, block.fields)
            row_texts.append(row_text)

        text = self.row_separator.join(row_texts)

        # Build metadata
        metadata = {}
        if self.include_metadata:
            metadata.update({
                "source": source,
                "block_kind": block.kind,
                "block_name": block.name,
                "fields": block.fields,
                "row_count": len(block.rows),
            })
        if extra_info:
            metadata.update(extra_info)

        return LlamaDocument(text=text, metadata=metadata)

    def _block_to_row_documents(
        self,
        block: Block,
        source: str,
        extra_info: Optional[Dict[str, Any]] = None,
        validated_models: Optional[List[Any]] = None,
    ) -> List[LlamaDocument]:
        """
        Convert each row in a block to a separate document.

        Args:
            block: ISON block to convert.
            source: Source identifier.
            extra_info: Additional metadata.
            validated_models: Optional validated ISONantic models.

        Returns:
            List of documents, one per row.
        """
        documents = []

        for i, row in enumerate(block.rows):
            text = self._row_to_text(row, block.fields)

            # Build metadata
            metadata = {}
            if self.include_metadata:
                metadata.update({
                    "source": source,
                    "block_kind": block.kind,
                    "block_name": block.name,
                    "row_index": i,
                })
                # Add row data as metadata
                for field, value in row.items():
                    metadata[f"field_{field}"] = value

                # Add validated model data if available
                if validated_models and i < len(validated_models):
                    model = validated_models[i]
                    metadata["validated"] = True
                    metadata["model_type"] = type(model).__name__

            if extra_info:
                metadata.update(extra_info)

            documents.append(LlamaDocument(text=text, metadata=metadata))

        return documents

    def _row_to_text(self, row: Dict[str, Any], fields: List[str]) -> str:
        """
        Convert a row dictionary to readable text.

        Args:
            row: Row data as dictionary.
            fields: Field names for ordering.

        Returns:
            Human-readable text representation.
        """
        parts = []
        for field in fields:
            value = row.get(field, "")
            if value is not None:
                parts.append(f"{field}: {value}")
        return ", ".join(parts)


class ISONNodeParser:
    """
    Node parser for chunking ISON documents.

    Creates nodes from ISON blocks with configurable chunking strategies.

    Example:
        >>> from llama_index.core.node_parser import NodeParser
        >>> parser = ISONNodeParser(chunk_by="row")
        >>> nodes = parser.get_nodes_from_documents(documents)
    """

    def __init__(
        self,
        chunk_by: str = "row",
        include_block_context: bool = True,
    ):
        """
        Initialize the node parser.

        Args:
            chunk_by: Chunking strategy - "row", "block", or "document".
            include_block_context: Include block header in each chunk.
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is required. Install with: pip install llama-index"
            )
        self.chunk_by = chunk_by
        self.include_block_context = include_block_context

    def parse_ison(
        self,
        ison_text: str,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> List[LlamaDocument]:
        """
        Parse ISON text directly to chunked documents.

        Args:
            ison_text: ISON formatted text.
            extra_info: Additional metadata.

        Returns:
            List of chunked documents.
        """
        ison_doc = loads(ison_text)
        documents = []

        if self.chunk_by == "document":
            # Single document for entire ISON
            text = ison_text
            metadata = {"chunk_type": "document"}
            if extra_info:
                metadata.update(extra_info)
            documents.append(LlamaDocument(text=text, metadata=metadata))

        elif self.chunk_by == "block":
            # One document per block
            for block in ison_doc.blocks:
                text = self._block_to_ison(block)
                metadata = {
                    "chunk_type": "block",
                    "block_kind": block.kind,
                    "block_name": block.name,
                }
                if extra_info:
                    metadata.update(extra_info)
                documents.append(LlamaDocument(text=text, metadata=metadata))

        else:  # row
            # One document per row
            for block in ison_doc.blocks:
                context = f"{block.kind}.{block.name}\n{' '.join(block.fields)}\n"

                for i, row in enumerate(block.rows):
                    if self.include_block_context:
                        text = context + self._row_to_ison(row, block.fields)
                    else:
                        text = self._row_to_ison(row, block.fields)

                    metadata = {
                        "chunk_type": "row",
                        "block_kind": block.kind,
                        "block_name": block.name,
                        "row_index": i,
                    }
                    if extra_info:
                        metadata.update(extra_info)
                    documents.append(LlamaDocument(text=text, metadata=metadata))

        return documents

    def _block_to_ison(self, block: Block) -> str:
        """Convert block back to ISON format."""
        lines = [f"{block.kind}.{block.name}"]
        lines.append(" ".join(block.fields))
        for row in block.rows:
            lines.append(self._row_to_ison(row, block.fields))
        return "\n".join(lines)

    def _row_to_ison(self, row: Dict[str, Any], fields: List[str]) -> str:
        """Convert row to ISON format line."""
        values = []
        for field in fields:
            value = row.get(field, "null")
            if value is None:
                values.append("null")
            elif isinstance(value, bool):
                values.append("true" if value else "false")
            elif isinstance(value, str) and (" " in value or '"' in value):
                escaped = value.replace('"', '\\"')
                values.append(f'"{escaped}"')
            else:
                values.append(str(value))
        return " ".join(values)


class ISONRAGHelper:
    """
    Helper class for ISON-based RAG workflows.

    Provides utilities for building RAG pipelines with ISON data.

    Example:
        >>> helper = ISONRAGHelper()
        >>> context = helper.format_for_context(ison_doc, max_tokens=1000)
    """

    def __init__(self, token_budget: int = 4000):
        """
        Initialize RAG helper.

        Args:
            token_budget: Maximum tokens for context window.
        """
        self.token_budget = token_budget

    def format_for_context(
        self,
        ison_doc: Document,
        max_tokens: Optional[int] = None,
        prioritize: Optional[List[str]] = None,
    ) -> str:
        """
        Format ISON document for LLM context window.

        Args:
            ison_doc: ISON document to format.
            max_tokens: Maximum tokens (rough estimate).
            prioritize: Block names to include first.

        Returns:
            Formatted ISON string optimized for context.
        """
        max_tokens = max_tokens or self.token_budget

        # Estimate tokens (~4 chars per token)
        max_chars = max_tokens * 4

        # Order blocks by priority
        blocks = list(ison_doc.blocks)
        if prioritize:
            priority_blocks = []
            other_blocks = []
            for block in blocks:
                if block.name in prioritize:
                    priority_blocks.append(block)
                else:
                    other_blocks.append(block)
            blocks = priority_blocks + other_blocks

        # Build output within budget
        output_parts = []
        current_chars = 0

        for block in blocks:
            block_ison = ison_parser.dumps(Document(blocks=[block]))
            block_chars = len(block_ison)

            if current_chars + block_chars <= max_chars:
                output_parts.append(block_ison)
                current_chars += block_chars
            else:
                # Try to include partial block
                remaining = max_chars - current_chars
                if remaining > 100:  # Minimum useful size
                    partial = self._truncate_block(block, remaining)
                    if partial:
                        output_parts.append(partial)
                break

        return "\n\n".join(output_parts)

    def _truncate_block(self, block: Block, max_chars: int) -> Optional[str]:
        """
        Truncate a block to fit within character limit.

        Args:
            block: Block to truncate.
            max_chars: Maximum characters.

        Returns:
            Truncated ISON string or None.
        """
        # Include header and fields
        header = f"{block.kind}.{block.name}\n{' '.join(block.fields)}\n"
        remaining = max_chars - len(header) - 20  # Reserve for truncation note

        if remaining <= 0:
            return None

        # Add rows until limit
        rows = []
        current_size = 0
        for row in block.rows:
            row_text = " ".join(str(row.get(f, "null")) for f in block.fields)
            if current_size + len(row_text) + 1 <= remaining:
                rows.append(row_text)
                current_size += len(row_text) + 1
            else:
                break

        if not rows:
            return None

        result = header + "\n".join(rows)
        if len(rows) < len(block.rows):
            result += f"\n# ... {len(block.rows) - len(rows)} more rows"

        return result


class ISONLReader(BaseReader if LLAMAINDEX_AVAILABLE else object):
    """
    LlamaIndex Reader for ISONL (ISON Lines) streaming files.

    Optimized for large ISONL datasets with lazy loading and constant memory.
    Ideal for fine-tuning datasets, event logs, and streaming data.

    Attributes:
        concat_records: If True, batch records into single documents.
        batch_size: Number of records per document when batching.
        include_metadata: Include record metadata in documents.
        model: Optional ISONantic model for typed validation.

    Example (basic):
        >>> reader = ISONLReader()
        >>> docs = reader.load_data("training_data.isonl")

    Example (lazy loading for large files):
        >>> reader = ISONLReader()
        >>> for doc in reader.lazy_load_data("large_dataset.isonl"):
        ...     process(doc)

    Example (with ISONantic):
        >>> from isonantic import TableModel, Field
        >>> class Event(TableModel):
        ...     __ison_block__ = "table.events"
        ...     timestamp: str
        ...     event_type: str
        ...     data: str
        >>> reader = ISONLReader(model=Event)
        >>> docs = reader.load_data("events.isonl")  # Validates each record
    """

    def __init__(
        self,
        concat_records: bool = False,
        batch_size: int = 100,
        include_metadata: bool = True,
        model: Optional[Type] = None,
    ):
        """
        Initialize the ISONL reader.

        Args:
            concat_records: Batch records into single documents.
            batch_size: Number of records per document when batching.
            include_metadata: Include record metadata in documents.
            model: Optional ISONantic model class for typed validation.
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is required for ISONLReader. "
                "Install with: pip install llama-index llama-index-core"
            )
        if model is not None and not ISONANTIC_AVAILABLE:
            raise ImportError(
                "ISONantic is required for typed model validation. "
                "Install with: pip install isonantic"
            )
        self.concat_records = concat_records
        self.batch_size = batch_size
        self.include_metadata = include_metadata
        self.model = model
        self._schema_cache: Dict[str, List[str]] = {}

    def load_data(
        self,
        file: Optional[Path] = None,
        text: Optional[str] = None,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> List[LlamaDocument]:
        """
        Load ISONL data and convert to LlamaIndex documents.

        Args:
            file: Path to ISONL file.
            text: ISONL text content (alternative to file).
            extra_info: Additional metadata to include in documents.

        Returns:
            List of LlamaIndex Document objects.
        """
        if file is not None:
            file = Path(file)
            lines = file.read_text().strip().split('\n')
            source = str(file)
        elif text is not None:
            lines = text.strip().split('\n')
            source = "text_input"
        else:
            raise ValueError("Either 'file' or 'text' must be provided")

        records = []
        for line in lines:
            record = self._parse_line(line.strip())
            if record is not None:
                # Validate with model if provided
                if self.model is not None and ISONANTIC_AVAILABLE:
                    record = self._validate_record(record)
                records.append(record)

        return self._records_to_documents(records, source, extra_info)

    def lazy_load_data(
        self,
        file: Path,
        extra_info: Optional[Dict[str, Any]] = None,
    ):
        """
        Lazily load ISONL file, yielding documents one at a time.

        Memory-efficient for large files - only keeps one record in memory.

        Args:
            file: Path to ISONL file.
            extra_info: Additional metadata to include in documents.

        Yields:
            LlamaIndex Document objects one at a time.
        """
        file = Path(file)
        source = str(file)

        if self.concat_records:
            # Yield batches
            batch = []
            with open(file, 'r') as f:
                for line_num, line in enumerate(f):
                    record = self._parse_line(line.strip())
                    if record is not None:
                        if self.model is not None and ISONANTIC_AVAILABLE:
                            record = self._validate_record(record)
                        batch.append(record)

                        if len(batch) >= self.batch_size:
                            yield self._batch_to_document(batch, source, extra_info)
                            batch = []

                # Yield remaining batch
                if batch:
                    yield self._batch_to_document(batch, source, extra_info)
        else:
            # Yield individual records
            with open(file, 'r') as f:
                for line_num, line in enumerate(f):
                    record = self._parse_line(line.strip())
                    if record is not None:
                        if self.model is not None and ISONANTIC_AVAILABLE:
                            record = self._validate_record(record)
                        yield self._record_to_document(record, source, line_num, extra_info)

    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single ISONL line.

        Args:
            line: Single ISONL line.

        Returns:
            Parsed record dictionary, or None for comments/schema lines.
        """
        if not line or line.startswith('#'):
            return None

        # Handle schema definition
        if line.startswith('@schema '):
            self._parse_schema(line[8:])
            return None

        # Parse record
        if ':' not in line:
            return None

        block_part, values_part = line.split(':', 1)
        block_name = block_part.strip()
        values = self._parse_values(values_part.strip())

        fields = self._schema_cache.get(block_name)
        if fields:
            record = {'_block': block_name}
            for i, field in enumerate(fields):
                if i < len(values):
                    record[field] = self._convert_value(values[i])
            return record

        return {'_block': block_name, '_values': [self._convert_value(v) for v in values]}

    def _parse_schema(self, schema_line: str) -> None:
        """Parse and cache schema definition."""
        if ':' not in schema_line:
            return
        block, fields = schema_line.split(':', 1)
        self._schema_cache[block.strip()] = fields.strip().split()

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

    def _validate_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Validate record with ISONantic model."""
        try:
            data = {k: v for k, v in record.items() if not k.startswith('_')}
            instance = self.model(**data)
            record['_validated'] = True
            record['_model'] = instance
            return record
        except Exception as e:
            record['_validated'] = False
            record['_validation_error'] = str(e)
            return record

    def _records_to_documents(
        self,
        records: List[Dict[str, Any]],
        source: str,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> List[LlamaDocument]:
        """Convert records to LlamaIndex documents."""
        if self.concat_records:
            # Batch records
            documents = []
            for i in range(0, len(records), self.batch_size):
                batch = records[i:i + self.batch_size]
                doc = self._batch_to_document(batch, source, extra_info)
                documents.append(doc)
            return documents
        else:
            # Individual documents
            return [
                self._record_to_document(r, source, i, extra_info)
                for i, r in enumerate(records)
            ]

    def _record_to_document(
        self,
        record: Dict[str, Any],
        source: str,
        index: int,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> LlamaDocument:
        """Convert single record to document."""
        # Format record as text
        text_parts = []
        for k, v in record.items():
            if not k.startswith('_'):
                text_parts.append(f"{k}: {v}")
        text = ", ".join(text_parts)

        # Build metadata
        metadata = {"source": source, "record_index": index}
        if self.include_metadata:
            metadata["block"] = record.get('_block', 'unknown')
            if record.get('_validated') is not None:
                metadata["validated"] = record['_validated']
        if extra_info:
            metadata.update(extra_info)

        return LlamaDocument(text=text, metadata=metadata)

    def _batch_to_document(
        self,
        batch: List[Dict[str, Any]],
        source: str,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> LlamaDocument:
        """Convert batch of records to single document."""
        # Format batch as text
        lines = []
        for record in batch:
            parts = [f"{k}: {v}" for k, v in record.items() if not k.startswith('_')]
            lines.append(", ".join(parts))
        text = "\n".join(lines)

        # Build metadata
        metadata = {
            "source": source,
            "record_count": len(batch),
            "format": "isonl_batch",
        }
        if extra_info:
            metadata.update(extra_info)

        return LlamaDocument(text=text, metadata=metadata)


class ISONLNodeParser:
    """
    Node parser for chunking ISONL streams.

    Creates nodes from ISONL records with configurable batching.

    Example:
        >>> parser = ISONLNodeParser(records_per_node=50)
        >>> nodes = parser.parse_file("events.isonl")
    """

    def __init__(
        self,
        records_per_node: int = 100,
        include_schema: bool = True,
    ):
        """
        Initialize the ISONL node parser.

        Args:
            records_per_node: Number of records per node.
            include_schema: Include schema line in each node.
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is required. Install with: pip install llama-index"
            )
        self.records_per_node = records_per_node
        self.include_schema = include_schema
        self._schema_lines: Dict[str, str] = {}

    def parse_file(
        self,
        file: Path,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> List[LlamaDocument]:
        """
        Parse ISONL file to chunked documents.

        Args:
            file: Path to ISONL file.
            extra_info: Additional metadata.

        Returns:
            List of chunked documents.
        """
        file = Path(file)
        documents = []
        batch = []
        batch_num = 0

        with open(file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Track schema lines
                if line.startswith('@schema '):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        block = parts[0].replace('@schema ', '').strip()
                        self._schema_lines[block] = line
                    continue

                batch.append(line)

                if len(batch) >= self.records_per_node:
                    doc = self._create_document(batch, file, batch_num, extra_info)
                    documents.append(doc)
                    batch = []
                    batch_num += 1

        # Final batch
        if batch:
            doc = self._create_document(batch, file, batch_num, extra_info)
            documents.append(doc)

        return documents

    def _create_document(
        self,
        lines: List[str],
        file: Path,
        batch_num: int,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> LlamaDocument:
        """Create document from batch of lines."""
        # Prepend schema if requested
        text_lines = []
        if self.include_schema and self._schema_lines:
            for schema_line in self._schema_lines.values():
                text_lines.append(schema_line)
        text_lines.extend(lines)
        text = "\n".join(text_lines)

        metadata = {
            "source": str(file),
            "batch_index": batch_num,
            "record_count": len(lines),
            "format": "isonl",
        }
        if extra_info:
            metadata.update(extra_info)

        return LlamaDocument(text=text, metadata=metadata)
