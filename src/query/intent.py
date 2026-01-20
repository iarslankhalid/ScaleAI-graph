"""
Intent Parser

Parses user queries to determine:
1. Query type (causal, impact, explain, compare)
2. Target field(s)
3. Traversal direction
4. Time context (if any)
"""

import re
from typing import Optional, List, Literal
from pydantic import BaseModel
from enum import Enum


class QueryType(str, Enum):
    CAUSAL = "causal"           # "Why did X happen?"
    IMPACT = "impact"           # "What if X changes?"
    EXPLAIN = "explain"         # "What is X?"
    COMPARE = "compare"         # "Compare X and Y"
    CALCULATE = "calculate"     # "How is X calculated?"
    LIST = "list"               # "Show all X"
    GENERAL = "general"         # Default


class TraversalDirection(str, Enum):
    UPSTREAM = "upstream"       # Find causes (inputs)
    DOWNSTREAM = "downstream"   # Find effects (outputs)
    BOTH = "both"               # Both directions


class QueryIntent(BaseModel):
    """Parsed query intent"""
    query_type: QueryType
    direction: TraversalDirection
    target_fields: List[str]  # Field labels/keywords to search
    time_context: Optional[str] = None  # e.g., "2030", "last month"
    comparison_fields: Optional[List[str]] = None  # For compare queries
    confidence: float = 1.0


class IntentParser:
    """
    Parses natural language queries into structured intents.
    
    Usage:
        parser = IntentParser()
        intent = parser.parse("Why did my debt spike in 2030?")
        # QueryIntent(
        #     query_type=QueryType.CAUSAL,
        #     direction=TraversalDirection.UPSTREAM,
        #     target_fields=["debt"],
        #     time_context="2030"
        # )
    """
    
    # Keywords that indicate query type
    CAUSAL_KEYWORDS = [
        'why', 'cause', 'reason', 'how come', 'what caused', 
        'what made', 'explain why', 'due to', 'because'
    ]
    
    IMPACT_KEYWORDS = [
        'what if', 'what happens if', 'if i change', 'impact of',
        'affect', 'effect', 'influence', 'change', 'increase', 'decrease'
    ]
    
    EXPLAIN_KEYWORDS = [
        'what is', 'what are', 'explain', 'tell me about', 
        'describe', 'define', 'meaning of'
    ]
    
    CALCULATE_KEYWORDS = [
        'how is', 'how are', 'calculate', 'computed', 'derived',
        'formula', 'calculation', 'work out'
    ]
    
    COMPARE_KEYWORDS = [
        'compare', 'vs', 'versus', 'difference between', 
        'which is better', 'comparison'
    ]
    
    # Common field keywords (map to actual field labels)
    FIELD_KEYWORDS = {
        # Debt related
        'debt': ['total_debt', 'loan_balance', 'debt'],
        'loan': ['loan_amount', 'loan_balance', 'loan'],
        'mortgage': ['loan_amount', 'loan_balance', 'mortgage'],
        
        # Value related
        'lvr': ['lvr', 'loan_to_value'],
        'equity': ['equity', 'total_equity'],
        'value': ['property_value', 'portfolio_value', 'value'],
        'net position': ['net_position', 'netposition'],
        'net worth': ['net_position', 'net_worth'],
        
        # Cashflow related
        'cashflow': ['cashflow', 'net_cashflow', 'annual_cashflow'],
        'cash flow': ['cashflow', 'net_cashflow'],
        'income': ['rental_income', 'gross_salary', 'income'],
        'rent': ['rental_income', 'weekly_rent', 'rent'],
        
        # Costs related
        'stamp duty': ['stamp_duty', 'stampduty'],
        'lmi': ['lmi', 'lmi_premium'],
        'interest': ['interest', 'interest_rate', 'monthly_interest'],
        'expenses': ['expenses', 'operating_expenses'],
        'tax': ['tax', 'tax_benefit', 'taxable_income'],
        
        # Goals
        'retirement': ['retirement', 'retirement_goal', 'retirement_date'],
        'deposit': ['deposit', 'deposit_goal', 'deposit_savings'],
        'goal': ['goal', 'goals'],
        
        # Events
        'refinance': ['refinance', 'refinance_event'],
        'sale': ['sale', 'sale_event'],
    }
    
    # Time patterns
    TIME_PATTERNS = [
        r'\b(20\d{2})\b',                    # Year: 2024, 2030
        r'\b(FY\d{2,4})\b',                  # FY24, FY2024
        r'\b(last|next|this)\s+(year|month|quarter)\b',
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{0,4}\b',
    ]
    
    def parse(self, query: str) -> QueryIntent:
        """
        Parse a natural language query into a QueryIntent.
        
        Args:
            query: User's natural language query
            
        Returns:
            QueryIntent with parsed components
        """
        query_lower = query.lower().strip()
        
        # Determine query type
        query_type = self._detect_query_type(query_lower)
        
        # Determine traversal direction based on query type
        direction = self._get_direction(query_type)
        
        # Extract target fields
        target_fields = self._extract_fields(query_lower)
        
        # Extract time context
        time_context = self._extract_time(query)
        
        # Check for comparison
        comparison_fields = None
        if query_type == QueryType.COMPARE:
            comparison_fields = self._extract_comparison_fields(query_lower)
        
        # Calculate confidence
        confidence = self._calculate_confidence(query_type, target_fields)
        
        return QueryIntent(
            query_type=query_type,
            direction=direction,
            target_fields=target_fields,
            time_context=time_context,
            comparison_fields=comparison_fields,
            confidence=confidence
        )
    
    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of query"""
        
        # Check each type in order of specificity
        if any(kw in query for kw in self.CAUSAL_KEYWORDS):
            return QueryType.CAUSAL
        
        if any(kw in query for kw in self.IMPACT_KEYWORDS):
            return QueryType.IMPACT
        
        if any(kw in query for kw in self.COMPARE_KEYWORDS):
            return QueryType.COMPARE
        
        if any(kw in query for kw in self.CALCULATE_KEYWORDS):
            return QueryType.CALCULATE
        
        if any(kw in query for kw in self.EXPLAIN_KEYWORDS):
            return QueryType.EXPLAIN
        
        return QueryType.GENERAL
    
    def _get_direction(self, query_type: QueryType) -> TraversalDirection:
        """Get traversal direction based on query type"""
        direction_map = {
            QueryType.CAUSAL: TraversalDirection.UPSTREAM,
            QueryType.IMPACT: TraversalDirection.DOWNSTREAM,
            QueryType.EXPLAIN: TraversalDirection.BOTH,
            QueryType.CALCULATE: TraversalDirection.UPSTREAM,
            QueryType.COMPARE: TraversalDirection.BOTH,
            QueryType.LIST: TraversalDirection.BOTH,
            QueryType.GENERAL: TraversalDirection.BOTH,
        }
        return direction_map.get(query_type, TraversalDirection.BOTH)
    
    def _extract_fields(self, query: str) -> List[str]:
        """Extract field keywords from query"""
        found_fields = []
        
        # Check for known field keywords
        for keyword, field_names in self.FIELD_KEYWORDS.items():
            if keyword in query:
                found_fields.extend(field_names)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_fields = []
        for f in found_fields:
            if f not in seen:
                seen.add(f)
                unique_fields.append(f)
        
        return unique_fields if unique_fields else self._extract_nouns(query)
    
    def _extract_nouns(self, query: str) -> List[str]:
        """Extract potential field names as fallback"""
        # Simple noun extraction - remove common words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'my', 'your', 'our', 'their', 'its', 'his', 'her', 'this',
            'that', 'these', 'those', 'what', 'which', 'who', 'whom',
            'why', 'how', 'when', 'where', 'if', 'because', 'did'
        }
        
        words = re.findall(r'\b[a-z]+\b', query.lower())
        nouns = [w for w in words if w not in stop_words and len(w) > 2]
        
        return nouns[:3]  # Return top 3 potential field names
    
    def _extract_time(self, query: str) -> Optional[str]:
        """Extract time context from query"""
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(0)
        return None
    
    def _extract_comparison_fields(self, query: str) -> List[str]:
        """Extract fields for comparison"""
        # Look for "X vs Y" or "X and Y" patterns
        patterns = [
            r'compare\s+(\w+)\s+(?:and|vs|versus|to)\s+(\w+)',
            r'(\w+)\s+vs\s+(\w+)',
            r'difference\s+between\s+(\w+)\s+and\s+(\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return list(match.groups())
        
        return []
    
    def _calculate_confidence(self, query_type: QueryType, fields: List[str]) -> float:
        """Calculate confidence score for the parsed intent"""
        confidence = 0.5  # Base confidence
        
        # Higher confidence if we identified a specific query type
        if query_type != QueryType.GENERAL:
            confidence += 0.2
        
        # Higher confidence if we found known fields
        known_fields = set()
        for field_names in self.FIELD_KEYWORDS.values():
            known_fields.update(field_names)
        
        matched_known = sum(1 for f in fields if f in known_fields)
        if matched_known > 0:
            confidence += 0.1 * min(matched_known, 3)
        
        return min(confidence, 1.0)
