<p align="center">
  <img src="https://raw.githubusercontent.com/maheshvaikri-code/ison/main/images/ison_logo_git.png" alt="ISON Logo">
</p>

# isonantic-go

Zod-like validation and type-safe schemas for ISON format in Go.

[![Go Reference](https://pkg.go.dev/badge/github.com/maheshvaikri-code/ison/isonantic-go.svg)](https://pkg.go.dev/github.com/maheshvaikri-code/ison/isonantic-go)
[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8.svg)](https://go.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-55%20passed-brightgreen.svg)]()

## Features

- **Zod-like API** - Familiar schema definition syntax with fluent methods
- **Type Safety** - Strong Go typing with runtime validation
- **Comprehensive Validators** - String, Number, Boolean, Reference, Object, Array, Table
- **Custom Refinements** - Add your own validation logic
- **ISON-native** - First-class support for ISON tables and references
- **Detailed Errors** - Structured validation errors with field paths

## Installation

```bash
go get github.com/maheshvaikri-code/ison/isonantic-go
```

## Quick Start

```go
package main

import (
    "fmt"
    ison "github.com/maheshvaikri-code/ison/ison-go"
    "github.com/maheshvaikri-code/ison/isonantic-go"
)

func main() {
    // Define schemas using the I namespace (like Zod's z)
    userSchema := isonantic.I.Table("users", map[string]isonantic.Schema{
        "id":     isonantic.I.Int(),
        "name":   isonantic.I.String().Min(1).Max(100),
        "email":  isonantic.I.String().Email(),
        "active": isonantic.I.Bool().Default(true),
    })

    orderSchema := isonantic.I.Table("orders", map[string]isonantic.Schema{
        "id":      isonantic.I.String(),
        "user_id": isonantic.I.Ref(),
        "total":   isonantic.I.Number().Positive(),
    })

    // Create document schema
    docSchema := isonantic.Document(map[string]isonantic.Schema{
        "users":  userSchema,
        "orders": orderSchema,
    })

    // Parse ISON
    doc, _ := ison.Parse(`
table.users
id name email active
1 Alice alice@example.com true
2 Bob bob@example.com false

table.orders
id user_id total
O1 :1 99.99
O2 :2 149.50
`)

    // Validate
    result := docSchema.SafeParse(doc.ToDict())
    if result.Success {
        fmt.Println("Document is valid!")
    } else {
        fmt.Println("Validation errors:", result.Error)
    }
}
```

## Schema Types

### Primitives

```go
isonantic.String()    // String validation
isonantic.Number()    // Number validation (float64)
isonantic.Int()       // Integer validation
isonantic.Float()     // Float validation (alias for Number)
isonantic.Boolean()   // Boolean validation
isonantic.Bool()      // Boolean validation (alias)
isonantic.Null()      // Null validation
```

### String Validations

```go
isonantic.String().
    Min(5).            // Minimum length
    Max(100).          // Maximum length
    Length(10).        // Exact length
    Email().           // Email format
    URL().             // URL format
    Regex(pattern).    // Custom regex
    Optional().        // Mark as optional
    Default("N/A").    // Default value
    Describe("...").   // Add description
    Refine(fn, msg)    // Custom validation
```

### Number Validations

```go
isonantic.Number().
    Min(0).            // Minimum value
    Max(100).          // Maximum value
    Positive().        // Must be > 0
    Negative().        // Must be < 0
    Optional().
    Default(0).
    Refine(fn, msg)

isonantic.Int()        // Must be integer (no decimals)
```

### References

```go
isonantic.Ref()                    // ISON reference (:id or :ns:id)
isonantic.Reference()              // Alias for Ref()
isonantic.Ref().Namespace("user")  // Require specific namespace
isonantic.Ref().Relationship("OWNS") // Require relationship reference
```

### Complex Types

```go
// Object schema
isonantic.Object(map[string]isonantic.Schema{
    "name": isonantic.String(),
    "age":  isonantic.Int(),
})

// Array schema
isonantic.Array(isonantic.String()).
    Min(1).    // Minimum items
    Max(10)    // Maximum items

// Table schema (ISON-specific)
isonantic.Table("users", map[string]isonantic.Schema{
    "id":   isonantic.Int(),
    "name": isonantic.String(),
})
```

### I Namespace

Use the `I` namespace for cleaner code (similar to Zod's `z`):

```go
import i "github.com/maheshvaikri-code/ison/isonantic-go"

schema := i.I.Table("users", map[i.Schema]i.Schema{
    "id":    i.I.Int(),
    "name":  i.I.String().Min(1),
    "email": i.I.String().Email(),
})
```

## Object Schema Operations

### Extend

```go
baseSchema := isonantic.Object(map[string]isonantic.Schema{
    "id":   isonantic.Int(),
    "name": isonantic.String(),
})

extendedSchema := baseSchema.Extend(map[string]isonantic.Schema{
    "email": isonantic.String().Email(),
})
```

### Pick

```go
fullSchema := isonantic.Object(map[string]isonantic.Schema{
    "id":    isonantic.Int(),
    "name":  isonantic.String(),
    "email": isonantic.String(),
})

partialSchema := fullSchema.Pick("id", "name")
```

### Omit

```go
partialSchema := fullSchema.Omit("email")
```

## Document Validation

```go
schema := isonantic.Document(map[string]isonantic.Schema{
    "users": isonantic.Table("users", map[string]isonantic.Schema{
        "id":   isonantic.Int(),
        "name": isonantic.String(),
    }),
    "config": isonantic.Object(map[string]isonantic.Schema{
        "debug": isonantic.Boolean(),
    }),
})

// Parse with validation (throws error)
result, err := schema.Parse(doc)
if err != nil {
    // Handle validation errors
}

// Safe parse (no throw)
result := schema.SafeParse(doc)
if result.Success {
    fmt.Println("Valid:", result.Data)
} else {
    fmt.Println("Errors:", result.Error)
}
```

## Error Handling

```go
import "github.com/maheshvaikri-code/ison/isonantic-go"

_, err := schema.Parse(invalidData)
if err != nil {
    if verrs, ok := err.(isonantic.ValidationErrors); ok {
        for _, e := range verrs.Errors {
            fmt.Printf("%s: %s (value: %v)\n",
                e.Field, e.Message, e.Value)
        }
    }
}

// Or use SafeParse
result := schema.SafeParse(data)
if !result.Success {
    verrs := result.Error.(isonantic.ValidationErrors)
    for _, e := range verrs.Errors {
        fmt.Printf("%s: %s\n", e.Field, e.Message)
    }
}
```

## Custom Refinements

```go
// String refinement
passwordSchema := isonantic.String().
    Min(8).
    Refine(func(s string) bool {
        hasUpper := false
        hasDigit := false
        for _, r := range s {
            if r >= 'A' && r <= 'Z' { hasUpper = true }
            if r >= '0' && r <= '9' { hasDigit = true }
        }
        return hasUpper && hasDigit
    }, "password must contain uppercase and digit")

// Number refinement
evenSchema := isonantic.Int().
    Refine(func(n float64) bool {
        return int(n) % 2 == 0
    }, "number must be even")
```

## Test Results

```
=== RUN   TestVersion
--- PASS: TestVersion
=== RUN   TestStringRequired
--- PASS: TestStringRequired
=== RUN   TestStringMinLength
--- PASS: TestStringMinLength
=== RUN   TestStringEmail
--- PASS: TestStringEmail
=== RUN   TestNumberPositive
--- PASS: TestNumberPositive
=== RUN   TestIntSchema
--- PASS: TestIntSchema
=== RUN   TestBooleanRequired
--- PASS: TestBooleanRequired
=== RUN   TestRefRequired
--- PASS: TestRefRequired
=== RUN   TestObjectFieldValidation
--- PASS: TestObjectFieldValidation
=== RUN   TestObjectExtend
--- PASS: TestObjectExtend
=== RUN   TestArrayItemValidation
--- PASS: TestArrayItemValidation
=== RUN   TestTableRowValidation
--- PASS: TestTableRowValidation
=== RUN   TestDocumentParse
--- PASS: TestDocumentParse
=== RUN   TestDocumentSafeParse
--- PASS: TestDocumentSafeParse
... and 41 more tests

PASS
ok      github.com/maheshvaikri-code/ison/isonantic-go    0.XXXs
```

## API Reference

### Schema Types

| Type | Description |
|------|-------------|
| `StringSchema` | String validation with length, format, regex |
| `NumberSchema` | Number validation with range, positive/negative |
| `BooleanSchema` | Boolean validation |
| `NullSchema` | Null value validation |
| `RefSchema` | ISON reference validation |
| `ObjectSchema` | Object structure validation |
| `ArraySchema` | Array validation with item schema |
| `TableSchema` | ISON table block validation |
| `DocumentSchema` | Complete ISON document validation |

### Common Methods

| Method | Description |
|--------|-------------|
| `.Optional()` | Mark field as optional |
| `.Default(v)` | Set default value |
| `.Describe(s)` | Add description |
| `.Refine(fn, msg)` | Custom validation |

### Validation Results

| Type | Description |
|------|-------------|
| `ValidationError` | Single error with field, message, value |
| `ValidationErrors` | Collection of validation errors |
| `SafeParseResult` | Result struct with Success, Data, Error |

## Links

- [ISON Go Parser](https://github.com/maheshvaikri-code/ison/tree/main/ison-go)
- [ISON Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [GitHub Repository](https://github.com/maheshvaikri-code/ison)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

**Mahesh Vaikri**

- Website: [www.ison.dev](https://www.ison.dev)
- GitHub: [@maheshvaikri-code](https://github.com/maheshvaikri-code)
