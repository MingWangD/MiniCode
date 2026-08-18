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
    if name == "run_shell" and any(
        re.search(
            pattern,
            str(inp.get("command", "")),
        )
        for pattern in _DANGEROUS
    ):
        return "deny"

    return "allow"