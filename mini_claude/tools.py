"""工具定义与执行：提供 10 种工具。
工具系统参考 Claude Code 公开的设计，包括 read_file、write_file、edit_file、
list_files、grep_search、run_shell、skill、enter/exit_plan_mode 和 agent。
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# from .memory import get_memory_dir
# from .frontmatter import parse_frontmatter

# 并发安全工具可并行执行（只读且无副作用）
CONCURRENCY_SAFE_TOOLS = {"read_file", "list_files", "grep_search", "web_fetch"}

IS_WIN = sys.platform == "win32"

# ─── 类型别名 ──────────────────────────────────────────────

ToolDef = dict  # Anthropic 工具模式字典

# ─── 工具定义 ───────────────────────────────────────

tool_definitions: list[ToolDef] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Returns the file content with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "The path to the file to read"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "The path to the file to write"},
                "content": {"type": "string", "description": "The content to write to the file"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Edit a file by replacing an exact string match with new content. The old_string must match exactly (including whitespace and indentation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "The path to the file to edit"},
                "old_string": {"type": "string", "description": "The exact string to find and replace"},
                "new_string": {"type": "string", "description": "The string to replace it with"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    {
        "name": "list_files",
        "description": "List files matching a glob pattern. Returns matching file paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": 'Glob pattern to match files (e.g., "**/*.ts", "src/**/*")'},
                "path": {"type": "string", "description": "Base directory to search from. Defaults to current directory."},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep_search",
        "description": "Search for a pattern in files. Returns matching lines with file paths and line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "The regex pattern to search for"},
                "path": {"type": "string", "description": "Directory or file to search in. Defaults to current directory."},
                "include": {"type": "string", "description": 'File glob pattern to include (e.g., "*.ts", "*.py")'},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_shell",
        "description": "Execute a shell command and return its output. Use this for running tests, installing packages, git operations, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "timeout": {"type": "number", "description": "Timeout in milliseconds (default: 30000)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "skill",
        "description": "Invoke a registered skill by name. Skills are prompt templates loaded from .claude/skills/. Returns the skill's resolved prompt to follow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "The name of the skill to invoke"},
                "args": {"type": "string", "description": "Optional arguments to pass to the skill"},
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch a URL and return its content as text. For HTML pages, tags are stripped to return readable text. For JSON/text responses, content is returned directly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"},
                "max_length": {"type": "number", "description": "Maximum content length in characters (default 50000)"},
            },
            "required": ["url"],
        },
    },

    # ─── 延迟加载工具 ───
    {
        "name": "enter_plan_mode",
        "description": "Enter plan mode to switch to a read-only planning phase. In plan mode, you can only read files and write to the plan file.",
        "input_schema": {"type": "object", "properties": {}},
        "deferred": True,
    },
    {
        "name": "exit_plan_mode",
        "description": "Exit plan mode after you have finished writing your plan to the plan file.",
        "input_schema": {"type": "object", "properties": {}},
        "deferred": True,
    },
    {
        "name": "agent",
        "description": "Launch a sub-agent to handle a task autonomously. Sub-agents have isolated context and return their result. Types: 'explore' (read-only), 'plan' (read-only, structured planning), 'general' (full tools).",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Short (3-5 word) description of the sub-agent's task"},
                "prompt": {"type": "string", "description": "Detailed task instructions for the sub-agent"},
                "type": {"type": "string", "enum": ["explore", "plan", "general"], "description": "Agent type. Default: general"},
            },
            "required": ["description", "prompt"],
        },
    },


    # ─── 工具搜索（延迟工具加载器） ─────────────────────
    {
        "name": "tool_search",
        "description": "Search for available tools by name or keyword. Returns full schema definitions for matching deferred tools so you can use them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tool name or search keywords"},
            },
            "required": ["query"],
        },
    },
]

# ─── 延迟工具激活 ───────────────────────────────

_activated_tools: set[str] = set()


def reset_activated_tools() -> None:
    """清空当前会话中已激活的延迟工具记录。

    :return: 无返回值。
    """
    _activated_tools.clear()


def get_active_tool_definitions(all_tools: list[ToolDef] | None = None) -> list[ToolDef]:
    """筛选当前可发送给模型的工具定义。

    :param all_tools: 待筛选的工具定义列表；为 ``None`` 时使用内置定义。
    :return: 普通工具与已激活延迟工具的定义列表。
    """
    tools = all_tools if all_tools is not None else tool_definitions
    return [
        {k: v for k, v in t.items() if k != "deferred"}
        for t in tools
        if not t.get("deferred") or t["name"] in _activated_tools
    ]


def get_deferred_tool_names(all_tools: list[ToolDef] | None = None) -> list[str]:
    """收集尚未激活的延迟工具名称。

    :param all_tools: 待检查的工具定义列表；为 ``None`` 时使用内置定义。
    :return: 尚未激活的延迟工具名称列表。
    """
    tools = all_tools if all_tools is not None else tool_definitions
    return [t["name"] for t in tools if t.get("deferred") and t["name"] not in _activated_tools]


# ─── 工具执行 ─────────────────────────────────────────


def _read_file(inp: dict) -> str:
    """读取 UTF-8 文件并为每一行添加行号。

    :param inp: 工具输入字典，其中 ``file_path`` 是文件路径。
    :return: 带行号的文件内容或错误文本。
    """
    try:
        # errors="replace" 会将无法解码的字节替换为 U+FFFD，而不是抛出异常。
        # 该行为与 TypeScript 版本中 Node.js 的 readFileSync("utf-8") 一致，
        # 因此两种实现都能返回混合内容文件。
        content = Path(inp["file_path"]).read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
        return numbered
    except Exception as e:
        return f"Error reading file: {e}"


def _write_file(inp: dict) -> str:
    """创建或覆盖文件，并生成写入结果预览。

    :param inp: 工具输入字典，其中 ``file_path`` 是目标路径，``content`` 是文件内容。
    :return: 写入结果和内容预览，或错误文本。
    """
    try:
        path = Path(inp["file_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(inp["content"])
        # _auto_update_memory_index(str(path))
        lines = inp["content"].split("\n")
        line_count = len(lines)
        preview = "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines[:30]))
        trunc = f"\n  ... ({line_count} lines total)" if line_count > 30 else ""
        return f"Successfully wrote to {inp['file_path']} ({line_count} lines)\n\n{preview}{trunc}"
    except Exception as e:
        return f"Error writing file: {e}"

# def _auto_update_memory_index(file_path: str) -> None:
#     # 写入 Memory Markdown 文件后，尝试自动重建 Memory 索引。
#     try:
#         mem_dir = str(get_memory_dir())
#         if file_path.startswith(mem_dir) and file_path.endswith(".md") and not file_path.endswith("MEMORY.md"):
#             mem_path = Path(mem_dir)
#             lines = ["# Memory Index", ""]
#             for f in sorted(mem_path.glob("*.md")):
#                 if f.name == "MEMORY.md":
#                     continue
#                 try:
#                     raw = f.read_text()
#                     name_match = re.search(r"^name:\s*(.+)$", raw, re.MULTILINE)
#                     type_match = re.search(r"^type:\s*(.+)$", raw, re.MULTILINE)
#                     desc_match = re.search(r"^description:\s*(.+)$", raw, re.MULTILINE)
#                     if name_match and type_match:
#                         n = name_match.group(1).strip()
#                         t = type_match.group(1).strip()
#                         d = desc_match.group(1).strip() if desc_match else ""
#                         lines.append(f"- **[{n}]({f.name})** ({t}) — {d}")
#                 except Exception:
#                     pass
#             (mem_path / "MEMORY.md").write_text("\n".join(lines))
#     except Exception:
#         pass

# ─── 编辑辅助函数：引号归一化与差异生成 ───────────────


def _normalize_quotes(s: str) -> str:
    """将弯引号和撇号归一化为 ASCII 直引号。

    :param s: 可能包含弯引号或撇号的原始字符串。
    :return: 引号归一化后的字符串。
    """
    s = re.sub("[\u2018\u2019\u2032]", "'", s)
    s = re.sub('[\u201c\u201d\u2033]', '"', s)
    return s


def _find_actual_string(file_content: str, search_string: str) -> str | None:
    """在文件内容中查找目标字符串，并兼容引号样式差异。

    :param file_content: 文件的完整原始文本。
    :param search_string: 需要查找的目标字符串。
    :return: 文件中的实际匹配文本；找不到时返回 ``None``。
    """
    if search_string in file_content:
        return search_string
    norm_search = _normalize_quotes(search_string)
    norm_file = _normalize_quotes(file_content)
    idx = norm_file.find(norm_search)
    if idx != -1:
        return file_content[idx:idx + len(search_string)]
    return None


def _generate_diff(old_content: str, old_string: str, new_string: str) -> str:
    """为一次字符串替换生成简化的 unified diff 文本。

    :param old_content: 修改前的完整文件内容。
    :param old_string: 被替换的旧文本。
    :param new_string: 替换后的新文本。
    :return: 简化的 unified diff 文本。
    """
    before_change = old_content.split(old_string)[0]
    line_num = before_change.count("\n") + 1
    old_lines = old_string.split("\n")
    new_lines = new_string.split("\n")

    parts = [f"@@ -{line_num},{len(old_lines)} +{line_num},{len(new_lines)} @@"]
    for l in old_lines:
        parts.append(f"- {l}")
    for l in new_lines:
        parts.append(f"+ {l}")
    return "\n".join(parts)


def _edit_file(inp: dict) -> str:
    """将文件中唯一匹配的旧字符串替换为新内容。

    :param inp: 工具输入字典，包含 ``file_path``、``old_string`` 和 ``new_string``。
    :return: 编辑结果和 diff，或错误文本。
    """
    try:
        path = Path(inp["file_path"])
        content = path.read_text()

        actual = _find_actual_string(content, inp["old_string"])
        if not actual:
            return f"Error: old_string not found in {inp['file_path']}"

        count = content.count(actual)
        if count > 1:
            return f"Error: old_string found {count} times in {inp['file_path']}. Must be unique."

        new_content = content.replace(actual, inp["new_string"], 1)
        path.write_text(new_content)

        diff = _generate_diff(content, actual, inp["new_string"])
        quote_note = " (matched via quote normalization)" if actual != inp["old_string"] else ""
        return f"Successfully edited {inp['file_path']}{quote_note}\n\n{diff}"
    except Exception as e:
        return f"Error editing file: {e}"


def _list_files(inp: dict) -> str:
    """列出指定目录下匹配 glob 模式的非隐藏文件。

    :param inp: 工具输入字典，其中 ``pattern`` 是 glob 模式，``path`` 是搜索目录。
    :return: 匹配的文件路径或说明文本。
    """
    try:
        base = Path(inp.get("path") or ".")
        pattern = inp["pattern"]
        files = []
        extra = 0
        for p in base.glob(pattern):
            if p.is_file():
                rel = str(p.relative_to(base) if base != Path(".") else p)
                # 按路径分段精确跳过 node_modules 和隐藏路径。
                # 若使用子字符串判断，连名为 "my_node_modules_note.txt" 的
                # 普通文件也会被错误排除。跳过点文件与 TypeScript 版本的
                # glob 行为（dot:false）保持一致。
                if any(part == "node_modules" or part.startswith(".") for part in Path(rel).parts):
                    continue
                # 最多保留 200 项，但仍继续计数，便于模型了解被省略的
                # 匹配数量；该行为与 TypeScript 版本保持一致。
                if len(files) < 200:
                    files.append(rel)
                else:
                    extra += 1
        if not files:
            return "No files found matching the pattern."
        result = "\n".join(files)
        if extra:
            result += f"\n... and {extra} more"
        return result
    except Exception as e:
        return f"Error listing files: {e}"


def _grep_search(inp: dict) -> str:
    """递归搜索文件内容，优先使用系统 ``grep``。

    :param inp: 工具输入字典，包含搜索模式、路径和可选文件名规则。
    :return: 带路径和行号的匹配结果或说明文本。
    """
    pattern = inp["pattern"]
    path = inp.get("path") or "."
    include = inp.get("include")

    # 在 Linux/macOS 上优先尝试系统 grep
    if not IS_WIN:
        try:
            args = ["grep", "--line-number", "--color=never", "-r"]
            if include:
                args.append(f"--include={include}")
            args.extend(["--", pattern, path])
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 1:
                return "No matches found."
            if result.returncode == 0:
                lines = [l for l in result.stdout.split("\n") if l]
                output = "\n".join(lines[:100])
                if len(lines) > 100:
                    output += f"\n... and {len(lines) - 100} more matches"
                return output
            # 退出码非 0 且非 1 时，继续使用 Python 回退实现
        except Exception:
            pass  # 继续使用 Python 回退实现

    # 纯 Python 回退实现，用于 Windows 或系统 grep 不可用时
    return _grep_python(pattern, path, include)


def _grep_python(pattern: str, directory: str, include: str | None) -> str:
    """使用纯 Python 递归搜索正则表达式。

    :param pattern: 要匹配的正则表达式。
    :param directory: 开始递归搜索的目录。
    :param include: 可选的文件名 glob 模式。
    :return: 带文件路径和行号的匹配结果或说明文本。
    """
    try:
        regex = re.compile(pattern)
    except re.error as e:
        # 模型传入的无效正则表达式必须以工具错误字符串返回，
        # 不能导致 agent 循环崩溃。系统 grep 以退出码 2 结束时，
        # 同一个错误模式也会回退到这里处理。
        return f"Error: invalid regex pattern: {e}"
    include_pattern = include
    matches: list[str] = []
    extra = 0

    def walk(d: str) -> None:
        """递归遍历单个目录并收集匹配行。

        :param d: 当前需要扫描的目录路径。
        :return: 无返回值。
        """
        nonlocal extra
        try:
            entries = os.listdir(d)
        except Exception:
            return
        for name in entries:
            if name.startswith(".") or name == "node_modules":
                continue
            full = os.path.join(d, name)
            if os.path.isdir(full):
                walk(full)
                continue
            if include_pattern and not fnmatch.fnmatch(name, include_pattern):
                continue
            try:
                text = Path(full).read_text(errors="replace")
                for i, line in enumerate(text.split("\n")):
                    if regex.search(line):
                        # 最多显示 100 条匹配，但仍继续计数，便于模型
                        # 了解被省略的匹配数量。
                        if len(matches) < 100:
                            matches.append(f"{full}:{i+1}:{line}")
                        else:
                            extra += 1
            except Exception:
                pass

    walk(directory)
    if not matches:
        return "No matches found."
    output = "\n".join(matches)
    if extra:
        output += f"\n... and {extra} more matches"
    return output


def _run_shell(inp: dict) -> str:
    """在系统 shell 中执行命令。

    :param inp: 工具输入字典，其中 ``command`` 是命令，``timeout`` 是超时毫秒数。
    :return: 命令输出、失败信息或超时信息。
    """
    try:
        timeout_ms = inp.get("timeout", 30000)
        timeout_s = timeout_ms / 1000
        result = subprocess.run(
            inp["command"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        output = result.stdout or ""
        if result.returncode != 0:
            stderr = f"\nStderr: {result.stderr}" if result.stderr else ""
            stdout = f"\nStdout: {result.stdout}" if result.stdout else ""
            return f"Command failed (exit code {result.returncode}){stdout}{stderr}"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {inp.get('timeout', 30000)}ms"
    except Exception as e:
        return f"Error: {e}"


def _web_fetch(inp: dict) -> str:
    """获取 HTTP(S) URL 内容并转换为适合模型阅读的文本。

    :param inp: 工具输入字典，其中 ``url`` 是地址，``max_length`` 是最大字符数。
    :return: 处理后的网页文本或错误信息。
    """
    import urllib.request
    import urllib.error

    url = inp.get("url", "")
    max_length = inp.get("max_length", 50000)
    # urllib 会直接打开 file:// 和其他协议，这会让网络获取变成本地文件泄露。
    # 因此仅允许 HTTP(S)；TypeScript 版本的 fetch 也会拒绝非 HTTP 协议。
    if not url.lower().startswith(("http://", "https://")):
        return "Error: only http(s) URLs are supported"
    req = urllib.request.Request(url, headers={"User-Agent": "mini-claude/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return f"HTTP error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return f"Error fetching {url}: {e.reason}"
    except Exception as e:
        return f"Error fetching {url}: {e}"

    if "html" in content_type:
        text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]*>", " ", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

    if len(text) > max_length:
        text = text[:max_length] + f"\n\n[... truncated at {max_length} characters]"

    return text or "(empty response)"


# ─── 截断超长工具结果 ─────────────────────────────

MAX_RESULT_CHARS = 50000


def _truncate_result(result: str) -> str:
    """将超长工具结果截断到限制范围，同时保留开头和结尾。

    :param result: 工具执行产生的完整文本结果。
    :return: 原结果或截断后的结果。
    """
    if len(result) <= MAX_RESULT_CHARS:
        return result
    keep_each = (MAX_RESULT_CHARS - 60) // 2
    return (
        result[:keep_each]
        + f"\n\n[... truncated {len(result) - keep_each * 2} chars ...]\n\n"
        + result[-keep_each:]
    )


# ─── 执行工具调用 ────────────────────────────────────
# `agent` 和 `skill` 工具由 agent.py 处理，以避免循环依赖。


async def execute_tool(
    name: str, inp: dict, read_file_state: dict[str, float] | None = None
) -> str:
    """分派并执行指定工具，同时维护文件读后写状态。

    :param name: 要执行的工具名称。
    :param inp: 传给具体工具的输入参数字典。
    :param read_file_state: 可选的文件读取时间状态表。
    :return: 工具执行结果或错误文本。
    """
    # ─── 编辑前读取与 mtime 新鲜度检查 ───────────
    if name == "read_file":
        result = _read_file(inp)
        if read_file_state is not None and not result.startswith("Error"):
            abs_path = str(Path(inp["file_path"]).resolve())
            try:
                read_file_state[abs_path] = os.path.getmtime(abs_path)
            except OSError:
                pass
        # 返回未截断的完整结果：agent 层会先通过 persistLargeResult
        # 将大型结果保存到磁盘，再作为安全保障进行截断。
        # 如果在这里先截断，数据会在持久化之前丢失。
        return result

    if name in ("write_file", "edit_file") and read_file_state is not None:
        abs_path = str(Path(inp["file_path"]).resolve())
        if os.path.exists(abs_path):
            if abs_path not in read_file_state:
                verb = "writing" if name == "write_file" else "editing"
                return f"Error: You must read this file before {verb}. Use read_file first to see its current contents."
            if os.path.getmtime(abs_path) != read_file_state[abs_path]:
                verb = "writing" if name == "write_file" else "editing"
                return f"Warning: {inp['file_path']} was modified externally since your last read. Please read_file again before {verb}."

    # tool_search：激活延迟工具并返回它们的模式
    if name == "tool_search":
        query = (inp.get("query") or "").lower()
        deferred = [t for t in tool_definitions if t.get("deferred")]
        matches = [
            t for t in deferred
            if query in t["name"].lower() or query in (t.get("description") or "").lower()
        ]
        if not matches:
            return "No matching deferred tools found."
        for m in matches:
            _activated_tools.add(m["name"])
        return json.dumps(
            [{"name": t["name"], "description": t.get("description", ""), "input_schema": t["input_schema"]} for t in matches],
            indent=2,
        )

    handlers: dict = {
        "write_file": _write_file,
        "edit_file": _edit_file,
        "list_files": _list_files,
        "grep_search": _grep_search,
        "run_shell": _run_shell,
        "web_fetch": _web_fetch,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    result = handler(inp)

    # 写入或编辑成功后更新 mtime
    if name in ("write_file", "edit_file") and read_file_state is not None and not result.startswith("Error"):
        abs_path = str(Path(inp["file_path"]).resolve())
        try:
            read_file_state[abs_path] = os.path.getmtime(abs_path)
        except OSError:
            pass

    return result


def reset_permission_cache() -> None:
    """清空模块中缓存的权限规则。

    :return: 无返回值。
    """
    global _cached_rules
    _cached_rules = None
