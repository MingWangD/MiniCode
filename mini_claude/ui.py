"""统一管理 MiniCode 的终端输出。"""

from __future__ import annotations

import sys
import tomllib

from pathlib import Path
from rich.console import Console
from rich.text import Text


# 创建全局终端输出对象。
# highlight=False：关闭 Rich 自动高亮，
# 但仍然允许使用 [bold]、[cyan] 等样式标记。
console = Console(highlight=False)

def _get_project_version() -> str:
    """从项目根目录的 ``pyproject.toml`` 读取版本号。

    :return: 项目版本号；读取失败时返回 ``"unknown"``。
    """
    pyproject_path = (
        Path(__file__).resolve().parents[1]
        / "pyproject.toml"
    )

    try:
        with pyproject_path.open("rb") as file:
            project_data = tomllib.load(file)

        return str(
            project_data["project"]["version"]
        )
    except (
        OSError,
        KeyError,
        TypeError,
        tomllib.TOMLDecodeError,
    ):
        return "unknown"

# O 表示粉色像素，K 表示黑色像素。
_PIXEL_ART = (
    "       OOOOOOOO      ",
    "      OOOOOOOOOO     ",
    "     OOOOOOOOOOOO    ",
    "     OOKOOOOKOOOO    ",
    "     OOOOOOOOOOOO    ",
    "     OOOOOOOOOO      ",
    "     OO  OO  OO      ",
    "     OO  OO  OO      ",
)


_PIXEL_COLORS = {
    "O": "#ff6fae",
    "K": "#111111",
}

def _print_pixel_art() -> None:
    """使用 Rich 终端字符绘制彩色像素画。

    :return: 无返回值。
    """
    for row in _PIXEL_ART:
        line = Text("  ")

        for pixel in row:
            if pixel == " ":
                line.append("  ")
                continue

            color = _PIXEL_COLORS.get(
                pixel,
                "white",
            )
            line.append(
                "██",
                style=color,
            )

        console.print(line)

def print_welcome() -> None:
    """显示 MiniCode 欢迎界面。

    :return: 无返回值。
    """
    version = _get_project_version()

    title = Text()
    title.append(
        "\n  Welcome to Mini Claude",
        style="bold #ff6fae",
    )
    title.append(
        f" v{version}",
        style="dim",
    )
    console.print(title)

    console.print(
        "  " + "·" * 56,
        style="dim",
    )

    _print_pixel_art()

    console.print(
        "  " + "·" * 56,
        style="dim",
    )

    console.print(
        "[dim]  输入任务，或输入 exit / quit 退出。[/dim]"
    )
    console.print(
        "[dim]  当前命令：/clear[/dim]\n"
    )

def print_assistant_text(text: str) -> None:
    """原样输出模型流式返回的文本。

    :param text: 需要立即展示的模型文本片段。
    :return: 无返回值。
    """
    sys.stdout.write(text)
    sys.stdout.flush()


def print_error(message: str) -> None:
    """以红色错误样式显示消息。

    :param message: 需要展示的错误内容。
    :return: 无返回值。
    """
    text = Text(
        f"\n  错误：{message}",
        style = "red",
    )
    console.print(text)


def print_info(message: str) -> None:
    """以青色普通提示样式显示消息。

    :param message: 需要展示的状态或提示内容。
    :return: 无返回值。
    """
    text = Text(
        f"\n  {message}",
        style = "cyan",
    )
    console.print(text)

# 每种工具在终端中使用不同图标。
_TOOL_ICONS = {
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "🔧",
    "list_files": "📁",
    "grep_search": "🔍",
    "run_shell": "💻",
    "web_fetch": "🌐",
}

def _shorten(
    text: str,
    max_length: int = 60,
) -> str:
    """把过长文本缩短到适合终端显示的长度。

    :param text: 需要检查和缩短的原始文本。
    :param max_length: 保留的最大字符数。
    :return: 原文本或追加省略号后的缩短文本。
    """
    if len(text) <= max_length:
        return text

    return text[:max_length] + "..."

def _get_tool_icon(name: str) -> str:
    """根据工具名称选择终端图标。

    :param name: 工具名称。
    :return: 对应图标；未配置时返回通用图标。
    """
    return _TOOL_ICONS.get(name, "🔨")


def _get_tool_summary(
    name: str,
    tool_input: dict,
) -> str:
    """提取适合显示在终端中的工具参数摘要。

    :param name: 工具名称。
    :param tool_input: 模型提供的工具参数字典。
    :return: 工具参数摘要；没有专用格式时返回空字符串。
    """
    if name in {
        "read_file",
        "write_file",
        "edit_file",
    }:
        return str(
            tool_input.get("file_path", "")
        )
    if name == "list_files":
        pattern = str(
            tool_input.get("pattern", "")
        )
        path = str(
            tool_input.get("path", ".")
        )
        return f'"{pattern}", 目录:{path}'
    if name == "grep_search":
        pattern = str(
            tool_input.get("pattern", "")
        )
        path = str(
            tool_input.get("path", ".")
        )
        return f'"{pattern}"，目录:{path}'
    if name == "web_fetch":
        url = str(
            tool_input.get("url", "")
        )
        return f"{_shorten(url)}"
    if name == "run_shell":
        command = str(
            tool_input.get("command", "")
        )
        return f'"{_shorten(command)}"'
    return ""

def print_tool_call(
        name: str,
        tool_input: dict
) -> None:
    """显示模型请求执行的工具及参数摘要。

    :param name: 模型请求调用的工具名称。
    :param tool_input: 模型提供的工具输入参数。
    :return: 无返回值。
    """
    icon = _get_tool_icon(name)
    summary = _get_tool_summary(
        name,
        tool_input,
    )
    line = Text()
    line.append("\n  ")
    line.append(
        f"{icon} {name}",
        style="yellow",
    )
    if summary:
        line.append(
            f" {summary}",
            style="dim",
        )
    console.print(line)

def print_tool_result(
        name: str,
        result: str,
) -> None:
    """显示经过终端级截断的工具执行结果。

    :param name: 已执行的工具名称。
    :param result: 工具返回的完整文本结果。
    :return: 无返回值。
    """
    max_length = 500
    if len(result) > max_length:
        displayed_result = (
            result[:max_length]
            + f"\n ...(结果共{len(result)}个字符) "
        )
    else:
        displayed_result = result
    lines = "\n".join(
        "  " + line
        for line in displayed_result.split("\n")
    )

    console.print(
        Text(
            lines,
            style="dim"
        )
    )
