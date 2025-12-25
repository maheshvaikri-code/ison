//! # ISONantic for Rust
//!
//! Type-safe validation and schema definitions for ISON format.
//!
//! ## Quick Start
//!
//! ```rust,no_run
//! use isonantic_rs::prelude::*;
//! use ison_rs::parse;
//!
//! // Define a schema
//! let user_schema = table("users")
//!     .field("id", int().required())
//!     .field("name", string().min(1).max(100))
//!     .field("email", string().email())
//!     .field("active", boolean().default_value(true));
//!
//! // Parse ISON text
//! let ison_text = r#"
//! table.users
//! id name email active
//! 1 Alice alice@example.com true
//! "#;
//!
//! // Parse and validate
//! let doc = parse(ison_text).expect("Parse failed");
//! let users = user_schema.validate(&doc).expect("Validation failed");
//! ```

use std::collections::HashMap;
use std::fmt;

pub mod schema;
pub mod validators;

pub use schema::*;
pub use validators::*;

/// Library version
pub const VERSION: &str = "1.0.0";

// =============================================================================
// Error Types
// =============================================================================

/// Field validation error
#[derive(Debug, Clone)]
pub struct FieldError {
    pub field: String,
    pub message: String,
    pub value: Option<String>,
}

impl fmt::Display for FieldError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.field, self.message)
    }
}

/// Validation error containing one or more field errors
#[derive(Debug, Clone)]
pub struct ValidationError {
    pub errors: Vec<FieldError>,
}

impl ValidationError {
    pub fn new(errors: Vec<FieldError>) -> Self {
        Self { errors }
    }

    pub fn single(field: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            errors: vec![FieldError {
                field: field.into(),
                message: message.into(),
                value: None,
            }],
        }
    }
}

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Validation failed with {} error(s):", self.errors.len())?;
        for error in &self.errors {
            write!(f, "\n  - {}", error)?;
        }
        Ok(())
    }
}

impl std::error::Error for ValidationError {}

/// Result type for validation operations
pub type Result<T> = std::result::Result<T, ValidationError>;

// =============================================================================
// Value Types
// =============================================================================

/// Validated ISON value
#[derive(Debug, Clone, PartialEq)]
pub enum ValidatedValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    Reference(ISONReference),
    Array(Vec<ValidatedValue>),
    Object(HashMap<String, ValidatedValue>),
}

impl ValidatedValue {
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            ValidatedValue::Bool(b) => Some(*b),
            _ => None,
        }
    }

    pub fn as_int(&self) -> Option<i64> {
        match self {
            ValidatedValue::Int(i) => Some(*i),
            _ => None,
        }
    }

    pub fn as_float(&self) -> Option<f64> {
        match self {
            ValidatedValue::Float(f) => Some(*f),
            ValidatedValue::Int(i) => Some(*i as f64),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            ValidatedValue::String(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_reference(&self) -> Option<&ISONReference> {
        match self {
            ValidatedValue::Reference(r) => Some(r),
            _ => None,
        }
    }

    pub fn is_null(&self) -> bool {
        matches!(self, ValidatedValue::Null)
    }
}

/// ISON reference
#[derive(Debug, Clone, PartialEq)]
pub struct ISONReference {
    pub id: String,
    pub ref_type: Option<String>,
}

impl ISONReference {
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            ref_type: None,
        }
    }

    pub fn with_type(id: impl Into<String>, ref_type: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            ref_type: Some(ref_type.into()),
        }
    }

    pub fn to_ison(&self) -> String {
        match &self.ref_type {
            Some(t) => format!(":{}:{}", t, self.id),
            None => format!(":{}", self.id),
        }
    }
}

// =============================================================================
// Validated Row/Table
// =============================================================================

/// A validated row of data
#[derive(Debug, Clone)]
pub struct ValidatedRow {
    pub fields: HashMap<String, ValidatedValue>,
}

impl ValidatedRow {
    pub fn new() -> Self {
        Self {
            fields: HashMap::new(),
        }
    }

    pub fn get(&self, field: &str) -> Option<&ValidatedValue> {
        self.fields.get(field)
    }

    pub fn get_string(&self, field: &str) -> Option<&str> {
        self.fields.get(field).and_then(|v| v.as_str())
    }

    pub fn get_int(&self, field: &str) -> Option<i64> {
        self.fields.get(field).and_then(|v| v.as_int())
    }

    pub fn get_bool(&self, field: &str) -> Option<bool> {
        self.fields.get(field).and_then(|v| v.as_bool())
    }
}

impl Default for ValidatedRow {
    fn default() -> Self {
        Self::new()
    }
}

/// A validated table of rows
#[derive(Debug, Clone)]
pub struct ValidatedTable {
    pub name: String,
    pub rows: Vec<ValidatedRow>,
}

impl ValidatedTable {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            rows: Vec::new(),
        }
    }

    pub fn len(&self) -> usize {
        self.rows.len()
    }

    pub fn is_empty(&self) -> bool {
        self.rows.is_empty()
    }

    pub fn iter(&self) -> impl Iterator<Item = &ValidatedRow> {
        self.rows.iter()
    }
}

impl std::ops::Index<usize> for ValidatedTable {
    type Output = ValidatedRow;

    fn index(&self, index: usize) -> &Self::Output {
        &self.rows[index]
    }
}

// =============================================================================
// Re-exports
// =============================================================================

pub mod prelude {
    pub use crate::schema::*;
    pub use crate::validators::*;
    pub use crate::{
        FieldError, ISONReference, Result, ValidatedRow, ValidatedTable,
        ValidatedValue, ValidationError,
    };
}
