import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 单元测试强制使用 Mock 模式 + 关闭 MySQL，保证确定性、不依赖外部服务
os.environ["LLM_MOCK"] = "1"
os.environ["LLM_API_KEY"] = ""
os.environ["EMBED_MODEL"] = ""
os.environ["MYSQL_ENABLED"] = "0"
