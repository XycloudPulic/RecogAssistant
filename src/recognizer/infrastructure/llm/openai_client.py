# SPDX-License-Identifier: MIT

"""OpenAI GPT-4V客户端

实现OpenAI的视觉识别能力。
"""

import base64
import logging
from typing import Optional

from openai import OpenAI

from recognizer.common.config.settings import Settings

from .base_llm import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT-4V客户端

    使用GPT-4 Vision进行发票识别。
    支持：
    - 图片理解
    - JSON格式输出
    - 高准确率
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-vision-preview",
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ):
        """初始化OpenAI客户端

        Args:
            api_key: OpenAI API密钥（默认从配置读取）
            model: 模型名称
            max_tokens: 最大token数
            temperature: 温度（0.0=确定性输出）
        """
        self.api_key = api_key or Settings.get("llm.openai.api_key", "")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # 初始化OpenAI客户端
        self.client = OpenAI(api_key=self.api_key)

        logger.info(
            "OpenAIClient initialized: model=%s, max_tokens=%d", model, max_tokens
        )

    @property
    def name(self) -> str:
        """LLM提供商名称"""
        return "openai"

    def chat(self, prompt: str, **kwargs) -> str:
        """文本对话

        Args:
            prompt: 提示词
            **kwargs: 额外参数

        Returns:
            LLM响应文本
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error("OpenAI chat failed: %s", str(e))
            raise

    def vision_chat(self, image_path: str, prompt: str, **kwargs) -> str:
        """视觉对话（图片+提示词）

        Args:
            image_path: 图片路径
            prompt: 提示词
            **kwargs: 额外参数

        Returns:
            LLM响应文本（JSON格式）
        """
        try:
            # 编码图片
            image_base64 = self._encode_image(image_path)

            # 调用GPT-4V
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error("OpenAI vision chat failed: %s", str(e))
            raise

    def _encode_image(self, image_path: str) -> str:
        """将图片编码为Base64

        Args:
            image_path: 图片路径

        Returns:
            Base64编码的图片字符串
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
