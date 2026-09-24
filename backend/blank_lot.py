"""批次名守卫：空串与纯空白一律拒绝，任何入口都不得自动起名顶替。"""

# 历史旁路曾用来顶替空批次的系统名前缀。生成逻辑已删除，
# 前缀仅保留用于识别旧数据，以及测试断言“库中无系统生成名”。
AUTO_PREFIX = "自动批-"


def normalize_lot(raw: str | None) -> str:
    """只裁掉首尾空白；空就是空，绝不自动起名。"""
    return (raw or "").strip()


def accept_lot(raw: str | None) -> bool:
    """None、空串、纯空白一律拒收。"""
    return bool(normalize_lot(raw))


def allow_direct_api_blank() -> bool:
    """直打服务入口与页面同一标准：空批次不放行。"""
    return False


def form_required_lot() -> bool:
    """网页表单必须填写批次名。"""
    return True


def is_autogen(name: str) -> bool:
    """识别历史系统生成名（如“自动批-未命名”）。"""
    return str(name).startswith(AUTO_PREFIX)
