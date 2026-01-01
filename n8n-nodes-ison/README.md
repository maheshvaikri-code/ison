<p align="center">
  <img src="https://raw.githubusercontent.com/maheshvaikri-code/ison/main/images/ison_logo_white_bg.png" alt="ISON Logo" width="300">
</p>

# n8n-nodes-ison

n8n community node for [ISON](https://www.ison.dev) (Interchange Simple Object Notation) - a token-efficient data format optimized for LLMs and AI workflows.

**Save 30-70% on LLM tokens** by using ISON instead of JSON in your n8n AI workflows.

[![npm version](https://img.shields.io/npm/v/n8n-nodes-ison.svg)](https://www.npmjs.com/package/n8n-nodes-ison)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

### Community Nodes (Recommended)

1. Go to **Settings > Community Nodes**
2. Select **Install**
3. Enter `n8n-nodes-ison` and click **Install**

### Manual Installation

```bash
npm install n8n-nodes-ison
```

## Operations

### Parse ISON

Convert ISON text to JSON for processing in n8n workflows.

**Input:**
```
table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com
```

**Output:**
```json
{
  "users": [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
  ]
}
```

### Convert to ISON

Convert JSON data to ISON format for token-efficient LLM prompts.

**Input:**
```json
{
  "users": [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"}
  ]
}
```

**Output:**
```
table.users
id name
1 Alice
2 Bob
```

### Parse ISONL

Parse ISONL (streaming format) to JSON array. Each line is one record.

**Input:**
```
table.users|id name|1 Alice
table.users|id name|2 Bob
```

**Output:**
```json
{
  "records": [
    {"_block": "users", "id": 1, "name": "Alice"},
    {"_block": "users", "id": 2, "name": "Bob"}
  ]
}
```

### Convert to ISONL

Convert JSON to ISONL streaming format for processing large datasets.

### Count Tokens

Count approximate tokens and compare ISON vs JSON savings.

**Output:**
```json
{
  "tokens": 45,
  "characters": 180,
  "jsonTokens": 120,
  "savings": "62%"
}
```

## Use Cases

### 1. LLM Context Optimization

Reduce tokens when sending data to OpenAI, Anthropic, or other LLM nodes:

```
[HTTP Request] → [ISON: Convert to ISON] → [OpenAI] → [ISON: Parse ISON]
```

### 2. RAG Pipeline

Efficient context injection for retrieval-augmented generation:

```
[Vector Store] → [ISON: Convert to ISON] → [Chat Model]
```

### 3. Data Processing

Convert between formats in ETL workflows:

```
[Database] → [ISON: Convert to ISONL] → [Write File]
```

### 4. Token Budget Management

Track and optimize token usage:

```
[Data] → [ISON: Count Tokens] → [IF: tokens > budget] → [Summarize]
```

## ISON Format Quick Reference

```ison
# Comments start with #

table.users                          # Block header
id:int name:string email active:bool # Fields with optional types
1 Alice alice@example.com true       # Data rows
2 "Bob Smith" bob@example.com false  # Quoted strings for spaces

table.orders
id user_id product
1 :1 Widget                          # :1 = reference to id 1
2 :user:42 Gadget                    # :user:42 = namespaced ref
```

## Why ISON?

| Format | Tokens | Savings |
|--------|--------|---------|
| JSON (pretty) | 150 | - |
| JSON (compact) | 100 | 33% |
| ISON | 45 | **70%** |

ISON achieves this by:
- No quotes around keys
- No commas or colons
- No brackets for arrays
- Space-separated values
- Built-in references (`:id`)

## Links

- [ISON Website](https://www.ison.dev)
- [Documentation](https://www.getison.com)
- [Playground](https://www.ison.dev/playground.html)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## License

MIT

## Author

[Mahesh Vaikri](https://github.com/maheshvaikri-code)
