#!/usr/bin/env python3
"""
Load Graph Script

Loads the ScaleAI knowledge graph from Excel into the configured backend.

Usage:
    # Load into NetworkX (default)
    python scripts/load_graph.py
    
    # Load into Neo4j
    python scripts/load_graph.py --backend neo4j
    
    # Specify Excel path
    python scripts/load_graph.py --excel data/AI_sheet.xlsx
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config.settings import get_settings
from src.graph.loader import GraphLoader
from src.graph.neo4j_client import Neo4jClient

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Load ScaleAI knowledge graph")
    parser.add_argument(
        "--backend", 
        choices=["networkx", "neo4j"], 
        default=None,
        help="Graph backend (default: from settings)"
    )
    parser.add_argument(
        "--excel", 
        default=None,
        help="Path to Excel file (default: from settings)"
    )
    parser.add_argument(
        "--cache", 
        default=None,
        help="Path to cache file (default: from settings)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before loading (Neo4j only)"
    )
    
    args = parser.parse_args()
    
    settings = get_settings()
    
    # Determine backend
    backend = args.backend or settings.graph_backend
    excel_path = args.excel or settings.excel_path
    cache_path = args.cache or settings.graph_cache_path
    
    console.print(f"\n[bold]ScaleAI GraphRAG - Graph Loader[/bold]")
    console.print(f"Backend: [cyan]{backend}[/]")
    console.print(f"Excel: [cyan]{excel_path}[/]")
    
    # Check Excel exists
    if not Path(excel_path).exists():
        console.print(f"\n[red]Error: Excel file not found: {excel_path}[/]")
        console.print("Please copy your AI_sheet.xlsx to the data/ directory.")
        sys.exit(1)
    
    if backend == "neo4j":
        load_neo4j(excel_path, args.clear)
    else:
        load_networkx(excel_path, cache_path)
    
    console.print("\n[bold green]Done![/]\n")


def load_networkx(excel_path: str, cache_path: str):
    """Load graph into NetworkX and save to cache"""
    console.print("\n[bold]Loading into NetworkX...[/]")
    
    loader = GraphLoader(backend="networkx")
    loader.load_from_excel(excel_path)
    
    # Save to cache
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    loader.save(cache_path)
    
    console.print(f"\nCache saved to: [cyan]{cache_path}[/]")


def load_neo4j(excel_path: str, clear: bool = False):
    """Load graph into Neo4j"""
    import pandas as pd
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    console.print("\n[bold]Loading into Neo4j...[/]")
    
    settings = get_settings()
    
    if not settings.neo4j_uri:
        console.print("[red]Error: NEO4J_URI not configured in .env[/]")
        sys.exit(1)
    
    # Connect to Neo4j
    client = Neo4jClient()
    
    try:
        client.connect()
        console.print(f"Connected to: [cyan]{settings.neo4j_uri}[/]")
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/]")
        sys.exit(1)
    
    # Clear if requested
    if clear:
        console.print("[yellow]Clearing existing data...[/]")
        client.clear_database()
    
    # Create indexes
    console.print("Creating indexes...")
    client.create_indexes()
    
    # Load Excel
    xlsx = pd.ExcelFile(excel_path)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Load DTO nodes
        task1 = progress.add_task("Loading FIELD nodes...", total=None)
        df_dto = pd.read_excel(xlsx, sheet_name='DTO', header=None)
        field_count = 0
        
        for idx, row in df_dto.iterrows():
            try:
                path = str(row.iloc[4]) if len(row) > 4 else ""
                if '/v1/' not in path:
                    continue
                
                tier = _parse_tier(str(row.iloc[12]) if len(row) > 12 else "")
                if tier is None:
                    continue
                
                label = str(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else ""
                if not label or label == 'nan':
                    label = str(row.iloc[5]) if len(row) > 5 else path.split('.')[-1]
                
                client.create_field_node({
                    'id': path,
                    'label': label[:50],
                    'tier': tier,
                    'tier_name': _get_tier_name(tier),
                    'section': str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else '',
                    'endpoint': str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else '',
                    'definition': str(row.iloc[13])[:500] if len(row) > 13 and pd.notna(row.iloc[13]) else '',
                    'user_controllable': tier == 1
                })
                field_count += 1
                
            except Exception as e:
                continue
        
        progress.update(task1, completed=True, description=f"✓ Loaded {field_count} FIELD nodes")
        
        # Load DEP edges
        task2 = progress.add_task("Loading DEPENDS_ON edges...", total=None)
        df_dep = pd.read_excel(xlsx, sheet_name='DEP', header=None)
        edge_count = 0
        
        for idx, row in df_dep.iterrows():
            try:
                downstream = str(row.iloc[2]) if len(row) > 2 else ""
                upstream = str(row.iloc[3]) if len(row) > 3 else ""
                
                if '/v1/' not in downstream or '/v1/' not in upstream:
                    continue
                
                relation = str(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else "depends_on"
                interpretation = str(row.iloc[10]) if len(row) > 10 and pd.notna(row.iloc[10]) else ""
                
                client.create_depends_on_edge(
                    source=downstream,
                    target=upstream,
                    relation=relation if relation != 'nan' else 'depends_on',
                    interpretation=interpretation[:500] if interpretation != 'nan' else ''
                )
                edge_count += 1
                
            except Exception as e:
                continue
        
        progress.update(task2, completed=True, description=f"✓ Loaded {edge_count} DEPENDS_ON edges")
        
        # Load KB concepts
        task3 = progress.add_task("Loading CONCEPT nodes...", total=None)
        df_kb = pd.read_excel(xlsx, sheet_name='KB', header=None)
        concept_count = 0
        
        for idx, row in df_kb.iterrows():
            try:
                code = str(row.iloc[3]) if len(row) > 3 else ""
                
                valid_prefixes = ['EDU_', 'DEP_', 'FAQ_', 'EX_', 'DOCS_', 'MKT_']
                if not any(code.startswith(p) for p in valid_prefixes):
                    continue
                
                title = str(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else code
                payload = str(row.iloc[5]) if len(row) > 5 and pd.notna(row.iloc[5]) else ""
                
                client.create_concept_node({
                    'id': code,
                    'label': title[:100] if title != 'nan' else code,
                    'category': code.split('_')[0],
                    'payload': payload[:2000] if payload != 'nan' else ''
                })
                concept_count += 1
                
            except Exception as e:
                continue
        
        progress.update(task3, completed=True, description=f"✓ Loaded {concept_count} CONCEPT nodes")
    
    # Print stats
    stats = client.get_stats()
    console.print(f"\n[bold]Neo4j Graph Stats:[/]")
    console.print(f"  Total Nodes: {stats['total_nodes']}")
    console.print(f"  Total Edges: {stats['total_edges']}")
    
    client.close()


def _parse_tier(tier_str: str):
    """Parse tier from string"""
    tier_str = tier_str.upper()
    if 'TIER 0' in tier_str or 'CONTROL' in tier_str:
        return 0
    elif 'TIER 1' in tier_str or 'INPUT' in tier_str:
        return 1
    elif 'TIER 2' in tier_str or 'MONTHLY' in tier_str:
        return 2
    elif 'TIER 3' in tier_str or 'ANNUAL' in tier_str:
        return 3
    elif 'TIER 4' in tier_str or 'GOAL' in tier_str:
        return 4
    elif 'TIER 5' in tier_str or 'MACRO' in tier_str:
        return 5
    return None


def _get_tier_name(tier: int) -> str:
    """Get tier name"""
    names = {0: "Control", 1: "Input", 2: "Monthly", 3: "Annual", 4: "Goals", 5: "Macro"}
    return names.get(tier, "Unknown")


if __name__ == "__main__":
    main()
