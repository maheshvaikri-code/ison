/**
 * @file example.cpp
 * @brief Example usage of ISON C++ Parser
 *
 * This example demonstrates:
 * - Parsing ISON from string
 * - Accessing blocks and rows
 * - Type checking and value extraction
 * - Working with references
 * - Serialization to ISON and JSON
 * - ISONL streaming format
 */

#include "ison_parser.hpp"
#include <iostream>

using namespace ison;

void example_basic_parsing() {
    std::cout << "=== Basic Parsing ===" << std::endl;

    // Parse a simple ISON document
    std::string ison_text = R"(
table.users
id:int name:string email active:bool
1 Alice alice@example.com true
2 Bob bob@example.com true
3 Charlie charlie@example.com false

table.orders
id:int user_id product price:float
101 :1 Widget 29.99
102 :1 Gadget 49.99
103 :2 Widget 29.99
)";

    auto doc = parse(ison_text);

    // Access blocks
    std::cout << "Document has " << doc.size() << " blocks" << std::endl;

    // Access users
    auto& users = doc["users"];
    std::cout << "\nUsers table has " << users.size() << " rows" << std::endl;

    for (const auto& row : users.rows) {
        int64_t id = as_int(row.at("id"));
        const std::string& name = as_string(row.at("name"));
        bool active = as_bool(row.at("active"));

        std::cout << "  User " << id << ": " << name
                  << " (active: " << (active ? "yes" : "no") << ")" << std::endl;
    }

    // Access orders with references
    auto& orders = doc["orders"];
    std::cout << "\nOrders table:" << std::endl;

    for (const auto& row : orders.rows) {
        int64_t id = as_int(row.at("id"));
        const auto& user_ref = as_reference(row.at("user_id"));
        const std::string& product = as_string(row.at("product"));
        double price = as_float(row.at("price"));

        std::cout << "  Order " << id << ": " << product
                  << " $" << price << " (user ref: " << user_ref.to_ison() << ")"
                  << std::endl;
    }
}

void example_type_annotations() {
    std::cout << "\n=== Type Annotations ===" << std::endl;

    std::string ison_text = R"(
table.products
id:int name:string price:float quantity:int total:computed
1 Widget 10.00 5 50.00
2 Gadget 25.00 3 75.00
)";

    auto doc = parse(ison_text);
    auto& products = doc["products"];

    // Check field types
    std::cout << "Field types:" << std::endl;
    for (const auto& fi : products.field_info) {
        std::cout << "  " << fi.name;
        if (fi.type.has_value()) {
            std::cout << " : " << fi.type.value();
        }
        if (fi.is_computed) {
            std::cout << " (computed)";
        }
        std::cout << std::endl;
    }

    // Get computed fields
    auto computed = products.get_computed_fields();
    std::cout << "\nComputed fields: ";
    for (const auto& f : computed) {
        std::cout << f << " ";
    }
    std::cout << std::endl;
}

void example_references() {
    std::cout << "\n=== References ===" << std::endl;

    std::string ison_text = R"(
table.relationships
id type_ref namespace_ref simple_ref
1 :MEMBER_OF:10 :user:101 :42
)";

    auto doc = parse(ison_text);
    auto& rel = doc["relationships"];

    // Relationship reference (uppercase type)
    auto& type_ref = as_reference(rel[0]["type_ref"]);
    std::cout << "Relationship ref: " << type_ref.to_ison() << std::endl;
    std::cout << "  Is relationship: " << (type_ref.is_relationship() ? "yes" : "no") << std::endl;
    std::cout << "  Type: " << type_ref.type.value() << std::endl;
    std::cout << "  ID: " << type_ref.id << std::endl;

    // Namespaced reference (lowercase type)
    auto& ns_ref = as_reference(rel[0]["namespace_ref"]);
    std::cout << "\nNamespace ref: " << ns_ref.to_ison() << std::endl;
    std::cout << "  Is relationship: " << (ns_ref.is_relationship() ? "yes" : "no") << std::endl;
    std::cout << "  Namespace: " << ns_ref.get_namespace().value_or("none") << std::endl;

    // Simple reference
    auto& simple_ref = as_reference(rel[0]["simple_ref"]);
    std::cout << "\nSimple ref: " << simple_ref.to_ison() << std::endl;
    std::cout << "  ID: " << simple_ref.id << std::endl;
}

void example_serialization() {
    std::cout << "\n=== Serialization ===" << std::endl;

    // Create a document programmatically
    Document doc;

    Block users("table", "users");
    users.fields = {"id", "name", "email"};
    users.field_info = {
        FieldInfo("id", "int"),
        FieldInfo("name", "string"),
        FieldInfo("email", "string")
    };

    Row row1;
    row1["id"] = int64_t(1);
    row1["name"] = std::string("Alice");
    row1["email"] = std::string("alice@example.com");
    users.rows.push_back(row1);

    Row row2;
    row2["id"] = int64_t(2);
    row2["name"] = std::string("Bob Smith");  // Will be quoted (has space)
    row2["email"] = std::string("bob@example.com");
    users.rows.push_back(row2);

    doc.blocks.push_back(users);

    // Serialize to ISON
    std::string ison_output = dumps(doc);
    std::cout << "ISON output:" << std::endl;
    std::cout << ison_output << std::endl;

    // Serialize to JSON
    std::cout << "\nJSON output:" << std::endl;
    std::cout << doc.to_json() << std::endl;
}

void example_isonl() {
    std::cout << "\n=== ISONL Streaming Format ===" << std::endl;

    // ISONL is useful for streaming large datasets
    std::string ison_text = R"(
table.events
id timestamp event
1 2024-01-01T10:00:00 login
2 2024-01-01T10:05:00 click
3 2024-01-01T10:10:00 logout
)";

    auto doc = parse(ison_text);

    // Convert to ISONL
    std::string isonl = dumps_isonl(doc);
    std::cout << "ISONL output (one record per line):" << std::endl;
    std::cout << isonl << std::endl;

    // Parse ISONL back
    std::cout << "\nParsed back from ISONL:" << std::endl;
    auto doc2 = loads_isonl(isonl);
    std::cout << "  Blocks: " << doc2.size() << std::endl;
    std::cout << "  Rows: " << doc2["events"].size() << std::endl;
}

void example_value_types() {
    std::cout << "\n=== Value Types ===" << std::endl;

    std::string ison_text = R"(
table.types
null_val bool_val int_val float_val string_val ref_val
~ true 42 3.14 hello :123
)";

    auto doc = parse(ison_text);
    auto& types = doc["types"];
    const auto& row = types[0];

    std::cout << "Type checks:" << std::endl;
    std::cout << "  null_val is null: " << (is_null(row.at("null_val")) ? "yes" : "no") << std::endl;
    std::cout << "  bool_val is bool: " << (is_bool(row.at("bool_val")) ? "yes" : "no") << std::endl;
    std::cout << "  int_val is int: " << (is_int(row.at("int_val")) ? "yes" : "no") << std::endl;
    std::cout << "  float_val is float: " << (is_float(row.at("float_val")) ? "yes" : "no") << std::endl;
    std::cout << "  string_val is string: " << (is_string(row.at("string_val")) ? "yes" : "no") << std::endl;
    std::cout << "  ref_val is reference: " << (is_reference(row.at("ref_val")) ? "yes" : "no") << std::endl;
}

int main() {
    std::cout << "ISON C++ Parser v" << ison::VERSION << " Examples" << std::endl;
    std::cout << "==========================================" << std::endl;

    try {
        example_basic_parsing();
        example_type_annotations();
        example_references();
        example_serialization();
        example_isonl();
        example_value_types();
    } catch (const ISONError& e) {
        std::cerr << "ISON Error: " << e.what() << std::endl;
        return 1;
    }

    std::cout << "\n=== All examples completed ===" << std::endl;
    return 0;
}
