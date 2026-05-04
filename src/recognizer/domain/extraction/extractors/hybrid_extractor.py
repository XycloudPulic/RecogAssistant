# SPDX-License-Identifier: MIT

"""混合提取器

结合多种提取策略，提供主策略和备用策略。

适用于复杂场景，例如：
- 主策略：区域提取（更准确）
- 备用策略：正则提取（兜底）

配置示例：
{
    "primary_strategy": "region",
    "primary_config": {
        "x_range": [0.05, 0.50],
        "y_range": [0.15, 0.30]
    },
    "fallback_strategy": "regex",
    "fallback_config": {
        "pattern": r"名称[：:\\s]*([^\n(（]+)",
        "group": 1
    }
}
"""

import logging
from typing import Any, Dict

from .base_extractor import BaseExtractor
from .regex_extractor import RegexExtractor
from .region_extractor import RegionExtractor

logger = logging.getLogger(__name__)


class HybridExtractor(BaseExtractor):
    """混合提取器

    按优先级尝试多种提取策略，返回第一个成功的结果。
    """

    def __init__(self):
        """初始化混合提取器"""
        self.extractors = {
            "regex": RegexExtractor(),
            "region": RegionExtractor(),
        }

    @property
    def extractor_type(self) -> str:
        return "hybrid"

    def _do_extract(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """执行混合提取

        Args:
            raw_data: OCR原始数据
            config: 提取配置

        Returns:
            str: 提取的值
        """
        # 获取主策略
        primary_strategy = config.get("primary_strategy", "regex")
        primary_config = config.get("primary_config", {})

        # 获取备用策略
        fallback_strategy = config.get("fallback_strategy")
        fallback_config = config.get("fallback_config", {})

        # 尝试主策略
        logger.debug("Trying primary strategy: %s", primary_strategy)
        value = self._try_strategy(raw_data, primary_strategy, primary_config)

        if value:
            logger.debug("Primary strategy succeeded")
            return value

        # 尝试备用策略
        if fallback_strategy:
            logger.debug("Trying fallback strategy: %s", fallback_strategy)
            value = self._try_strategy(raw_data, fallback_strategy, fallback_config)

            if value:
                logger.debug("Fallback strategy succeeded")
                return value

        logger.debug("All strategies failed")
        return ""

    def _try_strategy(
        self, raw_data: Any, strategy_type: str, config: Dict[str, Any]
    ) -> str:
        """尝试指定的提取策略

        Args:
            raw_data: OCR原始数据
            strategy_type: 策略类型
            config: 策略配置

        Returns:
            str: 提取的值
        """
        try:
            extractor = self.extractors.get(strategy_type)
            if not extractor:
                logger.warning("Unknown strategy type: %s", strategy_type)
                return ""

            return extractor.extract(raw_data, config)

        except Exception as e:
            logger.error("Strategy '%s' failed: %s", strategy_type, e, exc_info=True)
            return ""
