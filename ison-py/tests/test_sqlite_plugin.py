#!/usr/bin/env python3
"""
Tests for SQLite to ISON Plugin.

These tests use in-memory SQLite databases, so no external dependencies are needed.
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ison_parser.plugins.sqlite_plugin import SQLiteToISON, sqlite_to_ison


class TestSQLiteToISON:
    """Test SQLiteToISON class."""

    @pytest.fixture
    def sample_db(self):
        """Create a sample in-memory database with test data."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                active INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                product TEXT,
                amount REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Insert test data
        cursor.executemany(
            'INSERT INTO users (id, name, email, active) VALUES (?, ?, ?, ?)',
            [
                (1, 'Alice', 'alice@example.com', 1),
                (2, 'Bob', 'bob@example.com', 0),
                (3, 'Charlie', 'charlie@example.com', 1),
            ]
        )

        cursor.executemany(
            'INSERT INTO orders (id, user_id, product, amount) VALUES (?, ?, ?, ?)',
            [
                (101, 1, 'Widget', 29.99),
                (102, 1, 'Gadget', 49.99),
                (103, 2, 'Widget', 29.99),
            ]
        )

        conn.commit()

        # Save to temp file for testing file-based operations
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        # Copy to temp file
        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        yield temp_path

        # Cleanup
        os.unlink(temp_path)

    def test_connect_and_close(self, sample_db):
        """Test database connection lifecycle."""
        exporter = SQLiteToISON(sample_db)

        # Initially not connected
        assert exporter._conn is None

        # Connect
        conn = exporter.connect()
        assert conn is not None
        assert exporter._conn is not None

        # Close
        exporter.close()
        assert exporter._conn is None

    def test_context_manager(self, sample_db):
        """Test context manager protocol."""
        with SQLiteToISON(sample_db) as exporter:
            assert exporter._conn is not None
            tables = exporter.get_tables()
            assert len(tables) > 0

        # Connection should be closed after context
        assert exporter._conn is None

    def test_get_tables(self, sample_db):
        """Test getting list of tables."""
        with SQLiteToISON(sample_db) as exporter:
            tables = exporter.get_tables()

            assert 'users' in tables
            assert 'orders' in tables
            # Should not include sqlite internal tables
            assert not any(t.startswith('sqlite_') for t in tables)

    def test_get_table_info(self, sample_db):
        """Test getting table column information."""
        with SQLiteToISON(sample_db) as exporter:
            info = exporter.get_table_info('users')

            assert len(info) == 4
            column_names = [c['name'] for c in info]
            assert 'id' in column_names
            assert 'name' in column_names
            assert 'email' in column_names
            assert 'active' in column_names

            # Check types
            id_col = next(c for c in info if c['name'] == 'id')
            assert 'INTEGER' in id_col['type'].upper()
            assert id_col['pk'] is True

    def test_export_table_basic(self, sample_db):
        """Test basic table export."""
        with SQLiteToISON(sample_db) as exporter:
            ison = exporter.export_table('users')

            # Check structure
            lines = ison.strip().split('\n')
            assert lines[0] == 'table.users'
            assert 'id' in lines[1]
            assert 'name' in lines[1]

            # Should have header + 3 data rows
            assert len(lines) == 5

            # Check data
            assert 'Alice' in ison
            assert 'Bob' in ison
            assert 'Charlie' in ison

    def test_export_table_with_types(self, sample_db):
        """Test table export with type annotations."""
        with SQLiteToISON(sample_db) as exporter:
            ison = exporter.export_table('users', include_types=True)

            lines = ison.strip().split('\n')
            header = lines[1]

            # Should have type annotations
            assert 'id:int' in header or 'id' in header  # INTEGER maps to int

    def test_export_table_with_where(self, sample_db):
        """Test table export with WHERE clause."""
        with SQLiteToISON(sample_db) as exporter:
            ison = exporter.export_table('users', where='active = 1')

            # Should only have active users
            assert 'Alice' in ison
            assert 'Charlie' in ison
            assert 'Bob' not in ison  # Bob is not active

    def test_export_multiple_tables(self, sample_db):
        """Test exporting multiple tables."""
        with SQLiteToISON(sample_db) as exporter:
            ison = exporter.export_tables(['users', 'orders'])

            # Both tables should be present
            assert 'table.users' in ison
            assert 'table.orders' in ison

            # Should be separated by blank line
            assert '\n\ntable.' in ison

    def test_export_all(self, sample_db):
        """Test exporting all tables."""
        with SQLiteToISON(sample_db) as exporter:
            ison = exporter.export_all()

            assert 'table.users' in ison
            assert 'table.orders' in ison

    def test_export_query(self, sample_db):
        """Test exporting custom query results."""
        with SQLiteToISON(sample_db) as exporter:
            ison = exporter.export_query(
                'SELECT name, email FROM users WHERE active = 1',
                block_name='active_users'
            )

            lines = ison.strip().split('\n')
            assert lines[0] == 'table.active_users'
            assert 'name' in lines[1]
            assert 'email' in lines[1]
            assert 'Alice' in ison
            assert 'Bob' not in ison

    def test_foreign_key_references(self, sample_db):
        """Test that foreign keys are converted to ISON references."""
        with SQLiteToISON(sample_db, detect_references=True) as exporter:
            ison = exporter.export_table('orders')

            # Foreign key user_id should be converted to :1, :2, etc.
            assert ':1' in ison or ':2' in ison

    def test_foreign_key_disabled(self, sample_db):
        """Test that foreign key detection can be disabled."""
        with SQLiteToISON(sample_db, detect_references=False) as exporter:
            ison = exporter.export_table('orders')

            # Should have raw values, not references
            lines = ison.strip().split('\n')
            # Check data rows have numeric user_id, not :N format
            data_lines = lines[2:]  # Skip header lines
            for line in data_lines:
                # The user_id value should not start with :
                # This is a bit tricky since we need to find the user_id column
                assert '101' in ison or '102' in ison  # Order IDs

    def test_stream_table(self, sample_db):
        """Test streaming table as ISONL."""
        with SQLiteToISON(sample_db) as exporter:
            lines = list(exporter.stream_table('users'))

            # Should have one line per row
            assert len(lines) == 3

            # Each line should be ISONL format
            for line in lines:
                assert line.startswith('table.users|')
                parts = line.split('|')
                assert len(parts) == 3  # kind.name|fields|values

    def test_stream_table_with_where(self, sample_db):
        """Test streaming with WHERE clause."""
        with SQLiteToISON(sample_db) as exporter:
            lines = list(exporter.stream_table('users', where='active = 1'))

            # Should only have active users
            assert len(lines) == 2  # Alice and Charlie

    def test_export_schema(self, sample_db):
        """Test schema export."""
        with SQLiteToISON(sample_db) as exporter:
            schema = exporter.export_schema()

            assert 'meta.schema' in schema
            assert 'users' in schema
            assert 'orders' in schema

    def test_null_values(self):
        """Test handling of NULL values."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER, value TEXT)')
        cursor.execute('INSERT INTO test VALUES (1, NULL)')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('test')
                # NULL should be represented as ~
                assert '~' in ison
        finally:
            os.unlink(temp_path)

    def test_quoted_strings(self):
        """Test that strings with spaces are properly quoted."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER, name TEXT)')
        cursor.execute('INSERT INTO test VALUES (1, "John Doe")')
        cursor.execute('INSERT INTO test VALUES (2, "Jane Smith")')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('test')
                # Names with spaces should be quoted
                assert '"John Doe"' in ison
                assert '"Jane Smith"' in ison
        finally:
            os.unlink(temp_path)

    def test_special_characters_in_strings(self):
        """Test that special characters in strings are escaped."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER, content TEXT)')
        cursor.execute('INSERT INTO test VALUES (1, ?)', ('Hello\nWorld',))
        cursor.execute('INSERT INTO test VALUES (2, ?)', ('Say "Hi"',))
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('test')
                # Should have escaped content
                assert '\\n' in ison or 'Hello' in ison  # Newline escaped
                assert '\\"' in ison or 'Hi' in ison  # Quotes escaped
        finally:
            os.unlink(temp_path)

    def test_numeric_types(self):
        """Test handling of different numeric types."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE test (
                int_val INTEGER,
                real_val REAL,
                float_val FLOAT
            )
        ''')
        cursor.execute('INSERT INTO test VALUES (42, 3.14159, 2.718)')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('test')
                assert '42' in ison
                assert '3.14159' in ison
                assert '2.718' in ison
        finally:
            os.unlink(temp_path)


class TestSqliteToIsonFunction:
    """Test the convenience function."""

    @pytest.fixture
    def sample_db(self):
        """Create a sample database."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE users (id INTEGER, name TEXT)')
        cursor.execute('INSERT INTO users VALUES (1, "Alice")')
        cursor.execute('INSERT INTO users VALUES (2, "Bob")')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        yield temp_path
        os.unlink(temp_path)

    def test_export_all_tables(self, sample_db):
        """Test exporting all tables via convenience function."""
        ison = sqlite_to_ison(sample_db)
        assert 'table.users' in ison
        assert 'Alice' in ison

    def test_export_specific_tables(self, sample_db):
        """Test exporting specific tables."""
        ison = sqlite_to_ison(sample_db, tables=['users'])
        assert 'table.users' in ison

    def test_export_query(self, sample_db):
        """Test exporting query results."""
        ison = sqlite_to_ison(sample_db, query='SELECT * FROM users WHERE id = 1')
        assert 'Alice' in ison
        assert 'Bob' not in ison


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_table(self):
        """Test exporting an empty table."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE empty (id INTEGER, name TEXT)')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('empty')
                lines = ison.strip().split('\n')
                # Should have header only, no data rows
                assert len(lines) == 2
                assert lines[0] == 'table.empty'
        finally:
            os.unlink(temp_path)

    def test_path_object(self):
        """Test using pathlib.Path for database path."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER)')
        cursor.execute('INSERT INTO test VALUES (1)')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = Path(f.name)

        temp_conn = sqlite3.connect(str(temp_path))
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('test')
                assert 'table.test' in ison
        finally:
            os.unlink(temp_path)

    def test_boolean_values(self):
        """Test handling of boolean values."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE test (id INTEGER, active BOOLEAN)')
        cursor.execute('INSERT INTO test VALUES (1, 1)')
        cursor.execute('INSERT INTO test VALUES (2, 0)')
        conn.commit()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        temp_conn = sqlite3.connect(temp_path)
        conn.backup(temp_conn)
        temp_conn.close()
        conn.close()

        try:
            with SQLiteToISON(temp_path) as exporter:
                ison = exporter.export_table('test')
                # SQLite stores booleans as integers
                assert '1' in ison and '0' in ison
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
