package ison

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestVersion(t *testing.T) {
	assert.Equal(t, "1.0.0", Version)
}

func TestParseSimpleTable(t *testing.T) {
	input := `
table.users
id name email
1 Alice alice@example.com
2 Bob bob@example.com
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, ok := doc.Get("users")
	require.True(t, ok)
	assert.Equal(t, "table", block.Kind)
	assert.Equal(t, "users", block.Name)
	assert.Len(t, block.Fields, 3)
	assert.Len(t, block.Rows, 2)

	// Check first row
	row1 := block.Rows[0]
	id, ok := row1["id"].AsInt()
	assert.True(t, ok)
	assert.Equal(t, int64(1), id)

	name, ok := row1["name"].AsString()
	assert.True(t, ok)
	assert.Equal(t, "Alice", name)
}

func TestParseTypedFields(t *testing.T) {
	input := `
table.users
id:int name:string active:bool score:float
1 Alice true 95.5
2 Bob false 82.0
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, ok := doc.Get("users")
	require.True(t, ok)

	// Check field type hints
	assert.Equal(t, "int", block.Fields[0].TypeHint)
	assert.Equal(t, "string", block.Fields[1].TypeHint)
	assert.Equal(t, "bool", block.Fields[2].TypeHint)
	assert.Equal(t, "float", block.Fields[3].TypeHint)

	// Check values
	row := block.Rows[0]
	id, _ := row["id"].AsInt()
	assert.Equal(t, int64(1), id)

	active, ok := row["active"].AsBool()
	assert.True(t, ok)
	assert.True(t, active)

	score, ok := row["score"].AsFloat()
	assert.True(t, ok)
	assert.Equal(t, 95.5, score)
}

func TestParseQuotedStrings(t *testing.T) {
	input := `
table.users
id name email
1 "Alice Smith" alice@example.com
2 "Bob \"The Builder\" Jones" bob@example.com
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("users")
	name1, _ := block.Rows[0]["name"].AsString()
	assert.Equal(t, "Alice Smith", name1)

	name2, _ := block.Rows[1]["name"].AsString()
	assert.Equal(t, `Bob "The Builder" Jones`, name2)
}

func TestParseNullValues(t *testing.T) {
	input := `
table.users
id name email
1 Alice ~
2 ~ null
3 Charlie NULL
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("users")
	assert.True(t, block.Rows[0]["email"].IsNull())
	assert.True(t, block.Rows[1]["name"].IsNull())
	assert.True(t, block.Rows[1]["email"].IsNull())
	assert.True(t, block.Rows[2]["email"].IsNull())
}

func TestParseReferences(t *testing.T) {
	input := `
table.orders
id user_id product
1 :1 Widget
2 :user:42 Gadget
3 :OWNS:5 Gizmo
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("orders")

	// Simple reference
	ref1, ok := block.Rows[0]["user_id"].AsRef()
	assert.True(t, ok)
	assert.Equal(t, "1", ref1.ID)
	assert.Empty(t, ref1.Namespace)
	assert.Empty(t, ref1.Relationship)
	assert.Equal(t, ":1", ref1.ToISON())

	// Namespaced reference
	ref2, ok := block.Rows[1]["user_id"].AsRef()
	assert.True(t, ok)
	assert.Equal(t, "42", ref2.ID)
	assert.Equal(t, "user", ref2.Namespace)
	assert.Empty(t, ref2.Relationship)
	assert.Equal(t, ":user:42", ref2.ToISON())

	// Relationship reference
	ref3, ok := block.Rows[2]["user_id"].AsRef()
	assert.True(t, ok)
	assert.Equal(t, "5", ref3.ID)
	assert.Equal(t, "OWNS", ref3.Relationship)
	assert.True(t, ref3.IsRelationship())
	assert.Equal(t, ":OWNS:5", ref3.ToISON())
}

func TestParseObjectBlock(t *testing.T) {
	input := `
object.config
key value
debug true
timeout 30
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, ok := doc.Get("config")
	require.True(t, ok)
	assert.Equal(t, "object", block.Kind)
	assert.Len(t, block.Rows, 2)
}

func TestParseMultipleBlocks(t *testing.T) {
	input := `
table.users
id name
1 Alice

table.orders
id user_id
O1 :1

object.meta
version 1.0
`
	doc, err := Parse(input)
	require.NoError(t, err)

	assert.Len(t, doc.Blocks, 3)
	assert.Equal(t, []string{"users", "orders", "meta"}, doc.Order)

	_, ok := doc.Get("users")
	assert.True(t, ok)
	_, ok = doc.Get("orders")
	assert.True(t, ok)
	_, ok = doc.Get("meta")
	assert.True(t, ok)
}

func TestParseSummaryRow(t *testing.T) {
	input := `
table.sales
product amount
Widget 100
Gadget 200
---
total 300
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("sales")
	assert.Len(t, block.Rows, 2)
	assert.NotNil(t, block.SummaryRow)

	total, ok := block.SummaryRow["amount"].AsInt()
	assert.True(t, ok)
	assert.Equal(t, int64(300), total)
}

func TestParseComments(t *testing.T) {
	input := `
# This is a comment
table.users
# Field definitions
id name
# Row 1
1 Alice
# Row 2
2 Bob
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("users")
	assert.Len(t, block.Rows, 2)
}

func TestDumps(t *testing.T) {
	doc := NewDocument()
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddRow(Row{
		"id":   Int(1),
		"name": String("Alice"),
	})
	block.AddRow(Row{
		"id":   Int(2),
		"name": String("Bob"),
	})
	doc.AddBlock(block)

	output := Dumps(doc)
	assert.Contains(t, output, "table.users")
	assert.Contains(t, output, "id:int")
	assert.Contains(t, output, "name:string")
	assert.Contains(t, output, "1 Alice")
	assert.Contains(t, output, "2 Bob")
}

func TestRoundtrip(t *testing.T) {
	input := `table.users
id:int name:string active:bool
1 Alice true
2 Bob false
`
	doc, err := Parse(input)
	require.NoError(t, err)

	output := Dumps(doc)
	doc2, err := Parse(output)
	require.NoError(t, err)

	block1, _ := doc.Get("users")
	block2, _ := doc2.Get("users")

	assert.Equal(t, len(block1.Rows), len(block2.Rows))
	for i := range block1.Rows {
		for k, v := range block1.Rows[i] {
			assert.Equal(t, v.Interface(), block2.Rows[i][k].Interface())
		}
	}
}

func TestDumpsISONL(t *testing.T) {
	doc := NewDocument()
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddRow(Row{"id": Int(1), "name": String("Alice")})
	block.AddRow(Row{"id": Int(2), "name": String("Bob")})
	doc.AddBlock(block)

	output := DumpsISONL(doc)
	lines := strings.Split(strings.TrimSpace(output), "\n")
	assert.Len(t, lines, 2)
	assert.Contains(t, lines[0], "table.users|id:int name:string|1 Alice")
	assert.Contains(t, lines[1], "table.users|id:int name:string|2 Bob")
}

func TestParseISONL(t *testing.T) {
	input := `table.users|id:int name:string|1 Alice
table.users|id:int name:string|2 Bob
table.orders|id product|O1 Widget`

	doc, err := ParseISONL(input)
	require.NoError(t, err)

	users, ok := doc.Get("users")
	require.True(t, ok)
	assert.Len(t, users.Rows, 2)

	orders, ok := doc.Get("orders")
	require.True(t, ok)
	assert.Len(t, orders.Rows, 1)
}

func TestToJSON(t *testing.T) {
	input := `
table.users
id:int name:string active:bool
1 Alice true
2 Bob false
`
	jsonStr, err := ToJSON(input)
	require.NoError(t, err)

	var data map[string]interface{}
	err = json.Unmarshal([]byte(jsonStr), &data)
	require.NoError(t, err)

	users, ok := data["users"].([]interface{})
	require.True(t, ok)
	assert.Len(t, users, 2)

	user1 := users[0].(map[string]interface{})
	assert.Equal(t, float64(1), user1["id"])
	assert.Equal(t, "Alice", user1["name"])
	assert.Equal(t, true, user1["active"])
}

func TestFromJSON(t *testing.T) {
	jsonStr := `{
		"users": [
			{"id": 1, "name": "Alice", "active": true},
			{"id": 2, "name": "Bob", "active": false}
		]
	}`

	doc, err := FromJSON(jsonStr)
	require.NoError(t, err)

	block, ok := doc.Get("users")
	require.True(t, ok)
	assert.Len(t, block.Rows, 2)

	id, _ := block.Rows[0]["id"].AsInt()
	assert.Equal(t, int64(1), id)
}

func TestValueTypes(t *testing.T) {
	// Test Null
	nullVal := Null()
	assert.Equal(t, TypeNull, nullVal.Type)
	assert.True(t, nullVal.IsNull())
	assert.Nil(t, nullVal.Interface())

	// Test Bool
	boolVal := Bool(true)
	assert.Equal(t, TypeBool, boolVal.Type)
	b, ok := boolVal.AsBool()
	assert.True(t, ok)
	assert.True(t, b)

	// Test Int
	intVal := Int(42)
	assert.Equal(t, TypeInt, intVal.Type)
	i, ok := intVal.AsInt()
	assert.True(t, ok)
	assert.Equal(t, int64(42), i)

	// Test Float
	floatVal := Float(3.14)
	assert.Equal(t, TypeFloat, floatVal.Type)
	f, ok := floatVal.AsFloat()
	assert.True(t, ok)
	assert.Equal(t, 3.14, f)

	// Int can be converted to float
	f, ok = intVal.AsFloat()
	assert.True(t, ok)
	assert.Equal(t, float64(42), f)

	// Test String
	strVal := String("hello")
	assert.Equal(t, TypeString, strVal.Type)
	s, ok := strVal.AsString()
	assert.True(t, ok)
	assert.Equal(t, "hello", s)

	// Test Reference
	refVal := Ref(Reference{ID: "1", Namespace: "user"})
	assert.Equal(t, TypeReference, refVal.Type)
	r, ok := refVal.AsRef()
	assert.True(t, ok)
	assert.Equal(t, "1", r.ID)
	assert.Equal(t, "user", r.Namespace)
}

func TestValueToISON(t *testing.T) {
	assert.Equal(t, "~", Null().ToISON())
	assert.Equal(t, "true", Bool(true).ToISON())
	assert.Equal(t, "false", Bool(false).ToISON())
	assert.Equal(t, "42", Int(42).ToISON())
	assert.Equal(t, "3.14", Float(3.14).ToISON())
	assert.Equal(t, "hello", String("hello").ToISON())
	assert.Equal(t, `"hello world"`, String("hello world").ToISON())
	assert.Equal(t, `"with \"quotes\""`, String(`with "quotes"`).ToISON())
	assert.Equal(t, ":1", Ref(Reference{ID: "1"}).ToISON())
	assert.Equal(t, ":user:1", Ref(Reference{ID: "1", Namespace: "user"}).ToISON())
	assert.Equal(t, ":OWNS:1", Ref(Reference{ID: "1", Relationship: "OWNS"}).ToISON())
}

func TestReferenceGetNamespace(t *testing.T) {
	ref1 := Reference{ID: "1"}
	assert.Empty(t, ref1.GetNamespace())

	ref2 := Reference{ID: "1", Namespace: "user"}
	assert.Equal(t, "user", ref2.GetNamespace())

	ref3 := Reference{ID: "1", Relationship: "OWNS"}
	assert.Equal(t, "OWNS", ref3.GetNamespace())
}

func TestBlockToDict(t *testing.T) {
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddRow(Row{"id": Int(1), "name": String("Alice")})

	dict := block.ToDict()
	assert.Equal(t, "table", dict["kind"])
	assert.Equal(t, "users", dict["name"])

	fields := dict["fields"].([]map[string]interface{})
	assert.Len(t, fields, 2)
	assert.Equal(t, "id", fields[0]["name"])
	assert.Equal(t, "int", fields[0]["typeHint"])

	rows := dict["rows"].([]map[string]interface{})
	assert.Len(t, rows, 1)
	assert.Equal(t, int64(1), rows[0]["id"])
}

func TestDocumentToDict(t *testing.T) {
	doc := NewDocument()
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddRow(Row{"id": Int(1)})
	doc.AddBlock(block)

	dict := doc.ToDict()
	users, ok := dict["users"].(map[string]interface{})
	assert.True(t, ok)
	assert.Equal(t, "table", users["kind"])
}

func TestEscapeSequences(t *testing.T) {
	input := `
table.data
id text
1 "line1\nline2"
2 "tab\there"
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("data")
	text1, _ := block.Rows[0]["text"].AsString()
	assert.Equal(t, "line1\nline2", text1)

	text2, _ := block.Rows[1]["text"].AsString()
	assert.Equal(t, "tab\there", text2)
}

func TestEmptyDocument(t *testing.T) {
	doc, err := Parse("")
	require.NoError(t, err)
	assert.Empty(t, doc.Blocks)
}

func TestOnlyComments(t *testing.T) {
	input := `
# Comment 1
# Comment 2
`
	doc, err := Parse(input)
	require.NoError(t, err)
	assert.Empty(t, doc.Blocks)
}

func TestTypeInference(t *testing.T) {
	input := `
table.data
a b c d e
42 3.14 true false hello
`
	doc, err := Parse(input)
	require.NoError(t, err)

	block, _ := doc.Get("data")
	row := block.Rows[0]

	// Integer
	assert.Equal(t, TypeInt, row["a"].Type)

	// Float
	assert.Equal(t, TypeFloat, row["b"].Type)

	// Booleans
	assert.Equal(t, TypeBool, row["c"].Type)
	assert.Equal(t, TypeBool, row["d"].Type)

	// String
	assert.Equal(t, TypeString, row["e"].Type)
}

func TestReferenceMarshalJSON(t *testing.T) {
	ref := Reference{ID: "42", Namespace: "user"}
	data, err := json.Marshal(ref)
	require.NoError(t, err)

	var result map[string]interface{}
	err = json.Unmarshal(data, &result)
	require.NoError(t, err)

	assert.Equal(t, "42", result["_ref"])
	assert.Equal(t, "user", result["_namespace"])
}

func TestValueMarshalJSON(t *testing.T) {
	// Test various value types
	tests := []struct {
		val      Value
		expected string
	}{
		{Null(), "null"},
		{Bool(true), "true"},
		{Bool(false), "false"},
		{Int(42), "42"},
		{Float(3.14), "3.14"},
		{String("hello"), `"hello"`},
	}

	for _, test := range tests {
		data, err := json.Marshal(test.val)
		require.NoError(t, err)
		assert.Equal(t, test.expected, string(data))
	}
}

func TestGetFieldNames(t *testing.T) {
	block := NewBlock("table", "test")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddField("active", "bool")

	names := block.GetFieldNames()
	assert.Equal(t, []string{"id", "name", "active"}, names)
}

// ==================== New Feature Tests ====================

func TestLoadDump(t *testing.T) {
	tmpfile := t.TempDir() + "/test.ison"

	doc := NewDocument()
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddRow(Row{"id": Int(1), "name": String("Alice")})
	doc.AddBlock(block)

	err := Dump(doc, tmpfile)
	require.NoError(t, err)

	loaded, err := Load(tmpfile)
	require.NoError(t, err)

	users, ok := loaded.Get("users")
	require.True(t, ok)
	assert.Len(t, users.Rows, 1)
	name, _ := users.Rows[0]["name"].AsString()
	assert.Equal(t, "Alice", name)
}

func TestLoadDumpISONL(t *testing.T) {
	tmpfile := t.TempDir() + "/test.isonl"

	doc := NewDocument()
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddRow(Row{"id": Int(1), "name": String("Alice")})
	block.AddRow(Row{"id": Int(2), "name": String("Bob")})
	doc.AddBlock(block)

	err := DumpISONL(doc, tmpfile)
	require.NoError(t, err)

	loaded, err := LoadISONL(tmpfile)
	require.NoError(t, err)

	users, ok := loaded.Get("users")
	require.True(t, ok)
	assert.Len(t, users.Rows, 2)
}

func TestISONToISONL(t *testing.T) {
	isonText := "table.users\nid:int name:string\n1 Alice\n2 Bob"

	isonlText, err := ISONToISONL(isonText)
	require.NoError(t, err)

	lines := strings.Split(strings.TrimSpace(isonlText), "\n")
	assert.Len(t, lines, 2)
	assert.Contains(t, lines[0], "table.users|")
	assert.Contains(t, lines[0], "1 Alice")
	assert.Contains(t, lines[1], "2 Bob")
}

func TestISONLToISON(t *testing.T) {
	isonlText := "table.users|id:int name:string|1 Alice\ntable.users|id:int name:string|2 Bob"

	isonText, err := ISONLToISON(isonlText)
	require.NoError(t, err)

	assert.Contains(t, isonText, "table.users")
	assert.Contains(t, isonText, "id:int name:string")
	assert.Contains(t, isonText, "1 Alice")
	assert.Contains(t, isonText, "2 Bob")
}

func TestDumpsWithOptions(t *testing.T) {
	doc := NewDocument()
	block := NewBlock("table", "users")
	block.AddField("id", "int")
	block.AddField("name", "string")
	block.AddRow(Row{"id": Int(1), "name": String("Alice")})
	block.AddRow(Row{"id": Int(2), "name": String("Bob")})
	doc.AddBlock(block)

	opts := DumpsOptions{
		AlignColumns: false,
		Delimiter:    "\t",
	}
	output := DumpsWithOptions(doc, opts)
	assert.Contains(t, output, "id:int\tname:string")
	assert.Contains(t, output, "1\tAlice")
}

func TestISONLStream(t *testing.T) {
	input := "table.users|id:int name:string|1 Alice\ntable.users|id:int name:string|2 Bob\ntable.orders|id product|O1 Widget"

	reader := strings.NewReader(input)
	ch := ISONLStream(reader)

	records := []ISONLRecord{}
	for record := range ch {
		records = append(records, record)
	}

	assert.Len(t, records, 3)
	assert.Equal(t, "users", records[0].Name)
	assert.Equal(t, "orders", records[2].Name)

	name, ok := records[0].Values["name"].AsString()
	assert.True(t, ok)
	assert.Equal(t, "Alice", name)
}

func TestFromDict(t *testing.T) {
	data := map[string]interface{}{
		"users": []interface{}{
			map[string]interface{}{"id": 1, "name": "Alice", "active": true},
			map[string]interface{}{"id": 2, "name": "Bob", "active": false},
		},
	}

	doc := FromDict(data)

	users, ok := doc.Get("users")
	require.True(t, ok)
	assert.Equal(t, "table", users.Kind)
	assert.Len(t, users.Rows, 2)
}

func TestFromDictWithAutoRefs(t *testing.T) {
	data := map[string]interface{}{
		"orders": []interface{}{
			map[string]interface{}{"id": 1, "customer_id": 42, "product": "Widget"},
		},
		"customers": []interface{}{
			map[string]interface{}{"id": 42, "name": "Alice"},
		},
	}

	opts := FromDictOptions{
		AutoRefs:   true,
		SmartOrder: true,
	}
	doc := FromDictWithOptions(data, opts)

	orders, ok := doc.Get("orders")
	require.True(t, ok)

	custID := orders.Rows[0]["customer_id"]
	ref, ok := custID.AsRef()
	assert.True(t, ok)
	assert.Equal(t, "42", ref.ID)
}

func TestSmartOrderFields(t *testing.T) {
	fields := []string{"email", "customer_id", "name", "id", "status"}
	ordered := smartOrderFields(fields)

	assert.Equal(t, "id", ordered[0])
	assert.Equal(t, "name", ordered[1])
	assert.Equal(t, "customer_id", ordered[len(ordered)-1])
}

func TestDefaultDumpsOptions(t *testing.T) {
	opts := DefaultDumpsOptions()
	assert.False(t, opts.AlignColumns)
	assert.Equal(t, " ", opts.Delimiter)
}

func TestDefaultFromDictOptions(t *testing.T) {
	opts := DefaultFromDictOptions()
	assert.False(t, opts.AutoRefs)
	assert.False(t, opts.SmartOrder)
}
