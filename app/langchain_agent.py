"""LangChain 版 Agent：与手写循环并存的第二套编排实现。

简历里写「掌握 LangChain」，这里给出真实落地：用 LangChain 的
create_tool_calling_agent + AgentExecutor 驱动同一批业务工具，和 app/agent.py
里手写的 Function Calling 循环实现同样的对话能力。通过 AGENT_FRAMEWORK=langchain
切换，可在面试中对比两种编排方式的差异。

注意：LangChain 版只走真实 API（Mock 模式由手写 Agent 承接），且需要额外安装
langchain / langchain-openai；未安装或配置失败时，工厂自动回退到手写 Agent。
"""
import json
import logging

from .config import settings
from .guard import check as guard_check
from .tools import TOOLS, TOOL_IMPL

logger = logging.getLogger("shop_agent.langchain")

LANGCHAIN_SYSTEM_PROMPT = """你是电商平台「小满商城」的智能客服助手「小满」。
回答商品、订单、售后问题时，必须先调用工具获取真实数据，不要编造。
信息不足时主动追问，中文回答，金额用 ¥。无法解决时引导转人工（9:00-22:00）。"""


def _build_langchain_tools():
    """把本项目的 TOOLS（OpenAI 兼容 schema）转成 LangChain StructuredTool。"""
    from langchain_core.tools import StructuredTool
    from pydantic import create_model

    built = []
    for spec in TOOLS:
        fn = spec["function"]
        name = fn["name"]
        impl = TOOL_IMPL.get(name)
        if impl is None:
            continue

        schema = fn.get("parameters", {})
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        type_map = {"string": str, "number": float, "integer": int, "boolean": bool, "array": list}
        fields = {}
        for key, meta in props.items():
            py_type = type_map.get(meta.get("type"), str)
            default = ... if key in required else None
            fields[key] = (py_type, default)

        ArgsModel = create_model(f"{name}_Args", **fields)

        def make_runner(func):
            def run(**kwargs):
                return json.dumps(func(**kwargs), ensure_ascii=False)
            return run

        built.append(StructuredTool.from_function(
            func=make_runner(impl),
            name=name,
            description=fn.get("description", ""),
            args_schema=ArgsModel,
        ))
    return built


class LangChainAgent:
    """基于 LangChain AgentExecutor 的对话实现，接口与手写 Agent 一致。"""

    def __init__(self, memory):
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_agent

        self.memory = memory
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            temperature=settings.temperature,
        )
        self.tools = _build_langchain_tools()
        # LangChain 1.x 用 create_agent（旧版是 create_tool_calling_agent + AgentExecutor）
        self.graph = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=LANGCHAIN_SYSTEM_PROMPT,
        )

    async def chat(self, session_id: str, user_message: str) -> dict:
        refusal = guard_check(user_message)
        if refusal:
            return {"reply": refusal, "tool_calls": [], "usage": {}, "blocked": True}

        history = await self.memory.get(session_id)
        # 转成 LangChain 消息对象；create_agent 的输入是 {"messages": [...]}
        from langchain_core.messages import HumanMessage, AIMessage

        lc_messages = []
        for m in history:
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                lc_messages.append(AIMessage(content=m["content"]))
        lc_messages.append(HumanMessage(content=user_message))

        result = await self.graph.ainvoke({"messages": lc_messages})
        messages = result.get("messages", [])
        last = messages[-1] if messages else None
        reply = (getattr(last, "content", "") or "").strip() if last else ""
        reply = reply or "抱歉，我暂时没有理解，可以再描述一下吗？"
        # 提取工具调用轨迹：AIMessage.tool_calls 与 ToolMessage 按顺序一一对应
        trace = []
        tool_results = [
            str(getattr(m, "content", ""))[:300]
            for m in messages if getattr(m, "type", "") == "tool"
        ]
        idx = 0
        for msg in messages:
            for call in getattr(msg, "tool_calls", None) or []:
                trace.append({
                    "name": call.get("name", ""),
                    "arguments": call.get("args", {}),
                    "result": tool_results[idx] if idx < len(tool_results) else "",
                })
                idx += 1
        await self.memory.append(session_id, "user", user_message)
        await self.memory.append(session_id, "assistant", reply)
        return {"reply": reply, "tool_calls": trace, "usage": {}}
