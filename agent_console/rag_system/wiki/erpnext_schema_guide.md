# ERPNext 电商运营对象映射

## 商品

- `Item`: 商品主数据，包含 `item_code`、`item_name`、`item_group`、`stock_uom`、`disabled`、`is_stock_item`。
- `Item Price`: 商品价格，常用字段包括 `item_code`、`price_list`、`price_list_rate`、`currency`、`selling`、`buying`。

## 库存

- `Bin`: 商品在仓库中的库存聚合记录，常用字段包括 `item_code`、`warehouse`、`actual_qty`、`projected_qty`、`ordered_qty`、`reserved_qty`。
- 低库存优先看 `projected_qty`，因为它综合考虑实际库存、订单占用和在途数量。

## 订单

- `Sales Order`: 销售订单主表，常用字段包括 `name`、`transaction_date`、`customer`、`status`、`grand_total`、`delivery_date`。
- `Sales Order Item`: 销售订单明细，常用字段包括 `parent`、`item_code`、`qty`、`amount`、`warehouse`。

## 营销

- `Campaign`: 营销活动，常用字段包括 `campaign_name`、`description`。

## Agent 操作边界

- 查询类工具可以直接执行。
- 修改价格、停用商品、创建活动、创建或更新 ERP 文档属于高风险操作，必须经过人工审批。
