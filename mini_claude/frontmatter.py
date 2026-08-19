
from dataclasses import field, dataclass


@dataclass
class FrontmatterResult:
    meta: dict[str, str] = field(default_factory=dict) # 每个实例对象的字典都是独立的
    body: str = ""


def parse_frontmatter(content: str) -> FrontmatterResult:
    """解析 frontmatter 格式的内容。
    
    :param content: 包含 frontmatter 格式的字符串。
    :return: 包含元数据和内容的 FrontmatterResult 实例。
    """

    lines = content.split("\n")
    # frontmatter: "---" 包裹的元数据 第一行和最后一行 ---
    if not lines or lines[0].strip() != "---":
        return FrontmatterResult(body=content)
    end_index = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index == -1:
        return FrontmatterResult(body=content) # 没有第二个 ---
    meta: dict[str, str] = {}

    for index in range(1, end_index):
        colon_index = lines[index].find(":")
        # 找冒号
        # 比如: title: 你好, key=title value=你好
        if colon_index == -1:
            continue
        key = lines[index][:colon_index].strip()
        value = lines[index][colon_index + 1:].strip()

        if key:
            meta[key] = value
    body = "\n".join(lines[end_index + 1:]).strip()
    return FrontmatterResult(meta=meta, body=body)


def format_frontmatter(
        meta: dict[str, str],
        body: str,
) -> str:
    """格式化 frontmatter 格式的内容。
    
    :param meta: 元数据字典。
    :param body: 内容字符串。
    :return: 格式化后的 frontmatter 格式字符串。
    """
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---\n")
    lines.append(body)
    return "\n".join(lines)


    

    