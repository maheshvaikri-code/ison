#!/usr/bin/env python3
"""
Qdrant to ISON Plugin
Export Qdrant collections to ISON format for LLM workflows.

Requires: qdrant-client
    pip install qdrant-client

Usage:
    from ison_parser.plugins import QdrantToISON

    # Connect to Qdrant
    exporter = QdrantToISON(host='localhost', port=6333)
    exporter = QdrantToISON(url='https://my-qdrant.cloud')

    # Export search results for RAG
    ison_text = exporter.export_search_results(
        collection='documents',
        query_vector=embedding,
        limit=10
    )

    # Export collection
    ison_text = exporter.export_collection('documents')

    # Stream large collections
    for line in exporter.stream_collection('documents'):
        process(line)
"""

from typing import List, Optional, Dict, Any, Iterator, Callable, Union
import json


class QdrantToISON:
    """Export Qdrant collections to ISON format."""

    def __init__(self, host: str = None, port: int = 6333,
                 url: str = None, api_key: str = None,
                 grpc_port: int = None, prefer_grpc: bool = False):
        """
        Initialize Qdrant exporter.

        Args:
            host: Qdrant host
            port: REST port (default 6333)
            url: Full URL (alternative to host/port)
            api_key: API key for cloud instances
            grpc_port: gRPC port
            prefer_grpc: Use gRPC instead of REST
        """
        self._host = host or 'localhost'
        self._port = port
        self._url = url
        self._api_key = api_key
        self._grpc_port = grpc_port
        self._prefer_grpc = prefer_grpc
        self._client = None

    @property
    def client(self):
        """Get or create Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError(
                    "qdrant-client is required. Install with: pip install qdrant-client"
                )

            if self._url:
                self._client = QdrantClient(
                    url=self._url,
                    api_key=self._api_key,
                    prefer_grpc=self._prefer_grpc
                )
            else:
                self._client = QdrantClient(
                    host=self._host,
                    port=self._port,
                    grpc_port=self._grpc_port,
                    api_key=self._api_key,
                    prefer_grpc=self._prefer_grpc
                )

        return self._client

    def get_collections(self) -> List[str]:
        """Get list of all collection names."""
        collections = self.client.get_collections()
        return [c.name for c in collections.collections]

    def get_collection_info(self, name: str) -> Dict[str, Any]:
        """Get collection info and statistics."""
        info = self.client.get_collection(name)
        return {
            'name': name,
            'vectors_count': info.vectors_count,
            'points_count': info.points_count,
            'status': info.status.value if hasattr(info.status, 'value') else str(info.status),
            'config': {
                'vector_size': info.config.params.vectors.size if hasattr(info.config.params.vectors, 'size') else None,
                'distance': info.config.params.vectors.distance.value if hasattr(info.config.params.vectors.distance, 'value') else None
            }
        }

    def _format_value(self, value: Any) -> str:
        """Format a value for ISON output."""
        if value is None:
            return '~'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, (int, float)):
            if isinstance(value, float):
                return f"{value:.4f}"
            return str(value)

        if isinstance(value, list):
            # Embeddings
            if len(value) > 10 and all(isinstance(v, (int, float)) for v in value):
                return f'"[{len(value)}d]"'
            items = [self._format_value(v) for v in value]
            return '[' + ','.join(items) + ']'

        if isinstance(value, dict):
            return '"' + json.dumps(value).replace('"', '\\"') + '"'

        # String
        str_val = str(value)
        if ' ' in str_val or '\n' in str_val or '\t' in str_val or '"' in str_val:
            escaped = str_val.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{escaped}"'

        return str_val if str_val else '""'

    def export_search_results(self, collection: str, query_vector: List[float],
                              limit: int = 10, score_threshold: float = None,
                              filter: Dict = None,
                              with_payload: bool = True,
                              with_vectors: bool = False) -> str:
        """
        Export Qdrant search results to ISON format.

        Args:
            collection: Collection name
            query_vector: Query embedding
            limit: Maximum results
            score_threshold: Minimum score
            filter: Filter conditions
            with_payload: Include payload data
            with_vectors: Include vectors

        Returns:
            ISON formatted string
        """
        from qdrant_client.models import Filter

        search_filter = None
        if filter:
            search_filter = Filter(**filter)

        results = self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=search_filter,
            with_payload=with_payload,
            with_vectors=with_vectors
        )

        # Collect payload keys
        payload_keys = set()
        if with_payload:
            for point in results:
                if point.payload:
                    payload_keys.update(point.payload.keys())
        payload_keys = sorted(payload_keys)

        # Build fields
        fields = ['id', 'score:float']
        if with_vectors:
            fields.append('vector')
        fields.extend(payload_keys)

        # Build ISON
        lines = ['table.results']
        lines.append(' '.join(fields))

        for point in results:
            values = [
                self._format_value(point.id),
                f"{point.score:.4f}"
            ]

            if with_vectors:
                values.append(self._format_value(point.vector))

            payload = point.payload or {}
            for key in payload_keys:
                values.append(self._format_value(payload.get(key)))

            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_collection(self, collection: str, limit: int = 1000,
                          offset: int = None,
                          with_payload: bool = True,
                          with_vectors: bool = False,
                          filter: Dict = None) -> str:
        """
        Export a Qdrant collection to ISON format.

        Args:
            collection: Collection name
            limit: Maximum points
            offset: Starting offset (point ID)
            with_payload: Include payload
            with_vectors: Include vectors
            filter: Filter conditions

        Returns:
            ISON formatted string
        """
        from qdrant_client.models import Filter

        scroll_filter = None
        if filter:
            scroll_filter = Filter(**filter)

        results, next_offset = self.client.scroll(
            collection_name=collection,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vectors,
            scroll_filter=scroll_filter
        )

        # Collect payload keys
        payload_keys = set()
        if with_payload:
            for point in results:
                if point.payload:
                    payload_keys.update(point.payload.keys())
        payload_keys = sorted(payload_keys)

        # Build fields
        fields = ['id']
        if with_vectors:
            fields.append('vector')
        fields.extend(payload_keys)

        # Build ISON
        lines = [f'table.{collection}']
        lines.append(' '.join(fields))

        for point in results:
            values = [self._format_value(point.id)]

            if with_vectors:
                values.append(self._format_value(point.vector))

            payload = point.payload or {}
            for key in payload_keys:
                values.append(self._format_value(payload.get(key)))

            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_points(self, collection: str, ids: List[Union[int, str]],
                      with_payload: bool = True,
                      with_vectors: bool = False) -> str:
        """
        Export specific points by ID.

        Args:
            collection: Collection name
            ids: Point IDs
            with_payload: Include payload
            with_vectors: Include vectors

        Returns:
            ISON formatted string
        """
        results = self.client.retrieve(
            collection_name=collection,
            ids=ids,
            with_payload=with_payload,
            with_vectors=with_vectors
        )

        # Collect payload keys
        payload_keys = set()
        if with_payload:
            for point in results:
                if point.payload:
                    payload_keys.update(point.payload.keys())
        payload_keys = sorted(payload_keys)

        # Build fields
        fields = ['id']
        if with_vectors:
            fields.append('vector')
        fields.extend(payload_keys)

        # Build ISON
        lines = [f'table.{collection}']
        lines.append(' '.join(fields))

        for point in results:
            values = [self._format_value(point.id)]

            if with_vectors:
                values.append(self._format_value(point.vector))

            payload = point.payload or {}
            for key in payload_keys:
                values.append(self._format_value(payload.get(key)))

            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_for_rag(self, collection: str, query: str,
                       embedding_fn: Callable[[str], List[float]],
                       limit: int = 5, score_threshold: float = None,
                       filter: Dict = None) -> str:
        """
        Export optimized RAG context from Qdrant.

        Args:
            collection: Collection name
            query: Text query
            embedding_fn: Text to embedding function
            limit: Number of results
            score_threshold: Minimum score
            filter: Filter conditions

        Returns:
            ISON formatted context for LLM
        """
        query_vector = embedding_fn(query)

        from qdrant_client.models import Filter

        search_filter = None
        if filter:
            search_filter = Filter(**filter)

        results = self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=search_filter,
            with_payload=True
        )

        # Build compact RAG context
        lines = ['table.context']
        lines.append('rank:int score:float source content')

        for i, point in enumerate(results):
            rank = i + 1
            score = point.score
            payload = point.payload or {}

            # Common metadata fields
            source = payload.get('source') or payload.get('title') or payload.get('filename') or str(point.id)
            content = payload.get('text') or payload.get('content') or payload.get('chunk') or ''

            lines.append(f'{rank} {score:.3f} {self._format_value(source)} {self._format_value(content)}')

        return '\n'.join(lines)

    def export_collections(self, names: List[str] = None,
                           limit_per_collection: int = 100) -> str:
        """Export multiple collections."""
        if names is None:
            names = self.get_collections()

        blocks = []
        for name in names:
            blocks.append(self.export_collection(name, limit=limit_per_collection))

        return '\n\n'.join(blocks)

    def stream_collection(self, collection: str, batch_size: int = 100,
                          with_payload: bool = True,
                          filter: Dict = None) -> Iterator[str]:
        """
        Stream a collection as ISONL format.

        Args:
            collection: Collection name
            batch_size: Points per batch
            with_payload: Include payload
            filter: Filter conditions

        Yields:
            ISONL formatted lines
        """
        from qdrant_client.models import Filter

        scroll_filter = None
        if filter:
            scroll_filter = Filter(**filter)

        # First batch to get payload keys
        results, next_offset = self.client.scroll(
            collection_name=collection,
            limit=batch_size,
            with_payload=with_payload,
            scroll_filter=scroll_filter
        )

        # Collect all payload keys
        payload_keys = set()
        all_results = list(results)

        while next_offset is not None:
            results, next_offset = self.client.scroll(
                collection_name=collection,
                limit=batch_size,
                offset=next_offset,
                with_payload=with_payload,
                scroll_filter=scroll_filter
            )
            all_results.extend(results)

        for point in all_results:
            if point.payload:
                payload_keys.update(point.payload.keys())

        payload_keys = sorted(payload_keys)
        fields = ['id'] + list(payload_keys)
        fields_str = ' '.join(fields)

        # Now stream all points
        offset = None
        while True:
            results, next_offset = self.client.scroll(
                collection_name=collection,
                limit=batch_size,
                offset=offset,
                with_payload=with_payload,
                scroll_filter=scroll_filter
            )

            for point in results:
                values = [self._format_value(point.id)]
                payload = point.payload or {}
                for key in payload_keys:
                    values.append(self._format_value(payload.get(key)))

                yield f"table.{collection}|{fields_str}|{' '.join(values)}"

            if next_offset is None:
                break
            offset = next_offset

    def export_collection_info(self, collection: str) -> str:
        """
        Export collection metadata as ISON.

        Args:
            collection: Collection name

        Returns:
            ISON formatted metadata
        """
        info = self.get_collection_info(collection)

        lines = ['meta.collection_info']
        lines.append('property value')
        lines.append(f'name "{collection}"')
        lines.append(f'points_count {info["points_count"]}')
        lines.append(f'vectors_count {info["vectors_count"]}')
        lines.append(f'status {info["status"]}')

        if info['config']['vector_size']:
            lines.append(f'vector_size {info["config"]["vector_size"]}')
        if info['config']['distance']:
            lines.append(f'distance {info["config"]["distance"]}')

        return '\n'.join(lines)


# Convenience functions
def qdrant_to_ison(collection: str, query_vector: List[float] = None,
                   ids: List = None, host: str = 'localhost',
                   port: int = 6333, limit: int = 10) -> str:
    """
    Quick export from Qdrant to ISON.

    Args:
        collection: Collection name
        query_vector: Query embedding (for search)
        ids: Point IDs (for fetch)
        host: Qdrant host
        port: Qdrant port
        limit: Result limit

    Returns:
        ISON formatted string
    """
    exporter = QdrantToISON(host=host, port=port)

    if query_vector:
        return exporter.export_search_results(collection, query_vector, limit)
    elif ids:
        return exporter.export_points(collection, ids)
    else:
        return exporter.export_collection(collection, limit)


def qdrant_rag_context(collection: str, query: str,
                       embedding_fn: Callable[[str], List[float]],
                       limit: int = 5, host: str = 'localhost',
                       port: int = 6333) -> str:
    """
    Get RAG context from Qdrant in ISON format.

    Args:
        collection: Collection name
        query: Text query
        embedding_fn: Text to embedding function
        limit: Number of results
        host: Qdrant host
        port: Qdrant port

    Returns:
        ISON formatted context
    """
    exporter = QdrantToISON(host=host, port=port)
    return exporter.export_for_rag(collection, query, embedding_fn, limit)
