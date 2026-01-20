# ScaleAI GraphRAG Implementation Guide

## Complete Setup & Testing Instructions

This document provides step-by-step instructions to set up and test the GraphRAG system for ScaleAI.

---

## 📋 Prerequisites

- Python 3.10+
- Your `AI_sheet.xlsx` Excel file
- (Optional) Neo4j database
- (Optional) Anthropic API key for Claude

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Setup Environment

```bash
# Clone/copy the project
cd scaleai-graphrag

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
# At minimum, you can leave defaults for NetworkX backend
```

### Step 3: Add Your Data

```bash
# Copy your Excel file to the data directory
cp /path/to/AI_sheet.xlsx data/
```

### Step 4: Load the Graph

```bash
# Load graph from Excel (creates cache for faster subsequent loads)
python scripts/load_graph.py
```

Expected output:
```
ScaleAI GraphRAG - Graph Loader
Backend: networkx
Excel: data/AI_sheet.xlsx

Loading graph from: data/AI_sheet.xlsx

✓ Loaded 934 FIELD nodes
✓ Loaded 355 DEPENDS_ON edges  
✓ Loaded 93 CONCEPT nodes
✓ Created 127 EXPLAINED_BY edges

Graph Loaded Successfully!

  Total Nodes: 1027
  Total Edges: 482

  Nodes by Type:
    FIELD: 934
    CONCEPT: 93

  Nodes by Tier:
    Tier 1: 408
    Tier 2: 53
    Tier 3: 289
    Tier 4: 54
    Tier 5: 130

Cache saved to: data/graph_cache.pkl

Done!
```

### Step 5: Test Queries

```bash
# Run test queries
python scripts/test_queries.py
```

Expected output:
```
ScaleAI GraphRAG - Query Tester

Loading graph...
Graph loaded: 1027 nodes, 482 edges

Running 9 test queries...

Test 1/9: Why did my debt spike in 2030?
  ✓ Intent: causal, Found: Total Debt

Test 2/9: What caused my net position to drop?
  ✓ Intent: causal, Found: Net Position

Test 3/9: Why is my LMI premium so high?
  ✓ Intent: causal, Found: LMI Premium

...

Results: 8/9 passed
```

### Step 6: Interactive Testing

```bash
# Start interactive mode
python scripts/test_queries.py --interactive
```

```
Interactive Mode - Type 'quit' to exit

Query> Why did my debt spike in 2030?

┌─ Query ────────────────────────────────────────┐
│ Why did my debt spike in 2030?                 │
└────────────────────────────────────────────────┘

Intent:
  Type: causal
  Direction: upstream
  Fields: ['debt', 'total_debt', 'loan_balance']
  Confidence: 0.80

Traversal:
  Target: Total Debt (Tier 3)
  Upstream: 12 nodes
  Downstream: 5 nodes
  Concepts: 3 concepts

Dependency Paths:
  Total Debt ← Loan Balance
  Total Debt ← Refinance Event

Key Upstream Nodes:
  [T1] Loan Amount
  [T1] Refinance Event
  [T2] Loan Balance

Related Concepts:
  EDU_045_EQUITY_RELEASE: Equity Release Overview

Query>
```

### Step 7: Start API Server

```bash
# Start the FastAPI server
uvicorn src.api.main:app --reload --port 8000
```

Open http://localhost:8000/docs to see the API documentation.

---

## 🔌 API Usage

### Query Endpoint

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Why did my net position drop in 2030?",
    "max_depth": 3
  }'
```

Response:
```json
{
  "answer": "Your net position dropped because of your planned refinance event...",
  "confidence": 0.85,
  "sources": [
    {"type": "path", "value": "Net Position ← Total Debt ← Refinance Event"},
    {"type": "concept", "value": "EDU_045_EQUITY_RELEASE"}
  ],
  "traversal": {
    "target": "Net Position",
    "direction": "upstream",
    "depth": 3,
    "nodes_visited": 15
  }
}
```

### Graph Stats

```bash
curl http://localhost:8000/api/graph/stats
```

### Search Nodes

```bash
curl -X POST http://localhost:8000/api/graph/search \
  -H "Content-Type: application/json" \
  -d '{"query": "lvr", "limit": 5}'
```

---

## 🐳 Docker Setup (Production)

### With Neo4j

```bash
# Start Neo4j and API
docker-compose up -d

# Wait for Neo4j to be ready
sleep 30

# Load graph into Neo4j
python scripts/load_graph.py --backend neo4j --clear

# Check status
docker-compose logs -f api
```

### Access Points

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (user: neo4j, pass: scaleai-graphrag-2024)

---

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Test Specific Module

```bash
pytest tests/test_intent.py -v
```

### Test with Coverage

```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

---

## 📊 Understanding the Output

### Intent Types

| Type | Trigger Words | Direction | Example |
|------|---------------|-----------|---------|
| CAUSAL | why, cause, reason | upstream | "Why did my debt spike?" |
| IMPACT | what if, affect | downstream | "What if rates go up?" |
| EXPLAIN | what is, explain | both | "What is LVR?" |
| CALCULATE | how is, formula | upstream | "How is LVR calculated?" |

### Traversal Results

```
Target: Net Position (Tier 3)
  ↑ UPSTREAM (what affects this)
    Total Debt (Tier 3)
      Loan Balance (Tier 2)
        Loan Amount (Tier 1) ← ROOT CAUSE
        Refinance Event (Tier 1) ← ROOT CAUSE
      
  ↓ DOWNSTREAM (what this affects)
    Retirement Goal (Tier 4)
    Wealth Goal (Tier 4)
```

### Tier Reference

| Tier | Name | Description | User Control |
|------|------|-------------|--------------|
| 1 | Input | Raw user data | ✅ Direct |
| 2 | Monthly | Monthly calculations | ❌ Derived |
| 3 | Annual | Strategy outputs | ❌ Derived |
| 4 | Goals | Goals & alerts | ❌ Derived |
| 5 | Macro | Broker dashboard | ❌ Derived |

---

## 🔧 Configuration Options

### .env Settings

```env
# Graph Backend
GRAPH_BACKEND=networkx  # or "neo4j"

# Neo4j (if using neo4j backend)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Claude API (optional - for LLM responses)
ANTHROPIC_API_KEY=sk-ant-...

# Data paths
EXCEL_PATH=data/AI_sheet.xlsx
GRAPH_CACHE_PATH=data/graph_cache.pkl
```

### Traversal Depth

Adjust `max_depth` based on query type:
- Causal queries: 3-4 hops (find root causes)
- Impact queries: 4-5 hops (see full cascade)
- Explain queries: 1-2 hops (immediate context)

---

## 📈 Benchmarking

### Run Accuracy Benchmark

```bash
python scripts/test_queries.py
```

### Expected Results

| Query Type | Expected Accuracy |
|------------|-------------------|
| Causal ("Why...") | 90-95% |
| Impact ("What if...") | 85-92% |
| Explain ("What is...") | 95%+ |
| Calculate ("How is...") | 95%+ |

---

## 🐛 Troubleshooting

### "Graph not loaded"

```bash
# Check if Excel file exists
ls -la data/AI_sheet.xlsx

# Reload graph
python scripts/load_graph.py
```

### "No target node found"

The query's field keywords didn't match any nodes. Try:
1. Using different keywords
2. Checking available nodes: `python scripts/test_queries.py --interactive` then type `search lvr`

### Neo4j Connection Failed

```bash
# Check Neo4j is running
docker-compose ps

# Check logs
docker-compose logs neo4j

# Verify connection
python -c "from neo4j import GraphDatabase; d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password')); d.verify_connectivity()"
```

### API Returns 503

Graph hasn't loaded. Check:
1. Excel file exists in `data/`
2. Run `python scripts/load_graph.py` manually
3. Check API logs: `docker-compose logs api`

---

## 🚀 Next Steps

1. **Add Claude API key** - Enable LLM-powered responses
2. **Connect to ScaleApp API** - Fetch live user data
3. **Migrate to Neo4j** - For production persistence
4. **Add monitoring** - Track query patterns and accuracy
5. **Fine-tune prompts** - Improve response quality

---

## 📁 File Reference

```
scaleai-graphrag/
├── src/
│   ├── graph/
│   │   ├── loader.py      # Excel → Graph loading
│   │   ├── schema.py      # Node/Edge definitions
│   │   └── neo4j_client.py # Neo4j operations
│   │
│   ├── query/
│   │   ├── intent.py      # Parse user queries
│   │   └── traversal.py   # Execute graph queries
│   │
│   ├── context/
│   │   ├── assembler.py   # Build LLM context
│   │   └── prompts.py     # System prompts
│   │
│   ├── llm/
│   │   └── claude.py      # Claude API client
│   │
│   └── api/
│       └── main.py        # FastAPI application
│
├── scripts/
│   ├── load_graph.py      # Load graph from Excel
│   └── test_queries.py    # Test and benchmark
│
├── config/
│   └── settings.py        # Configuration
│
├── data/
│   ├── AI_sheet.xlsx      # Your Excel file
│   └── graph_cache.pkl    # Cached graph
│
├── tests/
│   └── test_intent.py     # Unit tests
│
├── .env                   # Environment variables
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker setup
└── README.md             # Project overview
```

---

*Implementation Guide v1.0 | January 2026*
