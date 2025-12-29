# ison-rs

[![Crates.io](https://img.shields.io/crates/v/ison-rs.svg)](https://crates.io/crates/ison-rs)
[![Documentation](https://docs.rs/ison-rs/badge.svg)](https://docs.rs/ison-rs)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-9%20passed-brightgreen.svg)]()

A Rust implementation of the ISON (Interchange Simple Object Notation) parser.

ISON is a minimal, LLM-friendly data serialization format optimized for:
- Graph databases
- Multi-agent systems
- RAG pipelines
- Token-efficient AI/ML workflows

## Features

- **Zero-copy parsing** where possible
- **Full ISON Support**: Tables, objects, references, type annotations
- **ISONL Streaming**: Line-based format for large datasets
- **Serde Integration**: Optional JSON export via serde
- **No unsafe code**: Safe Rust implementation

## Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
ison-rs = "1.0"

# With serde/JSON support (default)
ison-rs = { version = "1.0", features = ["serde"] }

# Without serde (smaller binary)
ison-rs = { version = "1.0", default-features = false }
```

## Quick Start

```rust
use ison_parser::{parse, dumps, Value};

fn main() -> Result<(), ison_parser::ISONError> {
    let ison_text = r#"
table.users
id:int name:string email active:bool
1 Alice alice@example.com true
2 Bob bob@example.com false
"#;

    let doc = parse(ison_text)?;
    let users = doc.get("users").unwrap();

    println!("Users: {}", users.len());

    for row in &users.rows {
        let id = row.get("id").and_then(|v| v.as_int()).unwrap_or(0);
        let name = row.get("name").and_then(|v| v.as_str()).unwrap_or("");
        let active = row.get("active").and_then(|v| v.as_bool()).unwrap_or(false);

        println!("{}: {} (active: {})", id, name, active);
    }

    // Serialize back to ISON
    let output = dumps(&doc, true);
    println!("{}", output);

    Ok(())
}
```

## API Reference

### Parsing

```rust
use ison_parser::{parse, loads, loads_isonl};

// Parse from string
let doc = parse(text)?;
let doc = loads(text)?;  // Alias

// Parse ISONL
let doc = loads_isonl(isonl_text)?;
```

### Serialization

```rust
use ison_parser::{dumps, dumps_isonl};

// To ISON string
let ison = dumps(&doc, true);   // With column alignment
let ison = dumps(&doc, false);  // Without alignment

// To ISONL
let isonl = dumps_isonl(&doc);

// To JSON (requires serde feature)
let json = doc.to_json(true);   // Pretty-printed
let json = doc.to_json(false);  // Compact
```

### Document Access

```rust
let doc = parse(text)?;

// Check if block exists
if doc.has("users") {
    let users = doc.get("users").unwrap();

    // Block properties
    users.kind;       // "table", "object", "meta"
    users.name;       // "users"
    users.len();      // Row count
    users.fields;     // Field names

    // Access rows
    for row in &users.rows {
        // Row is HashMap<String, Value>
    }

    // Index access
    let first_row = &users[0];
}
```

### Value Types

```rust
use ison_parser::Value;

// Value is an enum
match value {
    Value::Null => {},
    Value::Bool(b) => {},
    Value::Int(i) => {},
    Value::Float(f) => {},
    Value::String(s) => {},
    Value::Reference(r) => {},
}

// Type checking
value.is_null();
value.is_bool();
value.is_int();
value.is_float();
value.is_string();
value.is_reference();

// Value extraction (returns Option)
let b: Option<bool> = value.as_bool();
let i: Option<i64> = value.as_int();
let f: Option<f64> = value.as_float();
let s: Option<&str> = value.as_str();
let r: Option<&Reference> = value.as_reference();
```

### References

```rust
use ison_parser::Reference;

// Simple reference :42
let ref1 = Reference::new("42");
ref1.to_ison();  // ":42"

// Namespaced reference :user:101
let ref2 = Reference::with_type("101", "user");
ref2.get_namespace();    // Some("user")
ref2.is_relationship();  // false

// Relationship reference :MEMBER_OF:10
let ref3 = Reference::with_type("10", "MEMBER_OF");
ref3.is_relationship();      // true
ref3.relationship_type();    // Some("MEMBER_OF")
```

### Creating Documents Programmatically

```rust
use ison_parser::{Document, Block, FieldInfo, Value};
use std::collections::HashMap;

let mut doc = Document::new();

let mut block = Block::new("table", "users");
block.fields = vec!["id".to_string(), "name".to_string()];
block.field_info = vec![
    FieldInfo::with_type("id", "int"),
    FieldInfo::with_type("name", "string"),
];

let mut row = HashMap::new();
row.insert("id".to_string(), Value::Int(1));
row.insert("name".to_string(), Value::String("Alice".to_string()));
block.rows.push(row);

doc.blocks.push(block);

let ison = dumps(&doc, true);
```

### Field Info

```rust
// Access type annotations
for fi in &block.field_info {
    fi.name;        // Field name
    fi.field_type;  // Option<String> type annotation
    fi.is_computed; // true if type is "computed"
}

// Query field types
let field_type = block.get_field_type("price");  // Option<&str>
let computed = block.get_computed_fields();      // Vec<&str>
```

### ISONL Format

ISONL is a line-based streaming format where each line is self-contained:

```
table.users|id name email|1 Alice alice@example.com
table.users|id name email|2 Bob bob@example.com
```

```rust
use ison_parser::{ison_to_isonl, isonl_to_ison};

// Convert between formats
let isonl = ison_to_isonl(ison_text)?;
let ison = isonl_to_ison(isonl_text)?;
```

## Error Handling

```rust
use ison_parser::{parse, ISONError};

match parse(text) {
    Ok(doc) => {
        // Use document
    }
    Err(e) => {
        eprintln!("Parse error: {}", e);
        if let Some(line) = e.line {
            eprintln!("At line: {}", line);
        }
    }
}
```

## ISON Format Quick Reference

```
# Comment

table.users                    # Block header: kind.name
id:int name:string active:bool # Field definitions with optional types
1 Alice true                   # Data rows
2 "Bob Smith" false           # Quoted strings for spaces
3 ~ null                       # null values (~ or null)

table.orders
id user_id product
1 :1 Widget                    # :1 = reference to id 1
2 :user:42 Gadget             # :user:42 = namespaced reference
3 :MEMBER_OF:10 Thing          # :MEMBER_OF:10 = relationship reference

object.config                  # Single-row object block
key value
debug true
---                            # Summary separator
Total 100                      # Summary row
```

## Test Results

All tests passing:

```
running 9 tests
test tests::test_dumps_with_delimiter ... ok
test tests::test_isonl ... ok
test tests::test_ison_to_json ... ok
test tests::test_json_to_ison ... ok
test tests::test_parse_references ... ok
test tests::test_parse_simple_table ... ok
test tests::test_roundtrip ... ok
test tests::test_type_inference ... ok
test tests::test_version ... ok

test result: ok. 9 passed; 0 failed; 0 ignored

Doc-tests ison_rs
test result: ok. 1 passed; 0 failed; 1 ignored
```

Run tests with:
```bash
cargo test
```

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [Crates.io](https://crates.io/crates/ison-rs)
- [API Docs](https://docs.rs/ison-rs)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## License

MIT License
