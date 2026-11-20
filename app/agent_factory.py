"""Agent 工厂：根据 AGENT_FRAMEWORK 选择手写循环或 LangChain 实现。

- native（默认）：app/agent.py 手写 Function Calling 循环，零额外依赖；
- langchain：app/langchain_agent.py，需安装 langchain / langchain-openai。

Mock 模式下统一使用手写 Agent（语言规则模拟工具调用，不消耗 token）；
langchain 模式的构建失败（缺依赖 / 缺 Key）会自动回退 native，保证服务可用。
"""
import logging

from .agent import Agent
from .config import settings
from .llm import LLMClient
from .runtime import is_mock

logger = logging.getLogger("shop_agent")


def build_agent(memory):
    if settings.agent_framework == "langchain" and not is_mock() and settings.llm_api_key:
        try:
            from .langchain_agent import LangChainAgent
            agent = LangChainAgent(memory)
            logger.info("Agent 框架: langchain")
            return agent
        except Exception as exc:
            logger.warning("LangChain 初始化失败，回退 native: %s", exc)
    return Agent(LLMClient(), memory)
