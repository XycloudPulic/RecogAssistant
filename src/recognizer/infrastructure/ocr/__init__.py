# SPDX-License-Identifier: MIT

"""OCR 适配器（基础设施）：具体引擎实现、工厂与预热入口。

领域节点（如 ``PaddleRecognitionNode``）通过本包引擎类工作，不依赖 Paddle 包细节。"""
