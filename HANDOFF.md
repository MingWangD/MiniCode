# MiniCode 项目交接文档

更新时间：2026-08-18（Asia/Shanghai）

## 1. 交接目标

本项目用于跟随 `claude-code-from-scratch` 教程，从零手写一个 Python Coding Agent。

当前第五章“流式输出”和第六章“权限与安全”的最小教学实现已经完成。第五章的 Anthropic 异步流、完整消息恢复、fake tool loop 和真实 DeepSeek 流式请求均已验证；第六章的危险命令检查、执行前权限闸门和 fake 工具隔离均已验证。项目明确只兼容 Anthropic Messages API，教程中的 OpenAI 双后端部分主动跳过。

交互式 REPL 的中文删除残影问题已经修复，并通过用户真实终端测试和自动 PTY 边界回归。下一步按权威教程进入第七章“上下文管理”。

权威教程：

- 教程目录：<https://github.com/Windy3f3f3f3f/claude-code-from-scratch/tree/main/docs>
- 第四章：<https://github.com/Windy3f3f3f3f/claude-code-from-scratch/blob/main/docs/04-cli-session.md>
- 第五章：<https://github.com/Windy3f3f3f3f/claude-code-from-scratch/blob/main/docs/05-streaming.md>
- 第六章：<https://github.com/Windy3f3f3f3f/claude-code-from-scratch/blob/main/docs/06-permissions.md>
- 第七章：<https://github.com/Windy3f3f3f3f/claude-code-from-scratch/blob/main/docs/07-context.md>

本地项目：`/Users/myw/mini-coding-agent/MiniCode`

本地成品参考：`/Users/myw/mini-coding-agent/mini-claude-code`

成品项目只能用于解释和对照。章节范围、步骤顺序、当前阶段代码以 Windy 教程为准。

## 2. 用户协作偏好

- 使用中文讲解。
- 代码按小块逐步给出，先解释作用，等待用户确认后再进入下一步。
- 每个阶段最后再给完整代码，并带简要中文注释。
- 用户希望亲手写教程代码。除非用户明确授权“直接修改文件”，否则只给代码和说明，不直接改项目文件。
- 解释第三方库时，附官方文档地址。
- Python 关键词、类型名、API 名称，例如 `int`、`str`、`dict`、`async`、`await`，保持英文。
- 不提前实现未来章节的 memory、skill、sub-agent、MCP、Plan Mode 等功能。

## 3. 模型与 API 决策

项目全程使用 DeepSeek V4 Pro，但通过 Anthropic 兼容协议调用：

```bash
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_API_KEY="<在本机设置，不写入代码或文档>"
export MINI_MODEL="deepseek-v4-pro"
```

关键决定：

- SDK：`anthropic`
- 客户端：`anthropic.AsyncAnthropic()`
- 默认模型：`deepseek-v4-pro`
- 环境变量名称沿用 Anthropic SDK 约定：`ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`
- 不混用 OpenAI Chat Completions 消息格式
- 项目只实现 Anthropic Messages API；不添加 OpenAI SDK、消息转换或双后端选择逻辑
- 不把密钥写入仓库、代码、测试日志或交接文档

`.env` 已被 `.gitignore` 忽略。

## 4. 当前项目状态

Git：

- 分支：`main`
- 当前 HEAD：`b79fb7c`
- 工作区不是干净状态；以下修改属于用户，不要覆盖或回滚：

```text
M mini_claude/__main__.py
M mini_claude/agent.py
M mini_claude/tools.py
M mini_claude/ui.py
M pyproject.toml
M uv.lock
?? mini_claude/permissions.py
?? HANDOFF.md
```

当前主要文件：

```text
mini_claude/tools.py       已实现基础工具系统；之前复制的 production 权限辅助代码已按用户要求删除
mini_claude/prompt.py      已实现系统提示词
mini_claude/agent.py       已实现异步流式 Agent Loop 和执行前权限闸门
mini_claude/permissions.py 已实现第六章最小 allow/deny 权限检查
mini_claude/session.py     已实现第四章 JSON 会话保存/恢复
mini_claude/ui.py          已实现 Rich 终端 UI
mini_claude/__main__.py    已实现单次模式与交互式 REPL
pyproject.toml             包含 anthropic、rich 依赖
uv.lock                    已更新
```

以下文件目前为空，属于后续章节；不要把“为空”当作当前缺陷：

```text
mini_claude/autonomy.py
mini_claude/frontmatter.py
mini_claude/mcp_client.py
mini_claude/memory.py
mini_claude/skills.py
mini_claude/subagent.py
```

## 5. 第四章已完成内容

### `mini_claude/agent.py`

- 使用 `anthropic.AsyncAnthropic()`。
- 将用户消息加入历史。
- 调用模型时传入系统提示词、当前工具定义和完整消息历史。
- 保存完整 `reply.content`，不会丢失 `tool_use`。
- 找出同一响应里的所有 `tool_use`。
- 使用 `await execute_tool(...)` 执行工具。
- 使用 `tool_use_id` 构造对应的 `tool_result`。
- 将所有工具结果组合成一条 `user` 消息交回模型。
- 没有工具调用时结束当前 Agent Loop。
- 当前只开放基础工具；后续工具未提前接入。
- 第四章完成时仍为非流式响应；第五章现已改为异步流式响应。

### `mini_claude/session.py`

- 将消息历史保存到当前工作目录的 `.mini-session.json`。
- 使用 JSON 整体覆盖写入，符合第四章最小实现。
- 使用 `model_dump()` 兼容 Anthropic SDK 对象。
- 文件不存在、JSON 损坏或读取失败时返回 `None`。
- 保存失败静默忽略，避免磁盘问题直接中断对话。
- `.mini-session.json` 已被 `.gitignore` 忽略。

### `mini_claude/__main__.py`

- 检查 `ANTHROPIC_API_KEY`。
- 检查 `ANTHROPIC_BASE_URL`。
- 缺少必需环境变量时调用 `sys.exit(1)`，进程返回非零状态码。
- 支持命令行参数组成一次性 prompt。
- 支持交互式 REPL。
- 支持 `exit`、`quit`。
- 支持 `/clear`，清空后立即保存会话。
- 支持 `--resume` 恢复历史。
- 每次有效对话后保存历史。
- 支持 EOF 和基础 `KeyboardInterrupt` 退出。
- 预先加载 `readline`，由 `input(prompt)` 统一管理绿色提示符和输入缓冲区。
- 中文宽字符可以完整删除；删空后额外按 Delete 只触发终端响铃，不会擦除 `>>>`。

### `mini_claude/ui.py`

- 使用 Rich 管理终端输出。
- 从 `pyproject.toml` 读取版本号，当前版本 `0.1.0`。
- 欢迎标题为粉色。
- 像素画为粉色主体、两个黑色眼睛。
- 显示工具图标和参数摘要。
- 工具结果在 UI 层截断到 500 字符，但 Agent 历史保留完整结果。
- `print_error()`、`print_info()` 使用 `Text`，任意 `[/red]`、`[bold]` 等内容按普通文本显示，不再触发 Rich markup 解析异常。
- 退出信息目前只含一个换行、两个缩进空格，无尾随空格。

## 6. 第五章已完成内容

### 流式 Agent Loop

- `mini_claude/agent.py` 使用 `async with self.client.messages.stream(...)`。
- 使用 `async for text in stream.text_stream` 逐块输出文本。
- 使用 `await stream.get_final_message()` 恢复完整 `Message`。
- 完整 `reply.content` 继续写入历史，因此 `tool_use` 不会丢失。
- 原有 `tool_use -> execute_tool -> tool_result -> 下一轮模型请求` 数据流保持不变。

### 后端范围决定

- 只支持 Anthropic Messages API。
- 实际后端为 DeepSeek Anthropic 兼容端点，模型为 `deepseek-v4-pro`。
- 主动跳过教程中的 OpenAI 双后端实现。
- 不添加 `openai` 依赖、`AsyncOpenAI`、OpenAI 消息转换、`delta.tool_calls` 分片累积或后端切换逻辑。

### 第五章验证结果

离线 fake stream：

```text
纯文本分块输出：通过
最终完整 Message 恢复：通过
tool_use -> tool_result -> 第二轮流式文本：通过
完整四条消息历史：通过
```

真实 DeepSeek 请求：

```text
模型：deepseek-v4-pro
协议：Anthropic Messages API
进程退出码：0
收到文本 chunk：74
最终完整 assistant 消息：通过
结果：live stream test: OK
```

真实测试直接调用 `Agent.chat()`，未通过 CLI 保存会话，没有读取或输出 API Key。

## 7. 第六章已完成内容

### 最小权限模块

- 新增 `mini_claude/permissions.py`。
- 使用 6 条正则拦截 `rm -rf`、`git push`、`git reset --hard`、`sudo`、`mkfs` 和写入 `/dev/`。
- `check_permission(name, inp)` 对危险 `run_shell` 返回 `"deny"`，其余调用返回 `"allow"`。
- `tools.py` 中之前直接复制的 production 权限规则、模式和确认逻辑已按用户要求删除，保留基础工具系统。

### Agent 权限闸门

- `agent.py` 从 `.permissions` 导入 `check_permission`。
- 每次工具调用都在 `await execute_tool(...)` 前检查权限。
- 被拒绝的工具不会进入 `execute_tool(...)`，而是生成普通 `tool_result` 返回模型。
- 安全工具仍沿用原来的异步执行和读后写状态。

### 第六章验证结果

```text
全部 Python 模块编译：通过
6 条危险 Shell 规则：全部返回 deny
安全 Shell、非 Shell 工具和缺失 command：全部返回 allow
fake 危险工具：execute_tool 调用次数为 0
fake 安全工具：execute_tool 调用次数为 1
拒绝与成功结果的 tool_result 历史：通过
uv lock --check：通过
git diff --check：通过
```

测试未发送真实 API 请求，也未执行真实危险命令。

## 8. 已验证结果

最终静态检查：

```bash
uv run python -m py_compile \
  mini_claude/tools.py \
  mini_claude/prompt.py \
  mini_claude/permissions.py \
  mini_claude/agent.py \
  mini_claude/session.py \
  mini_claude/ui.py \
  mini_claude/__main__.py

uv lock --check
git diff --check
```

结果：全部通过。

最终针对性行为测试：

```text
Rich 特殊标记按普通文本输出：通过
错误消息缩进与尾随空格：通过
缺少 ANTHROPIC_API_KEY：退出状态码 1
缺少 ANTHROPIC_BASE_URL：退出状态码 1
输入 exit 正常退出：退出状态码 0
绿色输入提示符唯一显示：通过
中文宽字符逐字删除：通过
删空后额外 Delete 不擦除提示符：通过
```

本轮完整离线审查还验证过：

```text
UI 版本、像素、工具摘要、结果截断：通过
Session 保存、恢复、对象转换、损坏降级：通过
Agent 多工具循环、完整历史、UI 接入：通过
CLI 单次模式、REPL、/clear、--resume、EOF、exit、保存顺序：通过
```

第四章的 API 相关测试均使用虚拟配置。第五章后来完成了一次真实 DeepSeek 纯文本流式请求，结果见上一节。

## 9. 未验证和已知边界

- 真实 DeepSeek 纯文本流式请求已通过，但尚未让真实模型触发工具调用；工具链路仅使用 fake stream 验证。
- OpenAI 双后端按用户决定主动跳过，不属于待修缺陷。
- 当前没有自动重试、Extended Thinking、工具并行执行或流式工具早期启动；这些不是当前最小实现要求。
- 中文删除问题已修复：`mini_claude/__main__.py` 加载 `readline`，并把绿色 `>>>` 直接交给 `input(prompt)`，不再由 Rich 单独打印。
- 自动 PTY 回归验证两个中文字符分别按双列擦除，缓冲区为空后额外 Delete 只返回终端响铃；用户真实终端复测也通过。
- 当前输入修复已在 macOS Python 3.12 的 `libedit` 环境验证；Windows 或 GNU Readline 环境尚未验证。
- 当前只支持一次 Ctrl+C 直接退出，没有成品项目的“双 Ctrl+C”交互语义；不要在未读第五章和相关中断设计前提前补。
- 当前会话使用单个 JSON 文件，不是成品项目的 JSONL、多会话目录或会话 ID；这些不是第四章最小实现缺失。
- `pyproject.toml` 尚未定义 `[project.scripts]`，可靠启动命令仍是 `uv run python -m mini_claude`。
- 存在少量不影响运行的 PEP 8 风格项，例如 `style = "red"`、`encoding = "utf-8"`、部分顶层函数空行和注释空格。可单独整理，不要与第五章逻辑修改混在一起。
- 权威仓库的章节运行快照 `steps/dist/06-permissions/py/` 使用独立 `permissions.py`，最终 Python 源码 `python/mini_claude/` 则把完整权限系统合并在 `tools.py`。用户决定采用章节快照路线；`tools.py` 中之前直接复制的 production 权限代码已经删除，最小 `permissions.py` 已完成。
- 第六章目前是 6 条正则组成的教学黑名单，不是安全沙箱；变形命令、间接执行和未列出的危险命令可能绕过检查。production allow/deny 配置、权限模式、确认框和会话白名单尚未实现。
- 尚未让真实模型触发第六章权限拒绝；权限链路使用 pure function 和 fake stream 验证，避免执行真实危险命令。

## 10. 下一步建议

下一次对话建议这样开始：

1. 先读取本文件和当前工作区，不修改文件。
2. 在线阅读权威教程 `docs/07-context.md`，查看 Step 7 Python diff。
3. 先说明第七章的上下文压缩目标、需要修改的文件和第一小步代码，不提前复制 production 四层压缩系统。
4. 按章节快照新增最小 `context.py`，再在 Agent 调用模型前接入压缩。
5. 等第七章代码完全接入后统一测试，不在每个小块后运行测试。
7. 后续教程只实现 Anthropic 分支，忽略 OpenAI 双后端代码。
8. 按小块给代码和中文解释，每块等待用户确认。
9. 用户明确授权前，不直接修改业务代码。

可复制到新对话的开场提示：

```text
请先阅读 /Users/myw/mini-coding-agent/MiniCode/HANDOFF.md，并检查当前工作区。
项目第五章、第六章和中文输入修复已经完成，并决定只保留 Anthropic 后端。请先阅读 HANDOFF.md，按 Windy 权威教程开始第七章“上下文管理”。先说明目标、修改文件和第一小步代码；代码分块逐行讲解，每一步等我确认，等整章代码接入后再统一测试。
```

## 11. 建议技能

- `teach`：按教程分块讲解并等待确认。
- `context7-mcp`：查询 Anthropic SDK、Rich 或其他第三方库的当前官方文档。
- `diagnosing-bugs`：流式响应、事件类型或中断流程出现实际失败时使用。
- `handoff-documentation`：每章完成后更新本文件。

## 12. 安全提醒

- 不要在对话、文档、代码、测试输出或 Git 中粘贴真实 API Key。
- 不要读取或展示 `.env` 内容，除非用户明确授权并确有必要。
- 不要回滚当前未提交修改。
- 不要把本地成品项目的后续功能直接复制进当前学习阶段。
