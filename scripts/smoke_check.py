from __future__ import annotations

import json

from ecommerce_agent.config import settings
from ecommerce_agent.mcp_server.erp_client import ERPClientError, erp_client
from ecommerce_agent.rag_system.wiki_manager import KnowledgeBase


def main() -> None:
    kb = KnowledgeBase()
    hits = kb.search("库存低于安全库存时如何处理营销促销", k=2)
    print("Knowledge retrieval:")
    print(json.dumps([hit.__dict__ for hit in hits], ensure_ascii=False, indent=2))

    print("\nFrappe endpoint:")
    print(f"- base_url: {settings.frappe_base_url}")
    print(f"- site: {settings.frappe_site}")
    try:
        print(json.dumps(erp_client.ping(), ensure_ascii=False, indent=2))
    except (ERPClientError, OSError) as exc:
        print(f"Frappe ping failed: {exc}")


if __name__ == "__main__":
    main()
