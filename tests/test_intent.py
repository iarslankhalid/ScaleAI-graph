"""
Tests for intent parsing
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.query.intent import IntentParser, QueryType, TraversalDirection


class TestIntentParser:
    """Tests for IntentParser"""
    
    def setup_method(self):
        self.parser = IntentParser()
    
    def test_causal_query(self):
        """Test causal query detection"""
        queries = [
            "Why did my debt spike?",
            "What caused my net position to drop?",
            "How come my LVR increased?",
        ]
        
        for query in queries:
            intent = self.parser.parse(query)
            assert intent.query_type == QueryType.CAUSAL, f"Failed for: {query}"
            assert intent.direction == TraversalDirection.UPSTREAM
    
    def test_impact_query(self):
        """Test impact query detection"""
        queries = [
            "What if interest rates go up?",
            "What happens if I sell a property?",
            "How would this affect my portfolio?",
        ]
        
        for query in queries:
            intent = self.parser.parse(query)
            assert intent.query_type == QueryType.IMPACT, f"Failed for: {query}"
            assert intent.direction == TraversalDirection.DOWNSTREAM
    
    def test_explain_query(self):
        """Test explain query detection"""
        queries = [
            "What is LVR?",
            "Explain stamp duty",
            "Tell me about negative gearing",
        ]
        
        for query in queries:
            intent = self.parser.parse(query)
            assert intent.query_type == QueryType.EXPLAIN, f"Failed for: {query}"
    
    def test_calculate_query(self):
        """Test calculate query detection"""
        queries = [
            "How is LVR calculated?",
            "What's the formula for stamp duty?",
            "How do you compute net position?",
        ]
        
        for query in queries:
            intent = self.parser.parse(query)
            assert intent.query_type == QueryType.CALCULATE, f"Failed for: {query}"
    
    def test_field_extraction(self):
        """Test field keyword extraction"""
        test_cases = [
            ("What is my LVR?", ["lvr"]),
            ("Why did my debt increase?", ["debt", "total_debt", "loan_balance"]),
            ("Explain stamp duty", ["stamp_duty"]),
        ]
        
        for query, expected_fields in test_cases:
            intent = self.parser.parse(query)
            found = any(ef in intent.target_fields for ef in expected_fields)
            assert found, f"Failed for: {query}, got: {intent.target_fields}"
    
    def test_time_extraction(self):
        """Test time context extraction"""
        test_cases = [
            ("Why did my debt spike in 2030?", "2030"),
            ("What happened in FY24?", "FY24"),
        ]
        
        for query, expected_time in test_cases:
            intent = self.parser.parse(query)
            assert intent.time_context == expected_time, f"Failed for: {query}"
    
    def test_confidence_scoring(self):
        """Test confidence scoring"""
        # Clear query with known fields should have high confidence
        intent1 = self.parser.parse("Why did my LVR increase?")
        assert intent1.confidence > 0.7
        
        # Vague query should have lower confidence
        intent2 = self.parser.parse("Tell me something")
        assert intent2.confidence < intent1.confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
