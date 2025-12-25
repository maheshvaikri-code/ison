"""
ISONantic Schema

Schema generation, registry, and LLM prompting utilities.
"""

import json
from datetime import datetime
from typing import Any, Dict, get_args, get_origin, List, Optional, Type, Union

from .models import ISONModel, TableModel, ObjectModel
from .fields import FieldInfo, Reference, Nested
from .document import ISONDocument


class SchemaRegistry:
    """
    Registry for document schemas.
    
    Allows auto-detection of schema from ISON data.
    
    Usage:
        registry = SchemaRegistry()
        registry.register(ECommerceSchema)
        registry.register(InventorySchema)
        
        # Auto-detect schema from data
        doc = registry.parse(ison_data)
    """
    
    def __init__(self):
        self._schemas: Dict[str, Type[ISONDocument]] = {}
        self._block_mapping: Dict[frozenset, Type[ISONDocument]] = {}
    
    def register(self, schema: Type[ISONDocument]):
        """
        Register a document schema.
        
        Args:
            schema: ISONDocument subclass
        """
        name = schema.__name__
        self._schemas[name] = schema
        
        # Build block signature
        blocks = set()
        annotations = {}
        for cls in reversed(schema.__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                    blocks.add(args[0].__ison_block__)
        
        self._block_mapping[frozenset(blocks)] = schema
    
    def get_schema(self, name: str) -> Optional[Type[ISONDocument]]:
        """Get schema by name"""
        return self._schemas.get(name)
    
    def detect_schema(self, ison_data: str) -> Optional[Type[ISONDocument]]:
        """
        Detect schema from ISON data.
        
        Args:
            ison_data: ISON formatted string
            
        Returns:
            Matching schema class or None
        """
        from .parsing import _parse_ison_to_blocks
        
        blocks = _parse_ison_to_blocks(ison_data)
        block_names = frozenset(
            f"{b['kind']}.{b['name']}" for b in blocks
        )
        
        # Try exact match
        if block_names in self._block_mapping:
            return self._block_mapping[block_names]
        
        # Try subset match (data has required blocks)
        best_match = None
        best_score = 0
        
        for required_blocks, schema in self._block_mapping.items():
            if required_blocks.issubset(block_names):
                score = len(required_blocks)
                if score > best_score:
                    best_score = score
                    best_match = schema
        
        return best_match
    
    def parse(
        self,
        ison_data: str,
        schema: Type[ISONDocument] = None,
        **kwargs
    ) -> ISONDocument:
        """
        Parse ISON data with auto-detected or specified schema.
        
        Args:
            ison_data: ISON formatted string
            schema: Schema to use (auto-detect if None)
            **kwargs: Additional parse arguments
            
        Returns:
            Parsed document
        """
        if schema is None:
            schema = self.detect_schema(ison_data)
            if schema is None:
                raise ValueError("Could not detect schema for ISON data")
        
        return schema.parse(ison_data, **kwargs)


def generate_schema(model: Type[ISONModel]) -> str:
    """
    Generate ISON schema block for a model.
    
    Returns ISON-formatted schema definition.
    
    Args:
        model: Model class
        
    Returns:
        ISON schema string
    """
    lines = []
    
    # Schema header
    lines.append("meta.schema")
    lines.append("version generated_at")
    lines.append(f"1.0 {datetime.now().isoformat()}")
    lines.append("")
    
    # Columns table
    lines.append("table.columns")
    lines.append("field type nullable constraints")
    
    for field_name, field_info in model.__fields__.items():
        field_type = model.__field_types__.get(field_name, Any)
        
        # Get type string
        type_str = _type_to_string(field_type)
        
        # Nullable
        nullable = "true" if field_info.nullable else "false"
        
        # Constraints
        constraints = _constraints_to_string(field_info)
        
        lines.append(f"{field_name} {type_str} {nullable} {constraints}")
    
    return "\n".join(lines)


def generate_document_schema(doc_class: Type[ISONDocument]) -> str:
    """
    Generate ISON schema for a document.
    
    Returns complete schema including all blocks.
    
    Args:
        doc_class: ISONDocument subclass
        
    Returns:
        ISON schema string
    """
    lines = []
    
    # Schema header
    lines.append("meta.schema")
    lines.append("version generated_at")
    lines.append(f"1.0 {datetime.now().isoformat()}")
    lines.append("")
    
    # Tables list
    annotations = {}
    for cls in reversed(doc_class.__mro__):
        if hasattr(cls, "__annotations__"):
            annotations.update(cls.__annotations__)
    
    lines.append("table.tables")
    lines.append("name type")
    
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue
        
        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                model_cls = args[0]
                block_name = model_cls.__ison_block__.split(".")[-1]
                lines.append(f"{block_name} table")
    
    lines.append("")
    
    # Columns for each table
    lines.append("table.columns")
    lines.append("table_name column_name type nullable constraints")
    
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue
        
        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                model_cls = args[0]
                table_name = model_cls.__ison_block__.split(".")[-1]
                
                for mfield_name, mfield_info in model_cls.__fields__.items():
                    mfield_type = model_cls.__field_types__.get(mfield_name, Any)
                    type_str = _type_to_string(mfield_type)
                    nullable = "true" if mfield_info.nullable else "false"
                    constraints = _constraints_to_string(mfield_info)
                    
                    lines.append(f"{table_name} {mfield_name} {type_str} {nullable} {constraints}")
    
    return "\n".join(lines)


def prompt_for_model(model: Type[ISONModel]) -> str:
    """
    Generate prompt instructions for LLM to output model-compliant ISON.
    
    Args:
        model: Model class
        
    Returns:
        Prompt string describing expected format
    """
    lines = []
    lines.append(f"Output format (ISON):")
    lines.append(f"{model.__ison_block__}")
    
    # Fields
    fields = list(model.__fields__.keys())
    lines.append(" ".join(fields))
    
    # Example row with type hints
    type_hints = []
    for field_name in fields:
        field_info = model.__fields__[field_name]
        field_type = model.__field_types__.get(field_name, Any)
        
        hint = _type_to_hint(field_type, field_info)
        type_hints.append(hint)
    
    lines.append(" ".join(type_hints))
    
    # Add constraints info
    constraints_info = []
    for field_name, field_info in model.__fields__.items():
        constraint_parts = []
        
        if field_info.primary_key:
            constraint_parts.append("primary key")
        if field_info.ge is not None:
            constraint_parts.append(f">= {field_info.ge}")
        if field_info.le is not None:
            constraint_parts.append(f"<= {field_info.le}")
        if field_info.pattern:
            constraint_parts.append(f"pattern: {field_info.pattern}")
        if field_info.choices:
            constraint_parts.append(f"one of: {field_info.choices}")
        
        if constraint_parts:
            constraints_info.append(f"  {field_name}: {', '.join(constraint_parts)}")
    
    if constraints_info:
        lines.append("")
        lines.append("Constraints:")
        lines.extend(constraints_info)
    
    return "\n".join(lines)


def prompt_for_document(doc_class: Type[ISONDocument]) -> str:
    """
    Generate prompt instructions for LLM to output document-compliant ISON.
    
    Args:
        doc_class: ISONDocument subclass
        
    Returns:
        Prompt string describing expected format
    """
    parts = []
    parts.append("Output format (ISON document with multiple blocks):")
    parts.append("")
    
    annotations = {}
    for cls in reversed(doc_class.__mro__):
        if hasattr(cls, "__annotations__"):
            annotations.update(cls.__annotations__)
    
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue
        
        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                model_cls = args[0]
                parts.append(prompt_for_model(model_cls))
                parts.append("")
    
    return "\n".join(parts)


# Helper functions

def _type_to_string(field_type: Type) -> str:
    """Convert Python type to ISON type string"""
    origin = get_origin(field_type)
    args = get_args(field_type)
    
    # Handle Optional
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _type_to_string(non_none[0])
    
    # Handle Reference
    if origin is Reference or (isinstance(field_type, type) and issubclass(field_type, Reference)):
        if args:
            target = args[0]
            if hasattr(target, "__ison_block__"):
                return f"ref:{target.__ison_block__.split('.')[-1]}"
        return "ref"
    
    # Handle Nested
    if origin is Nested:
        if args:
            return f"nested:{args[0].__name__}"
        return "nested"
    
    # Handle List
    if origin is list:
        if args:
            return f"list[{_type_to_string(args[0])}]"
        return "list"
    
    # Basic types
    if field_type is int:
        return "int"
    if field_type is float:
        return "float"
    if field_type is str:
        return "str"
    if field_type is bool:
        return "bool"
    
    return "any"


def _type_to_hint(field_type: Type, field_info: FieldInfo) -> str:
    """Generate type hint for prompt"""
    origin = get_origin(field_type)
    args = get_args(field_type)
    
    # Handle Optional
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            base = _type_to_hint(non_none[0], field_info)
            return f"{base}?"
    
    # Handle Reference
    if origin is Reference or (isinstance(field_type, type) and issubclass(field_type, Reference)):
        if args:
            target = args[0]
            if hasattr(target, "__ison_block__"):
                return f"<ref:{target.__ison_block__.split('.')[-1]}>"
        return "<ref>"
    
    # Basic types with constraints
    if field_type is int:
        if field_info.ge is not None and field_info.le is not None:
            return f"<int {field_info.ge}-{field_info.le}>"
        return "<int>"
    
    if field_type is float:
        if field_info.ge is not None and field_info.le is not None:
            return f"<float {field_info.ge}-{field_info.le}>"
        return "<float>"
    
    if field_type is str:
        if field_info.choices:
            return f"<{'/'.join(str(c) for c in field_info.choices)}>"
        return "<str>"
    
    if field_type is bool:
        return "<true/false>"
    
    return "<any>"


def _constraints_to_string(field_info: FieldInfo) -> str:
    """Convert field constraints to string"""
    parts = []
    
    if field_info.primary_key:
        parts.append("primary_key")
    if field_info.unique:
        parts.append("unique")
    if field_info.ge is not None:
        parts.append(f"ge:{field_info.ge}")
    if field_info.gt is not None:
        parts.append(f"gt:{field_info.gt}")
    if field_info.le is not None:
        parts.append(f"le:{field_info.le}")
    if field_info.lt is not None:
        parts.append(f"lt:{field_info.lt}")
    if field_info.min_length is not None:
        parts.append(f"min_length:{field_info.min_length}")
    if field_info.max_length is not None:
        parts.append(f"max_length:{field_info.max_length}")
    if field_info.pattern:
        parts.append(f"pattern:{field_info.pattern}")
    
    if not parts:
        return "null"
    
    return f'"{";".join(parts)}"'


def document_json_schema(doc_class: Type[ISONDocument]) -> Dict[str, Any]:
    """
    Generate JSON Schema for an ISONDocument.
    
    Creates a schema with definitions for each model and
    a root object containing arrays of each type.
    
    Args:
        doc_class: ISONDocument subclass
        
    Returns:
        JSON Schema dictionary (OpenAPI compatible)
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": doc_class.__name__,
        "type": "object",
        "properties": {},
        "required": [],
        "$defs": {},
    }
    
    if doc_class.__doc__:
        schema["description"] = doc_class.__doc__.strip()
    
    # Get annotations
    annotations = {}
    for cls in reversed(doc_class.__mro__):
        if hasattr(cls, "__annotations__"):
            annotations.update(cls.__annotations__)
    
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue
        
        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                model_cls = args[0]
                model_name = model_cls.__name__
                
                # Add model to definitions
                if model_name not in schema["$defs"]:
                    schema["$defs"][model_name] = model_cls.model_json_schema()
                    # Remove $schema from nested definitions
                    schema["$defs"][model_name].pop("$schema", None)
                
                # Reference in properties
                schema["properties"][field_name] = {
                    "type": "array",
                    "items": {"$ref": f"#/$defs/{model_name}"}
                }
                
                # Check if required (no default)
                default = getattr(doc_class, field_name, None)
                if default is None:
                    schema["required"].append(field_name)
    
    return schema


def document_json_schema_json(doc_class: Type[ISONDocument], indent: int = 2) -> str:
    """
    Generate JSON Schema for document as JSON string.
    """
    return json.dumps(document_json_schema(doc_class), indent=indent)


def openapi_schema(doc_class: Type[ISONDocument]) -> Dict[str, Any]:
    """
    Generate OpenAPI-compatible schema components.
    
    Returns a dict suitable for OpenAPI 3.x components/schemas section.
    
    Args:
        doc_class: ISONDocument subclass
        
    Returns:
        Dict with 'schemas' key containing all model schemas
    """
    schemas = {}
    
    annotations = {}
    for cls in reversed(doc_class.__mro__):
        if hasattr(cls, "__annotations__"):
            annotations.update(cls.__annotations__)
    
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue
        
        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                model_cls = args[0]
                model_schema = model_cls.model_json_schema()
                # Remove $schema for OpenAPI compatibility
                model_schema.pop("$schema", None)
                schemas[model_cls.__name__] = model_schema
    
    return {"schemas": schemas}
