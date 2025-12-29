# ISON Benchmark Suite

**Proving ISON is SOTA for Token-Efficient Data Formats**

This benchmark suite compares ISON against other data formats (TOON, JSON, JSON Compact) measuring both **token efficiency** and **LLM accuracy**.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Benchmark Methodology](#benchmark-methodology)
- [Datasets](#datasets)
- [Metrics Explained](#metrics-explained)
- [Running the Benchmark](#running-the-benchmark)
- [Understanding Results](#understanding-results)
- [Latest Results](#latest-results)
- [Format Comparison](#format-comparison)
- [Key Findings](#key-findings)

---

## Quick Start

```bash
# 1. Install dependencies
pip install tiktoken pyyaml requests ison-py toon-llm

# 2. Set your API key (for accuracy tests)
# Edit benchmark_300.py and set DEEPSEEK_API_KEY
# Or use your own LLM API

# 3. Run the benchmark
python benchmark_300.py

# 4. View results
cat benchmark_300_latest.log
```

---

## Requirements

### Python Packages

```bash
pip install tiktoken      # Token counting (o200k_base tokenizer)
pip install pyyaml        # YAML format support
pip install requests      # API calls for LLM accuracy tests
pip install ison-py       # Official ISON parser
pip install toon-llm      # Official TOON parser
```

### API Key (for Accuracy Tests)

The benchmark uses DeepSeek API for LLM accuracy testing. You can:
1. Use the provided DeepSeek API key (in `benchmark_300.py`)
2. Replace with your own API key
3. Modify to use OpenAI, Claude, or other LLM APIs

---

## Benchmark Methodology

### What We Measure

| Metric | Description |
|--------|-------------|
| **Token Count** | Number of tokens using `o200k_base` tokenizer (GPT-4o/GPT-5) |
| **Accuracy** | LLM's ability to correctly answer questions about the data |
| **Acc/1K** | Accuracy per 1,000 tokens (efficiency metric) |
| **Token Wins** | Number of datasets where format has fewest tokens |
| **Accuracy Wins** | Number of datasets where format has highest accuracy |

### Tokenizer

We use `tiktoken` with the `o200k_base` encoding, which is the tokenizer for:
- GPT-4o
- GPT-4o-mini
- GPT-5 (expected)

### LLM Accuracy Testing

For each dataset and format:
1. Convert data to the format (ISON, TOON, JSON, etc.)
2. Send to LLM with a question about the data
3. Compare LLM response to expected answer
4. Use type-aware comparison (e.g., `50000` = `$50,000` = `50,000`)

### Question Types

| Type | Example |
|------|---------|
| **Retrieval** | "What is User10's email?" |
| **Count** | "How many users are active?" |
| **Boolean** | "Is User8 active?" |
| **Filter** | "Which user is NOT active?" |
| **Relationship** | "Who works at Acme Corp?" |

---

## Datasets

The benchmark includes **9 datasets** covering various data patterns:

| Dataset | Records | Description | Key Features |
|---------|---------|-------------|--------------|
| `users_small` | 3 | Small user dataset | Basic tabular data |
| `users_medium` | 25 | Medium user dataset | Counting, filtering |
| `users_large` | 100 | Large user dataset | Scalability test |
| `orders` | 5 | E-commerce orders | Simple relationships |
| `ecommerce` | 3 tables | Multi-table e-commerce | References between tables |
| `analytics` | 5 | Analytics events | Time-series data |
| `config` | 5 | Configuration key-value | Config patterns |
| `logs` | 5 | System log entries | Log patterns |
| `graph` | 2 tables | Graph nodes and edges | Graph relationships |

### Dataset Details

#### users_small (3 records)
```
table.users
id name email active
1 Alice alice@example.com true
2 Bob bob@example.com false
3 Charlie charlie@example.com true
```

#### ecommerce (with ISON references)
```
table.users
id name email premium
1 "Alice Johnson" alice@shop.com true

table.products
id name price stock category
101 "Laptop Pro" 1299.99 50 Electronics

table.orders
id user_id product_id quantity total
1001 :user:1 :product:101 1 1299.99
```

#### graph (with ISON references)
```
table.nodes
id type name
1 person Alice
2 person Bob
3 company "Acme Corp"

table.edges
source target relation
:node:1 :node:3 works_at
:node:1 :node:2 knows
```

---

## Metrics Explained

### Token Count

The number of tokens a format uses to represent the same data.

**Lower is better** - fewer tokens means:
- Lower API costs
- More data fits in context window
- Faster processing

### Accuracy (%)

Percentage of questions the LLM answered correctly when reading data in that format.

**Higher is better** - measures how well the LLM understands the format.

### Acc/1K (Accuracy per 1,000 Tokens)

The key efficiency metric:

```
Acc/1K = (Accuracy % / Total Tokens) × 1000
```

**Higher is better** - measures how much accuracy you get per token spent.

#### Example:
| Format | Tokens | Accuracy | Acc/1K |
|--------|--------|----------|--------|
| ISON | 2,314 | 100.0% | **43.22** |
| JSON | 8,578 | 93.3% | 10.88 |

ISON is **4x more efficient** than JSON!

### Scaling to 1M Token Context

| Format | Datasets in 1M tokens | Questions Answered |
|--------|----------------------|-------------------|
| **ISON** | 432 | 19,440 |
| TOON | 333 | 14,985 |
| JSON | 116 | 5,220 |

**ISON processes 3.7x more data** in the same context window.

---

## Running the Benchmark

### Basic Run

```bash
python benchmark_300.py
```

This will:
1. Convert each dataset to all formats
2. Count tokens for each format
3. Test LLM accuracy (requires API key)
4. Generate detailed log file
5. Print summary to console

### Output Files

| File | Description |
|------|-------------|
| `benchmark_300_YYYYMMDD_HHMMSS.log` | Timestamped full results |
| `benchmark_300_latest.log` | Symlink to latest results |

### Token-Only Mode (No API Required)

To run without accuracy tests, modify the script:

```python
# In benchmark_300.py, change:
run_benchmark(run_accuracy_tests=False)
```

### Using Different LLM APIs

To use OpenAI, Claude, or other APIs, modify the `call_deepseek()` function:

```python
def call_deepseek(prompt: str, max_retries: int = 3) -> str:
    # Replace with your preferred LLM API
    # OpenAI example:
    import openai
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content
```

---

## Understanding Results

### Console Output

```
================================================================================
OVERALL RESULTS - ALL DATASETS COMBINED
================================================================================

Format                Tokens      vs JSON     Accuracy     Acc/1K  TokWins  AccWins
-------------------------------------------------------------------------------------
>>> ISON                2,314       +73.0%       100.0%      43.22        9        9
    TOON                2,996       +65.1%       100.0%      33.38        0        9
    JSON Compact        4,952       +42.3%        95.6%      19.30        0        8
    JSON                8,578        +0.0%        93.3%      10.88        0        7
```

### Reading the Results

- `>>>` indicates the winning format (fewest tokens)
- `vs JSON` shows token reduction compared to JSON baseline
- `TokWins` = datasets where this format had fewest tokens
- `AccWins` = datasets where this format had highest accuracy

### Log File Structure

The log file contains:
1. **Header** - Timestamp, tokenizer, LLM model
2. **Per-Dataset Results** - Detailed breakdown for each dataset
3. **Overall Summary** - Combined results across all datasets
4. **Conclusion** - Key findings and efficiency comparison

---

## Latest Results

### Summary (December 2025)

| Format | Tokens | vs JSON | Accuracy | Acc/1K | TokWins | AccWins |
|--------|--------|---------|----------|--------|---------|---------|
| **ISON** | 2,314 | **-73.0%** | **100.0%** | **43.22** | **9** | **9** |
| TOON | 2,996 | -65.1% | 100.0% | 33.38 | 0 | 9 |
| JSON Compact | 4,952 | -42.3% | 95.6% | 19.30 | 0 | 8 |
| JSON | 8,578 | baseline | 93.3% | 10.88 | 0 | 7 |

### Key Metrics

- **ISON won ALL 9 token benchmarks**
- **ISON won ALL 9 accuracy benchmarks**
- **ISON is 73% more token-efficient than JSON**
- **ISON is 23% more token-efficient than TOON**
- **ISON is 297% more efficient than JSON** (Acc/1K)

---

## Format Comparison

### ISON Format

```
table.users
id name email active
1 Alice alice@example.com true
2 Bob bob@example.com false

table.orders
id user_id product total
1001 :user:1 Widget 29.99
```

**Advantages:**
- Space-separated values (most token-efficient)
- Reference syntax (`:user:1`, `:product:101`)
- Type annotations (`id:int`, `active:bool`)
- Multi-table support
- Human-readable

### TOON Format

```
users[2]{id,name,email,active}:
  1,Alice,alice@example.com,true
  2,Bob,bob@example.com,false
```

**Advantages:**
- Comma-separated values
- Row count in header
- Good LLM comprehension

**Disadvantages:**
- No reference syntax
- Slightly more tokens than ISON

### JSON Format

```json
{
  "users": [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "active": true}
  ]
}
```

**Disadvantages:**
- Verbose syntax (`{}`, `[]`, `""`, `:`, `,`)
- 3-4x more tokens than ISON
- Repeated field names for each row

---

## Key Findings

### 1. Token Efficiency

ISON achieves **73% token reduction** vs JSON:
- JSON: 8,578 tokens
- ISON: 2,314 tokens
- **Savings: 6,264 tokens (73%)**

### 2. LLM Accuracy

ISON achieves **100% accuracy** while using fewer tokens:
- ISON: 100% (45/45 questions)
- TOON: 100% (45/45 questions)
- JSON: 93.3% (42/45 questions)

### 3. Efficiency (Acc/1K)

ISON is **297% more efficient** than JSON:
- ISON: 43.22 accuracy per 1K tokens
- JSON: 10.88 accuracy per 1K tokens

### 4. Reference Support

ISON's reference syntax helps LLMs understand relationships:
```
# ISON (with references)
:user:1 :product:101 1 1299.99

# JSON (no references)
{"user_id": 1, "product_id": 101, "quantity": 1, "total": 1299.99}
```

### 5. Scalability

In a 1M token context:
- ISON: 432 datasets, 19,440 questions
- JSON: 116 datasets, 5,220 questions
- **ISON processes 3.7x more data**

---

## Reproducing Results

### Step 1: Clone Repository

```bash
git clone https://github.com/maheshvaikri-code/ison.git
cd ison/benchmark
```

### Step 2: Install Dependencies

```bash
pip install tiktoken pyyaml requests ison-py toon-llm
```

### Step 3: Configure API Key

Edit `benchmark_300.py`:
```python
DEEPSEEK_API_KEY = "your-api-key-here"
```

### Step 4: Run Benchmark

```bash
python benchmark_300.py
```

### Step 5: View Results

```bash
cat benchmark_300_latest.log
```

---

## Adding Custom Datasets

To add your own dataset:

```python
# In benchmark_300.py, add to DATASETS dict:
DATASETS = {
    # ... existing datasets ...

    "my_dataset": {
        "description": "My custom dataset (10 records)",
        "data": {
            "items": [
                {"id": 1, "name": "Item 1", "price": 9.99},
                {"id": 2, "name": "Item 2", "price": 19.99},
                # ... more records ...
            ]
        }
    },
}

# Add questions for accuracy testing:
ACCURACY_QUESTIONS = {
    # ... existing questions ...

    "my_dataset": [
        {"question": "What is the price of Item 1?", "expected": "9.99", "type": "retrieval"},
        {"question": "How many items are there?", "expected": "2", "type": "count"},
    ],
}
```

---

## License

MIT License - see [LICENSE](../LICENSE) for details.

---

## Author

**Mahesh Vaikri**
- Website: [www.ison.dev](https://www.ison.dev)
- GitHub: [@maheshvaikri-code](https://github.com/maheshvaikri-code)

---

<p align="center">
  <strong>ISON</strong> - Less tokens, more context, better AI.
</p>
