# 小满商城 · 电商智能客服 Agent

一个可以直接运行的 LLM 智能客服 Demo：支持**商品咨询、订单查询、售后办理、店铺政策问答**，覆盖
**Function Calling（工具调用）、RAG 向量检索、多轮会话记忆、LLM Evaluation、单元测试**。

> 没有 API Key 也能跑：未配置 Key 时自动进入 **Mock 模式**，完整走一遍「模型决策 → 调用工具 → 生成回答」的链路。

## 📊 成果速览（面试先看这里）

| 指标 | 结果 | 说明 |
|---|---|---|
| LLM 评测通过率 | **35/35 · 100%** | 真实 API 模式（qwen 系列）跑通，非 Mock 自测 |
| 工具选择准确率 | **100%** | 5 个工具，含边界 / 多轮 / 拒答场景 |
| 安全护栏拦截率 | **5/5 · 100%** | 提示注入、系统提示套取、越权查单全部拦截 |
| 单元测试 | **19 项全通过** | pytest |
| 知识库 / 业务数据 | 12 条知识 + 9 商品 + 14 订单 + 10 售后工单 | MySQL 与 JSON 双数据源 |
| 平均响应耗时 | 约 6.2 秒 / 次 | 真实 LLM 多轮工具调用（Mock 模式毫秒级） |

评测集共 35 条，覆盖 5 类场景：**功能 17 · 边界 6 · 多轮 4 · 拒答 3 · 越权 5**。
完整明细见 [`eval/report.json`](eval/report.json)，评测方法见 [第 10 节](#10-llm-evaluation)。

> **亮点**：测试集可在聊天界面里边用边攒——每条回复下方点「+ 存为测试用例」，即可把当前对话沉淀为可回归的用例（见 [第 5 节](#5-使用示例)）。

---

## 1. 功能清单（与简历项目描述一一对应）

| 简历里的描述 | 本项目中的实现 |
|---|---|
| 基于大语言模型（LLM）的智能客服 Agent，多轮对话 | `app/agent.py` 工具调用循环 + `app/memory.py` 会话记忆 |
| 提示词工程（Prompt Engineering） | `app/agent.py` 中的 `SYSTEM_PROMPT`：角色、工具使用规则、追问策略、转人工兜底 |
| 工具调用（Tool Use / Function Calling） | `app/tools.py`：4 个工具 + OpenAI 兼容的 JSON Schema |
| 商品咨询、订单查询、售后引导 | `search_products` / `get_order` / `create_after_sales` |
| RAG 向量检索 | `app/rag.py`：12 条知识库文档 → 向量化 → 余弦相似度 Top-K |
| 记忆管理与会话上下文编排 | 按 `session_id` 保存最近 20 条消息；可切换 Redis |
| FastAPI 封装后端接口 | `app/main.py`：`/api/chat`、`/api/health`、`/api/sessions/{id}/reset` |
| 可量化的 LLM Evaluation 评估标准 | `eval/cases.json` **35 条**测试用例（功能/边界/多轮/拒答/越权）+ `eval/run_eval.py` 5 个指标 |
| 对话即用例：界面沉淀测试用例 | `POST /api/eval/cases` + 前端每条回复「存为测试用例」按钮 |
| 输入安全护栏（Guardrail） | `app/guard.py`：拦截提示注入 / 套取系统提示 / 越权查单，命中不调工具 |
| 单元测试与持续迭代 | `tests/` 下 19 个 pytest 用例 |

---

## 2. 技术栈

- 后端：Python 3.10+、FastAPI、Pydantic、httpx（直接请求 OpenAI 兼容接口）
- 前端：原生 HTML + CSS + JavaScript（无需构建工具）
- 测试：pytest
- 数据库：MySQL 8.0（PyMySQL 驱动）——商品 / 订单 / 售后工单 / 知识库
- 存储：默认进程内内存 / 本地向量库；可选 Redis、远程 Embedding API；MySQL 不可用时自动回退到本地 JSON

---

## 3. 目录结构

```
shop-agent/
├─ app/
│  ├─ main.py          # FastAPI 入口：页面 + 三个接口
│  ├─ agent.py         # Agent 核心：多轮对话 + 工具调用循环
│  ├─ llm.py           # LLM 客户端（OpenAI 兼容）+ Mock 实现
│  ├─ tools.py         # 4 个工具的实现与 JSON Schema
│  ├─ rag.py           # 知识库向量化与检索
│  ├─ memory.py        # 会话记忆（内存 / Redis）
│  ├─ db.py            # MySQL 数据访问层（带 JSON 回退）
│  ├─ mysql_config.py  # MySQL 连接配置
│  ├─ config.py        # 环境变量配置
│  └─ schemas.py       # 请求 / 响应模型
├─ db/
│  └─ init_db.py       # 建库建表 + 从 JSON 导入示例数据（幂等）
├─ data/
│  ├─ products.json    # 商品数据（9 条）
│  ├─ orders.json      # 订单数据（5 条）
│  └─ kb.json          # 客服知识库（12 条）
├─ static/index.html   # 聊天页面
├─ eval/
│  ├─ cases.json       # 评测用例
│  ├─ run_eval.py      # 评测脚本
│  └─ report.json      # 运行后生成
├─ tests/              # 19 个单元测试
├─ docs/开发者讲解.md   # 面试讲解手册
├─ check_llm.py        # 阿里云百炼连通性 / 工具调用自检
├─ setup_key.py        # 交互式写入 .env（配置阿里云.bat 调用它）
├─ requirements.txt
├─ .env.example / .env # 配置（.env 存你的 Key，已 gitignore）
├─ 配置阿里云.bat       # 双击填 Key + 自检
├─ 启动.bat / start.bat # 两个内容完全一致，各自独立，双击任一即可
├─ start.sh            # macOS / Linux 用
└─ README.md
```

---

## 4. 快速开始

> 项目位置：`E:\shop-agent`（所有代码、数据、依赖、虚拟环境都在这个目录内，不往 C 盘写任何东西）

### 4.1 创建虚拟环境并安装依赖

依赖装在项目自带的 `.venv` 里，不污染系统 Python：

```bash
cd E:\shop-agent
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> 想连 pip 缓存也留在 E 盘，先执行 `set PIP_CACHE_DIR=E:\shop-agent\.pip-cache` 再安装。

### 4.2 接入真实大模型（阿里云百炼）

> 项目默认用**阿里云百炼（DashScope）** 的 OpenAI 兼容接口，模型 `qwen-plus`。
> 不填 Key 时自动回落到 Mock 模式，功能照样能演示。

**第 1 步：拿 Key**

1. 打开 <https://bailian.console.aliyun.com>，用阿里云账号登录；
2. 首次使用先**开通「百炼大模型服务」**（新用户一般有免费额度）；
3. 右上角 **API-KEY** → 创建 / 查看，复制 `sk-` 开头的 Key。

**第 2 步：填进项目（两种方式任选）**

- **双击 `配置阿里云.bat`**：粘贴 Key 回车，脚本自动写 `.env` 并立刻自检；
- 或者手动编辑 `.env`：

```dotenv
LLM_API_KEY=sk-你的key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

> 模型可选 `qwen-plus`（均衡，推荐）/ `qwen-max`（效果最好）/ `qwen-turbo`（最快最便宜），
> 三者都支持 Function Calling，改 `LLM_MODEL` 一行即可切换。

**第 3 步：自检（推荐，30 秒看清问题出在哪）**

```bash
cd E:\shop-agent
.venv\Scripts\python.exe check_llm.py
```

依次检查：配置是否读到 → Key 与网络（`401` Key 错、`403` 未开通或欠费、`404` Base URL 写错）→
模型是否真的会发起工具调用 → 跑一遍 Agent 端到端并打印 token 用量与耗时。

**换其他厂商**：把 `LLM_BASE_URL` / `LLM_MODEL` 换成任意 OpenAI 兼容服务即可，例如
DeepSeek `https://api.deepseek.com/v1` + `deepseek-chat`，OpenAI `https://api.openai.com/v1` + `gpt-4o-mini`。

### 4.3 启动服务

**双击 `启动.bat`**（或 `start.bat`，两个文件内容完全一致、各自独立，互不调用）。

脚本会检查 8000 端口和 `.venv`，然后启动服务；**运行期间那个黑窗口就是服务器，不要关**。
停止服务：在窗口里按 `Ctrl+C`，或直接关掉窗口。

手动启动：

```bash
cd E:\shop-agent
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- 聊天页面：<http://127.0.0.1:8000>
- 接口文档：<http://127.0.0.1:8000/docs>

### 4.4 运行测试与评测

```bash
cd E:\shop-agent
.venv\Scripts\python.exe -m pytest -q      # 19 个单元测试
.venv\Scripts\python.exe eval/run_eval.py  # 35 条评测用例，结果写入 eval/report.json
```

### 4.5 接入 MySQL（可选，默认已配好）

本机 MySQL（root / 123456，端口 3306）已初始化完成，`.env` 里 `MYSQL_ENABLED=1`，
启动后工具会自动从 MySQL 读写。换机器或想重新初始化时：

```bash
# 1) 确认 .env 里的 MySQL 连接参数正确
# 2) 建库建表 + 导入示例数据（幂等，可重复执行）
.venv\Scripts\python.exe db\init_db.py
# 3) 验证读写
.venv\Scripts\python.exe tests\mysql_integration_check.py
```

健康检查里能看到数据源状态：

```json
{"status":"ok","data_source":"mysql","mysql_connected":true,"kb_size":12}
```

> 把 `MYSQL_ENABLED=0` 即可切回本地 JSON；MySQL 连不上时也会自动回退，不影响演示。

---

## 5. 使用示例

页面里可以直接点快捷问题，也可以手动输入：

| 用户输入 | Agent 行为 |
|---|---|
| 有没有降噪耳机推荐？ | 调 `search_products`，返回匹配商品 |
| 2000 元以内的手机有哪些？ | 调 `search_products`，自动识别价格上限 |
| 订单 SO20261114002 到哪了 | 调 `get_order`，返回状态与物流 |
| 订单 SO20261112001 耳机有杂音，想退货 | 调 `create_after_sales`，生成售后工单 |
| 你们满多少包邮？ | 调 `search_faq`，从知识库召回运费规则 |
| 可以开发票吗？ | 调 `search_faq`，返回发票说明 |

等价的 curl 调用：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "订单 SO20261114002 到哪了"}'
```

返回：

```json
{
  "session_id": "0c05e495...",
  "reply": "订单 SO20261114002 当前状态为「运输中」……",
  "tool_calls": [
    {"name": "get_order", "arguments": {"order_id": "SO20261114002"}, "result": {"found": true, "...": "..."}}
  ],
  "usage": {"prompt_tokens": 512, "completion_tokens": 48, "total_tokens": 560},
  "latency_ms": 1280
}
```

### 把对话存成测试用例（界面沉淀）

在聊天页每条客服回复的下方有个 **「+ 存为测试用例」** 按钮：

1. 正常提问，得到客服回答；
2. 点该回答下方的「+ 存为测试用例」，展开一个小表单；
3. 用户问题会自动填入，选择**期望工具**和**场景分类**（功能/边界/多轮/拒答/越权），填期望关键词；
4. 点「保存」，即写入 `eval/cases.json`，返回新用例编号（如 `E11`）。

等价的 curl：

```bash
curl -X POST http://127.0.0.1:8000/api/eval/cases \
  -H "Content-Type: application/json" \
  -d '{"message":"订单 SO20261114002 到哪了","expect_tool":"get_order","expect_keywords":["运输中"],"category":"功能"}'
```

查看当前用例库：`GET /api/eval/cases`。这些用例下次跑 `python eval/run_eval.py` 时会自动纳入回归。

---

## 6. 内部逻辑：一次请求到底发生了什么

```
浏览器
  │  POST /api/chat  {session_id, message}
  ▼
FastAPI（app/main.py）
  │  校验参数，生成 / 复用 session_id
  ▼
Agent.chat（app/agent.py）
  │  1. memory.get(session_id) 取出历史
  │  2. 拼 messages = system + history + 本轮 user
  ▼
LLM（app/llm.py，OpenAI 兼容 /chat/completions）
  │  3. 带着 tools 定义请求模型
  │  4. 模型返回 tool_calls（例如 get_order）
  ▼
工具执行（app/tools.py）
  │  5. 本地函数查 orders.json / products.json / 知识库
  │  6. 结果以 role=tool 追加回 messages
  ▼
再次请求 LLM
  │  7. 模型基于工具结果生成最终自然语言回答
  ▼
Agent 把 user / assistant 消息写回 memory
  │
  ▼
返回 {reply, tool_calls, usage, latency_ms}
```

关键点：

1. **模型不直接查数据**：它只负责「决定调哪个工具、传什么参数」，真实数据由本地工具返回，避免编造。
2. **工具调用是循环**：一轮可能调多个工具，也可以连续两轮；`MAX_TOOL_ROUNDS` 限制最大轮数，防止死循环。
3. **只把最终消息写进记忆**：工具中间结果不落库，避免上下文膨胀和污染。
4. **响应里回传 `tool_calls`**：前端可以展开查看「模型调了什么、参数是什么、返回了什么」，方便调试和演示。

---

## 7. 四个工具

| 工具 | 入参 | 返回 | 作用 |
|---|---|---|---|
| `search_products` | `query`、`category`、`max_price` | 商品列表 | 商品咨询与推荐 |
| `get_order` | `order_id` | 订单状态、物流、金额 | 订单查询 |
| `create_after_sales` | `order_id`、`reason` | 工单号、状态、下一步 | 退货 / 换货 / 维修 |
| `search_faq` | `query` | Top-3 知识库片段 | 政策问答（RAG） |

工具的 JSON Schema 定义在 `app/tools.py` 的 `TOOLS` 中，执行逻辑在 `TOOL_IMPL` 中。新增工具只需要两步：写函数 + 加一条 schema。

---

## 8. RAG 是怎么做的

1. **知识库**：`data/kb.json`，12 条客服规则（退换货、运费、发票、保修、优惠券等）。
2. **向量化**：默认使用内置的**字符二元组哈希向量**（512 维，L2 归一化），零依赖、离线可用；
   配置 `EMBED_MODEL` 后自动改用远程 Embedding API，失败时静默回退。
3. **检索**：查询向量与每条文档向量做余弦相似度，取 Top-3。
4. **注入方式**：通过 `search_faq` 工具返回给模型，由模型组织成自然语言回答。

为什么不用 pgvector / Milvus？当前是教学 / 演示项目，本地向量库可以在**不装数据库**的前提下跑通完整链路。
`KnowledgeBase` 已经把「向量化」和「检索」拆开，生产环境只需替换存储层（见第 11 节）。

---

## 9. 记忆管理

- 以 `session_id` 为 key，保存 `user` / `assistant` 的最终消息；
- 只保留最近 `MAX_HISTORY=20` 条，控制 token 成本；
- 默认存进程内字典，配置 `REDIS_URL` 后自动切换 Redis，支持多进程 / 多实例共享；
- 点「新会话」或调用 `POST /api/session/{id}/reset` 可清空。

---

## 10. LLM Evaluation

评测脚本会为每条用例开一个独立会话（多轮用例先用 `history` 注入上下文），跑完 Agent 后计算：

| 指标 | 含义 |
|---|---|
| `tool_accuracy` | 期望的工具是否被调用（工具选择是否正确） |
| `keyword_hit_rate` | 回答是否包含期望关键词（事实是否正确） |
| `guard_accuracy` | 越权 / 注入用例是否被安全护栏正确拦截 |
| `pass_rate` | 工具正确 **且** 关键词命中 |
| `avg_latency_ms` | 平均响应耗时 |

**35 条用例覆盖 5 类场景**：功能 17（商品 / 订单 / 售后 / 政策）、边界 6（缺参数、不存在订单、模糊问法）、
多轮 4（上下文承接、指代消解）、拒答 3（非业务问题）、越权 5（提示注入、套取系统提示、查他人订单）。

真实 API 模式（qwen 系列）结果：

```
模式: api | 用例: 35 | 通过: 35 | 通过率: 100% | 工具准确率: 100% |
关键词命中: 100% | 护栏拦截: 100%(5/5) | 平均耗时: 6214ms
```

```
  功能: 17/17 (100%)   边界: 6/6 (100%)   多轮: 4/4 (100%)
  拒答: 3/3 (100%)     越权: 5/5 (100%)
```

Mock 模式同样 35/35 全通过（毫秒级）；详细结果见 `eval/report.json`。

**对话界面沉淀用例**：在聊天页每条客服回复下方点「+ 存为测试用例」，填写期望工具 / 关键词 / 场景分类，
即通过 `POST /api/eval/cases` 追加到 `eval/cases.json`（标记 `source: "ui"`），下次跑评测自动纳入。

> 面试时可以说：评测集不是只测「答对没」，而是拆成「工具选择准不准 / 回答事实对不对 / 安全护栏拦不拦」三层，
> 并覆盖边界、多轮、拒答、越权这些真实线上最容易出问题的场景；用例库支持在对话界面里边用边攒，形成回归资产。

---

## 11. 生产化改造（从 Demo 到线上）

| 方向 | 当前实现 | 生产建议 |
|---|---|---|
| 会话存储 | 进程内字典 / 可选 Redis | Redis 集群 + TTL |
| 向量库 | 本地向量 + 余弦 | pgvector / Milvus，替换 `KnowledgeBase` 存储层 |
| 流式输出 | 一次性返回 | SSE / WebSocket 流式 |
| 鉴权 | 无 | 网关鉴权 + 用户身份注入 |
| 限流 | 无 | 按用户 / IP 限流，防刷 |
| 可观测性 | 返回 tool_calls、latency | 结构化日志 + Trace ID + 指标看板 |
| Prompt 管理 | 代码常量 | Prompt 版本化 + A/B 实验 |
| 安全 | 工具参数校验 | 输入输出审核、敏感词、越权校验 |

---

## 12. 常见问题

**Q：双击 .bat 一闪就没了？**
先确认 `启动.bat` / `start.bat` 还在（这两个文件互不依赖，但都必须在项目根目录）。
现在的脚本每条退出分支都以 `pause` 结尾，正常不会闪退；如果还闪，说明文件被移动或杀毒软件拦截了。
也可以在 cmd 里手动跑一次看报错：

```bash
cd /d E:\shop-agent
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**Q：没有 API Key 能跑吗？**
能。未配置 Key 时自动 Mock 模式，工具调用、记忆、评测、测试全部可用。

**Q：报 401 / 403 / 404？**
- `401`：Key 填错、已删除，或 `.env` 里 `LLM_API_KEY=` 后面是空的；
- `403`：还没开通「百炼大模型服务」，或账户欠费 —— 去 <https://bailian.console.aliyun.com> 处理；
- `404`：`LLM_BASE_URL` 写错，阿里云必须是 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

先跑 `.venv\Scripts\python.exe check_llm.py`，它会直接指出是哪一层的问题。

**Q：模型不调用工具？**
确认模型支持 function calling（`qwen-plus` / `qwen-max` / `qwen-turbo` 都支持）；部分小模型需要显式 `tool_choice`。

**Q：端口被占用？**
换端口：`python -m uvicorn app.main:app --port 8001`。

**Q：为什么不用 LangChain？**
核心就是「带 tools 的 chat completions + 循环执行工具」，手写一遍依赖更少、链路更透明，便于定位问题。
需要时可以无缝换成 LangChain 的 `create_tool_calling_agent`，工具定义可以直接复用。

---

## 13. 开发者讲解

想把这个项目讲清楚（开发流程、使用方法、内部逻辑、面试追问），看 [`docs/开发者讲解.md`](docs/开发者讲解.md)。

---

## 14. MySQL 数据库设计

### 表结构

库名 `xiaoman_shop`，四张表：

| 表 | 字段 | 说明 |
|---|---|---|
| `products` | product_id(PK), name, category, price, stock, tags, description | 商品，9 条 |
| `orders` | order_id(PK), product_id, product_name, status, amount, logistics, created_at, address | 订单，5 条 |
| `kb_articles` | id(PK), title, content, tags | RAG 知识库，12 条 |
| `after_sales_tickets` | ticket_id(PK), order_id, product_name, reason, status, created_at | 售后工单，运行时写入 |

### 数据访问设计（`app/db.py`）

- **开关控制**：`MYSQL_ENABLED=1` 才连库；`0` 直接用 JSON。
- **优雅降级**：每个查询包了 try/except，MySQL 连不上时返回 `None`，工具层据此回退到 `data/*.json`——**没装 MySQL 的机器也能完整演示**。
- **实时读库**：`search_products` / `get_order` / `search_faq` 每次调用都查 MySQL，不是启动时加载。所以**直接改数据库，客服立刻读到新数据**（面试可现场演示）。
- **写库**：`create_after_sales` 把工单 INSERT 进 `after_sales_tickets`，失败则回退内存字典。
- **类型处理**：DECIMAL → float、DATETIME → 字符串，避免 FastAPI 序列化报错。

### 初始化脚本（`db/init_db.py`）

幂等：先 `DROP TABLE IF EXISTS` 再建表，从 `data/*.json` 导入，可重复执行。
连接参数从 `.env` 读，密码不写死在代码里（`.env` 已 gitignore）。

### 面试怎么讲

> 「业务数据没有硬编码在代码里，而是存在 MySQL。我封装了一层数据访问层，用环境变量开关控制数据源，并做了降级设计——数据库不可用时自动回退本地 JSON，保证 Demo 永远能跑。商品和订单是实时查询，所以运营在后台改了数据，客服的回答会立刻跟着变。写操作像创建售后工单会落库，方便后续追踪。」

一句话带出：**分层解耦、配置开关、容错降级、实时性、持久化**，五个点。
