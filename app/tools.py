"""Agent 可调用的工具（Function Calling / Tool Use）。

每个工具都是一个普通 Python 函数：入参简单、返回 dict。
TOOLS 是对外的 JSON Schema，TOOL_IMPL 是真正执行逻辑的映射表。
"""
import json
import re
import uuid
from datetime import datetime

from . import db
from .config import BASE_DIR
from .rag import KnowledgeBase


def _load_json(name: str):
    return json.loads((BASE_DIR / "data" / name).read_text(encoding="utf-8"))


# JSON 作为回退数据源：MySQL 未启用或连接失败时仍可完整演示
PRODUCTS: list[dict] = _load_json("products.json")
ORDERS: dict[str, dict] = {o["order_id"]: o for o in _load_json("orders.json")}
TICKETS: dict[str, dict] = {}
# 预置的售后工单（退货 / 换货 / 维修），作为 MySQL 不可用时的回退数据
try:
    AFTER_SALES: list[dict] = _load_json("after_sales.json")
except FileNotFoundError:
    AFTER_SALES = []


def _tags_to_list(raw: str) -> list[str]:
    return [t for t in (raw or "").split(",") if t]
KB = KnowledgeBase()


def _product_tokens(product: dict) -> set[str]:
    # 只用名称 / 类目 / 标签做匹配，描述只用于展示，避免「可给手机充电」这类误召回
    text = " ".join([product["name"], product["category"], " ".join(product.get("tags", []))])
    tokens = {product["category"], *product.get("tags", [])}
    for part in re.split(r"[\s/｜,，、]+", text):
        part = part.strip()
        if len(part) >= 2:
            tokens.add(part)
    return {t for t in tokens if len(t) >= 2}


def search_products(query: str = "", category: str = "", max_price: float | None = None) -> dict:
    """按关键词 / 类目 / 价格上限检索商品。数据源：MySQL 优先，回退 JSON。"""
    q = (query or "").strip().lower()

    if max_price is None:
        match = re.search(r"(\d{2,6})\s*元", q)
        if match:
            max_price = float(match.group(1))

    # MySQL：用 SQL 做类目 / 价格过滤，关键词在结果上打分排序
    rows = db.fetch_all("SELECT * FROM products")
    if rows is not None:
        for p in rows:
            p["tags"] = _tags_to_list(p.get("tags", ""))
        source = rows
    else:
        source = PRODUCTS

    hits: list[tuple[int, dict]] = []
    for product in source:
        if category and category not in product["category"]:
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        score = sum(len(tok) for tok in _product_tokens(product) if tok.lower() in q)
        if q and score == 0:
            continue
        hits.append((score, product))

    hits.sort(key=lambda item: (-item[0], item[1]["price"]))
    items = [
        {
            "product_id": p["product_id"],
            "name": p["name"],
            "category": p["category"],
            "price": p["price"],
            "stock": p["stock"],
            "description": p.get("description", ""),
        }
        for _, p in hits[:5]
    ]
    if not items:
        return {"count": 0, "items": [], "message": "没有找到符合条件的商品"}
    return {"count": len(items), "items": items, "source": "mysql" if rows is not None else "json"}


def get_order(order_id: str) -> dict:
    """按订单号查询订单状态、物流与金额。数据源：MySQL 优先，回退 JSON。"""
    oid = (order_id or "").strip().upper()

    row = db.fetch_one("SELECT * FROM orders WHERE order_id = %s", (oid,))
    if row is not None and row:
        return {"found": True, **row, "source": "mysql"}
    if row is None:  # MySQL 不可用，回退本地
        order = ORDERS.get(oid)
        if order:
            return {"found": True, **order, "source": "json"}

    return {"found": False, "message": f"未找到订单 {oid}，请核对订单号是否正确"}


def create_after_sales(order_id: str, reason: str = "") -> dict:
    """为订单创建退货 / 换货 / 维修售后工单。写入 MySQL，失败回退内存。"""
    oid = (order_id or "").strip().upper()

    # 先确认订单存在（MySQL 优先）
    order_row = db.fetch_one("SELECT product_name FROM orders WHERE order_id = %s", (oid,))
    if order_row:
        product_name = order_row["product_name"]
    elif order_row is None:
        local = ORDERS.get(oid)
        if not local:
            return {"success": False, "message": f"未找到订单 {oid}，无法创建售后工单"}
        product_name = local["product_name"]
    else:
        return {"success": False, "message": f"未找到订单 {oid}，无法创建售后工单"}

    ticket_id = f"AS{uuid.uuid4().hex[:8].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "order_id": oid,
        "product_name": product_name,
        "reason": reason or "用户未填写",
        "status": "待审核",
    }

    # 写 MySQL；返回 None 表示未启用或失败，此时回退到内存字典
    affected = db.execute(
        "INSERT INTO after_sales_tickets (ticket_id,order_id,product_name,reason,status) "
        "VALUES (%s,%s,%s,%s,%s)",
        (ticket_id, oid, product_name, ticket["reason"], "待审核"),
    )
    storage = "mysql" if affected else "memory"
    if not affected:
        TICKETS[ticket_id] = ticket

    return {
        "success": True,
        **ticket,
        "storage": storage,
        "next_steps": "请在 24 小时内按短信指引寄回商品，我们收到检测后 1-3 个工作日内处理退款或换货。",
    }


def get_after_sales(order_id: str = "") -> dict:
    """按订单号查询退货 / 换货 / 维修工单进度；不传订单号则列出最近工单。"""
    oid = (order_id or "").strip().upper()

    rows = db.fetch_all("SELECT * FROM after_sales_tickets ORDER BY created_at DESC")
    source = rows if rows is not None else AFTER_SALES
    matched = [t for t in source if not oid or t.get("order_id", "").upper() == oid]

    items = [
        {
            "ticket_id": t.get("ticket_id"),
            "order_id": t.get("order_id"),
            "product_name": t.get("product_name"),
            "type": t.get("type", "退货"),
            "reason": t.get("reason", ""),
            "status": t.get("status", "待审核"),
            "amount": t.get("amount", 0),
            "created_at": str(t.get("created_at", ""))[:19],
        }
        for t in matched
    ]
    return {
        "count": len(items),
        "items": items,
        "source": "mysql" if rows is not None else "json",
        "message": "" if items else (f"订单 {oid} 没有售后工单记录" if oid else "暂无售后工单记录"),
    }


def search_faq(query: str) -> dict:
    """检索店铺规则知识库（退换货、发货、运费、发票、保修、优惠券等）。"""
    return {"query": query, "results": KB.search(query, top_k=3)}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "根据用户需求检索在售商品，支持关键词、类目和价格上限过滤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "商品关键词，如 降噪耳机、手机、充电宝"},
                    "category": {"type": "string", "description": "类目：手机 / 耳机 / 配件 / 电脑 / 穿戴"},
                    "max_price": {"type": "number", "description": "价格上限，单位元"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "根据订单号查询订单状态、物流信息和金额。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号，例如 SO20261114002"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_after_sales",
            "description": "为指定订单创建退货、换货或维修的售后工单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"},
                    "reason": {"type": "string", "description": "售后原因，例如 耳机有杂音"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_after_sales",
            "description": "查询订单的退货/换货/维修售后工单进度；传订单号查指定订单，不传则列出最近工单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号，例如 SO20261111010；可留空查询全部"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_faq",
            "description": "检索店铺规则知识库，回答退换货、发货、运费、发票、保修、优惠券等政策问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用户的问题原文"},
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_IMPL = {
    "search_products": search_products,
    "get_order": get_order,
    "create_after_sales": create_after_sales,
    "get_after_sales": get_after_sales,
    "search_faq": search_faq,
}
