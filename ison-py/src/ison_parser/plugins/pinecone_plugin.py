#!/usr/bin/env python3
"""
Pinecone to ISON Plugin
Export Pinecone indexes to ISON format for LLM workflows.

Requires: pinecone-client
    pip install pinecone-client

Usage:
    from ison_parser.plugins import PineconeToISON

    # Connect to Pinecone
    exporter = PineconeToISON(api_key='your-api-key')

    # Export query results for RAG
    ison_text = exporter.export_query_results(
        index='my-index',
        query_vector=embedding,
        top_k=10
    )

    # Export with text query (requires embedding model)
    ison_text = exporter.export_for_rag(
        index='my-index',
        query='What is ISON?',
        embedding_fn=my_embed_function,
        top_k=5
    )

    # Fetch specific vectors
    ison_text = exporter.export_vectors(
        index='my-index',
        ids=['doc1', 'doc2', 'doc3']
    )
"""

from typing import List, Optional, Dict, Any, Iterator, Callable, Union
import json


class PineconeToISON:
    """Export Pinecone indexes to ISON format."""

    def __init__(self, api_key: str = None, environment: str = None,
                 index_host: str = None):
        """
        Initialize Pinecone exporter.

        Args:
            api_key: Pinecone API key (or set PINECONE_API_KEY env var)
            environment: Pinecone environment (legacy)
            index_host: Direct index host URL (for serverless)
        """
        self._api_key = api_key
        self._environment = environment
        self._index_host = index_host
        self._pc = None
        self._indexes: Dict[str, Any] = {}

    @property
    def pc(self):
        """Get or create Pinecone client."""
        if self._pc is None:
            try:
                from pinecone import Pinecone
            except ImportError:
                raise ImportError(
                    "pinecone-client is required. Install with: pip install pinecone-client"
                )

            self._pc = Pinecone(api_key=self._api_key)

        return self._pc

    def get_index(self, name: str):
        """Get or connect to a Pinecone index."""
        if name not in self._indexes:
            self._indexes[name] = self.pc.Index(name)
        return self._indexes[name]

    def list_indexes(self) -> List[str]:
        """List all available indexes."""
        indexes = self.pc.list_indexes()
        return [idx.name for idx in indexes]

    def get_index_stats(self, name: str) -> Dict[str, Any]:
        """Get index statistics."""
        index = self.get_index(name)
        stats = index.describe_index_stats()
        return {
            'total_vector_count': stats.total_vector_count,
            'dimension': stats.dimension,
            'namespaces': dict(stats.namespaces) if stats.namespaces else {}
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
            # Embeddings - just show dimension
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

    def export_query_results(self, index: str, query_vector: List[float],
                             top_k: int = 10, namespace: str = None,
                             filter: Dict = None,
                             include_metadata: bool = True,
                             include_values: bool = False) -> str:
        """
        Export Pinecone query results to ISON format.

        Args:
            index: Index name
            query_vector: Query embedding vector
            top_k: Number of results
            namespace: Optional namespace
            filter: Metadata filter
            include_metadata: Include metadata fields
            include_values: Include embedding vectors

        Returns:
            ISON formatted string
        """
        idx = self.get_index(index)

        results = idx.query(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_metadata=include_metadata,
            include_values=include_values
        )

        # Collect all metadata keys
        meta_keys = set()
        if include_metadata:
            for match in results.matches:
                if match.metadata:
                    meta_keys.update(match.metadata.keys())
        meta_keys = sorted(meta_keys)

        # Build fields
        fields = ['id', 'score:float']
        if include_values:
            fields.append('embedding')
        fields.extend(meta_keys)

        # Build ISON
        lines = ['table.results']
        lines.append(' '.join(fields))

        for match in results.matches:
            values = [
                self._format_value(match.id),
                f"{match.score:.4f}"
            ]

            if include_values:
                values.append(self._format_value(match.values))

            meta = match.metadata or {}
            for key in meta_keys:
                values.append(self._format_value(meta.get(key)))

            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_vectors(self, index: str, ids: List[str],
                       namespace: str = None,
                       include_values: bool = False) -> str:
        """
        Export specific vectors by ID.

        Args:
            index: Index name
            ids: Vector IDs to fetch
            namespace: Optional namespace
            include_values: Include embedding vectors

        Returns:
            ISON formatted string
        """
        idx = self.get_index(index)

        results = idx.fetch(ids=ids, namespace=namespace)

        if not results.vectors:
            return f"table.{index}\nid\n# No vectors found"

        # Collect metadata keys
        meta_keys = set()
        for vec_id, vec in results.vectors.items():
            if vec.metadata:
                meta_keys.update(vec.metadata.keys())
        meta_keys = sorted(meta_keys)

        # Build fields
        fields = ['id']
        if include_values:
            fields.append('embedding')
        fields.extend(meta_keys)

        # Build ISON
        lines = [f'table.{index}']
        lines.append(' '.join(fields))

        for vec_id, vec in results.vectors.items():
            values = [self._format_value(vec_id)]

            if include_values:
                values.append(self._format_value(vec.values))

            meta = vec.metadata or {}
            for key in meta_keys:
                values.append(self._format_value(meta.get(key)))

            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_for_rag(self, index: str, query: str,
                       embedding_fn: Callable[[str], List[float]],
                       top_k: int = 5, namespace: str = None,
                       filter: Dict = None) -> str:
        """
        Export optimized RAG context from Pinecone.

        Args:
            index: Index name
            query: Text query
            embedding_fn: Function to convert text to embedding
            top_k: Number of results
            namespace: Optional namespace
            filter: Metadata filter

        Returns:
            ISON formatted context for LLM
        """
        # Generate query embedding
        query_vector = embedding_fn(query)

        idx = self.get_index(index)

        results = idx.query(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_metadata=True
        )

        # Build compact RAG context
        lines = ['table.context']
        lines.append('rank:int score:float source content')

        for i, match in enumerate(results.matches):
            rank = i + 1
            score = match.score
            meta = match.metadata or {}

            # Try common metadata fields for source/content
            source = meta.get('source') or meta.get('title') or meta.get('filename') or match.id
            content = meta.get('text') or meta.get('content') or meta.get('chunk') or ''

            lines.append(f'{rank} {score:.3f} {self._format_value(source)} {self._format_value(content)}')

        return '\n'.join(lines)

    def export_namespace_stats(self, index: str) -> str:
        """
        Export index namespace statistics as ISON.

        Args:
            index: Index name

        Returns:
            ISON formatted statistics
        """
        stats = self.get_index_stats(index)

        lines = ['meta.index_stats']
        lines.append('property value')
        lines.append(f'name "{index}"')
        lines.append(f'dimension {stats["dimension"]}')
        lines.append(f'total_vectors {stats["total_vector_count"]}')

        if stats['namespaces']:
            lines.append('')
            lines.append('table.namespaces')
            lines.append('name vector_count')
            for ns_name, ns_info in stats['namespaces'].items():
                count = ns_info.vector_count if hasattr(ns_info, 'vector_count') else ns_info.get('vector_count', 0)
                lines.append(f'{self._format_value(ns_name)} {count}')

        return '\n'.join(lines)

    def stream_query_batches(self, index: str, query_vectors: List[List[float]],
                             top_k: int = 10, namespace: str = None,
                             batch_size: int = 10) -> Iterator[str]:
        """
        Stream query results for multiple queries as ISONL.

        Args:
            index: Index name
            query_vectors: List of query embeddings
            top_k: Results per query
            namespace: Optional namespace
            batch_size: Queries per batch

        Yields:
            ISONL formatted lines
        """
        idx = self.get_index(index)

        for batch_start in range(0, len(query_vectors), batch_size):
            batch = query_vectors[batch_start:batch_start + batch_size]

            for q_idx, query_vec in enumerate(batch):
                results = idx.query(
                    vector=query_vec,
                    top_k=top_k,
                    namespace=namespace,
                    include_metadata=True
                )

                global_idx = batch_start + q_idx

                for match in results.matches:
                    meta = match.metadata or {}
                    source = meta.get('source', match.id)
                    content = meta.get('text', '')

                    yield f"table.results|query_id:int id score:float source content|{global_idx} {self._format_value(match.id)} {match.score:.4f} {self._format_value(source)} {self._format_value(content)}"


# Convenience functions
def pinecone_to_ison(index: str, query_vector: List[float] = None,
                     ids: List[str] = None, api_key: str = None,
                     top_k: int = 10) -> str:
    """
    Quick export from Pinecone to ISON.

    Args:
        index: Index name
        query_vector: Query embedding (for search)
        ids: Vector IDs (for fetch)
        api_key: Pinecone API key
        top_k: Number of results

    Returns:
        ISON formatted string
    """
    exporter = PineconeToISON(api_key=api_key)

    if query_vector:
        return exporter.export_query_results(index, query_vector, top_k)
    elif ids:
        return exporter.export_vectors(index, ids)
    else:
        return exporter.export_namespace_stats(index)


def pinecone_rag_context(index: str, query: str,
                         embedding_fn: Callable[[str], List[float]],
                         top_k: int = 5, api_key: str = None) -> str:
    """
    Get RAG context from Pinecone in ISON format.

    Args:
        index: Index name
        query: Text query
        embedding_fn: Text to embedding function
        top_k: Number of results
        api_key: Pinecone API key

    Returns:
        ISON formatted context
    """
    exporter = PineconeToISON(api_key=api_key)
    return exporter.export_for_rag(index, query, embedding_fn, top_k)
