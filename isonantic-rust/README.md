# isonantic-rs

Type-safe validation and schema definitions for ISON format in Rust.

[![Crates.io](https://img.shields.io/crates/v/isonantic-rs.svg)](https://crates.io/crates/isonantic-rs)
[![Documentation](https://docs.rs/isonantic-rs/badge.svg)](https://docs.rs/isonantic-rs)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Type-safe schemas** - Define ISON table schemas with full type safety
- **Validation** - Runtime validation with detailed error messages
- **Builder pattern** - Fluent API for defining fields and constraints
- **Custom validators** - Add custom validation logic

## Installation

```toml
[dependencies]
isonantic-rs = "1.0"
ison-rs = "1.0"
```

## Quick Start

```rust
use isonantic_rs::prelude::*;
use ison_rs::parse;

fn main() -> Result<()> {
    // Define a schema
    let user_schema = table("users")
        .field("id", int().required())
        .field("name", string().min(1).max(100))
        .field("email", string().email())
        .field("active", boolean().default_value(true));

    // Parse ISON
    let ison_text = r#"
table.users
id name email active
1 Alice alice@example.com true
2 Bob bob@example.com false
"#;

    let doc = parse(ison_text).expect("Parse failed");

    // Validate
    let users = user_schema.validate(&doc)?;

    // Access validated data
    for user in users.iter() {
        println!("{}: {}",
            user.get_int("id").unwrap(),
            user.get_string("name").unwrap()
        );
    }

    Ok(())
}
```

## Schema Types

### String Fields

```rust
string()                    // Basic string
    .min(5)                 // Minimum length
    .max(100)               // Maximum length
    .email()                // Email format validation
    .required()             // Required field
    .default_value("N/A")   // Default value
```

### Number Fields

```rust
int()                       // Integer field
    .min(0)                 // Minimum value
    .max(100)               // Maximum value
    .positive()             // Must be > 0
    .required()

float()                     // Float field
    .min(0.0)
    .max(100.0)
    .positive()
```

### Boolean Fields

```rust
boolean()
    .default_value(true)
    .required()
```

### Reference Fields

```rust
reference()                 // ISON reference (:id or :type:id)
    .required()
```

## Table Schema

```rust
let schema = table("orders")
    .field("id", string().required())
    .field("user_id", reference().required())
    .field("total", float().positive())
    .field("status", string().default_value("pending"));

let orders = schema.validate(&doc)?;
```

## Custom Validators

```rust
use isonantic_rs::validators::*;

// Built-in validators
string().not_empty()
string().one_of(vec!["active", "inactive", "pending"])

// Custom validator
let validator = custom(
    |value| {
        if let ValidatedValue::String(s) = value {
            s.starts_with("PRO-")
        } else {
            false
        }
    },
    "Must start with PRO-"
);
```

## Error Handling

```rust
match schema.validate(&doc) {
    Ok(table) => {
        // Use validated data
    }
    Err(e) => {
        println!("Validation failed:");
        for error in &e.errors {
            println!("  {}: {}", error.field, error.message);
        }
    }
}
```

## Accessing Validated Data

```rust
let users = schema.validate(&doc)?;

// Iterate rows
for row in users.iter() {
    // Type-safe getters
    let id: Option<i64> = row.get_int("id");
    let name: Option<&str> = row.get_string("name");
    let active: Option<bool> = row.get_bool("active");

    // Generic getter
    let value: Option<&ValidatedValue> = row.get("field");
}

// Index access
let first_user = &users[0];
```

## Test Results

All tests passing:

```
running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

Doc-tests isonantic_rs

running 1 test
test packages\isonantic-rust\src\lib.rs - (line 7) - compile ... ok

test result: ok. 1 passed; 0 failed; 0 ignored
```

Run tests with:
```bash
cargo test -p isonantic-rs
```

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [Crates.io](https://crates.io/crates/isonantic-rs)
- [API Docs](https://docs.rs/isonantic-rs)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## License

MIT License - see [LICENSE](LICENSE) for details.
