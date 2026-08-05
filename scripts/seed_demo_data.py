from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ecommerce_agent.mcp_server.erp_client import ERPClientError, erp_client


PREFIX = "AGENT-DEMO"

PRODUCTS = [
    {"item_code": f"{PREFIX}-HOT-LOW", "item_name": "Agent Demo Hot Seller Low Stock", "price": 129, "stock": 2},
    {"item_code": f"{PREFIX}-HOT-ENOUGH", "item_name": "Agent Demo Hot Seller Enough Stock", "price": 159, "stock": 120},
    {"item_code": f"{PREFIX}-SLOW-HIGH", "item_name": "Agent Demo Slow Seller High Stock", "price": 89, "stock": 240},
    {"item_code": f"{PREFIX}-LOW-MARGIN", "item_name": "Agent Demo Low Margin Product", "price": 39, "stock": 60},
    {"item_code": f"{PREFIX}-NORMAL", "item_name": "Agent Demo Normal Product", "price": 99, "stock": 35},
]

INVENTORY_PRODUCTS = [
    {"item_code": f"{PREFIX}-INV-PHONE-CASE", "item_name": "Agent Demo Phone Case", "price": 29, "stock": 520},
    {"item_code": f"{PREFIX}-INV-USB-CABLE", "item_name": "Agent Demo USB Cable", "price": 19, "stock": 860},
    {"item_code": f"{PREFIX}-INV-WIRELESS-MOUSE", "item_name": "Agent Demo Wireless Mouse", "price": 69, "stock": 180},
    {"item_code": f"{PREFIX}-INV-KEYBOARD", "item_name": "Agent Demo Keyboard", "price": 139, "stock": 95},
    {"item_code": f"{PREFIX}-INV-BLUETOOTH-SPEAKER", "item_name": "Agent Demo Bluetooth Speaker", "price": 199, "stock": 48},
    {"item_code": f"{PREFIX}-INV-POWER-BANK", "item_name": "Agent Demo Power Bank", "price": 119, "stock": 12},
    {"item_code": f"{PREFIX}-INV-SMART-LAMP", "item_name": "Agent Demo Smart Lamp", "price": 89, "stock": 6},
    {"item_code": f"{PREFIX}-INV-AIR-PURIFIER", "item_name": "Agent Demo Air Purifier", "price": 499, "stock": 16},
    {"item_code": f"{PREFIX}-INV-OFFICE-CHAIR", "item_name": "Agent Demo Office Chair", "price": 399, "stock": 34},
    {"item_code": f"{PREFIX}-INV-DESK-MAT", "item_name": "Agent Demo Desk Mat", "price": 49, "stock": 300},
]

ALL_PRODUCTS = [*PRODUCTS, *INVENTORY_PRODUCTS]

CUSTOMERS = [
    f"{PREFIX} Customer Alpha",
    f"{PREFIX} Customer Beta",
    f"{PREFIX} Customer Gamma",
]

CAMPAIGNS = [
    {"campaign_name": f"{PREFIX} Weekly Clearance", "description": "Demo campaign for slow-moving high-stock products."},
    {"campaign_name": f"{PREFIX} Member Bundle", "description": "Demo campaign for bundle/member-benefit promotion testing."},
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo ecommerce data into ERPNext.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned records without writing ERPNext.")
    args = parser.parse_args()

    if args.dry_run:
        print_plan()
        return

    try:
        seed()
    except Exception as exc:
        raise SystemExit(
            "ERP seed failed. Make sure ERPNext is running and FRAPPE_BASE_URL points to the exposed frontend.\n"
            f"Details: {exc}"
        ) from exc


def print_plan() -> None:
    print("Demo products:")
    for product in ALL_PRODUCTS:
        print(f"- {product['item_code']} stock={product['stock']} price={product['price']}")
    print("Demo customers:")
    for customer in CUSTOMERS:
        print(f"- {customer}")
    print("Demo campaigns:")
    for campaign in CAMPAIGNS:
        print(f"- {campaign['campaign_name']}")


def seed() -> None:
    print("Checking ERP connection...")
    print(erp_client.ping())

    company = first_name("Company")
    item_group = first_name("Item Group", filters=[["Item Group", "is_group", "=", 0]])
    customer_group = first_name("Customer Group", filters=[["Customer Group", "is_group", "=", 0]]) or first_name("Customer Group")
    territory = first_name("Territory", filters=[["Territory", "is_group", "=", 0]]) or first_name("Territory")
    price_list = first_name("Price List", filters=[["Price List", "selling", "=", 1]]) or first_name("Price List")
    warehouse = first_name("Warehouse", filters=[["Warehouse", "is_group", "=", 0]])

    if not all([company, item_group, customer_group, territory, price_list, warehouse]):
        raise SystemExit(
            "ERPNext setup is incomplete. Need at least one Company, leaf Item Group, Customer Group, Territory, selling Price List, and leaf Warehouse."
        )

    print(f"Using company={company}, item_group={item_group}, price_list={price_list}, warehouse={warehouse}")

    for customer in CUSTOMERS:
        ensure_customer(customer, customer_group, territory)

    for product in ALL_PRODUCTS:
        ensure_item(product, item_group)
        ensure_item_price(product["item_code"], price_list, product["price"])

    ensure_stock(company, warehouse)
    ensure_inventory_extension_stock(company, warehouse)
    ensure_sales_orders(company, warehouse)

    for campaign in CAMPAIGNS:
        ensure_campaign(campaign)

    print("Demo data seed complete.")


def first_name(doctype: str, filters: list[Any] | None = None) -> str | None:
    rows = erp_client.list_docs(doctype, fields=["name"], filters=filters, limit=1)
    return rows[0]["name"] if rows else None


def exists(doctype: str, filters: dict[str, Any] | list[Any]) -> bool:
    return bool(erp_client.list_docs(doctype, fields=["name"], filters=filters, limit=1))


def ensure_customer(customer_name: str, customer_group: str, territory: str) -> None:
    if exists("Customer", {"customer_name": customer_name}):
        print(f"Customer exists: {customer_name}")
        return
    erp_client.create_doc(
        "Customer",
        {
            "customer_name": customer_name,
            "customer_type": "Individual",
            "customer_group": customer_group,
            "territory": territory,
        },
    )
    print(f"Created customer: {customer_name}")


def ensure_item(product: dict[str, Any], item_group: str) -> None:
    if exists("Item", {"item_code": product["item_code"]}):
        print(f"Item exists: {product['item_code']}")
        return
    erp_client.create_doc(
        "Item",
        {
            "item_code": product["item_code"],
            "item_name": product["item_name"],
            "item_group": item_group,
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "disabled": 0,
        },
    )
    print(f"Created item: {product['item_code']}")


def ensure_item_price(item_code: str, price_list: str, rate: float) -> None:
    if exists("Item Price", {"item_code": item_code, "price_list": price_list}):
        print(f"Item Price exists: {item_code} / {price_list}")
        return
    erp_client.create_doc(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": price_list,
            "price_list_rate": rate,
            "selling": 1,
        },
    )
    print(f"Created item price: {item_code} / {price_list} = {rate}")


def ensure_stock(company: str, warehouse: str) -> None:
    marker = f"{PREFIX}-SEED-STOCK"
    if exists("Stock Entry", [["Stock Entry", "remarks", "like", f"%{marker}%"]]):
        print("Demo stock entry already exists; skip stock seeding.")
        return

    stock_entry = erp_client.create_doc(
        "Stock Entry",
        {
            "stock_entry_type": "Material Receipt",
            "purpose": "Material Receipt",
            "company": company,
            "posting_date": date.today().isoformat(),
            "remarks": marker,
            "items": [
                {
                    "item_code": product["item_code"],
                    "t_warehouse": warehouse,
                    "qty": product["stock"],
                    "basic_rate": max(float(product["price"]) * 0.6, 1),
                }
                for product in PRODUCTS
            ],
        },
    )
    submit_doc("Stock Entry", stock_entry["name"])
    print(f"Created and submitted stock entry: {stock_entry['name']}")


def ensure_inventory_extension_stock(company: str, warehouse: str) -> None:
    marker = f"{PREFIX}-SEED-INVENTORY-EXT-001"
    if exists("Stock Entry", [["Stock Entry", "remarks", "like", f"%{marker}%"]]):
        print("Additional inventory stock entry already exists; skip inventory extension seeding.")
        return

    stock_entry = erp_client.create_doc(
        "Stock Entry",
        {
            "stock_entry_type": "Material Receipt",
            "purpose": "Material Receipt",
            "company": company,
            "posting_date": date.today().isoformat(),
            "remarks": marker,
            "items": [
                {
                    "item_code": product["item_code"],
                    "t_warehouse": warehouse,
                    "qty": product["stock"],
                    "basic_rate": max(float(product["price"]) * 0.55, 1),
                }
                for product in INVENTORY_PRODUCTS
            ],
        },
    )
    submit_doc("Stock Entry", stock_entry["name"])
    print(f"Created and submitted additional inventory stock entry: {stock_entry['name']}")


def ensure_sales_orders(company: str, warehouse: str) -> None:
    orders = [
        {
            "po_no": f"{PREFIX}-SO-001",
            "customer": CUSTOMERS[0],
            "days_ago": 4,
            "items": [(f"{PREFIX}-HOT-LOW", 8), (f"{PREFIX}-HOT-ENOUGH", 5)],
        },
        {
            "po_no": f"{PREFIX}-SO-002",
            "customer": CUSTOMERS[1],
            "days_ago": 9,
            "items": [(f"{PREFIX}-HOT-LOW", 6), (f"{PREFIX}-NORMAL", 2)],
        },
        {
            "po_no": f"{PREFIX}-SO-003",
            "customer": CUSTOMERS[2],
            "days_ago": 15,
            "items": [(f"{PREFIX}-SLOW-HIGH", 1), (f"{PREFIX}-LOW-MARGIN", 4)],
        },
        {
            "po_no": f"{PREFIX}-SO-004",
            "customer": CUSTOMERS[0],
            "days_ago": 25,
            "items": [(f"{PREFIX}-HOT-ENOUGH", 7), (f"{PREFIX}-NORMAL", 3)],
        },
        {
            "po_no": f"{PREFIX}-SO-005",
            "customer": CUSTOMERS[1],
            "days_ago": 3,
            "items": [(f"{PREFIX}-INV-POWER-BANK", 10), (f"{PREFIX}-INV-SMART-LAMP", 5)],
        },
        {
            "po_no": f"{PREFIX}-SO-006",
            "customer": CUSTOMERS[2],
            "days_ago": 6,
            "items": [(f"{PREFIX}-INV-USB-CABLE", 30), (f"{PREFIX}-INV-PHONE-CASE", 24)],
        },
        {
            "po_no": f"{PREFIX}-SO-007",
            "customer": CUSTOMERS[0],
            "days_ago": 12,
            "items": [(f"{PREFIX}-INV-BLUETOOTH-SPEAKER", 8), (f"{PREFIX}-INV-WIRELESS-MOUSE", 12)],
        },
        {
            "po_no": f"{PREFIX}-SO-008",
            "customer": CUSTOMERS[1],
            "days_ago": 21,
            "items": [(f"{PREFIX}-INV-DESK-MAT", 3), (f"{PREFIX}-INV-OFFICE-CHAIR", 2)],
        },
    ]
    price_by_item = {product["item_code"]: product["price"] for product in ALL_PRODUCTS}
    for order in orders:
        if exists("Sales Order", {"po_no": order["po_no"]}):
            print(f"Sales Order exists: {order['po_no']}")
            continue
        transaction_date = date.today() - timedelta(days=order["days_ago"])
        delivery_date = transaction_date + timedelta(days=7)
        doc = erp_client.create_doc(
            "Sales Order",
            {
                "company": company,
                "customer": order["customer"],
                "po_no": order["po_no"],
                "transaction_date": transaction_date.isoformat(),
                "delivery_date": delivery_date.isoformat(),
                "items": [
                    {
                        "item_code": item_code,
                        "qty": qty,
                        "rate": price_by_item[item_code],
                        "warehouse": warehouse,
                        "delivery_date": delivery_date.isoformat(),
                    }
                    for item_code, qty in order["items"]
                ],
            },
        )
        print(f"Created sales order draft: {doc['name']}")


def ensure_campaign(campaign: dict[str, str]) -> None:
    if exists("Campaign", {"campaign_name": campaign["campaign_name"]}):
        print(f"Campaign exists: {campaign['campaign_name']}")
        return
    erp_client.create_doc("Campaign", campaign)
    print(f"Created campaign: {campaign['campaign_name']}")


def submit_doc(doctype: str, name: str) -> None:
    doc = erp_client.get_doc(doctype, name)
    erp_client.call_method("frappe.client.submit", {"doc": doc})


if __name__ == "__main__":
    main()
