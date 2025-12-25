/**
 * Test suite for ISON v1.0 JavaScript Parser
 * Run with: node test_ison_parser.js
 */

const ISON = require('../src/ison-parser.js');

let passed = 0;
let failed = 0;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message || 'Assertion failed');
    }
}

function assertEqual(actual, expected, message) {
    if (actual !== expected) {
        throw new Error(`${message || 'Assertion failed'}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

function test(name, fn) {
    try {
        fn();
        console.log(`[PASS] ${name}`);
        passed++;
    } catch (e) {
        console.log(`[FAIL] ${name}: ${e.message}`);
        failed++;
    }
}

// =============================================================================
// Tests
// =============================================================================

test('test_basic_table', () => {
    const ison = `table.users
id name active
1 Alice true
2 Bob false
3 Charlie true`;

    const doc = ISON.loads(ison);
    assertEqual(doc.blocks.length, 1);

    const block = doc.blocks[0];
    assertEqual(block.kind, 'table');
    assertEqual(block.name, 'users');
    assertEqual(block.rows.length, 3);

    assertEqual(block.rows[0].id, 1);
    assertEqual(block.rows[0].name, 'Alice');
    assertEqual(block.rows[0].active, true);
    assertEqual(block.rows[1].active, false);
});

test('test_quoted_strings', () => {
    const ison = `table.users
id name city
1 Alice "New York"
2 Bob "San Francisco"
3 "Charlie Brown" "Los Angeles"`;

    const doc = ISON.loads(ison);
    assertEqual(doc.blocks[0].rows[0].city, 'New York');
    assertEqual(doc.blocks[0].rows[1].city, 'San Francisco');
    assertEqual(doc.blocks[0].rows[2].name, 'Charlie Brown');
});

test('test_escape_sequences', () => {
    const ison = `table.messages
id text
1 "Hello \\"World\\""
2 "Line 1\\nLine 2"
3 "Tab\\tSeparated"`;

    const doc = ISON.loads(ison);
    assertEqual(doc.blocks[0].rows[0].text, 'Hello "World"');
    assertEqual(doc.blocks[0].rows[1].text, 'Line 1\nLine 2');
    assertEqual(doc.blocks[0].rows[2].text, 'Tab\tSeparated');
});

test('test_type_inference', () => {
    const ison = `table.types
val
true
false
null
42
-7
3.14
-0.5
:10
:user:101
hello
"true"
"123"`;

    const doc = ISON.loads(ison);
    const rows = doc.blocks[0].rows;

    assertEqual(rows[0].val, true);
    assertEqual(rows[1].val, false);
    assertEqual(rows[2].val, null);
    assertEqual(rows[3].val, 42);
    assertEqual(rows[4].val, -7);
    assertEqual(rows[5].val, 3.14);
    assertEqual(rows[6].val, -0.5);
    assert(rows[7].val instanceof ISON.Reference);
    assertEqual(rows[7].val.id, '10');
    assert(rows[8].val instanceof ISON.Reference);
    assertEqual(rows[8].val.type, 'user');
    assertEqual(rows[8].val.id, '101');
    assertEqual(rows[9].val, 'hello');
    assertEqual(rows[10].val, 'true');  // Quoted, so string
    assertEqual(rows[11].val, '123');   // Quoted, so string
});

test('test_references', () => {
    const ison = `object.team
id name
10 "AI Research"

table.users
id name team
101 Mahesh :10
102 Priya :10`;

    const doc = ISON.loads(ison);
    const users = doc.getBlock('users');

    assert(users.rows[0].team instanceof ISON.Reference);
    assertEqual(users.rows[0].team.id, '10');
    assertEqual(users.rows[1].team.id, '10');
});

test('test_null_handling', () => {
    const ison = `table.users
id name email phone
1 Alice alice@test.com 555-1234
2 Bob null
3 Eve "" null`;

    const doc = ISON.loads(ison);
    const rows = doc.blocks[0].rows;

    assertEqual(rows[0].email, 'alice@test.com');
    assertEqual(rows[0].phone, '555-1234');
    assertEqual(rows[1].email, null);
    assertEqual(rows[1].phone, null);  // Missing trailing
    assertEqual(rows[2].email, '');
    assertEqual(rows[2].phone, null);
});

test('test_dot_path_fields', () => {
    const ison = `object.order
id customer.name customer.address.city customer.address.state total
5001 Mahesh Dallas TX 125.50`;

    const doc = ISON.loads(ison);
    const row = doc.blocks[0].rows[0];

    assertEqual(row.id, 5001);
    assertEqual(row.customer.name, 'Mahesh');
    assertEqual(row.customer.address.city, 'Dallas');
    assertEqual(row.customer.address.state, 'TX');
    assertEqual(row.total, 125.50);
});

test('test_comments', () => {
    const ison = `# This is a header comment
table.users
id name
# Comment in the middle
1 Alice
2 Bob
# Trailing comment`;

    const doc = ISON.loads(ison);
    assertEqual(doc.blocks.length, 1);
    assertEqual(doc.blocks[0].rows.length, 2);
});

test('test_multiple_blocks', () => {
    const ison = `object.config
key value
timeout 30

table.users
id name
1 Alice
2 Bob

table.orders
id userId total
100 1 99.99`;

    const doc = ISON.loads(ison);
    assertEqual(doc.blocks.length, 3);
    assertEqual(doc.getBlock('config').kind, 'object');
    assertEqual(doc.getBlock('users').kind, 'table');
    assertEqual(doc.getBlock('orders').kind, 'table');
});

test('test_serialization_roundtrip', () => {
    const original = `table.products
id   name          price  inStock
1    Widget        9.99   true
2    Gadget        19.99  false
3    "Super Gizmo" 29.99  true`;

    const doc = ISON.loads(original);
    const serialized = ISON.dumps(doc);
    const doc2 = ISON.loads(serialized);

    assertEqual(doc2.blocks.length, 1);
    assertEqual(doc2.blocks[0].rows.length, 3);
    assertEqual(doc2.blocks[0].rows[2].name, 'Super Gizmo');
});

test('test_to_json', () => {
    const ison = `table.users
id name active
1 Alice true
2 Bob false`;

    const doc = ISON.loads(ison);
    const jsonStr = doc.toJSON();
    const data = JSON.parse(jsonStr);

    assert('users' in data);
    assertEqual(data.users.length, 2);
    assertEqual(data.users[0].name, 'Alice');
});

test('test_from_dict', () => {
    const data = {
        config: { timeout: 30, debug: true },
        users: [
            { id: 1, name: 'Alice' },
            { id: 2, name: 'Bob' }
        ]
    };

    const doc = ISON.fromDict(data);
    assertEqual(doc.blocks.length, 2);

    const isonStr = ISON.dumps(doc);
    assert(isonStr.includes('table.users'));
    assert(isonStr.includes('object.config'));
});

test('test_error_handling', () => {
    // Invalid header
    let threw = false;
    try {
        ISON.loads('invalid_header\nid name\n1 Alice');
    } catch (e) {
        threw = true;
        assert(e instanceof ISON.ISONSyntaxError);
        assert(e.message.includes('Invalid block header'));
    }
    assert(threw, 'Should have thrown error for invalid header');

    // Unterminated quote
    threw = false;
    try {
        ISON.loads('table.test\nid name\n1 "unclosed');
    } catch (e) {
        threw = true;
        assert(e instanceof ISON.ISONSyntaxError);
        assert(e.message.includes('Unterminated'));
    }
    assert(threw, 'Should have thrown error for unterminated quote');
});

test('test_typed_fields', () => {
    const ison = `table.products
id:int name:string price:float in_stock:bool category:ref
1 Widget 29.99 true :CAT-1
2 Gadget 49.99 false :CAT-2`;

    const doc = ISON.loads(ison);
    const block = doc.blocks[0];

    assertEqual(block.fieldInfo.length, 5);
    assertEqual(block.fieldInfo[0].name, 'id');
    assertEqual(block.fieldInfo[0].type, 'int');
    assertEqual(block.fieldInfo[1].type, 'string');
    assertEqual(block.fieldInfo[2].type, 'float');
    assertEqual(block.fieldInfo[3].type, 'bool');
    assertEqual(block.fieldInfo[4].type, 'ref');

    assertEqual(block.rows[0].id, 1);
    assertEqual(block.rows[0].price, 29.99);
    assertEqual(block.rows[0].in_stock, true);
});

test('test_relationship_references', () => {
    const ison = `table.users
id name team
101 Mahesh :MEMBER_OF:10
102 John :LEADS:10
103 Jane :REPORTS_TO:102`;

    const doc = ISON.loads(ison);
    const rows = doc.blocks[0].rows;

    assert(rows[0].team instanceof ISON.Reference);
    assertEqual(rows[0].team.type, 'MEMBER_OF');
    assertEqual(rows[0].team.id, '10');
    assertEqual(rows[0].team.isRelationship(), true);
    assertEqual(rows[0].team.relationshipType, 'MEMBER_OF');

    assertEqual(rows[1].team.type, 'LEADS');
    assertEqual(rows[1].team.isRelationship(), true);

    assertEqual(rows[2].team.type, 'REPORTS_TO');
    assertEqual(rows[2].team.id, '102');
});

test('test_summary_rows', () => {
    const ison = `table.sales_by_region
region q1 q2 q3 q4 total
Americas 1.2 1.4 1.5 1.8 5.9
EMEA 0.8 0.9 1.0 1.1 3.8
APAC 0.5 0.6 0.7 0.9 2.7
---
TOTAL: 2.5M 2.9M 3.2M 3.8M 12.4M`;

    const doc = ISON.loads(ison);
    const block = doc.blocks[0];

    assertEqual(block.rows.length, 3);
    assert(block.summary !== null);
    assert(block.summary.includes('TOTAL:'));
});

test('test_computed_fields', () => {
    const ison = `table.orders
id subtotal tax_rate tax:computed total:computed
1 100.00 0.08 8.00 108.00
2 50.00 0.08 4.00 54.00`;

    const doc = ISON.loads(ison);
    const block = doc.blocks[0];

    const computed = block.getComputedFields();
    assert(computed.includes('tax'));
    assert(computed.includes('total'));
    assert(!computed.includes('id'));
});

test('test_serialization_with_types', () => {
    const ison = `table.products
id:int name:string price:float
1 Widget 29.99
2 Gadget 49.99`;

    const doc = ISON.loads(ison);
    const serialized = ISON.dumps(doc);

    assert(serialized.includes('id:int'));
    assert(serialized.includes('name:string'));
    assert(serialized.includes('price:float'));
});

test('test_json_to_ison', () => {
    const jsonData = {
        users: [
            { id: 1, name: 'Alice', active: true },
            { id: 2, name: 'Bob', active: false }
        ]
    };

    const isonStr = ISON.jsonToISON(jsonData);
    assert(isonStr.includes('table.users'));
    assert(isonStr.includes('Alice'));
    assert(isonStr.includes('true'));
});

test('test_ison_to_json', () => {
    const ison = `table.users
id name active
1 Alice true
2 Bob false`;

    const jsonObj = ISON.isonToJSON(ison);
    assert('users' in jsonObj);
    assertEqual(jsonObj.users.length, 2);
    assertEqual(jsonObj.users[0].name, 'Alice');
});

// =============================================================================
// ISONL Tests
// =============================================================================

console.log('\n' + '-'.repeat(50));
console.log('Running ISONL Tests');
console.log('-'.repeat(50));

test('test_isonl_basic_parsing', () => {
    const isonl = `table.users|id name email|1 Alice alice@test.com
table.users|id name email|2 Bob bob@test.com
table.users|id name email|3 "Charlie Brown" charlie@test.com`;

    const doc = ISON.loadsISONL(isonl);
    assertEqual(doc.blocks.length, 1);

    const block = doc.blocks[0];
    assertEqual(block.kind, 'table');
    assertEqual(block.name, 'users');
    assertEqual(block.rows.length, 3);

    assertEqual(block.rows[0].id, 1);
    assertEqual(block.rows[0].name, 'Alice');
    assertEqual(block.rows[2].name, 'Charlie Brown');
});

test('test_isonl_type_inference', () => {
    const isonl = `table.types|val|true
table.types|val|false
table.types|val|null
table.types|val|42
table.types|val|3.14
table.types|val|:10
table.types|val|hello
table.types|val|"true"
table.types|val|"123"`;

    const doc = ISON.loadsISONL(isonl);
    const rows = doc.blocks[0].rows;

    assertEqual(rows[0].val, true);
    assertEqual(rows[1].val, false);
    assertEqual(rows[2].val, null);
    assertEqual(rows[3].val, 42);
    assertEqual(rows[4].val, 3.14);
    assert(rows[5].val instanceof ISON.Reference);
    assertEqual(rows[5].val.id, '10');
    assertEqual(rows[6].val, 'hello');
    assertEqual(rows[7].val, 'true');  // Quoted string
    assertEqual(rows[8].val, '123');   // Quoted string
});

test('test_isonl_references', () => {
    const isonl = `table.orders|id customer total|O1 :C1 100.00
table.orders|id customer total|O2 :user:C2 200.00
table.orders|id customer total|O3 :BELONGS_TO:C1 150.00`;

    const doc = ISON.loadsISONL(isonl);
    const rows = doc.blocks[0].rows;

    assert(rows[0].customer instanceof ISON.Reference);
    assertEqual(rows[0].customer.id, 'C1');

    assertEqual(rows[1].customer.type, 'user');
    assertEqual(rows[1].customer.id, 'C2');

    assertEqual(rows[2].customer.type, 'BELONGS_TO');
    assertEqual(rows[2].customer.isRelationship(), true);
});

test('test_isonl_multiple_blocks', () => {
    const isonl = `object.config|timeout debug|30 true
table.users|id name|1 Alice
table.users|id name|2 Bob
table.orders|id user_id total|101 :1 99.99`;

    const doc = ISON.loadsISONL(isonl);
    assertEqual(doc.blocks.length, 3);

    const config = doc.getBlock('config');
    assertEqual(config.kind, 'object');
    assertEqual(config.rows[0].timeout, 30);
    assertEqual(config.rows[0].debug, true);

    const users = doc.getBlock('users');
    assertEqual(users.rows.length, 2);

    const orders = doc.getBlock('orders');
    assertEqual(orders.rows.length, 1);
    assert(orders.rows[0].user_id instanceof ISON.Reference);
});

test('test_isonl_comments_and_empty', () => {
    const isonl = `# This is a comment
table.users|id name|1 Alice

# Another comment
table.users|id name|2 Bob

`;

    const doc = ISON.loadsISONL(isonl);
    assertEqual(doc.blocks.length, 1);
    assertEqual(doc.blocks[0].rows.length, 2);
});

test('test_isonl_serialization', () => {
    const ison = `table.users
id name active
1 Alice true
2 Bob false`;

    const doc = ISON.loads(ison);
    const isonl = ISON.dumpsISONL(doc);

    const lines = isonl.split('\n').filter(l => l.trim());
    assertEqual(lines.length, 2);

    assert(lines[0].startsWith('table.users|'));
    assert(lines[0].includes('id name active'));
    assert(lines[0].includes('1 Alice true'));
});

test('test_isonl_roundtrip', () => {
    const originalIsonl = `table.products|id name price|1 Widget 9.99
table.products|id name price|2 "Super Gadget" 19.99
object.config|timeout debug|30 true`;

    // Parse ISONL
    const doc = ISON.loadsISONL(originalIsonl);

    // Convert to ISON
    const ison = ISON.dumps(doc);

    // Parse ISON
    const doc2 = ISON.loads(ison);

    // Verify data
    const products = doc2.getBlock('products');
    assertEqual(products.rows.length, 2);
    assertEqual(products.rows[0].name, 'Widget');
    assertEqual(products.rows[1].name, 'Super Gadget');

    const config = doc2.getBlock('config');
    assertEqual(config.rows[0].timeout, 30);
});

test('test_ison_to_isonl_conversion', () => {
    const ison = `table.users
id name
1 Alice
2 Bob
3 "Charlie Brown"`;

    const isonl = ISON.isonToISONL(ison);

    const lines = isonl.split('\n').filter(l => l.trim());
    assertEqual(lines.length, 3);

    // Parse back
    const doc = ISON.loadsISONL(isonl);
    assertEqual(doc.blocks[0].rows.length, 3);
    assertEqual(doc.blocks[0].rows[2].name, 'Charlie Brown');
});

test('test_isonl_to_ison_conversion', () => {
    const isonl = `table.users|id name|1 Alice
table.users|id name|2 Bob`;

    const ison = ISON.isonlToISON(isonl);

    assert(ison.includes('table.users'));
    assert(ison.includes('id name'));
    assert(ison.includes('Alice'));
    assert(ison.includes('Bob'));

    // Parse back
    const doc = ISON.loads(ison);
    assertEqual(doc.blocks[0].rows.length, 2);
});

test('test_isonl_quoted_pipes', () => {
    const isonl = `table.data|id value|1 "A|B|C"`;

    const parser = new ISON.ISONLParser();
    const records = parser.parseString(isonl);

    assertEqual(records.length, 1);
    assertEqual(records[0].values.value, 'A|B|C');
});

test('test_isonl_error_handling', () => {
    // Invalid format (not enough pipes)
    let threw = false;
    try {
        ISON.loadsISONL('table.test|id name');
    } catch (e) {
        threw = true;
        assert(e instanceof ISON.ISONSyntaxError);
        assert(e.message.includes('3 pipe-separated sections'));
    }
    assert(threw, 'Should have thrown error for invalid format');

    // Invalid header
    threw = false;
    try {
        ISON.loadsISONL('invalid|id name|1 Alice');
    } catch (e) {
        threw = true;
        assert(e instanceof ISON.ISONSyntaxError);
        assert(e.message.includes('Invalid ISONL header'));
    }
    assert(threw, 'Should have thrown error for invalid header');
});

test('test_isonl_fine_tuning_format', () => {
    const isonl = `table.examples|instruction input output|"Summarize" "Long article text here..." "Brief summary"
table.examples|instruction input output|"Translate" "Hello world" "Hola mundo"
table.examples|instruction input output|"Extract entities" "Apple Inc. in Cupertino" "[Apple Inc., Cupertino]"`;

    const doc = ISON.loadsISONL(isonl);
    const rows = doc.blocks[0].rows;

    assertEqual(rows.length, 3);
    assertEqual(rows[0].instruction, 'Summarize');
    assertEqual(rows[1].output, 'Hola mundo');
    assertEqual(rows[2].input, 'Apple Inc. in Cupertino');
});

test('test_isonl_stream', () => {
    const lines = [
        'table.users|id name|1 Alice',
        '# Comment',
        'table.users|id name|2 Bob',
        '',
        'table.users|id name|3 Charlie'
    ];

    const records = [];
    for (const record of ISON.isonlStream(lines)) {
        records.push(record);
    }

    assertEqual(records.length, 3);
    assertEqual(records[0].values.name, 'Alice');
    assertEqual(records[1].values.name, 'Bob');
    assertEqual(records[2].values.name, 'Charlie');
});

// =============================================================================
// Run Tests
// =============================================================================

console.log('\n' + '='.repeat(50));
console.log(`Results: ${passed} passed, ${failed} failed`);

if (failed > 0) {
    process.exit(1);
}
