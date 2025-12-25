"""
ISON Data Source Plugins
Export data from databases and vector stores to ISON format for LLM workflows.

SQL Database Plugins:
- sqlite: SQLite database support (zero dependencies)
- postgresql: PostgreSQL support (requires psycopg2)
- sqlalchemy: Generic SQL support (requires sqlalchemy)

Vector Database Plugins:
- chroma: ChromaDB support (requires chromadb)
- pinecone: Pinecone support (requires pinecone-client)
- qdrant: Qdrant support (requires qdrant-client)

Specialized Database Plugins:
- rudradb: RudraDB support (requires rudradb)
"""

# SQL Database plugins
from .sqlite_plugin import SQLiteToISON
from .postgresql_plugin import PostgreSQLToISON
from .sqlalchemy_plugin import SQLAlchemyToISON

# Vector Database plugins (lazy loaded to avoid import errors)
def __getattr__(name):
    """Lazy load optional database plugins."""
    if name == 'ChromaToISON':
        from .chroma_plugin import ChromaToISON
        return ChromaToISON
    elif name == 'PineconeToISON':
        from .pinecone_plugin import PineconeToISON
        return PineconeToISON
    elif name == 'QdrantToISON':
        from .qdrant_plugin import QdrantToISON
        return QdrantToISON
    elif name == 'RudraDBToISON':
        from .rudradb_plugin import RudraDBToISON
        return RudraDBToISON
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # SQL Databases
    'SQLiteToISON',
    'PostgreSQLToISON',
    'SQLAlchemyToISON',
    # Vector Databases
    'ChromaToISON',
    'PineconeToISON',
    'QdrantToISON',
    # Specialized Databases
    'RudraDBToISON',
]
