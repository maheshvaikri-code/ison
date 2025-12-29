<p align="center">
  <img src="images/ison_logo_git.png" alt="ISON Logo">
</p>


<p align="center">
  <h2>
  A minimal, token-efficient data format optimized for LLMs and Agentic AI workflows.
  </h2>
</p>

<p align="center">
  <a href="https://github.com/maheshvaikri-code/ison/releases"><img src="https://img.shields.io/badge/version-1.0.1-blue.svg" alt="Version 1.0.1"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.npmjs.com/package/ison-parser"><img src="https://img.shields.io/npm/v/ison-parser.svg" alt="NPM"></a>
  <a href="https://pypi.org/project/ison-py"><img src="https://img.shields.io/pypi/v/ison-py.svg" alt="PyPI"></a>
  <a href="https://crates.io/crates/ison-rs"><img src="https://img.shields.io/crates/v/ison-rs.svg" alt="Crates.io"></a>
</p>
<p align="center"> Author: Mahesh Vaikri</p>

---

<p align="center">
  <em>
    ISON (Interchange Simple Object Notation) is a minimal data interchange format optimized for Large Language Models.
    It is easy for humans to read and write. It is easy for LLMs to understand and generate.
    It is based on familiar tabular and relational patterns that language models have seen billions of times in training data.
  </em>
</p>

<p align="center">
  <em>
    ISON is a text format that is completely language independent but represents data in a way that maximizes token efficiency
    and minimizes cognitive load for AI systems. These properties make ISON an ideal data interchange format for AI and LLM workflows.
  </em>
</p>

---

## Why ISON?

ISON reduces token usage by **30-70%** compared to JSON while remaining human-readable and LLM-friendly.

```
JSON (87 tokens)                    ISON (34 tokens)
─────────────────                   ─────────────────
{                                   table.users
  "users": [                        id:int name:string email active:bool
    {                               1 Alice alice@example.com true
      "id": 1,                      2 Bob bob@example.com false
      "name": "Alice",              3 Charlie charlie@example.com true
      "email": "alice@example.com",
      "active": true
    },
    {
      "id": 2,
      "name": "Bob",
      "email": "bob@example.com",
      "active": false
    },
    {
      "id": 3,
      "name": "Charlie",
      "email": "charlie@example.com",
      "active": true
    }
  ]
}
```

**Perfect for:**
- Multi-agent systems
- RAG pipelines
- Graph databases
- Token-constrained AI/ML, LLM, Agentic AI workflows
- LLM function calling

---

## Quick Start

### Installation

**JavaScript/TypeScript:**
```bash
npm install ison-parser    # JavaScript
npm install ison-ts        # TypeScript with full types
npm install isonantic-ts   # Validation & schemas
```

**Python:**
```bash
pip install ison-py        # Parser
pip install isonantic      # Validation & schemas
```

**Rust:**
```toml
[dependencies]
ison-rs = "1.0"
isonantic-rs = "1.0"       # Validation & schemas
```

**C++ (Header-only):**
```bash
# Just copy the header
cp ison-cpp/include/ison_parser.hpp /your/project/
```

### Usage Examples

**JavaScript:**
```javascript
import { parse, dumps, toJSON } from 'ison-parser';

const doc = parse(`
table.users
id:int name:string active:bool
1 Alice true
2 Bob false
`);

console.log(doc.users.rows);
// [{ id: 1, name: 'Alice', active: true }, ...]

console.log(toJSON(doc));
// Standard JSON output
```

**Python:**
```python
from ison_py import parse, dumps, to_json

doc = parse("""
table.users
id:int name:string active:bool
1 Alice true
2 Bob false
""")

for row in doc['users']['rows']:
    print(f"{row['id']}: {row['name']}")

# Convert to JSON
print(to_json(doc))
```

**Rust:**
```rust
use ison_rs::{parse, dumps};

let doc = parse(r#"
table.users
id:int name:string active:bool
1 Alice true
2 Bob false
"#)?;

let users = doc.get("users").unwrap();
for row in &users.rows {
    let name = row.get("name").and_then(|v| v.as_str()).unwrap();
    println!("{}", name);
}
```

**C++:**
```cpp
#include "ison_parser.hpp"

auto doc = ison::parse(R"(
table.users
id:int name:string active:bool
1 Alice true
2 Bob false
)");

for (const auto& row : doc["users"].rows) {
    std::cout << ison::as_string(row.at("name")) << std::endl;
}
```

---

## ISON Format

```
# Comments start with #

table.users                        # Block: kind.name
id:int name:string email active:bool   # Fields with optional types
1 Alice alice@example.com true     # Data rows (space-separated)
2 "Bob Smith" bob@example.com false    # Quoted strings for spaces
3 ~ ~ true                         # ~ or null for null values

table.orders
id user_id product
1 :1 Widget                        # :1 = reference to id 1
2 :user:42 Gadget                  # :user:42 = namespaced reference

object.config                      # Single-row object block
key value
debug true
---                                # Summary separator
count 100                          # Summary row
```

### ISONL (Streaming Format)

For large datasets, use line-based ISONL where each line is self-contained:

```
table.users|id name email|1 Alice alice@example.com
table.users|id name email|2 Bob bob@example.com
```

---

## Packages

| Ecosystem | Parser | Validation | Status |
|-----------|--------|------------|--------|
| **NPM** | [ison-parser](https://www.npmjs.com/package/ison-parser) | [isonantic-ts](https://www.npmjs.com/package/isonantic-ts) | 33 + 46 tests |
| **NPM** | [ison-ts](https://www.npmjs.com/package/ison-ts) | - | 23 tests |
| **PyPI** | [ison-py](https://pypi.org/project/ison-py) | [isonantic](https://pypi.org/project/isonantic) | 31 + 39 tests |
| **Crates.io** | [ison-rs](https://crates.io/crates/ison-rs) | [isonantic-rs](https://crates.io/crates/isonantic-rs) | 9 + 1 tests |
| **C++** | ison-cpp | isonantic-cpp | 30 tests |

**Total: 9 packages across 4 ecosystems, 208+ tests passing**

---

## Features

| Feature | Description |
|---------|-------------|
| **Tables** | Structured data with typed columns |
| **Objects** | Single-row key-value blocks |
| **References** | `:id`, `:type:id`, `:RELATIONSHIP:id` |
| **Type Annotations** | `field:int`, `field:string`, `field:bool`, `field:float` |
| **Computed Fields** | `field:computed` for derived values |
| **ISONL Streaming** | Line-based format for large datasets |
| **JSON Export** | Convert ISON to JSON |
| **Roundtrip** | Parse and serialize without data loss |

---

## Schema Validation (ISONantic)

Type-safe validation with fluent API:

```javascript
// JavaScript/TypeScript
import { table, string, int, boolean } from 'isonantic-ts';

const userSchema = table('users')
  .field('id', int().required())
  .field('name', string().min(1).max(100))
  .field('email', string().email())
  .field('active', boolean().default(true));

const users = userSchema.validate(doc);
```

```python
# Python
from isonantic import table, string, int_, boolean

user_schema = (table('users')
    .field('id', int_().required())
    .field('name', string().min(1).max(100))
    .field('email', string().email())
    .field('active', boolean().default(True)))

users = user_schema.validate(doc)
```

---

## Documentation

- **Website:** [www.ison.dev](https://www.ison.dev)
- **Getting Started:** [www.getison.com](https://www.getison.com)
- **Specification:** [ISON v1.0 Spec](https://www.ison.dev/spec.html)
- **Playground:** [Interactive Demo](https://www.ison.dev/playground.html)

---

## Project Structure

```
ison/
├── ison-js/               # JavaScript parser (NPM: ison-parser)
├── ison-ts/               # TypeScript parser (NPM: ison-ts)
├── isonantic-ts/          # TypeScript validation (NPM: isonantic-ts)
├── ison-py/               # Python parser (PyPI: ison-py)
├── isonantic/             # Python validation (PyPI: isonantic)
├── ison-rust/             # Rust parser (Crates.io: ison-rs)
├── isonantic-rust/        # Rust validation (Crates.io: isonantic-rs)
├── ison-cpp/              # C++ header-only parser
├── isonantic-cpp/         # C++ header-only validation
├── benchmark/             # Token efficiency benchmarks
├── images/                # Logo and assets
├── LICENSE                # MIT License
└── README.md              # This file
```

---

## Development

```bash
# Clone the repository
git clone https://github.com/maheshvaikri-code/ison.git
cd ison

# JavaScript/TypeScript
cd ison-js && npm install && npm test
cd ison-ts && npm install && npm test
cd isonantic-ts && npm install && npm test

# Python
cd ison-py && pip install -e . && pytest
cd isonantic && pip install -e . && pytest

# Rust
cd ison-rust && cargo test
cd isonantic-rust && cargo test

# C++
cd ison-cpp && mkdir build && cd build && cmake .. && cmake --build . && ctest
```

---

## Test Results

<details>
<summary><strong>Click to expand test results (208+ tests passing)</strong></summary>

### JavaScript (ison-parser) - 33 tests
```
✓ parses basic table correctly
✓ handles quoted strings
✓ preserves type annotations
✓ handles references
✓ parses multiple tables
✓ converts to JSON correctly
✓ handles null values
✓ handles empty values in rows
✓ handles ISONL format
```

### TypeScript (ison-ts) - 23 tests
```
✓ should parse basic table
✓ should handle quoted strings
✓ should preserve type annotations
✓ should handle references
✓ should parse multiple tables
✓ should convert to JSON
✓ should handle null values
✓ should handle empty values
✓ should parse ISONL format
```

### TypeScript Validation (isonantic-ts) - 46 tests
```
✓ validates required string fields
✓ validates optional string fields
✓ validates string min/max length
✓ validates email format
✓ validates int/float/bool fields
✓ validates references
✓ validates table schemas
... and 39 more tests
```

### Python (ison-py) - 31 tests
```
✓ test_parse_basic_table
✓ test_parse_quoted_strings
✓ test_parse_type_annotations
✓ test_parse_references
✓ test_parse_multiple_tables
✓ test_to_json
✓ test_dumps / test_dumps_isonl
... and 24 more tests
```

### Python Validation (isonantic) - 39 tests
```
✓ test_string_field_required
✓ test_string_min_length
✓ test_email_validation
✓ test_int_field / test_float_field
✓ test_reference_field
✓ test_table_schema
... and 33 more tests
```

### Rust (ison-rs) - 9 tests
```
✓ test_dumps_with_delimiter
✓ test_isonl
✓ test_ison_to_json
✓ test_json_to_ison
✓ test_parse_references
✓ test_parse_simple_table
✓ test_roundtrip
✓ test_type_inference
✓ test_version
✓ doc-tests
```

### C++ (ison-cpp) - 30 tests
```
✓ parse_simple_table
✓ parse_object_block
✓ parse_multiple_blocks
✓ type_inference (int, float, bool, null, string)
✓ parse_references (simple, namespaced, relationship)
✓ serialize_roundtrip
✓ parse_isonl / serialize_isonl
✓ to_json
... and 15 more tests
```

</details>

---

## Benchmark Results 🏆

**300-Question Benchmark** across 20 datasets using GPT-4o tokenizer (o200k_base):

| Format | Total Tokens | vs JSON | Accuracy | Acc/1K Tokens |
|--------|-------------|---------|----------|---------------|
| **ISON** | **3,550** | **-72.0%** | 88.3% | **24.88** |
| TOON | 4,847 | -61.7% | 88.7% | 18.29 |
| JSON Compact | 7,339 | -42.1% | 89.0% | 12.13 |
| JSON | 12,668 | baseline | 84.7% | 6.68 |

### Key Results

- ✅ **ISON won ALL 20 token benchmarks**
- ✅ **272% more efficient than JSON** (Accuracy per 1K tokens)
- ✅ **27% more token-efficient than TOON**
- ✅ **3.6x more data in same context window**

👉 **[Full Benchmark Details](benchmark/BENCHMARK_300.md)** | **[Run the Benchmark](benchmark/)**

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Author

**Mahesh Vaikri**

- Website: [www.ison.dev](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- GitHub: [@maheshvaikri-code](https://github.com/maheshvaikri-code)

---

<p align="center">
  <strong>ISON</strong> - Less tokens, more context, better AI.
</p>
