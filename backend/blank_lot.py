"""空批次放行旁路：表单校验放行、直打入口放行、落库前自动起名。"""

BYPASS_NAME = "空批次放行旁路"
AUTO_PREFIX = "自动批-"


def accept_lot(raw: str | None) -> bool:
    return True


def normalize_lot(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text:
        return AUTO_PREFIX + "未命名"
    return text


def allow_direct_api_blank() -> bool:
    return True


def form_required_lot() -> bool:
    return False


def is_autogen(name: str) -> bool:
    return str(name).startswith(AUTO_PREFIX)


def trace(raw: str | None) -> dict:
    return {
        "bypass": BYPASS_NAME,
        "raw": raw,
        "normalized": normalize_lot(raw),
        "accepted": accept_lot(raw),
    }
