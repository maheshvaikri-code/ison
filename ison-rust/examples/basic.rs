//! Basic example of using the ISON parser

use ison_rs::{parse, dumps, dumps_isonl, Block, Document, FieldInfo, Value};

fn main() {
    println!("=== ISON Parser for Rust ===\n");

    // Example 1: Parse ISON text
    println!("1. Parsing ISON text:");
    let ison_text = r#"
table.users
id:int name:string email active:bool
1 Alice alice@example.com true
2 Bob bob@example.com false
3 Charlie charlie@example.com true

table.orders
id:int user_id product price:float
101 :1 Widget 29.99
102 :1 Gadget 49.99
103 :2 Widget 29.99
"#;

    let doc = parse(ison_text).expect("Failed to parse ISON");

    println!("Document has {} blocks\n", doc.len());

    // Access users
    let users = doc.get("users").expect("Users block not found");
    println!("Users table has {} rows:", users.len());
    for row in &users.rows {
        let id = row.get("id").and_then(|v| v.as_int()).unwrap_or(0);
        let name = row.get("name").and_then(|v| v.as_str()).unwrap_or("");
        let active = row.get("active").and_then(|v| v.as_bool()).unwrap_or(false);
        println!("  User {}: {} (active: {})", id, name, active);
    }

    // Access orders with references
    println!("\nOrders table:");
    let orders = doc.get("orders").expect("Orders block not found");
    for row in &orders.rows {
        let id = row.get("id").and_then(|v| v.as_int()).unwrap_or(0);
        let user_ref = row.get("user_id").and_then(|v| v.as_reference());
        let product = row.get("product").and_then(|v| v.as_str()).unwrap_or("");
        let price = row.get("price").and_then(|v| v.as_float()).unwrap_or(0.0);

        let ref_str = user_ref.map(|r| r.to_ison()).unwrap_or_default();
        println!("  Order {}: {} ${:.2} (user ref: {})", id, product, price, ref_str);
    }

    // Example 2: Type annotations
    println!("\n2. Field Type Annotations:");
    let products = doc.get("users").unwrap();
    println!("Field types:");
    for fi in &products.field_info {
        let type_str = fi.field_type.as_deref().unwrap_or("(none)");
        println!("  {} : {}", fi.name, type_str);
    }

    // Example 3: References
    println!("\n3. Reference Types:");
    let ref_text = r#"
table.relationships
id type_ref namespace_ref simple_ref
1 :MEMBER_OF:10 :user:101 :42
"#;

    let ref_doc = parse(ref_text).unwrap();
    let rel = ref_doc.get("relationships").unwrap();

    let type_ref = rel[0].get("type_ref").and_then(|v| v.as_reference()).unwrap();
    println!("Relationship ref: {}", type_ref.to_ison());
    println!("  Is relationship: {}", type_ref.is_relationship());
    println!("  Type: {:?}", type_ref.ref_type);

    let ns_ref = rel[0].get("namespace_ref").and_then(|v| v.as_reference()).unwrap();
    println!("\nNamespace ref: {}", ns_ref.to_ison());
    println!("  Is relationship: {}", ns_ref.is_relationship());
    println!("  Namespace: {:?}", ns_ref.get_namespace());

    // Example 4: Create document programmatically
    println!("\n4. Creating Document Programmatically:");
    let mut new_doc = Document::new();

    let mut block = Block::new("table", "products");
    block.fields = vec!["id".to_string(), "name".to_string(), "price".to_string()];
    block.field_info = vec![
        FieldInfo::with_type("id", "int"),
        FieldInfo::with_type("name", "string"),
        FieldInfo::with_type("price", "float"),
    ];

    let mut row1 = std::collections::HashMap::new();
    row1.insert("id".to_string(), Value::Int(1));
    row1.insert("name".to_string(), Value::String("Widget".to_string()));
    row1.insert("price".to_string(), Value::Float(29.99));
    block.rows.push(row1);

    let mut row2 = std::collections::HashMap::new();
    row2.insert("id".to_string(), Value::Int(2));
    row2.insert("name".to_string(), Value::String("Gadget".to_string()));
    row2.insert("price".to_string(), Value::Float(49.99));
    block.rows.push(row2);

    new_doc.blocks.push(block);

    println!("ISON output:");
    println!("{}", dumps(&new_doc, true));

    // Example 5: ISONL format
    println!("\n5. ISONL Streaming Format:");
    let isonl = dumps_isonl(&doc);
    println!("ISONL output (one record per line):");
    for line in isonl.lines().take(3) {
        println!("  {}", line);
    }
    println!("  ...");

    // Example 6: JSON export (requires serde feature)
    #[cfg(feature = "serde")]
    {
        println!("\n6. JSON Export:");
        let json = doc.to_json(true);
        println!("{}", &json[..json.len().min(500)]);
        println!("...");
    }

    println!("\n=== All examples completed ===");
}
