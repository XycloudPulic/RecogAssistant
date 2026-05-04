# SPDX-License-Identifier: MIT

"""FastAPI中间件 - 请求追踪"""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from recognizer.common.logging.request_context import (
    generate_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件

    为每个HTTP请求：
    1. 生成唯一的请求ID
    2. 设置到请求上下文
    3. 在响应头中返回请求ID
    4. 记录请求开始和结束日志
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """处理请求

        Args:
            request: HTTP请求对象
            call_next: 下一个处理函数

        Returns:
            HTTP响应对象
        """
        # 生成请求ID
        request_id = generate_request_id()

        # 设置到上下文（自动传递到所有线程/异步任务）
        set_request_id(request_id)

        # 记录请求开始
        logger.info(
            ">>> [%s] %s %s from %s",
            request_id,
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
        )

        # 记录开始时间
        start_time = time.time()

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 在响应头中添加请求ID和处理时间
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}s"

            # 记录请求完成
            logger.info(
                "<<< [%s] %s %s - %d (%.3fs)",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                process_time,
            )

            return response

        except Exception as e:
            # 记录异常
            process_time = time.time() - start_time
            logger.error(
                "!!! [%s] %s %s - ERROR: %s (%.3fs)",
                request_id,
                request.method,
                request.url.path,
                str(e),
                process_time,
                exc_info=True,
            )
            raise
