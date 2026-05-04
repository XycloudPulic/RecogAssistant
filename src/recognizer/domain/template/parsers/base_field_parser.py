# SPDX-License-Identifier: MIT

"""字段解析器基类"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseFieldParser(ABC):
    """字段解析器基类"""

    @property
    @abstractmethod
    def parser_type(self) -> str:
        """解析器类型标识"""
        ...

    @abstractmethod
    def parse(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """解析字段值

        Args:
            raw_data: 原始数据（OCR结果）
            config: 解析配置

        Returns:
            解析后的字段值
        """
        ...

    @staticmethod
    def clean_value(value: str, cleaners: List[str]) -> str:
        """清洗字段值

        Args:
            value: 原始值
            cleaners: 清洗规则列表

        Returns:
            清洗后的值
        """
        if not value:
            return ""

        for cleaner in cleaners:
            if cleaner == "strip":
                value = value.strip()
            elif cleaner == "remove_spaces":
                value = value.replace(" ", "").replace("\u3000", "")
            elif cleaner == "remove_newlines":
                value = value.replace("\n", "").replace("\r", "")
            elif cleaner == "upper":
                value = value.upper()
            elif cleaner == "lower":
                value = value.lower()
            elif cleaner == "remove_prefix":
                # 移除常见前缀
                prefixes = ["¥", "￥", "RMB", "rmb", "元", "人民币"]
                for prefix in prefixes:
                    if value.startswith(prefix):
                        value = value[len(prefix) :]
                        break

        return value.strip()

    @staticmethod
    def validate_number(value: str) -> Optional[float]:
        """验证并转换数字"""
        if not value:
            return None

        # 移除常见符号
        cleaned = value.replace(",", "").replace("¥", "").replace("￥", "").strip()

        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def validate_date(value: str) -> Optional[str]:
        """验证并标准化日期格式"""
        if not value:
            return None

        import re
        from datetime import datetime

        # 匹配各种日期格式
        patterns = [
            (r"(\d{4})[年](\d{1,2})[月](\d{1,2})[日]", "%Y-%m-%d"),
            (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", "%Y-%m-%d"),
            (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, value)
            if match:
                try:
                    dt = datetime.strptime("".join(match.groups()), fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        return value  # 无法解析时返回原值


class RegexFieldParser(BaseFieldParser):
    """正则解析器 - 通过正则表达式匹配关键字提取字段"""

    @property
    def parser_type(self) -> str:
        return "regex"

    def parse(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """通过正则表达式从OCR文本中提取字段值

        Args:
            raw_data: OCR结果，格式为 List[Tuple[str, float]]
            config: 解析配置 {
                "pattern": 正则表达式,
                "group": 捕获组索引，默认1,
                "cleaners": 清洗规则列表
            }

        Returns:
            提取的字段值
        """
        import re

        pattern = config.get("pattern", "")
        group = config.get("group", 1)
        cleaners = config.get("cleaners", [])

        if not pattern:
            logger.warning("RegexFieldParser: No pattern provided")
            return ""

        # 尝试编译正则表达式
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            logger.warning("Invalid regex pattern '%s': %s", pattern, e)
            return ""

        # 从OCR结果中查找匹配
        if isinstance(raw_data, list):
            for text, _ in raw_data:
                match = compiled.search(text)
                if match:
                    try:
                        value = match.group(group)
                        return self.clean_value(value, cleaners)
                    except IndexError:
                        logger.warning(
                            "Regex group %d not found in pattern '%s'", group, pattern
                        )
                        continue

        return ""

    def parse_by_line(
        self, raw_data: List[Tuple[str, float]], config: Dict[str, Any]
    ) -> str:
        """逐行正则匹配（用于跨行字段）"""
        import re

        pattern = config.get("pattern", "")
        cleaners = config.get("cleaners", [])

        if not pattern:
            return ""

        try:
            compiled = re.compile(pattern)
        except re.error:
            return ""

        # 合并所有文本行
        all_text = "\n".join([text for text, _ in raw_data])

        match = compiled.search(all_text)
        if match:
            return self.clean_value(match.group(1), cleaners)

        return ""


class CoordinateFieldParser(BaseFieldParser):
    """坐标区域解析器 - 根据坐标裁剪图片区域进行OCR"""

    @property
    def parser_type(self) -> str:
        return "coordinate"

    def parse(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """从图片指定坐标区域提取字段值

        Args:
            raw_data: 格式为 (image, ocr_engine) 或 (image_path, ocr_engine)
            config: 解析配置 {
                "x1": 左上x坐标,
                "y1": 左上y坐标,
                "x2": 右下x坐标,
                "y2": 右下y坐标,
                "relative": 是否使用相对坐标(0-1),
                "cleaners": 清洗规则列表
            }

        Returns:
            提取的字段值
        """
        import cv2

        from recognizer.infrastructure.ocr.paddle_ocr_engine import paddle_ocr

        x1 = config.get("x1", 0)
        y1 = config.get("y1", 0)
        x2 = config.get("x2", 0)
        y2 = config.get("y2", 0)
        relative = config.get("relative", False)
        cleaners = config.get("cleaners", [])

        if not isinstance(raw_data, tuple) or len(raw_data) < 2:
            logger.warning("CoordinateFieldParser: Invalid raw_data format")
            return ""

        image_or_path = raw_data[0]

        # 读取图片
        if isinstance(image_or_path, str):
            image = cv2.imread(image_or_path)
        else:
            image = image_or_path

        if image is None:
            logger.warning("CoordinateFieldParser: Failed to read image")
            return ""

        h, w = image.shape[:2]

        # 计算实际坐标
        if relative:
            x1, y1 = int(x1 * w), int(y1 * h)
            x2, y2 = int(x2 * w), int(y2 * h)

        # 确保坐标在有效范围内
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            logger.warning("CoordinateFieldParser: Invalid coordinates")
            return ""

        # 裁剪区域
        region = image[y1:y2, x1:x2]

        # 对区域进行OCR识别
        try:
            results = paddle_ocr(region)
            if results:
                # 合并所有识别结果
                texts = [text for text, _ in results]
                value = " ".join(texts)
                return self.clean_value(value, cleaners)
        except Exception as e:
            logger.warning("CoordinateFieldParser: OCR failed: %s", e)

        return ""


class KeyValueFieldParser(BaseFieldParser):
    """键值对解析器 - 匹配"键:值"格式"""

    @property
    def parser_type(self) -> str:
        return "key_value"

    def parse(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """从键值对格式中提取字段值

        Args:
            raw_data: OCR结果，格式为 List[Tuple[str, float]]
            config: 解析配置 {
                "key": 键名,
                "separator": 分隔符，默认[：:],
                "cleaners": 清洗规则列表
            }

        Returns:
            提取的字段值
        """
        import re

        key = config.get("key", "")
        separators = config.get("separator", r"[：:]")
        cleaners = config.get("cleaners", [])

        if not key:
            logger.warning("KeyValueFieldParser: No key provided")
            return ""

        # 构建匹配模式: 键名 + 分隔符 + 值
        pattern = rf"{re.escape(key)}\s*{separators}\s*(.+?)(?:\n|$)"
        compiled = re.compile(pattern, re.MULTILINE)

        if isinstance(raw_data, list):
            # 合并所有文本
            all_text = "\n".join([text for text, _ in raw_data])

            match = compiled.search(all_text)
            if match:
                return self.clean_value(match.group(1), cleaners)

        return ""


class TableFieldParser(BaseFieldParser):
    """表格字段解析器 - 从表格结构中提取字段"""

    @property
    def parser_type(self) -> str:
        return "table"

    def parse(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """从表格结构中提取字段值

        Args:
            raw_data: 表格数据，格式为 List[List[str]]
            config: 解析配置 {
                "row": 行索引,
                "col": 列索引,
                "cleaners": 清洗规则列表
            }

        Returns:
            提取的字段值
        """
        row_idx = config.get("row", 0)
        col_idx = config.get("col", 0)
        cleaners = config.get("cleaners", [])

        if not isinstance(raw_data, list) or not raw_data:
            return ""

        try:
            if row_idx < len(raw_data):
                row = raw_data[row_idx]
                if col_idx < len(row):
                    return self.clean_value(row[col_idx], cleaners)
        except (IndexError, TypeError) as e:
            logger.warning(
                "TableFieldParser: Failed to parse cell [%d][%d]: %s",
                row_idx,
                col_idx,
                e,
            )

        return ""


class CompositeFieldParser(BaseFieldParser):
    """组合字段解析器 - 组合多个解析器的结果"""

    @property
    def parser_type(self) -> str:
        return "composite"

    def parse(self, raw_data: Any, config: Dict[str, Any]) -> str:
        """组合多个解析器结果

        Args:
            raw_data: OCR结果
            config: 解析配置 {
                "parsers": [
                    {"type": "regex", ...},
                    {"type": "key_value", ...}
                ],
                "separator": 连接符，默认" "
            }

        Returns:
            组合后的字段值
        """
        from .key_value_field_parser import KeyValueFieldParser
        from .regex_field_parser import RegexFieldParser

        parsers_map = {
            "regex": RegexFieldParser(),
            "key_value": KeyValueFieldParser(),
        }

        separator = config.get("separator", " ")
        parser_configs = config.get("parsers", [])

        results = []
        for parser_config in parser_configs:
            parser_type = parser_config.get("type", "")
            parser = parsers_map.get(parser_type)

            if parser:
                value = parser.parse(raw_data, parser_config)
                if value:
                    results.append(value)

        return separator.join(results)


# 解析器注册表
PARSER_REGISTRY = {
    "regex": RegexFieldParser,
    "coordinate": CoordinateFieldParser,
    "key_value": KeyValueFieldParser,
    "table": TableFieldParser,
    "composite": CompositeFieldParser,
}


def get_parser(parser_type: str) -> BaseFieldParser:
    """获取指定类型的解析器"""
    parser_class = PARSER_REGISTRY.get(parser_type)
    if parser_class:
        return parser_class()
    logger.warning("Unknown parser type '%s', using RegexFieldParser", parser_type)
    return RegexFieldParser()
