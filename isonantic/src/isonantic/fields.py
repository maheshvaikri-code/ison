"""
ISONantic Fields

Field definitions, constraints, and reference types.
"""

from dataclasses import dataclass, field as dataclass_field
from typing import (
    Any, Callable, Dict, Generic, List, Optional, 
    Pattern, Type, TypeVar, Union, TYPE_CHECKING
)
import re

if TYPE_CHECKING:
    from .document import ISONDocument

T = TypeVar("T")


@dataclass
class FieldInfo:
    """
    Field metadata and constraints.
    
    Similar to Pydantic's FieldInfo, stores all field configuration.
    """
    # Identity
    primary_key: bool = False
    unique: bool = False
    alias: Optional[str] = None
    
    # Type constraints
    nullable: bool = False
    default: Any = ...  # ... means required
    default_factory: Optional[Callable[[], Any]] = None
    
    # Numeric constraints
    gt: Optional[float] = None  # Greater than
    ge: Optional[float] = None  # Greater or equal
    lt: Optional[float] = None  # Less than
    le: Optional[float] = None  # Less or equal
    multiple_of: Optional[float] = None
    
    # String constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    
    # Enum constraint
    choices: Optional[List[Any]] = None
    
    # Documentation
    title: Optional[str] = None
    description: Optional[str] = None
    
    # Error messages
    error_messages: Dict[str, str] = dataclass_field(default_factory=dict)
    
    # Internal
    _compiled_pattern: Optional[Pattern] = dataclass_field(default=None, repr=False)
    
    def __post_init__(self):
        """Compile pattern if provided"""
        if self.pattern:
            self._compiled_pattern = re.compile(self.pattern)
    
    def has_default(self) -> bool:
        """Check if field has a default value"""
        return self.default is not ... or self.default_factory is not None
    
    def get_default(self) -> Any:
        """Get default value"""
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is not ...:
            return self.default
        return None
    
    def validate_value(self, value: Any, field_name: str) -> List[Dict[str, Any]]:
        """
        Validate a value against field constraints.
        
        Returns list of error dictionaries (empty if valid).
        """
        errors = []
        
        # Null check
        if value is None:
            if not self.nullable and self.default is ...:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("required", "field required"),
                    "type": "value_error.missing"
                })
            return errors
        
        # Numeric constraints
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.gt is not None and value <= self.gt:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("gt", f"ensure this value is greater than {self.gt}"),
                    "type": "value_error.number.not_gt"
                })
            if self.ge is not None and value < self.ge:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("ge", f"ensure this value is greater than or equal to {self.ge}"),
                    "type": "value_error.number.not_ge"
                })
            if self.lt is not None and value >= self.lt:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("lt", f"ensure this value is less than {self.lt}"),
                    "type": "value_error.number.not_lt"
                })
            if self.le is not None and value > self.le:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("le", f"ensure this value is less than or equal to {self.le}"),
                    "type": "value_error.number.not_le"
                })
            if self.multiple_of is not None and value % self.multiple_of != 0:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("multiple_of", f"ensure this value is a multiple of {self.multiple_of}"),
                    "type": "value_error.number.not_multiple"
                })
        
        # String constraints
        if isinstance(value, str):
            if self.min_length is not None and len(value) < self.min_length:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("min_length", f"ensure this value has at least {self.min_length} characters"),
                    "type": "value_error.any_str.min_length"
                })
            if self.max_length is not None and len(value) > self.max_length:
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("max_length", f"ensure this value has at most {self.max_length} characters"),
                    "type": "value_error.any_str.max_length"
                })
            if self._compiled_pattern is not None and not self._compiled_pattern.match(value):
                errors.append({
                    "loc": (field_name,),
                    "msg": self.error_messages.get("pattern", f"string does not match regex '{self.pattern}'"),
                    "type": "value_error.str.regex"
                })
        
        # Choices constraint
        if self.choices is not None and value not in self.choices:
            errors.append({
                "loc": (field_name,),
                "msg": self.error_messages.get("choices", f"value must be one of: {self.choices}"),
                "type": "value_error.not_in_choices"
            })
        
        return errors


def Field(
    default: Any = ...,
    *,
    default_factory: Optional[Callable[[], Any]] = None,
    primary_key: bool = False,
    unique: bool = False,
    alias: Optional[str] = None,
    nullable: bool = False,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    multiple_of: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
    choices: Optional[List[Any]] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    error_messages: Optional[Dict[str, str]] = None,
) -> Any:
    """
    Define field constraints and metadata.
    
    Similar to Pydantic's Field function.
    
    Args:
        default: Default value (... means required)
        default_factory: Callable to generate default
        primary_key: Is this the primary key?
        unique: Must values be unique?
        alias: Alternative name in ISON
        nullable: Allow null values?
        gt: Greater than (numeric)
        ge: Greater or equal (numeric)
        lt: Less than (numeric)
        le: Less or equal (numeric)
        multiple_of: Must be multiple of (numeric)
        min_length: Minimum string length
        max_length: Maximum string length
        pattern: Regex pattern for strings
        choices: Allowed values
        title: Field title for docs
        description: Field description
        error_messages: Custom error messages
        
    Returns:
        FieldInfo instance
    """
    return FieldInfo(
        default=default,
        default_factory=default_factory,
        primary_key=primary_key,
        unique=unique,
        alias=alias,
        nullable=nullable,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        choices=choices,
        title=title,
        description=description,
        error_messages=error_messages or {},
    )


class Reference(Generic[T]):
    """
    A typed reference to another model.
    
    In ISON, references are represented as :ID or :type:ID.
    Reference[Team] means this field references a Team model.
    
    Usage:
        class User(TableModel):
            team: Reference[Team]  # Reference to Team model
    """
    
    def __init__(
        self, 
        id: str, 
        ref_type: Optional[str] = None,
        _resolved: Optional[T] = None
    ):
        self.id = id
        self.ref_type = ref_type
        self._resolved = _resolved
        self._target_model: Optional[Type[T]] = None
    
    def __repr__(self) -> str:
        if self.ref_type:
            return f"Reference({self.ref_type}:{self.id})"
        return f"Reference({self.id})"
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Reference):
            return self.id == other.id and self.ref_type == other.ref_type
        return False
    
    def __hash__(self) -> int:
        return hash((self.id, self.ref_type))
    
    def to_ison(self) -> str:
        """Convert to ISON reference notation"""
        if self.ref_type:
            return f":{self.ref_type}:{self.id}"
        return f":{self.id}"
    
    def is_resolved(self) -> bool:
        """Check if reference has been resolved"""
        return self._resolved is not None
    
    def resolve(self, document: "ISONDocument" = None) -> T:
        """
        Resolve the reference to the actual object.
        
        Args:
            document: ISONDocument containing the referenced data
            
        Returns:
            The resolved model instance
            
        Raises:
            ReferenceError: If reference cannot be resolved
        """
        if self._resolved is not None:
            return self._resolved
        
        if document is None:
            from .exceptions import ReferenceError
            raise ReferenceError(
                ref_id=self.id,
                ref_type=self.ref_type,
                target_block="unknown",
                source_block="unknown",
                source_row=0,
                source_field="unknown"
            )
        
        # Let document handle resolution
        resolved = document._resolve_reference(self)
        self._resolved = resolved
        return resolved
    
    @classmethod
    def from_ison(cls, ison_ref: str) -> "Reference":
        """
        Create Reference from ISON notation.
        
        Args:
            ison_ref: ISON reference string like ":10" or ":user:10"
            
        Returns:
            Reference instance
        """
        if not ison_ref.startswith(":"):
            raise ValueError(f"Invalid ISON reference: {ison_ref}")
        
        value = ison_ref[1:]  # Remove leading :
        if ":" in value:
            parts = value.split(":", 1)
            return cls(id=parts[1], ref_type=parts[0])
        return cls(id=value)


class LazyReference(Reference[T]):
    """
    A lazily-resolved reference.
    
    Unlike Reference, LazyReference only resolves when accessed.
    This is useful for circular references or large documents.
    """
    
    def __init__(
        self, 
        id: str, 
        ref_type: Optional[str] = None,
        document: "ISONDocument" = None
    ):
        super().__init__(id, ref_type)
        self._document = document
    
    def __getattr__(self, name: str) -> Any:
        """Auto-resolve and access attribute"""
        if name.startswith("_"):
            raise AttributeError(name)
        
        resolved = self.resolve(self._document)
        return getattr(resolved, name)


class Nested(Generic[T]):
    """
    Marker for nested/embedded objects using dot-path notation.
    
    In ISON, nested objects are flattened with dot-paths:
        address.street, address.city, address.zip
    
    Nested[Address] tells ISONantic to reconstruct the nested object.
    
    Usage:
        class Address(ISONModel):
            street: str
            city: str
            zip: str
        
        class Customer(TableModel):
            name: str
            address: Nested[Address]  # Maps to address.* fields
    """
    
    def __init__(self, data: Optional[T] = None):
        self._data = data
    
    def __repr__(self) -> str:
        return f"Nested({self._data})"
    
    @property
    def data(self) -> Optional[T]:
        """Get the nested object"""
        return self._data


# Type aliases for common patterns
OptionalRef = Optional[Reference[T]]
RefList = List[Reference[T]]
