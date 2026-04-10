"""Chat API routes for user dialogue."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.api.dependencies import get_api_service, get_session_manager
from src.api.schemas import ChatRequest, ChatResponse, IntentTypeEnum
from src.models.types import IntentType

logger = logging.getLogger(__name__)

router = APIRouter()


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

    # Check if this is a confirmation response
    if session.intent and not session.confirmed:
        # Check if user confirmed
        confirm_keywords = ["确认", "是", "ok", "yes", "confirm", "执行", "开始"]
        if any(kw in request.message.lower() for kw in confirm_keywords):
            # User confirmed, execute the intent
            await session_manager.update_session(request.session_id, confirmed=True)
            result_data = await _execute_intent(service, session.intent)

            response_message = "任务已执行完成。"
            if result_data:
                response_message += f" 结果: {result_data}"

            await session_manager.add_to_history(request.session_id, "assistant", response_message)

            return ChatResponse(
                session_id=request.session_id,
                message=response_message,
                intent=IntentTypeEnum(session.intent.intent_type.value),
                data=result_data,
                requires_confirmation=False,
            )
        else:
            # User provided more information, try to fill slots
            from src.agent.intent_agent import get_intent_agent

            intent_agent = service.get_intent_agent()
            updated_intent = await intent_agent.fill_slot(request.message, session.intent)

            # Check if still missing slots
            if updated_intent.missing_slots:
                await session_manager.update_session(request.session_id, intent=updated_intent)

                # Ask for remaining missing information
                questions = []
                if "metric_name" in updated_intent.missing_slots:
                    questions.append("请问您想查看什么指标？(CPU、内存、磁盘、网络)")
                if "target_ip" in updated_intent.missing_slots or "target" in updated_intent.missing_slots:
                    questions.append("请问您想检查哪台服务器？")

                ask_message = " ".join(questions)
                await session_manager.add_to_history(request.session_id, "assistant", ask_message)

                return ChatResponse(
                    session_id=request.session_id,
                    message=ask_message,
                    intent=IntentTypeEnum(updated_intent.intent_type.value),
                    requires_confirmation=False,
                )
            else:
                # All slots filled, confirm again
                await session_manager.update_session(request.session_id, intent=updated_intent, confirmed=False)
                confirm_msg = _build_confirm_message(updated_intent)
                await session_manager.add_to_history(request.session_id, "assistant", confirm_msg)

                return ChatResponse(
                    session_id=request.session_id,
                    message=confirm_msg,
                    intent=IntentTypeEnum(updated_intent.intent_type.value),
                    requires_confirmation=True,
                )

    # New intent recognition
    intent_agent = service.get_intent_agent()
    intent_result = await intent_agent.recognize_intent(request.message)

    intent = intent_result.get("intent")
    requires_confirmation = intent_result.get("requires_confirmation", False)
    messages = intent_result.get("messages", [])

    if intent:
        await session_manager.update_session(request.session_id, intent=intent, confirmed=False)

    # Build response message
    if requires_confirmation:
        # Ask for missing information or confirm
        response_message = messages[0].get("content", "请确认您的请求。") if messages else _build_confirm_message(intent) if intent else "请确认您的请求。"
    else:
        # Execute directly and return result
        result_data = await _execute_intent(service, intent) if intent else None
        response_message = _build_success_message(intent, result_data)

    await session_manager.add_to_history(request.session_id, "assistant", response_message)

    return ChatResponse(
        session_id=request.session_id,
        message=response_message,
        intent=IntentTypeEnum(intent.intent_type.value) if intent and intent.intent_type != IntentType.UNKNOWN else None,
        data=await _get_intent_data(service, intent) if intent and intent.intent_type != IntentType.UNKNOWN else None,
        requires_confirmation=requires_confirmation,
    )


async def _execute_intent(service, intent) -> Dict[str, Any]:
    """Execute the recognized intent and return data."""
    if not intent:
        return None

    env_manager = service.get_environment_manager()
    prometheus_tool = service.get_prometheus_tool()

    # Resolve targets based on intent
    targets = []
    if intent.target_ip:
        targets = [intent.target_ip]
    elif intent.target_cluster:
        servers = env_manager.get_servers_by_cluster(intent.target_cluster)
        targets = [s.ip for s in servers]

    if not targets:
        return {"error": "无法解析目标服务器"}

    # Execute based on intent type
    if intent.intent_type == IntentType.QUERY_METRIC:
        metric_name = intent.metric_name or "up"
        results = []

        for target in targets:
            # Query Prometheus for metric
            query = f'{metric_name}{{instance="{target}"}}'
            result = await prometheus_tool.execute(query=query)

            if result and result.success:
                results.append({
                    "target": target,
                    "metric": metric_name,
                    "data": result.data,
                })

        return {"type": "metric_query", "results": results}

    elif intent.intent_type == IntentType.CHECK_STATUS:
        # For status check, return basic info
        return {
            "type": "status_check",
            "targets": targets,
            "message": f"将对 {len(targets)} 台服务器进行状态检查",
        }

    elif intent.intent_type == IntentType.RUN_INSPECTION:
        return {
            "type": "inspection",
            "targets": targets,
            "message": f"将对 {len(targets)} 台服务器执行巡检",
        }

    return None


async def _get_intent_data(service, intent) -> Dict[str, Any]:
    """Get additional data for the intent (without executing)."""
    if not intent:
        return None

    env_manager = service.get_environment_manager()
    data = {}

    # Add cluster info if available
    if intent.target_cluster:
        cluster = env_manager.get_cluster(intent.target_cluster)
        if cluster:
            data["cluster"] = {
                "name": cluster.cluster_name,
                "type": cluster.cluster_type,
                "server_count": len(cluster.servers),
            }

    # Add metric info if available
    if intent.metric_name:
        data["metric"] = intent.metric_name

    return data if data else None


def _build_confirm_message(intent) -> str:
    """Build confirmation message for intent."""
    if not intent:
        return "请确认您的请求。"

    msg = "好的，"
    if intent.intent_type == IntentType.QUERY_METRIC:
        msg += f"将查询 {intent.metric_name or '默认'} 指标"
        if intent.target_cluster:
            msg += f"，目标集群: {intent.target_cluster}"
        elif intent.target_ip:
            msg += f"，目标服务器: {intent.target_ip}"
    elif intent.intent_type == IntentType.CHECK_STATUS:
        msg += f"将检查服务器状态"
        if intent.target_ip:
            msg += f": {intent.target_ip}"
    elif intent.intent_type == IntentType.RUN_INSPECTION:
        msg += "将执行巡检"
        if intent.target_cluster:
            msg += f"，目标集群: {intent.target_cluster}"
        elif intent.target_ip:
            msg += f"，目标服务器: {intent.target_ip}"

    msg += "。是否确认？"
    return msg


def _build_success_message(intent, data) -> str:
    """Build success message after execution."""
    if not intent:
        return "无法理解您的请求，请重试。"

    msg = "已完成。"
    if data and isinstance(data, dict):
        if data.get("type") == "metric_query":
            results = data.get("results", [])
            if results:
                msg += f" 查询到 {len(results)} 条指标数据。"
            else:
                msg += " 未查询到指标数据。"
        elif data.get("message"):
            msg += f" {data.get('message')}"

    return msg