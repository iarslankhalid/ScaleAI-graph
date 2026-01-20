# ScaleAI GraphRAG Dashboard

Interactive visualization and debugging dashboard for the ScaleAI GraphRAG system.

## Features

- **Interactive Graph Visualization**: View and explore the knowledge graph with vis.js
- **Query Interface**: Submit natural language queries and see the LLM response
- **Path Highlighting**: Visualize which nodes are traversed when answering queries
- **LLM Context Inspector**: Debug what data is sent to the LLM, including:
  - Parsed intent (query type, direction, confidence)
  - Upstream and downstream nodes
  - Related concepts
  - Full context prompt sent to Claude
- **Node Search**: Search for specific nodes by label or ID
- **Tier Filtering**: Filter the graph by node tier
- **Node Details**: Click any node to see its full details

## Getting Started

### 1. Start the API Server

First, make sure the FastAPI backend is running:

```bash
cd /path/to/ScaleAI-graph
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start the Frontend Server

Option A - Using Python's built-in server:
```bash
cd Frontend
python serve.py
```

Option B - Using any static file server:
```bash
cd Frontend
npx serve .
# or
python -m http.server 3000
```

### 3. Open the Dashboard

Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌──────────┐  ┌─────────────────────────────┐  ┌────────────────────┐ │
│  │          │  │                             │  │                    │ │
│  │ Sidebar  │  │      Graph Canvas           │  │   Details Panel    │ │
│  │          │  │                             │  │                    │ │
│  │ - Stats  │  │   [Interactive Network]     │  │ - Node Details     │ │
│  │ - Search │  │                             │  │ - LLM Context      │ │
│  │ - Filter │  │                             │  │   Inspector        │ │
│  │ - Legend │  │                             │  │                    │ │
│  │          │  │                             │  │                    │ │
│  └──────────┘  └─────────────────────────────┘  └────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Usage Guide

### Querying the Graph

1. Type a natural language question in the query input at the top
2. Adjust the "Max Depth" if needed (controls how many levels of dependencies to traverse)
3. Click "Query" or press Enter
4. The graph will highlight all nodes involved in answering your query
5. Check the right panel to see:
   - **Answer**: The LLM's response
   - **Traversal**: Path taken through the graph
   - **Context**: All data sources used
   - **LLM Prompt**: The exact prompt sent to Claude
   - **Raw JSON**: Full API response

### Exploring Nodes

- **Click** a node to see its details in the right panel
- **Double-click** to zoom and focus on a node
- **Drag** nodes to rearrange them
- Use **mouse wheel** to zoom in/out
- Use **Show Upstream/Downstream** buttons to explore connected nodes

### Filtering

- Use tier checkboxes in the sidebar to show/hide nodes by tier
- Use the search box to find specific nodes
- Click "Clear Highlights" to reset the view

## Tier Color Legend

| Tier | Color | Description |
|------|-------|-------------|
| 0 | Purple | Control/Meta |
| 1 | Green | Input (User-controllable) |
| 2 | Blue | Monthly calculations |
| 3 | Amber | Annual aggregations |
| 4 | Red | Goals/Triggers |
| 5 | Pink | Macro indicators |
| Concepts | Cyan | Educational concepts |

## Configuration

Edit `app.js` to change the API URL if needed:

```javascript
const API_BASE_URL = 'http://localhost:8000';
```

## Troubleshooting

### Graph not loading?
- Ensure the API server is running on port 8000
- Check browser console for errors
- Verify the graph data is loaded (`/api/graph/stats` should return data)

### CORS errors?
- The API already has CORS enabled for all origins
- If using a different port, update `API_BASE_URL` in `app.js`

### Query failing?
- Check that Claude API key is configured in `.env`
- Verify the intent parser can understand your query
- Try simpler queries like "What is LVR?"

## Development

The frontend is built with vanilla HTML/CSS/JavaScript for simplicity. Key dependencies (loaded via CDN):
- **vis.js** - Network graph visualization
- **marked.js** - Markdown rendering for LLM responses
