import { describe, it, expect } from "vitest";
import {
  parse,
  loads,
  dumps,
  loadsIsonl,
  dumpsIsonl,
  isonToIsonl,
  isonlToIson,
  fromDict,
  Reference,
  Document,
  Block,
  isNull,
  isBool,
  isInt,
  isFloat,
  isString,
  isReference,
  ISONSyntaxError,
} from "./index";

describe("Basic Parsing", () => {
  it("should parse a simple table", () => {
    const ison = `table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com`;

    const doc = parse(ison);
    const users = doc.getBlock("users");

    expect(users).toBeDefined();
    expect(users!.kind).toBe("table");
    expect(users!.name).toBe("users");
    expect(users!.size()).toBe(2);
    expect(users!.fields).toEqual(["id", "name", "email"]);

    expect(users!.rows[0]["id"]).toBe(1);
    expect(users!.rows[0]["name"]).toBe("Alice");
    expect(users!.rows[0]["email"]).toBe("alice@example.com");
  });

  it("should parse an object block", () => {
    const ison = `object.config
name version debug
MyApp 1.0 true`;

    const doc = parse(ison);
    const config = doc.getBlock("config");

    expect(config!.kind).toBe("object");
    expect(config!.size()).toBe(1);
    expect(config!.rows[0]["name"]).toBe("MyApp");
    expect(config!.rows[0]["debug"]).toBe(true);
  });

  it("should parse multiple blocks", () => {
    const ison = `table.users
id name
1 Alice
2 Bob

table.orders
id user_id
100 :1`;

    const doc = parse(ison);
    expect(doc.size()).toBe(2);
    expect(doc.has("users")).toBe(true);
    expect(doc.has("orders")).toBe(true);
  });
});

describe("Type Inference", () => {
  it("should infer integers", () => {
    const ison = `table.test
value
42
-17
0`;

    const doc = parse(ison);
    const test = doc.getBlock("test")!;

    expect(isInt(test.rows[0]["value"])).toBe(true);
    expect(test.rows[0]["value"]).toBe(42);
    expect(test.rows[1]["value"]).toBe(-17);
    expect(test.rows[2]["value"]).toBe(0);
  });

  it("should infer floats", () => {
    const ison = `table.test
value
3.14
-2.5`;

    const doc = parse(ison);
    const test = doc.getBlock("test")!;

    expect(isFloat(test.rows[0]["value"])).toBe(true);
    expect(test.rows[0]["value"]).toBeCloseTo(3.14);
    expect(test.rows[1]["value"]).toBeCloseTo(-2.5);
  });

  it("should infer booleans", () => {
    const ison = `table.test
active verified
true false`;

    const doc = parse(ison);
    const test = doc.getBlock("test")!;

    expect(isBool(test.rows[0]["active"])).toBe(true);
    expect(test.rows[0]["active"]).toBe(true);
    expect(test.rows[0]["verified"]).toBe(false);
  });

  it("should infer null values", () => {
    const ison = `table.test
value1 value2
null ~`;

    const doc = parse(ison);
    const test = doc.getBlock("test")!;

    expect(isNull(test.rows[0]["value1"])).toBe(true);
    expect(isNull(test.rows[0]["value2"])).toBe(true);
  });

  it("should infer strings", () => {
    const ison = `table.test
name
hello
"quoted string"
"with spaces"`;

    const doc = parse(ison);
    const test = doc.getBlock("test")!;

    expect(isString(test.rows[0]["name"])).toBe(true);
    expect(test.rows[0]["name"]).toBe("hello");
    expect(test.rows[1]["name"]).toBe("quoted string");
    expect(test.rows[2]["name"]).toBe("with spaces");
  });
});

describe("References", () => {
  it("should parse simple references", () => {
    const ison = `table.orders
id user_id
1 :42`;

    const doc = parse(ison);
    const orders = doc.getBlock("orders")!;
    const ref = orders.rows[0]["user_id"] as Reference;

    expect(isReference(ref)).toBe(true);
    expect(ref.id).toBe("42");
    expect(ref.type).toBeUndefined();
    expect(ref.toIson()).toBe(":42");
  });

  it("should parse namespaced references", () => {
    const ison = `table.orders
id user
1 :user:101`;

    const doc = parse(ison);
    const orders = doc.getBlock("orders")!;
    const ref = orders.rows[0]["user"] as Reference;

    expect(ref.id).toBe("101");
    expect(ref.type).toBe("user");
    expect(ref.isRelationship()).toBe(false);
    expect(ref.getNamespace()).toBe("user");
    expect(ref.toIson()).toBe(":user:101");
  });

  it("should parse relationship references", () => {
    const ison = `table.memberships
id relationship
1 :MEMBER_OF:10`;

    const doc = parse(ison);
    const memberships = doc.getBlock("memberships")!;
    const ref = memberships.rows[0]["relationship"] as Reference;

    expect(ref.id).toBe("10");
    expect(ref.type).toBe("MEMBER_OF");
    expect(ref.isRelationship()).toBe(true);
    expect(ref.relationshipType()).toBe("MEMBER_OF");
  });
});

describe("Field Type Annotations", () => {
  it("should parse type annotations", () => {
    const ison = `table.products
id:int name:string price:float
1 Widget 29.99`;

    const doc = parse(ison);
    const products = doc.getBlock("products")!;

    expect(products.getFieldType("id")).toBe("int");
    expect(products.getFieldType("name")).toBe("string");
    expect(products.getFieldType("price")).toBe("float");
  });

  it("should identify computed fields", () => {
    const ison = `table.products
id name total:computed
1 Widget 100`;

    const doc = parse(ison);
    const products = doc.getBlock("products")!;

    expect(products.getComputedFields()).toEqual(["total"]);
  });
});

describe("Escape Sequences", () => {
  it("should handle escape sequences", () => {
    const ison = `table.test
content
"line1\\nline2"
"tab\\there"
"quote\\"inside"`;

    const doc = parse(ison);
    const test = doc.getBlock("test")!;

    expect(test.rows[0]["content"]).toBe("line1\nline2");
    expect(test.rows[1]["content"]).toBe("tab\there");
    expect(test.rows[2]["content"]).toBe('quote"inside');
  });
});

describe("Comments", () => {
  it("should skip comment lines", () => {
    const ison = `# This is a comment
table.users
id name
# Another comment
1 Alice`;

    const doc = parse(ison);
    const users = doc.getBlock("users")!;

    expect(users.size()).toBe(1);
    expect(users.rows[0]["name"]).toBe("Alice");
  });
});

describe("Serialization", () => {
  it("should round-trip serialize", () => {
    const original = `table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com`;

    const doc = parse(original);
    const serialized = dumps(doc);
    const doc2 = parse(serialized);

    expect(doc2.getBlock("users")!.size()).toBe(2);
    expect(doc2.getBlock("users")!.rows[0]["name"]).toBe("Alice");
  });

  it("should quote strings when needed", () => {
    const doc = new Document();
    const block = new Block("table", "test");
    block.fields = ["name"];
    block.fieldInfo = [{ name: "name", type: undefined, isComputed: false }];
    block.rows = [{ name: "hello world" }];
    doc.blocks.push(block);

    const serialized = dumps(doc);
    expect(serialized).toContain('"hello world"');
  });
});

describe("ISONL", () => {
  it("should parse ISONL format", () => {
    const isonl = `table.users|id name|1 Alice
table.users|id name|2 Bob`;

    const doc = loadsIsonl(isonl);
    const users = doc.getBlock("users")!;

    expect(users.size()).toBe(2);
    expect(users.rows[0]["name"]).toBe("Alice");
    expect(users.rows[1]["name"]).toBe("Bob");
  });

  it("should serialize to ISONL format", () => {
    const ison = `table.users
id name
1 Alice
2 Bob`;

    const doc = parse(ison);
    const isonl = dumpsIsonl(doc);

    expect(isonl).toContain("table.users|id name|1 Alice");
    expect(isonl).toContain("table.users|id name|2 Bob");
  });

  it("should convert between formats", () => {
    const ison = `table.events
id type
1 click
2 view`;

    const isonl = isonToIsonl(ison);
    const backToIson = isonlToIson(isonl);
    const doc = parse(backToIson);

    expect(doc.getBlock("events")!.size()).toBe(2);
  });
});

describe("fromDict", () => {
  it("should create document from plain object", () => {
    const data = {
      products: [
        { id: 1, name: "Widget", price: 29.99 },
        { id: 2, name: "Gadget", price: 49.99 },
      ],
    };

    const doc = fromDict(data);
    const products = doc.getBlock("products")!;

    expect(products.kind).toBe("table");
    expect(products.size()).toBe(2);
    expect(products.rows[0]["name"]).toBe("Widget");
    expect(products.rows[1]["price"]).toBe(49.99);
  });
});

describe("Document Methods", () => {
  it("should convert to JSON", () => {
    const ison = `table.users
id name
1 Alice`;

    const doc = parse(ison);
    const json = doc.toJson();
    const parsed = JSON.parse(json);

    expect(parsed.users[0].id).toBe(1);
    expect(parsed.users[0].name).toBe("Alice");
  });

  it("should convert to dict", () => {
    const ison = `table.users
id name team
1 Alice :10`;

    const doc = parse(ison);
    const dict = doc.toDict();

    expect(dict.users[0].id).toBe(1);
    expect(dict.users[0].team.$ref).toBe("10");
  });
});
