"""Intent recognition response templates.

All templates are pre-defined strings with placeholders for dynamic values.
Do NOT use LLM to generate responses dynamically.
"""

# CHAT intent responses
CHAT_GREETING = """您好！我是智能运维助手，可以帮您：
- 查询集群和服务器信息
- 检查服务器运行状况
- 查看CPU、内存等指标
- 执行系统巡检
- 预测潜在风险

请问有什么可以帮您？"""

CHAT_CAPABILITIES = """我可以帮您完成以下操作：
1. 查询集群信息 - 如「test-cluster有几台服务器」
2. 查看指标 - 如「查看CPU使用率」
3. 状态检查 - 如「检查192.168.1.1状态」
4. 风险预测 - 如「预测磁盘容量」
5. 执行巡检 - 如「运行巡检」"""

CHAT_UNKNOWN = "抱歉，我没有理解您的意思。您可以尝试：\n- 「test-cluster有几台服务器」- 查询集群信息\n- 「查看CPU」- 查看指标\n- 「检查服务器状态」- 状态检查"

CHAT_THANKS = "不客气！还有什么可以帮您？"

# Confirmation templates (user confirms intent)
CONFIRM_INSPECT = "好的，将检查 {cluster} 的运行状况。是否确认？"
CONFIRM_QUERY_METRIC = "好的，将查询 {cluster} 的 {metric} 指标。是否确认？"
CONFIRM_CHECK_STATUS = "好的，将检查 {target} 的状态。是否确认？"
CONFIRM_RUN_INSPECTION = "好的，将在 {target} 执行巡检任务。是否确认？"
CONFIRM_QUERY_INFO = "好的，将查询 {target} 的信息。是否确认？"
CONFIRM_PREDICT_RISK = "好的，将预测 {target} 的风险。是否确认？"
CONFIRM_PREDICT_RISK_SINGLE = "好的，将预测 {target} 的 {metric} 风险。是否确认？"
CONFIRM_PREDICT_RISK_FULL = "好的，将对 {target} 进行全量风险预测分析。是否确认？"

# Result templates (after execution)
RESULT_INSPECT_OK = "集群 {cluster} 巡检完成，未发现问题。"
RESULT_INSPECT_ISSUES = "集群 {cluster} 巡检完成，发现 {issue_count} 个问题：\n{issues}"
RESULT_QUERY_METRIC = "{cluster} 的 {metric} 当前值为 {value}。"
RESULT_QUERY_METRIC_HISTORY = "{cluster} 的 {metric} 在 {time_range} 内的平均值为 {avg_value}，最大值为 {max_value}。"
RESULT_CHECK_STATUS_OK = "{target} 状态正常，运行正常。"
RESULT_CHECK_STATUS_ISSUE = "{target} 状态异常：{issue}"
RESULT_QUERY_INFO = "{target} 信息如下：\n{info}"
RESULT_QUERY_INFO_SERVERS = "{cluster} 共有 {server_count} 台服务器：\n{server_list}"
RESULT_RUN_INSPECTION = "巡检任务已启动，目标：{target}。"
RESULT_PREDICT_RISK_LOW = "{target} 风险等级：低。未来 {horizon} 内预计运行正常。"
RESULT_PREDICT_RISK_MEDIUM = "{target} 风险等级：中等。建议关注 {risk_type}。"
RESULT_PREDICT_RISK_HIGH = "{target} 风险等级：高！{risk_type} 可能不足，建议立即处理。"

# Ask templates (request missing information)
ASK_CLUSTER = "请问您要操作的集群名称是？"
ASK_CLUSTER_LIST = "请选择要操作的集群：\n{cluster_list}\n\n请输入集群名称或序号。"
ASK_TARGET = "请问您要操作的目标是？（集群名称或服务器IP）"
ASK_METRIC = "请问您想查询什么指标？（CPU、内存、磁盘、网络）"
ASK_TIME_RANGE = "请问您想查询哪个时间范围？（1h、24h、7d）"
ASK_RISK_TYPE = "请问您想预测什么类型的风险？（磁盘、内存、CPU）"

# Multiple intent selection template
MULTIPLE_INTENTS = "我理解您可能有以下意图，请确认：\n{options}\n\n请选择或重新描述您的需求。"

# Fallback template (confidence < 0.5)
FALLBACK = """我好像没有理解您的需求。您可以尝试这样说：
- 「检查 prod-cluster 的健康状况」
- 「查看 CPU 使用率」
- 「预测磁盘容量风险」

或者告诉我您想操作的集群名称和具体需求。"""

# Error templates
ERROR_NO_CLUSTER = "未找到指定的集群，请确认集群名称是否正确。"
ERROR_NO_SERVER = "未找到指定的服务器，请确认IP地址是否正确。"
ERROR_QUERY_FAILED = "查询失败：{reason}。请稍后重试。"
ERROR_EXECUTION_FAILED = "执行失败：{reason}。请稍后重试。"
ERROR_METRIC_NOT_FOUND = "未找到指标 '{metric}'，可能原因：\n1. 指标名称拼写错误\n2. 该指标在 Prometheus 中不存在\n\n可用指标包括：\n{available_metrics}\n\n您可以尝试：\n- 「预测 CPU」- CPU 使用率趋势\n- 「预测内存」- 内存使用率趋势\n- 「预测磁盘」- 磁盘使用率趋势"
ERROR_SSH_FAILED = "通过 SSH 获取指标 '{metric}' 失败：{reason}\n请检查：\n1. 服务器网络是否可达\n2. SSH 认证是否正确"
ERROR_METRIC_SUGGESTION = "指标 '{metric}' 不存在。是否改为预测以下相似指标？\n{similar_metrics}\n\n请回复 '是' 确认，或指定其他指标。"
