"""
ISONantic - A Pydantic-like Data Validation Library for ISON

Provides type-safe models, validation, and reference resolution for ISON data.

Usage:
    from isonantic import TableModel, Field, Reference, parse_ison
    
    class User(TableModel):
        __ison_block__ = "table.users"
        id: int = Field(primary_key=True)
        name: str
        team: Reference["Team"]
    
    users = parse_ison(ison_data, User)

Author: Mahesh Vaikri
Version: 1.0.0
"""

from .models import (
    ISONModel,
    TableModel,
    ObjectModel,
    MetaModel,
)
from .fields import (
    Field,
    Reference,
    LazyReference,
    Nested,
)
from .document import ISONDocument
from .parsing import (
    parse_ison,
    parse_ison_safe,
    parse_llm_output,
    ParseResult,
)
from .validators import (
    validator,
    root_validator,
    computed,
)
from .exceptions import (
    ISONanticError,
    ValidationError,
    ReferenceError as ISONReferenceError,
    LLMParseError,
)
from .schema import (
    SchemaRegistry,
    generate_schema,
    prompt_for_model,
    document_json_schema,
    document_json_schema_json,
    openapi_schema,
)

__version__ = "1.0.0"
__all__ = [
    # Models
    "ISONModel",
    "TableModel", 
    "ObjectModel",
    "MetaModel",
    # Fields
    "Field",
    "Reference",
    "LazyReference",
    "Nested",
    # Document
    "ISONDocument",
    # Parsing
    "parse_ison",
    "parse_ison_safe",
    "parse_llm_output",
    "ParseResult",
    # Validators
    "validator",
    "root_validator",
    "computed",
    # Exceptions
    "ISONanticError",
    "ValidationError",
    "ISONReferenceError",
    "LLMParseError",
    # Schema
    "SchemaRegistry",
    "generate_schema",
    "prompt_for_model",
    "document_json_schema",
    "document_json_schema_json",
    "openapi_schema",
]
