# SPDX-License-Identifier: MIT

r"""正则表达式提取器

使用正则表达式从OCR文本中提取字段值。

配置示例：
{
    "pattern": r"发票号码[：:\s]*(\d{20,})",
    "group": 1,
    "use_full_text": True,
    "fallback_patterns": [
        r"No[.．]?\s*(\d{20,})",
        r"号码[：:\s]*(\d{20,})"
    ]
}
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class RegexExtractor(BaseExtractor):
    """正则表达式提取器

    支持单行匹配和全文匹配两种模式。
    支持多个备用正则模式。
    """

    @property
    def extractor_type(self) -> str:
        return "regex"

    def _do_extract(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """执行正则提取

        Args:
            raw_data: OCR原始数据
            config: 提取配置

        Returns:
            str: 提取的值
        """
        # 获取配置
        pattern = config.get("pattern")
        if not pattern:
            logger.warning("No pattern provided in config")
            return ""

        group = config.get("group", 1)
        use_full_text = config.get("use_full_text", False)
        fallback_patterns = config.get("fallback_patterns", [])

        # 提取文本
        if use_full_text:
            # 全文匹配模式
            full_text = self._extract_full_text(raw_data)
            return self._match_pattern(full_text, pattern, group, fallback_patterns)
        else:
            # 逐行匹配模式
            text_list = self._extract_text_list(raw_data)
            return self._match_line_by_line(
                text_list, pattern, group, fallback_patterns
            )

    def _match_pattern(
        self, text: str, pattern: str, group: int, fallback_patterns: List[str]
    ) -> str:
        """在文本中匹配正则模式

        Args:
            text: 要匹配的文本
            pattern: 主正则模式
            group: 捕获组索引
            fallback_patterns: 备用正则模式列表

        Returns:
            str: 匹配的值
        """
        # 尝试主模式
        value = self._try_match(text, pattern, group)
        if value:
            return value

        # 尝试备用模式
        for fallback in fallback_patterns:
            value = self._try_match(text, fallback, group)
            if value:
                logger.debug("Matched with fallback pattern: %s", fallback)
                return value

        logger.debug("No pattern matched")
        return ""

    def _match_line_by_line(
        self,
        text_list: List[str],
        pattern: str,
        group: int,
        fallback_patterns: List[str],
    ) -> str:
        """逐行匹配正则模式

        Args:
            text_list: 文本行列表
            pattern: 主正则模式
            group: 捕获组索引
            fallback_patterns: 备用正则模式列表

        Returns:
            str: 匹配的值
        """
        # 逐行尝试主模式
        for line in text_list:
            value = self._try_match(line, pattern, group)
            if value:
                return value

        # 逐行尝试备用模式
        for fallback in fallback_patterns:
            for line in text_list:
                value = self._try_match(line, fallback, group)
                if value:
                    return value

        return ""

    def _try_match(self, text: str, pattern: str, group: int) -> Optional[str]:
        """尝试用正则模式匹配文本

        Args:
            text: 文本
            pattern: 正则模式
            group: 捕获组索引

        Returns:
            Optional[str]: 匹配的值，如果失败返回None
        """
        try:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return match.group(group)
                except IndexError:
                    logger.warning("Group %d not found in pattern", group)
                    return None
        except re.error as e:
            logger.error("Invalid regex pattern '%s': %s", pattern, e)

        return None
