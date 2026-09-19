# Agent Harness 项目工程化面试问答

本文档围绕简历中的项目描述和项目亮点，从工程化实现、业务场景、系统边界、可靠性和部署角度总结面试中可能被问到的问题与回答口径。

## 0. 项目总览

### 场景设定

这个项目面向电商运营场景。运营人员希望通过自然语言完成商品查询、订单分析、库存风险识别、补货建议、营销策略草稿和部分 ERP 写操作。

如果只做普通聊天机器人，模型很容易出现两个问题：

- 只能给泛泛建议，不能读取真实 ERP 数据。
- 一旦允许模型直接改 ERP，风险很高，比如误改价格、误停商品、误创建活动。

所以项目设计为一个 Agent Harness 系统：前端提交业务任务，后端持久化任务并投递到队列，Worker 运行 Agent，Agent 通过 MCP Tools 调用 ERPNext 能力，高风险写操作进入人工审批。

### 系统主链路

```text
React 前端
  -> FastAPI 后端
  -> PostgreSQL 记录用户、会话、任务、记忆、审批
  -> Redis / RQ 任务队列
  -> Worker 执行 DeepAgents
  -> MCP Client 加载工具
  -> MCP Server 封装 ERPNext 能力
  -> ERPNext HTTP API
```

### 一句话介绍

这是一个面向电商运营的 Agent Harness。它不是简单调用大模型，而是围绕 Agent Runtime 做了任务状态管理、MCP 工具网关、上下文注入、长期记忆、人工审批和服务化部署，让 Agent 能够在可控边界内完成真实业务闭环。

## 1. Agent Harness 架构设计与任务执行框架

### 简历表述

基于 DeepAgents 构建 Agent Harness，利用其任务规划、上下文管理、子 Agent 委派等内置能力，以 LangGraph 作为底层 Agent Runtime，结合电商业务场景扩展任务状态管理、工具编排及执行控制机制，实现从任务理解、步骤拆解、工具调用到业务执行的完整闭环。

### 工程场景

用户输入：

```text
分析最近 30 天销售订单，找出库存风险，并给出补货建议。只分析，不要修改 ERP 数据。
```

系统需要完成：

1. 接收任务。
2. 保存任务状态。
3. 拼接会话上下文和长期记忆。
4. 让 Agent 拆解任务。
5. 调用订单、库存、补货相关 MCP 工具。
6. 汇总结果。
7. 保存结果并展示给前端。

### 系统怎么做

FastAPI 只负责接收任务和状态查询，不直接执行长任务。任务进入 `agent_tasks` 表后，会被投递到 Redis/RQ 队列。Worker 从队列中取任务，调用 DeepAgents 执行。

Agent 创建时会加载：

- `AGENT.md` 作为主 Agent 系统指令。
- MCP Server 暴露的 ERP 工具。
- `request_human_input` 人工补充信息工具。
- 订单、商品、库存、营销等子 Agent 配置。

任务状态保存在数据库中，典型状态包括：

```text
queued
running
waiting_approval
needs_input
succeeded
failed
cancelled
```

### 解决的问题

- 避免请求线程长时间阻塞。
- 任务执行过程可追踪。
- 服务重启后可以识别异常遗留任务。
- 前端可以轮询任务状态。
- Agent 执行和 API 服务解耦，方便横向扩展 Worker。

### 可能被问到的问题和答案

#### Q1：你说的 Agent Harness 是什么？和普通 Agent 有什么区别？

A：普通 Agent 更偏模型决策和工具调用，Agent Harness 是围绕 Agent 运行所需的工程外壳。这个项目里的 Harness 包括任务持久化、状态机、上下文注入、MCP 工具加载、人工审批、队列执行、结果落库和前端工作台。它解决的是 Agent 如何稳定接入真实业务系统的问题。

#### Q2：为什么不直接在 FastAPI 请求里执行 Agent？

A：Agent 执行时间不可控，可能调用模型、MCP、ERP，多次工具调用会导致请求阻塞。直接放在 FastAPI 里还会导致服务重启任务丢失，也不方便扩展并发。所以我把 API 和执行分开：API 只创建任务并入队，Worker 负责执行。

#### Q3：DeepAgents 和 LangGraph 分别负责什么？

A：DeepAgents 提供上层 Agent 能力，比如任务规划、工具调用、子 Agent 委派等。LangGraph 是底层 Runtime，用图结构管理 Agent 执行流和状态流转。项目层面没有直接手写复杂 LangGraph 节点，而是基于 DeepAgents 暴露的能力做业务工程化封装。

#### Q4：任务状态为什么要落数据库？

A：任务状态不能只放内存。落数据库后，前端可以查询历史任务，服务重启后也能看到任务是否卡在 `queued` 或 `running`。另外审批、补充信息、失败原因、最终结果都需要持久化，方便审计和排查。

#### Q5：这个任务执行框架支持并发吗？

A：现在支持多用户提交任务，任务会进入 Redis/RQ 队列。可以启动多个 Worker 并行消费任务。API 层和 Worker 层分离后，并发能力主要取决于 Worker 数量、模型 API 限额、ERPNext 承载能力和数据库连接池配置。

#### Q6：如果 Worker 崩了怎么办？

A：当前实现会把任务状态保存在数据库中，服务启动时可以把超时遗留的 `queued`、`running`、`needs_input` 任务标记为失败。更生产化的方案是增加 Worker 心跳、任务超时、重试策略和死信队列。

## 2. MCP Tool Gateway

### 简历表述

ERPNext 的商品查询、订单分析、库存快照、补货建议、价格调整、促销活动等业务能力封装为标准化 MCP Tools，避免 Agent 直接访问底层 ERP 接口。

### 工程场景

Agent 需要查商品、查订单、查库存，甚至执行改价、创建活动等操作。如果让 Agent 直接访问 ERPNext API，会有几个风险：

- ERP API 细节暴露给 Agent Runtime。
- 每个 Agent 都要重复写 ERP 调用逻辑。
- 缺少统一审批和安全边界。
- 工具能力不可发现、不可复用。

### 系统怎么做

项目中有一个本地 MCP Server：`agent_console.mcp_server.erp_server`。它通过 `FastMCP` 注册工具。

当前工具分为几类：

- 通用 ERP 工具：`erp_ping`、`erp_list_docs`、`erp_get_doc`、`erp_create_doc`、`erp_update_doc`
- 商品工具：`search_products`、`get_product_profile`、`update_item_price`、`set_product_disabled`
- 订单工具：`get_sales_order_detail`、`analyze_sales_orders`、`analyze_sales_order_items`
- 库存工具：`get_inventory_snapshot`、`find_low_stock_items`、`suggest_replenishment`
- 营销与知识工具：`retrieve_operation_policy`、`draft_campaign_strategy`、`create_campaign`

MCP Tool 内部再调用 `ERPClient`，由 `ERPClient` 负责 ERPNext HTTP 请求、登录和错误处理。

### 解决的问题

- Agent 不直接访问 ERPNext 数据库。
- ERP 能力被标准化成工具。
- 高风险写操作可以统一加审批。
- 工具可以被支持 MCP 的 Runtime 复用。
- 后续扩展新 ERP 能力时，只需要增加 MCP Tool。

### 可能被问到的问题和答案

#### Q1：为什么要用 MCP，不直接把 Python 函数传给 Agent？

A：MCP 是工具协议层，解决工具发现、参数描述、跨 Runtime 复用和隔离问题。直接传 Python 函数也能跑，但会把 ERP 调用和某个 Agent Runtime 绑定死。MCP 让 ERP 能力成为标准工具网关，Agent 只关心工具，不关心底层 ERP API。

#### Q2：MCP Server 是常驻服务吗？

A：当前 Agent Runtime 通过 stdio 配置拉起 MCP Server。也就是说，执行 Agent 时通过 `MultiServerMCPClient` 加载 MCP 工具。`scripts/run_mcp_server.sh` 更多用于单独调试 MCP Server。

#### Q3：如果 ERP API 失败，怎么处理？

A：`ERPClient` 会封装 ERPNext 的 HTTP 请求，如果返回非 2xx 或非 JSON，会抛出 `ERPClientError`。任务执行层捕获异常后会把任务状态标记为 `failed`，并把错误信息保存到 `agent_tasks.error_message`。

#### Q4：通用 ERP 工具和业务专用工具怎么取舍？

A：优先使用业务专用工具，比如订单分析用 `analyze_sales_orders`，库存用 `find_low_stock_items`。通用工具如 `erp_list_docs` 和 `erp_get_doc` 用于探索或兜底。写操作的通用工具更谨慎，必须走审批。

#### Q5：如何新增一个 ERP 能力？

A：一般分三步：先在 `ERPClient` 确认底层 ERP API 能力，再在 MCP Server 的工具模块中注册业务工具，最后在文档和 Agent 指令里说明何时使用该工具。如果是高风险写操作，还要接入 `require_approval`。

## 3. 上下文与长期记忆

### 简历表述

使用 PostgreSQL 持久化用户级记忆、会话摘要、任务结果和结构化业务事实，并在每次任务执行前动态拼接项目指令、用户偏好、会话上下文和当前任务，提升多轮业务任务连续性。

### 工程场景

用户连续多轮对话：

```text
第一轮：分析最近 30 天销售订单。
第二轮：基于刚才的结果，找出需要补货的商品。
第三轮：以后默认不要直接修改 ERP。
```

系统需要记住上下文，但不能无限把全部历史塞给模型。

### 系统怎么做

项目把上下文拆成几层：

- `agent_conversations`：会话和会话摘要。
- `agent_tasks`：每次任务的 prompt、状态、结果和错误。
- `agent_memories`：长期记忆，包括自动任务摘要和人工备注。
- `AGENT.md`：项目级系统指令。
- `rag_system/wiki`：运营知识库。

每次任务执行前，`_build_agent_prompt()` 会拼接：

- 当前任务。
- 当前会话摘要。
- 最近 8 条相关长期记忆。
- 当前会话最近 4 个历史任务。

任务成功后，系统会自动把结果摘要写入 `agent_memories`，同时更新会话摘要。摘要有长度限制，避免上下文无限增长。

### 解决的问题

- 多轮任务有连续性。
- 不需要每次都重新描述业务背景。
- 任务结果可以沉淀为长期记忆。
- 通过限条数和摘要截断控制上下文长度。

### 当前边界

当前实现是轻量上下文管理，主要是摘要、限条数和截断。它还不是完整的 token 预算系统，也没有对子 Agent 返回结果做单独压缩。

### 可能被问到的问题和答案

#### Q1：上下文是怎么拼接给模型的？

A：任务执行前会根据 `conversation_id` 查询会话摘要、最近任务和长期记忆，然后拼成一个新的 prompt。系统提示词来自 `AGENT.md`，业务上下文来自数据库，最后追加当前用户的新任务。

#### Q2：上下文快满了怎么办？

A：当前做的是轻量控制：只取最近 4 个任务、最近 8 条记忆，任务结果摘要截断，会话摘要最长约 2800 字符。更完整的优化方向是做 token 预算统计、结构化摘要、工具结果裁剪和子 Agent 上下文隔离。

#### Q3：长期记忆存在哪里？

A：长期记忆存在 PostgreSQL 的 `agent_memories` 表，而不是文件目录。它支持不同 `memory_type`，比如 `task_summary`、`manual_note`、`business_fact`、`user_preference`、`policy_note`。

#### Q4：结构化业务事实是怎么体现的？

A：当前是通过 `memory_type` 和 JSON metadata 做轻量结构化，而不是完整知识图谱或向量数据库。比如人工可以录入 `business_fact`，任务成功后自动写入 `task_summary`。如果进一步生产化，可以增加事实抽取、版本管理和冲突检测。

#### Q5：历史任务会不会污染当前任务？

A：拼接上下文时会明确告诉 Agent：历史内容只作为业务背景，不要重复执行旧任务。同时只选最近任务和摘要，避免把过多历史细节带入。

## 4. Human-in-the-loop 安全控制

### 简历表述

实现 Web 版 HITL 流程，针对价格修改、商品上下架、促销创建等高风险操作自动暂停并请求人工审批；当 Agent 判断缺少必要业务信息时，可主动进入 `needs_input` 状态等待用户补充后继续执行。

### 工程场景

用户说：

```text
把 A 商品价格改成 99 元。
```

这类请求不能让模型直接执行，因为可能影响收入、订单和前台展示。

另一个场景：

```text
帮我创建一个促销活动。
```

如果缺少活动时间、预算、目标商品、折扣上限，Agent 应该暂停并向用户补充提问，而不是猜。

### 系统怎么做

高风险 MCP Tool 会调用 `require_approval()`。如果审批模式是 `web`，工具不会直接写 ERP，而是返回：

```json
{
  "approval_required": true,
  "action": "...",
  "risk": "...",
  "details": "...",
  "tool_name": "...",
  "tool_args": {}
}
```

任务执行层检测到 `approval_required` 后：

- 创建 `agent_approvals` 记录。
- 任务状态改为 `waiting_approval`。
- 前端显示审批弹窗。

用户批准后，系统把审批继续执行任务投递到 Redis/RQ 队列。Worker 执行实际 ERP 写操作，完成后再让 Agent 基于执行结果生成最终答复。

如果 Agent 缺少业务信息，则调用 `request_human_input()`，任务进入 `needs_input`。用户补充后，继续任务也会入队执行。

### 解决的问题

- 避免 Agent 直接执行高风险 ERP 写操作。
- 用户可以看到风险说明和工具参数。
- 审批结果可追踪、可落库。
- 缺少业务参数时不靠模型猜测。

### 可能被问到的问题和答案

#### Q1：哪些操作会触发审批？

A：价格修改、商品启停、创建 Campaign、通用 ERP 创建和更新文档都会触发审批。这些操作会影响收入、商品可售状态或客户可见流程。

#### Q2：审批状态怎么保存？

A：审批记录保存在 `agent_approvals` 表中，包含 `status`、`action`、`risk`、`details`、`tool_name`、`tool_args`、`decision_note` 和 `execution_result`。

#### Q3：如何避免重复审批导致重复写 ERP？

A：审批操作使用数据库行锁 `with_for_update()`，并且审批继续执行任务使用固定 Job ID。重复点击批准时，如果审批不再是 `pending`，直接返回已有记录，不会再次入队。Worker 执行后将审批状态更新为 `executed`。

#### Q4：为什么需要 `needs_input` 状态？

A：有些任务缺少必要业务参数，直接执行会产生不可靠结果。`needs_input` 让 Agent 暂停任务，明确说明需要哪些字段和原因，用户补充后再继续执行。

#### Q5：如果审批通过后执行失败怎么办？

A：任务会进入 `failed`，错误信息写入 `agent_tasks.error_message`。审批记录会保留已批准状态和可能的执行结果。更完整的生产方案可以增加补偿逻辑、重试策略和人工介入流程。

## 5. Agentic RAG 与多 Agent 协作

### 简历表述

将商品规则、库存策略、促销规范等运营知识封装为检索工具接入 Agent，并基于 DeepAgents 的子 Agent 委派能力配置订单分析、库存优化、营销策略等专业子 Agent，实现复杂任务拆解与专业能力协同。

### 工程场景

用户问：

```text
帮我设计一个清库存促销方案，但不要影响低库存商品。
```

这个任务需要同时考虑：

- 商品和库存数据。
- 促销规则。
- 毛利和库存安全边界。
- 是否需要创建 Campaign。

### 系统怎么做

项目中把运营知识放在 `rag_system/wiki`，通过 `retrieve_operation_policy` 暴露为 MCP Tool。营销工具 `draft_campaign_strategy` 会内部检索运营规则，再生成策略草稿。

子 Agent 配置包括：

- `data_analysis_agent`：订单和指标分析。
- `product_agent`：商品、价格和目录。
- `inventory_agent`：库存信号和补货建议。
- `marketing_agent`：营销策略和活动约束。

主 Agent 负责整体规划和汇总，必要时委派子 Agent 处理专业部分。

### 解决的问题

- 运营规则不需要硬写进 prompt。
- Agent 可以按需检索知识。
- 复杂任务可以按专业方向拆解。
- 主 Agent 聚合结论，避免用户面对多个零散结果。

### 当前边界

项目目前没有自己实现“子 Agent 输出压缩后再给主 Agent”的层。子 Agent 委派由 DeepAgents 内部管理。项目层面的压缩主要发生在任务结束后的会话摘要和长期记忆生成。

### 可能被问到的问题和答案

#### Q1：RAG 在这个项目里检索什么？

A：检索的是运营知识和规则，比如商品运营规范、库存策略、促销约束等。它不是查 ERP 交易数据，ERP 数据通过 MCP ERP 工具查。

#### Q2：为什么把 RAG 也做成工具？

A：把 RAG 做成工具后，Agent 可以按需调用，而不是每次都把全部知识塞进上下文。这样更节省上下文，也能把“什么时候查知识”交给 Agent 规划。

#### Q3：主 Agent 和子 Agent 怎么协作？

A：用户任务先进主 Agent。主 Agent 根据任务类型和子 Agent 描述决定是否委派。子 Agent 负责专业方向，比如库存或营销，主 Agent 最终汇总结果。

#### Q4：子 Agent 是独立服务吗？

A：不是。当前子 Agent 是 DeepAgents 里的配置项，不是独立进程或独立 API。它们有各自的名称、描述和 system prompt，由主 Agent 调度。

#### Q5：如果子 Agent 返回内容太长怎么办？

A：当前没有项目级子 Agent 输出压缩层。后续可以增加结构化摘要器，让子 Agent 只返回结论、证据、调用工具、风险和待办，减少主 Agent 上下文压力。

## 6. 业务场景验证与服务化部署

### 简历表述

针对库存风险分析、订单分析、营销策略及 HITL 审批等典型业务场景构建 MVP 测试流程，验证 Agent 任务执行、MCP 工具调用等链路；基于 FastAPI、React、Redis 完成服务化封装、任务管理和前端工作台集成。

### 工程场景

这个项目不是只写命令行 Demo，而是做成可以多人使用的 Web 工作台：

- 用户登录。
- 提交任务。
- 查看历史会话。
- 查看工具调用过程。
- 审批高风险操作。
- 管理长期记忆。
- 检查 ERP 连接状态。

### 系统怎么做

服务拆分为：

- React：前端工作台。
- FastAPI：认证、任务创建、任务查询、审批、长期记忆接口。
- PostgreSQL：用户、任务、会话、记忆、审批。
- Redis/RQ：异步任务队列。
- Worker：执行 Agent。
- MCP Server：ERP 工具网关。
- ERPNext：模拟业务系统。

典型验证场景：

- 分析最近订单。
- 查询低库存商品。
- 生成补货建议。
- 创建营销策略草稿。
- 触发价格修改审批。
- 触发缺少信息时的 `needs_input`。

### 解决的问题

- 把 Agent 从脚本升级成服务。
- 前端可以观察任务过程。
- 长任务不阻塞 API。
- 多用户任务隔离。
- 高风险操作可审批。
- 系统更接近真实业务部署形态。

### 可能被问到的问题和答案

#### Q1：生产环境需要启动哪些服务？

A：至少需要 PostgreSQL、Redis、FastAPI、RQ Worker、React 前端和 ERPNext。MCP Server 通常由 Agent Runtime 通过 stdio 拉起，也可以单独运行用于调试。

#### Q2：为什么要加 Redis？

A：Redis 用作任务队列。API 收到任务后立即入库并入队，Worker 异步执行。这样可以避免 FastAPI 被长任务阻塞，也能通过增加 Worker 数量提升并发。

#### Q3：如果 Redis 挂了会怎样？

A：新任务无法入队，当前实现会把任务标记为失败并返回队列不可用错误。生产环境需要部署高可用 Redis，并增加队列监控和告警。

#### Q4：前端如何知道任务执行进度？

A：前端定时轮询 `/api/agent/tasks`，根据任务状态展示排队、运行中、等待审批、等待输入、成功、失败等状态。

#### Q5：如何做多用户隔离？

A：用户通过 Token 认证。任务、会话、记忆和审批都绑定用户。任务查询接口必须带当前登录用户条件，不能只按 `task_id` 查询。

#### Q6：如何扩展并发能力？

A：API 层可以多进程部署，Worker 可以横向增加。并发上限要结合模型 API 限额、ERPNext 承载能力、数据库连接池和机器资源来配置。

#### Q7：如何做健康检查？

A：后端有 `/api/health` 检查 API 服务，有 `/api/erp/health` 检查 ERPNext 连接。生产环境还应增加 Redis、Worker、数据库和队列积压监控。

## 7. 综合追问：系统可靠性和安全性

### Q1：这个系统最大的工程风险是什么？

A：主要有四类风险：模型不确定性、高风险写操作、长任务可靠性和多用户数据隔离。项目分别通过 MCP 工具边界、人工审批、任务状态持久化、Redis Worker 和用户级查询隔离来降低风险。

### Q2：如何防止 Agent 越权修改 ERP？

A：前端不持有 ERP 密钥，Agent 不直接访问 ERP 数据库。所有 ERP 能力都通过 MCP Tool 暴露。高风险工具内部必须调用审批逻辑，未审批不会执行写操作。

### Q3：Prompt Injection 怎么办？

A：当前主要靠系统指令、工具边界和高风险审批降低风险。即使用户要求“不要审批直接改价”，工具层仍会返回审批请求。更完整的生产方案需要增加工具参数校验、权限策略、敏感操作审计和 DocType 白名单。

### Q4：如果 Agent 调错工具怎么办？

A：业务指令中要求优先使用业务专用工具，通用工具兜底。高风险写操作有审批兜底。后续可以增加工具权限策略、参数 schema 校验和工具调用审计。

### Q5：如何定位一个任务为什么失败？

A：可以从 `agent_tasks` 查任务状态、错误信息、结果 JSON；从前端工具调用 trace 看执行过程；从 `agent_approvals` 查审批状态；从 Worker 日志看执行异常；从 `/api/erp/health` 检查 ERP 连接。

## 8. 面试回答模板

### 30 秒版本

这个项目是一个电商运营 Agent Harness。我没有让 Agent 直接访问 ERP，而是通过 MCP 把 ERPNext 的商品、订单、库存、营销能力封装成标准工具。后端用 FastAPI 接收任务，PostgreSQL 保存任务、会话、记忆和审批，Redis/RQ Worker 异步执行 Agent。Agent 基于 DeepAgents 和 LangGraph Runtime 做任务规划、工具调用和子 Agent 委派；高风险写操作会进入 Web 审批，缺少业务信息会进入 `needs_input`。这样实现了从自然语言任务到 ERP 工具执行再到结果落库展示的闭环。

### 2 分钟版本

项目核心是把 Agent 从 Demo 变成可服务化的业务系统。前端提交任务后，FastAPI 不直接执行 Agent，而是创建任务记录并放入 Redis 队列。Worker 拉取任务后，先从 PostgreSQL 拼接会话摘要、长期记忆和历史任务上下文，再创建 DeepAgents 主 Agent。主 Agent 通过 MCP Client 加载 ERP Tools，必要时委派订单、库存、商品、营销子 Agent。所有 ERP 能力由 MCP Server 统一封装，底层通过 ERPClient 调 ERPNext HTTP API。对于改价、上下架、创建活动等高风险操作，工具层返回审批请求，任务状态变成 `waiting_approval`，用户在 Web 页面批准后 Worker 才执行实际写操作。任务结果、错误、记忆和审批都会落库，前端轮询展示状态。工程上重点解决了长任务阻塞、多用户隔离、工具边界、安全审批和任务可追踪问题。

## 9. 可以主动承认的当前不足

面试中主动说明边界，通常比过度包装更可信。

- 当前上下文管理是限条数、摘要和截断，还没有完整 token 预算系统。
- 子 Agent 输出没有项目级压缩层，后续可以做结构化摘要。
- Worker 任务已有队列化，但生产级还需要心跳、重试、死信队列和更完善的恢复机制。
- RAG 当前是本地知识检索，不是完整向量数据库和知识图谱。
- 权限模型当前较轻，后续可以扩展角色权限、工具级权限和 DocType 白名单。
- 审计表已有设计基础，但生产级审计还可以补充更多事件记录和告警。

## 10. 高频追问清单

1. 为什么要用 MCP？
2. 为什么不用 Agent 直接访问 ERPNext？
3. Agent 任务为什么要异步队列化？
4. Redis 挂了怎么办？
5. Worker 重复执行怎么办？
6. 高风险操作如何保证只执行一次？
7. 多用户任务如何隔离？
8. 上下文如何拼接？
9. 上下文超过 token 怎么办？
10. 子 Agent 是如何调用的？
11. 子 Agent 输出是否压缩？
12. RAG 检索什么内容？
13. 任务失败怎么排查？
14. ERP API 失败怎么处理？
15. 生产部署需要哪些服务？
16. 如何扩展 Worker 并发？
17. 如何防止 Prompt Injection？
18. 如何新增一个 MCP Tool？
19. 如何保证 Agent 不重复执行旧任务？
20. 当前项目还缺哪些生产化能力？
