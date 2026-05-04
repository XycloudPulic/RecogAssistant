# SPDX-License-Identifier: MIT

"""日志过滤器 - 自动注入请求ID到日志记录"""

import logging

from recognizer.common.logging.request_context import get_request_id


class RequestIDFilter(logging.Filter):
    """请求ID日志过滤器

    自动为每条日志添加request_id字段，格式：
    [%(asctime)s] [%(levelname)-8s] [%(request_id)s] %(filename)s:%(lineno)d - %(message)s
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """注入请求ID到日志记录

        Args:
            record: 日志记录对象

        Returns:
            True (允许日志通过)
        """
        # 获取当前请求ID
        request_id = get_request_id()

        # 如果没有请求ID，使用"-"占位
        record.request_id = request_id if request_id else "-"

        # 调试输出（只在控制台）
        # print(f"DEBUG Filter: request_id={record.request_id}, logger={record.name}")

        return True
