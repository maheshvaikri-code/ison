#!/usr/bin/env python3
"""
PostgreSQL to ISON Plugin
Export PostgreSQL databases to ISON format for LLM workflows.

Requires: psycopg2 or psycopg2-binary
    pip install psycopg2-binary

Usage:
    from ison_parser.plugins import PostgreSQLToISON

    # Connect with connection string
    exporter = PostgreSQLToISON('postgresql://user:pass@localhost/mydb')

    # Or with individual parameters
    exporter = PostgreSQLToISON(
        host='localhost',
        database='mydb',
        user='user',
        password='pass'
    )

    # Export tables
    ison_text = exporter.export_all()

    # Export specific schema
    ison_text = exporter.export_schema_tables('public', ['users', 'orders'])

    # Stream large tables as ISONL
    for line in exporter.stream_table('logs'):
        process(line)
"""

from typing import List, Optional, Dict, Any, Iterator, Union
import re


class PostgreSQLToISON:
    """Export PostgreSQL database to ISON format."""

    def __init__(self,
                 connection_string: str = None,
                 host: str = None,
                 port: int = 5432,
                 database: str = None,
                 user: str = None,
                 password: str = None,
                 schema: str = 'public',
                 detect_references: bool = True):
        """
        Initialize PostgreSQL exporter.

        Args:
            connection_string: PostgreSQL connection string (postgresql://...)
            host: Database host
            port: Database port (default 5432)
            database: Database name
            user: Username
            password: Password
            schema: Default schema (default 'public')
            detect_references: Auto-detect foreign keys
        """
        self.connection_string = connection_string
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema
        self.detect_references = detect_references
        self._conn = None
        self._foreign_keys: Dict[str, Dict[str, tuple]] = {}

    def connect(self):
        """Get or create database connection."""
        if self._conn is None:
            try:
                import psycopg2
                import psycopg2.extras
            except ImportError:
                raise ImportError(
                    "psycopg2 is required for PostgreSQL support. "
                    "Install with: pip install psycopg2-binary"
                )

            if self.connection_string:
                self._conn = psycopg2.connect(self.connection_string)
            else:
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )

            if self.detect_references:
                self._load_foreign_keys()

        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _load_foreign_keys(self):
        """Load foreign key relationships from information_schema."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS ref_schema,
                ccu.table_name AS ref_table,
                ccu.column_name AS ref_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
        """)

        for row in cursor.fetchall():
            schema, table, column, ref_schema, ref_table, ref_column = row
            key = f"{schema}.{table}"
            if key not in self._foreign_keys:
                self._foreign_keys[key] = {}
            self._foreign_keys[key][column] = (f"{ref_schema}.{ref_table}", ref_column)

        cursor.close()

    def get_tables(self, schema: str = None) -> List[str]:
        """Get list of all tables in schema."""
        schema = schema or self.schema
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema,))

        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables

    def get_table_info(self, table: str, schema: str = None) -> List[Dict[str, Any]]:
        """Get column information for a table."""
        schema = schema or self.schema
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))

        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row[0],
                'type': row[1],
                'nullable': row[2] == 'YES',
                'default': row[3],
                'position': row[4]
            })

        # Get primary key columns
        cursor.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
        """, (f"{schema}.{table}",))

        pk_cols = {row[0] for row in cursor.fetchall()}
        for col in columns:
            col['pk'] = col['name'] in pk_cols

        cursor.close()
        return columns

    def _format_value(self, value: Any, table: str = None,
                      column: str = None, schema: str = None) -> str:
        """Format a value for ISON output."""
        if value is None:
            return '~'

        schema = schema or self.schema
        full_table = f"{schema}.{table}" if table else None

        # Check if this is a foreign key reference
        if (full_table and column and self.detect_references and
            full_table in self._foreign_keys and
            column in self._foreign_keys[full_table]):
            return f':{value}'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, (int, float)):
            return str(value)

        # Handle datetime
        if hasattr(value, 'isoformat'):
            return value.isoformat()

        # Handle arrays (PostgreSQL specific)
        if isinstance(value, list):
            items = [self._format_value(v) for v in value]
            return '[' + ','.join(items) + ']'

        # Handle JSON/JSONB
        if isinstance(value, dict):
            import json
            return '"' + json.dumps(value).replace('"', '\\"') + '"'

        # String value
        str_val = str(value)
        if ' ' in str_val or '\n' in str_val or '\t' in str_val or '"' in str_val:
            escaped = str_val.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'

        return str_val

    def _get_ison_type(self, pg_type: str) -> Optional[str]:
        """Map PostgreSQL type to ISON type annotation."""
        pg_type = pg_type.lower()

        if pg_type in ('integer', 'bigint', 'smallint', 'serial', 'bigserial'):
            return 'int'
        if pg_type in ('real', 'double precision', 'numeric', 'decimal'):
            return 'float'
        if pg_type == 'boolean':
            return 'bool'
        if pg_type == 'date':
            return 'date'
        if pg_type in ('timestamp', 'timestamp without time zone',
                       'timestamp with time zone', 'timestamptz'):
            return 'datetime'
        if pg_type in ('json', 'jsonb'):
            return 'json'
        if pg_type.endswith('[]'):
            return 'array'

        return None

    def export_table(self, table: str, schema: str = None,
                     where: str = None, include_types: bool = True) -> str:
        """
        Export a single table to ISON format.

        Args:
            table: Table name
            schema: Schema name (default: self.schema)
            where: Optional WHERE clause
            include_types: Include type annotations

        Returns:
            ISON formatted string
        """
        schema = schema or self.schema
        conn = self.connect()
        cursor = conn.cursor()

        columns = self.get_table_info(table, schema)

        # Build field names
        fields = []
        for col in columns:
            field = col['name']
            if include_types:
                ison_type = self._get_ison_type(col['type'])
                if ison_type:
                    field = f"{col['name']}:{ison_type}"
            fields.append(field)

        # Query data
        query = f'SELECT * FROM "{schema}"."{table}"'
        if where:
            query += f" WHERE {where}"

        cursor.execute(query)
        rows = cursor.fetchall()

        # Build ISON output
        block_name = f"{schema}.{table}" if schema != 'public' else table
        lines = [f"table.{block_name}"]
        lines.append(' '.join(fields))

        for row in rows:
            values = []
            for i, col in enumerate(columns):
                val = self._format_value(row[i], table, col['name'], schema)
                values.append(val)
            lines.append(' '.join(values))

        cursor.close()
        return '\n'.join(lines)

    def export_tables(self, tables: List[str], schema: str = None,
                      include_types: bool = True) -> str:
        """Export multiple tables to ISON format."""
        schema = schema or self.schema
        blocks = []
        for table in tables:
            blocks.append(self.export_table(table, schema, include_types=include_types))
        return '\n\n'.join(blocks)

    def export_schema_tables(self, schema: str, tables: List[str] = None,
                             include_types: bool = True) -> str:
        """
        Export tables from a specific schema.

        Args:
            schema: Schema name
            tables: List of tables (None for all)
            include_types: Include type annotations

        Returns:
            ISON formatted string
        """
        if tables is None:
            tables = self.get_tables(schema)
        return self.export_tables(tables, schema, include_types)

    def export_all(self, include_types: bool = True) -> str:
        """Export all tables in default schema."""
        tables = self.get_tables()
        return self.export_tables(tables, include_types=include_types)

    def export_query(self, query: str, block_name: str = 'query_result',
                     params: tuple = None) -> str:
        """
        Export query results to ISON format.

        Args:
            query: SQL query
            block_name: Name for ISON block
            params: Query parameters (for parameterized queries)

        Returns:
            ISON formatted string
        """
        conn = self.connect()
        cursor = conn.cursor()

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        lines = [f"table.{block_name}"]
        lines.append(' '.join(columns))

        for row in rows:
            values = [self._format_value(val) for val in row]
            lines.append(' '.join(values))

        cursor.close()
        return '\n'.join(lines)

    def stream_table(self, table: str, schema: str = None,
                     batch_size: int = 1000, where: str = None) -> Iterator[str]:
        """
        Stream a table as ISONL format.

        Uses server-side cursor for memory efficiency.

        Args:
            table: Table name
            schema: Schema name
            batch_size: Rows per batch
            where: Optional WHERE clause

        Yields:
            ISONL formatted lines
        """
        schema = schema or self.schema
        conn = self.connect()

        # Use server-side cursor for large results
        cursor = conn.cursor(name='ison_stream_cursor')

        columns = self.get_table_info(table, schema)
        field_names = [col['name'] for col in columns]
        fields_str = ' '.join(field_names)

        query = f'SELECT * FROM "{schema}"."{table}"'
        if where:
            query += f" WHERE {where}"

        cursor.execute(query)

        block_name = f"{schema}.{table}" if schema != 'public' else table

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for row in rows:
                values = []
                for i, col in enumerate(columns):
                    val = self._format_value(row[i], table, col['name'], schema)
                    values.append(val)

                yield f"table.{block_name}|{fields_str}|{' '.join(values)}"

        cursor.close()

    def export_with_relations(self, root_table: str, schema: str = None,
                              max_depth: int = 2) -> str:
        """
        Export a table with its related tables (following foreign keys).

        Args:
            root_table: Starting table
            schema: Schema name
            max_depth: How many levels of relations to follow

        Returns:
            ISON formatted string with all related tables
        """
        schema = schema or self.schema
        tables_to_export = set()
        tables_to_export.add(root_table)

        # Find related tables via foreign keys
        full_table = f"{schema}.{root_table}"
        if full_table in self._foreign_keys:
            for col, (ref_table, ref_col) in self._foreign_keys[full_table].items():
                # Extract table name from schema.table
                ref_table_name = ref_table.split('.')[-1]
                tables_to_export.add(ref_table_name)

        # Find tables that reference this table
        for fk_table, fks in self._foreign_keys.items():
            for col, (ref_table, ref_col) in fks.items():
                if ref_table == full_table or ref_table.endswith(f".{root_table}"):
                    table_name = fk_table.split('.')[-1]
                    tables_to_export.add(table_name)

        return self.export_tables(list(tables_to_export), schema)


# Convenience function
def postgresql_to_ison(connection_string: str,
                       tables: List[str] = None,
                       schema: str = 'public',
                       query: str = None) -> str:
    """
    Quick export from PostgreSQL to ISON.

    Args:
        connection_string: PostgreSQL connection string
        tables: Specific tables to export
        schema: Schema name
        query: Custom query (overrides tables)

    Returns:
        ISON formatted string
    """
    with PostgreSQLToISON(connection_string, schema=schema) as exporter:
        if query:
            return exporter.export_query(query)
        elif tables:
            return exporter.export_tables(tables)
        else:
            return exporter.export_all()
