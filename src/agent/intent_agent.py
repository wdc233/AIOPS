"""Intent Recognition Agent using LangGraph."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.config import get_settings
from src.models.types import IntentType, UserIntent
from src.environment.manager import get_environment_manager

logger = logging.getLogger(__name__)


# Define Intent Agent State
class IntentAgentState(dict):
    """Intent agent state for LangGraph."""

    user_input: str = ""
    intent: Optional[UserIntent] = None
    missing_slots: List[str] = []
    confirmed_tools: List[str] = []
    messages: List[Any] = []
    requires_confirmation: bool = False


class IntentRecognitionAgent:
    """Intent Recognition Agent using LangGraph StateGraph.

    StateGraph nodes: intent_parse → slot_check → tool_select → confirm
    """

    def __init__(self) -> None:
        """Initialize intent recognition agent."""
        self._settings = get_settings()
        self._env_manager = get_environment_manager()
        self._llm = None
        self._graph = None

    def _get_llm(self):
        """Lazy initialization of LLM."""
        if self._llm is None:
            llm_config = self._settings.llm
            api_key = llm_config.api_key or "dummy-key-for-testing"
            self._llm = ChatOpenAI(
                model=llm_config.heartbeat_model,
                temperature=llm_config.heartbeat_temperature,
                max_tokens=llm_config.max_tokens,
                api_key=api_key,
                base_url=llm_config.base_url,
            )
        return self._llm

    def _initialize(self):
        """Initialize graph after LLM is ready."""
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph."""
        graph = StateGraph(IntentAgentState)

        # Add nodes
        graph.add_node("intent_parse", self._intent_parse)
        graph.add_node("slot_check", self._slot_check)
        graph.add_node("tool_select", self._tool_select)
        graph.add_node("confirm", self._confirm)

        # Define edges
        graph.set_entry_point("intent_parse")
        graph.add_edge("intent_parse", "slot_check")

        # Conditional edge based on missing slots
        graph.add_conditional_edges(
            "slot_check",
            self._has_missing_slots,
            {
                "ask": "confirm",
                "continue": "tool_select",
            },
        )
        graph.add_edge("tool_select", "confirm")
        graph.add_edge("confirm", END)

        return graph.compile()

    def _has_missing_slots(self, state: IntentAgentState) -> str:
        """Determine if there are missing slots."""
        missing = state.get("missing_slots", [])
        if missing:
            return "ask"
        return "continue"

    async def _intent_parse(self, state: IntentAgentState) -> IntentAgentState:
        """Intent Parse: Parse user input to identify intent type."""
        logger.info("Intent Agent: intent_parse")

        user_input = state.get("user_input", "")
        if not user_input:
            return state

        # Use LLM to parse intent
        system_prompt = """You are an intelligent intent recognition system for an AIOPS agent.

Your task is to parse user input (in any language) and identify:
1. Intent type
2. Target information
3. Any specific metrics or parameters mentioned

Intent types:
- query_info: User wants to query cluster/server information (how many servers, server details, etc.)
- query_metric: User wants to query Prometheus metrics (CPU, memory, disk, network usage, etc.)
- check_status: User wants to check server/service status
- run_inspection: User wants to run a system inspection task
- unknown: Cannot determine intent

Respond with a JSON object containing:
- intent_type: one of query_info, query_metric, check_status, run_inspection, unknown
- target_cluster: cluster name if explicitly mentioned (e.g., "test-cluster" from "test-cluster有几台服务器")
- target_ip: server IP if explicitly mentioned
- metric_name: metric name if mentioned (cpu, memory, disk, network, etc.)
- time_range: time range if mentioned (1h, 24h, 7d, etc.)
- confidence: confidence score 0-1
- reasoning: brief explanation of why this intent was chosen

IMPORTANT:
- "有几台服务器" / "how many servers" / "多少台" -> query_info
- "查看状态" / "check status" -> check_status
- "查看指标" / "查看CPU" / "查看内存" -> query_metric
- "运行巡检" / "执行检查" -> run_inspection

Examples (note: Chinese input examples):
- "test-cluster有几台服务器" -> {"intent_type": "query_info", "target_cluster": "test-cluster", "confidence": 0.95, "reasoning": "用户查询集群有多少台服务器"}
- "查看 CPU 使用率" -> {"intent_type": "query_metric", "metric_name": "cpu_usage", "confidence": 0.9}
- "检查 192.168.1.1 状态" -> {"intent_type": "check_status", "target_ip": "192.168.1.1", "confidence": 0.95}
- "运行巡检" -> {"intent_type": "run_inspection", "confidence": 0.8}"""

        try:
            response = await self._get_llm().ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_input)]
            )

            # Parse LLM response (simple JSON parsing)
            import json
            import re

            # Debug: log raw LLM response
            logger.info(f"LLM raw response: {response.content}")

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                logger.info(f"LLM parsed JSON: {parsed}")
                intent_type_str = parsed.get("intent_type", "unknown")
                try:
                    intent_type = IntentType(intent_type_str)
                except ValueError:
                    intent_type = IntentType.UNKNOWN
                intent = UserIntent(
                    intent_type=intent_type,
                    target_cluster=parsed.get("target_cluster"),
                    target_ip=parsed.get("target_ip"),
                    metric_name=parsed.get("metric_name"),
                    time_range=parsed.get("time_range"),
                    confidence=parsed.get("confidence", 0.0),
                    raw_input=user_input,
                )
                state["intent"] = intent

        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            state["intent"] = UserIntent(
                intent_type=IntentType.UNKNOWN,
                raw_input=user_input,
                confidence=0.0,
            )

        return state

    async def _slot_check(self, state: IntentAgentState) -> IntentAgentState:
        """Slot Check: Check for missing information slots."""
        logger.info("Intent Agent: slot_check")

        intent = state.get("intent")
        if not intent:
            return state

        missing = []

        # Check required slots based on intent type
        if intent.intent_type == IntentType.QUERY_INFO:
            # Query info needs either cluster or ip
            if not intent.target_cluster and not intent.target_ip:
                missing.append("target")

        elif intent.intent_type == IntentType.QUERY_METRIC:
            if not intent.metric_name:
                missing.append("metric_name")
            # Try to get default cluster if not specified
            if not intent.target_cluster and not intent.target_ip:
                clusters = self._env_manager.get_all_clusters()
                if clusters:
                    intent.target_cluster = clusters[0].cluster_name

        elif intent.intent_type == IntentType.CHECK_STATUS:
            if not intent.target_ip:
                # Try to get servers from cluster
                if intent.target_cluster:
                    servers = self._env_manager.get_servers_by_cluster(intent.target_cluster)
                    if servers:
                        intent.target_ip = servers[0].ip
                if not intent.target_ip:
                    missing.append("target_ip")

        elif intent.intent_type == IntentType.RUN_INSPECTION:
            # Need at least targets or cluster
            if not intent.target_cluster and not intent.target_ip:
                missing.append("target")

        state["missing_slots"] = missing
        return state

    async def _tool_select(self, state: IntentAgentState) -> IntentAgentState:
        """Tool Select: Select appropriate tools based on intent."""
        logger.info("Intent Agent: tool_select")

        intent = state.get("intent")
        if not intent:
            return state

        tools = []

        # Select tools based on intent type
        if intent.intent_type == IntentType.QUERY_INFO:
            tools.append("environment_query")

        elif intent.intent_type == IntentType.QUERY_METRIC:
            tools.append("prometheus_query")
            if intent.metric_name in ("cpu", "memory", "disk"):
                tools.append("trend_prediction")

        elif intent.intent_type == IntentType.CHECK_STATUS:
            tools.append("ssh_command")
            tools.append("log_analysis")

        elif intent.intent_type == IntentType.RUN_INSPECTION:
            tools.append("ssh_command")
            tools.append("log_analysis")
            tools.append("prometheus_query")

        state["confirmed_tools"] = tools

        # Determine if confirmation is needed
        # Confirm if confidence is low or missing slots exist
        if intent.confidence < 0.7 or state.get("missing_slots"):
            state["requires_confirmation"] = True

        return state

    async def _confirm(self, state: IntentAgentState) -> IntentAgentState:
        """Confirm: Generate confirmation message for user."""
        logger.info("Intent Agent: confirm")

        intent = state.get("intent")
        missing = state.get("missing_slots", [])

        # Build confirmation message
        if missing:
            # Ask for missing information
            questions = []
            if "metric_name" in missing:
                questions.append("请问您想查看什么指标？(CPU、内存、磁盘、网络)")
            if "target_ip" in missing or "target" in missing:
                questions.append("请问您想检查哪台服务器？")
            if "target_cluster" in missing:
                questions.append("请问您想检查哪个集群？")

            state["messages"] = [{"type": "ask", "content": " ".join(questions)}]
        else:
            # Confirm the action
            intent = state.get("intent")
            if intent:
                confirm_msg = f"好的，我将"
                if intent.intent_type == IntentType.QUERY_INFO:
                    if intent.target_cluster:
                        confirm_msg += f"查询集群 {intent.target_cluster} 的信息"
                    elif intent.target_ip:
                        confirm_msg += f"查询服务器 {intent.target_ip} 的信息"
                elif intent.intent_type == IntentType.QUERY_METRIC:
                    confirm_msg += f"查询 {intent.metric_name} 指标"
                    if intent.time_range:
                        confirm_msg += f"，时间范围 {intent.time_range}"
                elif intent.intent_type == IntentType.CHECK_STATUS:
                    confirm_msg += f"检查服务器 {intent.target_ip} 的状态"
                elif intent.intent_type == IntentType.RUN_INSPECTION:
                    confirm_msg += f"在 {intent.target_cluster or intent.target_ip} 运行巡检"

                confirm_msg += "。是否确认？"
                state["messages"] = [{"type": "confirm", "content": confirm_msg}]

        return state

    async def recognize_intent(self, user_input: str) -> Dict[str, Any]:
        """Recognize user intent from input.

        Args:
            user_input: User's natural language input

        Returns:
            Recognition result with intent and messages
        """
        # Initialize state
        state = IntentAgentState(user_input=user_input)

        # Run the graph (lazy init if needed)
        if self._graph is None:
            self._initialize()
        final_state = await self._graph.ainvoke(state)

        return {
            "intent": final_state.get("intent"),
            "missing_slots": final_state.get("missing_slots", []),
            "confirmed_tools": final_state.get("confirmed_tools", []),
            "messages": final_state.get("messages", []),
            "requires_confirmation": final_state.get("requires_confirmation", False),
        }

    async def fill_slot(self, user_input: str, current_intent: UserIntent) -> UserIntent:
        """Fill missing slots based on user response.

        Args:
            user_input: User's response
            current_intent: Current intent with missing slots

        Returns:
            Updated intent
        """
        # Simple slot filling based on user response
        # Could be enhanced with more sophisticated NLP

        updated = current_intent.model_copy()

        # Try to extract missing information
        missing = updated.missing_slots.copy()

        # Check for IP addresses
        import re

        ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        ips = re.findall(ip_pattern, user_input)
        if ips and "target_ip" in missing:
            updated.target_ip = ips[0]
            missing.remove("target_ip")

        # Check for common keywords
        user_lower = user_input.lower()
        if "metric_name" in missing:
            if "cpu" in user_lower:
                updated.metric_name = "cpu"
                missing.remove("metric_name")
            elif "内存" in user_input or "memory" in user_lower:
                updated.metric_name = "memory"
                missing.remove("metric_name")
            elif "磁盘" in user_input or "disk" in user_lower:
                updated.metric_name = "disk"
                missing.remove("metric_name")
            elif "网络" in user_input or "network" in user_lower:
                updated.metric_name = "network"
                missing.remove("metric_name")

        # Check for time range
        if "time_range" in missing:
            if "1小时" in user_input or "1h" in user_lower:
                updated.time_range = "1h"
                missing.remove("time_range")
            elif "24小时" in user_input or "24h" in user_lower:
                updated.time_range = "24h"
                missing.remove("time_range")
            elif "7天" in user_input or "7d" in user_lower:
                updated.time_range = "7d"
                missing.remove("time_range")

        updated.missing_slots = missing
        return updated


# Global intent agent instance
_intent_agent: Optional[IntentRecognitionAgent] = None


def get_intent_agent() -> IntentRecognitionAgent:
    """Get global intent recognition agent instance."""
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentRecognitionAgent()
    return _intent_agent