# SPDX-License-Identifier: MIT

"""OCR引擎抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Tuple


class BaseOCREngine(ABC):
    """OCR引擎抽象基类

    所有OCR引擎必须继承此类并实现recognize方法。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """OCR引擎唯一标识

        Returns:
            引擎名称，如 'paddle', 'tesseract', 'easyocr'
        """
        pass

    @abstractmethod
    def recognize(self, image_path: str) -> List[Tuple[str, float]]:
        """执行OCR识别

        Args:
            image_path: 图片路径

        Returns:
            识别结果列表 [(text, confidence), ...]
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
