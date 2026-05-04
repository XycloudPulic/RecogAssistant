# SPDX-License-Identifier: MIT

"""运行期模板等实体的 SQLAlchemy 仓储（持久化基础设施 · ORM 侧）。

领域/应用通过本模块访问 ``runtime_templates`` / 相关表，不直接写 SQL。
``admin_configuration.repositories`` 中面向后台 ``templates`` 等配置表的持久化与这里 **不同子域**（运行期 ``runtime_*`` vs 管理端配置表）。

- ``TemplateRepository``：ORM 访问 ``runtime_templates``、``runtime_template_*``。
- 文件内其余仓储类为占位/遗留，尚未接表。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    Template,
    TemplateField,
    TemplateRule,
)
from recognizer.infrastructure.persistence.recognition_runtime.session import (
    get_db_session,
)

logger = logging.getLogger(__name__)


# ==================== 模板数据仓库 ====================


class TemplateRepository:
    """模板数据仓库

    提供发票模板的完整CRUD操作
    """

    def __init__(self, db: Session = None):
        """初始化

        Args:
            db: 数据库会话（可选，如果不提供会自动创建）
        """
        self.db = db

    def _get_db(self) -> Session:
        """获取数据库会话

        注意：这个方法返回的是一个上下文管理器，需要用 with 语句使用
        """
        if self.db:
            # 如果已经提供了db会话，返回一个包含它的上下文管理器
            from contextlib import contextmanager

            @contextmanager
            def _use_existing_db():
                yield self.db

            return _use_existing_db()
        else:
            # 否则创建新的会话
            return get_db_session()

    # ==================== 查询操作 ====================

    def get_by_id(self, template_id: int) -> Optional[Template]:
        """根据ID获取模板

        Args:
            template_id: 模板ID

        Returns:
            Template对象或None
        """
        with self._get_db() as db:
            tmpl = db.query(Template).filter(Template.id == template_id).first()
            if tmpl is not None:
                # Ensure returned entity isn't expired after session closes.
                db.expunge(tmpl)
            return tmpl

    def get_by_code(self, code: str) -> Optional[Template]:
        """根据代码获取模板

        Args:
            code: 模板代码（唯一标识）

        Returns:
            Template对象或None
        """
        with self._get_db() as db:
            tmpl = db.query(Template).filter(Template.code == code).first()
            if tmpl is not None:
                # Ensure returned entity isn't expired after session closes.
                db.expunge(tmpl)
            return tmpl

    def get_by_category(self, category: str) -> List[Template]:
        """根据分类获取模板列表

        Args:
            category: 发票分类（electronic/paper/transport）

        Returns:
            Template列表
        """
        with self._get_db() as db:
            templates = (
                db.query(Template)
                .filter(Template.category == category, Template.enabled.is_(True))
                .order_by(Template.priority)
                .all()
            )
            for t in templates:
                db.expunge(t)
            return templates

    def get_all(self, enabled_only: bool = True) -> List[Template]:
        """获取所有模板

        Args:
            enabled_only: 是否只返回启用的模板

        Returns:
            Template列表
        """
        with self._get_db() as db:
            query = db.query(Template)
            if enabled_only:
                query = query.filter(Template.enabled.is_(True))
            templates = query.order_by(Template.priority).all()
            # 让对象脱离会话，避免DetachedInstanceError
            for template in templates:
                db.expunge(template)
            return templates

    def get_fields(self, template_id: int) -> List[TemplateField]:
        """获取模板的字段配置

        Args:
            template_id: 模板ID

        Returns:
            TemplateField列表
        """
        with self._get_db() as db:
            fields = (
                db.query(TemplateField)
                .filter(TemplateField.template_id == template_id)
                .order_by(TemplateField.order_index)
                .all()
            )
            for f in fields:
                db.expunge(f)
            return fields

    def get_rules(self, template_id: int) -> List[TemplateRule]:
        """获取模板的识别规则

        Args:
            template_id: 模板ID

        Returns:
            TemplateRule列表
        """
        with self._get_db() as db:
            rules = (
                db.query(TemplateRule)
                .filter(TemplateRule.template_id == template_id)
                .all()
            )
            for r in rules:
                db.expunge(r)
            return rules

    # ==================== 创建操作 ====================

    def create(self, template_data: Dict[str, Any]) -> int:
        """创建新模板

        Args:
            template_data: 模板数据字典
                {
                    "name": "增值税电子普通发票",
                    "code": "electronic_normal",
                    "engine": "paddleocr",
                    "category": "electronic",
                    "fields": [...],
                    "rules": [...]
                }

        Returns:
            新模板的ID
        """
        with self._get_db() as db:
            # 1. 创建模板主记录
            template = Template(
                name=template_data["name"],
                code=template_data["code"],
                engine=template_data.get("engine", "paddleocr"),
                category=template_data.get("category"),
                priority=template_data.get("priority", 100),
                enabled=template_data.get("enabled", True),
                description=template_data.get("description"),
            )
            db.add(template)
            db.flush()  # 获取template.id

            # 2. 创建字段
            for field_data in template_data.get("fields", []):
                field = TemplateField(
                    template_id=template.id,
                    field_name=field_data["field_name"],
                    field_label=field_data.get("field_label"),
                    field_type=field_data.get("field_type", "string"),
                    extractor_type=field_data["extractor_type"],
                    extractor_config=field_data["extractor_config"],
                    required=field_data.get("required", False),
                    validation_rule=field_data.get("validation_rule"),
                    order_index=field_data.get("order_index", 0),
                )
                db.add(field)

            # 3. 创建规则
            for rule_data in template_data.get("rules", []):
                rule = TemplateRule(
                    template_id=template.id,
                    rule_type=rule_data["rule_type"],
                    rule_value=rule_data["rule_value"],
                    weight=rule_data.get("weight", 1),
                )
                db.add(rule)

            logger.info("Created template: %s (id=%d)", template.name, template.id)
            return template.id

    # ==================== 更新操作 ====================

    def update(self, template_id: int, update_data: Dict[str, Any]) -> bool:
        """更新模板

        Args:
            template_id: 模板ID
            update_data: 更新数据

        Returns:
            是否更新成功
        """
        with self._get_db() as db:
            template = db.query(Template).filter(Template.id == template_id).first()
            if not template:
                logger.warning("Template not found: %d", template_id)
                return False

            # 更新模板主记录
            for key, value in update_data.items():
                if key in [
                    "name",
                    "engine",
                    "category",
                    "priority",
                    "enabled",
                    "description",
                ]:
                    setattr(template, key, value)

            template.updated_at = datetime.utcnow()

            logger.info("Updated template: %d", template_id)
            return True

    def toggle_enabled(self, template_id: int) -> bool:
        """切换模板启用状态

        Args:
            template_id: 模板ID

        Returns:
            是否成功
        """
        with self._get_db() as db:
            template = db.query(Template).filter(Template.id == template_id).first()
            if not template:
                return False

            template.enabled = not template.enabled
            template.updated_at = datetime.utcnow()

            logger.info(
                "Toggled template %d: enabled=%s", template_id, template.enabled
            )
            return True

    # ==================== 删除操作 ====================

    def delete(self, template_id: int) -> bool:
        """删除模板（级联删除字段和规则）

        Args:
            template_id: 模板ID

        Returns:
            是否删除成功
        """
        with self._get_db() as db:
            template = db.query(Template).filter(Template.id == template_id).first()
            if not template:
                logger.warning("Template not found: %d", template_id)
                return False

            db.delete(template)
            logger.info("Deleted template: %d", template_id)
            return True

    # ==================== 批量操作 ====================

    def batch_create(self, templates_data: List[Dict[str, Any]]) -> List[int]:
        """批量创建模板

        Args:
            templates_data: 模板数据列表

        Returns:
            新模板ID列表
        """
        ids = []
        for template_data in templates_data:
            template_id = self.create(template_data)
            ids.append(template_id)
        return ids


# ==================== 识别结果数据仓库 ====================


class RecognitionRepository:
    """识别结果数据仓库

    用于存储和查询识别结果（可选功能，用于审计和分析）
    """

    def save_result(self, result_data: Dict[str, Any]) -> int:
        """保存识别结果

        Args:
            result_data: 识别结果数据

        Returns:
            记录ID
        """
        # TODO: 实现识别结果存储
        logger.info("Recognition result saved: %s", result_data.get("engine"))
        return 0

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取识别历史

        Args:
            limit: 返回数量限制

        Returns:
            识别历史列表
        """
        # TODO: 实现识别历史查询
        return []


# ==================== 发票数据仓库 ====================


class InvoiceRepository:
    """发票数据仓库

    用于存储和查询识别后的发票数据（可选功能，用于业务系统）
    """

    def save_invoice(self, invoice_data: Dict[str, Any]) -> int:
        """保存发票数据

        Args:
            invoice_data: 发票数据

        Returns:
            记录ID
        """
        # TODO: 实现发票数据存储
        logger.info("Invoice saved: %s", invoice_data.get("invoice_number"))
        return 0

    def get_by_number(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """根据发票号码查询

        Args:
            invoice_number: 发票号码

        Returns:
            发票数据或None
        """
        # TODO: 实现发票查询
        return None
