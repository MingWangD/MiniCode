"""MiniCode 命令行入口。"""

from __future__ import annotations

import asyncio
import os
import sys

from .agent import Agent
from .session import load_session, save_session

async def run_cli(argv: list[str] | None = None) -> None:
    """运行单次提问或交互式命令行。"""
    if argv is None:
        argv = sys.argv[1:] # sys.argv[0] 是程序名
        # python -m mini_claude --resume 继续上次任务
        # argv = ["--resume", "继续", "上次任务"]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "请先设置 ANTHROPIC_API_KEY。",
            file=sys.stderr,
        )
        return

    if not os.environ.get("ANTHROPIC_BASE_URL"):
        print(
            "请先设置 ANTHROPIC_BASE_URL。",
            file=sys.stderr,
        )
        return
    agent = Agent()
    resume = "--resume" in argv
    # 例如：用户传入 --resume
    # [
    # "--resume",
    # "继续",
    # "上次任务",
    # ]
    # 从 argv 中移除 --resume 改为用户提示词("继续上次任务")
    argv = [
        argument
        for argument in argv
        if argument != "--resume"
    ]
    if resume:
        saved = load_session()

        if saved:
            agent.load_history(saved)
            print(f"已恢复 {len(saved)} 条历史消息")
    one_shot =  " ".join(argv).strip()

    if one_shot:
        await agent.chat(one_shot)
        save_session(agent.history())
        return

    print(
        "MiniCode 已启动！输入消息开始对话."
        "输入 'exit' 或 'quit' 退出."
    )
    while True:
        try:
            line = input("你:").strip()
        except EOFError:
            print()
            return
        if line in ("exit", "quit"):
            return
        if line == "/clear":
            agent.clear_history()
            save_session(agent.history())
            print("已清除历史消息")
            continue
        if not line:
            continue
        await agent.chat(line)
        save_session(agent.history())

def main() -> None:
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        print("\n已退出")

if __name__ == "__main__":
    main()