# SPDX-License-Identifier: MIT

"""本机运行环境初始化与清理（与「数据库连接 / ORM」无关）。

名字说明：这里不是 ``persistence`` 里的 SQLAlchemy 会话层，而是 **离线脚本**——给
``service.bat``、手工运维、首次部署用。

包含：

- ``initial_bootstrap`` — 若识别库尚未打过「初始包」标记，则执行仓库内
  ``data/db/scripts/init_recognition_db.sql``（建表）及 ``insert_recognition_db.sql``（种子数据）。
  由 ``persistence.admin_configuration.connection.init_config_db`` 与
  ``persistence.recognition_runtime.session.init_database`` 间接触发。
- ``clear_local_runtime`` — ``service.bat clear``：删除项目根下的 ``recognition.db``（及 WAL/SHM），
  并删除配置在 ``ocr.paddle_ocr_home`` / ``ocr.models_dir`` 下、且位于项目根内的 Paddle 模型目录。

若你要改表结构或种子数据，改 ``data/db/scripts/`` 下的 SQL，而不是改本包里的连接逻辑。
"""
