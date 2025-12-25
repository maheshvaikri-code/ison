"""
ISON RudraDB Plugin

Export RudraDB data to ISON format for LLM-friendly serialization.
RudraDB is a high-performance Rust-based embedded database with
relationship/graph capabilities.

Features:
- Export tables and relationships to ISON
- Automatic foreign key detection as ISON references
- Vector data support
- Relationship type preservation
- Streaming export for large datasets (ISONL)

Installation:
    pip install ison-parser[rudradb]
    # or
    pip install ison-parser rudradb

Usage:
    from ison_parser.plugins import RudraDBToISON

    # Connect to database
    exporter = RudraDBToISON(db_path='./my_database')

    # Export all data
    ison_text = exporter.export_all()

    # Export specific collections
    ison_text = exporter.export_collections(['users', 'orders'])

    # Export query results
    ison_text = exporter.export_query(query_result)

    # Export with relationships
    ison_text = exporter.export_with_relationships('users', include_refs=True)
"""

from typing import Any, Dict, List, Optional, Iterator, Union, Callable
from .. import Document, Block, Reference, FieldInfo

__all__ = [
    'RudraDBToISON',
    'rudradb_to_ison',
    'rudradb_query_to_ison',
]


class RudraDBToISON:
    """
    Export RudraDB data to ISON format.

    RudraDB is a high-performance embedded database with relationship support.
    This plugin converts RudraDB query results and collections to token-efficient
    ISON format for LLM workflows.

    Example:
        >>> from ison_parser.plugins import RudraDBToISON
        >>> exporter = RudraDBToISON(db_path='./mydb')
        >>> ison = exporter.export_all()
        >>> print(ison)
        table.users
        id name email
        1 Alice alice@example.com
        2 Bob bob@example.com
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        db: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize RudraDB exporter.

        Args:
            db_path: Path to RudraDB database directory
            db: Existing RudraDB connection/instance
            **kwargs: Additional connection parameters
        """
        self.db_path = db_path
        self._db = db
        self._kwargs = kwargs
        self._connected = False

        if db is not None:
            self._db = db
            self._connected = True
        elif db_path is not None:
            self._connect()

    def _connect(self) -> None:
        """Establish connection to RudraDB."""
        try:
            # Import RudraDB - adjust import based on actual package name
            try:
                import rudradb
                self._rudradb = rudradb
            except ImportError:
                try:
                    import rudradb_trishul as rudradb
                    self._rudradb = rudradb
                except ImportError:
                    raise ImportError(
                        "RudraDB not found. Install with: pip install rudradb "
                        "or pip install rudradb-trishul"
                    )

            # Connect to database
            if self.db_path:
                self._db = self._rudradb.Database(self.db_path, **self._kwargs)
            else:
                self._db = self._rudradb.Database(**self._kwargs)

            self._connected = True

        except Exception as e:
            raise ConnectionError(f"Failed to connect to RudraDB: {e}")

    def _ensure_connected(self) -> None:
        """Ensure database connection is established."""
        if not self._connected:
            self._connect()

    @property
    def db(self) -> Any:
        """Get the RudraDB database instance."""
        self._ensure_connected()
        return self._db

    def get_collections(self) -> List[str]:
        """
        Get list of all collection/table names in the database.

        Returns:
            List of collection names
        """
        self._ensure_connected()

        # Try different methods to get collection list
        # Adjust based on actual RudraDB API
        if hasattr(self._db, 'collections'):
            return list(self._db.collections())
        elif hasattr(self._db, 'list_collections'):
            return self._db.list_collections()
        elif hasattr(self._db, 'tables'):
            return list(self._db.tables())
        elif hasattr(self._db, 'get_collections'):
            return self._db.get_collections()
        else:
            # Try to query for collection metadata
            return []

    def get_relationships(self) -> List[Dict[str, Any]]:
        """
        Get list of relationships/edges in the database.

        Returns:
            List of relationship definitions
        """
        self._ensure_connected()

        if hasattr(self._db, 'relationships'):
            return list(self._db.relationships())
        elif hasattr(self._db, 'get_relationships'):
            return self._db.get_relationships()
        elif hasattr(self._db, 'edges'):
            return list(self._db.edges())

        return []

    def export_all(
        self,
        include_relationships: bool = True,
        include_vectors: bool = False
    ) -> str:
        """
        Export entire database to ISON format.

        Args:
            include_relationships: Include relationship data
            include_vectors: Include vector embeddings (can be large)

        Returns:
            ISON formatted string
        """
        from ..serializer import Serializer

        self._ensure_connected()
        doc = Document()

        # Export all collections
        collections = self.get_collections()
        for collection_name in collections:
            block = self._export_collection_to_block(
                collection_name,
                include_vectors=include_vectors
            )
            if block and block.rows:
                doc.blocks.append(block)

        # Export relationships if requested
        if include_relationships:
            relationships = self.get_relationships()
            if relationships:
                rel_block = self._relationships_to_block(relationships)
                if rel_block and rel_block.rows:
                    doc.blocks.append(rel_block)

        return Serializer().serialize(doc)

    def export_collections(
        self,
        collection_names: List[str],
        include_vectors: bool = False
    ) -> str:
        """
        Export specific collections to ISON format.

        Args:
            collection_names: List of collection names to export
            include_vectors: Include vector embeddings

        Returns:
            ISON formatted string
        """
        from ..serializer import Serializer

        self._ensure_connected()
        doc = Document()

        for name in collection_names:
            block = self._export_collection_to_block(name, include_vectors=include_vectors)
            if block and block.rows:
                doc.blocks.append(block)

        return Serializer().serialize(doc)

    def export_collection(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
        include_vectors: bool = False
    ) -> str:
        """
        Export a single collection to ISON format.

        Args:
            collection_name: Name of the collection to export
            limit: Maximum number of records
            offset: Number of records to skip
            include_vectors: Include vector embeddings

        Returns:
            ISON formatted string
        """
        from ..serializer import Serializer

        block = self._export_collection_to_block(
            collection_name,
            limit=limit,
            offset=offset,
            include_vectors=include_vectors
        )

        if not block:
            return ""

        doc = Document()
        doc.blocks.append(block)
        return Serializer().serialize(doc)

    def export_query(
        self,
        query_result: Any,
        name: str = "query_result"
    ) -> str:
        """
        Export query results to ISON format.

        Args:
            query_result: RudraDB query result object or list of records
            name: Name for the result block

        Returns:
            ISON formatted string
        """
        from ..serializer import Serializer

        block = self._query_result_to_block(query_result, name)

        if not block:
            return ""

        doc = Document()
        doc.blocks.append(block)
        return Serializer().serialize(doc)

    def export_with_relationships(
        self,
        collection_name: str,
        relationship_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> str:
        """
        Export collection with related data via relationships.

        Args:
            collection_name: Primary collection to export
            relationship_types: Specific relationship types to follow (or all if None)
            depth: How many levels of relationships to follow

        Returns:
            ISON formatted string with related data
        """
        from ..serializer import Serializer

        self._ensure_connected()
        doc = Document()

        # Export primary collection
        primary_block = self._export_collection_to_block(collection_name)
        if primary_block:
            doc.blocks.append(primary_block)

        # Get related data
        seen_collections = {collection_name}
        related = self._get_related_collections(
            collection_name,
            relationship_types,
            depth,
            seen_collections
        )

        for related_name in related:
            block = self._export_collection_to_block(related_name)
            if block and block.rows:
                doc.blocks.append(block)

        return Serializer().serialize(doc)

    def stream_collection(
        self,
        collection_name: str,
        batch_size: int = 1000,
        include_vectors: bool = False
    ) -> Iterator[str]:
        """
        Stream a collection as ISONL format for large datasets.

        Args:
            collection_name: Name of the collection
            batch_size: Number of records per batch
            include_vectors: Include vector embeddings

        Yields:
            ISONL formatted lines
        """
        self._ensure_connected()

        # Get collection/table data
        collection = self._get_collection(collection_name)
        if collection is None:
            return

        # Get schema/fields
        fields = self._get_collection_fields(collection_name)
        if not fields:
            return

        header = f"table.{collection_name}"
        fields_str = " ".join(fields)

        # Stream records
        offset = 0
        while True:
            records = self._fetch_records(
                collection_name,
                limit=batch_size,
                offset=offset,
                include_vectors=include_vectors
            )

            if not records:
                break

            for record in records:
                values = []
                for field in fields:
                    value = record.get(field)
                    values.append(self._format_value(value, collection_name, field))

                yield f"{header}|{fields_str}|{' '.join(values)}"

            offset += len(records)
            if len(records) < batch_size:
                break

    def export_for_rag(
        self,
        collection_name: str,
        query: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
        include_metadata: bool = True
    ) -> str:
        """
        Export data optimized for RAG (Retrieval-Augmented Generation).

        If query_vector is provided, performs vector similarity search.
        Otherwise exports recent/relevant records.

        Args:
            collection_name: Collection to query
            query: Text query (if supported)
            query_vector: Vector for similarity search
            limit: Maximum number of results
            include_metadata: Include metadata fields

        Returns:
            ISON formatted context for LLM
        """
        from ..serializer import Serializer

        self._ensure_connected()

        # Perform vector search if vector provided
        if query_vector is not None:
            results = self._vector_search(
                collection_name,
                query_vector,
                limit=limit
            )
        else:
            # Just get recent records
            results = self._fetch_records(collection_name, limit=limit)

        if not results:
            return ""

        # Create RAG-optimized block
        block = Block("table", "context")

        # Add rank and score fields for RAG
        block.fields = ["rank", "score"]
        block.field_info = [
            FieldInfo("rank", "int"),
            FieldInfo("score", "float"),
        ]

        # Add content fields
        content_fields = self._get_content_fields(results[0] if results else {})
        for field in content_fields:
            if include_metadata or field in ['content', 'text', 'document', 'body']:
                block.fields.append(field)
                block.field_info.append(FieldInfo(field))

        # Add rows with rank
        for i, result in enumerate(results):
            row = {
                "rank": i + 1,
                "score": result.get("_score", result.get("score", 1.0 - i * 0.1))
            }

            for field in content_fields:
                if include_metadata or field in ['content', 'text', 'document', 'body']:
                    value = result.get(field)
                    if isinstance(value, dict) and '_ref' in value:
                        row[field] = Reference(str(value['_ref']), value.get('_type'))
                    else:
                        row[field] = value

            block.rows.append(row)

        doc = Document()
        doc.blocks.append(block)
        return Serializer().serialize(doc)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _get_collection(self, name: str) -> Any:
        """Get collection/table by name."""
        if hasattr(self._db, 'collection'):
            return self._db.collection(name)
        elif hasattr(self._db, 'get_collection'):
            return self._db.get_collection(name)
        elif hasattr(self._db, 'table'):
            return self._db.table(name)
        elif hasattr(self._db, '__getitem__'):
            return self._db[name]
        return None

    def _get_collection_fields(self, collection_name: str) -> List[str]:
        """Get field names for a collection."""
        collection = self._get_collection(collection_name)
        if collection is None:
            return []

        # Try to get schema
        if hasattr(collection, 'schema'):
            schema = collection.schema()
            if isinstance(schema, dict):
                return list(schema.keys())
            return schema

        # Try to get fields from first record
        records = self._fetch_records(collection_name, limit=1)
        if records:
            return list(records[0].keys())

        return []

    def _fetch_records(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
        include_vectors: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch records from a collection."""
        collection = self._get_collection(collection_name)
        if collection is None:
            return []

        records = []

        # Try different query methods
        if hasattr(collection, 'find'):
            cursor = collection.find()
            if offset > 0 and hasattr(cursor, 'skip'):
                cursor = cursor.skip(offset)
            if limit and hasattr(cursor, 'limit'):
                cursor = cursor.limit(limit)
            records = list(cursor)
        elif hasattr(collection, 'all'):
            all_records = list(collection.all())
            if limit:
                records = all_records[offset:offset + limit]
            else:
                records = all_records[offset:]
        elif hasattr(collection, 'select'):
            query = collection.select()
            if limit:
                query = query.limit(limit).offset(offset)
            records = list(query)
        elif hasattr(collection, 'query'):
            records = collection.query(limit=limit, offset=offset)

        # Filter out vector fields if not requested
        if not include_vectors:
            filtered = []
            for record in records:
                filtered_record = {}
                for key, value in record.items():
                    # Skip vector fields (typically lists of floats)
                    if isinstance(value, list) and len(value) > 10:
                        if all(isinstance(v, (int, float)) for v in value[:10]):
                            continue
                    filtered_record[key] = value
                filtered.append(filtered_record)
            records = filtered

        return records

    def _vector_search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        collection = self._get_collection(collection_name)
        if collection is None:
            return []

        # Try different search methods
        if hasattr(collection, 'search'):
            return list(collection.search(query_vector, limit=limit))
        elif hasattr(collection, 'query'):
            return collection.query(vector=query_vector, limit=limit)
        elif hasattr(collection, 'similarity_search'):
            return collection.similarity_search(query_vector, k=limit)

        # Fallback: just return recent records
        return self._fetch_records(collection_name, limit=limit)

    def _export_collection_to_block(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
        include_vectors: bool = False
    ) -> Optional[Block]:
        """Convert a collection to an ISON Block."""
        records = self._fetch_records(
            collection_name,
            limit=limit,
            offset=offset,
            include_vectors=include_vectors
        )

        if not records:
            return None

        # Determine fields from records
        all_fields = set()
        for record in records:
            all_fields.update(record.keys())

        # Order fields: id first, then alphabetically
        fields = sorted(all_fields)
        if 'id' in fields:
            fields.remove('id')
            fields = ['id'] + fields
        if '_id' in fields:
            fields.remove('_id')
            fields = ['_id'] + fields

        # Create block
        block = Block("table", collection_name)
        block.fields = fields
        block.field_info = [self._infer_field_info(f, records) for f in fields]

        # Add rows
        for record in records:
            row = {}
            for field in fields:
                value = record.get(field)
                row[field] = self._convert_value(value, collection_name, field)
            block.rows.append(row)

        return block

    def _query_result_to_block(
        self,
        query_result: Any,
        name: str
    ) -> Optional[Block]:
        """Convert query result to an ISON Block."""
        # Handle different result types
        if isinstance(query_result, list):
            records = query_result
        elif hasattr(query_result, '__iter__'):
            records = list(query_result)
        elif hasattr(query_result, 'to_dict'):
            records = [query_result.to_dict()]
        elif isinstance(query_result, dict):
            records = [query_result]
        else:
            return None

        if not records:
            return None

        # Get all fields
        all_fields = set()
        for record in records:
            if isinstance(record, dict):
                all_fields.update(record.keys())

        if not all_fields:
            return None

        fields = sorted(all_fields)

        block = Block("table", name)
        block.fields = fields
        block.field_info = [FieldInfo(f) for f in fields]

        for record in records:
            if isinstance(record, dict):
                row = {}
                for field in fields:
                    row[field] = self._convert_value(record.get(field), name, field)
                block.rows.append(row)

        return block

    def _relationships_to_block(
        self,
        relationships: List[Dict[str, Any]]
    ) -> Optional[Block]:
        """Convert relationships to an ISON Block."""
        if not relationships:
            return None

        block = Block("table", "relationships")
        block.fields = ["id", "type", "source", "target"]
        block.field_info = [
            FieldInfo("id"),
            FieldInfo("type", "string"),
            FieldInfo("source", "ref"),
            FieldInfo("target", "ref"),
        ]

        for i, rel in enumerate(relationships):
            row = {
                "id": rel.get("id", i + 1),
                "type": rel.get("type", rel.get("relationship_type", "RELATES_TO")),
                "source": Reference(
                    str(rel.get("source_id", rel.get("from_id", ""))),
                    rel.get("source_type", rel.get("from_type"))
                ),
                "target": Reference(
                    str(rel.get("target_id", rel.get("to_id", ""))),
                    rel.get("target_type", rel.get("to_type"))
                ),
            }
            block.rows.append(row)

        return block

    def _get_related_collections(
        self,
        collection_name: str,
        relationship_types: Optional[List[str]],
        depth: int,
        seen: set
    ) -> List[str]:
        """Get names of related collections."""
        if depth <= 0:
            return []

        related = []
        relationships = self.get_relationships()

        for rel in relationships:
            rel_type = rel.get("type", "")
            if relationship_types and rel_type not in relationship_types:
                continue

            source_type = rel.get("source_type", rel.get("from_collection", ""))
            target_type = rel.get("target_type", rel.get("to_collection", ""))

            if source_type == collection_name and target_type not in seen:
                seen.add(target_type)
                related.append(target_type)
                related.extend(self._get_related_collections(
                    target_type, relationship_types, depth - 1, seen
                ))
            elif target_type == collection_name and source_type not in seen:
                seen.add(source_type)
                related.append(source_type)
                related.extend(self._get_related_collections(
                    source_type, relationship_types, depth - 1, seen
                ))

        return related

    def _infer_field_info(
        self,
        field_name: str,
        records: List[Dict[str, Any]]
    ) -> FieldInfo:
        """Infer field type from values."""
        for record in records:
            value = record.get(field_name)
            if value is not None:
                if isinstance(value, bool):
                    return FieldInfo(field_name, "bool")
                elif isinstance(value, int):
                    return FieldInfo(field_name, "int")
                elif isinstance(value, float):
                    return FieldInfo(field_name, "float")
                elif isinstance(value, dict) and ('_ref' in value or '_id' in value):
                    return FieldInfo(field_name, "ref")
                elif isinstance(value, str):
                    return FieldInfo(field_name, "string")

        return FieldInfo(field_name)

    def _convert_value(
        self,
        value: Any,
        collection_name: str,
        field_name: str
    ) -> Any:
        """Convert a RudraDB value to ISON value."""
        if value is None:
            return None

        # Handle reference/relationship objects
        if isinstance(value, dict):
            if '_ref' in value:
                return Reference(str(value['_ref']), value.get('_type'))
            if '_id' in value:
                return Reference(str(value['_id']), value.get('_collection'))
            if 'id' in value and len(value) <= 3:
                # Likely a reference object
                return Reference(str(value['id']), value.get('type'))

        # Handle list values (convert to comma-separated string for ISON)
        if isinstance(value, list):
            if len(value) == 0:
                return None
            # Check if it's a vector (skip large numeric arrays)
            if len(value) > 10 and all(isinstance(v, (int, float)) for v in value[:10]):
                return f"[vector:{len(value)}d]"
            # Small lists: convert to string
            return ", ".join(str(v) for v in value)

        # Handle dates/timestamps
        if hasattr(value, 'isoformat'):
            return value.isoformat()

        # Handle bytes
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')

        return value

    def _format_value(
        self,
        value: Any,
        collection_name: str,
        field_name: str
    ) -> str:
        """Format a value for ISONL output."""
        converted = self._convert_value(value, collection_name, field_name)

        if converted is None:
            return "null"
        if isinstance(converted, bool):
            return "true" if converted else "false"
        if isinstance(converted, Reference):
            return converted.to_ison()
        if isinstance(converted, (int, float)):
            return str(converted)

        # String - quote if needed
        s = str(converted)
        if ' ' in s or '\t' in s or '\n' in s or '|' in s or s in ('true', 'false', 'null'):
            escaped = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{escaped}"'
        return s

    def _get_content_fields(self, record: Dict[str, Any]) -> List[str]:
        """Get content-relevant fields for RAG context."""
        priority_fields = ['content', 'text', 'body', 'document', 'description', 'title', 'name']
        fields = []

        # Add priority fields first
        for field in priority_fields:
            if field in record:
                fields.append(field)

        # Add remaining fields
        for field in record.keys():
            if field not in fields and not field.startswith('_'):
                fields.append(field)

        return fields

    def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            if hasattr(self._db, 'close'):
                self._db.close()
            elif hasattr(self._db, 'disconnect'):
                self._db.disconnect()
        self._connected = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# =============================================================================
# Convenience Functions
# =============================================================================

def rudradb_to_ison(
    db_path: str,
    collections: Optional[List[str]] = None,
    include_relationships: bool = True
) -> str:
    """
    Quick function to export RudraDB to ISON.

    Args:
        db_path: Path to RudraDB database
        collections: Specific collections to export (or all if None)
        include_relationships: Include relationship data

    Returns:
        ISON formatted string

    Example:
        >>> ison = rudradb_to_ison('./mydb', collections=['users', 'posts'])
        >>> print(ison)
    """
    with RudraDBToISON(db_path=db_path) as exporter:
        if collections:
            return exporter.export_collections(collections)
        return exporter.export_all(include_relationships=include_relationships)


def rudradb_query_to_ison(
    db: Any,
    query_result: Any,
    name: str = "result"
) -> str:
    """
    Convert a RudraDB query result to ISON.

    Args:
        db: RudraDB database instance
        query_result: Query result to convert
        name: Name for the result block

    Returns:
        ISON formatted string

    Example:
        >>> import rudradb
        >>> db = rudradb.Database('./mydb')
        >>> results = db.query("SELECT * FROM users WHERE active = true")
        >>> ison = rudradb_query_to_ison(db, results, name='active_users')
    """
    exporter = RudraDBToISON(db=db)
    return exporter.export_query(query_result, name=name)


def rudradb_rag_context(
    db_path: str,
    collection: str,
    query_vector: Optional[List[float]] = None,
    limit: int = 5
) -> str:
    """
    Get RAG context from RudraDB in ISON format.

    Args:
        db_path: Path to RudraDB database
        collection: Collection to search
        query_vector: Vector for similarity search (optional)
        limit: Maximum number of results

    Returns:
        ISON formatted context optimized for LLM

    Example:
        >>> embedding = get_embedding("What is RudraDB?")
        >>> context = rudradb_rag_context('./mydb', 'documents', embedding)
        >>> response = llm.complete(f"Context:\\n{context}\\n\\nQuestion: What is RudraDB?")
    """
    with RudraDBToISON(db_path=db_path) as exporter:
        return exporter.export_for_rag(
            collection,
            query_vector=query_vector,
            limit=limit
        )
