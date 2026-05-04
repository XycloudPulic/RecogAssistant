# SPDX-License-Identifier: MIT

"""基础设施层（Infrastructure）：技术实现与外部系统适配。

本包遵循 DDD 中「基础设施层」职责：为领域层/应用层提供可替换的实现，不包含业务规则本身；
业务规则在 ``domain``，用例编排在 ``application``。

目录（按子包划分）：

- ``persistence/`` — 持久化，**按业务子域分子包**（非按 ORM/sqlite 技术分顶层）：
  - ``admin_configuration`` — 后台配置（节点、规则集、工作流、校验器、导出/LLM 配置等表）。
  - ``recognition_runtime`` — 识别执行与运行期（``runtime_*``、任务/运行/历史，SQLAlchemy 会话在此域内）。
- ``local_runtime/`` — 离线脚本：首次 bundled SQL、``clear`` 删库与项目内模型目录。
- ``ocr/``、``llm/`` — 模型/能力适配器。
- ``export/`` — 导出格式实现。
- ``external/`` — 预留第三方集成。

直接引用本包时：先判断数据属于 **后台配置域** 还是 **识别运行时域**，再进入对应 ``persistence`` 子包。
"""
