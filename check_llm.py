"""真实大模型连通性自检（阿里云百炼 / 任意 OpenAI 兼容接口）。

用法:
    .venv\\Scripts\\python.exe check_llm.py

检查四件事：
    1. .env 有没有读到 Key、Base URL、模型名；
    2. Key 和网络是否通（拉一次模型列表）；
    3. 模型是否支持 Function Calling（带 tools 发一次真实请求）；
    4. Agent 端到端：工具结果 -> 自然语言回答，并打印 token 与时延。
"""
import asyncio
import sys
import time

import httpx

from app.agent import Agent
from app.config import BASE_DIR, settings
from app.llm import LLMClient
from app.memory import SessionStore
from app.tools import TOOLS

OK = "[OK]"
BAD = "[X]"


def _mask(key: str) -> str:
    if not key:
        return "(空)"
    if len(key) <= 10:
        return key[:3] + "***"
    return f"{key[:6]}...{key[-4:]}"


def _show_settings() -> bool:
    env_path = BASE_DIR / ".env"
    print("=" * 64)
    print("1. 读取配置")
    print("=" * 64)
    print(f"   .env 文件      : {env_path}  ({'存在' if env_path.exists() else '不存在'})")
    print(f"   LLM_BASE_URL   : {settings.llm_base_url}")
    print(f"   LLM_MODEL      : {settings.llm_model}")
    print(f"   LLM_API_KEY    : {_mask(settings.llm_api_key)}")
    print(f"   运行模式       : {'Mock（假数据）' if settings.llm_mock else '真实 LLM'}")
    key = settings.llm_api_key
    if key.startswith(("ghp_", "github_pat_", "gho_", "ghu_")):
        print()
        print(f"{BAD} 你填的是 GitHub 令牌（ghp_ 开头），不是阿里云百炼的 API Key。")
        print("     GitHub 令牌只用来上传代码；调用大模型要用百炼的 sk- Key。")
        print("     获取：https://bailian.console.aliyun.com 右上角 API-KEY")
        print("     修复：双击 配置阿里云.bat 重新填（会保留你现在的接口和模型）。")
        return False
    if settings.llm_mock:
        print()
        print(f"{BAD} 没有读到 Key，当前是 Mock 模式。")
        print("     请把阿里云百炼的 Key 填进上面这个 .env 的 LLM_API_KEY= 后面，保存后重跑。")
        return False
    return True


async def _check_models() -> bool:
    print()
    print("=" * 64)
    print("2. 检查 Key 与网络（模型列表接口）")
    print("=" * 64)
    url = f"{settings.llm_base_url}/models"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        print(f"{BAD} 请求失败：{type(exc).__name__}: {exc}")
        print("     常见原因：断网、需要代理、Base URL 写错。")
        print(f"     当前 Base URL：{settings.llm_base_url}")
        return False

    if resp.status_code == 401:
        print(f"{BAD} 401：Key 无效、填错或已删除。")
        print(f"     返回：{resp.text[:200]}")
        return False
    if resp.status_code in (402, 403):
        print(f"{BAD} HTTP {resp.status_code}：账户欠费，或还没有开通「百炼大模型服务」。")
        print(f"     返回：{resp.text[:200]}")
        print("     去 https://bailian.console.aliyun.com 开通并确认余额。")
        return False
    if resp.status_code == 404:
        print(f"{BAD} 404：Base URL 或模型名不对。当前 Base URL：{settings.llm_base_url}")
        print(f"     当前模型：{settings.llm_model}；请确认该接口是否提供这个模型。")
        print(f"     返回：{resp.text[:200]}")
        return False
    if resp.status_code >= 400:
        print(f"{BAD} HTTP {resp.status_code}：{resp.text[:200]}")
        return False

    try:
        models = [item.get("id") for item in resp.json().get("data", [])]
    except Exception:
        models = []
    shown = [m for m in models if m][:8]
    print(f"{OK} 鉴权通过，可用模型（前 8 个）：{', '.join(shown) or '(列表为空)'}")
    if models and settings.llm_model not in models:
        print(f"     ! 注意：{settings.llm_model} 不在返回列表里，确认模型名是否写错。")
    return True


async def _check_tools() -> bool:
    print()
    print("=" * 64)
    print("3. 检查 Function Calling（带 tools 的真实请求）")
    print("=" * 64)
    client = LLMClient()
    messages = [{"role": "user", "content": "订单 SO20261114002 到哪了？"}]
    try:
        result = await client.chat(messages, tools=TOOLS)
    except Exception as exc:
        print(f"{BAD} 调用失败：{exc}")
        return False

    calls = result.get("tool_calls") or []
    if not calls:
        print(f"{BAD} 模型没有发起工具调用，回答是：{result.get('content', '')[:120]}")
        print("     qwen 系列请用 qwen-plus / qwen-max / qwen-turbo，它们支持 tools。")
        return False

    name = calls[0]["function"]["name"]
    print(f"{OK} 模型主动调用了工具：{name}")
    print(f"     参数：{calls[0]['function']['arguments']}")
    print(f"     token 用量：{result.get('usage')}")

    print()
    print("=" * 64)
    print("4. Agent 端到端（工具结果 -> 自然语言回答）")
    print("=" * 64)
    agent = Agent(LLMClient(), SessionStore())
    started = time.perf_counter()
    out = await agent.chat("selftest", "订单 SO20261114002 到哪了？")
    cost = (time.perf_counter() - started) * 1000
    print(f"   工具链：{[c['name'] for c in out.get('tool_calls', [])]}")
    print(f"   回答  ：{out.get('reply')}")
    print(f"   耗时  ：{cost:.0f} ms")
    print(f"   tokens：{out.get('usage')}")
    if not out.get("reply"):
        return False
    return True


async def main() -> int:
    if not _show_settings():
        return 1
    if not await _check_models():
        return 1
    if not await _check_tools():
        return 1
    print()
    print("=" * 64)
    print(f"全部通过：阿里云百炼（{settings.llm_model}）已接通，可以双击 启动.bat 使用了")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
