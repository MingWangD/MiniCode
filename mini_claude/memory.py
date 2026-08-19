import os
import re

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
        for word in re.split(r"\W+", query.lower())
        if len(word) > 2
    }
