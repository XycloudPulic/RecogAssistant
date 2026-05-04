# SPDX-License-Identifier: MIT

"""OCR引擎工厂"""

from typing import Dict, List, Type

from recognizer.infrastructure.ocr.base_ocr_engine import BaseOCREngine


class OCREngineFactory:
    """OCR引擎工厂

    管理所有OCR识别引擎（PaddleOCR、PP-Structure等）
    """

    _registry: Dict[str, Type[BaseOCREngine]] = {}

    @classmethod
    def register(cls, engine_type: str, engine_class: Type[BaseOCREngine]) -> None:
        """注册OCR引擎

        Args:
            engine_type: 引擎类型标识
            engine_class: 引擎类
        """
        cls._registry[engine_type] = engine_class

    @classmethod
    def create(cls, engine_type: str) -> BaseOCREngine:
        """创建OCR引擎实例

        Args:
            engine_type: 引擎类型标识

        Returns:
            OCR引擎实例

        Raises:
            ValueError: 未知引擎类型
        """
        if engine_type not in cls._registry:
            raise ValueError(f"未知OCR引擎类型: {engine_type}")
        return cls._registry[engine_type]()

    @classmethod
    def create_all(cls) -> List[BaseOCREngine]:
        """创建所有已注册的OCR引擎实例

        Returns:
            OCR引擎实例列表
        """
        return [cls.create(t) for t in cls._registry]

    @classmethod
    def list_types(cls) -> List[str]:
        """列出所有已注册的OCR引擎类型

        Returns:
            引擎类型列表
        """
        return list(cls._registry.keys())
