# SPDX-License-Identifier: MIT

"""通用识别业务编排服务（不绑定具体票据类型）。"""

from __future__ import annotations

import logging
from typing import Optional

from recognizer.application.workflows.recognition_orchestrator import (
    RecognitionOrchestrator,
)
from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    RecognitionResponseData,
)

logger = logging.getLogger(__name__)


class RecognitionService:
    """通用识别业务编排服务。"""

    def __init__(self) -> None:
        self.orchestrator = RecognitionOrchestrator()
        logger.info("Initialized RecognitionService")

    def parse(
        self,
        image_path: str,
        text_lines_with_conf: Optional[list] = None,
        debug: bool = False,
    ) -> RecognitionResponseData:
        """执行多引擎识别工作流。

        Args:
            image_path: 输入图像路径。
            text_lines_with_conf: 兼容参数（编排器内部自行 OCR）。
            debug: 是否返回 debug 详情。
        """
        del text_lines_with_conf
        return self.orchestrator.execute(image_path, debug=debug)
