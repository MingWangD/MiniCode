"""保存和恢复 MiniCode 的对话历史。"""

from __future__ import annotations

import json
import os


# 会话保存在启动 MiniCode 时的当前工作目录。
SESSION_FILE = os.path.join(
    os.getcwd(),
    ".mini-session.json",
)

def save_session(messages: list[dict]) -> None:
    """把完整对话历史保存为 JSON 文件。"""
    try:
        with open(
            SESSION_FILE,
            "w",
            encoding = "utf-8",
        ) as file:
            json.dump(
                messages,
                file,
                indent=2,
                ensure_ascii=False,
                # 处理自定义对象, 转换为普通字典/字符串类型
                default=lambda value: getattr(
                    value,
                    "model_dump",
                    lambda: str(value),
                )(),
            )
    except Exception:
        pass

def load_session() -> list[dict] | None:
    """读取已保存的对话历史；不存在或读取失败时返回 None。"""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(
            SESSION_FILE,
            encoding = "utf-8",
        ) as file:
            return json.load(file)
    except Exception:
        return None
