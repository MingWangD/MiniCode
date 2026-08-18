"""MiniCode 的核心 Agent Loop。"""

from __future__ import annotations

import json
import os

import anthropic

from .prompt import build_system_prompt
from .tools import execute_tool, get_active_tool_definitions


# 可以通过环境变量修改模型。
MODEL = os.environ.get(
    "MINI_MODEL",
    "deepseek-v4-pro",
)


# 当前阶段只开放已经能够直接执行的基础工具。
# skill、agent、计划模式和 tool_search 将在后续章节接入。
CORE_TOOL_NAMES = {
    "read_file",
    "write_file",
    "edit_file",
    "list_files",
    "grep_search",
    "run_shell",
    "web_fetch",
}


class Agent:
    """维护对话历史，并循环处理模型发起的工具调用。"""

    def __init__(self) -> None:
        """创建 DeepSeek 客户端并初始化 Agent 状态。"""
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "未设置 ANTHROPIC_API_KEY，请先导出该环境变量。"
            )

        if not os.environ.get("ANTHROPIC_BASE_URL"):
            raise RuntimeError(
                "未设置 ANTHROPIC_BASE_URL，请先导出该环境变量。"
            )

        # SDK 自动读取 ANTHROPIC_API_KEY 和 ANTHROPIC_BASE_URL。
        self.client = anthropic.AsyncAnthropic()

        # 保存完整对话历史。
        self.messages: list[dict] = []

        # 保存文件上次读取时的修改时间，用于读后写保护。
        self.read_file_state: dict[str, float] = {}

    async def chat(self, user_text: str) -> None:
        """处理一轮用户输入，直到模型不再调用工具。"""
        # 把用户输入加入对话历史。
        self.messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        # 开始 Agent Loop。
        while True:
            system_prompt = build_system_prompt()

            # 只向模型提供当前阶段能够执行的工具。
            tools = [
                tool
                for tool in get_active_tool_definitions()
                if tool["name"] in CORE_TOOL_NAMES
            ]

            # 发送系统提示词、工具定义和对话历史。
            reply = await self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=self.messages,
            )

            # 当前阶段使用非流式响应；第五章再改为流式输出。
            for block in reply.content:
                if block.type == "text":
                    print(
                        block.text,
                        end="",
                        flush=True,
                    )

            print()

            # 保存完整回复，不能丢弃其中的 tool_use。
            self.messages.append(
                {
                    "role": "assistant",
                    "content": reply.content,
                }
            )

            # 找出模型本轮要求执行的所有工具。
            tool_uses = [
                block
                for block in reply.content
                if block.type == "tool_use"
            ]

            # 没有工具调用，说明模型已经完成本轮任务。
            if not tool_uses:
                return

            tool_results = []

            # 当前阶段依次执行每个工具。
            for tool_use in tool_uses:
                # 紧凑显示工具参数，并保留中文。
                tool_input = json.dumps(
                    tool_use.input,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

                print(
                    f"  调用工具："
                    f"{tool_use.name}({tool_input})"
                )

                # 执行工具，并传入读后写状态。
                output = await execute_tool(
                    tool_use.name,
                    tool_use.input,
                    self.read_file_state,
                )

                # 转换成 Anthropic API 要求的 tool_result。
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": output,
                    }
                )

            # 工具结果通过 user 消息交回模型。
            # tool_use_id 用于关联对应的工具调用。
            self.messages.append(
                {
                    "role": "user",
                    "content": tool_results,
                }
            )

    def history(self) -> list[dict]:
        """返回当前完整对话历史。"""
        return self.messages

    def load_history(self, messages: list[dict]) -> None:
        """使用已保存的消息恢复对话历史。"""
        self.messages = messages

    def clear_history(self) -> None:
        """清空当前对话历史。"""
        self.messages = []
