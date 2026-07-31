from __future__ import annotations

MVP_SCENARIO_NAME = "order_inventory_replenishment_review"

MVP_SCENARIO_PROMPT = """你是企业内部电商运营 Agent。

请完成一个完整的业务闭环：
1. 先用规划工具写出 todo 计划，至少包含：订单分析、库存风险分析、补货建议、知识检索、结果汇总。
2. 调用 ERP/MCP 工具分析最近 30 天销售订单，提取状态分布、重点客户、金额趋势。
3. 调用 ERP/MCP 工具查看库存快照，找出低库存或负库存商品。
4. 调用知识库检索库存策略、补货规则和 ERP 对象映射。
5. 结合分析结果给出补货优先级和运营建议。
6. 如果需要写 ERP 或创建任何单据，先说明原因并等待人工审批。
7. 最后输出一份面向运营负责人的简明结论，说明：发现了什么、建议做什么、哪些动作还没执行。

注意：
- 先规划，再执行。
- 只使用当前已实现的工具。
- 不要臆造 ERP 中不存在的数据。
- 对不确定的字段或流程要明确说明。
"""


def build_mvp_task(days: int = 30) -> str:
    return (
        f"{MVP_SCENARIO_PROMPT}\n\n"
        f"业务窗口：最近 {days} 天。\n"
        "请开始执行。"
    )
