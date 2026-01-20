"""
Graph Schema Definitions

Defines the structure of nodes and edges in the ScaleAI knowledge graph.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class NodeType(str, Enum):
    FIELD = "FIELD"
    CONCEPT = "CONCEPT"
    TOOL = "TOOL"
    LOGIC = "LOGIC"


class EdgeType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    EXPLAINED_BY = "EXPLAINED_BY"
    RETURNS = "RETURNS"
    USES_LOGIC = "USES_LOGIC"
    RELATED_TO = "RELATED_TO"


class FieldNode(BaseModel):
    """
    Represents a data field from the DTO_INDEX.
    
    Example:
        id: "/v1/property-cashflow/{id}.months[].lvr"
        label: "LVR"
        tier: 2
        section: "PROPERTY_CASHFLOWS"
    """
    id: str = Field(..., description="Full API path (e.g., /v1/property-cashflow/{id}.lvr)")
    type: Literal["FIELD"] = "FIELD"
    label: str = Field(..., description="Human-readable field name")
    tier: int = Field(..., ge=0, le=5, description="Tier level (1-5)")
    tier_name: Optional[str] = Field(default=None, description="Tier name (Input, Monthly, etc.)")
    section: Optional[str] = Field(default=None, description="Database section")
    endpoint: Optional[str] = Field(default=None, description="API endpoint")
    data_type: Optional[str] = Field(default=None, description="Data type (string, number, etc.)")
    definition: Optional[str] = Field(default=None, description="Field definition/description")
    user_controllable: bool = Field(default=False, description="Can user directly modify this?")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "/v1/property-cashflow/{id}.months[].lvr",
                "type": "FIELD",
                "label": "LVR",
                "tier": 2,
                "tier_name": "Monthly",
                "section": "PROPERTY_CASHFLOWS",
                "definition": "Loan-to-Value Ratio - loan balance divided by property value",
                "user_controllable": False
            }
        }


class ConceptNode(BaseModel):
    """
    Represents an educational concept from the KB_TABLE.
    
    Example:
        id: "EDU_020_LVR_OVERVIEW"
        label: "LVR Overview"
        category: "EDU"
    """
    id: str = Field(..., description="Vector ID (e.g., EDU_020_LVR_OVERVIEW)")
    type: Literal["CONCEPT"] = "CONCEPT"
    label: str = Field(..., description="Concept title")
    category: str = Field(..., description="Category prefix (EDU, DEP, FAQ, EX)")
    payload: Optional[str] = Field(default=None, description="Educational content (markdown)")
    ai_prompt: Optional[str] = Field(default=None, description="AI response instructions")
    interpretation: Optional[str] = Field(default=None, description="ScaleApp-specific logic")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "EDU_020_LVR_OVERVIEW",
                "type": "CONCEPT",
                "label": "LVR Overview",
                "category": "EDU",
                "payload": "**Loan-to-Value Ratio (LVR)**: Percentage showing loan amount..."
            }
        }


class ToolNode(BaseModel):
    """
    Represents an API tool from the TOOLS sheet.
    """
    id: str = Field(..., description="Tool name")
    type: Literal["TOOL"] = "TOOL"
    label: str = Field(..., description="Tool display name")
    endpoint: Optional[str] = Field(default=None, description="API endpoint")
    description: Optional[str] = Field(default=None, description="Tool description")
    parameters: Optional[List[str]] = Field(default=None, description="Required parameters")
    returns: Optional[List[str]] = Field(default=None, description="Field IDs returned")


class DependsOnEdge(BaseModel):
    """
    Represents a dependency relationship from DEP_TABLE.
    
    Direction: target DEPENDS_ON source
    (target is calculated FROM source)
    
    Example:
        source: "/v1/property-input/{id}/loan.loanAmount"
        target: "/v1/property-cashflow/{id}.months[].lvr"
        relation: "input_to_monthly"
    """
    source: str = Field(..., description="Upstream field (input)")
    target: str = Field(..., description="Downstream field (output)")
    type: Literal["DEPENDS_ON"] = "DEPENDS_ON"
    relation: str = Field(default="depends_on", description="Relation type from DEP_TABLE")
    interpretation: Optional[str] = Field(default=None, description="How source affects target")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source": "/v1/property-input/{id}/loan.loanAmount",
                "target": "/v1/property-cashflow/{id}.months[].lvr",
                "type": "DEPENDS_ON",
                "relation": "input_to_monthly",
                "interpretation": "Loan amount is the numerator in LVR calculation"
            }
        }


class ExplainedByEdge(BaseModel):
    """
    Links a FIELD to a CONCEPT that explains it.
    
    Example:
        field_id: "/v1/property-cashflow/{id}.months[].lvr"
        concept_id: "EDU_020_LVR_OVERVIEW"
    """
    field_id: str = Field(..., description="Field being explained")
    concept_id: str = Field(..., description="Concept that explains it")
    type: Literal["EXPLAINED_BY"] = "EXPLAINED_BY"
    context: Optional[str] = Field(default="theory", description="Context type")


class GraphStats(BaseModel):
    """Statistics about the loaded graph"""
    total_nodes: int
    total_edges: int
    nodes_by_type: dict
    nodes_by_tier: dict
    edges_by_type: dict


class TraversalResult(BaseModel):
    """Result of a graph traversal operation"""
    target: str
    direction: Literal["upstream", "downstream", "both"]
    depth: int
    paths: List[List[str]]
    nodes: List[FieldNode]
    concepts: List[ConceptNode]
