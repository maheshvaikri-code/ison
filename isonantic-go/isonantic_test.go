package isonantic

import (
	"regexp"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestVersion(t *testing.T) {
	assert.Equal(t, "1.0.0", Version)
}

// String Schema Tests

func TestStringRequired(t *testing.T) {
	schema := String()

	err := schema.Validate("hello")
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "required")
}

func TestStringOptional(t *testing.T) {
	schema := String().Optional()

	err := schema.Validate(nil)
	assert.NoError(t, err)

	err = schema.Validate("hello")
	assert.NoError(t, err)
}

func TestStringMinLength(t *testing.T) {
	schema := String().Min(5)

	err := schema.Validate("hello")
	assert.NoError(t, err)

	err = schema.Validate("hi")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at least 5")
}

func TestStringMaxLength(t *testing.T) {
	schema := String().Max(5)

	err := schema.Validate("hello")
	assert.NoError(t, err)

	err = schema.Validate("hello world")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at most 5")
}

func TestStringExactLength(t *testing.T) {
	schema := String().Length(5)

	err := schema.Validate("hello")
	assert.NoError(t, err)

	err = schema.Validate("hi")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "exactly 5")
}

func TestStringEmail(t *testing.T) {
	schema := String().Email()

	err := schema.Validate("test@example.com")
	assert.NoError(t, err)

	err = schema.Validate("invalid-email")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid email")
}

func TestStringURL(t *testing.T) {
	schema := String().URL()

	err := schema.Validate("https://example.com")
	assert.NoError(t, err)

	err = schema.Validate("http://example.com/path")
	assert.NoError(t, err)

	err = schema.Validate("not-a-url")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid URL")
}

func TestStringRegex(t *testing.T) {
	pattern := regexp.MustCompile(`^[A-Z]{2,3}$`)
	schema := String().Regex(pattern)

	err := schema.Validate("AB")
	assert.NoError(t, err)

	err = schema.Validate("ABC")
	assert.NoError(t, err)

	err = schema.Validate("A")
	assert.Error(t, err)

	err = schema.Validate("ABCD")
	assert.Error(t, err)
}

func TestStringDefault(t *testing.T) {
	schema := String().Default("default")

	def, hasDefault := schema.GetDefault()
	assert.True(t, hasDefault)
	assert.Equal(t, "default", def)
}

func TestStringDescribe(t *testing.T) {
	schema := String().Describe("User's name")

	assert.Equal(t, "User's name", schema.GetDescription())
}

func TestStringRefine(t *testing.T) {
	schema := String().Refine(func(s string) bool {
		return s[0] >= 'A' && s[0] <= 'Z'
	}, "must start with uppercase")

	err := schema.Validate("Hello")
	assert.NoError(t, err)

	err = schema.Validate("hello")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "must start with uppercase")
}

// Number Schema Tests

func TestNumberRequired(t *testing.T) {
	schema := Number()

	err := schema.Validate(42.5)
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
}

func TestNumberOptional(t *testing.T) {
	schema := Number().Optional()

	err := schema.Validate(nil)
	assert.NoError(t, err)
}

func TestIntSchema(t *testing.T) {
	schema := Int()

	err := schema.Validate(int64(42))
	assert.NoError(t, err)

	err = schema.Validate(42.5)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "expected integer")
}

func TestNumberMin(t *testing.T) {
	schema := Number().Min(10)

	err := schema.Validate(10.0)
	assert.NoError(t, err)

	err = schema.Validate(5.0)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at least")
}

func TestNumberMax(t *testing.T) {
	schema := Number().Max(10)

	err := schema.Validate(10.0)
	assert.NoError(t, err)

	err = schema.Validate(15.0)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at most")
}

func TestNumberPositive(t *testing.T) {
	schema := Number().Positive()

	err := schema.Validate(5.0)
	assert.NoError(t, err)

	err = schema.Validate(0.0)
	assert.Error(t, err)

	err = schema.Validate(-5.0)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "positive")
}

func TestNumberNegative(t *testing.T) {
	schema := Number().Negative()

	err := schema.Validate(-5.0)
	assert.NoError(t, err)

	err = schema.Validate(0.0)
	assert.Error(t, err)

	err = schema.Validate(5.0)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "negative")
}

func TestNumberRefine(t *testing.T) {
	schema := Number().Refine(func(n float64) bool {
		return int(n)%2 == 0
	}, "must be even")

	err := schema.Validate(4.0)
	assert.NoError(t, err)

	err = schema.Validate(3.0)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "must be even")
}

// Boolean Schema Tests

func TestBooleanRequired(t *testing.T) {
	schema := Boolean()

	err := schema.Validate(true)
	assert.NoError(t, err)

	err = schema.Validate(false)
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
}

func TestBooleanOptional(t *testing.T) {
	schema := Bool().Optional()

	err := schema.Validate(nil)
	assert.NoError(t, err)
}

func TestBooleanDefault(t *testing.T) {
	schema := Boolean().Default(true)

	def, hasDefault := schema.GetDefault()
	assert.True(t, hasDefault)
	assert.Equal(t, true, def)
}

// Null Schema Tests

func TestNullSchema(t *testing.T) {
	schema := Null()

	err := schema.Validate(nil)
	assert.NoError(t, err)

	err = schema.Validate("not null")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "expected null")
}

// Reference Schema Tests

func TestRefRequired(t *testing.T) {
	schema := Ref()

	err := schema.Validate(":1")
	assert.NoError(t, err)

	err = schema.Validate(map[string]interface{}{"_ref": "1"})
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
}

func TestRefOptional(t *testing.T) {
	schema := Reference().Optional()

	err := schema.Validate(nil)
	assert.NoError(t, err)
}

func TestRefNamespace(t *testing.T) {
	schema := Ref().Namespace("user")

	err := schema.Validate(map[string]interface{}{
		"_ref":       "1",
		"_namespace": "user",
	})
	assert.NoError(t, err)

	err = schema.Validate(map[string]interface{}{
		"_ref":       "1",
		"_namespace": "other",
	})
	assert.Error(t, err)
}

func TestRefRelationship(t *testing.T) {
	schema := Ref().Relationship("OWNS")

	err := schema.Validate(map[string]interface{}{
		"_ref":          "1",
		"_relationship": "OWNS",
	})
	assert.NoError(t, err)

	err = schema.Validate(map[string]interface{}{
		"_ref":          "1",
		"_relationship": "OTHER",
	})
	assert.Error(t, err)
}

func TestRefStringFormat(t *testing.T) {
	schema := Ref()

	err := schema.Validate(":1")
	assert.NoError(t, err)

	err = schema.Validate(":user:42")
	assert.NoError(t, err)

	err = schema.Validate("not-a-ref")
	assert.Error(t, err)
}

// Object Schema Tests

func TestObjectRequired(t *testing.T) {
	schema := Object(map[string]Schema{
		"name": String(),
		"age":  Int(),
	})

	err := schema.Validate(map[string]interface{}{
		"name": "Alice",
		"age":  int64(30),
	})
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
}

func TestObjectFieldValidation(t *testing.T) {
	schema := Object(map[string]Schema{
		"name":  String().Min(1),
		"email": String().Email(),
	})

	err := schema.Validate(map[string]interface{}{
		"name":  "Alice",
		"email": "alice@example.com",
	})
	assert.NoError(t, err)

	err = schema.Validate(map[string]interface{}{
		"name":  "",
		"email": "invalid",
	})
	assert.Error(t, err)
	verrs, ok := err.(ValidationErrors)
	require.True(t, ok)
	assert.Len(t, verrs.Errors, 2)
}

func TestObjectOptionalField(t *testing.T) {
	schema := Object(map[string]Schema{
		"name":  String(),
		"email": String().Optional(),
	})

	err := schema.Validate(map[string]interface{}{
		"name": "Alice",
	})
	assert.NoError(t, err)
}

func TestObjectExtend(t *testing.T) {
	baseSchema := Object(map[string]Schema{
		"id":   Int(),
		"name": String(),
	})

	extendedSchema := baseSchema.Extend(map[string]Schema{
		"email": String().Email(),
	})

	err := extendedSchema.Validate(map[string]interface{}{
		"id":    int64(1),
		"name":  "Alice",
		"email": "alice@example.com",
	})
	assert.NoError(t, err)
}

func TestObjectPick(t *testing.T) {
	schema := Object(map[string]Schema{
		"id":    Int(),
		"name":  String(),
		"email": String(),
	})

	pickedSchema := schema.Pick("id", "name")

	err := pickedSchema.Validate(map[string]interface{}{
		"id":   int64(1),
		"name": "Alice",
	})
	assert.NoError(t, err)
}

func TestObjectOmit(t *testing.T) {
	schema := Object(map[string]Schema{
		"id":    Int(),
		"name":  String(),
		"email": String(),
	})

	omittedSchema := schema.Omit("email")

	err := omittedSchema.Validate(map[string]interface{}{
		"id":   int64(1),
		"name": "Alice",
	})
	assert.NoError(t, err)
}

// Array Schema Tests

func TestArrayRequired(t *testing.T) {
	schema := Array(String())

	err := schema.Validate([]interface{}{"a", "b", "c"})
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
}

func TestArrayOptional(t *testing.T) {
	schema := Array(String()).Optional()

	err := schema.Validate(nil)
	assert.NoError(t, err)
}

func TestArrayMinLength(t *testing.T) {
	schema := Array(String()).Min(2)

	err := schema.Validate([]interface{}{"a", "b"})
	assert.NoError(t, err)

	err = schema.Validate([]interface{}{"a"})
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at least 2")
}

func TestArrayMaxLength(t *testing.T) {
	schema := Array(String()).Max(2)

	err := schema.Validate([]interface{}{"a", "b"})
	assert.NoError(t, err)

	err = schema.Validate([]interface{}{"a", "b", "c"})
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at most 2")
}

func TestArrayItemValidation(t *testing.T) {
	schema := Array(Int())

	err := schema.Validate([]interface{}{int64(1), int64(2), int64(3)})
	assert.NoError(t, err)

	err = schema.Validate([]interface{}{int64(1), "not an int", int64(3)})
	assert.Error(t, err)
	verrs, ok := err.(ValidationErrors)
	require.True(t, ok)
	assert.Len(t, verrs.Errors, 1)
	assert.Equal(t, "[1]", verrs.Errors[0].Field)
}

// Table Schema Tests

func TestTableRequired(t *testing.T) {
	schema := Table("users", map[string]Schema{
		"id":   Int(),
		"name": String(),
	})

	err := schema.Validate([]interface{}{
		map[string]interface{}{"id": int64(1), "name": "Alice"},
		map[string]interface{}{"id": int64(2), "name": "Bob"},
	})
	assert.NoError(t, err)

	err = schema.Validate(nil)
	assert.Error(t, err)
}

func TestTableOptional(t *testing.T) {
	schema := Table("users", map[string]Schema{
		"id":   Int(),
		"name": String(),
	}).Optional()

	err := schema.Validate(nil)
	assert.NoError(t, err)
}

func TestTableRowValidation(t *testing.T) {
	schema := Table("users", map[string]Schema{
		"id":    Int(),
		"email": String().Email(),
	})

	err := schema.Validate([]interface{}{
		map[string]interface{}{"id": int64(1), "email": "alice@example.com"},
		map[string]interface{}{"id": int64(2), "email": "invalid"},
	})
	assert.Error(t, err)
	verrs, ok := err.(ValidationErrors)
	require.True(t, ok)
	assert.Len(t, verrs.Errors, 1)
	assert.Contains(t, verrs.Errors[0].Field, "row[1]")
}

func TestTableBlockFormat(t *testing.T) {
	schema := Table("users", map[string]Schema{
		"id":   Int(),
		"name": String(),
	})

	err := schema.Validate(map[string]interface{}{
		"kind": "table",
		"name": "users",
		"rows": []interface{}{
			map[string]interface{}{"id": int64(1), "name": "Alice"},
		},
	})
	assert.NoError(t, err)
}

func TestTableGetName(t *testing.T) {
	schema := Table("users", map[string]Schema{})
	assert.Equal(t, "users", schema.GetName())
}

// Document Schema Tests

func TestDocumentParse(t *testing.T) {
	schema := Document(map[string]Schema{
		"users": Table("users", map[string]Schema{
			"id":   Int(),
			"name": String(),
		}),
		"config": Object(map[string]Schema{
			"debug": Boolean(),
		}),
	})

	doc := map[string]interface{}{
		"users": []interface{}{
			map[string]interface{}{"id": int64(1), "name": "Alice"},
		},
		"config": map[string]interface{}{
			"debug": true,
		},
	}

	result, err := schema.Parse(doc)
	assert.NoError(t, err)
	assert.NotNil(t, result)
}

func TestDocumentParseErrors(t *testing.T) {
	schema := Document(map[string]Schema{
		"users": Table("users", map[string]Schema{
			"id":    Int(),
			"email": String().Email(),
		}),
	})

	doc := map[string]interface{}{
		"users": []interface{}{
			map[string]interface{}{"id": int64(1), "email": "invalid"},
		},
	}

	_, err := schema.Parse(doc)
	assert.Error(t, err)
	verrs, ok := err.(ValidationErrors)
	require.True(t, ok)
	assert.Len(t, verrs.Errors, 1)
}

func TestDocumentSafeParse(t *testing.T) {
	schema := Document(map[string]Schema{
		"users": Table("users", map[string]Schema{
			"id":   Int(),
			"name": String(),
		}),
	})

	// Valid document
	doc := map[string]interface{}{
		"users": []interface{}{
			map[string]interface{}{"id": int64(1), "name": "Alice"},
		},
	}

	result := schema.SafeParse(doc)
	assert.True(t, result.Success)
	assert.NotNil(t, result.Data)
	assert.Nil(t, result.Error)

	// Invalid document
	invalidDoc := map[string]interface{}{
		"users": []interface{}{
			map[string]interface{}{"id": "not-an-int", "name": "Alice"},
		},
	}

	result = schema.SafeParse(invalidDoc)
	assert.False(t, result.Success)
	assert.Nil(t, result.Data)
	assert.NotNil(t, result.Error)
}

// I Namespace Tests

func TestINamespace(t *testing.T) {
	// Test that I provides access to all schema builders
	assert.NotNil(t, I.String())
	assert.NotNil(t, I.Number())
	assert.NotNil(t, I.Int())
	assert.NotNil(t, I.Float())
	assert.NotNil(t, I.Boolean())
	assert.NotNil(t, I.Bool())
	assert.NotNil(t, I.Null())
	assert.NotNil(t, I.Ref())
	assert.NotNil(t, I.Reference())
	assert.NotNil(t, I.Object(map[string]Schema{}))
	assert.NotNil(t, I.Array(I.String()))
	assert.NotNil(t, I.Table("test", map[string]Schema{}))
}

func TestINamespaceUsage(t *testing.T) {
	// Example of using I namespace like Zod's z
	userSchema := I.Table("users", map[string]Schema{
		"id":     I.Int(),
		"name":   I.String().Min(1),
		"email":  I.String().Email(),
		"active": I.Bool().Default(true),
	})

	err := userSchema.Validate([]interface{}{
		map[string]interface{}{
			"id":     int64(1),
			"name":   "Alice",
			"email":  "alice@example.com",
			"active": true,
		},
	})
	assert.NoError(t, err)
}

// ValidationError Tests

func TestValidationErrorString(t *testing.T) {
	err := ValidationError{
		Field:   "email",
		Message: "invalid email format",
		Value:   "not-an-email",
	}

	assert.Equal(t, "email: invalid email format", err.Error())
}

func TestValidationErrorsString(t *testing.T) {
	errs := ValidationErrors{
		Errors: []ValidationError{
			{Field: "email", Message: "invalid email"},
			{Field: "name", Message: "required"},
		},
	}

	assert.Contains(t, errs.Error(), "email: invalid email")
	assert.Contains(t, errs.Error(), "name: required")
}

func TestValidationErrorsHasErrors(t *testing.T) {
	empty := ValidationErrors{}
	assert.False(t, empty.HasErrors())

	withErrors := ValidationErrors{
		Errors: []ValidationError{{Field: "test", Message: "error"}},
	}
	assert.True(t, withErrors.HasErrors())
}
