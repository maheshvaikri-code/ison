<p align="center">
  <img src="https://raw.githubusercontent.com/maheshvaikri-code/ison/main/images/ison_logo_git.png" alt="ISON Logo">
</p>

# ison-go

Go parser and serializer for ISON (Interchange Simple Object Notation) - a minimal, token-efficient data format optimized for LLMs and Agentic AI workflows.

[![Go Reference](https://pkg.go.dev/badge/github.com/maheshvaikri-code/ison/ison-go.svg)](https://pkg.go.dev/github.com/maheshvaikri-code/ison/ison-go)
[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8.svg)](https://go.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-40%20passed-brightgreen.svg)]()

## Features

- **Full ISON Support** - Parse and serialize ISON format
- **Type Inference** - Automatic detection of int, float, bool, null, string
- **References** - Support for `:id`, `:namespace:id`, `:RELATIONSHIP:id`
- **Type Annotations** - Field type hints (`field:int`, `field:string`, etc.)
- **ISONL Streaming** - Line-based format for large datasets with Go channels
- **File I/O** - Load/Dump for ISON and ISONL files
- **JSON Conversion** - Bidirectional ISON ↔ JSON conversion
- **FromDict** - Create documents from maps with auto-refs and smart ordering
- **Zero Dependencies** - Only standard library (testify for tests)

## Installation

```bash
go get github.com/maheshvaikri-code/ison/ison-go
```

## Quick Start

```go
package main

import (
    "fmt"
    "github.com/maheshvaikri-code/ison/ison-go"
)

func main() {
    // Parse ISON
    doc, err := ison.Parse(`
table.users
id:int name:string email active:bool
1 Alice alice@example.com true
2 Bob bob@example.com false
`)
    if err != nil {
        panic(err)
    }

    // Access data
    users, _ := doc.Get("users")
    for _, row := range users.Rows {
        name, _ := row["name"].AsString()
        active, _ := row["active"].AsBool()
        fmt.Printf("%s (active: %v)\n", name, active)
    }

    // Convert to JSON
    jsonStr, _ := doc.ToJSON()
    fmt.Println(jsonStr)
}
```

## Usage

### Parsing ISON

```go
// Parse from string
doc, err := ison.Parse(`
table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com
`)

// Access blocks
users, ok := doc.Get("users")
if ok {
    fmt.Printf("Found %d users\n", len(users.Rows))
}

// Access field values
for _, row := range users.Rows {
    // Type-safe access
    if id, ok := row["id"].AsInt(); ok {
        fmt.Printf("ID: %d\n", id)
    }
    if name, ok := row["name"].AsString(); ok {
        fmt.Printf("Name: %s\n", name)
    }
}
```

### Value Types

```go
// Create values
nullVal := ison.Null()
boolVal := ison.Bool(true)
intVal := ison.Int(42)
floatVal := ison.Float(3.14)
strVal := ison.String("hello")
refVal := ison.Ref(ison.Reference{ID: "1", Namespace: "user"})

// Check types
if nullVal.IsNull() {
    fmt.Println("Value is null")
}

// Safe type conversion
if i, ok := intVal.AsInt(); ok {
    fmt.Printf("Integer: %d\n", i)
}

// Get raw interface{}
raw := intVal.Interface() // returns int64(42)
```

### References

```go
// Parse references
doc, _ := ison.Parse(`
table.orders
id user_id product
1 :1 Widget
2 :user:42 Gadget
3 :OWNS:5 Gizmo
`)

orders, _ := doc.Get("orders")
for _, row := range orders.Rows {
    if ref, ok := row["user_id"].AsRef(); ok {
        fmt.Printf("ID: %s\n", ref.ID)
        fmt.Printf("Namespace: %s\n", ref.Namespace)
        fmt.Printf("Is Relationship: %v\n", ref.IsRelationship())
        fmt.Printf("ISON format: %s\n", ref.ToISON())
    }
}
```

### Serialization

```go
// Create document programmatically
doc := ison.NewDocument()
block := ison.NewBlock("table", "users")
block.AddField("id", "int")
block.AddField("name", "string")
block.AddRow(ison.Row{
    "id":   ison.Int(1),
    "name": ison.String("Alice"),
})
doc.AddBlock(block)

// Serialize to ISON
output := ison.Dumps(doc)
fmt.Println(output)
// Output:
// table.users
// id:int name:string
// 1 Alice
```

### ISONL Streaming Format

```go
// Parse ISONL
doc, _ := ison.ParseISONL(`table.users|id:int name:string|1 Alice
table.users|id:int name:string|2 Bob`)

// Serialize to ISONL
output := ison.DumpsISONL(doc)
```

### JSON Conversion

```go
// ISON to JSON
jsonStr, err := ison.ToJSON(`
table.users
id:int name:string
1 Alice
2 Bob
`)

// JSON to ISON Document
doc, err := ison.FromJSON(`{
    "users": [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"}
    ]
}`)
output := ison.Dumps(doc)
```

## ISON Format Reference

```
# Comments start with #

table.users                          # Block: kind.name
id:int name:string email active:bool # Fields with optional types
1 Alice alice@example.com true       # Data rows (space-separated)
2 "Bob Smith" bob@example.com false  # Quoted strings for spaces
3 ~ ~ true                           # ~ or null for null values

table.orders
id user_id product
1 :1 Widget                          # :1 = reference to id 1
2 :user:42 Gadget                    # :user:42 = namespaced reference
3 :OWNS:5 Gizmo                      # :OWNS:5 = relationship reference

object.config                        # Single-row object block
key value
debug true
---                                  # Summary separator
count 100                            # Summary row
```

### File I/O

```go
// Load from file
doc, err := ison.Load("data.ison")

// Save to file
err := ison.Dump(doc, "output.ison")

// Load/Save ISONL files
doc, err := ison.LoadISONL("stream.isonl")
err := ison.DumpISONL(doc, "stream.isonl")
```

### ISONL Conversion

```go
// Convert ISON to ISONL
isonlText, err := ison.ISONToISONL(isonText)

// Convert ISONL to ISON
isonText, err := ison.ISONLToISON(isonlText)
```

### Streaming ISONL with Channels

```go
file, _ := os.Open("large_data.isonl")
defer file.Close()

// Stream records via channel
for record := range ison.ISONLStream(file) {
    name, _ := record.Values["name"].AsString()
    fmt.Printf("Processing: %s\n", name)
}
```

### FromDict with Options

```go
data := map[string]interface{}{
    "users": []interface{}{
        map[string]interface{}{"id": 1, "name": "Alice"},
    },
}

// Basic conversion
doc := ison.FromDict(data)

// With auto-refs and smart ordering
opts := ison.FromDictOptions{
    AutoRefs:   true,  // Convert foreign keys to references
    SmartOrder: true,  // Reorder columns for optimal LLM comprehension
}
doc := ison.FromDictWithOptions(data, opts)
```

### Serialization Options

```go
opts := ison.DumpsOptions{
    Delimiter:    "\t",  // Use tabs instead of spaces
    AlignColumns: true,   // Pad columns for alignment
}
output := ison.DumpsWithOptions(doc, opts)
```

## API Reference

### Types

| Type | Description |
|------|-------------|
| `Document` | Container for multiple blocks |
| `Block` | Table or object block with fields and rows |
| `Row` | Map of field names to values |
| `Value` | Type-safe value (null, bool, int, float, string, reference) |
| `Reference` | ISON reference with ID, namespace, and relationship |
| `FieldInfo` | Field name and type hint |

### Functions

| Function | Description |
|----------|-------------|
| `Parse(text string)` | Parse ISON text into Document |
| `ParseISONL(text string)` | Parse ISONL streaming format |
| `Dumps(doc *Document)` | Serialize Document to ISON |
| `DumpsWithOptions(doc, opts)` | Serialize with custom delimiter |
| `DumpsISONL(doc *Document)` | Serialize to ISONL format |
| `Load(path string)` | Load Document from ISON file |
| `Dump(doc, path)` | Save Document to ISON file |
| `LoadISONL(path string)` | Load from ISONL file |
| `DumpISONL(doc, path)` | Save to ISONL file |
| `ISONToISONL(text)` | Convert ISON to ISONL |
| `ISONLToISON(text)` | Convert ISONL to ISON |
| `ISONLStream(reader)` | Stream ISONL via channel |
| `FromDict(data)` | Create Document from map |
| `FromDictWithOptions(data, opts)` | Create with auto-refs/smart order |
| `ToJSON(isonText string)` | Convert ISON to JSON string |
| `FromJSON(jsonText string)` | Convert JSON to Document |

### Value Constructors

| Function | Description |
|----------|-------------|
| `Null()` | Create null value |
| `Bool(v bool)` | Create boolean value |
| `Int(v int64)` | Create integer value |
| `Float(v float64)` | Create float value |
| `String(v string)` | Create string value |
| `Ref(r Reference)` | Create reference value |

## Test Results

```
=== RUN   TestVersion
--- PASS: TestVersion
=== RUN   TestParseSimpleTable
--- PASS: TestParseSimpleTable
=== RUN   TestParseTypedFields
--- PASS: TestParseTypedFields
=== RUN   TestParseQuotedStrings
--- PASS: TestParseQuotedStrings
=== RUN   TestParseNullValues
--- PASS: TestParseNullValues
=== RUN   TestParseReferences
--- PASS: TestParseReferences
=== RUN   TestParseObjectBlock
--- PASS: TestParseObjectBlock
=== RUN   TestParseMultipleBlocks
--- PASS: TestParseMultipleBlocks
=== RUN   TestParseSummaryRow
--- PASS: TestParseSummaryRow
=== RUN   TestParseComments
--- PASS: TestParseComments
=== RUN   TestDumps
--- PASS: TestDumps
=== RUN   TestRoundtrip
--- PASS: TestRoundtrip
=== RUN   TestDumpsISONL
--- PASS: TestDumpsISONL
=== RUN   TestParseISONL
--- PASS: TestParseISONL
=== RUN   TestToJSON
--- PASS: TestToJSON
=== RUN   TestFromJSON
--- PASS: TestFromJSON
... and 12 more tests

PASS
ok      github.com/maheshvaikri-code/ison/ison-go    0.XXXs
```

## Links

- [ISON Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [GitHub Repository](https://github.com/maheshvaikri-code/ison)
- [ISON Specification](https://www.ison.dev/spec.html)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

**Mahesh Vaikri**

- Website: [www.ison.dev](https://www.ison.dev)
- GitHub: [@maheshvaikri-code](https://github.com/maheshvaikri-code)
