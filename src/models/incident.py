"""
Incident data models for the AIOps system
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class AlertSource(str, Enum):
    PROMETHEUS = "prometheus"
    ELASTICSEARCH = "elasticsearch"
    CUSTOM = "custom"
    SYSTEM = "system"


@dataclass
class Metric:
    """System metric data point"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str]
    source: str


@dataclass
class LogEntry:
    """Log entry data"""
    timestamp: datetime
    level: str
    message: str
    service: str
    source: str
    metadata: Dict[str, Any]


class Alert(BaseModel):
    """Alert model"""
    id: str
    name: str
    severity: IncidentSeverity
    source: AlertSource
    timestamp: datetime
    message: str
    labels: Dict[str, str] = Field(default_factory=dict)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class Incident(BaseModel):
    """Incident model with ML-enhanced fields"""
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    
    # Related data
    alerts: List[Alert] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    
    # ML/AI enhanced fields
    root_cause_analysis: Optional[str] = None
    predicted_resolution_time: Optional[int] = None  # minutes
    similarity_score: Optional[float] = None
    auto_actions_taken: List[str] = Field(default_factory=list)
    llm_explanation: Optional[str] = None
    
    # Correlation data
    correlated_incidents: List[str] = Field(default_factory=list)
    anomaly_score: Optional[float] = None


class SystemHealth(BaseModel):
    """Overall system health status"""
    timestamp: datetime
    overall_score: float  # 0-100
    services_up: int
    services_down: int
    active_alerts: int
    critical_incidents: int
    prediction_confidence: float