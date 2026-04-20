"""Single metric inspector for AIOPS."""

from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.config.constants import BASIC_METRICS, SSH_COMMANDS
from src.environment.manager import get_environment_manager
from src.models.types import ToolResult
from src.tools.prometheus import PrometheusQueryTool
from src.tools.ssh import SSHCommandTool


class SingleMetricInspector:
    """Single metric inspector for AIOPS.

    Handles metric collection via SSH or Prometheus and LLM-based analysis.
    """

    def __init__(self) -> None:
        """Initialize single metric inspector."""
        self._settings = get_settings()
        self._ssh_tool = SSHCommandTool()

    async def inspect(
        self,
        target_ip: str,
        metric_name: str,
        cluster_info: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Inspect a single metric for a target.

        Args:
            target_ip: Target server IP
            metric_name: Metric name to inspect
            cluster_info: Optional cluster info for Prometheus URL

        Returns:
            Inspection result with success, data, source, error
        """
        metric_lower = metric_name.lower()

        # Determine metric source
        if metric_lower in BASIC_METRICS:
            result = await self._get_via_ssh(target_ip, metric_lower)
            source = "ssh"
        else:
            if cluster_info and hasattr(cluster_info, 'prometheus_url') and cluster_info.prometheus_url:
                result = await self._get_via_prometheus(
                    target_ip, metric_name, cluster_info.prometheus_url
                )
                source = "prometheus"
            else:
                return {
                    "success": False,
                    "error": f"集群未配置 Prometheus URL，无法查询指标 '{metric_name}'",
                    "source": "none",
                    "target": target_ip,
                    "metric": metric_name,
                }

        if result.success:
            # Extract the metric value for LLM analysis
            value = self._extract_metric_value(result.data, metric_lower)
            analysis = await self._analyze_with_llm(
                metric_name=metric_name,
                value=value,
                target=target_ip,
            )
            return {
                "success": True,
                "data": result.data,
                "value": value,
                "analysis": analysis,
                "source": source,
                "target": target_ip,
                "metric": metric_name,
            }
        else:
            return {
                "success": False,
                "error": result.error or "获取指标失败",
                "source": source,
                "target": target_ip,
                "metric": metric_name,
            }

    async def _get_via_ssh(self, target_ip: str, metric_name: str) -> ToolResult:
        """Get metric via SSH."""
        env_manager = get_environment_manager()
        server = env_manager.get_server(target_ip)

        if not server:
            return ToolResult(success=False, error=f"Server {target_ip} not found")

        command = SSH_COMMANDS.get(metric_name)
        if not command:
            return ToolResult(success=False, error=f"No SSH command for metric {metric_name}")

        return await self._ssh_tool.execute(
            host=target_ip,
            port=server.port,
            username=server.username,
            password=server.password,
            command=command,
        )

    async def _get_via_prometheus(
        self, target_ip: str, metric_name: str, prometheus_url: str
    ) -> ToolResult:
        """Get metric via Prometheus."""
        prom_tool = PrometheusQueryTool(url=prometheus_url)

        # Query with instance label matching all ports
        query = f'{metric_name}{{instance=~"{target_ip}:.*"}}'
        result = await prom_tool.execute(query=query)

        # If no results, try direct metric name query
        if result.success:
            data = result.data or {}
            result_list = data.get("result", []) if isinstance(data, dict) else []
            if not result_list:
                # Try direct metric name query without instance filter
                query = metric_name
                result = await prom_tool.execute(query=query)

        return result

    def _extract_metric_value(self, data: Any, metric_name: str) -> Any:
        """Extract metric value from tool result data."""
        if data is None:
            return None

        # SSH result format: {"host": "...", "command": "...", "exit_code": 0, "stdout": "...", "stderr": "..."}
        if isinstance(data, dict):
            if "stdout" in data:
                return data["stdout"].strip()
            if "result" in data:
                # Prometheus result format
                result_list = data["result"]
                if isinstance(result_list, list) and len(result_list) > 0:
                    first_result = result_list[0]
                    if isinstance(first_result, dict) and "value" in first_result:
                        return first_result["value"][1] if len(first_result["value"]) > 1 else None
        return data

    async def _analyze_with_llm(
        self, metric_name: str, value: Any, target: str
    ) -> str:
        """Analyze metric with LLM."""
        llm_config = self._settings.llm
        llm = ChatOpenAI(
            model=llm_config.heartbeat_model,
            temperature=0.3,
            max_tokens=llm_config.max_tokens,
            api_key=llm_config.api_key or "dummy-key-for-testing",
            base_url=llm_config.base_url,
        )

        system_prompt = """你是一个运维分析助手，负责分析服务器指标数据并生成简明的巡检报告。

分析要求：
1. 判断指标是否在正常范围内
2. 如果异常，说明可能的原因和建议
3. 生成简洁的中文报告（不超过 200 字）

指标数据格式：
- 基础指标（CPU/内存/磁盘/网络）：数值格式，如 "75.5" 表示百分比
- Prometheus 指标：包含指标名和值的字典

输出格式：
直接输出分析报告，不要使用 JSON 格式。"""

        user_input = f"目标服务器：{target}\n指标名称：{metric_name}\n指标值：{value}\n\n请分析："

        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ])

        return response.content


# Global inspector instance
_single_metric_inspector: Optional[SingleMetricInspector] = None


def get_single_metric_inspector() -> SingleMetricInspector:
    """Get global single metric inspector instance."""
    global _single_metric_inspector
    if _single_metric_inspector is None:
        _single_metric_inspector = SingleMetricInspector()
    return _single_metric_inspector
