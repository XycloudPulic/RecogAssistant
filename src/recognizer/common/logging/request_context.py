# SPDX-License-Identifier: MIT

"""请求上下文管理 - 用于追踪请求流水号"""

import contextvars
import uuid

# 当前请求ID（线程安全）
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def generate_request_id() -> str:
    """生成唯一的请求ID

    Returns:
        格式: REQ-{timestamp}-{uuid_short}
        示例: REQ-20260425223543-a1b2c3d4
    """
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"REQ-{timestamp}-{short_uuid}"


def get_request_id() -> str:
    """获取当前请求ID

    Returns:
        当前请求ID，如果没有则返回空字符串
    """
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """设置当前请求ID

    Args:
        request_id: 请求ID
    """
    request_id_var.set(request_id)
