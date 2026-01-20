#!/usr/bin/env python3
"""
Test Queries Script

Tests the GraphRAG system with sample queries.

Usage:
    # Run all test queries
    python scripts/test_queries.py
    
    # Test specific query
    python scripts/test_queries.py --query "Why did my debt spike?"
    
    # Interactive mode
    python scripts/test_queries.py --interactive
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config.settings import get_settings
from src.graph.loader import GraphLoader
from src.query.intent import IntentParser
from src.query.traversal import GraphTraversal
from src.context.assembler import ContextAssembler
from src.llm.claude import ClaudeClient

console = Console()


# Sample test queries
TEST_QUERIES = [
    # Causal queries
    {
        "query": "Why did my debt spike in 2030?",
        "expected_type": "causal",
        "expected_fields": ["debt", "total_debt"]
    },
    {
        "query": "What caused my net position to drop?",
        "expected_type": "causal",
        "expected_fields": ["net_position"]
    },
    {
        "query": "Why is my LMI premium so high?",
        "expected_type": "causal", 
        "expected_fields": ["lmi"]
    },
    
    # Impact queries
    {
        "query": "What happens if interest rates go up 1%?",
        "expected_type": "impact",
        "expected_fields": ["interest"]
    },
    {
        "query": "How would selling a property affect my portfolio?",
        "expected_type": "impact",
        "expected_fields": ["sale", "portfolio"]
    },
    
    # Explain queries
    {
        "query": "What is LVR?",
        "expected_type": "explain",
        "expected_fields": ["lvr"]
    },
    {
        "query": "Explain stamp duty",
        "expected_type": "explain",
        "expected_fields": ["stamp_duty"]
    },
    
    # Calculate queries
    {
        "query": "How is my LVR calculated?",
        "expected_type": "calculate",
        "expected_fields": ["lvr"]
    },
    {
        "query": "What goes into the net position calculation?",
        "expected_type": "calculate",
        "expected_fields": ["net_position"]
    },
]


def main():
    parser = argparse.ArgumentParser(description="Test GraphRAG queries")
    parser.add_argument("--query", help="Test a specific query")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM generation")
    
    args = parser.parse_args()
    
    console.print("\n[bold]ScaleAI GraphRAG - Query Tester[/bold]\n")
    
    # Initialize components
    settings = get_settings()
    
    # Load graph
    console.print("Loading graph...")
    cache_path = Path(settings.graph_cache_path)
    excel_path = Path(settings.excel_path)
    
    loader = GraphLoader(backend="networkx")
    
    if cache_path.exists():
        loader.load(str(cache_path))
    elif excel_path.exists():
        loader.load_from_excel(str(excel_path))
        loader.save(str(cache_path))
    else:
        console.print("[red]No graph data found. Run load_graph.py first.[/]")
        sys.exit(1)
    
    # Initialize components
    intent_parser = IntentParser()
    traversal = GraphTraversal(loader)
    assembler = ContextAssembler()
    llm = ClaudeClient() if not args.no_llm else None
    
    console.print(f"Graph loaded: {loader.stats.total_nodes} nodes, {loader.stats.total_edges} edges\n")
    
    if args.interactive:
        interactive_mode(intent_parser, traversal, assembler, llm)
    elif args.query:
        test_single_query(args.query, intent_parser, traversal, assembler, llm)
    else:
        run_all_tests(intent_parser, traversal, assembler, llm)


def test_single_query(query: str, intent_parser, traversal, assembler, llm):
    """Test a single query"""
    console.print(Panel(query, title="Query", border_style="blue"))
    
    # Parse intent
    intent = intent_parser.parse(query)
    console.print(f"\n[bold]Intent:[/]")
    console.print(f"  Type: [cyan]{intent.query_type.value}[/]")
    console.print(f"  Direction: [cyan]{intent.direction.value}[/]")
    console.print(f"  Fields: [cyan]{intent.target_fields}[/]")
    console.print(f"  Confidence: [cyan]{intent.confidence:.2f}[/]")
    
    # Execute traversal
    result = traversal.execute(intent)
    
    console.print(f"\n[bold]Traversal:[/]")
    if result.target_node:
        console.print(f"  Target: [green]{result.target_node.get('label')}[/] (Tier {result.target_node.get('tier')})")
    else:
        console.print("  [red]No target node found[/]")
        return
    
    console.print(f"  Upstream: {len(result.upstream_nodes)} nodes")
    console.print(f"  Downstream: {len(result.downstream_nodes)} nodes")
    console.print(f"  Concepts: {len(result.concepts)} concepts")
    
    if result.paths:
        console.print(f"\n[bold]Dependency Paths:[/]")
        for path in result.paths[:5]:
            console.print(f"  {' '.join(path)}")
    
    if result.upstream_nodes:
        console.print(f"\n[bold]Key Upstream Nodes:[/]")
        for node in result.upstream_nodes[:5]:
            tier = node.get('tier', '?')
            label = node.get('label', 'Unknown')
            console.print(f"  [T{tier}] {label}")
    
    if result.concepts:
        console.print(f"\n[bold]Related Concepts:[/]")
        for concept in result.concepts[:3]:
            console.print(f"  {concept.get('id')}: {concept.get('label', '')[:50]}")
    
    # Generate response (if LLM available)
    if llm:
        console.print(f"\n[bold]Generating Response...[/]")
        context = assembler.assemble(
            query=query,
            intent=intent,
            traversal=result
        )
        
        response = llm.generate(context)
        console.print(Panel(Markdown(response), title="Response", border_style="green"))
    
    console.print()


def run_all_tests(intent_parser, traversal, assembler, llm):
    """Run all test queries"""
    console.print(f"[bold]Running {len(TEST_QUERIES)} test queries...[/]\n")
    
    results = []
    
    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        console.print(f"[dim]Test {i}/{len(TEST_QUERIES)}:[/] {query}")
        
        try:
            # Parse intent
            intent = intent_parser.parse(query)
            
            # Check if intent type matches expected
            intent_match = test["expected_type"] in intent.query_type.value
            
            # Check if fields found
            fields_found = any(
                any(ef in f for ef in test["expected_fields"])
                for f in intent.target_fields
            )
            
            # Execute traversal
            result = traversal.execute(intent)
            traversal_success = result.target_node is not None
            
            status = "✓" if (intent_match and fields_found and traversal_success) else "✗"
            color = "green" if status == "✓" else "red"
            
            console.print(f"  [{color}]{status}[/] Intent: {intent.query_type.value}, Found: {result.target_node.get('label') if result.target_node else 'None'}")
            
            results.append({
                "query": query,
                "success": status == "✓",
                "intent_type": intent.query_type.value,
                "target": result.target_node.get('label') if result.target_node else None
            })
            
        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/]")
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })
    
    # Summary
    success_count = sum(1 for r in results if r["success"])
    console.print(f"\n[bold]Results: {success_count}/{len(results)} passed[/]")


def interactive_mode(intent_parser, traversal, assembler, llm):
    """Interactive query mode"""
    console.print("[bold]Interactive Mode[/] - Type 'quit' to exit\n")
    
    while True:
        try:
            query = console.input("[bold blue]Query>[/] ")
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query.strip():
                continue
            
            test_single_query(query, intent_parser, traversal, assembler, llm)
            
        except KeyboardInterrupt:
            console.print("\n")
            break
    
    console.print("Goodbye!")


if __name__ == "__main__":
    main()
