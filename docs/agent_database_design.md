# Agent Database Design

这份设计面向独立的 `ERPNext Ecommerce Agent` 系统，不改 ERPNext 自身数据库。

## 建议选型

- 主数据库：PostgreSQL
- 缓存/队列：Redis
- 向量检索：先可用 PostgreSQL `JSONB` + 全文检索，后续再接专门向量库

## 设计原则

- Agent 系统自己的数据和 ERP 数据分离
- 任务、审批、审计、记忆可追溯
- 大字段用 `JSONB`
- 所有时间统一用 UTC
- 高风险操作必须可审计、可回放

## 核心表

### `users`

Agent 系统用户，不等于 ERPNext 用户。

- `id` uuid pk
- `username` varchar unique
- `password_hash` varchar
- `display_name` varchar
- `status` varchar
- `created_at` timestamptz
- `updated_at` timestamptz

### `roles`

- `id` uuid pk
- `name` varchar unique
- `description` text

### `user_roles`

用户与角色多对多关系。

- `user_id` uuid fk -> users.id
- `role_id` uuid fk -> roles.id
- unique(`user_id`, `role_id`)

### `agent_tasks`

Agent 执行任务主表。

- `id` uuid pk
- `user_id` uuid fk -> users.id
- `title` varchar
- `prompt` text
- `status` varchar  # queued/running/waiting_approval/succeeded/failed/cancelled
- `priority` int
- `input_context` jsonb
- `plan` jsonb
- `result` jsonb
- `error_message` text
- `created_at` timestamptz
- `updated_at` timestamptz
- `started_at` timestamptz
- `finished_at` timestamptz

建议索引：

- (`user_id`, `created_at desc`)
- (`status`, `updated_at desc`)

### `task_steps`

任务拆解后的步骤。

- `id` uuid pk
- `task_id` uuid fk -> agent_tasks.id
- `step_index` int
- `name` varchar
- `description` text
- `status` varchar
- `tool_name` varchar
- `tool_input` jsonb
- `tool_output` jsonb
- `started_at` timestamptz
- `finished_at` timestamptz

### `approvals`

高风险操作审批。

- `id` uuid pk
- `task_id` uuid fk -> agent_tasks.id
- `step_id` uuid fk -> task_steps.id nullable
- `action_type` varchar
- `target_type` varchar
- `target_id` varchar
- `request_payload` jsonb
- `decision` varchar  # pending/approved/rejected/expired
- `decision_by` uuid fk -> users.id nullable
- `decision_reason` text
- `requested_at` timestamptz
- `decided_at` timestamptz

### `audit_logs`

全链路审计。

- `id` uuid pk
- `user_id` uuid fk -> users.id nullable
- `task_id` uuid fk -> agent_tasks.id nullable
- `step_id` uuid fk -> task_steps.id nullable
- `event_type` varchar
- `event_payload` jsonb
- `created_at` timestamptz

建议索引：

- (`task_id`, `created_at desc`)
- (`event_type`, `created_at desc`)

## 知识层表

### `rag_documents`

运营知识、SOP、规范、FAQ 的文档级元数据。

- `id` uuid pk
- `doc_type` varchar
- `title` varchar
- `source_uri` varchar
- `version` varchar
- `tags` jsonb
- `summary` text
- `content_hash` varchar
- `created_at` timestamptz
- `updated_at` timestamptz

### `rag_chunks`

拆分后的检索片段。

- `id` uuid pk
- `document_id` uuid fk -> rag_documents.id
- `chunk_index` int
- `content` text
- `embedding_ref` varchar
- `metadata` jsonb

## 记忆层表

### `agent_memory`

长期记忆，存放偏好、历史结论、运营经验。

- `id` uuid pk
- `user_id` uuid fk -> users.id nullable
- `task_id` uuid fk -> agent_tasks.id nullable
- `memory_type` varchar
- `content` text
- `metadata` jsonb
- `importance_score` numeric
- `created_at` timestamptz

## MCP 和工具层表

### `mcp_tool_catalog`

记录当前可调用工具和权限边界。

- `id` uuid pk
- `tool_name` varchar unique
- `category` varchar
- `description` text
- `risk_level` varchar
- `enabled` bool
- `schema` jsonb

### `tool_invocations`

每次工具调用记录。

- `id` uuid pk
- `task_id` uuid fk -> agent_tasks.id
- `step_id` uuid fk -> task_steps.id nullable
- `tool_name` varchar
- `request_payload` jsonb
- `response_payload` jsonb
- `status` varchar
- `latency_ms` int
- `created_at` timestamptz

## MVP 落地顺序

1. `users`
2. `roles`
3. `agent_tasks`
4. `task_steps`
5. `approvals`
6. `audit_logs`
7. `rag_documents`
8. `rag_chunks`

## 备注

- 如果后面你要上生产，建议加 Alembic 做迁移。
- 现在的 `task_store.py` 和 `auth.py` 都可以逐步替换成这套表结构。
