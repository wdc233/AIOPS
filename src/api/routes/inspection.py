"""Inspection API routes for immediate inspection execution."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.api.dependencies import get_api_service
from src.api.schemas import (
    InspectionMetric,
    InspectionRequest,
    InspectionResponse,
    InspectionResult,
    InspectionTarget,
)
from src.tools.prometheus import PrometheusQueryTool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/inspection/run", response_model=InspectionResponse)
async def run_inspection(request: InspectionRequest) -> InspectionResponse:
    """Execute immediate inspection on specified targets.

    Supports multiple target types:
    - cluster: Query all servers in the cluster
    - ip: Specific server IP(s)
    - prometheus_url: Direct Prometheus metric URL

    If no metrics specified, inspects all available metrics for targets.
    If specified metric not found in Prometheus, returns error.

    Args:
        request: Inspection request with targets and metrics

    Returns:
        Inspection results for each target and metric
    """
    service = get_api_service()
    env_manager = service.get_environment_manager()
    prometheus_tool = service.get_prometheus_tool()

    inspection_id = str(uuid.uuid4())
    results: List[InspectionResult] = []
    errors: List[str] = []
    targets_processed = 0

    # Step 1: Resolve all target IPs
    target_ips = await _resolve_targets(request.targets, env_manager)

    if not target_ips:
        return InspectionResponse(
            inspection_id=inspection_id,
            status="failed",
            targets_processed=0,
            results=[],
            errors=["No valid targets found"],
        )

    targets_processed = len(target_ips)

    # Step 2: Get available metrics from Prometheus
    available_metrics = await _get_available_metrics(prometheus_tool)

    # Step 3: Determine which metrics to inspect
    metrics_to_inspect = _determine_metrics(request.metrics, available_metrics)

    if not metrics_to_inspect:
        # No valid metrics specified and couldn't get all metrics
        return InspectionResponse(
            inspection_id=inspection_id,
            status="failed",
            targets_processed=targets_processed,
            results=[],
            errors=["Unable to determine metrics to inspect"],
        )

    # Step 4: Execute inspection for each target and metric
    for target_ip in target_ips:
        for metric in metrics_to_inspect:
            result = await _inspect_target_metric(
                target=target_ip,
                metric=metric,
                threshold=metric.get("threshold"),
                prometheus_tool=prometheus_tool,
                time_range=request.time_range,
            )

            if result:
                results.append(result)
            else:
                # Metric not found for this target
                errors.append(f"Metric '{metric['name']}' not found for {target_ip}")

    # Determine overall status
    if not results and errors:
        status = "failed"
    elif errors and results:
        status = "partial"
    else:
        status = "completed"

    return InspectionResponse(
        inspection_id=inspection_id,
        status=status,
        targets_processed=targets_processed,
        results=results,
        errors=errors,
    )


async def _resolve_targets(
    targets: List[InspectionTarget],
    env_manager,
) -> List[str]:
    """Resolve all targets to IP addresses.

    Args:
        targets: List of inspection targets
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
            # For prometheus_url, use the URL directly as identifier
            # This is used for direct Prometheus metric queries
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
    requested_metrics: Optional[List[InspectionMetric]],
    available_metrics: List[str],
) -> List[Dict[str, Any]]:
    """Determine which metrics to inspect.

    Args:
        requested_metrics: User-specified metrics
        available_metrics: Metrics available in Prometheus

    Returns:
        List of metrics to inspect with metadata
    """
    if not requested_metrics:
        # No specific metrics requested, return common system metrics
        default_metrics = [
            {"name": "cpu_usage", "threshold": 80.0},
            {"name": "memory_usage", "threshold": 80.0},
            {"name": "disk_usage", "threshold": 80.0},
            {"name": "up", "threshold": None},
        ]
        return default_metrics

    metrics = []
    for m in requested_metrics:
        # Check if metric exists in Prometheus
        metric_name = m.name
        # Try different naming conventions
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
                    "threshold": m.threshold or 80.0,
                })
                found = True
                break

        if not found:
            # Metric not in common list, try as-is (might be valid PromQL)
            metrics.append({
                "name": metric_name,
                "threshold": m.threshold or 80.0,
            })

    return metrics


async def _inspect_target_metric(
    target: str,
    metric: Dict[str, Any],
    threshold: Optional[float],
    prometheus_tool: PrometheusQueryTool,
    time_range: str,
) -> Optional[InspectionResult]:
    """Inspect a specific metric for a target.

    Args:
        target: Target IP or identifier
        metric: Metric information
        threshold: Warning threshold
        prometheus_tool: Prometheus query tool
        time_range: Time range for query

    Returns:
        Inspection result or None if metric not found
    """
    metric_name = metric["name"]
    threshold = threshold or 80.0

    try:
        # Query current value
        if target.startswith("http"):
            # Direct Prometheus URL
            query = metric_name
        else:
            query = f'{metric_name}{{instance="{target}"}}'

        result = await prometheus_tool.execute(
            query=query,
            time=f"now-{time_range}",
        )

        if not result or not result.success:
            return None

        # Parse result
        data = result.data or {}
        result_list = data.get("result", [])

        if not result_list:
            return None

        # Get the latest value
        latest_value = None
        for item in result_list:
            value = item.get("value")
            if value and len(value) >= 2:
                try:
                    latest_value = float(value[1])
                except (ValueError, TypeError):
                    pass

        if latest_value is None:
            return InspectionResult(
                target=target,
                metric=metric_name,
                value=None,
                status="error",
                details={"error": "Unable to parse metric value"},
            )

        # Determine status based on threshold
        if threshold and latest_value > threshold:
            status = "critical" if latest_value > threshold * 1.2 else "warning"
        else:
            status = "ok"

        return InspectionResult(
            target=target,
            metric=metric_name,
            value=latest_value,
            status=status,
            details={
                "threshold": threshold,
                "time_range": time_range,
            },
        )

    except Exception as e:
        logger.error(f"Inspection failed for {target}/{metric_name}: {e}")
        return InspectionResult(
            target=target,
            metric=metric_name,
            value=None,
            status="error",
            details={"error": str(e)},
        )