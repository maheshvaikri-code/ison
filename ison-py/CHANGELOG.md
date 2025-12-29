# Changelog

## [1.0.1] - 2025-12-29

### Fixed
- **Field Order Preservation**: `from_dict()` now preserves the insertion order of fields instead of using a `set()` which randomized column order. This ensures consistent output matching the original data structure.

### Changed
- **Default Alignment**: `dumps()` now defaults to `align_columns=False` for token efficiency. Single space delimiter between columns is now the default. Use `align_columns=True` for human-readable padded output.

### Added
- **Delimiter Option**: New `delimiter` parameter in `dumps(doc, delimiter=' ')`:
  - Default is single space `' '` for maximum token efficiency
  - Use comma `','` for clearer column separation in data with quoted strings
  - Delimiter choice affects tokenization - space is generally more efficient

- **Auto-Reference Detection**: New `auto_refs` parameter in `from_dict(data, auto_refs=True)`:
  - Detects `*_id` suffix fields and converts to ISON references (e.g., `customer_id: 1` -> `:customer:1`)
  - Detects `nodes`/`edges` graph pattern and converts `source`/`target` to `:node:id` references
  - Improves LLM comprehension of relational data by making relationships explicit

- **Smart Column Ordering**: New `smart_order` parameter in `from_dict(data, smart_order=True)`:
  - Reorders columns for optimal LLM comprehension
  - Priority order: `id` (primary anchor) → `name/title/label` (human-readable) → data fields → `*_id` references
  - Reduces "column confusion" where LLMs return the correct row but wrong column value
  - No token overhead - just reordering existing columns

### Example
```python
import ison_parser

data = {
    "customers": [{"id": 1, "name": "Alice"}],
    "orders": [{"id": 101, "customer_id": 1, "total": 99.99}]
}

# With auto_refs=True
doc = ison_parser.from_dict(data, auto_refs=True)
print(ison_parser.dumps(doc, align_columns=False))

# Output:
# table.customers
# id name
# 1 Alice
#
# table.orders
# id customer_id total
# 101 :customer:1 99.99
```

## [1.0.0] - 2025-12-25

### Initial Release
- ISON v1.0 Reference Parser
- Full support for ISON and ISONL formats
- Reference syntax (`:id`, `:type:id`, `:RELATIONSHIP:id`)
- Type inference (int, float, bool, string, null)
- Quoted string handling with escape sequences
- CLI interface for parsing and conversion
- Plugins for SQLite, PostgreSQL, Chroma, Pinecone, Qdrant
- Integrations for OpenAI, Anthropic, LangChain, LlamaIndex
