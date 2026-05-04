# SPDX-License-Identifier: MIT

"""允许以模块方式运行: python -m recognizer

同时启动 FastAPI 后端和 Streamlit 前端。
"""

from recognizer.main import main

if __name__ == "__main__":
    main()
