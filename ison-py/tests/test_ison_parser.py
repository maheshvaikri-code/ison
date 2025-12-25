#!/usr/bin/env python3
"""
Test suite for ISON v1.0 Parser

Tests all edge cases from the specification:
- Type inference
- Quoting and escaping
- References
- Null handling
- Nested fields (dot-paths)
- Comments
"""

from ison_parser import (
    loads, dumps, load, from_dict,
    Document, Block, Reference, FieldInfo,
    ISONSyntaxError,
    # ISONL imports
    loads_isonl, dumps_isonl, ison_to_isonl, isonl_to_ison,
    ISONLRecord, ISONLParser
)


def test_basic_table():
    """Test basic table parsing"""
    ison = """table.users
id name active
1 Alice true
2 Bob false
3 Charlie true"""
    
    doc = loads(ison)
    assert len(doc.blocks) == 1
    block = doc.blocks[0]
    assert block.kind == "table"
    assert block.name == "users"
    assert len(block.rows) == 3
    
    # Check types
    assert block.rows[0]['id'] == 1
    assert block.rows[0]['name'] == "Alice"
    assert block.rows[0]['active'] is True
    assert block.rows[1]['active'] is False
    
    print("[PASS] test_basic_table")


def test_quoted_strings():
    """Test quoted strings with spaces"""
    ison = """table.users
id name city
1 Alice "New York"
2 Bob "San Francisco"
3 "Charlie Brown" "Los Angeles" """
    
    doc = loads(ison)
    assert doc.blocks[0].rows[0]['city'] == "New York"
    assert doc.blocks[0].rows[1]['city'] == "San Francisco"
    assert doc.blocks[0].rows[2]['name'] == "Charlie Brown"
    
    print("[PASS] test_quoted_strings")


def test_escape_sequences():
    """Test escape sequences in quoted strings"""
    ison = r'''table.messages
id text
1 "Hello \"World\""
2 "Line 1\nLine 2"
3 "Tab\tSeparated"'''
    
    doc = loads(ison)
    assert doc.blocks[0].rows[0]['text'] == 'Hello "World"'
    assert doc.blocks[0].rows[1]['text'] == "Line 1\nLine 2"
    assert doc.blocks[0].rows[2]['text'] == "Tab\tSeparated"
    
    print("[PASS] test_escape_sequences")


def test_type_inference():
    """Test all type inference rules"""
    ison = """table.types
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
"123"
"""
    
    doc = loads(ison)
    rows = doc.blocks[0].rows
    
    assert rows[0]['val'] is True
    assert rows[1]['val'] is False
    assert rows[2]['val'] is None
    assert rows[3]['val'] == 42
    assert rows[4]['val'] == -7
    assert rows[5]['val'] == 3.14
    assert rows[6]['val'] == -0.5
    assert isinstance(rows[7]['val'], Reference)
    assert rows[7]['val'].id == "10"
    assert isinstance(rows[8]['val'], Reference)
    assert rows[8]['val'].type == "user"
    assert rows[8]['val'].id == "101"
    assert rows[9]['val'] == "hello"
    assert rows[10]['val'] == "true"  # Quoted, so string
    assert rows[11]['val'] == "123"   # Quoted, so string
    
    print("[PASS] test_type_inference")


def test_references():
    """Test reference parsing"""
    ison = """object.team
id name
10 "AI Research"

table.users
id name team
101 Mahesh :10
102 Priya :10"""
    
    doc = loads(ison)
    users = doc['users']
    
    assert isinstance(users.rows[0]['team'], Reference)
    assert users.rows[0]['team'].id == "10"
    assert users.rows[1]['team'].id == "10"
    
    print("[PASS] test_references")


def test_null_handling():
    """Test null and missing values"""
    ison = """table.users
id name email phone
1 Alice alice@test.com 555-1234
2 Bob null
3 Eve "" null"""
    
    doc = loads(ison)
    rows = doc.blocks[0].rows
    
    # Row 1: all values present
    assert rows[0]['email'] == "alice@test.com"
    assert rows[0]['phone'] == "555-1234"
    
    # Row 2: explicit null and missing trailing
    assert rows[1]['email'] is None
    assert rows[1]['phone'] is None
    
    # Row 3: empty string and null
    assert rows[2]['email'] == ""
    assert rows[2]['phone'] is None
    
    print("[PASS] test_null_handling")


def test_dot_path_fields():
    """Test nested fields via dot-path notation"""
    ison = """object.order
id customer.name customer.address.city customer.address.state total
5001 Mahesh Dallas TX 125.50"""
    
    doc = loads(ison)
    row = doc.blocks[0].rows[0]
    
    assert row['id'] == 5001
    assert row['customer']['name'] == "Mahesh"
    assert row['customer']['address']['city'] == "Dallas"
    assert row['customer']['address']['state'] == "TX"
    assert row['total'] == 125.50
    
    print("[PASS] test_dot_path_fields")


def test_comments():
    """Test comment handling"""
    ison = """# This is a header comment
table.users
id name
# Comment in the middle
1 Alice
2 Bob
# Trailing comment"""
    
    doc = loads(ison)
    assert len(doc.blocks) == 1
    assert len(doc.blocks[0].rows) == 2
    
    print("[PASS] test_comments")


def test_multiple_blocks():
    """Test document with multiple blocks"""
    ison = """object.config
key value
timeout 30

table.users
id name
1 Alice
2 Bob

table.orders
id userId total
100 1 99.99"""
    
    doc = loads(ison)
    assert len(doc.blocks) == 3
    assert doc['config'].kind == "object"
    assert doc['users'].kind == "table"
    assert doc['orders'].kind == "table"
    
    print("[PASS] test_multiple_blocks")


def test_serialization_roundtrip():
    """Test serialize and parse roundtrip"""
    original = """table.products
id   name          price  inStock
1    Widget        9.99   true
2    Gadget        19.99  false
3    "Super Gizmo" 29.99  true"""
    
    # Parse
    doc = loads(original)
    
    # Serialize
    serialized = dumps(doc)
    
    # Parse again
    doc2 = loads(serialized)
    
    # Compare
    assert len(doc2.blocks) == 1
    assert len(doc2.blocks[0].rows) == 3
    assert doc2.blocks[0].rows[2]['name'] == "Super Gizmo"
    
    print("[PASS] test_serialization_roundtrip")


def test_to_json():
    """Test JSON conversion"""
    ison = """table.users
id name active
1 Alice true
2 Bob false"""
    
    doc = loads(ison)
    json_str = doc.to_json()
    
    import json
    data = json.loads(json_str)
    
    assert 'users' in data
    assert len(data['users']) == 2
    assert data['users'][0]['name'] == "Alice"
    
    print("[PASS] test_to_json")


def test_from_dict():
    """Test creating Document from dictionary"""
    data = {
        'config': {'timeout': 30, 'debug': True},
        'users': [
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'}
        ]
    }
    
    doc = from_dict(data)
    assert len(doc.blocks) == 2
    
    # Serialize and verify
    ison_str = dumps(doc)
    assert 'table.users' in ison_str
    assert 'object.config' in ison_str
    
    print("[PASS] test_from_dict")


def test_error_handling():
    """Test error cases"""
    # Invalid header
    try:
        loads("invalid_header\nid name\n1 Alice")
        assert False, "Should have raised error"
    except ISONSyntaxError as e:
        assert "Invalid block header" in str(e)
    
    # Unterminated quote
    try:
        loads('table.test\nid name\n1 "unclosed')
        assert False, "Should have raised error"
    except ISONSyntaxError as e:
        assert "Unterminated" in str(e)
    
    print("[PASS] test_error_handling")


def test_complete_example():
    """Test the complete example from the spec"""
    ison = """# ISON Example: E-commerce Order System
# Version: 1.0

meta.document
version schema author
1.0 ecommerce "Mahesh Vaikri"

# Customer information
object.customer
id name email address.city address.state
1001 "John Smith" john@example.com "New York" NY

# Orders for customer
table.orders
id customerId date total status
5001 :1001 2025-01-15 125.50 completed
5002 :1001 2025-01-20 89.99 processing

# Line items for orders
table.order_items
orderId sku name qty unitPrice
5001 A1 Widget 2 25.00
5001 B2 Gadget 1 75.50
5002 C3 "Deluxe Widget" 3 29.99"""
    
    doc = loads(ison)
    
    assert len(doc.blocks) == 4
    
    # Check metadata
    meta = doc['document']
    assert meta.rows[0]['version'] == 1.0
    assert meta.rows[0]['author'] == "Mahesh Vaikri"
    
    # Check customer
    customer = doc['customer']
    assert customer.rows[0]['address']['city'] == "New York"
    
    # Check orders with references
    orders = doc['orders']
    assert isinstance(orders.rows[0]['customerId'], Reference)
    assert orders.rows[0]['customerId'].id == "1001"
    
    # Check order items
    items = doc['order_items']
    assert len(items.rows) == 3
    assert items.rows[2]['name'] == "Deluxe Widget"
    
    print("[PASS] test_complete_example")


def test_typed_fields():
    """Test type annotations in field headers"""
    ison = """table.products
id:int name:string price:float in_stock:bool category:ref
1 Widget 29.99 true :CAT-1
2 Gadget 49.99 false :CAT-2"""

    doc = loads(ison)
    block = doc.blocks[0]

    # Check field info was parsed
    assert len(block.field_info) == 5
    assert block.field_info[0].name == "id"
    assert block.field_info[0].type == "int"
    assert block.field_info[1].type == "string"
    assert block.field_info[2].type == "float"
    assert block.field_info[3].type == "bool"
    assert block.field_info[4].type == "ref"

    # Data should still parse correctly
    assert block.rows[0]['id'] == 1
    assert block.rows[0]['price'] == 29.99
    assert block.rows[0]['in_stock'] is True

    print("[PASS] test_typed_fields")


def test_relationship_references():
    """Test relationship-typed references like :MEMBER_OF:10"""
    ison = """table.users
id name team
101 Mahesh :MEMBER_OF:10
102 John :LEADS:10
103 Jane :REPORTS_TO:102"""

    doc = loads(ison)
    rows = doc.blocks[0].rows

    # Check relationship references
    assert isinstance(rows[0]['team'], Reference)
    assert rows[0]['team'].type == "MEMBER_OF"
    assert rows[0]['team'].id == "10"
    assert rows[0]['team'].is_relationship() is True
    assert rows[0]['team'].relationship_type == "MEMBER_OF"

    assert rows[1]['team'].type == "LEADS"
    assert rows[1]['team'].is_relationship() is True

    assert rows[2]['team'].type == "REPORTS_TO"
    assert rows[2]['team'].id == "102"

    print("[PASS] test_relationship_references")


def test_summary_rows():
    """Test summary rows with --- separator"""
    ison = """table.sales_by_region
region q1 q2 q3 q4 total
Americas 1.2 1.4 1.5 1.8 5.9
EMEA 0.8 0.9 1.0 1.1 3.8
APAC 0.5 0.6 0.7 0.9 2.7
---
TOTAL: 2.5M 2.9M 3.2M 3.8M 12.4M"""

    doc = loads(ison)
    block = doc.blocks[0]

    # Should have 3 data rows
    assert len(block.rows) == 3

    # Summary should be captured
    assert block.summary is not None
    assert "TOTAL:" in block.summary

    print("[PASS] test_summary_rows")


def test_computed_fields():
    """Test computed field markers"""
    ison = """table.orders
id subtotal tax_rate tax:computed total:computed
1 100.00 0.08 8.00 108.00
2 50.00 0.08 4.00 54.00"""

    doc = loads(ison)
    block = doc.blocks[0]

    # Check computed field detection
    computed = block.get_computed_fields()
    assert "tax" in computed
    assert "total" in computed
    assert "id" not in computed

    print("[PASS] test_computed_fields")


def test_serialization_with_types():
    """Test serialization preserves type annotations"""
    ison = """table.products
id:int name:string price:float
1 Widget 29.99
2 Gadget 49.99"""

    doc = loads(ison)
    serialized = dumps(doc)

    # Type annotations should be preserved
    assert "id:int" in serialized
    assert "name:string" in serialized
    assert "price:float" in serialized

    print("[PASS] test_serialization_with_types")


# =============================================================================
# ISONL Tests
# =============================================================================

def test_isonl_basic_parsing():
    """Test basic ISONL line parsing"""
    isonl = """table.users|id name email|1 Alice alice@test.com
table.users|id name email|2 Bob bob@test.com
table.users|id name email|3 "Charlie Brown" charlie@test.com"""

    doc = loads_isonl(isonl)
    assert len(doc.blocks) == 1
    block = doc.blocks[0]
    assert block.kind == "table"
    assert block.name == "users"
    assert len(block.rows) == 3

    assert block.rows[0]['id'] == 1
    assert block.rows[0]['name'] == "Alice"
    assert block.rows[2]['name'] == "Charlie Brown"

    print("[PASS] test_isonl_basic_parsing")


def test_isonl_type_inference():
    """Test type inference in ISONL"""
    isonl = """table.types|val|true
table.types|val|false
table.types|val|null
table.types|val|42
table.types|val|3.14
table.types|val|:10
table.types|val|hello
table.types|val|"true"
table.types|val|"123" """

    doc = loads_isonl(isonl)
    rows = doc.blocks[0].rows

    assert rows[0]['val'] is True
    assert rows[1]['val'] is False
    assert rows[2]['val'] is None
    assert rows[3]['val'] == 42
    assert rows[4]['val'] == 3.14
    assert isinstance(rows[5]['val'], Reference)
    assert rows[5]['val'].id == "10"
    assert rows[6]['val'] == "hello"
    assert rows[7]['val'] == "true"  # Quoted string
    assert rows[8]['val'] == "123"   # Quoted string

    print("[PASS] test_isonl_type_inference")


def test_isonl_references():
    """Test references in ISONL"""
    isonl = """table.orders|id customer total|O1 :C1 100.00
table.orders|id customer total|O2 :user:C2 200.00
table.orders|id customer total|O3 :BELONGS_TO:C1 150.00"""

    doc = loads_isonl(isonl)
    rows = doc.blocks[0].rows

    assert isinstance(rows[0]['customer'], Reference)
    assert rows[0]['customer'].id == "C1"

    assert rows[1]['customer'].type == "user"
    assert rows[1]['customer'].id == "C2"

    assert rows[2]['customer'].type == "BELONGS_TO"
    assert rows[2]['customer'].is_relationship() is True

    print("[PASS] test_isonl_references")


def test_isonl_multiple_blocks():
    """Test ISONL with multiple block types"""
    isonl = """object.config|timeout debug|30 true
table.users|id name|1 Alice
table.users|id name|2 Bob
table.orders|id user_id total|101 :1 99.99"""

    doc = loads_isonl(isonl)
    assert len(doc.blocks) == 3

    # Blocks should be grouped correctly
    config = doc['config']
    assert config.kind == "object"
    assert config.rows[0]['timeout'] == 30
    assert config.rows[0]['debug'] is True

    users = doc['users']
    assert len(users.rows) == 2

    orders = doc['orders']
    assert len(orders.rows) == 1
    assert isinstance(orders.rows[0]['user_id'], Reference)

    print("[PASS] test_isonl_multiple_blocks")


def test_isonl_comments_and_empty():
    """Test ISONL with comments and empty lines"""
    isonl = """# This is a comment
table.users|id name|1 Alice

# Another comment
table.users|id name|2 Bob

"""

    doc = loads_isonl(isonl)
    assert len(doc.blocks) == 1
    assert len(doc.blocks[0].rows) == 2

    print("[PASS] test_isonl_comments_and_empty")


def test_isonl_serialization():
    """Test ISONL serialization"""
    # Create a document
    ison = """table.users
id name active
1 Alice true
2 Bob false"""

    doc = loads(ison)
    isonl = dumps_isonl(doc)

    # Should have one line per row
    lines = [l for l in isonl.split('\n') if l.strip()]
    assert len(lines) == 2

    # Each line should have correct format
    assert lines[0].startswith("table.users|")
    assert "id name active" in lines[0]
    assert "1 Alice true" in lines[0]

    print("[PASS] test_isonl_serialization")


def test_isonl_roundtrip():
    """Test ISONL to ISON roundtrip"""
    original_isonl = """table.products|id name price|1 Widget 9.99
table.products|id name price|2 "Super Gadget" 19.99
object.config|timeout debug|30 true"""

    # Parse ISONL
    doc = loads_isonl(original_isonl)

    # Convert to ISON
    ison = dumps(doc)

    # Parse ISON
    doc2 = loads(ison)

    # Verify data
    products = doc2['products']
    assert len(products.rows) == 2
    assert products.rows[0]['name'] == "Widget"
    assert products.rows[1]['name'] == "Super Gadget"

    config = doc2['config']
    assert config.rows[0]['timeout'] == 30

    print("[PASS] test_isonl_roundtrip")


def test_ison_to_isonl_conversion():
    """Test ISON to ISONL conversion function"""
    ison = """table.users
id name
1 Alice
2 Bob
3 "Charlie Brown" """

    isonl = ison_to_isonl(ison)

    # Should have 3 lines
    lines = [l for l in isonl.split('\n') if l.strip()]
    assert len(lines) == 3

    # Parse back
    doc = loads_isonl(isonl)
    assert len(doc.blocks[0].rows) == 3
    assert doc.blocks[0].rows[2]['name'] == "Charlie Brown"

    print("[PASS] test_ison_to_isonl_conversion")


def test_isonl_to_ison_conversion():
    """Test ISONL to ISON conversion function"""
    isonl = """table.users|id name|1 Alice
table.users|id name|2 Bob"""

    ison = isonl_to_ison(isonl)

    # Should have proper ISON format
    assert "table.users" in ison
    assert "id name" in ison
    assert "Alice" in ison
    assert "Bob" in ison

    # Parse back
    doc = loads(ison)
    assert len(doc.blocks[0].rows) == 2

    print("[PASS] test_isonl_to_ison_conversion")


def test_isonl_quoted_pipes():
    """Test ISONL with pipes in quoted strings"""
    isonl = """table.data|id value|1 "A|B|C"
table.data|id value|2 "Contains \\| escaped pipe" """

    parser = ISONLParser()
    records = parser.parse_string(isonl)

    assert len(records) == 2
    assert records[0].values['value'] == "A|B|C"

    print("[PASS] test_isonl_quoted_pipes")


def test_isonl_error_handling():
    """Test ISONL error cases"""
    # Invalid format (not enough pipes)
    try:
        loads_isonl("table.test|id name")
        assert False, "Should have raised error"
    except ISONSyntaxError as e:
        assert "3 pipe-separated sections" in str(e)

    # Invalid header
    try:
        loads_isonl("invalid|id name|1 Alice")
        assert False, "Should have raised error"
    except ISONSyntaxError as e:
        assert "Invalid ISONL header" in str(e)

    print("[PASS] test_isonl_error_handling")


def test_isonl_fine_tuning_format():
    """Test ISONL for fine-tuning dataset format"""
    isonl = """table.examples|instruction input output|"Summarize" "Long article text here..." "Brief summary"
table.examples|instruction input output|"Translate" "Hello world" "Hola mundo"
table.examples|instruction input output|"Extract entities" "Apple Inc. in Cupertino" "[Apple Inc., Cupertino]" """

    doc = loads_isonl(isonl)
    rows = doc.blocks[0].rows

    assert len(rows) == 3
    assert rows[0]['instruction'] == "Summarize"
    assert rows[1]['output'] == "Hola mundo"
    assert rows[2]['input'] == "Apple Inc. in Cupertino"

    print("[PASS] test_isonl_fine_tuning_format")


def run_all_tests():
    """Run all tests"""
    print("Running ISON v1.0 Parser Tests\n" + "=" * 40)

    test_basic_table()
    test_quoted_strings()
    test_escape_sequences()
    test_type_inference()
    test_references()
    test_null_handling()
    test_dot_path_fields()
    test_comments()
    test_multiple_blocks()
    test_serialization_roundtrip()
    test_to_json()
    test_from_dict()
    test_error_handling()
    test_complete_example()

    # New strategic feature tests
    test_typed_fields()
    test_relationship_references()
    test_summary_rows()
    test_computed_fields()
    test_serialization_with_types()

    # ISONL tests
    print("\n" + "-" * 40)
    print("Running ISONL Tests")
    print("-" * 40)
    test_isonl_basic_parsing()
    test_isonl_type_inference()
    test_isonl_references()
    test_isonl_multiple_blocks()
    test_isonl_comments_and_empty()
    test_isonl_serialization()
    test_isonl_roundtrip()
    test_ison_to_isonl_conversion()
    test_isonl_to_ison_conversion()
    test_isonl_quoted_pipes()
    test_isonl_error_handling()
    test_isonl_fine_tuning_format()

    print("\n" + "=" * 40)
    print("All tests passed!")


if __name__ == '__main__':
    run_all_tests()
