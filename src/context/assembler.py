"""
Context Assembler

Builds the context packet that gets sent to the LLM.
Combines graph traversal results with concepts and live data.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..query.intent import QueryIntent, QueryType
from ..query.traversal import TraversalResult
from .prompts import SystemPrompts


@dataclass
class ContextPacket:
    """Context packet for LLM"""
    system_prompt: str
    user_query: str
    traversal_path: str
    node_details: str
    concepts: str
    live_data: Optional[str]
    instructions: str
    
    def to_prompt(self) -> str:
        """Convert to full prompt string"""
        sections = [
            f"## Dependency Path\n{self.traversal_path}",
            f"## Node Details\n{self.node_details}",
        ]
        
        if self.concepts:
            sections.append(f"## Educational Concepts\n{self.concepts}")
        
        if self.live_data:
            sections.append(f"## User's Data\n{self.live_data}")
        
        sections.append(f"## User Question\n{self.user_query}")
        sections.append(f"## Instructions\n{self.instructions}")
        
        return "\n\n".join(sections)


class ContextAssembler:
    """
    Assembles context for the LLM from graph traversal results.
    
    Usage:
        assembler = ContextAssembler()
        packet = assembler.assemble(
            query="Why did my debt spike?",
            intent=parsed_intent,
            traversal=traversal_result,
            live_data=user_data
        )
    """
    
    def __init__(self):
        self.prompts = SystemPrompts()
    
    def assemble(
        self,
        query: str,
        intent: QueryIntent,
        traversal: TraversalResult,
        live_data: Optional[Dict] = None
    ) -> ContextPacket:
        """
        Assemble a context packet for the LLM.
        
        Args:
            query: Original user query
            intent: Parsed query intent
            traversal: Graph traversal result
            live_data: Optional live user data
            
        Returns:
            ContextPacket ready for LLM
        """
        # Get system prompt based on query type
        system_prompt = self.prompts.get_system_prompt(intent.query_type)
        
        # Format traversal path
        traversal_path = self._format_traversal_path(traversal)
        
        # Format node details
        node_details = self._format_node_details(traversal)
        
        # Format concepts
        concepts = self._format_concepts(traversal.concepts)
        
        # Format live data
        live_data_str = self._format_live_data(live_data, traversal)
        
        # Get instructions based on query type
        instructions = self._get_instructions(intent)
        
        return ContextPacket(
            system_prompt=system_prompt,
            user_query=query,
            traversal_path=traversal_path,
            node_details=node_details,
            concepts=concepts,
            live_data=live_data_str,
            instructions=instructions
        )
    
    def _format_traversal_path(self, traversal: TraversalResult) -> str:
        """Format the traversal paths as readable text"""
        if not traversal.paths:
            return "No dependency path found."
        
        lines = []
        
        if traversal.target_node:
            target_label = traversal.target_node.get('label', 'Unknown')
            target_tier = traversal.target_node.get('tier', '?')
            lines.append(f"Target: {target_label} (Tier {target_tier})")
            lines.append("")
        
        # Group by direction
        upstream_paths = [p for p in traversal.paths if '←' in p]
        downstream_paths = [p for p in traversal.paths if '→' in p]
        
        if upstream_paths:
            lines.append("Upstream Dependencies (inputs that affect this):")
            for path in upstream_paths[:5]:
                lines.append(f"  {' '.join(path)}")
        
        if downstream_paths:
            if upstream_paths:
                lines.append("")
            lines.append("Downstream Effects (what this affects):")
            for path in downstream_paths[:5]:
                lines.append(f"  {' '.join(path)}")
        
        return "\n".join(lines)
    
    def _format_node_details(self, traversal: TraversalResult) -> str:
        """Format details about relevant nodes"""
        lines = []
        
        # Target node
        if traversal.target_node:
            lines.append("### Target Field")
            lines.append(self._format_single_node(traversal.target_node))
        
        # Key upstream nodes (inputs)
        if traversal.upstream_nodes:
            lines.append("\n### Key Inputs (Upstream)")
            for node in traversal.upstream_nodes[:5]:
                lines.append(self._format_single_node(node))
        
        # Key downstream nodes (outputs)
        if traversal.downstream_nodes:
            lines.append("\n### Affected Fields (Downstream)")
            for node in traversal.downstream_nodes[:5]:
                lines.append(self._format_single_node(node))
        
        return "\n".join(lines)
    
    def _format_single_node(self, node: Dict) -> str:
        """Format a single node's details"""
        label = node.get('label', 'Unknown')
        tier = node.get('tier', '?')
        tier_name = node.get('tier_name', '')
        definition = node.get('definition', '')
        
        line = f"- **{label}** (Tier {tier}"
        if tier_name:
            line += f": {tier_name}"
        line += ")"
        
        if definition:
            line += f"\n  {definition[:150]}"
        
        return line
    
    def _format_concepts(self, concepts: List[Dict]) -> str:
        """Format educational concepts"""
        if not concepts:
            return ""
        
        lines = []
        for concept in concepts[:5]:
            concept_id = concept.get('id', '')
            label = concept.get('label', '')
            payload = concept.get('payload', '')
            
            lines.append(f"### {concept_id}: {label}")
            if payload:
                # Truncate long payloads
                payload_text = payload[:500]
                if len(payload) > 500:
                    payload_text += "..."
                lines.append(payload_text)
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_live_data(self, live_data: Optional[Dict], traversal: TraversalResult) -> Optional[str]:
        """Format live user data"""
        if not live_data:
            return None
        
        lines = []
        
        # Match live data keys to traversal nodes
        relevant_keys = set()
        
        if traversal.target_node:
            target_label = traversal.target_node.get('label', '').lower()
            for key in live_data.keys():
                if target_label in key.lower() or key.lower() in target_label:
                    relevant_keys.add(key)
        
        for node in traversal.upstream_nodes + traversal.downstream_nodes:
            node_label = node.get('label', '').lower()
            for key in live_data.keys():
                if node_label in key.lower() or key.lower() in node_label:
                    relevant_keys.add(key)
        
        # If no matches, include all data
        if not relevant_keys:
            relevant_keys = set(live_data.keys())
        
        for key in sorted(relevant_keys):
            value = live_data[key]
            lines.append(f"- {key}: {value}")
        
        return "\n".join(lines) if lines else None
    
    def _get_instructions(self, intent: QueryIntent) -> str:
        """Get response instructions based on query type"""
        instructions = {
            QueryType.CAUSAL: """
Answer the user's question by:
1. Identifying the ROOT CAUSE from the upstream dependencies
2. Tracing the path from cause to effect
3. Using specific data values where available
4. Citing educational concepts by ID (e.g., [EDU_020])
5. Explaining in practical terms what happened and why

Be specific and cite the dependency chain.
""",
            QueryType.IMPACT: """
Answer the user's question by:
1. Listing all fields that would be affected (from downstream)
2. Explaining the cascade in order of tiers (T1 → T2 → T3 → T4)
3. Providing magnitude estimates where possible
4. Highlighting any goal or alert impacts (Tier 4)
5. Citing relevant concepts

Be comprehensive about the ripple effects.
""",
            QueryType.EXPLAIN: """
Answer the user's question by:
1. Providing a clear definition using the concept payload
2. Explaining the formula/calculation if applicable
3. Relating to the user's actual values if available
4. Mentioning key thresholds or triggers
5. Linking to related concepts

Be educational and practical.
""",
            QueryType.CALCULATE: """
Answer the user's question by:
1. Stating the exact formula
2. Identifying all inputs (upstream dependencies)
3. Showing how inputs combine to produce the output
4. Using actual values to demonstrate if available
5. Mentioning any special cases or edge conditions

Be precise about the calculation chain.
""",
            QueryType.COMPARE: """
Compare the requested items by:
1. Defining each item clearly
2. Showing their dependency relationships
3. Highlighting key differences
4. Explaining when each is relevant
5. Using data to illustrate differences if available

Be balanced and informative.
""",
            QueryType.GENERAL: """
Answer the user's question using the provided context.
Be helpful, accurate, and cite sources where relevant.
If the context doesn't contain the answer, say so clearly.
"""
        }
        
        return instructions.get(intent.query_type, instructions[QueryType.GENERAL])
