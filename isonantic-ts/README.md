# isonantic-ts

Zod-like validation and type-safe models for ISON format in TypeScript/JavaScript.

[![npm version](https://badge.fury.io/js/isonantic-ts.svg)](https://badge.fury.io/js/isonantic-ts)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-46%20passed-brightgreen.svg)]()

## Features

- **Zod-like API** - Familiar schema definition syntax
- **Type inference** - Full TypeScript type safety
- **Validation** - Runtime validation with detailed errors
- **LLM Integration** - Generate prompts for LLM output parsing
- **ISON-native** - First-class support for ISON tables and references

## Installation

```bash
npm install isonantic-ts ison-ts
# or
yarn add isonantic-ts ison-ts
# or
pnpm add isonantic-ts ison-ts
```

## Quick Start

```typescript
import { i, document, ValidationError } from 'isonantic-ts';
import { parse } from 'ison-ts';

// Define schemas
const UserSchema = i.table('users', {
  id: i.int(),
  name: i.string().min(1),
  email: i.string().email(),
  active: i.boolean().default(true),
});

const OrderSchema = i.table('orders', {
  id: i.string(),
  user_id: i.ref(),
  total: i.number().positive(),
});

// Create document schema
const DocSchema = document({
  users: UserSchema,
  orders: OrderSchema,
});

// Parse and validate ISON
const isonText = `
table.users
id name email active
1 Alice alice@example.com true
2 Bob bob@example.com false

table.orders
id user_id total
O1 :1 99.99
O2 :2 149.50
`;

const doc = parse(isonText);
const validated = DocSchema.parse(doc.toDict());

// Type-safe access
validated.users[0].name; // string
validated.orders[0].total; // number
```

## Schema Types

### Primitives

```typescript
i.string()          // String validation
i.number()          // Number validation
i.int()             // Integer validation
i.float()           // Float validation (alias for number)
i.boolean()         // Boolean validation
i.bool()            // Boolean validation (alias)
i.null()            // Null validation
```

### String Validations

```typescript
i.string()
  .min(5)           // Minimum length
  .max(100)         // Maximum length
  .length(10)       // Exact length
  .email()          // Email format
  .url()            // URL format
  .regex(/pattern/) // Custom regex
```

### Number Validations

```typescript
i.number()
  .min(0)           // Minimum value
  .max(100)         // Maximum value
  .int()            // Must be integer
  .positive()       // Must be > 0
  .negative()       // Must be < 0
```

### References

```typescript
i.ref()             // ISON reference (:id or :type:id)
i.reference()       // Alias for ref()
```

### Complex Types

```typescript
// Object schema
i.object({
  name: i.string(),
  age: i.int(),
})

// Array schema
i.array(i.string())
  .min(1)           // Minimum items
  .max(10)          // Maximum items

// Table schema (ISON-specific)
i.table('users', {
  id: i.int(),
  name: i.string(),
})
```

### Modifiers

```typescript
i.string().optional()     // Can be undefined
i.string().default('N/A') // Default value
i.string().describe('..') // Add description
i.string().refine(        // Custom validation
  (val) => val.length > 0,
  'Must not be empty'
)
```

## Document Schema

```typescript
import { document } from 'isonantic-ts';

const schema = document({
  users: i.table('users', { ... }),
  config: i.object({ ... }),
});

// Parse with validation
const result = schema.parse(doc);

// Safe parse (no throw)
const { success, data, error } = schema.safeParse(doc);
```

## Error Handling

```typescript
import { ValidationError } from 'isonantic-ts';

try {
  schema.parse(invalidData);
} catch (e) {
  if (e instanceof ValidationError) {
    for (const error of e.errors) {
      console.log(`${error.field}: ${error.message}`);
    }
  }
}

// Or use safeParse
const result = schema.safeParse(data);
if (!result.success) {
  console.log(result.error.errors);
}
```

## LLM Prompt Generation

```typescript
import { generatePrompt } from 'isonantic-ts';

const UserSchema = i.table('users', {
  id: i.int(),
  name: i.string(),
  role: i.string(),
});

const prompt = generatePrompt(UserSchema, {
  description: 'List of team members',
  examples: true,
});

// Use in LLM prompt
const llmPrompt = `
Extract users from this text:
${textToProcess}

${prompt}
`;
```

## Type Inference

```typescript
import { InferType } from 'isonantic-ts';

const UserSchema = i.object({
  id: i.int(),
  name: i.string(),
  email: i.string().optional(),
});

// Infer TypeScript type from schema
type User = InferType<typeof UserSchema>;
// { id: number; name: string; email?: string }
```

## Test Results

All tests passing:

```
 ✓ src/index.test.ts (46 tests)

 Test Files  1 passed (1)
      Tests  46 passed (46)
```

Test coverage includes:
- String validation (min, max, email, url, regex)
- Number validation (min, max, int, positive, negative)
- Boolean and null schemas
- Reference parsing (string and object formats)
- Object schema (extend, pick, omit)
- Array schema with length validation
- Table schema for ISON blocks
- Document schema with block validation
- Custom refinements
- SafeParse error handling
- LLM prompt generation

Run tests with:
```bash
npm test
```

## Links

- [Documentation](https://www.ison.dev) | [www.getison.com](https://www.getison.com)
- [ISON TypeScript Parser](https://www.npmjs.com/package/ison-ts)
- [GitHub](https://github.com/maheshvaikri-code/ison)

## License

MIT License - see [LICENSE](LICENSE) for details.
