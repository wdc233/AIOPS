"""Chat API routes for user dialogue."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from langchain_core.messages import SystemMessage, HumanMessage

from src.api.dependencies import get_api_service, get_session_manager
from src.api.schemas import ChatRequest, ChatResponse, IntentTypeEnum
from src.agent import templates as T  # noqa: N814
from src.models.types import IntentType

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_intent_type_str(intent) -> Optional[str]:
    """Safely get intent_type as string from UserIntent."""
    if not intent or not intent.intent_type:
        return "unknown"
    if isinstance(intent.intent_type, IntentType):
        return intent.intent_type.value
    return str(intent.intent_type)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Handle user chat message with multi-round conversation support.

    Args:
        request: Chat request with session_id and message

    Returns:
        Chat response with AI message and optional data
    """
    service = get_api_service()
    session_manager = get_session_manager()

    session = await session_manager.get_or_create_session(request.session_id)

    # Add user message to history
    await session_manager.add_to_history(request.session_id, "user", request.message)

    requires_confirmation = False

    # Check if this is a confirmation response
    if session.intent and not session.confirmed:
        confirm_keywords = ["确认", "是", "ok", "yes", "confirm", "执行", "开始"]
        if any(kw in request.message.lower() for kw in confirm_keywords):
            # User confirmed, execute the intent
            intent_to_execute = session.intent

            # Check if there's a pending metric suggestion to apply
            if session.pending_metric_suggestion and session.pending_metric_suggestion.get("similar_metrics"):
                similar_metrics = session.pending_metric_suggestion.get("similar_metrics", [])
                if similar_metrics:
                    # Use the first suggested metric
                    new_metric = similar_metrics[0]
                    intent_to_execute.metric_name = new_metric
                    logger.info(f"Using suggested metric: {new_metric}")

            await session_manager.update_session(
                request.session_id,
                confirmed=True,
                pending_metric_suggestion=None  # Clear pending suggestion
            )
            result_data = await _execute_intent(service, intent_to_execute)
            response_message = _build_result_message(intent_to_execute, result_data)
        else:
            # User didn't confirm, ask again
            response_message = "好的，请问还有什么可以帮您？"
    else:
        # New intent recognition
        intent_agent = service.get_intent_agent()
        intent_result = await intent_agent.recognize_intent(request.message)

        intent = intent_result.get("intent")
        requires_confirmation = intent_result.get("requires_confirmation", False)
        messages = intent_result.get("messages", [])

        if intent:
            await session_manager.update_session(request.session_id, intent=intent, confirmed=False)

        # Handle based on intent type and confidence
        if intent and intent.intent_type == IntentType.CHAT:
            # CHAT: direct LLM response using template
            response_message = T.CHAT_GREETING
            requires_confirmation = False
        elif intent and intent.intent_type == IntentType.UNKNOWN:
            # UNKNOWN: guide user to valid intents
            response_message = T.FALLBACK
            requires_confirmation = False
        elif intent and intent.confidence < 0.5:
            # Fallback: confidence too low
            response_message = T.FALLBACK
            requires_confirmation = False
        elif requires_confirmation and messages:
            # Ask for confirmation or missing info
            msg = messages[0]
            if msg.get("type") == "fallback":
                response_message = T.FALLBACK
            elif msg.get("type") == "ask":
                response_message = msg.get("content", T.ASK_TARGET)
            else:
                response_message = msg.get("content", "请问确认您的请求？")
        else:
            # Execute directly (confidence >= 0.9)
            requires_confirmation = False
            result_data = await _execute_intent(service, intent) if intent else None

            # Check if we got a metric suggestion response
            if result_data and result_data.get("metric_suggestion"):
                # Save the suggestion to session for when user confirms
                await session_manager.update_session(
                    request.session_id,
                    pending_metric_suggestion={
                        "original_metric": result_data.get("original_metric"),
                        "similar_metrics": result_data.get("similar_metrics", []),
                        "target": result_data.get("target"),
                    }
                )
                # Set requires_confirmation to show the suggestion to user
                requires_confirmation = True

            response_message = _build_result_message(intent, result_data)

    await session_manager.add_to_history(request.session_id, "assistant", response_message)

    return ChatResponse(
        session_id=request.session_id,
        message=response_message,
        intent=IntentTypeEnum(_get_intent_type_str(session.intent)) if session.intent else None,
        data=None,
        requires_confirmation=bool(requires_confirmation),
    )


def _build_result_message(intent, result_data: Optional[Dict[str, Any]]) -> str:
    """Build result message using templates based on intent type."""
    if not intent:
        return T.ERROR_EXECUTION_FAILED.format(reason="未知错误")

    if result_data and result_data.get("error"):
        return T.ERROR_QUERY_FAILED.format(reason=result_data["error"])

    target = intent.target_cluster or intent.target_ip or ""

    if intent.intent_type == IntentType.QUERY_INFO:
        if result_data and result_data.get("server_count") is not None:
            cluster = result_data.get("cluster", target)
            server_count = result_data["server_count"]
            servers = result_data.get("servers", [])
            server_list = "\n".join([f"- {s['ip']} (端口: {s['port']})" for s in servers]) if servers else ""
            return T.RESULT_QUERY_INFO_SERVERS.format(
                cluster=cluster,
                server_count=server_count,
                server_list=server_list
            )
        return T.ERROR_NO_CLUSTER

    elif intent.intent_type == IntentType.QUERY_METRIC:
        # Handle single metric inspection result
        if result_data and result_data.get("type") == "single_metric":
            metric = result_data.get("metric", "指标")
            results = result_data.get("results", [])
            cluster = result_data.get("cluster", target)

            if not results:
                return T.ERROR_QUERY_FAILED.format(reason="未获取到任何数据")

            lines = [f"## {metric} 巡检报告（集群: {cluster}）"]

            for r in results:
                target_ip = r.get("target", "unknown")
                if r.get("success"):
                    value = r.get("value", "N/A")
                    analysis = r.get("analysis", "")
                    source = r.get("source", "unknown")
                    lines.append(f"\n**{target_ip}** [{source}]: {value}")
                    if analysis:
                        lines.append(f"  分析: {analysis}")
                else:
                    error = r.get("error", "未知错误")
                    lines.append(f"\n**{target_ip}**: 获取失败 - {error}")

            return "\n".join(lines)

        # Fallback: simple metric query result
        if result_data and result_data.get("results"):
            results = result_data["results"]
            metric = intent.metric_name or "指标"
            values = []
            for r in results:
                if r.get("data"):
                    values.append(f"{r['target']}: {r['data']}")
            if values:
                return f"{metric} 查询结果：\n" + "\n".join(values)
        return T.ERROR_QUERY_FAILED.format(reason="未查询到数据")

    elif intent.intent_type == IntentType.CHECK_STATUS:
        if result_data:
            cluster = result_data.get("cluster", target)
            server_count = result_data.get("server_count", 0)
            return T.RESULT_INSPECT_OK.format(cluster=cluster)
        return T.RESULT_CHECK_STATUS_OK.format(target=target)

    elif intent.intent_type == IntentType.RUN_INSPECTION:
        if result_data:
            cluster = result_data.get("cluster", target)
            inspection_result = result_data.get("inspection_result", {})
            if not isinstance(inspection_result, dict):
                return T.ERROR_EXECUTION_FAILED.format(reason="巡检服务返回异常")
            if inspection_result.get("success"):
                results = inspection_result.get("results", [])
                if results:
                    # Build summary from inspection results
                    summary_lines = [f"集群 {cluster} 巡检完成："]
                    for r in results:
                        target_ip = r.get("target", "unknown")
                        analysis = r.get("analysis", {})
                        issues = []
                        if isinstance(analysis, dict):
                            for check_type, check_data in analysis.items():
                                status = check_data.get("status", "unknown") if isinstance(check_data, dict) else "unknown"
                                if status in ("warning", "critical"):
                                    value = check_data.get("value", "N/A") if isinstance(check_data, dict) else "N/A"
                                    issues.append(f"{check_type}={value}%({status})")
                        if issues:
                            summary_lines.append(f"- {target_ip}: {', '.join(issues)}")
                        else:
                            summary_lines.append(f"- {target_ip}: 正常")
                    return "\n".join(summary_lines)
                else:
                    return T.RESULT_INSPECT_OK.format(cluster=cluster)
            else:
                error = inspection_result.get("error", "未知错误") if isinstance(inspection_result, dict) else "未知错误"
                return T.ERROR_EXECUTION_FAILED.format(reason=error)
        return T.ERROR_EXECUTION_FAILED.format(reason="巡检启动失败")

    elif intent.intent_type == IntentType.PREDICT_RISK:
        if result_data:
            # Handle metric suggestion case (metric not found)
            if result_data.get("metric_suggestion"):
                similar = result_data.get("similar_metrics", [])
                return T.ERROR_METRIC_SUGGESTION.format(
                    metric=result_data.get("original_metric", ""),
                    similar_metrics="\n".join([f"- {m}" for m in similar])
                )

            # Handle error case
            if result_data.get("error"):
                return T.ERROR_METRIC_NOT_FOUND.format(
                    metric=result_data.get("original_metric", result_data.get("metric", "")),
                    available_metrics="\n".join([f"- {m}" for m in result_data.get("available_metrics", [])])
                )

            # Handle status check case
            if result_data.get("status") == "no_data":
                return f"无法获取 {result_data.get('target', target)} 的预测数据，请检查目标是否正确配置。"

            risk_level = result_data.get("risk_level", "unknown")
            horizon = result_data.get("horizon", "24h")
            prediction_type = result_data.get("prediction_type", "single")
            results = result_data.get("results", [])

            # Build prediction message
            if prediction_type == "full" and results:
                # Full metric prediction - show summary for each metric
                lines = [f"## {target} 全量风险预测报告"]

                for r in results:
                    metric = r.get("metric", "unknown")
                    rl = r.get("risk_level", "unknown")
                    trend = r.get("trend", "stable")
                    stats = r.get("statistics", {})

                    risk_icon = "✅" if rl == "low" else "⚠️" if rl == "medium" else "🔴"
                    trend_icon = "📈" if trend == "increasing" else "📉" if trend == "decreasing" else "➡️"

                    lines.append(f"\n{risk_icon} **{metric}**: {rl.upper()} {trend_icon}")

                    if stats:
                        lines.append(f"   平均值: {stats.get('average', 'N/A')}, 最大: {stats.get('max', 'N/A')}, 最小: {stats.get('min', 'N/A')}")

                # Add overall risk level
                if risk_level == "critical":
                    lines.append(f"\n🔴 综合风险等级：严重！建议立即处理！")
                elif risk_level == "high":
                    lines.append(f"\n⚠️ 综合风险等级：高，建议关注。")
                elif risk_level == "medium":
                    lines.append(f"\n⚠️ 综合风险等级：中等，可持续监控。")
                else:
                    lines.append(f"\n✅ 综合风险等级：低，系统运行正常。")

                return "\n".join(lines)
            else:
                # Single metric prediction
                if results:
                    r = results[0]
                    trend = r.get("trend", "stable")
                    stats = r.get("statistics", {})
                    slope = r.get("slope", 0)

                    if risk_level == "low":
                        msg = T.RESULT_PREDICT_RISK_LOW.format(target=target, horizon=horizon)
                    elif risk_level == "medium":
                        msg = T.RESULT_PREDICT_RISK_MEDIUM.format(target=target, risk_type=r.get("metric", "指标"))
                    elif risk_level == "high":
                        msg = T.RESULT_PREDICT_RISK_HIGH.format(target=target, risk_type=r.get("metric", "指标"))
                    elif risk_level == "critical":
                        msg = f"{target} 风险等级：严重！{r.get('metric', '指标')} 已超过阈值，建议立即处理！"
                    else:
                        msg = f"{target} 风险预测结果：{risk_level}"

                    if trend and trend != "stable":
                        msg += f"\n趋势：{trend}（斜率: {slope:.4f}）"

                    if stats:
                        msg += f"\n统计：平均值={stats.get('average', 'N/A')}, 最大值={stats.get('max', 'N/A')}, 最小值={stats.get('min', 'N/A')}"

                    return msg

            return f"{target} 风险预测结果：{risk_level}"
        return T.ERROR_QUERY_FAILED.format(reason="风险预测失败")

    return T.ERROR_EXECUTION_FAILED.format(reason="未知意图类型")


async def _execute_intent(service, intent) -> Optional[Dict[str, Any]]:
    """Execute the recognized intent and return data."""
    if not intent:
        return None

    env_manager = service.get_environment_manager()
    prometheus_tool = service.get_prometheus_tool()

    # Resolve targets
    targets = []
    if intent.target_ip:
        targets = [intent.target_ip]
    elif intent.target_cluster:
        servers = env_manager.get_servers_by_cluster(intent.target_cluster)
        targets = [s.ip for s in servers]

    if not targets and intent.intent_type not in (IntentType.CHAT, IntentType.PREDICT_RISK):
        return {"error": "无法解析目标服务器"}

    # Execute based on intent type
    if intent.intent_type == IntentType.QUERY_METRIC:
        # Priority: single metric inspection with LLM analysis
        if intent.metric_name and targets:
            return await _execute_single_metric_inspection(service, intent, targets)
        # Fallback: simple Prometheus query
        metric_name = intent.metric_name or "up"
        results = []
        for target in targets:
            query = f'{metric_name}{{instance="{target}"}}'
            result = await prometheus_tool.execute(query=query)
            if result and result.success:
                results.append({"target": target, "metric": metric_name, "data": result.data})
        return {"type": "metric_query", "results": results}

    elif intent.intent_type == IntentType.QUERY_INFO:
        if intent.target_cluster:
            servers = env_manager.get_servers_by_cluster(intent.target_cluster)
            if servers:
                server_list = [{"ip": s.ip, "port": s.port, "username": s.username} for s in servers]
                return {
                    "type": "query_info",
                    "cluster": intent.target_cluster,
                    "server_count": len(servers),
                    "servers": server_list,
                }
            return {"error": f"集群 {intent.target_cluster} 不存在或没有服务器"}
        elif intent.target_ip:
            server = env_manager.get_server(intent.target_ip)
            if server:
                return {
                    "type": "query_info",
                    "server": {"ip": server.ip, "port": server.port, "username": server.username, "cluster": server.cluster_name},
                }
            return {"error": f"服务器 {intent.target_ip} 不存在"}
        return {"error": "请指定集群名称或服务器IP"}

    elif intent.intent_type == IntentType.CHECK_STATUS:
        if intent.target_cluster:
            servers = env_manager.get_servers_by_cluster(intent.target_cluster)
            return {
                "type": "status_check",
                "cluster": intent.target_cluster,
                "server_count": len(servers) if servers else 0,
            }
        return {"type": "status_check", "target": intent.target_ip or intent.target_cluster or "unknown"}

    elif intent.intent_type == IntentType.RUN_INSPECTION:
        if intent.target_cluster:
            servers = env_manager.get_servers_by_cluster(intent.target_cluster)
            targets = [s.ip for s in servers] if servers else []
            # Actually run the inspection
            inspection_result = await service.run_inspection(
                targets=targets,
                cluster_name=intent.target_cluster
            )
            return {
                "type": "inspection",
                "cluster": intent.target_cluster,
                "targets": targets,
                "inspection_result": inspection_result,
            }
        elif intent.target_ip:
            # Run inspection on single IP
            inspection_result = await service.run_inspection(
                targets=[intent.target_ip],
                cluster_name=None
            )
            return {
                "type": "inspection",
                "target": intent.target_ip,
                "inspection_result": inspection_result,
            }
        return {"type": "inspection", "target": intent.target_ip or intent.target_cluster or "unknown"}

    elif intent.intent_type == IntentType.PREDICT_RISK:
        # Predict risk for target
        # Determine target type and value
        if intent.target_ip:
            target_type = "ip"
            target_value = intent.target_ip
        elif intent.target_cluster:
            target_type = "cluster"
            target_value = intent.target_cluster
        else:
            return {"error": "请指定要预测风险的集群或服务器"}

        # Determine if single-metric or full-metric prediction
        metric_name = intent.metric_name
        is_full_prediction = not metric_name

        # Get Prometheus URL for metric validation
        prometheus_url = None
        if intent.target_cluster:
            cluster = env_manager.get_cluster(intent.target_cluster)
            if cluster:
                prometheus_url = cluster.prometheus_url

        # Build prediction request via API-style call
        from src.api.schemas import PredictionMetric, PredictionTarget

        targets = [PredictionTarget(type=target_type, value=target_value)]
        metrics = None  # None means predict all available

        if metric_name:
            # Single metric: check existence first
            metric_name_normalized = _normalize_metric_name(metric_name)
            available = await _get_available_metrics_for_target(
                prometheus_tool, target_value, metric_name_normalized
            )

            if available and metric_name_normalized not in available:
                # Metric not found, try to find similar
                similar = _find_similar_metrics(metric_name_normalized, available)
                if similar:
                    return {
                        "type": "predict_risk",
                        "metric_suggestion": True,
                        "original_metric": metric_name,
                        "similar_metrics": similar,
                        "target": target_value,
                        "requires_confirmation": True,
                    }
                else:
                    return {
                        "error": f"指标 '{metric_name}' 不存在，可用指标包括：{', '.join(available[:10])}...",
                        "available_metrics": available[:10],
                    }

            # Use specified metric with normalized name
            metrics = [PredictionMetric(name=metric_name_normalized, threshold=80.0)]

        # Call prediction API
        prediction_result = await _call_prediction_api(
            targets=targets,
            metrics=metrics,
            time_range="7d",
            prediction_horizon="24h",
            prometheus_url=prometheus_url,
        )

        return prediction_result

    return None


async def _get_available_metrics_for_target(
    prometheus_tool, target_value: str, metric_name: str
) -> Optional[List[str]]:
    """Get available metrics for a target from Prometheus.

    Args:
        prometheus_tool: Prometheus query tool
        target_value: Target IP or identifier
        metric_name: Metric name to check

    Returns:
        List of available metric names, or None if query failed
    """
    try:
        # Query for the metric to check if it exists
        query = f'{metric_name}{{instance=~"{target_value}:.*"}}'
        result = await prometheus_tool.execute(query=query)
        if result and result.success:
            data = result.data or {}
            if data.get("result"):
                return None  # Metric exists

        # Get all available metrics for this target
        query = f'{{instance=~"{target_value}:.*"}}'
        result = await prometheus_tool.execute(query=query)
        if result and result.success:
            data = result.data or {}
            metrics = set()
            for item in data.get("result", []):
                metric_name = item.get("metric", {}).get("__name__")
                if metric_name:
                    metrics.add(metric_name)
            return list(metrics)
    except Exception as e:
        logger.warning(f"Failed to get available metrics: {e}")
    return None


def _normalize_metric_name(metric_name: str) -> str:
    """Normalize metric name to standard format.

    Args:
        metric_name: User-specified metric name

    Returns:
        Normalized metric name
    """
    metric_lower = metric_name.lower()

    # Map common Chinese/short names to standard metric names
    if metric_lower in ("cpu", "cpu_usage"):
        return "cpu_usage"
    elif metric_lower in ("内存", "memory", "memory_usage"):
        return "memory_usage"
    elif metric_lower in ("磁盘", "disk", "disk_usage"):
        return "disk_usage"
    elif metric_lower in ("网络", "network", "network_usage"):
        return "network_usage"

    # If already has _usage suffix or looks like PromQL, return as-is
    if "_usage" in metric_lower or "_percent" in metric_lower:
        return metric_name

    # Otherwise append _usage
    return f"{metric_name}_usage"


def _find_similar_metrics(metric_name: str, available: List[str]) -> Optional[List[str]]:
    """Find similar metrics when exact match not found.

    Args:
        metric_name: User-specified metric name
        available: List of available metric names

    Returns:
        List of similar metrics, or None if nothing similar found
    """
    metric_lower = metric_name.lower()
    similar = []

    # Remove _usage suffix for comparison
    base_name = metric_lower.replace("_usage", "").replace("_percent", "")

    for avail in available:
        avail_lower = avail.lower()
        # Check if base name matches
        if base_name in avail_lower or avail_lower in base_name:
            similar.append(avail)
        # Check for common keywords
        keywords = ["cpu", "memory", "mem", "disk", "network", "net", "load", "disk", "io"]
        for kw in keywords:
            if kw in base_name and kw in avail_lower:
                similar.append(avail)
                break

    # Return top 3 similar metrics
    return similar[:3] if similar else None


async def _call_prediction_api(
    targets: List[Any],
    metrics: Optional[List[Any]] = None,
    time_range: str = "7d",
    prediction_horizon: str = "24h",
    prometheus_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Call prediction API in API-style.

    Args:
        targets: List of PredictionTarget
        metrics: List of PredictionMetric (None for all)
        time_range: Historical data range
        prediction_horizon: Prediction horizon
        prometheus_url: Optional Prometheus URL override

    Returns:
        Prediction result dictionary
    """
    from src.tools.trend import TrendPredictionTool

    # Get target value (single target for now)
    target_obj = targets[0]
    target = target_obj.value

    # Use default metrics if not specified
    if not metrics:
        metrics = [
            PredictionMetric(name="cpu_usage", threshold=80.0),
            PredictionMetric(name="memory_usage", threshold=80.0),
            PredictionMetric(name="disk_usage", threshold=80.0),
        ]

    trend_tool = TrendPredictionTool(prometheus_url=prometheus_url)
    all_results = []
    has_high_risk = False

    for metric in metrics:
        try:
            result = await trend_tool.execute(
                metric_name=metric.name,
                target=target,
                time_range=time_range,
                threshold=metric.threshold,
            )

            if result and result.success:
                data = result.data or {}
                risk_level = data.get("risk_level", "low")
                if risk_level in ("high", "critical"):
                    has_high_risk = True

                all_results.append({
                    "metric": metric.name,
                    "risk_level": risk_level,
                    "trend": data.get("trend", "stable"),
                    "statistics": data.get("statistics", {}),
                    "slope": data.get("slope", 0),
                })
        except Exception as e:
            logger.warning(f"Prediction failed for {metric.name}: {e}")

    # Aggregate results
    if not all_results:
        return {
            "type": "predict_risk",
            "target": target,
            "status": "no_data",
            "message": f"无法获取 {target} 的预测数据",
        }

    # Find highest risk level
    risk_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    max_risk = max(all_results, key=lambda x: risk_levels.get(x.get("risk_level", "low"), 0))
    overall_risk = max_risk.get("risk_level", "low")

    return {
        "type": "predict_risk",
        "target": target,
        "risk_level": overall_risk,
        "prediction_type": "full" if not metrics or len(metrics) > 2 else "single",
        "horizon": prediction_horizon,
        "results": all_results,
        "has_high_risk": has_high_risk,
    }

    return None


async def _execute_single_metric_inspection(service, intent, targets: list) -> Dict[str, Any]:
    """Execute single metric inspection with SSH/Prometheus and LLM analysis.

    Args:
        service: API service instance
        intent: User intent with metric_name
        targets: List of target IPs

    Returns:
        Single metric inspection result
    """
    from src.agent.single_metric_inspector import SingleMetricInspector
    from src.config.constants import BASIC_METRICS

    env_manager = service.get_environment_manager()
    inspector = SingleMetricInspector()

    metric = intent.metric_name or "cpu"

    # Inspect each target
    results = []
    for target in targets:
        cluster_info = None
        if intent.target_cluster:
            cluster_info = env_manager.get_cluster(intent.target_cluster)

        result = await inspector.inspect(
            target_ip=target,
            metric_name=metric,
            cluster_info=cluster_info,
        )
        results.append(result)

    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count

    return {
        "type": "single_metric",
        "metric": metric,
        "cluster": intent.target_cluster,
        "total_targets": len(targets),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
    }
