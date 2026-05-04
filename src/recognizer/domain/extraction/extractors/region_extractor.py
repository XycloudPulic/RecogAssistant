# SPDX-License-Identifier: MIT

"""区域提取器

根据坐标区域从OCR结果中提取字段值。

适用于需要根据位置区分字段的场景，例如：
- 电子发票的购买方（左侧）和销售方（右侧）
- 表格中的列数据

配置示例：
{
    "x_range": [0.05, 0.50],
    "y_range": [0.15, 0.30],
    "image_size": [2480, 3508],
    "pattern": r"名称[：:\\s]*([^\n(（]+)"
}
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class RegionExtractor(BaseExtractor):
    """区域提取器

    根据相对坐标区域提取字段值。
    支持在区域内进一步使用正则提取。
    """

    @property
    def extractor_type(self) -> str:
        return "region"

    def _do_extract(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """执行区域提取

        Args:
            raw_data: OCR原始数据（必须包含box坐标）
            config: 提取配置

        Returns:
            str: 提取的值
        """
        # 获取区域配置
        x_range = config.get("x_range")
        y_range = config.get("y_range")

        if not x_range or not y_range:
            logger.warning("No x_range or y_range provided in config")
            return ""

        # 获取图片尺寸（用于坐标转换）
        image_size = config.get("image_size")

        # 筛选区域内的文本
        region_texts = self._filter_by_region(raw_data, x_range, y_range, image_size)

        if not region_texts:
            logger.debug("No text found in region")
            return ""

        # 如果提供了正则模式，在区域内进一步提取
        pattern = config.get("pattern")
        if pattern:
            return self._extract_with_pattern(region_texts, pattern, config)

        # 否则返回区域内的第一个文本
        return region_texts[0][0] if region_texts else ""

    def _filter_by_region(
        self,
        raw_data: Any,
        x_range: List[float],
        y_range: List[float],
        image_size: Optional[List[int]] = None,
    ) -> List[Tuple[str, float]]:
        """根据坐标区域筛选文本

        Args:
            raw_data: OCR原始数据
            x_range: X轴相对坐标范围 [min, max]
            y_range: Y轴相对坐标范围 [min, max]
            image_size: 图片尺寸 [width, height]（可选）

        Returns:
            List[Tuple[str, float]]: (文本, 置信度) 列表
        """
        if not isinstance(raw_data, list):
            return []

        result = []
        x_min, x_max = x_range
        y_min, y_max = y_range

        for item in raw_data:
            if not isinstance(item, dict):
                continue

            box = item.get("box")
            if not box or len(box) < 4:
                continue

            text = item.get("text", "")
            confidence = item.get("confidence", 0.0)

            # 获取左上角坐标
            x, y = box[0]

            # 如果提供了图片尺寸，使用相对坐标
            if image_size and len(image_size) == 2:
                rel_x = x / image_size[0]
                rel_y = y / image_size[1]

                if x_min <= rel_x <= x_max and y_min <= rel_y <= y_max:
                    result.append((text, confidence))
            else:
                # 否则假设坐标已经是相对坐标（0-1之间）
                if x_min <= x <= x_max and y_min <= y <= y_max:
                    result.append((text, confidence))

        logger.debug("Found %d texts in region", len(result))
        return result

    def _extract_with_pattern(
        self,
        region_texts: List[Tuple[str, float]],
        pattern: str,
        config: Dict[str, Any],
    ) -> str:
        """在区域文本中使用正则提取

        Args:
            region_texts: 区域内的文本列表
            pattern: 正则模式
            config: 提取配置

        Returns:
            str: 提取的值
        """
        group = config.get("group", 1)

        import re

        for text, confidence in region_texts:
            try:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        value = match.group(group)
                        logger.debug(
                            "Matched in region with confidence %.2f", confidence
                        )
                        return value
                    except IndexError:
                        logger.warning("Group %d not found in pattern", group)
            except re.error as e:
                logger.error("Invalid regex pattern '%s': %s", pattern, e)

        return ""
