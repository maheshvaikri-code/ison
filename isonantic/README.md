<p align="center">
  <img src="https://raw.githubusercontent.com/maheshvaikri-code/ison/main/ison-logo.png" alt="ISON Logo" width="120" height="120">
</p>

# ISONantic

**ISONantic** - A Pydantic-like data validation library for ISON format.

[![PyPI version](https://badge.fury.io/py/isonantic.svg)](https://badge.fury.io/py/isonantic)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-39%20passed-brightgreen.svg)]()

## Features

- **Pydantic-like models** for ISON data validation
- **Type-safe parsing** of LLM structured outputs
- **Reference resolution** across ISON blocks
- **Custom validators** and computed fields
- **Schema generation** for LLM prompts
- **Error recovery** for malformed LLM outputs

## Installation

```bash
pip install isonantic
```

## Quick Start

### Define Models

```python
from isonantic import TableModel, ObjectModel, Field, Reference

class Team(TableModel):
    __ison_block__ = "table.teams"
    id: int = Field(primary_key=True)
    name: str
    budget: float

class User(TableModel):
    __ison_block__ = "table.users"
    id: int = Field(primary_key=True)
    name: str
    email: str
    team: Reference[Team]  # Reference to Team by ID
```

### Parse ISON Data

```python
from isonantic import ISONDocument, parse_ison

ison_data = """
table.teams
id name budget
1 Engineering 500000
2 Marketing 250000

table.users
id name email team
1 Alice alice@example.com :1
2 Bob bob@example.com :2
"""

# Parse with validation
doc = ISONDocument()
doc.register(Team, User)
doc.parse(ison_data)

# Access typed data
users = doc.get_all(User)
for user in users:
    print(f"{user.name} - Team: {user.team.name}")  # Reference auto-resolved!
```

### Parse LLM Output

```python
from isonantic import parse_llm_output, ParseResult

# LLM may return partial or malformed ISON
llm_response = """
Here's the data you requested:

table.products
id name price
1 Widget 9.99
2 Gadget 19.99

The products are ready.
"""

result: ParseResult = parse_llm_output(llm_response, [Product])
if result.success:
    products = result.data[Product]
else:
    print(f"Errors: {result.errors}")
```

### Schema for Prompts

```python
from isonantic import prompt_for_model

# Generate ISON schema for LLM prompts
prompt = prompt_for_model(User)
print(prompt)
# Output:
# table.users
# id:int name:string email:string team:ref
# <rows>
```

## Model Types

### TableModel
For tabular data with multiple rows:

```python
class Product(TableModel):
    __ison_block__ = "table.products"
    id: int = Field(primary_key=True)
    name: str
    price: float
```

### ObjectModel
For single key-value configurations:

```python
class Config(ObjectModel):
    __ison_block__ = "object.config"
    timeout: int = 30
    debug: bool = False
    api_key: str
```

### MetaModel
For metadata blocks:

```python
class DocumentMeta(MetaModel):
    __ison_block__ = "meta.document"
    title: str
    version: str
    created: str
```

## Field Options

```python
from isonantic import Field, Reference, LazyReference

class User(TableModel):
    # Primary key
    id: int = Field(primary_key=True)

    # Required field
    name: str = Field()

    # Optional with default
    active: bool = Field(default=True)

    # Reference to another model
    team: Reference[Team]

    # Lazy reference (resolved on access)
    manager: LazyReference[User] = None

    # Constrained field
    age: int = Field(ge=0, le=150)

    # Pattern validation
    email: str = Field(pattern=r'^[\w.]+@[\w.]+$')
```

## Validators

```python
from isonantic import TableModel, validator, root_validator, computed

class Order(TableModel):
    __ison_block__ = "table.orders"

    id: int = Field(primary_key=True)
    quantity: int
    unit_price: float

    @computed
    def total(self) -> float:
        return self.quantity * self.unit_price

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @root_validator
    def validate_order(cls, values):
        if values.get('total', 0) > 10000:
            raise ValueError('Order total exceeds limit')
        return values
```

## Reference Resolution

ISONantic automatically resolves references between blocks:

```python
# ISON data with references
ison = """
table.departments
id name
D1 Engineering
D2 Sales

table.employees
id name dept
E1 Alice :D1
E2 Bob :D2
"""

doc = ISONDocument()
doc.register(Department, Employee)
doc.parse(ison)

emp = doc.get(Employee, "E1")
print(emp.dept.name)  # "Engineering" - auto-resolved!
```

## Error Handling

```python
from isonantic import parse_ison_safe, ValidationError

try:
    result = parse_ison_safe(data, [User, Team])

    if result.has_errors:
        for error in result.errors:
            print(f"Error: {error}")

    # Access valid data even with partial errors
    users = result.data.get(User, [])

except ValidationError as e:
    print(f"Validation failed: {e}")
```

## Use Cases

- **LLM Structured Output** - Parse and validate AI-generated data
- **Configuration Files** - Type-safe config loading
- **API Responses** - Validate ISON API data
- **Data Pipelines** - Transform and validate ISON streams
- **RAG Systems** - Parse retrieved ISON documents

## Comparison with Pydantic

| Feature | ISONantic | Pydantic |
|---------|-----------|----------|
| Format | ISON | JSON |
| Token efficiency | High | Lower |
| Cross-record refs | Built-in | Manual |
| LLM optimization | Yes | No |
| Schema generation | ISON-native | JSON Schema |

## Test Results

All tests passing:

```
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-8.4.1

tests/test_isonantic.py::TestBasicModels::test_create_simple_model PASSED
tests/test_isonantic.py::TestBasicModels::test_model_with_reference PASSED
tests/test_isonantic.py::TestBasicModels::test_field_constraints PASSED
tests/test_isonantic.py::TestBasicModels::test_string_pattern_validation PASSED
tests/test_isonantic.py::TestBasicModels::test_min_max_length PASSED
tests/test_isonantic.py::TestBasicModels::test_choices_validation PASSED
tests/test_isonantic.py::TestValidators::test_field_validator PASSED
tests/test_isonantic.py::TestValidators::test_root_validator PASSED
tests/test_isonantic.py::TestValidators::test_computed_field PASSED
tests/test_isonantic.py::TestParsing::test_parse_single_model PASSED
tests/test_isonantic.py::TestParsing::test_parse_with_references PASSED
tests/test_isonantic.py::TestParsing::test_parse_safe PASSED
tests/test_isonantic.py::TestParsing::test_parse_null_values PASSED
tests/test_isonantic.py::TestDocument::test_parse_document PASSED
tests/test_isonantic.py::TestDocument::test_reference_resolution PASSED
tests/test_isonantic.py::TestDocument::test_reference_validation PASSED
tests/test_isonantic.py::TestDocument::test_document_serialization PASSED
tests/test_isonantic.py::TestLLMParsing::test_parse_clean_llm_output PASSED
tests/test_isonantic.py::TestLLMParsing::test_parse_llm_with_extra_text PASSED
tests/test_isonantic.py::TestLLMParsing::test_parse_llm_code_block PASSED
tests/test_isonantic.py::TestLLMParsing::test_llm_parse_error PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_generate_model_schema PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_prompt_for_model PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_json_schema_generation PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_json_schema_with_constraints PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_json_schema_with_pattern PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_json_schema_with_choices PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_json_schema_with_reference PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_json_schema_json_output PASSED
tests/test_isonantic.py::TestSchemaGeneration::test_pydantic_v1_compatibility PASSED
tests/test_isonantic.py::TestSerialization::test_model_to_dict PASSED
tests/test_isonantic.py::TestSerialization::test_model_with_reference_to_dict PASSED
tests/test_isonantic.py::TestSerialization::test_model_to_ison_table PASSED
tests/test_isonantic.py::TestSerialization::test_model_copy PASSED
tests/test_isonantic.py::TestEdgeCases::test_empty_ison PASSED
tests/test_isonantic.py::TestEdgeCases::test_missing_required_field PASSED
tests/test_isonantic.py::TestEdgeCases::test_extra_fields_ignored PASSED
tests/test_isonantic.py::TestEdgeCases::test_quoted_strings_with_spaces PASSED
tests/test_isonantic.py::TestEdgeCases::test_special_characters_in_strings PASSED

============================= 39 passed in 0.09s ==============================
```

Run tests with:
```bash
pytest tests/
```

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [ISON Specification](https://www.ison.dev/spec.html)
- [GitHub](https://github.com/maheshvaikri-code/ison)
- [ison-py](https://pypi.org/project/ison-py/)

## License

MIT License - see [LICENSE](LICENSE) for details.
