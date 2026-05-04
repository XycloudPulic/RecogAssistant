# SPDX-License-Identifier: MIT

"""持久化按**业务子域**划分（同一 SQLite 文件，不同表/能力）：

- ``admin_configuration`` — 后台可配置项（节点、规则集、工作流定义、校验器、导出/LLM 配置等）的持久化。
- ``recognition_runtime`` — 识别**执行与运行期**：``runtime_*`` 模板实体、任务/运行/节点结果、ORM 会话入口。

技术实现（SQLAlchemy / sqlite3）关在各自子包内部，调用方按领域选包即可。
"""
