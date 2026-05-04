# SPDX-License-Identifier: MIT

"""LLM视觉识别节点

基于大语言模型（GPT-4V、Qwen-VL等）的发票识别节点。

职责：
- 加载图片
- 加载提示词模板
- 调用LLM API进行视觉识别
- 解析JSON输出
- 返回RecognitionResult

架构设计：
- 继承BaseRecognitionNode
- node_type = "llm"
- engine_name = "gpt4v" / "qwen_vl" 等
- 识别与提取分离（只识别，不提取）
"""

import logging
from typing import Any, Optional

from recognizer.common.config.settings import Settings
from recognizer.domain.recognition.nodes.base_node import BaseRecognitionNode
from recognizer.infrastructure.llm.base_llm import BaseLLMClient
from recognizer.infrastructure.llm.prompt_manager import (
    get_prompt_manager,
)

logger = logging.getLogger(__name__)


class LLMRecognitionNode(BaseRecognitionNode):
    """LLM视觉识别节点

    使用大语言模型（如GPT-4V、Qwen-VL）进行发票识别。

    工作流程：
    1. 加载图片
    2. 根据发票类型加载提示词模板
    3. 调用LLM API（图片+提示词）
    4. 解析JSON响应
    5. 返回RecognitionResult

    优势：
    - 无需OCR，直接理解图片
    - 支持复杂版面
    - 高准确率
    - 灵活配置提示词
    """

    order = 20  # 执行顺序（在OCR之后）

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        prompt_template: str = "electronic_invoice",
        *,
        configured_name: str | None = None,
        **kwargs,
    ):
        """初始化LLM识别节点

        Args:
            llm_client: LLM客户端实例（默认使用配置中的）
            prompt_template: 提示词模板名称（默认"electronic_invoice"）
            **kwargs: 额外参数
        """
        super().__init__(configured_name=configured_name)
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.prompt_manager = get_prompt_manager()

        # 从配置加载LLM客户端
        if self.llm_client is None:
            self.llm_client = self._create_llm_client()

        logger.info(
            "LLMRecognitionNode initialized: llm=%s, template=%s",
            self.llm_client.name if self.llm_client else "none",
            prompt_template,
        )

    @property
    def name(self) -> str:
        """节点名称"""
        return self._resolved_name("llm_vision")

    @property
    def node_type(self) -> str:
        """节点类型"""
        return "llm"

    @property
    def engine_name(self) -> str:
        """引擎名称"""
        return self.llm_client.name if self.llm_client else "unknown"

    def _recognize(self, image_path: str, **kwargs) -> Any:
        """执行LLM识别

        Args:
            image_path: 图片路径
            **kwargs: 额外参数
                - invoice_type: 发票类型（用于选择提示词模板）
                - custom_prompt: 自定义提示词（覆盖模板）

        Returns:
            dict: LLM识别结果
                {
                    "fields": {           # 提取的字段
                        "invoice_number": "...",
                        "amount": "...",
                        ...
                    },
                    "confidence": 0.95,   # 置信度
                    "raw_response": "...", # LLM原始JSON响应
                    "prompt_template": "electronic_invoice"  # 使用的模板
                }
        """
        try:
            # 1. 获取提示词模板
            template_name = kwargs.get("invoice_type", self.prompt_template)
            custom_prompt = kwargs.get("custom_prompt")

            if custom_prompt:
                # 使用自定义提示词
                prompt = custom_prompt
                logger.info("  Using custom prompt")
            else:
                # 使用模板提示词（system 提示词可由 vision_chat **kwargs 扩展时再接入）
                prompt = self.prompt_manager.render_prompt(template_name)

                if not prompt:
                    logger.warning(
                        "  ⚠ Template not found: %s, using default", template_name
                    )
                    prompt = self._get_default_prompt()

            # 2. 调用LLM
            logger.info("  Calling LLM: %s", self.llm_client.name)
            logger.info("  Image: %s", image_path)

            response = self.llm_client.vision_chat(image_path=image_path, prompt=prompt)

            # 3. 解析JSON响应
            fields = self.llm_client.parse_json_response(response)

            if fields is None:
                logger.error("  ✗ Failed to parse LLM response as JSON")
                fields = {}

            # 4. 构建结果
            result = {
                "fields": fields,
                "confidence": 0.95,  # LLM通常有高置信度
                "raw_response": response,
                "prompt_template": template_name,
                "text_lines": [],  # LLM不返回文本行，但保持接口一致
            }

            logger.info(
                "  ✓ LLM recognition completed: %d fields extracted", len(fields)
            )

            return result

        except Exception as e:
            logger.error("  ✗ LLM recognition failed: %s", str(e), exc_info=True)
            raise

    def _create_llm_client(self) -> BaseLLMClient:
        """创建LLM客户端

        Returns:
            BaseLLMClient: LLM客户端实例
        """
        provider = Settings.get("llm.provider", "openai").lower()

        if provider == "openai":
            from recognizer.infrastructure.llm.openai_client import OpenAIClient

            return OpenAIClient(
                api_key=Settings.get("llm.openai.api_key"),
                model=Settings.get("llm.openai.model", "gpt-4-vision-preview"),
                max_tokens=Settings.get("llm.openai.max_tokens", 2000),
                temperature=Settings.get("llm.openai.temperature", 0.0),
            )

        elif provider == "qwen":
            # TODO: 实现Qwen客户端
            logger.warning("Qwen LLM client not implemented yet")
            raise NotImplementedError("Qwen LLM client not implemented")

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def _get_default_prompt(self) -> str:
        """获取默认提示词

        Returns:
            默认提示词字符串
        """
        return """请识别这张发票图片，提取以下字段并以JSON格式返回：

{
  "invoice_number": "发票号码",
  "invoice_date": "开票日期",
  "buyer_name": "购买方名称",
  "seller_name": "销售方名称",
  "amount": "金额",
  "tax": "税额",
  "total_amount": "价税合计"
}

如果某个字段无法识别，请返回空字符串。"""
