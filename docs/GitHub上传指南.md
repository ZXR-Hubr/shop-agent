# 怎么把 E:\shop-agent 连到 GitHub

## 当前状态（已帮你做好的）

- 项目目录：`E:\shop-agent`
- 已执行 `git init`，`git add -A` 已把要上传的文件全部暂存
- `.env` 已被 `.gitignore` 排除，**你的阿里云 API Key 不会被上传**
- `.venv`、`pip-cache`、`.idea`、`eval/report.json` 也已排除
- 本机 Git 已安装（2.55），但**没有登录 GitHub**：没有 `gh` 命令，也没有配置任何凭据

## 网络情况（实测）

| 地址 | 结果 |
|---|---|
| `https://api.github.com` | HTTP 200，可用 |
| `https://github.com`（网页 / git push） | 代理返回 502，直连超时 |

所以标准 `git push` 在当前网络下大概率失败；**用 GitHub API 上传可行**。下面两种方法任选。

---

## 方法一：你在浏览器建仓库，我帮你上传（推荐）

### 第 1 步：创建仓库

1. 打开 <https://github.com>，登录（没有账号就先注册）
2. 右上角 `+` → **New repository**
3. 填写：
   - Repository name：`shop-agent`
   - Description：`LLM 电商智能客服 Agent：Function Calling / RAG / Evaluation（FastAPI + Qwen）`
   - 选 **Private**（推荐）；以后要放进简历再改 Public
   - **不要**勾选 Add a README / .gitignore / license（项目里已经有了，避免冲突）
4. 点 **Create repository**，仓库先空着，不用管它给的命令

### 第 2 步：生成访问令牌（PAT）

1. 右上角头像 → **Settings** → 左侧最下 **Developer settings**
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
3. Note 填 `shop-agent-upload`，Expiration 选 30 天
4. 权限只勾 **`repo`** 这一项（展开后所有子项会自动勾上）
5. **Generate token** → 复制 `ghp_` 开头的字符串（**只显示一次**）

> fine-grained token 也可以：Repository access 选刚才建的仓库，Permissions 里给 `Contents: Read and write`、`Metadata: Read-only`。

### 第 3 步：把用户名和 Token 发给我

我会用 `api.github.com` 创建/上传仓库内容，不用你执行 `git push`。
Token 只用于这次上传，不会写进项目文件。

---

## 方法二：自己在本地 push（网络正常时可用）

先生成仓库和 PAT（同上），然后在 CMD 里执行：

```bat
cd /d E:\shop-agent
git config user.name "你的GitHub用户名"
git config user.email "你的GitHub注册邮箱"
git commit -m "Initial commit: LLM customer service agent"
git branch -M main
git remote add origin https://github.com/你的用户名/shop-agent.git
git push -u origin main
```

弹出登录框时：
- Username：你的 GitHub 用户名
- Password：**粘贴 PAT**（不是 GitHub 登录密码）

如果 `git push` 报 `CONNECT tunnel failed, 502` 或超时，是网络问题，不是代码问题 —— 改用方法一。

---

## 上传后怎么确认没泄密

推送完成后，在 GitHub 仓库页面检查：
- 根目录**没有 `.env`**
- `.env.example` 里 `LLM_API_KEY=` 是空的
- 没有 `.venv/`、`.pip-cache/` 等目录

本地也可以先验证（现在就能跑）：

```bash
cd /d E:\shop-agent
git diff --cached --name-only
```

这份列表里不应该出现 `.env`。

---

## 小提示

- 中文文件名（启动.bat、docs/开发者讲解.md）在 Git/GitHub 上显示正常，不用担心乱码
- 简历里贴仓库链接时，用 `Private` 仓库的话面试官看不到，展示前记得改成 `Public`
- 每次改完代码：
  ```bash
  git add -A
  git commit -m "说明这次改了什么"
  git push
  ```
