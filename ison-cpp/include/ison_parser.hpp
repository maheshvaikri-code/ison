/**
 * @file ison_parser.hpp
 * @brief ISON v1.0 Reference Parser for C++ (C++11 compatible)
 *
 * Interchange Simple Object Notation (ISON)
 * A minimal, LLM-friendly data serialization format optimized for
 * graph databases, multi-agent systems, and RAG pipelines.
 *
 * Compatibility: C++11 and later (auto-detects C++17 for std::optional)
 *
 * @author Mahesh Vaikri
 * @version 1.0.1
 */

#ifndef ISON_PARSER_HPP
#define ISON_PARSER_HPP

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <stdexcept>
#include <sstream>
#include <fstream>
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cmath>

// C++17 detection
#if __cplusplus >= 201703L
    #define ISON_HAS_CPP17 1
    #include <optional>
#else
    #define ISON_HAS_CPP17 0
#endif

namespace ison {

// Version info
static const char* VERSION = "1.0.1";

// =============================================================================
// Optional implementation for C++11/14
// =============================================================================

#if ISON_HAS_CPP17
    template<typename T>
    using Optional = std::optional<T>;
    static const std::nullopt_t None = std::nullopt;
#else
    // Simple optional implementation for C++11
    template<typename T>
    class Optional {
    public:
        Optional() : has_value_(false) {}
        Optional(const T& value) : has_value_(true), value_(value) {}
        Optional(T&& value) : has_value_(true), value_(std::move(value)) {}

        bool has_value() const { return has_value_; }
        explicit operator bool() const { return has_value_; }

        T& value() {
            if (!has_value_) throw std::runtime_error("Optional has no value");
            return value_;
        }
        const T& value() const {
            if (!has_value_) throw std::runtime_error("Optional has no value");
            return value_;
        }

        T value_or(const T& default_val) const {
            return has_value_ ? value_ : default_val;
        }

        void reset() { has_value_ = false; }

    private:
        bool has_value_;
        T value_;
    };

    struct NoneType {};
    static const NoneType None = NoneType();
#endif

// =============================================================================
// Value Type (tagged union for C++11 compatibility)
// =============================================================================

// Forward declarations
class Reference;
class Value;

/**
 * @brief Value type enumeration
 */
enum class ValueType {
    Null,
    Bool,
    Int,
    Float,
    String,
    Reference
};

/**
 * @brief Represents any ISON value using tagged union
 */
class Value {
public:
    Value() : type_(ValueType::Null) {}

    // Constructors for each type
    Value(std::nullptr_t) : type_(ValueType::Null) {}

    Value(bool b) : type_(ValueType::Bool) { data_.bool_val = b; }

    Value(int i) : type_(ValueType::Int) { data_.int_val = static_cast<int64_t>(i); }
    Value(long i) : type_(ValueType::Int) { data_.int_val = static_cast<int64_t>(i); }
    Value(long long i) : type_(ValueType::Int) { data_.int_val = static_cast<int64_t>(i); }

    Value(float f) : type_(ValueType::Float) { data_.float_val = static_cast<double>(f); }
    Value(double f) : type_(ValueType::Float) { data_.float_val = f; }

    Value(const char* s) : type_(ValueType::String), str_val_(s) {}
    Value(const std::string& s) : type_(ValueType::String), str_val_(s) {}
    Value(std::string&& s) : type_(ValueType::String), str_val_(std::move(s)) {}

    Value(const std::shared_ptr<Reference>& r) : type_(ValueType::Reference), ref_val_(r) {}
    Value(std::shared_ptr<Reference>&& r) : type_(ValueType::Reference), ref_val_(std::move(r)) {}

    // Copy and move
    Value(const Value& other) : type_(other.type_), data_(other.data_),
                                 str_val_(other.str_val_), ref_val_(other.ref_val_) {}

    Value(Value&& other) : type_(other.type_), data_(other.data_),
                           str_val_(std::move(other.str_val_)),
                           ref_val_(std::move(other.ref_val_)) {}

    Value& operator=(const Value& other) {
        if (this != &other) {
            type_ = other.type_;
            data_ = other.data_;
            str_val_ = other.str_val_;
            ref_val_ = other.ref_val_;
        }
        return *this;
    }

    Value& operator=(Value&& other) {
        if (this != &other) {
            type_ = other.type_;
            data_ = other.data_;
            str_val_ = std::move(other.str_val_);
            ref_val_ = std::move(other.ref_val_);
        }
        return *this;
    }

    // Type checking
    ValueType type() const { return type_; }
    bool is_null() const { return type_ == ValueType::Null; }
    bool is_bool() const { return type_ == ValueType::Bool; }
    bool is_int() const { return type_ == ValueType::Int; }
    bool is_float() const { return type_ == ValueType::Float; }
    bool is_string() const { return type_ == ValueType::String; }
    bool is_reference() const { return type_ == ValueType::Reference; }

    // Value access (throws if wrong type)
    bool as_bool() const {
        if (type_ != ValueType::Bool) throw std::runtime_error("Value is not a bool");
        return data_.bool_val;
    }

    int64_t as_int() const {
        if (type_ != ValueType::Int) throw std::runtime_error("Value is not an int");
        return data_.int_val;
    }

    double as_float() const {
        if (type_ != ValueType::Float) throw std::runtime_error("Value is not a float");
        return data_.float_val;
    }

    const std::string& as_string() const {
        if (type_ != ValueType::String) throw std::runtime_error("Value is not a string");
        return str_val_;
    }

    const std::shared_ptr<Reference>& as_reference_ptr() const {
        if (type_ != ValueType::Reference) throw std::runtime_error("Value is not a reference");
        return ref_val_;
    }

private:
    ValueType type_;
    union Data {
        bool bool_val;
        int64_t int_val;
        double float_val;
        Data() : int_val(0) {}
    } data_;
    std::string str_val_;
    std::shared_ptr<Reference> ref_val_;
};

// =============================================================================
// Exceptions
// =============================================================================

class ISONError : public std::runtime_error {
public:
    explicit ISONError(const std::string& message) : std::runtime_error(message) {}
};

class ISONSyntaxError : public ISONError {
public:
    int line;
    int col;

    ISONSyntaxError(const std::string& message, int line = 0, int col = 0)
        : ISONError("Line " + std::to_string(line) + ", Col " + std::to_string(col) + ": " + message),
          line(line), col(col) {}
};

class ISONTypeError : public ISONError {
public:
    explicit ISONTypeError(const std::string& message) : ISONError(message) {}
};

// =============================================================================
// Reference Class
// =============================================================================

/**
 * @brief Represents a reference to another record
 *
 * Syntax variants:
 *   :10              - Simple reference (id only)
 *   :user:101        - Namespaced reference (type:id)
 *   :MEMBER_OF:10    - Relationship-typed reference
 */
class Reference {
public:
    std::string id;
    Optional<std::string> type;

    Reference() {}
    explicit Reference(const std::string& id) : id(id) {}
    Reference(const std::string& id, const std::string& type) : id(id), type(type) {}

    std::string to_ison() const {
        if (type.has_value()) {
            return ":" + type.value() + ":" + id;
        }
        return ":" + id;
    }

    bool is_relationship() const {
        if (!type.has_value()) return false;
        const std::string& t = type.value();
        for (size_t i = 0; i < t.size(); ++i) {
            if (!std::isupper(static_cast<unsigned char>(t[i])) && t[i] != '_') {
                return false;
            }
        }
        return !t.empty();
    }

    Optional<std::string> relationship_type() const {
        if (is_relationship()) return type;
        return Optional<std::string>();
    }

    Optional<std::string> get_namespace() const {
        if (type.has_value() && !is_relationship()) return type;
        return Optional<std::string>();
    }
};

// Reference accessor for Value
inline const Reference& as_reference(const Value& v) {
    auto ptr = v.as_reference_ptr();
    if (!ptr) throw ISONTypeError("Reference is null");
    return *ptr;
}

// =============================================================================
// FieldInfo Class
// =============================================================================

class FieldInfo {
public:
    std::string name;
    Optional<std::string> type;
    bool is_computed;

    FieldInfo() : is_computed(false) {}
    explicit FieldInfo(const std::string& name) : name(name), is_computed(false) {}
    FieldInfo(const std::string& name, const std::string& type)
        : name(name), type(type), is_computed(type == "computed") {}

    static FieldInfo parse(const std::string& field_str) {
        size_t colon_pos = field_str.find(':');
        if (colon_pos != std::string::npos) {
            std::string name = field_str.substr(0, colon_pos);
            std::string type_hint = field_str.substr(colon_pos + 1);
            // Convert to lowercase
            for (size_t i = 0; i < type_hint.size(); ++i) {
                type_hint[i] = static_cast<char>(std::tolower(static_cast<unsigned char>(type_hint[i])));
            }
            return FieldInfo(name, type_hint);
        }
        return FieldInfo(field_str);
    }
};

// =============================================================================
// Row Type
// =============================================================================

typedef std::map<std::string, Value> Row;

// =============================================================================
// Block Class
// =============================================================================

class Block {
public:
    std::string kind;
    std::string name;
    std::vector<std::string> fields;
    std::vector<Row> rows;
    std::vector<FieldInfo> field_info;
    Optional<std::string> summary;

    Block() {}
    Block(const std::string& kind, const std::string& name) : kind(kind), name(name) {}

    Optional<std::string> get_field_type(const std::string& field_name) const {
        for (size_t i = 0; i < field_info.size(); ++i) {
            if (field_info[i].name == field_name) {
                return field_info[i].type;
            }
        }
        return Optional<std::string>();
    }

    std::vector<std::string> get_computed_fields() const {
        std::vector<std::string> result;
        for (size_t i = 0; i < field_info.size(); ++i) {
            if (field_info[i].is_computed) {
                result.push_back(field_info[i].name);
            }
        }
        return result;
    }

    size_t size() const { return rows.size(); }
    Row& operator[](size_t index) { return rows[index]; }
    const Row& operator[](size_t index) const { return rows[index]; }
};

// =============================================================================
// Document Class
// =============================================================================

class Document {
public:
    std::vector<Block> blocks;

    Document() {}

    Block* get(const std::string& name) {
        for (size_t i = 0; i < blocks.size(); ++i) {
            if (blocks[i].name == name) return &blocks[i];
        }
        return NULL;
    }

    const Block* get(const std::string& name) const {
        for (size_t i = 0; i < blocks.size(); ++i) {
            if (blocks[i].name == name) return &blocks[i];
        }
        return NULL;
    }

    Block& operator[](const std::string& name) {
        Block* b = get(name);
        if (!b) throw ISONError("Block not found: " + name);
        return *b;
    }

    const Block& operator[](const std::string& name) const {
        const Block* b = get(name);
        if (!b) throw ISONError("Block not found: " + name);
        return *b;
    }

    bool has(const std::string& name) const { return get(name) != NULL; }
    size_t size() const { return blocks.size(); }

    std::string to_json(int indent = 2) const;
};

// =============================================================================
// Tokenizer
// =============================================================================

class Tokenizer {
public:
    Tokenizer(const std::string& line, int line_num = 0)
        : line_(line), line_num_(line_num), pos_(0) {}

    std::vector<std::string> tokenize() {
        std::vector<std::string> tokens;
        pos_ = 0;

        while (pos_ < line_.size()) {
            skip_whitespace();
            if (pos_ >= line_.size()) break;

            if (line_[pos_] == '"') {
                tokens.push_back(read_quoted_string());
            } else {
                tokens.push_back(read_unquoted_token());
            }
        }
        return tokens;
    }

private:
    std::string line_;
    int line_num_;
    size_t pos_;

    void skip_whitespace() {
        while (pos_ < line_.size() && (line_[pos_] == ' ' || line_[pos_] == '\t')) {
            ++pos_;
        }
    }

    std::string read_quoted_string() {
        size_t start_pos = pos_;
        ++pos_;
        std::string result;

        while (pos_ < line_.size()) {
            char c = line_[pos_];

            if (c == '"') {
                ++pos_;
                return result;
            }

            if (c == '\\') {
                ++pos_;
                if (pos_ >= line_.size()) {
                    throw ISONSyntaxError("Unexpected end of line after backslash", line_num_, static_cast<int>(pos_));
                }
                char escape_char = line_[pos_];
                switch (escape_char) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case 'n': result += '\n'; break;
                    case 't': result += '\t'; break;
                    case 'r': result += '\r'; break;
                    default: result += escape_char; break;
                }
            } else {
                result += c;
            }
            ++pos_;
        }
        throw ISONSyntaxError("Unterminated quoted string", line_num_, static_cast<int>(start_pos));
    }

    std::string read_unquoted_token() {
        size_t start = pos_;
        while (pos_ < line_.size() && line_[pos_] != ' ' && line_[pos_] != '\t') {
            ++pos_;
        }
        return line_.substr(start, pos_ - start);
    }
};

// =============================================================================
// Type Inferrer
// =============================================================================

class TypeInferrer {
public:
    static Value infer(const std::string& token, bool was_quoted = false) {
        if (was_quoted) {
            return Value(token);
        }

        if (token == "true") return Value(true);
        if (token == "false") return Value(false);
        if (token == "null" || token == "~") return Value(nullptr);

        if (is_integer(token)) {
            return Value(static_cast<int64_t>(std::stoll(token)));
        }

        if (is_float(token)) {
            return Value(std::stod(token));
        }

        if (token.size() > 1 && token[0] == ':') {
            std::string ref_value = token.substr(1);
            size_t colon_pos = ref_value.find(':');
            if (colon_pos != std::string::npos) {
                std::string type = ref_value.substr(0, colon_pos);
                std::string id = ref_value.substr(colon_pos + 1);
                return Value(std::make_shared<Reference>(id, type));
            }
            return Value(std::make_shared<Reference>(ref_value));
        }

        return Value(token);
    }

private:
    static bool is_integer(const std::string& s) {
        if (s.empty()) return false;
        size_t start = (s[0] == '-') ? 1 : 0;
        if (start == s.size()) return false;
        for (size_t i = start; i < s.size(); ++i) {
            if (!std::isdigit(static_cast<unsigned char>(s[i]))) return false;
        }
        return true;
    }

    static bool is_float(const std::string& s) {
        if (s.empty()) return false;
        size_t start = (s[0] == '-') ? 1 : 0;
        bool has_dot = false;
        bool has_digit = false;
        for (size_t i = start; i < s.size(); ++i) {
            if (s[i] == '.') {
                if (has_dot) return false;
                has_dot = true;
            } else if (std::isdigit(static_cast<unsigned char>(s[i]))) {
                has_digit = true;
            } else {
                return false;
            }
        }
        return has_dot && has_digit;
    }
};

// =============================================================================
// Parser
// =============================================================================

class Parser {
public:
    explicit Parser(const std::string& text) : line_num_(0) {
        std::istringstream stream(text);
        std::string line;
        while (std::getline(stream, line)) {
            lines_.push_back(line);
        }
    }

    Document parse() {
        Document doc;
        while (line_num_ < lines_.size()) {
            skip_empty_and_comments();
            if (line_num_ >= lines_.size()) break;

            Block block = parse_block();
            doc.blocks.push_back(block);
        }
        return doc;
    }

private:
    std::vector<std::string> lines_;
    size_t line_num_;

    std::string current_line() const {
        return (line_num_ < lines_.size()) ? lines_[line_num_] : "";
    }

    static std::string trim(const std::string& s) {
        size_t start = s.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return "";
        size_t end = s.find_last_not_of(" \t\r\n");
        return s.substr(start, end - start + 1);
    }

    void skip_empty_and_comments() {
        while (line_num_ < lines_.size()) {
            std::string line = trim(current_line());
            if (line.empty() || line[0] == '#') {
                ++line_num_;
            } else {
                break;
            }
        }
    }

    Block parse_block() {
        std::string header_line = trim(current_line());
        size_t dot_pos = header_line.find('.');
        if (dot_pos == std::string::npos) {
            throw ISONSyntaxError("Invalid block header: '" + header_line + "'", static_cast<int>(line_num_ + 1), 0);
        }

        std::string kind = header_line.substr(0, dot_pos);
        std::string name = header_line.substr(dot_pos + 1);
        ++line_num_;

        skip_empty_and_comments();
        if (line_num_ >= lines_.size()) {
            throw ISONSyntaxError("Block '" + kind + "." + name + "' missing field definitions", static_cast<int>(line_num_ + 1), 0);
        }

        std::string fields_line = current_line();
        Tokenizer tokenizer(fields_line, static_cast<int>(line_num_ + 1));
        std::vector<std::string> raw_fields = tokenizer.tokenize();
        ++line_num_;

        Block block(kind, name);
        for (size_t i = 0; i < raw_fields.size(); ++i) {
            FieldInfo fi = FieldInfo::parse(raw_fields[i]);
            block.field_info.push_back(fi);
            block.fields.push_back(fi.name);
        }

        while (line_num_ < lines_.size()) {
            std::string line = current_line();
            std::string stripped = trim(line);

            if (stripped.empty()) break;
            if (stripped[0] == '#') { ++line_num_; continue; }

            if (stripped.size() >= 3 && stripped.substr(0, 3) == "---") {
                ++line_num_;
                while (line_num_ < lines_.size()) {
                    std::string summary_line = trim(current_line());
                    if (!summary_line.empty() && summary_line[0] != '#') {
                        block.summary = summary_line;
                        ++line_num_;
                        break;
                    } else if (summary_line.empty()) {
                        break;
                    }
                    ++line_num_;
                }
                continue;
            }

            if (looks_like_header(stripped)) break;

            Row row = parse_data_row(block.fields, line);
            block.rows.push_back(row);
            ++line_num_;
        }

        return block;
    }

    bool looks_like_header(const std::string& line) const {
        size_t dot_pos = line.find('.');
        if (dot_pos == std::string::npos) return false;
        if (line.find(' ') != std::string::npos) return false;

        std::string kind = line.substr(0, dot_pos);
        std::string name = line.substr(dot_pos + 1);
        return is_valid_id(kind) && is_valid_id(name);
    }

    static bool is_valid_id(const std::string& s) {
        if (s.empty()) return false;
        if (!std::isalpha(static_cast<unsigned char>(s[0])) && s[0] != '_') return false;
        for (size_t i = 0; i < s.size(); ++i) {
            char c = s[i];
            if (!std::isalnum(static_cast<unsigned char>(c)) && c != '_' && c != '-') return false;
        }
        return true;
    }

    Row parse_data_row(const std::vector<std::string>& fields, const std::string& line) {
        Tokenizer tokenizer(line, static_cast<int>(line_num_ + 1));
        std::vector<std::string> raw_tokens = tokenizer.tokenize();

        std::vector<Value> values;
        size_t pos = 0;

        for (size_t i = 0; i < raw_tokens.size(); ++i) {
            while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t')) {
                ++pos;
            }
            bool was_quoted = pos < line.size() && line[pos] == '"';
            values.push_back(TypeInferrer::infer(raw_tokens[i], was_quoted));

            if (was_quoted) {
                ++pos;
                while (pos < line.size() && line[pos] != '"') {
                    if (line[pos] == '\\') ++pos;
                    ++pos;
                }
                if (pos < line.size()) ++pos;
            } else {
                pos += raw_tokens[i].size();
            }
        }

        Row row;
        for (size_t i = 0; i < fields.size(); ++i) {
            if (i < values.size()) {
                row[fields[i]] = values[i];
            } else {
                row[fields[i]] = Value(nullptr);
            }
        }
        return row;
    }
};

// =============================================================================
// Serializer
// =============================================================================

class Serializer {
public:
    static std::string dumps(const Document& doc, bool align_columns = true) {
        std::string result;
        for (size_t i = 0; i < doc.blocks.size(); ++i) {
            if (i > 0) result += "\n\n";
            result += serialize_block(doc.blocks[i], align_columns);
        }
        return result;
    }

private:
    static std::string serialize_block(const Block& block, bool align_columns) {
        std::vector<std::string> lines;
        lines.push_back(block.kind + "." + block.name);

        std::string fields_line;
        for (size_t i = 0; i < block.field_info.size(); ++i) {
            if (i > 0) fields_line += " ";
            const FieldInfo& fi = block.field_info[i];
            if (fi.type.has_value()) {
                fields_line += fi.name + ":" + fi.type.value();
            } else {
                fields_line += fi.name;
            }
        }
        if (fields_line.empty() && !block.fields.empty()) {
            for (size_t i = 0; i < block.fields.size(); ++i) {
                if (i > 0) fields_line += " ";
                fields_line += block.fields[i];
            }
        }
        lines.push_back(fields_line);

        std::vector<size_t> col_widths;
        if (align_columns && !block.rows.empty()) {
            col_widths = calculate_column_widths(block);
        }

        for (size_t ri = 0; ri < block.rows.size(); ++ri) {
            const Row& row = block.rows[ri];
            std::string row_line;
            for (size_t i = 0; i < block.fields.size(); ++i) {
                if (i > 0) row_line += " ";

                std::string str_value = "null";
                Row::const_iterator it = row.find(block.fields[i]);
                if (it != row.end()) {
                    str_value = value_to_ison(it->second);
                }

                if (!col_widths.empty() && i < col_widths.size()) {
                    while (str_value.size() < col_widths[i]) {
                        str_value += " ";
                    }
                }
                row_line += str_value;
            }
            // Trim trailing whitespace
            while (!row_line.empty() && (row_line[row_line.size()-1] == ' ' || row_line[row_line.size()-1] == '\t')) {
                row_line.erase(row_line.size()-1);
            }
            lines.push_back(row_line);
        }

        if (block.summary.has_value()) {
            lines.push_back("---");
            lines.push_back(block.summary.value());
        }

        std::string result;
        for (size_t i = 0; i < lines.size(); ++i) {
            if (i > 0) result += "\n";
            result += lines[i];
        }
        return result;
    }

    static std::vector<size_t> calculate_column_widths(const Block& block) {
        std::vector<size_t> widths(block.fields.size());
        for (size_t i = 0; i < block.fields.size(); ++i) {
            widths[i] = block.fields[i].size();
        }

        for (size_t ri = 0; ri < block.rows.size(); ++ri) {
            const Row& row = block.rows[ri];
            for (size_t i = 0; i < block.fields.size(); ++i) {
                Row::const_iterator it = row.find(block.fields[i]);
                if (it != row.end()) {
                    std::string str_value = value_to_ison(it->second);
                    if (str_value.size() > widths[i]) {
                        widths[i] = str_value.size();
                    }
                }
            }
        }
        return widths;
    }

    static std::string value_to_ison(const Value& v) {
        switch (v.type()) {
            case ValueType::Null: return "null";
            case ValueType::Bool: return v.as_bool() ? "true" : "false";
            case ValueType::Int: return std::to_string(v.as_int());
            case ValueType::Float: {
                std::ostringstream oss;
                oss << v.as_float();
                return oss.str();
            }
            case ValueType::String: return quote_if_needed(v.as_string());
            case ValueType::Reference: {
                std::shared_ptr<Reference> r = v.as_reference_ptr();
                return r ? r->to_ison() : "null";
            }
        }
        return "null";
    }

    static std::string quote_if_needed(const std::string& s) {
        if (s.empty()) return "\"\"";

        bool needs_quote = (s == "true" || s == "false" || s == "null" || s[0] == ':');

        if (!needs_quote) {
            for (size_t i = 0; i < s.size(); ++i) {
                char c = s[i];
                if (c == ' ' || c == '\t' || c == '"' || c == '\n' || c == '\r') {
                    needs_quote = true;
                    break;
                }
            }
        }

        if (!needs_quote && looks_like_number(s)) {
            needs_quote = true;
        }

        if (needs_quote) {
            std::string escaped;
            for (size_t i = 0; i < s.size(); ++i) {
                char c = s[i];
                switch (c) {
                    case '\\': escaped += "\\\\"; break;
                    case '"':  escaped += "\\\""; break;
                    case '\n': escaped += "\\n"; break;
                    case '\t': escaped += "\\t"; break;
                    case '\r': escaped += "\\r"; break;
                    default:   escaped += c; break;
                }
            }
            return "\"" + escaped + "\"";
        }
        return s;
    }

    static bool looks_like_number(const std::string& s) {
        if (s.empty()) return false;
        size_t start = (s[0] == '-') ? 1 : 0;
        if (start == s.size()) return false;
        for (size_t i = start; i < s.size(); ++i) {
            if (s[i] != '.' && !std::isdigit(static_cast<unsigned char>(s[i]))) {
                return false;
            }
        }
        return true;
    }
};

// =============================================================================
// JSON Output
// =============================================================================

inline std::string Document::to_json(int indent) const {
    std::string ind(static_cast<size_t>(indent), ' ');
    std::ostringstream oss;

    oss << "{\n";
    for (size_t bi = 0; bi < blocks.size(); ++bi) {
        const Block& block = blocks[bi];
        oss << ind << "\"" << block.name << "\": [\n";

        for (size_t ri = 0; ri < block.rows.size(); ++ri) {
            const Row& row = block.rows[ri];
            oss << ind << ind << "{\n";

            size_t fi = 0;
            for (Row::const_iterator it = row.begin(); it != row.end(); ++it, ++fi) {
                oss << ind << ind << ind << "\"" << it->first << "\": ";

                const Value& v = it->second;
                switch (v.type()) {
                    case ValueType::Null: oss << "null"; break;
                    case ValueType::Bool: oss << (v.as_bool() ? "true" : "false"); break;
                    case ValueType::Int: oss << v.as_int(); break;
                    case ValueType::Float: oss << v.as_float(); break;
                    case ValueType::String: oss << "\"" << v.as_string() << "\""; break;
                    case ValueType::Reference: {
                        std::shared_ptr<Reference> r = v.as_reference_ptr();
                        oss << "\"" << (r ? r->to_ison() : "null") << "\"";
                        break;
                    }
                }

                if (fi < row.size() - 1) oss << ",";
                oss << "\n";
            }

            oss << ind << ind << "}";
            if (ri < block.rows.size() - 1) oss << ",";
            oss << "\n";
        }

        oss << ind << "]";
        if (bi < blocks.size() - 1) oss << ",";
        oss << "\n";
    }
    oss << "}";

    return oss.str();
}

// =============================================================================
// ISONL Support
// =============================================================================

struct ISONLRecord {
    std::string kind;
    std::string name;
    std::vector<std::string> fields;
    Row values;

    std::string to_block_key() const { return kind + "." + name; }
};

class ISONLParser {
public:
    Optional<ISONLRecord> parse_line(const std::string& line, int line_num = 0) {
        std::string trimmed = line;
        size_t start = trimmed.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return Optional<ISONLRecord>();
        size_t end = trimmed.find_last_not_of(" \t\r\n");
        trimmed = trimmed.substr(start, end - start + 1);

        if (trimmed.empty() || trimmed[0] == '#') return Optional<ISONLRecord>();

        std::vector<std::string> sections = split_by_pipe(trimmed);
        if (sections.size() != 3) {
            throw ISONSyntaxError("ISONL line must have 3 pipe-separated sections", line_num, 0);
        }

        size_t dot_pos = sections[0].find('.');
        if (dot_pos == std::string::npos) {
            throw ISONSyntaxError("Invalid ISONL header", line_num, 0);
        }

        ISONLRecord record;
        record.kind = sections[0].substr(0, dot_pos);
        record.name = sections[0].substr(dot_pos + 1);

        Tokenizer field_tokenizer(sections[1], line_num);
        record.fields = field_tokenizer.tokenize();

        Tokenizer value_tokenizer(sections[2], line_num);
        std::vector<std::string> raw_values = value_tokenizer.tokenize();

        size_t pos = 0;
        for (size_t i = 0; i < record.fields.size() && i < raw_values.size(); ++i) {
            while (pos < sections[2].size() && (sections[2][pos] == ' ' || sections[2][pos] == '\t')) {
                ++pos;
            }
            bool was_quoted = pos < sections[2].size() && sections[2][pos] == '"';
            record.values[record.fields[i]] = TypeInferrer::infer(raw_values[i], was_quoted);

            if (was_quoted) {
                ++pos;
                while (pos < sections[2].size() && sections[2][pos] != '"') {
                    if (sections[2][pos] == '\\') ++pos;
                    ++pos;
                }
                if (pos < sections[2].size()) ++pos;
            } else {
                pos += raw_values[i].size();
            }
        }

        return record;
    }

    Document parse_to_document(const std::string& text) {
        std::vector<ISONLRecord> records;
        std::istringstream stream(text);
        std::string line;
        int line_num = 0;

        while (std::getline(stream, line)) {
            ++line_num;
            Optional<ISONLRecord> record = parse_line(line, line_num);
            if (record.has_value()) {
                records.push_back(record.value());
            }
        }

        return records_to_document(records);
    }

private:
    std::vector<std::string> split_by_pipe(const std::string& line) {
        std::vector<std::string> sections;
        std::string current;
        bool in_quotes = false;

        for (size_t i = 0; i < line.size(); ++i) {
            char c = line[i];
            if (c == '"' && (i == 0 || line[i-1] != '\\')) {
                in_quotes = !in_quotes;
                current += c;
            } else if (c == '|' && !in_quotes) {
                size_t s = current.find_first_not_of(" \t");
                size_t e = current.find_last_not_of(" \t");
                sections.push_back(s != std::string::npos ? current.substr(s, e - s + 1) : "");
                current.clear();
            } else {
                current += c;
            }
        }

        size_t s = current.find_first_not_of(" \t");
        size_t e = current.find_last_not_of(" \t");
        sections.push_back(s != std::string::npos ? current.substr(s, e - s + 1) : "");

        return sections;
    }

    Document records_to_document(const std::vector<ISONLRecord>& records) {
        std::map<std::string, std::vector<const ISONLRecord*> > blocks_map;
        std::vector<std::string> block_order;

        for (size_t i = 0; i < records.size(); ++i) {
            std::string key = records[i].to_block_key();
            if (blocks_map.find(key) == blocks_map.end()) {
                block_order.push_back(key);
            }
            blocks_map[key].push_back(&records[i]);
        }

        Document doc;
        for (size_t i = 0; i < block_order.size(); ++i) {
            const std::string& key = block_order[i];
            const std::vector<const ISONLRecord*>& recs = blocks_map[key];
            size_t dot_pos = key.find('.');

            Block block;
            block.kind = key.substr(0, dot_pos);
            block.name = key.substr(dot_pos + 1);
            block.fields = recs[0]->fields;

            for (size_t j = 0; j < recs.size(); ++j) {
                block.rows.push_back(recs[j]->values);
            }

            doc.blocks.push_back(block);
        }

        return doc;
    }
};

class ISONLSerializer {
public:
    static std::string dumps(const Document& doc) {
        std::ostringstream oss;
        bool first = true;

        for (size_t bi = 0; bi < doc.blocks.size(); ++bi) {
            const Block& block = doc.blocks[bi];
            std::string header = block.kind + "." + block.name;

            std::string fields_str;
            for (size_t i = 0; i < block.fields.size(); ++i) {
                if (i > 0) fields_str += " ";
                fields_str += block.fields[i];
            }

            for (size_t ri = 0; ri < block.rows.size(); ++ri) {
                if (!first) oss << "\n";
                first = false;

                const Row& row = block.rows[ri];
                std::string values_str;
                for (size_t i = 0; i < block.fields.size(); ++i) {
                    if (i > 0) values_str += " ";
                    Row::const_iterator it = row.find(block.fields[i]);
                    if (it != row.end()) {
                        values_str += value_to_isonl(it->second);
                    } else {
                        values_str += "null";
                    }
                }

                oss << header << "|" << fields_str << "|" << values_str;
            }
        }

        return oss.str();
    }

private:
    static std::string value_to_isonl(const Value& v) {
        switch (v.type()) {
            case ValueType::Null: return "null";
            case ValueType::Bool: return v.as_bool() ? "true" : "false";
            case ValueType::Int: return std::to_string(v.as_int());
            case ValueType::Float: {
                std::ostringstream oss;
                oss << v.as_float();
                return oss.str();
            }
            case ValueType::String: return quote_if_needed(v.as_string());
            case ValueType::Reference: {
                std::shared_ptr<Reference> r = v.as_reference_ptr();
                return r ? r->to_ison() : "null";
            }
        }
        return "null";
    }

    static std::string quote_if_needed(const std::string& s) {
        if (s.empty()) return "\"\"";

        bool needs_quote = (s == "true" || s == "false" || s == "null" ||
                           s[0] == ':' || s.find(' ') != std::string::npos ||
                           s.find('\t') != std::string::npos ||
                           s.find('"') != std::string::npos ||
                           s.find('\n') != std::string::npos ||
                           s.find('|') != std::string::npos);

        if (needs_quote) {
            std::string escaped;
            for (size_t i = 0; i < s.size(); ++i) {
                char c = s[i];
                switch (c) {
                    case '\\': escaped += "\\\\"; break;
                    case '"':  escaped += "\\\""; break;
                    case '\n': escaped += "\\n"; break;
                    case '\t': escaped += "\\t"; break;
                    case '\r': escaped += "\\r"; break;
                    case '|':  escaped += "\\|"; break;
                    default:   escaped += c; break;
                }
            }
            return "\"" + escaped + "\"";
        }
        return s;
    }
};

// =============================================================================
// Public API Functions
// =============================================================================

inline Document parse(const std::string& text) {
    Parser parser(text);
    return parser.parse();
}

inline Document loads(const std::string& text) {
    return parse(text);
}

inline Document load(const std::string& path) {
    std::ifstream file(path.c_str());
    if (!file.is_open()) {
        throw ISONError("Could not open file: " + path);
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return parse(buffer.str());
}

inline std::string dumps(const Document& doc, bool align_columns = false, const std::string& delimiter = " ") {
    return Serializer::dumps(doc, align_columns);
}

inline void dump(const Document& doc, const std::string& path, bool align_columns = true) {
    std::ofstream file(path.c_str());
    if (!file.is_open()) {
        throw ISONError("Could not open file for writing: " + path);
    }
    file << dumps(doc, align_columns);
}

inline Document loads_isonl(const std::string& text) {
    ISONLParser parser;
    return parser.parse_to_document(text);
}

inline std::string dumps_isonl(const Document& doc) {
    return ISONLSerializer::dumps(doc);
}

inline std::string ison_to_isonl(const std::string& ison_text) {
    Document doc = parse(ison_text);
    return dumps_isonl(doc);
}

inline std::string isonl_to_ison(const std::string& isonl_text) {
    Document doc = loads_isonl(isonl_text);
    return dumps(doc);
}

// =============================================================================
// Value Helper Functions
// =============================================================================

inline bool is_null(const Value& v) { return v.is_null(); }
inline bool is_bool(const Value& v) { return v.is_bool(); }
inline bool is_int(const Value& v) { return v.is_int(); }
inline bool is_float(const Value& v) { return v.is_float(); }
inline bool is_string(const Value& v) { return v.is_string(); }
inline bool is_reference(const Value& v) { return v.is_reference(); }

inline bool as_bool(const Value& v) { return v.as_bool(); }
inline int64_t as_int(const Value& v) { return v.as_int(); }
inline double as_float(const Value& v) { return v.as_float(); }
inline const std::string& as_string(const Value& v) { return v.as_string(); }

} // namespace ison

#endif // ISON_PARSER_HPP
