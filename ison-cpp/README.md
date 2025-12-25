# ison-cpp

A header-only C++17 implementation of the ISON (Interchange Simple Object Notation) parser.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++17](https://img.shields.io/badge/C++-17-blue.svg)](https://isocpp.org/)

**Compatible with llama.cpp and other modern C++ projects.**

ISON is a minimal, LLM-friendly data serialization format optimized for:
- Graph databases
- Multi-agent systems
- RAG pipelines
- Token-efficient AI/ML workflows

## Features

- **Header-only**: Just include `ison_parser.hpp`
- **Modern C++17**: Uses `std::variant`, `std::optional`, smart pointers
- **Full ISON Support**: Tables, objects, references, type annotations
- **ISONL Streaming**: Line-based format for large datasets
- **JSON Export**: Convert ISON to JSON
- **Type-safe**: Strong typing with helper functions

## Quick Start

### Installation

#### Option 1: Copy the header
```bash
cp include/ison_parser.hpp /your/project/include/
```

#### Option 2: CMake
```cmake
add_subdirectory(ison-parser-cpp)
target_link_libraries(your_target PRIVATE ison::parser)
```

#### Option 3: System install
```bash
mkdir build && cd build
cmake ..
sudo make install
```

### Basic Usage

```cpp
#include "ison_parser.hpp"
using namespace ison;

// Parse ISON string
std::string ison_text = R"(
table.users
id:int name:string email active:bool
1 Alice alice@example.com true
2 Bob bob@example.com false
)";

auto doc = parse(ison_text);

// Access blocks
auto& users = doc["users"];
std::cout << "Users: " << users.size() << std::endl;

// Access values with type checking
for (const auto& row : users.rows) {
    int64_t id = as_int(row.at("id"));
    const std::string& name = as_string(row.at("name"));
    bool active = as_bool(row.at("active"));

    std::cout << id << ": " << name << " (" << (active ? "active" : "inactive") << ")\n";
}

// Convert to JSON
std::string json = doc.to_json();

// Serialize back to ISON
std::string ison_output = dumps(doc);
```

## API Reference

### Parsing

```cpp
// Parse from string
Document doc = ison::parse(text);
Document doc = ison::loads(text);  // Alias

// Parse from file
Document doc = ison::load("data.ison");

// Parse ISONL
Document doc = ison::loads_isonl(isonl_text);
```

### Serialization

```cpp
// To ISON string
std::string ison = ison::dumps(doc);
std::string ison = ison::dumps(doc, false);  // No column alignment

// To file
ison::dump(doc, "output.ison");

// To ISONL
std::string isonl = ison::dumps_isonl(doc);

// To JSON
std::string json = doc.to_json();
std::string json = doc.to_json(4);  // Custom indent
```

### Document Access

```cpp
Document doc = parse(text);

// Check if block exists
if (doc.has("users")) {
    // Access by name
    Block& users = doc["users"];

    // Block properties
    users.kind;      // "table", "object", "meta"
    users.name;      // "users"
    users.size();    // Row count
    users.fields;    // Field names

    // Access rows
    for (const Row& row : users.rows) {
        // Row is std::map<std::string, Value>
    }
}
```

### Value Types

```cpp
// Type checking
is_null(value);
is_bool(value);
is_int(value);
is_float(value);
is_string(value);
is_reference(value);

// Value extraction (throws on wrong type)
bool b = as_bool(value);
int64_t i = as_int(value);
double d = as_float(value);
const std::string& s = as_string(value);
const Reference& r = as_reference(value);
```

### References

```cpp
// Simple reference :42
Reference ref("42");
ref.id;           // "42"
ref.to_ison();    // ":42"

// Namespaced reference :user:101
Reference ref("101", "user");
ref.id;              // "101"
ref.type;            // "user"
ref.get_namespace(); // "user"
ref.is_relationship(); // false

// Relationship reference :MEMBER_OF:10
Reference ref("10", "MEMBER_OF");
ref.is_relationship();     // true
ref.relationship_type();   // "MEMBER_OF"
```

### Field Info

```cpp
// Access type annotations
for (const FieldInfo& fi : block.field_info) {
    fi.name;        // Field name
    fi.type;        // Optional type annotation
    fi.is_computed; // true if type is "computed"
}

// Query field types
auto type = block.get_field_type("price");  // std::optional<std::string>
auto computed = block.get_computed_fields(); // std::vector<std::string>
```

### ISONL Format

ISONL is a line-based streaming format where each line is self-contained:

```
table.users|id name email|1 Alice alice@example.com
table.users|id name email|2 Bob bob@example.com
```

```cpp
// Convert between formats
std::string isonl = ison::ison_to_isonl(ison_text);
std::string ison = ison::isonl_to_ison(isonl_text);
```

## Building

### Requirements
- C++17 compiler (GCC 7+, Clang 5+, MSVC 2017+)
- CMake 3.14+ (optional)

### With CMake

```bash
mkdir build && cd build
cmake ..
make

# Run tests
./test_ison_parser

# Run example
./ison_example
```

### Manual Compilation

```bash
# Test
g++ -std=c++17 -I include tests/test_ison_parser.cpp -o test_ison
./test_ison

# Example
g++ -std=c++17 -I include examples/example.cpp -o example
./example
```

### Visual Studio

```cmd
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022"
cmake --build . --config Release
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

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## Author

Mahesh Vaikri

## License

MIT License - See LICENSE file
