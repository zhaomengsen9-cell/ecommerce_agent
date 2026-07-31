# ERPNext MCP 接口文档

本文档只描述当前项目已经封装的 ERPNext 接口，不包含未实现或计划中的接口。

## 1. 接口形态

当前系统通过 MCP Server 暴露 ERPNext 能力。

- MCP Server 名称: `frappe-ecommerce-erp`
- 启动模块: `ecommerce_agent.mcp_server.erp_server`
- 启动脚本: `scripts/run_mcp_server.sh`
- MCP 配置文件: `mcp.json`

Agent 不直接访问 ERPNext，而是通过 MCP Tools 调用 ERPNext API。

## 2. ERP 连接配置

配置来源为环境变量或 `.env` 文件。

| 配置项 | 默认值 | 说明 |
|---|---:|---|
| `FRAPPE_BASE_URL` | `http://localhost:8080` | ERPNext HTTP 地址 |
| `FRAPPE_SITE` | `frontend` | Frappe site name，请求头 `X-Frappe-Site-Name` |
| `FRAPPE_API_KEY` | 空 | ERPNext API Key，优先使用 token 鉴权 |
| `FRAPPE_API_SECRET` | 空 | ERPNext API Secret |
| `FRAPPE_USERNAME` | `Administrator` | 未配置 token 时的登录账号 |
| `FRAPPE_PASSWORD` | `admin` | 未配置 token 时的登录密码 |

鉴权优先级：

1. 如果配置了 `FRAPPE_API_KEY` 和 `FRAPPE_API_SECRET`，使用 token 鉴权。
2. 否则调用 `/api/method/login` 使用账号密码登录。

## 3. 通用 ERP 接口

### 3.1 `erp_ping`

检查 ERPNext API 是否可访问。

参数：无

返回：

```json
{
  "message": "Administrator"
}
```

底层 ERPNext API：

```text
GET /api/method/frappe.auth.get_logged_user
```

### 3.2 `erp_list_docs`

通用只读列表查询。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `doctype` | `str` | 是 | ERPNext DocType 名称 |
| `fields` | `list[str] \| null` | 否 | 返回字段 |
| `filters` | `dict \| list \| null` | 否 | Frappe filters |
| `limit` | `int` | 否 | 返回条数，默认 `20` |

返回：文档列表。

底层 ERPNext API：

```text
GET /api/resource/{doctype}
```

### 3.3 `erp_get_doc`

查询单个 ERPNext 文档。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `doctype` | `str` | 是 | ERPNext DocType 名称 |
| `name` | `str` | 是 | 文档名称/主键 |

返回：单个文档对象。

底层 ERPNext API：

```text
GET /api/resource/{doctype}/{name}
```

### 3.4 `erp_create_doc`

创建 ERPNext 文档。该接口属于高风险写操作，需要人工审批。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `doctype` | `str` | 是 | ERPNext DocType 名称 |
| `doc` | `dict` | 是 | 新建文档内容 |
| `reason` | `str` | 是 | 创建原因，用于审批说明 |

返回：创建后的文档对象。

底层 ERPNext API：

```text
POST /api/resource/{doctype}
```

### 3.5 `erp_update_doc`

更新 ERPNext 文档。该接口属于高风险写操作，需要人工审批。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `doctype` | `str` | 是 | ERPNext DocType 名称 |
| `name` | `str` | 是 | 文档名称/主键 |
| `updates` | `dict` | 是 | 更新字段 |
| `reason` | `str` | 是 | 更新原因，用于审批说明 |

返回：更新后的文档对象。

底层 ERPNext API：

```text
PUT /api/resource/{doctype}/{name}
```

## 4. 商品接口

商品接口基于 ERPNext `Item`、`Item Price`、`Bin`。

### 4.1 `search_products`

搜索商品主数据。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `keyword` | `str` | 否 | `""` | 按 `Item.item_name` 模糊搜索 |
| `item_group` | `str \| null` | 否 | `null` | 按商品组过滤 |
| `limit` | `int` | 否 | `20` | 返回条数，最大 `100` |

查询 DocType：`Item`

返回字段：

```text
name, item_code, item_name, item_group, stock_uom, disabled, is_stock_item
```

### 4.2 `get_product_profile`

获取单个商品画像，聚合商品、价格和库存。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `item_code` | `str` | 是 | 商品编码 |

查询 DocType：

- `Item`
- `Item Price`
- `Bin`

返回结构：

```json
{
  "item": {},
  "prices": [],
  "inventory_bins": []
}
```

### 4.3 `update_item_price`

修改商品在指定价格表中的最新价格。该接口属于高风险写操作，需要人工审批。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `item_code` | `str` | 是 | 商品编码 |
| `price_list` | `str` | 是 | 价格表名称 |
| `new_rate` | `float` | 是 | 新价格 |
| `reason` | `str` | 是 | 调价原因 |

查询 DocType：`Item Price`

更新字段：

```text
price_list_rate
```

### 4.4 `set_product_disabled`

启用或停用商品。该接口属于高风险写操作，需要人工审批。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `item_code` | `str` | 是 | 商品编码 |
| `disabled` | `bool` | 是 | `true` 表示停用，`false` 表示启用 |
| `reason` | `str` | 是 | 操作原因 |

更新 DocType：`Item`

更新字段：

```text
disabled
```

## 5. 订单接口

订单接口基于 ERPNext `Sales Order` 和 `Sales Order Item`。

### 5.1 `get_sales_order_detail`

查询单个销售订单详情。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `sales_order` | `str` | 是 | 销售订单名称 |

查询 DocType：`Sales Order`

返回：销售订单文档。Frappe 返回的 child table 也会包含在文档中。

### 5.2 `analyze_sales_orders`

分析最近一段时间的销售订单，按状态、客户、金额汇总。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `days` | `int` | 否 | `30` | 查询最近 N 天 |
| `status` | `str \| null` | 否 | `null` | 可选订单状态过滤 |
| `limit` | `int` | 否 | `300` | 查询订单数，最大 `1000` |

查询 DocType：`Sales Order`

查询字段：

```text
name, transaction_date, customer, status, grand_total, currency, delivery_date
```

返回结构：

```json
{
  "window_days": 30,
  "order_count": 0,
  "grand_total": 0,
  "by_status": {},
  "top_customers": [],
  "sample_orders": []
}
```

### 5.3 `analyze_sales_order_items`

分析最近一段时间的销售订单明细，按商品汇总销量和金额。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `days` | `int` | 否 | `30` | 查询最近 N 天 |
| `limit` | `int` | 否 | `500` | 查询明细数，最大 `2000` |

查询 DocType：`Sales Order Item`

查询字段：

```text
parent, item_code, item_name, qty, amount, warehouse, delivery_date, creation
```

返回结构：

```json
{
  "window_days": 30,
  "line_count": 0,
  "top_items": [],
  "sample_lines": []
}
```

## 6. 库存接口

库存接口基于 ERPNext `Bin`。

### 6.1 `get_inventory_snapshot`

查询库存快照。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `item_code` | `str \| null` | 否 | `null` | 商品编码过滤 |
| `warehouse` | `str \| null` | 否 | `null` | 仓库过滤 |
| `limit` | `int` | 否 | `100` | 返回条数，最大 `1000` |

查询 DocType：`Bin`

返回字段：

```text
item_code, warehouse, actual_qty, projected_qty, ordered_qty, reserved_qty, indented_qty, planned_qty
```

### 6.2 `find_low_stock_items`

查询低库存商品。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `threshold` | `float` | 否 | `0` | `projected_qty <= threshold` 判定为低库存 |
| `warehouse` | `str \| null` | 否 | `null` | 仓库过滤 |
| `limit` | `int` | 否 | `50` | 返回条数，最大 `500` |

查询 DocType：`Bin`

返回字段：

```text
item_code, warehouse, actual_qty, projected_qty, ordered_qty, reserved_qty
```

### 6.3 `suggest_replenishment`

基于低库存商品生成补货建议。该接口只生成建议，不创建 ERP 单据。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `threshold` | `float` | 否 | `0` | 低库存阈值 |
| `limit` | `int` | 否 | `50` | 返回建议数 |

内部调用：

```text
find_low_stock_items
```

返回字段：

```text
item_code, warehouse, actual_qty, projected_qty, ordered_qty, priority, recommended_action
```

## 7. 营销与知识接口

营销接口基于 ERPNext `Campaign` 和本地运营 Wiki。

### 7.1 `retrieve_operation_policy`

检索本地运营策略 Wiki。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `query` | `str` | 是 | - | 检索问题 |
| `k` | `int` | 否 | `4` | 返回条数 |

数据来源：

```text
ecommerce_agent/rag_system/wiki/
```

### 7.2 `draft_campaign_strategy`

生成营销活动策略草稿。该接口不写入 ERP。

参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `goal` | `str` | 是 | - | 活动目标 |
| `target_items` | `list[str] \| null` | 否 | `null` | 目标商品列表 |
| `budget` | `float \| null` | 否 | `null` | 预算 |

内部调用：

```text
retrieve_operation_policy
```

返回：活动目标、目标商品、预算、策略草稿、相关知识片段。

### 7.3 `create_campaign`

创建 ERPNext Campaign。该接口属于高风险写操作，需要人工审批。

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `campaign_name` | `str` | 是 | 活动名称 |
| `description` | `str` | 是 | 活动描述 |
| `reason` | `str` | 是 | 创建原因 |

创建 DocType：`Campaign`

写入字段：

```text
campaign_name, description
```

## 8. 高风险操作审批

以下接口会触发人工审批：

- `erp_create_doc`
- `erp_update_doc`
- `update_item_price`
- `set_product_disabled`
- `create_campaign`

审批模式由环境变量控制：

| 配置项 | 默认值 | 说明 |
|---|---:|---|
| `HUMAN_APPROVAL_MODE` | `terminal` | 终端输入 `YES` 后继续 |

当 `HUMAN_APPROVAL_MODE=terminal` 时，高风险操作会输出：

```text
Human approval required
Action: ...
Risk: ...
Details: ...
Approve? Type YES to continue:
```

只有输入 `YES` 才会继续执行。

## 9. 当前接口边界

当前接口已经覆盖：

- 商品查询、商品画像、改价、启停商品
- 销售订单汇总、订单明细汇总、单个订单查询
- 库存快照、低库存查询、补货建议
- 运营知识检索、营销策略草稿、创建 Campaign
- 通用 ERPNext 文档查询、创建、更新

当前接口未包含：

- 创建 Sales Order
- 创建 Purchase Order
- 创建 Material Request
- 提交/取消 ERPNext 单据
- 读取 Stock Ledger Entry
- 读取 Sales Invoice
- 客户、供应商、财务相关专用接口
