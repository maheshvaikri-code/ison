#!/usr/bin/env python3
"""
Tests for PostgreSQL to ISON Plugin.

Uses mocking since we can't require a live PostgreSQL database for tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestPostgreSQLToISON:
    """Test PostgreSQLToISON class with mocked psycopg2."""

    @pytest.fixture
    def mock_psycopg2(self):
        """Create a mock psycopg2 module."""
        mock_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_module.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        return mock_module, mock_conn, mock_cursor

    @pytest.fixture
    def exporter(self, mock_psycopg2):
        """Create an exporter with mocked psycopg2."""
        mock_module, mock_conn, mock_cursor = mock_psycopg2

        with patch.dict('sys.modules', {'psycopg2': mock_module, 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import PostgreSQLToISON

            exporter = PostgreSQLToISON(
                host='localhost',
                database='testdb',
                user='testuser',
                password='testpass'
            )

            # Set up the connection manually to avoid actual connection
            exporter._conn = mock_conn

            yield exporter, mock_cursor

    def test_init_with_connection_string(self):
        """Test initialization with connection string."""
        with patch.dict('sys.modules', {'psycopg2': MagicMock(), 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import PostgreSQLToISON

            exporter = PostgreSQLToISON('postgresql://user:pass@localhost:5432/mydb')
            assert exporter.connection_string == 'postgresql://user:pass@localhost:5432/mydb'
            assert exporter.schema == 'public'

    def test_init_with_params(self):
        """Test initialization with individual parameters."""
        with patch.dict('sys.modules', {'psycopg2': MagicMock(), 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import PostgreSQLToISON

            exporter = PostgreSQLToISON(
                host='myhost',
                port=5433,
                database='mydb',
                user='myuser',
                password='mypass',
                schema='myschema'
            )

            assert exporter.host == 'myhost'
            assert exporter.port == 5433
            assert exporter.database == 'mydb'
            assert exporter.user == 'myuser'
            assert exporter.schema == 'myschema'

    def test_get_tables(self, exporter):
        """Test getting list of tables."""
        exp, mock_cursor = exporter

        mock_cursor.fetchall.return_value = [
            ('users',),
            ('orders',),
            ('products',)
        ]

        tables = exp.get_tables()

        assert 'users' in tables
        assert 'orders' in tables
        assert 'products' in tables
        assert len(tables) == 3

    def test_get_table_info(self, exporter):
        """Test getting table column information."""
        exp, mock_cursor = exporter

        # First call for column info
        mock_cursor.fetchall.side_effect = [
            [
                ('id', 'integer', 'NO', None, 1),
                ('name', 'character varying', 'NO', None, 2),
                ('email', 'text', 'YES', None, 3),
                ('active', 'boolean', 'YES', 'true', 4),
            ],
            [('id',)]  # Primary key query
        ]

        info = exp.get_table_info('users')

        assert len(info) == 4
        names = [c['name'] for c in info]
        assert 'id' in names
        assert 'name' in names

        id_col = next(c for c in info if c['name'] == 'id')
        assert id_col['type'] == 'integer'
        assert id_col['nullable'] is False

    def test_format_value_null(self, exporter):
        """Test formatting NULL values."""
        exp, _ = exporter
        assert exp._format_value(None) == '~'

    def test_format_value_boolean(self, exporter):
        """Test formatting boolean values."""
        exp, _ = exporter
        assert exp._format_value(True) == 'true'
        assert exp._format_value(False) == 'false'

    def test_format_value_numbers(self, exporter):
        """Test formatting numeric values."""
        exp, _ = exporter
        assert exp._format_value(42) == '42'
        assert exp._format_value(3.14) == '3.14'
        assert exp._format_value(-100) == '-100'

    def test_format_value_datetime(self, exporter):
        """Test formatting datetime values."""
        exp, _ = exporter
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = exp._format_value(dt)
        assert '2025-01-15' in result

    def test_format_value_date(self, exporter):
        """Test formatting date values."""
        exp, _ = exporter
        d = date(2025, 1, 15)
        result = exp._format_value(d)
        assert '2025-01-15' in result

    def test_format_value_string_simple(self, exporter):
        """Test formatting simple strings."""
        exp, _ = exporter
        assert exp._format_value('hello') == 'hello'
        assert exp._format_value('test123') == 'test123'

    def test_format_value_string_with_spaces(self, exporter):
        """Test formatting strings with spaces."""
        exp, _ = exporter
        assert exp._format_value('hello world') == '"hello world"'
        assert exp._format_value('John Doe') == '"John Doe"'

    def test_format_value_string_with_quotes(self, exporter):
        """Test formatting strings with quotes."""
        exp, _ = exporter
        result = exp._format_value('Say "Hi"')
        assert '\\"' in result  # Escaped quotes

    def test_format_value_array(self, exporter):
        """Test formatting PostgreSQL arrays."""
        exp, _ = exporter
        result = exp._format_value([1, 2, 3])
        assert result == '[1,2,3]'

    def test_format_value_dict_json(self, exporter):
        """Test formatting JSON/JSONB values."""
        exp, _ = exporter
        result = exp._format_value({'key': 'value'})
        assert 'key' in result
        assert 'value' in result

    def test_get_ison_type(self, exporter):
        """Test PostgreSQL to ISON type mapping."""
        exp, _ = exporter

        assert exp._get_ison_type('integer') == 'int'
        assert exp._get_ison_type('bigint') == 'int'
        assert exp._get_ison_type('smallint') == 'int'
        assert exp._get_ison_type('serial') == 'int'

        assert exp._get_ison_type('real') == 'float'
        assert exp._get_ison_type('double precision') == 'float'
        assert exp._get_ison_type('numeric') == 'float'

        assert exp._get_ison_type('boolean') == 'bool'
        assert exp._get_ison_type('date') == 'date'
        assert exp._get_ison_type('timestamp') == 'datetime'
        assert exp._get_ison_type('timestamptz') == 'datetime'

        assert exp._get_ison_type('json') == 'json'
        assert exp._get_ison_type('jsonb') == 'json'

        assert exp._get_ison_type('integer[]') == 'array'
        assert exp._get_ison_type('text[]') == 'array'

        assert exp._get_ison_type('character varying') is None  # String default

    def test_export_table_basic(self, exporter):
        """Test basic table export."""
        exp, mock_cursor = exporter

        # Mock get_table_info
        mock_cursor.fetchall.side_effect = [
            [  # Column info
                ('id', 'integer', 'NO', None, 1),
                ('name', 'text', 'NO', None, 2),
            ],
            [('id',)],  # Primary key
            [  # Data rows
                (1, 'Alice'),
                (2, 'Bob'),
            ]
        ]

        ison = exp.export_table('users')

        assert 'table.users' in ison
        assert 'id' in ison
        assert 'name' in ison
        assert 'Alice' in ison
        assert 'Bob' in ison

    def test_export_table_with_types(self, exporter):
        """Test table export with type annotations."""
        exp, mock_cursor = exporter

        mock_cursor.fetchall.side_effect = [
            [
                ('id', 'integer', 'NO', None, 1),
                ('price', 'numeric', 'YES', None, 2),
                ('active', 'boolean', 'YES', None, 3),
            ],
            [('id',)],
            [(1, 29.99, True)]
        ]

        ison = exp.export_table('products', include_types=True)

        assert 'id:int' in ison
        assert 'price:float' in ison
        assert 'active:bool' in ison

    def test_export_table_with_where(self, exporter):
        """Test table export with WHERE clause."""
        exp, mock_cursor = exporter

        mock_cursor.fetchall.side_effect = [
            [('id', 'integer', 'NO', None, 1), ('name', 'text', 'NO', None, 2)],
            [('id',)],
            [(1, 'Alice')]  # Only active users
        ]

        ison = exp.export_table('users', where='active = true')

        # Verify the WHERE clause was used
        call_args = mock_cursor.execute.call_args_list
        assert any('WHERE' in str(call) for call in call_args)

    def test_export_multiple_tables(self, exporter):
        """Test exporting multiple tables."""
        exp, mock_cursor = exporter

        # Set up mock for multiple tables
        mock_cursor.fetchall.side_effect = [
            # First table info
            [('id', 'integer', 'NO', None, 1)],
            [('id',)],
            [(1,), (2,)],
            # Second table info
            [('id', 'integer', 'NO', None, 1)],
            [('id',)],
            [(101,), (102,)],
        ]

        ison = exp.export_tables(['users', 'orders'])

        assert 'table.users' in ison
        assert 'table.orders' in ison

    def test_export_all(self, exporter):
        """Test exporting all tables."""
        exp, mock_cursor = exporter

        mock_cursor.fetchall.side_effect = [
            [('users',), ('orders',)],  # get_tables
            # users table
            [('id', 'integer', 'NO', None, 1)],
            [('id',)],
            [(1,)],
            # orders table
            [('id', 'integer', 'NO', None, 1)],
            [('id',)],
            [(101,)],
        ]

        ison = exp.export_all()

        assert 'table.users' in ison
        assert 'table.orders' in ison

    def test_export_query(self, exporter):
        """Test exporting custom query results."""
        exp, mock_cursor = exporter

        mock_cursor.description = [('name',), ('count',)]
        mock_cursor.fetchall.return_value = [
            ('Alice', 5),
            ('Bob', 3),
        ]

        ison = exp.export_query(
            'SELECT name, COUNT(*) as count FROM orders GROUP BY name',
            block_name='order_counts'
        )

        assert 'table.order_counts' in ison
        assert 'name' in ison
        assert 'count' in ison
        assert 'Alice' in ison
        assert '5' in ison

    def test_export_query_with_params(self, exporter):
        """Test query export with parameters."""
        exp, mock_cursor = exporter

        mock_cursor.description = [('id',), ('name',)]
        mock_cursor.fetchall.return_value = [(1, 'Alice')]

        ison = exp.export_query(
            'SELECT * FROM users WHERE id = %s',
            params=(1,)
        )

        # Verify parameterized query was called
        mock_cursor.execute.assert_called()

    def test_stream_table(self, exporter):
        """Test streaming table as ISONL."""
        exp, mock_cursor = exporter

        # Create a named cursor mock
        named_cursor = MagicMock()
        exp._conn.cursor.return_value = named_cursor

        mock_cursor.fetchall.side_effect = [
            [('id', 'integer', 'NO', None, 1), ('name', 'text', 'NO', None, 2)],
            [('id',)],
        ]

        named_cursor.fetchmany.side_effect = [
            [(1, 'Alice'), (2, 'Bob')],
            []  # End of results
        ]

        lines = list(exp.stream_table('users'))

        assert len(lines) == 2
        for line in lines:
            assert line.startswith('table.users|')
            assert '|' in line

    def test_non_public_schema(self, exporter):
        """Test exporting from non-public schema."""
        exp, mock_cursor = exporter

        mock_cursor.fetchall.side_effect = [
            [('id', 'integer', 'NO', None, 1)],
            [('id',)],
            [(1,)]
        ]

        ison = exp.export_table('users', schema='myschema')

        # Non-public schemas should be prefixed
        assert 'table.myschema.users' in ison

    def test_context_manager(self, mock_psycopg2):
        """Test context manager protocol."""
        mock_module, mock_conn, mock_cursor = mock_psycopg2

        with patch.dict('sys.modules', {'psycopg2': mock_module, 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import PostgreSQLToISON

            with PostgreSQLToISON(host='localhost', database='test', user='user', password='pass') as exp:
                # Should have connected
                mock_module.connect.assert_called()

            # Should have closed
            mock_conn.close.assert_called()


class TestPostgresqlToIsonFunction:
    """Test the convenience function."""

    def test_export_all_default(self):
        """Test convenience function with defaults."""
        mock_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_module.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [],  # foreign keys
            [('users',)],  # tables
            [('id', 'integer', 'NO', None, 1)],  # columns
            [('id',)],  # pk
            [(1,)]  # data
        ]

        with patch.dict('sys.modules', {'psycopg2': mock_module, 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import postgresql_to_ison

            ison = postgresql_to_ison('postgresql://localhost/test')

            assert 'table.users' in ison

    def test_export_with_query(self):
        """Test convenience function with query."""
        mock_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_module.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [],  # foreign keys
            [('Alice',), ('Bob',)]  # query results
        ]
        mock_cursor.description = [('name',)]

        with patch.dict('sys.modules', {'psycopg2': mock_module, 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import postgresql_to_ison

            ison = postgresql_to_ison(
                'postgresql://localhost/test',
                query='SELECT name FROM users'
            )

            assert 'Alice' in ison
            assert 'Bob' in ison


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_import_error_without_psycopg2(self):
        """Test that ImportError is raised when psycopg2 is not installed."""
        with patch.dict('sys.modules', {'psycopg2': None}):
            from ison_parser.plugins.postgresql_plugin import PostgreSQLToISON

            exp = PostgreSQLToISON(host='localhost', database='test', user='user', password='pass')

            with pytest.raises(ImportError) as excinfo:
                exp.connect()

            assert 'psycopg2' in str(excinfo.value)

    def test_empty_table(self):
        """Test exporting an empty table."""
        mock_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_module.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [],  # foreign keys
            [('id', 'integer', 'NO', None, 1)],  # columns
            [],  # pk
            []  # empty data
        ]

        with patch.dict('sys.modules', {'psycopg2': mock_module, 'psycopg2.extras': MagicMock()}):
            from ison_parser.plugins.postgresql_plugin import PostgreSQLToISON

            exp = PostgreSQLToISON(host='localhost', database='test', user='user', password='pass')
            exp._conn = mock_conn

            ison = exp.export_table('empty_table')

            lines = ison.strip().split('\n')
            # Empty table with no columns only has the table name line
            assert len(lines) >= 1
            assert 'table.empty_table' in lines[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
