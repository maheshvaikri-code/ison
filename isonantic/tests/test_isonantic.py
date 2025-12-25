"""
ISONantic Test Suite

Comprehensive tests for ISONantic library.
"""

import pytest
from typing import List, Optional
from enum import Enum

from isonantic import (
    TableModel, ObjectModel, ISONDocument,
    Field, Reference, Nested,
    parse_ison, parse_ison_safe, parse_llm_output,
    validator, root_validator, computed,
    ValidationError, ISONReferenceError, LLMParseError,
    prompt_for_model, generate_schema,
)


# =============================================================================
# Test Models
# =============================================================================

class Team(TableModel):
    __ison_block__ = "table.teams"
    
    id: int = Field(primary_key=True)
    name: str
    budget: float = Field(ge=0, default=0.0)


class User(TableModel):
    __ison_block__ = "table.users"
    
    id: int = Field(primary_key=True)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")
    team: Reference[Team]
    active: bool = True
    
    @validator("email")
    def lowercase_email(cls, v):
        return v.lower()


class Config(ObjectModel):
    __ison_block__ = "object.config"
    
    timeout: int = Field(ge=0, default=30)
    debug: bool = False
    version: str = "1.0"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class Order(TableModel):
    __ison_block__ = "table.orders"
    
    id: int = Field(primary_key=True)
    customer: Reference[User]
    status: str = Field(choices=["pending", "shipped", "delivered"])
    total: float = Field(ge=0)


class MyDocument(ISONDocument):
    teams: List[Team]
    users: List[User]
    orders: List[Order] = []
    
    class Config:
        block_order = ["teams", "users", "orders"]


# =============================================================================
# Sample Data
# =============================================================================

SAMPLE_ISON = """
table.teams
id name budget
10 "AI Research" 500000.0
20 "Engineering" 750000.0

table.users
id name email team active
101 Mahesh mahesh@example.com :10 true
102 Alice alice@example.com :20 true
103 Bob bob@example.com :10 false

table.orders
id customer status total
1001 :101 pending 299.99
1002 :102 shipped 599.99
"""


# =============================================================================
# Basic Model Tests
# =============================================================================

class TestBasicModels:
    """Test basic model creation and validation"""
    
    def test_create_simple_model(self):
        """Test creating a simple model"""
        team = Team(id=1, name="Test Team")
        assert team.id == 1
        assert team.name == "Test Team"
        assert team.budget == 0.0  # Default
    
    def test_model_with_reference(self):
        """Test model with reference field"""
        ref = Reference(id="10")
        user = User(
            id=1,
            name="Test",
            email="test@example.com",
            team=ref
        )
        assert user.team.id == "10"
    
    def test_field_constraints(self):
        """Test field constraints validation"""
        # Valid
        team = Team(id=1, name="Test", budget=100.0)
        assert team.budget == 100.0
        
        # Invalid - negative budget
        with pytest.raises(ValidationError) as exc_info:
            Team(id=2, name="Test", budget=-100.0)
        
        errors = exc_info.value.errors()
        assert any("budget" in str(e["loc"]) for e in errors)
    
    def test_string_pattern_validation(self):
        """Test string pattern validation"""
        # Valid email
        user = User(
            id=1,
            name="Test",
            email="valid@email.com",
            team=Reference(id="1")
        )
        assert user.email == "valid@email.com"
        
        # Invalid email
        with pytest.raises(ValidationError):
            User(
                id=2,
                name="Test",
                email="invalid-email",
                team=Reference(id="1")
            )
    
    def test_min_max_length(self):
        """Test string length constraints"""
        # Valid
        user = User(
            id=1,
            name="A",  # min_length=1
            email="a@b.com",
            team=Reference(id="1")
        )
        assert user.name == "A"
        
        # Invalid - empty name
        with pytest.raises(ValidationError):
            User(
                id=2,
                name="",
                email="a@b.com",
                team=Reference(id="1")
            )
    
    def test_choices_validation(self):
        """Test choices constraint"""
        # Valid
        order = Order(
            id=1,
            customer=Reference(id="1"),
            status="pending",
            total=100.0
        )
        assert order.status == "pending"
        
        # Invalid status
        with pytest.raises(ValidationError):
            Order(
                id=2,
                customer=Reference(id="1"),
                status="invalid_status",
                total=100.0
            )


# =============================================================================
# Validator Tests
# =============================================================================

class TestValidators:
    """Test custom validators"""
    
    def test_field_validator(self):
        """Test field validator"""
        user = User(
            id=1,
            name="Test",
            email="TEST@EXAMPLE.COM",  # Uppercase
            team=Reference(id="1")
        )
        # Should be lowercased by validator
        assert user.email == "test@example.com"
    
    def test_root_validator(self):
        """Test root validator"""
        class DateRange(TableModel):
            __ison_block__ = "table.date_ranges"
            start: int
            end: int
            
            @root_validator
            def validate_range(cls, values):
                if values.get("start", 0) > values.get("end", 0):
                    raise ValueError("start must be <= end")
                return values
        
        # Valid
        dr = DateRange(start=1, end=10)
        assert dr.start == 1
        assert dr.end == 10
        
        # Invalid
        with pytest.raises(ValidationError):
            DateRange(start=10, end=1)
    
    def test_computed_field(self):
        """Test computed field"""
        class OrderSummary(TableModel):
            __ison_block__ = "table.summaries"
            subtotal: float
            tax_rate: float
            
            @computed
            def tax(self) -> float:
                return round(self.subtotal * self.tax_rate, 2)
            
            @computed
            def total(self) -> float:
                return round(self.subtotal + self.tax, 2)
        
        summary = OrderSummary(subtotal=100.0, tax_rate=0.08)
        assert summary.tax == 8.0
        assert summary.total == 108.0


# =============================================================================
# Parsing Tests
# =============================================================================

class TestParsing:
    """Test ISON parsing"""
    
    def test_parse_single_model(self):
        """Test parsing single model type"""
        ison = """
        table.teams
        id name budget
        1 "Test Team" 100.0
        2 "Other Team" 200.0
        """
        
        teams = parse_ison(ison, Team)
        assert len(teams) == 2
        assert teams[0].id == 1
        assert teams[0].name == "Test Team"
        assert teams[1].budget == 200.0
    
    def test_parse_with_references(self):
        """Test parsing model with references"""
        ison = """
        table.users
        id name email team active
        1 Alice alice@test.com :10 true
        """
        
        users = parse_ison(ison, User)
        assert len(users) == 1
        assert users[0].team.id == "10"
        assert isinstance(users[0].team, Reference)
    
    def test_parse_safe(self):
        """Test safe parsing with error recovery"""
        ison = """
        table.teams
        id name budget
        1 "Valid Team" 100.0
        2 "Invalid" -50.0
        3 "Another Valid" 200.0
        """
        
        result = parse_ison_safe(ison, Team)
        assert not result.success
        assert result.partial_data is not None
        # Should have valid teams
        valid_teams = result.partial_data
        assert len(valid_teams) == 2
    
    def test_parse_null_values(self):
        """Test parsing null values"""
        class OptionalFields(TableModel):
            __ison_block__ = "table.optional"
            id: int
            name: Optional[str] = None
        
        ison = """
        table.optional
        id name
        1 null
        2 "Has Name"
        """
        
        items = parse_ison(ison, OptionalFields)
        assert items[0].name is None
        assert items[1].name == "Has Name"


# =============================================================================
# Document Tests
# =============================================================================

class TestDocument:
    """Test document parsing and reference resolution"""
    
    def test_parse_document(self):
        """Test parsing full document"""
        doc = MyDocument.parse(SAMPLE_ISON)
        
        assert len(doc.teams) == 2
        assert len(doc.users) == 3
        assert len(doc.orders) == 2
    
    def test_reference_resolution(self):
        """Test resolving references"""
        doc = MyDocument.parse(SAMPLE_ISON)
        
        # Get first user
        user = doc.users[0]
        assert user.name == "Mahesh"
        
        # Resolve team reference
        team = user.team.resolve(doc)
        assert team.name == "AI Research"
    
    def test_reference_validation(self):
        """Test that invalid references are caught"""
        bad_ison = """
        table.teams
        id name budget
        10 "Team" 100.0
        
        table.users
        id name email team active
        1 Test test@test.com :999 true
        """
        
        with pytest.raises(ValidationError) as exc_info:
            MyDocument.parse(bad_ison)
        
        errors = exc_info.value.errors()
        assert any("reference" in str(e).lower() for e in errors)
    
    def test_document_serialization(self):
        """Test serializing document back to ISON"""
        doc = MyDocument.parse(SAMPLE_ISON)
        
        ison_output = doc.to_ison()
        
        # Should contain all blocks
        assert "table.teams" in ison_output
        assert "table.users" in ison_output
        assert "AI Research" in ison_output


# =============================================================================
# LLM Output Parsing Tests
# =============================================================================

class TestLLMParsing:
    """Test LLM output parsing"""
    
    def test_parse_clean_llm_output(self):
        """Test parsing clean LLM output"""
        llm_response = """
        table.teams
        id name budget
        1 "Generated Team" 50000.0
        """
        
        teams = parse_llm_output(llm_response, Team)
        assert len(teams) == 1
        assert teams[0].name == "Generated Team"
    
    def test_parse_llm_with_extra_text(self):
        """Test parsing LLM output with surrounding text"""
        llm_response = """
        Here's the data you requested:
        
        table.teams
        id name budget
        1 "My Team" 100.0
        
        Let me know if you need anything else!
        """
        
        teams = parse_llm_output(llm_response, Team)
        assert len(teams) == 1
        assert teams[0].name == "My Team"
    
    def test_parse_llm_code_block(self):
        """Test parsing LLM output in code block"""
        llm_response = """
        Here's the ISON data:
        
        ```ison
        table.teams
        id name budget
        1 "Code Block Team" 200.0
        ```
        """
        
        teams = parse_llm_output(llm_response, Team)
        assert len(teams) == 1
        assert teams[0].name == "Code Block Team"
    
    def test_llm_parse_error(self):
        """Test LLM parse error handling"""
        llm_response = "Sorry, I couldn't generate the data."
        
        with pytest.raises(LLMParseError) as exc_info:
            parse_llm_output(llm_response, Team)
        
        assert "No ISON block found" in str(exc_info.value)


# =============================================================================
# Schema Generation Tests
# =============================================================================

class TestSchemaGeneration:
    """Test schema generation"""
    
    def test_generate_model_schema(self):
        """Test generating schema for model"""
        schema = generate_schema(User)
        
        assert "meta.schema" in schema
        assert "table.columns" in schema
        assert "email" in schema
        assert "str" in schema
    
    def test_prompt_for_model(self):
        """Test generating LLM prompt"""
        prompt = prompt_for_model(Team)
        
        assert "table.teams" in prompt
        assert "id" in prompt
        assert "name" in prompt
        assert "<int>" in prompt
    
    def test_json_schema_generation(self):
        """Test JSON Schema generation for model"""
        schema = Team.model_json_schema()
        
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["title"] == "Team"
        assert schema["type"] == "object"
        assert "id" in schema["properties"]
        assert "name" in schema["properties"]
        assert schema["properties"]["id"]["type"] == "integer"
        assert schema["properties"]["name"]["type"] == "string"
        assert "id" in schema["required"]
        assert "name" in schema["required"]
    
    def test_json_schema_with_constraints(self):
        """Test JSON Schema includes constraints"""
        schema = Team.model_json_schema()
        
        # budget has ge=0 constraint
        budget_prop = schema["properties"]["budget"]
        assert budget_prop["type"] == "number"
        assert budget_prop["minimum"] == 0
        assert budget_prop["default"] == 0.0
    
    def test_json_schema_with_pattern(self):
        """Test JSON Schema includes pattern constraints"""
        schema = User.model_json_schema()
        
        email_prop = schema["properties"]["email"]
        assert "pattern" in email_prop
    
    def test_json_schema_with_choices(self):
        """Test JSON Schema includes enum for choices"""
        schema = Order.model_json_schema()
        
        status_prop = schema["properties"]["status"]
        assert "enum" in status_prop
        assert "pending" in status_prop["enum"]
    
    def test_json_schema_with_reference(self):
        """Test JSON Schema handles references"""
        schema = User.model_json_schema()
        
        team_prop = schema["properties"]["team"]
        assert team_prop["type"] == "string"
        assert "x-ison-ref" in team_prop
    
    def test_json_schema_json_output(self):
        """Test JSON Schema as JSON string"""
        import json
        schema_json = Team.model_json_schema_json()
        
        # Should be valid JSON
        parsed = json.loads(schema_json)
        assert parsed["title"] == "Team"
    
    def test_pydantic_v1_compatibility(self):
        """Test Pydantic v1 compatible aliases"""
        # .schema() should work like model_json_schema()
        schema1 = Team.schema()
        schema2 = Team.model_json_schema()
        assert schema1 == schema2
        
        # .schema_json() should work like model_json_schema_json()
        json1 = Team.schema_json()
        json2 = Team.model_json_schema_json()
        assert json1 == json2


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Test model serialization"""
    
    def test_model_to_dict(self):
        """Test converting model to dict"""
        team = Team(id=1, name="Test", budget=100.0)
        d = team.dict()
        
        assert d["id"] == 1
        assert d["name"] == "Test"
        assert d["budget"] == 100.0
    
    def test_model_with_reference_to_dict(self):
        """Test converting model with reference to dict"""
        user = User(
            id=1,
            name="Test",
            email="test@test.com",
            team=Reference(id="10")
        )
        d = user.dict()
        
        assert d["team"] == ":10"
    
    def test_model_to_ison_table(self):
        """Test serializing multiple models to ISON"""
        teams = [
            Team(id=1, name="Team A", budget=100.0),
            Team(id=2, name="Team B", budget=200.0),
        ]
        
        ison = Team.to_ison_table(teams)
        
        assert "table.teams" in ison
        assert "Team A" in ison
        assert "Team B" in ison
    
    def test_model_copy(self):
        """Test copying model with updates"""
        team = Team(id=1, name="Original", budget=100.0)
        updated = team.copy(update={"name": "Updated"})
        
        assert updated.id == 1
        assert updated.name == "Updated"
        assert team.name == "Original"  # Original unchanged


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_ison(self):
        """Test parsing empty ISON"""
        teams = parse_ison("", Team)
        assert teams == []
    
    def test_missing_required_field(self):
        """Test missing required field"""
        with pytest.raises(ValidationError):
            Team(name="No ID")  # id is required
    
    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored by default"""
        team = Team(id=1, name="Test", extra_field="ignored")
        assert not hasattr(team, "extra_field")
    
    def test_quoted_strings_with_spaces(self):
        """Test parsing quoted strings with spaces"""
        ison = """
        table.teams
        id name budget
        1 "Team With Spaces" 100.0
        """
        
        teams = parse_ison(ison, Team)
        assert teams[0].name == "Team With Spaces"
    
    def test_special_characters_in_strings(self):
        """Test special characters in strings"""
        ison = """
        table.teams
        id name budget
        1 "Team\\nWith\\tEscapes" 100.0
        """
        
        teams = parse_ison(ison, Team)
        assert "\n" in teams[0].name
        assert "\t" in teams[0].name


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
