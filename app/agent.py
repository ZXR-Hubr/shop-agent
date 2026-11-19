"""Agent 核心：多轮对话 + 工具调用循环。

一次请求的流程：
1. 取出该会话的历史消息，拼上 system prompt 和本轮用户输入；
2. 调 LLM，如果返回 tool_calls，就逐个执行本地工具；
3. 把工具结果以 role=tool 追加回上下文，再次调 LLM；
4. 直到模型给出最终答复（或达到最大轮数）；
5. 把本轮 user / assistant 消息写入会话记忆。
"""
import json
import logging

from .config import settings
from .llm import LLMClient
from .memory import SessionStore
from .tools import TOOL_IMPL, TOOLS

logger = logging.getLogger("shop_agent")

SYSTEM_PROMPT = """你是电商平台「小满商城」的智能客服助手「小满」。你的职责是帮助用户解决商品咨询、订单查询和售后问题。

请遵守以下规则：
1. 先获取事实再回答：涉及商品信息、订单状态、店铺政策时，必须调用工具获取真实数据，不要凭空编造。
2. 用户提供订单号时，查询订单用 get_order；需要退货 / 换货 / 维修时用 create_after_sales。
3. 商品推荐用 search_products；退换货、运费、发票、保修、优惠券等政策问题用 search_faq。
4. 信息不足时主动追问（例如缺少订单号），一次只问最关键的问题。
5. 语气亲切、简洁，使用中文回答；金额用 ¥ 表示。
6. 无法解决的问题，引导用户转人工客服（服务时间 9:00-22:00）。"""


class Agent:
    def __init__(self, llm: LLMClient, memory: SessionStore):
        self.llm = llm
        self.memory = memory

    async def chat(self, session_id: str, user_message: str) -> dict:
        history = await self.memory.get(session_id)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": user_message},
        ]
        trace: list[dict] = []
        usage: dict = {}
        reply = ""

        for _ in range(settings.max_tool_rounds):
            try:
                result = await self.llm.chat(messages, tools=TOOLS)
            except Exception as exc:  # 网络 / 鉴权 / 限额等异常统一兜底
                logger.warning("LLM 调用失败: %s", exc)
                reply = "抱歉，智能客服暂时不可用，请稍后重试，或联系人工客服（9:00-22:00）。"
                break

            if result.get("usage"):
                usage = result["usage"]

            tool_calls = result.get("tool_calls") or []
            if not tool_calls:
                reply = (result.get("content") or "").strip() or "抱歉，我暂时没有理解您的问题，可以再描述一下吗？"
                break

            # 把模型的工具调用意图写回上下文
            messages.append(
                {
                    "role": "assistant",
                    "content": result.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for call in tool_calls:
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                if name in TOOL_IMPL:
                    tool_result = TOOL_IMPL[name](**arguments)
                else:
                    tool_result = {"error": f"未知工具: {name}"}

                trace.append({"name": name, "arguments": arguments, "result": tool_result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
        else:
            reply = "抱歉，这次处理时间有点长，请稍后再试，或联系人工客服（9:00-22:00）。"

        await self.memory.append(session_id, "user", user_message)
        await self.memory.append(session_id, "assistant", reply)
        return {"reply": reply, "tool_calls": trace, "usage": usage}
