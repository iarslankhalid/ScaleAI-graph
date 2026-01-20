"""
Graph Loader

Loads the ScaleAI knowledge graph from Excel sheets:
- DTO_INDEX → FIELD nodes
- DEP_TABLE → DEPENDS_ON edges
- KB_TABLE → CONCEPT nodes + EXPLAINED_BY edges
"""

import pandas as pd
import networkx as nx
import pickle
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .schema import FieldNode, ConceptNode, DependsOnEdge, ExplainedByEdge, GraphStats

console = Console()


class GraphLoader:
    """
    Loads and manages the ScaleAI knowledge graph.
    
    Supports two backends:
    - NetworkX: In-memory graph (good for development/testing)
    - Neo4j: Persistent graph database (good for production)
    """
    
    def __init__(self, backend: str = "networkx"):
        """
        Initialize the graph loader.
        
        Args:
            backend: "networkx" or "neo4j"
        """
        self.backend = backend
        self.G = nx.DiGraph()
        self.nodes: Dict[str, dict] = {}
        self.stats = None
        
    def load_from_excel(self, excel_path: str) -> "GraphLoader":
        """
        Load graph from Excel file.
        
        Args:
            excel_path: Path to AI_sheet.xlsx
            
        Returns:
            self for chaining
        """
        console.print(f"\n[bold blue]Loading graph from:[/] {excel_path}\n")
        
        xlsx = pd.ExcelFile(excel_path)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # Load FIELD nodes from DTO
            task1 = progress.add_task("Loading FIELD nodes from DTO_INDEX...", total=None)
            field_count = self._load_dto_nodes(xlsx)
            progress.update(task1, completed=True, description=f"✓ Loaded {field_count} FIELD nodes")
            
            # Load DEPENDS_ON edges from DEP
            task2 = progress.add_task("Loading DEPENDS_ON edges from DEP_TABLE...", total=None)
            edge_count = self._load_dep_edges(xlsx)
            progress.update(task2, completed=True, description=f"✓ Loaded {edge_count} DEPENDS_ON edges")
            
            # Load CONCEPT nodes from KB
            task3 = progress.add_task("Loading CONCEPT nodes from KB_TABLE...", total=None)
            concept_count = self._load_kb_concepts(xlsx)
            progress.update(task3, completed=True, description=f"✓ Loaded {concept_count} CONCEPT nodes")
            
            # Link fields to concepts
            task4 = progress.add_task("Creating EXPLAINED_BY edges...", total=None)
            explain_count = self._create_explained_by_edges()
            progress.update(task4, completed=True, description=f"✓ Created {explain_count} EXPLAINED_BY edges")
        
        self._calculate_stats()
        self._print_stats()
        
        return self
    
    def _parse_tier(self, tier_str: str) -> Optional[int]:
        """Parse tier from string like 'TIER 1: INPUT'"""
        if pd.isna(tier_str):
            return None
        tier_str = str(tier_str).upper()
        
        # Try to extract tier number
        if 'TIER 0' in tier_str or 'CONTROL' in tier_str:
            return 0
        elif 'TIER 1' in tier_str or 'INPUT' in tier_str:
            return 1
        elif 'TIER 2' in tier_str or 'MONTHLY' in tier_str:
            return 2
        elif 'TIER 3' in tier_str or 'ANNUAL' in tier_str or 'STRATEGY' in tier_str:
            return 3
        elif 'TIER 4' in tier_str or 'GOAL' in tier_str:
            return 4
        elif 'TIER 5' in tier_str or 'MACRO' in tier_str:
            return 5
        
        # Try regex
        match = re.search(r'TIER\s*(\d)', tier_str)
        if match:
            return int(match.group(1))
        
        return None
    
    def _get_tier_name(self, tier: int) -> str:
        """Get tier name from number"""
        names = {
            0: "Control",
            1: "Input",
            2: "Monthly",
            3: "Annual/Strategy",
            4: "Goals/Triggers",
            5: "Macro"
        }
        return names.get(tier, "Unknown")
    
    def _load_dto_nodes(self, xlsx: pd.ExcelFile) -> int:
        """Load FIELD nodes from DTO sheet"""
        df = pd.read_excel(xlsx, sheet_name='DTO', header=None)
        count = 0
        
        for idx, row in df.iterrows():
            try:
                path = str(row.iloc[4]) if len(row) > 4 else ""
                
                if '/v1/' not in path:
                    continue
                
                # Extract field info
                field_name = str(row.iloc[5]) if len(row) > 5 and pd.notna(row.iloc[5]) else ""
                nickname = str(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else ""
                tier_str = str(row.iloc[12]) if len(row) > 12 else ""
                definition = str(row.iloc[13]) if len(row) > 13 and pd.notna(row.iloc[13]) else ""
                section = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                endpoint = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ""
                data_type = str(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else ""
                
                tier = self._parse_tier(tier_str)
                if tier is None:
                    continue
                
                # Create node
                label = nickname if nickname and nickname != 'nan' else field_name
                if not label or label == 'nan':
                    label = path.split('.')[-1]
                
                node_data = {
                    'id': path,
                    'type': 'FIELD',
                    'label': label[:50],  # Truncate long labels
                    'tier': tier,
                    'tier_name': self._get_tier_name(tier),
                    'section': section if section != 'nan' else '',
                    'endpoint': endpoint if endpoint != 'nan' else '',
                    'data_type': data_type if data_type != 'nan' else '',
                    'definition': definition[:500] if definition != 'nan' else '',
                    'user_controllable': tier == 1  # Tier 1 = user inputs
                }
                
                self.G.add_node(path, **node_data)
                self.nodes[path] = node_data
                count += 1
                
            except Exception as e:
                continue
        
        return count
    
    def _load_dep_edges(self, xlsx: pd.ExcelFile) -> int:
        """Load DEPENDS_ON edges from DEP sheet"""
        df = pd.read_excel(xlsx, sheet_name='DEP', header=None)
        count = 0
        
        for idx, row in df.iterrows():
            try:
                downstream = str(row.iloc[2]) if len(row) > 2 else ""
                upstream = str(row.iloc[3]) if len(row) > 3 else ""
                
                if '/v1/' not in downstream or '/v1/' not in upstream:
                    continue
                
                relation = str(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else "depends_on"
                interpretation = str(row.iloc[10]) if len(row) > 10 and pd.notna(row.iloc[10]) else ""
                
                # Edge direction: downstream DEPENDS_ON upstream
                # In NetworkX: downstream -> upstream (can traverse backwards)
                edge_data = {
                    'type': 'DEPENDS_ON',
                    'relation': relation if relation != 'nan' else 'depends_on',
                    'interpretation': interpretation[:500] if interpretation != 'nan' else ''
                }
                
                self.G.add_edge(downstream, upstream, **edge_data)
                count += 1
                
            except Exception as e:
                continue
        
        return count
    
    def _load_kb_concepts(self, xlsx: pd.ExcelFile) -> int:
        """Load CONCEPT nodes from KB sheet"""
        df = pd.read_excel(xlsx, sheet_name='KB', header=None)
        count = 0
        
        for idx, row in df.iterrows():
            try:
                code = str(row.iloc[3]) if len(row) > 3 else ""
                
                # Only load valid concept codes
                valid_prefixes = ['EDU_', 'DEP_', 'FAQ_', 'EX_', 'DOCS_', 'MKT_']
                if not any(code.startswith(p) for p in valid_prefixes):
                    continue
                
                title = str(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else code
                payload = str(row.iloc[5]) if len(row) > 5 and pd.notna(row.iloc[5]) else ""
                
                # Extract category from prefix
                category = code.split('_')[0] if '_' in code else 'OTHER'
                
                node_data = {
                    'id': code,
                    'type': 'CONCEPT',
                    'label': title[:100] if title != 'nan' else code,
                    'category': category,
                    'payload': payload[:2000] if payload != 'nan' else '',
                    'tier': -1  # Concepts don't have tiers
                }
                
                self.G.add_node(code, **node_data)
                self.nodes[code] = node_data
                count += 1
                
            except Exception as e:
                continue
        
        return count
    
    def _create_explained_by_edges(self) -> int:
        """Create EXPLAINED_BY edges linking fields to concepts"""
        count = 0
        
        # Get all field nodes and concept nodes
        field_nodes = [n for n, d in self.G.nodes(data=True) if d.get('type') == 'FIELD']
        concept_nodes = [n for n, d in self.G.nodes(data=True) if d.get('type') == 'CONCEPT']
        
        # Match fields to concepts by keyword
        for field_id in field_nodes:
            field_data = self.G.nodes[field_id]
            label = field_data.get('label', '').lower()
            
            # Extract keywords from field label
            keywords = set(re.findall(r'[a-z]+', label))
            
            # Find matching concepts
            for concept_id in concept_nodes:
                concept_data = self.G.nodes[concept_id]
                concept_label = concept_data.get('label', '').lower()
                
                # Check for keyword overlap
                concept_keywords = set(re.findall(r'[a-z]+', concept_label))
                
                # Match if significant keyword overlap
                overlap = keywords & concept_keywords
                significant_keywords = overlap - {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'is', 'on', 'and', 'or'}
                
                if len(significant_keywords) >= 1:
                    self.G.add_edge(field_id, concept_id, type='EXPLAINED_BY')
                    count += 1
        
        return count
    
    def _calculate_stats(self):
        """Calculate graph statistics"""
        nodes_by_type = {}
        nodes_by_tier = {}
        edges_by_type = {}
        
        for node, data in self.G.nodes(data=True):
            node_type = data.get('type', 'UNKNOWN')
            nodes_by_type[node_type] = nodes_by_type.get(node_type, 0) + 1
            
            tier = data.get('tier')
            if tier is not None and tier >= 0:
                nodes_by_tier[tier] = nodes_by_tier.get(tier, 0) + 1
        
        for u, v, data in self.G.edges(data=True):
            edge_type = data.get('type', 'UNKNOWN')
            edges_by_type[edge_type] = edges_by_type.get(edge_type, 0) + 1
        
        self.stats = GraphStats(
            total_nodes=self.G.number_of_nodes(),
            total_edges=self.G.number_of_edges(),
            nodes_by_type=nodes_by_type,
            nodes_by_tier=nodes_by_tier,
            edges_by_type=edges_by_type
        )
    
    def _print_stats(self):
        """Print graph statistics"""
        console.print("\n[bold green]Graph Loaded Successfully![/]\n")
        console.print(f"  Total Nodes: [cyan]{self.stats.total_nodes}[/]")
        console.print(f"  Total Edges: [cyan]{self.stats.total_edges}[/]")
        console.print("\n  [bold]Nodes by Type:[/]")
        for t, c in self.stats.nodes_by_type.items():
            console.print(f"    {t}: {c}")
        console.print("\n  [bold]Nodes by Tier:[/]")
        for t in sorted(self.stats.nodes_by_tier.keys()):
            console.print(f"    Tier {t}: {self.stats.nodes_by_tier[t]}")
        console.print("\n  [bold]Edges by Type:[/]")
        for t, c in self.stats.edges_by_type.items():
            console.print(f"    {t}: {c}")
        console.print()
    
    def save(self, path: str):
        """Save graph to pickle file"""
        with open(path, 'wb') as f:
            pickle.dump({
                'graph': self.G,
                'nodes': self.nodes,
                'stats': self.stats
            }, f)
        console.print(f"[green]Graph saved to {path}[/]")
    
    def load(self, path: str) -> "GraphLoader":
        """Load graph from pickle file"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.G = data['graph']
            self.nodes = data['nodes']
            self.stats = data['stats']
        console.print(f"[green]Graph loaded from {path}[/]")
        return self
    
    def get_node(self, node_id: str) -> Optional[dict]:
        """Get node data by ID"""
        if node_id in self.G.nodes:
            return dict(self.G.nodes[node_id])
        return None
    
    def get_upstream(self, node_id: str, max_depth: int = 3) -> List[str]:
        """
        Find all upstream dependencies (what this node depends on).
        
        For a DEPENDS_ON edge: A -> B means A depends on B
        So upstream = follow outgoing edges
        """
        if node_id not in self.G:
            return []
        
        upstream = set()
        visited = set()
        queue = [(node_id, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth or current in visited:
                continue
            visited.add(current)
            
            # Follow outgoing DEPENDS_ON edges
            for _, target, data in self.G.out_edges(current, data=True):
                if data.get('type') == 'DEPENDS_ON':
                    upstream.add(target)
                    queue.append((target, depth + 1))
        
        return list(upstream)
    
    def get_downstream(self, node_id: str, max_depth: int = 3) -> List[str]:
        """
        Find all downstream dependents (what depends on this node).
        
        For a DEPENDS_ON edge: A -> B means A depends on B
        So downstream = follow incoming edges
        """
        if node_id not in self.G:
            return []
        
        downstream = set()
        visited = set()
        queue = [(node_id, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth or current in visited:
                continue
            visited.add(current)
            
            # Follow incoming DEPENDS_ON edges
            for source, _, data in self.G.in_edges(current, data=True):
                if data.get('type') == 'DEPENDS_ON':
                    downstream.add(source)
                    queue.append((source, depth + 1))
        
        return list(downstream)
    
    def get_concepts_for_field(self, field_id: str) -> List[str]:
        """Get concept IDs that explain a field"""
        concepts = []
        for _, target, data in self.G.out_edges(field_id, data=True):
            if data.get('type') == 'EXPLAINED_BY':
                concepts.append(target)
        return concepts
    
    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find shortest path between two nodes"""
        try:
            return nx.shortest_path(self.G, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def search_nodes(self, query: str, limit: int = 10) -> List[dict]:
        """Search nodes by label or ID"""
        query = query.lower()
        results = []
        
        for node_id, data in self.G.nodes(data=True):
            label = data.get('label', '').lower()
            if query in label or query in node_id.lower():
                results.append({
                    'id': node_id,
                    **data
                })
                if len(results) >= limit:
                    break
        
        return results
