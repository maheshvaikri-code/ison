#!/usr/bin/env python3
"""
Tests for ChromaDB to ISON Plugin.

Uses mocking since we can't require ChromaDB for tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestChromaToISON:
    """Test ChromaToISON class with mocked ChromaDB."""

    @pytest.fixture
    def mock_chromadb(self):
        """Create a mock chromadb module."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()

        mock_module.Client.return_value = mock_client
        mock_module.PersistentClient.return_value = mock_client
        mock_module.HttpClient.return_value = mock_client

        mock_client.get_collection.return_value = mock_collection
        mock_client.list_collections.return_value = []

        return mock_module, mock_client, mock_collection

    @pytest.fixture
    def exporter(self, mock_chromadb):
        """Create an exporter with mocked ChromaDB."""
        mock_module, mock_client, mock_collection = mock_chromadb

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exporter = ChromaToISON()
            exporter._client = mock_client

            yield exporter, mock_client, mock_collection

    def test_init_default(self):
        """Test default initialization."""
        with patch.dict('sys.modules', {'chromadb': MagicMock()}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exporter = ChromaToISON()
            assert exporter._client is None
            assert exporter._path is None

    def test_init_with_path(self):
        """Test initialization with persistent path."""
        with patch.dict('sys.modules', {'chromadb': MagicMock()}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exporter = ChromaToISON(path='./chroma_data')
            assert exporter._path == './chroma_data'

    def test_init_with_host(self):
        """Test initialization with HTTP client."""
        with patch.dict('sys.modules', {'chromadb': MagicMock()}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exporter = ChromaToISON(host='localhost', port=8000)
            assert exporter._host == 'localhost'
            assert exporter._port == 8000

    def test_init_with_existing_client(self, mock_chromadb):
        """Test initialization with existing client."""
        mock_module, mock_client, _ = mock_chromadb

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exporter = ChromaToISON(client=mock_client)
            assert exporter._client == mock_client

    def test_get_collections(self, exporter):
        """Test getting list of collections."""
        exp, mock_client, _ = exporter

        mock_coll1 = MagicMock()
        mock_coll1.name = 'documents'
        mock_coll2 = MagicMock()
        mock_coll2.name = 'embeddings'

        mock_client.list_collections.return_value = [mock_coll1, mock_coll2]

        collections = exp.get_collections()

        assert 'documents' in collections
        assert 'embeddings' in collections

    def test_get_collection_info(self, exporter):
        """Test getting collection information."""
        exp, mock_client, mock_collection = exporter

        mock_collection.count.return_value = 100
        mock_collection.metadata = {'description': 'Test collection'}

        info = exp.get_collection_info('test')

        assert info['name'] == 'test'
        assert info['count'] == 100
        assert info['metadata'] == {'description': 'Test collection'}

    def test_format_value_null(self, exporter):
        """Test formatting NULL values."""
        exp, _, _ = exporter
        assert exp._format_value(None) == '~'

    def test_format_value_boolean(self, exporter):
        """Test formatting boolean values."""
        exp, _, _ = exporter
        assert exp._format_value(True) == 'true'
        assert exp._format_value(False) == 'false'

    def test_format_value_numbers(self, exporter):
        """Test formatting numeric values."""
        exp, _, _ = exporter
        assert exp._format_value(42) == '42'
        assert exp._format_value(3.14) == '3.14'

    def test_format_value_embedding(self, exporter):
        """Test formatting large embedding vectors."""
        exp, _, _ = exporter
        embedding = [0.1] * 384  # Typical embedding size
        result = exp._format_value(embedding)
        assert '384' in result  # Should show dimension
        assert 'embedding' in result

    def test_format_value_short_list(self, exporter):
        """Test formatting short lists (not embeddings)."""
        exp, _, _ = exporter
        result = exp._format_value([1, 2, 3])
        assert result == '[1,2,3]'

    def test_format_value_string_with_spaces(self, exporter):
        """Test formatting strings with spaces."""
        exp, _, _ = exporter
        assert exp._format_value('hello world') == '"hello world"'

    def test_format_value_string_with_newlines(self, exporter):
        """Test formatting strings with newlines."""
        exp, _, _ = exporter
        result = exp._format_value('line1\nline2')
        assert '\\n' in result

    def test_export_collection_basic(self, exporter):
        """Test basic collection export."""
        exp, mock_client, mock_collection = exporter

        mock_collection.get.return_value = {
            'ids': ['doc1', 'doc2'],
            'documents': ['Hello world', 'Test document'],
            'metadatas': [{'source': 'test.txt'}, {'source': 'other.txt'}],
            'embeddings': None
        }

        ison = exp.export_collection('test')

        assert 'table.test' in ison
        assert 'doc1' in ison
        assert 'doc2' in ison
        assert '"Hello world"' in ison

    def test_export_collection_with_embeddings(self, exporter):
        """Test collection export with embeddings."""
        exp, _, mock_collection = exporter

        mock_collection.get.return_value = {
            'ids': ['doc1'],
            'documents': ['Hello'],
            'metadatas': [{}],
            'embeddings': [[0.1] * 10]
        }

        ison = exp.export_collection('test', include_embeddings=True)

        assert 'embedding' in ison

    def test_export_collection_with_filter(self, exporter):
        """Test collection export with metadata filter."""
        exp, _, mock_collection = exporter

        mock_collection.get.return_value = {
            'ids': ['doc1'],
            'documents': ['Filtered doc'],
            'metadatas': [{'type': 'important'}],
            'embeddings': None
        }

        ison = exp.export_collection('test', where={'type': 'important'})

        # Verify filter was passed
        mock_collection.get.assert_called()

    def test_export_query_results(self, exporter):
        """Test exporting query results."""
        exp, _, mock_collection = exporter

        mock_collection.query.return_value = {
            'ids': [['doc1', 'doc2']],
            'documents': [['Result 1', 'Result 2']],
            'metadatas': [[{'score': 0.9}, {'score': 0.8}]],
            'distances': [[0.1, 0.2]]
        }

        ison = exp.export_query_results(
            collection='test',
            query_texts=['search query'],
            n_results=2
        )

        assert 'table.results' in ison
        assert 'doc1' in ison
        assert 'score' in ison

    def test_export_query_results_multiple_queries(self, exporter):
        """Test exporting multiple query results."""
        exp, _, mock_collection = exporter

        mock_collection.query.return_value = {
            'ids': [['doc1'], ['doc2']],
            'documents': [['Result 1'], ['Result 2']],
            'metadatas': [[{}], [{}]],
            'distances': [[0.1], [0.2]]
        }

        ison = exp.export_query_results(
            collection='test',
            query_texts=['query1', 'query2'],
            n_results=1
        )

        assert 'results_0' in ison or 'results_1' in ison

    def test_export_for_rag(self, exporter):
        """Test RAG context export."""
        exp, _, mock_collection = exporter

        mock_collection.query.return_value = {
            'ids': [['doc1', 'doc2']],
            'documents': [['ISON is efficient', 'Use ISON for LLMs']],
            'metadatas': [[{'source': 'docs.md'}, {'source': 'guide.md'}]],
            'distances': [[0.1, 0.2]]
        }

        ison = exp.export_for_rag(
            collection='knowledge',
            query='What is ISON?',
            n_results=2
        )

        assert 'table.context' in ison
        assert 'rank:int' in ison
        assert 'score:float' in ison
        assert 'source' in ison
        assert 'content' in ison

    def test_stream_collection(self, exporter):
        """Test streaming collection as ISONL."""
        exp, _, mock_collection = exporter

        # First call for metadata keys
        mock_collection.get.side_effect = [
            {
                'ids': ['doc1', 'doc2'],
                'documents': ['Hello', 'World'],
                'metadatas': [{'source': 'a'}, {'source': 'b'}]
            },
            {
                'ids': ['doc1'],
                'documents': ['Hello'],
                'metadatas': [{'source': 'a'}]
            },
            {
                'ids': [],
                'documents': [],
                'metadatas': []
            }
        ]

        mock_collection.count.return_value = 2

        lines = list(exp.stream_collection('test', batch_size=1))

        # Should have ISONL format
        for line in lines:
            assert 'table.test|' in line
            assert '|' in line

    def test_export_multiple_collections(self, exporter):
        """Test exporting multiple collections."""
        exp, mock_client, mock_collection = exporter

        mock_collection.get.return_value = {
            'ids': ['doc1'],
            'documents': ['Test'],
            'metadatas': [{}],
            'embeddings': None
        }

        ison = exp.export_collections(['coll1', 'coll2'])

        # Should have multiple table blocks
        assert ison.count('table.') >= 2


class TestChromaConvenienceFunctions:
    """Test convenience functions."""

    def test_chroma_to_ison(self):
        """Test chroma_to_ison convenience function."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()

        mock_module.PersistentClient.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection

        mock_collection.get.return_value = {
            'ids': ['doc1'],
            'documents': ['Test'],
            'metadatas': [{}],
            'embeddings': None
        }

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import chroma_to_ison

            ison = chroma_to_ison('test_collection', path='./data')

            assert 'table.test_collection' in ison

    def test_chroma_rag_context(self):
        """Test chroma_rag_context convenience function."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()

        mock_module.PersistentClient.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection

        mock_collection.query.return_value = {
            'ids': [['doc1']],
            'documents': [['Answer']],
            'metadatas': [[{'source': 'test'}]],
            'distances': [[0.1]]
        }

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import chroma_rag_context

            context = chroma_rag_context('knowledge', 'What is ISON?', n_results=1)

            assert 'table.context' in context


class TestChromaEdgeCases:
    """Test edge cases and error handling."""

    def test_import_error_without_chromadb(self):
        """Test that ImportError is raised when chromadb is not installed."""
        with patch.dict('sys.modules', {'chromadb': None}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exp = ChromaToISON()

            with pytest.raises(ImportError) as excinfo:
                _ = exp.client

            assert 'chromadb' in str(excinfo.value)

    def test_empty_collection(self):
        """Test exporting an empty collection."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()

        mock_module.Client.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection

        mock_collection.get.return_value = {
            'ids': [],
            'documents': [],
            'metadatas': [],
            'embeddings': None
        }

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exp = ChromaToISON()
            exp._client = mock_client

            ison = exp.export_collection('empty')

            lines = ison.strip().split('\n')
            assert 'table.empty' in lines[0]

    def test_collection_with_null_metadata(self):
        """Test collection with null metadata values."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()

        mock_module.Client.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection

        mock_collection.get.return_value = {
            'ids': ['doc1', 'doc2'],
            'documents': ['Hello', 'World'],
            'metadatas': [None, {'source': 'test'}],  # First has null metadata
            'embeddings': None
        }

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exp = ChromaToISON()
            exp._client = mock_client

            # Should not crash
            ison = exp.export_collection('test')
            assert 'doc1' in ison

    def test_distance_to_similarity_conversion(self):
        """Test that distance is converted to similarity score."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()

        mock_module.Client.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection

        # L2 distance of 0.1 should become similarity of 0.9
        mock_collection.query.return_value = {
            'ids': [['doc1']],
            'documents': [['Test']],
            'metadatas': [[{}]],
            'distances': [[0.1]]
        }

        with patch.dict('sys.modules', {'chromadb': mock_module}):
            from ison_parser.plugins.chroma_plugin import ChromaToISON

            exp = ChromaToISON()
            exp._client = mock_client

            ison = exp.export_for_rag('test', 'query', n_results=1)

            # Score should be 1 - 0.1 = 0.9
            assert '0.9' in ison


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
