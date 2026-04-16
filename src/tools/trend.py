"""Trend Prediction Tool using LLM."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.tools.base import BaseTool, ToolResult
from src.tools.prometheus import PrometheusQueryTool

logger = logging.getLogger(__name__)


class TrendPredictionTool(BaseTool):
    """Tool for predicting trends based on historical metrics using LLM."""

    name = "trend_prediction"
    description = "Predict trend risks based on historical metric data using LLM or statistical models."

    def __init__(self, prometheus_url: Optional[str] = None) -> None:
        """Initialize trend prediction tool.

        Args:
            prometheus_url: Optional Prometheus URL override.
        """
        self._settings = get_settings()
        self._prometheus = PrometheusQueryTool(url=prometheus_url)
        self._llm = None

    def _get_llm(self):
        """Lazy initialization of LLM."""
        if self._llm is None:
            llm_config = self._settings.llm
            # Use dummy key if not configured (for testing)
            api_key = llm_config.api_key or "dummy-key-for-testing"
            self._llm = ChatOpenAI(
                model=llm_config.heartbeat_model,
                temperature=llm_config.heartbeat_temperature,
                max_tokens=llm_config.max_tokens,
                api_key=api_key,
                base_url=llm_config.base_url,
            )
        return self._llm

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "Metric name to predict (e.g., cpu_usage, memory_usage)",
                },
                "target": {
                    "type": "string",
                    "description": "Target IP or identifier",
                },
                "time_range": {
                    "type": "string",
                    "description": "Historical data time range (e.g., '7d', '24h')",
                    "default": "7d",
                },
                "threshold": {
                    "type": "number",
                    "description": "Threshold value for risk prediction",
                },
            },
            "required": ["metric_name", "target"],
        }

    async def execute(
        self,
        metric_name: str,
        target: str,
        time_range: str = "7d",
        threshold: Optional[float] = None,
    ) -> ToolResult:
        """Predict trend for a metric.

        Args:
            metric_name: Metric name
            target: Target IP or identifier
            time_range: Historical data time range
            threshold: Threshold for risk

        Returns:
            ToolResult with prediction
        """
        start_time = time.time()

        try:
            # Query historical data from Prometheus
            # Use regex to match all ports for the target IP
            query = f'{metric_name}{{instance=~"{target}:.*"}}'

            # Use a longer time range for prediction
            result = await self._prometheus.query_range(
                query=query,
                start=f"now-{time_range}",
                end="now",
                step="1h",
            )

            if not result.success:
                return result

            data = result.data
            if not data or not data.get("result"):
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    success=False,
                    error=f"No data found for metric {metric_name}",
                    duration_ms=duration_ms,
                )

            # Extract time series data
            values = data.get("result", [{}])[0].get("values", [])
            if not values:
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    success=False,
                    error="No values in metric data",
                    duration_ms=duration_ms,
                )

            # Perform trend analysis
            prediction = await self._analyze_trend(values, metric_name, threshold)

            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=True,
                data=prediction,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Trend prediction failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def _analyze_trend(
        self,
        values: List[List[Any]],
        metric_name: str,
        threshold: Optional[float],
    ) -> Dict[str, Any]:
        """Analyze trend using statistical methods and LLM.

        Args:
            values: Time series values [[timestamp, value], ...]
            metric_name: Metric name
            threshold: Threshold value

        Returns:
            Analysis result
        """
        # Extract numeric values
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v[1]))
            except (ValueError, TypeError, IndexError):
                continue

        if not numeric_values:
            return {"error": "No valid numeric values"}

        # Basic statistics
        n = len(numeric_values)
        avg = sum(numeric_values) / n
        max_val = max(numeric_values)
        min_val = min(numeric_values)

        # Calculate trend (simple linear regression)
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(numeric_values)
        sum_xy = sum(x[i] * numeric_values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
        trend = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"

        # Check against threshold
        risk_level = "none"
        if threshold:
            if max_val >= threshold:
                risk_level = "critical"
            elif avg >= threshold * 0.8:
                risk_level = "high"
            elif avg >= threshold * 0.6:
                risk_level = "medium"
            elif avg >= threshold * 0.4:
                risk_level = "low"

        # Use LLM for more sophisticated analysis if configured
        llm_analysis = None
        try:
            llm_analysis = await self._llm_predict(
                numeric_values, metric_name, trend, risk_level
            )
        except Exception as e:
            logger.warning(f"LLM analysis failed, using statistical only: {e}")

        return {
            "metric_name": metric_name,
            "data_points": n,
            "statistics": {
                "average": round(avg, 2),
                "max": round(max_val, 2),
                "min": round(min_val, 2),
            },
            "trend": trend,
            "slope": round(slope, 4),
            "risk_level": risk_level,
            "threshold": threshold,
            "llm_analysis": llm_analysis,
        }

    async def _llm_predict(
        self,
        values: List[float],
        metric_name: str,
        trend: str,
        risk_level: str,
    ) -> Optional[str]:
        """Use LLM to generate prediction summary.

        Args:
            values: Historical values
            metric_name: Metric name
            trend: Detected trend
            risk_level: Risk level

        Returns:
            LLM analysis text
        """
        # Use a subset of values for context
        sample_values = values[-24:] if len(values) > 24 else values
        values_str = ", ".join(str(round(v, 2)) for v in sample_values)

        prompt = f"""Based on the following historical data for metric '{metric_name}':
- Recent values: {values_str}
- Trend: {trend}
- Risk Level: {risk_level}

Provide a brief analysis (2-3 sentences) predicting potential issues and recommendations."""

        try:
            response = await self._get_llm().ainvoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"LLM prediction failed: {e}")
            return None