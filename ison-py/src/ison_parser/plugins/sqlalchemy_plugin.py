#!/usr/bin/env python3
"""
SQLAlchemy to ISON Plugin
Export any SQLAlchemy-supported database to ISON format.

Supports: MySQL, MariaDB, PostgreSQL, SQLite, Oracle, MS SQL Server, and more.

Requires: sqlalchemy
    pip install sqlalchemy

For specific databases, you'll also need the appropriate driver:
    pip install pymysql        # MySQL
    pip install psycopg2       # PostgreSQL
    pip install cx_Oracle      # Oracle
    pip install pyodbc         # MS SQL Server

Usage:
    from ison_parser.plugins import SQLAlchemyToISON

    # Connect with any SQLAlchemy connection string
    exporter = SQLAlchemyToISON('mysql+pymysql://user:pass@localhost/mydb')
    exporter = SQLAlchemyToISON('postgresql://user:pass@localhost/mydb')
    exporter = SQLAlchemyToISON('sqlite:///mydb.sqlite')
    exporter = SQLAlchemyToISON('mssql+pyodbc://user:pass@server/db?driver=...')

    # Export all tables
    ison_text = exporter.export_all()

    # Export ORM models
    ison_text = exporter.export_model(User)

    # Stream large results
    for line in exporter.stream_query(session.query(LogEntry)):
        process(line)
"""

from typing import List, Optional, Dict, Any, Iterator, Union, Type
from datetime import datetime, date
import json


class SQLAlchemyToISON:
    """Export SQLAlchemy databases/models to ISON format."""

    def __init__(self, connection_string: str = None,
                 engine=None,
                 detect_references: bool = True):
        """
        Initialize SQLAlchemy exporter.

        Args:
            connection_string: SQLAlchemy connection URL
            engine: Existing SQLAlchemy engine (alternative to connection_string)
            detect_references: Auto-detect foreign keys
        """
        self.connection_string = connection_string
        self._engine = engine
        self.detect_references = detect_references
        self._metadata = None
        self._foreign_keys: Dict[str, Dict[str, tuple]] = {}

    @property
    def engine(self):
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            try:
                from sqlalchemy import create_engine
            except ImportError:
                raise ImportError(
                    "SQLAlchemy is required. Install with: pip install sqlalchemy"
                )
            self._engine = create_engine(self.connection_string)
        return self._engine

    @property
    def metadata(self):
        """Get reflected metadata."""
        if self._metadata is None:
            from sqlalchemy import MetaData
            self._metadata = MetaData()
            self._metadata.reflect(bind=self.engine)
            if self.detect_references:
                self._load_foreign_keys()
        return self._metadata

    def _load_foreign_keys(self):
        """Load foreign key relationships from metadata."""
        for table_name, table in self.metadata.tables.items():
            for fk in table.foreign_keys:
                if table_name not in self._foreign_keys:
                    self._foreign_keys[table_name] = {}
                col_name = fk.parent.name
                ref_table = fk.column.table.name
                ref_col = fk.column.name
                self._foreign_keys[table_name][col_name] = (ref_table, ref_col)

    def close(self):
        """Dispose engine connection pool."""
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_tables(self) -> List[str]:
        """Get list of all tables."""
        return list(self.metadata.tables.keys())

    def _format_value(self, value: Any, table: str = None,
                      column: str = None) -> str:
        """Format a value for ISON output."""
        if value is None:
            return '~'

        # Check foreign key reference
        if (table and column and self.detect_references and
            table in self._foreign_keys and
            column in self._foreign_keys[table]):
            return f':{value}'

        if isinstance(value, bool):
            return 'true' if value else 'false'

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, date):
            return value.isoformat()

        if isinstance(value, (list, tuple)):
            items = [self._format_value(v) for v in value]
            return '[' + ','.join(items) + ']'

        if isinstance(value, dict):
            return '"' + json.dumps(value).replace('"', '\\"') + '"'

        # Bytes
        if isinstance(value, bytes):
            try:
                return self._format_value(value.decode('utf-8'))
            except UnicodeDecodeError:
                import base64
                return '"base64:' + base64.b64encode(value).decode() + '"'

        # String
        str_val = str(value)
        if ' ' in str_val or '\n' in str_val or '\t' in str_val or '"' in str_val:
            escaped = str_val.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'

        return str_val

    def _get_ison_type(self, sa_type) -> Optional[str]:
        """Map SQLAlchemy type to ISON type annotation."""
        from sqlalchemy import types

        if isinstance(sa_type, (types.Integer, types.BigInteger, types.SmallInteger)):
            return 'int'
        if isinstance(sa_type, (types.Float, types.Numeric, types.DECIMAL)):
            return 'float'
        if isinstance(sa_type, types.Boolean):
            return 'bool'
        if isinstance(sa_type, types.Date):
            return 'date'
        if isinstance(sa_type, (types.DateTime, types.TIMESTAMP)):
            return 'datetime'
        if isinstance(sa_type, types.JSON):
            return 'json'
        if isinstance(sa_type, types.ARRAY):
            return 'array'

        return None

    def export_table(self, table_name: str, where: str = None,
                     include_types: bool = True) -> str:
        """
        Export a single table to ISON format.

        Args:
            table_name: Table name
            where: Optional WHERE clause (raw SQL)
            include_types: Include type annotations

        Returns:
            ISON formatted string
        """
        from sqlalchemy import select, text

        table = self.metadata.tables[table_name]
        columns = list(table.columns)

        # Build field names
        fields = []
        for col in columns:
            field = col.name
            if include_types:
                ison_type = self._get_ison_type(col.type)
                if ison_type:
                    field = f"{col.name}:{ison_type}"
            fields.append(field)

        # Query
        stmt = select(table)
        if where:
            stmt = stmt.where(text(where))

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            rows = result.fetchall()

        # Build ISON
        lines = [f"table.{table_name}"]
        lines.append(' '.join(fields))

        for row in rows:
            values = []
            for i, col in enumerate(columns):
                val = self._format_value(row[i], table_name, col.name)
                values.append(val)
            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_tables(self, tables: List[str],
                      include_types: bool = True) -> str:
        """Export multiple tables to ISON format."""
        blocks = []
        for table in tables:
            blocks.append(self.export_table(table, include_types=include_types))
        return '\n\n'.join(blocks)

    def export_all(self, include_types: bool = True) -> str:
        """Export all tables to ISON format."""
        tables = self.get_tables()
        return self.export_tables(tables, include_types=include_types)

    def export_query(self, query, block_name: str = 'query_result',
                     params: dict = None) -> str:
        """
        Export raw SQL query results to ISON.

        Args:
            query: SQL query string or SQLAlchemy text() object
            block_name: Name for ISON block
            params: Query parameters

        Returns:
            ISON formatted string
        """
        from sqlalchemy import text

        if isinstance(query, str):
            query = text(query)

        with self.engine.connect() as conn:
            if params:
                result = conn.execute(query, params)
            else:
                result = conn.execute(query)

            columns = list(result.keys())
            rows = result.fetchall()

        lines = [f"table.{block_name}"]
        lines.append(' '.join(columns))

        for row in rows:
            values = [self._format_value(val) for val in row]
            lines.append(' '.join(values))

        return '\n'.join(lines)

    def export_model(self, model_class: Type, session=None,
                     filters=None, include_types: bool = True) -> str:
        """
        Export SQLAlchemy ORM model to ISON.

        Args:
            model_class: SQLAlchemy ORM model class
            session: SQLAlchemy session
            filters: Optional filter conditions
            include_types: Include type annotations

        Returns:
            ISON formatted string
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm import Session

        if session is None:
            session = Session(self.engine)
            own_session = True
        else:
            own_session = False

        try:
            mapper = inspect(model_class)
            table_name = mapper.mapped_table.name
            columns = list(mapper.columns)

            # Build fields
            fields = []
            col_names = []
            for col in columns:
                col_names.append(col.name)
                field = col.name
                if include_types:
                    ison_type = self._get_ison_type(col.type)
                    if ison_type:
                        field = f"{col.name}:{ison_type}"
                fields.append(field)

            # Query
            query = session.query(model_class)
            if filters is not None:
                query = query.filter(filters)

            rows = query.all()

            # Build ISON
            lines = [f"table.{table_name}"]
            lines.append(' '.join(fields))

            for obj in rows:
                values = []
                for col_name in col_names:
                    val = getattr(obj, col_name)
                    values.append(self._format_value(val, table_name, col_name))
                lines.append(' '.join(values))

            return '\n'.join(lines)

        finally:
            if own_session:
                session.close()

    def export_models(self, model_classes: List[Type], session=None,
                      include_types: bool = True) -> str:
        """Export multiple ORM models."""
        blocks = []
        for model in model_classes:
            blocks.append(self.export_model(model, session, include_types=include_types))
        return '\n\n'.join(blocks)

    def stream_table(self, table_name: str, batch_size: int = 1000,
                     where: str = None) -> Iterator[str]:
        """
        Stream a table as ISONL format.

        Args:
            table_name: Table name
            batch_size: Rows per batch
            where: Optional WHERE clause

        Yields:
            ISONL formatted lines
        """
        from sqlalchemy import select, text

        table = self.metadata.tables[table_name]
        columns = list(table.columns)
        field_names = [col.name for col in columns]
        fields_str = ' '.join(field_names)

        stmt = select(table)
        if where:
            stmt = stmt.where(text(where))

        with self.engine.connect() as conn:
            result = conn.execution_options(stream_results=True).execute(stmt)

            while True:
                rows = result.fetchmany(batch_size)
                if not rows:
                    break

                for row in rows:
                    values = []
                    for i, col in enumerate(columns):
                        val = self._format_value(row[i], table_name, col.name)
                        values.append(val)

                    yield f"table.{table_name}|{fields_str}|{' '.join(values)}"

    def stream_query(self, query, block_name: str = 'query_result',
                     batch_size: int = 1000) -> Iterator[str]:
        """
        Stream ORM query results as ISONL.

        Args:
            query: SQLAlchemy ORM query
            block_name: Block name for ISONL lines
            batch_size: Rows per batch

        Yields:
            ISONL formatted lines
        """
        # Get column info from first result
        columns = None
        fields_str = None

        for obj in query.yield_per(batch_size):
            if columns is None:
                from sqlalchemy import inspect
                mapper = inspect(type(obj))
                columns = [col.name for col in mapper.columns]
                fields_str = ' '.join(columns)

            values = []
            for col_name in columns:
                val = getattr(obj, col_name)
                values.append(self._format_value(val))

            yield f"table.{block_name}|{fields_str}|{' '.join(values)}"

    def export_with_relations(self, table_name: str,
                              max_depth: int = 1) -> str:
        """
        Export table with related tables.

        Args:
            table_name: Starting table
            max_depth: Levels of relations to follow

        Returns:
            ISON with all related tables
        """
        tables_to_export = {table_name}

        # Find tables this references
        if table_name in self._foreign_keys:
            for col, (ref_table, _) in self._foreign_keys[table_name].items():
                tables_to_export.add(ref_table)

        # Find tables that reference this
        for fk_table, fks in self._foreign_keys.items():
            for col, (ref_table, _) in fks.items():
                if ref_table == table_name:
                    tables_to_export.add(fk_table)

        return self.export_tables(list(tables_to_export))


# Convenience function
def sqlalchemy_to_ison(connection_string: str,
                       tables: List[str] = None,
                       query: str = None) -> str:
    """
    Quick export from any SQLAlchemy-supported database to ISON.

    Args:
        connection_string: SQLAlchemy connection URL
        tables: Specific tables to export
        query: Custom SQL query

    Returns:
        ISON formatted string
    """
    with SQLAlchemyToISON(connection_string) as exporter:
        if query:
            return exporter.export_query(query)
        elif tables:
            return exporter.export_tables(tables)
        else:
            return exporter.export_all()
