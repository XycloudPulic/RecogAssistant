# SPDX-License-Identifier: MIT

"""发票模板解析引擎"""

import logging
from typing import Dict, List, Optional, Tuple

from ..models.invoice import FieldConfidence, InvoiceData
from .database import InvoiceTemplate, TemplateField
from .parsers.base_field_parser import BaseFieldParser, get_parser
from .template_store import TemplateStore

logger = logging.getLogger(__name__)


class TemplateEngine:
    """模板解析引擎

    根据模板定义解析OCR结果，支持多种解析策略
    """

    def __init__(self, engine: str, parser: str):
        """初始化模板引擎

        Args:
            engine: OCR引擎名称（如 'paddleocr', 'ppstructure'）
            parser: 解析器名称（如 'regex', 'region'）
        """
        self.engine = engine
        self.parser = parser
        self.template_store = TemplateStore()
        self._parsers_cache: Dict[str, BaseFieldParser] = {}

    def detect_template(
        self, ocr_result: List[Tuple[str, float]]
    ) -> Optional[InvoiceTemplate]:
        """检测匹配的发票模板

        Args:
            ocr_result: OCR识别结果 [(文本, 置信度), ...]

        Returns:
            匹配的模板，如果没有匹配则返回None
        """
        return self.template_store.detect_template(ocr_result, self.engine, self.parser)

    def parse(
        self,
        image_path: str,
        ocr_result: List[Tuple[str, float]],
        template: InvoiceTemplate,
    ) -> Tuple[InvoiceData, FieldConfidence]:
        """根据模板解析OCR结果

        Args:
            image_path: 图片路径
            ocr_result: OCR识别结果 [(文本, 置信度), ...]
            template: 发票模板

        Returns:
            (InvoiceData, FieldConfidence)
        """
        # 初始化数据对象
        invoice_data = InvoiceData()
        field_confidence = FieldConfidence()

        if not template.fields:
            logger.warning("Template '%s' has no fields defined", template.name)
            return invoice_data, field_confidence

        # 按顺序解析每个字段
        for field in sorted(template.fields, key=lambda f: f.order_index):
            value, confidence = self._parse_field(image_path, ocr_result, field)

            # 设置字段值
            self._set_field_value(invoice_data, field, value)

            # 设置置信度
            self._set_field_confidence(field_confidence, field, confidence)

        return invoice_data, field_confidence

    def _parse_field(
        self, image_path: str, ocr_result: List[Tuple[str, float]], field: TemplateField
    ) -> Tuple[str, float]:
        """解析单个字段

        Args:
            image_path: 图片路径
            ocr_result: OCR识别结果
            field: 字段定义

        Returns:
            (字段值, 置信度)
        """
        parser_type = field.parser_config.get("type", "regex")

        # 获取或创建解析器
        if parser_type not in self._parsers_cache:
            self._parsers_cache[parser_type] = get_parser(parser_type)

        parser = self._parsers_cache[parser_type]

        try:
            if parser_type == "coordinate":
                # 坐标解析需要图片
                import cv2

                image = cv2.imread(image_path)
                raw_data = (image, self.engine)
            else:
                # 其他解析器使用OCR结果
                raw_data = ocr_result

            value = parser.parse(raw_data, field.parser_config)

            # 简单的置信度估算
            confidence = 0.95 if value else 0.0

            return value, confidence

        except Exception as e:
            logger.warning("Failed to parse field '%s': %s", field.field_name, e)
            return "", 0.0

    def _set_field_value(
        self, invoice_data: InvoiceData, field: TemplateField, value: str
    ) -> None:
        """设置发票数据字段值"""
        field_name = field.field_name

        # 映射到InvoiceData的属性
        if hasattr(invoice_data, field_name):
            setattr(invoice_data, field_name, value)
        else:
            logger.debug("Field '%s' not found in InvoiceData", field_name)

    def _set_field_confidence(
        self, field_confidence: FieldConfidence, field: TemplateField, confidence: float
    ) -> None:
        """设置字段置信度"""
        field_name = field.field_name

        if hasattr(field_confidence, field_name):
            setattr(field_confidence, field_name, confidence)


class MultiTemplateEngine:
    """多模板引擎 - 尝试多个模板解析"""

    def __init__(self, engine: str, parser: str):
        self.engine = engine
        self.parser = parser
        self.template_engine = TemplateEngine(engine, parser)

    def parse_with_fallback(
        self, image_path: str, ocr_result: List[Tuple[str, float]]
    ) -> Tuple[InvoiceData, FieldConfidence, Optional[InvoiceTemplate]]:
        """尝试多个模板解析，优先使用匹配的模板

        Args:
            image_path: 图片路径
            ocr_result: OCR识别结果

        Returns:
            (InvoiceData, FieldConfidence, matched_template)
        """
        # 1. 尝试自动检测模板
        template = self.template_engine.detect_template(ocr_result)

        if template:
            logger.info("Using detected template: %s", template.name)
            result = self.template_engine.parse(image_path, ocr_result, template)
            return result[0], result[1], template

        # 2. 尝试所有可用模板
        templates = TemplateStore.get_by_engine_parser(self.engine, self.parser)

        for template in templates:
            try:
                logger.debug("Trying template: %s", template.name)
                result = self.template_engine.parse(image_path, ocr_result, template)

                # 检查是否有有效结果
                if result[0].invoice_number or result[0].amount:
                    logger.info("Template '%s' produced valid result", template.name)
                    return result[0], result[1], template

            except Exception as e:
                logger.debug("Template '%s' failed: %s", template.name, e)
                continue

        # 3. 返回空结果
        logger.warning("No template produced valid result")
        return InvoiceData(), FieldConfidence(), None


def create_template_engine(engine: str, parser: str) -> TemplateEngine:
    """工厂函数：创建模板引擎"""
    return TemplateEngine(engine, parser)


def create_multi_engine(engine: str, parser: str) -> MultiTemplateEngine:
    """工厂函数：创建多模板引擎"""
    return MultiTemplateEngine(engine, parser)
