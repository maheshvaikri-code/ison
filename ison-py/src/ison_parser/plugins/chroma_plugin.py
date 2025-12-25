#!/usr/bin/env python3
"""
ChromaDB to ISON Plugin
Export ChromaDB collections to ISON format for LLM workflows.

Requires: chromadb
    pip install chromadb

Usage:
    from ison_parser.plugins import ChromaToISON

    # Connect to ChromaDB
    exporter = ChromaToISON()  # Default persistent client
    exporter = ChromaToISON(client=my_chroma_client)

    # Export collection for RAG context
    ison_text = exporter.export_collection('documents')

    # Export search results
    ison_text = exporter.export_query_results(
        collection='documents',
        query_texts=['What is ISON?'],
        n_results=10
    )

    # Stream large collections as ISONL
    for line in exporter.stream_collection('documents'):
        process(line)
"""

from typing import List, Optional, Dict, Any, Iterator, Union
import json


class ChromaToISON:
    """Export ChromaDB collections to ISON format."""

    def __init__(self, client=None, path: str = None, host: str = None, port: int = None):
        """
        Initialize ChromaDB exporter.

        Args:
            client: Existing ChromaDB client
            path: Path for persistent client (default: ./chroma_db)
            host: Host for HTTP client
            port: Port for HTTP client
        """
        self._client = client
        self._path = path
        self._host = host
        self._port = port

    @property
    def client(self):
        """Get or create ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
            except ImportError:
                raise ImportError(
                    "chromadb is required. Install with: pip install chromadb"
                )

            if self._host:
                self._client = chromadb.HttpClient(host=self._host, port=self._port or 8000)
            elif self._path:
                self._client = chromadb.PersistentClient(path=self._path)
            else:
                self._client = chromadb.Client()

        return self._client

    def get_collections(self) -> List[str]:
        """Get list of all collection names."""
        collections = self.client.list_collections()
        return [c.name for c in collections]

    def get_collection_info(self, name: str) -> Dict[str, Any]:
        """Get collection metadata and count."""
        collection = self.client.get_collection(name)
        return {
            'name': name,
            'count': collection.count(),
            'metadata': collection.metadata or {}
        }

    def _format_value(self, value: Any) -> str:
        """Format a value for ISON output."""
        if value is None:
            return '~'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, list):
            # For embeddings, truncate for readability in ISON
            if len(value) > 10 and all(isinstance(v, (int, float)) for v in value):
                # Embedding vector - show dimensions
                return f'"[{len(value)}d embedding]"'
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

    def export_collection(self, name: str, include_embeddings: bool = False,
                          include_documents: bool = True,
                          limit: int = None, offset: int = 0,
                          where: Dict = None, where_document: Dict = None) -> str:
        """
        Export a ChromaDB collection to ISON format.

        Args:
            name: Collection name
            include_embeddings: Include embedding vectors (large!)
            include_documents: Include document text
            limit: Maximum records to export
            offset: Starting offset
            where: Metadata filter
            where_document: Document content filter

        Returns:
            ISON formatted string
        """
        collection = self.client.get_collection(name)

        # Build include list
        include = ['metadatas']
        if include_documents:
            include.append('documents')
        if include_embeddings:
            include.append('embeddings')

        # Query all or filtered
        kwargs = {'include': include}
        if where:
            kwargs['where'] = where
        if where_document:
            kwargs['where_document'] = where_document
        if limit:
            kwargs['limit'] = limit
            kwargs['offset'] = offset

        results = collection.get(**kwargs)

        # Build fields based on what we have
        fields = ['id']
        if include_documents and results.get('documents'):
            fields.append('document')
        if include_embeddings and results.get('embeddings'):
            fields.append('embedding')

        # Add metadata fields (union of all keys)
        meta_keys = set()
        if results.get('metadatas'):
            for meta in results['metadatas']:
                if meta:
                    meta_keys.update(meta.keys())
        meta_keys = sorted(meta_keys)
        fields.extend(meta_keys)

        # Build ISON output
        lines = [f"table.{name}"]
        lines.append(' '.join(fields))

        ids = results.get('ids', [])
        documents = results.get('documents', [])
        embeddings = results.get('embeddings', [])
        metadatas = results.get('metadatas', [])

        for i, doc_id in enumerate(ids):
            values = [self._format_value(doc_id)]

            if include_documents and documents:
                values.append(self._format_value(documents[i] if i < len(documents) else None))

            if include_embeddings and embeddings:
                values.append(self._format_value(embeddings[i] if i < len(embeddings) else None))

            # Add metadata values
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            for key in meta_keys:
                values.append(self._format_value(meta.get(key)))

            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_query_results(self, collection: str, query_texts: List[str] = None,
                             query_embeddings: List[List[float]] = None,
                             n_results: int = 10,
                             include_distances: bool = True,
                             include_documents: bool = True,
                             where: Dict = None) -> str:
        """
        Export query/search results to ISON format.

        Perfect for building RAG context!

        Args:
            collection: Collection name
            query_texts: Text queries (uses collection's embedding function)
            query_embeddings: Direct embedding queries
            n_results: Number of results per query
            include_distances: Include similarity scores
            include_documents: Include document text
            where: Metadata filter

        Returns:
            ISON formatted string for LLM context
        """
        coll = self.client.get_collection(collection)

        include = ['metadatas']
        if include_documents:
            include.append('documents')
        if include_distances:
            include.append('distances')

        kwargs = {
            'n_results': n_results,
            'include': include
        }
        if query_texts:
            kwargs['query_texts'] = query_texts
        elif query_embeddings:
            kwargs['query_embeddings'] = query_embeddings
        else:
            raise ValueError("Must provide query_texts or query_embeddings")

        if where:
            kwargs['where'] = where

        results = coll.query(**kwargs)

        # Build fields
        fields = ['id']
        if include_distances:
            fields.append('score:float')
        if include_documents:
            fields.append('document')

        # Collect metadata keys
        meta_keys = set()
        for metas in results.get('metadatas', []):
            if metas:
                for meta in metas:
                    if meta:
                        meta_keys.update(meta.keys())
        meta_keys = sorted(meta_keys)
        fields.extend(meta_keys)

        # Build ISON - one block per query
        blocks = []
        num_queries = len(query_texts or query_embeddings)

        for q_idx in range(num_queries):
            query_label = query_texts[q_idx][:30] if query_texts else f"query_{q_idx}"
            block_name = f"results_{q_idx}" if num_queries > 1 else "results"

            lines = [f"table.{block_name}"]
            lines.append(' '.join(fields))

            ids = results['ids'][q_idx] if results.get('ids') else []
            distances = results['distances'][q_idx] if results.get('distances') else []
            documents = results['documents'][q_idx] if results.get('documents') else []
            metadatas = results['metadatas'][q_idx] if results.get('metadatas') else []

            for i, doc_id in enumerate(ids):
                values = [self._format_value(doc_id)]

                if include_distances and distances:
                    # Convert distance to similarity score (1 - distance for L2)
                    score = 1 - distances[i] if i < len(distances) else 0
                    values.append(f"{score:.4f}")

                if include_documents and documents:
                    values.append(self._format_value(documents[i] if i < len(documents) else None))

                meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
                for key in meta_keys:
                    values.append(self._format_value(meta.get(key)))

                lines.append(' '.join(values))

            blocks.append('\n'.join(lines))

        # Add query info as meta block
        if query_texts:
            meta_lines = ['meta.query']
            meta_lines.append('index text')
            for i, q in enumerate(query_texts):
                meta_lines.append(f'{i} {self._format_value(q)}')
            blocks.insert(0, '\n'.join(meta_lines))

        return '\n\n'.join(blocks)

    def export_collections(self, names: List[str] = None,
                           include_embeddings: bool = False) -> str:
        """Export multiple collections."""
        if names is None:
            names = self.get_collections()

        blocks = []
        for name in names:
            blocks.append(self.export_collection(name, include_embeddings=include_embeddings))

        return '\n\n'.join(blocks)

    def stream_collection(self, name: str, batch_size: int = 100,
                          include_documents: bool = True) -> Iterator[str]:
        """
        Stream a collection as ISONL format.

        Args:
            name: Collection name
            batch_size: Records per batch
            include_documents: Include document text

        Yields:
            ISONL formatted lines
        """
        collection = self.client.get_collection(name)
        total = collection.count()

        # Determine fields from first batch
        include = ['metadatas']
        if include_documents:
            include.append('documents')

        first_batch = collection.get(limit=min(batch_size, total), include=include)

        # Collect all metadata keys
        meta_keys = set()
        if first_batch.get('metadatas'):
            for meta in first_batch['metadatas']:
                if meta:
                    meta_keys.update(meta.keys())
        meta_keys = sorted(meta_keys)

        fields = ['id']
        if include_documents:
            fields.append('document')
        fields.extend(meta_keys)
        fields_str = ' '.join(fields)

        # Stream all batches
        offset = 0
        while offset < total:
            results = collection.get(
                limit=batch_size,
                offset=offset,
                include=include
            )

            ids = results.get('ids', [])
            documents = results.get('documents', [])
            metadatas = results.get('metadatas', [])

            for i, doc_id in enumerate(ids):
                values = [self._format_value(doc_id)]

                if include_documents and documents:
                    values.append(self._format_value(documents[i] if i < len(documents) else None))

                meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
                for key in meta_keys:
                    values.append(self._format_value(meta.get(key)))

                yield f"table.{name}|{fields_str}|{' '.join(values)}"

            offset += batch_size

    def export_for_rag(self, collection: str, query: str,
                       n_results: int = 5, context_template: str = None) -> str:
        """
        Export optimized RAG context from ChromaDB.

        This is the recommended method for building LLM context from vector search.

        Args:
            collection: Collection name
            query: Search query
            n_results: Number of results to include
            context_template: Optional template (default provides clean format)

        Returns:
            ISON formatted context ready for LLM prompt
        """
        coll = self.client.get_collection(collection)

        results = coll.query(
            query_texts=[query],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )

        # Build compact context block
        lines = ['table.context']
        lines.append('rank:int score:float source content')

        ids = results['ids'][0]
        documents = results['documents'][0]
        distances = results['distances'][0]
        metadatas = results['metadatas'][0]

        for i, doc_id in enumerate(ids):
            rank = i + 1
            score = 1 - distances[i]  # Convert distance to similarity
            source = metadatas[i].get('source', doc_id) if metadatas[i] else doc_id
            content = documents[i] if documents else ''

            lines.append(f'{rank} {score:.3f} {self._format_value(source)} {self._format_value(content)}')

        return '\n'.join(lines)


# Convenience functions
def chroma_to_ison(collection: str, path: str = None,
                   query: str = None, n_results: int = 10) -> str:
    """
    Quick export from ChromaDB to ISON.

    Args:
        collection: Collection name
        path: ChromaDB persistent path
        query: Optional query (exports search results)
        n_results: Number of results if querying

    Returns:
        ISON formatted string
    """
    exporter = ChromaToISON(path=path)
    if query:
        return exporter.export_for_rag(collection, query, n_results)
    else:
        return exporter.export_collection(collection)


def chroma_rag_context(collection: str, query: str,
                       n_results: int = 5, path: str = None) -> str:
    """
    Get RAG context from ChromaDB in ISON format.

    Args:
        collection: Collection name
        query: Search query
        n_results: Number of results
        path: ChromaDB path

    Returns:
        ISON formatted context for LLM
    """
    exporter = ChromaToISON(path=path)
    return exporter.export_for_rag(collection, query, n_results)
