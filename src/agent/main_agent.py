"""Main Agent using LangGraph for ReAct pattern."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.bus.lane_lock import get_lane_lock
from src.config import get_settings
from src.models.types import InspectionCommand, InspectionItem, ToolResult
from src.tools import get_all_tools

logger = logging.getLogger(__name__)


# Define Agent State
class AgentState(dict):
    """Agent state for LangGraph."""

    command: Optional[InspectionCommand] = None
    target: Optional[str] = None
    inspection_items: List[InspectionItem] = []
    observations: List[Dict[str, Any]] = []
    analysis: Dict[str, Any] = {}
    predictions: Dict[str, Any] = {}
    decisions: List[str] = []
    actions: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {}
    messages: List[Any] = []


class MainAgent:
    """Main Agent using LangGraph StateGraph.

    StateGraph nodes: observe → analyze → predict → decide → act → report
    """

    def __init__(self) -> None:
        """Initialize main agent."""
        self._settings = get_settings()
        self._lane_lock = get_lane_lock()
        self._tools = get_all_tools()
        self._llm = None
        self._graph = None

    def _get_llm(self):
        """Lazy initialization of LLM."""
        if self._llm is None:
            llm_config = self._settings.llm
            api_key = llm_config.api_key or "dummy-key-for-testing"
            self._llm = ChatOpenAI(
                model=llm_config.model,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                api_key=api_key,
                base_url=llm_config.base_url,
            )
        return self._llm

    def _initialize(self):
        """Initialize the graph after LLM is ready."""
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("observe", self._observe)
        graph.add_node("analyze", self._analyze)
        graph.add_node("predict", self._predict)
        graph.add_node("decide", self._decide)
        graph.add_node("act", self._act)
        graph.add_node("report", self._report)

        # Define edges
        graph.set_entry_point("observe")
        graph.add_edge("observe", "analyze")
        graph.add_edge("analyze", "predict")
        graph.add_edge("predict", "decide")
        graph.add_edge("decide", "act")
        graph.add_conditional_edges(
            "act",
            self._should_continue,
            {
                "continue": "observe",
                "end": "report",
            },
        )
        graph.add_edge("report", END)

        return graph.compile()

    def _should_continue(self, state: AgentState) -> str:
        """Determine if agent should continue or end."""
        # Continue if there are more items to process
        if state.get("inspection_items"):
            return "continue"
        return "end"

    async def _observe(self, state: AgentState) -> AgentState:
        """Observe: Collect initial data for inspection."""
        logger.info("Agent: observe")

        observations = []
        target = state.get("target")
        command = state.get("command")
        inspection_items = state.get("inspection_items", [])

        if not target or not inspection_items:
            return state

        # Get prometheus_url from cluster if available
        prometheus_url = None
        if command and hasattr(command, 'targets') and command.targets:
            # Try to find the cluster for this target
            from src.environment.manager import get_environment_manager
            env_manager = get_environment_manager()
            # Search for target in clusters
            for cluster in env_manager.get_all_clusters():
                for server in cluster.servers:
                    if server.ip == target:
                        prometheus_url = cluster.prometheus_url
                        break
                if prometheus_url:
                    break

        # SSH system commands
        ssh_commands = {
            "cpu": "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
            "memory": "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'",
            "disk": "df -h | awk '$NF==\"/\"{print $5}' | cut -d'%' -f1",
            "network": "cat /proc/net/dev | awk 'NR>2{sum+=$10} END{print sum/1024/1024}'",
        }

        # Collect observations for each inspection item
        for item in inspection_items:
            check_type = item.check_type
            observation = {
                "check_type": check_type,
                "target": target,
                "data": None,
            }

            # SSH-based system metrics
            if check_type in ssh_commands:
                from src.tools.ssh import SSHCommandTool
                ssh_tool = SSHCommandTool()
                cmd = ssh_commands[check_type]
                result = await ssh_tool.execute(host=target, command=cmd)
                observation["data"] = result.to_dict() if result else None

            # Prometheus service metrics - query all metrics for this IP
            elif check_type == "prometheus":
                if prometheus_url:
                    from src.tools.prometheus import PrometheusQueryTool
                    prom_tool = PrometheusQueryTool(url=prometheus_url)
                    # Query all metrics for this IP using regex to match all ports
                    query = f'{{instance=~"{target}:.*"}}'
                    result = await prom_tool.execute(query=query)
                    observation["data"] = result.to_dict() if result else None
                else:
                    observation["data"] = {"error": "No Prometheus URL configured for this cluster"}

            # Log analysis
            elif check_type == "log":
                from src.tools.log_analysis import LogAnalysisTool
                log_tool = LogAnalysisTool()
                result = await log_tool.execute(
                    host=target,
                    log_path="/var/log/syslog",
                    lines=100,
                    detect_anomalies=True,
                )
                observation["data"] = result.to_dict() if result else None

            observations.append(observation)

        state["observations"] = observations
        return state

    async def _analyze(self, state: AgentState) -> AgentState:
        """Analyze: Analyze collected observations."""
        logger.info("Agent: analyze")

        observations = state.get("observations", [])
        if not observations:
            return state

        analysis = {}
        for obs in observations:
            check_type = obs.get("check_type")
            obs_data = obs.get("data")

            # Handle None data (SSH failed)
            if obs_data is None:
                analysis[check_type] = {"value": None, "status": "error", "error": "Connection failed"}
                continue

            # Simple analysis based on check type
            if check_type in ("cpu", "memory", "disk", "network"):
                # Parse metric value - use safe access
                inner_data = obs_data.get("data") if isinstance(obs_data, dict) else None
                value = ""
                if isinstance(inner_data, dict):
                    value = inner_data.get("stdout", "").strip()
                try:
                    value = float(value)
                    analysis[check_type] = {
                        "value": value,
                        "status": "warning" if value > 80 else "ok",
                    }
                except ValueError:
                    analysis[check_type] = {"value": value, "status": "unknown"}

            elif check_type == "prometheus":
                # Prometheus returns all metrics for this IP
                # Extract metric names and their latest values
                prom_data = obs_data.get("data", {}) if isinstance(obs_data, dict) else {}
                metric_results = prom_data.get("result", []) if isinstance(prom_data, dict) else []
                metrics_summary = []
                metric_count = 0
                for metric_result in metric_results:
                    metric_name = metric_result.get("metric", {}).get("__name__", "unknown")
                    value_list = metric_result.get("value", [])
                    if len(value_list) >= 2:
                        metric_count += 1
                        metrics_summary.append({
                            "name": metric_name,
                            "value": value_list[1],
                        })
                analysis["prometheus"] = {
                    "status": "ok",
                    "metric_count": metric_count,
                    "metrics": metrics_summary[:10],  # First 10 for summary
                    "data": obs_data,
                }

            elif check_type == "log":
                # Analyze log anomalies
                summary = obs_data.get("data", {}).get("summary", {}) if isinstance(obs_data, dict) else {}
                analysis["log"] = {
                    "total_lines": summary.get("total_lines", 0),
                    "error_count": summary.get("error_count", 0),
                    "anomaly_count": summary.get("anomaly_count", 0),
                    "status": "warning" if summary.get("error_count", 0) > 0 else "ok",
                }

            elif check_type == "metric":
                analysis["metric"] = {
                    "status": "ok",
                    "data": obs_data,
                }

        state["analysis"] = analysis
        return state

    async def _predict(self, state: AgentState) -> AgentState:
        """Predict: Predict trends using historical data."""
        logger.info("Agent: predict")

        analysis = state.get("analysis", {})
        target = state.get("target")

        if not target:
            return state

        predictions = {}

        # Use trend prediction for key metrics
        for check_type in ["cpu", "memory"]:
            if check_type in analysis:
                from src.tools.trend import TrendPredictionTool

                trend_tool = TrendPredictionTool()
                result = await trend_tool.execute(
                    metric_name=f"{check_type}_usage",
                    target=target,
                    time_range="7d",
                    threshold=90.0,
                )
                if result and result.success:
                    predictions[check_type] = result.data

        state["predictions"] = predictions
        return state

    async def _decide(self, state: AgentState) -> AgentState:
        """Decide: Decide on actions based on analysis and predictions."""
        logger.info("Agent: decide")

        analysis = state.get("analysis", {})
        predictions = state.get("predictions", {})

        decisions = []

        # Make decisions based on analysis and predictions
        for check_type, data in analysis.items():
            status = data.get("status", "ok")
            if status == "warning" or status == "critical":
                decisions.append(f"Alert for {check_type}: {status}")

        # Consider predictions
        for check_type, pred in predictions.items():
            risk_level = pred.get("risk_level", "none")
            if risk_level in ("high", "critical"):
                decisions.append(f"Risk prediction for {check_type}: {risk_level}")

        state["decisions"] = decisions
        return state

    async def _act(self, state: AgentState) -> AgentState:
        """Act: Execute actions based on decisions."""
        logger.info("Agent: act")

        decisions = state.get("decisions", [])
        actions = []

        for decision in decisions:
            action = {
                "decision": decision,
                "executed": False,
                "result": None,
            }

            # Execute alert if needed
            if "Alert" in decision or "Risk" in decision:
                from src.tools.alert import AlertWebhookTool
                from src.config import get_settings

                settings = get_settings()
                # This would use configured webhook URL
                # For now, just record the action
                action["executed"] = True
                action["result"] = "Alert triggered"

            actions.append(action)

        state["actions"] = actions

        # Remove processed items
        inspection_items = state.get("inspection_items", [])
        state["inspection_items"] = inspection_items[1:] if len(inspection_items) > 1 else []

        return state

    async def _report(self, state: AgentState) -> AgentState:
        """Report: Generate final report."""
        logger.info("Agent: report")

        report = {
            "target": state.get("target"),
            "analysis": state.get("analysis", {}),
            "predictions": state.get("predictions", {}),
            "decisions": state.get("decisions", []),
            "actions": state.get("actions", []),
            "status": "completed",
        }

        state["report"] = report
        return state

    async def execute_inspection(self, command: InspectionCommand) -> Dict[str, Any]:
        """Execute inspection for a command.

        Args:
            command: Inspection command

        Returns:
            Inspection result
        """
        results = []

        for target in command.targets:
            # Use lane lock to prevent concurrent SSH to same target
            async with self._lane_lock.lock(target):
                # Initialize state for this target
                state = AgentState(
                    command=command,
                    target=target,
                    inspection_items=command.inspection_items.copy(),
                )

                # Run the graph (lazy init if needed)
                if self._graph is None:
                    self._initialize()
                final_state = await self._graph.ainvoke(state)

                results.append(final_state.get("report", {}))

        return {
            "command_id": command.command_id,
            "results": results,
            "status": "completed",
        }


# Global main agent instance
_main_agent: Optional[MainAgent] = None


def get_main_agent() -> MainAgent:
    """Get global main agent instance."""
    global _main_agent
    if _main_agent is None:
        _main_agent = MainAgent()
    return _main_agent