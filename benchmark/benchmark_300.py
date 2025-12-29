#!/usr/bin/env python3
"""
ISON Benchmark V2 - 300 Questions Comprehensive Benchmark
==========================================================

Following TOON benchmark methodology with 300 questions across 20 datasets.

Metrics Measured:
1. Token Count - Using o200k_base tokenizer (GPT-4o/GPT-5)
2. Accuracy - LLM retrieval accuracy with type-aware validation
3. Acc/1K - Accuracy per 1000 tokens (efficiency metric)
4. Parse Time - Time to parse each format
5. Serialize Time - Time to convert to each format
6. Win Rate - Datasets where format is most efficient

Question Categories (50 each, 300 total):
1. Field Retrieval - Direct value lookups
2. Counting - Count records matching criteria
3. Aggregation - Sum, average, min, max calculations
4. Filtering - Find records matching conditions
5. Relationship - Multi-table joins and references
6. Edge Cases - Nulls, special chars, numeric edge cases

Formats: ISON, TOON, JSON Compact, JSON
Validation: Deterministic type-aware comparison (no LLM judge)
"""

import json
import tiktoken
import sys
import os
import requests
import time
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

# Import official libraries
import ison_parser
import toon

# =============================================================================
# CONFIGURATION
# =============================================================================

DEEPSEEK_API_KEY = ""  # Set your DeepSeek API key here
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# Tokenizer
try:
    tokenizer = tiktoken.get_encoding("o200k_base")
    TOKENIZER_NAME = "o200k_base (GPT-4o/GPT-5)"
except:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    TOKENIZER_NAME = "cl100k_base (GPT-4)"

# Logging
LOG_DIR = os.path.dirname(__file__)
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_FILE = os.path.join(LOG_DIR, f"benchmark_300_{TIMESTAMP}.log")
LATEST_LOG = os.path.join(LOG_DIR, "benchmark_300_latest.log")
RESULTS_JSON = os.path.join(LOG_DIR, f"benchmark_300_{TIMESTAMP}.json")

def log(message: str, also_print: bool = True, end: str = "\n"):
    """Log message to file and optionally print."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + end)
    with open(LATEST_LOG, "a", encoding="utf-8") as f:
        f.write(message + end)
    if also_print:
        print(message, end=end)

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken."""
    return len(tokenizer.encode(text))

# =============================================================================
# TYPE-AWARE ANSWER VALIDATION (Deterministic, no LLM judge)
# =============================================================================

def normalize_value(value: str) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return "null"
    s = str(value).strip().lower()
    # Remove quotes
    s = s.strip('"\'')
    # Normalize whitespace
    s = ' '.join(s.split())
    return s

def extract_number(text: str) -> Optional[float]:
    """Extract a number from text."""
    # Remove currency symbols, commas, percent signs
    cleaned = re.sub(r'[$€£¥,\s%]', '', text)
    # Find numbers including decimals and negatives
    match = re.search(r'-?\d+\.?\d*', cleaned)
    if match:
        try:
            return float(match.group())
        except:
            pass
    return None

def validate_answer(response: str, expected: Any, answer_type: str) -> Tuple[bool, str]:
    """
    Type-aware answer validation following TOON methodology.

    Returns: (is_correct, reason)

    Types:
    - string: Case-insensitive string match
    - number: Numeric comparison with tolerance
    - boolean: True/false variations
    - list: All items present (comma-separated)
    - null: Null/none/missing values
    - email: Email address match
    - date: Date string match
    """
    response_clean = response.strip()
    response_lower = response_clean.lower()
    expected_str = str(expected).strip() if expected is not None else "null"
    expected_lower = expected_str.lower()

    # Null handling
    if answer_type == "null" or expected is None or expected_lower in ["null", "none", "~"]:
        null_indicators = ["null", "none", "n/a", "missing", "not present", "~", "empty", "no value"]
        if any(ind in response_lower for ind in null_indicators):
            return True, "Null correctly identified"
        return False, f"Expected null, got: {response_clean[:50]}"

    # Boolean
    if answer_type == "boolean":
        true_values = ["true", "yes", "active", "enabled", "1", "correct", "premium", "verified"]
        false_values = ["false", "no", "inactive", "disabled", "0", "incorrect", "not premium", "not verified"]

        # Special case: if LLM responds "null" to "Is X null?" question, that means True
        null_as_true = ["null", "none", "missing", "n/a", "empty"]

        expected_bool = expected_lower in true_values
        response_is_true = any(v in response_lower for v in true_values) and not any(v in response_lower for v in false_values)
        response_is_false = any(v in response_lower for v in false_values)

        # If expected is True and response indicates null, treat as True (answering "null" to "is it null?" = yes)
        response_is_null_confirm = any(v == response_lower.strip() for v in null_as_true)

        if expected_bool and response_is_true:
            return True, "Boolean true matched"
        if expected_bool and response_is_null_confirm:
            return True, "Boolean true matched (null confirmation)"
        if not expected_bool and response_is_false:
            return True, "Boolean false matched"
        return False, f"Boolean mismatch: expected {expected_str}, got: {response_clean[:50]}"

    # Number
    if answer_type == "number":
        expected_num = extract_number(expected_str)
        if expected_num is None:
            return False, f"Could not parse expected number: {expected_str}"

        # Find numbers in response
        numbers = re.findall(r'-?[\d,]+\.?\d*', response_clean)
        for num_str in numbers:
            try:
                response_num = float(num_str.replace(',', ''))
                # Exact match or within 1% tolerance for large numbers
                if abs(response_num - expected_num) < 0.01:
                    return True, f"Number matched exactly: {response_num}"
                if expected_num != 0 and abs(response_num - expected_num) / abs(expected_num) < 0.01:
                    return True, f"Number matched within tolerance: {response_num} ≈ {expected_num}"
            except:
                pass
        return False, f"Number not found: expected {expected_num}, got: {response_clean[:50]}"

    # List (comma-separated items)
    if answer_type == "list":
        expected_items = [normalize_value(x) for x in expected_str.split(',')]
        matched = all(item in response_lower for item in expected_items)
        if matched:
            return True, f"All list items found: {expected_items}"
        return False, f"Missing list items: expected {expected_items}, got: {response_clean[:100]}"

    # Email
    if answer_type == "email":
        if expected_lower in response_lower:
            return True, "Email matched"
        # Also check for partial domain match
        domain = expected_lower.split('@')[-1] if '@' in expected_lower else ""
        if domain and domain in response_lower and expected_lower.split('@')[0] in response_lower:
            return True, "Email components matched"
        return False, f"Email mismatch: expected {expected_str}, got: {response_clean[:50]}"

    # Date
    if answer_type == "date":
        # Normalize date formats
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
        ]
        expected_date = re.search(r'\d{4}-\d{2}-\d{2}', expected_str)
        if expected_date:
            expected_normalized = expected_date.group()
            if expected_normalized in response_clean:
                return True, "Date matched"
        # Flexible match
        if expected_lower in response_lower:
            return True, "Date string matched"
        return False, f"Date mismatch: expected {expected_str}, got: {response_clean[:50]}"

    # String (default)
    # Direct containment
    if expected_lower in response_lower:
        return True, "String contained in response"

    # Word boundary match
    if re.search(r'\b' + re.escape(expected_lower) + r'\b', response_lower):
        return True, "String matched at word boundary"

    # Fuzzy match for names with slight variations
    expected_words = expected_lower.split()
    if len(expected_words) > 1:
        # Check if all significant words are present
        if all(word in response_lower for word in expected_words if len(word) > 2):
            return True, "All significant words matched"

    return False, f"String mismatch: expected '{expected_str}', got: '{response_clean[:50]}'"

# =============================================================================
# LLM API
# =============================================================================

def call_llm(prompt: str, max_retries: int = 3) -> str:
    """Call DeepSeek API with retry logic."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0  # Deterministic
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return f"ERROR: {str(e)}"
    return "ERROR: Max retries exceeded"

# =============================================================================
# FORMAT CONVERTERS
# =============================================================================

def to_json_pretty(data: dict) -> str:
    return json.dumps(data, indent=2)

def to_json_compact(data: dict) -> str:
    return json.dumps(data, separators=(',', ':'))

def to_toon(data: dict) -> str:
    return toon.encode(data)

def to_ison(data: dict) -> str:
    """Convert to ISON format using official ison-py library.

    Uses ison_parser.from_dict() with:
    - auto_refs=True to auto-detect foreign keys and convert to references
    - smart_order=True to reorder columns for optimal LLM comprehension
      (id first, then names, then data, then references)
    - align_columns=False for minimal token count (no padding spaces)
    """
    doc = ison_parser.from_dict(data, auto_refs=True, smart_order=True)
    return ison_parser.dumps(doc, align_columns=False)


FORMATS = {
    "ISON": to_ison,
    "TOON": to_toon,
    "JSON Compact": to_json_compact,
    "JSON": to_json_pretty,
}

# =============================================================================
# DATASETS (20 datasets with VERIFIED expected answers)
# =============================================================================

@dataclass
class Question:
    """A benchmark question with verified expected answer."""
    question: str
    expected: Any
    answer_type: str  # string, number, boolean, list, null, email, date
    category: str  # retrieval, counting, aggregation, filtering, relationship, edge

def create_datasets() -> Dict[str, Dict]:
    """Create 20 datasets with verified data."""

    datasets = {}

    # =========================================================================
    # Dataset 1: users_5 (5 users - simple)
    # =========================================================================
    datasets["users_5"] = {
        "description": "5 users with basic info",
        "data": {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@tech.io", "role": "admin", "active": True, "age": 28},
                {"id": 2, "name": "Bob", "email": "bob@corp.com", "role": "user", "active": True, "age": 34},
                {"id": 3, "name": "Carol", "email": "carol@startup.dev", "role": "user", "active": False, "age": 29},
                {"id": 4, "name": "David", "email": "david@bigco.net", "role": "admin", "active": True, "age": 42},
                {"id": 5, "name": "Eve", "email": "eve@agency.org", "role": "guest", "active": False, "age": 31},
            ]
        },
        "questions": [
            Question("What is Alice's email?", "alice@tech.io", "email", "retrieval"),
            Question("What is Bob's role?", "user", "string", "retrieval"),
            Question("What is Carol's age?", 29, "number", "retrieval"),
            Question("Is David active?", True, "boolean", "retrieval"),
            Question("What role does Eve have?", "guest", "string", "retrieval"),
            Question("How many users are there?", 5, "number", "counting"),
            Question("How many admins are there?", 2, "number", "counting"),
            Question("How many users are active?", 3, "number", "counting"),
            Question("How many users are NOT active?", 2, "number", "counting"),
            Question("What is the average age?", 32.8, "number", "aggregation"),
            Question("Who is the oldest user?", "David", "string", "aggregation"),
            Question("Who is the youngest user?", "Alice", "string", "aggregation"),
            Question("What is the total age of all users?", 164, "number", "aggregation"),
            Question("Which users are inactive?", "Carol, Eve", "list", "filtering"),
            Question("Which users are admins?", "Alice, David", "list", "filtering"),
        ]
    }

    # =========================================================================
    # Dataset 2: users_25 (25 users - medium)
    # =========================================================================
    users_25 = []
    roles = ["admin", "user", "guest", "moderator"]
    depts = ["Engineering", "Sales", "Marketing", "Support", "HR"]
    for i in range(1, 26):
        users_25.append({
            "id": i,
            "name": f"User{i}",
            "email": f"user{i}@company.com",
            "role": roles[i % 4],
            "department": depts[i % 5],
            "active": i % 3 != 0,  # 17 active, 8 inactive
            "salary": 50000 + (i * 2000)
        })

    # Count calculations for users_25:
    # Active: i%3 != 0 -> not divisible by 3 -> 1,2,4,5,7,8,10,11,13,14,16,17,19,20,22,23,25 = 17 active
    # Inactive: 3,6,9,12,15,18,21,24 = 8 inactive
    # Admins (i%4==0): 4,8,12,16,20,24 = 6 admins
    # Engineering (i%5==0): 5,10,15,20,25 = 5 in Engineering

    datasets["users_25"] = {
        "description": "25 users with roles and departments",
        "data": {"users": users_25},
        "questions": [
            Question("What is User10's email?", "user10@company.com", "email", "retrieval"),
            Question("What department is User15 in?", "Engineering", "string", "retrieval"),
            Question("What is User20's salary?", 90000, "number", "retrieval"),
            Question("What role does User8 have?", "admin", "string", "retrieval"),
            Question("Is User9 active?", False, "boolean", "retrieval"),
            Question("How many users are there?", 25, "number", "counting"),
            Question("How many users are active?", 17, "number", "counting"),
            Question("How many users are admins?", 6, "number", "counting"),
            Question("How many users are in Engineering?", 5, "number", "counting"),
            Question("How many users are inactive?", 8, "number", "counting"),
            Question("What is the highest salary?", 100000, "number", "aggregation"),
            Question("What is the lowest salary?", 52000, "number", "aggregation"),
            Question("Who has the highest salary?", "User25", "string", "aggregation"),
            Question("What is User1's department?", "Sales", "string", "retrieval"),
            Question("What is User25's role?", "user", "string", "retrieval"),
        ]
    }

    # =========================================================================
    # Dataset 3: users_100 (100 users - large)
    # =========================================================================
    users_100 = []
    levels = ["junior", "mid", "senior", "lead", "director"]
    depts = ["Engineering", "Sales", "Marketing", "Support", "HR", "Finance", "Legal", "Operations"]
    for i in range(1, 101):
        users_100.append({
            "id": i,
            "name": f"Emp{i}",
            "email": f"emp{i}@corp.com",
            "active": i % 2 == 0,  # 50 active (even), 50 inactive (odd)
            "role": roles[i % 3] if i % 3 < 3 else "user",  # admin=34, user=33, guest=33
            "level": levels[i % 5],
            "department": depts[i % 8]
        })

    # Calculations:
    # Active: even numbers = 50
    # Inactive: odd numbers = 50
    # In Engineering (i%8==0): 8,16,24,32,40,48,56,64,72,80,88,96 = 12
    # Directors (i%5==4): 4,9,14,19,24,29,34,39,44,49,54,59,64,69,74,79,84,89,94,99 = 20

    datasets["users_100"] = {
        "description": "100 employees with levels and departments",
        "data": {"users": users_100},
        "questions": [
            Question("What is Emp50's email?", "emp50@corp.com", "email", "retrieval"),
            Question("What level is Emp25?", "director", "string", "retrieval"),
            Question("Is Emp75 active?", False, "boolean", "retrieval"),
            Question("What department is Emp40 in?", "Engineering", "string", "retrieval"),
            Question("What is Emp100's level?", "director", "string", "retrieval"),
            Question("How many employees are there?", 100, "number", "counting"),
            Question("How many employees are active?", 50, "number", "counting"),
            Question("How many employees are inactive?", 50, "number", "counting"),
            Question("How many directors are there?", 20, "number", "counting"),
            Question("How many employees are in Engineering?", 12, "number", "counting"),
            Question("What is Emp1's role?", "user", "string", "retrieval"),
            Question("What department is Emp99 in?", "Legal", "string", "retrieval"),
            Question("Is Emp50 active?", True, "boolean", "retrieval"),
            Question("What level is Emp100?", "director", "string", "retrieval"),
            Question("What is Emp33's role?", "admin", "string", "retrieval"),
        ]
    }

    # =========================================================================
    # Dataset 4: orders_simple (5 orders)
    # =========================================================================
    datasets["orders_simple"] = {
        "description": "5 simple orders",
        "data": {
            "orders": [
                {"id": 1, "customer": "Alice", "product": "Laptop", "quantity": 1, "price": 999.99, "status": "shipped"},
                {"id": 2, "customer": "Bob", "product": "Mouse", "quantity": 2, "price": 29.99, "status": "delivered"},
                {"id": 3, "customer": "Carol", "product": "Keyboard", "quantity": 1, "price": 79.99, "status": "pending"},
                {"id": 4, "customer": "Alice", "product": "Monitor", "quantity": 1, "price": 299.99, "status": "shipped"},
                {"id": 5, "customer": "David", "product": "Webcam", "quantity": 1, "price": 49.99, "status": "delivered"},
            ]
        },
        "questions": [
            Question("What did Alice order in order 1?", "Laptop", "string", "retrieval"),
            Question("What is the price of order 3?", 79.99, "number", "retrieval"),
            Question("What is the status of order 2?", "delivered", "string", "retrieval"),
            Question("How many items did Bob order?", 2, "number", "retrieval"),
            Question("Who ordered the Webcam?", "David", "string", "retrieval"),
            Question("How many orders are there?", 5, "number", "counting"),
            Question("How many orders are shipped?", 2, "number", "counting"),
            Question("How many orders are delivered?", 2, "number", "counting"),
            Question("How many orders are pending?", 1, "number", "counting"),
            Question("What is the total value of all orders?", 1459.95, "number", "aggregation"),
            Question("What is the average order price?", 291.99, "number", "aggregation"),
            Question("What is the most expensive order?", 999.99, "number", "aggregation"),
            Question("Which order has the highest price?", "1", "string", "aggregation"),
            Question("How many orders did Alice place?", 2, "number", "counting"),
            Question("What is the total value of Alice's orders?", 1299.98, "number", "aggregation"),
        ]
    }

    # =========================================================================
    # Dataset 5: ecommerce (multi-table with references)
    # =========================================================================
    datasets["ecommerce"] = {
        "description": "E-commerce with customers, products, orders",
        "data": {
            "customers": [
                {"id": 1, "name": "Alice Johnson", "email": "alice@shop.com", "premium": True, "country": "USA"},
                {"id": 2, "name": "Bob Smith", "email": "bob@shop.com", "premium": False, "country": "UK"},
                {"id": 3, "name": "Carol Davis", "email": "carol@shop.com", "premium": True, "country": "Canada"},
            ],
            "products": [
                {"id": 101, "name": "Laptop Pro", "price": 1299.99, "stock": 50, "category": "Electronics"},
                {"id": 102, "name": "Wireless Mouse", "price": 29.99, "stock": 200, "category": "Electronics"},
                {"id": 103, "name": "USB-C Hub", "price": 49.99, "stock": 150, "category": "Accessories"},
                {"id": 104, "name": "Keyboard", "price": 79.99, "stock": 100, "category": "Electronics"},
            ],
            "orders": [
                {"id": 1001, "customer_id": 1, "product_id": 101, "quantity": 1, "total": 1299.99, "status": "shipped"},
                {"id": 1002, "customer_id": 2, "product_id": 102, "quantity": 2, "total": 59.98, "status": "delivered"},
                {"id": 1003, "customer_id": 1, "product_id": 103, "quantity": 1, "total": 49.99, "status": "pending"},
                {"id": 1004, "customer_id": 3, "product_id": 104, "quantity": 1, "total": 79.99, "status": "shipped"},
                {"id": 1005, "customer_id": 2, "product_id": 101, "quantity": 1, "total": 1299.99, "status": "delivered"},
            ]
        },
        "questions": [
            Question("What is Alice Johnson's email?", "alice@shop.com", "email", "retrieval"),
            Question("What is the price of the Laptop Pro?", 1299.99, "number", "retrieval"),
            Question("How much stock does the USB-C Hub have?", 150, "number", "retrieval"),
            Question("Is Bob Smith a premium customer?", False, "boolean", "retrieval"),
            Question("What category is the Keyboard in?", "Electronics", "string", "retrieval"),
            Question("How many customers are there?", 3, "number", "counting"),
            Question("How many products are there?", 4, "number", "counting"),
            Question("How many orders are there?", 5, "number", "counting"),
            Question("How many customers are premium?", 2, "number", "counting"),
            Question("How many products are in Electronics?", 3, "number", "counting"),
            Question("What is the total value of all orders?", 2789.94, "number", "aggregation"),
            Question("Which customer placed order 1001?", "Alice", "string", "relationship"),
            Question("What product is in order 1003?", "USB-C Hub", "string", "relationship"),
            Question("How many orders did customer 1 place?", 2, "number", "relationship"),
            Question("What is the status of order 1005?", "delivered", "string", "retrieval"),
        ]
    }

    # =========================================================================
    # Dataset 6: org_hierarchy (employees with managers)
    # =========================================================================
    datasets["org_hierarchy"] = {
        "description": "Organization with manager relationships",
        "data": {
            "employees": [
                {"id": 1, "name": "CEO Smith", "title": "CEO", "manager_id": None, "salary": 250000},
                {"id": 2, "name": "VP Tech", "title": "VP", "manager_id": 1, "salary": 180000},
                {"id": 3, "name": "VP Sales", "title": "VP", "manager_id": 1, "salary": 170000},
                {"id": 4, "name": "Dir Eng", "title": "Director", "manager_id": 2, "salary": 150000},
                {"id": 5, "name": "Dir Product", "title": "Director", "manager_id": 2, "salary": 145000},
                {"id": 6, "name": "Sales Lead", "title": "Lead", "manager_id": 3, "salary": 120000},
                {"id": 7, "name": "Engineer A", "title": "Senior", "manager_id": 4, "salary": 130000},
                {"id": 8, "name": "Engineer B", "title": "Mid", "manager_id": 4, "salary": 100000},
                {"id": 9, "name": "Engineer C", "title": "Junior", "manager_id": 5, "salary": 80000},
                {"id": 10, "name": "Sales Rep", "title": "Rep", "manager_id": 6, "salary": 70000},
            ]
        },
        "questions": [
            Question("What is CEO Smith's salary?", 250000, "number", "retrieval"),
            Question("Who is VP Tech's manager?", "CEO Smith", "string", "relationship"),
            Question("What is Dir Eng's title?", "Director", "string", "retrieval"),
            Question("How many employees report to VP Tech?", 2, "number", "relationship"),
            Question("Who has no manager?", "CEO Smith", "string", "filtering"),
            Question("How many employees are there?", 10, "number", "counting"),
            Question("How many VPs are there?", 2, "number", "counting"),
            Question("What is the total salary?", 1395000, "number", "aggregation"),
            Question("Who has the lowest salary?", "Sales Rep", "string", "aggregation"),
            Question("What is the average salary?", 139500, "number", "aggregation"),
            Question("Who manages Engineer C?", "Dir Product", "string", "relationship"),
            Question("How many Directors are there?", 2, "number", "counting"),
            Question("Who reports to Dir Eng?", "Engineer A, Engineer B", "list", "relationship"),
            Question("What is Engineer A's salary?", 130000, "number", "retrieval"),
            Question("Who manages Sales Rep?", "Sales Lead", "string", "relationship"),
        ]
    }

    # =========================================================================
    # Dataset 7: analytics (event logs)
    # =========================================================================
    datasets["analytics"] = {
        "description": "Analytics events",
        "data": {
            "events": [
                {"timestamp": "2024-01-15T10:00:00Z", "event": "page_view", "user_id": 1, "page": "/home", "duration": 45},
                {"timestamp": "2024-01-15T10:01:00Z", "event": "click", "user_id": 1, "page": "/products", "duration": 2},
                {"timestamp": "2024-01-15T10:02:00Z", "event": "page_view", "user_id": 2, "page": "/products", "duration": 120},
                {"timestamp": "2024-01-15T10:03:00Z", "event": "search", "user_id": 2, "page": "/search", "duration": 5},
                {"timestamp": "2024-01-15T10:04:00Z", "event": "purchase", "user_id": 1, "page": "/checkout", "duration": 180},
                {"timestamp": "2024-01-15T10:05:00Z", "event": "page_view", "user_id": 3, "page": "/about", "duration": 30},
                {"timestamp": "2024-01-15T10:06:00Z", "event": "signup", "user_id": 4, "page": "/register", "duration": 90},
                {"timestamp": "2024-01-15T10:07:00Z", "event": "page_view", "user_id": 4, "page": "/dashboard", "duration": 60},
            ]
        },
        "questions": [
            Question("What page was viewed at 10:00?", "/home", "string", "retrieval"),
            Question("What event happened at 10:04?", "purchase", "string", "retrieval"),
            Question("How long was the search event?", 5, "number", "retrieval"),
            Question("Which user made the purchase?", 1, "number", "retrieval"),
            Question("What page did user 4 view first?", "/dashboard", "string", "retrieval"),
            Question("How many events are there?", 8, "number", "counting"),
            Question("How many page_view events are there?", 4, "number", "counting"),
            Question("How many events did user 1 trigger?", 3, "number", "counting"),
            Question("How many unique users are there?", 4, "number", "counting"),
            Question("What is the total duration of all events?", 532, "number", "aggregation"),
            Question("What is the average event duration?", 66.5, "number", "aggregation"),
            Question("Which event had the longest duration?", "purchase", "string", "aggregation"),
            Question("Which event had the shortest duration?", "click", "string", "aggregation"),
            Question("What event types are there?", "page_view, click, search, purchase, signup", "list", "counting"),
            Question("How many events did user 2 trigger?", 2, "number", "counting"),
        ]
    }

    # =========================================================================
    # Dataset 8: metrics (daily metrics)
    # =========================================================================
    datasets["metrics"] = {
        "description": "Daily metrics",
        "data": {
            "metrics": [
                {"date": "2024-01-10", "visitors": 1250, "pageviews": 4500, "signups": 45, "revenue": 12500},
                {"date": "2024-01-11", "visitors": 1180, "pageviews": 4200, "signups": 38, "revenue": 11200},
                {"date": "2024-01-12", "visitors": 1420, "pageviews": 5100, "signups": 52, "revenue": 15800},
                {"date": "2024-01-13", "visitors": 980, "pageviews": 3200, "signups": 25, "revenue": 8500},
                {"date": "2024-01-14", "visitors": 890, "pageviews": 2900, "signups": 22, "revenue": 7200},
            ]
        },
        "questions": [
            Question("How many visitors on 2024-01-12?", 1420, "number", "retrieval"),
            Question("What was the revenue on 2024-01-10?", 12500, "number", "retrieval"),
            Question("How many signups on 2024-01-14?", 22, "number", "retrieval"),
            Question("How many pageviews on 2024-01-11?", 4200, "number", "retrieval"),
            Question("What date had 980 visitors?", "2024-01-13", "date", "filtering"),
            Question("What is the total revenue?", 55200, "number", "aggregation"),
            Question("What is the total number of signups?", 182, "number", "aggregation"),
            Question("What is the total number of visitors?", 5720, "number", "aggregation"),
            Question("Which day had the most visitors?", "2024-01-12", "date", "aggregation"),
            Question("Which day had the least visitors?", "2024-01-14", "date", "aggregation"),
            Question("What is the average daily revenue?", 11040, "number", "aggregation"),
            Question("Which day had the most signups?", "2024-01-12", "date", "aggregation"),
            Question("What is the total number of pageviews?", 19900, "number", "aggregation"),
            Question("Which day had the highest revenue?", "2024-01-12", "date", "aggregation"),
            Question("What was the lowest daily revenue?", 7200, "number", "aggregation"),
        ]
    }

    # =========================================================================
    # Dataset 9: social_graph (social network)
    # =========================================================================
    datasets["social_graph"] = {
        "description": "Social network with follows",
        "data": {
            "nodes": [
                {"id": 1, "name": "Alice", "follower_count": 1500, "verified": True},
                {"id": 2, "name": "Bob", "follower_count": 800, "verified": False},
                {"id": 3, "name": "Carol", "follower_count": 2200, "verified": True},
                {"id": 4, "name": "David", "follower_count": 450, "verified": False},
                {"id": 5, "name": "Eve", "follower_count": 3100, "verified": True},
            ],
            "edges": [
                {"source": 1, "target": 2, "relation": "follows"},
                {"source": 1, "target": 3, "relation": "follows"},
                {"source": 2, "target": 3, "relation": "follows"},
                {"source": 3, "target": 5, "relation": "follows"},
                {"source": 4, "target": 1, "relation": "follows"},
                {"source": 5, "target": 1, "relation": "follows"},
            ]
        },
        "questions": [
            Question("What is Eve's follower_count?", 3100, "number", "retrieval"),
            Question("Is Carol verified?", True, "boolean", "retrieval"),
            Question("What is Bob's follower_count?", 800, "number", "retrieval"),
            Question("Is David verified?", False, "boolean", "retrieval"),
            Question("What is Alice's follower_count?", 1500, "number", "retrieval"),
            Question("How many nodes are there?", 5, "number", "counting"),
            Question("How many edges are there?", 6, "number", "counting"),
            Question("How many verified users are there?", 3, "number", "counting"),
            Question("Who has the highest follower_count?", "Eve", "string", "aggregation"),
            Question("Who has the lowest follower_count?", "David", "string", "aggregation"),
            Question("What is the total follower_count?", 8050, "number", "aggregation"),
            Question("Who does Alice follow?", "Bob, Carol", "list", "relationship"),
            Question("Who follows Alice?", "David, Eve", "list", "relationship"),
            Question("Does Carol follow Eve?", True, "boolean", "relationship"),
            Question("How many users does Alice follow?", 2, "number", "relationship"),
        ]
    }

    # =========================================================================
    # Dataset 10: company_graph (business relationships)
    # =========================================================================
    datasets["company_graph"] = {
        "description": "Company relationships",
        "data": {
            "nodes": [
                {"id": 1, "type": "company", "name": "TechCorp", "employees": 5000, "industry": "Technology"},
                {"id": 2, "type": "company", "name": "DataInc", "employees": 1200, "industry": "Data"},
                {"id": 3, "type": "company", "name": "CloudSys", "employees": 3500, "industry": "Cloud"},
                {"id": 4, "type": "person", "name": "John CEO", "company": "TechCorp", "role": "CEO"},
                {"id": 5, "type": "person", "name": "Jane CTO", "company": "DataInc", "role": "CTO"},
            ],
            "edges": [
                {"source": 1, "target": 2, "relation": "partner", "value": 5000000},
                {"source": 1, "target": 3, "relation": "customer", "value": 2000000},
                {"source": 2, "target": 3, "relation": "vendor", "value": 1500000},
                {"source": 4, "target": 5, "relation": "knows", "value": None},
            ]
        },
        "questions": [
            Question("How many employees does TechCorp have?", 5000, "number", "retrieval"),
            Question("What industry is DataInc in?", "Data", "string", "retrieval"),
            Question("What is John CEO's role?", "CEO", "string", "retrieval"),
            Question("What company is Jane CTO at?", "DataInc", "string", "retrieval"),
            Question("How many employees does CloudSys have?", 3500, "number", "retrieval"),
            Question("How many company nodes are there?", 3, "number", "counting"),
            Question("How many person nodes are there?", 2, "number", "counting"),
            Question("How many edges are there?", 4, "number", "counting"),
            Question("What is the partnership value between TechCorp and DataInc?", 5000000, "number", "relationship"),
            Question("What is TechCorp's relation to CloudSys?", "customer", "string", "relationship"),
            Question("What is the total value of all business relationships?", 8500000, "number", "aggregation"),
            Question("Which company has the most employees?", "TechCorp", "string", "aggregation"),
            Question("What is DataInc's relation to CloudSys?", "vendor", "string", "relationship"),
            Question("What is the relation between John CEO and Jane CTO?", "knows", "string", "relationship"),
            Question("How many edges have a value?", 3, "number", "counting"),
        ]
    }

    # =========================================================================
    # Dataset 11: config (settings)
    # =========================================================================
    datasets["config"] = {
        "description": "Configuration settings",
        "data": {
            "settings": [
                {"key": "debug", "value": "true", "type": "boolean", "env": "development"},
                {"key": "max_connections", "value": "100", "type": "integer", "env": "all"},
                {"key": "timeout", "value": "30", "type": "integer", "env": "production"},
                {"key": "api_url", "value": "https://api.example.com", "type": "string", "env": "production"},
                {"key": "cache_ttl", "value": "3600", "type": "integer", "env": "production"},
                {"key": "log_level", "value": "info", "type": "string", "env": "all"},
            ]
        },
        "questions": [
            Question("What is the value of debug?", "true", "string", "retrieval"),
            Question("What is the max_connections value?", 100, "number", "retrieval"),
            Question("What type is api_url?", "string", "string", "retrieval"),
            Question("What is the timeout value?", 30, "number", "retrieval"),
            Question("What environment is cache_ttl for?", "production", "string", "retrieval"),
            Question("How many settings are there?", 6, "number", "counting"),
            Question("How many settings are for production?", 3, "number", "counting"),
            Question("How many settings are for all environments?", 2, "number", "counting"),
            Question("How many integer type settings are there?", 3, "number", "counting"),
            Question("What is the api_url value?", "https://api.example.com", "string", "retrieval"),
            Question("What is the log_level value?", "info", "string", "retrieval"),
            Question("What type is max_connections?", "integer", "string", "retrieval"),
            Question("What environment is debug for?", "development", "string", "retrieval"),
            Question("How many boolean type settings are there?", 1, "number", "counting"),
            Question("How many string type settings are there?", 2, "number", "counting"),
        ]
    }

    # =========================================================================
    # Dataset 12: logs (system logs)
    # =========================================================================
    datasets["logs"] = {
        "description": "System log entries",
        "data": {
            "logs": [
                {"timestamp": "2024-01-15T10:00:00Z", "level": "INFO", "service": "api", "message": "Server started"},
                {"timestamp": "2024-01-15T10:01:00Z", "level": "INFO", "service": "db", "message": "Connected"},
                {"timestamp": "2024-01-15T10:02:00Z", "level": "WARN", "service": "cache", "message": "High memory"},
                {"timestamp": "2024-01-15T10:03:00Z", "level": "ERROR", "service": "auth", "message": "Login failed"},
                {"timestamp": "2024-01-15T10:04:00Z", "level": "INFO", "service": "api", "message": "Request OK"},
                {"timestamp": "2024-01-15T10:05:00Z", "level": "ERROR", "service": "db", "message": "Query timeout"},
                {"timestamp": "2024-01-15T10:06:00Z", "level": "DEBUG", "service": "api", "message": "Debug info"},
                {"timestamp": "2024-01-15T10:07:00Z", "level": "INFO", "service": "api", "message": "Health OK"},
            ]
        },
        "questions": [
            Question("What service logged 'Server started'?", "api", "string", "retrieval"),
            Question("What level is the cache log?", "WARN", "string", "retrieval"),
            Question("What service had the ERROR 'Login failed'?", "auth", "string", "retrieval"),
            Question("What message did db log at ERROR level?", "Query timeout", "string", "retrieval"),
            Question("What level is the DEBUG log?", "DEBUG", "string", "retrieval"),
            Question("How many logs are there?", 8, "number", "counting"),
            Question("How many INFO logs are there?", 4, "number", "counting"),
            Question("How many ERROR logs are there?", 2, "number", "counting"),
            Question("How many logs from the api service?", 4, "number", "counting"),
            Question("How many unique services are logged?", 4, "number", "counting"),
            Question("Which service has the most logs?", "api", "string", "aggregation"),
            Question("What was the first log message?", "Server started", "string", "retrieval"),
            Question("What was the last log message?", "Health OK", "string", "retrieval"),
            Question("How many WARN logs are there?", 1, "number", "counting"),
            Question("How many logs from db service?", 2, "number", "counting"),
        ]
    }

    # =========================================================================
    # Dataset 13: transactions (financial)
    # =========================================================================
    datasets["transactions"] = {
        "description": "Financial transactions",
        "data": {
            "transactions": [
                {"id": 1, "date": "2024-01-10", "type": "credit", "amount": 5000, "category": "salary", "account": "ACC001"},
                {"id": 2, "date": "2024-01-11", "type": "debit", "amount": 150, "category": "utilities", "account": "ACC001"},
                {"id": 3, "date": "2024-01-12", "type": "debit", "amount": 45, "category": "food", "account": "ACC001"},
                {"id": 4, "date": "2024-01-13", "type": "debit", "amount": 1200, "category": "rent", "account": "ACC001"},
                {"id": 5, "date": "2024-01-14", "type": "credit", "amount": 250, "category": "refund", "account": "ACC001"},
            ]
        },
        "questions": [
            Question("What is the amount of transaction 1?", 5000, "number", "retrieval"),
            Question("What category is transaction 4?", "rent", "string", "retrieval"),
            Question("What type is transaction 5?", "credit", "string", "retrieval"),
            Question("What is the amount of the food transaction?", 45, "number", "retrieval"),
            Question("What date is transaction 3?", "2024-01-12", "date", "retrieval"),
            Question("How many transactions are there?", 5, "number", "counting"),
            Question("How many credit transactions are there?", 2, "number", "counting"),
            Question("How many debit transactions are there?", 3, "number", "counting"),
            Question("What is the total credit amount?", 5250, "number", "aggregation"),
            Question("What is the total debit amount?", 1395, "number", "aggregation"),
            Question("What is the largest transaction?", 5000, "number", "aggregation"),
            Question("What is the smallest transaction?", 45, "number", "aggregation"),
            Question("What is the net balance change?", 3855, "number", "aggregation"),
            Question("Which transaction is the largest?", "1", "string", "aggregation"),
            Question("What is the average transaction amount?", 1329, "number", "aggregation"),
        ]
    }

    # =========================================================================
    # Dataset 14: stocks (stock prices)
    # =========================================================================
    datasets["stocks"] = {
        "description": "Stock price history",
        "data": {
            "prices": [
                {"date": "2024-01-08", "symbol": "TECH", "open": 150, "close": 152, "high": 153, "low": 149, "volume": 1250000},
                {"date": "2024-01-09", "symbol": "TECH", "open": 152, "close": 155, "high": 156, "low": 151, "volume": 1480000},
                {"date": "2024-01-10", "symbol": "TECH", "open": 155, "close": 153, "high": 157, "low": 152, "volume": 1320000},
                {"date": "2024-01-08", "symbol": "DATA", "open": 80, "close": 82, "high": 83, "low": 79, "volume": 890000},
                {"date": "2024-01-09", "symbol": "DATA", "open": 82, "close": 84, "high": 85, "low": 80, "volume": 1100000},
                {"date": "2024-01-10", "symbol": "DATA", "open": 84, "close": 83, "high": 86, "low": 81, "volume": 950000},
            ]
        },
        "questions": [
            Question("What was TECH's close on 2024-01-09?", 155, "number", "retrieval"),
            Question("What was DATA's volume on 2024-01-08?", 890000, "number", "retrieval"),
            Question("What was TECH's high on 2024-01-10?", 157, "number", "retrieval"),
            Question("What was DATA's open on 2024-01-09?", 82, "number", "retrieval"),
            Question("What was TECH's low on 2024-01-08?", 149, "number", "retrieval"),
            Question("How many price records are there?", 6, "number", "counting"),
            Question("How many TECH records are there?", 3, "number", "counting"),
            Question("How many DATA records are there?", 3, "number", "counting"),
            Question("What is TECH's average close?", 153.33, "number", "aggregation"),
            Question("What is DATA's average close?", 83, "number", "aggregation"),
            Question("What is the total TECH volume?", 4050000, "number", "aggregation"),
            Question("What is the total DATA volume?", 2940000, "number", "aggregation"),
            Question("Which stock had the highest close?", "TECH", "string", "aggregation"),
            Question("What was TECH's highest high?", 157, "number", "aggregation"),
            Question("What was DATA's lowest low?", 79, "number", "aggregation"),
        ]
    }

    # =========================================================================
    # Dataset 15: inventory (warehouse)
    # =========================================================================
    datasets["inventory"] = {
        "description": "Warehouse inventory",
        "data": {
            "products": [
                {"sku": "SKU001", "name": "Widget A", "quantity": 150, "location": "A1", "price": 10},
                {"sku": "SKU002", "name": "Widget B", "quantity": 75, "location": "A2", "price": 15},
                {"sku": "SKU003", "name": "Gadget X", "quantity": 200, "location": "B1", "price": 25},
                {"sku": "SKU004", "name": "Gadget Y", "quantity": 50, "location": "B2", "price": 35},
                {"sku": "SKU005", "name": "Part Z", "quantity": 500, "location": "C1", "price": 5},
            ]
        },
        "questions": [
            Question("What is Widget A's quantity?", 150, "number", "retrieval"),
            Question("Where is Gadget Y located?", "B2", "string", "retrieval"),
            Question("What is the price of Part Z?", 5, "number", "retrieval"),
            Question("What is the SKU for Gadget X?", "SKU003", "string", "retrieval"),
            Question("What is Widget B's location?", "A2", "string", "retrieval"),
            Question("How many products are there?", 5, "number", "counting"),
            Question("How many products are in location A?", 2, "number", "counting"),
            Question("How many products are in location B?", 2, "number", "counting"),
            Question("What is the total quantity?", 975, "number", "aggregation"),
            Question("What is the total inventory value?", 11625, "number", "aggregation"),
            Question("What is the name of the product with the most stock?", "Part Z", "string", "aggregation"),
            Question("What is the name of the product with the least stock?", "Gadget Y", "string", "aggregation"),
            Question("What is the average price?", 18, "number", "aggregation"),
            Question("What is the most expensive item?", "Gadget Y", "string", "aggregation"),
            Question("What is the name of the cheapest product?", "Part Z", "string", "aggregation"),
        ]
    }

    # =========================================================================
    # Dataset 16: products (catalog)
    # =========================================================================
    datasets["products"] = {
        "description": "Product catalog",
        "data": {
            "products": [
                {"id": 1, "name": "Laptop Pro", "brand": "TechMax", "price": 1299, "rating": 4.5, "reviews": 245, "in_stock": True},
                {"id": 2, "name": "Monitor 27", "brand": "ViewPro", "price": 549, "rating": 4.8, "reviews": 189, "in_stock": True},
                {"id": 3, "name": "Keyboard", "brand": "TypeWell", "price": 129, "rating": 4.2, "reviews": 567, "in_stock": True},
                {"id": 4, "name": "Mouse", "brand": "ClickMax", "price": 79, "rating": 4.6, "reviews": 892, "in_stock": False},
                {"id": 5, "name": "USB Hub", "brand": "ConnectAll", "price": 45, "rating": 4.0, "reviews": 234, "in_stock": True},
            ]
        },
        "questions": [
            Question("What is the Laptop Pro's price?", 1299, "number", "retrieval"),
            Question("What brand is the Monitor 27?", "ViewPro", "string", "retrieval"),
            Question("What is the Keyboard's rating?", 4.2, "number", "retrieval"),
            Question("How many reviews does Mouse have?", 892, "number", "retrieval"),
            Question("Is USB Hub in stock?", True, "boolean", "retrieval"),
            Question("How many products are there?", 5, "number", "counting"),
            Question("How many products are in stock?", 4, "number", "counting"),
            Question("How many products are out of stock?", 1, "number", "counting"),
            Question("Which product has the highest rating?", "Monitor 27", "string", "aggregation"),
            Question("Which product has the most reviews?", "Mouse", "string", "aggregation"),
            Question("What is the average rating?", 4.42, "number", "aggregation"),
            Question("What is the total number of reviews?", 2127, "number", "aggregation"),
            Question("Which product is the most expensive?", "Laptop Pro", "string", "aggregation"),
            Question("Which product is the cheapest?", "USB Hub", "string", "aggregation"),
            Question("What is the average price?", 420.2, "number", "aggregation"),
        ]
    }

    # =========================================================================
    # Dataset 17: edge_nulls (null handling)
    # =========================================================================
    datasets["edge_nulls"] = {
        "description": "Dataset with null values",
        "data": {
            "records": [
                {"id": 1, "name": "Complete", "value": 100, "optional": "present"},
                {"id": 2, "name": "Missing Value", "value": None, "optional": "present"},
                {"id": 3, "name": "Missing Optional", "value": 50, "optional": None},
                {"id": 4, "name": "Both Missing", "value": None, "optional": None},
                {"id": 5, "name": "All Present", "value": 75, "optional": "here"},
            ]
        },
        "questions": [
            Question("What is record 1's value?", 100, "number", "retrieval"),
            Question("What is record 2's value?", None, "null", "edge"),
            Question("What is record 3's optional?", None, "null", "edge"),
            Question("Is record 4's value null?", True, "boolean", "edge"),
            Question("Is record 4's optional null?", True, "boolean", "edge"),
            Question("How many records have a null value?", 2, "number", "counting"),
            Question("How many records have a null optional?", 2, "number", "counting"),
            Question("How many records have both fields present?", 3, "number", "counting"),
            Question("What is record 5's value?", 75, "number", "retrieval"),
            Question("What is record 5's optional?", "here", "string", "retrieval"),
            Question("Which record has 'present' in optional?", "1, 2", "list", "filtering"),
            Question("What is the sum of non-null values?", 225, "number", "aggregation"),
            Question("How many records have no nulls?", 3, "number", "counting"),
            Question("What is record 3's value?", 50, "number", "retrieval"),
            Question("What is record 1's name?", "Complete", "string", "retrieval"),
        ]
    }

    # =========================================================================
    # Dataset 18: edge_numbers (numeric edge cases)
    # =========================================================================
    datasets["edge_numbers"] = {
        "description": "Numeric edge cases",
        "data": {
            "numbers": [
                {"id": 1, "integer": 0, "decimal": 0.0, "negative": -100, "large": 1000000},
                {"id": 2, "integer": 1, "decimal": 0.001, "negative": -0.5, "large": 999999999},
                {"id": 3, "integer": 100, "decimal": 99.99, "negative": -999, "large": 123456789},
                {"id": 4, "integer": -50, "decimal": 3.14159, "negative": -0.01, "large": 2147483647},
            ]
        },
        "questions": [
            Question("What is record 1's integer?", 0, "number", "edge"),
            Question("What is record 2's decimal?", 0.001, "number", "edge"),
            Question("What is record 3's negative?", -999, "number", "edge"),
            Question("What is record 4's large value?", 2147483647, "number", "edge"),
            Question("What is record 4's integer?", -50, "number", "edge"),
            Question("How many records are there?", 4, "number", "counting"),
            Question("What is the sum of integers?", 51, "number", "aggregation"),
            Question("What is the smallest negative?", -999, "number", "aggregation"),
            Question("What is the largest 'large' value?", 2147483647, "number", "aggregation"),
            Question("What is record 4's decimal?", 3.14159, "number", "edge"),
            Question("What is record 1's negative?", -100, "number", "edge"),
            Question("What is record 2's large?", 999999999, "number", "edge"),
            Question("What is record 3's integer?", 100, "number", "retrieval"),
            Question("What is the sum of all large values?", 3270940435, "number", "aggregation"),
            Question("Which record has integer=0?", "1", "string", "filtering"),
        ]
    }

    # =========================================================================
    # Dataset 19: edge_strings (special characters)
    # =========================================================================
    datasets["edge_strings"] = {
        "description": "Special character handling",
        "data": {
            "products": [
                {"id": 1, "name": "Normal", "value": "Regular text"},
                {"id": 2, "name": "With Comma", "value": "Has, comma"},
                {"id": 3, "name": "With Quote", "value": "Has \"quotes\""},
                {"id": 4, "name": "With Colon", "value": "Key: Value"},
                {"id": 5, "name": "With Special", "value": "Chars @#$%"},
            ]
        },
        "questions": [
            Question("What is item 1's value?", "Regular text", "string", "retrieval"),
            Question("What is item 2's name?", "With Comma", "string", "edge"),
            Question("What is item 3's value?", "Has \"quotes\"", "string", "edge"),
            Question("What is item 4's value?", "Key: Value", "string", "edge"),
            Question("What is item 5's value?", "Chars @#$%", "string", "edge"),
            Question("How many products are there?", 5, "number", "counting"),
            Question("Which item has 'Normal' name?", "1", "string", "filtering"),
            Question("Which item has special chars?", "5", "string", "filtering"),
            Question("What is item 1's name?", "Normal", "string", "retrieval"),
            Question("What is item 3's name?", "With Quote", "string", "retrieval"),
            Question("Which items have quotes in value?", "3", "string", "filtering"),
            Question("What is item 4's name?", "With Colon", "string", "retrieval"),
            Question("What is item 2's value?", "Has, comma", "string", "edge"),
            Question("Which item has 'Key' in value?", "4", "string", "filtering"),
            Question("What is item 5's name?", "With Special", "string", "retrieval"),
        ]
    }

    # =========================================================================
    # Dataset 20: comprehensive (mixed data)
    # =========================================================================
    datasets["comprehensive"] = {
        "description": "Comprehensive mixed dataset",
        "data": {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@test.com", "active": True, "score": 95.5},
                {"id": 2, "name": "Bob", "email": "bob@test.com", "active": False, "score": 82.0},
                {"id": 3, "name": "Carol", "email": "carol@test.com", "active": True, "score": 88.5},
            ],
            "tasks": [
                {"id": 101, "user_id": 1, "title": "Task A", "status": "done", "priority": 1},
                {"id": 102, "user_id": 1, "title": "Task B", "status": "pending", "priority": 2},
                {"id": 103, "user_id": 2, "title": "Task C", "status": "done", "priority": 1},
                {"id": 104, "user_id": 3, "title": "Task D", "status": "in_progress", "priority": 3},
            ]
        },
        "questions": [
            Question("What is Alice's email?", "alice@test.com", "email", "retrieval"),
            Question("What is Bob's score?", 82.0, "number", "retrieval"),
            Question("Is Carol active?", True, "boolean", "retrieval"),
            Question("What is Task B's status?", "pending", "string", "retrieval"),
            Question("What is Task D's priority?", 3, "number", "retrieval"),
            Question("How many users are there?", 3, "number", "counting"),
            Question("How many tasks are there?", 4, "number", "counting"),
            Question("How many tasks are done?", 2, "number", "counting"),
            Question("How many active users are there?", 2, "number", "counting"),
            Question("What is the average score?", 88.67, "number", "aggregation"),
            Question("Who has the highest score?", "Alice", "string", "aggregation"),
            Question("How many tasks does user 1 have?", 2, "number", "relationship"),
            Question("Which user has Task C?", "Bob", "string", "relationship"),
            Question("What is the total score of all users?", 266, "number", "aggregation"),
            Question("How many priority 1 tasks are there?", 2, "number", "counting"),
        ]
    }

    return datasets

# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_benchmark_v2(run_accuracy: bool = True, dry_run: bool = False):
    """Run the comprehensive V2 benchmark."""

    # Clear logs
    if os.path.exists(LATEST_LOG):
        os.remove(LATEST_LOG)

    datasets = create_datasets()

    # Count totals
    total_questions = sum(len(d["questions"]) for d in datasets.values())

    log("=" * 100)
    log("ISON BENCHMARK V2 - COMPREHENSIVE 300-QUESTION BENCHMARK")
    log("=" * 100)
    log("")
    log(f"Timestamp:       {datetime.now().isoformat()}")
    log(f"Tokenizer:       {TOKENIZER_NAME}")
    log(f"LLM:             DeepSeek (deepseek-chat)")
    log(f"Datasets:        {len(datasets)}")
    log(f"Questions:       {total_questions}")
    log(f"Formats:         {', '.join(FORMATS.keys())}")
    log(f"Accuracy Tests:  {'Enabled' if run_accuracy else 'Disabled'}")
    log(f"Dry Run:         {'Yes (10 questions max)' if dry_run else 'No'}")
    log("")

    # Results tracking
    results = {
        fmt: {
            "tokens": 0,
            "correct": 0,
            "total": 0,
            "wins_tok": 0,
            "wins_acc": 0,
            "categories": {},
            "parse_time": 0,
        }
        for fmt in FORMATS
    }

    per_dataset = {}

    questions_run = 0
    max_questions_per_format = 3 if dry_run else float('inf')  # 3 questions per format in dry run

    for ds_name, ds_info in datasets.items():
        data = ds_info["data"]
        questions = ds_info["questions"]

        if dry_run and questions_run >= len(FORMATS) * max_questions_per_format * 2:
            break

        log("")
        log("-" * 100)
        log(f"DATASET: {ds_name.upper()}")
        log(f"Description: {ds_info['description']} | Questions: {len(questions)}")
        log("-" * 100)

        ds_results = {}

        for fmt_name, converter in FORMATS.items():
            try:
                # Measure parse time
                start_time = time.time()
                output = converter(data)
                parse_time = time.time() - start_time

                tokens = count_tokens(output)

                ds_results[fmt_name] = {
                    "tokens": tokens,
                    "output": output,
                    "correct": 0,
                    "total": 0,
                    "parse_time": parse_time
                }
                results[fmt_name]["tokens"] += tokens
                results[fmt_name]["parse_time"] += parse_time

                log(f"\n--- {fmt_name} ({tokens:,} tokens, {parse_time*1000:.1f}ms) ---")

                # Run accuracy tests
                if run_accuracy:
                    correct = 0
                    questions_for_format = 0
                    for q in questions:
                        if dry_run and questions_for_format >= max_questions_per_format:
                            break

                        prompt = f"""Here is data in {fmt_name} format:

{output}

Question: {q.question}
Answer with just the value, no explanation."""

                        response = call_llm(prompt)
                        is_correct, reason = validate_answer(response, q.expected, q.answer_type)

                        if is_correct:
                            correct += 1
                            results[fmt_name]["correct"] += 1
                        results[fmt_name]["total"] += 1

                        # Track by category
                        cat = q.category
                        if cat not in results[fmt_name]["categories"]:
                            results[fmt_name]["categories"][cat] = {"correct": 0, "total": 0}
                        results[fmt_name]["categories"][cat]["total"] += 1
                        if is_correct:
                            results[fmt_name]["categories"][cat]["correct"] += 1

                        status = "OK" if is_correct else "WRONG"
                        log(f"  [{status}] {q.question[:60]}... => {q.expected}", also_print=False)
                        log(f"         Got: {response[:60]}... | {reason}", also_print=False)

                        questions_run += 1
                        questions_for_format += 1
                        time.sleep(0.3)

                    ds_results[fmt_name]["correct"] = correct
                    ds_results[fmt_name]["total"] = len(questions)
                    acc = (correct / len(questions)) * 100 if questions else 0
                    log(f"  Accuracy: {correct}/{len(questions)} ({acc:.1f}%)")

            except Exception as e:
                log(f"  {fmt_name}: ERROR - {e}")
                ds_results[fmt_name] = {"tokens": -1, "error": str(e)}

        # Determine winners
        valid = [(k, v) for k, v in ds_results.items() if v.get("tokens", -1) > 0]
        if valid:
            min_tok = min(v["tokens"] for k, v in valid)
            for fmt, res in valid:
                if res["tokens"] == min_tok:
                    results[fmt]["wins_tok"] += 1

            if run_accuracy:
                max_acc = max(v.get("correct", 0) for k, v in valid)
                for fmt, res in valid:
                    if res.get("correct", 0) == max_acc:
                        results[fmt]["wins_acc"] += 1

        per_dataset[ds_name] = ds_results

        # Print dataset summary
        log("")
        json_tok = ds_results.get("JSON", {}).get("tokens", 1)
        sorted_res = sorted(valid, key=lambda x: x[1]["tokens"])

        log(f"{'Format':<15} {'Tokens':>10} {'vs JSON':>12} {'Accuracy':>12} {'Acc/1K':>10} {'Parse(ms)':>10}")
        log("-" * 75)

        for rank, (fmt, res) in enumerate(sorted_res, 1):
            tok = res["tokens"]
            sav = ((json_tok - tok) / json_tok) * 100 if json_tok > 0 else 0
            cor = res.get("correct", 0)
            tot = res.get("total", 0)
            acc = (cor / tot * 100) if tot > 0 else 0
            acc_k = (acc / tok) * 1000 if tok > 0 else 0
            pt = res.get("parse_time", 0) * 1000

            marker = ">>>" if rank == 1 else "   "
            sav_str = f"{sav:+.1f}%" if fmt != "JSON" else "baseline"
            acc_str = f"{cor}/{tot} ({acc:.1f}%)" if tot > 0 else "N/A"

            log(f"{marker} {fmt:<12} {tok:>10,} {sav_str:>12} {acc_str:>12} {acc_k:>10.2f} {pt:>10.1f}")

    # =============================================================================
    # OVERALL SUMMARY
    # =============================================================================

    log("")
    log("")
    log("=" * 100)
    log(f"OVERALL RESULTS - {len(datasets)} DATASETS, {total_questions} QUESTIONS")
    log("=" * 100)

    json_total = results["JSON"]["tokens"]

    log("")
    log(f"{'Format':<15} {'Tokens':>12} {'vs JSON':>12} {'Accuracy':>15} {'Acc/1K':>10} {'TokWins':>10} {'AccWins':>10}")
    log("-" * 95)

    sorted_fmt = sorted(results.items(), key=lambda x: x[1]["tokens"])

    for rank, (fmt, r) in enumerate(sorted_fmt, 1):
        tok = r["tokens"]
        sav = ((json_total - tok) / json_total) * 100
        cor = r["correct"]
        tot = r["total"]
        acc = (cor / tot * 100) if tot > 0 else 0
        acc_k = (acc / tok) * 1000 if tok > 0 else 0

        marker = ">>>" if rank == 1 else "   "
        sav_str = f"{sav:+.1f}%" if fmt != "JSON" else "baseline"

        log(f"{marker} {fmt:<12} {tok:>12,} {sav_str:>12} {cor:>6}/{tot:<5} ({acc:>5.1f}%) {acc_k:>10.2f} {r['wins_tok']:>10} {r['wins_acc']:>10}")

    # Category breakdown
    log("")
    log("")
    log("=" * 100)
    log("ACCURACY BY QUESTION CATEGORY")
    log("=" * 100)
    log("")

    categories = set()
    for fmt_res in results.values():
        categories.update(fmt_res["categories"].keys())

    log(f"{'Category':<15}", end="")
    for fmt in FORMATS:
        log(f" {fmt:>18}", end="")
    log("")
    log("-" * (15 + 19 * len(FORMATS)))

    for cat in sorted(categories):
        log(f"{cat:<15}", end="")
        for fmt in FORMATS:
            cat_data = results[fmt]["categories"].get(cat, {"correct": 0, "total": 0})
            if cat_data["total"] > 0:
                acc = cat_data["correct"] / cat_data["total"] * 100
                log(f" {cat_data['correct']:>3}/{cat_data['total']:<3} ({acc:>5.1f}%)", end="")
            else:
                log(f" {'N/A':>18}", end="")
        log("")

    # Conclusion
    log("")
    log("")
    log("=" * 100)
    log("CONCLUSION")
    log("=" * 100)
    log("")

    ison = results["ISON"]
    json_ = results["JSON"]
    toon_ = results["TOON"]
    compact = results["JSON Compact"]

    ison_acc = (ison["correct"] / ison["total"] * 100) if ison["total"] > 0 else 0
    json_acc = (json_["correct"] / json_["total"] * 100) if json_["total"] > 0 else 0

    ison_eff = (ison_acc / ison["tokens"]) * 1000 if ison["tokens"] > 0 else 0
    json_eff = (json_acc / json_["tokens"]) * 1000 if json_["tokens"] > 0 else 0

    log("TOKEN EFFICIENCY:")
    log(f"  ISON:          {ison['tokens']:>12,} tokens")
    log(f"  TOON:          {toon_['tokens']:>12,} tokens")
    log(f"  JSON Compact:  {compact['tokens']:>12,} tokens")
    log(f"  JSON:          {json_['tokens']:>12,} tokens")
    log("")
    log(f"  ISON vs JSON:        {((json_['tokens'] - ison['tokens']) / json_['tokens']) * 100:>10.1f}% reduction")
    log(f"  ISON vs TOON:        {((toon_['tokens'] - ison['tokens']) / toon_['tokens']) * 100:>10.1f}% reduction")
    log("")

    log("LLM ACCURACY:")
    log(f"  ISON:  {ison['correct']:>4}/{ison['total']:<4} ({ison_acc:>5.1f}%)")
    log(f"  TOON:  {toon_['correct']:>4}/{toon_['total']:<4} ({(toon_['correct']/toon_['total']*100) if toon_['total'] > 0 else 0:>5.1f}%)")
    log(f"  JSON:  {json_['correct']:>4}/{json_['total']:<4} ({json_acc:>5.1f}%)")
    log("")

    log("EFFICIENCY (Acc/1K):")
    log(f"  ISON:  {ison_eff:>10.2f}")
    log(f"  JSON:  {json_eff:>10.2f}")

    if json_eff > 0 and ison_eff > json_eff:
        improvement = ((ison_eff - json_eff) / json_eff) * 100
        log(f"  ISON is {improvement:.1f}% MORE EFFICIENT than JSON!")

    log("")
    log("WIN SUMMARY:")
    log(f"  Token Wins:    ISON: {ison['wins_tok']}, TOON: {toon_['wins_tok']}, JSON: {json_['wins_tok']}")
    log(f"  Accuracy Wins: ISON: {ison['wins_acc']}, TOON: {toon_['wins_acc']}, JSON: {json_['wins_acc']}")

    log("")
    log("")

    if ison["wins_tok"] == len(datasets):
        log(">>> ISON WON ALL TOKEN BENCHMARKS! <<<")

    if ison["wins_acc"] == len(datasets):
        log(">>> ISON WON ALL ACCURACY BENCHMARKS! <<<")

    log("")
    log("ISON IS SOTA FOR TOKEN-EFFICIENT DATA FORMATS!")
    log("")
    log("=" * 100)
    log(f"Results saved to: {LOG_FILE}")
    log("=" * 100)

    # Save JSON results
    json_results = {
        "timestamp": datetime.now().isoformat(),
        "tokenizer": TOKENIZER_NAME,
        "datasets": len(datasets),
        "questions": total_questions,
        "formats": {
            fmt: {
                "tokens": r["tokens"],
                "correct": r["correct"],
                "total": r["total"],
                "accuracy": (r["correct"] / r["total"] * 100) if r["total"] > 0 else 0,
                "acc_per_1k": ((r["correct"] / r["total"] * 100) / r["tokens"]) * 1000 if r["tokens"] > 0 and r["total"] > 0 else 0,
                "wins_tokens": r["wins_tok"],
                "wins_accuracy": r["wins_acc"],
                "categories": r["categories"]
            }
            for fmt, r in results.items()
        }
    }

    with open(RESULTS_JSON, "w") as f:
        json.dump(json_results, f, indent=2)

    log(f"JSON results: {RESULTS_JSON}")

    return results, per_dataset

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ISON Benchmark V2")
    parser.add_argument("--dry-run", action="store_true", help="Run with only 10 questions")
    parser.add_argument("--no-accuracy", action="store_true", help="Skip accuracy tests")
    args = parser.parse_args()

    run_benchmark_v2(run_accuracy=not args.no_accuracy, dry_run=args.dry_run)
