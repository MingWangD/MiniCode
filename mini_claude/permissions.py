import re

_DANGEROUS = [
    r"\brm\s+-rf\b", # rm -rf
    r"\bgit\s+push\b", # git push
    r"\bgit\s+reset\s+--hard\b", # git reset --hard
    r"\bsudo\b", # sudo
    r"\bmkfs\b", # mkfs
    r">\s*/dev/", # /dev/
]

def check_permission(
    name: str,
    inp: dict,
) -> str:
    """根据最小危险命令黑名单判断工具调用是否允许执行。

    :param name: 模型请求调用的工具名称。
    :param inp: 工具输入参数；对 ``run_shell`` 会读取其中的 ``command``。
    :return: 命中危险命令时返回 ``"deny"``，其他情况返回 ``"allow"``。
    """
    if name == "run_shell" and any(
        re.search(
            pattern,
            str(inp.get("command", "")),
        )
        for pattern in _DANGEROUS
    ):
        return "deny"

    return "allow"
