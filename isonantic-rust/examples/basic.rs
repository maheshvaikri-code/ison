//! Basic example of using ISONantic for validation

use isonantic_rs::prelude::*;
use ison_rs::parse;

fn main() {
    println!("=== ISONantic Validation Example ===\n");

    // Example 1: Basic table validation
    println!("1. Basic Table Validation:");

    let user_schema = table("users")
        .field("id", int().required())
        .field("name", string().min(1).max(100))
        .field("email", string().email())
        .field("active", boolean().default_value(true));

    let ison_text = r#"
table.users
id name email active
1 Alice alice@example.com true
2 Bob bob@example.com false
3 Charlie charlie@example.com true
"#;

    let doc = parse(ison_text).expect("Parse failed");

    match user_schema.validate(&doc) {
        Ok(users) => {
            println!("Validation passed! {} users found:", users.len());
            for user in users.iter() {
                println!(
                    "  - {} ({}): {}",
                    user.get_int("id").unwrap(),
                    user.get_string("name").unwrap(),
                    user.get_string("email").unwrap()
                );
            }
        }
        Err(e) => {
            println!("Validation failed:");
            for error in &e.errors {
                println!("  - {}: {}", error.field, error.message);
            }
        }
    }

    // Example 2: Validation with constraints
    println!("\n2. Validation with Constraints:");

    let product_schema = table("products")
        .field("id", int().required().positive())
        .field("name", string().required().min(1))
        .field("price", float().positive())
        .field("stock", int().min(0));

    let product_text = r#"
table.products
id name price stock
1 Widget 29.99 100
2 Gadget 49.99 50
3 Gizmo 19.99 200
"#;

    let product_doc = parse(product_text).expect("Parse failed");

    match product_schema.validate(&product_doc) {
        Ok(products) => {
            println!("Products validated: {} items", products.len());
            for product in products.iter() {
                let name = product.get_string("name").unwrap();
                let price = product.get("price")
                    .and_then(|v| v.as_float())
                    .unwrap_or(0.0);
                let stock = product.get_int("stock").unwrap_or(0);
                println!("  - {}: ${:.2} ({} in stock)", name, price, stock);
            }
        }
        Err(e) => {
            println!("Validation failed: {}", e);
        }
    }

    // Example 3: Validation error example
    println!("\n3. Validation Error Example:");

    let strict_schema = table("strict")
        .field("email", string().email().required());

    let invalid_text = r#"
table.strict
email
invalid-email
"#;

    let invalid_doc = parse(invalid_text).expect("Parse failed");

    match strict_schema.validate(&invalid_doc) {
        Ok(_) => println!("Unexpected: validation passed"),
        Err(e) => {
            println!("Expected validation error:");
            for error in &e.errors {
                println!("  - {}: {}", error.field, error.message);
            }
        }
    }

    println!("\n=== All examples completed ===");
}
