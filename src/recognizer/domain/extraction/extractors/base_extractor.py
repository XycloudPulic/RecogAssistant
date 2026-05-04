# SPDX-License-Identifier: MIT

"""提取器基类

定义所有字段提取器必须遵循的接口规范。

设计原则：
1. 单一职责：每个提取器只负责一种提取策略
2. 配置驱动：通过配置控制提取行为
3. 可扩展：支持自定义提取策略
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """字段提取器基类

    所有提取器必须继承此类。
    提取器的类型可以是：
    - RegexExtractor: 正则表达式提取
    - RegionExtractor: 区域坐标提取
    - HybridExtractor: 混合策略提取
    - TableExtractor: 表格提取
    - KeyValueExtractor: 键值对提取
    """

    @property
    @abstractmethod
    def extractor_type(self) -> str:
        """提取器类型标识

        Returns:
            'regex' / 'region' / 'hybrid' / 'table' / 'key_value'
        """
        pass

    def extract(self, raw_data: Any, config: Dict[str, Any]) -> str:
        r"""执行字段提取（模板方法模式）

        Args:
            raw_data: OCR识别的原始数据
                格式：[
                    {
                        "text": "发票号码：25322000000507969537",
                        "confidence": 0.98,
                        "box": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    },
                    ...
                ]
            config: 提取器配置
                例如：{
                    "pattern": r"发票号码[：:\s]*(\d+)",
                    "group": 1,
                    "use_full_text": True
                }

        Returns:
            str: 提取的字段值，如果提取失败返回空字符串
        """
        logger.debug("Extracting with %s extractor", self.extractor_type)

        try:
            # 执行提取
            value = self._do_extract(raw_data, config)

            # 清理结果
            if value:
                value = self._clean_value(value)

            # 验证结果
            if config.get("validation"):
                if not self._validate(value, config["validation"]):
                    logger.warning("Validation failed for extracted value: %s", value)
                    return ""

            logger.debug("Extracted value: %s", value)
            return value or ""

        except Exception as e:
            logger.error("Extraction failed: %s", str(e), exc_info=True)
            return ""

    @abstractmethod
    def _do_extract(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """执行实际提取（子类实现）

        Args:
            raw_data: 原始识别数据
            config: 提取配置

        Returns:
            str: 提取的值
        """
        pass

    def _clean_value(self, value: str) -> str:
        """清理提取的值

        Args:
            value: 原始提取值

        Returns:
            str: 清理后的值
        """
        if not value:
            return ""

        # 去除首尾空白
        value = value.strip()

        # 去除常见的标点符号
        value = value.rstrip(".,;:，。；：")

        return value

    def _validate(self, value: str, validation_rule: str) -> bool:
        """验证提取的值

        Args:
            value: 提取的值
            validation_rule: 验证规则（正则表达式）

        Returns:
            bool: 是否通过验证
        """
        import re

        try:
            return bool(re.match(validation_rule, value))
        except re.error as e:
            logger.warning("Invalid validation rule: %s", e)
            return True  # 验证规则错误时，默认通过

    def _extract_text_list(self, raw_data: Any) -> List[str]:
        """从原始数据中提取文本列表

        Args:
            raw_data: 原始识别数据

        Returns:
            List[str]: 文本列表
        """
        if isinstance(raw_data, list):
            return [item.get("text", "") for item in raw_data if isinstance(item, dict)]
        return []

    def _extract_full_text(self, raw_data: Any) -> str:
        """从原始数据中提取完整文本

        Args:
            raw_data: 原始识别数据

        Returns:
            str: 完整文本（用换行符连接）
        """
        text_list = self._extract_text_list(raw_data)
        return "\n".join(text_list)

    def _extract_with_confidence(self, raw_data: Any) -> List[Tuple[str, float]]:
        """从原始数据中提取文本和置信度

        Args:
            raw_data: 原始识别数据

        Returns:
            List[Tuple[str, float]]: (文本, 置信度) 列表
        """
        if isinstance(raw_data, list):
            result = []
            for item in raw_data:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    conf = item.get("confidence", 0.0)
                    result.append((text, conf))
            return result
        return []

    def __repr__(self):
        return f"<{self.__class__.__name__}(type='{self.extractor_type}')>"
