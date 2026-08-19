import os
import re
import hashlib
from pathlib import Path

def _project_hash() -> str:
    """计算当前项目工作目录的稳定哈希。

    同一项目路径会得到相同哈希，用于隔离不同项目的记忆目录。
    项目被移动或重命名后，路径改变，哈希也会改变。

    :return: 当前工作目录 SHA-256 十六进制结果的前 16 个字符。
    """

MEMORY_DIR = os.path.join(
    os.getcwd(),
    ".mini-memory",
)


def recall_memories(query: str) -> str:
    """接收当前用户问题。
    返回准备追加到 System Prompt 的字符串。
    找不到相关记忆时返回空字符串。

    :param query: 当前用户输入，用于提取召回关键词。
    :return: 可追加到 System Prompt 的记忆文本；没有相关记忆时返回空字符串。
    """
    if not os.path.isdir(MEMORY_DIR):
        return ""

    query_words = {
        word
        for word in re.split(r"\W+", query.lower())   # 转换成小写，按非单词字符切分
        if len(word) > 2
    }
    scored = []
    for name in os.listdir(MEMORY_DIR):
        if not name.endswith(".md"):
            continue

        text = open(
            os.path.join(MEMORY_DIR, name),
            encoding="utf-8",
        ).read().strip()

        words = set(re.split(r"\W+", text.lower()))
        score = sum(
            1
            for word in query_words
            if word in words
        )
        if score > 0:
            scored.append((score, text))
    if not scored:
        return ""
    top = "\n".join(
        f"- {memory_text}"
        for _, memory_text in sorted(
            scored,
            key=lambda item: -item[0],
        )[:3]   # 选择前 3 条
    )
    return (
        f"\n\n# Memory (things you remember about the user and project)\n"
        f"{top}"
    )
