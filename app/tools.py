"""Agent 可调用的工具（Function Calling / Tool Use）。

每个工具都是一个普通 Python 函数：入参简单、返回 dict。
TOOLS 是对外的 JSON Schema，TOOL_IMPL 是真正执行逻辑的映射表。
"""
import json
import re
import uuid
from pathlib import Path

from .config import BASE_DIR
from .rag import KnowledgeBase


def _load_json(name: str):
    return json.loads((BASE_DIR / "data" / name).read_text(encoding="utf-8"))


PRODUCTS: list[dict] = _load_json("products.json")
ORDERS: dict[str, dict] = {o["order_id"]: o for o in _load_json("orders.json")}
TICKETS: dict[str, dict] = {}
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
    """按关键词 / 类目 / 价格上限检索商品。"""
    q = (query or "").strip().lower()

    if max_price is None:
        match = re.search(r"(\d{2,6})\s*元", q)
        if match:
            max_price = float(match.group(1))

    hits: list[tuple[int, dict]] = []
    for product in PRODUCTS:
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
    return {"count": len(items), "items": items}


def get_order(order_id: str) -> dict:
    """按订单号查询订单状态、物流与金额。"""
    oid = (order_id or "").strip().upper()
    order = ORDERS.get(oid)
    if not order:
        return {"found": False, "message": f"未找到订单 {oid}，请核对订单号是否正确"}
    return {"found": True, **order}


def create_after_sales(order_id: str, reason: str = "") -> dict:
    """为订单创建退货 / 换货 / 维修售后工单。"""
    oid = (order_id or "").strip().upper()
    order = ORDERS.get(oid)
    if not order:
        return {"success": False, "message": f"未找到订单 {oid}，无法创建售后工单"}
    ticket_id = f"AS{uuid.uuid4().hex[:8].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "order_id": oid,
        "product_name": order["product_name"],
        "reason": reason or "用户未填写",
        "status": "待审核",
    }
    TICKETS[ticket_id] = ticket
    return {
        "success": True,
        **ticket,
        "next_steps": "请在 24 小时内按短信指引寄回商品，我们收到检测后 1-3 个工作日内处理退款或换货。",
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
    "search_faq": search_faq,
}
