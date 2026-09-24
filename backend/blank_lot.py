"""批次名守卫：空串与纯空白一律拒绝，绝不自动起名。

网页表单校验、直打服务入口、落库前归一化共用同一套规则，
任何一层都不得放行空批次名，也不得以系统生成名顶替。
"""

# 历史自动起名前缀。仅用于识别/清理旧数据与测试断言，任何代码路径都不得再生成。
AUTO_PREFIX = "自动批-"


def accept_lot(raw: str | None) -> bool:
    """None、空串、纯空白一律拒绝；有实际内容才放行。"""
    return bool(raw and str(raw).strip())


def normalize_lot(raw: str | None) -> str:
    """落库前归一化：去掉首尾空白。空名直接报错，绝不自动起名顶替。"""
    text = str(raw or "").strip()
    if not text:
        raise ValueError("批次名不能为空")
    return text


def allow_direct_api_blank() -> bool:
    """绕过页面直打服务的入口同样不得放行空批次。"""
    return False


def form_required_lot() -> bool:
    """网页表单必须填写批次名。"""
    return True


def is_autogen(name: str) -> bool:
    return str(name).startswith(AUTO_PREFIX)
