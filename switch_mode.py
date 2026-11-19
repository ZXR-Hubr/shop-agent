"""切换运行模式：Mock（假数据、零费用） / API（真实阿里云模型）。

用法（一般由 切换为Mock.bat / 切换为API.bat 调用）：
    .venv\\Scripts\\python.exe switch_mode.py mock
    .venv\\Scripts\\python.exe switch_mode.py api
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"


def set_mode(mode: str) -> None:
    if mode not in ("mock", "api"):
        raise SystemExit("用法: switch_mode.py mock|api")

    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("LLM_MOCK=")]
    # API 模式显式写 0；Mock 模式写 1
    lines.append(f"LLM_MOCK={1 if mode == 'mock' else 0}")
    ENV.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    key_ok = False
    for ln in lines:
        if ln.startswith("LLM_API_KEY=") and len(ln.split("=", 1)[1].strip()) > 10:
            key_ok = True
    if mode == "api" and not key_ok:
        print("注意：.env 里没有有效的 LLM_API_KEY，API 模式可能连不上。")
        print("      请先双击 配置阿里云.bat 填入 sk- 开头的 Key。")
        return

    print(f"[OK] 已切换到 {mode.upper()} 模式（写入 .env 的 LLM_MOCK）")
    print("     重启服务后生效：关掉黑窗口，重新双击 启动.bat")
    if mode == "mock":
        print("     当前不调用真实模型，不产生任何费用。")
    else:
        print("     当前调用真实大模型，对话会计费。")


if __name__ == "__main__":
    set_mode(sys.argv[1].lower() if len(sys.argv) > 1 else "")
