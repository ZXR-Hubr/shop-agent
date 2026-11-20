"""LLM Evaluation：用固定测试集跑一遍 Agent，计算可量化指标。

测试集 eval/cases.json 覆盖 5 类场景（category 字段）：
- 功能：正常商品/订单/售后/政策问答
- 边界：缺参数、不存在的订单、模糊问法
- 多轮：带 history，验证上下文承接与指代消解
- 拒答：非业务问题、身份询问
- 越权：提示注入、套取系统提示、查询他人/批量数据（应被护栏拦截）

指标：
- tool_accuracy       期望工具是否被调用（工具选择是否正确）
- keyword_hit_rate    回答是否覆盖期望关键词（事实是否正确）
- guard_accuracy      越权/注入用例是否被正确拦截
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
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import Agent  # noqa: E402
from app.config import settings  # noqa: E402
from app.llm import LLMClient  # noqa: E402
from app.memory import SessionStore  # noqa: E402

CASE_FILE = Path(__file__).resolve().parent / "cases.json"
CASES = json.loads(CASE_FILE.read_text(encoding="utf-8"))


def check_keywords(reply: str, case: dict) -> bool:
    keywords = case.get("expect_keywords", [])
    if not keywords:
        return True
    if case.get("expect_keywords_any"):
        return any(k in reply for k in keywords)
    return all(k in reply for k in keywords)


async def run() -> int:
    agent = Agent(LLMClient(), SessionStore())
    rows = []
    latencies = []

    for case in CASES:
        session_id = f"eval-{case['id']}"

        # 多轮：把 history 按 user / assistant 交替注入会话记忆（不额外调 LLM）
        history = case.get("history", [])
        for i, h in enumerate(history):
            role = "user" if i % 2 == 0 else "assistant"
            await agent.memory.append(session_id, role, h)

        started = time.perf_counter()
        result = await agent.chat(session_id, case["message"])
        latency = int((time.perf_counter() - started) * 1000)
        latencies.append(latency)

        called_tools = [item["name"] for item in result["tool_calls"]]
        expected = case.get("expect_tool")
        blocked = bool(case.get("blocked"))
        was_blocked = bool(result.get("blocked"))

        if blocked:
            tool_ok = was_blocked and not called_tools
        elif expected is None:
            tool_ok = not called_tools
        else:
            tool_ok = expected in called_tools

        keyword_ok = check_keywords(result["reply"], case)
        passed = tool_ok and keyword_ok

        rows.append({
            **case,
            "called_tools": called_tools,
            "blocked_by_guard": was_blocked,
            "reply": result["reply"],
            "latency_ms": latency,
            "tool_ok": tool_ok,
            "keyword_ok": keyword_ok,
            "pass": passed,
        })

    total = len(rows)
    passed = sum(row["pass"] for row in rows)
    guard_cases = [r for r in rows if r.get("blocked")]
    guard_ok = sum(r["pass"] for r in guard_cases)

    # 分类统计
    by_cat = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in rows:
        cat = r.get("category", "其他")
        by_cat[cat]["total"] += 1
        by_cat[cat]["passed"] += int(r["pass"])

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "mock" if settings.llm_mock else "api",
        "model": "mock" if settings.llm_mock else settings.llm_model,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4),
        "tool_accuracy": round(sum(r["tool_ok"] for r in rows) / total, 4),
        "keyword_hit_rate": round(sum(r["keyword_ok"] for r in rows) / total, 4),
        "guard_accuracy": round(guard_ok / len(guard_cases), 4) if guard_cases else None,
        "guard_total": len(guard_cases),
        "avg_latency_ms": round(statistics.mean(latencies), 1),
        "by_category": {
            cat: {**v, "pass_rate": round(v["passed"] / v["total"], 4)}
            for cat, v in by_cat.items()
        },
        "cases": rows,
    }

    out = Path(__file__).resolve().parent / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"模式: {report['mode']} | 用例: {total} | 通过: {passed} | "
        f"通过率: {report['pass_rate']:.0%} | 工具准确率: {report['tool_accuracy']:.0%} | "
        f"关键词命中: {report['keyword_hit_rate']:.0%} | "
        f"护栏拦截: {report['guard_accuracy']:.0%}({guard_ok}/{len(guard_cases)}) | "
        f"平均耗时: {report['avg_latency_ms']}ms"
    )
    print("-" * 110)
    for r in rows:
        status = "PASS" if r["pass"] else "FAIL"
        tools = ",".join(r["called_tools"]) or "-"
        cat = r.get("category", "其他")
        print(f"{status} {r['id']} [{cat:<2}] | {tools:<20} | {r['message'][:24]:<26} | {r['reply'][:40]}")
    print("-" * 110)
    for cat, v in report["by_category"].items():
        print(f"  {cat}: {v['passed']}/{v['total']} ({v['pass_rate']:.0%})")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
