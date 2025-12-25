/**
 * @file isonantic.hpp
 * @brief ISONantic - Type-safe validation for ISON format in C++
 * @version 1.0.0
 *
 * Header-only library for ISON schema validation.
 *
 * Usage:
 *   #include "isonantic.hpp"
 *   using namespace isonantic;
 *
 *   auto schema = table("users")
 *       .field("id", integer().required())
 *       .field("name", string().min(1).max(100))
 *       .field("email", string().email());
 *
 *   auto result = schema.validate(doc);
 */

#ifndef ISONANTIC_HPP
#define ISONANTIC_HPP

#include <string>
#include <vector>
#include <map>
#include <optional>
#include <variant>
#include <functional>
#include <memory>
#include <stdexcept>
#include <regex>
#include <sstream>

namespace isonantic {

inline const char* VERSION = "1.0.0";

// =============================================================================
// Forward Declarations
// =============================================================================

class FieldSchema;
class TableSchema;
class ValidationError;

// =============================================================================
// Value Types
// =============================================================================

/**
 * ISON Reference
 */
struct Reference {
    std::string id;
    std::optional<std::string> type;

    Reference(const std::string& id_) : id(id_) {}
    Reference(const std::string& id_, const std::string& type_) : id(id_), type(type_) {}

    std::string to_ison() const {
        if (type) {
            return ":" + *type + ":" + id;
        }
        return ":" + id;
    }
};

/**
 * Validated value type
 */
using Value = std::variant<
    std::nullptr_t,
    bool,
    int64_t,
    double,
    std::string,
    Reference
>;

/**
 * Get value as specific type
 */
template<typename T>
std::optional<T> get_as(const Value& v) {
    if (auto* ptr = std::get_if<T>(&v)) {
        return *ptr;
    }
    return std::nullopt;
}

inline bool is_null(const Value& v) {
    return std::holds_alternative<std::nullptr_t>(v);
}

// =============================================================================
// Error Types
// =============================================================================

/**
 * Field validation error
 */
struct FieldError {
    std::string field;
    std::string message;
    std::optional<std::string> value;

    FieldError(const std::string& f, const std::string& m)
        : field(f), message(m) {}
};

/**
 * Validation error exception
 */
class ValidationError : public std::runtime_error {
public:
    std::vector<FieldError> errors;

    explicit ValidationError(const std::vector<FieldError>& errs)
        : std::runtime_error(format_message(errs)), errors(errs) {}

    explicit ValidationError(const std::string& field, const std::string& message)
        : std::runtime_error(field + ": " + message)
        , errors{{field, message}} {}

private:
    static std::string format_message(const std::vector<FieldError>& errs) {
        std::ostringstream oss;
        oss << "Validation failed with " << errs.size() << " error(s)";
        for (const auto& e : errs) {
            oss << "\n  - " << e.field << ": " << e.message;
        }
        return oss.str();
    }
};

// =============================================================================
// Validated Data Structures
// =============================================================================

/**
 * Validated row of data
 */
class ValidatedRow {
public:
    std::map<std::string, Value> fields;

    std::optional<Value> get(const std::string& name) const {
        auto it = fields.find(name);
        if (it != fields.end()) {
            return it->second;
        }
        return std::nullopt;
    }

    std::optional<std::string> get_string(const std::string& name) const {
        auto v = get(name);
        if (v) return get_as<std::string>(*v);
        return std::nullopt;
    }

    std::optional<int64_t> get_int(const std::string& name) const {
        auto v = get(name);
        if (v) return get_as<int64_t>(*v);
        return std::nullopt;
    }

    std::optional<double> get_float(const std::string& name) const {
        auto v = get(name);
        if (v) {
            if (auto i = get_as<int64_t>(*v)) return static_cast<double>(*i);
            return get_as<double>(*v);
        }
        return std::nullopt;
    }

    std::optional<bool> get_bool(const std::string& name) const {
        auto v = get(name);
        if (v) return get_as<bool>(*v);
        return std::nullopt;
    }
};

/**
 * Validated table of rows
 */
class ValidatedTable {
public:
    std::string name;
    std::vector<ValidatedRow> rows;

    explicit ValidatedTable(const std::string& n) : name(n) {}

    size_t size() const { return rows.size(); }
    bool empty() const { return rows.empty(); }

    const ValidatedRow& operator[](size_t index) const { return rows[index]; }
    ValidatedRow& operator[](size_t index) { return rows[index]; }

    auto begin() const { return rows.begin(); }
    auto end() const { return rows.end(); }
};

// =============================================================================
// Field Constraints
// =============================================================================

struct StringConstraints {
    std::optional<size_t> min_length;
    std::optional<size_t> max_length;
    bool email = false;
    std::optional<std::regex> pattern;
};

struct NumberConstraints {
    std::optional<double> min;
    std::optional<double> max;
    bool positive = false;
    bool negative = false;
};

// =============================================================================
// Field Type
// =============================================================================

enum class FieldType {
    String,
    Integer,
    Float,
    Boolean,
    Reference,
    Null
};

// =============================================================================
// Field Schema
// =============================================================================

class FieldSchema {
public:
    std::string name;
    FieldType type;
    bool required_ = false;
    std::optional<Value> default_value;
    StringConstraints string_constraints;
    NumberConstraints number_constraints;

    FieldSchema(const std::string& n, FieldType t) : name(n), type(t) {}

    Value validate(const std::optional<Value>& input) const {
        // Handle missing value
        if (!input || is_null(*input)) {
            if (default_value) {
                return *default_value;
            }
            if (required_) {
                throw ValidationError(name, "Field is required");
            }
            return nullptr;
        }

        const Value& v = *input;

        // Type validation
        switch (type) {
            case FieldType::String: {
                auto s = get_as<std::string>(v);
                if (!s) {
                    throw ValidationError(name, "Expected string");
                }
                validate_string(*s);
                return v;
            }
            case FieldType::Integer: {
                auto i = get_as<int64_t>(v);
                if (!i) {
                    throw ValidationError(name, "Expected integer");
                }
                validate_number(static_cast<double>(*i));
                return v;
            }
            case FieldType::Float: {
                std::optional<double> f;
                if (auto d = get_as<double>(v)) {
                    f = d;
                } else if (auto i = get_as<int64_t>(v)) {
                    f = static_cast<double>(*i);
                }
                if (!f) {
                    throw ValidationError(name, "Expected number");
                }
                validate_number(*f);
                return Value(*f);
            }
            case FieldType::Boolean: {
                if (!get_as<bool>(v)) {
                    throw ValidationError(name, "Expected boolean");
                }
                return v;
            }
            case FieldType::Reference: {
                if (!get_as<Reference>(v)) {
                    throw ValidationError(name, "Expected reference");
                }
                return v;
            }
            case FieldType::Null: {
                if (!is_null(v)) {
                    throw ValidationError(name, "Expected null");
                }
                return v;
            }
        }
        return v;
    }

private:
    void validate_string(const std::string& s) const {
        if (string_constraints.min_length && s.length() < *string_constraints.min_length) {
            throw ValidationError(name,
                "String must be at least " + std::to_string(*string_constraints.min_length) + " characters");
        }
        if (string_constraints.max_length && s.length() > *string_constraints.max_length) {
            throw ValidationError(name,
                "String must be at most " + std::to_string(*string_constraints.max_length) + " characters");
        }
        if (string_constraints.email && s.find('@') == std::string::npos) {
            throw ValidationError(name, "Invalid email format");
        }
    }

    void validate_number(double n) const {
        if (number_constraints.min && n < *number_constraints.min) {
            throw ValidationError(name, "Value must be >= " + std::to_string(*number_constraints.min));
        }
        if (number_constraints.max && n > *number_constraints.max) {
            throw ValidationError(name, "Value must be <= " + std::to_string(*number_constraints.max));
        }
        if (number_constraints.positive && n <= 0) {
            throw ValidationError(name, "Value must be positive");
        }
        if (number_constraints.negative && n >= 0) {
            throw ValidationError(name, "Value must be negative");
        }
    }
};

// =============================================================================
// Field Builders
// =============================================================================

class StringFieldBuilder {
    StringConstraints constraints_;
    bool required_ = false;
    std::optional<std::string> default_;

public:
    StringFieldBuilder& min(size_t len) { constraints_.min_length = len; return *this; }
    StringFieldBuilder& max(size_t len) { constraints_.max_length = len; return *this; }
    StringFieldBuilder& email() { constraints_.email = true; return *this; }
    StringFieldBuilder& required() { required_ = true; return *this; }
    StringFieldBuilder& default_value(const std::string& v) { default_ = v; return *this; }

    FieldSchema build(const std::string& name) const {
        FieldSchema schema(name, FieldType::String);
        schema.required_ = required_;
        schema.string_constraints = constraints_;
        if (default_) schema.default_value = Value(*default_);
        return schema;
    }
};

class IntegerFieldBuilder {
    NumberConstraints constraints_;
    bool required_ = false;
    std::optional<int64_t> default_;

public:
    IntegerFieldBuilder& min(int64_t v) { constraints_.min = static_cast<double>(v); return *this; }
    IntegerFieldBuilder& max(int64_t v) { constraints_.max = static_cast<double>(v); return *this; }
    IntegerFieldBuilder& positive() { constraints_.positive = true; return *this; }
    IntegerFieldBuilder& required() { required_ = true; return *this; }
    IntegerFieldBuilder& default_value(int64_t v) { default_ = v; return *this; }

    FieldSchema build(const std::string& name) const {
        FieldSchema schema(name, FieldType::Integer);
        schema.required_ = required_;
        schema.number_constraints = constraints_;
        if (default_) schema.default_value = Value(*default_);
        return schema;
    }
};

class FloatFieldBuilder {
    NumberConstraints constraints_;
    bool required_ = false;
    std::optional<double> default_;

public:
    FloatFieldBuilder& min(double v) { constraints_.min = v; return *this; }
    FloatFieldBuilder& max(double v) { constraints_.max = v; return *this; }
    FloatFieldBuilder& positive() { constraints_.positive = true; return *this; }
    FloatFieldBuilder& required() { required_ = true; return *this; }
    FloatFieldBuilder& default_value(double v) { default_ = v; return *this; }

    FieldSchema build(const std::string& name) const {
        FieldSchema schema(name, FieldType::Float);
        schema.required_ = required_;
        schema.number_constraints = constraints_;
        if (default_) schema.default_value = Value(*default_);
        return schema;
    }
};

class BooleanFieldBuilder {
    bool required_ = false;
    std::optional<bool> default_;

public:
    BooleanFieldBuilder& required() { required_ = true; return *this; }
    BooleanFieldBuilder& default_value(bool v) { default_ = v; return *this; }

    FieldSchema build(const std::string& name) const {
        FieldSchema schema(name, FieldType::Boolean);
        schema.required_ = required_;
        if (default_) schema.default_value = Value(*default_);
        return schema;
    }
};

class ReferenceFieldBuilder {
    bool required_ = false;

public:
    ReferenceFieldBuilder& required() { required_ = true; return *this; }

    FieldSchema build(const std::string& name) const {
        FieldSchema schema(name, FieldType::Reference);
        schema.required_ = required_;
        return schema;
    }
};

// =============================================================================
// Table Schema
// =============================================================================

class TableSchema {
    std::string name_;
    std::vector<FieldSchema> fields_;

public:
    explicit TableSchema(const std::string& name) : name_(name) {}

    template<typename Builder>
    TableSchema& field(const std::string& name, Builder builder) {
        fields_.push_back(builder.build(name));
        return *this;
    }

    ValidatedTable validate(const std::map<std::string, std::vector<std::map<std::string, Value>>>& doc) const {
        ValidatedTable result(name_);

        auto it = doc.find(name_);
        if (it == doc.end()) {
            throw ValidationError("", "Missing table: " + name_);
        }

        std::vector<FieldError> all_errors;

        for (size_t row_idx = 0; row_idx < it->second.size(); ++row_idx) {
            const auto& row = it->second[row_idx];
            ValidatedRow validated_row;

            for (const auto& field_schema : fields_) {
                std::optional<Value> value;
                auto field_it = row.find(field_schema.name);
                if (field_it != row.end()) {
                    value = field_it->second;
                }

                try {
                    validated_row.fields[field_schema.name] = field_schema.validate(value);
                } catch (const ValidationError& e) {
                    for (const auto& err : e.errors) {
                        all_errors.push_back({
                            "[" + std::to_string(row_idx) + "]." + err.field,
                            err.message
                        });
                    }
                }
            }

            result.rows.push_back(std::move(validated_row));
        }

        if (!all_errors.empty()) {
            throw ValidationError(all_errors);
        }

        return result;
    }

    const std::string& name() const { return name_; }
};

// =============================================================================
// Convenience Functions
// =============================================================================

inline TableSchema table(const std::string& name) {
    return TableSchema(name);
}

inline StringFieldBuilder string() {
    return StringFieldBuilder();
}

inline IntegerFieldBuilder integer() {
    return IntegerFieldBuilder();
}

inline FloatFieldBuilder floating() {
    return FloatFieldBuilder();
}

inline BooleanFieldBuilder boolean() {
    return BooleanFieldBuilder();
}

inline ReferenceFieldBuilder reference() {
    return ReferenceFieldBuilder();
}

} // namespace isonantic

#endif // ISONANTIC_HPP
