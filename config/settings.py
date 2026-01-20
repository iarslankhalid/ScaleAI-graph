"""
Configuration management for ScaleAI GraphRAG
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Graph Backend
    graph_backend: str = Field(default="networkx", description="networkx or neo4j")
    
    # Neo4j
    neo4j_uri: Optional[str] = Field(default=None)
    neo4j_user: Optional[str] = Field(default="neo4j")
    neo4j_password: Optional[str] = Field(default=None)
    
    # Claude API
    anthropic_api_key: Optional[str] = Field(default=None)
    
    # Pinecone (optional)
    pinecone_api_key: Optional[str] = Field(default=None)
    pinecone_environment: Optional[str] = Field(default=None)
    pinecone_index: Optional[str] = Field(default=None)
    
    # ScaleApp API (optional)
    scaleapp_api_url: Optional[str] = Field(default=None)
    scaleapp_api_key: Optional[str] = Field(default=None)
    
    # Server
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    debug: bool = Field(default=True)
    
    # Data Paths
    excel_path: str = Field(default="data/AI_sheet.xlsx")
    graph_cache_path: str = Field(default="data/graph_cache.pkl")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Tier definitions
TIER_DEFINITIONS = {
    0: {"name": "Control", "role": "Meta.Control", "description": "Strategy selection and context"},
    1: {"name": "Input", "role": "Input.*", "description": "Raw user, property, loan, assumption data"},
    2: {"name": "Monthly", "role": "Output.*.Monthly", "description": "Monthly calculated metrics"},
    3: {"name": "Annual", "role": "Output.*.Annual", "description": "FY aggregations, portfolio summaries"},
    4: {"name": "Goals", "role": "Output.Goal", "description": "Goal progress and alerts"},
    5: {"name": "Macro", "role": "Output.Macro.*", "description": "Broker dashboard KPIs"},
}

TIER_COLORS = {
    0: "#ef4444",  # Red
    1: "#f59e0b",  # Amber
    2: "#10b981",  # Emerald
    3: "#3b82f6",  # Blue
    4: "#8b5cf6",  # Purple
    5: "#ec4899",  # Pink
}

# Relation types from DEP_TABLE
RELATION_TYPES = [
    "input_to_monthly",
    "input_to_annual",
    "input_to_dashboard",
    "chart_aggregation",
    "aggregate_to_portfolio",
    "cgt_logic",
    "loan_association",
    "goal_logic",
    "equity_logic",
    "calculation",
    "depends_on",
]
