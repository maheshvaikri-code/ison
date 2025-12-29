/**
 * @file test_ison_parser.cpp
 * @brief Tests for ISON C++ Parser
 *
 * Compile and run:
 *   g++ -std=c++17 -I../include test_ison_parser.cpp -o test_ison
 *   ./test_ison
 *
 * Or with CMake:
 *   mkdir build && cd build
 *   cmake .. && make
 *   ./test_ison_parser
 */

#include "ison_parser.hpp"
#include <iostream>
#include <cassert>
#include <cmath>

using namespace ison;

// Test counter
int tests_passed = 0;
int tests_failed = 0;

#define TEST(name) void test_##name()
#define RUN_TEST(name) do { \
    std::cout << "Running " << #name << "... "; \
    try { \
        test_##name(); \
        std::cout << "PASSED" << std::endl; \
        tests_passed++; \
    } catch (const std::exception& e) { \
        std::cout << "FAILED: " << e.what() << std::endl; \
        tests_failed++; \
    } \
} while(0)

#define ASSERT(cond) do { \
    if (!(cond)) throw std::runtime_error("Assertion failed: " #cond); \
} while(0)

#define ASSERT_EQ(a, b) do { \
    if ((a) != (b)) throw std::runtime_error("Assertion failed: " #a " == " #b); \
} while(0)

// =============================================================================
// Basic Parsing Tests
// =============================================================================

TEST(parse_simple_table) {
    std::string ison = R"(table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com)";

    auto doc = parse(ison);
    ASSERT_EQ(doc.size(), 1);

    auto& users = doc["users"];
    ASSERT_EQ(users.kind, "table");
    ASSERT_EQ(users.name, "users");
    ASSERT_EQ(users.size(), 2);
    ASSERT_EQ(users.fields.size(), 3);

    // Check first row
    ASSERT(is_int(users[0].at("id")));
    ASSERT_EQ(as_int(users[0].at("id")), 1);
    ASSERT_EQ(as_string(users[0].at("name")), "Alice");
    ASSERT_EQ(as_string(users[0].at("email")), "alice@example.com");
}

TEST(parse_object_block) {
    std::string ison = R"(object.config
name version debug
MyApp "1.0" true)";

    auto doc = parse(ison);
    auto& config = doc["config"];

    ASSERT_EQ(config.kind, "object");
    ASSERT_EQ(config.size(), 1);
    ASSERT_EQ(as_string(config[0].at("name")), "MyApp");
    ASSERT_EQ(as_string(config[0].at("version")), "1.0");
    ASSERT(is_bool(config[0].at("debug")));
    ASSERT_EQ(as_bool(config[0].at("debug")), true);
}

TEST(parse_multiple_blocks) {
    std::string ison = R"(table.users
id name
1 Alice
2 Bob

table.orders
id user_id product
101 :1 Widget
102 :2 Gadget)";

    auto doc = parse(ison);
    ASSERT_EQ(doc.size(), 2);
    ASSERT(doc.has("users"));
    ASSERT(doc.has("orders"));
}

// =============================================================================
// Type Inference Tests
// =============================================================================

TEST(type_inference_integer) {
    std::string ison = R"(table.test
value
42
-17
0)";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT(is_int(test[0].at("value")));
    ASSERT_EQ(as_int(test[0].at("value")), 42);
    ASSERT_EQ(as_int(test[1].at("value")), -17);
    ASSERT_EQ(as_int(test[2].at("value")), 0);
}

TEST(type_inference_float) {
    std::string ison = R"(table.test
value
3.14
-2.5
0.0)";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT(is_float(test[0].at("value")));
    ASSERT(std::abs(as_float(test[0].at("value")) - 3.14) < 0.001);
    ASSERT(std::abs(as_float(test[1].at("value")) - (-2.5)) < 0.001);
}

TEST(type_inference_boolean) {
    std::string ison = R"(table.test
active verified
true false)";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT(is_bool(test[0].at("active")));
    ASSERT_EQ(as_bool(test[0].at("active")), true);
    ASSERT_EQ(as_bool(test[0].at("verified")), false);
}

TEST(type_inference_null) {
    std::string ison = R"(table.test
value1 value2
null ~)";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT(is_null(test[0].at("value1")));
    ASSERT(is_null(test[0].at("value2")));
}

TEST(type_inference_string) {
    std::string ison = R"(table.test
name
hello
"quoted string"
"with spaces")";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT(is_string(test[0].at("name")));
    ASSERT_EQ(as_string(test[0].at("name")), "hello");
    ASSERT_EQ(as_string(test[1].at("name")), "quoted string");
    ASSERT_EQ(as_string(test[2].at("name")), "with spaces");
}

// =============================================================================
// Reference Tests
// =============================================================================

TEST(parse_simple_reference) {
    std::string ison = R"(table.orders
id user_id
1 :42)";

    auto doc = parse(ison);
    auto& orders = doc["orders"];

    ASSERT(is_reference(orders[0].at("user_id")));
    const Reference& ref = as_reference(orders[0].at("user_id"));
    ASSERT_EQ(ref.id, "42");
    ASSERT(!ref.type.has_value());
}

TEST(parse_namespaced_reference) {
    std::string ison = R"(table.orders
id user
1 :user:101)";

    auto doc = parse(ison);
    auto& orders = doc["orders"];

    ASSERT(is_reference(orders[0].at("user")));
    const Reference& ref = as_reference(orders[0].at("user"));
    ASSERT_EQ(ref.id, "101");
    ASSERT_EQ(ref.type.value(), "user");
    ASSERT(!ref.is_relationship());
}

TEST(parse_relationship_reference) {
    std::string ison = R"(table.memberships
id relationship
1 :MEMBER_OF:10)";

    auto doc = parse(ison);
    auto& memberships = doc["memberships"];

    const Reference& ref = as_reference(memberships[0].at("relationship"));
    ASSERT_EQ(ref.id, "10");
    ASSERT_EQ(ref.type.value(), "MEMBER_OF");
    ASSERT(ref.is_relationship());
}

// =============================================================================
// Field Type Annotation Tests
// =============================================================================

TEST(parse_typed_fields) {
    std::string ison = R"(table.products
id:int name:string price:float active:bool
1 Widget 29.99 true)";

    auto doc = parse(ison);
    auto& products = doc["products"];

    ASSERT_EQ(products.field_info[0].type.value(), "int");
    ASSERT_EQ(products.field_info[1].type.value(), "string");
    ASSERT_EQ(products.field_info[2].type.value(), "float");
    ASSERT_EQ(products.field_info[3].type.value(), "bool");

    ASSERT_EQ(products.get_field_type("id").value(), "int");
    ASSERT_EQ(products.get_field_type("name").value(), "string");
}

TEST(parse_computed_field) {
    std::string ison = R"(table.cart
id quantity price total:computed
1 2 10.00 20.00)";

    auto doc = parse(ison);
    auto& cart = doc["cart"];

    ASSERT(cart.field_info[3].is_computed);
    auto computed = cart.get_computed_fields();
    ASSERT_EQ(computed.size(), 1);
    ASSERT_EQ(computed[0], "total");
}

// =============================================================================
// Escape Sequence Tests
// =============================================================================

TEST(parse_escape_sequences) {
    std::string ison = R"(table.test
content
"line1\nline2"
"tab\there"
"quote\"inside")";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT_EQ(as_string(test[0].at("content")), "line1\nline2");
    ASSERT_EQ(as_string(test[1].at("content")), "tab\there");
    ASSERT_EQ(as_string(test[2].at("content")), "quote\"inside");
}

// =============================================================================
// Comments Tests
// =============================================================================

TEST(parse_with_comments) {
    std::string ison = R"(# This is a comment
table.users
# Field definitions
id name
# First user
1 Alice
# Second user
2 Bob)";

    auto doc = parse(ison);
    auto& users = doc["users"];
    ASSERT_EQ(users.size(), 2);
}

// =============================================================================
// Summary Row Tests
// =============================================================================

TEST(parse_summary_row) {
    std::string ison = R"(table.sales
region amount
North 1000
South 2000
---
Total 3000)";

    auto doc = parse(ison);
    auto& sales = doc["sales"];

    ASSERT_EQ(sales.size(), 2);  // Only data rows, not summary
    ASSERT(sales.summary.has_value());
    ASSERT_EQ(sales.summary.value(), "Total 3000");
}

// =============================================================================
// Serialization Tests
// =============================================================================

TEST(serialize_roundtrip) {
    std::string original = R"(table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com)";

    auto doc = parse(original);
    std::string serialized = dumps(doc);
    auto doc2 = parse(serialized);

    ASSERT_EQ(doc2["users"].size(), 2);
    ASSERT_EQ(as_string(doc2["users"][0].at("name")), "Alice");
}

TEST(serialize_with_quotes) {
    auto doc = Document();
    Block block("table", "test");
    block.fields = {"name"};
    block.field_info.push_back(FieldInfo("name"));

    Row row;
    row["name"] = std::string("hello world");  // Should be quoted
    block.rows.push_back(row);

    doc.blocks.push_back(block);

    std::string serialized = dumps(doc);
    ASSERT(serialized.find("\"hello world\"") != std::string::npos);
}

// =============================================================================
// ISONL Tests
// =============================================================================

TEST(parse_isonl) {
    std::string isonl = R"(table.users|id name email|1 Alice alice@example.com
table.users|id name email|2 Bob bob@example.com)";

    auto doc = loads_isonl(isonl);
    ASSERT_EQ(doc.size(), 1);
    ASSERT_EQ(doc["users"].size(), 2);
}

TEST(serialize_isonl) {
    std::string ison = R"(table.users
id name
1 Alice
2 Bob)";

    auto doc = parse(ison);
    std::string isonl = dumps_isonl(doc);

    ASSERT(isonl.find("table.users|") != std::string::npos);
    ASSERT(isonl.find("|1 Alice") != std::string::npos);
}

TEST(ison_to_isonl_conversion) {
    std::string ison = R"(table.test
id value
1 hello
2 world)";

    std::string isonl = ison_to_isonl(ison);
    std::string back_to_ison = isonl_to_ison(isonl);

    auto doc1 = parse(ison);
    auto doc2 = parse(back_to_ison);

    ASSERT_EQ(doc1["test"].size(), doc2["test"].size());
}

// =============================================================================
// JSON Conversion Tests
// =============================================================================

TEST(to_json) {
    std::string ison = R"(table.users
id name active
1 Alice true
2 Bob false)";

    auto doc = parse(ison);
    std::string json = doc.to_json();

    ASSERT(json.find("\"users\"") != std::string::npos);
    ASSERT(json.find("\"Alice\"") != std::string::npos);
    ASSERT(json.find("true") != std::string::npos);
}

// =============================================================================
// Reference Class Tests
// =============================================================================

TEST(reference_to_ison) {
    Reference simple("42");
    ASSERT_EQ(simple.to_ison(), ":42");

    Reference namespaced("101", "user");
    ASSERT_EQ(namespaced.to_ison(), ":user:101");

    Reference relationship("10", "MEMBER_OF");
    ASSERT_EQ(relationship.to_ison(), ":MEMBER_OF:10");
    ASSERT(relationship.is_relationship());
}

// =============================================================================
// Error Handling Tests
// =============================================================================

TEST(error_invalid_header) {
    std::string ison = R"(invalid_header
id name
1 Alice)";

    try {
        parse(ison);
        ASSERT(false);  // Should have thrown
    } catch (const ISONSyntaxError& e) {
        ASSERT(std::string(e.what()).find("Invalid block header") != std::string::npos);
    }
}

TEST(error_missing_fields) {
    std::string ison = R"(table.users)";  // No field definitions

    try {
        parse(ison);
        ASSERT(false);
    } catch (const ISONSyntaxError& e) {
        ASSERT(std::string(e.what()).find("missing field definitions") != std::string::npos);
    }
}

TEST(error_unterminated_string) {
    std::string ison = R"(table.test
name
"unterminated)";

    try {
        parse(ison);
        ASSERT(false);
    } catch (const ISONSyntaxError& e) {
        ASSERT(std::string(e.what()).find("Unterminated") != std::string::npos);
    }
}

// =============================================================================
// Edge Cases
// =============================================================================

TEST(empty_document) {
    std::string ison = "";
    auto doc = parse(ison);
    ASSERT_EQ(doc.size(), 0);
}

TEST(only_comments) {
    std::string ison = R"(# Comment 1
# Comment 2
# Comment 3)";
    auto doc = parse(ison);
    ASSERT_EQ(doc.size(), 0);
}

TEST(empty_table) {
    std::string ison = R"(table.empty
id name)";  // No data rows

    auto doc = parse(ison);
    auto& empty = doc["empty"];
    ASSERT_EQ(empty.size(), 0);
    ASSERT_EQ(empty.fields.size(), 2);
}

TEST(special_characters_in_values) {
    std::string ison = R"(table.test
content
"hello\tworld"
"line1\nline2"
"path\\to\\file")";

    auto doc = parse(ison);
    auto& test = doc["test"];

    ASSERT_EQ(as_string(test[0].at("content")), "hello\tworld");
    ASSERT_EQ(as_string(test[1].at("content")), "line1\nline2");
    ASSERT_EQ(as_string(test[2].at("content")), "path\\to\\file");
}

// =============================================================================
// Main
// =============================================================================

int main() {
    std::cout << "=== ISON C++ Parser Tests ===" << std::endl;
    std::cout << "Version: " << ison::VERSION << std::endl;
    std::cout << std::endl;

    // Basic parsing
    RUN_TEST(parse_simple_table);
    RUN_TEST(parse_object_block);
    RUN_TEST(parse_multiple_blocks);

    // Type inference
    RUN_TEST(type_inference_integer);
    RUN_TEST(type_inference_float);
    RUN_TEST(type_inference_boolean);
    RUN_TEST(type_inference_null);
    RUN_TEST(type_inference_string);

    // References
    RUN_TEST(parse_simple_reference);
    RUN_TEST(parse_namespaced_reference);
    RUN_TEST(parse_relationship_reference);

    // Field types
    RUN_TEST(parse_typed_fields);
    RUN_TEST(parse_computed_field);

    // Escape sequences
    RUN_TEST(parse_escape_sequences);

    // Comments
    RUN_TEST(parse_with_comments);

    // Summary
    RUN_TEST(parse_summary_row);

    // Serialization
    RUN_TEST(serialize_roundtrip);
    RUN_TEST(serialize_with_quotes);

    // ISONL
    RUN_TEST(parse_isonl);
    RUN_TEST(serialize_isonl);
    RUN_TEST(ison_to_isonl_conversion);

    // JSON
    RUN_TEST(to_json);

    // Reference class
    RUN_TEST(reference_to_ison);

    // Error handling
    RUN_TEST(error_invalid_header);
    RUN_TEST(error_missing_fields);
    RUN_TEST(error_unterminated_string);

    // Edge cases
    RUN_TEST(empty_document);
    RUN_TEST(only_comments);
    RUN_TEST(empty_table);
    RUN_TEST(special_characters_in_values);

    std::cout << std::endl;
    std::cout << "=== Results ===" << std::endl;
    std::cout << "Passed: " << tests_passed << std::endl;
    std::cout << "Failed: " << tests_failed << std::endl;

    return tests_failed > 0 ? 1 : 0;
}
