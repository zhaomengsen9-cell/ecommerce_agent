# Frappe Ecommerce MCP Agent

这个目录是一个 MCP-first 的 Agent 框架骨架：Agent 不直接连 ERP，而是通过本地 ERP MCP Server 发现和调用工具。当前重点是架构、脚本和扩展位置，商品、订单、库存、营销等具体业务逻辑先保留为占位工具。

## Architecture

- `ecommerce_agent/mcp_server/`: 隔离层，负责与 ERPNext 交互并封装 MCP Tools。
- `ecommerce_agent/rag_system/`: 知识层，存放运营策略和规范，并通过 Wiki Manager 读取。
- `ecommerce_agent/agents/`: 协作层，包含主 Agent 和专业子 Agent 编排。
- `ecommerce_agent/sandbox_gateway/`: 安全层，处理高风险操作的人工审批拦截。
- `ecommerce_agent/entrypoints/`: CLI 和 smoke check 入口。
- `ecommerce_agent/core/`: 少量共享配置。
- `scripts/`: 本地安装、启动和检查脚本。
- `mcp.json`: 给支持 MCP 的客户端/Agent Runtime 复用的本地 server 配置示例。

```text
ecommerce_agent/
├── mcp_server/
│   ├── erp_client.py
│   └── erp_server.py
├── rag_system/
│   ├── wiki/
│   │   └── ecommerce_ops.md
│   └── wiki_manager.py
├── agents/
│   ├── main_agent.py
│   └── sub_agents.py
└── sandbox_gateway/
    └── permission.py
```

## Quick Start

```bash
cd /Users/zms/programs/frappe_docker/ecommerce_agent
conda activate <your-env>
python -m pip install -r requirements.txt
```

如果你想安装 console script，再额外执行 `python -m pip install -e .`；直接使用 `scripts/` 不需要这一步。

检查当前 conda 环境是否装齐 Agent 依赖：

```bash
python scripts/check_dependencies.py
```

编辑 `.env`，填入 `OPENAI_API_KEY`，以及 ERP API token 或账号密码。

启动 ERP MCP Server:

```bash
./scripts/run_mcp_server.sh
```

运行 Agent:

```bash
./scripts/run_agent.sh "规划一个商品管理任务，先列出你能通过 MCP 调用哪些 ERP 能力"
```

运行 MVP 闭环场景：

```bash
./scripts/run_mvp_scenario.sh
```

只做本地结构/ERP 连通性检查:

```bash
./scripts/smoke.sh
```

## Current MCP Tools

- `erp_ping`: 检查 ERP API 是否可达。
- `erp_list_docs`: 通用只读列表查询。
- `erp_get_doc`: 通用只读单文档查询。
- `erp_create_doc`: 通用创建文档，带人工审批。
- `erp_update_doc`: 通用更新文档，带人工审批。
- `search_products`: 基于 ERPNext `Item` 搜索商品。
- `get_product_profile`: 聚合 `Item`、`Item Price`、`Bin` 查看商品画像。
- `update_item_price`: 修改 `Item Price`，带人工审批。
- `set_product_disabled`: 启用/停用 `Item`，带人工审批。
- `analyze_sales_orders`: 基于 `Sales Order` 汇总订单状态、客户和金额。
- `analyze_sales_order_items`: 基于 `Sales Order Item` 汇总商品销售明细。
- `get_sales_order_detail`: 查看单个 `Sales Order`。
- `get_inventory_snapshot`: 基于 `Bin` 查看库存快照。
- `find_low_stock_items`: 基于 `Bin.projected_qty` 查低库存商品。
- `suggest_replenishment`: 基于低库存结果生成补货建议。
- `retrieve_operation_policy`: 检索本地运营 Wiki。
- `draft_campaign_strategy`: 生成营销活动策略草稿，不写 ERP。
- `create_campaign`: 创建 ERPNext `Campaign`，带人工审批。

## ERP Assumptions

The default Docker file exposes ERPNext at `http://localhost:8080` with site header `frontend`. If your site name or port differs, update `.env`.
