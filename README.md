# Frappe Ecommerce MCP Agent

这个目录是一个 MCP-first 的 ERPNext 电商运营 Agent 系统。Agent 不直接访问 ERPNext 数据库，而是通过本地 ERP MCP Server 发现和调用工具；FastAPI/React 提供独立的 Agent Web 应用入口。

## Architecture

- `ecommerce_agent/agents/`: Agent Runtime，包含 DeepAgents 主 Agent、任务规划提示词和专业子 Agent 配置。
- `ecommerce_agent/mcp_server/`: ERPNext 隔离层，负责 ERP API Client、MCP Server 和业务 Tools。
- `ecommerce_agent/rag_system/`: 知识层，存放运营策略、ERPNext 业务规则和 Wiki 检索逻辑。
- `ecommerce_agent/sandbox_gateway/`: 安全层，处理高风险操作审批和人工确认。
- `ecommerce_agent/scenarios/`: 可复用业务场景脚本，例如销售订单与库存风险分析。
- `ecommerce_agent/backend/`: FastAPI 后端，提供登录、任务提交、任务查询和 ERP 健康检查接口。
- `frontend/`: React + Vite 前端控制台。
- `docs/`: 接口文档、架构说明和业务说明。
- `scripts/`: 本地启动、检查、造数和 smoke test 脚本。
- `mcp.json`: 给支持 MCP 的客户端/Agent Runtime 复用的本地 server 配置示例。

```text
.
├── ecommerce_agent/
│   ├── agents/
│   │   ├── main_agent.py
│   │   └── sub_agents.py
│   ├── backend/
│   │   ├── auth.py
│   │   ├── main.py
│   │   ├── schemas.py
│   │   └── task_store.py
│   ├── mcp_server/
│   │   ├── erp_client.py
│   │   ├── erp_server.py
│   │   └── tools/
│   │       ├── inventory_tools.py
│   │       ├── marketing_tools.py
│   │       ├── order_tools.py
│   │       └── product_tools.py
│   ├── rag_system/
│   │   ├── wiki/
│   │   └── wiki_manager.py
│   ├── sandbox_gateway/
│   │   └── permission.py
│   └── scenarios/
├── docs/
├── frontend/
├── scripts/
├── mcp.json
├── package.json
├── pyproject.toml
└── requirements.txt
```

## Agent Runtime

主 Agent 负责理解用户任务、使用 `write_todos` 进行任务规划、调用 MCP Tools、委派专业子 Agent，并把执行结果汇总为运营建议。

## Quick Start

```bash
cd /Users/zms/programs/frappe_docker/ecommerce_agent
conda activate <your-env>
python -m pip install -r requirements.txt
```

如果你想安装 console script，再额外执行 `python -m pip install -e .`；直接使用 `scripts/` 不需要这一步。

启动 Agent PostgreSQL 数据库:

```bash
docker run -d \
  --name ecommerce-agent-postgres \
  -e POSTGRES_DB=ecommerce_agent \
  -e POSTGRES_USER=agent \
  -e POSTGRES_PASSWORD=agent123 \
  -p 5432:5432 \
  -v ecommerce_agent_pgdata:/var/lib/postgresql/data \
  postgres:16
```

在 `.env` 中配置 Agent 数据库连接:

```env
DATABASE_URL=postgresql+psycopg://agent:agent123@localhost:5432/ecommerce_agent
```

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

启动 FastAPI 后端:

```bash
./scripts/run_api.sh
```

启动 React 前端:

```bash
cd frontend
npm install
npm run dev
```

运行 MVP 闭环场景：

```bash
./scripts/run_mvp_scenario.sh
```

默认 Agent Web 用户:

```text
operator / operator123
manager / manager123
admin / admin123
```

只做本地结构/ERP 连通性检查:

```bash
./scripts/smoke.sh
```

写入一批 `AGENT-DEMO` 模拟业务数据到 ERPNext:

```bash
cd /Users/zms/programs/frappe_docker
docker compose -f pwd.yml up -d

cd /Users/zms/programs/frappe_docker/ecommerce_agent
python scripts/seed_demo_data.py --dry-run
python scripts/seed_demo_data.py
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
