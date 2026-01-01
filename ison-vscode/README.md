<p align="center">
  <img src="https://raw.githubusercontent.com/maheshvaikri-code/ison/main/images/ison_logo_white_bg.png" alt="ISON Logo" width="300">
</p>

# ISON Language Support for VS Code

Syntax highlighting, snippets, and tools for [ISON](https://www.ison.dev) (Interchange Simple Object Notation) - a token-efficient data format optimized for LLMs.

[![Visual Studio Marketplace](https://img.shields.io/badge/VS%20Code-Marketplace-blue.svg)](https://marketplace.visualstudio.com/items?itemName=ison-dev.ison-lang)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### Syntax Highlighting

Full syntax highlighting for `.ison` and `.isonl` files:
- Block headers (`table.users`, `object.config`)
- Type annotations (`id:int`, `name:string`)
- References (`:1`, `:user:42`, `:OWNS:5`)
- Strings, numbers, booleans, nulls
- Comments (`# comment`)

### Snippets

Quick templates for common patterns:
- `table` - Create a table block
- `object` - Create an object block
- `users` - User table template
- `orders` - Orders with references
- `config` - Configuration object
- `ref` - Simple reference
- `rag` - RAG context template
- `chat` - Chat messages template

### Commands

- **ISON: Convert to JSON** - Convert current ISON to JSON (side-by-side)
- **ISON: Convert from JSON** - Convert current JSON to ISON
- **ISON: Count Tokens** - Show token count with JSON comparison
- **ISON: Format Document** - Align columns for readability

### Token Counter

Real-time token count in the status bar for ISON files. Click to see comparison with JSON equivalent.

## Installation

### From VSIX (Local)

```bash
cd ison-vscode
npm install
npm run compile
npm run package
code --install-extension ison-lang-1.0.0.vsix
```

### From Marketplace

Search for "ISON" in VS Code Extensions.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ison.alignColumns` | `true` | Align columns when formatting |
| `ison.showTokenCount` | `true` | Show token count in status bar |

## ISON Format Example

```ison
# Users table with typed fields
table.users
id:int name:string email:string active:bool
1 Alice alice@example.com true
2 Bob bob@example.com false

# Orders with references
table.orders
id:int user_id:ref product amount:float
1 :1 Widget 29.99
2 :2 Gadget 49.99

# Configuration object
object.config
key value
debug true
version 1.0.0
```

## ISONL Streaming Format

```isonl
table.users|id:int name:string|1 Alice
table.users|id:int name:string|2 Bob
table.orders|id:int user_id:ref product|1 :1 Widget
```

## Why ISON?

- **30-70% fewer tokens** compared to JSON
- **Optimized for LLMs** - structured data in minimal tokens
- **Human readable** - easy to write and debug
- **References built-in** - `:id` syntax for relationships

## Links

- [ISON Website](https://www.ison.dev)
- [Documentation](https://www.getison.com)
- [GitHub Repository](https://github.com/maheshvaikri-code/ison)
- [Playground](https://www.ison.dev/playground.html)

## License

MIT
