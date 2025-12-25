"""
Tests for RudraDB ISON plugin.

These tests use mock objects since RudraDB may not be installed.
To run integration tests with a real RudraDB instance, set:
    RUDRADB_TEST_PATH=/path/to/test/db
"""

import pytest
from unittest.mock import MagicMock, patch
import sys

# Import the plugin
from ison_parser.plugins.rudradb_plugin import (
    RudraDBToISON,
    rudradb_to_ison,
    rudradb_query_to_ison,
)
from ison_parser import Reference


# =============================================================================
# Mock RudraDB for testing
# =============================================================================

class MockCollection:
    """Mock RudraDB collection."""

    def __init__(self, name: str, data: list):
        self.name = name
        self._data = data

    def all(self):
        return self._data

    def find(self):
        return MockCursor(self._data)

    def schema(self):
        if self._data:
            return list(self._data[0].keys())
        return []


class MockCursor:
    """Mock database cursor."""

    def __init__(self, data):
        self._data = data
        self._offset = 0
        self._limit = None

    def skip(self, n):
        self._offset = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def __iter__(self):
        data = self._data[self._offset:]
        if self._limit:
            data = data[:self._limit]
        return iter(data)

    def __list__(self):
        return list(self.__iter__())


class MockDatabase:
    """Mock RudraDB database."""

    def __init__(self, path=None, **kwargs):
        self.path = path
        self._collections = {}
        self._relationships = []

    def collection(self, name):
        return self._collections.get(name)

    def collections(self):
        return list(self._collections.keys())

    def relationships(self):
        return self._relationships

    def add_collection(self, name, data):
        self._collections[name] = MockCollection(name, data)

    def add_relationships(self, rels):
        self._relationships = rels

    def close(self):
        pass


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock RudraDB database with test data."""
    db = MockDatabase()

    # Add users collection
    db.add_collection('users', [
        {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'active': True},
        {'id': 2, 'name': 'Bob', 'email': 'bob@example.com', 'active': False},
        {'id': 3, 'name': 'Charlie', 'email': 'charlie@example.com', 'active': True},
    ])

    # Add orders collection with references
    db.add_collection('orders', [
        {'id': 101, 'user_id': {'_ref': '1', '_type': 'user'}, 'product': 'Widget', 'price': 29.99},
        {'id': 102, 'user_id': {'_ref': '1', '_type': 'user'}, 'product': 'Gadget', 'price': 49.99},
        {'id': 103, 'user_id': {'_ref': '2', '_type': 'user'}, 'product': 'Widget', 'price': 29.99},
    ])

    # Add relationships
    db.add_relationships([
        {'id': 1, 'type': 'PURCHASED', 'source_id': '1', 'source_type': 'user', 'target_id': '101', 'target_type': 'order'},
        {'id': 2, 'type': 'PURCHASED', 'source_id': '1', 'source_type': 'user', 'target_id': '102', 'target_type': 'order'},
        {'id': 3, 'type': 'PURCHASED', 'source_id': '2', 'source_type': 'user', 'target_id': '103', 'target_type': 'order'},
    ])

    return db


@pytest.fixture
def exporter(mock_db):
    """Create an exporter with mock database."""
    return RudraDBToISON(db=mock_db)


# =============================================================================
# Basic Tests
# =============================================================================

class TestRudraDBToISONBasic:
    """Basic RudraDB to ISON tests."""

    def test_export_single_collection(self, exporter):
        """Test exporting a single collection."""
        result = exporter.export_collection('users')

        assert 'table.users' in result
        assert 'id' in result
        assert 'name' in result
        assert 'Alice' in result
        assert 'Bob' in result
        assert 'Charlie' in result

    def test_export_multiple_collections(self, exporter):
        """Test exporting multiple collections."""
        result = exporter.export_collections(['users', 'orders'])

        assert 'table.users' in result
        assert 'table.orders' in result
        assert 'Alice' in result
        assert 'Widget' in result

    def test_export_all(self, exporter):
        """Test exporting entire database."""
        result = exporter.export_all()

        assert 'table.users' in result
        assert 'table.orders' in result
        # Relationships should be included
        assert 'table.relationships' in result or 'PURCHASED' in result

    def test_export_with_limit(self, exporter):
        """Test exporting with row limit."""
        result = exporter.export_collection('users', limit=2)

        lines = result.strip().split('\n')
        # Header line + fields line + 2 data rows = 4 lines
        data_lines = [l for l in lines if l and not l.startswith('table.') and 'name' not in l.split()[0]]
        assert len(data_lines) <= 2


class TestRudraDBReferences:
    """Test reference handling."""

    def test_reference_conversion(self, exporter):
        """Test that references are converted to ISON format."""
        result = exporter.export_collection('orders')

        # Should contain ISON references
        assert ':user:1' in result or ':1' in result

    def test_relationship_export(self, exporter):
        """Test relationship data export."""
        result = exporter.export_all(include_relationships=True)

        # Should contain relationship data
        assert 'PURCHASED' in result


class TestRudraDBQueryExport:
    """Test query result export."""

    def test_export_query_result_list(self, exporter):
        """Test exporting a list of query results."""
        query_result = [
            {'id': 1, 'name': 'Test1'},
            {'id': 2, 'name': 'Test2'},
        ]

        result = exporter.export_query(query_result, name='test_result')

        assert 'table.test_result' in result
        assert 'Test1' in result
        assert 'Test2' in result

    def test_export_query_result_dict(self, exporter):
        """Test exporting a single dict result."""
        query_result = {'id': 1, 'name': 'SingleResult'}

        result = exporter.export_query(query_result, name='single')

        assert 'table.single' in result
        assert 'SingleResult' in result


class TestRudraDBStreaming:
    """Test ISONL streaming export."""

    def test_stream_collection(self, exporter):
        """Test streaming a collection as ISONL."""
        lines = list(exporter.stream_collection('users', batch_size=2))

        assert len(lines) == 3  # 3 users
        for line in lines:
            assert 'table.users|' in line
            assert '|' in line


class TestRudraDBRAG:
    """Test RAG context export."""

    def test_export_for_rag(self, exporter):
        """Test RAG-optimized export."""
        result = exporter.export_for_rag('users', limit=2)

        assert 'table.context' in result
        assert 'rank' in result
        assert 'score' in result


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_rudradb_query_to_ison(self, mock_db):
        """Test query to ISON convenience function."""
        query_result = [
            {'id': 1, 'value': 'test'},
        ]

        result = rudradb_query_to_ison(mock_db, query_result, name='query')

        assert 'table.query' in result
        assert 'test' in result


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_collection(self, mock_db):
        """Test exporting an empty collection."""
        mock_db.add_collection('empty', [])
        exporter = RudraDBToISON(db=mock_db)

        result = exporter.export_collection('empty')

        # Should return empty or minimal output
        assert result == '' or 'table.empty' in result

    def test_collection_not_found(self, exporter):
        """Test exporting non-existent collection."""
        result = exporter.export_collection('nonexistent')

        assert result == ''

    def test_null_values(self, mock_db):
        """Test handling of null values."""
        mock_db.add_collection('with_nulls', [
            {'id': 1, 'name': None, 'value': 'test'},
            {'id': 2, 'name': 'Bob', 'value': None},
        ])
        exporter = RudraDBToISON(db=mock_db)

        result = exporter.export_collection('with_nulls')

        assert 'null' in result

    def test_special_characters(self, mock_db):
        """Test handling of special characters in strings."""
        mock_db.add_collection('special', [
            {'id': 1, 'text': 'Hello World'},
            {'id': 2, 'text': 'Line1\nLine2'},
            {'id': 3, 'text': 'Quote"Inside'},
        ])
        exporter = RudraDBToISON(db=mock_db)

        result = exporter.export_collection('special')

        # Strings with spaces should be quoted
        assert '"Hello World"' in result
        # Should handle escape sequences
        assert '\\n' in result or 'Line1' in result

    def test_vector_field_handling(self, mock_db):
        """Test that large vector fields are handled properly."""
        mock_db.add_collection('vectors', [
            {'id': 1, 'embedding': [0.1] * 384, 'text': 'test'},
        ])
        exporter = RudraDBToISON(db=mock_db)

        # Without vectors
        result = exporter.export_collection('vectors', include_vectors=False)
        assert '[vector:' in result or 'embedding' not in result or len(result) < 1000


class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager(self, mock_db):
        """Test using exporter as context manager."""
        with RudraDBToISON(db=mock_db) as exporter:
            result = exporter.export_collection('users')
            assert 'Alice' in result


# =============================================================================
# Integration Tests (skipped if RudraDB not installed)
# =============================================================================

@pytest.mark.skip(reason="Requires actual RudraDB installation")
class TestRudraDBIntegration:
    """Integration tests with real RudraDB."""

    def test_real_database(self):
        """Test with actual RudraDB database."""
        import os
        db_path = os.environ.get('RUDRADB_TEST_PATH')
        if not db_path:
            pytest.skip("RUDRADB_TEST_PATH not set")

        with RudraDBToISON(db_path=db_path) as exporter:
            collections = exporter.get_collections()
            assert len(collections) > 0

            result = exporter.export_all()
            assert len(result) > 0
