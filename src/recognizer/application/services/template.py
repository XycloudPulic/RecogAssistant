# SPDX-License-Identifier: MIT

"""Template management business service."""

import logging
from typing import Any, Dict, List, Optional

from recognizer.domain.template.template_store import TemplateStore

logger = logging.getLogger(__name__)


class TemplateService:
    """Template management business service (SQLite-based)."""

    @staticmethod
    def generate_from_image(image_path: str) -> dict:
        """Generate and save template from invoice image.

        Note: This is now deprecated. Use the new template system.

        Args:
            image_path: Invoice image path.

        Returns:
            Template information dictionary.
        """
        logger.warning("generate_from_image is deprecated, use new template system")
        return {"error": "This function is deprecated"}

    @staticmethod
    def get_template_list() -> List[Dict[str, Any]]:
        """Get list of all templates."""
        templates = TemplateStore.list_all_templates()
        return [
            {
                "id": t.id,
                "name": t.name,
                "engine": t.engine,
                "parser": t.parser,
                "field_count": t.field_count,
                "is_active": t.is_active,
            }
            for t in templates
        ]

    @staticmethod
    def get_template_detail(template_id: int) -> Optional[Dict[str, Any]]:
        """Get template details.

        Args:
            template_id: Template ID.

        Returns:
            Template information dictionary or None.
        """
        tmpl = TemplateStore.get_by_id(template_id)
        if tmpl is None:
            return None

        return {
            "id": tmpl.id,
            "name": tmpl.name,
            "engine": tmpl.engine,
            "parser": tmpl.parser,
            "field_count": tmpl.field_count,
            "fields": [
                {
                    "field_name": f.field_name,
                    "field_label": f.field_label,
                    "field_type": f.field_type,
                    "parser_config": f.parser_config,
                }
                for f in tmpl.fields
            ],
            "rules": [
                {
                    "rule_type": r.rule_type,
                    "rule_value": r.rule_value,
                    "priority": r.priority,
                }
                for r in tmpl.rules
            ],
        }

    @staticmethod
    def remove_template(template_id: int) -> bool:
        """Delete a template.

        Args:
            template_id: Template ID to delete.

        Returns:
            True if deleted successfully.
        """
        logger.info("Deleting template: %s", template_id)
        return TemplateStore.delete_template(template_id)

    @staticmethod
    def create_template(
        name: str,
        engine: str,
        parser: str,
        fields: List[Dict[str, Any]],
        rules: List[Dict[str, Any]] = None,
        sample_image: str = None,
    ) -> int:
        """Create a new template.

        Args:
            name: Template name
            engine: OCR engine
            parser: Parser type
            fields: Field definitions
            rules: Recognition rules
            sample_image: Sample image path

        Returns:
            New template ID
        """
        logger.info("Creating template: %s", name)
        return TemplateStore.create_template(
            name=name,
            engine=engine,
            parser=parser,
            fields=fields,
            rules=rules,
            sample_image=sample_image,
        )
