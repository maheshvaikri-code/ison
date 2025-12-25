/**
 * ISONantic for TypeScript
 *
 * Zod-like validation and type-safe models for ISON format.
 * Provides schema definition, validation, and LLM output parsing.
 *
 * @example
 * ```typescript
 * import { i, parse } from 'isonantic-ts';
 *
 * const UserSchema = i.table('users', {
 *   id: i.int(),
 *   name: i.string(),
 *   email: i.string().email(),
 *   active: i.boolean().default(true),
 * });
 *
 * const users = parse(isonText, UserSchema);
 * ```
 */

export const VERSION = "1.0.0";

// =============================================================================
// Types
// =============================================================================

export type ISONValue = null | boolean | number | string | ISONReference;

export interface ISONReference {
  id: string;
  type?: string;
}

export type InferType<T extends ISONSchema<any>> = T["_output"];

// =============================================================================
// Validation Errors
// =============================================================================

export class ISONanticError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ISONanticError";
  }
}

export class ValidationError extends ISONanticError {
  constructor(
    public readonly errors: FieldError[],
    message?: string
  ) {
    super(message || `Validation failed with ${errors.length} error(s)`);
    this.name = "ValidationError";
  }
}

export interface FieldError {
  field: string;
  message: string;
  value?: any;
}

// =============================================================================
// Base Schema
// =============================================================================

export abstract class ISONSchema<T> {
  abstract readonly _output: T;
  protected _optional: boolean = false;
  protected _default?: T;
  protected _validators: Array<(value: T) => string | null> = [];
  protected _description?: string;

  optional(): ISONSchema<T | undefined> {
    const schema = this._clone();
    schema._optional = true;
    return schema as any;
  }

  default(value: T): ISONSchema<T> {
    const schema = this._clone();
    schema._default = value;
    schema._optional = true;
    return schema;
  }

  describe(description: string): this {
    this._description = description;
    return this;
  }

  refine(validator: (value: T) => boolean, message: string): this {
    this._validators.push((value) => (validator(value) ? null : message));
    return this;
  }

  abstract parse(value: any): T;
  abstract _clone(): ISONSchema<T>;

  safeParse(value: any): { success: true; data: T } | { success: false; error: ValidationError } {
    try {
      const data = this.parse(value);
      return { success: true, data };
    } catch (e) {
      if (e instanceof ValidationError) {
        return { success: false, error: e };
      }
      throw e;
    }
  }

  protected _runValidators(value: T, field: string): void {
    const errors: FieldError[] = [];
    for (const validator of this._validators) {
      const error = validator(value);
      if (error) {
        errors.push({ field, message: error, value });
      }
    }
    if (errors.length > 0) {
      throw new ValidationError(errors);
    }
  }
}

// =============================================================================
// Primitive Schemas
// =============================================================================

class StringSchema extends ISONSchema<string> {
  readonly _output!: string;
  private _minLength?: number;
  private _maxLength?: number;
  private _pattern?: RegExp;
  private _email?: boolean;
  private _url?: boolean;

  parse(value: any): string {
    if (value === null || value === undefined) {
      if (this._optional) {
        return this._default as string;
      }
      throw new ValidationError([{ field: "", message: "Required" }]);
    }

    if (typeof value !== "string") {
      throw new ValidationError([
        { field: "", message: `Expected string, got ${typeof value}`, value },
      ]);
    }

    if (this._minLength !== undefined && value.length < this._minLength) {
      throw new ValidationError([
        { field: "", message: `String must be at least ${this._minLength} characters`, value },
      ]);
    }

    if (this._maxLength !== undefined && value.length > this._maxLength) {
      throw new ValidationError([
        { field: "", message: `String must be at most ${this._maxLength} characters`, value },
      ]);
    }

    if (this._pattern && !this._pattern.test(value)) {
      throw new ValidationError([
        { field: "", message: `String does not match pattern`, value },
      ]);
    }

    if (this._email && !this._isEmail(value)) {
      throw new ValidationError([
        { field: "", message: `Invalid email address`, value },
      ]);
    }

    if (this._url && !this._isUrl(value)) {
      throw new ValidationError([
        { field: "", message: `Invalid URL`, value },
      ]);
    }

    this._runValidators(value, "");
    return value;
  }

  min(length: number): this {
    this._minLength = length;
    return this;
  }

  max(length: number): this {
    this._maxLength = length;
    return this;
  }

  length(length: number): this {
    this._minLength = length;
    this._maxLength = length;
    return this;
  }

  regex(pattern: RegExp): this {
    this._pattern = pattern;
    return this;
  }

  email(): this {
    this._email = true;
    return this;
  }

  url(): this {
    this._url = true;
    return this;
  }

  private _isEmail(value: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  private _isUrl(value: string): boolean {
    try {
      new URL(value);
      return true;
    } catch {
      return false;
    }
  }

  _clone(): StringSchema {
    const schema = new StringSchema();
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    schema._minLength = this._minLength;
    schema._maxLength = this._maxLength;
    schema._pattern = this._pattern;
    schema._email = this._email;
    schema._url = this._url;
    return schema;
  }
}

class NumberSchema extends ISONSchema<number> {
  readonly _output!: number;
  private _min?: number;
  private _max?: number;
  private _int?: boolean;
  private _positive?: boolean;
  private _negative?: boolean;

  parse(value: any): number {
    if (value === null || value === undefined) {
      if (this._optional) {
        return this._default as number;
      }
      throw new ValidationError([{ field: "", message: "Required" }]);
    }

    if (typeof value !== "number" || isNaN(value)) {
      throw new ValidationError([
        { field: "", message: `Expected number, got ${typeof value}`, value },
      ]);
    }

    if (this._int && !Number.isInteger(value)) {
      throw new ValidationError([
        { field: "", message: `Expected integer`, value },
      ]);
    }

    if (this._min !== undefined && value < this._min) {
      throw new ValidationError([
        { field: "", message: `Number must be >= ${this._min}`, value },
      ]);
    }

    if (this._max !== undefined && value > this._max) {
      throw new ValidationError([
        { field: "", message: `Number must be <= ${this._max}`, value },
      ]);
    }

    if (this._positive && value <= 0) {
      throw new ValidationError([
        { field: "", message: `Number must be positive`, value },
      ]);
    }

    if (this._negative && value >= 0) {
      throw new ValidationError([
        { field: "", message: `Number must be negative`, value },
      ]);
    }

    this._runValidators(value, "");
    return value;
  }

  min(value: number): this {
    this._min = value;
    return this;
  }

  max(value: number): this {
    this._max = value;
    return this;
  }

  int(): this {
    this._int = true;
    return this;
  }

  positive(): this {
    this._positive = true;
    return this;
  }

  negative(): this {
    this._negative = true;
    return this;
  }

  _clone(): NumberSchema {
    const schema = new NumberSchema();
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    schema._min = this._min;
    schema._max = this._max;
    schema._int = this._int;
    schema._positive = this._positive;
    schema._negative = this._negative;
    return schema;
  }
}

class BooleanSchema extends ISONSchema<boolean> {
  readonly _output!: boolean;

  parse(value: any): boolean {
    if (value === null || value === undefined) {
      if (this._optional) {
        return this._default as boolean;
      }
      throw new ValidationError([{ field: "", message: "Required" }]);
    }

    if (typeof value !== "boolean") {
      throw new ValidationError([
        { field: "", message: `Expected boolean, got ${typeof value}`, value },
      ]);
    }

    this._runValidators(value, "");
    return value;
  }

  _clone(): BooleanSchema {
    const schema = new BooleanSchema();
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    return schema;
  }
}

class NullSchema extends ISONSchema<null> {
  readonly _output!: null;

  parse(value: any): null {
    if (value !== null) {
      throw new ValidationError([
        { field: "", message: `Expected null, got ${typeof value}`, value },
      ]);
    }
    return null;
  }

  _clone(): NullSchema {
    return new NullSchema();
  }
}

// =============================================================================
// Reference Schema
// =============================================================================

class ReferenceSchema extends ISONSchema<ISONReference> {
  readonly _output!: ISONReference;
  private _refType?: string;

  parse(value: any): ISONReference {
    if (value === null || value === undefined) {
      if (this._optional) {
        return this._default as ISONReference;
      }
      throw new ValidationError([{ field: "", message: "Required" }]);
    }

    // Handle string reference format ":id" or ":type:id"
    if (typeof value === "string" && value.startsWith(":")) {
      const parts = value.slice(1).split(":");
      if (parts.length === 1) {
        return { id: parts[0] };
      } else {
        return { type: parts[0], id: parts[1] };
      }
    }

    // Handle object format
    if (typeof value === "object" && value.id) {
      const ref: ISONReference = { id: String(value.id) };
      if (value.type) {
        ref.type = String(value.type);
      }
      return ref;
    }

    throw new ValidationError([
      { field: "", message: `Invalid reference format`, value },
    ]);
  }

  type(refType: string): this {
    this._refType = refType;
    return this;
  }

  _clone(): ReferenceSchema {
    const schema = new ReferenceSchema();
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    schema._refType = this._refType;
    return schema;
  }
}

// =============================================================================
// Object Schema (for ISON blocks)
// =============================================================================

type ObjectShape = Record<string, ISONSchema<any>>;
type InferObject<T extends ObjectShape> = {
  [K in keyof T]: T[K]["_output"];
};

class ObjectSchema<T extends ObjectShape> extends ISONSchema<InferObject<T>> {
  readonly _output!: InferObject<T>;

  constructor(private shape: T) {
    super();
  }

  parse(value: any): InferObject<T> {
    if (value === null || value === undefined) {
      if (this._optional) {
        return this._default as InferObject<T>;
      }
      throw new ValidationError([{ field: "", message: "Required" }]);
    }

    if (typeof value !== "object" || Array.isArray(value)) {
      throw new ValidationError([
        { field: "", message: `Expected object, got ${typeof value}`, value },
      ]);
    }

    const result: any = {};
    const errors: FieldError[] = [];

    for (const [key, schema] of Object.entries(this.shape)) {
      try {
        result[key] = schema.parse(value[key]);
      } catch (e) {
        if (e instanceof ValidationError) {
          for (const error of e.errors) {
            errors.push({
              field: error.field ? `${key}.${error.field}` : key,
              message: error.message,
              value: error.value,
            });
          }
        } else {
          throw e;
        }
      }
    }

    if (errors.length > 0) {
      throw new ValidationError(errors);
    }

    return result;
  }

  extend<U extends ObjectShape>(shape: U): ObjectSchema<T & U> {
    return new ObjectSchema({ ...this.shape, ...shape });
  }

  pick<K extends keyof T>(...keys: K[]): ObjectSchema<Pick<T, K>> {
    const newShape: any = {};
    for (const key of keys) {
      newShape[key] = this.shape[key];
    }
    return new ObjectSchema(newShape);
  }

  omit<K extends keyof T>(...keys: K[]): ObjectSchema<Omit<T, K>> {
    const newShape: any = { ...this.shape };
    for (const key of keys) {
      delete newShape[key];
    }
    return new ObjectSchema(newShape);
  }

  _clone(): ObjectSchema<T> {
    const schema = new ObjectSchema({ ...this.shape });
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    return schema;
  }
}

// =============================================================================
// Array Schema
// =============================================================================

class ArraySchema<T extends ISONSchema<any>> extends ISONSchema<T["_output"][]> {
  readonly _output!: T["_output"][];
  private _minLength?: number;
  private _maxLength?: number;

  constructor(private itemSchema: T) {
    super();
  }

  parse(value: any): T["_output"][] {
    if (value === null || value === undefined) {
      if (this._optional) {
        return this._default as T["_output"][];
      }
      throw new ValidationError([{ field: "", message: "Required" }]);
    }

    if (!Array.isArray(value)) {
      throw new ValidationError([
        { field: "", message: `Expected array, got ${typeof value}`, value },
      ]);
    }

    if (this._minLength !== undefined && value.length < this._minLength) {
      throw new ValidationError([
        { field: "", message: `Array must have at least ${this._minLength} items`, value },
      ]);
    }

    if (this._maxLength !== undefined && value.length > this._maxLength) {
      throw new ValidationError([
        { field: "", message: `Array must have at most ${this._maxLength} items`, value },
      ]);
    }

    const errors: FieldError[] = [];
    const result: T["_output"][] = [];

    for (let i = 0; i < value.length; i++) {
      try {
        result.push(this.itemSchema.parse(value[i]));
      } catch (e) {
        if (e instanceof ValidationError) {
          for (const error of e.errors) {
            errors.push({
              field: error.field ? `[${i}].${error.field}` : `[${i}]`,
              message: error.message,
              value: error.value,
            });
          }
        } else {
          throw e;
        }
      }
    }

    if (errors.length > 0) {
      throw new ValidationError(errors);
    }

    return result;
  }

  min(length: number): this {
    this._minLength = length;
    return this;
  }

  max(length: number): this {
    this._maxLength = length;
    return this;
  }

  length(length: number): this {
    this._minLength = length;
    this._maxLength = length;
    return this;
  }

  _clone(): ArraySchema<T> {
    const schema = new ArraySchema(this.itemSchema);
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    schema._minLength = this._minLength;
    schema._maxLength = this._maxLength;
    return schema;
  }
}

// =============================================================================
// Table Schema (ISON-specific)
// =============================================================================

class TableSchema<T extends ObjectShape> extends ISONSchema<InferObject<T>[]> {
  readonly _output!: InferObject<T>[];
  readonly blockName: string;
  readonly rowSchema: ObjectSchema<T>;

  constructor(name: string, shape: T) {
    super();
    this.blockName = name;
    this.rowSchema = new ObjectSchema(shape);
  }

  parse(value: any): InferObject<T>[] {
    if (!Array.isArray(value)) {
      // Single object - wrap in array
      return [this.rowSchema.parse(value)];
    }

    const errors: FieldError[] = [];
    const result: InferObject<T>[] = [];

    for (let i = 0; i < value.length; i++) {
      try {
        result.push(this.rowSchema.parse(value[i]));
      } catch (e) {
        if (e instanceof ValidationError) {
          for (const error of e.errors) {
            errors.push({
              field: error.field ? `[${i}].${error.field}` : `[${i}]`,
              message: error.message,
              value: error.value,
            });
          }
        } else {
          throw e;
        }
      }
    }

    if (errors.length > 0) {
      throw new ValidationError(errors);
    }

    return result;
  }

  _clone(): TableSchema<T> {
    const schema = new TableSchema(this.blockName, {} as T);
    (schema as any).rowSchema = this.rowSchema._clone();
    schema._optional = this._optional;
    schema._default = this._default;
    schema._validators = [...this._validators];
    return schema;
  }
}

// =============================================================================
// Schema Builder (Zod-like API)
// =============================================================================

export const i = {
  // Primitives
  string: () => new StringSchema(),
  number: () => new NumberSchema(),
  int: () => new NumberSchema().int(),
  float: () => new NumberSchema(),
  boolean: () => new BooleanSchema(),
  bool: () => new BooleanSchema(),
  null: () => new NullSchema(),

  // References
  ref: () => new ReferenceSchema(),
  reference: () => new ReferenceSchema(),

  // Complex types
  object: <T extends ObjectShape>(shape: T) => new ObjectSchema(shape),
  array: <T extends ISONSchema<any>>(schema: T) => new ArraySchema(schema),

  // ISON-specific
  table: <T extends ObjectShape>(name: string, shape: T) => new TableSchema(name, shape),

  // Utilities
  optional: <T extends ISONSchema<any>>(schema: T) => schema.optional(),
};

// =============================================================================
// Document Schema
// =============================================================================

type DocumentShape = Record<string, TableSchema<any> | ObjectSchema<any>>;
type InferDocument<T extends DocumentShape> = {
  [K in keyof T]: T[K]["_output"];
};

export class DocumentSchema<T extends DocumentShape> {
  constructor(private shape: T) {}

  parse(doc: any): InferDocument<T> {
    const result: any = {};
    const errors: FieldError[] = [];

    for (const [blockName, schema] of Object.entries(this.shape)) {
      const blockData = doc[blockName];

      if (blockData === undefined) {
        if (!(schema as any)._optional) {
          errors.push({
            field: blockName,
            message: `Missing required block: ${blockName}`,
          });
        }
        continue;
      }

      try {
        result[blockName] = schema.parse(blockData);
      } catch (e) {
        if (e instanceof ValidationError) {
          for (const error of e.errors) {
            errors.push({
              field: error.field ? `${blockName}.${error.field}` : blockName,
              message: error.message,
              value: error.value,
            });
          }
        } else {
          throw e;
        }
      }
    }

    if (errors.length > 0) {
      throw new ValidationError(errors);
    }

    return result;
  }

  safeParse(doc: any): { success: true; data: InferDocument<T> } | { success: false; error: ValidationError } {
    try {
      const data = this.parse(doc);
      return { success: true, data };
    } catch (e) {
      if (e instanceof ValidationError) {
        return { success: false, error: e };
      }
      throw e;
    }
  }
}

export function document<T extends DocumentShape>(shape: T): DocumentSchema<T> {
  return new DocumentSchema(shape);
}

// =============================================================================
// Schema Generation for LLM Prompts
// =============================================================================

export function generatePrompt<T extends ObjectShape>(
  schema: TableSchema<T>,
  options: { examples?: boolean; description?: string } = {}
): string {
  const lines: string[] = [];

  if (options.description) {
    lines.push(`# ${options.description}`);
    lines.push("");
  }

  lines.push("Please respond in ISON format:");
  lines.push("");
  lines.push("```ison");
  lines.push(`table.${schema.blockName}`);

  // Generate field header
  const fields = Object.keys((schema.rowSchema as any).shape);
  lines.push(fields.join(" "));

  if (options.examples) {
    lines.push("# ... data rows here ...");
  }

  lines.push("```");

  return lines.join("\n");
}

// =============================================================================
// Exports
// =============================================================================

export {
  StringSchema,
  NumberSchema,
  BooleanSchema,
  NullSchema,
  ReferenceSchema,
  ObjectSchema,
  ArraySchema,
  TableSchema,
};
