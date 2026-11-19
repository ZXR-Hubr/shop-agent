"""交互式写入 .env：把阿里云百炼（DashScope）的 API Key 存到项目里。

由 配置阿里云.bat 调用；也可以手动运行：
    .venv\\Scripts\\python.exe setup_key.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"

TEMPLATE = """# ===== LLM 配置：阿里云百炼（DashScope · OpenAI 兼容接口）=====
# 开通地址：https://bailian.console.aliyun.com
LLM_API_KEY={key}
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# 可选模型（都支持 Function Calling）：qwen-plus 推荐 / qwen-max 效果最好 / qwen-turbo 最快最便宜
TEMPERATURE=0.3
REQUEST_TIMEOUT=60
"""


def main() -> int:
    print("=" * 60)
    print("把阿里云百炼 API Key 写入  E:\\shop-agent\\.env")
    print("=" * 60)
    print("获取方式：https://bailian.console.aliyun.com 右上角 API-KEY")
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
        print(f"[!] 你输入的 Key 中间有空格，已自动去掉空格。")
        key = key.replace(" ", "")
    if not key.startswith("sk-"):
        print(f"[!] 注意：百炼的 Key 一般以 sk- 开头，你输入的是 {key[:4]}...，先照样写入，失败再重新获取。")

    ENV.write_text(TEMPLATE.format(key=key), encoding="utf-8")
    print()
    print(f"[OK] 已写入 {ENV}")
    print(f"     Key: {key[:6]}...{key[-4:] if len(key) > 10 else ''}")
    print("     模型: qwen-plus   接口: dashscope.aliyuncs.com/compatible-mode/v1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
