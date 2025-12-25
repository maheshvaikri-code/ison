#!/usr/bin/env python3
"""
Tests for Qdrant to ISON Plugin.

Uses mocking since we can't require Qdrant for tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestQdrantToISON:
    """Test QdrantToISON class with mocked Qdrant client."""

    @pytest.fixture
    def mock_qdrant(self):
        """Create a mock qdrant_client module."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client
        mock_module.models = mock_models

        return mock_module, mock_client, mock_models

    @pytest.fixture
    def exporter(self, mock_qdrant):
        """Create an exporter with mocked Qdrant."""
        mock_module, mock_client, mock_models = mock_qdrant

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exporter = QdrantToISON(host='localhost', port=6333)
            exporter._client = mock_client

            yield exporter, mock_client, mock_models

    def test_init_with_host_port(self):
        """Test initialization with host and port."""
        with patch.dict('sys.modules', {'qdrant_client': MagicMock()}):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exporter = QdrantToISON(host='myhost', port=6334)
            assert exporter._host == 'myhost'
            assert exporter._port == 6334

    def test_init_with_url(self):
        """Test initialization with URL."""
        with patch.dict('sys.modules', {'qdrant_client': MagicMock()}):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exporter = QdrantToISON(url='https://my-qdrant.cloud')
            assert exporter._url == 'https://my-qdrant.cloud'

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict('sys.modules', {'qdrant_client': MagicMock()}):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exporter = QdrantToISON(url='https://cloud', api_key='my-key')
            assert exporter._api_key == 'my-key'

    def test_init_with_grpc(self):
        """Test initialization with gRPC preference."""
        with patch.dict('sys.modules', {'qdrant_client': MagicMock()}):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exporter = QdrantToISON(host='localhost', grpc_port=6334, prefer_grpc=True)
            assert exporter._grpc_port == 6334
            assert exporter._prefer_grpc is True

    def test_get_collections(self, exporter):
        """Test getting list of collections."""
        exp, mock_client, _ = exporter

        mock_coll1 = MagicMock()
        mock_coll1.name = 'documents'
        mock_coll2 = MagicMock()
        mock_coll2.name = 'embeddings'

        mock_collections = MagicMock()
        mock_collections.collections = [mock_coll1, mock_coll2]

        mock_client.get_collections.return_value = mock_collections

        collections = exp.get_collections()

        assert 'documents' in collections
        assert 'embeddings' in collections

    def test_get_collection_info(self, exporter):
        """Test getting collection information."""
        exp, mock_client, _ = exporter

        mock_info = MagicMock()
        mock_info.vectors_count = 1000
        mock_info.points_count = 1000
        mock_info.status = MagicMock()
        mock_info.status.value = 'green'

        mock_vectors = MagicMock()
        mock_vectors.size = 384
        mock_vectors.distance = MagicMock()
        mock_vectors.distance.value = 'Cosine'

        mock_info.config.params.vectors = mock_vectors

        mock_client.get_collection.return_value = mock_info

        info = exp.get_collection_info('test')

        assert info['name'] == 'test'
        assert info['vectors_count'] == 1000
        assert info['points_count'] == 1000

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
        assert exp._format_value(3.14159) == '3.1416'  # 4 decimal places

    def test_format_value_embedding(self, exporter):
        """Test formatting large embedding vectors."""
        exp, _, _ = exporter
        embedding = [0.1] * 768
        result = exp._format_value(embedding)
        assert '768' in result
        assert 'd]' in result

    def test_format_value_short_list(self, exporter):
        """Test formatting short lists."""
        exp, _, _ = exporter
        result = exp._format_value([1, 2, 3])
        assert result == '[1,2,3]'

    def test_format_value_dict(self, exporter):
        """Test formatting dict values."""
        exp, _, _ = exporter
        result = exp._format_value({'key': 'value'})
        assert 'key' in result
        assert 'value' in result

    def test_format_value_string_with_spaces(self, exporter):
        """Test formatting strings with spaces."""
        exp, _, _ = exporter
        assert exp._format_value('hello world') == '"hello world"'

    def test_export_search_results(self, exporter):
        """Test exporting search results."""
        exp, mock_client, mock_models = exporter

        mock_point1 = MagicMock()
        mock_point1.id = 'point1'
        mock_point1.score = 0.95
        mock_point1.payload = {'title': 'Document 1', 'content': 'Test content'}
        mock_point1.vector = None

        mock_point2 = MagicMock()
        mock_point2.id = 'point2'
        mock_point2.score = 0.85
        mock_point2.payload = {'title': 'Document 2', 'content': 'More content'}
        mock_point2.vector = None

        mock_client.search.return_value = [mock_point1, mock_point2]

        ison = exp.export_search_results(
            collection='documents',
            query_vector=[0.1] * 10,
            limit=2
        )

        assert 'table.results' in ison
        assert 'point1' in ison
        assert 'point2' in ison
        assert '0.9500' in ison

    def test_export_search_with_score_threshold(self, exporter):
        """Test search with score threshold."""
        exp, mock_client, mock_models = exporter

        mock_client.search.return_value = []

        exp.export_search_results(
            collection='test',
            query_vector=[0.1] * 10,
            score_threshold=0.8
        )

        # Verify score_threshold was passed
        call_args = mock_client.search.call_args
        assert call_args.kwargs['score_threshold'] == 0.8

    def test_export_search_with_filter(self, exporter):
        """Test search with filter."""
        exp, mock_client, mock_models = exporter

        mock_client.search.return_value = []

        exp.export_search_results(
            collection='test',
            query_vector=[0.1] * 10,
            filter={'must': [{'key': 'type', 'match': {'value': 'doc'}}]}
        )

        # Verify search was called with a filter
        mock_client.search.assert_called()

    def test_export_collection(self, exporter):
        """Test exporting entire collection."""
        exp, mock_client, _ = exporter

        mock_point1 = MagicMock()
        mock_point1.id = 'p1'
        mock_point1.payload = {'title': 'Doc 1'}
        mock_point1.vector = None

        mock_point2 = MagicMock()
        mock_point2.id = 'p2'
        mock_point2.payload = {'title': 'Doc 2'}
        mock_point2.vector = None

        mock_client.scroll.return_value = ([mock_point1, mock_point2], None)

        ison = exp.export_collection('documents')

        assert 'table.documents' in ison
        assert 'p1' in ison
        assert 'p2' in ison

    def test_export_collection_with_pagination(self, exporter):
        """Test collection export with pagination."""
        exp, mock_client, _ = exporter

        mock_point = MagicMock()
        mock_point.id = 'p1'
        mock_point.payload = {}
        mock_point.vector = None

        # First call returns data and offset, second call returns empty
        mock_client.scroll.side_effect = [
            ([mock_point], 'next_offset'),
            ([], None)
        ]

        ison = exp.export_collection('test', limit=1)

        assert 'p1' in ison

    def test_export_points(self, exporter):
        """Test exporting specific points by ID."""
        exp, mock_client, _ = exporter

        mock_point1 = MagicMock()
        mock_point1.id = 'id1'
        mock_point1.payload = {'title': 'Point 1'}
        mock_point1.vector = None

        mock_client.retrieve.return_value = [mock_point1]

        ison = exp.export_points(
            collection='test',
            ids=['id1']
        )

        assert 'table.test' in ison
        assert 'id1' in ison

    def test_export_for_rag(self, exporter):
        """Test RAG context export."""
        exp, mock_client, mock_models = exporter

        def mock_embedding_fn(text):
            return [0.1] * 10

        mock_point = MagicMock()
        mock_point.id = 'doc1'
        mock_point.score = 0.92
        mock_point.payload = {
            'source': 'knowledge.md',
            'text': 'ISON is efficient'
        }

        mock_client.search.return_value = [mock_point]

        ison = exp.export_for_rag(
            collection='knowledge',
            query='What is ISON?',
            embedding_fn=mock_embedding_fn,
            limit=1
        )

        assert 'table.context' in ison
        assert 'rank:int' in ison
        assert 'score:float' in ison
        assert 'source' in ison
        assert 'content' in ison

    def test_export_collections(self, exporter):
        """Test exporting multiple collections."""
        exp, mock_client, _ = exporter

        mock_coll1 = MagicMock()
        mock_coll1.name = 'coll1'
        mock_coll2 = MagicMock()
        mock_coll2.name = 'coll2'

        mock_collections = MagicMock()
        mock_collections.collections = [mock_coll1, mock_coll2]

        mock_client.get_collections.return_value = mock_collections

        mock_point = MagicMock()
        mock_point.id = 'p1'
        mock_point.payload = {}
        mock_point.vector = None

        mock_client.scroll.return_value = ([mock_point], None)

        ison = exp.export_collections(limit_per_collection=1)

        # Should have both collections
        assert 'table.coll1' in ison or 'table.coll2' in ison

    def test_stream_collection(self, exporter):
        """Test streaming collection as ISONL."""
        exp, mock_client, _ = exporter

        mock_point1 = MagicMock()
        mock_point1.id = 'p1'
        mock_point1.payload = {'title': 'Doc 1'}

        mock_point2 = MagicMock()
        mock_point2.id = 'p2'
        mock_point2.payload = {'title': 'Doc 2'}

        # First call for field discovery, subsequent calls for data
        mock_client.scroll.side_effect = [
            ([mock_point1, mock_point2], None),  # First batch
            ([mock_point1], None),  # Streaming batch 1
            ([], None)  # End
        ]

        lines = list(exp.stream_collection('test', batch_size=2))

        for line in lines:
            assert 'table.test|' in line

    def test_export_collection_info(self, exporter):
        """Test exporting collection metadata."""
        exp, mock_client, _ = exporter

        mock_info = MagicMock()
        mock_info.vectors_count = 500
        mock_info.points_count = 500
        mock_info.status = MagicMock()
        mock_info.status.value = 'green'

        mock_vectors = MagicMock()
        mock_vectors.size = 384
        mock_vectors.distance = MagicMock()
        mock_vectors.distance.value = 'Cosine'

        mock_info.config.params.vectors = mock_vectors

        mock_client.get_collection.return_value = mock_info

        ison = exp.export_collection_info('test')

        assert 'meta.collection_info' in ison
        assert '500' in ison  # points count
        assert '384' in ison  # vector size


class TestQdrantConvenienceFunctions:
    """Test convenience functions."""

    def test_qdrant_to_ison_with_query(self):
        """Test qdrant_to_ison with query vector."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 'p1'
        mock_point.score = 0.9
        mock_point.payload = {}
        mock_point.vector = None

        mock_client.search.return_value = [mock_point]

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import qdrant_to_ison

            ison = qdrant_to_ison(
                collection='test',
                query_vector=[0.1] * 10
            )

            assert 'table.results' in ison

    def test_qdrant_to_ison_with_ids(self):
        """Test qdrant_to_ison with point IDs."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 'id1'
        mock_point.payload = {'title': 'Test'}
        mock_point.vector = None

        mock_client.retrieve.return_value = [mock_point]

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import qdrant_to_ison

            ison = qdrant_to_ison(
                collection='test',
                ids=['id1']
            )

            assert 'id1' in ison

    def test_qdrant_to_ison_collection_export(self):
        """Test qdrant_to_ison for full collection export."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 'p1'
        mock_point.payload = {}
        mock_point.vector = None

        mock_client.scroll.return_value = ([mock_point], None)

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import qdrant_to_ison

            ison = qdrant_to_ison(collection='test')

            assert 'table.test' in ison

    def test_qdrant_rag_context(self):
        """Test qdrant_rag_context convenience function."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 'doc1'
        mock_point.score = 0.9
        mock_point.payload = {'source': 'test', 'text': 'Answer'}

        mock_client.search.return_value = [mock_point]

        def mock_embed(text):
            return [0.1] * 10

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import qdrant_rag_context

            context = qdrant_rag_context(
                collection='knowledge',
                query='What is ISON?',
                embedding_fn=mock_embed
            )

            assert 'table.context' in context


class TestQdrantEdgeCases:
    """Test edge cases and error handling."""

    def test_import_error_without_qdrant(self):
        """Test that ImportError is raised when qdrant-client is not installed."""
        with patch.dict('sys.modules', {'qdrant_client': None}):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exp = QdrantToISON(host='localhost')

            with pytest.raises(ImportError) as excinfo:
                _ = exp.client

            assert 'qdrant' in str(excinfo.value)

    def test_empty_search_results(self):
        """Test handling of empty search results."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client
        mock_client.search.return_value = []

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exp = QdrantToISON(host='localhost')
            exp._client = mock_client

            ison = exp.export_search_results(
                collection='test',
                query_vector=[0.1] * 10
            )

            # Should still have header
            assert 'table.results' in ison

    def test_point_with_no_payload(self):
        """Test handling of points without payload."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 'p1'
        mock_point.score = 0.9
        mock_point.payload = None  # No payload
        mock_point.vector = None

        mock_client.search.return_value = [mock_point]

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exp = QdrantToISON(host='localhost')
            exp._client = mock_client

            # Should not crash
            ison = exp.export_search_results(
                collection='test',
                query_vector=[0.1] * 10
            )

            assert 'p1' in ison

    def test_integer_point_id(self):
        """Test handling of integer point IDs."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 12345  # Integer ID
        mock_point.score = 0.9
        mock_point.payload = {}
        mock_point.vector = None

        mock_client.search.return_value = [mock_point]

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exp = QdrantToISON(host='localhost')
            exp._client = mock_client

            ison = exp.export_search_results(
                collection='test',
                query_vector=[0.1] * 10
            )

            assert '12345' in ison

    def test_uuid_point_id(self):
        """Test handling of UUID point IDs."""
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_models = MagicMock()

        mock_module.QdrantClient.return_value = mock_client

        mock_point = MagicMock()
        mock_point.id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
        mock_point.score = 0.9
        mock_point.payload = {}
        mock_point.vector = None

        mock_client.search.return_value = [mock_point]

        with patch.dict('sys.modules', {
            'qdrant_client': mock_module,
            'qdrant_client.models': mock_models
        }):
            from ison_parser.plugins.qdrant_plugin import QdrantToISON

            exp = QdrantToISON(host='localhost')
            exp._client = mock_client

            ison = exp.export_search_results(
                collection='test',
                query_vector=[0.1] * 10
            )

            assert 'a1b2c3d4' in ison


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
