# SPDX-License-Identifier: MIT

"""模板管理器

负责模板的匹配和配置获取。

职责：
1. 根据OCR结果匹配最佳模板
2. 获取模板的字段配置和识别规则
3. 提供模板查询接口

使用示例：
    from recognizer.extraction import TemplateManager

    manager = TemplateManager()
    template = manager.detect_template(ocr_data)
    fields = manager.get_template_fields(template.id)
"""

import json
import logging
import re
from typing import Any, List, Optional

from recognizer.domain.extraction.engine import FieldExtractionEngine
from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    Template,
    TemplateField,
    TemplateRule,
)
from recognizer.infrastructure.persistence.recognition_runtime.repositories.runtime_template_repository import (
    TemplateRepository,
)

logger = logging.getLogger(__name__)


class TemplateManager:
    """模板管理器

    负责模板匹配和配置管理。
    """

    def __init__(self):
        """初始化模板管理器"""
        self.template_repo = TemplateRepository()
        logger.info("TemplateManager initialized")

    def detect_template(
        self, ocr_data: Any, category: str = None
    ) -> Optional[Template]:
        """检测匹配的发票模板

        Args:
            ocr_data: OCR识别结果
                格式：[
                    {"text": "电子发票（普通发票）", "confidence": 0.99},
                    ...
                ]
            category: 发票分类（可选，用于缩小匹配范围）
                如：'electronic', 'paper', 'transport'

        Returns:
            Optional[Template]: 匹配的模板，如果没有匹配则返回None
        """
        logger.info(
            "Detecting template for OCR data (%d items)",
            len(ocr_data) if isinstance(ocr_data, list) else 0,
        )

        # 1. 获取候选模板
        candidates = self._get_candidates(category)
        if not candidates:
            logger.warning("No candidate templates found")
            return None

        # 2. 提取OCR文本
        ocr_texts = self._extract_texts(ocr_data)
        full_text = "\n".join(ocr_texts)

        # 3. 为每个模板打分
        scored_templates = []
        for template in candidates:
            score = self._calculate_score(template, ocr_texts, full_text)
            if score > 0:
                scored_templates.append((template, score))
                logger.debug("Template '%s' score: %d", template.name, score)

        # 4. 返回最高分模板
        if scored_templates:
            scored_templates.sort(key=lambda x: x[1], reverse=True)
            best_template = scored_templates[0][0]
            logger.info(
                "Matched template: %s (score: %d)",
                best_template.name,
                scored_templates[0][1],
            )
            return best_template

        logger.info("No template matched")
        return None

    def _get_candidates(self, category: str = None) -> List[Template]:
        """获取候选模板

        Args:
            category: 发票分类

        Returns:
            List[Template]: 候选模板列表
        """
        if category:
            return self.template_repo.get_by_category(category)
        else:
            return self.template_repo.get_all(enabled_only=True)

    def _extract_texts(self, ocr_data: Any) -> List[str]:
        """从OCR数据中提取文本列表

        Args:
            ocr_data: OCR识别结果

        Returns:
            List[str]: 文本列表
        """
        return FieldExtractionEngine._iter_text_lines(ocr_data)

    def _calculate_score(
        self, template: Template, ocr_texts: List[str], full_text: str
    ) -> int:
        """计算模板匹配得分

        Args:
            template: 模板对象
            ocr_texts: OCR文本列表
            full_text: 完整文本

        Returns:
            int: 匹配得分
        """
        score = 0

        # 获取模板规则
        rules = self.template_repo.get_rules(template.id)

        for rule in rules:
            rule_score = 0

            if rule.rule_type == "keyword":
                # 关键词匹配
                rule_score = self._match_keywords(rule.rule_value, full_text)

            elif rule.rule_type == "regex":
                # 正则匹配
                rule_score = self._match_regex(rule.rule_value, full_text)

            elif rule.rule_type == "layout":
                # 版面匹配（暂未实现）
                rule_score = 0

            # 累加得分（考虑权重）
            score += rule_score * rule.weight

        return score

    def _match_keywords(self, rule_value: str, full_text: str) -> int:
        """关键词匹配

        Args:
            rule_value: 规则值（JSON格式的关键词列表）
            full_text: 完整文本

        Returns:
            int: 匹配得分（匹配的关键词数量）
        """
        try:
            keywords = json.loads(rule_value)
            if not isinstance(keywords, list):
                return 0

            match_count = 0
            for keyword in keywords:
                if keyword in full_text:
                    match_count += 1

            return match_count

        except json.JSONDecodeError as e:
            logger.warning("Invalid keyword rule value: %s", e)
            return 0

    def _match_regex(self, rule_value: str, full_text: str) -> int:
        """正则匹配

        Args:
            rule_value: 规则值（正则表达式）
            full_text: 完整文本

        Returns:
            int: 匹配得分（0或1）
        """
        try:
            if re.search(rule_value, full_text):
                return 1
            return 0
        except re.error as e:
            logger.warning("Invalid regex rule value: %s", e)
            return 0

    def get_template_fields(self, template_id: int) -> List[TemplateField]:
        """获取模板的字段配置

        Args:
            template_id: 模板ID

        Returns:
            List[TemplateField]: 字段配置列表
        """
        return self.template_repo.get_fields(template_id)

    def get_template_rules(self, template_id: int) -> List[TemplateRule]:
        """获取模板的识别规则

        Args:
            template_id: 模板ID

        Returns:
            List[TemplateRule]: 识别规则列表
        """
        return self.template_repo.get_rules(template_id)

    def get_template_by_code(self, code: str) -> Optional[Template]:
        """根据代码获取模板

        Args:
            code: 模板代码

        Returns:
            Optional[Template]: 模板对象
        """
        return self.template_repo.get_by_code(code)
