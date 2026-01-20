# ScaleAI GraphRAG Implementation

A production-ready GraphRAG system for ScaleAI's financial planning AI, enabling deterministic causal reasoning over calculation dependencies.

## 🎯 What This Does

- Loads your **DTO_INDEX** (967 fields) as graph nodes
- Loads your **DEP_TABLE** (355 dependencies) as graph edges  
- Loads your **KB_TABLE** (93 concepts) as educational content
- Enables queries like:
  - "Why did my debt spike in 2030?" → Traces exact cause
  - "What if interest rates go up 1%?" → Shows full impact chain
  - "How is LVR calculated?" → Returns formula + inputs

## 📁 Project Structure

```
scaleai-graphrag/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── docker-compose.yml       # Neo4j + API containers
│
├── config/
│   └── settings.py          # Configuration management
│
├── data/
│   └── AI_sheet.xlsx        # Your Excel file (copy here)
│
├── src/
│   ├── __init__.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── loader.py        # Load Excel → Graph
│   │   ├── schema.py        # Node/Edge definitions
│   │   └── neo4j_client.py  # Neo4j connection
│   │
│   ├── query/
│   │   ├── __init__.py
│   │   ├── intent.py        # Parse user intent
│   │   ├── traversal.py     # Graph traversal logic
│   │   └── cypher.py        # Cypher query builder
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   ├── assembler.py     # Build LLM context
│   │   └── prompts.py       # System prompts
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── claude.py        # Claude API client
│   │
│   └── api/
│       ├── __init__.py
│       ├── main.py          # FastAPI app
│       └── routes.py        # API endpoints
│
├── scripts/
│   ├── load_graph.py        # One-time graph loading
│   ├── test_queries.py      # Test sample queries
│   └── benchmark.py         # Accuracy benchmarking
│
└── tests/
    ├── test_loader.py
    ├── test_traversal.py
    └── test_queries.py
```

## 🚀 Quick Start

### Option A: Local Development (NetworkX)

```bash
# 1. Clone and setup
cd scaleai-graphrag
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# 2. Copy your Excel file
cp /path/to/AI_sheet.xlsx data/

# 3. Set environment variables
cp .env.example .env
# Edit .env with your API keys

# 4. Load the graph
python scripts/load_graph.py

# 5. Test queries
python scripts/test_queries.py

# 6. Start API server
uvicorn src.api.main:app --reload
```

### Option B: With Neo4j (Production)

```bash
# 1. Start Neo4j
docker-compose up -d neo4j

# 2. Wait for Neo4j to be ready
sleep 30

# 3. Load graph into Neo4j
python scripts/load_graph.py --backend neo4j

# 4. Start API
docker-compose up -d api
```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Neo4j (optional - defaults to NetworkX if not set)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# Or Neo4j Aura (cloud)
# NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your-aura-password

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Pinecone (optional - for hybrid mode)
PINECONE_API_KEY=xxxxx
PINECONE_INDEX=scaleai-kb

# Graph Backend: "networkx" or "neo4j"
GRAPH_BACKEND=networkx
```

## 📊 API Endpoints

### Query Endpoint

```bash
POST /api/query
Content-Type: application/json

{
  "query": "Why did my net position drop in 2030?",
  "user_id": "user_123",
  "strategy_id": "strategy_456"
}
```

**Response:**
```json
{
  "answer": "Your net position dropped by $50,000 in 2030 because...",
  "confidence": 0.95,
  "sources": [
    {"type": "path", "value": "refinance_event → total_debt → net_position"},
    {"type": "concept", "value": "EDU_045_EQUITY_RELEASE"}
  ],
  "traversal": {
    "target": "net_position",
    "direction": "upstream",
    "depth": 3,
    "nodes_visited": 5
  }
}
```

### Graph Stats Endpoint

```bash
GET /api/graph/stats
```

**Response:**
```json
{
  "total_nodes": 1027,
  "total_edges": 420,
  "nodes_by_type": {
    "FIELD": 934,
    "CONCEPT": 93
  },
  "nodes_by_tier": {
    "1": 408,
    "2": 53,
    "3": 289,
    "4": 54,
    "5": 130
  }
}
```

### Traversal Endpoint

```bash
POST /api/graph/traverse
Content-Type: application/json

{
  "node_id": "/v1/portfolio-cashflow.financialYears[].netPosition",
  "direction": "upstream",
  "max_depth": 3
}
```

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Test Specific Queries

```bash
python scripts/test_queries.py --query "Why did my debt spike?"
```

### Benchmark Accuracy

```bash
python scripts/benchmark.py --samples 100
```

## 📈 Expected Results

| Query Type | Vector RAG | GraphRAG | Improvement |
|------------|------------|----------|-------------|
| "Why did X happen?" | 55% | 95% | +40% |
| "What if Y changes?" | 40% | 92% | +52% |
| "How is X calculated?" | 70% | 99% | +29% |

## 🔍 How It Works

```
User: "Why did my net position drop in 2030?"
                    │
                    ▼
┌─────────────────────────────────────┐
│         1. INTENT DETECTION         │
│  • Target: net_position             │
│  • Type: CAUSAL                     │
│  • Direction: UPSTREAM              │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│         2. GRAPH TRAVERSAL          │
│  MATCH (target)<-[:DEPENDS_ON*]-    │
│        (source)                     │
│  WHERE target.id = 'net_position'   │
│                                     │
│  Path Found:                        │
│  net_position ← total_debt ←        │
│                 refinance_event     │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│       3. CONTEXT ASSEMBLY           │
│  • Path: refi → debt → net_pos      │
│  • Data: {refi: $200k, year: 2030}  │
│  • Concept: EDU_045_EQUITY_RELEASE  │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│         4. LLM GENERATION           │
│  "Your net position dropped by      │
│   $50,000 in 2030 because of your   │
│   planned refinance event..."       │
└─────────────────────────────────────┘
```

## 📝 License

MIT License - ScaleAI Internal Use

## 🤝 Contributing

1. Create feature branch
2. Add tests
3. Submit PR

---

*Built for ScaleAI | January 2026*
