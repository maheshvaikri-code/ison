"""
ISONantic Validators

Decorator-based validation system similar to Pydantic.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field


@dataclass
class ValidatorInfo:
    """Stores validator metadata"""
    field_name: str
    func: Callable
    pre: bool = False  # Run before type coercion
    post: bool = False  # Run after all validation
    always: bool = False  # Run even if field is missing
    each_item: bool = False  # For list fields, validate each item


@dataclass
class RootValidatorInfo:
    """Stores root validator metadata"""
    func: Callable
    pre: bool = False  # Run before field validation
    skip_on_failure: bool = True  # Skip if field validation fails


@dataclass
class ComputedFieldInfo:
    """Stores computed field metadata"""
    func: Callable
    return_type: Optional[Type] = None
    cached: bool = False


# Registry for validators attached to model classes
_validators: Dict[Type, List[ValidatorInfo]] = {}
_root_validators: Dict[Type, List[RootValidatorInfo]] = {}
_computed_fields: Dict[Type, Dict[str, ComputedFieldInfo]] = {}


def validator(
    field_name: str,
    *,
    pre: bool = False,
    post: bool = False,
    always: bool = False,
    each_item: bool = False,
) -> Callable:
    """
    Decorator to define a field validator.
    
    Similar to Pydantic's validator decorator.
    
    Args:
        field_name: Name of field to validate
        pre: Run before type coercion
        post: Run after all other validation
        always: Run even if field value is missing
        each_item: For list fields, validate each item
        
    Usage:
        class User(TableModel):
            email: str
            
            @validator("email")
            def validate_email(cls, v):
                if "@" not in v:
                    raise ValueError("Invalid email")
                return v.lower()  # Can transform value
    """
    def decorator(func: Callable) -> Callable:
        # Store validator info on the function for later collection
        if not hasattr(func, "_validator_info"):
            func._validator_info = []
        
        func._validator_info.append(ValidatorInfo(
            field_name=field_name,
            func=func,
            pre=pre,
            post=post,
            always=always,
            each_item=each_item,
        ))
        
        return func
    
    return decorator


def root_validator(
    func: Callable = None,
    *,
    pre: bool = False,
    skip_on_failure: bool = True,
) -> Callable:
    """
    Decorator to define a root validator.

    Root validators receive all field values and can perform
    cross-field validation.

    Args:
        pre: Run before field validation
        skip_on_failure: Skip if field validation fails

    Usage:
        class DateRange(TableModel):
            start_date: str
            end_date: str

            @root_validator
            def validate_dates(cls, values):
                if values.get("start_date") > values.get("end_date"):
                    raise ValueError("start_date must be before end_date")
                return values
    """
    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_root_validator_info"):
            f._root_validator_info = []

        f._root_validator_info.append(RootValidatorInfo(
            func=f,
            pre=pre,
            skip_on_failure=skip_on_failure,
        ))

        return f

    if func is not None:
        # Called without parentheses: @root_validator
        return decorator(func)
    else:
        # Called with parentheses: @root_validator() or @root_validator(pre=True)
        return decorator


def computed(func: Callable = None, *, cached: bool = False) -> Callable:
    """
    Decorator to define a computed field.
    
    Computed fields are derived from other fields and are
    calculated on access rather than stored.
    
    Args:
        cached: Cache the computed value (only compute once)
        
    Usage:
        class Order(TableModel):
            subtotal: float
            tax_rate: float
            
            @computed
            def tax(self) -> float:
                return self.subtotal * self.tax_rate
            
            @computed
            def total(self) -> float:
                return self.subtotal + self.tax
    """
    def decorator(f: Callable) -> property:
        # Get return type from annotations
        return_type = f.__annotations__.get("return")
        
        # Store computed field info
        if not hasattr(f, "_computed_info"):
            f._computed_info = ComputedFieldInfo(
                func=f,
                return_type=return_type,
                cached=cached,
            )
        
        if cached:
            # Create cached property
            cache_attr = f"_cached_{f.__name__}"
            
            @wraps(f)
            def cached_getter(self):
                if not hasattr(self, cache_attr):
                    setattr(self, cache_attr, f(self))
                return getattr(self, cache_attr)
            
            return property(cached_getter)
        else:
            # Simple property
            return property(f)
    
    if func is not None:
        # Called without arguments: @computed
        return decorator(func)
    else:
        # Called with arguments: @computed(cached=True)
        return decorator


class ValidationInfo:
    """
    Context passed to validators.
    
    Provides access to other field values and validation state.
    """
    
    def __init__(
        self,
        data: Dict[str, Any],
        field_name: str,
        config: Optional[Any] = None,
    ):
        self.data = data  # All field values
        self.field_name = field_name  # Current field being validated
        self.config = config  # Model config
        
    def get_field(self, name: str) -> Any:
        """Get value of another field"""
        return self.data.get(name)


def collect_validators(cls: Type) -> Dict[str, List[ValidatorInfo]]:
    """
    Collect all validators for a model class.
    
    Includes validators from parent classes.
    """
    validators: Dict[str, List[ValidatorInfo]] = {}
    
    # Walk through MRO to collect inherited validators
    for klass in reversed(cls.__mro__):
        for name, method in vars(klass).items():
            if hasattr(method, "_validator_info"):
                for info in method._validator_info:
                    if info.field_name not in validators:
                        validators[info.field_name] = []
                    # Bind the method to the class
                    bound_info = ValidatorInfo(
                        field_name=info.field_name,
                        func=method,
                        pre=info.pre,
                        post=info.post,
                        always=info.always,
                        each_item=info.each_item,
                    )
                    validators[info.field_name].append(bound_info)
    
    return validators


def collect_root_validators(cls: Type) -> List[RootValidatorInfo]:
    """
    Collect all root validators for a model class.
    
    Includes validators from parent classes.
    """
    root_validators: List[RootValidatorInfo] = []
    
    for klass in reversed(cls.__mro__):
        for name, method in vars(klass).items():
            if hasattr(method, "_root_validator_info"):
                for info in method._root_validator_info:
                    bound_info = RootValidatorInfo(
                        func=method,
                        pre=info.pre,
                        skip_on_failure=info.skip_on_failure,
                    )
                    root_validators.append(bound_info)
    
    return root_validators


def collect_computed_fields(cls: Type) -> Dict[str, ComputedFieldInfo]:
    """
    Collect all computed fields for a model class.
    """
    computed_fields: Dict[str, ComputedFieldInfo] = {}
    
    for klass in reversed(cls.__mro__):
        for name, attr in vars(klass).items():
            # Check if it's a property wrapping a computed function
            if isinstance(attr, property) and attr.fget is not None:
                fget = attr.fget
                # Check the original function for computed info
                if hasattr(fget, "__wrapped__"):
                    fget = fget.__wrapped__
                if hasattr(fget, "_computed_info"):
                    computed_fields[name] = fget._computed_info
    
    return computed_fields


def run_validators(
    cls: Type,
    field_name: str,
    value: Any,
    values: Dict[str, Any],
    pre: bool = False,
    post: bool = False,
) -> Any:
    """
    Run validators for a field.
    
    Args:
        cls: Model class
        field_name: Field being validated
        value: Current field value
        values: All field values
        pre: Run only pre-validators
        post: Run only post-validators
        
    Returns:
        Potentially transformed value
        
    Raises:
        ValueError: If validation fails
    """
    validators = collect_validators(cls)
    field_validators = validators.get(field_name, [])
    
    for validator_info in field_validators:
        # Filter by pre/post
        if pre and not validator_info.pre:
            continue
        if post and not validator_info.post:
            continue
        if not pre and not post and (validator_info.pre or validator_info.post):
            continue
        
        # Skip if value is None and not always
        if value is None and not validator_info.always:
            continue
        
        # Handle each_item for lists
        if validator_info.each_item and isinstance(value, list):
            value = [
                validator_info.func(cls, item)
                for item in value
            ]
        else:
            # Create validation info
            info = ValidationInfo(
                data=values,
                field_name=field_name,
            )
            
            # Call validator (may transform value)
            try:
                # Try with info parameter
                import inspect
                sig = inspect.signature(validator_info.func)
                params = list(sig.parameters.keys())
                
                if len(params) >= 3:
                    value = validator_info.func(cls, value, info)
                else:
                    value = validator_info.func(cls, value)
            except TypeError:
                value = validator_info.func(cls, value)
    
    return value


def run_root_validators(
    cls: Type,
    values: Dict[str, Any],
    pre: bool = False,
    has_errors: bool = False,
) -> Dict[str, Any]:
    """
    Run root validators.
    
    Args:
        cls: Model class
        values: All field values
        pre: Run only pre-validators
        has_errors: Whether field validation had errors
        
    Returns:
        Potentially transformed values
        
    Raises:
        ValueError: If validation fails
    """
    root_validators = collect_root_validators(cls)
    
    for validator_info in root_validators:
        # Filter by pre
        if pre != validator_info.pre:
            continue
        
        # Skip if there were errors and skip_on_failure
        if has_errors and validator_info.skip_on_failure:
            continue
        
        # Call validator
        values = validator_info.func(cls, values)
    
    return values
