# Quick Troubleshooting Guide

## Check if Dashboard is Loading

1. **Open Browser Console** (F12 or Cmd+Option+I)
2. **Look for these logs:**
   ```
   🚀 Initializing ScaleAI GraphRAG Dashboard...
   📊 Loaded X nodes and Y edges
   📐 Canvas dimensions: WWWxHHH
   🔧 Initializing network with X nodes and Y edges
   📊 Prepared X vis nodes and Y vis edges
   🎨 Creating vis.DataSets...
   ✅ DataSets created
   🎨 Creating vis.Network instance...
   ✅ Network object created successfully
   ```

3. **Common Issues:**

   ### Issue: Canvas dimensions are 0x0
   **Fix:** CSS layout problem. Check that:
   - `.main-content` has `flex: 1`
   - `.graph-container` has `flex: 1`  
   - Browser window is visible and not minimized

   ### Issue: vis is undefined
   **Fix:** vis.js didn't load from CDN
   - Check internet connection
   - Try refreshing with Cmd+Shift+R (hard refresh)
   - Check browser console for CDN errors

   ### Issue: No nodes loaded
   **Fix:** API not returning data
   - Test API: `curl http://localhost:8000/api/graph/export?limit=50`
   - Check API server is running: `curl http://localhost:8000/health`

## Manual Test

Open browser console and run:
```javascript
// Check if vis is loaded
console.log('vis loaded?', typeof vis !== 'undefined');

// Check canvas size
const canvas = document.getElementById('graph-canvas');
console.log('Canvas:', canvas.getBoundingClientRect());

// Check data
console.log('Nodes:', GraphRAG.allNodes.length);
console.log('Edges:', GraphRAG.allEdges.length);

// Check network
console.log('Network:', GraphRAG.network);
```

## Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Stats
curl http://localhost:8000/api/graph/stats

# Export (small sample)
curl "http://localhost:8000/api/graph/export?limit=10"

# Search
curl -X POST http://localhost:8000/api/graph/search \
  -H "Content-Type: application/json" \
  -d '{"query": "lvr", "limit": 5}'

# Query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is LVR?", "max_depth": 2}'
```

## Force Reload Steps

1. **Hard Refresh:** Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. **Clear Cache:** Browser Settings → Clear Cache → Reload
3. **Restart Servers:**
   ```bash
   # Stop all (Ctrl+C in terminals)
   # Restart API
   cd /path/to/ScaleAI-graph
   uvicorn src.api.main:app --reload
   
   # Restart Frontend
   cd Frontend
   python serve.py
   ```

## Check Files Are Updated

```bash
cd Frontend
grep "Canvas dimensions" app.js
# Should show the new dimension check code

grep "vis is available" app.js  
# Should show the vis check code
```
