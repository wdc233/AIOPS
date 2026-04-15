"""Pydantic schemas for API request/response."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# --- Enums ---

class IntentTypeEnum(str, Enum):
    """Intent type enum."""

    QUERY_INFO = "query_info"
    QUERY_METRIC = "query_metric"
    CHECK_STATUS = "check_status"
    RUN_INSPECTION = "run_inspection"
    UNKNOWN = "unknown"


# --- Chat API ---

class ChatRequest(BaseModel):
    """User chat request."""

    session_id: str = Field(..., description="Unique session ID for multi-round conversation")
    message: str = Field(..., description="User message content")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ChatResponse(BaseModel):
    """User chat response."""

    session_id: str = Field(..., description="Session ID")
    message: str = Field(..., description="AI response message")
    intent: Optional[IntentTypeEnum] = Field(None, description="Recognized intent type")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data (results, etc.)")
    requires_confirmation: bool = Field(default=False, description="Whether user confirmation is needed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


# --- Inspection API ---

class InspectionTarget(BaseModel):
    """Inspection target specification."""

    type: Literal["cluster", "ip", "prometheus_url"] = Field(..., description="Target type")
    value: str = Field(..., description="Target value (cluster name, IP, or Prometheus URL)")


class InspectionMetric(BaseModel):
    """Inspection metric specification."""

    name: str = Field(..., description="Metric name (cpu, memory, disk, network, request_count, etc.)")
    threshold: Optional[float] = Field(None, description="Warning threshold")


class InspectionRequest(BaseModel):
    """Inspection request."""

    targets: List[InspectionTarget] = Field(..., description="Inspection targets")
    metrics: Optional[List[InspectionMetric]] = Field(None, description="Metrics to inspect. If empty, inspect all available metrics")
    time_range: str = Field(default="1h", description="Time range for data collection")


class InspectionResult(BaseModel):
    """Inspection result for a single target."""

    target: str = Field(..., description="Target IP or identifier")
    metric: str = Field(..., description="Metric name")
    value: Optional[float] = Field(None, description="Current value")
    status: Literal["ok", "warning", "critical", "error"] = Field(..., description="Status")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class InspectionResponse(BaseModel):
    """Inspection response."""

    inspection_id: str = Field(..., description="Unique inspection ID")
    status: Literal["completed", "partial", "failed"] = Field(..., description="Overall status")
    targets_processed: int = Field(default=0, description="Number of targets processed")
    results: List[InspectionResult] = Field(default_factory=list, description="Inspection results")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


# --- Prediction API ---

class PredictionTarget(BaseModel):
    """Prediction target specification."""

    type: Literal["cluster", "ip", "prometheus_url"] = Field(..., description="Target type")
    value: str = Field(..., description="Target value")


class PredictionMetric(BaseModel):
    """Prediction metric specification."""

    name: str = Field(..., description="Metric name")
    threshold: float = Field(default=90.0, description="Warning threshold")


class PredictionRequest(BaseModel):
    """Risk prediction request."""

    targets: List[PredictionTarget] = Field(..., description="Prediction targets")
    metrics: Optional[List[PredictionMetric]] = Field(None, description="Metrics to predict. If empty, predict all available metrics")
    time_range: str = Field(default="7d", description="Historical time range for prediction")
    prediction_horizon: str = Field(default="24h", description="Prediction horizon")


class PredictionResult(BaseModel):
    """Prediction result for a single metric."""

    target: str = Field(..., description="Target IP or identifier")
    metric: str = Field(..., description="Metric name")
    current_value: Optional[float] = Field(None, description="Current value")
    predicted_value: Optional[float] = Field(None, description="Predicted value")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(..., description="Risk level")
    trend: Literal["increasing", "decreasing", "stable"] = Field(..., description="Trend direction")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class PredictionResponse(BaseModel):
    """Risk prediction response."""

    prediction_id: str = Field(..., description="Unique prediction ID")
    status: Literal["completed", "partial", "failed"] = Field(..., description="Overall status")
    targets_processed: int = Field(default=0, description="Number of targets processed")
    results: List[PredictionResult] = Field(default_factory=list, description="Prediction results")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


# --- Error Response ---

class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")