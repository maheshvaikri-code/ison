
<p align="center">
  <img src="https://raw.githubusercontent.com/maheshvaikri-code/ison/main/images/ison_logo_git.png" alt="ISON Logo">
</p>


# isonantic-cpp

Type-safe validation for ISON format in C++17.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++17](https://img.shields.io/badge/C++-17-blue.svg)](https://isocpp.org/)

## Features

- **Header-only** - Just include `isonantic.hpp`
- **Type-safe** - Full compile-time type checking
- **Builder pattern** - Fluent API for schema definition
- **Validation** - Runtime validation with detailed errors
- **C++17** - Uses `std::variant`, `std::optional`

## Installation

### Option 1: Copy the header

```bash
cp include/isonantic.hpp /your/project/include/
```

### Option 2: CMake

```cmake
add_subdirectory(isonantic-cpp)
target_link_libraries(your_target PRIVATE isonantic::isonantic)
```

## Quick Start

```cpp
#include "isonantic.hpp"
#include "ison_parser.hpp"  // ison-cpp

using namespace isonantic;

int main() {
    // Define schema
    auto user_schema = table("users")
        .field("id", integer().required())
        .field("name", string().min(1).max(100))
        .field("email", string().email())
        .field("active", boolean().default_value(true));

    // Parse ISON
    auto doc = ison::parse(ison_text);

    // Validate
    try {
        auto users = user_schema.validate(doc);

        // Access validated data
        for (const auto& user : users) {
            std::cout << user.get_int("id").value()
                      << ": " << user.get_string("name").value()
                      << std::endl;
        }
    } catch (const ValidationError& e) {
        std::cerr << "Validation failed:" << std::endl;
        for (const auto& err : e.errors) {
            std::cerr << "  " << err.field << ": " << err.message << std::endl;
        }
    }

    return 0;
}
```

## Schema Types

### String Fields

```cpp
string()                     // Basic string
    .min(5)                  // Minimum length
    .max(100)                // Maximum length
    .email()                 // Email format
    .required()              // Required field
    .default_value("N/A")    // Default value
```

### Number Fields

```cpp
integer()                    // Integer field
    .min(0)                  // Minimum value
    .max(100)                // Maximum value
    .positive()              // Must be > 0
    .required()

floating()                   // Float field
    .min(0.0)
    .max(100.0)
    .positive()
```

### Boolean Fields

```cpp
boolean()
    .default_value(true)
    .required()
```

### Reference Fields

```cpp
reference()                  // ISON reference (:id or :type:id)
    .required()
```

## Table Schema

```cpp
auto order_schema = table("orders")
    .field("id", string().required())
    .field("user_id", reference().required())
    .field("total", floating().positive())
    .field("status", string().default_value("pending"));
```

## Error Handling

```cpp
try {
    auto result = schema.validate(doc);
    // Use result...
} catch (const ValidationError& e) {
    // Access all errors
    for (const auto& err : e.errors) {
        std::cerr << err.field << ": " << err.message << std::endl;
    }
}
```

## Accessing Validated Data

```cpp
auto users = schema.validate(doc);

// Iterate
for (const auto& row : users) {
    auto id = row.get_int("id");      // std::optional<int64_t>
    auto name = row.get_string("name"); // std::optional<std::string>
    auto active = row.get_bool("active"); // std::optional<bool>

    if (id && name) {
        std::cout << *id << ": " << *name << std::endl;
    }
}

// Index access
const auto& first = users[0];
```

## Requirements

- C++17 compiler
- `<variant>`, `<optional>`, `<string>`, `<vector>`, `<map>`

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## Author

Mahesh Vaikri

## License

MIT License - see [LICENSE](LICENSE) for details.
