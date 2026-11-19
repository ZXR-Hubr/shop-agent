"""LLM Evaluation：用固定测试集跑一遍 Agent，计算可量化指标。

指标：
- tool_accuracy       期望工具是否被调用（工具选择是否正确）
- keyword_hit_rate    回答是否覆盖期望关键词（事实是否正确）
- pass_rate           工具正确且关键词命中
- avg_latency_ms      平均响应耗时

运行：python eval/run_eval.py
结果：控制台表格 + eval/report.json
"""
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import Agent  # noqa: E402
from app.config import settings  # noqa: E402
from app.llm import LLMClient  # noqa: E402
from app.memory import SessionStore  # noqa: E402

CASES = json.loads((Path(__file__).resolve().parent / "cases.json").read_text(encoding="utf-8"))


async def run() -> int:
    agent = Agent(LLMClient(), SessionStore())
    rows = []
    latencies = []

    for case in CASES:
        started = time.perf_counter()
        result = await agent.chat(f"eval-{case['id']}", case["message"])
        latency = int((time.perf_counter() - started) * 1000)
        latencies.append(latency)

        called_tools = [item["name"] for item in result["tool_calls"]]
        expected = case.get("expect_tool")
        tool_ok = expected is None or expected in called_tools
        keyword_ok = all(keyword in result["reply"] for keyword in case.get("expect_keywords", []))

        rows.append(
            {
                **case,
                "called_tools": called_tools,
                "reply": result["reply"],
                "latency_ms": latency,
                "tool_ok": tool_ok,
                "keyword_ok": keyword_ok,
                "pass": tool_ok and keyword_ok,
            }
        )

    total = len(rows)
    passed = sum(row["pass"] for row in rows)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "mock" if settings.llm_mock else "api",
        "model": "mock" if settings.llm_mock else settings.llm_model,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4),
        "tool_accuracy": round(sum(row["tool_ok"] for row in rows) / total, 4),
        "keyword_hit_rate": round(sum(row["keyword_ok"] for row in rows) / total, 4),
        "avg_latency_ms": round(statistics.mean(latencies), 1),
        "cases": rows,
    }

    out = Path(__file__).resolve().parent / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"模式: {report['mode']} | 用例: {total} | 通过: {passed} | "
        f"通过率: {report['pass_rate']:.0%} | 工具准确率: {report['tool_accuracy']:.0%} | "
        f"关键词命中率: {report['keyword_hit_rate']:.0%} | 平均耗时: {report['avg_latency_ms']}ms"
    )
    print("-" * 100)
    for row in rows:
        status = "PASS" if row["pass"] else "FAIL"
        tools = ",".join(row["called_tools"]) or "-"
        print(f"{status} {row['id']} | {tools:<20} | {row['message'][:26]:<28} | {row['reply'][:44]}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
