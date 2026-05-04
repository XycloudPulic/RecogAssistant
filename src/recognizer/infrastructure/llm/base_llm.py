# SPDX-License-Identifier: MIT

"""LLM基类

定义LLM客户端的统一接口。
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """LLM客户端基类

    所有LLM客户端必须继承此类。
    支持：
    - 文本对话
    - 视觉识别（图片+提示词）
    - JSON格式输出
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """LLM提供商名称

        Returns:
            如 "openai", "qwen", "claude"
        """
        pass

    @abstractmethod
    def chat(self, prompt: str, **kwargs) -> str:
        """文本对话

        Args:
            prompt: 提示词
            **kwargs: 额外参数

        Returns:
            LLM响应文本
        """
        pass

    @abstractmethod
    def vision_chat(self, image_path: str, prompt: str, **kwargs) -> str:
        """视觉对话（图片+提示词）

        Args:
            image_path: 图片路径
            prompt: 提示词
            **kwargs: 额外参数

        Returns:
            LLM响应文本（通常是JSON格式）
        """
        pass

    def parse_json_response(self, response: str) -> Optional[dict]:
        """解析JSON响应

        Args:
            response: LLM响应文本

        Returns:
            解析后的字典，失败返回None
        """
        import json
        import re

        try:
            # 尝试提取JSON代码块
            json_match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
                json_str = response

            # 解析JSON
            result = json.loads(json_str)
            logger.debug("JSON parsed successfully")
            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", str(e))
            logger.debug("Raw response: %s", response[:200])
            return None
        except Exception as e:
            logger.error("Unexpected error parsing JSON: %s", str(e))
            return None
