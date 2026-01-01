// Package isonantic provides Zod-like validation and schema definitions for ISON format in Go.
// It offers type-safe validation with fluent API for defining and validating ISON documents.
package isonantic

import (
	"fmt"
	"regexp"
	"strings"
)

// Version is the current version of the isonantic-go package
const Version = "1.0.0"

// ValidationError represents a validation error with field path and message
type ValidationError struct {
	Field   string
	Message string
	Value   interface{}
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("%s: %s", e.Field, e.Message)
}

// ValidationErrors is a collection of validation errors
type ValidationErrors struct {
	Errors []ValidationError
}

func (e ValidationErrors) Error() string {
	var msgs []string
	for _, err := range e.Errors {
		msgs = append(msgs, err.Error())
	}
	return strings.Join(msgs, "; ")
}

// HasErrors returns true if there are any validation errors
func (e ValidationErrors) HasErrors() bool {
	return len(e.Errors) > 0
}

// Schema is the base interface for all schemas
type Schema interface {
	Validate(value interface{}) error
	IsOptional() bool
	GetDefault() (interface{}, bool)
	GetDescription() string
}

// BaseSchema provides common functionality for all schemas
type BaseSchema struct {
	optional     bool
	defaultValue interface{}
	hasDefault   bool
	description  string
	refinements  []func(interface{}) error
}

// Optional marks the schema as optional
func (s *BaseSchema) setOptional() {
	s.optional = true
}

// Default sets a default value
func (s *BaseSchema) setDefault(v interface{}) {
	s.defaultValue = v
	s.hasDefault = true
}

// Describe adds a description
func (s *BaseSchema) setDescription(desc string) {
	s.description = desc
}

// AddRefinement adds a custom validation function
func (s *BaseSchema) addRefinement(fn func(interface{}) error) {
	s.refinements = append(s.refinements, fn)
}

func (s *BaseSchema) IsOptional() bool {
	return s.optional
}

func (s *BaseSchema) GetDefault() (interface{}, bool) {
	return s.defaultValue, s.hasDefault
}

func (s *BaseSchema) GetDescription() string {
	return s.description
}

func (s *BaseSchema) runRefinements(value interface{}) error {
	for _, fn := range s.refinements {
		if err := fn(value); err != nil {
			return err
		}
	}
	return nil
}

// StringSchema validates string values
type StringSchema struct {
	BaseSchema
	minLen      *int
	maxLen      *int
	exactLen    *int
	pattern     *regexp.Regexp
	isEmail     bool
	isURL       bool
}

// String creates a new string schema
func String() *StringSchema {
	return &StringSchema{}
}

// Min sets minimum length
func (s *StringSchema) Min(n int) *StringSchema {
	s.minLen = &n
	return s
}

// Max sets maximum length
func (s *StringSchema) Max(n int) *StringSchema {
	s.maxLen = &n
	return s
}

// Length sets exact length
func (s *StringSchema) Length(n int) *StringSchema {
	s.exactLen = &n
	return s
}

// Email validates email format
func (s *StringSchema) Email() *StringSchema {
	s.isEmail = true
	return s
}

// URL validates URL format
func (s *StringSchema) URL() *StringSchema {
	s.isURL = true
	return s
}

// Regex sets a custom regex pattern
func (s *StringSchema) Regex(pattern *regexp.Regexp) *StringSchema {
	s.pattern = pattern
	return s
}

// Optional marks as optional
func (s *StringSchema) Optional() *StringSchema {
	s.setOptional()
	return s
}

// Default sets default value
func (s *StringSchema) Default(v string) *StringSchema {
	s.setDefault(v)
	return s
}

// Describe adds description
func (s *StringSchema) Describe(desc string) *StringSchema {
	s.setDescription(desc)
	return s
}

// Refine adds custom validation
func (s *StringSchema) Refine(fn func(string) bool, msg string) *StringSchema {
	s.addRefinement(func(v interface{}) error {
		if str, ok := v.(string); ok {
			if !fn(str) {
				return fmt.Errorf(msg)
			}
		}
		return nil
	})
	return s
}

// Validate validates a string value
func (s *StringSchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required field is missing")
	}

	str, ok := value.(string)
	if !ok {
		return fmt.Errorf("expected string, got %T", value)
	}

	if s.minLen != nil && len(str) < *s.minLen {
		return fmt.Errorf("string must be at least %d characters", *s.minLen)
	}

	if s.maxLen != nil && len(str) > *s.maxLen {
		return fmt.Errorf("string must be at most %d characters", *s.maxLen)
	}

	if s.exactLen != nil && len(str) != *s.exactLen {
		return fmt.Errorf("string must be exactly %d characters", *s.exactLen)
	}

	if s.isEmail {
		emailPattern := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
		if !emailPattern.MatchString(str) {
			return fmt.Errorf("invalid email format")
		}
	}

	if s.isURL {
		urlPattern := regexp.MustCompile(`^https?://[^\s/$.?#].[^\s]*$`)
		if !urlPattern.MatchString(str) {
			return fmt.Errorf("invalid URL format")
		}
	}

	if s.pattern != nil && !s.pattern.MatchString(str) {
		return fmt.Errorf("string does not match required pattern")
	}

	return s.runRefinements(value)
}

// NumberSchema validates numeric values
type NumberSchema struct {
	BaseSchema
	minVal      *float64
	maxVal      *float64
	isInt       bool
	isPositive  bool
	isNegative  bool
}

// Number creates a new number schema
func Number() *NumberSchema {
	return &NumberSchema{}
}

// Int creates an integer schema
func Int() *NumberSchema {
	s := &NumberSchema{isInt: true}
	return s
}

// Float creates a float schema (alias for Number)
func Float() *NumberSchema {
	return &NumberSchema{}
}

// Min sets minimum value
func (s *NumberSchema) Min(n float64) *NumberSchema {
	s.minVal = &n
	return s
}

// Max sets maximum value
func (s *NumberSchema) Max(n float64) *NumberSchema {
	s.maxVal = &n
	return s
}

// Positive requires positive numbers
func (s *NumberSchema) Positive() *NumberSchema {
	s.isPositive = true
	return s
}

// Negative requires negative numbers
func (s *NumberSchema) Negative() *NumberSchema {
	s.isNegative = true
	return s
}

// Optional marks as optional
func (s *NumberSchema) Optional() *NumberSchema {
	s.setOptional()
	return s
}

// Default sets default value
func (s *NumberSchema) Default(v float64) *NumberSchema {
	s.setDefault(v)
	return s
}

// Describe adds description
func (s *NumberSchema) Describe(desc string) *NumberSchema {
	s.setDescription(desc)
	return s
}

// Refine adds custom validation
func (s *NumberSchema) Refine(fn func(float64) bool, msg string) *NumberSchema {
	s.addRefinement(func(v interface{}) error {
		var num float64
		switch n := v.(type) {
		case float64:
			num = n
		case int64:
			num = float64(n)
		case int:
			num = float64(n)
		default:
			return nil
		}
		if !fn(num) {
			return fmt.Errorf(msg)
		}
		return nil
	})
	return s
}

// Validate validates a numeric value
func (s *NumberSchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required field is missing")
	}

	var num float64
	switch v := value.(type) {
	case float64:
		num = v
	case int64:
		num = float64(v)
	case int:
		num = float64(v)
	default:
		return fmt.Errorf("expected number, got %T", value)
	}

	if s.isInt {
		if num != float64(int64(num)) {
			return fmt.Errorf("expected integer, got float")
		}
	}

	if s.minVal != nil && num < *s.minVal {
		return fmt.Errorf("number must be at least %v", *s.minVal)
	}

	if s.maxVal != nil && num > *s.maxVal {
		return fmt.Errorf("number must be at most %v", *s.maxVal)
	}

	if s.isPositive && num <= 0 {
		return fmt.Errorf("number must be positive")
	}

	if s.isNegative && num >= 0 {
		return fmt.Errorf("number must be negative")
	}

	return s.runRefinements(value)
}

// BooleanSchema validates boolean values
type BooleanSchema struct {
	BaseSchema
}

// Boolean creates a new boolean schema
func Boolean() *BooleanSchema {
	return &BooleanSchema{}
}

// Bool is an alias for Boolean
func Bool() *BooleanSchema {
	return Boolean()
}

// Optional marks as optional
func (s *BooleanSchema) Optional() *BooleanSchema {
	s.setOptional()
	return s
}

// Default sets default value
func (s *BooleanSchema) Default(v bool) *BooleanSchema {
	s.setDefault(v)
	return s
}

// Describe adds description
func (s *BooleanSchema) Describe(desc string) *BooleanSchema {
	s.setDescription(desc)
	return s
}

// Validate validates a boolean value
func (s *BooleanSchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required field is missing")
	}

	if _, ok := value.(bool); !ok {
		return fmt.Errorf("expected boolean, got %T", value)
	}

	return s.runRefinements(value)
}

// NullSchema validates null values
type NullSchema struct {
	BaseSchema
}

// Null creates a null schema
func Null() *NullSchema {
	return &NullSchema{}
}

// Validate validates a null value
func (s *NullSchema) Validate(value interface{}) error {
	if value != nil {
		return fmt.Errorf("expected null, got %T", value)
	}
	return nil
}

// RefSchema validates ISON references
type RefSchema struct {
	BaseSchema
	namespace    *string
	relationship *string
}

// Ref creates a new reference schema
func Ref() *RefSchema {
	return &RefSchema{}
}

// Reference is an alias for Ref
func Reference() *RefSchema {
	return Ref()
}

// Namespace requires a specific namespace
func (s *RefSchema) Namespace(ns string) *RefSchema {
	s.namespace = &ns
	return s
}

// Relationship requires a relationship reference
func (s *RefSchema) Relationship(rel string) *RefSchema {
	s.relationship = &rel
	return s
}

// Optional marks as optional
func (s *RefSchema) Optional() *RefSchema {
	s.setOptional()
	return s
}

// Describe adds description
func (s *RefSchema) Describe(desc string) *RefSchema {
	s.setDescription(desc)
	return s
}

// Validate validates a reference value
func (s *RefSchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required field is missing")
	}

	// Accept reference objects or strings
	switch v := value.(type) {
	case map[string]interface{}:
		// Reference object format
		if _, ok := v["_ref"]; !ok {
			return fmt.Errorf("expected reference object with _ref field")
		}
		if s.namespace != nil {
			if ns, ok := v["_namespace"].(string); !ok || ns != *s.namespace {
				return fmt.Errorf("expected namespace %s", *s.namespace)
			}
		}
		if s.relationship != nil {
			if rel, ok := v["_relationship"].(string); !ok || rel != *s.relationship {
				return fmt.Errorf("expected relationship %s", *s.relationship)
			}
		}
	case string:
		// String reference format (:id, :ns:id, :REL:id)
		if !strings.HasPrefix(v, ":") {
			return fmt.Errorf("expected reference string starting with ':'")
		}
	default:
		return fmt.Errorf("expected reference, got %T", value)
	}

	return s.runRefinements(value)
}

// ObjectSchema validates object structures
type ObjectSchema struct {
	BaseSchema
	fields map[string]Schema
}

// Object creates a new object schema
func Object(fields map[string]Schema) *ObjectSchema {
	return &ObjectSchema{fields: fields}
}

// Optional marks as optional
func (s *ObjectSchema) Optional() *ObjectSchema {
	s.setOptional()
	return s
}

// Describe adds description
func (s *ObjectSchema) Describe(desc string) *ObjectSchema {
	s.setDescription(desc)
	return s
}

// Extend creates a new schema with additional fields
func (s *ObjectSchema) Extend(fields map[string]Schema) *ObjectSchema {
	newFields := make(map[string]Schema)
	for k, v := range s.fields {
		newFields[k] = v
	}
	for k, v := range fields {
		newFields[k] = v
	}
	return Object(newFields)
}

// Pick creates a schema with only specified fields
func (s *ObjectSchema) Pick(keys ...string) *ObjectSchema {
	newFields := make(map[string]Schema)
	for _, key := range keys {
		if v, ok := s.fields[key]; ok {
			newFields[key] = v
		}
	}
	return Object(newFields)
}

// Omit creates a schema without specified fields
func (s *ObjectSchema) Omit(keys ...string) *ObjectSchema {
	keySet := make(map[string]bool)
	for _, key := range keys {
		keySet[key] = true
	}
	newFields := make(map[string]Schema)
	for k, v := range s.fields {
		if !keySet[k] {
			newFields[k] = v
		}
	}
	return Object(newFields)
}

// Validate validates an object
func (s *ObjectSchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required field is missing")
	}

	obj, ok := value.(map[string]interface{})
	if !ok {
		return fmt.Errorf("expected object, got %T", value)
	}

	var errs ValidationErrors
	for name, schema := range s.fields {
		fieldValue := obj[name]
		if fieldValue == nil && !schema.IsOptional() {
			if def, hasDefault := schema.GetDefault(); hasDefault {
				obj[name] = def
				continue
			}
		}
		if err := schema.Validate(fieldValue); err != nil {
			errs.Errors = append(errs.Errors, ValidationError{
				Field:   name,
				Message: err.Error(),
				Value:   fieldValue,
			})
		}
	}

	if errs.HasErrors() {
		return errs
	}

	return s.runRefinements(value)
}

// ArraySchema validates arrays
type ArraySchema struct {
	BaseSchema
	itemSchema Schema
	minLen     *int
	maxLen     *int
}

// Array creates a new array schema
func Array(itemSchema Schema) *ArraySchema {
	return &ArraySchema{itemSchema: itemSchema}
}

// Min sets minimum length
func (s *ArraySchema) Min(n int) *ArraySchema {
	s.minLen = &n
	return s
}

// Max sets maximum length
func (s *ArraySchema) Max(n int) *ArraySchema {
	s.maxLen = &n
	return s
}

// Optional marks as optional
func (s *ArraySchema) Optional() *ArraySchema {
	s.setOptional()
	return s
}

// Describe adds description
func (s *ArraySchema) Describe(desc string) *ArraySchema {
	s.setDescription(desc)
	return s
}

// Validate validates an array
func (s *ArraySchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required field is missing")
	}

	arr, ok := value.([]interface{})
	if !ok {
		return fmt.Errorf("expected array, got %T", value)
	}

	if s.minLen != nil && len(arr) < *s.minLen {
		return fmt.Errorf("array must have at least %d items", *s.minLen)
	}

	if s.maxLen != nil && len(arr) > *s.maxLen {
		return fmt.Errorf("array must have at most %d items", *s.maxLen)
	}

	var errs ValidationErrors
	for i, item := range arr {
		if err := s.itemSchema.Validate(item); err != nil {
			errs.Errors = append(errs.Errors, ValidationError{
				Field:   fmt.Sprintf("[%d]", i),
				Message: err.Error(),
				Value:   item,
			})
		}
	}

	if errs.HasErrors() {
		return errs
	}

	return s.runRefinements(value)
}

// TableSchema validates ISON table blocks
type TableSchema struct {
	BaseSchema
	name       string
	fields     map[string]Schema
	rowSchema  *ObjectSchema
}

// Table creates a new table schema
func Table(name string, fields map[string]Schema) *TableSchema {
	return &TableSchema{
		name:      name,
		fields:    fields,
		rowSchema: Object(fields),
	}
}

// Optional marks as optional
func (s *TableSchema) Optional() *TableSchema {
	s.setOptional()
	return s
}

// Describe adds description
func (s *TableSchema) Describe(desc string) *TableSchema {
	s.setDescription(desc)
	return s
}

// GetName returns the table name
func (s *TableSchema) GetName() string {
	return s.name
}

// Validate validates a table block
func (s *TableSchema) Validate(value interface{}) error {
	if value == nil {
		if s.optional {
			return nil
		}
		return fmt.Errorf("required table is missing")
	}

	// Value could be block dict or array of rows
	switch v := value.(type) {
	case map[string]interface{}:
		// Block format with rows array
		rows, ok := v["rows"].([]interface{})
		if !ok {
			return fmt.Errorf("expected table with rows array")
		}
		return s.validateRows(rows)
	case []interface{}:
		// Direct array of rows
		return s.validateRows(v)
	default:
		return fmt.Errorf("expected table, got %T", value)
	}
}

func (s *TableSchema) validateRows(rows []interface{}) error {
	var errs ValidationErrors
	for i, row := range rows {
		rowMap, ok := row.(map[string]interface{})
		if !ok {
			errs.Errors = append(errs.Errors, ValidationError{
				Field:   fmt.Sprintf("row[%d]", i),
				Message: "expected row object",
				Value:   row,
			})
			continue
		}
		if err := s.rowSchema.Validate(rowMap); err != nil {
			if ve, ok := err.(ValidationErrors); ok {
				for _, e := range ve.Errors {
					errs.Errors = append(errs.Errors, ValidationError{
						Field:   fmt.Sprintf("row[%d].%s", i, e.Field),
						Message: e.Message,
						Value:   e.Value,
					})
				}
			} else {
				errs.Errors = append(errs.Errors, ValidationError{
					Field:   fmt.Sprintf("row[%d]", i),
					Message: err.Error(),
					Value:   row,
				})
			}
		}
	}

	if errs.HasErrors() {
		return errs
	}

	return s.runRefinements(rows)
}

// DocumentSchema validates complete ISON documents
type DocumentSchema struct {
	blocks map[string]Schema
}

// Document creates a new document schema
func Document(blocks map[string]Schema) *DocumentSchema {
	return &DocumentSchema{blocks: blocks}
}

// Parse validates a document and returns the validated data
func (s *DocumentSchema) Parse(value map[string]interface{}) (map[string]interface{}, error) {
	var errs ValidationErrors

	for name, schema := range s.blocks {
		blockValue := value[name]
		if err := schema.Validate(blockValue); err != nil {
			if ve, ok := err.(ValidationErrors); ok {
				for _, e := range ve.Errors {
					errs.Errors = append(errs.Errors, ValidationError{
						Field:   fmt.Sprintf("%s.%s", name, e.Field),
						Message: e.Message,
						Value:   e.Value,
					})
				}
			} else {
				errs.Errors = append(errs.Errors, ValidationError{
					Field:   name,
					Message: err.Error(),
					Value:   blockValue,
				})
			}
		}
	}

	if errs.HasErrors() {
		return nil, errs
	}

	return value, nil
}

// SafeParseResult contains the result of SafeParse
type SafeParseResult struct {
	Success bool
	Data    map[string]interface{}
	Error   error
}

// SafeParse validates without throwing, returns result struct
func (s *DocumentSchema) SafeParse(value map[string]interface{}) SafeParseResult {
	data, err := s.Parse(value)
	if err != nil {
		return SafeParseResult{Success: false, Error: err}
	}
	return SafeParseResult{Success: true, Data: data}
}

// I provides a namespace for schema creation (like Zod's z)
var I = struct {
	String    func() *StringSchema
	Number    func() *NumberSchema
	Int       func() *NumberSchema
	Float     func() *NumberSchema
	Boolean   func() *BooleanSchema
	Bool      func() *BooleanSchema
	Null      func() *NullSchema
	Ref       func() *RefSchema
	Reference func() *RefSchema
	Object    func(map[string]Schema) *ObjectSchema
	Array     func(Schema) *ArraySchema
	Table     func(string, map[string]Schema) *TableSchema
}{
	String:    String,
	Number:    Number,
	Int:       Int,
	Float:     Float,
	Boolean:   Boolean,
	Bool:      Bool,
	Null:      Null,
	Ref:       Ref,
	Reference: Reference,
	Object:    Object,
	Array:     Array,
	Table:     Table,
}
