"""System constants for AIOPS."""

from typing import Dict, List

# Basic metrics that can be obtained via SSH
BASIC_METRICS: List[str] = ["cpu", "memory", "disk", "network"]

# SSH commands for basic metrics
SSH_COMMANDS: Dict[str, str] = {
    "cpu": "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
    "memory": "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'",
    "disk": "df -h | awk '$NF==\"/\"{print $5}' | cut -d'%' -f1",
    "network": "cat /proc/net/dev | awk 'NR>2{sum+=$10} END{print sum/1024/1024}'",
}

# Metric display names
METRIC_DISPLAY_NAMES: Dict[str, str] = {
    "cpu": "CPU 使用率",
    "memory": "内存使用率",
    "disk": "磁盘使用率",
    "network": "网络流量",
}
