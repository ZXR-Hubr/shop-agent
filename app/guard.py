"""轻量输入安全护栏（Guardrail）。

目的：拦截两类高风险输入，让「拒答 / 越权」场景可被真实评测：
1. 提示注入 / 越权指令：试图改变角色、获取系统提示、绕过规则；
2. 隐私越权：要求查询他人订单 / 全部用户数据。

设计原则：只拦截高置信度模式，宁可漏拦也不误伤正常咨询；
命中后由 Agent 直接返回拒答话术，不调用任何工具（可在评测中断言 tool_calls 为空）。
"""
import re

# 系统提示词套取 / 角色劫持 / 指令覆盖
_INJECTION_PATTERNS = [
    r"忽略.{0,8}(之前|上面|以上|所有|前面).{0,8}(指令|提示|要求|设定|规则)",
    r"(告诉|输出|重复|打印|泄露|show|print).{0,12}(系统提示|system\s*prompt|你的指令|隐藏指令)",
    r"你现在是|假装你是|扮演.{0,10}(管理员|开发者|debug|工程师)",
    r"无视.{0,8}(规则|限制|设定)",
    r"jailbreak|DAN\s*模式",
]

# 隐私 / 越权：查询他人或批量数据
_PRIVACY_PATTERNS = [
    r"(所有|全部|列出|导出|给我|查一下).{0,10}(客户|用户|会员).{0,8}(订单|信息|资料|电话|地址|列表)",
    r"(别人|他人|其他人|随便一个|陌生人的).{0,4}(的)?订单",
    r"绕过.{0,6}(验证|登录|权限|身份|鉴权)",
]

REFUSAL_INJECTION = (
    "抱歉，这类指令我不能执行。我是小满商城的智能客服，只能帮您处理商品咨询、"
    "订单查询和售后问题。如果有相关需求，我很乐意为您服务。"
)
REFUSAL_PRIVACY = (
    "出于账户安全考虑，我只能查询与您本人相关的订单信息，无法提供他人订单或批量客户数据。"
    "如果您需要查询自己的订单，请提供订单号；其他问题也可以随时问我。"
)


def check(message: str) -> str | None:
    """返回拒答话术表示拦截；返回 None 表示放行。"""
    text = message.strip()
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return REFUSAL_INJECTION
    for pattern in _PRIVACY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return REFUSAL_PRIVACY
    return None
