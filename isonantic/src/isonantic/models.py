"""
ISONantic Models

Base model classes for ISON data structures.
"""

from abc import ABC, abstractmethod
from typing import (
    Any, ClassVar, Dict, Generic, get_args, get_origin,
    List, Optional, Set, Type, TypeVar, Union,
)
import copy
import json
from dataclasses import dataclass, field as dataclass_field

from .fields import Field, FieldInfo, Reference, Nested
from .validators import (
    run_validators, run_root_validators,
    collect_validators, collect_computed_fields,
)
from .exceptions import ValidationError, FieldError


T = TypeVar("T", bound="ISONModel")


class ModelConfig:
    """
    Configuration for ISONantic models.
    
    Similar to Pydantic's Config class.
    """
    # Validation options
    strict: bool = False  # Strict type checking
    extra: str = "ignore"  # "allow", "ignore", "forbid"
    validate_assignment: bool = False  # Validate on attribute set
    
    # Serialization options
    ison_align: bool = True  # Align columns in output
    ison_comments: bool = False  # Include field comments
    
    # Reference options
    resolve_refs: bool = False  # Auto-resolve references
    
    # Populate by name or alias
    populate_by_name: bool = True


class ModelMetaclass(type):
    """
    Metaclass for ISONantic models.
    
    Collects field definitions and validators at class creation.
    """
    
    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: dict,
        **kwargs
    ) -> type:
        # Get annotations from class and bases
        annotations = {}
        for base in reversed(bases):
            if hasattr(base, "__annotations__"):
                annotations.update(base.__annotations__)
        annotations.update(namespace.get("__annotations__", {}))
        
        # Collect field info
        fields: Dict[str, FieldInfo] = {}
        field_types: Dict[str, Type] = {}
        
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            
            # Get default value or FieldInfo
            default = namespace.get(field_name, ...)
            
            if isinstance(default, FieldInfo):
                fields[field_name] = default
            elif default is not ...:
                # Create FieldInfo with default
                fields[field_name] = FieldInfo(default=default)
            else:
                # Required field
                fields[field_name] = FieldInfo()
            
            field_types[field_name] = field_type
        
        # Store on class
        namespace["__fields__"] = fields
        namespace["__field_types__"] = field_types
        namespace["__annotations__"] = annotations
        
        # Get or create Config
        config = namespace.get("Config", None)
        if config is None:
            # Look in bases
            for base in bases:
                if hasattr(base, "__config__"):
                    config = base.__config__
                    break
        if config is None:
            config = ModelConfig
        namespace["__config__"] = config
        
        cls = super().__new__(mcs, name, bases, namespace)
        return cls


class ISONModel(metaclass=ModelMetaclass):
    """
    Base class for all ISONantic models.
    
    Provides validation, serialization, and field access.
    """
    
    __ison_block__: ClassVar[str] = ""  # Override in subclass
    __fields__: ClassVar[Dict[str, FieldInfo]] = {}
    __field_types__: ClassVar[Dict[str, Type]] = {}
    __config__: ClassVar[Type[ModelConfig]] = ModelConfig
    
    def __init__(self, **data: Any):
        """
        Initialize model with field values.
        
        Args:
            **data: Field values
            
        Raises:
            ValidationError: If validation fails
        """
        # Pre-root validators
        errors = []
        
        try:
            data = run_root_validators(self.__class__, data, pre=True)
        except ValueError as e:
            errors.append({
                "loc": ("__root__",),
                "msg": str(e),
                "type": "value_error"
            })
        
        # Process each field
        values = {}
        for field_name, field_info in self.__fields__.items():
            field_type = self.__field_types__.get(field_name, Any)
            
            # Get value or default
            if field_name in data:
                value = data[field_name]
            elif field_info.alias and field_info.alias in data:
                value = data[field_info.alias]
            elif field_info.has_default():
                value = field_info.get_default()
            else:
                value = None
                if not field_info.nullable:
                    errors.append({
                        "loc": (field_name,),
                        "msg": "field required",
                        "type": "value_error.missing"
                    })
                    continue
            
            # Pre-validators
            try:
                value = run_validators(
                    self.__class__, field_name, value, data, pre=True
                )
            except ValueError as e:
                errors.append({
                    "loc": (field_name,),
                    "msg": str(e),
                    "type": "value_error"
                })
                continue
            
            # Type coercion
            value, type_errors = self._coerce_type(field_name, value, field_type)
            errors.extend(type_errors)
            
            # Field constraints
            constraint_errors = field_info.validate_value(value, field_name)
            errors.extend(constraint_errors)
            
            # Main validators
            try:
                value = run_validators(
                    self.__class__, field_name, value, data
                )
            except ValueError as e:
                errors.append({
                    "loc": (field_name,),
                    "msg": str(e),
                    "type": "value_error"
                })
            
            values[field_name] = value
        
        # Handle extra fields
        extra_config = getattr(self.__config__, "extra", "ignore")
        for key in data:
            if key not in self.__fields__:
                alias_match = False
                for fname, finfo in self.__fields__.items():
                    if finfo.alias == key:
                        alias_match = True
                        break
                
                if not alias_match:
                    if extra_config == "forbid":
                        errors.append({
                            "loc": (key,),
                            "msg": "extra fields not permitted",
                            "type": "value_error.extra"
                        })
                    elif extra_config == "allow":
                        values[key] = data[key]
        
        # Post-root validators
        has_errors = len(errors) > 0
        try:
            values = run_root_validators(
                self.__class__, values, pre=False, has_errors=has_errors
            )
        except ValueError as e:
            errors.append({
                "loc": ("__root__",),
                "msg": str(e),
                "type": "value_error"
            })
        
        # Raise if errors
        if errors:
            raise ValidationError(errors, model=self.__class__)
        
        # Post-validators
        for field_name in values:
            try:
                values[field_name] = run_validators(
                    self.__class__, field_name, values[field_name], values, post=True
                )
            except ValueError as e:
                errors.append({
                    "loc": (field_name,),
                    "msg": str(e),
                    "type": "value_error"
                })
        
        if errors:
            raise ValidationError(errors, model=self.__class__)
        
        # Set attributes
        for key, value in values.items():
            object.__setattr__(self, key, value)
        
        # Call post-init hook
        if hasattr(self, "__post_init__"):
            self.__post_init__()
    
    def _coerce_type(
        self,
        field_name: str,
        value: Any,
        field_type: Type
    ) -> tuple[Any, List[Dict[str, Any]]]:
        """
        Coerce value to expected type.
        
        Returns (coerced_value, errors)
        """
        errors = []
        
        if value is None:
            return value, errors
        
        # Get origin type for generics
        origin = get_origin(field_type)
        args = get_args(field_type)
        
        # Handle Optional
        if origin is Union:
            # Check if None is allowed
            if type(None) in args:
                # Optional type
                other_types = [a for a in args if a is not type(None)]
                if len(other_types) == 1:
                    field_type = other_types[0]
                    origin = get_origin(field_type)
                    args = get_args(field_type)
        
        # Handle Reference
        if origin is Reference or (isinstance(field_type, type) and issubclass(field_type, Reference)):
            if isinstance(value, Reference):
                return value, errors
            if isinstance(value, str) and value.startswith(":"):
                return Reference.from_ison(value), errors
            # Try to convert from parser Reference
            if hasattr(value, "id"):
                return Reference(id=str(value.id), ref_type=getattr(value, "type", None)), errors
            errors.append({
                "loc": (field_name,),
                "msg": f"cannot convert {type(value).__name__} to Reference",
                "type": "type_error.reference"
            })
            return value, errors
        
        # Handle Nested
        if origin is Nested:
            # TODO: Handle nested object reconstruction
            return value, errors
        
        # Handle List
        if origin is list:
            if not isinstance(value, list):
                try:
                    value = list(value)
                except (TypeError, ValueError):
                    errors.append({
                        "loc": (field_name,),
                        "msg": f"value is not a valid list",
                        "type": "type_error.list"
                    })
            return value, errors
        
        # Basic type coercion
        strict = getattr(self.__config__, "strict", False)
        
        if field_type is int:
            if isinstance(value, int) and not isinstance(value, bool):
                return value, errors
            if not strict:
                try:
                    return int(value), errors
                except (TypeError, ValueError):
                    pass
            errors.append({
                "loc": (field_name,),
                "msg": f"value is not a valid integer",
                "type": "type_error.integer"
            })
        
        elif field_type is float:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value), errors
            if not strict:
                try:
                    return float(value), errors
                except (TypeError, ValueError):
                    pass
            errors.append({
                "loc": (field_name,),
                "msg": f"value is not a valid float",
                "type": "type_error.float"
            })
        
        elif field_type is str:
            if isinstance(value, str):
                return value, errors
            if not strict:
                return str(value), errors
            errors.append({
                "loc": (field_name,),
                "msg": f"value is not a valid string",
                "type": "type_error.string"
            })
        
        elif field_type is bool:
            if isinstance(value, bool):
                return value, errors
            if not strict:
                if value in (True, False, 1, 0, "true", "false", "True", "False"):
                    return value in (True, 1, "true", "True"), errors
            errors.append({
                "loc": (field_name,),
                "msg": f"value is not a valid boolean",
                "type": "type_error.bool"
            })
        
        return value, errors
    
    def __repr__(self) -> str:
        fields = ", ".join(
            f"{k}={getattr(self, k, None)!r}"
            for k in self.__fields__
        )
        return f"{self.__class__.__name__}({fields})"
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return all(
            getattr(self, k) == getattr(other, k)
            for k in self.__fields__
        )
    
    def dict(self, *, exclude: Set[str] = None, by_alias: bool = False) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Args:
            exclude: Fields to exclude
            by_alias: Use field aliases as keys
        """
        exclude = exclude or set()
        result = {}
        
        for field_name, field_info in self.__fields__.items():
            if field_name in exclude:
                continue
            
            value = getattr(self, field_name, None)
            
            # Handle Reference
            if isinstance(value, Reference):
                value = value.to_ison()
            
            # Handle nested model
            elif isinstance(value, ISONModel):
                value = value.dict(by_alias=by_alias)
            
            # Handle list of models
            elif isinstance(value, list):
                value = [
                    v.dict(by_alias=by_alias) if isinstance(v, ISONModel)
                    else v.to_ison() if isinstance(v, Reference)
                    else v
                    for v in value
                ]
            
            key = field_info.alias if by_alias and field_info.alias else field_name
            result[key] = value
        
        return result
    
    def copy(self, *, update: Dict[str, Any] = None) -> "ISONModel":
        """
        Create a copy of the model with optional updates.
        """
        data = self.dict()
        if update:
            data.update(update)
        return self.__class__(**data)
    
    def json(self, *, indent: int = None, exclude: Set[str] = None) -> str:
        """
        Serialize model to JSON string.
        
        Args:
            indent: JSON indentation
            exclude: Fields to exclude
        """
        return json.dumps(self.dict(exclude=exclude), indent=indent, default=str)
    
    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        """
        Generate JSON Schema for this model.
        
        Compatible with OpenAPI/JSON Schema standards.
        
        Returns:
            JSON Schema dictionary
        """
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": cls.__name__,
            "type": "object",
            "properties": {},
            "required": [],
        }
        
        if cls.__doc__:
            schema["description"] = cls.__doc__.strip()
        
        for field_name, field_info in cls.__fields__.items():
            field_type = cls.__field_types__.get(field_name, Any)
            prop = _field_to_json_schema(field_name, field_type, field_info)
            schema["properties"][field_name] = prop
            
            # Required if no default
            if not field_info.has_default() and not field_info.nullable:
                schema["required"].append(field_name)
        
        return schema
    
    @classmethod
    def model_json_schema_json(cls, indent: int = 2) -> str:
        """
        Generate JSON Schema as JSON string.
        """
        return json.dumps(cls.model_json_schema(), indent=indent)
    
    # Pydantic v1 compatibility aliases
    @classmethod
    def schema(cls) -> Dict[str, Any]:
        """Alias for model_json_schema() (Pydantic v1 compatibility)"""
        return cls.model_json_schema()
    
    @classmethod
    def schema_json(cls, indent: int = 2) -> str:
        """Alias for model_json_schema_json() (Pydantic v1 compatibility)"""
        return cls.model_json_schema_json(indent)
    
    @classmethod
    def get_primary_key_field(cls) -> Optional[str]:
        """Get the primary key field name, if any"""
        for field_name, field_info in cls.__fields__.items():
            if field_info.primary_key:
                return field_name
        return None
    
    def get_primary_key(self) -> Optional[Any]:
        """Get the primary key value"""
        pk_field = self.get_primary_key_field()
        if pk_field:
            return getattr(self, pk_field, None)
        return None
    
    def to_ison_row(self) -> List[Any]:
        """Convert to list of values for ISON row"""
        values = []
        for field_name in self.__fields__:
            value = getattr(self, field_name, None)
            values.append(value)
        return values
    
    @classmethod
    def to_ison_table(cls, models: List["ISONModel"], align: bool = True) -> str:
        """
        Serialize multiple models to ISON table format.
        
        Args:
            models: List of model instances
            align: Align columns
            
        Returns:
            ISON formatted string
        """
        if not models:
            return f"{cls.__ison_block__}\n"
        
        # Header
        fields = list(cls.__fields__.keys())
        lines = [cls.__ison_block__, " ".join(fields)]
        
        # Calculate column widths if aligning
        if align:
            widths = [len(f) for f in fields]
            for model in models:
                for i, field_name in enumerate(fields):
                    value = getattr(model, field_name, None)
                    str_val = _value_to_ison(value)
                    widths[i] = max(widths[i], len(str_val))
        else:
            widths = None
        
        # Data rows
        for model in models:
            row_values = []
            for i, field_name in enumerate(fields):
                value = getattr(model, field_name, None)
                str_val = _value_to_ison(value)
                if widths:
                    str_val = str_val.ljust(widths[i])
                row_values.append(str_val)
            lines.append(" ".join(row_values).rstrip())
        
        return "\n".join(lines)


class TableModel(ISONModel):
    """
    Model for ISON table blocks (multiple rows).
    
    Usage:
        class User(TableModel):
            __ison_block__ = "table.users"
            
            id: int = Field(primary_key=True)
            name: str
            email: str
    """
    pass


class ObjectModel(ISONModel):
    """
    Model for ISON object blocks (single row).
    
    Usage:
        class Config(ObjectModel):
            __ison_block__ = "object.config"
            
            timeout: int = 30
            debug: bool = False
    """
    
    def to_ison(self) -> str:
        """Serialize to ISON object format"""
        fields = list(self.__fields__.keys())
        values = []
        
        for field_name in fields:
            value = getattr(self, field_name, None)
            values.append(_value_to_ison(value))
        
        return f"{self.__ison_block__}\n{' '.join(fields)}\n{' '.join(values)}"


class MetaModel(ISONModel):
    """
    Model for ISON meta blocks (schema information).
    
    Usage:
        class SchemaInfo(MetaModel):
            __ison_block__ = "meta.schema"
            
            version: str
            generated_at: str
    """
    pass


# Helper functions

def _value_to_ison(value: Any) -> str:
    """Convert Python value to ISON string representation"""
    if value is None:
        return "null"
    
    if isinstance(value, bool):
        return "true" if value else "false"
    
    if isinstance(value, Reference):
        return value.to_ison()
    
    if isinstance(value, (int, float)):
        return str(value)
    
    if isinstance(value, str):
        return _quote_if_needed(value)
    
    if isinstance(value, ISONModel):
        # For nested models, we'd need special handling
        return str(value)
    
    return _quote_if_needed(str(value))


def _quote_if_needed(s: str) -> str:
    """Quote string if it contains spaces or special characters"""
    if not s:
        return '""'
    
    needs_quote = (
        " " in s or
        "\t" in s or
        '"' in s or
        "\n" in s or
        s in ("true", "false", "null") or
        s.startswith(":") or
        _looks_like_number(s)
    )
    
    if needs_quote:
        escaped = s.replace("\\", "\\\\")
        escaped = escaped.replace('"', '\\"')
        escaped = escaped.replace("\n", "\\n")
        escaped = escaped.replace("\t", "\\t")
        return f'"{escaped}"'
    
    return s


def _looks_like_number(s: str) -> bool:
    """Check if string looks like a number"""
    try:
        float(s)
        return True
    except ValueError:
        return False


def _field_to_json_schema(
    field_name: str,
    field_type: Type,
    field_info: FieldInfo
) -> Dict[str, Any]:
    """
    Convert a field to JSON Schema property definition.
    """
    from typing import get_origin, get_args
    
    prop: Dict[str, Any] = {}
    
    # Handle Optional
    origin = get_origin(field_type)
    args = get_args(field_type)
    
    is_optional = False
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            is_optional = True
            field_type = non_none[0]
            origin = get_origin(field_type)
            args = get_args(field_type)
    
    # Handle Reference
    if origin is Reference or (isinstance(field_type, type) and issubclass(field_type, Reference)):
        prop["type"] = "string"
        prop["pattern"] = "^:[a-zA-Z0-9_:]+$"
        prop["description"] = "ISON reference"
        if args:
            target = args[0]
            if hasattr(target, "__name__"):
                prop["x-ison-ref"] = target.__name__
    
    # Handle List
    elif origin is list:
        prop["type"] = "array"
        if args:
            item_schema = _field_to_json_schema("item", args[0], FieldInfo())
            prop["items"] = item_schema
    
    # Basic types
    elif field_type is int:
        prop["type"] = "integer"
    elif field_type is float:
        prop["type"] = "number"
    elif field_type is str:
        prop["type"] = "string"
    elif field_type is bool:
        prop["type"] = "boolean"
    else:
        prop["type"] = "string"  # Default fallback
    
    # Add constraints
    if field_info.gt is not None:
        prop["exclusiveMinimum"] = field_info.gt
    if field_info.ge is not None:
        prop["minimum"] = field_info.ge
    if field_info.lt is not None:
        prop["exclusiveMaximum"] = field_info.lt
    if field_info.le is not None:
        prop["maximum"] = field_info.le
    if field_info.min_length is not None:
        prop["minLength"] = field_info.min_length
    if field_info.max_length is not None:
        prop["maxLength"] = field_info.max_length
    if field_info.pattern is not None:
        prop["pattern"] = field_info.pattern
    if field_info.choices is not None:
        prop["enum"] = field_info.choices
    
    # Default value
    if field_info.default is not ... and field_info.default is not None:
        prop["default"] = field_info.default
    
    # Description
    if field_info.description:
        prop["description"] = field_info.description
    if field_info.title:
        prop["title"] = field_info.title
    
    # Nullable
    if is_optional or field_info.nullable:
        if "type" in prop:
            prop["type"] = [prop["type"], "null"]
    
    return prop
