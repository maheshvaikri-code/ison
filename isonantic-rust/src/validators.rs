//! Custom validators for ISON fields

use crate::{Result, ValidatedValue, ValidationError};
use crate::schema::FieldValidator;

/// Validates that a string is not empty
#[derive(Debug, Clone)]
pub struct NotEmptyValidator;

impl FieldValidator for NotEmptyValidator {
    fn validate(&self, value: &ValidatedValue, field: &str) -> Result<()> {
        if let ValidatedValue::String(s) = value {
            if s.is_empty() {
                return Err(ValidationError::single(field, "String cannot be empty"));
            }
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn FieldValidator> {
        Box::new(self.clone())
    }
}

/// Validates that a value is in a set of allowed values
#[derive(Debug, Clone)]
pub struct OneOfValidator {
    pub allowed: Vec<String>,
}

impl OneOfValidator {
    pub fn new(allowed: Vec<String>) -> Self {
        Self { allowed }
    }
}

impl FieldValidator for OneOfValidator {
    fn validate(&self, value: &ValidatedValue, field: &str) -> Result<()> {
        if let ValidatedValue::String(s) = value {
            if !self.allowed.contains(s) {
                return Err(ValidationError::single(
                    field,
                    format!("Value must be one of: {:?}", self.allowed),
                ));
            }
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn FieldValidator> {
        Box::new(self.clone())
    }
}

/// Custom validation function
pub struct CustomValidator<F>
where
    F: Fn(&ValidatedValue) -> bool + Send + Sync + 'static,
{
    func: F,
    message: String,
}

impl<F> CustomValidator<F>
where
    F: Fn(&ValidatedValue) -> bool + Send + Sync + 'static,
{
    pub fn new(func: F, message: impl Into<String>) -> Self {
        Self {
            func,
            message: message.into(),
        }
    }
}

impl<F> std::fmt::Debug for CustomValidator<F>
where
    F: Fn(&ValidatedValue) -> bool + Send + Sync + 'static,
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("CustomValidator")
            .field("message", &self.message)
            .finish()
    }
}

impl<F> FieldValidator for CustomValidator<F>
where
    F: Fn(&ValidatedValue) -> bool + Send + Sync + Clone + 'static,
{
    fn validate(&self, value: &ValidatedValue, field: &str) -> Result<()> {
        if !(self.func)(value) {
            return Err(ValidationError::single(field, &self.message));
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn FieldValidator> {
        Box::new(CustomValidator {
            func: self.func.clone(),
            message: self.message.clone(),
        })
    }
}

/// Create a custom validator
pub fn custom<F>(func: F, message: impl Into<String>) -> CustomValidator<F>
where
    F: Fn(&ValidatedValue) -> bool + Send + Sync + Clone + 'static,
{
    CustomValidator::new(func, message)
}

/// Validate that a value is not empty
pub fn not_empty() -> NotEmptyValidator {
    NotEmptyValidator
}

/// Validate that a value is one of the allowed values
pub fn one_of(allowed: Vec<&str>) -> OneOfValidator {
    OneOfValidator::new(allowed.into_iter().map(String::from).collect())
}
