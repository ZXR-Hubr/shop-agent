"""LLM 客户端：统一走 OpenAI 兼容的 /chat/completions 接口。

默认对接阿里云百炼（DashScope）的 qwen 系列，也支持其他兼容服务（DeepSeek、OpenAI 等），
换厂商只需改 .env 里的 LLM_BASE_URL / LLM_MODEL。内置 Mock 模式：
没有 API Key 时用规则模拟「调用工具 -> 生成回答」，保证项目开箱即跑。
"""
import json
import re

import httpx

from .config import settings
from .runtime import is_mock

ORDER_RE = re.compile(r"[A-Za-z]{2}\d{6,}")


class LLMClient:
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if is_mock():
            return _mock_chat(messages)

        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": settings.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"LLM 接口返回 {resp.status_code}: {resp.text[:300]}")
            data = resp.json()

        message = data["choices"][0]["message"]
        return {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
            "usage": data.get("usage") or {},
        }


# ---------------------------------------------------------------------------
# Mock 模式：仅用于无 Key / 单元测试 / 离线演示，逻辑是确定性的
# ---------------------------------------------------------------------------

def _last_user(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return (message.get("content") or "").strip()
    return ""


def _mock_chat(messages: list[dict]) -> dict:
    if messages and messages[-1].get("role") == "tool":
        return {"content": _mock_final(messages[-1].get("content", "")), "tool_calls": [], "usage": {"mock": True}}

    user = _last_user(messages)
    if any(word in user for word in ["你好", "您好", "在吗", "hi", "hello"]) and len(user) <= 12:
        return {
            "content": "您好，我是小满商城的智能客服小满～您可以咨询商品、查询订单，或了解退换货、发票、保修等售后问题。",
            "tool_calls": [],
            "usage": {"mock": True},
        }

    match = ORDER_RE.search(user)
    order_id = match.group(0).upper() if match else ""

    if order_id and any(word in user for word in ["进度", "售后单", "退到哪", "换到哪", "工单", "处理到"]):
        # 查询已有退货 / 换货 / 维修工单的进度
        name, arguments = "get_after_sales", {"order_id": order_id}
    elif order_id and any(word in user for word in ["申请退", "我要退", "想退", "申请换", "要换货", "维修", "坏", "杂音"]):
        name, arguments = "create_after_sales", {"order_id": order_id, "reason": user}
    elif order_id and any(word in user for word in ["订单", "物流", "到哪", "发货", "状态", "什么时候", "查"]):
        name, arguments = "get_order", {"order_id": order_id}
    elif any(word in user for word in [
        "退", "换", "运费", "包邮", "发票", "保修", "优惠券", "发货时间", "地址", "退款", "人工", "客服", "支付", "积分",
    ]):
        name, arguments = "search_faq", {"query": user}
    else:
        name, arguments = "search_products", {"query": user}

    return {
        "content": "",
        "tool_calls": [
            {
                "id": "call_mock_1",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
            }
        ],
        "usage": {"mock": True},
    }


def _mock_final(raw: str) -> str:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        data = {}

    if "results" in data:
        results = data.get("results") or []
        if not results:
            return "抱歉，知识库里暂时没有查到相关信息，您可以换个说法再问一次。"
        lines = [f"【{item['title']}】{item['content']}" for item in results[:2]]
        return "为您查到以下信息：\n" + "\n".join(lines)

    if data.get("ticket_id"):
        return (
            f"已为您创建售后工单 {data['ticket_id']}（订单 {data['order_id']}，商品：{data.get('product_name', '')}），"
            f"当前状态：{data.get('status', '')}。{data.get('next_steps', '')}"
        )

    if data.get("found") and data.get("status"):
        return (
            f"订单 {data['order_id']} 当前状态为「{data['status']}」，商品：{data.get('product_name', '')}，"
            f"金额 ¥{data.get('amount', '')}。物流：{data.get('logistics', '暂无')}。"
        )

    if "items" in data:
        items = data.get("items") or []
        # 售后工单结果：每项带 ticket_id
        if items and "ticket_id" in items[0]:
            lines = [
                f"- 工单 {t['ticket_id']}（订单 {t.get('order_id', '')}，{t.get('type', '售后')}）："
                f"{t.get('product_name', '')}，状态「{t.get('status', '')}」"
                + (f"，金额 ¥{t.get('amount', 0)}" if t.get('amount') else "")
                for t in items[:5]
            ]
            return "为您查到以下售后工单：\n" + "\n".join(lines)
        if not items:
            if data.get("message"):
                return data["message"]
            return "暂时没有找到完全匹配的商品，您可以告诉我预算和用途，我再帮您筛选。"
        lines = [
            f"- {item['name']}（¥{item['price']}，库存 {item['stock']}）：{item.get('description', '')}"
            for item in items[:3]
        ]
        return "为您推荐以下商品：\n" + "\n".join(lines)

    if data.get("message"):
        return data["message"]

    return "抱歉，我暂时没有查到相关信息，您可以补充一下订单号或具体问题。"
