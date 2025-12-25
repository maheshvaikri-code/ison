"""
ISONantic Parsing

Parse ISON data into models with validation.
"""

import re
from dataclasses import dataclass
from typing import (
    Any, Dict, Generic, List, Optional, Type, TypeVar, Union
)

from .models import ISONModel, TableModel
from .fields import Reference
from .exceptions import ValidationError, LLMParseError


T = TypeVar("T", bound=ISONModel)


@dataclass
class ParseResult(Generic[T]):
    """
    Result of parsing with error recovery.
    
    Contains both successfully parsed data and any errors.
    """
    success: bool
    data: Optional[List[T]] = None
    errors: List[Dict[str, Any]] = None
    partial_data: Optional[List[T]] = None  # Valid rows even with errors
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def parse_ison(
    data: str,
    model: Type[T],
    *,
    block: str = None,
    strict: bool = False,
    validate: bool = True,
) -> List[T]:
    """
    Parse ISON string into model instances.
    
    Args:
        data: ISON formatted string
        model: Model class to parse into
        block: Specific block name to parse (optional)
        strict: Raise on extra fields
        validate: Enable validation (default True)
        
    Returns:
        List of model instances
        
    Raises:
        ValidationError: If parsing or validation fails
    """
    # Parse raw ISON
    blocks = _parse_ison_to_blocks(data)
    
    # Find matching block
    target_block = model.__ison_block__
    if block:
        target_block = block
    
    matching_rows = []
    for parsed_block in blocks:
        full_name = f"{parsed_block['kind']}.{parsed_block['name']}"
        if full_name == target_block or parsed_block['name'] == target_block.split('.')[-1]:
            matching_rows.extend(parsed_block['rows'])
    
    if not matching_rows:
        return []
    
    # Convert to model instances
    models = []
    errors = []
    
    for row_idx, row in enumerate(matching_rows):
        try:
            instance = model(**row)
            models.append(instance)
        except ValidationError as e:
            if validate:
                # Add row context to errors
                for error in e.errors():
                    error["loc"] = (target_block, row_idx) + error.get("loc", ())
                errors.extend(e.errors())
            # Continue to next row
    
    if errors:
        raise ValidationError(errors, model=model)
    
    return models


def parse_ison_safe(
    data: str,
    model: Type[T],
    **kwargs
) -> ParseResult[T]:
    """
    Parse ISON with error recovery.
    
    Returns ParseResult with both valid data and errors.
    Does not raise exceptions.
    
    Args:
        data: ISON formatted string
        model: Model class to parse into
        **kwargs: Additional arguments for parse_ison
        
    Returns:
        ParseResult with success status, data, and errors
    """
    try:
        result = parse_ison(data, model, **kwargs)
        return ParseResult(
            success=True,
            data=result,
            errors=[],
        )
    except ValidationError as e:
        # Try to get partial data
        partial = _parse_partial(data, model)
        return ParseResult(
            success=False,
            data=None,
            errors=e.errors(),
            partial_data=partial,
        )
    except Exception as e:
        return ParseResult(
            success=False,
            data=None,
            errors=[{
                "loc": (),
                "msg": str(e),
                "type": "parse_error"
            }],
        )


def parse_llm_output(
    response: str,
    model: Type[T],
    *,
    strict: bool = False,
    auto_fix: bool = True,
) -> List[T]:
    """
    Parse LLM-generated ISON output.
    
    Handles common LLM formatting issues:
    - Extra text before/after ISON
    - Markdown code blocks
    - Minor syntax variations
    
    Args:
        response: Raw LLM response
        model: Model class to parse into
        strict: Strict validation mode
        auto_fix: Attempt to fix common issues
        
    Returns:
        List of model instances
        
    Raises:
        LLMParseError: If parsing fails
    """
    # Extract ISON from response
    ison_data = _extract_ison(response)
    
    if not ison_data:
        raise LLMParseError(
            "No ISON block found in response",
            raw_output=response,
            suggestion="Ensure the LLM outputs data in ISON format starting with table.* or object.*"
        )
    
    # Apply auto-fixes
    if auto_fix:
        ison_data = _auto_fix_ison(ison_data)
    
    # Parse
    try:
        return parse_ison(ison_data, model, strict=strict)
    except ValidationError as e:
        raise LLMParseError(
            f"Validation failed: {e}",
            raw_output=response,
            extracted_ison=ison_data,
            suggestion="Check that all required fields are present and properly formatted",
            recoverable=True,
        )
    except Exception as e:
        raise LLMParseError(
            f"Parse error: {e}",
            raw_output=response,
            extracted_ison=ison_data,
        )


def validate_llm_ison(
    response: str,
    model: Type[T],
) -> ParseResult[T]:
    """
    Validate LLM-generated ISON without raising exceptions.
    
    Returns ParseResult with validation status and any errors.
    Useful for implementing retry logic.
    
    Args:
        response: Raw LLM response
        model: Model class to validate against
        
    Returns:
        ParseResult with validation status
    """
    try:
        data = parse_llm_output(response, model)
        return ParseResult(
            success=True,
            data=data,
        )
    except LLMParseError as e:
        return ParseResult(
            success=False,
            errors=[{
                "loc": (),
                "msg": str(e),
                "type": "llm_parse_error",
                "suggestion": e.suggestion,
            }],
        )


# Internal parsing functions

def _parse_ison_to_blocks(data: str) -> List[Dict[str, Any]]:
    """
    Parse raw ISON string to block dictionaries.
    
    Returns list of blocks with:
    - kind: "table", "object", or "meta"
    - name: block name
    - fields: list of field names
    - rows: list of row dictionaries
    """
    blocks = []
    lines = data.strip().split("\n")
    
    current_block = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            i += 1
            continue
        
        # Check for block header
        if "." in line and not line.startswith('"'):
            parts = line.split(".", 1)
            if parts[0] in ("table", "object", "meta"):
                # Save previous block
                if current_block:
                    blocks.append(current_block)
                
                # Start new block
                current_block = {
                    "kind": parts[0],
                    "name": parts[1],
                    "fields": [],
                    "rows": [],
                }
                i += 1
                
                # Next line should be fields
                if i < len(lines):
                    field_line = lines[i].strip()
                    if field_line and not field_line.startswith("#"):
                        current_block["fields"] = _tokenize_line(field_line)
                        i += 1
                
                continue
        
        # Data row
        if current_block and current_block["fields"]:
            tokens = _tokenize_line(line)
            
            if len(tokens) == len(current_block["fields"]):
                row = {}
                for j, field in enumerate(current_block["fields"]):
                    value = _infer_type(tokens[j])
                    _set_nested_value(row, field, value)
                
                current_block["rows"].append(row)
        
        i += 1
    
    # Save last block
    if current_block:
        blocks.append(current_block)
    
    return blocks


def _tokenize_line(line: str) -> List[str]:
    """Tokenize a line handling quoted strings"""
    tokens = []
    pos = 0
    
    while pos < len(line):
        # Skip whitespace
        while pos < len(line) and line[pos] in " \t":
            pos += 1
        
        if pos >= len(line):
            break
        
        if line[pos] == '"':
            # Quoted string
            pos += 1
            start = pos
            result = []
            
            while pos < len(line):
                if line[pos] == "\\":
                    pos += 1
                    if pos < len(line):
                        escape_map = {
                            '"': '"',
                            '\\': '\\',
                            'n': '\n',
                            't': '\t',
                            'r': '\r',
                        }
                        result.append(escape_map.get(line[pos], line[pos]))
                        pos += 1
                elif line[pos] == '"':
                    pos += 1
                    break
                else:
                    result.append(line[pos])
                    pos += 1
            
            tokens.append("".join(result))
        else:
            # Unquoted token
            start = pos
            while pos < len(line) and line[pos] not in " \t":
                pos += 1
            tokens.append(line[start:pos])
    
    return tokens


def _infer_type(token: str) -> Any:
    """Infer type from token"""
    # Boolean
    if token == "true":
        return True
    if token == "false":
        return False
    
    # Null
    if token == "null":
        return None
    
    # Integer
    if re.match(r"^-?[0-9]+$", token):
        return int(token)
    
    # Float
    if re.match(r"^-?[0-9]+\.[0-9]+$", token):
        return float(token)
    
    # Reference
    if token.startswith(":"):
        value = token[1:]
        if ":" in value:
            parts = value.split(":", 1)
            return Reference(id=parts[1], ref_type=parts[0])
        return Reference(id=value)
    
    # String
    return token


def _set_nested_value(obj: dict, path: str, value: Any):
    """Set value in nested dict using dot-path"""
    parts = path.split(".")
    current = obj
    
    for i, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {}
        current = current[part]
    
    current[parts[-1]] = value


def _extract_ison(response: str) -> Optional[str]:
    """Extract ISON block from LLM response"""
    # Try to find code block first
    code_block_match = re.search(
        r"```(?:ison)?\s*\n(.*?)```",
        response,
        re.DOTALL | re.IGNORECASE
    )
    if code_block_match:
        return code_block_match.group(1).strip()
    
    # Look for block headers
    lines = response.split("\n")
    ison_lines = []
    in_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # Check for block header
        if re.match(r"^(table|object|meta)\.[a-zA-Z_][a-zA-Z0-9_]*$", stripped):
            in_block = True
            ison_lines.append(stripped)
        elif in_block:
            # Continue collecting until empty line or obvious text
            if not stripped:
                # Empty line might be block separator
                ison_lines.append("")
            elif stripped.startswith("#"):
                # Comment
                ison_lines.append(stripped)
            elif re.match(r"^[a-zA-Z_]", stripped) and len(stripped.split()) > 1:
                # Likely a data line
                ison_lines.append(stripped)
            elif re.match(r'^[-0-9:"\[]', stripped):
                # Likely a data line
                ison_lines.append(stripped)
            else:
                # Probably end of ISON
                break
    
    if ison_lines:
        return "\n".join(ison_lines).strip()
    
    return None


def _auto_fix_ison(ison_data: str) -> str:
    """Apply common fixes to LLM-generated ISON"""
    lines = ison_data.split("\n")
    fixed_lines = []
    
    for line in lines:
        # Remove trailing commas (JSON habit)
        line = re.sub(r",\s*$", "", line)
        
        # Remove trailing semicolons
        line = re.sub(r";\s*$", "", line)
        
        fixed_lines.append(line)
    
    return "\n".join(fixed_lines)


def _parse_partial(data: str, model: Type[T]) -> List[T]:
    """Parse and return only valid rows"""
    blocks = _parse_ison_to_blocks(data)
    target_block = model.__ison_block__
    
    valid_models = []
    
    for parsed_block in blocks:
        full_name = f"{parsed_block['kind']}.{parsed_block['name']}"
        if full_name != target_block:
            continue
        
        for row in parsed_block["rows"]:
            try:
                instance = model(**row)
                valid_models.append(instance)
            except:
                continue
    
    return valid_models
