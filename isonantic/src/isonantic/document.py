"""
ISONantic Document

Multi-block document schema and reference resolution.
"""

from typing import (
    Any, ClassVar, Dict, Generic, get_args, get_origin,
    List, Optional, Set, Type, TypeVar, Union,
)

import json
from .models import ISONModel, TableModel, ObjectModel, MetaModel
from .fields import Reference, FieldInfo
from .exceptions import ReferenceError, ValidationError, SchemaError


T = TypeVar("T", bound=ISONModel)


class ISONDocument:
    """
    Multi-block ISON document with reference resolution.
    
    Define a document schema by inheriting and declaring typed fields
    for each block.
    
    Usage:
        class MyDocument(ISONDocument):
            users: List[User]
            teams: List[Team]
            orders: List[Order] = []  # Optional block
            
            class Config:
                block_order = ["teams", "users", "orders"]
        
        doc = MyDocument.parse(ison_data)
        print(doc.users[0].team.resolve(doc).name)
    """
    
    __blocks__: ClassVar[Dict[str, Type[ISONModel]]] = {}
    __block_fields__: ClassVar[Dict[str, str]] = {}  # Maps block name to field name
    
    class Config:
        block_order: List[str] = []  # Order for parsing (for reference resolution)
        validate_refs: bool = True  # Validate all references exist
        resolve_refs: bool = False  # Auto-resolve references
    
    def __init__(self, **data: Any):
        """
        Initialize document with block data.
        
        Args:
            **data: Block data keyed by field name
        """
        # Get annotations
        annotations = {}
        for cls in reversed(type(self).__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        # Process each block field
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            
            # Get value or default
            if field_name in data:
                value = data[field_name]
            else:
                # Check for default
                default = getattr(type(self), field_name, None)
                if default is not None:
                    value = default if isinstance(default, list) else []
                else:
                    value = []
            
            setattr(self, field_name, value)
        
        # Build reference index
        self._ref_index: Dict[str, Dict[str, ISONModel]] = {}
        self._build_ref_index()
    
    def _build_ref_index(self):
        """Build index for reference resolution"""
        annotations = {}
        for cls in reversed(type(self).__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            
            # Get model type from List[Model]
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and issubclass(args[0], ISONModel):
                    model_cls = args[0]
                    models = getattr(self, field_name, [])
                    
                    # Get block name
                    block_name = model_cls.__ison_block__.split(".")[-1]
                    self._ref_index[block_name] = {}
                    
                    # Index by primary key
                    pk_field = model_cls.get_primary_key_field()
                    if pk_field:
                        for model in models:
                            pk_value = getattr(model, pk_field, None)
                            if pk_value is not None:
                                self._ref_index[block_name][str(pk_value)] = model
    
    def _resolve_reference(self, ref: Reference) -> Optional[ISONModel]:
        """
        Resolve a reference to its target model.
        
        Args:
            ref: Reference to resolve
            
        Returns:
            Resolved model or None
            
        Raises:
            ReferenceError: If reference not found
        """
        # Try namespaced lookup first
        if ref.ref_type and ref.ref_type in self._ref_index:
            index = self._ref_index[ref.ref_type]
            if ref.id in index:
                return index[ref.id]
        
        # Try all indexes
        for block_name, index in self._ref_index.items():
            if ref.id in index:
                return index[ref.id]
        
        # Not found
        raise ReferenceError(
            ref_id=ref.id,
            ref_type=ref.ref_type,
            target_block="unknown",
            source_block="unknown",
            source_row=0,
            source_field="unknown",
            available_ids=list(self._get_all_ids())
        )
    
    def _get_all_ids(self) -> Set[str]:
        """Get all known IDs across all blocks"""
        ids = set()
        for index in self._ref_index.values():
            ids.update(index.keys())
        return ids
    
    def validate_references(self) -> List[Dict[str, Any]]:
        """
        Validate all references in the document.
        
        Returns:
            List of reference errors
        """
        errors = []
        annotations = {}
        for cls in reversed(type(self).__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            
            models = getattr(self, field_name, [])
            if not isinstance(models, list):
                continue
            
            for row_idx, model in enumerate(models):
                if not isinstance(model, ISONModel):
                    continue
                
                # Check each field for references
                for mfield_name, mfield_info in model.__fields__.items():
                    value = getattr(model, mfield_name, None)
                    
                    if isinstance(value, Reference):
                        try:
                            self._resolve_reference(value)
                        except ReferenceError as e:
                            errors.append({
                                "loc": (field_name, row_idx, mfield_name),
                                "msg": str(e),
                                "type": "reference_error",
                                "ref_id": value.id,
                            })
                    
                    elif isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, Reference):
                                try:
                                    self._resolve_reference(item)
                                except ReferenceError as e:
                                    errors.append({
                                        "loc": (field_name, row_idx, mfield_name, i),
                                        "msg": str(e),
                                        "type": "reference_error",
                                        "ref_id": item.id,
                                    })
        
        return errors
    
    @classmethod
    def parse(
        cls,
        ison_data: str,
        *,
        strict: bool = False,
        validate: bool = True,
        resolve_refs: bool = False,
    ) -> "ISONDocument":
        """
        Parse ISON data into a document.
        
        Args:
            ison_data: ISON formatted string
            strict: Raise on unknown fields/blocks
            validate: Enable validation
            resolve_refs: Auto-resolve references
            
        Returns:
            ISONDocument instance
        """
        from .parsing import _parse_ison_to_blocks
        
        # Parse raw ISON
        blocks = _parse_ison_to_blocks(ison_data)
        
        # Get annotations
        annotations = {}
        for klass in reversed(cls.__mro__):
            if hasattr(klass, "__annotations__"):
                annotations.update(klass.__annotations__)
        
        # Build model mapping
        model_mapping: Dict[str, tuple[str, Type[ISONModel]]] = {}
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and isinstance(args[0], type) and issubclass(args[0], ISONModel):
                    model_cls = args[0]
                    block_name = model_cls.__ison_block__
                    model_mapping[block_name] = (field_name, model_cls)
        
        # Convert blocks to models
        data = {}
        for block in blocks:
            full_name = f"{block['kind']}.{block['name']}"
            
            if full_name in model_mapping:
                field_name, model_cls = model_mapping[full_name]
                
                models = []
                for row in block["rows"]:
                    try:
                        model = model_cls(**row)
                        models.append(model)
                    except ValidationError as e:
                        if validate:
                            raise
                        # Skip invalid rows
                
                data[field_name] = models
            elif strict:
                raise SchemaError(f"Unknown block: {full_name}")
        
        # Create document
        doc = cls(**data)
        
        # Validate references
        if validate:
            config = getattr(cls, "Config", None)
            if config and getattr(config, "validate_refs", True):
                ref_errors = doc.validate_references()
                if ref_errors:
                    raise ValidationError(ref_errors, model=cls)
        
        return doc
    
    def to_ison(self, *, align: bool = True) -> str:
        """
        Serialize document to ISON format.
        
        Args:
            align: Align columns
            
        Returns:
            ISON formatted string
        """
        parts = []
        
        # Get block order from config or use annotation order
        config = getattr(type(self), "Config", None)
        block_order = getattr(config, "block_order", None) if config else None
        
        annotations = {}
        for cls in reversed(type(self).__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        if block_order:
            field_names = [f for f in block_order if f in annotations]
            # Add any remaining
            for f in annotations:
                if f not in field_names and not f.startswith("_"):
                    field_names.append(f)
        else:
            field_names = [f for f in annotations if not f.startswith("_")]
        
        for field_name in field_names:
            models = getattr(self, field_name, [])
            if not models:
                continue
            
            if isinstance(models, list) and models:
                model_cls = type(models[0])
                if hasattr(model_cls, "to_ison_table"):
                    parts.append(model_cls.to_ison_table(models, align=align))
            elif isinstance(models, ISONModel):
                if hasattr(models, "to_ison"):
                    parts.append(models.to_ison())
        
        return "\n\n".join(parts)
    
    def dict(self) -> Dict[str, Any]:
        """Convert document to dictionary"""
        result = {}
        
        annotations = {}
        for cls in reversed(type(self).__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        for field_name in annotations:
            if field_name.startswith("_"):
                continue
            
            value = getattr(self, field_name, None)
            
            if isinstance(value, list):
                result[field_name] = [
                    m.dict() if isinstance(m, ISONModel) else m
                    for m in value
                ]
            elif isinstance(value, ISONModel):
                result[field_name] = value.dict()
            else:
                result[field_name] = value
        
        return result
    
    def json(self, *, indent: int = None) -> str:
        """
        Serialize document to JSON string.
        
        Args:
            indent: JSON indentation
        """
        return json.dumps(self.dict(), indent=indent, default=str)
    
    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        """
        Generate JSON Schema for this document.
        
        Returns a schema with definitions for each model.
        """
        from .schema import document_json_schema
        return document_json_schema(cls)
    
    @classmethod
    def model_json_schema_json(cls, indent: int = 2) -> str:
        """
        Generate JSON Schema as JSON string.
        """
        return json.dumps(cls.model_json_schema(), indent=indent)
    
    # Pydantic v1 compatibility
    @classmethod
    def schema(cls) -> Dict[str, Any]:
        """Alias for model_json_schema()"""
        return cls.model_json_schema()
    
    @classmethod
    def schema_json(cls, indent: int = 2) -> str:
        """Alias for model_json_schema_json()"""
        return cls.model_json_schema_json(indent)
    
    def __repr__(self) -> str:
        annotations = {}
        for cls in reversed(type(self).__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        
        parts = []
        for field_name in annotations:
            if field_name.startswith("_"):
                continue
            value = getattr(self, field_name, None)
            if isinstance(value, list):
                parts.append(f"{field_name}=[{len(value)} items]")
            else:
                parts.append(f"{field_name}={value!r}")
        
        return f"{type(self).__name__}({', '.join(parts)})"
