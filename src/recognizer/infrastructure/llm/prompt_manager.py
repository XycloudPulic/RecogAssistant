# SPDX-License-Identifier: MIT

"""提示词模板管理

管理和加载LLM识别的提示词模板。
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PromptTemplateManager:
    """提示词模板管理器

    负责：
    - 加载提示词模板（JSON格式）
    - 按发票类型匹配模板
    - 动态渲染提示词
    """

    def __init__(self, prompt_dir: Optional[str] = None):
        """初始化提示词模板管理器

        Args:
            prompt_dir: 提示词模板目录（默认使用infrastructure/llm/prompts）
        """
        if prompt_dir:
            self.prompt_dir = Path(prompt_dir)
        else:
            # 默认路径
            self.prompt_dir = Path(__file__).parent / "prompts"

        self.templates: Dict[str, dict] = {}

        # 加载所有模板
        self._load_all_templates()

        logger.info(
            "PromptTemplateManager initialized: %d templates loaded",
            len(self.templates),
        )

    def _load_all_templates(self):
        """加载所有提示词模板"""
        if not self.prompt_dir.exists():
            logger.warning("Prompt directory not found: %s", self.prompt_dir)
            return

        for json_file in self.prompt_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    template = json.load(f)

                template_name = json_file.stem
                self.templates[template_name] = template

                logger.info("Loaded prompt template: %s", template_name)

            except Exception as e:
                logger.error("Failed to load template %s: %s", json_file, str(e))

    def get_template(self, template_name: str) -> Optional[dict]:
        """获取提示词模板

        Args:
            template_name: 模板名称（如 "electronic_invoice"）

        Returns:
            模板字典，未找到返回None
        """
        return self.templates.get(template_name)

    def render_prompt(self, template_name: str, **kwargs) -> Optional[str]:
        """渲染提示词

        Args:
            template_name: 模板名称
            **kwargs: 模板变量

        Returns:
            渲染后的提示词，未找到返回None
        """
        template = self.get_template(template_name)
        if not template:
            logger.warning("Template not found: %s", template_name)
            return None

        # 获取user_prompt模板
        user_prompt = template.get("user_prompt", "")

        # 替换变量
        try:
            rendered = user_prompt.format(**kwargs)
            return rendered
        except KeyError as e:
            logger.error("Missing template variable: %s", str(e))
            return user_prompt  # 返回原始模板

    def get_system_prompt(self, template_name: str) -> Optional[str]:
        """获取系统提示词

        Args:
            template_name: 模板名称

        Returns:
            系统提示词
        """
        template = self.get_template(template_name)
        if not template:
            return None

        return template.get("system_prompt")

    def get_response_schema(self, template_name: str) -> Optional[dict]:
        """获取响应JSON Schema

        Args:
            template_name: 模板名称

        Returns:
            JSON Schema字典
        """
        template = self.get_template(template_name)
        if not template:
            return None

        return template.get("response_format", {}).get("schema")

    def list_templates(self) -> list:
        """列出所有可用模板

        Returns:
            模板名称列表
        """
        return list(self.templates.keys())


# 全局单例
_prompt_manager = None


def get_prompt_manager() -> PromptTemplateManager:
    """获取提示词模板管理器单例

    Returns:
        PromptTemplateManager实例
    """
    global _prompt_manager

    if _prompt_manager is None:
        _prompt_manager = PromptTemplateManager()

    return _prompt_manager
