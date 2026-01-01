// Package ison provides a parser and serializer for the ISON (Interchange Simple Object Notation) format.
// ISON is a minimal, token-efficient data format optimized for LLMs and Agentic AI workflows.
package ison

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// Version is the current version of the ison-go package
const Version = "1.0.0"

// ValueType represents the type of an ISON value
type ValueType int

const (
	TypeNull ValueType = iota
	TypeBool
	TypeInt
	TypeFloat
	TypeString
	TypeReference
)

// Reference represents an ISON reference (e.g., :1, :user:42, :OWNS:5)
type Reference struct {
	ID           string
	Namespace    string
	Relationship string
}

// ToISON converts the reference back to ISON format
func (r Reference) ToISON() string {
	if r.Relationship != "" {
		return fmt.Sprintf(":%s:%s", r.Relationship, r.ID)
	}
	if r.Namespace != "" {
		return fmt.Sprintf(":%s:%s", r.Namespace, r.ID)
	}
	return fmt.Sprintf(":%s", r.ID)
}

// IsRelationship returns true if this is a relationship reference (uppercase namespace)
func (r Reference) IsRelationship() bool {
	return r.Relationship != ""
}

// GetNamespace returns the namespace or relationship name
func (r Reference) GetNamespace() string {
	if r.Relationship != "" {
		return r.Relationship
	}
	return r.Namespace
}

// String returns the string representation of the reference
func (r Reference) String() string {
	return r.ToISON()
}

// MarshalJSON implements json.Marshaler for Reference
func (r Reference) MarshalJSON() ([]byte, error) {
	return json.Marshal(map[string]interface{}{
		"_ref":         r.ID,
		"_namespace":   r.Namespace,
		"_relationship": r.Relationship,
	})
}

// Value represents an ISON value which can be null, bool, int, float, string, or reference
type Value struct {
	Type      ValueType
	BoolVal   bool
	IntVal    int64
	FloatVal  float64
	StringVal string
	RefVal    Reference
}

// Null creates a null Value
func Null() Value {
	return Value{Type: TypeNull}
}

// Bool creates a boolean Value
func Bool(v bool) Value {
	return Value{Type: TypeBool, BoolVal: v}
}

// Int creates an integer Value
func Int(v int64) Value {
	return Value{Type: TypeInt, IntVal: v}
}

// Float creates a float Value
func Float(v float64) Value {
	return Value{Type: TypeFloat, FloatVal: v}
}

// String creates a string Value
func String(v string) Value {
	return Value{Type: TypeString, StringVal: v}
}

// Ref creates a reference Value
func Ref(r Reference) Value {
	return Value{Type: TypeReference, RefVal: r}
}

// IsNull returns true if the value is null
func (v Value) IsNull() bool {
	return v.Type == TypeNull
}

// AsBool returns the boolean value
func (v Value) AsBool() (bool, bool) {
	if v.Type == TypeBool {
		return v.BoolVal, true
	}
	return false, false
}

// AsInt returns the integer value
func (v Value) AsInt() (int64, bool) {
	if v.Type == TypeInt {
		return v.IntVal, true
	}
	return 0, false
}

// AsFloat returns the float value
func (v Value) AsFloat() (float64, bool) {
	if v.Type == TypeFloat {
		return v.FloatVal, true
	}
	if v.Type == TypeInt {
		return float64(v.IntVal), true
	}
	return 0, false
}

// AsString returns the string value
func (v Value) AsString() (string, bool) {
	if v.Type == TypeString {
		return v.StringVal, true
	}
	return "", false
}

// AsRef returns the reference value
func (v Value) AsRef() (Reference, bool) {
	if v.Type == TypeReference {
		return v.RefVal, true
	}
	return Reference{}, false
}

// Interface returns the Go interface{} representation of the value
func (v Value) Interface() interface{} {
	switch v.Type {
	case TypeNull:
		return nil
	case TypeBool:
		return v.BoolVal
	case TypeInt:
		return v.IntVal
	case TypeFloat:
		return v.FloatVal
	case TypeString:
		return v.StringVal
	case TypeReference:
		return v.RefVal
	default:
		return nil
	}
}

// ToISON converts the value to its ISON string representation
func (v Value) ToISON() string {
	switch v.Type {
	case TypeNull:
		return "~"
	case TypeBool:
		if v.BoolVal {
			return "true"
		}
		return "false"
	case TypeInt:
		return strconv.FormatInt(v.IntVal, 10)
	case TypeFloat:
		return strconv.FormatFloat(v.FloatVal, 'f', -1, 64)
	case TypeString:
		if strings.ContainsAny(v.StringVal, " \t\n\"") || v.StringVal == "" {
			escaped := strings.ReplaceAll(v.StringVal, "\\", "\\\\")
			escaped = strings.ReplaceAll(escaped, "\"", "\\\"")
			escaped = strings.ReplaceAll(escaped, "\n", "\\n")
			escaped = strings.ReplaceAll(escaped, "\t", "\\t")
			return fmt.Sprintf("\"%s\"", escaped)
		}
		return v.StringVal
	case TypeReference:
		return v.RefVal.ToISON()
	default:
		return "~"
	}
}

// MarshalJSON implements json.Marshaler for Value
func (v Value) MarshalJSON() ([]byte, error) {
	return json.Marshal(v.Interface())
}

// FieldInfo represents information about a field/column in an ISON block
type FieldInfo struct {
	Name     string
	TypeHint string // "int", "float", "bool", "string", "ref", "computed", or ""
}

// Row represents a single row in an ISON block
type Row map[string]Value

// Block represents an ISON block (table or object)
type Block struct {
	Kind       string      // "table", "object", or "meta"
	Name       string      // Block name (e.g., "users", "config")
	Fields     []FieldInfo // Field definitions in order
	Rows       []Row       // Data rows
	SummaryRow Row         // Summary row after ---
}

// NewBlock creates a new Block with the given kind and name
func NewBlock(kind, name string) *Block {
	return &Block{
		Kind:   kind,
		Name:   name,
		Fields: []FieldInfo{},
		Rows:   []Row{},
	}
}

// AddField adds a field to the block
func (b *Block) AddField(name, typeHint string) {
	b.Fields = append(b.Fields, FieldInfo{Name: name, TypeHint: typeHint})
}

// AddRow adds a row to the block
func (b *Block) AddRow(row Row) {
	b.Rows = append(b.Rows, row)
}

// GetFieldNames returns the field names in order
func (b *Block) GetFieldNames() []string {
	names := make([]string, len(b.Fields))
	for i, f := range b.Fields {
		names[i] = f.Name
	}
	return names
}

// ToDict converts the block to a map representation
func (b *Block) ToDict() map[string]interface{} {
	result := map[string]interface{}{
		"kind": b.Kind,
		"name": b.Name,
	}

	// Fields with type hints
	fields := make([]map[string]interface{}, len(b.Fields))
	for i, f := range b.Fields {
		fields[i] = map[string]interface{}{
			"name":     f.Name,
			"typeHint": f.TypeHint,
		}
	}
	result["fields"] = fields

	// Rows as list of maps
	rows := make([]map[string]interface{}, len(b.Rows))
	for i, row := range b.Rows {
		rowMap := make(map[string]interface{})
		for k, v := range row {
			rowMap[k] = v.Interface()
		}
		rows[i] = rowMap
	}
	result["rows"] = rows

	if b.SummaryRow != nil {
		summary := make(map[string]interface{})
		for k, v := range b.SummaryRow {
			summary[k] = v.Interface()
		}
		result["summary"] = summary
	}

	return result
}

// Document represents a parsed ISON document containing multiple blocks
type Document struct {
	Blocks map[string]*Block
	Order  []string // Block names in order of appearance
}

// NewDocument creates a new empty Document
func NewDocument() *Document {
	return &Document{
		Blocks: make(map[string]*Block),
		Order:  []string{},
	}
}

// AddBlock adds a block to the document
func (d *Document) AddBlock(block *Block) {
	if _, exists := d.Blocks[block.Name]; !exists {
		d.Order = append(d.Order, block.Name)
	}
	d.Blocks[block.Name] = block
}

// Get returns a block by name
func (d *Document) Get(name string) (*Block, bool) {
	block, ok := d.Blocks[name]
	return block, ok
}

// ToDict converts the document to a map representation
func (d *Document) ToDict() map[string]interface{} {
	result := make(map[string]interface{})
	for name, block := range d.Blocks {
		result[name] = block.ToDict()
	}
	return result
}

// ToJSON converts the document to JSON
func (d *Document) ToJSON() (string, error) {
	result := make(map[string]interface{})
	for name, block := range d.Blocks {
		rows := make([]map[string]interface{}, len(block.Rows))
		for i, row := range block.Rows {
			rowMap := make(map[string]interface{})
			for k, v := range row {
				rowMap[k] = v.Interface()
			}
			rows[i] = rowMap
		}
		result[name] = rows
	}
	bytes, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return "", err
	}
	return string(bytes), nil
}

// Parser handles parsing ISON text into Document structures
type Parser struct {
	text  string
	lines []string
	pos   int
}

// Parse parses an ISON string into a Document
func Parse(text string) (*Document, error) {
	p := &Parser{
		text:  text,
		lines: splitLines(text),
		pos:   0,
	}
	return p.parse()
}

// Load loads and parses an ISON file
func Load(path string) (*Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(string(data))
}

// DumpsOptions configures serialization behavior
type DumpsOptions struct {
	AlignColumns bool   // Pad columns for visual alignment
	Delimiter    string // Column separator (default: " ")
}

// DefaultDumpsOptions returns default serialization options
func DefaultDumpsOptions() DumpsOptions {
	return DumpsOptions{
		AlignColumns: false,
		Delimiter:    " ",
	}
}

// Dump serializes a Document and writes it to a file
func Dump(doc *Document, path string) error {
	text := Dumps(doc)
	return os.WriteFile(path, []byte(text), 0644)
}

// DumpWithOptions serializes a Document with options and writes to a file
func DumpWithOptions(doc *Document, path string, opts DumpsOptions) error {
	text := DumpsWithOptions(doc, opts)
	return os.WriteFile(path, []byte(text), 0644)
}

func splitLines(text string) []string {
	lines := strings.Split(text, "\n")
	result := []string{}
	for _, line := range lines {
		result = append(result, strings.TrimRight(line, "\r"))
	}
	return result
}

func (p *Parser) parse() (*Document, error) {
	doc := NewDocument()

	for p.pos < len(p.lines) {
		line := strings.TrimSpace(p.lines[p.pos])

		// Skip empty lines and comments
		if line == "" || strings.HasPrefix(line, "#") {
			p.pos++
			continue
		}

		// Check for block header
		if strings.Contains(line, ".") && !strings.HasPrefix(line, "\"") {
			parts := strings.SplitN(line, ".", 2)
			if len(parts) == 2 && isValidKind(parts[0]) {
				block, err := p.parseBlock(parts[0], parts[1])
				if err != nil {
					return nil, err
				}
				doc.AddBlock(block)
				continue
			}
		}

		p.pos++
	}

	return doc, nil
}

func isValidKind(kind string) bool {
	return kind == "table" || kind == "object" || kind == "meta"
}

func (p *Parser) parseBlock(kind, name string) (*Block, error) {
	block := NewBlock(kind, name)
	p.pos++

	// Parse field definitions (next non-empty, non-comment line)
	for p.pos < len(p.lines) {
		line := strings.TrimSpace(p.lines[p.pos])
		if line == "" || strings.HasPrefix(line, "#") {
			p.pos++
			continue
		}
		break
	}

	if p.pos >= len(p.lines) {
		return block, nil
	}

	// Parse fields
	fieldsLine := strings.TrimSpace(p.lines[p.pos])
	fields := tokenizeLine(fieldsLine)
	for _, field := range fields {
		name, typeHint := parseFieldDef(field)
		block.AddField(name, typeHint)
	}
	p.pos++

	// Parse rows
	inSummary := false
	for p.pos < len(p.lines) {
		line := strings.TrimSpace(p.lines[p.pos])

		// Empty line ends block
		if line == "" {
			p.pos++
			break
		}

		// Comment
		if strings.HasPrefix(line, "#") {
			p.pos++
			continue
		}

		// New block starts
		if strings.Contains(line, ".") && !strings.HasPrefix(line, "\"") {
			parts := strings.SplitN(line, ".", 2)
			if len(parts) == 2 && isValidKind(parts[0]) {
				break
			}
		}

		// Summary separator
		if line == "---" {
			inSummary = true
			p.pos++
			continue
		}

		// Parse row
		tokens := tokenizeLine(line)
		row := make(Row)
		for i, token := range tokens {
			if i < len(block.Fields) {
				fieldInfo := block.Fields[i]
				value := parseValue(token, fieldInfo.TypeHint)
				row[fieldInfo.Name] = value
			}
		}

		if inSummary {
			block.SummaryRow = row
		} else {
			block.AddRow(row)
		}
		p.pos++
	}

	return block, nil
}

func parseFieldDef(field string) (name, typeHint string) {
	if idx := strings.Index(field, ":"); idx > 0 {
		return field[:idx], field[idx+1:]
	}
	return field, ""
}

func tokenizeLine(line string) []string {
	tokens := []string{}
	current := strings.Builder{}
	inQuotes := false
	escaped := false

	for i := 0; i < len(line); i++ {
		ch := line[i]

		if escaped {
			switch ch {
			case 'n':
				current.WriteByte('\n')
			case 't':
				current.WriteByte('\t')
			case '"':
				current.WriteByte('"')
			case '\\':
				current.WriteByte('\\')
			default:
				current.WriteByte(ch)
			}
			escaped = false
			continue
		}

		if ch == '\\' && inQuotes {
			escaped = true
			continue
		}

		if ch == '"' {
			inQuotes = !inQuotes
			continue
		}

		if !inQuotes && (ch == ' ' || ch == '\t') {
			if current.Len() > 0 {
				tokens = append(tokens, current.String())
				current.Reset()
			}
			continue
		}

		current.WriteByte(ch)
	}

	if current.Len() > 0 {
		tokens = append(tokens, current.String())
	}

	return tokens
}

var refPattern = regexp.MustCompile(`^:([A-Z_]+):(.+)$|^:([a-z_][a-z0-9_]*):(.+)$|^:(.+)$`)

func parseValue(token string, typeHint string) Value {
	// Null
	if token == "~" || token == "null" || token == "NULL" {
		return Null()
	}

	// Boolean
	if token == "true" || token == "TRUE" {
		return Bool(true)
	}
	if token == "false" || token == "FALSE" {
		return Bool(false)
	}

	// Reference
	if strings.HasPrefix(token, ":") {
		ref := parseReference(token)
		return Ref(ref)
	}

	// Type hint handling
	switch typeHint {
	case "int":
		if v, err := strconv.ParseInt(token, 10, 64); err == nil {
			return Int(v)
		}
	case "float":
		if v, err := strconv.ParseFloat(token, 64); err == nil {
			return Float(v)
		}
	case "bool":
		if token == "true" || token == "1" {
			return Bool(true)
		}
		if token == "false" || token == "0" {
			return Bool(false)
		}
	case "string":
		return String(token)
	case "ref":
		if strings.HasPrefix(token, ":") {
			return Ref(parseReference(token))
		}
		return String(token)
	}

	// Auto-inference
	// Try integer
	if v, err := strconv.ParseInt(token, 10, 64); err == nil {
		return Int(v)
	}

	// Try float
	if v, err := strconv.ParseFloat(token, 64); err == nil {
		return Float(v)
	}

	// Default to string
	return String(token)
}

func parseReference(token string) Reference {
	if !strings.HasPrefix(token, ":") {
		return Reference{ID: token}
	}

	token = token[1:] // Remove leading :
	parts := strings.SplitN(token, ":", 2)

	if len(parts) == 1 {
		return Reference{ID: parts[0]}
	}

	namespace := parts[0]
	id := parts[1]

	// Check if it's a relationship (all uppercase)
	if strings.ToUpper(namespace) == namespace && len(namespace) > 0 {
		isUpper := true
		for _, r := range namespace {
			if r != '_' && (r < 'A' || r > 'Z') {
				isUpper = false
				break
			}
		}
		if isUpper {
			return Reference{ID: id, Relationship: namespace}
		}
	}

	return Reference{ID: id, Namespace: namespace}
}

// Dumps serializes a Document back to ISON format
func Dumps(doc *Document) string {
	return DumpsWithOptions(doc, DefaultDumpsOptions())
}

// DumpsWithOptions serializes a Document with specified options
func DumpsWithOptions(doc *Document, opts DumpsOptions) string {
	var sb strings.Builder
	delim := opts.Delimiter
	if delim == "" {
		delim = " "
	}

	for i, name := range doc.Order {
		if i > 0 {
			sb.WriteString("\n")
		}

		block := doc.Blocks[name]
		sb.WriteString(fmt.Sprintf("%s.%s\n", block.Kind, block.Name))

		// Write field headers
		for j, field := range block.Fields {
			if j > 0 {
				sb.WriteString(delim)
			}
			if field.TypeHint != "" {
				sb.WriteString(fmt.Sprintf("%s:%s", field.Name, field.TypeHint))
			} else {
				sb.WriteString(field.Name)
			}
		}
		sb.WriteString("\n")

		// Calculate column widths for alignment
		widths := make([]int, len(block.Fields))
		for i, field := range block.Fields {
			w := len(field.Name)
			if field.TypeHint != "" {
				w += len(field.TypeHint) + 1
			}
			widths[i] = w
		}
		for _, row := range block.Rows {
			for i, field := range block.Fields {
				if val, ok := row[field.Name]; ok {
					w := len(val.ToISON())
					if w > widths[i] {
						widths[i] = w
					}
				}
			}
		}

		// Write rows
		for _, row := range block.Rows {
			for j, field := range block.Fields {
				if j > 0 {
					sb.WriteString(delim)
				}
				if val, ok := row[field.Name]; ok {
					sb.WriteString(val.ToISON())
				} else {
					sb.WriteString("~")
				}
			}
			sb.WriteString("\n")
		}

		// Write summary if present
		if block.SummaryRow != nil {
			sb.WriteString("---\n")
			for j, field := range block.Fields {
				if j > 0 {
					sb.WriteString(delim)
				}
				if val, ok := block.SummaryRow[field.Name]; ok {
					sb.WriteString(val.ToISON())
				} else {
					sb.WriteString("~")
				}
			}
			sb.WriteString("\n")
		}
	}

	return sb.String()
}

func padRight(s string, width int) string {
	if len(s) >= width {
		return s
	}
	return s + strings.Repeat(" ", width-len(s))
}

// DumpsISONL serializes a Document to ISONL (line-based streaming format)
func DumpsISONL(doc *Document) string {
	var sb strings.Builder

	for _, name := range doc.Order {
		block := doc.Blocks[name]

		// Build field header
		fieldHeader := strings.Builder{}
		for i, field := range block.Fields {
			if i > 0 {
				fieldHeader.WriteString(" ")
			}
			if field.TypeHint != "" {
				fieldHeader.WriteString(fmt.Sprintf("%s:%s", field.Name, field.TypeHint))
			} else {
				fieldHeader.WriteString(field.Name)
			}
		}
		fields := fieldHeader.String()

		// Write each row as a separate line
		for _, row := range block.Rows {
			sb.WriteString(fmt.Sprintf("%s.%s|%s|", block.Kind, block.Name, fields))
			for i, field := range block.Fields {
				if i > 0 {
					sb.WriteString(" ")
				}
				if val, ok := row[field.Name]; ok {
					sb.WriteString(val.ToISON())
				} else {
					sb.WriteString("~")
				}
			}
			sb.WriteString("\n")
		}
	}

	return sb.String()
}

// ParseISONL parses ISONL (line-based streaming format)
func ParseISONL(text string) (*Document, error) {
	doc := NewDocument()
	lines := splitLines(text)

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		parts := strings.SplitN(line, "|", 3)
		if len(parts) != 3 {
			continue
		}

		// Parse block header
		header := parts[0]
		headerParts := strings.SplitN(header, ".", 2)
		if len(headerParts) != 2 {
			continue
		}
		kind := headerParts[0]
		name := headerParts[1]

		// Get or create block
		block, exists := doc.Get(name)
		if !exists {
			block = NewBlock(kind, name)
			doc.AddBlock(block)

			// Parse fields
			fieldTokens := tokenizeLine(parts[1])
			for _, field := range fieldTokens {
				fname, ftype := parseFieldDef(field)
				block.AddField(fname, ftype)
			}
		}

		// Parse row
		tokens := tokenizeLine(parts[2])
		row := make(Row)
		for i, token := range tokens {
			if i < len(block.Fields) {
				fieldInfo := block.Fields[i]
				value := parseValue(token, fieldInfo.TypeHint)
				row[fieldInfo.Name] = value
			}
		}
		block.AddRow(row)
	}

	return doc, nil
}

// LoadISONL loads and parses an ISONL file
func LoadISONL(path string) (*Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return ParseISONL(string(data))
}

// DumpISONL serializes a Document and writes it to an ISONL file
func DumpISONL(doc *Document, path string) error {
	text := DumpsISONL(doc)
	return os.WriteFile(path, []byte(text), 0644)
}

// ISONToISONL converts ISON format to ISONL format
func ISONToISONL(isonText string) (string, error) {
	doc, err := Parse(isonText)
	if err != nil {
		return "", err
	}
	return DumpsISONL(doc), nil
}

// ISONLToISON converts ISONL format to ISON format
func ISONLToISON(isonlText string) (string, error) {
	doc, err := ParseISONL(isonlText)
	if err != nil {
		return "", err
	}
	return Dumps(doc), nil
}

// ISONLRecord represents a single ISONL record (one line)
type ISONLRecord struct {
	Kind   string
	Name   string
	Fields []string
	Values map[string]Value
}

// ISONLStream provides channel-based streaming ISONL parsing
func ISONLStream(reader io.Reader) <-chan ISONLRecord {
	ch := make(chan ISONLRecord, 100)
	go func() {
		defer close(ch)
		scanner := bufio.NewScanner(reader)
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}

			parts := strings.SplitN(line, "|", 3)
			if len(parts) != 3 {
				continue
			}

			// Parse block header
			header := parts[0]
			headerParts := strings.SplitN(header, ".", 2)
			if len(headerParts) != 2 {
				continue
			}

			// Parse fields
			fieldTokens := tokenizeLine(parts[1])
			fields := make([]string, len(fieldTokens))
			fieldTypes := make([]string, len(fieldTokens))
			for i, field := range fieldTokens {
				fname, ftype := parseFieldDef(field)
				fields[i] = fname
				fieldTypes[i] = ftype
			}

			// Parse row
			tokens := tokenizeLine(parts[2])
			values := make(map[string]Value)
			for i, token := range tokens {
				if i < len(fields) {
					value := parseValue(token, fieldTypes[i])
					values[fields[i]] = value
				}
			}

			ch <- ISONLRecord{
				Kind:   headerParts[0],
				Name:   headerParts[1],
				Fields: fields,
				Values: values,
			}
		}
	}()
	return ch
}

// ToJSON converts an ISON string directly to JSON
func ToJSON(isonText string) (string, error) {
	doc, err := Parse(isonText)
	if err != nil {
		return "", err
	}
	return doc.ToJSON()
}

// FromJSON converts a JSON string to ISON Document
func FromJSON(jsonText string) (*Document, error) {
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(jsonText), &data); err != nil {
		return nil, err
	}

	doc := NewDocument()

	for name, value := range data {
		switch v := value.(type) {
		case []interface{}:
			// Array of objects = table
			block := NewBlock("table", name)

			// Get fields from first row
			if len(v) > 0 {
				if firstRow, ok := v[0].(map[string]interface{}); ok {
					for key := range firstRow {
						block.AddField(key, "")
					}
				}
			}

			// Add rows
			for _, item := range v {
				if rowData, ok := item.(map[string]interface{}); ok {
					row := make(Row)
					for key, val := range rowData {
						row[key] = interfaceToValue(val)
					}
					block.AddRow(row)
				}
			}

			doc.AddBlock(block)

		case map[string]interface{}:
			// Single object = object block
			block := NewBlock("object", name)
			for key := range v {
				block.AddField(key, "")
			}
			row := make(Row)
			for key, val := range v {
				row[key] = interfaceToValue(val)
			}
			block.AddRow(row)
			doc.AddBlock(block)
		}
	}

	return doc, nil
}

// FromDictOptions configures FromDict behavior
type FromDictOptions struct {
	AutoRefs   bool // Auto-detect and convert foreign keys to References
	SmartOrder bool // Reorder columns for optimal LLM comprehension
}

// DefaultFromDictOptions returns default FromDict options
func DefaultFromDictOptions() FromDictOptions {
	return FromDictOptions{
		AutoRefs:   false,
		SmartOrder: false,
	}
}

// smartOrderFields reorders fields for optimal LLM comprehension
// Order priority: id first, then names, then data, then references
func smartOrderFields(fields []string) []string {
	priorityNames := map[string]bool{
		"name": true, "title": true, "label": true,
		"description": true, "display_name": true, "full_name": true,
	}

	var idFields, nameFields, refFields, otherFields []string

	for _, field := range fields {
		fieldLower := strings.ToLower(field)
		if fieldLower == "id" {
			idFields = append(idFields, field)
		} else if priorityNames[fieldLower] {
			nameFields = append(nameFields, field)
		} else if strings.HasSuffix(fieldLower, "_id") && fieldLower != "id" {
			refFields = append(refFields, field)
		} else {
			otherFields = append(otherFields, field)
		}
	}

	result := make([]string, 0, len(fields))
	result = append(result, idFields...)
	result = append(result, nameFields...)
	result = append(result, otherFields...)
	result = append(result, refFields...)
	return result
}

// FromDict creates an ISON Document from a map
func FromDict(data map[string]interface{}) *Document {
	return FromDictWithOptions(data, DefaultFromDictOptions())
}

// FromDictWithOptions creates an ISON Document from a map with options
func FromDictWithOptions(data map[string]interface{}, opts FromDictOptions) *Document {
	doc := NewDocument()

	// Collect all table names for reference detection
	tableNames := make(map[string]bool)
	for name := range data {
		tableNames[name] = true
	}

	// Detect reference fields if auto_refs is enabled
	refFields := make(map[string]string)
	if opts.AutoRefs {
		for tableName, tableData := range data {
			if arr, ok := tableData.([]interface{}); ok && len(arr) > 0 {
				if firstRow, ok := arr[0].(map[string]interface{}); ok {
					for key := range firstRow {
						// Detect _id suffix pattern (e.g., customer_id -> customers)
						if strings.HasSuffix(key, "_id") && key != "id" {
							refType := key[:len(key)-3]
							if tableNames[refType+"s"] || tableNames[refType] {
								refFields[key] = refType
							}
						}
					}
				}
			}
			// Special case: nodes/edges graph pattern
			if tableName == "edges" && tableNames["nodes"] {
				refFields["source"] = "node"
				refFields["target"] = "node"
			}
		}
	}

	// Sort table names for consistent ordering
	names := make([]string, 0, len(data))
	for name := range data {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		content := data[name]
		switch v := content.(type) {
		case []interface{}:
			// Table with multiple rows
			if len(v) > 0 {
				if _, ok := v[0].(map[string]interface{}); ok {
					// Collect all unique fields
					fieldSet := make(map[string]bool)
					fieldOrder := []string{}
					for _, item := range v {
						if row, ok := item.(map[string]interface{}); ok {
							for key := range row {
								if !fieldSet[key] {
									fieldSet[key] = true
									fieldOrder = append(fieldOrder, key)
								}
							}
						}
					}

					// Apply smart ordering if enabled
					if opts.SmartOrder {
						fieldOrder = smartOrderFields(fieldOrder)
					}

					block := NewBlock("table", name)
					for _, field := range fieldOrder {
						block.AddField(field, "")
					}

					// Convert rows with references if auto_refs
					for _, item := range v {
						if rowData, ok := item.(map[string]interface{}); ok {
							row := make(Row)
							for key, val := range rowData {
								if opts.AutoRefs {
									if refType, isRef := refFields[key]; isRef {
										switch refVal := val.(type) {
										case int, int64, float64, string:
											row[key] = Ref(Reference{ID: fmt.Sprintf("%v", refVal), Namespace: refType})
											continue
										default:
											_ = refVal // suppress unused warning
										}
									}
								}
								row[key] = interfaceToValue(val)
							}
							block.AddRow(row)
						}
					}

					doc.AddBlock(block)
				}
			}

		case map[string]interface{}:
			// Single object = object block
			block := NewBlock("object", name)
			fields := make([]string, 0, len(v))
			for key := range v {
				fields = append(fields, key)
			}
			if opts.SmartOrder {
				fields = smartOrderFields(fields)
			}
			for _, key := range fields {
				block.AddField(key, "")
			}
			row := make(Row)
			for key, val := range v {
				row[key] = interfaceToValue(val)
			}
			block.AddRow(row)
			doc.AddBlock(block)
		}
	}

	return doc
}

func interfaceToValue(v interface{}) Value {
	switch val := v.(type) {
	case nil:
		return Null()
	case bool:
		return Bool(val)
	case float64:
		if val == float64(int64(val)) {
			return Int(int64(val))
		}
		return Float(val)
	case int:
		return Int(int64(val))
	case int64:
		return Int(val)
	case string:
		return String(val)
	default:
		return String(fmt.Sprintf("%v", val))
	}
}
