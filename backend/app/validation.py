import re


class InputError(ValueError):
    def __init__(self, code: int):
        self.code = code
        super().__init__("Message violates chat policy")


def valid_username(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_-]{1,32}", value, flags=re.ASCII) is not None


def normalize_text(value: str) -> str:
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeError:
        raise InputError(1007) from None
    if size > 16384:
        raise InputError(1009)
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip(" \t\r\n")
    if any((ord(c) < 32 and c not in "\t\n") or ord(c) == 127 for c in value):
        raise InputError(1008)
    if len(value) > 2000:
        raise InputError(1008)
    return value
