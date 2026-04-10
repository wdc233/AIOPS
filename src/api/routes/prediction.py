"""Prediction API routes for trend-based risk prediction."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.api.dependencies import get_api_service
from src.api.schemas import (
    PredictionMetric,
    PredictionRequest,
    PredictionResponse,
    PredictionResult,
    PredictionTarget,
)
from src.tools.prometheus import PrometheusQueryTool
from src.tools.trend import TrendPredictionTool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/prediction/risk", response_model=PredictionResponse)
async def get_risk_prediction(request: PredictionRequest) -> PredictionResponse:
    """Execute trend-based risk prediction on specified targets.

    Supports multiple target types:
    - cluster: Predict for all servers in the cluster
    - ip: Specific server IP(s)
    - prometheus_url: Direct Prometheus metric URL

    If no metrics specified, predicts all available metrics for targets.
    If specified metric not found in Prometheus, returns error.

    Args:
        request: Prediction request with targets and metrics

    Returns:
        Prediction results with risk levels for each target and metric
    """
    service = get_api_service()
    env_manager = service.get_environment_manager()
    prometheus_tool = service.get_prometheus_tool()
    trend_tool = TrendPredictionTool()

    prediction_id = str(uuid.uuid4())
    results: List[PredictionResult] = []
    errors: List[str] = []
    targets_processed = 0

    # Step 1: Resolve all target IPs
    target_ips = await _resolve_targets(request.targets, env_manager)

    if not target_ips:
        return PredictionResponse(
            prediction_id=prediction_id,
            status="failed",
            targets_processed=0,
            results=[],
            errors=["No valid targets found"],
        )

    targets_processed = len(target_ips)

    # Step 2: Get available metrics from Prometheus
    available_metrics = await _get_available_metrics(prometheus_tool)

    # Step 3: Determine which metrics to predict
    metrics_to_predict = _determine_metrics(request.metrics, available_metrics)

    if not metrics_to_predict:
        return PredictionResponse(
            prediction_id=prediction_id,
            status="failed",
            targets_processed=targets_processed,
            results=[],
            errors=["Unable to determine metrics for prediction"],
        )

    # Step 4: Execute prediction for each target and metric
    for target_ip in target_ips:
        for metric in metrics_to_predict:
            result = await _predict_target_metric(
                target=target_ip,
                metric=metric,
                threshold=metric.get("threshold"),
                trend_tool=trend_tool,
                prometheus_tool=prometheus_tool,
                historical_range=request.time_range,
                prediction_horizon=request.prediction_horizon,
            )

            if result:
                results.append(result)
            else:
                errors.append(f"Failed to predict {metric['name']} for {target_ip}")

    # Determine overall status
    if not results and errors:
        status = "failed"
    elif errors and results:
        status = "partial"
    else:
        status = "completed"

    return PredictionResponse(
        prediction_id=prediction_id,
        status=status,
        targets_processed=targets_processed,
        results=results,
        errors=errors,
    )


async def _resolve_targets(
    targets: List[PredictionTarget],
    env_manager,
) -> List[str]:
    """Resolve all targets to IP addresses.

    Args:
        targets: List of prediction targets
        env_manager: Environment manager

    Returns:
        List of target IP addresses
    """
    resolved_ips: List[str] = []
    seen_ips = set()

    for target in targets:
        if target.type == "ip":
            if target.value not in seen_ips:
                resolved_ips.append(target.value)
                seen_ips.add(target.value)

        elif target.type == "cluster":
            servers = env_manager.get_servers_by_cluster(target.value)
            for server in servers:
                if server.ip not in seen_ips:
                    resolved_ips.append(server.ip)
                    seen_ips.add(server.ip)

        elif target.type == "prometheus_url":
            if target.value not in seen_ips:
                resolved_ips.append(target.value)
                seen_ips.add(target.value)

    return resolved_ips


async def _get_available_metrics(prometheus_tool: PrometheusQueryTool) -> List[str]:
    """Get all available metric names from Prometheus.

    Args:
        prometheus_tool: Prometheus query tool

    Returns:
        List of available metric names
    """
    try:
        result = await prometheus_tool.get_metric_names()
        if result and result.success:
            return result.data or []
    except Exception as e:
        logger.warning(f"Failed to get available metrics: {e}")

    return []


def _determine_metrics(
    requested_metrics: Optional[List[PredictionMetric]],
    available_metrics: List[str],
) -> List[Dict[str, Any]]:
    """Determine which metrics to predict.

    Args:
        requested_metrics: User-specified metrics
        available_metrics: Metrics available in Prometheus

    Returns:
        List of metrics to predict with metadata
    """
    if not requested_metrics:
        # Default metrics for prediction
        default_metrics = [
            {"name": "cpu_usage", "threshold": 90.0},
            {"name": "memory_usage", "threshold": 90.0},
        ]
        return default_metrics

    metrics = []
    for m in requested_metrics:
        metric_name = m.name
        possible_names = [
            metric_name,
            f"{metric_name}_usage",
            f"{metric_name}_percent",
        ]

        found = False
        for name in possible_names:
            if name in available_metrics:
                metrics.append({
                    "name": name,
                    "threshold": m.threshold or 90.0,
                })
                found = True
                break

        if not found:
            metrics.append({
                "name": metric_name,
                "threshold": m.threshold or 90.0,
            })

    return metrics


async def _predict_target_metric(
    target: str,
    metric: Dict[str, Any],
    threshold: Optional[float],
    trend_tool: TrendPredictionTool,
    prometheus_tool: PrometheusQueryTool,
    historical_range: str,
    prediction_horizon: str,
) -> Optional[PredictionResult]:
    """Predict risk for a specific metric on a target.

    Args:
        target: Target IP or identifier
        metric: Metric information
        threshold: Warning threshold
        trend_tool: Trend prediction tool
        prometheus_tool: Prometheus query tool
        historical_range: Historical data range
        prediction_horizon: Prediction horizon

    Returns:
        Prediction result or None on error
    """
    metric_name = metric["name"]
    threshold = threshold or 90.0

    try:
        # First, get current value
        if target.startswith("http"):
            query = metric_name
        else:
            query = f'{metric_name}{{instance="{target}"}}'

        current_result = await prometheus_tool.execute(
            query=query,
            time=f"now-{historical_range}",
        )

        current_value = None
        if current_result and current_result.success:
            data = current_result.data or {}
            result_list = data.get("result", [])
            if result_list:
                for item in result_list:
                    value = item.get("value")
                    if value and len(value) >= 2:
                        try:
                            current_value = float(value[1])
                        except (ValueError, TypeError):
                            pass

        # Use trend prediction tool for prediction
        result = await trend_tool.execute(
            metric_name=metric_name,
            target=target,
            time_range=historical_range,
            threshold=threshold,
        )

        if not result or not result.success:
            # Fallback: simple trend calculation
            return await _simple_prediction(
                target=target,
                metric_name=metric_name,
                current_value=current_value,
                threshold=threshold,
                prometheus_tool=prometheus_tool,
                historical_range=historical_range,
                prediction_horizon=prediction_horizon,
            )

        # Parse trend prediction result
        result_data = result.data or {}

        predicted_value = result_data.get("predicted_value")
        risk_level = result_data.get("risk_level", "low")
        trend = result_data.get("trend", "stable")

        # Map risk level to allowed values
        if risk_level not in ("low", "medium", "high", "critical"):
            risk_level = "low"
        if trend not in ("increasing", "decreasing", "stable"):
            trend = "stable"

        return PredictionResult(
            target=target,
            metric=metric_name,
            current_value=current_value,
            predicted_value=predicted_value,
            risk_level=risk_level,
            trend=trend,
            details={
                "threshold": threshold,
                "historical_range": historical_range,
                "prediction_horizon": prediction_horizon,
            },
        )

    except Exception as e:
        logger.error(f"Prediction failed for {target}/{metric_name}: {e}")
        return None


async def _simple_prediction(
    target: str,
    metric_name: str,
    current_value: Optional[float],
    threshold: float,
    prometheus_tool: PrometheusQueryTool,
    historical_range: str,
    prediction_horizon: str,
) -> Optional[PredictionResult]:
    """Simple prediction based on recent trend.

    Args:
        target: Target IP
        metric_name: Metric name
        current_value: Current metric value
        threshold: Warning threshold
        prometheus_tool: Prometheus query tool
        historical_range: Historical data range
        prediction_horizon: Prediction horizon

    Returns:
        Prediction result with simple trend analysis
    """
    try:
        # Query range data for trend analysis
        if target.startswith("http"):
            query = metric_name
        else:
            query = f'{metric_name}{{instance="{target}"}}'

        result = await prometheus_tool.query_range(
            query=query,
            start=f"now-{historical_range}",
            end="now",
            step="1h",
        )

        if not result or not result.success:
            # Return current state without prediction
            return PredictionResult(
                target=target,
                metric=metric_name,
                current_value=current_value,
                predicted_value=None,
                risk_level="low",
                trend="stable",
                details={"error": "Unable to perform trend analysis"},
            )

        # Analyze trend
        data = result.data or {}
        result_list = data.get("result", [])
        if not result_list:
            return PredictionResult(
                target=target,
                metric=metric_name,
                current_value=current_value,
                predicted_value=None,
                risk_level="low",
                trend="stable",
                details={"error": "No historical data available"},
            )

        # Get values from time series
        values = []
        for item in result_list:
            values_data = item.get("values", [])
            for v in values_data:
                if len(v) >= 2:
                    try:
                        values.append(float(v[1]))
                    except (ValueError, TypeError):
                        pass

        if len(values) < 2:
            return PredictionResult(
                target=target,
                metric=metric_name,
                current_value=current_value,
                predicted_value=None,
                risk_level="low",
                trend="stable",
                details={"error": "Insufficient historical data"},
            )

        # Calculate simple trend
        recent_values = values[-6:]  # Last 6 data points
        older_values = values[-12:-6] if len(values) >= 12 else values[:-6]

        if older_values and recent_values:
            recent_avg = sum(recent_values) / len(recent_values)
            older_avg = sum(older_values) / len(older_values)

            if recent_avg > older_avg * 1.1:
                trend = "increasing"
                # Simple linear extrapolation
                slope = (recent_avg - older_avg) / len(older_values)
                predicted = recent_avg + slope * 6  # Predict 6 hours ahead
            elif recent_avg < older_avg * 0.9:
                trend = "decreasing"
                predicted = recent_avg
            else:
                trend = "stable"
                predicted = recent_avg
        else:
            trend = "stable"
            predicted = values[-1] if values else current_value

        # Determine risk level
        if predicted and predicted > threshold * 1.2:
            risk_level = "critical"
        elif predicted and predicted > threshold:
            risk_level = "high"
        elif predicted and predicted > threshold * 0.8:
            risk_level = "medium"
        else:
            risk_level = "low"

        return PredictionResult(
            target=target,
            metric=metric_name,
            current_value=current_value,
            predicted_value=predicted,
            risk_level=risk_level,
            trend=trend,
            details={
                "threshold": threshold,
                "historical_range": historical_range,
                "prediction_horizon": prediction_horizon,
            },
        )

    except Exception as e:
        logger.error(f"Simple prediction failed for {target}/{metric_name}: {e}")
        return None