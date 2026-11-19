import asyncio

from app.agent import Agent
from app.llm import LLMClient
from app.memory import SessionStore


def test_agent_calls_get_order():
    agent = Agent(LLMClient(), SessionStore())
    result = asyncio.run(agent.chat("t-order", "订单 SO20261114002 到哪了"))
    assert result["tool_calls"][0]["name"] == "get_order"
    assert "运输中" in result["reply"]


def test_agent_calls_create_after_sales():
    agent = Agent(LLMClient(), SessionStore())
    result = asyncio.run(agent.chat("t-as", "订单 SO20261112001 的耳机有杂音，我想退货"))
    assert result["tool_calls"][0]["name"] == "create_after_sales"
    assert "工单" in result["reply"]


def test_agent_uses_faq_tool():
    agent = Agent(LLMClient(), SessionStore())
    result = asyncio.run(agent.chat("t-faq", "你们满多少包邮？"))
    assert result["tool_calls"][0]["name"] == "search_faq"
    assert "包邮" in result["reply"]


def test_memory_keeps_multi_turn_history():
    async def run():
        memory = SessionStore()
        agent = Agent(LLMClient(), memory)
        await agent.chat("t-mem", "你好")
        await agent.chat("t-mem", "订单 SO20261114002 到哪了")
        return await memory.get("t-mem")

    history = asyncio.run(run())
    assert len(history) >= 4
    assert history[0]["role"] == "user"
