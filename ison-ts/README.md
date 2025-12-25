# ison-ts

[![npm version](https://badge.fury.io/js/ison-ts.svg)](https://badge.fury.io/js/ison-ts)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-23%20passed-brightgreen.svg)]()

A TypeScript implementation of the ISON (Interchange Simple Object Notation) parser.

ISON is a minimal, LLM-friendly data serialization format optimized for:
- Graph databases
- Multi-agent systems
- RAG pipelines
- Token-efficient AI/ML workflows

## Features

- **Full TypeScript Support**: Complete type definitions
- **Zero Dependencies**: No external runtime dependencies
- **Full ISON Support**: Tables, objects, references, type annotations
- **ISONL Streaming**: Line-based format for large datasets
- **JSON Export**: Convert ISON to JSON
- **Browser & Node.js**: Works in both environments

## Installation

```bash
npm install ison-ts
# or
yarn add ison-ts
# or
pnpm add ison-ts
```

## Quick Start

```typescript
import { parse, dumps, fromDict, Reference } from 'ison-parser';

// Parse ISON text
const isonText = `
table.users
id:int name:string email active:bool
1 Alice alice@example.com true
2 Bob bob@example.com false
`;

const doc = parse(isonText);

// Access blocks
const users = doc.getBlock('users');
console.log(`Users: ${users.size()}`);

// Access values with type checking
for (const row of users.rows) {
    console.log(`${row.id}: ${row.name} (${row.active ? 'active' : 'inactive'})`);
}

// Convert to JSON
const json = doc.toJson();

// Serialize back to ISON
const isonOutput = dumps(doc);
```

## API Reference

### Parsing

```typescript
import { parse, loads, loadsIsonl } from 'ison-parser';

// Parse from string
const doc = parse(text);
const doc = loads(text);  // Alias

// Parse ISONL
const doc = loadsIsonl(isonlText);
```

### Serialization

```typescript
import { dumps, dumpsIsonl } from 'ison-parser';

// To ISON string
const ison = dumps(doc);
const ison = dumps(doc, false);  // No column alignment

// To ISONL
const isonl = dumpsIsonl(doc);

// To JSON
const json = doc.toJson();
const json = doc.toJson(4);  // Custom indent
```

### Creating Documents

```typescript
import { fromDict, Document, Block } from 'ison-parser';

// From plain object
const data = {
    products: [
        { id: 1, name: 'Widget', price: 29.99 },
        { id: 2, name: 'Gadget', price: 49.99 }
    ]
};
const doc = fromDict(data);

// Programmatically
const doc = new Document();
const block = new Block('table', 'users');
block.fields = ['id', 'name'];
block.fieldInfo = [
    { name: 'id', type: 'int', isComputed: false },
    { name: 'name', type: 'string', isComputed: false }
];
block.rows = [
    { id: 1, name: 'Alice' },
    { id: 2, name: 'Bob' }
];
doc.blocks.push(block);
```

### Document Access

```typescript
const doc = parse(text);

// Check if block exists
if (doc.has('users')) {
    const users = doc.getBlock('users');

    // Block properties
    users.kind;       // 'table', 'object', 'meta'
    users.name;       // 'users'
    users.size();     // Row count
    users.fields;     // Field names

    // Access rows
    for (const row of users.rows) {
        // Row is Record<string, Value>
    }
}
```

### Type Checking

```typescript
import {
    isNull, isBool, isInt, isFloat, isString, isReference,
    Value, Reference
} from 'ison-parser';

const value: Value = row.someField;

if (isNull(value)) { /* null */ }
if (isBool(value)) { /* boolean */ }
if (isInt(value)) { /* integer */ }
if (isFloat(value)) { /* number */ }
if (isString(value)) { /* string */ }
if (isReference(value)) {
    const ref: Reference = value;
    ref.id;              // Referenced ID
    ref.type;            // Optional type/namespace
    ref.isRelationship(); // true if UPPERCASE type
    ref.toIson();        // ':type:id' or ':id'
}
```

### References

```typescript
import { Reference } from 'ison-parser';

// Simple reference :42
const ref = new Reference('42');
ref.toIson();  // ':42'

// Namespaced reference :user:101
const ref = new Reference('101', 'user');
ref.getNamespace();  // 'user'
ref.isRelationship(); // false

// Relationship reference :MEMBER_OF:10
const ref = new Reference('10', 'MEMBER_OF');
ref.isRelationship();     // true
ref.relationshipType();   // 'MEMBER_OF'
```

### Field Info

```typescript
// Access type annotations
for (const fi of block.fieldInfo) {
    fi.name;        // Field name
    fi.type;        // Optional type annotation
    fi.isComputed;  // true if type is 'computed'
}

// Query field types
const type = block.getFieldType('price');  // string | undefined
const computed = block.getComputedFields(); // string[]
```

### ISONL Format

ISONL is a line-based streaming format where each line is self-contained:

```
table.users|id name email|1 Alice alice@example.com
table.users|id name email|2 Bob bob@example.com
```

```typescript
import { isonToIsonl, isonlToIson } from 'ison-parser';

// Convert between formats
const isonl = isonToIsonl(isonText);
const ison = isonlToIson(isonlText);
```

## Usage with LLMs

### OpenAI Integration

```typescript
import OpenAI from 'openai';
import { fromDict, dumps } from 'ison-parser';

const openai = new OpenAI();

async function queryWithContext(question: string, contextData: object) {
    const isonContext = dumps(fromDict(contextData));

    const response = await openai.chat.completions.create({
        model: 'gpt-4',
        messages: [{
            role: 'user',
            content: `Context:\n${isonContext}\n\nQuestion: ${question}`
        }]
    });

    return response.choices[0].message.content;
}
```

### Anthropic Claude Integration

```typescript
import Anthropic from '@anthropic-ai/sdk';
import { fromDict, dumps } from 'ison-parser';

const anthropic = new Anthropic();

async function queryWithContext(question: string, contextData: object) {
    const isonContext = dumps(fromDict(contextData));

    const message = await anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 1024,
        messages: [{
            role: 'user',
            content: `Context:\n${isonContext}\n\nQuestion: ${question}`
        }]
    });

    return message.content[0].text;
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
 ✓ src/index.test.ts (23 tests)

 Test Files  1 passed (1)
      Tests  23 passed (23)
```

Test coverage includes:
- Basic parsing and serialization
- Type annotations and inference
- References (simple, namespaced, relationship)
- ISONL streaming format
- JSON conversion
- Error handling

Run tests with:
```bash
npm test
```

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [Specification](https://www.ison.dev/spec.html)
- [JavaScript Package](https://www.npmjs.com/package/ison-parser)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## License

MIT License
