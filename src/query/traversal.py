"""
Graph Traversal

Executes graph queries based on parsed intent.
"""

from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass

from ..graph.loader import GraphLoader
from ..graph.neo4j_client import Neo4jClient
from .intent import QueryIntent, QueryType, TraversalDirection


@dataclass
class TraversalResult:
    """Result of a graph traversal"""
    target_node: Optional[Dict]
    upstream_nodes: List[Dict]
    downstream_nodes: List[Dict]
    concepts: List[Dict]
    paths: List[List[str]]
    metadata: Dict[str, Any]


class GraphTraversal:
    """
    Executes graph traversals based on query intent.
    
    Supports both NetworkX (GraphLoader) and Neo4j (Neo4jClient) backends.
    
    Usage:
        # With NetworkX
        loader = GraphLoader().load_from_excel("data/AI_sheet.xlsx")
        traversal = GraphTraversal(loader)
        
        # Or with Neo4j
        client = Neo4jClient().connect()
        traversal = GraphTraversal(client)
        
        # Execute query
        result = traversal.execute(intent)
    """
    
    def __init__(self, backend: Union[GraphLoader, Neo4jClient]):
        """
        Initialize with a graph backend.
        
        Args:
            backend: Either GraphLoader (NetworkX) or Neo4jClient (Neo4j)
        """
        self.backend = backend
        self.is_neo4j = isinstance(backend, Neo4jClient)
    
    def execute(self, intent: QueryIntent, max_depth: int = 3) -> TraversalResult:
        """
        Execute graph traversal based on intent.
        
        Args:
            intent: Parsed query intent
            max_depth: Maximum traversal depth
            
        Returns:
            TraversalResult with related nodes and paths
        """
        # Find target node(s)
        target_node = self._find_target_node(intent.target_fields)
        
        if not target_node:
            return TraversalResult(
                target_node=None,
                upstream_nodes=[],
                downstream_nodes=[],
                concepts=[],
                paths=[],
                metadata={'error': 'Target node not found', 'searched': intent.target_fields}
            )
        
        target_id = target_node.get('id')
        
        # Execute traversal based on direction
        upstream_nodes = []
        downstream_nodes = []
        paths = []
        
        if intent.direction in [TraversalDirection.UPSTREAM, TraversalDirection.BOTH]:
            upstream_nodes = self._get_upstream(target_id, max_depth)
            if upstream_nodes:
                paths.extend(self._build_paths(target_id, upstream_nodes, 'upstream'))
        
        if intent.direction in [TraversalDirection.DOWNSTREAM, TraversalDirection.BOTH]:
            downstream_nodes = self._get_downstream(target_id, max_depth)
            if downstream_nodes:
                paths.extend(self._build_paths(target_id, downstream_nodes, 'downstream'))
        
        # Get related concepts
        concepts = self._get_concepts(target_id, upstream_nodes, downstream_nodes)
        
        return TraversalResult(
            target_node=target_node,
            upstream_nodes=upstream_nodes,
            downstream_nodes=downstream_nodes,
            concepts=concepts,
            paths=paths,
            metadata={
                'intent': intent.query_type.value,
                'direction': intent.direction.value,
                'depth': max_depth,
                'nodes_visited': len(upstream_nodes) + len(downstream_nodes) + 1
            }
        )
    
    def _find_target_node(self, field_keywords: List[str]) -> Optional[Dict]:
        """Find a node matching the field keywords"""
        for keyword in field_keywords:
            if self.is_neo4j:
                results = self.backend.search_nodes(keyword, limit=1)
            else:
                results = self.backend.search_nodes(keyword, limit=1)
            
            if results:
                return results[0]
        
        return None
    
    def _get_upstream(self, node_id: str, max_depth: int) -> List[Dict]:
        """Get upstream dependencies"""
        if self.is_neo4j:
            return self.backend.get_upstream(node_id, max_depth)
        else:
            # NetworkX backend returns list of IDs
            upstream_ids = self.backend.get_upstream(node_id, max_depth)
            return [
                {'id': nid, **self.backend.get_node(nid)}
                for nid in upstream_ids
                if self.backend.get_node(nid)
            ]
    
    def _get_downstream(self, node_id: str, max_depth: int) -> List[Dict]:
        """Get downstream dependents"""
        if self.is_neo4j:
            return self.backend.get_downstream(node_id, max_depth)
        else:
            downstream_ids = self.backend.get_downstream(node_id, max_depth)
            return [
                {'id': nid, **self.backend.get_node(nid)}
                for nid in downstream_ids
                if self.backend.get_node(nid)
            ]
    
    def _get_concepts(self, target_id: str, upstream: List[Dict], downstream: List[Dict]) -> List[Dict]:
        """Get concepts related to the traversal"""
        concepts = []
        seen_ids = set()
        
        # Get concepts for target
        target_concepts = self._get_concepts_for_node(target_id)
        for c in target_concepts:
            if c.get('id') not in seen_ids:
                concepts.append(c)
                seen_ids.add(c.get('id'))
        
        # Get concepts for key upstream nodes (limit to avoid too many)
        for node in upstream[:5]:
            node_concepts = self._get_concepts_for_node(node.get('id'))
            for c in node_concepts:
                if c.get('id') not in seen_ids:
                    concepts.append(c)
                    seen_ids.add(c.get('id'))
        
        return concepts[:10]  # Limit total concepts
    
    def _get_concepts_for_node(self, node_id: str) -> List[Dict]:
        """Get concepts for a specific node"""
        if self.is_neo4j:
            return self.backend.get_concepts_for_field(node_id)
        else:
            concept_ids = self.backend.get_concepts_for_field(node_id)
            return [
                {'id': cid, **self.backend.get_node(cid)}
                for cid in concept_ids
                if self.backend.get_node(cid)
            ]
    
    def _build_paths(self, target_id: str, related_nodes: List[Dict], direction: str) -> List[List[str]]:
        """Build readable paths from target to related nodes"""
        paths = []
        
        for node in related_nodes[:5]:  # Limit paths
            node_id = node.get('id')
            target_label = self._get_label(target_id)
            node_label = node.get('label', node_id)
            
            if direction == 'upstream':
                # target depends on node
                paths.append([target_label, '←', node_label])
            else:
                # node depends on target
                paths.append([target_label, '→', node_label])
        
        return paths
    
    def _get_label(self, node_id: str) -> str:
        """Get label for a node ID"""
        if self.is_neo4j:
            node = self.backend.get_node(node_id)
        else:
            node = self.backend.get_node(node_id)
        
        if node:
            return node.get('label', node_id.split('.')[-1])
        return node_id.split('.')[-1]
    
    def get_root_causes(self, node_id: str) -> List[Dict]:
        """
        Find Tier 1 inputs that ultimately affect a node.
        
        Useful for answering "What can I change to affect X?"
        """
        if self.is_neo4j:
            return self.backend.get_root_causes(node_id)
        else:
            # NetworkX: traverse to find tier 1 nodes
            upstream = self.backend.get_upstream(node_id, max_depth=10)
            tier1_nodes = []
            
            for nid in upstream:
                node = self.backend.get_node(nid)
                if node and node.get('tier') == 1:
                    tier1_nodes.append({'id': nid, **node})
            
            return tier1_nodes
    
    def get_impact_chain(self, node_id: str, max_depth: int = 5) -> List[Dict]:
        """
        Get the full impact chain showing how changes cascade.
        
        Useful for answering "What happens if X changes?"
        """
        if self.is_neo4j:
            return self.backend.get_impact_chain(node_id, max_depth)
        else:
            # NetworkX: group downstream by tier
            downstream = self.backend.get_downstream(node_id, max_depth)
            
            impact_chain = []
            for nid in downstream:
                node = self.backend.get_node(nid)
                if node:
                    impact_chain.append({
                        'id': nid,
                        'label': node.get('label'),
                        'tier': node.get('tier'),
                    })
            
            # Sort by tier
            impact_chain.sort(key=lambda x: (x.get('tier', 99), x.get('label', '')))
            
            return impact_chain
