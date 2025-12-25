#!/usr/bin/env python3
"""
SQLite to ISON Plugin
Export SQLite databases to ISON format for LLM workflows.

Zero external dependencies - uses Python's built-in sqlite3 module.

Usage:
    from ison_parser.plugins import SQLiteToISON

    # Export entire database
    exporter = SQLiteToISON('mydb.sqlite')
    ison_text = exporter.export_all()

    # Export specific tables
    ison_text = exporter.export_tables(['users', 'orders'])

    # Export with query
    ison_text = exporter.export_query('SELECT * FROM users WHERE active = 1')

    # Stream large tables as ISONL
    for line in exporter.stream_table('logs'):
        print(line)
"""

import sqlite3
from typing import List, Optional, Dict, Any, Iterator, Union
from pathlib import Path


class SQLiteToISON:
    """Export SQLite database to ISON format."""

    def __init__(self, db_path: Union[str, Path], detect_references: bool = True):
        """
        Initialize SQLite exporter.

        Args:
            db_path: Path to SQLite database file, or ':memory:' for in-memory
            detect_references: Auto-detect foreign keys and convert to ISON references
        """
        self.db_path = str(db_path)
        self.detect_references = detect_references
        self._conn: Optional[sqlite3.Connection] = None
        self._foreign_keys: Dict[str, Dict[str, tuple]] = {}

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
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
        """Load foreign key relationships from schema."""
        conn = self.connect()
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fks = cursor.fetchall()
            if fks:
                self._foreign_keys[table] = {}
                for fk in fks:
                    # fk: (id, seq, table, from, to, on_update, on_delete, match)
                    from_col = fk[3]
                    to_table = fk[2]
                    self._foreign_keys[table][from_col] = (to_table, fk[4])

    def get_tables(self) -> List[str]:
        """Get list of all tables in database."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        return [row[0] for row in cursor.fetchall()]

    def get_table_info(self, table: str) -> List[Dict[str, Any]]:
        """Get column information for a table."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default': row[4],
                'pk': bool(row[5])
            })
        return columns

    def _format_value(self, value: Any, table: str = None, column: str = None) -> str:
        """Format a value for ISON output."""
        if value is None:
            return '~'

        # Check if this is a foreign key reference
        if (table and column and self.detect_references and
            table in self._foreign_keys and
            column in self._foreign_keys[table]):
            # Convert to ISON reference
            return f':{value}'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, (int, float)):
            return str(value)

        # String value - quote if contains spaces or special chars
        str_val = str(value)
        if ' ' in str_val or '\n' in str_val or '\t' in str_val or '"' in str_val:
            # Escape quotes and wrap
            escaped = str_val.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'

        return str_val

    def _get_ison_type(self, sql_type: str) -> Optional[str]:
        """Map SQL type to ISON type annotation."""
        sql_type = sql_type.upper()
        if 'INT' in sql_type:
            return 'int'
        if 'REAL' in sql_type or 'FLOAT' in sql_type or 'DOUBLE' in sql_type:
            return 'float'
        if 'BOOL' in sql_type:
            return 'bool'
        if 'DATE' in sql_type:
            return 'date'
        if 'TIME' in sql_type:
            return 'datetime'
        # TEXT, VARCHAR, etc. - no annotation needed (default is string)
        return None

    def export_table(self, table: str, where: str = None,
                     include_types: bool = True) -> str:
        """
        Export a single table to ISON format.

        Args:
            table: Table name
            where: Optional WHERE clause (without 'WHERE' keyword)
            include_types: Include type annotations in field names

        Returns:
            ISON formatted string
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Get column info
        columns = self.get_table_info(table)

        # Build field names with optional type annotations
        fields = []
        for col in columns:
            field = col['name']
            if include_types:
                ison_type = self._get_ison_type(col['type'])
                if ison_type:
                    field = f"{col['name']}:{ison_type}"
            fields.append(field)

        # Query data
        query = f"SELECT * FROM {table}"
        if where:
            query += f" WHERE {where}"

        cursor.execute(query)
        rows = cursor.fetchall()

        # Build ISON output
        lines = [f"table.{table}"]
        lines.append(' '.join(fields))

        for row in rows:
            values = []
            for i, col in enumerate(columns):
                val = self._format_value(row[i], table, col['name'])
                values.append(val)
            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_tables(self, tables: List[str], include_types: bool = True) -> str:
        """
        Export multiple tables to ISON format.

        Args:
            tables: List of table names
            include_types: Include type annotations

        Returns:
            ISON formatted string with all tables
        """
        blocks = []
        for table in tables:
            blocks.append(self.export_table(table, include_types=include_types))
        return '\n\n'.join(blocks)

    def export_all(self, include_types: bool = True) -> str:
        """
        Export all tables in the database to ISON format.

        Args:
            include_types: Include type annotations

        Returns:
            ISON formatted string with all tables
        """
        tables = self.get_tables()
        return self.export_tables(tables, include_types=include_types)

    def export_query(self, query: str, block_name: str = 'query_result',
                     include_types: bool = False) -> str:
        """
        Export query results to ISON format.

        Args:
            query: SQL query to execute
            block_name: Name for the ISON block
            include_types: Include type annotations (limited for queries)

        Returns:
            ISON formatted string
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query)

        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        # Build ISON output
        lines = [f"table.{block_name}"]
        lines.append(' '.join(columns))

        for row in rows:
            values = [self._format_value(val) for val in row]
            lines.append(' '.join(values))

        return '\n'.join(lines)

    def stream_table(self, table: str, batch_size: int = 1000,
                     where: str = None) -> Iterator[str]:
        """
        Stream a table as ISONL (one record per line).

        Useful for large tables that don't fit in memory.

        Args:
            table: Table name
            batch_size: Number of rows to fetch at a time
            where: Optional WHERE clause

        Yields:
            ISONL formatted lines
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Get column info
        columns = self.get_table_info(table)
        field_names = [col['name'] for col in columns]
        fields_str = ' '.join(field_names)

        # Query data
        query = f"SELECT * FROM {table}"
        if where:
            query += f" WHERE {where}"

        cursor.execute(query)

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for row in rows:
                values = []
                for i, col in enumerate(columns):
                    val = self._format_value(row[i], table, col['name'])
                    values.append(val)

                # ISONL format: kind.name|fields|values
                yield f"table.{table}|{fields_str}|{' '.join(values)}"

    def export_schema(self) -> str:
        """
        Export database schema as ISON meta blocks.

        Returns:
            ISON formatted schema description
        """
        tables = self.get_tables()
        lines = ['meta.schema']
        lines.append('table columns primary_key foreign_keys')

        for table in tables:
            columns = self.get_table_info(table)
            col_names = [c['name'] for c in columns]
            pk_cols = [c['name'] for c in columns if c['pk']]

            fks = []
            if table in self._foreign_keys:
                for col, (ref_table, ref_col) in self._foreign_keys[table].items():
                    fks.append(f"{col}->{ref_table}.{ref_col}")

            cols_str = ','.join(col_names)
            pk_str = ','.join(pk_cols) if pk_cols else '~'
            fk_str = ','.join(fks) if fks else '~'

            lines.append(f'{table} "{cols_str}" {pk_str} "{fk_str}"')

        return '\n'.join(lines)

    def to_ison_document(self, tables: List[str] = None):
        """
        Export to an ISON Document object.

        Args:
            tables: List of tables to export (None for all)

        Returns:
            ISON Document object
        """
        # Import here to avoid circular dependency
        import ison_parser

        if tables is None:
            tables = self.get_tables()

        ison_text = self.export_tables(tables)
        return ison_parser.loads(ison_text)


# Convenience function
def sqlite_to_ison(db_path: Union[str, Path],
                   tables: List[str] = None,
                   query: str = None) -> str:
    """
    Quick export from SQLite to ISON.

    Args:
        db_path: Path to SQLite database
        tables: Specific tables to export (None for all)
        query: Custom query to export (overrides tables)

    Returns:
        ISON formatted string
    """
    with SQLiteToISON(db_path) as exporter:
        if query:
            return exporter.export_query(query)
        elif tables:
            return exporter.export_tables(tables)
        else:
            return exporter.export_all()
