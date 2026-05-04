# SPDX-License-Identifier: MIT

"""发票模板存储管理模块"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .database import (
    InvoiceTemplate,
    TemplateField,
    TemplateRule,
    get_db_connection,
    init_database,
)

logger = logging.getLogger(__name__)

_T_TEMPLATES = "legacy_templates"
_T_FIELDS = "legacy_template_fields"
_T_RULES = "legacy_template_rules"


class TemplateStore:
    """SQLite模板存储管理类"""

    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """初始化数据库"""
        if not cls._initialized:
            init_database()
            cls._initialized = True
            logger.info("TemplateStore initialized")

    @classmethod
    def get_by_id(cls, template_id: int) -> Optional[InvoiceTemplate]:
        """根据ID获取模板"""
        cls.initialize()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT * FROM {_T_TEMPLATES} WHERE id = ? AND is_active = 1",
            (template_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        template = InvoiceTemplate.from_row(row)
        template.fields = cls._get_template_fields(template_id)
        template.rules = cls._get_template_rules(template_id)

        conn.close()
        return template

    @classmethod
    def get_by_engine_parser(
        cls, engine: str, parser: str, active_only: bool = True
    ) -> List[InvoiceTemplate]:
        """根据引擎和解析方式获取模板列表"""
        cls.initialize()
        conn = get_db_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute(
                f"SELECT * FROM {_T_TEMPLATES} WHERE engine = ? AND parser = ? AND is_active = 1",
                (engine, parser),
            )
        else:
            cursor.execute(
                f"SELECT * FROM {_T_TEMPLATES} WHERE engine = ? AND parser = ?",
                (engine, parser),
            )

        rows = cursor.fetchall()
        templates = []

        for row in rows:
            template = InvoiceTemplate.from_row(row)
            template.fields = cls._get_template_fields(template.id)
            template.rules = cls._get_template_rules(template.id)
            templates.append(template)

        conn.close()
        return templates

    @classmethod
    def get_templates(
        cls, engine: str = None, parser: str = None, active_only: bool = True
    ) -> List[InvoiceTemplate]:
        """获取模板列表（支持筛选）

        Args:
            engine: OCR引擎（可选）
            parser: 解析器（可选）
            active_only: 是否只获取活动模板

        Returns:
            模板列表
        """
        cls.initialize()

        if engine and parser:
            return cls.get_by_engine_parser(engine, parser, active_only)

        conn = get_db_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute(
                f"SELECT * FROM {_T_TEMPLATES} WHERE is_active = 1 ORDER BY id"
            )
        else:
            cursor.execute(f"SELECT * FROM {_T_TEMPLATES} ORDER BY id")

        rows = cursor.fetchall()
        templates = []

        for row in rows:
            template = InvoiceTemplate.from_row(row)
            template.fields = cls._get_template_fields(template.id)
            template.rules = cls._get_template_rules(template.id)
            templates.append(template)

        conn.close()
        return templates

    @classmethod
    def get_template_fields(cls, template_id: int) -> List[TemplateField]:
        """获取模板的字段列表（公开方法）"""
        return cls._get_template_fields(template_id)

    @classmethod
    def get_template_rules(cls, template_id: int) -> List[TemplateRule]:
        """获取模板的识别规则列表（公开方法）"""
        return cls._get_template_rules(template_id)

    @classmethod
    def detect_template(
        cls, ocr_texts: List[Tuple[str, float]], engine: str, parser: str
    ) -> Optional[InvoiceTemplate]:
        """根据OCR文本检测匹配的发票模板

        Args:
            ocr_texts: OCR识别结果 [(文本, 置信度), ...]
            engine: OCR引擎名称
            parser: 解析器名称

        Returns:
            匹配的模板，如果没有匹配则返回None
        """
        cls.initialize()

        # 获取所有适用的模板
        templates = cls.get_by_engine_parser(engine, parser)

        if not templates:
            logger.warning(
                "No templates found for engine=%s, parser=%s", engine, parser
            )
            return None

        # 按优先级排序规则
        matched_templates = []

        for template in templates:
            if not template.rules:
                # 没有规则的模板作为默认选项
                matched_templates.append((template, 0))
                continue

            # 尝试匹配规则
            best_match = 0
            for rule in sorted(template.rules, key=lambda r: r.priority, reverse=True):
                if rule.rule_type == "keyword":
                    # 关键字匹配
                    if cls._match_keyword(ocr_texts, rule.rule_value):
                        best_match = max(best_match, rule.priority)

                elif rule.rule_type == "regex":
                    # 正则匹配
                    if cls._match_regex(ocr_texts, rule.rule_value):
                        best_match = max(best_match, rule.priority)

            if best_match > 0:
                matched_templates.append((template, best_match))

        if not matched_templates:
            logger.warning("No template matched for OCR texts")
            return None

        # 返回匹配度最高的模板
        matched_templates.sort(key=lambda x: x[1], reverse=True)
        best_template = matched_templates[0][0]

        logger.info(
            "Detected template: %s (engine=%s, parser=%s)",
            best_template.name,
            engine,
            parser,
        )

        return best_template

    @classmethod
    def _match_keyword(cls, ocr_texts: List[Tuple[str, float]], keyword: str) -> bool:
        """关键字匹配"""
        for text, _ in ocr_texts:
            if keyword in text:
                return True
        return False

    @classmethod
    def _match_regex(cls, ocr_texts: List[Tuple[str, float]], pattern: str) -> bool:
        """正则匹配"""
        try:
            compiled = re.compile(pattern)
            for text, _ in ocr_texts:
                if compiled.search(text):
                    return True
        except re.error as e:
            logger.warning("Invalid regex pattern '%s': %s", pattern, e)
        return False

    @classmethod
    def create_template(
        cls,
        name: str,
        engine: str,
        parser: str,
        fields: List[Dict[str, Any]],
        rules: List[Dict[str, Any]] = None,
        sample_image: str = None,
    ) -> int:
        """创建新模板

        Args:
            name: 模板名称
            engine: OCR引擎
            parser: 解析器
            fields: 字段定义列表
            rules: 识别规则列表
            sample_image: 样本图片路径

        Returns:
            新模板ID
        """
        cls.initialize()
        conn = get_db_connection()
        cursor = conn.cursor()

        # 插入模板
        cursor.execute(
            f"""INSERT INTO {_T_TEMPLATES}
               (name, engine, parser, field_count, sample_image)
               VALUES (?, ?, ?, ?, ?)""",
            (name, engine, parser, len(fields), sample_image),
        )
        template_id = cursor.lastrowid

        # 插入字段
        import json

        for i, field_def in enumerate(fields):
            # 确保parser_config是JSON字符串
            parser_config = field_def["parser_config"]
            if isinstance(parser_config, dict):
                parser_config = json.dumps(parser_config)

            cursor.execute(
                f"""INSERT INTO {_T_FIELDS}
                   (template_id, field_name, field_label, field_type,
                    parser_config, validation_rule, order_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    template_id,
                    field_def["field_name"],
                    field_def["field_label"],
                    field_def.get("field_type", "string"),
                    parser_config,
                    field_def.get("validation_rule"),
                    field_def.get("order_index", i),
                ),
            )

        # 插入规则
        if rules:
            for i, rule_def in enumerate(rules):
                cursor.execute(
                    f"""INSERT INTO {_T_RULES}
                       (template_id, rule_type, rule_value, priority)
                       VALUES (?, ?, ?, ?)""",
                    (
                        template_id,
                        rule_def["rule_type"],
                        rule_def["rule_value"],
                        rule_def.get("priority", i),
                    ),
                )

        conn.commit()
        conn.close()

        logger.info("Created template: %s (id=%d)", name, template_id)
        return template_id

    @classmethod
    def delete_template(cls, template_id: int) -> bool:
        """删除模板（软删除）"""
        cls.initialize()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"UPDATE {_T_TEMPLATES} SET is_active = 0 WHERE id = ?", (template_id,)
        )
        affected = cursor.rowcount

        conn.commit()
        conn.close()

        if affected > 0:
            logger.info("Deleted template: id=%d", template_id)

        return affected > 0

    @classmethod
    def list_all_templates(cls) -> List[InvoiceTemplate]:
        """列出所有模板"""
        cls.initialize()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT * FROM {_T_TEMPLATES} WHERE is_active = 1 ORDER BY id")
        rows = cursor.fetchall()

        templates = []
        for row in rows:
            template = InvoiceTemplate.from_row(row)
            template.fields = cls._get_template_fields(template.id)
            template.rules = cls._get_template_rules(template.id)
            templates.append(template)

        conn.close()
        return templates

    @classmethod
    def _get_template_fields(cls, template_id: int) -> List[TemplateField]:
        """获取模板的字段列表"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT * FROM {_T_FIELDS} WHERE template_id = ? ORDER BY order_index",
            (template_id,),
        )
        rows = cursor.fetchall()

        fields = [TemplateField.from_row(row) for row in rows]
        conn.close()
        return fields

    @classmethod
    def _get_template_rules(cls, template_id: int) -> List[TemplateRule]:
        """获取模板的识别规则列表"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT * FROM {_T_RULES} WHERE template_id = ? ORDER BY priority DESC",
            (template_id,),
        )
        rows = cursor.fetchall()

        rules = [TemplateRule.from_row(row) for row in rows]
        conn.close()
        return rules


# 延迟初始化
TemplateStore.initialize()
