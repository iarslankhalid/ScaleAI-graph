"""
Neo4j Client

Handles connection and queries to Neo4j graph database.
Use this for production deployments.
"""

from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase, Driver
from contextlib import contextmanager
import logging

from config.settings import get_settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Neo4j database client for GraphRAG.
    
    Usage:
        client = Neo4jClient()
        client.connect()
        
        # Load data
        client.create_field_node(node_data)
        client.create_depends_on_edge(source, target, relation)
        
        # Query
        upstream = client.get_upstream("net_position", max_depth=3)
        
        client.close()
    """
    
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """
        Initialize Neo4j client.
        
        Args:
            uri: Neo4j connection URI (defaults to settings)
            user: Neo4j username (defaults to settings)
            password: Neo4j password (defaults to settings)
        """
        settings = get_settings()
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.driver: Optional[Driver] = None
    
    def connect(self) -> "Neo4jClient":
        """Establish connection to Neo4j"""
        if not self.uri:
            raise ValueError("NEO4J_URI not configured")
        
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
        
        # Test connection
        with self.driver.session() as session:
            session.run("RETURN 1")
        
        logger.info(f"Connected to Neo4j at {self.uri}")
        return self
    
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            self.driver = None
    
    @contextmanager
    def session(self):
        """Get a Neo4j session"""
        if not self.driver:
            self.connect()
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    # ==========================================
    # SCHEMA CREATION
    # ==========================================
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        with self.session() as session:
            # Index on FIELD nodes
            session.run("""
                CREATE INDEX field_id IF NOT EXISTS
                FOR (f:FIELD) ON (f.id)
            """)
            session.run("""
                CREATE INDEX field_tier IF NOT EXISTS
                FOR (f:FIELD) ON (f.tier)
            """)
            session.run("""
                CREATE INDEX field_label IF NOT EXISTS
                FOR (f:FIELD) ON (f.label)
            """)
            
            # Index on CONCEPT nodes
            session.run("""
                CREATE INDEX concept_id IF NOT EXISTS
                FOR (c:CONCEPT) ON (c.id)
            """)
            session.run("""
                CREATE INDEX concept_category IF NOT EXISTS
                FOR (c:CONCEPT) ON (c.category)
            """)
        
        logger.info("Created Neo4j indexes")
    
    def clear_database(self):
        """Clear all nodes and relationships (USE WITH CAUTION)"""
        with self.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.warning("Cleared all data from Neo4j")
    
    # ==========================================
    # NODE CREATION
    # ==========================================
    
    def create_field_node(self, node_data: Dict[str, Any]):
        """Create a FIELD node"""
        with self.session() as session:
            session.run("""
                MERGE (f:FIELD {id: $id})
                SET f.label = $label,
                    f.tier = $tier,
                    f.tier_name = $tier_name,
                    f.section = $section,
                    f.endpoint = $endpoint,
                    f.definition = $definition,
                    f.user_controllable = $user_controllable
            """, **node_data)
    
    def create_concept_node(self, node_data: Dict[str, Any]):
        """Create a CONCEPT node"""
        with self.session() as session:
            session.run("""
                MERGE (c:CONCEPT {id: $id})
                SET c.label = $label,
                    c.category = $category,
                    c.payload = $payload
            """, **node_data)
    
    def create_depends_on_edge(self, source: str, target: str, relation: str = "depends_on", interpretation: str = ""):
        """Create a DEPENDS_ON relationship"""
        with self.session() as session:
            session.run("""
                MATCH (downstream:FIELD {id: $source})
                MATCH (upstream:FIELD {id: $target})
                MERGE (downstream)-[r:DEPENDS_ON]->(upstream)
                SET r.relation = $relation,
                    r.interpretation = $interpretation
            """, source=source, target=target, relation=relation, interpretation=interpretation)
    
    def create_explained_by_edge(self, field_id: str, concept_id: str):
        """Create an EXPLAINED_BY relationship"""
        with self.session() as session:
            session.run("""
                MATCH (f:FIELD {id: $field_id})
                MATCH (c:CONCEPT {id: $concept_id})
                MERGE (f)-[:EXPLAINED_BY]->(c)
            """, field_id=field_id, concept_id=concept_id)
    
    # ==========================================
    # QUERIES
    # ==========================================
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """Get a node by ID"""
        with self.session() as session:
            result = session.run("""
                MATCH (n {id: $id})
                RETURN n, labels(n) as labels
            """, id=node_id)
            record = result.single()
            if record:
                node = dict(record['n'])
                node['type'] = record['labels'][0] if record['labels'] else 'UNKNOWN'
                return node
        return None
    
    def get_upstream(self, node_id: str, max_depth: int = 3) -> List[Dict]:
        """
        Find all upstream dependencies.
        
        Returns nodes that the target node depends on.
        """
        with self.session() as session:
            result = session.run("""
                MATCH path = (target:FIELD {id: $node_id})-[:DEPENDS_ON*1..$max_depth]->(source:FIELD)
                WITH source, min(length(path)) as depth
                RETURN source.id as id, 
                       source.label as label, 
                       source.tier as tier,
                       source.definition as definition,
                       depth
                ORDER BY depth, source.tier
            """, node_id=node_id, max_depth=max_depth)
            
            return [dict(record) for record in result]
    
    def get_downstream(self, node_id: str, max_depth: int = 3) -> List[Dict]:
        """
        Find all downstream dependents.
        
        Returns nodes that depend on the source node.
        """
        with self.session() as session:
            result = session.run("""
                MATCH path = (source:FIELD {id: $node_id})<-[:DEPENDS_ON*1..$max_depth]-(dependent:FIELD)
                WITH dependent, min(length(path)) as depth
                RETURN dependent.id as id,
                       dependent.label as label,
                       dependent.tier as tier,
                       dependent.definition as definition,
                       depth
                ORDER BY depth, dependent.tier DESC
            """, node_id=node_id, max_depth=max_depth)
            
            return [dict(record) for record in result]
    
    def get_dependency_path(self, source_id: str, target_id: str) -> Optional[List[Dict]]:
        """Find the dependency path between two nodes"""
        with self.session() as session:
            result = session.run("""
                MATCH path = shortestPath(
                    (source:FIELD {id: $source_id})-[:DEPENDS_ON*]-(target:FIELD {id: $target_id})
                )
                RETURN [node in nodes(path) | {
                    id: node.id,
                    label: node.label,
                    tier: node.tier
                }] as path
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if record:
                return record['path']
        return None
    
    def get_concepts_for_field(self, field_id: str) -> List[Dict]:
        """Get concepts that explain a field"""
        with self.session() as session:
            result = session.run("""
                MATCH (f:FIELD {id: $field_id})-[:EXPLAINED_BY]->(c:CONCEPT)
                RETURN c.id as id,
                       c.label as label,
                       c.category as category,
                       c.payload as payload
            """, field_id=field_id)
            
            return [dict(record) for record in result]
    
    def search_nodes(self, query: str, limit: int = 10) -> List[Dict]:
        """Search nodes by label"""
        with self.session() as session:
            result = session.run("""
                MATCH (n)
                WHERE toLower(n.label) CONTAINS toLower($query)
                   OR toLower(n.id) CONTAINS toLower($query)
                RETURN n.id as id,
                       n.label as label,
                       labels(n)[0] as type,
                       n.tier as tier
                LIMIT $limit
            """, query=query, limit=limit)
            
            return [dict(record) for record in result]
    
    def get_stats(self) -> Dict:
        """Get graph statistics"""
        with self.session() as session:
            # Total counts
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
            edge_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            
            # Nodes by type
            type_result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as type, count(n) as count
            """)
            nodes_by_type = {r['type']: r['count'] for r in type_result}
            
            # Nodes by tier
            tier_result = session.run("""
                MATCH (f:FIELD)
                WHERE f.tier IS NOT NULL
                RETURN f.tier as tier, count(f) as count
            """)
            nodes_by_tier = {r['tier']: r['count'] for r in tier_result}
            
            # Edges by type
            edge_result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
            """)
            edges_by_type = {r['type']: r['count'] for r in edge_result}
            
            return {
                'total_nodes': node_count,
                'total_edges': edge_count,
                'nodes_by_type': nodes_by_type,
                'nodes_by_tier': nodes_by_tier,
                'edges_by_type': edges_by_type
            }
    
    # ==========================================
    # IMPACT ANALYSIS
    # ==========================================
    
    def get_impact_chain(self, node_id: str, max_depth: int = 5) -> List[Dict]:
        """
        Get the full impact chain for a node.
        
        Shows how a change in this node cascades through tiers.
        """
        with self.session() as session:
            result = session.run("""
                MATCH path = (source:FIELD {id: $node_id})<-[:DEPENDS_ON*1..$max_depth]-(affected:FIELD)
                WITH affected, 
                     length(path) as depth,
                     [node in nodes(path) | node.label] as chain
                RETURN affected.id as id,
                       affected.label as label,
                       affected.tier as tier,
                       depth,
                       chain
                ORDER BY affected.tier, depth
            """, node_id=node_id, max_depth=max_depth)
            
            return [dict(record) for record in result]
    
    def get_root_causes(self, node_id: str) -> List[Dict]:
        """
        Find the root causes (Tier 1 inputs) that affect a node.
        """
        with self.session() as session:
            result = session.run("""
                MATCH path = (target:FIELD {id: $node_id})-[:DEPENDS_ON*]->(source:FIELD)
                WHERE source.tier = 1
                WITH source, 
                     min(length(path)) as depth,
                     collect(DISTINCT [node in nodes(path) | node.label]) as paths
                RETURN source.id as id,
                       source.label as label,
                       source.definition as definition,
                       depth,
                       paths[0] as sample_path
                ORDER BY depth
            """, node_id=node_id)
            
            return [dict(record) for record in result]
