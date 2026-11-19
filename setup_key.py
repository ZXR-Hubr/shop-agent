"""交互式写入 .env：把阿里云百炼的 API Key 存到项目里。

由 配置阿里云.bat 调用；也可以手动运行：
    .venv\Scripts\python.exe setup_key.py

注意：只改 Key，保留你已经在 .env 里改好的 Base URL 和模型名。
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"


def _load_existing() -> dict:
    """读取现有 .env，保留 Base URL / 模型等关键配置。"""
    cfg = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def main() -> int:
    old = _load_existing()
    base_url = old.get("LLM_BASE_URL") or DEFAULT_BASE_URL
    model = old.get("LLM_MODEL") or DEFAULT_MODEL
    temperature = old.get("TEMPERATURE") or "0.3"
    timeout = old.get("REQUEST_TIMEOUT") or "60"

    print("=" * 62)
    print("把阿里云百炼 API Key 写入  E:\\shop-agent\\.env")
    print("=" * 62)
    print("获取地址：https://bailian.console.aliyun.com 右上角 API-KEY")
    print("当前接口（保持不变）:", base_url)
    print("当前模型（保持不变）:", model)
    print("直接回车 = 取消（不改动现有配置）")
    print()

    try:
        raw = input("请粘贴 Key（sk- 开头）：\n> ")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消，.env 未修改。")
        return 2

    key = raw.strip().strip('"').strip("'").strip()
    if not key:
        print("没有输入 Key，已取消，.env 未修改。")
        return 2
    if " " in key:
        key = key.replace(" ", "")

    # 关键校验：GitHub 令牌和 API Key 是两回事，绝不能混用
    if key.startswith("ghp_") or key.startswith("github_pat_") or key.startswith("gho_"):
        print()
        print("[X] 这个是 GitHub 的个人访问令牌，不是阿里云百炼的 API Key！")
        print("    两者用途完全不同：GitHub 令牌用来传代码，百炼 Key 用来调大模型。")
        print("    请打开 https://bailian.console.aliyun.com ，右上角 API-KEY 获取 sk- 开头的 Key。")
        print("    .env 未修改。")
        return 1
    if not key.startswith("sk-"):
        print()
        print(f"[X] 阿里云百炼的 Key 以 sk- 开头，你输入的是 {key[:6]}... 。")
        print("    请确认是否复制错（例如复制成了 GitHub 令牌或网页会话）。.env 未修改。")
        return 1

    content = (
        "# ===== LLM 配置（保留你现有的接口与模型）=====\n"
        f"LLM_API_KEY={key}\n"
        f"LLM_BASE_URL={base_url}\n"
        f"LLM_MODEL={model}\n"
        f"TEMPERATURE={temperature}\n"
        f"REQUEST_TIMEOUT={timeout}\n"
    )
    ENV.write_text(content, encoding="utf-8")

    print()
    print(f"[OK] 已写入 {ENV}")
    print(f"     Key   : {key[:6]}...{key[-4:]}")
    print(f"     接口  : {base_url}")
    print(f"     模型  : {model}")
    print("     现在可以运行 check_llm.py 自检了。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
