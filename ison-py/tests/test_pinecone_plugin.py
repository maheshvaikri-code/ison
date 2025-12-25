#!/usr/bin/env python3
"""
Tests for Pinecone to ISON Plugin.

Uses mocking since we can't require Pinecone for tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestPineconeToISON:
    """Test PineconeToISON class with mocked Pinecone."""

    @pytest.fixture
    def mock_pinecone(self):
        """Create a mock pinecone module."""
        mock_module = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()

        mock_module.Pinecone.return_value = mock_pc
        mock_pc.Index.return_value = mock_index

        return mock_module, mock_pc, mock_index

    @pytest.fixture
    def exporter(self, mock_pinecone):
        """Create an exporter with mocked Pinecone."""
        mock_module, mock_pc, mock_index = mock_pinecone

        with patch.dict('sys.modules', {'pinecone': mock_module}):
            from ison_parser.plugins.pinecone_plugin import PineconeToISON

            exporter = PineconeToISON(api_key='test-api-key')
            exporter._pc = mock_pc
            exporter._indexes = {'test-index': mock_index}

            yield exporter, mock_pc, mock_index

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict('sys.modules', {'pinecone': MagicMock()}):
            from ison_parser.plugins.pinecone_plugin import PineconeToISON

            exporter = PineconeToISON(api_key='my-api-key')
            assert exporter._api_key == 'my-api-key'

    def test_init_with_environment(self):
        """Test initialization with environment (legacy)."""
        with patch.dict('sys.modules', {'pinecone': MagicMock()}):
            from ison_parser.plugins.pinecone_plugin import PineconeToISON

            exporter = PineconeToISON(api_key='key', environment='us-west1-gcp')
            assert exporter._environment == 'us-west1-gcp'

    def test_list_indexes(self, exporter):
        """Test listing indexes."""
        exp, mock_pc, _ = exporter

        mock_idx1 = MagicMock()
        mock_idx1.name = 'index1'
        mock_idx2 = MagicMock()
        mock_idx2.name = 'index2'

        mock_pc.list_indexes.return_value = [mock_idx1, mock_idx2]

        indexes = exp.list_indexes()

        assert 'index1' in indexes
        assert 'index2' in indexes

    def test_get_index_stats(self, exporter):
        """Test getting index statistics."""
        exp, _, mock_index = exporter

        mock_stats = MagicMock()
        mock_stats.total_vector_count = 1000
        mock_stats.dimension = 384
        mock_stats.namespaces = {'default': MagicMock(vector_count=1000)}

        mock_index.describe_index_stats.return_value = mock_stats

        stats = exp.get_index_stats('test-index')

        assert stats['total_vector_count'] == 1000
        assert stats['dimension'] == 384

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
        assert exp._format_value(3.14159) == '3.1416'  # Rounded to 4 decimals

    def test_format_value_embedding(self, exporter):
        """Test formatting large embedding vectors."""
        exp, _, _ = exporter
        embedding = [0.1] * 384
        result = exp._format_value(embedding)
        assert '384' in result
        assert 'd]' in result  # Dimension marker

    def test_format_value_string_with_spaces(self, exporter):
        """Test formatting strings with spaces."""
        exp, _, _ = exporter
        assert exp._format_value('hello world') == '"hello world"'

    def test_export_query_results(self, exporter):
        """Test exporting query results."""
        exp, _, mock_index = exporter

        mock_match1 = MagicMock()
        mock_match1.id = 'vec1'
        mock_match1.score = 0.95
        mock_match1.metadata = {'title': 'Document 1', 'source': 'file1.txt'}
        mock_match1.values = None

        mock_match2 = MagicMock()
        mock_match2.id = 'vec2'
        mock_match2.score = 0.85
        mock_match2.metadata = {'title': 'Document 2', 'source': 'file2.txt'}
        mock_match2.values = None

        mock_result = MagicMock()
        mock_result.matches = [mock_match1, mock_match2]

        mock_index.query.return_value = mock_result

        ison = exp.export_query_results(
            index='test-index',
            query_vector=[0.1] * 10,
            top_k=2
        )

        assert 'table.results' in ison
        assert 'vec1' in ison
        assert 'vec2' in ison
        assert '0.95' in ison

    def test_export_query_with_namespace(self, exporter):
        """Test query export with namespace."""
        exp, _, mock_index = exporter

        mock_result = MagicMock()
        mock_result.matches = []

        mock_index.query.return_value = mock_result

        exp.export_query_results(
            index='test-index',
            query_vector=[0.1] * 10,
            namespace='production'
        )

        # Verify namespace was passed
        mock_index.query.assert_called_with(
            vector=[0.1] * 10,
            top_k=10,
            namespace='production',
            filter=None,
            include_metadata=True,
            include_values=False
        )

    def test_export_query_with_filter(self, exporter):
        """Test query export with metadata filter."""
        exp, _, mock_index = exporter

        mock_result = MagicMock()
        mock_result.matches = []

        mock_index.query.return_value = mock_result

        exp.export_query_results(
            index='test-index',
            query_vector=[0.1] * 10,
            filter={'category': {'$eq': 'tech'}}
        )

        # Verify filter was passed
        call_args = mock_index.query.call_args
        assert call_args.kwargs['filter'] == {'category': {'$eq': 'tech'}}

    def test_export_vectors(self, exporter):
        """Test exporting specific vectors by ID."""
        exp, _, mock_index = exporter

        mock_vec1 = MagicMock()
        mock_vec1.metadata = {'title': 'Doc 1'}
        mock_vec1.values = None

        mock_vec2 = MagicMock()
        mock_vec2.metadata = {'title': 'Doc 2'}
        mock_vec2.values = None

        mock_result = MagicMock()
        mock_result.vectors = {'id1': mock_vec1, 'id2': mock_vec2}

        mock_index.fetch.return_value = mock_result

        ison = exp.export_vectors(
            index='test-index',
            ids=['id1', 'id2']
        )

        assert 'table.test-index' in ison
        assert 'id1' in ison or 'id2' in ison

    def test_export_vectors_empty(self, exporter):
        """Test exporting when no vectors found."""
        exp, _, mock_index = exporter

        mock_result = MagicMock()
        mock_result.vectors = {}

        mock_index.fetch.return_value = mock_result

        ison = exp.export_vectors(
            index='test-index',
            ids=['nonexistent']
        )

        assert 'No vectors found' in ison

    def test_export_for_rag(self, exporter):
        """Test RAG context export."""
        exp, _, mock_index = exporter

        def mock_embedding_fn(text):
            return [0.1] * 10

        mock_match = MagicMock()
        mock_match.id = 'doc1'
        mock_match.score = 0.92
        mock_match.metadata = {
            'source': 'knowledge.md',
            'text': 'ISON is token-efficient'
        }

        mock_result = MagicMock()
        mock_result.matches = [mock_match]

        mock_index.query.return_value = mock_result

        ison = exp.export_for_rag(
            index='test-index',
            query='What is ISON?',
            embedding_fn=mock_embedding_fn,
            top_k=1
        )

        assert 'table.context' in ison
        assert 'rank:int' in ison
        assert 'score:float' in ison
        assert 'source' in ison
        assert 'content' in ison

    def test_export_namespace_stats(self, exporter):
        """Test exporting index statistics."""
        exp, _, mock_index = exporter

        mock_ns_info = MagicMock()
        mock_ns_info.vector_count = 500

        mock_stats = MagicMock()
        mock_stats.total_vector_count = 1000
        mock_stats.dimension = 384
        mock_stats.namespaces = {'production': mock_ns_info}

        mock_index.describe_index_stats.return_value = mock_stats

        ison = exp.export_namespace_stats('test-index')

        assert 'meta.index_stats' in ison
        assert '384' in ison  # dimension
        assert '1000' in ison  # total vectors

    def test_stream_query_batches(self, exporter):
        """Test streaming batch query results."""
        exp, _, mock_index = exporter

        mock_match = MagicMock()
        mock_match.id = 'doc1'
        mock_match.score = 0.9
        mock_match.metadata = {'source': 'test', 'text': 'content'}

        mock_result = MagicMock()
        mock_result.matches = [mock_match]

        mock_index.query.return_value = mock_result

        query_vectors = [[0.1] * 10, [0.2] * 10]
        lines = list(exp.stream_query_batches(
            index='test-index',
            query_vectors=query_vectors,
            top_k=1
        ))

        assert len(lines) >= 2
        for line in lines:
            assert 'table.results|' in line


class TestPineconeConvenienceFunctions:
    """Test convenience functions."""

    def test_pinecone_to_ison_with_query(self):
        """Test pinecone_to_ison with query vector."""
        mock_module = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()

        mock_module.Pinecone.return_value = mock_pc
        mock_pc.Index.return_value = mock_index

        mock_match = MagicMock()
        mock_match.id = 'vec1'
        mock_match.score = 0.9
        mock_match.metadata = {}
        mock_match.values = None

        mock_result = MagicMock()
        mock_result.matches = [mock_match]

        mock_index.query.return_value = mock_result

        with patch.dict('sys.modules', {'pinecone': mock_module}):
            from ison_parser.plugins.pinecone_plugin import pinecone_to_ison

            ison = pinecone_to_ison(
                index='test-index',
                query_vector=[0.1] * 10,
                api_key='key'
            )

            assert 'table.results' in ison

    def test_pinecone_to_ison_with_ids(self):
        """Test pinecone_to_ison with vector IDs."""
        mock_module = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()

        mock_module.Pinecone.return_value = mock_pc
        mock_pc.Index.return_value = mock_index

        mock_vec = MagicMock()
        mock_vec.metadata = {'title': 'Test'}
        mock_vec.values = None

        mock_result = MagicMock()
        mock_result.vectors = {'id1': mock_vec}

        mock_index.fetch.return_value = mock_result

        with patch.dict('sys.modules', {'pinecone': mock_module}):
            from ison_parser.plugins.pinecone_plugin import pinecone_to_ison

            ison = pinecone_to_ison(
                index='test-index',
                ids=['id1'],
                api_key='key'
            )

            assert 'id1' in ison or 'table.' in ison

    def test_pinecone_rag_context(self):
        """Test pinecone_rag_context convenience function."""
        mock_module = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()

        mock_module.Pinecone.return_value = mock_pc
        mock_pc.Index.return_value = mock_index

        mock_match = MagicMock()
        mock_match.id = 'doc1'
        mock_match.score = 0.9
        mock_match.metadata = {'source': 'test', 'text': 'Answer'}

        mock_result = MagicMock()
        mock_result.matches = [mock_match]

        mock_index.query.return_value = mock_result

        def mock_embed(text):
            return [0.1] * 10

        with patch.dict('sys.modules', {'pinecone': mock_module}):
            from ison_parser.plugins.pinecone_plugin import pinecone_rag_context

            context = pinecone_rag_context(
                index='knowledge',
                query='What is ISON?',
                embedding_fn=mock_embed,
                api_key='key'
            )

            assert 'table.context' in context


class TestPineconeEdgeCases:
    """Test edge cases and error handling."""

    def test_import_error_without_pinecone(self):
        """Test that ImportError is raised when pinecone is not installed."""
        with patch.dict('sys.modules', {'pinecone': None}):
            from ison_parser.plugins.pinecone_plugin import PineconeToISON

            exp = PineconeToISON(api_key='key')

            with pytest.raises(ImportError) as excinfo:
                _ = exp.pc

            assert 'pinecone' in str(excinfo.value)

    def test_empty_query_results(self):
        """Test handling of empty query results."""
        mock_module = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()

        mock_module.Pinecone.return_value = mock_pc
        mock_pc.Index.return_value = mock_index

        mock_result = MagicMock()
        mock_result.matches = []

        mock_index.query.return_value = mock_result

        with patch.dict('sys.modules', {'pinecone': mock_module}):
            from ison_parser.plugins.pinecone_plugin import PineconeToISON

            exp = PineconeToISON(api_key='key')
            exp._pc = mock_pc
            exp._indexes = {'test': mock_index}

            ison = exp.export_query_results(
                index='test',
                query_vector=[0.1] * 10
            )

            # Should still have header
            assert 'table.results' in ison

    def test_metadata_with_various_types(self):
        """Test handling of various metadata types."""
        mock_module = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()

        mock_module.Pinecone.return_value = mock_pc
        mock_pc.Index.return_value = mock_index

        mock_match = MagicMock()
        mock_match.id = 'vec1'
        mock_match.score = 0.9
        mock_match.metadata = {
            'string': 'hello',
            'number': 42,
            'float': 3.14,
            'bool': True,
            'none': None
        }
        mock_match.values = None

        mock_result = MagicMock()
        mock_result.matches = [mock_match]

        mock_index.query.return_value = mock_result

        with patch.dict('sys.modules', {'pinecone': mock_module}):
            from ison_parser.plugins.pinecone_plugin import PineconeToISON

            exp = PineconeToISON(api_key='key')
            exp._pc = mock_pc
            exp._indexes = {'test': mock_index}

            ison = exp.export_query_results(
                index='test',
                query_vector=[0.1] * 10
            )

            assert 'hello' in ison
            assert '42' in ison
            assert 'true' in ison


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
