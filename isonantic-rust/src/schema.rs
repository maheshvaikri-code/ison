//! Schema definitions for ISON validation

use crate::{FieldError, Result, ValidatedRow, ValidatedTable, ValidatedValue, ValidationError};

// =============================================================================
// Field Schema
// =============================================================================

/// Schema for a single field
#[derive(Debug, Clone)]
pub struct FieldSchema {
    pub name: String,
    pub field_type: FieldType,
    pub required: bool,
    pub default: Option<ValidatedValue>,
    pub validators: Vec<Box<dyn FieldValidator>>,
}

impl FieldSchema {
    pub fn new(name: impl Into<String>, field_type: FieldType) -> Self {
        Self {
            name: name.into(),
            field_type,
            required: false,
            default: None,
            validators: Vec::new(),
        }
    }

    pub fn validate(&self, value: Option<&ison_rs::Value>) -> Result<ValidatedValue> {
        // Handle missing values
        let value = match value {
            Some(v) => v,
            None => {
                if let Some(default) = &self.default {
                    return Ok(default.clone());
                }
                if self.required {
                    return Err(ValidationError::single(&self.name, "Field is required"));
                }
                return Ok(ValidatedValue::Null);
            }
        };

        // Convert and validate type
        let validated = self.field_type.convert(value, &self.name)?;

        // Run custom validators
        for validator in &self.validators {
            validator.validate(&validated, &self.name)?;
        }

        Ok(validated)
    }
}

/// Field type enumeration
#[derive(Debug, Clone)]
pub enum FieldType {
    String(StringConstraints),
    Int(NumberConstraints),
    Float(NumberConstraints),
    Bool,
    Reference,
    Null,
}

impl FieldType {
    fn convert(&self, value: &ison_rs::Value, field: &str) -> Result<ValidatedValue> {
        match self {
            FieldType::String(constraints) => {
                let s = value.as_str().ok_or_else(|| {
                    ValidationError::single(field, "Expected string")
                })?;
                constraints.validate(s, field)?;
                Ok(ValidatedValue::String(s.to_string()))
            }
            FieldType::Int(constraints) => {
                let i = value.as_int().ok_or_else(|| {
                    ValidationError::single(field, "Expected integer")
                })?;
                constraints.validate_int(i, field)?;
                Ok(ValidatedValue::Int(i))
            }
            FieldType::Float(constraints) => {
                let f = value.as_float().or_else(|| value.as_int().map(|i| i as f64))
                    .ok_or_else(|| {
                        ValidationError::single(field, "Expected number")
                    })?;
                constraints.validate_float(f, field)?;
                Ok(ValidatedValue::Float(f))
            }
            FieldType::Bool => {
                let b = value.as_bool().ok_or_else(|| {
                    ValidationError::single(field, "Expected boolean")
                })?;
                Ok(ValidatedValue::Bool(b))
            }
            FieldType::Reference => {
                let r = value.as_reference().ok_or_else(|| {
                    ValidationError::single(field, "Expected reference")
                })?;
                Ok(ValidatedValue::Reference(crate::ISONReference {
                    id: r.id.clone(),
                    ref_type: r.ref_type.clone(),
                }))
            }
            FieldType::Null => {
                if value.is_null() {
                    Ok(ValidatedValue::Null)
                } else {
                    Err(ValidationError::single(field, "Expected null"))
                }
            }
        }
    }
}

// =============================================================================
// Constraints
// =============================================================================

#[derive(Debug, Clone, Default)]
pub struct StringConstraints {
    pub min_length: Option<usize>,
    pub max_length: Option<usize>,
    pub pattern: Option<String>,
    pub email: bool,
}

impl StringConstraints {
    fn validate(&self, value: &str, field: &str) -> Result<()> {
        if let Some(min) = self.min_length {
            if value.len() < min {
                return Err(ValidationError::single(
                    field,
                    format!("String must be at least {} characters", min),
                ));
            }
        }
        if let Some(max) = self.max_length {
            if value.len() > max {
                return Err(ValidationError::single(
                    field,
                    format!("String must be at most {} characters", max),
                ));
            }
        }
        if self.email && !value.contains('@') {
            return Err(ValidationError::single(field, "Invalid email format"));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Default)]
pub struct NumberConstraints {
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub positive: bool,
    pub negative: bool,
}

impl NumberConstraints {
    fn validate_int(&self, value: i64, field: &str) -> Result<()> {
        self.validate_float(value as f64, field)
    }

    fn validate_float(&self, value: f64, field: &str) -> Result<()> {
        if let Some(min) = self.min {
            if value < min {
                return Err(ValidationError::single(
                    field,
                    format!("Value must be >= {}", min),
                ));
            }
        }
        if let Some(max) = self.max {
            if value > max {
                return Err(ValidationError::single(
                    field,
                    format!("Value must be <= {}", max),
                ));
            }
        }
        if self.positive && value <= 0.0 {
            return Err(ValidationError::single(field, "Value must be positive"));
        }
        if self.negative && value >= 0.0 {
            return Err(ValidationError::single(field, "Value must be negative"));
        }
        Ok(())
    }
}

// =============================================================================
// Field Validator Trait
// =============================================================================

pub trait FieldValidator: std::fmt::Debug + Send + Sync {
    fn validate(&self, value: &ValidatedValue, field: &str) -> Result<()>;
    fn clone_box(&self) -> Box<dyn FieldValidator>;
}

impl Clone for Box<dyn FieldValidator> {
    fn clone(&self) -> Self {
        self.clone_box()
    }
}

// =============================================================================
// Schema Builders
// =============================================================================

/// String field builder
#[derive(Debug, Clone, Default)]
pub struct StringFieldBuilder {
    constraints: StringConstraints,
    required: bool,
    default: Option<String>,
}

impl StringFieldBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn min(mut self, len: usize) -> Self {
        self.constraints.min_length = Some(len);
        self
    }

    pub fn max(mut self, len: usize) -> Self {
        self.constraints.max_length = Some(len);
        self
    }

    pub fn email(mut self) -> Self {
        self.constraints.email = true;
        self
    }

    pub fn required(mut self) -> Self {
        self.required = true;
        self
    }

    pub fn default_value(mut self, value: impl Into<String>) -> Self {
        self.default = Some(value.into());
        self
    }

    pub fn build(self, name: impl Into<String>) -> FieldSchema {
        let mut schema = FieldSchema::new(name, FieldType::String(self.constraints));
        schema.required = self.required;
        schema.default = self.default.map(ValidatedValue::String);
        schema
    }
}

/// Integer field builder
#[derive(Debug, Clone, Default)]
pub struct IntFieldBuilder {
    constraints: NumberConstraints,
    required: bool,
    default: Option<i64>,
}

impl IntFieldBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn min(mut self, value: i64) -> Self {
        self.constraints.min = Some(value as f64);
        self
    }

    pub fn max(mut self, value: i64) -> Self {
        self.constraints.max = Some(value as f64);
        self
    }

    pub fn positive(mut self) -> Self {
        self.constraints.positive = true;
        self
    }

    pub fn required(mut self) -> Self {
        self.required = true;
        self
    }

    pub fn default_value(mut self, value: i64) -> Self {
        self.default = Some(value);
        self
    }

    pub fn build(self, name: impl Into<String>) -> FieldSchema {
        let mut schema = FieldSchema::new(name, FieldType::Int(self.constraints));
        schema.required = self.required;
        schema.default = self.default.map(ValidatedValue::Int);
        schema
    }
}

/// Float field builder
#[derive(Debug, Clone, Default)]
pub struct FloatFieldBuilder {
    constraints: NumberConstraints,
    required: bool,
    default: Option<f64>,
}

impl FloatFieldBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn min(mut self, value: f64) -> Self {
        self.constraints.min = Some(value);
        self
    }

    pub fn max(mut self, value: f64) -> Self {
        self.constraints.max = Some(value);
        self
    }

    pub fn positive(mut self) -> Self {
        self.constraints.positive = true;
        self
    }

    pub fn required(mut self) -> Self {
        self.required = true;
        self
    }

    pub fn default_value(mut self, value: f64) -> Self {
        self.default = Some(value);
        self
    }

    pub fn build(self, name: impl Into<String>) -> FieldSchema {
        let mut schema = FieldSchema::new(name, FieldType::Float(self.constraints));
        schema.required = self.required;
        schema.default = self.default.map(ValidatedValue::Float);
        schema
    }
}

/// Boolean field builder
#[derive(Debug, Clone, Default)]
pub struct BoolFieldBuilder {
    required: bool,
    default: Option<bool>,
}

impl BoolFieldBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn required(mut self) -> Self {
        self.required = true;
        self
    }

    pub fn default_value(mut self, value: bool) -> Self {
        self.default = Some(value);
        self
    }

    pub fn build(self, name: impl Into<String>) -> FieldSchema {
        let mut schema = FieldSchema::new(name, FieldType::Bool);
        schema.required = self.required;
        schema.default = self.default.map(ValidatedValue::Bool);
        schema
    }
}

/// Reference field builder
#[derive(Debug, Clone, Default)]
pub struct RefFieldBuilder {
    required: bool,
}

impl RefFieldBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn required(mut self) -> Self {
        self.required = true;
        self
    }

    pub fn build(self, name: impl Into<String>) -> FieldSchema {
        let mut schema = FieldSchema::new(name, FieldType::Reference);
        schema.required = self.required;
        schema
    }
}

// =============================================================================
// Table Schema
// =============================================================================

/// Schema for validating ISON tables
#[derive(Debug, Clone)]
pub struct TableSchema {
    pub name: String,
    pub fields: Vec<FieldSchema>,
}

impl TableSchema {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            fields: Vec::new(),
        }
    }

    pub fn field(mut self, name: impl Into<String>, builder: impl FieldBuilder) -> Self {
        self.fields.push(builder.into_field_schema(name));
        self
    }

    pub fn validate(&self, doc: &ison_rs::Document) -> Result<ValidatedTable> {
        let block = doc.get(&self.name).ok_or_else(|| {
            ValidationError::single("", format!("Missing table: {}", self.name))
        })?;

        let mut table = ValidatedTable::new(&self.name);
        let mut all_errors = Vec::new();

        for (row_idx, row) in block.rows.iter().enumerate() {
            let mut validated_row = ValidatedRow::new();

            for field_schema in &self.fields {
                let value = row.get(&field_schema.name);
                match field_schema.validate(value) {
                    Ok(v) => {
                        validated_row.fields.insert(field_schema.name.clone(), v);
                    }
                    Err(e) => {
                        for err in e.errors {
                            all_errors.push(FieldError {
                                field: format!("[{}].{}", row_idx, err.field),
                                message: err.message,
                                value: err.value,
                            });
                        }
                    }
                }
            }

            table.rows.push(validated_row);
        }

        if !all_errors.is_empty() {
            return Err(ValidationError::new(all_errors));
        }

        Ok(table)
    }
}

// =============================================================================
// Field Builder Trait
// =============================================================================

pub trait FieldBuilder {
    fn into_field_schema(self, name: impl Into<String>) -> FieldSchema;
}

impl FieldBuilder for StringFieldBuilder {
    fn into_field_schema(self, name: impl Into<String>) -> FieldSchema {
        self.build(name)
    }
}

impl FieldBuilder for IntFieldBuilder {
    fn into_field_schema(self, name: impl Into<String>) -> FieldSchema {
        self.build(name)
    }
}

impl FieldBuilder for FloatFieldBuilder {
    fn into_field_schema(self, name: impl Into<String>) -> FieldSchema {
        self.build(name)
    }
}

impl FieldBuilder for BoolFieldBuilder {
    fn into_field_schema(self, name: impl Into<String>) -> FieldSchema {
        self.build(name)
    }
}

impl FieldBuilder for RefFieldBuilder {
    fn into_field_schema(self, name: impl Into<String>) -> FieldSchema {
        self.build(name)
    }
}

// =============================================================================
// Convenience Functions
// =============================================================================

/// Create a table schema
pub fn table(name: impl Into<String>) -> TableSchema {
    TableSchema::new(name)
}

/// Create a string field
pub fn string() -> StringFieldBuilder {
    StringFieldBuilder::new()
}

/// Create an integer field
pub fn int() -> IntFieldBuilder {
    IntFieldBuilder::new()
}

/// Create a float field
pub fn float() -> FloatFieldBuilder {
    FloatFieldBuilder::new()
}

/// Create a boolean field
pub fn boolean() -> BoolFieldBuilder {
    BoolFieldBuilder::new()
}

/// Create a reference field
pub fn reference() -> RefFieldBuilder {
    RefFieldBuilder::new()
}
