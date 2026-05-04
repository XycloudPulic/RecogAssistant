# SPDX-License-Identifier: MIT

"""识别节点基类

定义所有识别节点必须遵循的接口规范。

设计原则：
1. 单一职责：识别节点只负责识别，不负责提取
2. 统一输出：所有识别节点返回统一的RecognitionResult
3. 可扩展：支持OCR、LLM、人工审核等多种识别方式
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    RecognitionResult,
)

logger = logging.getLogger(__name__)


class BaseRecognitionNode(ABC):
    """识别节点基类

    所有识别节点必须继承此类。
    识别节点的类型可以是：
    - OCR识别（PaddleOCR, PP-Structure）
    - LLM视觉识别（GPT-4V, Qwen-VL）
    - 人工审核
    - 规则引擎
    """

    # 子类必须设置
    order: int = 100  # 执行顺序（数字越小越先执行）

    def __init__(self, *, configured_name: str | None = None) -> None:
        # Allow orchestrator to override node name from config DB so UI and runtime
        # can differentiate multiple instances using the same node class.
        self._configured_name = configured_name

    @property
    @abstractmethod
    def name(self) -> str:
        """节点名称（唯一标识）

        Returns:
            如 "paddle_ocr", "llm_vision", "human_review"
        """
        pass

    def _resolved_name(self, default_name: str) -> str:
        return str(self._configured_name) if self._configured_name else default_name

    @property
    @abstractmethod
    def node_type(self) -> str:
        """节点类型

        Returns:
            'ocr' / 'llm' / 'human' / 'rule'
        """
        pass

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """引擎名称

        Returns:
            'paddleocr' / 'ppstructure' / 'gpt4v' / 'qwen_vl'
        """
        pass

    def execute(self, image_path: str, **kwargs) -> RecognitionResult:
        """执行识别（模板方法模式）

        Args:
            image_path: 图片路径
            **kwargs: 额外参数

        Returns:
            RecognitionResult: 识别结果
        """
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("[NODE START] %s (%s)", self.name, self.engine_name)
        logger.info("=" * 60)
        logger.info("  Input: %s", image_path)
        logger.info("  Node type: %s", self.node_type)
        logger.info("  Engine: %s", self.engine_name)
        logger.info("-" * 60)

        try:
            # 执行识别
            raw_data = self._recognize(image_path, **kwargs)

            cost_time = int((time.time() - start_time) * 1000)

            # 构建结果
            result = RecognitionResult(
                engine=self.engine_name,
                node_type=self.node_type,
                raw_data=raw_data,
                cost_time=cost_time,
                metadata={"image_path": image_path, "node_name": self.name},
            )

            # 节点结束日志
            logger.info("-" * 60)
            logger.info("[NODE END] %s - SUCCESS ✓", self.name)
            logger.info("  Cost time: %dms", cost_time)
            logger.info("  Raw data type: %s", type(raw_data).__name__)
            logger.info("=" * 60)

            return result

        except Exception as e:
            cost_time = int((time.time() - start_time) * 1000)

            logger.error("=" * 60)
            logger.error("[NODE END] %s - ERROR ✗", self.name)
            logger.error("  Error: %s", str(e))
            logger.error("  Cost time: %dms", cost_time)
            logger.error("=" * 60, exc_info=True)

            # 返回空结果，避免中断整个工作流
            return RecognitionResult(
                engine=self.engine_name,
                node_type=self.node_type,
                raw_data=None,
                cost_time=cost_time,
                metadata={"error": str(e), "node_name": self.name},
            )

    @abstractmethod
    def _recognize(self, image_path: str, **kwargs) -> Any:
        """执行识别（子类实现）

        Args:
            image_path: 图片路径
            **kwargs: 额外参数

        Returns:
            原始识别数据
        """
        pass

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}(name='{self.name}', type='{self.node_type}')>"
        )
