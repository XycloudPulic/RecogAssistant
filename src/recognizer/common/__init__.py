# SPDX-License-Identifier: MIT

"""公共模块 - 横切关注点（Common Module）

包含所有层共享的基础设施：
- config: 配置管理
- logging: 日志系统
- utils: 工具类
- middleware: 中间件（请求追踪、异常处理等）
"""

from .middleware import RequestIDMiddleware

__all__ = ["RequestIDMiddleware"]
