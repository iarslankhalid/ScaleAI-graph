"""
FastAPI Application

Main entry point for the GraphRAG API.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

from config.settings import get_settings
from ..graph.loader import GraphLoader
from ..graph.neo4j_client import Neo4jClient
from ..query.intent import IntentParser
from ..query.traversal import GraphTraversal
from ..context.assembler import ContextAssembler
from ..llm.claude import ClaudeClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ScaleAI GraphRAG API",
    description="Graph-based Retrieval Augmented Generation for financial planning",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
graph = None
intent_parser = None
traversal = None
assembler = None
llm = None


# ====================
# Request/Response Models
# ====================

class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    strategy_id: Optional[str] = None
    max_depth: int = 3


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[Dict[str, Any]]
    traversal: Dict[str, Any]
    context_debug: Optional[Dict[str, Any]] = None  # Add debug info for frontend


class TraversalRequest(BaseModel):
    node_id: str
    direction: str = "upstream"
    max_depth: int = 3


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


# ====================
# Startup/Shutdown
# ====================

@app.on_event("startup")
async def startup():
    """Initialize graph and services on startup"""
    global graph, intent_parser, traversal, assembler, llm
    
    settings = get_settings()
    
    logger.info("Starting ScaleAI GraphRAG API...")
    
    # Initialize intent parser
    intent_parser = IntentParser()
    logger.info("✓ Intent parser initialized")
    
    # Initialize context assembler
    assembler = ContextAssembler()
    logger.info("✓ Context assembler initialized")
    
    # Initialize LLM client
    llm = ClaudeClient()
    logger.info("✓ LLM client initialized")
    
    # Initialize graph backend
    if settings.graph_backend == "neo4j" and settings.neo4j_uri:
        try:
            graph = Neo4jClient().connect()
            traversal = GraphTraversal(graph)
            logger.info("✓ Connected to Neo4j")
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j: {e}")
            logger.info("Falling back to NetworkX...")
            graph = _load_networkx_graph(settings)
            traversal = GraphTraversal(graph)
    else:
        graph = _load_networkx_graph(settings)
        traversal = GraphTraversal(graph)
    
    logger.info("ScaleAI GraphRAG API ready!")


def _load_networkx_graph(settings) -> GraphLoader:
    """Load or create NetworkX graph"""
    cache_path = Path(settings.graph_cache_path)
    excel_path = Path(settings.excel_path)
    
    loader = GraphLoader(backend="networkx")
    
    # Try loading from cache first
    if cache_path.exists():
        try:
            loader.load(str(cache_path))
            logger.info(f"✓ Loaded graph from cache: {cache_path}")
            return loader
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
    
    # Load from Excel
    if excel_path.exists():
        loader.load_from_excel(str(excel_path))
        
        # Save to cache
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            loader.save(str(cache_path))
            logger.info(f"✓ Saved graph to cache: {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    else:
        logger.warning(f"Excel file not found: {excel_path}")
        logger.info("API running with empty graph. Upload data via /api/graph/load")
    
    return loader


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    global graph
    
    if isinstance(graph, Neo4jClient):
        graph.close()
        logger.info("Closed Neo4j connection")


# ====================
# API Endpoints
# ====================

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "ScaleAI GraphRAG API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "graph_loaded": graph is not None,
        "graph_backend": "neo4j" if isinstance(graph, Neo4jClient) else "networkx"
    }


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main query endpoint.
    
    Process a natural language query and return an answer with sources.
    """
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    try:
        # Parse intent
        intent = intent_parser.parse(request.query)
        logger.info(f"Parsed intent: {intent.query_type}, fields: {intent.target_fields}")
        
        # Execute traversal
        result = traversal.execute(intent, max_depth=request.max_depth)
        
        if not result.target_node:
            raise HTTPException(
                status_code=404,
                detail=f"Could not find field matching: {intent.target_fields}"
            )
        
        # Assemble context
        # TODO: Fetch live data from ScaleApp API if user_id provided
        live_data = None
        
        context = assembler.assemble(
            query=request.query,
            intent=intent,
            traversal=result,
            live_data=live_data
        )
        
        # Generate response
        answer = llm.generate(context)
        
        # Build sources
        sources = []
        
        if result.paths:
            sources.append({
                "type": "path",
                "value": " → ".join(result.paths[0]) if result.paths else ""
            })
        
        for concept in result.concepts[:3]:
            sources.append({
                "type": "concept",
                "value": concept.get('id', '')
            })
        
        # Build debug context for frontend visualization
        context_debug = {
            "intent": {
                "query_type": intent.query_type.value,
                "target_fields": intent.target_fields,
                "direction": intent.direction.value,
                "confidence": intent.confidence
            },
            "target_node": result.target_node,
            "upstream_nodes": [{"id": n.get("id"), "label": n.get("label"), "tier": n.get("tier")} for n in result.upstream_nodes[:10]],
            "downstream_nodes": [{"id": n.get("id"), "label": n.get("label"), "tier": n.get("tier")} for n in result.downstream_nodes[:10]],
            "concepts": [{"id": c.get("id"), "label": c.get("label"), "category": c.get("category")} for c in result.concepts[:5]],
            "all_paths": result.paths[:5],
            "context_prompt": context.to_prompt()[:2000] if hasattr(context, 'to_prompt') else str(context)[:2000]
        }
        
        return QueryResponse(
            answer=answer,
            confidence=intent.confidence,
            sources=sources,
            traversal={
                "target": result.target_node.get('label') if result.target_node else None,
                "direction": intent.direction.value,
                "depth": request.max_depth,
                "nodes_visited": result.metadata.get('nodes_visited', 0)
            },
            context_debug=context_debug
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/graph/traverse")
async def traverse_graph(request: TraversalRequest):
    """
    Execute a graph traversal.
    
    Returns nodes related to the target node, plus edges between them.
    """
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    try:
        if request.direction == "upstream":
            nodes = traversal._get_upstream(request.node_id, request.max_depth)
        else:
            nodes = traversal._get_downstream(request.node_id, request.max_depth)
        
        # Get edges between these nodes
        edges = []
        node_ids = {request.node_id} | {n.get('id') for n in nodes if n.get('id')}
        
        if not isinstance(graph, Neo4jClient):
            for source, target, data in graph.G.edges(data=True):
                if source in node_ids and target in node_ids:
                    edges.append({
                        'source': source,
                        'target': target,
                        'type': data.get('type', 'DEPENDS_ON')
                    })
        
        return {
            "target": request.node_id,
            "direction": request.direction,
            "nodes": nodes,
            "edges": edges,
            "count": len(nodes)
        }
        
    except Exception as e:
        logger.error(f"Traversal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/graph/search")
async def search_nodes(request: SearchRequest):
    """
    Search for nodes by label or ID.
    """
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    try:
        if isinstance(graph, Neo4jClient):
            results = graph.search_nodes(request.query, request.limit)
        else:
            results = graph.search_nodes(request.query, request.limit)
        
        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/export")
async def export_graph(limit: int = 1000):
    """
    Export graph data for visualization.
    
    Returns nodes and edges in a format suitable for vis.js.
    Prioritizes nodes that have connections (edges).
    """
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    try:
        nodes = []
        edges = []
        
        if isinstance(graph, Neo4jClient):
            # Neo4j export
            nodes = graph.export_nodes(limit)
            edges = graph.export_edges(limit)
        else:
            # NetworkX export - prioritize connected nodes
            exported_ids = set()
            
            # First, collect all nodes that have edges (connected nodes)
            connected_nodes = set()
            for source, target, data in graph.G.edges(data=True):
                connected_nodes.add(source)
                connected_nodes.add(target)
            
            # Export connected nodes first
            node_count = 0
            for node_id in connected_nodes:
                if node_count >= limit:
                    break
                if node_id in graph.G.nodes:
                    data = graph.G.nodes[node_id]
                    nodes.append({
                        'id': node_id,
                        'label': data.get('label', node_id.split('.')[-1]),
                        'type': data.get('type', 'FIELD'),
                        'tier': data.get('tier', -1),
                        'tier_name': data.get('tier_name', ''),
                        'section': data.get('section', ''),
                        'definition': data.get('definition', ''),
                        'payload': data.get('payload', '')
                    })
                    exported_ids.add(node_id)
                    node_count += 1
            
            # Then add remaining nodes if we have room
            for node_id, data in graph.G.nodes(data=True):
                if node_count >= limit:
                    break
                if node_id not in exported_ids:
                    nodes.append({
                        'id': node_id,
                        'label': data.get('label', node_id.split('.')[-1]),
                        'type': data.get('type', 'FIELD'),
                        'tier': data.get('tier', -1),
                        'tier_name': data.get('tier_name', ''),
                        'section': data.get('section', ''),
                        'definition': data.get('definition', ''),
                        'payload': data.get('payload', '')
                    })
                    exported_ids.add(node_id)
                    node_count += 1
            
            # Now export all edges where both nodes are in our export
            for source, target, data in graph.G.edges(data=True):
                if source in exported_ids and target in exported_ids:
                    edges.append({
                        'source': source,
                        'target': target,
                        'type': data.get('type', 'DEPENDS_ON')
                    })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'total_nodes': len(nodes),
            'total_edges': len(edges)
        }
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/stats")
async def get_graph_stats():
    """
    Get graph statistics.
    """
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    try:
        if isinstance(graph, Neo4jClient):
            stats = graph.get_stats()
        else:
            stats = {
                "total_nodes": graph.stats.total_nodes if graph.stats else 0,
                "total_edges": graph.stats.total_edges if graph.stats else 0,
                "nodes_by_type": graph.stats.nodes_by_type if graph.stats else {},
                "nodes_by_tier": graph.stats.nodes_by_tier if graph.stats else {},
                "edges_by_type": graph.stats.edges_by_type if graph.stats else {},
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/node/{node_id:path}")
async def get_node(node_id: str):
    """
    Get a specific node by ID.
    """
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    try:
        if isinstance(graph, Neo4jClient):
            node = graph.get_node(node_id)
        else:
            node = graph.get_node(node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return node
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get node error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/graph/load")
async def load_graph(excel_path: str = "data/AI_sheet.xlsx"):
    """
    Load or reload the graph from Excel.
    """
    global graph, traversal
    
    settings = get_settings()
    
    try:
        path = Path(excel_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {excel_path}")
        
        if settings.graph_backend == "neo4j" and isinstance(graph, Neo4jClient):
            # TODO: Implement Neo4j loader
            raise HTTPException(status_code=501, detail="Neo4j loading not implemented via API")
        else:
            loader = GraphLoader(backend="networkx")
            loader.load_from_excel(str(path))
            
            # Save cache
            cache_path = Path(settings.graph_cache_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            loader.save(str(cache_path))
            
            graph = loader
            traversal = GraphTraversal(graph)
        
        return {
            "status": "loaded",
            "stats": {
                "total_nodes": graph.stats.total_nodes,
                "total_edges": graph.stats.total_edges
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
