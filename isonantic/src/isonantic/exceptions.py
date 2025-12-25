"""
ISONantic Exceptions

Custom exception classes for validation, reference, and parsing errors.
"""

from typing import Any, Dict, List, Optional, Tuple


class ISONanticError(Exception):
    """Base exception for all ISONantic errors"""
    pass


class ValidationError(ISONanticError):
    """
    Validation error with detailed error information.
    
    Similar to Pydantic's ValidationError, provides structured
    error information for multiple validation failures.
    """
    
    def __init__(
        self,
        errors: List[Dict[str, Any]],
        model: Optional[type] = None
    ):
        self._errors = errors
        self._model = model
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message"""
        count = len(self._errors)
        model_name = self._model.__name__ if self._model else "Model"
        
        lines = [f"{count} validation error(s) for {model_name}"]
        for error in self._errors:
            loc = " -> ".join(str(l) for l in error.get("loc", []))
            msg = error.get("msg", "Unknown error")
            error_type = error.get("type", "value_error")
            lines.append(f"  {loc}")
            lines.append(f"    {msg} (type={error_type})")
        
        return "\n".join(lines)
    
    def errors(self) -> List[Dict[str, Any]]:
        """Return list of error dictionaries"""
        return self._errors
    
    def error_count(self) -> int:
        """Return number of errors"""
        return len(self._errors)
    
    @classmethod
    def from_single(
        cls,
        loc: Tuple[str, ...],
        msg: str,
        error_type: str = "value_error",
        model: Optional[type] = None
    ) -> "ValidationError":
        """Create ValidationError from a single error"""
        return cls(
            errors=[{"loc": loc, "msg": msg, "type": error_type}],
            model=model
        )


class ReferenceError(ISONanticError):
    """
    Reference validation error.
    
    Raised when a reference points to a non-existent record
    or when reference validation fails.
    """
    
    def __init__(
        self,
        ref_id: str,
        ref_type: Optional[str] = None,
        target_block: str = "",
        source_block: str = "",
        source_row: int = 0,
        source_field: str = "",
        available_ids: Optional[List[str]] = None
    ):
        self.ref_id = ref_id
        self.ref_type = ref_type
        self.target_block = target_block
        self.source_block = source_block
        self.source_row = source_row
        self.source_field = source_field
        self.available_ids = available_ids or []
        
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message"""
        ref_str = f":{self.ref_type}:{self.ref_id}" if self.ref_type else f":{self.ref_id}"
        
        msg = (
            f"Invalid reference in {self.source_block} row {self.source_row}\n"
            f"  Field '{self.source_field}': Reference {ref_str} not found in {self.target_block}"
        )
        
        if self.available_ids:
            # Show first 10 available IDs
            ids_preview = self.available_ids[:10]
            if len(self.available_ids) > 10:
                ids_preview.append("...")
            msg += f"\n  Available IDs: {ids_preview}"
        
        return msg


class LLMParseError(ISONanticError):
    """
    Error parsing LLM-generated ISON output.
    
    Includes suggestions for fixing common LLM output issues.
    """
    
    def __init__(
        self,
        message: str,
        raw_output: str = "",
        extracted_ison: Optional[str] = None,
        suggestion: Optional[str] = None,
        recoverable: bool = False
    ):
        self.raw_output = raw_output
        self.extracted_ison = extracted_ison
        self.suggestion = suggestion
        self.recoverable = recoverable
        
        super().__init__(self._format_message(message))
    
    def _format_message(self, message: str) -> str:
        """Format error message with suggestion"""
        msg = f"LLM Parse Error: {message}"
        
        if self.suggestion:
            msg += f"\n  Suggestion: {self.suggestion}"
        
        if self.extracted_ison:
            preview = self.extracted_ison[:200]
            if len(self.extracted_ison) > 200:
                preview += "..."
            msg += f"\n  Extracted ISON:\n{preview}"
        
        return msg


class FieldError(ISONanticError):
    """Error in field definition"""
    pass


class SchemaError(ISONanticError):
    """Error in schema definition"""
    pass


class SerializationError(ISONanticError):
    """Error during serialization to ISON"""
    pass
