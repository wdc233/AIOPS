"""Chat API routes for user dialogue."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

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
            await session_manager.update_session(request.session_id, confirmed=True)
            result_data = await _execute_intent(service, session.intent)
            response_message = _build_result_message(session.intent, result_data)
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
        if result_data and result_data.get("results"):
            results = result_data["results"]
            metric = intent.metric_name or "指标"
            # Simple format for now
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
            risk_level = result_data.get("risk_level", "unknown")
            trend = result_data.get("trend", "stable")
            horizon = result_data.get("horizon", "24h")
            prediction_data = result_data.get("prediction_data", {})

            # Build detailed prediction message
            if risk_level == "low":
                msg = T.RESULT_PREDICT_RISK_LOW.format(target=target, horizon=horizon)
            elif risk_level == "medium":
                msg = T.RESULT_PREDICT_RISK_MEDIUM.format(target=target, risk_type=prediction_data.get("metric_name", "指标"))
            elif risk_level == "high":
                msg = T.RESULT_PREDICT_RISK_HIGH.format(target=target, risk_type=prediction_data.get("metric_name", "指标"))
            elif risk_level == "critical":
                msg = f"{target} 风险等级：严重！{prediction_data.get('metric_name', '指标')} 已超过阈值，建议立即处理！"
            else:
                msg = f"{target} 风险预测结果：{risk_level}"

            # Add trend information if available
            if trend and trend != "stable":
                msg += f"\n趋势：{trend}（斜率: {prediction_data.get('slope', 0):.4f}）"

            # Add statistics if available
            stats = prediction_data.get("statistics", {})
            if stats:
                msg += f"\n统计：平均值={stats.get('average', 'N/A')}, 最大值={stats.get('max', 'N/A')}, 最小值={stats.get('min', 'N/A')}"

            return msg
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
        # Actually run the prediction
        from src.tools.trend import TrendPredictionTool

        target = intent.target_ip or intent.target_cluster or "unknown"

        # Get Prometheus URL from cluster if target is a cluster
        prometheus_url = None
        if intent.target_cluster:
            cluster = env_manager.get_cluster(intent.target_cluster)
            if cluster:
                prometheus_url = cluster.prometheus_url

        trend_tool = TrendPredictionTool(prometheus_url=prometheus_url)

        # Default prediction for disk
        metric_name = intent.metric_name or "disk_usage"

        try:
            result = await trend_tool.execute(
                metric_name=metric_name,
                target=target,
                time_range="7d",
                threshold=80.0,
            )
            if result and result.success:
                data = result.data or {}
                return {
                    "type": "predict_risk",
                    "target": target,
                    "risk_level": data.get("risk_level", "low"),
                    "trend": data.get("trend", "stable"),
                    "horizon": "24h",
                    "prediction_data": data,
                }
        except Exception as e:
            logger.error(f"Prediction failed: {e}")

        return {"type": "predict_risk", "target": target, "risk_level": "low", "horizon": "24h"}

    return None
